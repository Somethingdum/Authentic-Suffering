"""Routines (P9). Owner 'society.routine' (routines). Rules ROUT-01..07, DEMO-02. docs/as/06_WORLD.md
§2.3. The COLD life of a settlement — who sleeps, works and plays where, hour by hour. Routines run
on ROUTINE_STEP timers (kernel.clock.QUEUE_TYPES) dispatched by turn.timers. Every function that
returns an Event has committed it. R = RulesConfig().society.

ROUT-01 Who has a routine: a living body with an actors row whose controller is NOT 'human' (code
  never acts for a human-controlled body — SEL-06) and who is a named member of a settlement
  (society.population.census; the settlement with the lowest id when several). Everyone else has
  none: steps_for returns [].
ROUT-02 steps_for(store, actor_id) -> list[Step]   (derived fresh on every call; never cached)
  Step(start_hh, end_hh, activity, place_id, workplace_id=None, role=None) covers the hours
  [start_hh, end_hh) of every day; end_hh <= start_hh means the window crosses midnight (18 -> 6
  is 18:00-06:00); a single step for the whole day is (0, 0). The 24 hours are filled in order:
  1 work: the actor's work_assignments rows (their own and any cover), in (shift_start_hh,
    workplace_id, role) order; each takes the still-free hours of its shift: activity 'work',
    place = workplaces.place_id, workplace_id, role.
  2 sleep: the window starts at R.child_sleep[0] and ends at R.child_sleep[1] for bands infant and
    child; else, when hour 0 is taken by a work row, it starts at that row's shift_end_hh and lasts
    R.sleep_h hours; else R.adult_sleep. The sleep step is the run of FREE hours from the window's
    start up to its end or the first taken hour, whichever comes first; a run shorter than
    R.min_sleep_h hours is dropped (a double shift leaves no sleep). Place = the dwelling: the
    households.dwelling_place of society.household.household_of(actor), else the settlement's
    place.
  3 every hour still free: activity 'play' for bands infant, child and preteen, else 'free';
    place = the dwelling for infants, else the settlement's place (settlements.place_id).
  Consecutive hours with the same (activity, place_id, workplace_id, role) form one step, also
  across midnight. Returned sorted by start_hh.
ROUT-03 step_for(store, actor_id, hour) -> Step | None: the step whose window contains ``hour``
  (0..23); None without a routine.
ROUT-04 next_boundary(store, actor_id, after_ms) -> int | None: the smallest t > after_ms whose
  minute and second are 0 and whose hour is the start_hh of one of the actor's steps. None without
  a routine.
ROUT-05 COLD option (action.intent.plan_continuation step 5): OPTION_FOR = {'sleep': 'sleep',
  'work': 'observe_area'}; 'free' and 'play' have none (the step is skipped).
ROUT-06 step(tx, rng, row, fired, turn_index) -> list[Event]   (the ROUTINE_STEP handler)
  actor = row['subject_id'], at = row['due_at'], cause = fired.event_id. The outcome:
    'ended'   steps_for is empty (dead, left the settlement, now human-controlled); reason 'dead'
              when the body is dead, else 'no routine';
    'skipped' reason 'unable' when awareness is 'unconscious' or bodies.restrained = 1; reason
              'busy' when the actor has an active tasks row or a pending ACTION_LAND row
              (kernel.clock.pending_for) — a routine yields to what someone is doing; (P10)
              reason 'away' when the actor is a participant of an operation whose status is
              'active' (world.worldmove) — nobody is walked home from a job by their timetable;
    otherwise st = step_for(hour of at) — except that a 'work' step whose worker is not able for
    the role (society.work.able) is spent as a 'free' step at the settlement's place (reason
    'cannot work'; an injured pump hand does not stand in the pump house) — and, in this order,
    each with the cause above:
      1 waking: st.activity != 'sleep' and awareness 'asleep' or 'drowsy' -> physical.bodies.wake,
        physical.bodies.refresh_need(..., 'fatigue', ...) (a night's sleep), then physical.bodies.
        posture_event(..., 'standing', ...);
      2 moving: when the body's place differs from st.place_id — unless st.activity is 'sleep'
        and the body is asleep (a sleeper is not carried) — and physical.bodies.capacity is
        mobile: commit physical.space.move_event(tx, actor, st.place_id, None, width_m / 2,
        depth_m / 2, at, cause, turn_index) (the place's centre) -> 'moved' (P10: then
        world.worldmove.on_arrival(tx, rng, actor, st.place_id, at, the MOVE id, turn_index)); it had to move and
        cannot -> 'stayed' with reason 'cannot walk'; no move needed -> 'stayed'; the reason is ''
        unless said otherwise;
      3 sleeping: st.activity == 'sleep' and awareness in (alert, awake, drowsy) ->
        physical.bodies.posture_event(..., 'lying', ..., awareness='asleep');
      4 working: st.activity == 'work' -> society.work.shift_start(tx, actor, st.workplace_id,
        st.role, at, turn_index, cause).
  Then RS = ROUTINE_STEP {actor_id, activity, place_id, step_start_hh, outcome, reason} (writer
  'society.routine', event actor_id = the actor; activity / place_id / step_start_hh null unless
  a step was taken) writing routines UPSERT keyed by the actor's routine_id (minted kind 'rtn'
  when the actor has no routines row yet): {routine_id, actor_id, steps: the steps as dicts in
  order, next_due_at: next_boundary(at), NULL for 'ended'}; for 'ended' with no routines row
  nothing is written. Finally, unless 'ended': kernel.clock.schedule(tx, next_boundary(at),
  'ROUTINE_STEP', actor, {'actor_id': actor}, RS). Returns every event committed, in seq order.
ROUT-07 ensure_timers(tx, settlement_id, at, turn_index) -> list[str]
  For each named member of the settlement (sorted) with a routine and no pending ROUTINE_STEP row
  (kernel.clock.pending_for): kernel.clock.schedule(tx, next_boundary(at), 'ROUTINE_STEP',
  actor, {'actor_id': actor}, None). Returns the new queue ids in order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.rng import Rng
    from ..kernel.store import Store, Tx

OPTION_FOR: dict[str, str] = {"sleep": "sleep", "work": "observe_area"}


@dataclass(frozen=True)
class Step:
    start_hh: int
    end_hh: int
    activity: str          # work | sleep | free | play
    place_id: str
    workplace_id: str | None = None
    role: str | None = None


def steps_for(store: "Store | Tx", actor_id: str) -> list[Step]:
    raise NotImplementedError("P9")


def step_for(store: "Store | Tx", actor_id: str, hour: int) -> Step | None:
    raise NotImplementedError("P9")


def next_boundary(store: "Store | Tx", actor_id: str, after_ms: int) -> int | None:
    raise NotImplementedError("P9")


def step(tx: "Tx", rng: "Rng", row: dict, fired: "Event", turn_index: int) -> list["Event"]:
    raise NotImplementedError("P9")


def ensure_timers(tx: "Tx", settlement_id: str, at: int, turn_index: int) -> list[str]:
    raise NotImplementedError("P9")
from ._impl_society import steps_for, step_for, next_boundary, routine_step as step, routine_ensure as ensure_timers  # noqa
