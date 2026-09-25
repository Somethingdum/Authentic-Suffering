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
  8b (H1) friction(tx, rng, s, at, turn_index, SD) — STL-15.
  9 kernel.clock.schedule(tx, at + DAY, 'SETTLEMENT_DAY', s, {'settlement_id': s}, SD).
  Returns every event committed, in seq order.
STL-15 (H1) friction(tx, rng, settlement_id, at, turn_index, cause_event_id) -> list[Event]: people
  who live on top of each other, short of everything, fight. The pairs: the settlement's named
  members (group_members of settlements.group_id with status 'member' or 'probation', alive, never
  the PC), each unordered pair (a, b) with a < b, where either has resentment >= 2 toward the other
  (relationships) or an open 'grudge' loop naming the other. For each pair in (a, b) order: m =
  the higher actors.stress of the two; p = min(1, R.quarrel_base + R.quarrel_per_stress x m);
  rng.chance(tx, 'society', f"quarrel:{a}:{b}:{day}", p) (day = at // 86 400 000) -> a quarrel.
  The instigator is the one with the higher stress (ties: a); brawl = rng.chance(tx, 'society',
  f"brawl:{a}:{b}:{day}", R.brawl_chance x (1.0 when the instigator's temper outlet is 'fists',
  else 0.25)). Q = QUARREL {settlement_id, a, b, instigator_id, brawl} (writer 'society.settlement',
  actor_id = the instigator, cause SD); then, each with cause Q: mind.temper.provoke(tx, x, y,
  'quarreled', Q, ...) both ways (a toward b first); when brawl, for each of the two (a first)
  physical.bodies.apply_harm(tx, who, WoundSpec(rng.weighted('society', f"bruise:{who}:{day}",
  CENTRE_MASS), 'blunt', 'minor', 0), at, Q, turn_index, rng) and mind.mind.adjust_group_standing(tx,
  the settlement's group, who, -1, Q, at, turn_index); world.rumours.seed(tx, each id of the
  cascade selector who_would_hear_of(the instigator) (action.cascade CAS-05), the instigator,
  'lost_it' when brawl else 'fell_out', at, turn_index, Q) — people talk. Returns every event
  committed, in seq order.

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


def friction(tx: "Tx", rng: "Rng", settlement_id: str, at: int, turn_index: int,
             cause_event_id: str | None) -> list["Event"]:
    import json as _j
    from ..action.cascade import select as _select
    from ..action.effects import CENTRE_MASS
    from ..contracts.events import Event as _Ev, EventType
    from ..mind import mind as _mind, temper as _temper
    from ..physical.bodies import WoundSpec, apply_harm
    from ..world import rumours
    R = tx.rules.society
    first = tx.query_one("SELECT COALESCE(MAX(seq),0) FROM events")[0]
    g = tx.query_one("SELECT group_id, place_id FROM settlements WHERE settlement_id=?", (settlement_id,))
    if g is None or not g[0]:
        return []
    gid = g[0]
    pc = tx.query_one("SELECT value FROM meta WHERE key='pc_actor_id'")
    pc = pc[0] if pc else None
    mem = sorted(r[0] for r in tx.query("SELECT gm.actor_id FROM group_members gm JOIN bodies b ON b.body_id=gm.actor_id "
                                        "WHERE gm.group_id=? AND gm.status IN ('member','probation') AND b.alive=1", (gid,))
                 if r[0] != pc)

    def sore(x, y):
        r = tx.query_one("SELECT resentment FROM relationships WHERE from_id=? AND to_id=?", (x, y))
        if r and r[0] >= 2:
            return True
        return any(y in _j.loads(q[0]) for q in tx.query("SELECT subject_ids FROM open_loops WHERE holder_id=? AND kind='grudge' "
                                                          "AND status='open'", (x,)))

    def stress(x):
        r = tx.query_one("SELECT stress FROM actors WHERE actor_id=?", (x,))
        return r[0] if r else 0

    day = at // 86_400_000
    for i, a in enumerate(mem):
        for b in mem[i + 1:]:
            if not (sore(a, b) or sore(b, a)):
                continue
            sa, sb = stress(a), stress(b)
            p = min(1.0, R.quarrel_base + R.quarrel_per_stress * max(sa, sb))
            if not rng.chance(tx, "society", f"quarrel:{a}:{b}:{day}", p):
                continue
            inst = b if sb > sa else a
            mult = 1.0 if _temper.temper_of(tx, inst).outlet == "fists" else 0.25
            brawl = bool(rng.chance(tx, "society", f"brawl:{a}:{b}:{day}", R.brawl_chance * mult))
            q = tx.commit_event(_Ev(type=EventType.QUARREL, writer="society.settlement", at=at, turn_index=turn_index,
                                    actor_id=inst, cause_event_id=cause_event_id,
                                    payload={"settlement_id": settlement_id, "a": a, "b": b, "instigator_id": inst,
                                             "brawl": brawl}))
            _temper.provoke(tx, a, b, "quarreled", q.event_id, at, turn_index)
            _temper.provoke(tx, b, a, "quarreled", q.event_id, at, turn_index)
            if brawl:
                for who in (a, b):
                    anat = rng.weighted(tx, "society", f"bruise:{who}:{day}", list(CENTRE_MASS))
                    apply_harm(tx, who, WoundSpec(anat, "blunt", "minor", 0), at, q.event_id, turn_index, rng)
                    _mind.adjust_group_standing(tx, gid, who, -1, q.event_id, at, turn_index)
            for h in _select(tx, "who_would_hear_of(trigger.payload.instigator_id)", q):
                rumours.seed(tx, h, inst, "lost_it" if brawl else "fell_out", at, turn_index, q.event_id)
    from ._impl_society import _since
    return _since(tx, first)
from ._impl_society import daily_need, days_of, has_shortage, receive, settlement_day as day, declare_shortage, change_ration, stl_adjust as adjust, add_vacancy, remove_vacancy, laws_of, law_def, apply_law, settlement_of, trade_terms, settlement_ensure as ensure_timers  # noqa
from ._impl_society import set_lockdown  # noqa
