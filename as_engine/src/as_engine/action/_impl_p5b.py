"""Implementation: conflict, resolve, intent (barrier etc.), reactions, propagate,
cascade, scheduler.plan_cognition."""
from __future__ import annotations

import dataclasses
import json
import math
import re

from ..contracts.common import LOD, CallClass, Lane, Verb, attr_mod
from ..contracts.events import Event, EventType


def _row(s, sql, p=()):
    r = s.query_one(sql, p)
    return dict(r) if r is not None else None


def _canon(tx):
    return tx.canon if getattr(tx, "canon", None) is not None else tx.store.canon


def _def(tx, def_id):
    return _canon(tx).find("affordance", def_id)


# ============================================================ intent helpers
def intent_to_dict(i):
    b = i.bound
    return {"actor_id": i.actor_id, "manner": i.manner, "goal": i.goal, "private_reason": i.private_reason, "source": i.source,
            "lod": i.lod.value if hasattr(i.lod, "value") else i.lod, "blocked": i.blocked, "pace": i.pace,
            "inscription": None if i.inscription is None else {"text": i.inscription.text,
                                                               "quotation_source": i.inscription.quotation_source},
            "speech": None if i.speech is None else {"text": i.speech.text, "to": list(i.speech.to), "volume": str(i.speech.volume.value if hasattr(i.speech.volume, "value") else i.speech.volume),
                                                     "delivery": i.speech.delivery, "timing": i.speech.timing},
            "bound": {"def_id": b.def_id, "verb": b.verb.value if hasattr(b.verb, "value") else b.verb, "label": b.label, "ui_label": b.ui_label,
                      "target_id": b.target_id, "destination_id": b.destination_id, "item_id": b.item_id, "est_duration_s": b.est_duration_s,
                      "noise_db": b.noise_db, "cost_note": b.cost_note, "risk_note": b.risk_note,
                      "check": None if b.check is None else b.check.model_dump(mode="json"), "tags": list(b.tags),
                      "paces": list(b.paces), "hands": b.hands},
            "gesture": None if i.gesture is None else list(i.gesture), "attention": i.attention}


def intent_from_dict(d):
    from ..contracts.common import Volume
    from ..contracts.content import CheckSpec
    from ..mind.affordance import BoundAffordance
    from .intent import InscriptionAct, Intent, SpeechAct
    bd = dict(d["bound"])
    bd["verb"] = Verb(bd["verb"])
    bd["check"] = None if bd["check"] is None else CheckSpec.model_validate(bd["check"])
    bd["tags"] = tuple(bd["tags"])
    bd["paces"] = tuple(bd.get("paces", ()))
    bd["hands"] = bd.get("hands", 0)
    sp = d["speech"]
    ins = d.get("inscription")
    return Intent(actor_id=d["actor_id"], bound=BoundAffordance(**bd),
                  speech=None if sp is None else SpeechAct(text=sp["text"], to=tuple(sp["to"]), volume=Volume(sp["volume"]),
                                                           delivery=sp.get("delivery", "ordinary"),
                                                           timing=sp.get("timing", "alongside")),
                  manner=d["manner"], goal=d["goal"], private_reason=d["private_reason"], source=d["source"], lod=LOD(d["lod"]),
                  blocked=d.get("blocked"), pace=d.get("pace", "normal"),
                  inscription=None if ins is None else InscriptionAct(text=ins["text"],
                                                                      quotation_source=ins.get("quotation_source")),
                  gesture=None if d.get("gesture") is None else tuple(d["gesture"]), attention=d.get("attention"))


def barrier(tx, intents):
    out = []
    for i in intents:
        b = i.bound
        bad = False
        for ref in (b.target_id, b.destination_id, b.item_id):
            if ref and not _exists(tx, ref):
                bad = True
        d = _def(tx, b.def_id)
        if not bad and d.binds == "item_reachable" and b.target_id:
            it = _row(tx, "SELECT * FROM items WHERE item_id=?", (b.target_id,))
            if it is None or (b.destination_id and it["anchor_id"] != b.destination_id) or it["place_id"] is None:
                bad = True
        if not bad and d.binds in ("item_held", "item_carried") and b.item_id:
            it = _row(tx, "SELECT * FROM items WHERE item_id=?", (b.item_id,))
            from ._impl_effects import _carries
            if it is None or not _carries(tx, i.actor_id, b.item_id):
                bad = True
        out.append(dataclasses.replace(i, blocked="referent_missing") if bad else i)
    return out


_TABLES = {"act": ("bodies", "body_id"), "itm": ("items", "item_id"), "prt": ("portals", "portal_id"),
           "anc": ("anchors", "anchor_id"), "wnd": ("wounds", "wound_id"), "plc": ("places", "place_id")}


def _exists(tx, ref):
    k = ref.split("_", 1)[0]
    if k not in _TABLES:
        return True
    t, c = _TABLES[k]
    return tx.query_one(f"SELECT 1 FROM {t} WHERE {c}=?", (ref,)) is not None


def plan_continuation(tx, actor_id, affordances, at, turn_index, *, accepted_only=False):
    from ..mind.actor import fused
    from ..mind.cues import cues_of
    from .intent import Intent
    opts = affordances.options
    act = _row(tx, "SELECT * FROM actors WHERE actor_id=?", (actor_id,))

    def mk(o, source):
        return Intent(actor_id=actor_id, bound=o, speech=None, manner="", goal=act["goal_text"] or o.label,
                      private_reason="", source=source, lod=LOD.COLD)
    present = cues_of(tx, actor_id, turn_index, at)
    d = fused(tx, actor_id)
    for tr in d.capability.trained_responses:
        if tr.cue in present:
            for o in opts:
                if o.verb == tr.verb:
                    return mk(o, "reflex")
    plan = _row(tx, "SELECT * FROM plans WHERE actor_id=?", (actor_id,))
    if plan:
        for so in json.loads(plan["standing_orders"]):
            if so["trigger"] in present:
                for o in opts:
                    if o.verb == Verb.OBSERVE:
                        return mk(o, "plan")
    for o in opts:
        if o.def_id == "keep_working":
            return mk(o, "plan")
    if plan:
        steps = json.loads(plan["steps"])
        if steps:
            st = steps[0].lower()
            for o in opts:
                if st in o.label.lower() or o.def_id == steps[0]:
                    return mk(o, "plan")
    from ..kernel.clock import world_time as _wt
    from ..society._impl_society import step_for as _step_for
    from ..society.routine import OPTION_FOR as _OPT
    _st = _step_for(tx, actor_id, _wt(at).hour)
    if _st is not None and _st.activity in _OPT:
        for o in opts:
            if o.def_id == _OPT[_st.activity]:
                return mk(o, "plan")
    if act["duty_anchor"]:
        for o in opts:
            if o.def_id == "guard_anchor" and o.destination_id == act["duty_anchor"]:
                return mk(o, "plan")
    if accepted_only:
        return None                  # HOLD-01: no invented willingness
    for want in ("observe_area", "wait_here"):
        for o in opts:
            if o.def_id == want:
                return mk(o, "plan")
    return mk(opts[0], "plan") if opts else None      # nothing offered (asleep): nothing goes on


# ============================================================ conflict
def resources_of(tx, intent):
    b = intent.bound
    d = _def(tx, b.def_id)
    out = []

    def add(r):
        if r not in out:
            out.append(r)
    t = b.target_id
    if t and t.startswith("act_"):
        add(("body", t))
    if b.item_id:
        add(("object", b.item_id))
    if t and t.startswith("itm_"):
        add(("object", t))
    if t and t.startswith("prt_"):
        add(("portal", t))
    if d.effect in ("move_through_portal", "leave_place", "flee"):
        here = _row(tx, "SELECT place_id FROM positions WHERE body_id=?", (intent.actor_id,))["place_id"]
        if d.effect == "move_through_portal":
            p = _row(tx, "SELECT place_a, place_b FROM portals WHERE portal_id=?", (t,))
            far = p["place_b"] if p["place_a"] == here else p["place_a"]
            a, z = sorted([here, far])
            add(("route", f"{a}|{z}"))
        else:
            add(("route", f"{here}|*"))
    dest = b.destination_id
    if dest and dest.startswith("anc_") and d.effect in ("move_to_anchor", "take_cover", "hide"):
        an = _row(tx, "SELECT cover, concealment FROM anchors WHERE anchor_id=?", (dest,))
        if an and (an["cover"] >= 1 or an["concealment"] >= 1):
            add(("anchor", dest))
    if b.def_id == "keep_working":
        from ._impl_p5a import active_task
        tk = active_task(tx, intent.actor_id)
        if tk:
            add(("task_window", tk["task_id"]))
    if "ranged" in d.tags and t:
        add(("line", t))
    return out


def form_groups(tx, intents):
    from .conflict import ConflictGroup
    by = {}
    for i in intents:
        for r in resources_of(tx, i):
            by.setdefault(r, []).append(i)
    groups = [ConflictGroup(resource=r, members=sorted(m, key=lambda i: i.actor_id)) for r, m in sorted(by.items()) if len(m) >= 2]
    ingroup = {id(i) for g in groups for i in g.members}
    return groups, [i for i in intents if id(i) not in ingroup]


