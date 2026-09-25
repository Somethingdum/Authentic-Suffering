"""Implementation of society/* (P9)."""
from __future__ import annotations

import json
import math

from ..contracts.common import ANATOMY_GROUP, AgeBand, OpenLoopKind, RelationAxis
from ..contracts.events import Event, EventType, WriteOp, WriteRecord

H = 3_600_000
DAY = 86_400_000
_BANDS = [b.value for b in AgeBand]


# ------------------------------------------------------------------ helpers
def _row(s, sql, p=()):
    r = s.query_one(sql, p)
    return dict(r) if r is not None else None


def _rows(s, sql, p=()):
    return [dict(r) for r in s.query(sql, p)]


def _j(v):
    if v is None:
        return None
    return json.loads(v) if isinstance(v, str) else v


def _R(s):
    return s.rules.society


def _W(op, table, values=None, key=None):
    return WriteRecord(op=op, table=table, values=values or {}, key=key or {})


def _maxseq(tx):
    return tx.query_one("SELECT COALESCE(MAX(seq),0) FROM events")[0]


def _since(tx, seq):
    from ..action._impl_p5b import _events_since
    return _events_since(tx, seq)


def _commit(tx, **kw):
    return tx.commit_event(Event(**kw))


def _alive(s, b):
    r = _row(s, "SELECT alive FROM bodies WHERE body_id=?", (b,))
    return bool(r and r["alive"])


def _controller(s, a):
    r = _row(s, "SELECT controller FROM actors WHERE actor_id=?", (a,))
    return r["controller"] if r else None


def _hours(s, e):
    s, e = int(s) % 24, int(e) % 24
    n = (e - s) % 24 or 24
    return [(s + i) % 24 for i in range(n)]


def _hour(ms):
    from ..kernel.clock import world_time
    return world_time(ms).hour


def _num(v):
    v = round(v, 2)
    return int(v) if v == int(v) else v


# ================================================================== population
def census(store, settlement_id):
    from ..society.population import Census
    s = _row(store, "SELECT * FROM settlements WHERE settlement_id=?", (settlement_id,))
    if s is None:
        raise ValueError(f"unknown settlement {settlement_id}")
    bands = {b: 0 for b in _BANDS}
    named = []
    if s["group_id"]:
        for r in _rows(store, "SELECT gm.actor_id, b.age_band FROM group_members gm JOIN actors a ON a.actor_id=gm.actor_id "
                              "JOIN bodies b ON b.body_id=gm.actor_id WHERE gm.group_id=? AND gm.status IN ('member','probation') "
                              "AND b.alive=1 ORDER BY gm.actor_id", (s["group_id"],)):
            named.append(r["actor_id"])
            bands[r["age_band"]] += 1
    unnamed = 0
    for c in _rows(store, "SELECT age_band, count FROM cohorts WHERE settlement_id=? ORDER BY cohort_id", (settlement_id,)):
        bands[c["age_band"]] += c["count"]
        unnamed += c["count"]
    return Census(settlement_id, tuple(named), bands, unnamed, len(named) + unnamed)


_GROUPS = (("young", ("infant", "child"), "children"), ("youth", ("preteen", "teen"), "young people"),
           ("adults", ("adult",), "adults"), ("elders", ("elder",), "elders"))


def demographic_issues(c, rules):
    if c.total <= rules.demo_min_population:
        return []
    out = []
    for g, bands, word in _GROUPS:
        n = sum(c.by_band[b] for b in bands)
        share = n / c.total
        lo, hi = rules.pyramid[g]
        if share < lo or share > hi:
            out.append(f"Too {'few' if share < lo else 'many'} {word}: {n} of {c.total} ({int(share * 100 + 0.5)}%), "
                       f"expected {int(lo * 100 + 0.5)}-{int(hi * 100 + 0.5)}%.")
    return out


def consumption(c, rules):
    return {"food": sum(c.by_band[b] * rules.food_per_day[b] for b in _BANDS),
            "water": sum(c.by_band[b] * rules.water_per_day[b] for b in _BANDS)}


def adjust_cohort(tx, cohort_id, delta, reason, at, turn_index, cause_event_id):
    if delta == 0:
        raise ValueError("delta 0")
    c = _row(tx, "SELECT * FROM cohorts WHERE cohort_id=?", (cohort_id,))
    if c is None:
        raise ValueError(f"unknown cohort {cohort_id}")
    after = c["count"] + delta
    if after < 0:
        raise ValueError("a cohort cannot go below 0")
    return _commit(tx, type=EventType.POPULATION_CHANGE, writer="society.population", at=at, turn_index=turn_index,
                   cause_event_id=cause_event_id,
                   payload={"cohort_id": cohort_id, "settlement_id": c["settlement_id"], "delta": delta,
                            "count_before": c["count"], "count_after": after, "reason": reason},
                   writes=[_W(WriteOp.UPDATE, "cohorts", {"count": after}, {"cohort_id": cohort_id})])


# ================================================================== household
def hh_members(store, household_id, living=True):
    ids = [r["actor_id"] for r in _rows(store, "SELECT actor_id FROM household_members WHERE household_id=? ORDER BY actor_id", (household_id,))]
    return [a for a in ids if _alive(store, a)] if living else ids


def household_of(store, actor_id):
    r = _row(store, "SELECT MIN(household_id) AS h FROM household_members WHERE actor_id=?", (actor_id,))
    return r["h"] if r else None


def head_of(store, household_id):
    rows = _rows(store, "SELECT hm.actor_id, hm.role, b.age_years FROM household_members hm JOIN bodies b ON b.body_id=hm.actor_id "
                        "WHERE hm.household_id=? AND b.alive=1 ORDER BY hm.actor_id", (household_id,))
    for role in ("head", "partner"):
        for r in rows:
            if r["role"] == role:
                return r["actor_id"]
    adults = [r for r in rows if (r["age_years"] or 0) >= 15]
    if adults:
        return sorted(adults, key=lambda r: (-r["age_years"], r["actor_id"]))[0]["actor_id"]
    return None


def dependents_of(store, actor_id):
    out = set()
    for r in _rows(store, "SELECT guardian_of FROM household_members WHERE actor_id=?", (actor_id,)):
        out |= set(_j(r["guardian_of"]) or [])
    return sorted(a for a in out if _alive(store, a))


def _is_dependent(r):
    return r["role"] in ("child", "dependent") or r["age_band"] in ("infant", "child", "preteen")


def _living_rows(store, household_id):
    return _rows(store, "SELECT hm.actor_id, hm.role, b.age_band, b.age_years FROM household_members hm JOIN bodies b "
                        "ON b.body_id=hm.actor_id WHERE hm.household_id=? AND b.alive=1 ORDER BY hm.actor_id", (household_id,))


def has_dependents(store, household_id):
    return any(_is_dependent(r) for r in _living_rows(store, household_id))


def households_of(store, settlement_id):
    out = {r["household_id"] for r in _rows(store, "SELECT household_id FROM households WHERE settlement_id=?", (settlement_id,))}
    named = set(census(store, settlement_id).named)
    for r in _rows(store, "SELECT household_id, actor_id FROM household_members"):
        if r["actor_id"] in named:
            out.add(r["household_id"])
    return sorted(out)


def worst_hit(store, settlement_id):
    from ..physical.bodies import capacity
    best = None
    for h in households_of(store, settlement_id):
        rows = _living_rows(store, h)
        if not rows:
            continue
        deps = [r for r in rows if _is_dependent(r)]
        prov = [r for r in rows if not _is_dependent(r) and (r["age_years"] or 0) >= 15 and capacity(store, r["actor_id"]).mobile]
        ratio = len(deps) / max(1, len(prov))
        hs = _row(store, "SELECT shared_stores FROM households WHERE household_id=?", (h,))
        stores = sum((_j(hs["shared_stores"]) or {}).values())
        key = (-ratio, stores, h)
        if best is None or key < best[0]:
            best = (key, h)
    return best[1] if best else None


