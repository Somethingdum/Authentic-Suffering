"""Cascade table (Stage 10, P5/P9). Rules CAS-01..04. Secondary consequences are a DECLARATIVE
rule table from content (CascadeRuleDef), applied by code. Every cascade event MUST set
``rule_cited`` to the rule id (G10). The optional CASCADE_ADVISORY model call (lane B, parallel)
proposes rules the table missed; its output is written to as_runs/<run>/reports/cascade_debt.jsonl
and NEVER committed (CAS-03).

sweep(tx, deltas, rules, at, turn_index) -> list[Event]
  For each committed event in order, for each rule whose trigger_event == event.type and whose
  `where` equality filters match the payload and whose preconditions evaluate true, apply the
  effects (emit/schedule/adjust/create_trace/create_rumour/drain_resolve). Cascades may trigger
  further cascades up to depth 3 (CAS-02); depth is carried in payload '_cascade_depth'.

CAS-05 target selectors (CascadeEffect.target). '<path>' is any precondition path (trigger.payload.<key>,
  trigger.actor_id, trigger.event_id). Each selector returns 0..n entity ids, deterministically
  ordered by id; the effect is applied once per id:
    actor(<path>)                             the actor itself
    household_of(<path>)                      society.household.household_of(actor)
    settlement_of(<path>)                     society.settlement.settlement_of(id): an actor, place,
                                              workplace, household or settlement id
    workplace_of(<path>)                      the workplace itself, when it exists
    work_assignments_of(<path>)               every work_assignments row of the actor (its own and any
                                              cover), as society.work keys 'wkp:role:actor:start_hh'
    cover_candidate_for(<path>)               society.work.pick_cover(<path> = the workplace, role =
                                              trigger.payload.role, trigger.payload.shift_start_hh,
                                              trigger.payload.shift_end_hh, exclude =
                                              trigger.payload.actor_id) — none -> no-op (the missed
                                              shift already put the role on the vacancies, WORK-06)
    active_task_of(<path>)                    the actor's active task, if any
    heads_of_households_with_dependents(<p>)  for each h in society.household.households_of(<p> = a
                                              settlement) with has_dependents(h): head_of(h), when
                                              it exists and its controller is not 'human'
    head_of_worst_hit_household(<p>)          head_of(society.household.worst_hit(<p>)), when it
                                              exists and its controller is not 'human'
    leadership_of(<p>) / group_of(<p>)        the settlement's governing group id, settlements.group_id
                                              (the same group; two names for readability)
    infected_within_hearing_of(<p>)           infected bodies whose place receives the trigger NOISE above their hearing threshold
    witnesses_of(<path>)                      bodies with a PERCEIVE row for that event
    place_of(<path>)                          the body's current place
    who_would_hear_of(<path>)                 the living members of the body's households and of every
                                              group it belongs to (status member / probation), plus
                                              every living holder of an acquaintance row naming it
                                              with a known_name — never the body itself
  Payload values that are strings starting with '$' are resolved the same way ('$trigger.payload.x'
  resolves to the value; '$leadership_of(...)' to the first id). Unknown selector names are a
  content error at compile (CNT-04).
CAS-06 schedule_event, and any rule with delay_s > 0, enqueues a CASCADE_EFFECT queue row
  (kernel.clock.QUEUE_TYPES) instead of emitting now: kernel.clock.schedule(tx, due,
  'CASCADE_EFFECT', target, {rule_id, effect_index, target, trigger_event_id: E.event_id}, E),
  once per target id, inside the rule's citing block (so the TIMER_SET cites the rule). due:
  payload.due 'next_shift_start' -> society.settlement.next_hour(at, the targeted work
  assignment's shift_start_hh); else payload.due_s -> at + due_s * 1000; else at + delay_s * 1000.
  fire_scheduled(tx, rng, row, fired, turn_index) -> list[Event] (turn.timers dispatches the row,
  P9): rule = the canon cascade rule row.payload.rule_id, effect = rule.effects[effect_index], E =
  the trigger event (kernel.events.get); the effect is dispatched now as an emit_event of its
  event_type (a schedule_event IS a delayed emit) to row.payload.target, with its payload minus the
  keys 'due' and 'due_s' ('$' values resolved against E as usual), at = row.due_at, inside
  ``with tx.citing(rule.id, 0)``: cascade depth restarts at 0, and the owner's own validity checks
  still apply (society.work refuses a SHIFT_MISSED when the worker turns up able to work —
  audit_log, no event). A rule that no longer exists (content changed) -> audit.log.record(tx,
  'G10-cascade', 'action.cascade', 'warn', [{kind: 'cascade_rule_gone', rule_id}], turn_index)
  and []. Returns the events committed; the caller (turn.timers.fire_one) sweeps them.
CAS-07 an effect whose target resolves to no ids is a no-op, not an error; the rule still counts as
  fired for the decision audit.
Settlement derived columns usable in preconditions: days_of_<resource> = stores[resource] /
  daily consumption (06_WORLD.md §2.4), has_shortage_<resource> (bool) — in addition to real columns.

CAS-08 sweep order and bookkeeping. ``deltas`` are the events committed by stages 8–9 of this wave,
  in seq order. For each event E (then, depth-first, for each event a rule produced, up to depth
  3): for each rule in rule-id order with trigger_event == E.type, every ``where`` key equal to
  E.payload[key] (a missing key -> no match), and every precondition true: for each effect in
  order, resolve its target ids (CAS-05) and dispatch once per id. Every event a dispatch commits
  gets Event.rule_cited = the rule id (G10) and payload '_cascade_depth' = E's depth + 1: each
  dispatch runs inside ``with tx.citing(rule.id, depth + 1):`` (kernel.store.Tx.citing), so owner
  modules need no cascade parameters. A trigger E of depth 3 fires no rules (CAS-02). Returns
  every event committed, in seq order.
CAS-09 DISPATCH — kind (and event_type) -> the owning module's function (target = one id):
  emit_event TASK_STEP {status: paused}      action.tasks.interrupt(task_id = target)
  emit_event RELATION_CHANGE                 mind.mind.relate(from_id = target, to_id = payload.toward,
                                             axis = payload.axis, delta = payload.delta, cause = E)     (P6)
  emit_event LOOP_OPENED                     mind.mind.open_loop(holder = target, kind = payload.kind,
                                             text = payload.text, subject_ids = [payload.subject] or [],
                                             strength = payload.strength or 2, cause = E)               (P6)
                                             (E = the triggering event's id; '$trigger.…' payload values
                                             are resolved like targets, CAS-05)
  (P9; p = the effect payload with '$' values resolved, E = the trigger, at, turn_index as given)
  emit_event HOUSEHOLD_CHANGE                society.household.apply_change(tx, target, p.change,
                                             p.actor_id, at, turn_index, E, grief_delta=p.grief_delta or 0)
  emit_event SHIFT_MISSED                    society.work.miss_shift(tx, target (an assignment key),
                                             p.reason, at, turn_index, E)
  emit_event ROLE_ASSIGNED                   society.work.assign_cover(tx, target, p.workplace_id, p.role,
                                             p.shift_start_hh, p.shift_end_hh, p.covering_for, at,
                                             turn_index, E)
  emit_event SHORTAGE                        society.settlement.declare_shortage(tx, target, p.resource, ...)
  emit_event RATION_CHANGE                   society.settlement.change_ration(tx, target, p.delta, p.cause, ...)
  emit_event LAW_APPLIED                     society.settlement.apply_law(tx, target, p.law, p.subject, ...)
  emit_event TENSION_CHANGE                  society.group.adjust_tension(tx, target, p.toward, p.delta,
                                             p.cause, at, turn_index, E)
  emit_event LOYALTY_CHECK                   society.group.loyalty_check(tx, target, p.group, p.reason, ...)
  emit_event INFECTED_DRIFT                  world.infected.attract(tx, target, p.toward (a place or body
                                             id, '$'-resolved), at, E, turn_index, reason = p.reason or
                                             'noise')                                                   (P10)
  schedule_event / delay_s > 0               the CASCADE_EFFECT row of CAS-06
  adjust                                     by the target id's kind: 'wkp' -> society.work.adjust(tx,
                                             target, field, amount, ...); 'stl' -> society.settlement.
                                             adjust(tx, target, field, amount, ...); any other -> ValueError
  create_trace                               world.traces.create(tx, target (a place id), p.kind,
                                             p.text or TRACE_TEXT[p.kind], E, at, turn_index)         (P10)
                                             (TRACE_TEXT: the texts below, implemented)
  create_rumour                              world.rumours.seed(tx, target, p.about, p.claim, at,
                                             turn_index, E, confidence = p.confidence or 3)            (P9)
  drain_resolve                              mind.resolve.drain(target, reason = payload.cause or
                                             'coerced', ...) — payload.scale_by 'bond_to_subject' drains
                                             once per affection step >= 1 toward the dead (max 3)
  A dispatch whose owner function raises NotImplementedError (its phase is not built yet) is
  recorded with audit.log.record(tx, 'G10-cascade', 'action.cascade', 'warn', [{kind:
  'cascade_unbuilt', rule_id, what: event_type or kind}], turn_index) and skipped, so an
  earlier phase runs with the full content table; the P11 audit fails a release build that still
  records any such row.
CAS-05 selectors built by phase: P5 actor, place_of, witnesses_of, active_task_of,
  infected_within_hearing_of; P9 household_of, settlement_of, workplace_of, work_assignments_of,
  cover_candidate_for, heads_of_households_with_dependents, head_of_worst_hit_household,
  leadership_of, group_of, who_would_hear_of. An unbuilt selector counts as unbuilt dispatch.
  Precondition paths (P9): settlement_of(<path>).<column> reads a settlements column or the derived
  days_of_<resource> / has_shortage_<resource> (society.settlement.days_of / has_shortage);
  workplace_of(<path>).<column> reads a workplaces column.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.content import CascadeRuleDef
    from ..contracts.events import Event
    from ..kernel.store import Tx

# create_trace's default texts (P10; implemented data)
TRACE_TEXT: dict[str, str] = {
    "corpse": "A body lies here.", "blood": "Blood on the ground, still wet.", "tracks": "Footprints in the dust.",
    "damage": "Something here has been broken.",
}


# fire_scheduled (P9) stands above sweep (P5) so the kit's P9 patch merges over a built sweep.
def fire_scheduled(tx: "Tx", rng, row: dict, fired: "Event", turn_index: int) -> list["Event"]:
    """CAS-06 (P9): a CASCADE_EFFECT queue row comes due — dispatch its effect now (see above)."""
    raise NotImplementedError("P9")


def sweep(tx: "Tx", deltas: list["Event"], rules: list["CascadeRuleDef"], at: int,
          turn_index: int) -> list["Event"]:
    raise NotImplementedError("P5")


def select(tx: "Tx", selector: str, trigger: "Event") -> list[str]:
    """CAS-05: resolve one selector expression to entity ids (sorted)."""
    raise NotImplementedError("P5")


def evaluate_precondition(tx: "Tx", expr: str, trigger: "Event") -> bool:
    """Tiny expression language (docs/as/07_RULES.md §Cascade expressions):
    '<path> <op> <literal>' with op in == != >= <= > <, joined by ' and '. Paths:
    trigger.payload.<key>, trigger.actor_id, trigger.type, actor(<path>).<column>,
    settlement_of(<path>).<column or derived column>, workplace_of(<path>).<column>.
    Literals: integers, floats, true/false, quoted strings. A missing payload key makes the
    comparison false (never an exception)."""
    raise NotImplementedError("P5")
from ._impl_p5b import sweep, select, evaluate_precondition  # noqa
from ._impl_p5b import fire_scheduled  # noqa
