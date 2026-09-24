"""Implementation: conflict, resolve, intent (barrier etc.), reactions, propagate,
cascade, scheduler.plan_cognition."""
from __future__ import annotations

import dataclasses
import json
import math
import re

from ..contracts.common import LOD, Lane, Verb, attr_mod
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
                      "paces": list(b.paces)}}


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
    sp = d["speech"]
    ins = d.get("inscription")
    return Intent(actor_id=d["actor_id"], bound=BoundAffordance(**bd),
                  speech=None if sp is None else SpeechAct(text=sp["text"], to=tuple(sp["to"]), volume=Volume(sp["volume"]),
                                                           delivery=sp.get("delivery", "ordinary"),
                                                           timing=sp.get("timing", "alongside")),
                  manner=d["manner"], goal=d["goal"], private_reason=d["private_reason"], source=d["source"], lod=LOD(d["lod"]),
                  blocked=d.get("blocked"), pace=d.get("pace", "normal"),
                  inscription=None if ins is None else InscriptionAct(text=ins["text"],
                                                                      quotation_source=ins.get("quotation_source")))


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
                                          "est_duration_s": b.est_duration_s, "visible": d.visible_act, "seen": SEEN.get(b.def_id),
                                          "continues_task": b.def_id == "keep_working", "label": b.label, "goal": intent.goal}))


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
            if old.bound.signature == i.bound.signature:
                carry = True
                continue
            clock.cancel(tx, row["queue_id"], "new_action", wave_at, pl.get("start_event_id"), turn_index)
            tx.commit_event(Event(type=EventType.ACTION_INTERRUPT, writer="action.resolve", at=wave_at, turn_index=turn_index, actor_id=i.actor_id,
                                  cause_event_id=pl.get("start_event_id"),
                                  payload={"actor_id": i.actor_id, "def_id": old.bound.def_id, "cause": "new_action"}))
        if carry:
            continue
        st = _start_event(tx, i, wave_at, turn_index)
        if i.speech is not None:
            R = tx.rules.acoustics
            vol = i.speech.volume.value if hasattr(i.speech.volume, "value") else i.speech.volume
            tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=wave_at, turn_index=turn_index, actor_id=i.actor_id,
                                  cause_event_id=st.event_id,
                                  payload={"words": i.speech.text, "volume": vol, "to": list(i.speech.to), "source_db": R.speech_db[vol],
                                           "armed": _armed(tx, i.actor_id)}))
        d = _def(tx, i.bound.def_id)
        la = wave_at if d.duration.condition_ended else land_ms(wave_at, i.bound.est_duration_s)
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
    for la, i, st in started:
        if la > horizon_ms:
            clock.schedule(tx, la, "ACTION_LAND", i.actor_id, {"intent": intent_to_dict(i), "start_event_id": st.event_id}, st.event_id)
            continue
        _land(tx, rng, i, la, EffectCtx(turn_index=turn_index, horizon_ms=horizon_ms, start_event_id=st.event_id, wave_start_ms=wave_at))
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
        if mat and h not in found:
            found[h] = p["at"]
    return sorted(found.items(), key=lambda kv: (kv[1], kv[0]))


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
    m = re.match(r"^(\w+)\((.+)\)\.(\w+)$", path)
    if m:
        fn, inner, col = m.groups()
        ids = select(tx, f"{fn}({inner})", trig)
        if not ids:
            return _MISSING
        if fn == "actor":
            r = _row(tx, "SELECT * FROM actors WHERE actor_id=?", (ids[0],))
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
    if fn == "place_of":
        r = _row(tx, "SELECT place_id FROM positions WHERE body_id=?", (v,))
        return [r["place_id"]] if r else []
    if fn == "witnesses_of":
        return sorted({r[0] for r in tx.query("SELECT holder_id FROM percept_log WHERE event_id=?", (v,))})
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
        soc.apply_law(tx, target, pl["law"], pl["subject"], at, turn_index, E)
    elif eff.kind == "emit_event" and et == "TENSION_CHANGE":
        soc.adjust_tension(tx, target, pl["toward"], int(pl["delta"]), pl.get("cause") or "", at, turn_index, E)
    elif eff.kind == "emit_event" and et == "LOYALTY_CHECK":
        soc.loyalty_check(tx, target, pl["group"], pl.get("reason") or "cascade", at, turn_index, E)
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
    if not lanes_up:
        for a, _s, _m in order:
            plan.lod[a] = LOD.COLD
        plan.notes.append("NO_LANES")
        return plan
    conc = {Lane.A: config.lanes[Lane.A].max_concurrency, Lane.B: config.lanes[Lane.B].max_concurrency}
    tot = {Lane.A: 0.0, Lane.B: 0.0}
    wall = lambda: max(tot[Lane.A] / conc[Lane.A], tot[Lane.B] / conc[Lane.B])  # noqa: E731
    budget = S.turn_budget_s[turn_depth] - S.reserve_narration_s
    i = 0
    if Lane.A in lanes_up:
        for a, _s, _m in order[: S.max_hot[turn_depth]]:
            plan.lod[a] = LOD.HOT
            plan.lane[a] = Lane.A
            tot[Lane.A] += S.estimated_call_s["actor_cognition_hot"]
            i += 1
    cold = False
    for a, _s, mand in order[i:]:
        if cold and not mand:
            plan.lod[a] = LOD.COLD
            continue
        ups = [l for l in (Lane.B, Lane.A) if l in lanes_up]
        lane = min(ups, key=lambda l: (tot[l] / conc[l], 0 if l == Lane.B else 1))
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
