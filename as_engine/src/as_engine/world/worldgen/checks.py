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
  release audit re-runs assert_world on the genesis snapshot instead; DECISIONS D-45).
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
from ._impl_wg import assert_world  # noqa
