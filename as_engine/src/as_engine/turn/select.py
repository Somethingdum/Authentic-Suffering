"""Who takes part in a wave, who must think, and how long the turn runs (P7, stage 4 and the
horizon). Rules SEL-01..07, HOR-01..04, SKULL-10, TEMPER-06. docs/as/04_TURN_PIPELINE.md §3.1, §3.4.
Pure reads (nothing here commits an event). May read any table: selection is scheduling, not a
mind, so the Skull law does not apply here — but nothing here is ever shown to a mind.

Constants: MANDATORY_CUES = ('weapon_pointed', 'infected_close', 'grabbed_from_behind',
'addressed_by_name', 'dependent_in_danger'); LOUD_DB = 80; LOUD_MEMORY_MS = 10 min (P10);
MAX_WINDOW_MS = 8 h; MIN_WINDOW_MS = 3000; REACT_MARGIN_MS = 3000.

SEL-01 active_area(tx, pc_id, turn_index) -> list[str]   (sorted place ids)
  The PC's place, every place within 2 portal hops of it (physical.space.places_near(place, 2):
  walls and fences count as hops), and — for every NOISE event of this turn (events.turn_index ==
  turn_index, in seq order) whose payload.source_db >= LOUD_DB, whose payload has a place_id and
  (P10) whose at is no earlier than kernel.clock.now(tx) - LOUD_MEMORY_MS — that place and every
  place 1 hop from it (a loud crash makes its neighbourhood part of the moment: the gust at the
  alley fence brings in the lot behind it; a roar days ago in the off-screen step, where the turn
  does not change, does not).

SEL-01 candidates(tx, pc_id, turn_index, horizon_ms) -> list[str]   (sorted actor ids)
  Every actor (actors JOIN bodies, alive = 1) except the PC whose position is in the active area,
  plus every living actor elsewhere whose actors.next_due_at is not NULL and <= horizon_ms (these
  run COLD unless selected). Awareness is not filtered here (a sleeper may be woken by what it
  perceives).
SEL-06 The PC is never a candidate, never planned and never reacts: the player decides for the PC
  (the pipeline passes exclude={pc} to action.reactions.next_wave).

SEL-07 (Actor v2 B6, fidelity C08: wake distant recipients by causal reach) reached(tx, events,
  turn_index) -> list[str]   (sorted actor ids)
  The active area is where the moment is; a sound goes as far as it goes. For each NOISE or SPEECH
  event of ``events`` with a payload.source_db, in seq order: sense.acoustics.receptions(tx,
  source_db, sense.acoustics.source_point(tx, payload, event.actor_id), event.at, the run's
  acoustic rules, exclude = {event.actor_id}) — each listener whose fidelity is not NONE, or who
  wakes — keeping those with an actors row (people, not the dead or the infected), each once.
  A sound with no source point reaches nobody. Only what a sound reaches is looked at: nobody
  thinks for the whole city. The pipeline perceives each wave's events for these people too
  (turn.pipeline S11), so a gunshot three streets away reaches the people who hear it, and
  action.reactions decides whether they react.

SEL-05 conscious(tx, actor_id) -> bool
  bodies.alive = 1 and awareness in ('awake', 'drowsy'). Only conscious candidates are planned,
  offered options, or asked to decide.

SEL-02 mandatory(tx, actor_id, turn_index, at, horizon_ms, pc_intent, forced=frozenset()) -> bool
  True when ANY of (a mandatory mind always gets a model call, even past the budget):
    * actor_id in ``forced`` (a pending reaction resolved at stage 0 of this turn);
    * mind.cues.cues_of(tx, actor_id, turn_index, at) meets MANDATORY_CUES;
    * a trigger of one of its plans.standing_orders is among those cues (a guard told to answer
      'loud_noise' hears a loud noise);
    * it is gripped (physical.bodies.grips_on(tx, actor_id) is non-empty);
    * it has a tactile percept this turn up to ``at`` (it was touched or hurt; SKULL-10);
    * its first active task (tasks with status 'active', ordered (started_at, task_id)) ends by the
      horizon: started_at + steps_total x round(step_s x 1000) <= horizon_ms;
    * pc_intent is given and pc_intent.bound.target_id == actor_id (the PC acts on it);
    * (H1) it snapped this wave: an INVOLUNTARY event with actor_id = actor_id, payload kind
      'outburst' and at == ``at`` (mind.temper TEMPER-05) — the person decides what they say.
  The pipeline passes pc_intent and ``forced`` at wave 0 only (a reaction wave passes None and an
  empty set: its minds are there because what they perceived was material, and the reaction
  budget of lanes.scheduler.plan_cognition decides who thinks with a model).

SEL-03 salience_flags(tx, actor_id, cands, pc_id, turn_index, at) -> dict[str, bool]
  ``cands`` = the conscious candidates of this wave. Over this turn's percept rows up to the
  wave (percept_log, turn_index == turn_index and at <= ``at`` — SKULL-10 —, ordered (at,
  percept_id)); "held" percepts are those at EXACT or PARTIAL:
    unique_info       the actor holds a percept of an event (event_id not 'scene:…') no other
                      candidate holds, OR holds a standing-view percept ('scene:…') of a body
                      (source id 'act_…') other than itself, the PC and the candidates that no
                      other candidate holds one of — Nita alone sees the man in the lot. Only
                      held (EXACT / PARTIAL) percepts count; items and silhouettes do not;
    loudest_percept   its loudest received_db (percept detail, auditory and speech channels, at
                      ANY fidelity: a sound too faint to make out is still loud; 0 when none) is
                      > 0 and >= every other candidate's;
    addressed         a speech percept with detail.addressed_to_me at EXACT or PARTIAL;
    in_conflict       its cues include threat_seen or weapon_pointed, or it has a tactile percept;
    interrupt_trigger a cue present is a trigger of its standing orders or in its first active
                      task's interrupt_on;
    open_loop_with_pc it has an 'open' loop whose subject_ids contain pc_id;
    dependent_present a body it is guardian_of (household_members.guardian_of) is in its place;
    visible_to_pc     the PC holds a visual percept of it this turn (up to ``at``) at EXACT or
                      PARTIAL;
    grievance_near    (H1) another living body in its place toward which mind.temper.heat(tx, actor,
                      it, at) >= max(1, mind.temper.threshold(tx, actor) // 2), or about which it has
                      an open 'grudge' loop (subject_ids) — someone it can hardly stand is right there.
SEL-04 salience(flags, is_mandatory, weights) -> float
  sum(weights[flag] for true flags) + weights['mandatory'] when mandatory (SchedulerRules
  .salience_weights). lanes.scheduler.plan_cognition orders by it (ties by actor id).

HOR-01 horizon(tx, pc_intent, t0) -> int   (the end of the simulation window, ms)
  The PC's def is looked up in canon (tx.canon.find('affordance', def_id)).
  condition-ended (duration.condition_ended: watch, wait, guard…): the earliest of t0 +
    MAX_WINDOW_MS, the earliest pending event_queue.due_at > t0, and the earliest actors.next_due_at
    > t0 — "keep watching" runs to the next scheduled thing (task steps do not count: a colleague's
    counting is not news) — and never less than t0 + MIN_WINDOW_MS. P9: queue rows whose type is in
    kernel.clock.BACKGROUND_QUEUE_TYPES (shifts, draws, routines, group days, delayed
    consequences) do not count either: a settlement's daily life is not news. What they cause can
    still end the window through a material percept (HOR-02).
  otherwise: max(t0 + MIN_WINDOW_MS, action.effects.land_ms(t0, pc_intent.bound.est_duration_s)).
HOR-02..04 pull(horizon_ms, trigger_at, last_event_at) -> int
  min(horizon_ms, max(trigger_at + REACT_MARGIN_MS, last_event_at)). When the PC holds a MATERIAL
  percept (action.reactions.material_holders) at trigger_at, the window closes REACT_MARGIN_MS after
  it so the player can answer (HOR-02) — but never before an event already committed this turn
  (HOR-03: G04 must hold), and a pull never lengthens the window (HOR-04). The pipeline applies
  it at wave 0 (to the PC's material percepts from stage 0's timers) and after every wave and
  every timer fired inside the window.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..action.intent import Intent
    from ..contracts.events import Event
    from ..kernel.store import Tx

MANDATORY_CUES: tuple[str, ...] = ("weapon_pointed", "infected_close", "grabbed_from_behind", "addressed_by_name",
                                   "dependent_in_danger")
LOUD_DB = 80
LOUD_MEMORY_MS = 10 * 60 * 1000
MAX_WINDOW_MS = 8 * 3600 * 1000
MIN_WINDOW_MS = 3000
REACT_MARGIN_MS = 3000


def active_area(tx: "Tx", pc_id: str, turn_index: int) -> list[str]:
    raise NotImplementedError("P7")


def candidates(tx: "Tx", pc_id: str, turn_index: int, horizon_ms: int) -> list[str]:
    raise NotImplementedError("P7")


def conscious(tx: "Tx", actor_id: str) -> bool:
    raise NotImplementedError("P7")


def mandatory(tx: "Tx", actor_id: str, turn_index: int, at: int, horizon_ms: int, pc_intent: "Intent | None",
              forced: frozenset[str] | set[str] = frozenset()) -> bool:
    raise NotImplementedError("P7")


def salience_flags(tx: "Tx", actor_id: str, cands: list[str], pc_id: str, turn_index: int, at: int) -> dict[str, bool]:
    raise NotImplementedError("P7")


def salience(flags: dict[str, bool], is_mandatory: bool, weights: dict[str, Any]) -> float:
    raise NotImplementedError("P7")


def horizon(tx: "Tx", pc_intent: "Intent", t0: int) -> int:
    raise NotImplementedError("P7")


def pull(horizon_ms: int, trigger_at: int, last_event_at: int) -> int:
    raise NotImplementedError("P7")


def reached(tx: "Tx", events: list["Event"], turn_index: int) -> list[str]:
    raise NotImplementedError("P7")
from ._impl_select import *  # noqa
from ._impl_select import _row  # noqa
