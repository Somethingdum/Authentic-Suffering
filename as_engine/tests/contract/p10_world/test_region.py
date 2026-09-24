"""The region, WG1 (P10). Rules WG-15..17, GEO-00, GEO-03 (world/worldgen/region.py).

A region is zones joined by roads; each zone is a hub street with the building sites and outdoor
places that open off it. Buildings are only their grounds until somebody arrives (rooms come at
discovery, GEO-03). The start zone always has two ways out.
"""

from __future__ import annotations

import json

import pytest

from as_engine.contracts.common import Difficulty, Era
from as_engine.contracts.dossier import WorldgenBias
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.kernel.rng import Rng
from as_engine.world.worldgen import atlas, params, region, tables
from as_engine.world.worldgen.pipeline import WorldgenAssertion

pytestmark = pytest.mark.phase(10)

AT = 1000


def build(store, canon, seed, detail="gotta_go_to_work_soon", dsf=900):
    rng = Rng(seed)
    with store.transaction() as tx:
        p, _ = params.generate_params(rng, tx, Difficulty.NORMAL, Era.ESTABLISHED, WorldgenBias(), dsf)
    with store.transaction() as tx:
        reg = region.build_region(rng, tx, p, detail, canon, AT)
    return p, reg


def row(store, table, key, value):
    r = store.query_one(f"SELECT * FROM {table} WHERE {key} = ?", (value,))
    return None if r is None else dict(r)


def portals_between(store, a, b):
    return [dict(r) for r in store.query("SELECT * FROM portals WHERE (place_a = ? AND place_b = ?) OR (place_a = ? AND place_b = ?)",
                                         (a, b, b, a))]


@pytest.mark.parametrize("case", [0, 1])
def test_region_vectors(store, canon, vectors, case):
    """WG-DET-01: the same seed makes the same region, draw for draw."""
    c = vectors("region")["cases"][case]
    rng = Rng(c["seed"])
    with store.transaction() as tx:
        p, _ = params.generate_params(rng, tx, Difficulty(c["difficulty"]), Era(c["era"]), WorldgenBias(), c["days_since_fall"])
    with store.transaction() as tx:
        reg = region.build_region(rng, tx, p, c["detail"], canon, c["at"])
    got = [dict(r) for r in store.query("SELECT purpose, n, value FROM prng_ledger WHERE stream = 'worldgen:region' ORDER BY seq")]
    for i, want in enumerate(c["draws"]):
        assert i < len(got) and got[i] == want, f"draw {i}: expected {want}, got {got[i] if i < len(got) else None}"
    assert len(got) == len(c["draws"])
    zones = [{"kind": z.kind, "name": z.name,
              "sites": [[row(store, "places", "place_id", s)[k] for k in ("name", "kind", "archetype_ref")] for s in z.site_ids]}
             for z in reg.zones]
    assert zones == c["zones"]
    idx = {z.zone_id: i for i, z in enumerate(reg.zones)}
    routes = [[idx[r.a_zone], idx[r.b_zone], row(store, "routes", "route_id", r.route_id)["distance_m"],
               row(store, "places", "place_id", r.road_id)["name"]] for r in reg.routes]
    assert routes == c["routes"]


@pytest.mark.parametrize("seed, detail", [(21, "gotta_go_to_work_soon"), (8, "quick_look"), (33, "standard")])
def test_zones_hubs_and_sites(store, canon, seed, detail):
    """Step 1-2: n zones, each a hub street and its sites, one PLACE_DISCOVERED per zone."""
    T = tables.DETAIL_TIERS[detail]
    p, reg = build(store, canon, seed, detail)
    values = params.flat_values(p)
    assert len(reg.zones) == T["zones"] and reg.start_zone_id == reg.zones[0].zone_id
    assert reg.zones[0].kind in dict(atlas.START_ZONE_WEIGHTS)
    assert len({z.name for z in reg.zones}) == len(reg.zones), "zone names are not reused"
    ev = [dict(r) for r in store.query("SELECT * FROM events WHERE type = 'PLACE_DISCOVERED' ORDER BY seq")]
    zone_events = [e for e in ev if "zone_id" in json.loads(e["payload"])]
    assert len(zone_events) == len(reg.zones)
    for e in ev:
        assert (e["writer"], e["origin"], e["turn_index"], e["at"]) == ("physical.space", "worldgen", 0, AT)
    for z in reg.zones:
        zr = row(store, "zones", "zone_id", z.zone_id)
        assert (zr["name"], zr["kind"]) == (z.name, z.kind) and z.name in atlas.ZONE_NAMES[z.kind]
        assert json.loads(zr["danger"]) == region.danger(values, z.kind)
        hub = row(store, "places", "place_id", z.hub_id)
        assert (hub["kind"], hub["name"], hub["zone_id"], hub["indoor"], hub["layout_generated"]) == ("street", z.name, z.zone_id, 0, 1)
        assert (hub["width_m"], hub["depth_m"]) == (60, 20)
        assert [r["name"] for r in store.query("SELECT name FROM anchors WHERE place_id = ?", (z.hub_id,))] == ["the middle of the street"]
        assert len(z.site_ids) == T["places_per_zone"]
        kinds_here = atlas.ZONE_BUILDING_KINDS[z.kind]
        names = []
        for sid in z.site_ids:
            site = row(store, "places", "place_id", sid)
            names.append(site["name"])
            anchors = [dict(r) for r in store.query("SELECT * FROM anchors WHERE place_id = ?", (sid,))]
            assert len(anchors) == 1
            if kinds_here:
                assert (site["kind"], site["layout_generated"], site["indoor"]) == ("building", 0, 0)
                assert canon.get(site["archetype_ref"]).kind in kinds_here
                assert anchors[0]["name"] == "the front"
            else:
                assert (site["kind"], site["archetype_ref"], site["layout_generated"]) == ("outdoor", None, 1)
                assert site["name"].split(" (")[0] in atlas.OUTDOOR_PLACE_NAMES and anchors[0]["name"] == "the middle"
            (way,) = portals_between(store, z.hub_id, sid)
            assert way["kind"] == "opening" and way["is_open"] == 1 and (way["aperture_w_cm"], way["aperture_h_cm"]) == (300, 300)
            assert way["anchor_b" if way["place_b"] == sid else "anchor_a"] == anchors[0]["anchor_id"]
            shown = site["name"][0].lower() + site["name"][1:] if site["name"].startswith("The ") else site["name"]
            assert way["name"] == f"the way to {shown}"
        assert len(set(names)) == len(names), "a repeated name gets ' (2)', ' (3)'…"


