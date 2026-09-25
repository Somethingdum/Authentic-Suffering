"""Buildings are found, not pre-built (P10). Rules GEO-03, GEO-04 (physical/space.py
discover_layout), OPS-05 (world/worldmove.py on_arrival).

A worldgen building site is only its grounds until somebody walks in. Then its rooms, doors,
furniture and what is left on the shelves are laid out once, from its archetype and its own seed,
and they stay that way. A place the Fall went through has been picked over: its doors hang broken
or open and there is less left to find.
"""

from __future__ import annotations

import json
import shutil

import pytest
from world_kit import REPO_PACKS, all_rows, now, one, rows, turn

from as_engine.contracts.events import EventType
from as_engine.contracts.settings import EngineConfig
from as_engine.physical import space
from as_engine.world import worldmove

pytestmark = pytest.mark.phase(10)


# --------------------------------------------------------------------------- helpers
def site(s, *, held: int) -> str:
    """An undiscovered building (by id), its held flag set as asked (physical.space.change_place)."""
    r = one(s, "SELECT place_id, held FROM places WHERE kind = 'building' AND archetype_ref IS NOT NULL "
               "AND layout_generated = 0 ORDER BY held = ? DESC, place_id LIMIT 1", (held,))
    if r is None:
        pytest.skip("no undiscovered building in this world")
    if r["held"] != held:
        with s.store.transaction() as tx:
            space.change_place(tx, r["place_id"], {"held": held}, "test", now(s), None, turn(s))
    return r["place_id"]


def discover(s, place_id) -> list:
    with s.store.transaction() as tx:
        return space.discover_layout(tx, s.rng, place_id, now(s), turn(s))


def archetype(s, place_id):
    return s.store.canon.get(one(s, "SELECT archetype_ref FROM places WHERE place_id = ?", (place_id,))["archetype_ref"])


def rooms_of(s, place_id) -> list[dict]:
    return all_rows(s, "SELECT * FROM places WHERE parent_id = ? AND kind = 'room' ORDER BY place_id", (place_id,))


def anchors_of(s, place_id) -> list[dict]:
    return all_rows(s, "SELECT * FROM anchors WHERE place_id = ? ORDER BY anchor_id", (place_id,))


def portal(s, a, b, name) -> dict:
    """The one portal of that name between two places (a building may have two doors into one room)."""
    [r] = all_rows(s, "SELECT * FROM portals WHERE ((place_a = ? AND place_b = ?) OR (place_a = ? AND place_b = ?)) "
                      "AND name = ?", (a, b, b, a, name))
    return r


def ledger(s, stream) -> int:
    return s.store.query_one("SELECT COUNT(*) FROM prng_ledger WHERE stream = ?", (stream,))[0]


# =========================================================================== GEO-03 the layout
def test_rooms_doors_and_furniture_come_from_the_archetype(gw):
    """GEO-03: one PLACE_DISCOVERED; per room template, in order, a room of the building (its zone,
    its size and material, light 1, 25 dB, held as the building) with its anchors; the inside doors
    as written; the doors to the grounds, on a held building, whole and locked where they lock."""
    s = gw
    b = site(s, held=1)
    a = archetype(s, b)
    bld = one(s, "SELECT * FROM places WHERE place_id = ?", (b,))
    evs = discover(s, b)
    assert evs[0].type == EventType.PLACE_DISCOVERED and evs[0].writer == "physical.space"
    assert evs[0].payload == {"place_id": b, "rooms": len(a.rooms), "source": "discovery"}
    rooms = rooms_of(s, b)
    assert [(r["name"], r["width_m"], r["depth_m"], r["indoor"], r["material"]) for r in rooms] == [
        (t.name, t.width_m, t.depth_m, int(t.indoor), t.material) for t in a.rooms]
    for r in rooms:
        assert (r["kind"], r["zone_id"], r["light_level"], r["ambient_db"], r["layout_generated"], r["held"],
                r["archetype_ref"]) == ("room", bld["zone_id"], 1, 25.0, 1, 1, None)
    room_of = {t.id: r["place_id"] for t, r in zip(a.rooms, rooms, strict=True)}
    for t in a.rooms:
        got = anchors_of(s, room_of[t.id])
        assert [(x["name"], x["kind"], x["x_m"], x["y_m"], x["cover"], x["concealment"], x["capacity"]) for x in got] == [
            (an.name, an.kind, an.x_m, an.y_m, an.cover, an.concealment, 4) for an in t.anchors]
        for pt in t.portals:
            p = portal(s, room_of[t.id], room_of[pt.to_room], pt.name)
            assert (p["kind"], p["name"], p["is_open"], p["is_locked"], p["lock_quality"], p["damage"],
                    p["aperture_w_cm"], p["aperture_h_cm"], p["seal_db"], p["anchor_a"], p["anchor_b"]) == (
                pt.kind, pt.name, int(pt.starts_open), 0, pt.lock_quality, 0, pt.aperture_w_cm, pt.aperture_h_cm,
                pt.seal_db, None, None)
    first = one(s, "SELECT anchor_id FROM anchors WHERE place_id = ? ORDER BY anchor_id LIMIT 1", (b,))
    for pt in a.exterior_portals:
        p = portal(s, b, room_of[pt.to_room], pt.name)
        assert (p["name"], p["is_open"], p["is_locked"], p["damage"], p["anchor_a"]) == (
            pt.name, int(pt.starts_open), int(pt.lockable), 0, first["anchor_id"] if first else None)
    assert one(s, "SELECT layout_generated FROM places WHERE place_id = ?", (b,))["layout_generated"] == 1


