"""Population and demographics (P9). Owner 'society.population' (cohorts). Rules DEMO-01..04,
CONSERVE-04. docs/as/06_WORLD.md §2.1. R = the store's RulesConfig().society (SocietyRules).

A settlement's people are its NAMED members plus its UNNAMED people:
  named   = every living body with an actors row that has a group_members row with status
            'member' or 'probation' in the settlement's governing group (settlements.group_id);
            the PC is counted like anyone (L12);
  unnamed = the cohorts rows whose settlement_id is the settlement (counts, not bodies).

DEMO-04 census(store, settlement_id) -> Census
  Census(settlement_id, named: tuple of actor ids sorted, by_band: dict AgeBand value -> int with
  EVERY AgeBand value as a key (named + unnamed), unnamed: int (sum of cohort counts), total: int
  (len(named) + unnamed)). A named person's band is bodies.age_band; a cohort's band is
  cohorts.age_band. A settlement without a group has no named members. Unknown settlement ->
  ValueError.
DEMO-01 demographic_issues(census, rules) -> list[str]
  [] when census.total <= R.demo_min_population (15). Otherwise the bands are grouped
  young = infant + child, youth = preteen + teen, adults = adult, elders = elder, and each
  group's share = count / total must lie inside R.pyramid[group] (inclusive bounds). One plain
  sentence per group outside its bounds, in the order young, youth, adults, elders:
      f"Too {'few' or 'many'} {word}: {count} of {total} ({pct}%), expected {lo}-{hi}%."
  word: young 'children', youth 'young people', adults 'adults', elders 'elders'; pct =
  int(share * 100 + 0.5); lo / hi = int(bound * 100 + 0.5). 'few' when below the lower bound.
DEMO-02 Children are inhabitants: they get routines like everyone (society.routine: play in the
  daylight hours, sleep at night — never a day of only 'sleep'), so they are seen in ordinary,
  non-threat contexts.
DEMO-03 A settlement of only military-age adults must cite a reason. demographic_issues does not
  know reasons; worldgen (P10) records the history event that excuses the issue.
consumption(census, rules) -> dict[str, float]
  The settlement's daily need at the normal ration (level 3): {'food': sum over bands of
  by_band[band] * R.food_per_day[band], 'water': sum of by_band[band] * R.water_per_day[band]}
  (floats, not rounded; keys in that order).
CONSERVE-04 adjust_cohort(tx, cohort_id, delta, reason, at, turn_index, cause_event_id) -> Event
  Commits POPULATION_CHANGE {cohort_id, settlement_id, delta, count_before, count_after, reason}
  (writer 'society.population', cause as given) writing cohorts.count. delta == 0, an unknown
  cohort, or count_after < 0 -> ValueError (nobody is subtracted who is not there).
P10 — naming the unnamed (L11, CONSERVE-04):
take_from_cohort(tx, settlement_id, zone_id, band, sex, at, turn_index, cause_event_id, *,
                 archetype=None) -> Event | None
  The cohort with that settlement_id (or, when settlement_id is None, that zone_id and archetype),
  age_band and sex whose count > 0 (lowest cohort_id) -> adjust_cohort(tx, it, -1, 'materialised',
  ...). None when there is no such cohort left (nothing changes).
materialise(tx, rng, *, settlement_id, zone_id, band, sex, dossier, place_id, at, turn_index,
            cause_event_id, archetype=None, event_origin='sim') -> str
  One unnamed person becomes a named one: ev = take_from_cohort(...) — no cohort left -> ValueError
  (nobody is made who is not there); then, each caused by ev: physical.bodies.create(kind 'human',
  sex, age_years = dossier identity age, height_cm / mass_kg / special from the dossier, origin
  'worldgen' when event_origin is 'worldgen' else 'materialize'; looks = the dossier's
  appearance.looks when it has them, LOOK-01), physical.space.place_body at
  ``place_id``'s first anchor by anchor_id (its point; without one, the place centre (width_m / 2,
  depth_m / 2) and no anchor), (F1a-2, LOOK-10) each piece of the looks' outfit, in order, as
  physical.objects.dress makes it but with item origin 'worldgen' (what they wore was already in
  the world, only unnamed) and event origin ``event_origin`` — nobody steps out of the count naked —,
  mind.actor.create(source 'generated', mind_kind 'model',
  event_origin) and a known_places row {first_seen = last_seen = at, visited 1} for that place
  (one PERCEIVE {holder_id, seed: true}, writer 'mind.perception', actor_id = the new body).
  Returns the new actor id.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..contracts.settings import SocietyRules
    from ..kernel.store import Store, Tx


@dataclass(frozen=True)
class Census:
    settlement_id: str
    named: tuple[str, ...]
    by_band: dict[str, int]
    unnamed: int
    total: int


def take_from_cohort(tx: "Tx", settlement_id: str | None, zone_id: str | None, band: str, sex: str, at: int,
                     turn_index: int, cause_event_id: str | None, *, archetype: str | None = None):
    raise NotImplementedError("P10")


def materialise(tx: "Tx", rng, *, settlement_id: str | None, zone_id: str | None, band: str, sex: str, dossier: dict,
                place_id: str, at: int, turn_index: int, cause_event_id: str | None, archetype: str | None = None,
                event_origin: str = "sim") -> str:
    raise NotImplementedError("P10")


def census(store: "Store | Tx", settlement_id: str) -> Census:
    raise NotImplementedError("P9")


def demographic_issues(c: Census, rules: "SocietyRules") -> list[str]:
    raise NotImplementedError("P9")


def consumption(c: Census, rules: "SocietyRules") -> dict[str, float]:
    raise NotImplementedError("P9")


def adjust_cohort(tx: "Tx", cohort_id: str, delta: int, reason: str, at: int, turn_index: int,
                  cause_event_id: str | None) -> "Event":
    raise NotImplementedError("P9")
from ._impl_society import census, demographic_issues, consumption, adjust_cohort  # noqa
from ..world._impl_p10 import take_from_cohort, materialise  # noqa
