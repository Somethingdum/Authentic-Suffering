"""The region's dead in numbers, the hordes and the Mega Horde (P10). Rules HRD-01..18, INF-11,
INF-13, OPS-03, SEL-01's memory for loud noises (world/hordes.py, world/infected.py, turn/select.py;
fidelity E01-E03, W04, F04, §5 LOD).

The dead are counted, district by district, and they are finite: a body you meet was taken from a
count, a crowd on the road is the same dead walking, and nothing refills by itself. A crowd that
stops somewhere presses on whoever lives there; one big enough breaks in. And sometimes, seen
coming for days, the whole country's dead come through.
"""

from __future__ import annotations

import json
import math

import pytest
from world_kit import (
    DAY,
    H,
    all_rows,
    area,
    cause,
    now,
    one,
    params,
    pc,
    rows,
    run,
    settlement,
    tune,
    turn,
)

from as_engine.contracts.events import Event, EventType
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec
from as_engine.world import hordes, infected
from as_engine.world.worldgen import atlas

pytestmark = pytest.mark.phase(10)

SH, CR, RU = infected.SHAMBLER, infected.CRAWLER, infected.RUNNER
TYPES = (SH, CR, RU)
MIN = 60_000


# --------------------------------------------------------------------------- helpers
def zones(s, exterior=False) -> list[dict]:
    op = "=" if exterior else "!="
    return all_rows(s, f"SELECT * FROM zones WHERE kind {op} 'exterior' ORDER BY zone_id")


def hub(s, zone_id) -> str:
    return one(s, "SELECT p.place_id FROM places p JOIN zones z ON z.zone_id = p.zone_id AND z.name = p.name "
                  "WHERE p.zone_id = ? AND p.kind = 'street'", (zone_id,))["place_id"]


def zone_of(s, place_id) -> str:
    return one(s, "SELECT zone_id FROM places WHERE place_id = ?", (place_id,))["zone_id"]


def give(s, zone_id, n, type_id=SH):
    """Test setup: n more active dead in a district (the census baseline is taken after it)."""
    with s.store.transaction() as tx:
        hordes.change(tx, zone_id, type_id, n, 0, "test", now(s), turn(s), None)


def empty(s, zone_id):
    with s.store.transaction() as tx:
        for t, (a, d) in hordes.pool(tx, zone_id).items():
            if a or d:
                hordes.change(tx, zone_id, t, -a, -d, "test", now(s), turn(s), None)


def horde(s, horde_id) -> dict:
    r = one(s, "SELECT * FROM hordes WHERE horde_id = ?", (horde_id,))
    for k in ("composition", "route", "props"):
        r[k] = json.loads(r[k])
    return r


def total(s) -> int:
    return hordes.census(s.store)["total"]


def risen_and_destroyed(s) -> int:
    risen = sum(r["payload"]["active_delta"] + r["payload"]["dormant_delta"]
                for r in rows(s, "POOL_CHANGE") if r["payload"]["reason"] == "risen")
    risen += s.store.query_one("SELECT COUNT(*) FROM infected_state WHERE risen_from IS NOT NULL")[0]
    destroyed = s.store.query_one("SELECT COUNT(*) FROM bodies WHERE kind = 'infected' AND alive = 0")[0]
    return risen - destroyed


def neighbour_hubs(s, hub_id) -> list[str]:
    out = []
    for r in all_rows(s, "SELECT from_place, to_place FROM routes WHERE from_place = ? OR to_place = ? ORDER BY route_id",
                      (hub_id, hub_id)):
        out.append(r["to_place"] if r["from_place"] == hub_id else r["from_place"])
    return out


def far_pair(s) -> tuple[str, str]:
    """A region district and a neighbouring district's hub, the whole walk between them outside the
    PC's area (so nobody meets the crowd on the way)."""
    near = area(s)
    for z in zones(s):
        h = hub(s, z["zone_id"])
        for to in neighbour_hubs(s, h):
            kind = one(s, "SELECT z.kind FROM places p JOIN zones z ON z.zone_id = p.zone_id WHERE p.place_id = ?",
                       (to,))["kind"]
            walk = hordes.path(s.store, h, to)
            if kind != "exterior" and walk and not ({h, *walk} & near):
                return z["zone_id"], to
    pytest.skip("every road runs past the PC")


# =========================================================================== HRD-01 / HRD-02 pools
def test_every_district_has_its_counted_dead(gw):
    """HRD-02: region zones from atlas.ZONE_INFECTED x (0.4 + zombie_common / 10); exterior zones
    from H.exterior_pool x (0.5 + zombie_common / 10); runners, crawlers, then shamblers; a share
    of each dormant."""
    s = gw
    H_ = s.store.rules.hordes
    from as_engine.contracts.worldgen import WorldParams
    from as_engine.world.worldgen.params import flat_values
    wp = WorldParams.model_validate(params(s))
    v = flat_values(wp)
    era, diff = str(getattr(wp.era, "value", wp.era)), str(getattr(wp.difficulty, "value", wp.difficulty))
    assert len(zones(s, exterior=True)) == 4
    for z in zones(s) + zones(s, exterior=True):
        if z["kind"] == "exterior":
            n = round(H_.exterior_pool[diff] * (0.5 + v["zombie_common"] / 10))
        else:
            n = round(atlas.ZONE_INFECTED[z["kind"]] * (0.4 + v["zombie_common"] / 10))
        runner = round(n * H_.runner_share[era] * v["runner_pressure"] / 5)
        crawler = round(n * H_.crawler_share)
        want = {SH: n - runner - crawler, CR: crawler, RU: runner}
        pool = hordes.pool(s.store, z["zone_id"])
        populated = sum(-(r["payload"]["active_delta"] + r["payload"]["dormant_delta"]) for r in rows(s, "POOL_CHANGE")
                        if r["payload"]["zone_id"] == z["zone_id"] and r["payload"]["reason"] == "populated")
        assert sum(a + d for a, d in pool.values()) + populated == n
        for t in TYPES:
            seeded = [r["payload"] for r in rows(s, "POOL_CHANGE") if r["payload"]["zone_id"] == z["zone_id"]
                      and r["payload"]["type_id"] == t and r["payload"]["reason"] == "worldgen"]
            if want[t] == 0:
                assert seeded == []
                continue
            [p] = seeded
            dorm = round(want[t] * H_.dormant_share[era])
            assert (p["active_delta"], p["dormant_delta"]) == (want[t] - dorm, dorm)
    assert all(r["origin"] == "worldgen" for r in rows(s, "POOL_CHANGE") if r["payload"]["reason"] == "worldgen")


def test_a_count_never_goes_below_zero(gw):
    """HRD-01: a change that would leave fewer than nobody, or changes nothing, is refused."""
    s = gw
    z = zones(s)[0]["zone_id"]
    a, d = hordes.pool(s.store, z)[SH]
    with s.store.transaction() as tx:
        with pytest.raises(ValueError):
            hordes.change(tx, z, SH, -(a + 1), 0, "test", now(s), turn(s), None)
        with pytest.raises(ValueError):
            hordes.change(tx, z, SH, 0, 0, "test", now(s), turn(s), None)
        ev = hordes.change(tx, z, SH, -1, 1, "test", now(s), turn(s), None)
    assert ev.payload == {"zone_id": z, "type_id": SH, "active_delta": -1, "dormant_delta": 1, "active": a - 1,
                          "dormant": d + 1, "reason": "test"}
    assert hordes.pool(s.store, z)[SH] == (a - 1, d + 1) and hordes.total(s.store, z) == sum(
        x + y for x, y in hordes.pool(s.store, z).values())


