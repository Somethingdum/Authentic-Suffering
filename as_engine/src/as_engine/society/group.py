"""Groups: tension, drift, animosity, loyalty, the group day (P9). Owner 'society.group' (groups,
group_members, group_standing, tension). Rules GRP-01..12, SOC-01..03. docs/as/06_WORLD.md §2.5.
Every function that returns an Event has committed it (writer 'society.group', at and turn_index
as given). R = RulesConfig().society, DAY = 86_400_000 ms. rng draws use stream 'society'.
Code never acts for a human-controlled body: the PC is never a drift pair, never a loyalty check,
never an animosity roll (SEL-06); what others feel TOWARD the PC changes through play.

members(store, group_id, living=True) -> list[str]: actor ids with a group_members row of status
  'member' or 'probation', sorted; living=True keeps the living.
leader_of(store, group_id) -> str | None: groups.leader_id when it is set and alive; else the living
  member with role 'leader' (lowest id); else None.
GRP-01 tension_of(store, a_id, b_id) -> int: tension.score of the row (a_id, b_id), 0 without one.
  Tension is directional: what a (an actor or a group) holds against b.
GRP-02 adjust_tension(tx, a_id, b_id, delta, cause_text, at, turn_index, cause_event_id) ->
  list[Event]. new = clamp(old + delta, 0, 100); new == old -> [] (nothing committed).
  TENSION_CHANGE {a_id, b_id, old, new, delta: new - old, cause: cause_text} (event actor_id =
  a_id when it has an actors row) writing tension UPSERT (a_id, b_id): score = new, boiling_point
  = the row's, or R.boiling_point for a new row, causes = (the old list + [cause_event_id])[-10:]
  (unchanged when cause_event_id is None).
  Crossing upward (old < boiling_point <= new): ESCALATION {a_id, b_id, form: 'verbal', score}
  (cause = the TENSION_CHANGE); then, when a_id is an actor and the other side is a living actor
  — b_id itself, or the group's leader_of when b_id is a group — and they differ:
  mind.mind.relate(tx, a_id, other, 'resentment', 1, the ESCALATION id, at, turn_index).
  Returns the events committed, in seq order.
GRP-03 contacts(store, actor_id, group_id) -> list[str]: living members of the group other than
  the actor who share a household with them (society.household), or have a work_assignments row
  at a workplace where the actor has one, or toward whom the actor's relationships row has trust
  >= 1 or affection >= 1. Sorted.
GRP-04 drift (SOC-02: relationships change with the PC nowhere near). pairs(store, group_id) ->
  list[tuple[str, str]]: every (a, b), a < b, where a and b are living members whose controller
  is not 'human' and b in contacts(a) or a in contacts(b); sorted. In day(), for each pair, for
  (x, y) in ((a, b), (b, a)), with rel = the (x, y) relationships row (all axes 0 when missing):
    rel.resentment >= 1 or rel.trust <= -1 (a sour tie):
      when resentment < 3: rng.chance(tx, 'society', f'friction:{x}:{y}', R.drift_friction) ->
      mind.mind.relate(x, y, 'resentment', 1, GD);
    otherwise:
      when trust < R.drift_cap: chance(f'bond:{x}:{y}', R.drift_bond) -> relate(x, y, 'trust', 1);
      then, when x and y share a household and affection < R.drift_cap:
      chance(f'home:{x}:{y}', R.drift_household) -> relate(x, y, 'affection', 1).
  A draw is made only when its axis can still move (the conditions above are checked first).
GRP-05 ration strain: when the settlement the group governs (settlements.group_id) has ration_level
  <= 2, for each pair and direction (x, y) whose relationships row (after drift) has resentment >=
  1: adjust_tension(x, y, R.ration_strain_tension, 'short rations', GD).
GRP-06 decay: every tension row with score > 0 whose a_id is the group or one of its living
  members, and which no TENSION_CHANGE with delta > 0 touched in the last day (at - DAY < e.at <=
  at), in (a_id, b_id) order: adjust_tension(a, b, -R.tension_decay_per_day, 'time', GD).
GRP-07 defection_pressure(store, actor_id, group_id) -> Pressure(value, terms)
  terms (ints, this order): grievance = tension_of(actor, group) // 20; deprivation = 2 when the
  governed settlement's ration_level <= 1, 1 when <= 2, else 0; dependents = 1 when the actor has
  dependents (society.household.dependents_of) and ration_level <= 2, else 0; endangered = 2 when
  any dependent's needs.thirst_stage or hunger_stage >= 3, else 0; viability = 2 when the
  settlement's morale <= 1, 1 when <= 3, else 0; leader = 1 when the actor's resentment toward
  leader_of(group) >= 2, else 0; standing = 1 when the actor's group_members.standing <= -1, else
  0. Without a governed settlement the settlement terms are 0. value = min(10, sum of terms).
  [SALVAGE: Loyalty_Score + Betrayal_Threshold, split — Rebuild Plan §6.6]
GRP-08 loyalty_check(tx, actor_id, group_id, reason, at, turn_index, cause_event_id) -> list[Event]
  (the group benefit check; core CAS-006 schedules one at a ration cut, day() runs the rest.)
  A dead body, a body without an actors row, or a human-controlled actor -> [] (the player
  decides for the PC). threshold = the fused dossier's motive.risk_threshold; p =
  defection_pressure. result = 'plans_to_leave' when p.value >= threshold, 'wavering' when
  p.value >= threshold - 1, else 'stays'. LOYALTY_CHECK {actor_id, group_id, pressure: p.value,
  threshold, terms: p.terms, result, reason} (event actor_id = the actor). 'plans_to_leave'
  then opens a plan the actor holds: mind.mind.open_loop(tx, actor, 'plan', f"Leave {groups.name}
  before it is too late.", [], 2, the LOYALTY_CHECK id, at, turn_index) (LOOP-02 keeps one).
  Crossing the threshold starts PLANNING, never an instant betrayal; leaving is P10 (world.worldmove
  defection).
GRP-09 animosity(tx, rng, actor_ids, workplace_id, at, turn_index, cause_event_id) -> float
  (society.work.cycle calls it for a shift's crew: working beside someone you resent costs.)
  spite = 1.0. For each pair a < b of the distinct ids (sorted), for (x, y) in ((a, b), (b, a))
  whose relationships row has resentment >= 2 and whose x is not human-controlled:
  r = action.checks.roll(tx, rng, x, 'animosity', CheckSpec(attribute='I'), situation =
  clamp(actors.resolve_cur - 3, -3, 3), resistance = resentment, at=at, turn_index=turn_index,
  cause_event_id=cause_event_id). Band 'fail' -> spite *= 0.9 and adjust_tension(x, y, 10,
  'forced to work together', ...); 'break' -> spite *= 0.75 and adjust_tension(x, y, 20, ...).
  Returns round(spite, 2).
GRP-10 day(tx, rng, row, fired, turn_index) -> list[Event]   (the GROUP_DAY handler, daily at
  R.group_hour). g = row['subject_id'], at = row['due_at']. GD = GROUP_DAY {group_id, members:
  living members, pairs: len(pairs)} (cause = fired) writing groups.next_due_at = at + DAY. Then,
  each with cause GD: drift (GRP-04), ration strain (GRP-05), decay (GRP-06),
  world.rumours.spread_day(tx, g, at, turn_index, GD), and loyalty checks — for each living member
  (sorted) who is not human-controlled, whose age band is teen, adult or elder, whose
  defection_pressure is >= threshold - 1, and who has no LOYALTY_CHECK event for this group in
  (at - R.loyalty_recheck_days * DAY, at]: loyalty_check(..., reason 'daily'). Finally
  kernel.clock.schedule(tx, at + DAY, 'GROUP_DAY', g, {'group_id': g}, GD). Returns every event
  committed, in seq order.
GRP-11 Standing — the world's memory of you — lives in group_standing (this owner's table); the
  functions are mind.mind.standing_toward / adjust_group_standing (they build their events with
  writer 'society.group').
GRP-12 ensure_timers(tx, group_id, at, turn_index) -> list[str]: no pending GROUP_DAY row for the
  group -> kernel.clock.schedule(tx, society.settlement.next_hour(at, R.group_hour), 'GROUP_DAY',
  group_id, {'group_id': group_id}, None). Returns the new queue ids.
Leadership challenges, splintering and coalitions would ride on the same tension and pressure
numbers; they are backlog, not v1 (DECISIONS D-49). P10 brings leaving a group (world.worldmove,
DEFECTION).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.rng import Rng
    from ..kernel.store import Store, Tx


@dataclass(frozen=True)
class Pressure:
    value: int
    terms: dict[str, int]


def members(store: "Store | Tx", group_id: str, living: bool = True) -> list[str]:
    raise NotImplementedError("P9")


def leader_of(store: "Store | Tx", group_id: str) -> str | None:
    raise NotImplementedError("P9")


def tension_of(store: "Store | Tx", a_id: str, b_id: str) -> int:
    raise NotImplementedError("P9")


def adjust_tension(tx: "Tx", a_id: str, b_id: str, delta: int, cause_text: str, at: int, turn_index: int,
                   cause_event_id: str | None) -> list["Event"]:
    raise NotImplementedError("P9")


def contacts(store: "Store | Tx", actor_id: str, group_id: str) -> list[str]:
    raise NotImplementedError("P9")


def pairs(store: "Store | Tx", group_id: str) -> list[tuple[str, str]]:
    raise NotImplementedError("P9")


def defection_pressure(store: "Store | Tx", actor_id: str, group_id: str) -> Pressure:
    raise NotImplementedError("P9")


def loyalty_check(tx: "Tx", actor_id: str, group_id: str, reason: str, at: int, turn_index: int,
                  cause_event_id: str | None) -> list["Event"]:
    raise NotImplementedError("P9")


def animosity(tx: "Tx", rng: "Rng", actor_ids: list[str], workplace_id: str, at: int, turn_index: int,
              cause_event_id: str | None) -> float:
    raise NotImplementedError("P9")


def day(tx: "Tx", rng: "Rng", row: dict, fired: "Event", turn_index: int) -> list["Event"]:
    raise NotImplementedError("P9")


def ensure_timers(tx: "Tx", group_id: str, at: int, turn_index: int) -> list[str]:
    raise NotImplementedError("P9")
from ._impl_society import g_members as members, leader_of, tension_of, adjust_tension, contacts, pairs, defection_pressure, loyalty_check, animosity, group_day as day, group_ensure as ensure_timers  # noqa