def test_it_happens_once(gw):
    """GEO-03: a building already laid out, or anything that is not a building, is left alone."""
    s = gw
    b = site(s, held=1)
    discover(s, b)
    n = s.store.query_one("SELECT COUNT(*) FROM places")[0]
    assert discover(s, b) == []
    street = one(s, "SELECT place_id FROM places WHERE kind = 'street' ORDER BY place_id LIMIT 1")["place_id"]
    assert discover(s, street) == []
    assert s.store.query_one("SELECT COUNT(*) FROM places")[0] == n


def test_the_fall_went_through_an_unheld_building(gw):
    """GEO-03: nobody held it — its outside doors are unlocked, some open, some damaged (0..2); its
    rooms are unheld too."""
    s = gw
    b = site(s, held=0)
    a = archetype(s, b)
    discover(s, b)
    rooms = rooms_of(s, b)
    assert {r["held"] for r in rooms} == {0}
    room_of = {t.id: r["place_id"] for t, r in zip(a.rooms, rooms, strict=True)}
    for pt in a.exterior_portals:
        p = portal(s, b, room_of[pt.to_room], pt.name)
        assert p["is_locked"] == 0 and 0 <= p["damage"] <= 2 and p["is_open"] in (0, 1)
    assert ledger(s, f"layout:{b}") == 2 * len(a.exterior_portals), "a damage and an open draw per outside door"


# =========================================================================== GEO-04 things inside
def _loot(s, b, held):
    a = archetype(s, b)
    rooms = rooms_of(s, b)
    for t, r in zip(a.rooms, rooms, strict=True):
        containers = []
        for an, x in zip(t.anchors, anchors_of(s, r["place_id"]), strict=True):
            if an.container_item:
                [c] = all_rows(s, "SELECT * FROM items WHERE place_id = ? AND anchor_id = ? AND def_ref = ?",
                               (r["place_id"], x["anchor_id"], an.container_item))
                assert c["origin"] == "loot"
                containers.append(c["item_id"])
        inside = [i for c in containers for i in all_rows(s, "SELECT * FROM items WHERE container_id = ?", (c,))]
        loose = [i for i in all_rows(s, "SELECT * FROM items WHERE place_id = ? ORDER BY item_id", (r["place_id"],))
                 if i["item_id"] not in containers]
        found = inside + loose
        if not t.loot_table:
            assert found == [] and ledger(s, f"loot:{b}:{t.id}") == 0
            continue
        table = s.store.canon.get(t.loot_table)
        draws = ledger(s, f"loot:{b}:{t.id}")
        assert (draws - 1) % 3 == 0
        n = (draws - 1) // 3
        lo, hi = table.rolls
        if not held:
            lo, hi = 0, max(0, hi - 2)
        assert lo <= n <= hi, (t.id, n)
        first_anchor = anchors_of(s, r["place_id"])[0]["anchor_id"]
        assert all(i["anchor_id"] == first_anchor for i in loose), "what does not fit lies at the first anchor"
        for i in found:
            entries = [e for e in table.entries if e.item == i["def_ref"]]
            assert entries and i["origin"] == "loot", i["def_ref"]
            assert any(e.condition[0] <= i["condition"] <= e.condition[1] for e in entries)
            stackable = s.store.canon.get(i["def_ref"]).stackable
            assert i["qty"] == 1 if not stackable else any(e.qty[0] <= i["qty"] <= e.qty[1] for e in entries)
        for c in containers:
            cap = s.store.canon.get(one(s, "SELECT def_ref FROM items WHERE item_id = ?", (c,))["def_ref"]).container
            bulk = sum(s.store.canon.get(i["def_ref"]).bulk * i["qty"]
                       for i in all_rows(s, "SELECT * FROM items WHERE container_id = ?", (c,)))
            assert bulk <= cap.capacity_bulk
        if n == 0:
            assert found == []
        else:
            assert len(found) >= n


