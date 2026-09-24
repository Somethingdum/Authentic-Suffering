"""Implementation of turn/select.py."""
from __future__ import annotations

import json

MANDATORY_CUES = ("weapon_pointed", "infected_close", "grabbed_from_behind", "addressed_by_name", "dependent_in_danger")
LOUD_DB = 80
LOUD_MEMORY_MS = 10 * 60 * 1000
MAX_WINDOW_MS = 8 * 3600 * 1000
MIN_WINDOW_MS = 3000
REACT_MARGIN_MS = 3000


def _row(s, sql, p=()):
    r = s.query_one(sql, p)
    return dict(r) if r is not None else None


def _place(tx, body):
    r = _row(tx, "SELECT place_id FROM positions WHERE body_id=?", (body,))
    return r["place_id"] if r else None


def active_area(tx, pc_id, turn_index):
    from ..physical.space import places_near
    base = _place(tx, pc_id)
    area = {base} | set(places_near(tx, base, 2))
    since = tx.query_one("SELECT now_ms FROM world_clock")[0] - LOUD_MEMORY_MS
    for r in tx.query("SELECT payload FROM events INDEXED BY ev_at WHERE at >= ? AND turn_index=? AND type='NOISE' "
                      "ORDER BY seq", (since, turn_index)):
        pl = json.loads(r[0])
        if pl.get("source_db", 0) >= LOUD_DB and pl.get("place_id"):
            area.add(pl["place_id"])
            area |= set(places_near(tx, pl["place_id"], 1))
    return sorted(area)


def candidates(tx, pc_id, turn_index, horizon_ms):
    area = set(active_area(tx, pc_id, turn_index))
    out = []
    for r in tx.query("SELECT a.actor_id, a.next_due_at, p.place_id FROM actors a JOIN bodies b ON b.body_id=a.actor_id "
                      "LEFT JOIN positions p ON p.body_id=a.actor_id WHERE b.alive=1 ORDER BY a.actor_id"):
        if r["actor_id"] == pc_id:
            continue
        if r["place_id"] in area or (r["next_due_at"] is not None and r["next_due_at"] <= horizon_ms):
            out.append(r["actor_id"])
    return out


def conscious(tx, actor_id):
    r = _row(tx, "SELECT alive, awareness FROM bodies WHERE body_id=?", (actor_id,))
    return bool(r and r["alive"] and r["awareness"] in ("awake", "drowsy"))


def _percepts(tx, holder, turn_index, at):
    # SKULL-10: nothing later than the moment reaches a mind
    return [dict(r) for r in tx.query("SELECT * FROM percept_log WHERE holder_id=? AND turn_index=? AND at<=? "
                                      "ORDER BY at, percept_id", (holder, turn_index, at))]


def _standing_triggers(tx, actor_id):
    r = _row(tx, "SELECT standing_orders FROM plans WHERE actor_id=?", (actor_id,))
    return [o.get("trigger") for o in json.loads(r["standing_orders"])] if r else []


def mandatory(tx, actor_id, turn_index, at, horizon_ms, pc_intent, forced=frozenset()):
    from ..mind.cues import cues_of
    from ..physical.bodies import grips_on
    if actor_id in forced:
        return True
    cues = cues_of(tx, actor_id, turn_index, at)
    if cues & set(MANDATORY_CUES):
        return True
    if any(t in cues for t in _standing_triggers(tx, actor_id)):
        return True
    if grips_on(tx, actor_id):
        return True
    if any(p["channel"] == "tactile" for p in _percepts(tx, actor_id, turn_index, at)):
        return True
    t = _row(tx, "SELECT * FROM tasks WHERE actor_id=? AND status='active' ORDER BY started_at, task_id LIMIT 1", (actor_id,))
    if t and t["started_at"] + t["steps_total"] * round(t["step_s"] * 1000) <= horizon_ms:
        return True
    if pc_intent is not None and pc_intent.bound.target_id == actor_id:
        return True
    return False


