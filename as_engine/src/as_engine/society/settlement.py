"""Settlements (P9). Owner 'society.settlement' (settlements, laws_active). Rules STL-01..12, ECON-01,
SOC-03. docs/as/06_WORLD.md §2.4. Every function that returns an Event has committed it (writer
'society.settlement', at and turn_index as given, place_id = settlements.place_id).
R = RulesConfig().society. RESOURCES = ('food', 'water') are the rationed stores.

STL-01 daily_need(store, settlement_id) -> dict[str, float]: society.population.consumption(
  census, R) with every value multiplied by R.ration_mult[ration_level].
  days_of(store, settlement_id, resource) -> float: stores[resource] (0 when absent) /
  daily_need[resource]; a need of 0 (or a resource with no need) -> float('inf').
  has_shortage(store, settlement_id, resource) -> bool: resource in settlements.shortages.
  (The cascade precondition paths settlement_of(...).days_of_<resource> and
  .has_shortage_<resource> read these two; every real settlements column is readable too.)
STL-02 receive(tx, settlement_id, changes, reason, at, turn_index, cause_event_id) -> Event
  changes = {resource: amount} (amount may be negative). STORES_CHANGE {settlement_id, changes,
  after, reason}: each new value = round(max(0, old + amount), 2) (a draw larger than the store
  takes what is there), written as an integer when it is whole; ``changes`` in the payload holds
  the amounts actually applied (new - old, same rounding), ``after`` the new values of the changed
  resources; keys sorted. Unknown settlement -> ValueError.
STL-03 day(tx, rng, row, fired, turn_index) -> list[Event]   (the SETTLEMENT_DAY handler, daily
  at R.draw_hour). s = row['subject_id'], at = row['due_at']; everything below has cause = the
  SETTLEMENT_DAY event (SD) unless said otherwise.
  1 The draw. level = ration_level, mult = R.ration_mult[level]. People in priority order: the
    named members sorted by (band rank infant 0, child 1, preteen 2, teen 3, elder 4, adult 5;
    actor_id). For resource in ('water', 'food'): available = stores[resource]; for each named
    person, share = R.<resource>_per_day[band] * mult; covered when share <= available (then
    available -= share), else they go on short[resource] and the next person is tried. Then the
    unnamed people's share (sum over cohorts of count * rate[band] * mult) comes out of what is
    left, down to 0. drawn[resource] = stores[resource] - available.
    P10 (C01): unnamed_short[resource] = how many unnamed people that left without a whole
    share: serve them one person at a time, cohorts in (band rank, cohort_id) order, each share
    = R.<resource>_per_day[band] * mult out of what the named left; the first person whose
    share does not fit and everyone after them are short. At level 0 every unnamed person is
    short of both; at level 1, of food (as the named: they drink but go hungry).
  2 SD = SETTLEMENT_DAY {settlement_id, ration_level: level, drawn, short: {resource: [ids]},
    unnamed_short: {resource: n} (P10), min_days} writing settlements.next_due_at = at + DAY,
    where min_days = min over RESOURCES of (stores[resource] - drawn[resource]) /
    daily_need[resource] rounded to 2 (inf -> 999.0).
  2b P10 (C01) The unfed unnamed — after SD: for resource in ('water', 'food'): k =
    R.privation_days[resource]; when the newest k SETTLEMENT_DAY events of this settlement (SD
    included) all have unnamed_short[resource] > 0, n = the smallest of those k values: n people
    die of it, the last in line first — cohorts in reverse serving order (highest band rank, then
    highest cohort_id), each giving min(its count, the rest) — each through
    society.population.adjust_cohort(tx, cohort, -m, 'thirst' | 'hunger', at, turn_index, SD);
    their dead rise (world.hordes HRD-16, pathway 'cold_start', zone = the settlement site's
    zone, count = n, cause SD). (Named people die of the same thing through their own needs,
    physical.bodies.)
  3 receive(tx, s, {resource: -drawn}, 'consumption', ...) when anything was drawn.
  4 The fed: for each named person covered for water and level >= 1: physical.bodies.
    refresh_need(tx, p, 'thirst', at, SD, turn_index); covered for food and level >= 2:
    refresh_need(..., 'hunger', ...). (At level 1 people drink but go hungry; at level 0 neither.)
  5 Morale (SETTLEMENT_CHANGE, field 'morale', clamp 0..10): level <= 2 -> -1 (reason 'rations');
    else when there is no shortage and morale < R.morale_baseline -> +1 (reason 'recovering').
  6 Shortages end: for each resource in shortages (in list order) whose days_of after the draw is
    >= R.shortage_days: SHORTAGE_ENDED {settlement_id, resource, days} removing it (days rounded
    to 2; inf -> 999.0, as for min_days: a settlement with no one left to feed).
  7 Rations recover: level < 3, and the newest R.recovery_streak SETTLEMENT_DAY events of this
    settlement (this one included) all have min_days >= R.recovery_days, and no RATION_CHANGE
    event of this settlement is newer than the oldest of them -> change_ration(+1, 'recovered').
  8 society.household.day(tx, h, at, turn_index, SD) for each h in households_of(s).
  9 kernel.clock.schedule(tx, at + DAY, 'SETTLEMENT_DAY', s, {'settlement_id': s}, SD).
  Returns every event committed, in seq order.
STL-04 declare_shortage(tx, settlement_id, resource, at, turn_index, cause_event_id) -> Event | None
  (cascade dispatch of SHORTAGE — core CAS-004.) Already short of it -> None. Else SHORTAGE
  {settlement_id, resource, days: days_of rounded to 2 (inf -> 999.0)} appending resource to
  shortages.
STL-05 change_ration(tx, settlement_id, delta, reason, at, turn_index, cause_event_id) -> Event | None
  (cascade dispatch of RATION_CHANGE — core CAS-005.) new = clamp(level + delta, 0, 4); new ==
  level -> None. RATION_CHANGE {settlement_id, delta: new - level, level_before, level_after,
  cause: reason} writing ration_level. (Core CAS-006 fires on delta < 0 and level_after <= 2.)
STL-06 adjust(tx, settlement_id, field, amount, at, turn_index, cause_event_id, reason='cascade')
  -> Event | None: field in {'morale', 'cohesion', 'defences', 'sanitation', 'power'} (ValueError
  otherwise), new = clamp(old + int(amount), 0, 10); new == old -> None. SETTLEMENT_CHANGE
  {settlement_id, field, old, new, reason}.
STL-07 add_vacancy(tx, settlement_id, workplace_id, role, for_actor, at, turn_index, cause) ->
  Event | None / remove_vacancy(tx, settlement_id, workplace_id, role, for_actor, at, turn_index,
  cause) -> Event | None: vacancies is a JSON list of {workplace_id, role, for_actor, since} kept
  sorted by (workplace_id, role, for_actor); adding one that is there, or removing one that is
  not, -> None. SETTLEMENT_CHANGE {settlement_id, field: 'vacancies', old, new, reason: 'vacancy'
  | 'filled'} (old / new = the lists).
STL-08 laws_of(store, settlement_id) -> list[str]: the laws_active law_refs, sorted.
  law_def(store, settlement_id, law) -> LawDef | None: ``law`` is a ref ('core:law/ration_law') or
  a bare id ('ration_law'); the active law whose ref equals it or ends with '/' + it, looked up in
  the store's canon; None when the settlement does not have it.
STL-09 apply_law(tx, settlement_id, law, subject_id, at, turn_index, cause_event_id) -> Event | None
  (cascade dispatch of LAW_APPLIED — core CAS-015.) Not an active law of the settlement ->
  audit.log.record(tx, 'G10-cascade', 'society.settlement', 'warn', [{kind: 'law_not_active',
  law, settlement_id}], turn_index) and None. Else LAW_APPLIED {settlement_id, law_ref, kind,
  subject_id, punishment} (event actor_id = the subject); then, for a law whose kind is in
  PUNISHING ('curfew', 'weapons', 'ration', 'trade', 'theft', 'noise', 'visitors'):
  mind.mind.adjust_group_standing(tx, the settlement's group, subject_id, -1, the LAW_APPLIED id,
  at, turn_index). Protective laws (contamination, intake, quarantine, ...) change no standing.
STL-10 settlement_of(store, entity_id) -> str | None: an id of kind 'stl' -> itself when it exists;
  'wkp' -> workplaces.settlement_id; 'plc' -> the settlement whose place_id it is; 'hh' ->
  households.settlement_id, else the settlement of its lowest-id living member; 'act' -> the
  lowest settlement_id among settlements whose group has the actor as a 'member' or 'probation'
  group_members row. Anything else -> None.
STL-11 trade_terms(store, settlement_id, buyer_id) -> TradeTerms   (SOC-03: a rumour reaches trade)
  trader = the named member, not the buyer, whose controller is not 'human', with the highest
  fused-dossier 'trade' rank >= 1 (ties by id); none -> TradeTerms(False, 0.0, None, ['Nobody
  here trades.']). mult = 1.0, willing = True, reasons = [] (plain sentences, in this order):
    standing = mind.mind.standing_toward(store, group, buyer): <= -3 -> unwilling ("{G} will not
      deal with them."); -2 -> mult *= 1.5 and -1 -> mult *= 1.25 ("{G} thinks little of
      them."); >= 2 -> mult *= 0.9 ("{G} thinks well of them.");
    the trader's relationships row toward the buyer: resentment >= 2 -> unwilling ("{T} holds a
      grudge against them."); trust <= -2 -> mult *= 1.25 ("{T} does not trust them.");
    the trader's live (superseded_by NULL), believed claim_holdings on propositions with
      subject_type 'body', subject_id = buyer and predicate in THIEF_PREDICATES: the highest
      confidence >= 2 -> unwilling ("{T} believes they steal."); == 1 -> mult *= 1.5 ("{T} has
      heard they steal.").
  {G} = groups.name, {T} = mind.actor.display_name(trader). price_mult = round(mult, 2) when
  willing, else 0.0. TradeTerms(willing, price_mult, trader_id, reasons).
STL-12 ensure_timers(tx, settlement_id, at, turn_index) -> list[str]: no pending SETTLEMENT_DAY row
  for the settlement -> kernel.clock.schedule(tx, next_hour(at, R.draw_hour), 'SETTLEMENT_DAY',
  settlement_id, {'settlement_id': settlement_id}, None). next_hour(ms, hh) = the smallest t > ms
  with hour hh, minute 0, second 0. Returns the new queue ids.
STL-13 set_lockdown(tx, settlement_id, on, reason, at, turn_index, cause_event_id) -> Event | None
  (P10, world.factions FAC-01) new = 1 when on else 0; new == settlements.lockdown -> None. Else
  SETTLEMENT_CHANGE {settlement_id, field: 'lockdown', old, new, reason} writing it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.content import LawDef
    from ..contracts.events import Event
    from ..kernel.rng import Rng
    from ..kernel.store import Store, Tx

RESOURCES: tuple[str, ...] = ("food", "water")
PUNISHING: frozenset[str] = frozenset({"curfew", "weapons", "ration", "trade", "theft", "noise", "visitors"})
THIEF_PREDICATES: frozenset[str] = frozenset({"took_what_was_not_theirs", "thief"})
BAND_RANK: dict[str, int] = {"infant": 0, "child": 1, "preteen": 2, "teen": 3, "elder": 4, "adult": 5}


@dataclass(frozen=True)
class TradeTerms:
    willing: bool
    price_mult: float
    trader_id: str | None
    reasons: list[str] = field(default_factory=list)


def next_hour(ms: int, hh: int) -> int:
    """The smallest t > ms whose hour is hh and whose minute and second are 0 (implemented)."""
    day_ms, hour_ms = 86_400_000, 3_600_000
    t = (ms // day_ms) * day_ms + hh * hour_ms
    while t <= ms:
        t += day_ms
    return t


def daily_need(store: "Store | Tx", settlement_id: str) -> dict[str, float]:
    raise NotImplementedError("P9")


def days_of(store: "Store | Tx", settlement_id: str, resource: str) -> float:
    raise NotImplementedError("P9")


def has_shortage(store: "Store | Tx", settlement_id: str, resource: str) -> bool:
    raise NotImplementedError("P9")


def receive(tx: "Tx", settlement_id: str, changes: dict[str, float], reason: str, at: int, turn_index: int,
            cause_event_id: str | None) -> "Event":
    raise NotImplementedError("P9")


def day(tx: "Tx", rng: "Rng", row: dict, fired: "Event", turn_index: int) -> list["Event"]:
    raise NotImplementedError("P9")


def declare_shortage(tx: "Tx", settlement_id: str, resource: str, at: int, turn_index: int,
                     cause_event_id: str | None) -> "Event | None":
    raise NotImplementedError("P9")


def change_ration(tx: "Tx", settlement_id: str, delta: int, reason: str, at: int, turn_index: int,
                  cause_event_id: str | None) -> "Event | None":
    raise NotImplementedError("P9")


def adjust(tx: "Tx", settlement_id: str, field: str, amount: float, at: int, turn_index: int,
           cause_event_id: str | None, reason: str = "cascade") -> "Event | None":
    raise NotImplementedError("P9")


def add_vacancy(tx: "Tx", settlement_id: str, workplace_id: str, role: str, for_actor: str, at: int,
                turn_index: int, cause_event_id: str | None) -> "Event | None":
    raise NotImplementedError("P9")


def remove_vacancy(tx: "Tx", settlement_id: str, workplace_id: str, role: str, for_actor: str, at: int,
                   turn_index: int, cause_event_id: str | None) -> "Event | None":
    raise NotImplementedError("P9")


def laws_of(store: "Store | Tx", settlement_id: str) -> list[str]:
    raise NotImplementedError("P9")


def law_def(store: "Store | Tx", settlement_id: str, law: str) -> "LawDef | None":
    raise NotImplementedError("P9")


def apply_law(tx: "Tx", settlement_id: str, law: str, subject_id: str, at: int, turn_index: int,
              cause_event_id: str | None) -> "Event | None":
    raise NotImplementedError("P9")


def settlement_of(store: "Store | Tx", entity_id: str) -> str | None:
    raise NotImplementedError("P9")


def trade_terms(store: "Store | Tx", settlement_id: str, buyer_id: str) -> TradeTerms:
    raise NotImplementedError("P9")


def ensure_timers(tx: "Tx", settlement_id: str, at: int, turn_index: int) -> list[str]:
    raise NotImplementedError("P9")


def set_lockdown(tx: "Tx", settlement_id: str, on: bool, reason: str, at: int, turn_index: int,
                 cause_event_id: str | None) -> "Event | None":
    raise NotImplementedError("P10")