# =========================================================================== INF-11 populate
def _fresh_site(s):
    """A building or outdoor site nobody has been to, off screen, outside every settlement."""
    near = area(s)
    stl_sites = {r["place_id"] for r in all_rows(s, "SELECT place_id FROM settlements")}
    for r in all_rows(s, "SELECT p.place_id, p.zone_id, p.props FROM places p JOIN zones z ON z.zone_id = p.zone_id "
                         "WHERE p.parent_id IS NULL AND p.kind IN ('building', 'outdoor') AND z.kind != 'exterior' "
                         "ORDER BY p.place_id"):
        if r["place_id"] not in near and r["place_id"] not in stl_sites and not json.loads(r["props"]).get("populated"):
            return r["place_id"], r["zone_id"]
    pytest.skip("no fresh site")


def test_the_dead_you_meet_come_from_the_district(gw):
    """INF-11: per type and count, floor(x) or floor(x) + 1 bodies (x = count x place factor /
    (the zone's top-level places x H.populate_scale)), at most I.populate_max; exactly that many
    leave the district's count (POOL_CHANGE 'populated'); the total dead is unchanged."""
    s = gw
    site, z = _fresh_site(s)
    give(s, z, 3000)
    before, pool0 = total(s), hordes.pool(s.store, z)
    n_z = s.store.query_one("SELECT COUNT(*) FROM places WHERE zone_id = ? AND parent_id IS NULL", (z,))[0]
    kind = one(s, "SELECT kind FROM places WHERE place_id = ?", (site,))["kind"]
    f = s.store.rules.infected.place_factor[kind]
    with s.store.transaction() as tx:
        made = infected.populate(tx, s.rng, site, now(s), turn(s), cause(tx, now(s)).event_id)
    assert total(s) == before
    got = {}
    for b in made:
        r = one(s, "SELECT type_id, states FROM infected_state WHERE body_id = ?", (b,))
        key = (r["type_id"], "dormant" in json.loads(r["states"]))
        got[key] = got.get(key, 0) + 1
    for t in TYPES:
        for i, dormant in ((0, False), (1, True)):
            c = pool0[t][i]
            x = c * f / (n_z * s.store.rules.hordes.populate_scale)
            k = got.get((t, dormant), 0)
            assert k <= min(s.store.rules.infected.populate_max, c)
            assert k in (min(math.floor(x), s.store.rules.infected.populate_max), min(math.floor(x) + 1, c,
                                                                                      s.store.rules.infected.populate_max))
        assert hordes.pool(s.store, z)[t] == (pool0[t][0] - got.get((t, False), 0), pool0[t][1] - got.get((t, True), 0))
    assert got.get((SH, False), 0) == s.store.rules.infected.populate_max, "3000 shamblers fill a place"
    assert [r["payload"]["reason"] for r in rows(s, "POOL_CHANGE")][-1] == "populated"


def test_a_cleared_district_stays_clear(gw):
    """INF-11 / E01: a district with no dead left shows nobody when someone arrives."""
    s = gw
    site, z = _fresh_site(s)
    empty(s, z)
    with s.store.transaction() as tx:
        assert infected.populate(tx, s.rng, site, now(s), turn(s), None) == []
    assert json.loads(one(s, "SELECT props FROM places WHERE place_id = ?", (site,))["props"])["populated"] is True


# =========================================================================== HRD-03 paths
def test_a_horde_walks_the_roads(gw):
    """HRD-03: path = hub, then per road crossed [road, far hub], then the site; a room stands for
    its building site; leg_ms: a road's length at the given speed, 2 minutes otherwise."""
    s = gw
    a, b = zones(s)[0]["zone_id"], zones(s)[1]["zone_id"]
    ha, hb = hub(s, a), hub(s, b)
    site = one(s, "SELECT place_id FROM places WHERE zone_id = ? AND parent_id IS NULL AND kind != 'street' ORDER BY place_id",
               (b,))["place_id"]
    p = hordes.path(s.store, ha, site)
    assert p is not None and p[-2:] == [hb, site] and len(p) % 2 == 1
    road = p[-3]
    assert one(s, "SELECT kind FROM places WHERE place_id = ?", (road,))["kind"] == "street"
    assert hordes.path(s.store, ha, ha) == [] and hordes.target(s.store, site) == site
    w = one(s, "SELECT width_m FROM places WHERE place_id = ?", (road,))["width_m"]
    assert hordes.leg_ms(s.store, road, p[p.index(road) + 1], 0.5) == round(w / 0.5 * 1000)
    assert hordes.leg_ms(s.store, hb, site, 0.5) == 2 * MIN and hordes.leg_ms(s.store, p[0], p[1], 0.5) in (2 * MIN,
                                                                                                           round(w / 0.5 * 1000))


def test_a_body_takes_the_road_it_means_to(gw):
    """physical.space path (its P10 line): a route enters each place at most once. A hub's roads
    all meet at its centre, so stepping into one road and straight back out costs nothing; without
    the rule a tie sends a walker down the road with the lowest portal id and back before it takes
    its own. From off the centre of every hub, each road is one crossing; from one road's hub end,
    another road is two."""
    s = gw
    for z in zones(s):
        h = hub(s, z["zone_id"])
        ways = {}
        for r in all_rows(s, "SELECT * FROM portals WHERE place_a = ? OR place_b = ? ORDER BY portal_id", (h, h)):
            other = r["place_b"] if r["place_a"] == h else r["place_a"]
            if one(s, "SELECT kind FROM places WHERE place_id = ?", (other,))["kind"] == "street":
                ways[other] = r["portal_id"]
        roads = sorted(ways, key=ways.get)
        assert len(roads) >= 2, h
        with s.store.transaction() as tx:
            walker = infected.spawn(tx, s.rng, h, SH, now(s), turn(s), None, x_m=1.0, y_m=1.0, origin="scenario")
        for road in roads:
            legs = space.path(s.store, walker, road)
            assert [(leg.portal_id, leg.place_id) for leg in legs] == [(ways[road], road), (None, road)], (h, road)
        first, last = roads[0], roads[-1]
        x, y = space.portal_point(s.store, ways[first], first)
        with s.store.transaction() as tx:
            tx.commit_event(space.move_event(tx, walker, first, None, x, y, now(s), None, turn(s)))
        legs = space.path(s.store, walker, last)
        assert [(leg.portal_id, leg.place_id) for leg in legs] == [(ways[first], h), (ways[last], last), (None, last)]


# =========================================================================== HRD-04..06 a drift
def test_a_drift_walks_scatters_and_nothing_is_lost(gw):
    """HRD-04..06: formed from the district's active dead; it steps onto the road after 2 minutes,
    reaches the far hub after the road's length at H.speed_m_s (stragglers fall behind, it
    rallies), mills H.mill_h hours and scatters into that district. The dead are conserved."""
    s = gw
    tune(s, world={"op_chance": {"scavenge": 0.0, "patrol": 0.0, "trade_run": 0.0, "raid": 0.0}}, hordes={"drift_chance": 0.0})
    z, to = far_pair(s)
    give(s, z, 500)
    zb = zone_of(s, to)
    base = total(s)
    t0 = now(s)
    with s.store.transaction() as tx:
        hid = hordes.form(tx, "drift", z, {SH: 300}, to, t0, turn(s), cause(tx, t0).event_id)
    h = horde(s, hid)
    assert (h["kind"], h["status"], h["composition"], h["place_id"], h["target_place"]) == ("drift", "moving", {SH: 300}, hub(s, z), to)
    assert total(s) == base
    road = h["route"][0]
    walk = hordes.leg_ms(s.store, road, to, s.store.rules.hordes.speed_m_s)
    run(s, (2 * MIN + walk) / H + 0.01)
    moved = [r for r in rows(s, "HORDE_MOVED") if r["payload"]["horde_id"] == hid]
    assert [m["payload"]["to_place"] for m in moved] == [road, to]
    arrive = moved[-1]
    shown = sum(len(r["payload"]["bodies"]) for r in rows(s, "HORDE_PROMOTED")
                if r["payload"]["horde_id"] == hid and r["seq"] < arrive["seq"])
    k = math.floor((300 - shown) * s.store.rules.hordes.straggle)
    assert "stragglers" not in moved[0]["payload"], "a road is not a hub"
    assert arrive["payload"].get("stragglers", {}) == ({SH: k} if k else {})
    h = horde(s, hid)
    assert h["status"] == "milling" and h["props"]["until"] > now(s) - 1
    assert total(s) + 0 == base + risen_and_destroyed(s)
    run(s, s.store.rules.hordes.mill_h + 0.5)
    [gone] = [r["payload"] for r in rows(s, "HORDE_GONE") if r["payload"]["horde_id"] == hid]
    assert gone == {"horde_id": hid, "reason": "dispersed", "zone_id": zb}
    assert horde(s, hid)["composition"] == {} and hordes.count(s.store, hid) == 0
    assert total(s) == base + risen_and_destroyed(s)


