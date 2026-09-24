"""Work and production (P9). Owner 'society.work' (workplaces, work_assignments). Rules WORK-01..12,
ECON-01. docs/as/06_WORLD.md §2.3. Every function that returns an Event has committed it (writer
'society.work', at and turn_index as given; place_id = the workplace's place when it has one).
R = RulesConfig().society. H = 3_600_000 ms, DAY = 24 H.

Assignment keys: a work_assignments row is named f"{workplace_id}:{role}:{actor_id}:{shift_start_hh}"
  (the cascade selector work_assignments_of returns these). parse_key(key) -> (workplace_id, role,
  actor_id, shift_start_hh:int). Malformed -> ValueError.

WORK-01 qualified(store, actor_id, role) -> bool
  R.role_skill[role] = (domain, rank): the fused dossier's (mind.actor.fused) skill rank in that
  domain >= rank. A role not in R.role_skill -> True. A body without an actors row -> False.
WORK-02 able(store, actor_id, role) -> tuple[bool, str]
  (False, reason) for the first that applies: the body is dead ('dead'); awareness 'unconscious'
  ('unconscious'); bodies.restrained = 1 ('held'); the role is in R.manual_roles and an unhealed
  wound (healed_at NULL) on anatomy whose ANATOMY_GROUP is 'arm' or 'hand' has function_loss >= 1
  ('hurt'). Otherwise (True, ''). Asleep is able: people wake for their shift.
WORK-03 overlap_h(shift_start_hh, shift_end_hh, start_ms, end_ms) -> float
  Hours shared by the interval (start_ms, end_ms] and the daily shift [shift_start_hh,
  shift_end_hh) — every daily occurrence of it, including the one that began the day before
  start_ms; a shift with end <= start runs past midnight (18 -> 6 is twelve hours).
  shifts_overlap(a_start, a_end, b_start, b_end) -> bool: two daily shifts share at least one hour.
WORK-04 crew(store, workplace_id, start_ms, end_ms) -> list[tuple[str, str]]
  (actor_id, role) of every work_assignments row of the workplace with overlap_h > 0 whose actor is
  able (WORK-02) and qualified (WORK-01) for the row's role, without duplicates, sorted by (role,
  actor_id). staffed_fraction(required_roles, crew) -> float: for each distinct role r in
  required_roles, min(required_roles.count(r), number of crew entries with role r); their sum /
  len(required_roles); 1.0 when required_roles is empty.
WORK-05 cycle(tx, rng, row, fired, turn_index) -> list[Event]   (the PRODUCTION_CYCLE handler)
  w = the workplace row['subject_id'], at = row['due_at'], start = at - cycle_h * H.
  1 crew = crew(w, start, at); staffed = staffed_fraction(w.required_roles, crew).
  2 spite = society.group.animosity(tx, rng, [actor ids of crew], w, at, turn_index,
    fired.event_id) (1.0 when no pair qualifies).
  3 condition_factor = 1.0 when machinery_condition >= R.condition_full_at, else 0.5 +
    machinery_condition / 100. factor = efficiency * staffed * condition_factor * spite (in that
    order). output = {res: floor(base * factor + 1e-9)} for each outputs entry, sorted by name.
  4 PRODUCTION_CYCLE {workplace_id, settlement_id, site_type, crew: [[actor, role], ...], staffed,
    efficiency, condition_factor, spite, output, window_start: start, window_end: at} (cause
    fired) writing workplaces next_due_at = at + cycle_h * H and stall_reasons = ['unstaffed']
    when staffed == 0, else [].
  5 when any output value > 0 and the workplace has a settlement: society.settlement.receive(tx,
    settlement_id, {res: value > 0 ...}, 'production', at, turn_index, the PRODUCTION_CYCLE id).
  6 covers end: for each covering row (covering_for NOT NULL) at this workplace, in key order,
    whose covered actor is able for the role again: ROLE_RELEASED {workplace_id, role, actor_id,
    shift_start_hh, covering_for, reason: 'returned'} deleting the row, then society.settlement.
    remove_vacancy for (workplace, role, the covered actor) when there is one. (A dead worker's
    cover is not released: it has become the post.)
  7 WORK-09 efficiency recovery.
  8 kernel.clock.schedule(tx, at + cycle_h * H, 'PRODUCTION_CYCLE', w, {'workplace_id': w}, the
    PRODUCTION_CYCLE id). Returns every event committed, in seq order.
WORK-06 miss_shift(tx, key, reason, at, turn_index, cause_event_id) -> Event | None
  (cascade dispatch of SHIFT_MISSED — core CAS-001 schedules it for an arm injury, CAS-007 at a
  death.) No such row -> None. The worker able for the role (they turned up able to work) ->
  audit.log.record(tx, 'G10-cascade', 'society.work', 'pass', [{kind: 'shift_not_missed', key}],
  turn_index) and None. Otherwise SHIFT_MISSED {workplace_id, role, actor_id, shift_start_hh,
  shift_end_hh, reason} (event actor_id = the worker); for reason 'dead' the same event deletes
  the row (a dead worker holds no post). Then, when reason is 'dead' or pick_cover(...) finds
  nobody: society.settlement.add_vacancy(tx, settlement_id, workplace_id, role, actor_id, at,
  turn_index, the SHIFT_MISSED id).
WORK-07 pick_cover(store, workplace_id, role, shift_start_hh, shift_end_hh, exclude) -> str | None
  Candidates: named members of the workplace's settlement (society.population.census) other than
  ``exclude``, whose actors.controller is not 'human' (code never assigns a human's body), whose
  age band is teen or adult, who are qualified and able for the role, and none of whose
  work_assignments rows shares an hour with [shift_start_hh, shift_end_hh) (shifts_overlap).
  Sorted by (the total daily hours of their work_assignments rows, actor_id): the first, or None.
WORK-08 assign_cover(tx, actor_id, workplace_id, role, shift_start_hh, shift_end_hh, covering_for,
                     at, turn_index, cause_event_id) -> Event
  (cascade dispatch of ROLE_ASSIGNED — core CAS-002, whose payload carries the missed shift's
  hours, so a dead worker's deleted row is not needed.) An unknown workplace -> ValueError.
  ROLE_ASSIGNED {workplace_id, role, actor_id, covering_for, shift_start_hh, shift_end_hh,
  is_cover: true, left_workplace_id} (event actor_id = the cover) inserting work_assignments
  {workplace_id, actor_id, role, shift_start_hh, shift_end_hh, covering_for};
  left_workplace_id = the lowest workplace_id among the cover's own rows (covering_for NULL)
  before this insert, or null.
WORK-09 efficiency recovery (end of cycle): when efficiency < 1.0 and no worker with an own row
  (covering_for NULL) at this workplace has a covering row anywhere: WORKPLACE_CHANGE
  {workplace_id, field: 'efficiency', old, new, reason: 'recovering'} with new = min(1.0,
  round(old + R.efficiency_recovery, 2)).
WORK-10 adjust(tx, workplace_id, field, amount, at, turn_index, cause_event_id) -> Event | None
  (the cascade 'adjust' dispatch for a workplace id.) field 'efficiency': new = clamp(round(old +
  amount, 2), 0.0, 1.5); field 'machinery_condition': new = clamp(int(round(old + amount)), 0,
  100); any other field -> ValueError; unknown workplace -> ValueError. new == old -> None.
  WORKPLACE_CHANGE {workplace_id, field, old, new, reason: 'cascade'}.
WORK-11 shift_start(tx, actor_id, workplace_id, role, at, turn_index, cause_event_id) -> Event | None
  (society.routine calls it at a work step.) The actor able for the role -> SHIFT_START
  {workplace_id, role, actor_id} (event actor_id = the actor); else None.
WORK-12 ensure_timers(tx, settlement_id, at, turn_index) -> list[str]
  For each workplace of the settlement (by workplace_id) with a non-NULL next_due_at and no
  pending PRODUCTION_CYCLE row: kernel.clock.schedule(tx, max(next_due_at, at),
  'PRODUCTION_CYCLE', workplace_id, {'workplace_id': workplace_id}, None). Returns the queue ids.
Lots for settlement goods (provenance, theft, adulteration) are backlog, not v1 (DECISIONS D-49):
  settlement stores are counted units in settlements.stores, and P10's trade runs and raids move
  those counts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.rng import Rng
    from ..kernel.store import Store, Tx


def parse_key(key: str) -> tuple[str, str, str, int]:
    raise NotImplementedError("P9")


def qualified(store: "Store | Tx", actor_id: str, role: str) -> bool:
    raise NotImplementedError("P9")


def able(store: "Store | Tx", actor_id: str, role: str) -> tuple[bool, str]:
    raise NotImplementedError("P9")


def overlap_h(shift_start_hh: int, shift_end_hh: int, start_ms: int, end_ms: int) -> float:
    raise NotImplementedError("P9")


def shifts_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    raise NotImplementedError("P9")


def crew(store: "Store | Tx", workplace_id: str, start_ms: int, end_ms: int) -> list[tuple[str, str]]:
    raise NotImplementedError("P9")


def staffed_fraction(required_roles: list[str], crew_rows: list[tuple[str, str]]) -> float:
    raise NotImplementedError("P9")


def cycle(tx: "Tx", rng: "Rng", row: dict, fired: "Event", turn_index: int) -> list["Event"]:
    raise NotImplementedError("P9")


def miss_shift(tx: "Tx", key: str, reason: str, at: int, turn_index: int,
               cause_event_id: str | None) -> "Event | None":
    raise NotImplementedError("P9")


def pick_cover(store: "Store | Tx", workplace_id: str, role: str, shift_start_hh: int, shift_end_hh: int,
               exclude: str | None) -> str | None:
    raise NotImplementedError("P9")


def assign_cover(tx: "Tx", actor_id: str, workplace_id: str, role: str, shift_start_hh: int, shift_end_hh: int,
                 covering_for: str, at: int, turn_index: int, cause_event_id: str | None) -> "Event":
    raise NotImplementedError("P9")


def adjust(tx: "Tx", workplace_id: str, field: str, amount: float, at: int, turn_index: int,
           cause_event_id: str | None) -> "Event | None":
    raise NotImplementedError("P9")


def shift_start(tx: "Tx", actor_id: str, workplace_id: str, role: str, at: int, turn_index: int,
                cause_event_id: str | None) -> "Event | None":
    raise NotImplementedError("P9")


def ensure_timers(tx: "Tx", settlement_id: str, at: int, turn_index: int) -> list[str]:
    raise NotImplementedError("P9")
from ._impl_society import parse_key, qualified, able, overlap_h, shifts_overlap, crew, staffed_fraction, cycle, miss_shift, pick_cover, assign_cover, work_adjust as adjust, shift_start, work_ensure as ensure_timers  # noqa
