"""Implementation of turn/timers.py."""
from __future__ import annotations

import json


def _ev_model(tx, seq_after):
    from ..action._impl_p5b import _events_since
    return _events_since(tx, seq_after)


def dispatch(tx, rng, row, fired, turn_index, horizon_ms):
    from ..audit.log import record
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    first = tx.query_one("SELECT COALESCE(MAX(seq),0) FROM events")[0]
    pl = json.loads(row["payload"]) if isinstance(row["payload"], str) else dict(row["payload"])
    t = row["type"]
    at = row["due_at"]
    if t == "NOISE":
        tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", at=at, turn_index=turn_index, place_id=pl.get("place_id"),
                              cause_event_id=fired.event_id, payload=pl))
    elif t == "ACTION_LAND":
        from ..action.resolve import land_pending
        land_pending(tx, rng, row, turn_index, horizon_ms=horizon_ms)
    elif t == "SPEECH_SEGMENT":
        from ..action.resolve import say_pending
        say_pending(tx, row, turn_index)
    elif t == "WEATHER_CHANGE":
        vals = {"weather": pl["weather"]}
        if "wind_level" in pl:
            vals["wind_level"] = pl["wind_level"]
        tx.commit_event(Event(type=EventType.WEATHER_CHANGE, writer="kernel.clock", at=at, turn_index=turn_index, cause_event_id=fired.event_id,
                              payload=pl, writes=[WriteRecord(op=WriteOp.UPDATE, table="world_clock", key={"id": 1}, values=vals)]))
    elif t == "PORTAL_CHANGE":
        from ..physical.space import portal_change_event
        tx.commit_event(portal_change_event(tx, pl["portal_id"], pl["changes"], at, None, fired.event_id, turn_index))
    elif t == "ARRIVAL":
        from ..physical.space import move_event
        a = pl.get("anchor_id")
        if a:
            r = tx.query_one("SELECT x_m, y_m FROM anchors WHERE anchor_id=?", (a,))
            x, y = r[0], r[1]
        else:
            p = tx.query_one("SELECT width_m, depth_m FROM places WHERE place_id=?", (pl["place_id"],))
            x, y = p[0] / 2, p[1] / 2
        tx.commit_event(move_event(tx, pl["body_id"], pl["place_id"], a, x, y, at, fired.event_id, turn_index))
    elif t == "CASCADE_EFFECT":
        from ..action._impl_p5b import fire_scheduled
        fire_scheduled(tx, rng, row, fired, turn_index)
    elif t == "PRODUCTION_CYCLE":
        from ..society._impl_society import cycle
        cycle(tx, rng, row, fired, turn_index)
    elif t == "SETTLEMENT_DAY":
        from ..society._impl_society import settlement_day
        settlement_day(tx, rng, row, fired, turn_index)
    elif t == "GROUP_DAY":
        from ..society._impl_society import group_day
        group_day(tx, rng, row, fired, turn_index)
    elif t == "ROUTINE_STEP":
        from ..society._impl_society import routine_step
        routine_step(tx, rng, row, fired, turn_index)
    elif t == "LOYALTY_CHECK":
        from ..society._impl_society import loyalty_check
        loyalty_check(tx, pl["actor_id"], pl["group_id"], pl.get("reason") or "scheduled", at, turn_index, fired.event_id)
    elif t == "WORLD_DAY":
        from ..world import worldmove
        worldmove.day(tx, rng, row, fired, turn_index)
    elif t == "OPERATION_STEP":
        from ..world import worldmove
        worldmove.step(tx, rng, row, fired, turn_index)
    elif t == "INFECTED_STEP":
        from ..world import infected
        infected.step(tx, rng, row, fired, turn_index)
    elif t == "REANIMATION":
        from ..world import infected
        infected.rise(tx, rng, row, fired, turn_index)
    elif t == "TRACE_DECAY":
        from ..world import traces
        traces.decay(tx, rng, row, fired, turn_index)
    elif t == "HORDE_STEP":
        from ..world import hordes
        hordes.step(tx, rng, row, fired, turn_index)
    elif t == "POOL_RISE":
        from ..world import hordes
        hordes.rise(tx, rng, row, fired, turn_index)
    elif t == "COUNCIL":
        from ..world import factions
        factions.step(tx, rng, row, fired, turn_index)
    else:
        record(tx, "G0-timers", "turn.pipeline", "warn", [{"kind": "timer_unbuilt", "type": t, "queue_id": row["queue_id"]}], turn_index)
    return _ev_model(tx, first)


def fire_one(tx, rng, row, turn_index, horizon_ms):
    from ..action import cascade
    from ..action.propagate import propagate
    from ..kernel import clock
    fired = clock.fire(tx, row, turn_index)
    made = dispatch(tx, rng, row, fired, turn_index, horizon_ms)
    made += propagate(tx, made, row["due_at"], turn_index)
    made += cascade.sweep(tx, made, tx.canon.all("cascade"), row["due_at"], turn_index)
    return [fired] + made


def fire_due(tx, rng, until_ms, turn_index, horizon_ms):
    from ..kernel import clock
    out = []
    while True:
        rows = clock.due_between(tx, -1, until_ms)
        if not rows:
            return out
        out += fire_one(tx, rng, rows[0], turn_index, horizon_ms)


def seed_society(tx, at, turn_index):
    from ..society import _impl_society as soc
    out = []
    for r in tx.query("SELECT settlement_id, group_id FROM settlements ORDER BY settlement_id"):
        sid, gid = r[0], r[1]
        out += soc.settlement_ensure(tx, sid, at, turn_index)
        out += soc.work_ensure(tx, sid, at, turn_index)
        if gid:
            out += soc.group_ensure(tx, gid, at, turn_index)
        out += soc.routine_ensure(tx, sid, at, turn_index)
    return out


def seed_world(tx, at, turn_index):
    if tx.query_one("SELECT 1 FROM world_params WHERE id=1") is None:
        return []
    from ..world import factions, worldmove
    return worldmove.ensure_timers(tx, at, turn_index) + factions.ensure_timers(tx, at, turn_index)


def run_offscreen(tx, rng, until_ms, turn_index):
    from ..kernel import clock
    from ..kernel.errors import ClockError
    from ..physical import bodies
    first = tx.query_one("SELECT COALESCE(MAX(seq),0) FROM events")[0]
    now = clock.now(tx)
    if until_ms < now:
        raise ClockError("the off-screen step cannot run backwards")
    step = int(tx.rules.world.offscreen_tick_h * 3_600_000)
    while now < until_ms:
        end = min(until_ms, now + step)
        seed_society(tx, now, turn_index)
        seed_world(tx, now, turn_index)
        fire_due(tx, rng, end, turn_index, end)
        for b in [r[0] for r in tx.query("SELECT b.body_id FROM bodies b JOIN positions p ON p.body_id=b.body_id "
                                         "WHERE b.alive=1 ORDER BY b.body_id")]:
            bodies.progress(tx, b, end, turn_index, rng)
        clock.advance_event(tx, end, "offscreen")
        now = end
    return _ev_model(tx, first)