# =========================================================================== HRD-07 contact
def test_a_horde_in_sight_becomes_bodies(gw):
    """HRD-07: where the player is, a horde shows up to H.local_cap bodies (horde_id set), taken
    from its count; when some are destroyed it fills the place again on its next tick."""
    s = gw
    tune(s, hordes={"drift_chance": 0.0, "local_cap": 12})
    here = one(s, "SELECT place_id FROM positions WHERE body_id = ?", (pc(s),))["place_id"]
    assert here in area(s)
    z = zone_of(s, hordes.target(s.store, here))
    give(s, z, 100)
    base = total(s)
    with s.store.transaction() as tx:
        hid = hordes.form(tx, "drawn", z, {SH: 50}, here, now(s), turn(s), None, first_leg_ms=5 * MIN)
    run(s, 0.6)
    bodies = [r["body_id"] for r in all_rows(s, "SELECT i.body_id FROM infected_state i JOIN positions q ON q.body_id = i.body_id "
                                                "WHERE i.horde_id = ? AND q.place_id = ?", (hid, here))]
    assert len(bodies) == 12 and hordes.count(s.store, hid) == 38
    [promo] = [r["payload"] for r in rows(s, "HORDE_PROMOTED") if r["payload"]["horde_id"] == hid][:1]
    assert promo["place_id"] == here and sorted(promo["bodies"]) == sorted(bodies) and promo["composition"] == {SH: 38}
    assert total(s) == base + risen_and_destroyed(s)
    with s.store.transaction() as tx:
        for b in bodies[:5]:
            tx.commit_event(Event(type=EventType.DEATH, writer="physical.bodies", at=now(s), turn_index=turn(s), actor_id=b,
                                  payload={"body_id": b, "cause": "test"},
                                  writes=[dict_write("bodies", {"body_id": b}, {"alive": 0, "core_intact": 0})]))
    run(s, s.store.rules.hordes.tick_min / 60 + 0.05)
    alive = s.store.query_one("SELECT COUNT(*) FROM infected_state i JOIN bodies b ON b.body_id = i.body_id "
                              "JOIN positions q ON q.body_id = i.body_id WHERE i.horde_id = ? AND b.alive = 1 AND q.place_id = ?",
                              (hid, here))[0]
    assert alive == 12 and hordes.count(s.store, hid) == 33
    assert total(s) == base + risen_and_destroyed(s)


def dict_write(table, key, values):
    from as_engine.contracts.events import WriteOp, WriteRecord
    return WriteRecord(op=WriteOp.UPDATE, table=table, key=key, values=values)


# =========================================================================== HRD-07 / HRD-18 in sight and out of it
def living_in(s, place_id) -> list[str]:
    """The living bodies that are not infected standing in a place."""
    return [r["body_id"] for r in all_rows(s, "SELECT b.body_id FROM bodies b JOIN positions q ON q.body_id = b.body_id "
                                              "WHERE q.place_id = ? AND b.alive = 1 AND b.kind != 'infected' "
                                              "ORDER BY b.body_id", (place_id,))]


def quiet_far_hub(s) -> tuple[str, str, str]:
    """A region district whose hub nobody alive stands in, and a neighbouring region district's
    hub, the hub and the whole walk between them outside the PC's area: (zone_id, hub, the other
    hub)."""
    near = area(s)
    for z in zones(s):
        h = hub(s, z["zone_id"])
        if h in near or living_in(s, h):
            continue
        for to in neighbour_hubs(s, h):
            kind = one(s, "SELECT z.kind FROM places p JOIN zones z ON z.zone_id = p.zone_id WHERE p.place_id = ?",
                       (to,))["kind"]
            walk = hordes.path(s.store, h, to)
            if kind != "exterior" and walk and not set(walk) & near:
                return z["zone_id"], h, to
    pytest.skip("every hub is in the PC's area or has somebody in it")


def pending_steps(s, body_id) -> list[str]:
    return [r["queue_id"] for r in all_rows(s, "SELECT queue_id FROM event_queue WHERE type = 'INFECTED_STEP' "
                                               "AND subject_id = ? AND status = 'pending' ORDER BY queue_id", (body_id,))]


def target_of(s, body_id) -> str | None:
    return one(s, "SELECT target_id FROM infected_state WHERE body_id = ?", (body_id,))["target_id"]


def test_a_milling_crowd_stands_where_it_is_shown(gw):
    """HRD-07: the bodies shown of a moving horde follow it (attract route[0], reason 'horde');
    a milling horde's stay where they were promoted, even when it still has a way to go (the Mega
    Horde mills at every hub of its passage): they are the crowd that fills the street."""
    s = gw
    tune(s, hordes={"drift_chance": 0.0, "local_cap": 3})
    z, h, to = quiet_far_hub(s)
    give(s, z, 20)
    with s.store.transaction() as tx:
        moving = hordes.form(tx, "drift", z, {SH: 5}, to, now(s), turn(s), None)
        milling = hordes.form(tx, "drift", z, {SH: 5}, to, now(s), turn(s), None)
        tx.commit_event(Event(type=EventType.HORDE_STATE, writer="world.hordes", at=now(s), turn_index=turn(s),
                              payload={"horde_id": milling, "changes": {"status": "milling"}},
                              writes=[dict_write("hordes", {"horde_id": milling}, {"status": "milling"})]))
        walking = hordes.promote(tx, s.rng, moving, h, now(s), turn(s), None)
        standing = hordes.promote(tx, s.rng, milling, h, now(s), turn(s), None)
    route = horde(s, milling)["route"]
    assert route and horde(s, moving)["route"] == route and len(walking) == len(standing) == 3
    drifts = {r["payload"]["body_id"]: r["payload"] for r in rows(s, "INFECTED_DRIFT")}
    for b in walking:
        assert drifts[b]["target_id"] == route[0] and drifts[b]["reason"] == "horde"
        assert target_of(s, b) == route[0] and len(pending_steps(s, b)) == 1
    for b in standing:
        assert b not in drifts and target_of(s, b) is None and not pending_steps(s, b)
        assert one(s, "SELECT place_id FROM positions WHERE body_id = ?", (b,))["place_id"] == h


