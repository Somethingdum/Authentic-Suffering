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
                            consult_kinds=kinds, families=list(packet.families) if kinds else [], subject_handles=subj,
                            gesture_handles=[g.handle for g in packet.gestures],
                            attention_handles=[f.handle for f in packet.attention_points])


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


async def decide(tx, session, plan, affs, turn_index, at, *, reaction, answered=frozenset(), calls_ok=True, audits=None):
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
    # 1b PORT-05: the targeted portrayal pre-check (D-07), before the barrier
    from ..audit import portrayal
    prechecked = set()
    for a in sorted(out):
        it = out[a]
        if a not in st or it is None or it.source != "model":
            continue
        why = portrayal.high_stakes(tx, a, it, turn_index, answered)
        if why is None:
            continue
        prechecked.add(a)

        async def regen(err, raw, a=a):
            it2, _why = await repair(a, err, raw)
            return it2
        out[a] = await portrayal.precheck(tx, session.client, cfg, a, st[a]["pkt"], st[a]["req"], it, why,
                                          None if st[a]["repair"] else regen, turn_index, at)
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
    await _snap(tx, out, affs, at, turn_index, plan, st, repair)
    if audits is not None:   # PORT-06: what the retrospective audit may judge
        for a in sorted(out):
            if a in st and out[a] is not None and out[a].source == "model":
                audits.append(portrayal.Judged(a, plan.lod[a], st[a]["pkt"], st[a]["req"], out[a], a in prechecked))
    return out


def _urge_act(tx, a, at):
    """W1: (stage, compulsion, act, item, target, def_id) or None — the first act at hand, and whether
    the gap has passed."""
    import math as _m
    from ..physical.bodies import stages
    from ..physical.space import point_distance
    R = tx.rules.infected
    st = next((s for pw, s in stages(tx, a) if pw == "wet" and s.compulsion >= 2), None)
    if st is None:
        return None
    exp = tx.query_one("SELECT exposed_at FROM infections WHERE body_id=? AND pathway='wet'", (a,))[0]
    h = max((at - exp) / 3_600_000, 1.0)
    gap = max(R.compulsion_min_gap_min, R.compulsion_cooldown_min * 336 / h)
    last = tx.query_one("SELECT MAX(at) FROM events WHERE type='INVOLUNTARY' AND actor_id=? "
                        "AND json_extract(payload,'$.kind') IN ('compulsion','urge')", (a,))[0]
    if last is not None and at - last < gap * 60_000:
        return None
    here = tx.query_one("SELECT place_id, x_m, y_m FROM positions WHERE body_id=?", (a,))

    def near(asleep):
        out = []
        for r in tx.query("SELECT b.body_id, b.awareness FROM bodies b JOIN positions q ON q.body_id=b.body_id "
                          "WHERE q.place_id=? AND b.alive=1 AND b.kind='human' AND b.body_id != ?", (here[0], a)):
            if asleep and r[1] != "asleep":
                continue
            d = point_distance(tx, a, r[0])
            if d is not None and d <= 1.5:
                out.append((d, r[0]))
        return sorted(out)[0][1] if out else None

    sl = near(True)
    if sl:
        return st, "mouth", None, sl, "spit_in_mouth"
    hands = []
    for slot in ("hand_l", "hand_r"):
        r = tx.query_one("SELECT item_id, def_ref FROM items WHERE holder_body=? AND holder_slot=?", (a, slot))
        if r:
            hands.append((r[0], tx.canon.get(r[1]).kind))
    water = next((i for i, k in hands if k == "water"), None)
    who = near(False)
    if water and who:
        return st, "give", water, who, "give_item"
    food = next((i for i, k in hands if k in ("water", "food")), None)
    if food is None:
        for r in tx.query("SELECT item_id, def_ref, anchor_id FROM items WHERE place_id=? ORDER BY item_id", (here[0],)):
            if tx.canon.get(r[1]).kind not in ("water", "food"):
                continue
            if r[2]:
                ap = tx.query_one("SELECT x_m, y_m FROM anchors WHERE anchor_id=?", (r[2],))
                x, y = ap[0], ap[1]
            else:
                pl = tx.query_one("SELECT width_m, depth_m FROM places WHERE place_id=?", (here[0],))
                x, y = pl[0] / 2, pl[1] / 2
            if _m.hypot(x - here[1], y - here[2]) <= 1.5:
                food = r[0]
                break
    if food:
        return st, "spit", food, None, "spit_into"
    return None