def precedence(tx, rng, resource, members, land_at):
    from ..physical.bodies import grips_on
    from ..physical.space import distance_to_point, point_distance

    def in_progress(i):
        return i.bound.def_id == "keep_working" or (resource[0] == "body" and i.actor_id in grips_on(tx, resource[1]))

    def control(i):
        k, v = resource
        if k == "object":
            it = _row(tx, "SELECT holder_body FROM items WHERE item_id=?", (v,))
            return bool(it and it["holder_body"] == i.actor_id)
        if k == "body":
            return i.actor_id in grips_on(tx, v)
        if k == "anchor":
            p = _row(tx, "SELECT anchor_id FROM positions WHERE body_id=?", (i.actor_id,))
            return p["anchor_id"] == v
        return False

    def dist(i):
        k, v = resource
        if k == "body":
            return point_distance(tx, i.actor_id, v) or 0.0
        pt = None
        if k == "object":
            from ._impl_effects import _item_point
            pt = _item_point(tx, v)
        elif k == "anchor":
            a = _row(tx, "SELECT * FROM anchors WHERE anchor_id=?", (v,))
            pt = (a["place_id"], v, a["x_m"], a["y_m"])
        elif k == "portal":
            from ._impl_effects import _portal_side_point
            here = _row(tx, "SELECT place_id FROM positions WHERE body_id=?", (i.actor_id,))["place_id"]
            pt = _portal_side_point(tx, v, here)
        if pt is None:
            return 0.0
        dd = distance_to_point(tx, i.actor_id, pt[0], pt[2], pt[3])
        return 999.0 if dd is None else dd

    def cap(i):
        d = _def(tx, i.bound.def_id)
        letter = d.check.attribute if d.check else "A"
        letter = getattr(letter, "value", letter)
        sp = json.loads(_row(tx, "SELECT special FROM bodies WHERE body_id=?", (i.actor_id,))["special"])
        return attr_mod(sp[letter])
    keyed = sorted(members, key=lambda i: (not in_progress(i), not control(i), round(dist(i), 6), -cap(i), i.actor_id))
    # ties on the full key -> one shuffle over the tied actor ids
    out = []
    j = 0
    k = lambda i: (not in_progress(i), not control(i), round(dist(i), 6), -cap(i))  # noqa: E731
    while j < len(keyed):
        grp = [keyed[j]]
        while j + len(grp) < len(keyed) and k(keyed[j + len(grp)]) == k(keyed[j]):
            grp.append(keyed[j + len(grp)])
        if len(grp) > 1:
            ids = rng.shuffle(tx, "resolve", f"ladder:{resource[0]}:{resource[1]}", sorted(i.actor_id for i in grp))
            grp = sorted(grp, key=lambda i: ids.index(i.actor_id))
        out += grp
        j += len(grp)
    return out


# ============================================================ resolve
def _start_event(tx, intent, at, turn_index):
    from .effects import SEEN
    b = intent.bound
    d = _def(tx, b.def_id)
    return tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=turn_index, actor_id=intent.actor_id,
                                 payload={"actor_id": intent.actor_id, "def_id": b.def_id, "verb": b.verb.value if hasattr(b.verb, "value") else b.verb,
                                          "target_id": b.target_id, "destination_id": b.destination_id, "item_id": b.item_id,
                                          "est_duration_s": b.est_duration_s, "visible": d.visible_act, "seen": b.label if b.def_id == "forced_act" else SEEN.get(b.def_id),
                                          "continues_task": b.def_id == "keep_working", "label": b.label, "goal": intent.goal,
                                          "attention": intent.attention}))


def _armed(tx, actor):
    for r in tx.query("SELECT def_ref FROM items WHERE holder_body=? AND holder_slot IN ('hand_l','hand_r')", (actor,)):
        dd = _canon(tx).get(r[0])
        if dd.firearm is not None or dd.melee is not None:
            return True
    return False


def resolve_wave(tx, rng, intents, wave_at, turn_index, *, horizon_ms):
    from ..kernel import clock
    from .effects import EffectCtx, land_ms
    first = tx.query_one("SELECT COALESCE(MAX(seq),0) FROM events")[0]
    started = []
    segq = []
    for i in sorted(intents, key=lambda x: x.actor_id):
        if i.blocked:
            tx.commit_event(Event(type=EventType.ACTION_BLOCKED, writer="action.resolve", at=wave_at, turn_index=turn_index, actor_id=i.actor_id,
                                  payload={"actor_id": i.actor_id, "def_id": i.bound.def_id, "cause": i.blocked}))
            continue
        pend = clock.pending_for(tx, "ACTION_LAND", i.actor_id)
        carry = False
        for row in pend:
            pl = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
            old = intent_from_dict(pl["intent"])
            if old.bound.signature == i.bound.signature and i.speech is None:
                carry = True
                continue
            clock.cancel(tx, row["queue_id"], "new_action", wave_at, pl.get("start_event_id"), turn_index)
            tx.commit_event(Event(type=EventType.ACTION_INTERRUPT, writer="action.resolve", at=wave_at, turn_index=turn_index, actor_id=i.actor_id,
                                  cause_event_id=pl.get("start_event_id"),
                                  payload={"actor_id": i.actor_id, "def_id": old.bound.def_id, "cause": "new_action"}))
        if carry:
            continue
        _cut_speech(tx, i.actor_id, wave_at, turn_index, "new_action")
        if _def(tx, i.bound.def_id).effect != "sleep" and (tx.query_one(
                "SELECT controller FROM actors WHERE actor_id=?", (i.actor_id,)) or [None])[0] == "human":
            from ..physical.bodies import wake                 # SLEEP-02 (D-122): the player wakes the PC
            wake(tx, i.actor_id, wave_at, None, turn_index)
        st = _start_event(tx, i, wave_at, turn_index)
        if i.gesture is not None:
            tx.commit_event(Event(type=EventType.GESTURE, writer="action.propagate", at=wave_at, turn_index=turn_index,
                                  actor_id=i.actor_id, cause_event_id=st.event_id,
                                  payload={"actor_id": i.actor_id, "gesture": i.gesture[0], "target_id": i.gesture[1]}))
        d = _def(tx, i.bound.def_id)
        la = wave_at if d.duration.condition_ended else land_ms(wave_at, i.bound.est_duration_s)
        if i.speech is not None:
            import math as _m
            from .intent import segments as _segs
            R = tx.rules.acoustics
            vol = i.speech.volume.value if hasattr(i.speech.volume, "value") else i.speech.volume
            from ..physical.bodies import speaks_broken
            text = broken_words(tx, rng, i.actor_id, i.speech.text, wave_at) if speaks_broken(tx, i.actor_id, wave_at) \
                else i.speech.text   # RESOLVE-07 (D-107)
            segs = _segs(text)
            nwords = len(text.split())
            say_at = wave_at
            if i.speech.timing == "after" and d.effect != "speak":
                la = wave_at if d.duration.condition_ended else land_ms(wave_at, i.bound.est_duration_s - nwords / 2.5)
                say_at = la
            before = 0
            for k, seg in enumerate(segs, 1):
                pl = {"words": seg, "volume": vol, "to": list(i.speech.to), "source_db": R.speech_db[vol],
                      "armed": _armed(tx, i.actor_id), "utterance_id": st.event_id, "segment": k, "segments": len(segs)}
                due = say_at + _m.ceil(1000 * before / 2.5)
                before += len(seg.split())
                if k == 1 and due == wave_at:
                    tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=wave_at, turn_index=turn_index,
                                          actor_id=i.actor_id, cause_event_id=st.event_id, payload=pl,
                                          writes=_voice_line(tx, i.actor_id, pl, wave_at)))
                else:
                    segq.append((due, i.actor_id, k, pl, st.event_id))
        started.append((la, i, st))
    # ordering within the same land time by precedence
    groups, _ = form_groups(tx, [s[1] for s in started])
    rank = {}
    for g in groups:
        same = {}
        for s in started:
            if s[1] in g.members:
                same.setdefault(s[0], []).append(s[1])
        for la, mem in same.items():
            if len(mem) >= 2:
                for pos, i in enumerate(precedence(tx, rng, g.resource, mem, la)):
                    rank.setdefault(id(i), pos)
    started.sort(key=lambda s: (s[0], rank.get(id(s[1]), 0), s[1].actor_id))
    timeline = [(s[0], 0, n, "land", s) for n, s in enumerate(started)]
    timeline += [(q[0], 1, n, "say", q) for n, q in enumerate(sorted(segq, key=lambda q: (q[0], q[1], q[2])))]
    timeline.sort(key=lambda e: (e[0], e[1], e[2]))
    cut_off = set()
    for when, _k, _n, kind, item in timeline:
        if kind == "land":
            la, i, st = item
            if la > horizon_ms:
                clock.schedule(tx, la, "ACTION_LAND", i.actor_id, {"intent": intent_to_dict(i), "start_event_id": st.event_id}, st.event_id)
                continue
            _land(tx, rng, i, la, EffectCtx(turn_index=turn_index, horizon_ms=horizon_ms, start_event_id=st.event_id, wave_start_ms=wave_at))
        else:
            due, speaker, k, pl, sid = item
            if pl["utterance_id"] in cut_off:
                continue
            if due > horizon_ms:
                clock.schedule(tx, due, "SPEECH_SEGMENT", speaker, pl, sid)
                continue
            if not _say(tx, speaker, pl, sid, due, turn_index):
                cut_off.add(pl["utterance_id"])
    return _events_since(tx, first)