def test_the_dead_nobody_is_near_fold_back_into_their_crowd(gw):
    """HRD-18 (fidelity F04 demotion): a body shown of a horde that is unhurt, walks its crowd's
    way, grips nobody and stands where nobody alive is, outside the PC's area, goes back into its
    horde's count: HORDE_REJOINED (+1 of its type), INFECTED_STATE folded_at / target None (writer
    'world.infected'), its pending INFECTED_STEP cancelled (reason 'folded') and DEMATERIALIZE
    deleting its position, both caused by the INFECTED_STATE — in that order. Its row stays, it is
    never folded twice, and the census never moves."""
    s = gw
    tune(s, hordes={"drift_chance": 0.0, "local_cap": 4})
    z, h, to = quiet_far_hub(s)
    give(s, z, 30)
    base = total(s)
    with s.store.transaction() as tx:
        hid = hordes.form(tx, "drift", z, {SH: 10}, to, now(s), turn(s), None)
        ids = hordes.promote(tx, s.rng, hid, h, now(s), turn(s), None)
    assert len(ids) == 4 and hordes.count(s.store, hid) == 6 and total(s) == base
    shown = hordes.census(s.store)["bodies"]
    first = ids[0]
    pos = one(s, "SELECT * FROM positions WHERE body_id = ?", (first,))
    [step] = pending_steps(s, first)
    t = now(s) + 1000
    with s.store.transaction() as tx:
        c = cause(tx, t, "nobody is near")
        out = hordes.fold(tx, first, t, turn(s), c.event_id)
    assert [e.type for e in out] == [EventType.HORDE_REJOINED, EventType.INFECTED_STATE, EventType.TIMER_CANCELLED,
                                     EventType.DEMATERIALIZE]
    rejoined, state, cancelled, gone = out
    assert rejoined.payload == {"horde_id": hid, "body_id": first, "type_id": SH, "composition": {SH: 7}}
    assert rejoined.cause_event_id == c.event_id and horde(s, hid)["composition"] == {SH: 7}
    assert state.writer == "world.infected" and state.payload["changes"] == {"folded_at": t, "target_id": None}
    assert state.cause_event_id == c.event_id
    assert cancelled.payload["queue_id"] == step and cancelled.payload["reason"] == "folded"
    assert cancelled.cause_event_id == state.event_id
    assert one(s, "SELECT status FROM event_queue WHERE queue_id = ?", (step,))["status"] == "cancelled"
    assert gone.writer == "physical.space" and gone.cause_event_id == state.event_id
    assert gone.payload == {"body_id": first, "place_id": h, "x_m": pos["x_m"], "y_m": pos["y_m"]}
    assert s.store.query_one("SELECT 1 FROM positions WHERE body_id = ?", (first,)) is None
    row = one(s, "SELECT * FROM infected_state WHERE body_id = ?", (first,))
    assert row["folded_at"] == t and row["target_id"] is None
    assert one(s, "SELECT alive FROM bodies WHERE body_id = ?", (first,))["alive"] == 1  # its history is whole
    assert not infected.active(s.store, first)
    assert hordes.census(s.store)["bodies"] == shown - 1 and total(s) == base
    with s.store.transaction() as tx:
        assert hordes.fold(tx, first, t, turn(s), None) == []
        space.place_body(tx, first, h, None, 1.0, 1.0, t, None, turn(s))  # put back by hand: still folded
        assert hordes.fold(tx, first, t, turn(s), None) == []  # a body is counted once
        for b in ids[1:]:
            assert hordes.fold(tx, b, t, turn(s), None)
    assert horde(s, hid)["composition"] == {SH: 10} and total(s) == base


def test_a_body_with_anything_of_its_own_stays_a_body(gw):
    """HRD-18: no fold for a hurt body (F04: it keeps its wounds), one hunting a body, one that
    grips or is gripped, one not taken from a count (a cheat's), a destroyed one, one in the PC's
    area, or one where somebody alive stands. The same body folds once the reason is gone."""
    s = gw
    tune(s, hordes={"drift_chance": 0.0, "local_cap": 8})
    z, h, _ = quiet_far_hub(s)
    near = area(s)
    spot = next(p for p in sorted(near) if not living_in(s, p))
    person = next(r["body_id"] for r in all_rows(s, "SELECT b.body_id FROM bodies b JOIN positions q ON q.body_id = b.body_id "
                                                    "WHERE b.alive = 1 AND b.kind != 'infected' AND b.body_id != ? "
                                                    "ORDER BY b.body_id", (pc(s),)))
    give(s, z, 30)
    with s.store.transaction() as tx:
        hid = hordes.form(tx, "drift", z, {SH: 20}, h, now(s), turn(s), None)  # to its own hub: it mills
        hurt, hunter, holder, held, dead, wanders, alone, control = hordes.promote(tx, s.rng, hid, h, now(s), turn(s), None)
        c = cause(tx, now(s))
        bodies.apply_harm(tx, hurt, WoundSpec("arm_l", "blunt", "minor", 0), now(s), c.event_id, turn(s), s.rng)
        assert infected.attract(tx, hunter, pc(s), now(s), c.event_id, turn(s), reason="noise") is not None
        bodies.grip_event(tx, holder, held, now(s), c.event_id, turn(s))
        tx.commit_event(Event(type=EventType.DEATH, writer="physical.bodies", at=now(s), turn_index=turn(s), actor_id=dead,
                              payload={"body_id": dead, "cause": "test"},
                              writes=[dict_write("bodies", {"body_id": dead}, {"alive": 0, "core_intact": 0})]))
        cheat = infected.spawn(tx, s.rng, h, SH, now(s), turn(s), c.event_id, origin="cheat")
        tx.commit_event(space.move_event(tx, wanders, spot, None, 1.0, 1.0, now(s), c.event_id, turn(s)))
    t = now(s)
    with s.store.transaction() as tx:
        for b in (hurt, hunter, holder, held, dead, cheat, wanders):
            assert hordes.fold(tx, b, t, turn(s), None) == [], b
        assert hordes.fold(tx, control, t, turn(s), None)
        tx.commit_event(space.move_event(tx, wanders, h, None, 1.0, 1.0, t, None, turn(s)))
        assert hordes.fold(tx, wanders, t, turn(s), None)  # out of the PC's area again
        tx.commit_event(space.move_event(tx, person, h, None, 2.0, 2.0, t, None, turn(s)))
        assert hordes.fold(tx, alone, t, turn(s), None) == []
        tx.commit_event(space.move_event(tx, person, spot, None, 2.0, 2.0, t, None, turn(s)))
        assert hordes.fold(tx, alone, t, turn(s), None)
    for b in (hurt, hunter, holder, held, cheat):
        assert one(s, "SELECT folded_at FROM infected_state WHERE body_id = ?", (b,))["folded_at"] is None
        assert s.store.query_one("SELECT 1 FROM positions WHERE body_id = ?", (b,)) is not None


def test_a_body_with_somewhere_of_its_own_to_be_keeps_walking(gw):
    """HRD-18: a body folds only when it is going nowhere of its own — no target, or its crowd's
    way (the horde's place or a place on its route). One of a crowd drawn somewhere else, or a
    body of no crowd walking to a noise, keeps walking as a body: the dead drawn by a shot three
    streets away still arrive (F04: the anonymous dead merge only with a compatible destination)."""
    s = gw
    tune(s, hordes={"drift_chance": 0.0, "local_cap": 4})
    z, h, to = quiet_far_hub(s)
    give(s, z, 30)
    with s.store.transaction() as tx:
        hid = hordes.form(tx, "drift", z, {SH: 10}, to, now(s), turn(s), None)
        follows, strays, back, _ = hordes.promote(tx, s.rng, hid, h, now(s), turn(s), None)
    road = horde(s, hid)["route"][0]
    site = one(s, "SELECT place_id FROM places WHERE zone_id = ? AND parent_id IS NULL AND kind != 'street' ORDER BY place_id",
               (z,))["place_id"]
    assert road not in area(s) and not living_in(s, road)
    with s.store.transaction() as tx:
        c = cause(tx, now(s))
        hordes.change(tx, z, SH, -1, 0, "test", now(s), turn(s), None)
        loner = infected.spawn(tx, s.rng, h, SH, now(s), turn(s), c.event_id)  # taken from the count; no crowd
        assert infected.attract(tx, loner, road, now(s), c.event_id, turn(s), reason="noise") is not None
        assert infected.attract(tx, strays, site, now(s), c.event_id, turn(s), reason="noise") is not None
        tx.commit_event(space.move_event(tx, back, road, None, 1.0, 1.0, now(s), c.event_id, turn(s)))
        assert infected.attract(tx, back, h, now(s), c.event_id, turn(s), reason="horde") is not None
    assert target_of(s, follows) == road and target_of(s, back) == h == horde(s, hid)["place_id"]
    t = now(s)
    with s.store.transaction() as tx:
        assert hordes.fold(tx, loner, t, turn(s), None) == []  # walking to a noise, with no crowd
        assert hordes.fold(tx, strays, t, turn(s), None) == []  # drawn off its crowd's way
        assert hordes.fold(tx, follows, t, turn(s), None)  # on its crowd's route
        assert hordes.fold(tx, back, t, turn(s), None)  # heading for the place its crowd is in
    assert horde(s, hid)["composition"] == {SH: 8}


