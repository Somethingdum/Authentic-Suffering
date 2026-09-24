"""WG1 — the region: zones, their streets and buildings, the roads between them, and the four ways
out (P10). Rules WG-15..17, GEO-00, GEO-03. docs/as/06_WORLD.md §1.3. Code only; rng stream
'worldgen:region'.
Tables: world/worldgen/atlas.py. T = tables.DETAIL_TIERS[detail].

build_region(rng, tx, params, detail, canon, at) -> Region
  Writes the region and returns what later stages need. Every event: origin 'worldgen', turn_index
  0, at = ``at``; writer 'physical.space' (it owns zones, places, anchors, portals, routes). Row
  shapes as testing/scenario.py "Row details" (places: layout_generated as below, held 0, props '{}';
  anchors capacity 4; portals is_open 1, is_locked 0, lock_quality 0, barricade 0, damage 0,
  open_loss_db 0, transparent 1, height_cm 0).
  1 Zone kinds (n = T['zones']): zone 0 — the start zone — rng.weighted(atlas.START_ZONE_WEIGHTS,
    purpose 'start_kind'); zones 1..n-1 rng.weighted(atlas.ZONE_WEIGHTS, purpose f"kind:{i}").
    A region holds at most ONE 'wilds' zone (it has no buildings; two would leave too few places
    worth the risk for the opening's leads, WG-35 1): a 'wilds' draw after an earlier one is drawn
    again, once, with rng.weighted over atlas.ZONE_WEIGHTS without 'wilds' (purpose
    f"kind:{i}:again").
    Names: for i in order, rng.choice (purpose f"name:{i}") among atlas.ZONE_NAMES[kind] not used by
    an earlier zone of the run.
  2 Per zone i (in order), one PLACE_DISCOVERED {zone_id, places: [place ids], source: 'worldgen'}
    inserting:
      the zones row {zone_id, name, kind, content_ref NULL, danger = danger(values, kind)};
      the HUB: a place kind 'street', name = the zone name, zone_id, width 60, depth 20, indoor 0,
        material 'open_air', light 3, ambient_db 35, layout_generated 1, one anchor 'the middle of
        the street' (kind 'feature', x 30, y 10, cover 0, concealment 0);
      T['places_per_zone'] SITES, j = 0.. in order. Archetypes = the canon building records whose
        kind is in atlas.ZONE_BUILDING_KINDS[kind], by ref. None -> an OUTDOOR site: kind 'outdoor',
        name = rng.choice(atlas.OUTDOOR_PLACE_NAMES, purpose f"outdoor:{i}:{j}"), width 20, depth 20,
        indoor 0, open_air, light 3, ambient_db 30, layout_generated 1, anchor 'the middle' (feature,
        10, 10). Otherwise a BUILDING site: ref = rng.choice(archetype refs, purpose f"building:{i}:{j}");
        kind 'building', archetype_ref = ref, layout_generated 0 (rooms come at discovery,
        physical.space.discover_layout), width 15, depth 10, indoor 0, open_air, light 3, ambient_db
        32, anchor 'the front' (feature, 7.5, 1); name: archetype kind 'house' -> f"The {family}
        house", 'apartment' -> f"The {family} apartment" (family = rng.choice(the family names of the
        first canon names record by id, purpose f"family:{i}:{j}")), else the archetype's name; a name
        already used in this zone gets f" ({k})" with k = 2, 3, …;
      per site one portal hub <-> site: kind 'opening', name f"the way to {site name}" (a leading 'The'
        lower-cased), aperture 300 x 300, seal_db 0, anchor_a NULL, anchor_b = the site's anchor.
  3 Routes: the ring pairs (i, (i + 1) % n) for i in 0..n-1, each written smaller index first (the
    last one is (0, n-1)), then chords (i, j) for i < j that are not ring neighbours, each when rng.chance(atlas.CHORD_CHANCE, purpose f"chord:{i}:{j}"); per route (ring
    first, then chords, each in (i, j) order) distance = rng.range_int(*atlas.ROUTE_DISTANCE_M,
    purpose f"distance:{i}:{j}") and one PLACE_DISCOVERED {route_id, place_id, source: 'worldgen'}
    inserting: the ROAD place (kind 'street', name f"The road from {A} to {B}", zone_id = zone i's,
    width_m = distance, depth 8, indoor 0, open_air, light 3, ambient_db 30, layout_generated 1,
    anchors f"the {A} end" (feature, 0.5, 4) and f"the {B} end" (feature, distance - 0.5, 4)); portals
    hub A <-> road (opening, f"the {A} end of the road to {B}", anchor_b = the A end) and road <->
    hub B (opening, f"the {B} end of the road to {A}", anchor_a = the B end), both aperture 400 x 400,
    seal_db 0; the routes row {route_id, from_place = hub A, to_place = hub B, distance_m, terrain
    'road', danger = max(zone A danger 'shambler', zone B danger 'shambler'), known_by_default 1}.
    (A = zone i's name, B = zone j's name.)
  4 The exterior (P10, fidelity W04: the region is not the world): for k, dir in enumerate(
    atlas.EXTERIOR_DIRECTIONS), one PLACE_DISCOVERED {zone_id, places: [hub id], source: 'worldgen'}
    inserting the zones row {zone_id, name = atlas.EXTERIOR_NAMES[dir], kind 'exterior',
    content_ref NULL, danger = every key of danger() at 10} and its HUB (kind 'street', named as the
    zone, zone_id, width 80, depth 30, indoor 0, open_air, light 3, ambient_db 40, layout_generated
    1, one anchor 'the middle of the road' (feature, 40, 15)); gateway = region zone number (k x n)
    // 4; then a route from the gateway's hub (A) to this hub (B) written exactly as in step 3, with
    distance = rng.range_int(*atlas.EXTERIOR_DISTANCE_M, purpose f"exterior:{dir}"), the road place
    in the gateway zone named f"The road {dir} out of {A}", and routes.danger 10.
  5 world.hordes.seed_pools(tx, params, at): the dead of every zone, region and exterior (HRD-02).
  Returns Region(zones: [Zone(zone_id, kind, name, hub_id, site_ids)] of the REGION zones,
  routes: [Route(route_id, a_zone, b_zone, road_id)] (step 3's, then the exterior ones),
  start_zone_id = zone 0's id, exterior: [Zone(zone_id, 'exterior', name, hub_id, ())] in
  direction order). No stage after WG1 places anything in an exterior zone.

danger(values, zone_kind) -> dict[str, int]   (implemented below)
  {'crawler': zombie_common // 2, 'horde': horde_pressure, 'hostile': hostile_human, 'lurker':
  lurker_pressure, 'runner': runner_pressure, 'shambler': zombie_common}, each plus
  atlas.ZONE_DANGER_MOD[zone_kind] for its key, clamped 0..10 (keys sorted).

WG-15 assert_region(store, region) -> None   (raises WorldgenAssertion(stage 'WG1', ...))
  Checks what was WRITTEN (the store), not the Region it was handed: every place of the region
  (hubs, sites, roads) is reachable from the start zone's hub through the portals rows whose kind is
  not 'wall' (open or not), and the start zone has at least two edge-disjoint paths to some other
  zone over the routes rows (an edge per row joining the zones of its from_place and to_place hubs)
  (WG-17 — the ring guarantees it; the check guards against a broken writer).
WG-16 Every building site has layout_generated 0 and an archetype_ref; no room exists yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .atlas import ZONE_DANGER_MOD

if TYPE_CHECKING:
    from ...contracts.worldgen import WorldParams
    from ...kernel.rng import Rng
    from ...kernel.store import Store, Tx


@dataclass(frozen=True)
class Zone:
    zone_id: str
    kind: str
    name: str
    hub_id: str
    site_ids: tuple[str, ...]


@dataclass(frozen=True)
class Route:
    route_id: str
    a_zone: str
    b_zone: str
    road_id: str


@dataclass(frozen=True)
class Region:
    zones: tuple[Zone, ...]
    routes: tuple[Route, ...]
    start_zone_id: str
    extras: dict = field(default_factory=dict, compare=False)
    exterior: tuple[Zone, ...] = ()


def danger(values: dict, zone_kind: str) -> dict[str, int]:
    """Zone danger by kind (implemented)."""
    base = {"crawler": int(values["zombie_common"]) // 2, "horde": int(values["horde_pressure"]),
            "hostile": int(values["hostile_human"]), "lurker": int(values["lurker_pressure"]),
            "runner": int(values["runner_pressure"]), "shambler": int(values["zombie_common"])}
    mod = ZONE_DANGER_MOD.get(zone_kind, {})
    return {k: max(0, min(10, v + mod.get(k, 0))) for k, v in sorted(base.items())}


def build_region(rng: "Rng", tx: "Tx", params: "WorldParams", detail: str, canon, at: int) -> Region:
    raise NotImplementedError("P10")


def assert_region(store: "Store | Tx", region: Region) -> None:
    raise NotImplementedError("P10")
