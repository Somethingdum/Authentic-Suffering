"""Implementation of turn/cognition.py."""
from __future__ import annotations

import dataclasses

FALLBACK_KIND = {"grammar_fail": "grammar_fail", "schema_fail": "schema_fail", "empty": "grammar_fail",
                 "timeout": "timeout", "lane_error": "lane_down", "cancelled": "timeout",
                 "hallucinated_choice": "hallucinated_ref", "hallucinated_target": "hallucinated_ref",
                 "empty_speech": "schema_fail", "speech_too_long": "schema_fail", "unsupported_pace": "schema_fail",
                 "hallucinated_expression": "hallucinated_ref", "bad_inscription": "schema_fail",
                 "bad_consultation": "schema_fail"}
REPAIRABLE = ("grammar_fail", "schema_fail", "empty", "hallucinated_choice", "hallucinated_target", "empty_speech",
              "speech_too_long", "unsupported_pace", "hallucinated_expression", "bad_inscription", "bad_consultation")


def _schema(packet, consult=True):
    from ..lanes.schemas import cognition_schema
    kinds = list(packet.consult_kinds) if consult else []
    subj = [h for h in packet.handles if h[:1] == "P"] + [h for h in packet.handles if h[:1] == "S"] if kinds else []
    return cognition_schema([a.handle for a in packet.affordances], [e.handle for e in packet.entities],
                            consult_kinds=kinds, families=list(packet.families) if kinds else [], subject_handles=subj)


def cognition_request(config, packet, lod, lane, *, reaction, turn_index):
    from ..contracts.common import LOD, CallClass, Lane
    from ..lanes.requests import build_request
    cc = CallClass.ACTOR_REACTION if reaction else CallClass.ACTOR_COGNITION
    if lod == LOD.HOT:
        reg = config.hot_cognition
        structured = config.lanes[Lane.A].structured_with_thinking == "supported" or not reg.thinking
        return build_request(config, cc, turn_index=turn_index, actor_id=packet.actor_id, context=packet,
                             json_schema=_schema(packet) if structured else None, regime=reg, lane=lane, p=packet)
    return build_request(config, cc, turn_index=turn_index, actor_id=packet.actor_id, context=packet,
                         json_schema=_schema(packet), lane=lane, p=packet)


def _read(packet, aff, resp, lod, reaction, second):
    # REPLY-01 -> ('intent', Intent) | ('consult', Consultation) | ('fail', kind)
    from ..action.intent import IntentError, to_intent
    from ..contracts.mind import ActorReplyV2
    from ..mind.consult import check
    if resp.parse_status != "ok":
        return "fail", resp.parse_status
    try:
        reply = ActorReplyV2.model_validate(resp.parsed)
    except Exception:  # noqa: BLE001 — a reply that does not validate is a schema failure
        return "fail", "schema_fail"
    if reply.kind == "consultation":
        if second or check(packet, reply.consultation) is not None:
            return "fail", "bad_consultation"
        return "consult", reply.consultation
    it = to_intent(packet, aff, reply.action, lod=lod, source="model", reaction=reaction)
    if isinstance(it, IntentError):
        return "fail", ("empty_speech" if it.kind == "empty" else it.kind)
    return "intent", it


def consequential(tx, actor_id, affordances, turn_index, answered):
    # HOLD-02
    return bool(asks_for(tx, actor_id, turn_index, answered)) or bool(getattr(affordances, "threats", []))