def test_with_its_crowd_gone_it_folds_into_the_district(gw):
    """HRD-18: a body whose horde is gone (or that never had one) and that is going nowhere goes
    back into the district's count where it stands: change(zone, type, +1 active — or +1 dormant
    for a dormant one —, reason 'folded'), no HORDE_REJOINED. Nothing is lost and nothing is made.
    The last of a crowd that was walking when it was spent walk on where it was going (HRD-07):
    that is their own way now, and they stay bodies."""
    s = gw
    tune(s, hordes={"drift_chance": 0.0, "local_cap": 3})
    z, h, to = quiet_far_hub(s)
    give(s, z, 20)
    give(s, z, 5, CR)
    with s.store.transaction() as tx:
        hid = hordes.form(tx, "drift", z, {SH: 3}, h, now(s), turn(s), None)
        ids = hordes.promote(tx, s.rng, hid, h, now(s), turn(s), None)
        walker = hordes.form(tx, "drift", z, {SH: 3}, to, now(s), turn(s), None)
        last = hordes.promote(tx, s.rng, walker, h, now(s), turn(s), None)
        hordes.change(tx, z, CR, -1, 0, "test", now(s), turn(s), None)
        sleeper = infected.spawn(tx, s.rng, h, CR, now(s), turn(s), None, dormant=True)  # taken from the count
    assert len(ids) == 3 and horde(s, hid)["status"] == "gone"
    assert len(last) == 3 and horde(s, walker)["status"] == "gone"
    assert all(target_of(s, b) == horde(s, walker)["route"][0] for b in last)
    with s.store.transaction() as tx:
        assert hordes.fold(tx, last[0], now(s), turn(s), None) == []
    base, before = total(s), hordes.pool(s.store, z)
    with s.store.transaction() as tx:
        out = hordes.fold(tx, ids[0], now(s), turn(s), None) + hordes.fold(tx, sleeper, now(s), turn(s), None)
    assert EventType.HORDE_REJOINED not in [e.type for e in out]
    pools = [e.payload for e in out if e.type == EventType.POOL_CHANGE]
    assert [(p["zone_id"], p["type_id"], p["active_delta"], p["dormant_delta"], p["reason"]) for p in pools] == [
        (z, SH, 1, 0, "folded"), (z, CR, 0, 1, "folded")]
    after = hordes.pool(s.store, z)
    assert after[SH] == (before[SH][0] + 1, before[SH][1]) and after[CR] == (before[CR][0], before[CR][1] + 1)
    assert total(s) == base


def test_the_ones_that_walk_off_unseen_go_back_into_the_count(gw):
    """HRD-18 through INF-12: world.infected.step folds a body before it steps (the step's cause
    is its TIMER_FIRED). Shown where nobody is and left alone, a horde's bodies are back in its
    count at their first step, before it has walked on; the census never moves."""
    s = gw
    tune(s, hordes={"drift_chance": 0.0, "local_cap": 5})
    z, h, to = quiet_far_hub(s)
    give(s, z, 30)
    base = total(s)
    with s.store.transaction() as tx:
        hid = hordes.form(tx, "drift", z, {SH: 10}, to, now(s), turn(s), None)
        ids = hordes.promote(tx, s.rng, hid, h, now(s), turn(s), None)
    run(s, 0.02)
    back = [r for r in rows(s, "HORDE_REJOINED") if r["payload"]["horde_id"] == hid]
    assert sorted(r["payload"]["body_id"] for r in back) == sorted(ids)
    for r in back:
        fired = one(s, "SELECT type, payload FROM events WHERE event_id = ?", (r["cause_event_id"],))
        assert fired["type"] == "TIMER_FIRED" and json.loads(fired["payload"])["type"] == "INFECTED_STEP"
    for b in ids:
        assert s.store.query_one("SELECT 1 FROM positions WHERE body_id = ?", (b,)) is None
    assert all(r["payload"]["horde_id"] != hid for r in rows(s, "HORDE_MOVED"))  # it has not walked on yet
    assert horde(s, hid)["composition"] == {SH: 10} and total(s) == base


def test_a_roar_long_ago_no_longer_holds_the_moment(gw):
    """SEL-01 (P10): a loud noise of this turn brings its place and every place 1 hop from it into
    the active area for LOUD_MEMORY_MS (10 minutes) of world time — no longer: the off-screen step
    keeps one turn for days, and a roar hours ago must not keep a district in detail (HRD-18 folds
    by the area)."""
    from as_engine.turn import timers
    from as_engine.turn.select import LOUD_MEMORY_MS
    s = gw
    z, h, _ = quiet_far_hub(s)
    near = area(s)
    t0 = now(s)
    with s.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", at=t0, turn_index=turn(s),
                              payload={"source_db": 95, "kind": "roar", "text": "a roar", "place_id": h, "x_m": 1.0,
                                       "y_m": 1.0}))
        around = {h, *space.places_near(tx, h, 1)}
    assert LOUD_MEMORY_MS == 10 * MIN and h not in near
    assert around <= area(s)
    with s.store.transaction() as tx:
        timers.run_offscreen(tx, s.rng, t0 + LOUD_MEMORY_MS, turn(s))
    assert now(s) == t0 + LOUD_MEMORY_MS and around <= area(s)
    with s.store.transaction() as tx:
        timers.run_offscreen(tx, s.rng, t0 + LOUD_MEMORY_MS + 1, turn(s))
    assert not (around - near) & area(s)


# =========================================================================== HRD-08 pressing
def _stl_with_people(s):
    """A settlement with unnamed people that is not a sealed enclave (world.factions FAC-01)."""
    return next(r for r in all_rows(s, "SELECT * FROM settlements ORDER BY settlement_id")
                if s.store.query_one("SELECT SUM(count) FROM cohorts WHERE settlement_id = ?", (r["settlement_id"],))[0]
                and not json.loads(one(s, "SELECT props FROM places WHERE place_id = ?", (r["place_id"],))["props"]).get("enclave"))


def test_a_small_crowd_only_scratches_the_walls(gw):
    """HRD-08: pressure = N / (H.breach_scale x (1 + defences)); below 0.5 there is no breach; at
    N >= H.breach_scale the walls take it: defences -1, morale -1, a 'damage' trace."""
    s = gw
    st = _stl_with_people(s)
    sid, D = st["settlement_id"], st["defences"]
    z = zone_of(s, st["place_id"])
    Hs = s.store.rules.hordes
    n = int(Hs.breach_scale * (1 + D) * 0.5) - 1
    give(s, z, n)
    with s.store.transaction() as tx:
        hid = hordes.form(tx, "drift", z, {SH: n}, hub(s, z), now(s), turn(s), None)
        ev = hordes.press(tx, s.rng, hid, sid, now(s), turn(s), None)
    assert ev.payload["breached"] is False and ev.payload["killed"] == 0 and ev.payload["bitten"] == []
    assert ev.payload["pressure"] == round(n / (Hs.breach_scale * (1 + D)), 2)
    after = settlement(s, sid)
    if n >= Hs.breach_scale:
        assert after["defences"] == max(0, D - 1)
        assert any(t["kind"] == "damage" and t["place_id"] == st["place_id"] for t in all_rows(s, "SELECT * FROM traces"))
    else:
        assert after["defences"] == D