def test_wg16_buildings_wait_to_be_found(store, canon):
    """WG-16: a building site has an archetype and no rooms until someone arrives."""
    _p, reg = build(store, canon, 33, "standard")
    sites = [s for z in reg.zones for s in z.site_ids]
    rooms = store.query_one("SELECT COUNT(*) FROM places WHERE kind = 'room'")[0]
    assert rooms == 0
    for sid in sites:
        site = row(store, "places", "place_id", sid)
        if site["kind"] == "building":
            assert site["archetype_ref"] and site["layout_generated"] == 0
        assert store.query_one("SELECT COUNT(*) FROM places WHERE parent_id = ?", (sid,))[0] == 0


@pytest.mark.parametrize("seed, detail", [(21, "gotta_go_to_work_soon"), (8, "quick_look"), (5, "settle_in")])
def test_routes_ring_and_roads(store, canon, seed, detail):
    """Step 3: the ring first, then the chords; each route is a road place between two hubs."""
    p, reg = build(store, canon, seed, detail)
    n = len(reg.zones)
    idx = {z.zone_id: i for i, z in enumerate(reg.zones)}
    pairs = [(idx[r.a_zone], idx[r.b_zone]) for r in reg.routes]
    ring = [tuple(sorted((i, (i + 1) % n))) for i in range(n)]
    assert pairs[:n] == ring
    assert all(a < b and (a, b) not in ring for a, b in pairs[n:]), "chords join non-neighbours, smaller index first"
    assert pairs[n:] == sorted(pairs[n:])
    for r in reg.routes:
        za, zb = reg.zones[idx[r.a_zone]], reg.zones[idx[r.b_zone]]
        rr = row(store, "routes", "route_id", r.route_id)
        lo, hi = atlas.ROUTE_DISTANCE_M
        assert lo <= rr["distance_m"] <= hi
        assert (rr["from_place"], rr["to_place"], rr["terrain"], rr["known_by_default"]) == (za.hub_id, zb.hub_id, "road", 1)
        da = json.loads(row(store, "zones", "zone_id", za.zone_id)["danger"])["shambler"]
        db = json.loads(row(store, "zones", "zone_id", zb.zone_id)["danger"])["shambler"]
        assert rr["danger"] == max(da, db)
        road = row(store, "places", "place_id", r.road_id)
        assert (road["kind"], road["name"], road["zone_id"]) == ("street", f"The road from {za.name} to {zb.name}", za.zone_id)
        assert (road["width_m"], road["depth_m"]) == (rr["distance_m"], 8)
        ends = {a["name"]: a for a in (dict(x) for x in store.query("SELECT * FROM anchors WHERE place_id = ?", (r.road_id,)))}
        assert set(ends) == {f"the {za.name} end", f"the {zb.name} end"}
        assert ends[f"the {zb.name} end"]["x_m"] == rr["distance_m"] - 0.5
        (a_way,) = portals_between(store, za.hub_id, r.road_id)
        (b_way,) = portals_between(store, r.road_id, zb.hub_id)
        assert a_way["name"] == f"the {za.name} end of the road to {zb.name}"
        assert b_way["name"] == f"the {zb.name} end of the road to {za.name}"
        assert (a_way["aperture_w_cm"], b_way["aperture_w_cm"]) == (400, 400)


def test_wg15_the_region_holds(store, canon):
    """WG-15 / WG-17: every place is reachable from the start hub; two ways out of the start zone."""
    _p, reg = build(store, canon, 21)
    region.assert_region(store, reg)


def _delete(store, table, key):
    with store.transaction() as tx:
        tx.commit_event(Event(type=EventType.PLACE_CHANGE, writer="physical.space", at=AT, turn_index=0,
                              payload={"test": "break the region"}, writes=[WriteRecord(op=WriteOp.DELETE, table=table, key=key)]))


def test_wg15_an_unreachable_site_is_caught(store, canon):
    _p, reg = build(store, canon, 21)
    z = reg.zones[1]
    (way,) = portals_between(store, z.hub_id, z.site_ids[0])
    _delete(store, "portals", {"portal_id": way["portal_id"]})
    with pytest.raises(WorldgenAssertion) as e:
        region.assert_region(store, reg)
    assert e.value.stage == "WG1"


def test_wg17_one_way_out_is_caught(store, canon):
    _p, reg = build(store, canon, 21)
    start_routes = [r for r in reg.routes if reg.start_zone_id in (r.a_zone, r.b_zone)]
    _delete(store, "routes", {"route_id": start_routes[0].route_id})
    with pytest.raises(WorldgenAssertion) as e:
        region.assert_region(store, reg)
    assert e.value.stage == "WG1"
