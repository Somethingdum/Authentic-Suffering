"""World clock (P0). docs/as/07_RULES.md §Time. Rules TIME-01..05.

World time is integer milliseconds since the world epoch: day 0 00:00 = the day of the Fall.
The clock only moves forward (TIME-01). A turn is a transaction, not a unit of time: the turn
controller advances the clock to the earliest due event / completion / percept / condition
change, never by a fixed tick and never by zero when a condition-ended action waits (TIME-03).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from ..contracts.events import Event
    from .store import Store, Tx

MS_PER_S = 1000
MS_PER_MIN = 60 * MS_PER_S
MS_PER_H = 60 * MS_PER_MIN
MS_PER_DAY = 24 * MS_PER_H

PartOfDay = Literal["dawn", "morning", "midday", "afternoon", "evening", "night", "late night"]


@dataclass(frozen=True)
class WorldTime:
    day: int
    hour: int
    minute: int
    second: int
    part_of_day: PartOfDay


def part_of_day(hour: int) -> PartOfDay:
    """05-06 dawn, 07-10 morning, 11-13 midday, 14-17 afternoon, 18-20 evening, 21-23 night, 00-04 late night."""
    if 5 <= hour <= 6:
        return "dawn"
    if 7 <= hour <= 10:
        return "morning"
    if 11 <= hour <= 13:
        return "midday"
    if 14 <= hour <= 17:
        return "afternoon"
    if 18 <= hour <= 20:
        return "evening"
    if 21 <= hour <= 23:
        return "night"
    return "late night"


def world_time(ms: int) -> WorldTime:
    """Implemented. Negative ms raise ValueError."""
    if ms < 0:
        raise ValueError("world time cannot be negative")
    day, rem = divmod(ms, MS_PER_DAY)
    hour, rem = divmod(rem, MS_PER_H)
    minute, rem = divmod(rem, MS_PER_MIN)
    second = rem // MS_PER_S
    return WorldTime(day, hour, minute, second, part_of_day(hour))


def format_clock(ms: int) -> str:
    """'HH:MM' 24h."""
    t = world_time(ms)
    return f"{t.hour:02d}:{t.minute:02d}"


# Timer queue types (TIME-06): event_queue.type -> the module whose handler runs when it comes due.
# Stage 0 (and the post-wave sweep) commits TIMER_FIRED (writer 'kernel.clock', status -> 'fired',
# cause = the queue row's source_event_id) and then calls the owner's handler with the row, which
# commits the resulting events with cause = the TIMER_FIRED event. An unknown type is a
# ValidationFailure (rule TIME-06) at scheduling time, never a silent skip.
QUEUE_TYPES: dict[str, str] = {
    "NOISE": "action.propagate",          # payload {source_db, kind, text, anchor_id?, x_m?, y_m?}
    "WEATHER_CHANGE": "kernel.clock",     # payload {weather, wind_level}
    "PORTAL_CHANGE": "physical.space",    # payload {portal_id, changes}
    "ARRIVAL": "physical.space",          # payload {body_id, place_id, anchor_id?} (a body walks in)
    "CASCADE_EFFECT": "action.cascade",   # payload {rule_id, effect_index, target, trigger_event_id} (CAS-06, P9)
    "REANIMATION": "world.infected",      # payload {body_id, pathway} (a corpse rises, P10: world.infected.rise)
    "INFECTED_STEP": "world.infected",    # payload {body_id, leg} (P10: one step of an infected body)
    "WORLD_DAY": "world.worldmove",       # payload {} (P10: the world's daily tick)
    "OPERATION_STEP": "world.worldmove",  # payload {op_id, step} (P10)
    "HORDE_STEP": "world.hordes",         # payload {horde_id} (P10: a horde walks on, mills, or keeps a street full)
    "POOL_RISE": "world.hordes",          # payload {zone_id, count, pathway} (P10: the unnamed dead rise)
    "COUNCIL": "world.factions",          # payload {group_id, step, meeting?} (P10: a faction council convenes / adjourns)
    "ROUTINE_STEP": "society.routine",    # payload {actor_id}
    "PRODUCTION_CYCLE": "society.work",   # payload {workplace_id}
    "SETTLEMENT_DAY": "society.settlement",  # payload {settlement_id} (the daily draw, P9)
    "GROUP_DAY": "society.group",         # payload {group_id} (the daily group tick, P9)
    "TRACE_DECAY": "world.traces",        # payload {trace_id}
    "LOYALTY_CHECK": "society.group",     # payload {actor_id, group_id, reason} (group benefit check at a crisis)
    "ACTION_LAND": "action.resolve",      # payload {intent: action.intent.intent_to_dict(...), start_event_id} (P5)
    "SPEECH_SEGMENT": "action.resolve",   # payload {the SPEECH payload of one segment} (P5, SEG-03: action.resolve.say_pending)
}

# P9: the background life of a place — a settlement's shifts, draws, routines and group days, and
# delayed consequences. These rows do not end the PC's condition-ended window (turn.select HOR-01):
# a neighbour's shift change is not news. Everything else in QUEUE_TYPES is news. P10 adds the
# world's own clocks: its day, operations, infected steps and rising dead (what they cause still
# ends a watch through what the PC perceives). The hordes' steps and the rising of the unnamed dead
# are background too: a horde matters when it is heard or seen, through the PC's percepts.
BACKGROUND_QUEUE_TYPES: frozenset[str] = frozenset({
    "ROUTINE_STEP", "PRODUCTION_CYCLE", "SETTLEMENT_DAY", "GROUP_DAY", "LOYALTY_CHECK",
    "CASCADE_EFFECT", "TRACE_DECAY",
    "WORLD_DAY", "OPERATION_STEP", "INFECTED_STEP", "REANIMATION", "HORDE_STEP", "POOL_RISE", "COUNCIL",
})


def now(store_or_tx: "Store | Tx") -> int:
    """Current world time from world_clock.now_ms."""
    return store_or_tx.query_one("SELECT now_ms FROM world_clock WHERE id=1")[0]


def turn_index(store_or_tx: "Store | Tx") -> int:
    return store_or_tx.query_one("SELECT turn_index FROM world_clock WHERE id=1")[0]


def advance_event(tx: "Tx", to_ms: int, reason: str) -> "Event | None":
    """Build (and commit through ``tx.commit_event``) a CLOCK_ADVANCE event writer 'kernel.clock'
    updating world_clock.now_ms. ``to_ms == now`` returns None (no event). ``to_ms < now`` raises
    ClockError (rule TIME-01)."""
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    from .errors import ClockError
    cur = now(tx)
    if to_ms == cur:
        return None
    if to_ms < cur:
        raise ClockError("clock cannot go back")
    return tx.commit_event(Event(type=EventType.CLOCK_ADVANCE, writer="kernel.clock", at=to_ms, turn_index=turn_index(tx),
        payload={"reason": reason, "from": cur}, writes=[WriteRecord(op=WriteOp.UPDATE, table="world_clock", key={"id": 1}, values={"now_ms": to_ms})]))


def schedule(tx: "Tx", due_at: int, type_: str, subject_id: str | None, payload: dict[str, Any],
             source_event_id: str | None, *, event_origin: str = "sim") -> str:
    """Commit a TIMER_SET event (writer 'kernel.clock', cause = source_event_id, origin =
    event_origin — the scenario loader passes 'system') inserting a
    pending event_queue row. Returns queue_id (kind 'que'). ``due_at`` < now raises ClockError;
    ``type_`` not in QUEUE_TYPES raises ValidationFailure(rule='TIME-06').
    When the turn controller reaches ``due_at`` it commits TIMER_FIRED (status -> 'fired') and
    dispatches ``type_`` to the owning module's handler (04_TURN_PIPELINE.md §Stage 0)."""
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    from .errors import ClockError, ValidationFailure
    if type_ not in QUEUE_TYPES:
        raise ValidationFailure(f"unknown timer type {type_}", rule="TIME-06")
    cur = now(tx)
    if due_at < cur:
        raise ClockError("cannot schedule in the past")
    qid = tx.mint("que")
    tx.commit_event(Event(type=EventType.TIMER_SET, writer="kernel.clock", at=cur, turn_index=turn_index(tx), cause_event_id=source_event_id, origin=event_origin,
        payload={"queue_id": qid, "type": type_}, writes=[WriteRecord(op=WriteOp.INSERT, table="event_queue", values={"queue_id": qid, "due_at": due_at, "type": type_, "subject_id": subject_id, "payload": payload, "source_event_id": source_event_id, "status": "pending"})]))
    return qid


