"""Cascade table (Stage 10, P5/P9). Rules CAS-01..04. Secondary consequences are a DECLARATIVE
rule table from content (CascadeRuleDef), applied by code. Every cascade event MUST set
``rule_cited`` to the rule id (G10). The optional CASCADE_ADVISORY model call (lane B, parallel)
proposes rules the table missed; its output is written to as_runs/<run>/reports/cascade_debt.jsonl
and NEVER committed (CAS-03).

sweep(tx, deltas, rules, at, turn_index) -> list[Event]
  For each committed event in order, for each rule whose trigger_event == event.type and whose
  `where` equality filters match the payload and whose preconditions evaluate true, apply the
  effects (emit/schedule/adjust/create_trace/create_rumour/drain_resolve/adjust_stress/
  recover_resolve). Cascades may trigger
  further cascades up to depth 3 (CAS-02); depth is carried in payload '_cascade_depth'.

CAS-05 target selectors (CascadeEffect.target). '<path>' is any precondition path (trigger.payload.<key>,
  trigger.actor_id, trigger.event_id, and — D-119 — trigger.killer, trigger.killer_provoked). Each
  selector returns 0..n entity ids, deterministically ordered by id; the effect is applied once per id:
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
    body(<path>)                              (D-123) the body itself (none when there is no such body)
    onlookers_of_act(<path>)                  (D-133) the holders of a visual EXACT or PARTIAL percept of
                                              the event, never its actor or the PC (what the player's
                                              character feels is theirs, C06)
    onlookers_bonded_to_target(<path>)        (D-133) of onlookers_of_act, those bonded to the event's
                                              payload target_id (affection >= 1 toward it, or one
                                              household)
    robbed_by(<path>)                         (D-129) for an ITEM_TRANSFER: of theft_witnesses_of, those
                                              whose believed owner of the item is themselves or one of
                                              their households (and not the taker's own, as there) —
                                              never the PC
    bonded_onlookers_of(<path>)               (D-129) for a HARM with trigger.attacker: of
                                              assault_onlookers_of, for a DEATH with trigger.killer: of
                                              onlookers_of — those bonded to the one hurt or killed
                                              (affection >= 1 toward them, or one household)
    humiliated_by(<path>)                     (D-129) for a SPEECH: the holders of an EXACT or PARTIAL
                                              speech percept of it addressed to them whose words hold an
                                              entry of mind.temper.INSULT_WORDS (whole words), when
                                              someone else besides the speaker heard it too (an
                                              audience), and no RESOLVE_CHANGE of theirs with reason
                                              'humiliated_publicly' in the hour up to it; never the
                                              speaker or the PC
    made_to_watch(<path>)                     (D-129) for a HARM or DEATH: the holders of a visual EXACT
                                              or PARTIAL percept of it who are held (bodies.restrained)
                                              and bonded to the one hurt (as above), never that body or
                                              the one who did it, with no RESOLVE_CHANGE of theirs with
                                              reason 'made_to_watch' in the hour up to it
    hurt_by_someone(<path>)                   (D-126) for a HARM one person did to another
                                              (trigger.attacker present): the one hurt — never the
                                              player's character (what they feel is theirs, C06)
    assault_onlookers_of(<path>)              (D-126) for such a HARM: the holders of a visual EXACT or
                                              PARTIAL percept of it who also saw who did it (as
                                              onlookers_of), never the attacker, the one hurt or the PC
    threatened_by(<path>)                     (D-126) for a SPEECH: the holders of a speech percept of
                                              it addressed to them with the weapon on them (detail
                                              addressed_to_me and armed_at_me) whose words, as heard, are
                                              a threat in themselves (mind.firewall.classify_form without
                                              the weapon: "or I'll", "I'll kill you" — an armed "Quiet."
                                              is not one); never the speaker or the PC
    protecting_today(<path>)                  (D-139) for an ACTION_START of a def tagged
                                              'protect_dependent' (shield_dependent: offered only under a
                                              threat, at someone the actor guards, lives with or loves):
                                              its actor, alive, when no RESOLVE_CHANGE of theirs with
                                              reason 'protected_dependent' falls in the 24 h up to it
                                              (once a day, however often they do it)
    left_bleeding_by(<path>)                  (D-142) for a MOVE out of a place (payload from_place set and
                                              not to_place) by someone with an actors row: those still in
                                              from_place (positions, as the sweep runs) who hold a visual
                                              EXACT or PARTIAL percept of it, are bonded to the one leaving
                                              (affection >= 1 toward them, or one household) and have an
                                              unhealed, unclotted severe or catastrophic wound; never the
                                              PC, and not twice in an hour (no grudge of theirs naming the
                                              one leaving whose text says they 'left you bleeding', made in
                                              the hour up to it by another event)
    kin_group_of(<path>)                      (D-144) for a DEATH with trigger.killer: the groups the dead
                                              and the killer both belonged to (group_members rows; the
                                              dead's any status but 'departed' or 'expelled', the killer's
                                              'member' or 'probation'), sorted — one of their own killed
                                              one of their own
    kin_onlookers_of(<path>)                  (D-144) of onlookers_of, the living members ('member' or
                                              'probation') of the first kin_group_of group; never the
                                              killer, the dead or the PC
    left_in_danger_by(<path>)                 (D-148) for a MOVE out of a place (as left_bleeding_by) by
                                              someone with an actors row, while that place is dangerous
                                              (an infected body there, alive; or a HARM there in the 60 s
                                              up to it): those still in from_place who saw it go and whom
                                              the one leaving is guardian_of (household_members
                                              .guardian_of); never the PC, not twice in an hour (no grudge
                                              of theirs naming the one leaving whose text says they 'left
                                              you behind', made in the hour up to it by another event)
    saw_child_left_by(<path>)                 (D-148) for such a MOVE with someone left_in_danger_by it:
                                              the others still in from_place who saw it go — never the one
                                              leaving, one left, or the PC
    attacked_by_someone(<path>)               (D-161) for an ACTION_COMPLETE of an attack that hurt
                                              nobody (trigger.missed_attacker present): the one it was
                                              made on — never the PC (C06)
    attack_onlookers_of(<path>)               (D-161) for such an ACTION_COMPLETE: the holders of a
                                              visual EXACT or PARTIAL percept of its ACTION_START (the
                                              weapon raised, the swing), never the attacker, the one it
                                              was made on, or the PC
    loved_ones_threatened(<path>)             (D-138) for a SPEECH: the holders of a speech or visual
                                              EXACT or PARTIAL percept of it bonded (affection >= 1, or
                                              one household) to someone it threatened at weapon point
                                              (as threatened_by, the PC counted among those threatened);
                                              never the speaker, one threatened, or the PC
    settlements_seeing(<path>)                (D-124) the settlements (society.settlement.settlement_of)
                                              of the holders of a visual EXACT or PARTIAL percept of that
                                              event, never counting the event's own body (payload body_id)
    seen_clearly_by(<path>)                   (D-123) the holders of a visual EXACT or PARTIAL percept
                                              of that event (they saw who it was) — never the event's
                                              own body (payload body_id)
    onlookers_of(<path>)                      (D-119) for a killing (trigger.killer present): the holders
                                              of a visual EXACT or PARTIAL percept of that event or of
                                              the killing blow (they saw who fell) who also saw who did
                                              it — a visual EXACT or PARTIAL percept whose source is the
                                              killer, from 10 s before the blow to the trigger, or
                                              sense.optics.visibility of the killer at the blow's time
                                              'clear' or 'partial'. Never the killer, the dead or the
                                              player's character (what they feel about it is the
                                              player's, C06). A figure going down in the dark names
                                              nobody. No killer: []
    groups_that_saw(<path>)                   (D-119) for a killing: the groups the dead was a 'member'
                                              or 'probation' member of that have one of
                                              onlookers_of(<path>) as a 'member' or 'probation' member —
                                              what none of them saw costs no standing
    theft_witnesses_of(<path>)                (B6, AFF-11: whether a taking is theft is for those who
                                              see it and what they know) for an ITEM_TRANSFER into its
                                              actor's own hands or carry (payload.to is a body holder
                                              whose id is the event's actor): the holders other than
                                              the actor of an EXACT or PARTIAL percept of it (they saw
                                              who took it) who believe the item belongs to someone
                                              else — a live believed holding (believed 1, superseded_by
                                              NULL) of a proposition with subject ('object',
                                              payload.item_id) and predicate 'owner' whose
                                              object_value is not the actor, a household it belongs to
                                              or a group it has a group_members row in, as
                                              mind.affordance reads 'owned'. Any other event -> none
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
                                             — (D-124) with p.where_in_force true, a settlement that does
                                             not have that law in force is skipped (no event, no warning)
  emit_event TENSION_CHANGE                  society.group.adjust_tension(tx, target, p.toward, p.delta,
                                             p.cause, at, turn_index, E)
  emit_event LOYALTY_CHECK                   society.group.loyalty_check(tx, target, p.group, p.reason, ...)
  emit_event AWARENESS_CHANGE                (D-146) physical.bodies.wake(tx, target, at, E, turn_index): an
                                             asleep or drowsy body wakes (anyone else: nothing) — a
                                             scheduled one is a night broken, and does nothing when the
                                             body has woken since E (an AWARENESS_CHANGE or
                                             POSTURE_CHANGE of it with awareness 'awake' after E: that
                                             sleep is over)
  emit_event STANDING_CHANGE                 (D-119) mind.mind.adjust_group_standing(tx, target (a group id),
                                             p.toward, int(p.delta), E, at, turn_index)
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
                                             turn_index, E, confidence = p.confidence or 3, seen =
                                             bool(p.seen) — D-162: true for a rule whose targets saw
                                             it happen, an eyewitness's own account)                    (P9)
  drain_resolve                              mind.resolve.drain(target, reason = payload.cause or
                                             'coerced', ...) for a target that is a living actor (anyone
                                             else: no-op). (D-123) payload.scale_by — the subject is
                                             trigger.payload.body_id, else about_id, else subject_id:
                                             'bond_to_subject': a guardian of the subject (its
                                             household_members.guardian_of) is drained 'lost_dependent'
                                             instead; otherwise only a target bonded to the subject
                                             (affection >= 1 toward them, or one household) is drained,
                                             with the given cause; 'dependent_of_subject': only a guardian,
                                             'lost_dependent'. Either way a loss is grieved once: no drain
                                             when the target already has a RESOLVE_CHANGE of reason
                                             witness_bonded_death or lost_dependent whose cause event's
                                             payload body_id or about_id is the subject, nor for the
                                             subject itself
  recover_resolve                            (D-122) mind.resolve.recover(tx, target, payload.cause,
                                             E, at, turn_index) for a target that is a living actor
                                             (anyone else: no-op)
  adjust_stress                              (H1) mind.actor.adjust_stress(tx, target, int(effect.amount)
                                             + bond, E, at, turn_index) — bond = 0, or with payload.scale_by
                                             'bond_to_subject' the target's affection toward
                                             trigger.payload.body_id when it is >= 1 (max 3); a target that
                                             is not an actor (no actors row: the dead, the infected) or the
                                             subject itself -> no-op
  A dispatch whose owner function raises NotImplementedError (its phase is not built yet) is
  recorded with audit.log.record(tx, 'G10-cascade', 'action.cascade', 'warn', [{kind:
  'cascade_unbuilt', rule_id, what: event_type or kind}], turn_index) and skipped, so an
  earlier phase runs with the full content table; the P11 audit fails a release build that still
  records any such row.
CAS-05 selectors built by phase: P5 actor, place_of, witnesses_of, active_task_of,
  infected_within_hearing_of; P9 household_of, settlement_of, workplace_of, work_assignments_of,
  cover_candidate_for, heads_of_households_with_dependents, head_of_worst_hit_household,
  leadership_of, group_of, who_would_hear_of, theft_witnesses_of (B6). An unbuilt selector counts
  as unbuilt dispatch.
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
    (D-119, a killing) trigger.killer — for a DEATH from wounds (payload cause blood_loss, head_wound,
    neck_wound or harm): the actor of the killing blow — its cause event when that is a HARM to the
    dead body, else the latest HARM (at <= the death) whose wound_id is a wound still open on the dead
    body; the blow's actor must have an actors row and not be the dead; otherwise missing (hunger, the
    cold, infection, an infected's bite never have a killer) — and trigger.killer_provoked — true
    when, in the 10 minutes up to the blow, the dead was fighting a person (any actor but the dead,
    so defending someone else counts): a HARM by the dead to them, an ACTION_START by the dead with
    verb 'attack' at them, or an armed SPEECH by the dead (payload armed true) to them or to
    'everyone'; false otherwise; missing when there is no killer; (D-123) trigger.killer_first —
    true when no DEATH committed before this one has the same trigger.killer, false otherwise,
    missing when there is no killer; body(<path>).<column> — a bodies column (age_years, kind, ...),
    (D-126) trigger.attacker — for a HARM: its actor (payload actor_id, else the event's), when that and
    the one hurt both have actors rows and differ, and (D-132) the one hurt was not already dead when it
    landed (bodies.dead_at earlier than the HARM: the dead put down — head, or fire, as everyone must,
    lore cold_start — is no one hurt); otherwise missing — (D-134) trigger.victim_held — for a HARM: the one
    hurt was held when it landed; for a DEATH someone caused: when the killing blow landed (grips
    taken on it up to then — CONTROL_ESTABLISH — outnumber those let go, or it is restrained now and
    alive); otherwise missing — (D-135) trigger.victim_yielded — for a HARM: the one hurt had given up
    when it landed — in the 10 minutes up to it their latest surrender (an ACTION_START with payload
    verb 'surrender' or a GESTURE 'empty_hands', by them) with no ACTION_START with payload verb
    'attack' by them after it (one in the same instant counts after: a feint is no surrender); for a
    DEATH someone caused: when the killing blow landed; otherwise missing — and trigger.attacker_provoked —
    true when the one hurt was fighting a person in the 10 minutes up to it (as killer_provoked),
    (D-161) trigger.missed_attacker, trigger.missed_provoked, trigger.missed_lethal — for an
    ACTION_COMPLETE whose cause is an ACTION_START of an affordance whose verb is 'attack', by someone
    with an actors row on a human body, at someone else with an actors row on a human body alive when
    it started, that put no HARM on them (no HARM of that body caused by the start): the attacker;
    whether the one it was made on was fighting a person in the 10 minutes up to the start (as
    attacker_provoked); whether the def is tagged 'lethal' (a shot, a blade) — a miss, a dry click,
    a grab that slips is still an attack; otherwise missing.
    settlement_of(<path>).<column or derived column>, workplace_of(<path>).<column>.
    Literals: integers, floats, true/false, quoted strings. A missing payload key makes the
    comparison false (never an exception)."""
    raise NotImplementedError("P5")
from ._impl_p5b import sweep, select, evaluate_precondition  # noqa
from ._impl_p5b import fire_scheduled  # noqa
