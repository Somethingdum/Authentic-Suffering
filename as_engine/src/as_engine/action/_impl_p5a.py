"""Implementation: action.checks, action.tasks, mind.cues, actor.adjust_stress."""
from __future__ import annotations

import json
import math
import re

from ..contracts.common import CheckBand, attr_mod
from ..contracts.events import Event, EventType, WriteOp, WriteRecord


def _row(s, sql, p=()):
    r = s.query_one(sql, p)
    return dict(r) if r is not None else None


# =========================================================== checks
def compute_target(attr_value, skill_rank, has_tag, situation, scale, impairment, resistance, rules):
    t = attr_mod(attr_value) + skill_rank + (rules.tag_bonus if has_tag else 0) + situation + scale - impairment // 2 - resistance
    return max(rules.target_min, min(rules.target_max, t))


def band_for_margin(margin, rules):
    if margin >= rules.clean_margin:
        return CheckBand.CLEAN
    if margin >= 0:
        return CheckBand.COST
    if margin >= rules.fail_margin_min:
        return CheckBand.FAIL
    return CheckBand.BREAK


def stealth6(margin):
    if margin >= 5:
        return "ghost_protocol"
    if margin >= 3:
        return "unseen_passage"
    if margin >= 1:
        return "fleeting_suspicion"
    if margin == 0:
        return "heightened_suspicion"
    if margin >= -2:
        return "detected"
    return "compromised_with_prejudice"


def _skill_and_tag(tx, actor_id, spec):
    if not tx.query_one("SELECT 1 FROM actors WHERE actor_id=?", (actor_id,)):
        return 0, False
    from ..mind.actor import fused
    d = fused(tx, actor_id)
    rank = 0
    if spec.skill is not None:
        for s in d.capability.skills:
            if s.domain == spec.skill:
                rank = s.rank
    tag = bool(set(d.capability.tags) & set(spec.tags))
    return rank, tag