def due_between(store_or_tx: "Store | Tx", start_ms: int, end_ms: int) -> list[dict[str, Any]]:
    """Pending event_queue rows with start_ms < due_at <= end_ms ordered by (due_at, queue_id)."""
    return [dict(r) for r in store_or_tx.query("SELECT * FROM event_queue WHERE status='pending' AND due_at > ? AND due_at <= ? ORDER BY due_at, queue_id", (start_ms, end_ms))]


def next_due(store_or_tx: "Store | Tx", after_ms: int) -> int | None:
    """Earliest due_at in the timer_bank view strictly after ``after_ms`` (None if none)."""
    r = store_or_tx.query_one("SELECT MIN(due_at) FROM timer_bank WHERE due_at > ?", (after_ms,))
    return r[0]


def begin_turn(tx: "Tx", turn_index: int) -> "Event":
    """P7 (the turn pipeline's stage 0). Commit CLOCK_ADVANCE {reason: 'turn_start', from: now,
    turn_index} (writer 'kernel.clock', at = now, the event's own turn_index = ``turn_index``)
    updating world_clock.turn_index (now_ms unchanged). ``turn_index`` must be the current
    world_clock.turn_index + 1, else ClockError: turns are numbered 1, 2, 3 … and never skip (the
    scenario / worldgen load is turn 0)."""
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    from .errors import ClockError
    cur = turn_index_ = tx.query_one("SELECT turn_index FROM world_clock WHERE id=1")[0]
    if turn_index != cur + 1:
        raise ClockError(f"turn {turn_index} does not follow {cur}")
    n = now(tx)
    return tx.commit_event(Event(type=EventType.CLOCK_ADVANCE, writer="kernel.clock", at=n, turn_index=turn_index,
        payload={"reason": "turn_start", "from": n, "turn_index": turn_index},
        writes=[WriteRecord(op=WriteOp.UPDATE, table="world_clock", key={"id": 1}, values={"turn_index": turn_index})]))


