"""WG3, WG4, WG5, WG7 — the groups, the settlements and their work, the people counted but not yet
named, and the laws (P10). Rules WG-22..25, DEMO-01, DEMO-02, CONSERVE-04. docs/as/06_WORLD.md §1.3,
§2. Code only; rng stream 'worldgen:polity'. Every event: origin 'worldgen', turn_index 0, at =
``at``, one MATERIALIZE per row group written by the table's owner (payload {<id>: id, source:
'worldgen'}), row shapes as testing/scenario.py "Row details". values = params.flat_values(params);
dsf = params.days_since_fall; round(x) = params.rnd(x) = floor(x + 0.5) everywhere in worldgen.

WG-22 write_groups(tx, plan, params, canon, at) -> list[Event]   (WG3)
  Per planned group (plan order) a MATERIALIZE (writer 'society.group') inserting groups {group_id,
  kind, name, content_ref, descriptor, presence, doctrine = the faction record's doctrine
  (model_dump, JSON) or '{}', cohesion = clamp(5 + (social_order - 5) // 2, 0, 10), morale 5,
  leader_id NULL, next_due_at NULL}. Then one MATERIALIZE (society.group, payload {tension: n})
  inserting a tension row for every ordered pair (a, b), a != b, whose score = clamp((6 -
  faction_relations) x 10, 0, 100) + 30 when either is hostile (capped at 100) is above 0:
  {a_id, b_id, score, boiling_point = SocietyRules.boiling_point, causes []}.

WG-23 write_settlements(rng, tx, plan, params, region, at) -> list[Event]   (WG4)
  Per planned settlement s (plan order), P = s.population:
    stores: water = round(3 x P x (3 + water)), food = round(2 x P x (3 + food)) (days of need x
      daily need, the need being 3 x P water and 2 x P food); the HOME settlement
      (history.home_settlement(plan, region.start_zone_id)) is the region's bottleneck: its scarcer
      store (water when water <= food, else food) holds round(daily need x (2 + rng.range_int(0, 3,
      purpose f"bottleneck:{s}"))) instead (2-5 days of the flat need: under 7 days of the real one
      whatever the cohorts turn out to be, WG9 check 2); medicine = meds x 2; fuel = fuel x 5; ammunition = ammo x 10.
    MATERIALIZE (society.settlement) inserting settlements {settlement_id, name, place_id = s.site_id,
      group_id, stores (keys sorted), morale 5, cohesion = the group's cohesion, defences =
      clamp(social_order // 2 + 1, 0, 10), sanitation = clamp(tech_preservation // 2, 0, 10), power =
      1 when tech_baseline >= 6 else 0, ration_level 3, shortages [], vacancies [], next_due_at NULL}.
    Workplaces, in this order, each its own MATERIALIZE (society.work): water_pump, kitchen, watch
      always; clinic when meds >= 4; garden when the settlement's zone kind is 'rural' or
      'riverside'. From atlas.WORKPLACE_PLANS[site]: cycle_h, the output resource and the first cycle
      hour h0; required_roles [] (named labour only at the home settlement: WG6 sets the roles of
      the posts it staffs, and a workplace nobody staffs runs on its unnamed people). place_id = s.site_id, settlement_id, site_type, inputs {}, outputs:
      water_pump {water: ceil(P x 3 x (0.7 + 0.06 x water) x cycle_h / 24)}, kitchen {food: ceil(P x
      2 x (0.7 + 0.06 x food) x cycle_h / 24)}, garden {food: ceil(P x 0.3)}, else {};
      machinery_condition = min(100, 40 + 5 x tech_preservation); efficiency 1.0; stall_reasons [];
      next_due_at = the first t > at with t = day start + h0 + k x cycle_h hours (k >= 0, same day
      or later).
  (Work assignments are written with the people, WG6.)

WG-24 write_cohorts(rng, tx, plan, params, at) -> list[Event]   (WG5, DEMO-01/02)
  Per planned settlement (plan order), P = its population; shares young 0.20, youth 0.14, elders
  0.11, each + rng.range_int(-3, 3, purpose f"share:{s}:{band group}") / 100 (young, youth, elders
  in that order); counts: young = round(P x young), youth = round(P x youth), elders = round(P x
  elders), each clamped to [ceil(P x lo), floor(P x hi)] of its SocietyRules.pyramid bounds (so a
  small settlement stays inside DEMO-01), adults = P - the rest; infant = young x 2 // 5, child = young - infant; preteen = youth //
  2, teen = youth - preteen; adult = adults; elder = elders. Every band's count splits female =
  count // 2 + (count % 2 when rng.chance(0.5, purpose f"sex:{s}:{band}")), male = the rest.
  cohort_kind from the band's typical age (infant 1, child 7, preteen 13, teen 17, adult 35, elder
  68): age at the Fall = typical - dsf / 365; < 0 'post_fall_born', < 18 'fall_child', else
  'pre_fall_adult'. One MATERIALIZE (writer 'society.population', payload {settlement_id, cohorts:
  n}) inserting a cohorts row {cohort_id, settlement_id, zone_id = its zone, age_band, sex,
  cohort_kind, count, archetype NULL} for every (band in AgeBand order, sex female then male) with
  count > 0. Each hostile group gets zone cohorts the same way but adults only: count =
  rng.range_int(6, 12, purpose f"band:{g}"), settlement_id NULL, zone_id = its home zone, archetype =
  the group id (the band's own people).
  The named people of WG6 are materialised FROM these cohorts (society.population.materialise), so
  the headcount is conserved (CONSERVE-04, L11).

WG-25 write_laws(tx, plan, params, canon, at) -> list[Event]   (WG7)
  Per settlement one MATERIALIZE (writer 'society.settlement', payload {settlement_id, laws: n})
  inserting laws_active {settlement_id, law_ref, since = at} for the sorted set of:
  'core:law/ration_law' and 'core:law/theft_law' always; for a faction's settlement every ref in the
  faction record's laws that resolves in canon; for a procedural group's settlement
  'core:law/nightfall_curfew' when hostile_human >= 6, 'core:law/firearms_discipline' when
  social_order >= 6, 'core:law/intake_screening' and 'core:law/contamination_quarantine' when
  zombie_common >= 6.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...contracts.events import Event
    from ...contracts.worldgen import WorldParams
    from ...kernel.rng import Rng
    from ...kernel.store import Tx
    from .history import PolityPlan
    from .region import Region


def write_groups(tx: "Tx", plan: "PolityPlan", params: "WorldParams", canon, at: int) -> list["Event"]:
    raise NotImplementedError("P10")


def write_settlements(rng: "Rng", tx: "Tx", plan: "PolityPlan", params: "WorldParams", region: "Region",
                      at: int) -> list["Event"]:
    raise NotImplementedError("P10")


def write_cohorts(rng: "Rng", tx: "Tx", plan: "PolityPlan", params: "WorldParams", at: int) -> list["Event"]:
    raise NotImplementedError("P10")


def write_laws(tx: "Tx", plan: "PolityPlan", params: "WorldParams", canon, at: int) -> list["Event"]:
    raise NotImplementedError("P10")
