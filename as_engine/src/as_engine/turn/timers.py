"""Timer dispatch (P7; the society's clocks P9; the world's P10): what happens when an event_queue row comes due.
Rules TIME-06..10, CAS-06.
kernel.clock.QUEUE_TYPES names each type's owner; this module is the switchboard the turn pipeline
calls after kernel.clock.fire has committed TIMER_FIRED for the row.

dispatch(tx, rng, row, fired, turn_index, horizon_ms) -> list[Event]
  ``row`` is the event_queue row (payload may be a JSON string or a dict), ``fired`` the committed
  TIMER_FIRED event (the cause of everything below); at = row.due_at. Returns every event committed
  from here (in seq order), including those the owners commit.
    NOISE           commit NOISE (writer 'action.propagate', no writes) with payload = the row's
                    payload unchanged, place_id = payload.place_id, cause = fired.
    ACTION_LAND     action.resolve.land_pending(tx, rng, row, turn_index, horizon_ms=horizon_ms).
    WEATHER_CHANGE  commit WEATHER_CHANGE (writer 'kernel.clock', payload = the row's payload)
                    updating world_clock.weather (and wind_level when the payload has it).
    PORTAL_CHANGE   commit physical.space.portal_change_event(tx, payload.portal_id,
                    payload.changes, at, None, fired.event_id, turn_index).
    ARRIVAL         commit physical.space.move_event(tx, payload.body_id, payload.place_id,
                    payload.anchor_id or None, x, y, at, fired.event_id, turn_index) — x, y = the
                    anchor's point, or the place centre (width_m / 2, depth_m / 2) without one.
    CASCADE_EFFECT  action.cascade.fire_scheduled(tx, rng, row, fired, turn_index)        (P9)
    PRODUCTION_CYCLE society.work.cycle(tx, rng, row, fired, turn_index)                   (P9)
    SETTLEMENT_DAY  society.settlement.day(tx, rng, row, fired, turn_index)                (P9)
    GROUP_DAY       society.group.day(tx, rng, row, fired, turn_index)                     (P9)
    ROUTINE_STEP    society.routine.step(tx, rng, row, fired, turn_index)                  (P9)
    LOYALTY_CHECK   society.group.loyalty_check(tx, payload.actor_id, payload.group_id,
                    payload.reason or 'scheduled', at, turn_index, fired.event_id)          (P9)
    WORLD_DAY       world.worldmove.day(tx, rng, row, fired, turn_index)                   (P10)
    OPERATION_STEP  world.worldmove.step(tx, rng, row, fired, turn_index)                  (P10)
    INFECTED_STEP   world.infected.step(tx, rng, row, fired, turn_index)                   (P10)
    REANIMATION     world.infected.rise(tx, rng, row, fired, turn_index)                   (P10)
    TRACE_DECAY     world.traces.decay(tx, rng, row, fired, turn_index)                    (P10)
    any other type  (a type whose owner is not built) -> audit.log.record(tx, 'G0-timers', 'turn.pipeline', 'warn',
                    [{kind: 'timer_unbuilt', type, queue_id}], turn_index) and nothing else. The row
                    has already been fired, so the gate's S08 still holds; the P11 release audit
                    fails a build that still records one.
  When a later phase builds an owner it adds its line here (the handler's name is in that phase's
  module docstring).

P9 — the society's clocks and the off-screen step:
fire_one(tx, rng, row, turn_index, horizon_ms) -> list[Event]   (TIME-07)
  fired = kernel.clock.fire(tx, row, turn_index); made = dispatch(tx, rng, row, fired, turn_index,
  horizon_ms); made += action.propagate.propagate(tx, made, row['due_at'], turn_index); made +=
  action.cascade.sweep(tx, made, the canon cascade rules, row['due_at'], turn_index). Returns
  [fired] + made — every event committed, in seq order. (Stage 11's timer loop is exactly this,
  plus perception.)
fire_due(tx, rng, until_ms, turn_index, horizon_ms) -> list[Event]   (TIME-08)
  While kernel.clock.due_between(tx, -1, until_ms) is not empty: fire_one(its first row). A row a
  handler schedules inside the window fires in the same call. Returns every event committed.
seed_society(tx, at, turn_index) -> list[str]   (TIME-09)
  Makes sure every settlement's clocks are running (idempotent; a world without settlements —
  every P7 scenario — gets nothing). For each settlement (by settlement_id):
  society.settlement.ensure_timers, then society.work.ensure_timers, then — when it has a
  governing group — society.group.ensure_timers(group), then society.routine.ensure_timers; all
  with (tx, id, at, turn_index). Returns every new queue id in that order.
seed_world(tx, at, turn_index) -> list[str]   (P10, TIME-11)
  A run with a world_params row (a generated world) -> world.worldmove.ensure_timers(tx, at,
  turn_index); a run without one (every hand-made scenario) -> [] (nothing changes for them).
run_offscreen(tx, rng, until_ms, turn_index) -> list[Event]   (TIME-10, the off-screen step)
  The world with nobody deciding: COLD fidelity, code only, no model call. until_ms < now ->
  ClockError. While now < until_ms: end = min(until_ms, now + WorldRules.offscreen_tick_h hours);
  seed_society(tx, now, turn_index); seed_world(tx, now, turn_index) (P10); fire_due(tx, rng, end,
  turn_index, end);
  physical.bodies.progress(tx, b, end, turn_index, rng) for every living body (by body_id);
  kernel.clock.advance_event(tx, end, 'offscreen'). Returns every event committed. The turn
  pipeline plays the same rules inside its own windows (04 §Stage 0, §Stage 12); P9 tests use this
  to let a settlement run for days, and P10 uses it for the world beyond the PC.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.rng import Rng
    from ..kernel.store import Tx


# P10 (above the P9 and P7 functions, so the kit's patches merge over built code).
def seed_world(tx: "Tx", at: int, turn_index: int) -> list[str]:
    raise NotImplementedError("P10")


# The P9 functions stand above dispatch (P7) so the kit's P9 patch merges over a built dispatch.
def fire_one(tx: "Tx", rng: "Rng", row: dict, turn_index: int, horizon_ms: int) -> list["Event"]:
    raise NotImplementedError("P9")


def fire_due(tx: "Tx", rng: "Rng", until_ms: int, turn_index: int, horizon_ms: int) -> list["Event"]:
    raise NotImplementedError("P9")


def seed_society(tx: "Tx", at: int, turn_index: int) -> list[str]:
    raise NotImplementedError("P9")


def run_offscreen(tx: "Tx", rng: "Rng", until_ms: int, turn_index: int) -> list["Event"]:
    raise NotImplementedError("P9")


def dispatch(tx: "Tx", rng: "Rng", row: dict, fired: "Event", turn_index: int, horizon_ms: int) -> list["Event"]:
    raise NotImplementedError("P7")