def daylight_level(ms: int, weather: str) -> int:
    """Outdoor light 0..4 (07_RULES.md §Light): late night 0, night 1 (moon), dawn/evening 2,
    morning/afternoon 3, midday 4; overcast/rain -1, storm/fog -2; clamp 0..4. Implemented below."""
    pod = world_time(ms).part_of_day
    base = {"late night": 0, "night": 1, "dawn": 2, "evening": 2, "morning": 3, "afternoon": 3, "midday": 4}[pod]
    base -= {"overcast": 1, "rain": 1, "storm": 2, "fog": 2}.get(weather, 0)
    return max(0, min(4, base))


def fire(tx: "Tx", row: dict[str, Any], turn_index: int) -> "Event":
    """P5. Commit TIMER_FIRED {queue_id, type, subject_id} (writer 'kernel.clock', at =
    row['due_at'], cause = row['source_event_id']) setting the row's status to 'fired'. The caller
    then dispatches the row to its owner's handler with this event as cause. A row that is not
    pending -> ClockError."""
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    from .errors import ClockError
    cur = tx.query_one("SELECT status FROM event_queue WHERE queue_id=?", (row["queue_id"],))
    if cur is None or cur[0] != "pending":
        raise ClockError("not pending")
    return tx.commit_event(Event(type=EventType.TIMER_FIRED, writer="kernel.clock", at=row["due_at"], turn_index=turn_index,
                                 cause_event_id=row.get("source_event_id"),
                                 payload={"queue_id": row["queue_id"], "type": row["type"], "subject_id": row.get("subject_id")},
                                 writes=[WriteRecord(op=WriteOp.UPDATE, table="event_queue", key={"queue_id": row["queue_id"]}, values={"status": "fired"})]))


def cancel(tx: "Tx", queue_id: str, reason: str, at: int, cause_event_id: str | None,
           turn_index: int) -> "Event":
    """P5. Commit TIMER_CANCELLED {queue_id, type, reason} (writer 'kernel.clock') setting status
    'cancelled'. A row that is not pending -> ClockError."""
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    from .errors import ClockError
    cur = tx.query_one("SELECT status, type FROM event_queue WHERE queue_id=?", (queue_id,))
    if cur is None or cur[0] != "pending":
        raise ClockError("not pending")
    return tx.commit_event(Event(type=EventType.TIMER_CANCELLED, writer="kernel.clock", at=at, turn_index=turn_index,
                                 cause_event_id=cause_event_id, payload={"queue_id": queue_id, "type": cur[1], "reason": reason},
                                 writes=[WriteRecord(op=WriteOp.UPDATE, table="event_queue", key={"queue_id": queue_id}, values={"status": "cancelled"})]))


def pending_for(store_or_tx: "Store | Tx", type_: str, subject_id: str) -> list[dict[str, Any]]:
    """P5. Pending rows of one type for one subject, ordered by (due_at, queue_id)."""
    return [dict(r) for r in store_or_tx.query("SELECT * FROM event_queue WHERE status='pending' AND type=? AND subject_id=? ORDER BY due_at, queue_id", (type_, subject_id))]