def test_a_breach_kills_the_ones_on_the_walls(gw):
    """HRD-08: breached — defences -2, morale -2; killed = min(unnamed, ceil(N x H.breach_kill)),
    from the cohorts in reverse serving order (POOL_RISE 'wet' scheduled for them); named members
    at the site off screen may be bitten (a 'bite' wound and a wet exposure)."""
    s = gw
    st = _stl_with_people(s)
    sid = st["settlement_id"]
    z = zone_of(s, st["place_id"])
    give(s, z, 5000)
    with s.store.transaction() as tx:
        hid = hordes.form(tx, "drift", z, {SH: 5000}, hub(s, z), now(s), turn(s), None)
    before = {r["cohort_id"]: r for r in all_rows(s, "SELECT * FROM cohorts WHERE settlement_id = ?", (sid,))}
    unnamed = sum(r["count"] for r in before.values())
    ev = None
    for k in range(6):
        with s.store.transaction() as tx:
            ev = hordes.press(tx, s.rng, hid, sid, now(s) + k, turn(s), None)
        if ev.payload["breached"]:
            break
    assert ev.payload["breached"], "p = 0.95 at this pressure"
    killed = ev.payload["killed"]
    assert killed == min(unnamed, math.ceil(5000 * s.store.rules.hordes.breach_kill))
    deaths = [r for r in rows(s, "POPULATION_CHANGE") if r["cause_event_id"] == ev.event_id]
    assert sum(-r["payload"]["delta"] for r in deaths) == killed and all(r["payload"]["reason"] == "horde" for r in deaths)
    rank = {"infant": 0, "child": 1, "preteen": 2, "teen": 3, "elder": 4, "adult": 5}
    order = sorted([c for c in before.values() if c["count"]], key=lambda c: (rank[c["age_band"]], c["cohort_id"]), reverse=True)
    assert [r["payload"]["cohort_id"] for r in deaths] == [c["cohort_id"] for c in order][:len(deaths)]
    rise = one(s, "SELECT * FROM event_queue WHERE type = 'POOL_RISE' AND status = 'pending' ORDER BY due_at DESC")
    assert rise is not None and json.loads(rise["payload"]) == {"zone_id": z, "count": killed, "pathway": "wet"}
    for b in ev.payload["bitten"]:
        assert one(s, "SELECT type FROM wounds WHERE body_id = ? ORDER BY created_at DESC", (b,))["type"] == "bite"
        assert any(r["payload"]["body_id"] == b for r in rows(s, "INFECTION_EXPOSURE"))
    assert settlement(s, sid)["defences"] <= max(0, st["defences"] - 2)


# =========================================================================== HRD-09 noise draws
def test_a_gunshot_draws_the_district(gw):
    """HRD-09 via action.propagate: a NOISE at or above H.draw_db draws floor(active x
    H.draw_share x (db - draw_db + 10) / 10) of each type toward it, due in H.draw_minutes; a
    second one within H.draw_cooldown_h draws nobody new."""
    from as_engine.action import propagate
    s = gw
    tune(s, hordes={"drift_chance": 0.0})
    site, z = _fresh_site(s)
    give(s, z, 2000)
    pool0 = hordes.pool(s.store, z)
    Hs = s.store.rules.hordes
    t0 = now(s)
    with s.store.transaction() as tx:
        shot = tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", at=t0, turn_index=turn(s),
                                     payload={"source_db": 160, "kind": "gunshot", "text": "a gunshot", "place_id": site,
                                              "x_m": 1.0, "y_m": 1.0}, place_id=site))
        propagate.propagate(tx, [shot], t0, turn(s))
    [formed] = [r["payload"] for r in rows(s, "HORDE_FORMED")]
    want = {t: math.floor(pool0[t][0] * Hs.draw_share * (160 - Hs.draw_db + 10) / 10) for t in TYPES}
    assert formed["composition"] == {t: n for t, n in want.items() if n > 0}
    assert formed["kind"] == "drawn" and formed["target_place"] == site
    q = one(s, "SELECT due_at FROM event_queue WHERE type = 'HORDE_STEP' AND subject_id = ?", (formed["horde_id"],))
    assert q["due_at"] == t0 + Hs.draw_minutes * MIN
    with s.store.transaction() as tx:
        assert hordes.draw(tx, site, 170, t0 + H, turn(s), shot.event_id) is None
        ext_hub = hub(s, zones(s, exterior=True)[0]["zone_id"])
        assert hordes.draw(tx, ext_hub, 170, t0, turn(s), shot.event_id) is None


# =========================================================================== HRD-10 / HRD-16 lifecycle
def test_runners_become_shamblers_in_the_count(gw):
    """HRD-10 step 1: floor(runners / H.runner_days) (+1 on the fraction's chance) of each pooled
    Runner count become Shamblers each world day, active ones first; the total is unchanged."""
    s = gw
    tune(s, world={"op_chance": {"scavenge": 0.0, "patrol": 0.0, "trade_run": 0.0, "raid": 0.0}},
         hordes={"drift_chance": 0.0, "mega_daily_chance": {k: 0.0 for k in s.store.rules.hordes.mega_daily_chance}})
    z = zones(s)[0]["zone_id"]
    give(s, z, 300, RU)
    r0, s0 = hordes.pool(s.store, z)[RU], hordes.pool(s.store, z)[SH]
    base = total(s)
    run(s, 24)
    moved = [r["payload"] for r in rows(s, "POOL_CHANGE") if r["payload"]["zone_id"] == z and r["payload"]["reason"] == "degraded"]
    ru = next(m for m in moved if m["type_id"] == RU)
    sh = next(m for m in moved if m["type_id"] == SH)
    n = -(ru["active_delta"] + ru["dormant_delta"])
    x = (r0[0] + r0[1]) / s.store.rules.hordes.runner_days
    assert n in (math.floor(x), math.floor(x) + 1)
    assert -ru["active_delta"] == min(n, r0[0])
    assert (sh["active_delta"], sh["dormant_delta"]) == (-ru["active_delta"], -ru["dormant_delta"])
    assert hordes.pool(s.store, z)[SH][0] >= s0[0]
    assert total(s) == base + risen_and_destroyed(s)


def test_districts_send_crowds_off(gw):
    """HRD-10 step 2: a district with at least H.drift_min active dead may send floor(active x
    H.drift_share) of each type toward a neighbouring district's hub (never the exterior)."""
    s = gw
    tune(s, world={"op_chance": {"scavenge": 0.0, "patrol": 0.0, "trade_run": 0.0, "raid": 0.0}},
         hordes={"drift_chance": 5.0, "mega_daily_chance": {k: 0.0 for k in s.store.rules.hordes.mega_daily_chance}})
    for z in zones(s):
        give(s, z["zone_id"], 1000)
    pools = {z["zone_id"]: hordes.pool(s.store, z["zone_id"]) for z in zones(s)}
    run(s, 24)
    formed = [r["payload"] for r in rows(s, "HORDE_FORMED")]
    assert {f["zone_id"] for f in formed} == {z["zone_id"] for z in zones(s)}
    for f in formed:
        assert f["kind"] == "drift"
        want = {t: math.floor(pools[f["zone_id"]][t][0] * s.store.rules.hordes.drift_share) for t in TYPES}
        assert f["composition"] == {t: n for t, n in want.items() if n > 0}
        assert f["target_place"] in neighbour_hubs(s, hub(s, f["zone_id"]))
        assert one(s, "SELECT kind FROM zones WHERE zone_id = ?", (zone_of(s, f["target_place"]),))["kind"] != "exterior"


def test_census_and_density(gw):
    """HRD-11: census counts every form of the dead; density reads a district's active dead
    against H.density_full (0..10)."""
    s = gw
    z = zones(s)[0]["zone_id"]
    c = hordes.census(s.store)
    pooled = sum(a + d for zz in c["pools"].values() for a, d in zz.values())
    bodies = s.store.query_one("SELECT COUNT(*) FROM bodies WHERE kind = 'infected' AND alive = 1")[0]
    assert c["bodies"] == bodies and c["total"] == pooled + bodies + sum(h["count"] for h in c["hordes"])
    act = sum(a for a, _d in hordes.pool(s.store, z).values())
    assert hordes.density(s.store, z) == min(10, round(10 * act / s.store.rules.hordes.density_full))
    give(s, z, s.store.rules.hordes.density_full * 2)
    assert hordes.density(s.store, z) == 10
    empty(s, z)
    assert hordes.density(s.store, z) == 0