async def decide(tx, session, plan, affs, turn_index, at, *, reaction, answered=frozenset(), calls_ok=True):
    # Returns {actor_id: Intent} for every actor in plan.lod but those held in place (HOLD-01).
    from ..action.intent import plan_continuation
    from ..audit.log import repair as log_repair
    from ..contracts.common import LOD
    from ..contracts.events import Event, EventType
    from ..contracts.mind import ActorReplyV2
    from ..lanes.requests import repair_request
    from ..lanes.scheduler import Job, run_jobs
    from ..mind.consult import answer as consult_answer
    from ..mind.packet import build_packet
    from ..narration.lint import check_line
    from .cognition import DecisionHeld
    cfg = session.config
    numbers = tx.rules.style
    defs = {d.id: d for d in tx.canon.all("affordance")}
    out = {}
    st = {}

    def job(a, pkt):
        lod = plan.lod[a]
        req = cognition_request(cfg, pkt, lod, plan.lane[a], reaction=reaction, turn_index=turn_index)
        est = cfg.rules.scheduler.estimated_call_s["actor_cognition_hot" if lod == LOD.HOT else "actor_cognition_warm"]
        return req, Job(job_id=a, call_class=req.call_class, request=req, output_model=ActorReplyV2,
                        lane_pref=plan.lane[a], est_s=est)

    jobs = []
    for a in sorted(plan.lod):
        if plan.lod[a] == LOD.COLD:
            continue
        pkt = build_packet(tx, a, plan.lod[a], affs[a], turn_index, at, reaction=reaction)
        req, j = job(a, pkt)
        st[a] = {"pkt": pkt, "req": req, "repair": False}
        jobs.append(j)
    results = await run_jobs(session.client, jobs) if jobs else {}

    async def repair(a, error_text, raw):
        s_ = st[a]
        s_["repair"] = True
        rq = repair_request(cfg, s_["req"], {"raw": raw, "error": error_text}, s_["pkt"], _schema(s_["pkt"], consult=False))
        resp = await session.client.call(rq, ActorReplyV2)
        kind, val = _read(s_["pkt"], affs[a], resp, plan.lod[a], reaction, second=True)
        return (val, None) if kind == "intent" else (None, val if kind == "fail" else "bad_consultation")

    def hold(a, kind):
        if consequential(tx, a, affs[a], turn_index, answered):
            raise DecisionHeld(a, kind)
        it = plan_continuation(tx, a, affs[a], at, turn_index, accepted_only=True)
        path = "continued" if it is not None else "held"
        tx.commit_event(Event(type=EventType.DEGRADED_FALLBACK, writer="turn.pipeline", at=at, turn_index=turn_index, actor_id=a,
                              payload={"actor_id": a, "reason": kind, "path": path}))
        log_repair(tx, FALLBACK_KIND.get(kind, "degraded"), 6, "LANE-06", {"actor_id": a, "reason": kind, "path": path},
                   turn_index, at)
        return dataclasses.replace(it, source="fallback") if it is not None else None

    async def settle(a, kind, val, resp):
        """A read answer -> Intent | None (held) | 'consult'."""
        if kind == "intent":
            return val
        if kind == "consult":
            return "consult"
        if val in REPAIRABLE and not st[a]["repair"]:
            it2, _why = await repair(a, resp.error or val, resp.raw or resp.text)
            if it2 is not None:
                log_repair(tx, FALLBACK_KIND.get(val, "degraded"), 6, "LANE-06", {"actor_id": a, "reason": val}, turn_index, at,
                           repaired=True)
                return it2
        return hold(a, val)

    consulting = []
    for a in sorted(plan.lod):
        if plan.lod[a] == LOD.COLD:
            out[a] = plan_continuation(tx, a, affs[a], at, turn_index)
            continue
        kind, val = _read(st[a]["pkt"], affs[a], results[a], plan.lod[a], reaction, second=False)
        got = await settle(a, kind, val, results[a])
        if got == "consult":
            consulting.append((a, val))
        elif got is not None:
            out[a] = got
    # REPLY-02: the one consultation, answered from the same snapshot, then the second call
    if consulting:
        jobs2 = []
        for a, c in consulting:
            done = consult_answer(tx, st[a]["pkt"], affs[a], c, defs, turn_index, at)
            pkt2 = build_packet(tx, a, plan.lod[a], affs[a], turn_index, at, reaction=reaction, consulted=done)
            req2, j2 = job(a, pkt2)
            st[a].update(pkt=pkt2, req=req2)
            jobs2.append(j2)
        results2 = await run_jobs(session.client, jobs2)
        for a, _c in consulting:
            kind, val = _read(st[a]["pkt"], affs[a], results2[a], plan.lod[a], reaction, second=True)
            got = await settle(a, kind, val, results2[a])
            if got is not None and got != "consult":
                out[a] = got
    # ECHO-02: one repair if the decision's repair is unspent; a failed one keeps the original words
    for a in sorted(out):
        it = out[a]
        if a not in st or it is None or it.source != "model" or it.speech is None:
            continue
        hits = check_line(tx, it.speech.text, numbers)
        if not hits:
            continue
        if not st[a]["repair"]:
            it2, _why = await repair(a, "Do not repeat these phrases the other person used: " + "; ".join(sorted(hits)),
                                     it.speech.text)
            if it2 is not None and (it2.speech is None or not check_line(tx, it2.speech.text, numbers)):
                log_repair(tx, "echo_reject", 6, "ECHO-02", {"actor_id": a, "ngrams": sorted(hits)}, turn_index, at, repaired=True)
                out[a] = it2
                continue
        log_repair(tx, "echo_reject", 6, "ECHO-02", {"actor_id": a, "ngrams": sorted(hits)}, turn_index, at)
    _compel(tx, out, affs, at, turn_index)
    return out