def salience_flags(tx, actor_id, cands, pc_id, turn_index, at):
    from ..mind.cues import cues_of
    cues = cues_of(tx, actor_id, turn_index, at)
    mine = _percepts(tx, actor_id, turn_index, at)
    others = [c for c in cands if c != actor_id]

    def held(h):
        ev, src = set(), set()
        for p in _percepts(tx, h, turn_index, at):
            if p["fidelity"] not in ("exact", "partial"):
                continue
            if p["event_id"].startswith("scene:"):
                if p["source_id"] and p["source_id"].startswith("act_"):
                    src.add(p["source_id"])
            else:
                ev.add(p["event_id"])
        return ev, src

    my_ev, my_src = held(actor_id)
    o_ev, o_src = set(), set()
    for o in others:
        e, s = held(o)
        o_ev |= e
        o_src |= s
    my_src.discard(actor_id)
    unique = bool(my_ev - o_ev) or bool({s for s in my_src if s not in o_src and s != pc_id and s not in others})

    def loud(h):
        dbs = [json.loads(p["detail"]).get("received_db", 0) or 0 for p in _percepts(tx, h, turn_index, at)
               if p["channel"] in ("auditory", "speech")]
        return max(dbs) if dbs else 0
    my_loud = loud(actor_id)
    loudest = my_loud > 0 and all(my_loud >= loud(o) for o in others)
    addressed = any(p["channel"] == "speech" and json.loads(p["detail"]).get("addressed_to_me") and p["fidelity"] in ("exact", "partial")
                    for p in mine)
    in_conflict = bool(cues & {"threat_seen", "weapon_pointed"}) or any(p["channel"] == "tactile" for p in mine)
    t = _row(tx, "SELECT interrupt_on FROM tasks WHERE actor_id=? AND status='active' ORDER BY started_at, task_id LIMIT 1", (actor_id,))
    trig = set(_standing_triggers(tx, actor_id)) | (set(json.loads(t["interrupt_on"])) if t else set())
    interrupt = bool(cues & trig)
    loop_pc = any(pc_id in json.loads(r[0]) for r in tx.query("SELECT subject_ids FROM open_loops WHERE holder_id=? AND status='open'", (actor_id,)))
    here = _place(tx, actor_id)
    dep = False
    for r in tx.query("SELECT guardian_of FROM household_members WHERE actor_id=?", (actor_id,)):
        for d in json.loads(r[0]):
            if here is not None and _place(tx, d) == here:
                dep = True
    vis = tx.query_one("SELECT 1 FROM percept_log WHERE holder_id=? AND turn_index=? AND at<=? AND channel='visual' "
                       "AND source_id=? AND fidelity IN ('exact','partial')", (pc_id, turn_index, at, actor_id)) is not None
    return {"unique_info": unique, "loudest_percept": loudest, "addressed": addressed, "in_conflict": in_conflict,
            "interrupt_trigger": interrupt, "open_loop_with_pc": loop_pc, "dependent_present": dep, "visible_to_pc": vis}


def salience(flags, is_mandatory, weights):
    s = sum(weights[k] for k, v in flags.items() if v)
    if is_mandatory:
        s += weights["mandatory"]
    return float(s)


def _def(tx, def_id):
    return tx.canon.find("affordance", def_id)


def horizon(tx, pc_intent, t0):
    d = _def(tx, pc_intent.bound.def_id)
    if d.duration.condition_ended:
        cands = [t0 + MAX_WINDOW_MS]
        from ..kernel.clock import BACKGROUND_QUEUE_TYPES as _BG
        _qs = ",".join("?" * len(_BG))
        q = tx.query_one(f"SELECT MIN(due_at) FROM event_queue WHERE status='pending' AND due_at > ? AND type NOT IN ({_qs})",
                         (t0, *sorted(_BG)))[0]
        if q is not None:
            cands.append(q)
        a = tx.query_one("SELECT MIN(next_due_at) FROM actors WHERE next_due_at > ?", (t0,))[0]
        if a is not None:
            cands.append(a)
        return max(t0 + MIN_WINDOW_MS, min(cands))
    from ..action.effects import land_ms
    return max(t0 + MIN_WINDOW_MS, land_ms(t0, pc_intent.bound.est_duration_s))


def pull(horizon_ms, trigger_at, last_event_at):
    return min(horizon_ms, max(trigger_at + REACT_MARGIN_MS, last_event_at))