def test_the_dead_of_the_unnamed_rise(gw):
    """HRD-16: schedule_rise draws the delay inside the pathway's rise window; POOL_RISE adds
    count - count // 4 of its first rise_as type and count // 4 of the second."""
    s = gw
    z = zones(s)[0]["zone_id"]
    t0 = now(s)
    with s.store.transaction() as tx:
        q = hordes.schedule_rise(tx, s.rng, z, 10, "cold_start", t0, turn(s), cause(tx, t0).event_id)
    row = one(s, "SELECT * FROM event_queue WHERE queue_id = ?", (q,))
    assert row["type"] == "POOL_RISE" and 66 * H <= row["due_at"] - t0 <= 78 * H
    p0 = hordes.pool(s.store, z)
    tune(s, world={"op_chance": {"scavenge": 0.0, "patrol": 0.0, "trade_run": 0.0, "raid": 0.0}},
         hordes={"drift_chance": 0.0})
    run(s, (row["due_at"] - t0) / H + 0.01)
    risen = [r["payload"] for r in rows(s, "POOL_CHANGE") if r["payload"]["reason"] == "risen"]
    assert [(r["type_id"], r["active_delta"]) for r in risen] == [(SH, 8), (CR, 2)]
    assert hordes.pool(s.store, z)[CR][0] >= p0[CR][0] + 2


# =========================================================================== HRD-12..14 the Mega Horde
def _mega(s):
    return next((r for r in all_rows(s, "SELECT * FROM hordes WHERE kind = 'mega'")), None)


def test_the_mega_horde_is_seen_coming(gw):
    """HRD-12 / HRD-13: formed at a WORLD_DAY from an exterior pool (size within the difficulty's
    range, capped by that pool), heading for the most peopled district; birds, then talk, then the
    roar, each once, days before it sets foot on the road in."""
    s = gw
    tune(s, world={"op_chance": {"scavenge": 0.0, "patrol": 0.0, "trade_run": 0.0, "raid": 0.0}},
         hordes={"drift_chance": 0.0, "mega_daily_chance": {k: 50.0 for k in s.store.rules.hordes.mega_daily_chance},
                 "mega_ramp_days": 1, "mega_eta_days": [8, 8]})
    ext0 = {z["zone_id"]: sum(a for a, _d in hordes.pool(s.store, z["zone_id"]).values()) for z in zones(s, exterior=True)}
    base = total(s)
    run(s, 24)
    m = _mega(s)
    assert m is not None and m["status"] == "moving"
    comp = json.loads(m["composition"])
    lo, hi = s.store.rules.hordes.mega_size["normal"] if params(s)["difficulty"] == "normal" else (0, 10 ** 9)
    size = sum(comp.values())
    assert size <= ext0[m["origin"]] and (lo <= size or size == ext0[m["origin"]])
    props = json.loads(m["props"])
    formed_at = next(r["at"] for r in rows(s, "HORDE_FORMED") if r["payload"]["horde_id"] == m["horde_id"])
    assert props["eta_at"] == formed_at + 8 * DAY and props["exit_zone"] != m["origin"]
    step = one(s, "SELECT due_at FROM event_queue WHERE type = 'HORDE_STEP' AND subject_id = ? AND status = 'pending'",
               (m["horde_id"],))
    assert step["due_at"] == props["eta_at"]
    people = {}
    for st in all_rows(s, "SELECT settlement_id, place_id FROM settlements"):
        from as_engine.society.population import census
        people[zone_of(s, st["place_id"])] = people.get(zone_of(s, st["place_id"]), 0) + census(s.store, st["settlement_id"]).total
    top = sorted(people.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if people else None
    if top and people[top] > 0:
        assert m["target_place"] == hub(s, top)
    assert total(s) == base + risen_and_destroyed(s)
    assert rows(s, "HORDE_SIGN") == []
    run(s, 24)
    assert [r["payload"]["sign"] for r in rows(s, "HORDE_SIGN")] == ["birds"]
    birds = [r for r in rows(s, "NOISE") if r["payload"].get("kind") == "birds"]
    gateway = zone_of(s, json.loads(m["route"])[1])
    assert birds and {zone_of(s, r["payload"]["place_id"]) for r in birds} == {gateway}
    run(s, 2 * 24)
    assert [r["payload"]["sign"] for r in rows(s, "HORDE_SIGN")] == ["birds", "talk"]
    talk = [r for r in all_rows(s, "SELECT p.predicate, p.subject_type, p.subject_id FROM rumours r "
                                   "JOIN propositions p ON p.prop_id = r.prop_id") if r["predicate"] == "horde_coming"]
    assert talk and all(t["subject_type"] == "place" and t["subject_id"] == hub(s, gateway) for t in talk)
    run(s, 3 * 24)
    assert [r["payload"]["sign"] for r in rows(s, "HORDE_SIGN")] == ["birds", "talk", "roar"]
    assert any(r["payload"].get("kind") == "distant_roar" for r in rows(s, "NOISE"))


def test_the_mega_horde_passes_through(gw):
    """HRD-14: it walks in, mills in each district for ceil(count / throughput x 24) hours with the
    district SATURATED (outdoor places at H.mega_ambient_db), presses its settlements, gives the
    quiet back when it leaves, and is gone at its exit, where its dead join that pool. Conserved."""
    s = gw
    tune(s, world={"op_chance": {"scavenge": 0.0, "patrol": 0.0, "trade_run": 0.0, "raid": 0.0}},
         hordes={"drift_chance": 0.0, "mega_daily_chance": {k: 50.0 for k in s.store.rules.hordes.mega_daily_chance},
                 "mega_ramp_days": 1, "mega_eta_days": [3, 3], "mega_size": {k: [20000, 20000] for k in
                                                                               s.store.rules.hordes.mega_size}})
    run(s, 24)
    m = _mega(s)
    hid = m["horde_id"]
    tune(s, hordes={"mega_daily_chance": {k: 0.0 for k in s.store.rules.hordes.mega_daily_chance}})
    base = total(s)
    route = json.loads(m["route"])
    gateway = zone_of(s, route[1])
    ambient = {r["place_id"]: r["ambient_db"] for r in all_rows(s, "SELECT place_id, ambient_db FROM places WHERE zone_id = ? "
                                                                   "AND parent_id IS NULL AND indoor = 0", (gateway,))}
    eta = json.loads(m["props"])["eta_at"]
    run(s, (eta - now(s)) / H + 12)
    h = horde(s, hid)
    assert h["zone_id"] == gateway and h["status"] == "milling"
    assert h["props"]["until"] - [r["at"] for r in rows(s, "HORDE_MOVED") if r["payload"]["horde_id"] == hid
                                  and r["payload"]["to_place"] == route[1]][0] == math.ceil(
        (20000 - math.floor(20000 * s.store.rules.hordes.straggle) + sum(
            h2 for h2 in next(r["payload"] for r in rows(s, "HORDE_MOVED") if r["payload"]["horde_id"] == hid
                              and r["payload"]["to_place"] == route[1]).get("rallied", {}).values()))
        / s.store.rules.hordes.mega_throughput_per_day * 24) * H
    for pl, old in ambient.items():
        assert one(s, "SELECT ambient_db FROM places WHERE place_id = ?", (pl,))["ambient_db"] == max(old, 85.0)
    assert any(r["payload"]["horde_id"] == hid for r in rows(s, "HORDE_PRESSED")) or not all_rows(
        s, "SELECT s.settlement_id FROM settlements s JOIN places p ON p.place_id = s.place_id WHERE p.zone_id = ?", (gateway,))
    run(s, 30 * 24)
    [gone] = [r["payload"] for r in rows(s, "HORDE_GONE") if r["payload"]["horde_id"] == hid]
    assert gone["reason"] == "left" and gone["zone_id"] == h["props"]["exit_zone"]
    for pl, old in ambient.items():
        assert one(s, "SELECT ambient_db FROM places WHERE place_id = ?", (pl,))["ambient_db"] == old
    assert hordes.count(s.store, hid) == 0
    assert total(s) == base + risen_and_destroyed(s)


# =========================================================================== INF-13 doors
def _door_scene(scenario, bodies: int):
    """metal_fence: June waits in the office behind its closed door; everyone else is moved to the
    stockroom (the dead would rather have someone in reach) and the scenario's scripted crash in the
    alley is called off; infected a few metres from the door on the sales floor side go for her. The
    door holds 3 minutes here instead of 30."""
    from as_engine.contracts.settings import RulesConfig
    from as_engine.kernel import clock
    w = scenario("metal_fence")
    r = w.store.rules.model_dump()
    r["infected"]["portal_holds_min"] = {"door": 3}
    w.store.attach(rules=RulesConfig.model_validate(r))
    office_door = one_w(w, "SELECT * FROM portals WHERE portal_id = ?", (w.id("office_door"),))
    assert (office_door["is_open"], office_door["barricade"], office_door["lock_quality"]) == (0, 0, 0)
    with w.store.transaction() as tx:
        for q in tx.query("SELECT queue_id FROM event_queue WHERE status = 'pending' ORDER BY queue_id"):
            clock.cancel(tx, q[0], "test", now_w(w), None, 0)
        for k, who in enumerate(("eli", "pc", "mara", "alice")):
            tx.commit_event(space.move_event(tx, w.id(who), w.id("storeroom"), None, 2.0 + k, 2.0, now_w(w), None, 0))
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("office"), None, 2.0, 1.5, now_w(w), None, 0))
        x, y = space.portal_point(tx, w.id("office_door"), w.id("sales_floor"))
        made = [infected.spawn(tx, w.rng, w.id("sales_floor"), SH, now_w(w), 0, None, x_m=x + 3.0, y_m=y - 2.5)
                for _ in range(bodies)]
        for b in made:
            infected.attract(tx, b, w.id("june"), now_w(w), None, 0, reason="sight")
    return w, made, (x, y)