def _compel(tx, out, affs, at, turn_index):
    """P10: the wet strain's week-3 compulsion — an involuntary offer of the bottle in hand (never
    the PC)."""
    from ..contracts.events import Event, EventType
    from ..mind.affordance import BoundAffordance
    from ..physical.bodies import stages
    from ..physical.space import point_distance
    pcr = tx.query_one("SELECT value FROM meta WHERE key='pc_actor_id'")
    pc = pcr[0] if pcr else None
    R = tx.rules.infected
    for a in sorted(out):
        if a == pc or not any(st.compulsion >= 3 for _pw, st in stages(tx, a)):
            continue
        item = None
        for slot in ("hand_l", "hand_r"):
            r = tx.query_one("SELECT item_id, def_ref FROM items WHERE holder_body=? AND holder_slot=?", (a, slot))
            if r and tx.canon.get(r[1]).kind == "water":
                item = r[0]
                break
        if item is None:
            continue
        last = tx.query_one("SELECT MAX(at) FROM events WHERE type='INVOLUNTARY' AND actor_id=? "
                            "AND json_extract(payload,'$.kind')='compulsion'", (a,))[0]
        if last is not None and at - last < R.compulsion_cooldown_min * 60_000:
            continue
        here = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (a,))[0]
        near = []
        for r in tx.query("SELECT b.body_id FROM bodies b JOIN positions q ON q.body_id=b.body_id WHERE q.place_id=? "
                          "AND b.alive=1 AND b.kind='human' AND b.body_id != ?", (here, a)):
            d = point_distance(tx, a, r[0])
            if d is not None and d <= 1.5:
                near.append((d, r[0]))
        if not near:
            continue
        who = sorted(near)[0][1]
        d = tx.canon.find("affordance", "give_item")
        iname = tx.canon.get(tx.query_one("SELECT def_ref FROM items WHERE item_id=?", (item,))[0]).name
        fill = lambda s: s.replace("{item}", iname).replace("{target}", "someone")  # noqa: E731
        o = BoundAffordance(def_id=d.id, verb=d.verb, label=fill(d.label), ui_label=fill(d.ui_label), target_id=who,
                            item_id=item, est_duration_s=d.duration.base_s, noise_db=d.noise_db, check=d.check,
                            tags=tuple(d.tags))
        tx.commit_event(Event(type=EventType.INVOLUNTARY, writer="turn.pipeline", at=at, turn_index=turn_index, actor_id=a,
                              payload={"actor_id": a, "kind": "compulsion", "pathway": "wet", "item_id": item,
                                       "target_id": who}))
        out[a] = dataclasses.replace(out[a], bound=o, speech=None, manner="", goal="", private_reason="", source="reflex")


ASK_FORMS = ("request", "order", "demand", "threat")


def perceived_entities(tx, actor_id, turn_index):
    out = {}
    for r in tx.query("SELECT subject_id, known_name, description FROM acquaintance WHERE holder_id=? ORDER BY subject_id", (actor_id,)):
        if r[1]:
            out.setdefault(r[1].lower(), r[0])
        if r[2]:
            out.setdefault(r[2].lower(), r[0])
    pl = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (actor_id,))[0]
    for r in tx.query("SELECT anchor_id, name FROM anchors WHERE place_id=? ORDER BY anchor_id", (pl,)):
        out.setdefault(r[1].lower(), r[0])
    for r in tx.query("SELECT portal_id, name FROM portals WHERE place_a=? OR place_b=? ORDER BY portal_id", (pl, pl)):
        out.setdefault(r[1].lower(), r[0])
    items = [r[0] for r in tx.query("SELECT DISTINCT source_id FROM percept_log WHERE holder_id=? AND turn_index=? AND source_id LIKE 'itm_%' "
                                    "ORDER BY source_id", (actor_id, turn_index))]
    items += [r[0] for r in tx.query("SELECT item_id FROM items WHERE holder_body=? ORDER BY item_id", (actor_id,))]
    for i in items:
        r = tx.query_one("SELECT def_ref FROM items WHERE item_id=?", (i,))
        if r:
            out.setdefault(tx.canon.get(r[0]).name.lower(), i)
    return out