def apply_change(tx, household_id, change, actor_id, at, turn_index, cause_event_id, grief_delta=0):
    if change not in ("member_died", "member_joined", "member_left", "grief_eased"):
        raise ValueError(f"unknown household change {change}")
    h = _row(tx, "SELECT * FROM households WHERE household_id=?", (household_id,))
    if h is None:
        raise ValueError(f"unknown household {household_id}")
    writes = []
    here = _row(tx, "SELECT 1 AS x FROM household_members WHERE household_id=? AND actor_id=?", (household_id, actor_id)) if actor_id else None
    if change == "member_joined":
        if here:
            raise ValueError("already a member")
        writes.append(_W(WriteOp.INSERT, "household_members", {"household_id": household_id, "actor_id": actor_id, "role": "lodger",
                                                                "guardian_of": [], "protection_priority": 0}))
    elif change == "member_left":
        if not here:
            raise ValueError("not a member")
        writes.append(_W(WriteOp.DELETE, "household_members", key={"household_id": household_id, "actor_id": actor_id}))
    gb = h["grief_state"]
    ga = gb
    if grief_delta:
        ga = max(0, min(3, gb + grief_delta))
        writes.append(_W(WriteOp.UPDATE, "households", {"grief_state": ga}, {"household_id": household_id}))
    return _commit(tx, type=EventType.HOUSEHOLD_CHANGE, writer="society.household", at=at, turn_index=turn_index,
                   actor_id=actor_id, cause_event_id=cause_event_id, writes=writes,
                   payload={"household_id": household_id, "change": change, "actor_id": actor_id,
                            "grief_before": gb, "grief_after": ga})


def household_day(tx, household_id, at, turn_index, cause_event_id):
    h = _row(tx, "SELECT grief_state FROM households WHERE household_id=?", (household_id,))
    if not h or h["grief_state"] <= 0:
        return None
    last = tx.query_one("SELECT MAX(at) FROM events WHERE type='HOUSEHOLD_CHANGE' AND json_extract(payload,'$.household_id')=?",
                        (household_id,))[0]
    if last is not None and at - last < _R(tx).grief_ease_days * DAY:
        return None
    return apply_change(tx, household_id, "grief_eased", None, at, turn_index, cause_event_id, grief_delta=-1)


# ================================================================== routine
def _settlement_of_actor(s, actor_id):
    r = _row(s, "SELECT MIN(st.settlement_id) AS sid FROM settlements st JOIN group_members gm ON gm.group_id=st.group_id "
                "WHERE gm.actor_id=? AND gm.status IN ('member','probation')", (actor_id,))
    return r["sid"] if r else None


def steps_for(store, actor_id):
    from ..society.routine import Step
    b = _row(store, "SELECT * FROM bodies WHERE body_id=?", (actor_id,))
    if b is None or not b["alive"]:
        return []
    ctl = _controller(store, actor_id)
    if ctl is None or ctl == "human":
        return []
    sid = _settlement_of_actor(store, actor_id)
    if sid is None:
        return []
    R = _R(store)
    st = _row(store, "SELECT * FROM settlements WHERE settlement_id=?", (sid,))
    hh = household_of(store, actor_id)
    dw = _row(store, "SELECT dwelling_place FROM households WHERE household_id=?", (hh,)) if hh else None
    dwell = (dw or {}).get("dwelling_place") or st["place_id"]
    slots = [None] * 24
    slot_row = {}
    rows = _rows(store, "SELECT wa.*, w.place_id FROM work_assignments wa JOIN workplaces w ON w.workplace_id=wa.workplace_id "
                        "WHERE wa.actor_id=? ORDER BY wa.shift_start_hh, wa.workplace_id, wa.role", (actor_id,))
    for r in rows:
        for h in _hours(r["shift_start_hh"], r["shift_end_hh"]):
            if slots[h] is None:
                slots[h] = ("work", r["place_id"], r["workplace_id"], r["role"])
                slot_row[h] = r
    band = b["age_band"]
    if band in ("infant", "child"):
        window = _hours(*R.child_sleep)
    elif slots[0] is not None:
        ss = slot_row[0]["shift_end_hh"]
        window = _hours(ss, (ss + R.sleep_h) % 24)
    else:
        window = _hours(*R.adult_sleep)
    run = []
    for h in window:
        if slots[h] is not None:
            break
        run.append(h)
    if len(run) >= R.min_sleep_h:
        for h in run:
            slots[h] = ("sleep", dwell, None, None)
    act = "play" if band in ("infant", "child", "preteen") else "free"
    place = dwell if band == "infant" else st["place_id"]
    for h in range(24):
        if slots[h] is None:
            slots[h] = (act, place, None, None)
    if all(x == slots[0] for x in slots):
        return [Step(0, 0, *slots[0])]
    starts = [h for h in range(24) if slots[h] != slots[(h - 1) % 24]]
    return [Step(s0, starts[(i + 1) % len(starts)], *slots[s0]) for i, s0 in enumerate(starts)]


def step_for(store, actor_id, hour):
    for st in steps_for(store, actor_id):
        if hour in _hours(st.start_hh, st.end_hh):
            return st
    return None


