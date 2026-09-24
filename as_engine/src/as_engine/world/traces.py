"""Diegetic traces (P10). Owner 'world.traces' (traces). Rules WORLD-03, TRACE-01..06.
docs/as/06_WORLD.md §3. The engine never says the world progressed; the world shows it: blood on a
step, boot prints in the dust, a gap on a shelf. A trace is what an observer can perceive of
something that happened when they were not there. It comes from something that happened (the event
that left it) and it goes the way marks go: time, weather, feet — never because a quota or the
player's absence said so (fidelity C02, C11). Every function that returns an Event has committed it
(writer 'world.traces', at and turn_index as given). W = RulesConfig().world.

TRACE-01 create(tx, place_id, kind, text, source_event_id, at, turn_index, *, locked=False,
                decay_days=None) -> str
  trace_id = tx.mint('trc'); days = decay_days, else W.trace_decay_days[kind] when the kind is
  listed there, else 14 — times W.sheltered_trace_mult when the place is not exposed
  (world.decay.exposed: a mark under a roof lasts longer); decay_days given is used as it is.
  TRACE_CREATED {trace_id, place_id, kind, text, locked} (place_id = the place, cause =
  source_event_id) inserting traces {trace_id, place_id, kind, text, source_event =
  source_event_id or '', created_at = at, decays_at = NULL when locked else at + days x DAY,
  locked} and, unless locked, kernel.clock.schedule(tx, decays_at, 'TRACE_DECAY', trace_id,
  {'trace_id': trace_id}, the TRACE_CREATED id). locked means a permanent mark (a carved name, a
  grave): no decay clock. An unknown place -> ValueError. Returns trace_id.
TRACE-02 decay(tx, rng, row, fired, turn_index) -> list[Event]   (the TRACE_DECAY handler)
  The trace named by the payload; gone already, or locked -> []. Else TRACE_DECAYED {trace_id,
  place_id, kind, reason: 'time'} (cause = fired) deleting the row. (The row is the world's working
  set; the TRACE_CREATED and TRACE_DECAYED events keep its whole history.)
TRACE-04 traces_in(store, place_id) -> list[dict]: the place's traces, ordered (created_at,
  trace_id), as row dicts.
TRACE-05 What people perceive: mind.perception.compile_scene gives a holder in a place with light
  above 'dark' one visual percept per trace there (text = the trace text, source_id = the trace id)
  — the narrator and the Where you are panel read those percepts, never this table (Skull law).
TRACE-06 washout(tx, at, turn_index, cause_event_id) -> list[Event]   (world.worldmove.day step 1,
  after the day's weather)
  Only when world.decay.wet(tx): every trace (by trace_id) that is not locked, whose kind is in
  W.washes_out and whose place is exposed -> TRACE_DECAYED {trace_id, place_id, kind, reason:
  'weather'} (cause = cause_event_id) deleting the row, and its pending TRACE_DECAY row (when there
  is one) cancelled with kernel.clock.cancel(tx, queue_id, 'washed out', at, that event's id,
  turn_index). Marks indoors stay. Returns every event committed, in seq order.
Trace kinds used by the core engine: 'blood', 'corpse', 'damage', 'tracks', 'missing_stock',
'smoke', 'dropped_item', 'claw_marks', 'graffiti'; content (cascade create_trace) may add others.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.store import Store, Tx


def create(tx: "Tx", place_id: str, kind: str, text: str, source_event_id: str | None, at: int, turn_index: int, *,
           locked: bool = False, decay_days: float | None = None) -> str:
    raise NotImplementedError("P10")


def decay(tx: "Tx", rng, row: dict, fired: "Event", turn_index: int) -> list["Event"]:
    raise NotImplementedError("P10")


def traces_in(store: "Store | Tx", place_id: str) -> list[dict]:
    raise NotImplementedError("P10")


def washout(tx: "Tx", at: int, turn_index: int, cause_event_id: str | None) -> list["Event"]:
    raise NotImplementedError("P10")
from ._impl_p10 import trace_create as create, trace_decay as decay, traces_in, trace_washout as washout  # noqa