def asks_for(tx, actor_id, turn_index, answered):
    """Speech percepts of this turn addressed to the actor, heard at EXACT or PARTIAL with words, not
    yet answered — what its packet shows it was asked before it decides."""
    import json as _j
    out = []
    for p in tx.query("SELECT p.*, e.actor_id AS speaker FROM percept_log p JOIN events e ON e.event_id=p.event_id "
                      "WHERE p.holder_id=? AND p.turn_index=? AND p.channel='speech' AND p.fidelity IN ('exact','partial') "
                      "ORDER BY p.at, p.percept_id", (actor_id, turn_index)):
        p = dict(p)
        det = _j.loads(p["detail"])
        if det.get("addressed_to_me") and det.get("words") and (actor_id, p["event_id"]) not in answered:
            p["detail"] = det
            out.append(p)
    return out


def record_responses(tx, intents, affs, asks, turn_index, wave_at, first_seq):
    # After stage 8: how each mind answered the asks it had heard before deciding (WILL-05..11).
    # Returns [(actor_id, speech_event_id, ResponseClass value or 'not_an_ask')].
    from ..contracts.common import ResponseClass
    from ..mind import firewall
    from ..mind.perception import norm_text
    out = []
    for a in sorted(asks):
        it = intents.get(a)
        if it is None:
            continue
        for p in asks[a]:
            det = p["detail"]
            words = det["words"]
            form = firewall.classify_form(words, weapon_pointed_at_receiver=bool(det.get("armed_at_me")))
            standing = firewall.classify_standing(tx, p["speaker"], a, words)
            eff = firewall.effective_form(form, standing)
            if eff.value not in ASK_FORMS:
                out.append((a, p["event_id"], "not_an_ask"))
                continue
            sig = firewall.request_signature(words, p["speaker"], a, perceived_entities(tx, a, turn_index))
            block = any(r.def_id == sig.split(":")[0] and r.gate == "moral" for r in affs[a].rejected) if a in affs else False
            rc = tx.query_one("SELECT resolve_cur FROM actors WHERE actor_id=?", (a,))[0]
            drained = tx.query_one("SELECT 1 FROM events WHERE type='RESOLVE_CHANGE' AND actor_id=? AND turn_index=? "
                                   "AND json_extract(payload,'$.delta') < 0", (a, turn_index)) is not None
            resp = firewall.classify_response(sig, it.bound, it.speech.text if it.speech else None, rc, eff,
                                              entrenched_block=block, resolve_drained_this_turn=drained)
            out.append((a, p["event_id"], resp.value))
            if resp in (ResponseClass.REFUSAL, ResponseClass.ENTRENCHED_REFUSAL):
                rel = tx.query_one("SELECT trust, fear FROM relationships WHERE from_id=? AND to_id=?", (a, p["speaker"]))
                if resp == ResponseClass.ENTRENCHED_REFUSAL:
                    reason = next(r.gate for r in affs[a].rejected if r.def_id == sig.split(":")[0] and r.gate == "moral")
                elif rel is not None and rel[1] >= 2:
                    reason = "fear"
                elif rel is None or rel[0] <= -1:
                    reason = "distrust"
                else:
                    reason = "cost"
                firewall.record_refusal(tx, a, p["speaker"], sig, norm_text(words), reason, [p["event_id"]], it.private_reason[:200],
                                        resp == ResponseClass.ENTRENCHED_REFUSAL, wave_at, turn_index, p["event_id"])
            elif resp == ResponseClass.FALSE_COMPLIANCE:
                sp = tx.query_one("SELECT event_id FROM events WHERE type='SPEECH' AND actor_id=? AND seq > ? ORDER BY seq LIMIT 1", (a, first_seq))
                if sp is not None:
                    firewall.record_lie(tx, a, p["speaker"], sig, it.speech.text, sp[0], wave_at, turn_index)
    return out