def next_boundary(store, actor_id, after_ms):
    steps = steps_for(store, actor_id)
    if not steps:
        return None
    starts = {st.start_hh for st in steps}
    t = (after_ms // H + 1) * H
    for _ in range(48):
        if _hour(t) in starts:
            return t
        t += H
    return None


def routine_step(tx, rng, row, fired, turn_index):
    from dataclasses import asdict
    from ..kernel import clock
    from ..physical import bodies as B
    from ..physical.space import move_event
    actor = row["subject_id"]
    at = row["due_at"]
    cause = fired.event_id
    first = _maxseq(tx)
    steps = steps_for(tx, actor)
    b = _row(tx, "SELECT * FROM bodies WHERE body_id=?", (actor,))
    st = None
    if not steps:
        outcome, reason = "ended", ("dead" if not b or not b["alive"] else "no routine")
    elif b["awareness"] == "unconscious" or b["restrained"]:
        outcome, reason = "skipped", "unable"
    elif _row(tx, "SELECT 1 AS x FROM tasks WHERE actor_id=? AND status='active'", (actor,)) or clock.pending_for(tx, "ACTION_LAND", actor):
        outcome, reason = "skipped", "busy"
    elif any(actor in _j(r[0]) for r in tx.query("SELECT participants FROM operations WHERE status='active'")):
        outcome, reason = "skipped", "away"
    else:
        st = step_for(tx, actor, _hour(at))
        if st.activity == "work" and not able(tx, actor, st.role)[0]:
            from ..society.routine import Step
            sp = _row(tx, "SELECT place_id FROM settlements WHERE settlement_id=?", (_settlement_of_actor(tx, actor),))["place_id"]
            st = Step(st.start_hh, st.end_hh, "free", sp)
            why = "cannot work"
        else:
            why = ""
        aw = b["awareness"]
        if st.activity != "sleep" and aw in ("asleep", "drowsy"):
            B.wake(tx, actor, at, cause, turn_index)
            B.refresh_need(tx, actor, "fatigue", at, cause, turn_index)
            B.posture_event(tx, actor, "standing", at, cause, turn_index)
            aw = "awake"
        pos = _row(tx, "SELECT place_id FROM positions WHERE body_id=?", (actor,))
        need = pos is None or pos["place_id"] != st.place_id
        if need and not (st.activity == "sleep" and aw == "asleep"):
            if B.capacity(tx, actor).mobile:
                p = _row(tx, "SELECT width_m, depth_m FROM places WHERE place_id=?", (st.place_id,))
                mev = tx.commit_event(move_event(tx, actor, st.place_id, None, p["width_m"] / 2, p["depth_m"] / 2, at, cause, turn_index))
                from ..world.worldmove import on_arrival
                on_arrival(tx, rng, actor, st.place_id, at, mev.event_id, turn_index)
                outcome, reason = "moved", ""
            else:
                outcome, reason = "stayed", "cannot walk"
        else:
            outcome, reason = "stayed", why
        if outcome == "moved":
            reason = why
        if st.activity == "sleep" and aw in ("alert", "awake", "drowsy"):
            B.posture_event(tx, actor, "lying", at, cause, turn_index, awareness="asleep")
        if st.activity == "work":
            shift_start(tx, actor, st.workplace_id, st.role, at, turn_index, cause)
    rt = _row(tx, "SELECT * FROM routines WHERE actor_id=? ORDER BY routine_id LIMIT 1", (actor,))
    nb = None if outcome == "ended" else next_boundary(tx, actor, at)
    writes = []
    if not (outcome == "ended" and rt is None):
        rid = rt["routine_id"] if rt else tx.mint("rtn")
        writes.append(_W(WriteOp.UPSERT, "routines", {"actor_id": actor, "steps": [asdict(x) for x in steps], "next_due_at": nb},
                         {"routine_id": rid}))
    rs = _commit(tx, type=EventType.ROUTINE_STEP, writer="society.routine", at=at, turn_index=turn_index, actor_id=actor,
                 cause_event_id=cause, writes=writes,
                 payload={"actor_id": actor, "activity": st.activity if st else None, "place_id": st.place_id if st else None,
                          "step_start_hh": st.start_hh if st else None, "outcome": outcome, "reason": reason})
    if outcome != "ended":
        clock.schedule(tx, nb, "ROUTINE_STEP", actor, {"actor_id": actor}, rs.event_id)
    return _since(tx, first)


def routine_ensure(tx, settlement_id, at, turn_index):
    from ..kernel import clock
    out = []
    for a in census(tx, settlement_id).named:
        if not steps_for(tx, a) or clock.pending_for(tx, "ROUTINE_STEP", a):
            continue
        out.append(clock.schedule(tx, next_boundary(tx, a, at), "ROUTINE_STEP", a, {"actor_id": a}, None))
    return out


# ================================================================== work
def parse_key(key):
    parts = key.split(":")
    if len(parts) != 4:
        raise ValueError(f"bad assignment key {key}")
    try:
        return parts[0], parts[1], parts[2], int(parts[3])
    except ValueError as e:
        raise ValueError(f"bad assignment key {key}") from e


def _key(r):
    return f"{r['workplace_id']}:{r['role']}:{r['actor_id']}:{r['shift_start_hh']}"


def qualified(store, actor_id, role):
    from ..mind.actor import fused
    req = _R(store).role_skill.get(role)
    if req is None:
        return True
    if _controller(store, actor_id) is None:
        return False
    d = fused(store, actor_id)
    rank = max((sk.rank for sk in d.capability.skills if str(sk.domain) == req[0]), default=0)
    return rank >= req[1]


def able(store, actor_id, role):
    b = _row(store, "SELECT * FROM bodies WHERE body_id=?", (actor_id,))
    if b is None or not b["alive"]:
        return False, "dead"
    if b["awareness"] == "unconscious":
        return False, "unconscious"
    if b["restrained"]:
        return False, "held"
    if role in _R(store).manual_roles:
        for w in _rows(store, "SELECT anatomy, function_loss FROM wounds WHERE body_id=? AND healed_at IS NULL", (actor_id,)):
            if ANATOMY_GROUP.get(w["anatomy"]) in ("arm", "hand") and w["function_loss"] >= 1:
                return False, "hurt"
    return True, ""


def overlap_h(s, e, start_ms, end_ms):
    dur = (int(e) - int(s)) % 24 or 24
    total = 0
    for d in range(start_ms // DAY - 1, end_ms // DAY + 2):
        os_ = d * DAY + int(s) * H
        oe = os_ + dur * H
        lo, hi = max(os_, start_ms), min(oe, end_ms)
        if hi > lo:
            total += hi - lo
    return total / H


def shifts_overlap(a_s, a_e, b_s, b_e):
    return bool(set(_hours(a_s, a_e)) & set(_hours(b_s, b_e)))


def crew(store, workplace_id, start_ms, end_ms):
    out = set()
    for r in _rows(store, "SELECT * FROM work_assignments WHERE workplace_id=?", (workplace_id,)):
        if overlap_h(r["shift_start_hh"], r["shift_end_hh"], start_ms, end_ms) > 0 and able(store, r["actor_id"], r["role"])[0] \
                and qualified(store, r["actor_id"], r["role"]):
            out.add((r["actor_id"], r["role"]))
    return sorted(out, key=lambda x: (x[1], x[0]))


def staffed_fraction(required_roles, crew_rows):
    if not required_roles:
        return 1.0
    tot = sum(min(required_roles.count(r), sum(1 for c in crew_rows if c[1] == r)) for r in sorted(set(required_roles)))
    return tot / len(required_roles)


def cycle(tx, rng, row, fired, turn_index):
    from ..kernel import clock
    wid = row["subject_id"]
    at = row["due_at"]
    w = _row(tx, "SELECT * FROM workplaces WHERE workplace_id=?", (wid,))
    first = _maxseq(tx)
    R = _R(tx)
    span = int(round(w["cycle_h"] * H))
    start = at - span
    cr = crew(tx, wid, start, at)
    staffed = staffed_fraction(_j(w["required_roles"]), cr)
    spite = animosity(tx, rng, [a for a, _ in cr], wid, at, turn_index, fired.event_id)
    cf = 1.0 if w["machinery_condition"] >= R.condition_full_at else 0.5 + w["machinery_condition"] / 100
    factor = w["efficiency"] * staffed * cf * spite
    output = {k: math.floor(v * factor + 1e-9) for k, v in sorted((_j(w["outputs"]) or {}).items())}
    ev = _commit(tx, type=EventType.PRODUCTION_CYCLE, writer="society.work", at=at, turn_index=turn_index, place_id=w["place_id"],
                 cause_event_id=fired.event_id,
                 payload={"workplace_id": wid, "settlement_id": w["settlement_id"], "site_type": w["site_type"],
                          "crew": [[a, r] for a, r in cr], "staffed": staffed, "efficiency": w["efficiency"], "condition_factor": cf,
                          "spite": spite, "output": output, "window_start": start, "window_end": at},
                 writes=[_W(WriteOp.UPDATE, "workplaces", {"next_due_at": at + span, "stall_reasons": ["unstaffed"] if staffed == 0 else []},
                            {"workplace_id": wid})])
    if w["settlement_id"] and any(v > 0 for v in output.values()):
        receive(tx, w["settlement_id"], {k: v for k, v in output.items() if v > 0}, "production", at, turn_index, ev.event_id)
    covers = sorted(_rows(tx, "SELECT * FROM work_assignments WHERE workplace_id=? AND covering_for IS NOT NULL", (wid,)), key=_key)
    for r in covers:
        if able(tx, r["covering_for"], r["role"])[0]:
            _commit(tx, type=EventType.ROLE_RELEASED, writer="society.work", at=at, turn_index=turn_index, actor_id=r["actor_id"],
                    place_id=w["place_id"], cause_event_id=ev.event_id,
                    payload={"workplace_id": wid, "role": r["role"], "actor_id": r["actor_id"], "shift_start_hh": r["shift_start_hh"],
                             "covering_for": r["covering_for"], "reason": "returned"},
                    writes=[_W(WriteOp.DELETE, "work_assignments", key={"workplace_id": wid, "actor_id": r["actor_id"], "role": r["role"],
                                                                        "shift_start_hh": r["shift_start_hh"]})])
            if w["settlement_id"]:
                remove_vacancy(tx, w["settlement_id"], wid, r["role"], r["covering_for"], at, turn_index, ev.event_id)
    w2 = _row(tx, "SELECT efficiency FROM workplaces WHERE workplace_id=?", (wid,))
    if w2["efficiency"] < 1.0:
        own = {r["actor_id"] for r in _rows(tx, "SELECT actor_id FROM work_assignments WHERE workplace_id=? AND covering_for IS NULL", (wid,))}
        covering = any(r["actor_id"] in own for r in _rows(tx, "SELECT actor_id FROM work_assignments WHERE covering_for IS NOT NULL"))
        if not covering:
            new = min(1.0, round(w2["efficiency"] + R.efficiency_recovery, 2))
            _commit(tx, type=EventType.WORKPLACE_CHANGE, writer="society.work", at=at, turn_index=turn_index, place_id=w["place_id"],
                    cause_event_id=ev.event_id,
                    payload={"workplace_id": wid, "field": "efficiency", "old": w2["efficiency"], "new": new, "reason": "recovering"},
                    writes=[_W(WriteOp.UPDATE, "workplaces", {"efficiency": new}, {"workplace_id": wid})])
    clock.schedule(tx, at + span, "PRODUCTION_CYCLE", wid, {"workplace_id": wid}, ev.event_id)
    return _since(tx, first)


def miss_shift(tx, key, reason, at, turn_index, cause_event_id):
    from ..audit.log import record
    wid, role, actor, ssh = parse_key(key)
    r = _row(tx, "SELECT * FROM work_assignments WHERE workplace_id=? AND role=? AND actor_id=? AND shift_start_hh=?", (wid, role, actor, ssh))
    if r is None:
        return None
    if able(tx, actor, role)[0]:
        record(tx, "G10-cascade", "society.work", "pass", [{"kind": "shift_not_missed", "key": key}], turn_index)
        return None
    w = _row(tx, "SELECT * FROM workplaces WHERE workplace_id=?", (wid,))
    writes = []
    if reason == "dead":
        writes.append(_W(WriteOp.DELETE, "work_assignments", key={"workplace_id": wid, "actor_id": actor, "role": role, "shift_start_hh": ssh}))
    ev = _commit(tx, type=EventType.SHIFT_MISSED, writer="society.work", at=at, turn_index=turn_index, actor_id=actor, place_id=w["place_id"],
                 cause_event_id=cause_event_id, writes=writes,
                 payload={"workplace_id": wid, "role": role, "actor_id": actor, "shift_start_hh": ssh,
                          "shift_end_hh": r["shift_end_hh"], "reason": reason})
    if w["settlement_id"] and (reason == "dead" or pick_cover(tx, wid, role, ssh, r["shift_end_hh"], actor) is None):
        add_vacancy(tx, w["settlement_id"], wid, role, actor, at, turn_index, ev.event_id)
    return ev


def pick_cover(store, workplace_id, role, shift_start_hh, shift_end_hh, exclude):
    w = _row(store, "SELECT settlement_id FROM workplaces WHERE workplace_id=?", (workplace_id,))
    if not w or not w["settlement_id"]:
        return None
    cands = []
    for a in census(store, w["settlement_id"]).named:
        if a == exclude or _controller(store, a) == "human":
            continue
        b = _row(store, "SELECT age_band FROM bodies WHERE body_id=?", (a,))
        if b["age_band"] not in ("teen", "adult"):
            continue
        if not qualified(store, a, role) or not able(store, a, role)[0]:
            continue
        rows = _rows(store, "SELECT shift_start_hh, shift_end_hh FROM work_assignments WHERE actor_id=?", (a,))
        if any(shifts_overlap(r["shift_start_hh"], r["shift_end_hh"], shift_start_hh, shift_end_hh) for r in rows):
            continue
        hours = sum((r["shift_end_hh"] - r["shift_start_hh"]) % 24 or 24 for r in rows)
        cands.append((hours, a))
    return min(cands)[1] if cands else None


def assign_cover(tx, actor_id, workplace_id, role, shift_start_hh, shift_end_hh, covering_for, at, turn_index, cause_event_id):
    w = _row(tx, "SELECT * FROM workplaces WHERE workplace_id=?", (workplace_id,))
    if w is None:
        raise ValueError(f"unknown workplace {workplace_id}")
    own = _row(tx, "SELECT MIN(workplace_id) AS w FROM work_assignments WHERE actor_id=? AND covering_for IS NULL", (actor_id,))
    left = own["w"] if own else None
    return _commit(tx, type=EventType.ROLE_ASSIGNED, writer="society.work", at=at, turn_index=turn_index, actor_id=actor_id,
                   place_id=w["place_id"], cause_event_id=cause_event_id,
                   payload={"workplace_id": workplace_id, "role": role, "actor_id": actor_id, "covering_for": covering_for,
                            "shift_start_hh": int(shift_start_hh), "shift_end_hh": int(shift_end_hh), "is_cover": True,
                            "left_workplace_id": left},
                   writes=[_W(WriteOp.INSERT, "work_assignments", {"workplace_id": workplace_id, "actor_id": actor_id, "role": role,
                                                                   "shift_start_hh": int(shift_start_hh), "shift_end_hh": int(shift_end_hh),
                                                                   "covering_for": covering_for})])


def work_adjust(tx, workplace_id, field, amount, at, turn_index, cause_event_id):
    w = _row(tx, "SELECT * FROM workplaces WHERE workplace_id=?", (workplace_id,))
    if w is None:
        raise ValueError(f"unknown workplace {workplace_id}")
    if field == "efficiency":
        new = max(0.0, min(1.5, round(w["efficiency"] + amount, 2)))
    elif field == "machinery_condition":
        new = max(0, min(100, int(round(w["machinery_condition"] + amount))))
    else:
        raise ValueError(f"cannot adjust workplace field {field}")
    if new == w[field]:
        return None
    return _commit(tx, type=EventType.WORKPLACE_CHANGE, writer="society.work", at=at, turn_index=turn_index, place_id=w["place_id"],
                   cause_event_id=cause_event_id,
                   payload={"workplace_id": workplace_id, "field": field, "old": w[field], "new": new, "reason": "cascade"},
                   writes=[_W(WriteOp.UPDATE, "workplaces", {field: new}, {"workplace_id": workplace_id})])


def shift_start(tx, actor_id, workplace_id, role, at, turn_index, cause_event_id):
    if not able(tx, actor_id, role)[0]:
        return None
    w = _row(tx, "SELECT place_id FROM workplaces WHERE workplace_id=?", (workplace_id,))
    return _commit(tx, type=EventType.SHIFT_START, writer="society.work", at=at, turn_index=turn_index, actor_id=actor_id,
                   place_id=w["place_id"] if w else None, cause_event_id=cause_event_id,
                   payload={"workplace_id": workplace_id, "role": role, "actor_id": actor_id})


def work_ensure(tx, settlement_id, at, turn_index):
    from ..kernel import clock
    out = []
    for w in _rows(tx, "SELECT workplace_id, next_due_at FROM workplaces WHERE settlement_id=? ORDER BY workplace_id", (settlement_id,)):
        if w["next_due_at"] is None or clock.pending_for(tx, "PRODUCTION_CYCLE", w["workplace_id"]):
            continue
        out.append(clock.schedule(tx, max(w["next_due_at"], at), "PRODUCTION_CYCLE", w["workplace_id"], {"workplace_id": w["workplace_id"]}, None))
    return out


# ================================================================== settlement
RESOURCES = ("food", "water")
_BAND_RANK = {"infant": 0, "child": 1, "preteen": 2, "teen": 3, "elder": 4, "adult": 5}


def _stl(s, sid):
    r = _row(s, "SELECT * FROM settlements WHERE settlement_id=?", (sid,))
    if r is None:
        raise ValueError(f"unknown settlement {sid}")
    return r


def daily_need(store, settlement_id):
    s = _stl(store, settlement_id)
    R = _R(store)
    m = R.ration_mult[s["ration_level"]]
    return {k: v * m for k, v in consumption(census(store, settlement_id), R).items()}


def days_of(store, settlement_id, resource):
    s = _stl(store, settlement_id)
    need = daily_need(store, settlement_id).get(resource, 0)
    if not need:
        return float("inf")
    return (_j(s["stores"]) or {}).get(resource, 0) / need


def has_shortage(store, settlement_id, resource):
    return resource in (_j(_stl(store, settlement_id)["shortages"]) or [])


def receive(tx, settlement_id, changes, reason, at, turn_index, cause_event_id):
    s = _stl(tx, settlement_id)
    stores = dict(_j(s["stores"]) or {})
    applied, after = {}, {}
    for k in sorted(changes):
        old = stores.get(k, 0)
        new = _num(max(0.0, old + changes[k]))
        applied[k] = _num(new - old)
        after[k] = new
        stores[k] = new
    return _commit(tx, type=EventType.STORES_CHANGE, writer="society.settlement", at=at, turn_index=turn_index, place_id=s["place_id"],
                   cause_event_id=cause_event_id,
                   payload={"settlement_id": settlement_id, "changes": applied, "after": after, "reason": reason},
                   writes=[_W(WriteOp.UPDATE, "settlements", {"stores": stores}, {"settlement_id": settlement_id})])


def settlement_day(tx, rng, row, fired, turn_index):
    from ..kernel import clock
    from ..physical.bodies import refresh_need
    sid = row["subject_id"]
    at = row["due_at"]
    first = _maxseq(tx)
    R = _R(tx)
    s = _stl(tx, sid)
    level = s["ration_level"]
    mult = R.ration_mult[level]
    stores = _j(s["stores"]) or {}
    c = census(tx, sid)
    bands = {a: _row(tx, "SELECT age_band FROM bodies WHERE body_id=?", (a,))["age_band"] for a in c.named}
    people = sorted(c.named, key=lambda a: (_BAND_RANK[bands[a]], a))
    cohorts = _rows(tx, "SELECT cohort_id, age_band, count FROM cohorts WHERE settlement_id=? ORDER BY cohort_id", (sid,))
    serving = sorted(cohorts, key=lambda co: (_BAND_RANK[co["age_band"]], co["cohort_id"]))
    unnamed = sum(co["count"] for co in cohorts)
    covered, short, drawn, ushort = {}, {}, {}, {}
    for res in ("water", "food"):
        rate = R.water_per_day if res == "water" else R.food_per_day
        avail = float(stores.get(res, 0))
        covered[res], short[res] = set(), []
        for p in people:
            share = rate[bands[p]] * mult
            if share <= avail + 1e-9:
                avail -= share
                covered[res].add(p)
            else:
                short[res].append(p)
        if level == 0 or (level == 1 and res == "food"):
            ushort[res] = unnamed
        else:
            left, n, broke = avail, 0, False
            for co in serving:
                sh = rate[co["age_band"]] * mult
                if broke:
                    n += co["count"]
                    continue
                fit = co["count"] if sh <= 0 else min(co["count"], int((left + 1e-9) // sh))
                left -= fit * sh
                if fit < co["count"]:
                    n += co["count"] - fit
                    broke = True
            ushort[res] = n
        avail = max(0.0, avail - sum(co["count"] * rate[co["age_band"]] * mult for co in cohorts))
        drawn[res] = _num(stores.get(res, 0) - avail)
    need = daily_need(tx, sid)
    mins = []
    for res in RESOURCES:
        n = need.get(res, 0)
        mins.append((stores.get(res, 0) - drawn.get(res, 0)) / n if n else float("inf"))
    md = min(mins)
    md = 999.0 if md == float("inf") else round(md, 2)
    sd = _commit(tx, type=EventType.SETTLEMENT_DAY, writer="society.settlement", at=at, turn_index=turn_index, place_id=s["place_id"],
                 cause_event_id=fired.event_id,
                 payload={"settlement_id": sid, "ration_level": level, "drawn": {k: drawn[k] for k in sorted(drawn)},
                          "short": {k: short[k] for k in sorted(short)},
                          "unnamed_short": {k: ushort[k] for k in sorted(ushort)}, "min_days": md},
                 writes=[_W(WriteOp.UPDATE, "settlements", {"next_due_at": at + DAY}, {"settlement_id": sid})])
    _privation(tx, rng, sid, R, at, turn_index, sd.event_id)
    if any(v > 0 for v in drawn.values()):
        receive(tx, sid, {k: -v for k, v in drawn.items() if v > 0}, "consumption", at, turn_index, sd.event_id)
    for p in people:
        if p in covered["water"] and level >= 1:
            refresh_need(tx, p, "thirst", at, sd.event_id, turn_index)
        if p in covered["food"] and level >= 2:
            refresh_need(tx, p, "hunger", at, sd.event_id, turn_index)
    s = _stl(tx, sid)
    shortages = _j(s["shortages"]) or []
    if level <= 2:
        stl_adjust(tx, sid, "morale", -1, at, turn_index, sd.event_id, reason="rations")
    elif not shortages and s["morale"] < R.morale_baseline:
        stl_adjust(tx, sid, "morale", 1, at, turn_index, sd.event_id, reason="recovering")
    for res in list(shortages):
        d = days_of(tx, sid, res)
        if d >= R.shortage_days:
            cur = _j(_stl(tx, sid)["shortages"]) or []
            _commit(tx, type=EventType.SHORTAGE_ENDED, writer="society.settlement", at=at, turn_index=turn_index, place_id=s["place_id"],
                    cause_event_id=sd.event_id, payload={"settlement_id": sid, "resource": res, "days": _days(d)},
                    writes=[_W(WriteOp.UPDATE, "settlements", {"shortages": [x for x in cur if x != res]}, {"settlement_id": sid})])
    if level < 3:
        sds = _rows(tx, "SELECT seq, payload FROM events WHERE type='SETTLEMENT_DAY' AND json_extract(payload,'$.settlement_id')=? "
                        "ORDER BY seq DESC LIMIT ?", (sid, R.recovery_streak))
        if len(sds) == R.recovery_streak and all(_j(r["payload"])["min_days"] >= R.recovery_days for r in sds):
            oldest = min(r["seq"] for r in sds)
            rc = tx.query_one("SELECT MAX(seq) FROM events WHERE type='RATION_CHANGE' AND json_extract(payload,'$.settlement_id')=?", (sid,))[0]
            if rc is None or rc < oldest:
                change_ration(tx, sid, 1, "recovered", at, turn_index, sd.event_id)
    for h in households_of(tx, sid):
        household_day(tx, h, at, turn_index, sd.event_id)
    from . import settlement as _stl_mod
    _stl_mod.friction(tx, rng, sid, at, turn_index, sd.event_id)
    clock.schedule(tx, at + DAY, "SETTLEMENT_DAY", sid, {"settlement_id": sid}, sd.event_id)
    return _since(tx, first)


def _privation(tx, rng, sid, R, at, turn_index, cause):
    # STL-03 step 2b (P10, C01): the unnamed short for R.privation_days draws in a row die of it.
    for res in ("water", "food"):
        k = int(R.privation_days[res])
        sds = _rows(tx, "SELECT payload FROM events WHERE type='SETTLEMENT_DAY' AND json_extract(payload,'$.settlement_id')=? "
                        "ORDER BY seq DESC LIMIT ?", (sid, k))
        if len(sds) < k:
            continue
        vals = [(_j(r["payload"]).get("unnamed_short") or {}).get(res, 0) for r in sds]
        n = min(vals)
        if n <= 0:
            continue
        rows = _rows(tx, "SELECT cohort_id, age_band, count FROM cohorts WHERE settlement_id=? AND count > 0", (sid,))
        dead = 0
        for co in sorted(rows, key=lambda c: (_BAND_RANK[c["age_band"]], c["cohort_id"]), reverse=True):
            m = min(co["count"], n)
            if m > 0:
                adjust_cohort(tx, co["cohort_id"], -m, "thirst" if res == "water" else "hunger", at, turn_index, cause)
                n -= m
                dead += m
            if n == 0:
                break
        if dead:
            from ..world import hordes
            zone = tx.query_one("SELECT p.zone_id FROM settlements s JOIN places p ON p.place_id = s.place_id "
                                "WHERE s.settlement_id=?", (sid,))[0]
            if zone is not None:
                hordes.schedule_rise(tx, rng, zone, dead, "cold_start", at, turn_index, cause)


def _days(d):
    return 999.0 if d == float("inf") else round(d, 2)


def declare_shortage(tx, settlement_id, resource, at, turn_index, cause_event_id):
    s = _stl(tx, settlement_id)
    cur = _j(s["shortages"]) or []
    if resource in cur:
        return None
    return _commit(tx, type=EventType.SHORTAGE, writer="society.settlement", at=at, turn_index=turn_index, place_id=s["place_id"],
                   cause_event_id=cause_event_id,
                   payload={"settlement_id": settlement_id, "resource": resource, "days": _days(days_of(tx, settlement_id, resource))},
                   writes=[_W(WriteOp.UPDATE, "settlements", {"shortages": cur + [resource]}, {"settlement_id": settlement_id})])


def change_ration(tx, settlement_id, delta, reason, at, turn_index, cause_event_id):
    s = _stl(tx, settlement_id)
    lvl = s["ration_level"]
    new = max(0, min(4, lvl + int(delta)))
    if new == lvl:
        return None
    return _commit(tx, type=EventType.RATION_CHANGE, writer="society.settlement", at=at, turn_index=turn_index, place_id=s["place_id"],
                   cause_event_id=cause_event_id,
                   payload={"settlement_id": settlement_id, "delta": new - lvl, "level_before": lvl, "level_after": new, "cause": reason},
                   writes=[_W(WriteOp.UPDATE, "settlements", {"ration_level": new}, {"settlement_id": settlement_id})])


def stl_adjust(tx, settlement_id, field, amount, at, turn_index, cause_event_id, reason="cascade"):
    if field not in ("morale", "cohesion", "defences", "sanitation", "power"):
        raise ValueError(f"cannot adjust settlement field {field}")
    s = _stl(tx, settlement_id)
    new = max(0, min(10, s[field] + int(amount)))
    if new == s[field]:
        return None
    return _commit(tx, type=EventType.SETTLEMENT_CHANGE, writer="society.settlement", at=at, turn_index=turn_index, place_id=s["place_id"],
                   cause_event_id=cause_event_id,
                   payload={"settlement_id": settlement_id, "field": field, "old": s[field], "new": new, "reason": reason},
                   writes=[_W(WriteOp.UPDATE, "settlements", {field: new}, {"settlement_id": settlement_id})])


def set_lockdown(tx, settlement_id, on, reason, at, turn_index, cause_event_id):
    # STL-13 (P10).
    s = _stl(tx, settlement_id)
    new = 1 if on else 0
    if new == s["lockdown"]:
        return None
    return _commit(tx, type=EventType.SETTLEMENT_CHANGE, writer="society.settlement", at=at, turn_index=turn_index, place_id=s["place_id"],
                   cause_event_id=cause_event_id,
                   payload={"settlement_id": settlement_id, "field": "lockdown", "old": s["lockdown"], "new": new, "reason": reason},
                   writes=[_W(WriteOp.UPDATE, "settlements", {"lockdown": new}, {"settlement_id": settlement_id})])


def _vac(tx, settlement_id, entry, add, at, turn_index, cause_event_id):
    s = _stl(tx, settlement_id)
    old = _j(s["vacancies"]) or []
    match = [v for v in old if (v["workplace_id"], v["role"], v["for_actor"]) == (entry["workplace_id"], entry["role"], entry["for_actor"])]
    if add == bool(match):
        return None
    new = old + [entry] if add else [v for v in old if v not in match]
    new = sorted(new, key=lambda v: (v["workplace_id"], v["role"], v["for_actor"]))
    return _commit(tx, type=EventType.SETTLEMENT_CHANGE, writer="society.settlement", at=at, turn_index=turn_index, place_id=s["place_id"],
                   cause_event_id=cause_event_id,
                   payload={"settlement_id": settlement_id, "field": "vacancies", "old": old, "new": new,
                            "reason": "vacancy" if add else "filled"},
                   writes=[_W(WriteOp.UPDATE, "settlements", {"vacancies": new}, {"settlement_id": settlement_id})])


def add_vacancy(tx, settlement_id, workplace_id, role, for_actor, at, turn_index, cause_event_id):
    return _vac(tx, settlement_id, {"workplace_id": workplace_id, "role": role, "for_actor": for_actor, "since": at}, True, at, turn_index,
                cause_event_id)


def remove_vacancy(tx, settlement_id, workplace_id, role, for_actor, at, turn_index, cause_event_id):
    return _vac(tx, settlement_id, {"workplace_id": workplace_id, "role": role, "for_actor": for_actor, "since": at}, False, at, turn_index,
                cause_event_id)


def laws_of(store, settlement_id):
    return [r["law_ref"] for r in _rows(store, "SELECT law_ref FROM laws_active WHERE settlement_id=? ORDER BY law_ref", (settlement_id,))]


def law_def(store, settlement_id, law):
    canon = store.canon if getattr(store, "canon", None) is not None else store.store.canon
    for ref in laws_of(store, settlement_id):
        if ref == law or ref.endswith("/" + law):
            return canon.find("law", ref.split("/")[-1])
    return None


PUNISHING = frozenset({"curfew", "weapons", "ration", "trade", "theft", "noise", "visitors"})


def apply_law(tx, settlement_id, law, subject_id, at, turn_index, cause_event_id):
    from ..audit.log import record
    s = _stl(tx, settlement_id)
    d = law_def(tx, settlement_id, law)
    if d is None:
        record(tx, "G10-cascade", "society.settlement", "warn", [{"kind": "law_not_active", "law": law, "settlement_id": settlement_id}], turn_index)
        return None
    ref = next(r for r in laws_of(tx, settlement_id) if r == law or r.endswith("/" + law))
    ev = _commit(tx, type=EventType.LAW_APPLIED, writer="society.settlement", at=at, turn_index=turn_index, place_id=s["place_id"],
                 actor_id=subject_id, cause_event_id=cause_event_id,
                 payload={"settlement_id": settlement_id, "law_ref": ref, "kind": d.kind, "subject_id": subject_id, "punishment": d.punishment})
    if d.kind in PUNISHING and s["group_id"]:
        from ..mind.mind import adjust_group_standing
        adjust_group_standing(tx, s["group_id"], subject_id, -1, ev.event_id, at, turn_index)
    return ev


def settlement_of(store, entity_id):
    if not entity_id or "_" not in str(entity_id):
        return None
    kind = str(entity_id).split("_")[0]
    if kind == "stl":
        return entity_id if _row(store, "SELECT 1 AS x FROM settlements WHERE settlement_id=?", (entity_id,)) else None
    if kind == "wkp":
        r = _row(store, "SELECT settlement_id FROM workplaces WHERE workplace_id=?", (entity_id,))
        return r["settlement_id"] if r else None
    if kind == "plc":
        r = _row(store, "SELECT MIN(settlement_id) AS s FROM settlements WHERE place_id=?", (entity_id,))
        return r["s"] if r else None
    if kind == "hh":
        r = _row(store, "SELECT settlement_id FROM households WHERE household_id=?", (entity_id,))
        if r and r["settlement_id"]:
            return r["settlement_id"]
        for a in hh_members(store, entity_id):
            sid = _settlement_of_actor(store, a)
            if sid:
                return sid
        return None
    if kind == "act":
        return _settlement_of_actor(store, entity_id)
    return None


THIEF_PREDICATES = frozenset({"took_what_was_not_theirs", "thief"})


def trade_terms(store, settlement_id, buyer_id):
    from ..mind.actor import display_name, fused
    from ..mind.mind import standing_toward
    from ..society.settlement import TradeTerms
    s = _stl(store, settlement_id)
    best = None
    for a in census(store, settlement_id).named:
        if a == buyer_id or _controller(store, a) == "human":
            continue
        d = fused(store, a)
        rank = max((sk.rank for sk in d.capability.skills if str(sk.domain) == "trade"), default=0)
        if rank >= 1 and (best is None or (-rank, a) < best[0]):
            best = ((-rank, a), a)
    if best is None:
        return TradeTerms(False, 0.0, None, ["Nobody here trades."])
    trader = best[1]
    mult, willing, reasons = 1.0, True, []
    g = _row(store, "SELECT name FROM groups WHERE group_id=?", (s["group_id"],)) if s["group_id"] else None
    if g:
        st = standing_toward(store, s["group_id"], buyer_id)
        if st <= -3:
            willing = False
            reasons.append(f"{g['name']} will not deal with them.")
        elif st == -2:
            mult *= 1.5
            reasons.append(f"{g['name']} thinks little of them.")
        elif st == -1:
            mult *= 1.25
            reasons.append(f"{g['name']} thinks little of them.")
        elif st >= 2:
            mult *= 0.9
            reasons.append(f"{g['name']} thinks well of them.")
    T = display_name(store, trader)
    rel = _row(store, "SELECT * FROM relationships WHERE from_id=? AND to_id=?", (trader, buyer_id))
    if rel:
        if rel["resentment"] >= 2:
            willing = False
            reasons.append(f"{T} holds a grudge against them.")
        if rel["trust"] <= -2:
            mult *= 1.25
            reasons.append(f"{T} does not trust them.")
    qs = ",".join("?" * len(THIEF_PREDICATES))
    conf = store.query_one(f"SELECT MAX(h.confidence) FROM claim_holdings h JOIN propositions p ON p.prop_id=h.claim_id "
                           f"WHERE h.holder_id=? AND h.superseded_by IS NULL AND h.believed=1 AND p.subject_type='body' "
                           f"AND p.subject_id=? AND p.predicate IN ({qs})", (trader, buyer_id, *sorted(THIEF_PREDICATES)))[0]
    if conf is not None and conf >= 2:
        willing = False
        reasons.append(f"{T} believes they steal.")
    elif conf == 1:
        mult *= 1.5
        reasons.append(f"{T} has heard they steal.")
    return TradeTerms(willing, round(mult, 2) if willing else 0.0, trader, reasons)


def settlement_ensure(tx, settlement_id, at, turn_index):
    from ..kernel import clock
    from ..society.settlement import next_hour
    if clock.pending_for(tx, "SETTLEMENT_DAY", settlement_id):
        return []
    return [clock.schedule(tx, next_hour(at, _R(tx).draw_hour), "SETTLEMENT_DAY", settlement_id, {"settlement_id": settlement_id}, None)]


# ================================================================== group
def g_members(store, group_id, living=True):
    ids = [r["actor_id"] for r in _rows(store, "SELECT actor_id FROM group_members WHERE group_id=? AND status IN ('member','probation') "
                                               "ORDER BY actor_id", (group_id,))]
    return [a for a in ids if _alive(store, a)] if living else ids


def leader_of(store, group_id):
    g = _row(store, "SELECT leader_id FROM groups WHERE group_id=?", (group_id,))
    if g and g["leader_id"] and _alive(store, g["leader_id"]):
        return g["leader_id"]
    for r in _rows(store, "SELECT actor_id FROM group_members WHERE group_id=? AND role='leader' ORDER BY actor_id", (group_id,)):
        if _alive(store, r["actor_id"]):
            return r["actor_id"]
    return None


def tension_of(store, a_id, b_id):
    r = _row(store, "SELECT score FROM tension WHERE a_id=? AND b_id=?", (a_id, b_id))
    return r["score"] if r else 0


def _is_actor(s, x):
    return _row(s, "SELECT 1 AS x FROM actors WHERE actor_id=?", (x,)) is not None


def adjust_tension(tx, a_id, b_id, delta, cause_text, at, turn_index, cause_event_id):
    from ..mind.mind import relate
    first = _maxseq(tx)
    R = _R(tx)
    r = _row(tx, "SELECT * FROM tension WHERE a_id=? AND b_id=?", (a_id, b_id))
    old = r["score"] if r else 0
    new = max(0, min(100, old + int(delta)))
    if new == old:
        return []
    bp = r["boiling_point"] if r else R.boiling_point
    causes = list(_j(r["causes"]) if r else [])
    if cause_event_id is not None:
        causes = (causes + [cause_event_id])[-10:]
    tc = _commit(tx, type=EventType.TENSION_CHANGE, writer="society.group", at=at, turn_index=turn_index,
                 actor_id=a_id if _is_actor(tx, a_id) else None, cause_event_id=cause_event_id,
                 payload={"a_id": a_id, "b_id": b_id, "old": old, "new": new, "delta": new - old, "cause": cause_text},
                 writes=[_W(WriteOp.UPSERT, "tension", {"score": new, "boiling_point": bp, "causes": causes}, {"a_id": a_id, "b_id": b_id})])
    if old < bp <= new:
        esc = _commit(tx, type=EventType.ESCALATION, writer="society.group", at=at, turn_index=turn_index,
                      actor_id=a_id if _is_actor(tx, a_id) else None, cause_event_id=tc.event_id,
                      payload={"a_id": a_id, "b_id": b_id, "form": "verbal", "score": new})
        if _is_actor(tx, a_id):
            other = b_id if _is_actor(tx, b_id) else (leader_of(tx, b_id) if _row(tx, "SELECT 1 AS x FROM groups WHERE group_id=?", (b_id,)) else None)
            if other and other != a_id and _alive(tx, other):
                relate(tx, a_id, other, RelationAxis.RESENTMENT, 1, esc.event_id, at, turn_index)
    return _since(tx, first)


def _share_household(s, a, b):
    return _row(s, "SELECT 1 AS x FROM household_members x JOIN household_members y ON x.household_id=y.household_id "
                   "WHERE x.actor_id=? AND y.actor_id=?", (a, b)) is not None


def _share_work(s, a, b):
    return _row(s, "SELECT 1 AS x FROM work_assignments x JOIN work_assignments y ON x.workplace_id=y.workplace_id "
                   "WHERE x.actor_id=? AND y.actor_id=?", (a, b)) is not None


def contacts(store, actor_id, group_id):
    out = []
    for c in g_members(store, group_id):
        if c == actor_id:
            continue
        rel = _row(store, "SELECT trust, affection FROM relationships WHERE from_id=? AND to_id=?", (actor_id, c))
        if _share_household(store, actor_id, c) or _share_work(store, actor_id, c) or (rel and (rel["trust"] >= 1 or rel["affection"] >= 1)):
            out.append(c)
    return out


def pairs(store, group_id):
    ok = [m for m in g_members(store, group_id) if _controller(store, m) != "human"]
    oks = set(ok)
    out = set()
    for m in ok:
        for c in contacts(store, m, group_id):
            if c in oks:
                out.add((min(m, c), max(m, c)))
    return sorted(out)


def _rel(s, x, y):
    r = _row(s, "SELECT * FROM relationships WHERE from_id=? AND to_id=?", (x, y))
    return r or {"trust": 0, "fear": 0, "respect": 0, "affection": 0, "resentment": 0, "obligation": 0}


def _governed(s, group_id):
    r = _row(s, "SELECT MIN(settlement_id) AS s FROM settlements WHERE group_id=?", (group_id,))
    return r["s"] if r else None


def defection_pressure(store, actor_id, group_id):
    from ..society.group import Pressure
    sid = _governed(store, group_id)
    st = _stl(store, sid) if sid else None
    lvl = st["ration_level"] if st else 3
    terms = {}
    terms["grievance"] = tension_of(store, actor_id, group_id) // 20
    terms["deprivation"] = (2 if lvl <= 1 else 1 if lvl <= 2 else 0) if st else 0
    deps = dependents_of(store, actor_id)
    terms["dependents"] = 1 if (st and deps and lvl <= 2) else 0
    endangered = 0
    for d in deps:
        n = _row(store, "SELECT thirst_stage, hunger_stage FROM needs WHERE body_id=?", (d,))
        if n and (n["thirst_stage"] >= 3 or n["hunger_stage"] >= 3):
            endangered = 2
    terms["endangered"] = endangered
    terms["viability"] = (2 if st["morale"] <= 1 else 1 if st["morale"] <= 3 else 0) if st else 0
    ld = leader_of(store, group_id)
    terms["leader"] = 1 if (ld and ld != actor_id and _rel(store, actor_id, ld)["resentment"] >= 2) else 0
    gm = _row(store, "SELECT standing FROM group_members WHERE group_id=? AND actor_id=?", (group_id, actor_id))
    terms["standing"] = 1 if (gm and gm["standing"] <= -1) else 0
    return Pressure(min(10, sum(terms.values())), terms)


def loyalty_check(tx, actor_id, group_id, reason, at, turn_index, cause_event_id):
    from ..mind.actor import fused
    from ..mind.mind import open_loop
    if not _alive(tx, actor_id) or _controller(tx, actor_id) in (None, "human"):
        return []
    first = _maxseq(tx)
    thr = fused(tx, actor_id).motive.risk_threshold
    p = defection_pressure(tx, actor_id, group_id)
    result = "plans_to_leave" if p.value >= thr else "wavering" if p.value >= thr - 1 else "stays"
    lc = _commit(tx, type=EventType.LOYALTY_CHECK, writer="society.group", at=at, turn_index=turn_index, actor_id=actor_id,
                 cause_event_id=cause_event_id,
                 payload={"actor_id": actor_id, "group_id": group_id, "pressure": p.value, "threshold": thr, "terms": p.terms,
                          "result": result, "reason": reason})
    if result == "plans_to_leave":
        g = _row(tx, "SELECT name FROM groups WHERE group_id=?", (group_id,))
        open_loop(tx, actor_id, OpenLoopKind.PLAN, f"Leave {g['name']} before it is too late.", [], 2, lc.event_id, at, turn_index)
    return _since(tx, first)


def animosity(tx, rng, actor_ids, workplace_id, at, turn_index, cause_event_id):
    from ..action.checks import roll
    from ..contracts.content import CheckSpec
    ids = sorted(set(actor_ids))
    spite = 1.0
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            for x, y in ((a, b), (b, a)):
                res = _rel(tx, x, y)["resentment"]
                if res < 2 or _controller(tx, x) == "human":
                    continue
                act = _row(tx, "SELECT resolve_cur FROM actors WHERE actor_id=?", (x,))
                r = roll(tx, rng, x, "animosity", CheckSpec(attribute="I"), situation=max(-3, min(3, act["resolve_cur"] - 3)),
                         resistance=res, at=at, turn_index=turn_index, cause_event_id=cause_event_id)
                band = str(r.band.value if hasattr(r.band, "value") else r.band)
                if band == "fail":
                    spite *= 0.9
                    adjust_tension(tx, x, y, 10, "forced to work together", at, turn_index, cause_event_id)
                elif band == "break":
                    spite *= 0.75
                    adjust_tension(tx, x, y, 20, "forced to work together", at, turn_index, cause_event_id)
    return round(spite, 2)


def group_day(tx, rng, row, fired, turn_index):
    from ..kernel import clock
    from ..mind.actor import fused
    from ..mind.mind import relate
    from ..world._impl_rumours import spread_day
    gid = row["subject_id"]
    at = row["due_at"]
    first = _maxseq(tx)
    R = _R(tx)
    prs = pairs(tx, gid)
    mem = g_members(tx, gid)
    gd = _commit(tx, type=EventType.GROUP_DAY, writer="society.group", at=at, turn_index=turn_index, cause_event_id=fired.event_id,
                 payload={"group_id": gid, "members": len(mem), "pairs": len(prs)},
                 writes=[_W(WriteOp.UPDATE, "groups", {"next_due_at": at + DAY}, {"group_id": gid})])
    G = gd.event_id
    for a, b in prs:
        for x, y in ((a, b), (b, a)):
            rel = _rel(tx, x, y)
            if rel["resentment"] >= 1 or rel["trust"] <= -1:
                if rel["resentment"] < 3 and rng.chance(tx, "society", f"friction:{x}:{y}", R.drift_friction):
                    relate(tx, x, y, RelationAxis.RESENTMENT, 1, G, at, turn_index)
            else:
                if rel["trust"] < R.drift_cap and rng.chance(tx, "society", f"bond:{x}:{y}", R.drift_bond):
                    relate(tx, x, y, RelationAxis.TRUST, 1, G, at, turn_index)
                if _share_household(tx, x, y) and rel["affection"] < R.drift_cap and rng.chance(tx, "society", f"home:{x}:{y}", R.drift_household):
                    relate(tx, x, y, RelationAxis.AFFECTION, 1, G, at, turn_index)
    sid = _governed(tx, gid)
    if sid and _stl(tx, sid)["ration_level"] <= 2:
        for a, b in prs:
            for x, y in ((a, b), (b, a)):
                if _rel(tx, x, y)["resentment"] >= 1:
                    adjust_tension(tx, x, y, R.ration_strain_tension, "short rations", at, turn_index, G)
    alive_members = set(mem)
    for t in _rows(tx, "SELECT * FROM tension WHERE score > 0 ORDER BY a_id, b_id"):
        if not (t["a_id"] == gid or t["a_id"] in alive_members):
            continue
        raised = tx.query_one("SELECT 1 FROM events WHERE type='TENSION_CHANGE' AND at > ? AND at <= ? AND json_extract(payload,'$.a_id')=? "
                              "AND json_extract(payload,'$.b_id')=? AND json_extract(payload,'$.delta') > 0",
                              (at - DAY, at, t["a_id"], t["b_id"]))
        if raised is None:
            adjust_tension(tx, t["a_id"], t["b_id"], -R.tension_decay_per_day, "time", at, turn_index, G)
    spread_day(tx, gid, at, turn_index, G)
    for m in mem:
        if _controller(tx, m) == "human":
            continue
        b = _row(tx, "SELECT age_band FROM bodies WHERE body_id=?", (m,))
        if b["age_band"] not in ("teen", "adult", "elder"):
            continue
        thr = fused(tx, m).motive.risk_threshold
        if defection_pressure(tx, m, gid).value < thr - 1:
            continue
        recent = tx.query_one("SELECT 1 FROM events WHERE type='LOYALTY_CHECK' AND at > ? AND at <= ? AND json_extract(payload,'$.actor_id')=? "
                              "AND json_extract(payload,'$.group_id')=?", (at - R.loyalty_recheck_days * DAY, at, m, gid))
        if recent is None:
            loyalty_check(tx, m, gid, "daily", at, turn_index, G)
    clock.schedule(tx, at + DAY, "GROUP_DAY", gid, {"group_id": gid}, G)
    return _since(tx, first)


def group_ensure(tx, group_id, at, turn_index):
    from ..kernel import clock
    from ..society.settlement import next_hour
    if clock.pending_for(tx, "GROUP_DAY", group_id):
        return []
    return [clock.schedule(tx, next_hour(at, _R(tx).group_hour), "GROUP_DAY", group_id, {"group_id": group_id}, None)]