def broken_words(tx, rng, speaker, text, at):
    """What comes out of a broken mind (RESOLVE-07, D-107)."""
    words = text.split()
    if not words:
        return text
    keep = rng.range_int(tx, "doom", f"words:{speaker}:{at}", 1, max(1, min(4, (len(words) + 1) // 2)))
    pieces = [w.strip(",.;:!?\"'") or w for w in words[:keep]]
    if rng.chance(tx, "doom", f"again:{speaker}:{at}", 0.5):
        pieces.append(pieces[-1])
    return "\u2014 ".join(pieces) + "\u2014"


def _voice_line(tx, speaker, pl, at):
    """D-117 (DOS-05, SEG-03): the words a person says become their voice line, written by the SPEECH itself."""
    from ..contracts.events import WriteOp, WriteRecord
    words = (pl.get("words") or "").strip()
    if not words or tx.query_one("SELECT 1 FROM actors WHERE actor_id=?", (speaker,)) is None:
        return []
    return [WriteRecord(op=WriteOp.INSERT, table="voice_lines", values={
        "line_id": tx.mint("vln"), "actor_id": speaker, "text": words, "at": at, "event_id": pl["utterance_id"],
        "pinned": 0})]


def _say(tx, speaker, pl, sid, due, turn_index):
    """SEG-04: say one segment if the speaker can; else the SPEECH_CUT. True when said."""
    from ..physical.bodies import capacity
    b = _row(tx, "SELECT alive FROM bodies WHERE body_id=?", (speaker,))
    if b["alive"] and capacity(tx, speaker).conscious:
        tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=due, turn_index=turn_index, actor_id=speaker,
                              cause_event_id=sid, payload=pl, writes=_voice_line(tx, speaker, pl, due)))
        return True
    tx.commit_event(Event(type=EventType.SPEECH_CUT, writer="action.propagate", at=due, turn_index=turn_index, actor_id=speaker,
                          cause_event_id=sid, payload={"actor_id": speaker, "utterance_id": pl["utterance_id"],
                                                       "delivered": pl["segment"] - 1, "of": pl["segments"],
                                                       "cause": "dead" if not b["alive"] else "unconscious"}))
    return False


def _cut_speech(tx, speaker, at, turn_index, cause):
    from ..kernel import clock
    rows = clock.pending_for(tx, "SPEECH_SEGMENT", speaker)
    by = {}
    for r in rows:
        pl = json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"]
        by.setdefault(pl["utterance_id"], []).append((r, pl))
    for uid in sorted(by):
        items = by[uid]
        for r, pl in items:
            clock.cancel(tx, r["queue_id"], cause, at, uid, turn_index)
        first = min(pl["segment"] for _, pl in items)
        tx.commit_event(Event(type=EventType.SPEECH_CUT, writer="action.propagate", at=at, turn_index=turn_index, actor_id=speaker,
                              cause_event_id=uid, payload={"actor_id": speaker, "utterance_id": uid, "delivered": first - 1,
                                                           "of": items[0][1]["segments"], "cause": cause}))


def say_pending(tx, row, turn_index):
    from ..kernel import clock
    first = tx.query_one("SELECT COALESCE(MAX(seq),0) FROM events")[0]
    pl = json.loads(row["payload"]) if isinstance(row["payload"], str) else dict(row["payload"])
    speaker = row["subject_id"]
    if not _say(tx, speaker, pl, pl["utterance_id"], row["due_at"], turn_index):
        for r in clock.pending_for(tx, "SPEECH_SEGMENT", speaker):
            p2 = json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"]
            if p2["utterance_id"] == pl["utterance_id"] and r["queue_id"] != row["queue_id"]:
                clock.cancel(tx, r["queue_id"], "speech_cut", row["due_at"], pl["utterance_id"], turn_index)
    return _events_since(tx, first)


def _land(tx, rng, i, la, ctx):
    from ._impl_effects import land
    lg = land(tx, rng, i, la, ctx)
    if lg.blocked:
        tx.commit_event(Event(type=EventType.ACTION_BLOCKED, writer="action.resolve", at=la, turn_index=ctx.turn_index, actor_id=i.actor_id,
                              cause_event_id=ctx.start_event_id, payload={"actor_id": i.actor_id, "def_id": i.bound.def_id, "cause": lg.blocked}))
    else:
        tx.commit_event(Event(type=EventType.ACTION_COMPLETE, writer="action.resolve", at=lg.complete_at or la, turn_index=ctx.turn_index,
                              actor_id=i.actor_id, cause_event_id=ctx.start_event_id,
                              payload={"actor_id": i.actor_id, "def_id": i.bound.def_id, "result": lg.result,
                                       "band": lg.band.value if lg.band is not None else None, "visible": False}))
    return lg


def _events_since(tx, seq):
    from ..kernel.events import get
    return [_ev_model(tx, r) for r in tx.query("SELECT * FROM events WHERE seq>? ORDER BY seq", (seq,))]


def _ev_model(tx, r):
    d = dict(r)
    return Event(event_id=d["event_id"], seq=d["seq"], type=EventType(d["type"]), writer=d["writer"], at=d["at"], turn_index=d["turn_index"],
                 actor_id=d["actor_id"], cause_event_id=d["cause_event_id"], place_id=d["place_id"], rule_cited=d["rule_cited"],
                 origin=d["origin"], target_ids=json.loads(d["target_ids"]) if d["target_ids"] else [],
                 payload=json.loads(d["payload"]) if isinstance(d["payload"], str) else d["payload"])


def land_pending(tx, rng, row, turn_index, *, horizon_ms):
    from .effects import EffectCtx
    first = tx.query_one("SELECT COALESCE(MAX(seq),0) FROM events")[0]
    pl = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
    i = intent_from_dict(pl["intent"])
    _land(tx, rng, i, row["due_at"], EffectCtx(turn_index=turn_index, horizon_ms=horizon_ms, start_event_id=pl["start_event_id"], wave_start_ms=row["due_at"]))
    return _events_since(tx, first)


# ============================================================ reactions
def _bonded(tx, holder):
    out = {r[0] for r in tx.query("SELECT to_id FROM relationships WHERE from_id=? AND affection>=2", (holder,))}
    for h in tx.query("SELECT household_id FROM household_members WHERE actor_id=?", (holder,)):
        out |= {r[0] for r in tx.query("SELECT actor_id FROM household_members WHERE household_id=?", (h[0],))}
    out.discard(holder)
    return out


def material_holders(tx, new_events, turn_index):
    from ..physical.space import distance_to_point
    from ..sense import acoustics
    ids = [e.event_id for e in new_events if e.event_id]
    evmap = {e.event_id: e for e in new_events}
    found = {}
    if not ids:
        return []
    ph = ",".join("?" * len(ids))
    for p in tx.query(f"SELECT * FROM percept_log WHERE event_id IN ({ph}) ORDER BY at, percept_id", tuple(ids)):
        p = dict(p)
        h = p["holder_id"]
        if not tx.query_one("SELECT 1 FROM actors WHERE actor_id=?", (h,)):
            continue
        b = _row(tx, "SELECT alive, awareness FROM bodies WHERE body_id=?", (h,))
        if not b["alive"] or b["awareness"] in ("unconscious", "dead"):
            continue
        ev = evmap[p["event_id"]]
        if ev.actor_id == h:
            continue
        det = json.loads(p["detail"])
        pl = ev.payload
        vis = p["channel"] == "visual" and det.get("level") in ("clear", "partial")
        mat = False
        if p["channel"] == "speech" and det.get("addressed_to_me") and p["fidelity"] in ("exact", "partial"):
            mat = True
        if p["channel"] == "speech" and det.get("armed_at_me"):
            mat = True
        if p["channel"] == "auditory" and ev.type == EventType.NOISE and p["fidelity"] in ("exact", "partial"):
            if pl.get("source_db", 0) >= 80:
                mat = True
            else:
                src = acoustics.source_point(tx, pl, ev.actor_id)
                dd = distance_to_point(tx, h, src.place_id, src.x_m, src.y_m)
                if dd is not None and dd <= 10:
                    mat = True
        if p["channel"] == "tactile":
            mat = True
        if vis:
            bonded = _bonded(tx, h) | {h}
            if ev.type in (EventType.HARM, EventType.DEATH, EventType.FALSE_DEATH) and pl.get("body_id") in bonded:
                mat = True
            if ev.type == EventType.ACTION_START and pl.get("verb") == "attack" and pl.get("target_id") in bonded:
                mat = True
            if ev.type == EventType.ACTION_START and pl.get("def_id") in ("shoot_center_mass", "shoot_head") and pl.get("target_id") == h:
                mat = True
            if ev.type == EventType.MOVE and ev.cause_event_id:
                cause = _row(tx, "SELECT payload FROM events WHERE event_id=?", (ev.cause_event_id,))
                cdef = json.loads(cause["payload"]).get("def_id") if cause else None
                kn = _row(tx, "SELECT known_name FROM acquaintance WHERE holder_id=? AND subject_id=?", (h, ev.actor_id))
                if cdef in ("run_to_anchor", "flee_threat", "leave_place") and not (kn and kn["known_name"]):
                    dd = distance_to_point(tx, h, pl["to_place"], pl["x_m"], pl["y_m"])
                    if dd is not None and dd <= 20:
                        mat = True
            if ev.type == EventType.MOVE and not mat:
                kind = tx.query_one("SELECT kind FROM bodies WHERE body_id=?", (pl.get("body_id"),))
                if kind is not None and kind[0] == "infected":      # P10: the dead coming near
                    dd = distance_to_point(tx, h, pl["to_place"], pl["x_m"], pl["y_m"])
                    if dd is not None and dd <= 20:
                        mat = True
            if not mat:
                mat = _looks_up(tx, h, ev, pl, bonded)               # D-137
        if mat and h not in found:
            found[h] = p["at"]
    return sorted(found.items(), key=lambda kv: (kv[1], kv[0]))


def _looks_up(tx, h, ev, pl, bonded):
    """D-137: a weapon drawn near you, something done to you or yours, your things taken, a gesture at you, or the
    one you were fighting giving up."""
    from ..physical.space import point_distance
    if ev.type == EventType.ACTION_START and pl.get("def_id") == "equip_item" and pl.get("item_id"):
        ref = tx.query_one("SELECT def_ref FROM items WHERE item_id=?", (pl["item_id"],))
        d = tx.canon.get(ref[0]) if ref and tx.canon.has(ref[0]) else None
        if d is not None and (getattr(d, "firearm", None) is not None or getattr(d, "melee", None) is not None):
            dd = point_distance(tx, h, ev.actor_id)
            if dd is not None and dd <= 20:
                return True
    if ev.type == EventType.ACTION_START and pl.get("verb") == "manipulate" and pl.get("target_id") in bonded:
        return True
    if ev.type == EventType.ITEM_TRANSFER and h in _theft_victims(tx, ev.event_id):
        return True
    if ev.type == EventType.GESTURE and pl.get("target_id") == h:
        return True
    gave_up = ((ev.type == EventType.GESTURE and pl.get("gesture") == "empty_hands")
               or (ev.type == EventType.ACTION_START and pl.get("verb") == "surrender"))
    if gave_up and ev.actor_id:
        return tx.query_one(
            "SELECT 1 FROM events WHERE type='ACTION_START' AND at BETWEEN ? AND ? AND json_extract(payload,'$.verb')='attack' "
            "AND ((actor_id=? AND json_extract(payload,'$.target_id')=?) OR (actor_id=? AND json_extract(payload,'$.target_id')=?))",
            (ev.at - 60_000, ev.at, h, ev.actor_id, ev.actor_id, h)) is not None
    return False


def reaction_time(tx, rng, holder_id, trigger_at):
    lo, hi = tx.rules.acoustics.reaction_window_ms
    t = trigger_at + rng.range_int(tx, "resolve", f"react:{holder_id}:{trigger_at}", lo, hi)
    b = _row(tx, "SELECT awareness FROM bodies WHERE body_id=?", (holder_id,))
    focused = tx.query_one("SELECT 1 FROM tasks WHERE actor_id=? AND status='active' AND focus=1", (holder_id,))
    if b["awareness"] == "drowsy" or focused:
        t += 400
    return t


def next_wave(tx, rng, new_events, turn_index, wave_index, horizon_ms, *, exclude=frozenset()):
    hs = [(h, t) for h, t in material_holders(tx, new_events, turn_index) if h not in exclude]
    timed = [(reaction_time(tx, rng, h, t), h) for h, t in hs]
    timed = [(t, h) for t, h in timed if t <= horizon_ms]
    if not timed:
        return None, []
    if wave_index > tx.rules.scheduler.max_reaction_waves:
        return None, sorted(h for _, h in timed)
    return min(t for t, _ in timed), sorted(h for _, h in timed)


# ============================================================ propagate
def propagate(tx, outcome_events, at, turn_index):
    return []


# ============================================================ cascade
_OPS = {"==": lambda a, b: a == b, "!=": lambda a, b: a != b, ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b, "<": lambda a, b: a < b}


def _lit(s):
    s = s.strip()
    if s in ("true", "false"):
        return s == "true"
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        return s[1:-1]
    try:
        return int(s)
    except ValueError:
        return float(s)


_MISSING = object()


def _path(tx, path, trig):
    path = path.strip()
    if path.startswith("trigger.payload."):
        return trig.payload.get(path[len("trigger.payload."):], _MISSING)
    if path == "trigger.actor_id":
        return trig.actor_id
    if path == "trigger.type":
        return trig.type.value if hasattr(trig.type, "value") else trig.type
    if path == "trigger.event_id":
        return trig.event_id
    if path in ("trigger.killer", "trigger.killer_provoked"):      # D-119: a killing
        k = _killing(tx, trig)
        if k is None:
            return _MISSING
        return k[0] if path == "trigger.killer" else k[1]
    if path in ("trigger.victim_held", "trigger.victim_yielded"):  # D-134 a captive, D-135 one who gave up
        how = _held_when if path == "trigger.victim_held" else _yielded_when
        typ = trig.type.value if hasattr(trig.type, "value") else trig.type
        body = (trig.payload or {}).get("body_id")
        if typ == "HARM" and body:
            return how(tx, body, trig.at)
        if typ == "DEATH":
            k = _killing(tx, trig)
            if k is None:
                return _MISSING
            return how(tx, body, tx.query_one("SELECT at FROM events WHERE event_id=?", (k[2],))[0])
        return _MISSING
    if path in ("trigger.attacker", "trigger.attacker_provoked"):  # D-126: someone hurt
        a = _assault(tx, trig)
        if a is None:
            return _MISSING
        return a[0] if path == "trigger.attacker" else a[1]
    if path == "trigger.killer_first":                             # D-123
        k = _killing(tx, trig)
        if k is None:
            return _MISSING
        for r in tx.query("SELECT * FROM events WHERE type='DEATH' AND seq < (SELECT seq FROM events WHERE event_id=?) "
                          "ORDER BY seq", (trig.event_id,)):
            ok = _killing(tx, _ev_model(tx, r))
            if ok is not None and ok[0] == k[0]:
                return False
        return True
    m = re.match(r"^(\w+)\((.+)\)\.(\w+)$", path)
    if m:
        fn, inner, col = m.groups()
        ids = select(tx, f"{fn}({inner})", trig)
        if not ids:
            return _MISSING
        if fn == "actor":
            r = _row(tx, "SELECT * FROM actors WHERE actor_id=?", (ids[0],))
            return r.get(col, _MISSING) if r else _MISSING
        if fn == "body":                                            # D-123
            r = _row(tx, "SELECT * FROM bodies WHERE body_id=?", (ids[0],))
            return r.get(col, _MISSING) if r else _MISSING
        if fn == "settlement_of":
            from ..society._impl_society import days_of, has_shortage
            if col.startswith("days_of_"):
                return days_of(tx, ids[0], col[len("days_of_"):])
            if col.startswith("has_shortage_"):
                return has_shortage(tx, ids[0], col[len("has_shortage_"):])
            r = _row(tx, "SELECT * FROM settlements WHERE settlement_id=?", (ids[0],))
            return r.get(col, _MISSING) if r else _MISSING
        if fn == "workplace_of":
            r = _row(tx, "SELECT * FROM workplaces WHERE workplace_id=?", (ids[0],))
            return r.get(col, _MISSING) if r else _MISSING
        raise NotImplementedError(f"selector {fn} (P9)")
    raise ValueError(f"bad path {path}")


def _killing(tx, trig):
    """D-119: (killer, provoked, the killing blow's event id) for a DEATH someone caused, else None."""
    if (trig.type.value if hasattr(trig.type, "value") else trig.type) != "DEATH":
        return None
    pl = trig.payload or {}
    dead = pl.get("body_id")
    if pl.get("cause") not in _WOUND_DEATHS:
        return None
    blow = None
    if trig.cause_event_id:
        r = _row(tx, "SELECT event_id, type, actor_id, at, json_extract(payload, '$.body_id') AS body_id FROM events "
                     "WHERE event_id=?", (trig.cause_event_id,))
        if r and r["type"] == "HARM" and r["body_id"] == dead:
            blow = r
    if blow is None:
        blow = _row(tx, "SELECT event_id, actor_id, at FROM events WHERE type='HARM' AND json_extract(payload, '$.body_id')=? "
                        "AND at<=? AND json_extract(payload, '$.wound_id') IN (SELECT wound_id FROM wounds WHERE body_id=? AND "
                        "healed_at IS NULL) ORDER BY at DESC, seq DESC LIMIT 1", (dead, trig.at, dead))
    if blow is None or not blow["actor_id"] or blow["actor_id"] == dead:
        return None
    killer = blow["actor_id"]
    if tx.query_one("SELECT 1 FROM actors WHERE actor_id=?", (killer,)) is None:
        return None
    return killer, _was_fighting(tx, dead, blow["at"]), blow["event_id"]


def _was_fighting(tx, who, until):
    """D-119 / D-126: in the 10 minutes up to ``until`` ``who`` harmed a person, started an attack at one, or
    spoke armed to one or to everyone."""
    person = "(SELECT actor_id FROM actors WHERE actor_id != :who)"
    return tx.query_one(
        "SELECT 1 FROM events WHERE actor_id=:who AND at>=:lo AND at<=:at AND ("
        f"(type='HARM' AND json_extract(payload, '$.body_id') IN {person}) OR "
        f"(type='ACTION_START' AND json_extract(payload, '$.verb')='attack' AND json_extract(payload, '$.target_id') IN {person}) OR "
        "(type='SPEECH' AND json_extract(payload, '$.armed')=1 AND EXISTS (SELECT 1 FROM json_each(json_extract(payload, '$.to')) "
        f"WHERE value='everyone' OR value IN {person}))) LIMIT 1", {"who": who, "lo": until - 10 * 60_000, "at": until}) is not None


def _assault(tx, trig):
    """D-126: (attacker, provoked) for a HARM one person did to another, else None."""
    if (trig.type.value if hasattr(trig.type, "value") else trig.type) != "HARM":
        return None
    pl = trig.payload or {}
    victim, attacker = pl.get("body_id"), pl.get("actor_id") or trig.actor_id
    if not attacker or attacker == victim:
        return None
    if tx.query_one("SELECT 1 FROM actors WHERE actor_id=?", (attacker,)) is None or \
            tx.query_one("SELECT 1 FROM actors WHERE actor_id=?", (victim,)) is None:
        return None
    dead = tx.query_one("SELECT dead_at FROM bodies WHERE body_id=?", (victim,))
    if dead is not None and dead[0] is not None and dead[0] < trig.at:
        return None                     # D-132: the dead put down — as everyone must — is no one hurt
    return attacker, _was_fighting(tx, victim, trig.at)


_WOUND_DEATHS = ("blood_loss", "head_wound", "neck_wound", "harm")


def _onlookers(tx, trigger, event_id):
    """D-119: who saw the death or the blow land, and saw who did it."""
    from ..sense.optics import visibility
    k = _killing(tx, trigger)
    if k is None:
        return []
    killer, _provoked, blow_id = k
    blow_at = tx.query_one("SELECT at FROM events WHERE event_id=?", (blow_id,))[0]
    saw = set()
    for e in (event_id, blow_id):
        saw |= {r[0] for r in tx.query("SELECT holder_id FROM percept_log WHERE event_id=? AND channel='visual' AND "
                                       "fidelity IN ('exact','partial')", (e,))}
    from ..society._impl_society import _controller
    out = []
    for h in sorted(saw - {killer, (trigger.payload or {}).get("body_id")}):
        if _controller(tx, h) == "human":
            continue
        named = tx.query_one("SELECT 1 FROM percept_log WHERE holder_id=? AND source_id=? AND channel='visual' AND fidelity IN "
                             "('exact','partial') AND at>=? AND at<=?", (h, killer, blow_at - 10_000, trigger.at)) is not None
        if named or visibility(tx, h, killer, blow_at) in ("clear", "partial"):
            out.append(h)
    return out


def evaluate_precondition(tx, expr, trigger):
    for part in expr.split(" and "):
        m = re.match(r"^\s*(.+?)\s*(==|!=|>=|<=|>|<)\s*(.+?)\s*$", part)
        if not m:
            raise ValueError(f"bad precondition {part}")
        left = _path(tx, m.group(1), trigger)
        if left is _MISSING:
            return False
        try:
            if not _OPS[m.group(2)](left, _lit(m.group(3))):
                return False
        except TypeError:
            return False
    return True


def _theft_witnesses(tx, event_id):
    # CAS-05 (B6): who saw the taking clearly and knows the thing is someone else's
    ev = _row(tx, "SELECT type, actor_id, payload FROM events WHERE event_id=?", (event_id,))
    if ev is None or ev["type"] != "ITEM_TRANSFER" or not ev["actor_id"]:
        return []
    pl = json.loads(ev["payload"])
    taker = ev["actor_id"]
    to = pl.get("to") or {}
    if to.get("kind") != "body" or to.get("id") != taker:
        return []
    theirs = {taker}
    theirs |= {r[0] for r in tx.query("SELECT household_id FROM household_members WHERE actor_id=?", (taker,))}
    theirs |= {r[0] for r in tx.query("SELECT group_id FROM group_members WHERE actor_id=?", (taker,))}
    out = []
    for (holder,) in tx.query("SELECT DISTINCT holder_id FROM percept_log WHERE event_id=? AND fidelity IN ('exact','partial') "
                              "ORDER BY holder_id", (event_id,)):
        if holder == taker:
            continue
        owners = [r[0] for r in tx.query(
            "SELECT p.object_value FROM claim_holdings h JOIN propositions p ON p.prop_id=h.claim_id WHERE h.holder_id=? "
            "AND h.superseded_by IS NULL AND h.believed=1 AND p.subject_type='object' AND p.subject_id=? AND p.predicate='owner'",
            (holder, pl.get("item_id")))]
        if any(o and o not in theirs for o in owners):
            out.append(holder)
    return out


def _held_when(tx, body_id, at):
    """D-134: held (gripped or tied) when it happened: grips taken on it up to ``at`` outnumber those let go, or it is
    restrained now and still alive (a fixture's ropes leave no grip events)."""
    est = tx.query_one("SELECT COUNT(*) FROM events WHERE type='CONTROL_ESTABLISH' AND json_extract(payload,'$.target_id')=? "
                       "AND at<=?", (body_id, at))[0]
    rel = tx.query_one("SELECT COUNT(*) FROM events WHERE type='CONTROL_RELEASE' AND json_extract(payload,'$.target_id')=? "
                       "AND at<=?", (body_id, at))[0]
    if est > rel:
        return True
    b = tx.query_one("SELECT restrained, alive FROM bodies WHERE body_id=?", (body_id,))
    return b is not None and bool(b[0]) and bool(b[1])


def _yielded_when(tx, body_id, at):
    """D-135: had given up when it happened: in the 10 minutes up to ``at`` their latest surrender (ACTION_START verb
    'surrender', GESTURE 'empty_hands') with no attack of theirs after it (an attack in the same instant counts after)."""
    rows = tx.query("SELECT type, payload, at, seq FROM events WHERE actor_id=? AND type IN ('ACTION_START','GESTURE') "
                    "AND at BETWEEN ? AND ?", (body_id, at - 600_000, at))
    return _gave_up([(r[2], r[3], r[0], json.loads(r[1])) for r in rows])


def _gave_up(seen):
    """D-135: of (at, order, event type, payload) rows about one person, whether the latest surrender stands."""
    out = False
    for _at, _o, typ, pl in sorted(seen, key=lambda x: (x[0], x[2] == "ACTION_START" and x[3].get("verb") == "attack", x[1])):
        if (typ == "GESTURE" and pl.get("gesture") == "empty_hands") or (typ == "ACTION_START" and pl.get("verb") == "surrender"):
            out = True
        elif typ == "ACTION_START" and pl.get("verb") == "attack":
            out = False
    return out


def _threatened(tx, trigger, event_id):
    """D-126: who a SPEECH threatened at weapon point (addressed, armed at them, a threat in its words), the PC
    included; never the speaker."""
    from ..mind.firewall import classify_form
    out = []
    for h, det in tx.query("SELECT holder_id, detail FROM percept_log WHERE event_id=? AND channel='speech' ORDER BY "
                           "holder_id", (event_id,)):
        d = json.loads(det) if isinstance(det, str) else (det or {})
        if not (d.get("addressed_to_me") and d.get("armed_at_me")) or h == trigger.actor_id:
            continue
        form = classify_form(d.get("words") or "")
        if (form.value if hasattr(form, "value") else form) == "threat":
            out.append(h)
    return sorted(set(out))


def _theft_victims(tx, event_id):
    """D-129: of a taking's witnesses, those who believe the thing is their own or their household's."""
    ev = _row(tx, "SELECT actor_id, payload FROM events WHERE event_id=?", (event_id,))
    if ev is None:
        return []
    taker, item = ev["actor_id"], json.loads(ev["payload"]).get("item_id")
    theirs = {taker}
    theirs |= {r[0] for r in tx.query("SELECT household_id FROM household_members WHERE actor_id=?", (taker,))}
    theirs |= {r[0] for r in tx.query("SELECT group_id FROM group_members WHERE actor_id=?", (taker,))}
    out = []
    for h in _theft_witnesses(tx, event_id):
        mine = {h} | {r[0] for r in tx.query("SELECT household_id FROM household_members WHERE actor_id=?", (h,))}
        owners = [r[0] for r in tx.query(
            "SELECT p.object_value FROM claim_holdings c JOIN propositions p ON p.prop_id=c.claim_id WHERE c.holder_id=? "
            "AND c.superseded_by IS NULL AND c.believed=1 AND p.subject_type='object' AND p.subject_id=? AND p.predicate='owner'",
            (h, item))]
        if any(o in mine and o not in theirs for o in owners):
            out.append(h)
    return out


def _drained_lately(tx, actor, reason, at):
    """D-129: a Resolve drain of this reason in the hour up to ``at`` (once an hour, however often it happens)."""
    return tx.query_one("SELECT 1 FROM events WHERE type='RESOLVE_CHANGE' AND actor_id=? AND json_extract(payload,'$.reason')=? "
                        "AND at>? AND at<=?", (actor, reason, at - 3_600_000, at)) is not None


def select(tx, selector, trigger):
    m = re.match(r"^(\w+)\((.*)\)$", selector.strip())
    if not m:
        raise ValueError(f"bad selector {selector}")
    fn, arg = m.groups()
    v = _path(tx, arg, trigger) if arg else None
    if v is _MISSING or v is None:
        return []
    if fn == "actor":
        return [v]
    if fn == "body":                                                 # D-123
        return [v] if tx.query_one("SELECT 1 FROM bodies WHERE body_id=?", (v,)) else []
    if fn == "place_of":
        r = _row(tx, "SELECT place_id FROM positions WHERE body_id=?", (v,))
        return [r["place_id"]] if r else []
    if fn == "witnesses_of":
        return sorted({r[0] for r in tx.query("SELECT holder_id FROM percept_log WHERE event_id=?", (v,))})
    if fn == "theft_witnesses_of":
        return _theft_witnesses(tx, v)
    if fn in ("onlookers_of_act", "onlookers_bonded_to_target"):   # D-133
        from ..society._impl_society import _controller
        out = [h for (h,) in tx.query("SELECT DISTINCT holder_id FROM percept_log WHERE event_id=? AND channel='visual' AND "
                                      "fidelity IN ('exact','partial') ORDER BY holder_id", (v,))
               if h != trigger.actor_id and _controller(tx, h) != "human"]
        if fn == "onlookers_bonded_to_target":
            tgt = (trigger.payload or {}).get("target_id")
            out = [h for h in out if tgt and h != tgt and _bonded_to(tx, h, tgt)]
        return out
    if fn == "robbed_by":                                            # D-129: they saw what is theirs taken
        from ..society._impl_society import _controller
        return [h for h in _theft_victims(tx, v) if _controller(tx, h) != "human"]
    if fn == "bonded_onlookers_of":                                  # D-129: someone they love, hurt or killed
        body = (trigger.payload or {}).get("body_id")
        seen = select(tx, "assault_onlookers_of(trigger.event_id)", trigger) if _assault(tx, trigger) is not None \
            else _onlookers(tx, trigger, v)
        return [h for h in seen if _bonded_to(tx, h, body)]
    if fn == "humiliated_by":                                        # D-129: insulted in front of others
        from ..mind.temper import INSULT_WORDS, _words_have
        from ..society._impl_society import _controller
        heard = [(h, json.loads(d) if isinstance(d, str) else (d or {})) for h, d in tx.query(
            "SELECT holder_id, detail FROM percept_log WHERE event_id=? AND channel='speech' AND fidelity IN ('exact','partial') "
            "ORDER BY holder_id", (v,))]
        out = []
        for h, d in heard:
            if h == trigger.actor_id or _controller(tx, h) == "human" or not d.get("addressed_to_me"):
                continue
            if not any(_words_have(d.get("words") or "", x) for x in INSULT_WORDS):
                continue
            if not any(o not in (h, trigger.actor_id) for o, _d in heard) or _drained_lately(tx, h, "humiliated_publicly", trigger.at):
                continue
            out.append(h)
        return sorted(set(out))
    if fn == "made_to_watch":                                        # D-129: held, and made to see it
        body = (trigger.payload or {}).get("body_id")
        doer = (_assault(tx, trigger) or _killing(tx, trigger) or (trigger.actor_id,))[0]
        out = []
        for (h,) in tx.query("SELECT DISTINCT holder_id FROM percept_log WHERE event_id=? AND channel='visual' AND fidelity IN "
                             "('exact','partial') ORDER BY holder_id", (v,)):
            if h in (body, doer) or not _bonded_to(tx, h, body):
                continue
            held = tx.query_one("SELECT restrained FROM bodies WHERE body_id=?", (h,))
            if held is None or not held[0] or _drained_lately(tx, h, "made_to_watch", trigger.at):
                continue
            out.append(h)
        return out
    if fn == "hurt_by_someone":                                      # D-126: the one hurt, never the PC
        a = _assault(tx, trigger)
        victim = (trigger.payload or {}).get("body_id")
        from ..society._impl_society import _controller
        return [victim] if a is not None and _controller(tx, victim) != "human" else []
    if fn == "assault_onlookers_of":                                 # D-126
        from ..sense.optics import visibility
        from ..society._impl_society import _controller
        a = _assault(tx, trigger)
        if a is None:
            return []
        attacker, victim = a[0], (trigger.payload or {}).get("body_id")
        out = []
        for (h,) in tx.query("SELECT DISTINCT holder_id FROM percept_log WHERE event_id=? AND channel='visual' AND "
                             "fidelity IN ('exact','partial') ORDER BY holder_id", (v,)):
            if h in (attacker, victim) or _controller(tx, h) == "human":
                continue
            named = tx.query_one("SELECT 1 FROM percept_log WHERE holder_id=? AND source_id=? AND channel='visual' AND fidelity "
                                 "IN ('exact','partial') AND at>=? AND at<=?", (h, attacker, trigger.at - 10_000, trigger.at))
            if named is not None or visibility(tx, h, attacker, trigger.at) in ("clear", "partial"):
                out.append(h)
        return out
    if fn == "threatened_by":                                        # D-126: a threat at weapon point
        from ..society._impl_society import _controller
        return [h for h in _threatened(tx, trigger, v) if _controller(tx, h) != "human"]
    if fn == "protecting_today":                                     # D-139: once a day, however often
        ev = _row(tx, "SELECT type, actor_id, payload, at FROM events WHERE event_id=?", (v,))
        if ev is None or ev["type"] != "ACTION_START" or not ev["actor_id"]:
            return []
        try:
            d = _def(tx, json.loads(ev["payload"]).get("def_id") or "")
        except KeyError:
            return []
        if "protect_dependent" not in d.tags:
            return []
        alive = tx.query_one("SELECT alive FROM bodies WHERE body_id=?", (ev["actor_id"],))
        if not (alive and alive[0]) or not tx.query_one("SELECT 1 FROM actors WHERE actor_id=?", (ev["actor_id"],)):
            return []
        if tx.query_one("SELECT 1 FROM events WHERE type='RESOLVE_CHANGE' AND actor_id=? AND json_extract(payload,'$.reason')="
                        "'protected_dependent' AND at>? AND at<=?", (ev["actor_id"], ev["at"] - 86_400_000, ev["at"])):
            return []
        return [ev["actor_id"]]
    if fn == "left_bleeding_by":                                     # D-142: walked out on
        from ..society._impl_society import _controller
        ev = _row(tx, "SELECT type, actor_id, payload, at FROM events WHERE event_id=?", (v,))
        if ev is None or ev["type"] != "MOVE":
            return []
        pl = json.loads(ev["payload"])
        who, frm = pl.get("body_id") or ev["actor_id"], pl.get("from_place")
        if not frm or frm == pl.get("to_place") or not tx.query_one("SELECT 1 FROM actors WHERE actor_id=?", (who,)):
            return []
        out = []
        for (h,) in tx.query("SELECT DISTINCT p.holder_id FROM percept_log p JOIN positions s ON s.body_id=p.holder_id WHERE "
                             "p.event_id=? AND p.channel='visual' AND p.fidelity IN ('exact','partial') AND s.place_id=? "
                             "ORDER BY p.holder_id", (v, frm)):
            if h == who or _controller(tx, h) == "human" or not _bonded_to(tx, h, who):
                continue
            if not tx.query_one("SELECT 1 FROM wounds WHERE body_id=? AND healed_at IS NULL AND clotted=0 AND severity IN "
                                "('severe','catastrophic')", (h,)):
                continue
            if tx.query_one("SELECT 1 FROM open_loops WHERE holder_id=? AND kind='grudge' AND subject_ids LIKE ? AND text LIKE "
                            "'%left you bleeding%' AND created_at>?", (h, f'%"{who}"%', ev["at"] - 3_600_000)):
                continue
            out.append(h)
        return out
    if fn in ("kin_group_of", "kin_onlookers_of"):                   # D-144: one of our own killed one of our own
        k = _killing(tx, trigger)
        dead = (trigger.payload or {}).get("body_id")
        if k is None or not dead:
            return []
        groups = sorted({r[0] for r in tx.query("SELECT d.group_id FROM group_members d JOIN group_members k ON k.group_id=d.group_id "
                                                "WHERE d.actor_id=? AND d.status NOT IN ('departed','expelled') AND k.actor_id=? AND "
                                                "k.status IN ('member','probation')", (dead, k[0]))})
        if fn == "kin_group_of" or not groups:
            return groups
        mates = {r[0] for r in tx.query("SELECT m.actor_id FROM group_members m JOIN bodies b ON b.body_id=m.actor_id WHERE "
                                        "m.group_id=? AND m.status IN ('member','probation') AND b.alive=1", (groups[0],))}
        return [h for h in _onlookers(tx, trigger, v) if h in mates and h not in (k[0], dead)]
    if fn == "loved_ones_threatened":                                # D-138: someone you love, at gunpoint
        from ..society._impl_society import _controller
        them = _threatened(tx, trigger, v)
        if not them:
            return []
        heard = {r[0] for r in tx.query("SELECT holder_id FROM percept_log WHERE event_id=? AND channel IN ('speech','visual') "
                                        "AND fidelity IN ('exact','partial')", (v,))}
        return sorted(h for h in heard - set(them) - {trigger.actor_id}
                      if _controller(tx, h) != "human" and any(_bonded_to(tx, h, x) for x in them))
    if fn == "settlements_seeing":                                   # D-124
        from ..society._impl_society import settlement_of as _stl_of
        dead = (trigger.payload or {}).get("body_id")
        holders = {r[0] for r in tx.query("SELECT holder_id FROM percept_log WHERE event_id=? AND channel='visual' AND "
                                          "fidelity IN ('exact','partial')", (v,))} - {dead}
        return sorted({s for s in (_stl_of(tx, h) for h in holders) if s})
    if fn == "seen_clearly_by":                                      # D-123
        dead = (trigger.payload or {}).get("body_id")
        return sorted({r[0] for r in tx.query("SELECT holder_id FROM percept_log WHERE event_id=? AND channel='visual' AND "
                                              "fidelity IN ('exact','partial')", (v,))} - {dead})
    if fn == "onlookers_of":                                         # D-119
        return _onlookers(tx, trigger, v)
    if fn == "groups_that_saw":                                      # D-119
        seen = _onlookers(tx, trigger, v)
        dead = (trigger.payload or {}).get("body_id")
        return sorted({r[0] for r in tx.query("SELECT group_id FROM group_members WHERE actor_id=? AND status IN "
                                              "('member','probation')", (dead,))
                       if any(tx.query_one("SELECT 1 FROM group_members WHERE group_id=? AND actor_id=? AND status IN "
                                           "('member','probation')", (r[0], h)) for h in seen)})
    if fn == "active_task_of":
        from ._impl_p5a import active_task
        t = active_task(tx, v)
        return [t["task_id"]] if t else []
    if fn == "infected_within_hearing_of":
        return []   # P10 hearing thresholds
    from ..society import _impl_society as soc
    if fn == "household_of":
        h = soc.household_of(tx, v)
        return [h] if h else []
    if fn == "settlement_of":
        sid = soc.settlement_of(tx, v)
        return [sid] if sid else []
    if fn == "workplace_of":
        return [v] if _row(tx, "SELECT 1 AS x FROM workplaces WHERE workplace_id=?", (v,)) else []
    if fn == "work_assignments_of":
        rows = [dict(r) for r in tx.query("SELECT * FROM work_assignments WHERE actor_id=?", (v,))]
        return sorted(soc._key(r) for r in rows)
    if fn == "cover_candidate_for":
        pl = trigger.payload
        c = soc.pick_cover(tx, v, pl.get("role"), pl.get("shift_start_hh"), pl.get("shift_end_hh"), pl.get("actor_id"))
        return [c] if c else []
    if fn == "heads_of_households_with_dependents":
        out = []
        for h in soc.households_of(tx, v):
            if soc.has_dependents(tx, h):
                hd = soc.head_of(tx, h)
                if hd and soc._controller(tx, hd) != "human":
                    out.append(hd)
        return sorted(set(out))
    if fn == "head_of_worst_hit_household":
        h = soc.worst_hit(tx, v)
        hd = soc.head_of(tx, h) if h else None
        return [hd] if hd and soc._controller(tx, hd) != "human" else []
    if fn in ("leadership_of", "group_of"):
        r = _row(tx, "SELECT group_id FROM settlements WHERE settlement_id=?", (v,))
        return [r["group_id"]] if r and r["group_id"] else []
    if fn == "who_would_hear_of":
        out = set()
        for r in tx.query("SELECT household_id FROM household_members WHERE actor_id=?", (v,)):
            out |= set(soc.hh_members(tx, r[0]))
        for r in tx.query("SELECT group_id FROM group_members WHERE actor_id=? AND status IN ('member','probation')", (v,)):
            out |= set(soc.g_members(tx, r[0]))
        for r in tx.query("SELECT holder_id FROM acquaintance WHERE subject_id=? AND known_name IS NOT NULL", (v,)):
            if soc._alive(tx, r[0]):
                out.add(r[0])
        out.discard(v)
        return sorted(out)
    raise NotImplementedError(f"selector {fn} (P9)")


def sweep(tx, deltas, rules, at, turn_index):
    first = tx.query_one("SELECT COALESCE(MAX(seq),0) FROM events")[0]
    queue = [(e, 0) for e in deltas]
    rules = sorted(rules, key=lambda r: r.id)
    while queue:
        ev, depth = queue.pop(0)
        if depth >= 3:
            continue
        for rule in rules:
            if rule.trigger_event != (ev.type.value if hasattr(ev.type, "value") else ev.type):
                continue
            if any(ev.payload.get(k, _MISSING) != v for k, v in rule.where.items()):
                continue
            try:
                if not all(evaluate_precondition(tx, p, ev) for p in rule.preconditions):
                    continue
            except NotImplementedError:
                _unbuilt(tx, rule, "precondition", at, turn_index)
                continue
            for idx, eff in enumerate(rule.effects):
                try:
                    from . import cascade as _cascade_mod   # the module attribute, so a monkeypatch reaches it
                    ids = _cascade_mod.select(tx, eff.target, ev) if eff.target else []
                except NotImplementedError:
                    _unbuilt(tx, rule, eff.event_type or eff.kind, at, turn_index)
                    continue
                for tid in ids:
                    with tx.citing(rule.id, depth + 1):
                        if eff.kind == "schedule_event" or (rule.delay_s or 0) > 0:
                            made = _schedule(tx, rule, idx, eff, tid, ev, at)
                        else:
                            made = _dispatch(tx, rule, eff, tid, ev, depth + 1, at, turn_index)
                    queue += [(m, depth + 1) for m in made]
    return _events_since(tx, first)


def _guardian_of(tx, actor, subject):
    return tx.query_one("SELECT 1 FROM household_members WHERE actor_id=? AND EXISTS (SELECT 1 FROM json_each(guardian_of) "
                        "WHERE value=?)", (actor, subject)) is not None


def _bonded_to(tx, actor, subject):
    """D-123: affection >= 1 toward them, or one household."""
    r = tx.query_one("SELECT affection FROM relationships WHERE from_id=? AND to_id=?", (actor, subject))
    if r is not None and r[0] >= 1:
        return True
    return tx.query_one("SELECT 1 FROM household_members a JOIN household_members b ON a.household_id=b.household_id "
                        "WHERE a.actor_id=? AND b.actor_id=?", (actor, subject)) is not None


def _grieved(tx, actor, subject):
    """D-123: a loss is grieved once — an earlier grief drain of this actor whose cause names the subject."""
    return tx.query_one(
        "SELECT 1 FROM events r JOIN events c ON c.event_id = r.cause_event_id WHERE r.type='RESOLVE_CHANGE' AND "
        "json_extract(r.payload,'$.actor_id')=? AND json_extract(r.payload,'$.reason') IN ('witness_bonded_death','lost_dependent') "
        "AND (json_extract(c.payload,'$.body_id')=? OR json_extract(c.payload,'$.about_id')=?)",
        (actor, subject, subject)) is not None


def _unbuilt(tx, rule, what, at, turn_index):
    from ..audit.log import record
    record(tx, "G10-cascade", "action.cascade", "warn", [{"kind": "cascade_unbuilt", "rule_id": rule.id, "what": what}], turn_index)


def _dispatch(tx, rule, eff, target, trig, depth, at, turn_index):
    if eff.kind == "emit_event" and eff.event_type == "TASK_STEP" and eff.payload.get("status") == "paused":
        from ._impl_p5a import pause
        ev = pause(tx, target, at, trig.event_id, turn_index)
        return [] if ev is None else [ev]
    if eff.kind == "drain_resolve":
        from ..mind.resolve import drain
        reason = eff.payload.get("cause", "coerced")
        R = tx.rules.resolve
        if reason not in R.drains:
            reason = "coerced"
        alive = tx.query_one("SELECT b.alive FROM actors a JOIN bodies b ON b.body_id = a.actor_id WHERE a.actor_id=?", (target,))
        if alive is None or not alive[0]:
            return []
        scale = (eff.payload or {}).get("scale_by")
        if scale in ("bond_to_subject", "dependent_of_subject"):        # D-123
            pl = trig.payload or {}
            subj = pl.get("body_id") or pl.get("about_id") or pl.get("subject_id")
            if not subj or subj == target or _grieved(tx, target, subj):
                return []
            if _guardian_of(tx, target, subj):
                reason = "lost_dependent"
            elif scale == "dependent_of_subject" or not _bonded_to(tx, target, subj):
                return []
        ev = drain(tx, target, reason, trig.event_id, at, turn_index)
        return [] if ev is None else [ev]
    if eff.kind == "emit_event" and eff.event_type in ("RELATION_CHANGE", "LOOP_OPENED"):
        from ..mind.mind import open_loop, relate
        pl = {k: _resolve_value(tx, v, trig) for k, v in eff.payload.items()}
        if eff.event_type == "RELATION_CHANGE":
            ev = relate(tx, target, pl["toward"], pl["axis"], int(pl["delta"]), trig.event_id, at, turn_index)
            return [] if ev is None else [ev]
        before = tx.query_one("SELECT MAX(seq) FROM events")[0] or 0
        open_loop(tx, target, pl["kind"], pl.get("text") or "", [pl["subject"]] if pl.get("subject") else [], int(pl.get("strength") or 2),
                  trig.event_id, at, turn_index)
        return _events_since(tx, before)
    if eff.kind == "recover_resolve":                                # D-122
        from ..mind.resolve import recover
        alive = tx.query_one("SELECT b.alive FROM actors a JOIN bodies b ON b.body_id = a.actor_id WHERE a.actor_id=?", (target,))
        if alive is None or not alive[0]:
            return []
        ev = recover(tx, target, eff.payload.get("cause"), trig.event_id, at, turn_index)
        return [] if ev is None else [ev]
    if eff.kind == "adjust_stress":
        from ..mind.actor import adjust_stress
        alive = tx.query_one("SELECT b.alive FROM actors a JOIN bodies b ON b.body_id = a.actor_id WHERE a.actor_id=?", (target,))
        if alive is None or not alive[0]:
            return []
        subj = (trig.payload or {}).get("body_id")
        bond = 0
        if (eff.payload or {}).get("scale_by") == "bond_to_subject":
            if subj == target:
                return []
            r = tx.query_one("SELECT affection FROM relationships WHERE from_id=? AND to_id=?", (target, subj)) if subj else None
            if r and r[0] >= 1:
                bond = min(3, r[0])
        ev = adjust_stress(tx, target, int(eff.amount) + bond, trig.event_id, at, turn_index)
        return [] if ev is None else [ev]
    made = _dispatch_p9(tx, rule, eff, target, trig, at, turn_index)
    if made is not None:
        return made
    _unbuilt(tx, rule, eff.event_type or eff.kind, at, turn_index)
    return []


def _dispatch_p9(tx, rule, eff, target, trig, at, turn_index):
    from ..society import _impl_society as soc
    from ..world import _impl_rumours as rum
    pl = {k: _resolve_value(tx, v, trig) for k, v in eff.payload.items()}
    E = trig.event_id
    before = tx.query_one("SELECT COALESCE(MAX(seq),0) FROM events")[0]
    et = eff.event_type
    if eff.kind == "emit_event" and et == "HOUSEHOLD_CHANGE":
        soc.apply_change(tx, target, pl["change"], pl.get("actor_id"), at, turn_index, E, grief_delta=int(pl.get("grief_delta") or 0))
    elif eff.kind == "emit_event" and et == "SHIFT_MISSED":
        soc.miss_shift(tx, target, pl.get("reason") or "missed", at, turn_index, E)
    elif eff.kind == "emit_event" and et == "ROLE_ASSIGNED":
        soc.assign_cover(tx, target, pl["workplace_id"], pl["role"], int(pl["shift_start_hh"]), int(pl["shift_end_hh"]), pl["covering_for"],
                         at, turn_index, E)
    elif eff.kind == "emit_event" and et == "SHORTAGE":
        soc.declare_shortage(tx, target, pl["resource"], at, turn_index, E)
    elif eff.kind == "emit_event" and et == "RATION_CHANGE":
        soc.change_ration(tx, target, int(pl["delta"]), pl.get("cause") or "cascade", at, turn_index, E)
    elif eff.kind == "emit_event" and et == "LAW_APPLIED":
        if not (pl.get("where_in_force") and soc.law_def(tx, target, pl["law"]) is None):   # D-124
            soc.apply_law(tx, target, pl["law"], pl["subject"], at, turn_index, E)
    elif eff.kind == "emit_event" and et == "TENSION_CHANGE":
        soc.adjust_tension(tx, target, pl["toward"], int(pl["delta"]), pl.get("cause") or "", at, turn_index, E)
    elif eff.kind == "emit_event" and et == "LOYALTY_CHECK":
        soc.loyalty_check(tx, target, pl["group"], pl.get("reason") or "cascade", at, turn_index, E)
    elif eff.kind == "emit_event" and et == "AWARENESS_CHANGE":         # D-146: a night broken
        from ..physical.bodies import wake
        over = tx.query_one("SELECT 1 FROM events WHERE seq > (SELECT seq FROM events WHERE event_id=?) AND type IN "
                            "('AWARENESS_CHANGE','POSTURE_CHANGE') AND json_extract(payload,'$.body_id')=? AND "
                            "json_extract(payload,'$.awareness')='awake'", (E, target))
        if over is None:
            wake(tx, target, at, E, turn_index)
    elif eff.kind == "emit_event" and et == "STANDING_CHANGE":           # D-119
        from ..mind.mind import adjust_group_standing
        if pl.get("toward"):
            adjust_group_standing(tx, target, pl["toward"], int(pl["delta"]), E, at, turn_index)
    elif eff.kind == "adjust":
        kind = str(target).split("_")[0]
        if kind == "wkp":
            soc.work_adjust(tx, target, eff.field, eff.amount, at, turn_index, E)
        elif kind == "stl":
            soc.stl_adjust(tx, target, eff.field, eff.amount, at, turn_index, E)
        else:
            raise ValueError(f"adjust cannot target {target}")
    elif eff.kind == "create_rumour":
        rum.seed(tx, target, pl["about"], pl["claim"], at, turn_index, E, confidence=int(pl.get("confidence") or 3))
    elif eff.kind == "emit_event" and et == "INFECTED_DRIFT":
        from ..world import infected
        infected.attract(tx, target, pl["toward"], at, E, turn_index, reason=pl.get("reason") or "noise")
    elif eff.kind == "create_trace":
        from ..action.cascade import TRACE_TEXT
        from ..world import traces
        traces.create(tx, target, pl["kind"], pl.get("text") or TRACE_TEXT[pl["kind"]], E, at, turn_index)
    else:
        return None
    return _events_since(tx, before)


def _schedule(tx, rule, idx, eff, target, trig, at):
    from ..kernel import clock
    from ..society._impl_society import parse_key
    from ..society.settlement import next_hour
    if eff.payload.get("due") == "next_shift_start":
        due = next_hour(at, parse_key(target)[3])
    elif "due_s" in eff.payload:
        due = at + int(float(eff.payload["due_s"]) * 1000)
    else:
        due = at + int((rule.delay_s or 0) * 1000)
    before = tx.query_one("SELECT COALESCE(MAX(seq),0) FROM events")[0]
    clock.schedule(tx, due, "CASCADE_EFFECT", target,
                   {"rule_id": rule.id, "effect_index": idx, "target": target, "trigger_event_id": trig.event_id}, trig.event_id)
    return _events_since(tx, before)


def fire_scheduled(tx, rng, row, fired, turn_index):
    from ..audit.log import record
    pl = json.loads(row["payload"]) if isinstance(row["payload"], str) else dict(row["payload"])
    rule = next((r for r in _canon(tx).all("cascade") if r.id == pl["rule_id"]), None)
    if rule is None:
        record(tx, "G10-cascade", "action.cascade", "warn", [{"kind": "cascade_rule_gone", "rule_id": pl["rule_id"]}], turn_index)
        return []
    eff = rule.effects[pl["effect_index"]]
    eff2 = eff.model_copy(update={"kind": "emit_event" if eff.kind == "schedule_event" else eff.kind,
                                  "payload": {k: v for k, v in eff.payload.items() if k not in ("due", "due_s")}})
    tr = tx.query_one("SELECT * FROM events WHERE event_id=?", (pl["trigger_event_id"],))
    trig = _ev_model(tx, tr)
    before = tx.query_one("SELECT COALESCE(MAX(seq),0) FROM events")[0]
    with tx.citing(rule.id, 0):
        _dispatch(tx, rule, eff2, pl["target"], trig, 0, row["due_at"], turn_index)
    return _events_since(tx, before)


def _resolve_value(tx, v, trig):
    if isinstance(v, str) and v.startswith("$"):
        expr = v[1:]
        if expr.startswith("trigger."):
            got = _path(tx, expr, trig)
            return None if got is _MISSING else got
        ids = select(tx, expr, trig)
        return ids[0] if ids else None
    return v




# ============================================================ scheduler
def plan_cognition(candidates, config, turn_depth, lanes_up):
    from ..lanes.scheduler import CognitionPlan
    S = config.rules.scheduler
    plan = CognitionPlan()
    order = sorted([c for c in candidates if c[2]], key=lambda c: (-c[1], c[0])) + sorted([c for c in candidates if not c[2]], key=lambda c: (-c[1], c[0]))
    plan.order = [a for a, _s, _m in order]                  # D-128: who comes first, for the room's lines
    if not lanes_up:
        for a, _s, _m in order:
            plan.lod[a] = LOD.COLD
        plan.notes.append("NO_LANES")
        return plan
    conc = {Lane.A: config.lanes[Lane.A].max_concurrency, Lane.B: config.lanes[Lane.B].max_concurrency}
    tot = {Lane.A: 0.0, Lane.B: 0.0}
    wall = lambda: max(tot[Lane.A] / conc[Lane.A], tot[Lane.B] / conc[Lane.B])  # noqa: E731
    budget = S.turn_budget_s[turn_depth] - S.reserve_narration_s
    hot_lane = config.hot_cognition.lane
    warm = config.regimes[CallClass.ACTOR_COGNITION].lane
    warm_lane = warm if warm in lanes_up else next(l for l in (Lane.B, Lane.A) if l in lanes_up)
    i = 0
    if hot_lane in lanes_up:
        for a, _s, _m in order[: S.max_hot[turn_depth]]:
            plan.lod[a] = LOD.HOT
            plan.lane[a] = hot_lane
            tot[hot_lane] += S.estimated_call_s["actor_cognition_hot"]
            i += 1
    cold = False
    for a, _s, mand in order[i:]:
        if cold and not mand:
            plan.lod[a] = LOD.COLD
            continue
        lane = warm_lane
        est = S.estimated_call_s["actor_cognition_warm"]
        tot[lane] += est
        if wall() > budget:
            if mand:
                plan.overrun = True
                plan.notes.append(f"BUDGET_OVERRUN {a}")
            else:
                tot[lane] -= est
                plan.lod[a] = LOD.COLD
                cold = True
                continue
        plan.lod[a] = LOD.WARM
        plan.lane[a] = lane
    plan.est_wall_s = wall()
    return plan