def _act_intent(tx, a, def_id, item, target, lod):
    from ..action.intent import Intent
    from ..mind.affordance import BoundAffordance
    d = tx.canon.find("affordance", def_id)
    iname = tx.canon.get(tx.query_one("SELECT def_ref FROM items WHERE item_id=?", (item,))[0]).name if item else ""
    fill = lambda s: s.replace("{item}", iname).replace("{target}", "someone")  # noqa: E731
    o = BoundAffordance(def_id=d.id, verb=d.verb, label=fill(d.label), ui_label=fill(d.ui_label), target_id=target,
                        item_id=item, est_duration_s=d.duration.base_s, noise_db=d.noise_db, check=d.check, tags=tuple(d.tags))
    return Intent(actor_id=a, bound=o, speech=None, manner="", goal="", private_reason="", source="reflex", lod=lod)


def _commit_act(tx, a, act, item, target, at, turn_index, kind, pc=False):
    from ..contracts.events import Event, EventType
    from ..mind.actor import adjust_stress
    from ..mind.resolve import drain
    pl = {"actor_id": a, "kind": kind, "pathway": "wet", "act": act, "item_id": item, "target_id": target}
    if pc:
        pl["pc"] = True
    ev = tx.commit_event(Event(type=EventType.INVOLUNTARY, writer="turn.pipeline", at=at, turn_index=turn_index, actor_id=a,
                               payload=pl))
    if kind == "compulsion":
        adjust_stress(tx, a, 1, ev.event_id, at, turn_index)
        drain(tx, a, "self_disgust", ev.event_id, at, turn_index)
    else:
        drain(tx, a, "resisting_urge", ev.event_id, at, turn_index)
    return ev


def _compel(tx, out, affs, at, turn_index):
    """W1: the wet strain's compulsion (never the PC)."""
    pcr = tx.query_one("SELECT value FROM meta WHERE key='pc_actor_id'")
    pc = pcr[0] if pcr else None
    for a in sorted(out):
        if a == pc or out[a] is None:
            continue
        got = _urge_act(tx, a, at)
        if got is None:
            continue
        st, act, item, target, def_id = got
        if st.compulsion >= 3:
            _commit_act(tx, a, act, item, target, at, turn_index, "compulsion")
            out[a] = _act_intent(tx, a, def_id, item, target, out[a].lod)
        else:
            _commit_act(tx, a, act, item, target, at, turn_index, "urge")


def urge_pc(tx, rng, pc_id, intent, turn_index, at):
    got = _urge_act(tx, pc_id, at)
    if got is None:
        return intent
    st, act, item, target, def_id = got
    if st.compulsion < 3:
        return intent
    if not rng.chance(tx, "mind", f"pc_urge:{pc_id}:{at}", tx.rules.infected.pc_urge_share.get(st.name, 0.0)):
        return intent
    _commit_act(tx, pc_id, act, item, target, at, turn_index, "compulsion", pc=True)
    return _act_intent(tx, pc_id, def_id, item, target, intent.lod)