def roll(tx, rng, actor_id, def_id, spec, *, situation, resistance, scale=0, at, turn_index, cause_event_id=None):
    from ..action.checks import CheckResult
    R = tx.rules.checks
    b = _row(tx, "SELECT special, impairment FROM bodies WHERE body_id=?", (actor_id,))
    attr = json.loads(b["special"])[spec.attribute.value if hasattr(spec.attribute, "value") else spec.attribute]
    rank, tag = _skill_and_tag(tx, actor_id, spec)
    target = compute_target(attr, rank, tag, situation, scale, b["impairment"], resistance, R)
    draw = rng.d10(tx, "resolve", f"check:{actor_id}:{def_id}")
    margin = target - draw
    band = band_for_margin(margin, R)
    ladder = stealth6(margin) if spec.consequence_ladder == "stealth6" else None
    comps = {"attr_mod": attr_mod(attr), "skill_rank": rank, "tag_bonus": R.tag_bonus if tag else 0, "situation": situation,
             "scale": scale, "impairment_penalty": b["impairment"] // 2, "resistance": resistance}
    tx.commit_event(Event(type=EventType.CHECK_RESOLVED, writer="action.resolve", at=at, turn_index=turn_index, actor_id=actor_id,
                          cause_event_id=cause_event_id,
                          payload={"actor_id": actor_id, "def_id": def_id, "attribute": str(spec.attribute.value if hasattr(spec.attribute, "value") else spec.attribute),
                                   "attr_value": attr, "skill": spec.skill.value if spec.skill is not None else None, "skill_rank": rank,
                                   "tag_bonus": comps["tag_bonus"], "situation": situation, "scale": scale, "impairment": b["impairment"],
                                   "resistance": resistance, "target": target, "draw": draw, "margin": margin, "band": band.value, "ladder": ladder}))
    return CheckResult(target=target, draw=draw, margin=margin, band=band, components=comps)


def opposed(tx, rng, a_id, a_spec, b_id, b_spec, *, def_id, a_situation, b_situation, at, turn_index, cause_event_id=None,
            established_control=None):
    ra = roll(tx, rng, a_id, def_id, a_spec, situation=a_situation, resistance=0, at=at, turn_index=turn_index, cause_event_id=cause_event_id)
    rb = roll(tx, rng, b_id, def_id + ":defend", b_spec, situation=b_situation, resistance=0, at=at, turn_index=turn_index, cause_event_id=cause_event_id)
    diff = ra.margin - rb.margin
    if diff != 0:
        w = a_id if diff > 0 else b_id
        return w, ra, rb, ("clean" if abs(diff) >= 3 else "cost")
    if established_control in (a_id, b_id):
        return established_control, ra, rb, "control"
    if ra.components["attr_mod"] != rb.components["attr_mod"]:
        return (a_id if ra.components["attr_mod"] > rb.components["attr_mod"] else b_id), ra, rb, "ladder"
    d = rng.draw(tx, "resolve", f"tie:{a_id}:{b_id}", 2)
    return (a_id if d == 1 else b_id), ra, rb, "tie"


# =========================================================== tasks
def active_task(store, actor_id):
    return _row(store, "SELECT * FROM tasks WHERE actor_id=? AND status='active' ORDER BY started_at, task_id", (actor_id,))


def _step_ms(t):
    return round(t["step_s"] * 1000)


def _task_event(tx, t, values, at, turn_index, cause, extra=None):
    row = dict(t)
    row.update(values)
    payload = {"task_id": t["task_id"], "actor_id": t["actor_id"], "kind": t["kind"], "label": t["label"],
               "steps_done": row["steps_done"], "steps_total": t["steps_total"], "status": row["status"]}
    if extra:
        payload.update(extra)
    return tx.commit_event(Event(type=EventType.TASK_STEP, writer="action.tasks", at=at, turn_index=turn_index, actor_id=t["actor_id"],
                                 cause_event_id=cause, writes=[WriteRecord(op=WriteOp.UPDATE, table="tasks", key={"task_id": t["task_id"]}, values=values)],
                                 payload=payload))


def start(tx, actor_id, kind, label, steps_total, step_s, at, interrupt_on, target_ids, turn_index, *, focus=False):
    cur = active_task(tx, actor_id)
    if cur:
        pause(tx, cur["task_id"], at, None, turn_index)
    tid = tx.mint("tsk")
    sm = round(step_s * 1000)
    tx.commit_event(Event(type=EventType.TASK_STEP, writer="action.tasks", at=at, turn_index=turn_index, actor_id=actor_id,
                          writes=[WriteRecord(op=WriteOp.INSERT, table="tasks", values={
                              "task_id": tid, "actor_id": actor_id, "kind": kind, "label": label, "steps_total": steps_total,
                              "steps_done": 0, "step_s": step_s, "started_at": at, "next_due_at": at + sm, "interrupt_on": list(interrupt_on),
                              "target_ids": list(target_ids), "focus": int(focus), "status": "active"})],
                          payload={"task_id": tid, "actor_id": actor_id, "kind": kind, "label": label, "steps_done": 0,
                                   "steps_total": steps_total, "status": "active"}))
    return tid


def advance(tx, actor_id, to_ms, turn_index):
    t = active_task(tx, actor_id)
    if not t:
        return []
    sm = _step_ms(t)
    done = min(t["steps_total"], max(0, (to_ms - t["started_at"]) // sm))
    if done <= t["steps_done"]:
        return []
    at = t["started_at"] + done * sm
    if done == t["steps_total"]:
        vals = {"steps_done": done, "status": "done", "next_due_at": None}
    else:
        vals = {"steps_done": done, "status": "active", "next_due_at": t["started_at"] + (done + 1) * sm}
    return [_task_event(tx, t, vals, at, turn_index, None)]


def pause(tx, task_id, at, cause_event_id, turn_index):
    t = _row(tx, "SELECT * FROM tasks WHERE task_id=?", (task_id,))
    if not t or t["status"] != "active":
        raise ValueError("task is not active")
    advance(tx, t["actor_id"], at, turn_index)
    t = _row(tx, "SELECT * FROM tasks WHERE task_id=?", (task_id,))
    if t["status"] == "done":
        return None
    return _task_event(tx, t, {"status": "paused", "next_due_at": None}, at, turn_index, cause_event_id)


def resume(tx, task_id, at, cause_event_id, turn_index):
    t = _row(tx, "SELECT * FROM tasks WHERE task_id=?", (task_id,))
    if not t or t["status"] != "paused":
        raise ValueError("task is not paused")
    other = active_task(tx, t["actor_id"])
    if other:
        pause(tx, other["task_id"], at, cause_event_id, turn_index)
    sm = _step_ms(t)
    return _task_event(tx, t, {"status": "active", "started_at": at - t["steps_done"] * sm, "next_due_at": at + sm}, at, turn_index, cause_event_id)


def interrupt(tx, task_id, cause_event_id, at, turn_index):
    return pause(tx, task_id, at, cause_event_id, turn_index)


# =========================================================== actor stress
def adjust_stress(tx, actor_id, delta, cause_event_id, at, turn_index):
    if delta == 0:
        return None
    a = _row(tx, "SELECT stress FROM actors WHERE actor_id=?", (actor_id,))
    new = max(0, min(10, a["stress"] + delta))
    return tx.commit_event(Event(type=EventType.RESOLVE_CHANGE, writer="mind.actor", at=at, turn_index=turn_index, actor_id=actor_id,
                                 cause_event_id=cause_event_id,
                                 writes=[WriteRecord(op=WriteOp.UPDATE, table="actors", key={"actor_id": actor_id}, values={"stress": new})],
                                 payload={"stress_delta": delta, "stress": new}))


# =========================================================== cues
_MOVE_EFFECTS = {"move_to_anchor", "move_through_portal", "follow_body", "leave_place", "flee"}


def _ev(tx, eid):
    if not eid or str(eid).startswith("scene:"):
        return None
    r = _row(tx, "SELECT * FROM events WHERE event_id=?", (eid,))
    if r:
        r["payload"] = json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"]
    return r


def _pt_dist(tx, holder, place_id, x, y):
    pos = _row(tx, "SELECT * FROM positions WHERE body_id=?", (holder,))
    if pos["place_id"] == place_id:
        return math.hypot(pos["x_m"] - x, pos["y_m"] - y)
    return 999.0


def cues_of(tx, holder_id, turn_index, at):
    from ..physical.space import point_distance
    from ..sense import acoustics, optics
    out = set()
    ps = [dict(r) for r in tx.query("SELECT * FROM percept_log WHERE holder_id=? AND turn_index=? AND at<=? ORDER BY at, percept_id", (holder_id, turn_index, at))]
    body = lambda b: _row(tx, "SELECT * FROM bodies WHERE body_id=?", (b,))  # noqa: E731
    visible_srcs = set()
    for p in ps:
        det = json.loads(p["detail"])
        if p["channel"] == "visual" and det.get("level") in ("clear", "partial") and p["source_id"]:
            visible_srcs.add(p["source_id"])
    known = {r[0] for r in tx.query("SELECT known_name FROM acquaintance WHERE holder_id=? AND known_name IS NOT NULL", (holder_id,))}
    rel_aff = {r[0] for r in tx.query("SELECT to_id FROM relationships WHERE from_id=? AND affection>=2", (holder_id,))}
    hh = [r[0] for r in tx.query("SELECT household_id FROM household_members WHERE actor_id=?", (holder_id,))]
    house = set()
    guard_of = set()
    for h in hh:
        house |= {r[0] for r in tx.query("SELECT actor_id FROM household_members WHERE household_id=?", (h,))}
    for r in tx.query("SELECT guardian_of FROM household_members WHERE actor_id=?", (holder_id,)):
        guard_of |= set(json.loads(r[0]))
    house.discard(holder_id)
    bonded = rel_aff | house
    threats_near = set()
    for p in ps:
        det = json.loads(p["detail"])
        ev = _ev(tx, p["event_id"])
        pl = ev["payload"] if ev else {}
        vis = p["channel"] == "visual" and det.get("level") in ("clear", "partial")
        if p["channel"] in ("auditory", "speech") and p["fidelity"] in ("exact", "partial") and pl.get("source_db", 0) >= 80:
            out.add("loud_noise")
        if det.get("received_db", 0) >= 80:
            out.add("loud_noise")
        if ev and ev["type"] == "NOISE" and p["channel"] == "auditory":
            k = pl.get("kind")
            from ..physical.space import distance_to_point
            src = acoustics.source_point(tx, pl, ev["actor_id"])
            d = distance_to_point(tx, holder_id, src.place_id, src.x_m, src.y_m)
            d = 999.0 if d is None else d
            if k == "shoot":
                out.add("gunshot_close" if d <= 30 else "gunshot_distant")
            if k in ("glass_break", "metal_crash"):
                out.add(k)
            if k in _MOVE_EFFECTS and d <= 5 and ev["actor_id"] not in visible_srcs:
                out.add("footsteps_close")
            if k == "force_portal":
                out.add("door_forced")
        if p["channel"] == "speech":
            kn = det.get("speaker_known_as")
            if kn is None or kn not in known:
                out.add("voice_unknown")
            if det.get("addressed_to_me") and p["fidelity"] in ("exact", "partial"):
                names = _own_names(tx, holder_id)
                words = set(re.findall(r"[a-z']+", det.get("words", "").lower()))
                if names & words:
                    out.add("addressed_by_name")
            if det.get("armed_at_me"):
                out.add("weapon_pointed")
                out.add("threat_seen")
                if p["source_id"]:
                    threats_near.add(p["source_id"])
        if vis and ev:
            if ev["type"] == "ACTION_START" and pl.get("def_id") in ("shoot_center_mass", "shoot_head") and pl.get("target_id") == holder_id:
                out.add("weapon_pointed")
                out.add("threat_seen")
            if ev["type"] == "HARM" or (ev["type"] == "ACTION_START" and pl.get("verb") == "attack"):
                out.add("threat_seen")
                if ev["actor_id"]:
                    threats_near.add(ev["actor_id"])
            if ev["type"] == "HARM":
                w = _row(tx, "SELECT severity FROM wounds WHERE wound_id=?", (pl.get("wound_id"),))
                if w and w["severity"] in ("severe", "catastrophic"):
                    out.add("blood_seen")
                if pl.get("body_id") in bonded:
                    out.add("bonded_hurt")
                if pl.get("body_id") in guard_of:
                    out.add("dependent_in_danger")
            if ev["type"] == "ACTION_START" and pl.get("verb") == "attack" and pl.get("target_id") in guard_of:
                out.add("dependent_in_danger")
            if ev["type"] == "PORTAL_CHANGE" and "damage" in pl.get("changes", {}):
                out.add("door_forced")
            if ev["type"] == "MOVE" and ev["actor_id"] and ev["actor_id"] != holder_id:
                kn = _row(tx, "SELECT known_name FROM acquaintance WHERE holder_id=? AND subject_id=?", (holder_id, ev["actor_id"]))
                if not (kn and kn["known_name"]) and pl.get("from_place"):
                    hp = _row(tx, "SELECT * FROM positions WHERE body_id=?", (holder_id,))
                    if pl["to_place"] == hp["place_id"]:
                        fp = pl.get("from_place") == hp["place_id"]
                        prev = _prev_point(tx, ev)
                        dn = math.hypot(pl["x_m"] - hp["x_m"], pl["y_m"] - hp["y_m"])
                        dp = math.hypot(prev[0] - hp["x_m"], prev[1] - hp["y_m"]) if (fp and prev) else 1e9
                        if dn < dp:
                            out.add("stranger_approaching")
        if p["channel"] == "visual" and "bleeding badly" in p["text"]:
            out.add("blood_seen")
        if vis and p["source_id"] and p["source_id"].startswith("act_"):
            b = body(p["source_id"])
            if b:
                if b["kind"] == "infected" and b["alive"] and b["false_dead_until"] is None:
                    out.add("infected_seen")
                    out.add("threat_seen")
                    threats_near.add(p["source_id"])
                    d = point_distance(tx, holder_id, p["source_id"])
                    if d is not None and d <= 2:
                        out.add("infected_close")
                if not b["alive"] or b["false_dead_until"] is not None:
                    out.add("corpse_seen")
        # P10: what an infection shows, to someone who sees the host clearly and close
        if (p["channel"] == "visual" and det.get("level") == "clear" and p["source_id"]
                and p["source_id"].startswith("act_") and p["source_id"] != holder_id):
            b = body(p["source_id"])
            if b and b["alive"] and b["kind"] == "human":
                d = point_distance(tx, holder_id, p["source_id"])
                if d is not None and d <= tx.rules.infected.sign_range_m:
                    from ..physical.bodies import stages
                    if tx.query_one("SELECT 1 FROM wounds WHERE body_id=? AND type='bite' AND healed_at IS NULL",
                                    (p["source_id"],)):
                        out.add("bite_wound_seen")
                    for _pw, st in stages(tx, p["source_id"]):
                        out |= set(st.signs)
    for r in tx.query("SELECT payload, at FROM events WHERE type='CONTROL_ESTABLISH' AND turn_index=? AND at<=?", (turn_index, at)):
        pl = json.loads(r[0])
        if pl.get("target_id") == holder_id:
            saw = any(p["source_id"] == pl["holder_id"] and p["channel"] == "visual" and json.loads(p["detail"]).get("level") in ("clear", "partial")
                      and p["at"] < r[1] for p in ps)
            if not saw:
                out.add("grabbed_from_behind")
    if optics.light_at(tx, holder_id, at) <= 1:
        out.add("dark_room")
    for tb in threats_near:
        for g in guard_of:
            d = point_distance(tx, g, tb)
            if d is not None and d <= 5:
                out.add("dependent_in_danger")
    for r in tx.query("SELECT payload FROM events WHERE type='PROMISE_BROKEN' AND turn_index=? AND at<=?", (turn_index, at)):
        if json.loads(r[0]).get("promisee_id") == holder_id:
            out.add("promise_broken")
    return out


def _other_place_distance(tx, holder_id, src):
    from ..physical.space import portal_point, distance_m
    # portal-path distance to a point: route via path() from the holder to the source place
    from ..physical.space import path
    legs = path(tx, holder_id, src.place_id, None, allow_closed=True)
    if legs is None:
        return 999.0
    tot = sum(l.distance_m for l in legs[:-1])
    last_portal = legs[-2].portal_id if len(legs) >= 2 else None
    if last_portal:
        x, y = portal_point(tx, last_portal, src.place_id)
        tot += distance_m(x, y, src.x_m, src.y_m)
    return tot


def _prev_point(tx, ev):
    pl = ev["payload"]
    if pl.get("from_anchor"):
        a = _row(tx, "SELECT x_m, y_m FROM anchors WHERE anchor_id=?", (pl["from_anchor"],))
        return (a["x_m"], a["y_m"])
    return None


def _own_names(tx, holder_id):
    from ..mind.actor import fused
    try:
        d = fused(tx, holder_id)
    except Exception:  # noqa: BLE001
        return set()
    names = {d.identity.name.split()[0].lower()} | {a.split()[0].lower() for a in d.identity.aliases}
    return names