def one_w(w, sql, p=()):
    r = w.store.query_one(sql, p)
    return None if r is None else dict(r)


def now_w(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def _run_w(w, minutes):
    from as_engine.turn import timers
    with w.store.transaction() as tx:
        timers.run_offscreen(tx, w.rng, now_w(w) + int(minutes * MIN), 0)


def test_a_crowd_breaks_down_a_door(scenario):
    """INF-13: the dead walk up to the closed door (a MOVE to its point on their side); with
    I.push_min bodies there it takes 1 damage a minute at most; at I.portal_holds_min[kind] +
    barricade and lock terms it gives way (open, unlocked, no barricade) with a 'breaking' NOISE."""
    w, made, (x, y) = _door_scene(scenario, 3)
    _run_w(w, 6)
    for b in made:
        walked = [json.loads(e["payload"]) for e in w.store.query(
            "SELECT payload FROM events WHERE type = 'MOVE' AND actor_id = ? ORDER BY seq", (b,))]
        assert walked and walked[0]["to_place"] == w.id("sales_floor"), "it walks up to the door first"
    changes = [(x["at"], json.loads(x["payload"])) for x in w.store.query("SELECT at, payload FROM events WHERE type = 'PORTAL_CHANGE' "
                                                                          "ORDER BY seq")
               if json.loads(x["payload"])["portal_id"] == w.id("office_door")]
    strain = [(at, c["changes"]) for at, c in changes if "strain_min" in c["changes"]]
    assert [c["strain_min"] for _at, c in strain] == [1, 2, 3], "a minute of pressure at a time (holds 3 here)"
    assert [c.get("damage") for _at, c in strain] == [1, 2, 3], "damage (0..3) shows how near it is to giving way"
    assert all(b[0] - a[0] >= MIN for a, b in zip(strain, strain[1:], strict=False))
    door = one_w(w, "SELECT * FROM portals WHERE portal_id = ?", (w.id("office_door"),))
    assert (door["is_open"], door["is_locked"], door["barricade"], door["damage"]) == (1, 0, 0, 3)
    assert any(json.loads(x["payload"]).get("kind") == "breaking" for x in w.store.query("SELECT payload FROM events WHERE type = 'NOISE'"))


def test_a_locked_door_is_still_a_door(scenario):
    """INF-12 (allow_locked) + INF-13: the dead find a locked door and lean on it like any other;
    lock quality only makes it hold longer (here 3 + 15 x 1 minutes)."""
    w, _made, _pt = _door_scene(scenario, 3)
    with w.store.transaction() as tx:
        tx.commit_event(space.portal_change_event(tx, w.id("office_door"), {"is_locked": 1}, now_w(w), None, None, 0))
    from as_engine.contracts.settings import RulesConfig
    r = w.store.rules.model_dump()
    r["infected"]["lock_min"] = 2
    w.store.attach(rules=RulesConfig.model_validate(r))
    with w.store.transaction() as tx:
        w.store.query_one("SELECT 1")
    door = one_w(w, "SELECT * FROM portals WHERE portal_id = ?", (w.id("office_door"),))
    holds = 3 + 2 * door["lock_quality"]
    _run_w(w, holds + 3)
    door = one_w(w, "SELECT * FROM portals WHERE portal_id = ?", (w.id("office_door"),))
    assert (door["is_open"], door["is_locked"], door["strain_min"]) == (1, 0, holds)


def test_the_strain_counts_minutes_the_damage_shows_how_near(scenario):
    """INF-13: strain_min counts every minute of pressure; damage (0..3) rises in thirds of what the
    door holds; it gives way when the strain reaches the hold — here 7 minutes."""
    from as_engine.contracts.settings import RulesConfig
    w, _made, _pt = _door_scene(scenario, 3)
    r = w.store.rules.model_dump()
    r["infected"]["portal_holds_min"] = {"door": 7}
    w.store.attach(rules=RulesConfig.model_validate(r))
    _run_w(w, 10)
    got = [json.loads(x["payload"])["changes"] for x in w.store.query("SELECT payload FROM events WHERE type = 'PORTAL_CHANGE' "
                                                                       "ORDER BY seq")
           if json.loads(x["payload"])["portal_id"] == w.id("office_door") and "strain_min" in json.loads(x["payload"])["changes"]]
    assert [c["strain_min"] for c in got] == [1, 2, 3, 4, 5, 6, 7]
    assert [c.get("damage") for c in got] == [None, None, 1, None, 2, None, 3]
    door = one_w(w, "SELECT * FROM portals WHERE portal_id = ?", (w.id("office_door"),))
    assert (door["is_open"], door["damage"], door["strain_min"]) == (1, 3, 7)


def test_one_body_only_bangs_and_tires_by_the_minute(scenario):
    """INF-13: fewer than I.push_min bodies bang on a door but never break it. INF-03: six minutes of
    banging, every few seconds, costs a Shambler one energy a minute, not one a bang."""
    w, [b], _pt = _door_scene(scenario, 1)
    t0 = now_w(w)
    _run_w(w, 6)
    door = one_w(w, "SELECT * FROM portals WHERE portal_id = ?", (w.id("office_door"),))
    assert (door["is_open"], door["damage"], door["strain_min"]) == (0, 0, 0)
    bangs = [json.loads(x["payload"]) for x in w.store.query("SELECT payload FROM events WHERE type = 'NOISE' ORDER BY seq")
             if json.loads(x["payload"]).get("kind") == "banging"]
    assert len(bangs) > 20
    st = one_w(w, "SELECT energy, states, charged_at FROM infected_state WHERE body_id = ?", (b,))
    period = w.store.rules.infected.energy_period_s[SH] * 1000
    assert "dormant" not in json.loads(st["states"])
    assert st["energy"] == w.store.rules.infected.energy_start - (st["charged_at"] - t0) // period
    assert 5 * MIN <= st["charged_at"] - t0 <= 6 * MIN