async def _snap(tx, out, affs, at, turn_index, plan, st, repair):
    """H1 (TEMPER-06): what a breaking point does."""
    import json as _j
    from ..action.intent import Intent
    from ..mind.affordance import BoundAffordance
    from ..physical.bodies import capacity
    from ..physical.space import admits, point_distance
    R = tx.rules.temper
    rows = tx.query("SELECT actor_id, payload FROM events WHERE type='INVOLUNTARY' AND at=? AND turn_index=? AND "
                    "json_extract(payload,'$.kind')='outburst' ORDER BY actor_id, seq", (at, turn_index))
    seen = set()
    for a, raw in rows:
        if a in seen or a not in plan.lod:
            continue
        seen.add(a)
        pl = _j.loads(raw)
        T, outlet = pl["toward_id"], pl["outlet"]
        lod = plan.lod.get(a)

        def reflex(def_id, *, target=None, dest=None, dur=None):
            d = tx.canon.find("affordance", def_id)
            o = BoundAffordance(def_id=d.id, verb=d.verb, label=d.label, ui_label=d.ui_label, target_id=target,
                                destination_id=dest, item_id=None,
                                est_duration_s=d.duration.base_s if dur is None else dur, noise_db=d.noise_db,
                                check=d.check, tags=tuple(d.tags))
            return Intent(actor_id=a, bound=o, speech=None, manner="", goal="", private_reason="", source="reflex", lod=lod)

        cap = capacity(tx, a)
        if outlet == "wrath":                                   # TEMPER-06/10 (D-102): nothing stops it
            from ..mind.temper import gifted_by
            wid = "wonder_smite" if gifted_by(tx, a, T) else "wonder_hurt"
            try:
                out[a] = reflex(wid, target=T)
                continue
            except KeyError:
                outlet = "words"
        if outlet == "fists":
            dd = point_distance(tx, a, T)
            band = tx.query_one("SELECT age_band FROM bodies WHERE body_id=?", (T,))
            band = band[0] if band else None
            cares = any(T in _j.loads(r[0]) for r in tx.query("SELECT guardian_of FROM household_members WHERE actor_id=?", (a,)))
            if (cap.conscious and cap.hands_free >= 1 and dd is not None and dd <= R.fists_reach_m
                    and band not in ("infant", "child", "preteen") and not cares):
                out[a] = reflex("punch", target=T)
                continue
            outlet = "words"
        if outlet == "words":
            def ok(it):
                return (it is not None and it.speech is not None and T in it.speech.to
                        and str(getattr(it.speech.volume, "value", it.speech.volume)) in ("raised", "shout"))
            it = out.get(a)
            if it is not None and it.source == "model" and ok(it):
                continue
            if it is not None and it.source == "model" and a in st and not st[a]["repair"]:
                handle = next((h for h, v in st[a]["pkt"].handles.items() if v == T), "them")
                it2, _why = await repair(a, f"You have snapped at {handle}: say what you say to them, raised or shouted.",
                                         it.speech.text if it.speech else "")
                if ok(it2):
                    out[a] = it2
                    continue
            outlet = "flight"
        if outlet in ("cold", "flight"):
            got = None
            if cap.mobile:
                here = tx.query_one("SELECT place_id, x_m, y_m FROM positions WHERE body_id=?", (a,))
                ports = [r[0] for r in tx.query("SELECT portal_id FROM portals WHERE place_a=? OR place_b=? ORDER BY portal_id",
                                                (here[0], here[0]))]
                if any(admits(tx, p, a)[0] for p in ports):
                    got = reflex("leave_place")
                else:
                    tp = tx.query_one("SELECT x_m, y_m FROM positions WHERE body_id=?", (T,))
                    best = None
                    for an in tx.query("SELECT anchor_id, x_m, y_m FROM anchors WHERE place_id=? ORDER BY anchor_id", (here[0],)):
                        far = ((an[1] - tp[0]) ** 2 + (an[2] - tp[1]) ** 2) ** 0.5
                        if best is None or far > best[0]:
                            best = (far, an)
                    if best is not None:
                        an = best[1]
                        d = tx.canon.find("affordance", "move_to_anchor")
                        walk = ((an[1] - here[1]) ** 2 + (an[2] - here[2]) ** 2) ** 0.5
                        got = reflex("move_to_anchor", dest=an[0],
                                     dur=d.duration.base_s + (d.duration.per_meter_s or 0) * walk)
            if got is not None:
                out[a] = got
            else:
                out.pop(a, None)
            continue
        if outlet == "tears":
            out[a] = reflex("rest")


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
    for r in tx.query("SELECT anchor_id, name FROM anchors WHERE place_id=? ORDER BY anchor_id", (pl,)):
        out.setdefault("anchor|" + r[1].lower(), r[0])
    for r in tx.query("SELECT portal_id, name FROM portals WHERE place_a=? OR place_b=? ORDER BY portal_id", (pl, pl)):
        out.setdefault("portal|" + r[1].lower(), r[0])
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
            tgt = sig.split(":", 1)[1] if ":" in sig else "*"
            toward = set()
            if tgt.startswith("prt_"):
                pr = tx.query_one("SELECT anchor_a, anchor_b FROM portals WHERE portal_id=?", (tgt,))
                if pr is not None:
                    toward |= {x for x in (pr[0], pr[1]) if x}
            elif tgt.startswith("act_"):
                pr = tx.query_one("SELECT anchor_id FROM positions WHERE body_id=?", (tgt,))
                if pr is not None and pr[0]:
                    toward.add(pr[0])
            elif tgt.startswith("itm_"):
                pr = tx.query_one("SELECT anchor_id FROM items WHERE item_id=?", (tgt,))
                if pr is not None and pr[0]:
                    toward.add(pr[0])
            resp = firewall.classify_response(sig, it.bound, it.speech.text if it.speech else None, rc, eff,
                                              entrenched_block=block, resolve_drained_this_turn=drained,
                                              steps_toward=frozenset(toward))
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
            elif resp in (ResponseClass.READY_COMPLIANCE, ResponseClass.RELUCTANT_COMPLIANCE, ResponseClass.COERCED_COMPLIANCE):
                firewall.revise_refusal(tx, a, p["speaker"], sig, wave_at, turn_index, p["event_id"])
            elif resp == ResponseClass.PREPARING:
                sp = tx.query_one("SELECT event_id FROM events WHERE type='SPEECH' AND actor_id=? AND seq > ? ORDER BY seq LIMIT 1", (a, first_seq))
                if sp:
                    from ..mind import promise as _pm
                    d, _, tg = sig.partition(":")
                    _pm.hold(tx, a, promiser_id=a, promisee_id=p["speaker"], category=_pm.CATEGORY_OF_DEF.get(d, "assist"),
                             text=f'I said I would: {norm_text(words)} — "{it.speech.text}"',
                             object_id=None if tg in ("*", "") else tg, condition=None, source_event_id=sp[0],
                             loop_id=None, status="in_progress", at=wave_at, turn_index=turn_index)
            elif resp in (ResponseClass.DEFERRED_ASSENT, ResponseClass.UNRESOLVED_ASSENT):
                sp = tx.query_one("SELECT event_id FROM events WHERE type='SPEECH' AND actor_id=? AND seq > ? ORDER BY seq LIMIT 1", (a, first_seq))
                if resp == ResponseClass.DEFERRED_ASSENT:
                    from ..mind import mind as _mindmod
                    from ..contracts.events import EventLink as _EL
                    lid = _mindmod.open_loop(tx, a, "promise_made", f'I said I would: {norm_text(words)} — "{it.speech.text}"', [p["speaker"]],
                                       1, sp[0] if sp else p["event_id"], wave_at, turn_index,
                                       links=[_EL(event_id=p["event_id"], role="answered")] if sp else [])
                    if sp:
                        from ..mind import promise as _pm
                        d, _, tg = sig.partition(":")
                        txt = tx.query_one("SELECT text FROM open_loops WHERE loop_id=?", (lid,))[0]
                        _pm.hold(tx, a, promiser_id=a, promisee_id=p["speaker"], category=_pm.CATEGORY_OF_DEF.get(d, "assist"), text=txt,
                                 object_id=None if tg in ("*", "") else tg, condition=it.speech.text, source_event_id=sp[0],
                                 loop_id=lid, status="accepted", at=wave_at, turn_index=turn_index)
                else:
                    firewall.record_unmet_assent(tx, a, p["speaker"], sig, it.speech.text, it.bound.def_id, sp[0] if sp else None,
                                                 wave_at, turn_index, ask_event_id=p["event_id"])
    return out