def test_containers_stand_where_the_archetype_puts_them_and_loot_is_rolled(gw):
    """GEO-04: a container at every anchor that names one; per room with a loot table, the table's
    number of rolls on the room's own stream, each a listed item in its condition range, put in the
    room's first container with room, else at its first anchor; single things one by one."""
    s = gw
    b = site(s, held=1)
    discover(s, b)
    _loot(s, b, held=1)


def test_a_picked_over_place_has_less_left(gw):
    """GEO-04: nobody held it — each table rolls from 0 to two fewer than its most."""
    s = gw
    b = site(s, held=0)
    discover(s, b)
    _loot(s, b, held=0)


def test_the_same_world_lays_out_the_same_building(made_world, tmp_path):
    """GEO-03: the layout is the building's own seed's — two copies of one world discover the same
    rooms, doors and things."""
    from as_engine.service import runs
    from as_engine.testing.fake_lm import FakeTransport

    got = []
    for k in range(2):
        shutil.copytree(made_world.root / "runs", tmp_path / f"runs{k}")
        s = runs.load_run(EngineConfig(runs_dir=str(tmp_path / f"runs{k}"), content_dir=str(REPO_PACKS)),
                          made_world.run_id, FakeTransport())
        try:
            b = site(s, held=0)
            discover(s, b)
            ids = [b] + [r["place_id"] for r in rooms_of(s, b)]
            marks = ",".join("?" * len(ids))
            doors = f"SELECT name, is_open, is_locked, damage FROM portals WHERE place_a IN ({marks}) " \
                    f"OR place_b IN ({marks}) ORDER BY portal_id"
            things = f"SELECT def_ref, qty, condition, place_id, container_id FROM items WHERE place_id IN ({marks}) " \
                     f"OR container_id IN (SELECT item_id FROM items WHERE place_id IN ({marks})) ORDER BY item_id"
            got.append(([(r["name"], r["held"]) for r in rooms_of(s, b)], all_rows(s, doors, ids + ids),
                        all_rows(s, things, ids + ids)))
        finally:
            s.store.close()
    assert got[0] == got[1]


# =========================================================================== OPS-05 on arrival
def test_walking_in_lays_it_out_and_shows_the_old_damage(gw):
    """OPS-05: the first person to arrive at an undiscovered building lays it out; an unheld one
    shows the old damage in its entrance room ("Old damage: this place was picked over long
    ago."); the dead of the district are put in it (world.infected.populate)."""
    s = gw
    b = site(s, held=0)
    a = archetype(s, b)
    who = s.store.meta("pc_actor_id")
    with s.store.transaction() as tx:
        evs = worldmove.on_arrival(tx, s.rng, who, b, now(s), None, turn(s))
    assert any(e.type == EventType.PLACE_DISCOVERED for e in evs)
    entrance = next(t for t in a.rooms if t.id == a.entrance_room)
    room = one(s, "SELECT place_id FROM places WHERE parent_id = ? AND name = ? ORDER BY place_id LIMIT 1",
               (b, entrance.name))["place_id"]
    [mark] = [r for r in rows(s, "TRACE_CREATED") if r["payload"]["place_id"] == room]
    assert (mark["payload"]["kind"], mark["payload"]["text"]) == ("damage", "Old damage: this place was picked over long ago.")
    assert json.loads(one(s, "SELECT props FROM places WHERE place_id = ?", (b,))["props"]).get("populated") is True
    with s.store.transaction() as tx:
        again = worldmove.on_arrival(tx, s.rng, who, b, now(s), None, turn(s))
    assert not any(e.type in (EventType.PLACE_DISCOVERED, EventType.TRACE_CREATED) for e in again)


def test_the_dead_do_not_open_up_buildings(gw):
    """OPS-05: on_arrival is not for infected bodies — a crowd walking past lays nothing out."""
    from as_engine.world import infected
    s = gw
    b = site(s, held=1)
    street = one(s, "SELECT place_id FROM places WHERE kind = 'street' ORDER BY place_id LIMIT 1")["place_id"]
    with s.store.transaction() as tx:
        body = infected.spawn(tx, s.rng, street, infected.SHAMBLER, now(s), turn(s), None)
        assert worldmove.on_arrival(tx, s.rng, body, b, now(s), None, turn(s)) == []
    assert one(s, "SELECT layout_generated FROM places WHERE place_id = ?", (b,))["layout_generated"] == 0
