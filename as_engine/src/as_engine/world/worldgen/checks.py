"""WG9 — does the world hold together? (P10). Rules WG-35..37, WORLD-01, DEMO-01. docs/as/06_WORLD.md
§1.3. Pure reads; the pipeline aborts on any failure (every invariant below is made true by
construction in an earlier stage, so a failure means a stage was built wrong — never a flow).

WG-35 assert_world(store, region, plan, opening) -> list[str]   (plain sentences; [] = it holds)
  1 "Fewer than three places worth the risk." unless len(opening.magnets) >= 3 and the PC holds a
    live, believed 'lead' proposition on each.
  2 "No settlement is short of anything." unless some settlement has society.settlement.days_of <
    7 for 'food' or 'water', and the PC holds a live, believed 'shortage' proposition on a site.
  3 "Nothing dangerous is near the start." unless opening.threat_ids is not empty and every threat
    body is alive and stands in a place of physical.space.places_near(the PC's place, 2) or the PC's
    place itself.
  4 "Nothing warns of the danger." unless the telegraph trace exists in the PC's place.
  5 "The start zone has only one way out." unless the start zone has two edge-disjoint paths to
    some other zone over the routes rows (as region.assert_region reads them).
  6 f"{name} has no history." for every planned settlement and group that no history_events row
    names in subject_ids (WORLD-01).
  7 f"{settlement name}: {issue}" for every society.population.demographic_issues sentence of every
    settlement (DEMO-01).
  8 "The world fails its own checks: <bit names>." unless audit.commit_gate.compute(store, 0).passed.
WG-36 The seven world checks name nothing from the story: which people will betray, die or befriend
  the player is never decided here or anywhere in worldgen (WG-30).
WG-37 The continuous re-assertion of these invariants every in-game day is not built in v1 (P11's
  release audit re-runs assert_world on the run's turn-0 snapshot instead; DECISIONS D-45, D-95:
  not the world's genesis, which is taken before the PC is placed, so the opening checks 1-4 could
  not run on it).
reassert(store) -> list[str]   (P11, WG-37)
  WG-35 again, on a store that holds a generated world: skeleton = world_params.commit_json's
  'skeleton' (contracts.worldgen.WorldgenCommit.skeleton); no world_params row, or no skeleton ->
  ["There is no generated world here to check."]. Otherwise region = Region(zones, routes,
  start_zone_id, exterior=exterior) with each Zone / Route rebuilt from its dict (lists become
  tuples), plan = PolityPlan(groups, settlements) likewise, opening = Opening(**skeleton opening,
  opening = the commit's OpeningPressure) -> assert_world(store, region, plan, opening).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...kernel.store import Store, Tx
    from .history import PolityPlan
    from .opening import Opening
    from .region import Region


def assert_world(store: "Store | Tx", region: "Region", plan: "PolityPlan", opening: "Opening") -> list[str]:
    raise NotImplementedError("P10")


def reassert(store: "Store | Tx") -> list[str]:
    import json

    from ...contracts.worldgen import OpeningPressure
    from .history import PlannedGroup, PlannedSettlement, PolityPlan
    from .opening import Opening
    from .region import Region, Route, Zone
    row = store.query_one("SELECT commit_json FROM world_params WHERE id=1")
    wc = json.loads(row[0]) if row is not None else {}
    sk = wc.get("skeleton")
    if not sk:
        return ["There is no generated world here to check."]

    def zone(d):
        return Zone(**{**d, "site_ids": tuple(d["site_ids"])})
    region = Region(zones=tuple(zone(z) for z in sk["zones"]), routes=tuple(Route(**r) for r in sk["routes"]),
                    start_zone_id=sk["start_zone_id"], exterior=tuple(zone(z) for z in sk["exterior"]))
    plan = PolityPlan(groups=tuple(PlannedGroup(**g) for g in sk["groups"]),
                      settlements=tuple(PlannedSettlement(**x) for x in sk["settlements"]))
    opening = Opening(**sk["opening"], opening=OpeningPressure.model_validate(wc["opening"]))
    return assert_world(store, region, plan, opening)
from ._impl_wg import assert_world  # noqa
