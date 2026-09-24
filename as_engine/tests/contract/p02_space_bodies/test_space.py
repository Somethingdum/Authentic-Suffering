"""Places, portals, routes, positions (P2). Rules GEO-00..02 (physical/space.py).

Numbers are hand-checked on the metal_fence layout (tests/fixtures/scenarios/metal_fence.yaml):
Owen is 188 cm / 98 kg -> shoulder 30 + 98 x 0.2 = 49.6 cm; upright needs aperture h >= 169.2 cm.
"""

from __future__ import annotations

import math

import pytest

from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.physical import space
from as_engine.physical.space import PathLeg

pytestmark = pytest.mark.phase(2)


def d(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


# --------------------------------------------------------------------------- clearance
def test_shoulder_width():
    assert space.shoulder_cm(98) == pytest.approx(49.6)
    assert space.shoulder_cm(10) == pytest.approx(32.0) and space.shoulder_cm(200) == 65.0  # upper clamp
    assert space.shoulder_cm(98, "lurker") == pytest.approx(24.8)  # LUR_FLEX_SLITHER


def test_admits_reasons_on_the_real_layout(scenario):
    w = scenario("metal_fence")
    pc = w.id("pc")
    assert space.admits(w.store, w.id("storeroom_door"), pc) == (True, "upright")
    assert space.admits(w.store, w.id("back_door"), pc) == (True, "upright")
    assert space.admits(w.store, w.id("office_door"), pc) == (False, "closed")
    assert space.admits(w.store, w.id("front_door"), pc) == (False, "closed")
    assert space.admits(w.store, w.id("office_wall"), pc) == (False, "wall")
    assert space.admits(w.store, w.id("rear_fence"), pc) == (False, "wall"), "a fence is climbed, never walked through"


def _vent_world(fixture_packs, core_pack_dir, w_cm, h_cm):
    from as_engine.testing.scenario import load_scenario

    return load_scenario({
        "schema": "as.scenario.v1", "name": "vent", "seed": 1, "start": {"day": 30, "time": "12:00"},
        "places": [{"id": "a", "name": "A", "anchors": [{"id": "va", "name": "vent", "x": 1, "y": 1}]},
                   {"id": "b", "name": "B", "anchors": [{"id": "vb", "name": "vent", "x": 1, "y": 1}]}],
        "portals": [{"id": "vent", "a": "a", "b": "b", "anchor_a": "va", "anchor_b": "vb", "kind": "vent",
                     "name": "vent", "open": True, "w": w_cm, "h": h_cm}],
        "bodies": [{"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "a", "anchor": "va"},
                   {"id": "kid", "dossier": "core:actor/eli_voss", "place": "a", "anchor": "va"}],
    }, packs_root=fixture_packs, core_pack_dir=core_pack_dir)


@pytest.mark.parametrize("w_cm,h_cm,owen,eli", [
    (60, 50, (True, "crawl"), (True, "crawl")),       # 50 >= 45 but < 0.9 x height
    (60, 40, (False, "too_low"), (False, "too_low")),  # under 45 cm nobody crawls through
    (40, 120, (False, "too_narrow"), (True, "upright")),  # Eli: shoulder 35.2, 120 >= 0.9 x 132 = 118.8
    (45, 60, (False, "too_narrow"), (True, "crawl")),
])
def test_body_clearance(fixture_packs, core_pack_dir, w_cm, h_cm, owen, eli):
    w = _vent_world(fixture_packs, core_pack_dir, w_cm, h_cm)
    try:
        assert space.admits(w.store, w.id("vent"), w.id("pc")) == owen
        assert space.admits(w.store, w.id("vent"), w.id("kid")) == eli
    finally:
        w.store.close()


# --------------------------------------------------------------------------- points and routes
def test_portal_point_is_the_anchor_or_the_centre(scenario, fixture_packs, core_pack_dir):
    w = scenario("metal_fence")
    assert space.portal_point(w.store, w.id("storeroom_door"), w.id("storeroom")) == (7.5, 0.5)
    assert space.portal_point(w.store, w.id("storeroom_door"), w.id("sales_floor")) == (13.5, 8.5)
    with pytest.raises(ValueError):
        space.portal_point(w.store, w.id("storeroom_door"), w.id("alley"))
    p = scenario("pump_settlement")
    # pump_door has no anchor on the yard side -> the yard's centre (40 x 30)
    assert space.portal_point(p.store, p.id("pump_door"), p.id("yard")) == (20.0, 15.0)


def test_path_through_open_doors(scenario):
    w = scenario("metal_fence")
    legs = space.path(w.store, w.id("pc"), w.id("alley"), w.id("back_door_out"))
    assert [(l.portal_id, l.place_id) for l in legs] == [
        (w.id("storeroom_door"), w.id("storeroom")), (w.id("back_door"), w.id("alley")), (None, w.id("alley"))]
    assert legs[0].distance_m == pytest.approx(d(6, 4, 13.5, 8.5))   # counter -> storeroom doorway
    assert legs[1].distance_m == pytest.approx(d(7.5, 0.5, 4, 4.5))  # doorway -> back door
    assert legs[2].distance_m == pytest.approx(0.0)                   # the destination IS the door's far side


def test_path_same_place_and_toward_the_counter(scenario):
    w = scenario("metal_fence")
    assert space.path(w.store, w.id("pc"), w.id("sales_floor"), w.id("rear_cover")) == [
        PathLeg(None, w.id("sales_floor"), pytest.approx(d(6, 4, 12.5, 8)))]
    legs = space.path(w.store, w.id("nita"), w.id("sales_floor"), w.id("counter"))
    assert [l.portal_id for l in legs] == [w.id("back_door"), w.id("storeroom_door"), None]
    assert sum(l.distance_m for l in legs) == pytest.approx(d(9, 3, 6, 0.5) + d(4, 4.5, 7.5, 0.5) + d(13.5, 8.5, 6, 4))


def test_closed_locked_and_barricaded_portals(scenario):
    w = scenario("metal_fence")
    pc = w.id("pc")
    assert space.path(w.store, pc, w.id("office"), w.id("desk")) is None, "the office door is shut"
    legs = space.path(w.store, pc, w.id("office"), w.id("desk"), allow_closed=True)
    assert [l.portal_id for l in legs] == [w.id("office_door"), None]
    assert legs[1].distance_m == pytest.approx(d(1, 0.3, 2, 1.2))
    # the front door is locked AND barricaded, the front window barricaded: no way out even if you
    # are willing to open things
    assert space.path(w.store, pc, w.id("street")) is None
    assert space.path(w.store, pc, w.id("street"), allow_closed=True) is None
    assert space.path(w.store, pc, w.id("back_lot"), allow_closed=True) is None, "fences are climbed"


def test_path_rejects_an_anchor_in_another_place(scenario):
    w = scenario("metal_fence")
    with pytest.raises(ValueError):
        space.path(w.store, w.id("pc"), w.id("alley"), w.id("counter"))


def test_point_distance_goes_through_anything(scenario):
    """Distance, not walkability: walls, fences and closed portals all count (GEO-00)."""
    w = scenario("metal_fence")
    assert space.point_distance(w.store, w.id("pc"), w.id("mara")) == pytest.approx(d(6, 4, 3, 0.5))
    # counter -> office door (closed) -> boarded window (closed) -> fence sheet -> fence far side
    via_office = d(6, 4, 1, 8.5) + d(1, 0.3, 2, 2.9) + d(1.5, 0.3, 5, 5.8) + 0.0
    assert space.point_distance(w.store, w.id("pc"), w.id("stranger")) == pytest.approx(via_office)
    # June (shelves) to Eli (cot) through the office wall
    assert space.point_distance(w.store, w.id("june"), w.id("eli")) == pytest.approx(d(2, 2, 0.3, 2.5) + d(3.8, 1.5, 3.2, 2.4))


def test_a_route_never_enters_a_place_twice(scenario):
    """GEO-00 (its P10 line): a route enters each place at most once and never goes back into the
    place it starts in. A side room whose two doors both open at its centre (no anchor on its side)
    joins the two ends of a 100 m street for nothing: out of the street into it and back in is not a
    way along the street — for path and point_distance alike."""
    w = scenario("metal_fence")
    at = w.store.query_one("SELECT now_ms FROM world_clock")[0]

    def ins(table, **values):
        return WriteRecord(op=WriteOp.INSERT, table=table, values=values)

    door = {"kind": "door", "is_open": 1, "aperture_w_cm": 90, "aperture_h_cm": 210}
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.PLACE_DISCOVERED, writer="physical.space", at=at, turn_index=0,
                              payload={"test": "a long street with a side room"}, writes=[
            ins("places", place_id="plc_t_start", kind="room", name="Start room", width_m=4, depth_m=4),
            ins("places", place_id="plc_t_street", kind="street", name="Long street", width_m=100, depth_m=4, indoor=0),
            ins("places", place_id="plc_t_side", kind="room", name="Side room", width_m=10, depth_m=10),
            ins("places", place_id="plc_t_far", kind="room", name="Far room", width_m=4, depth_m=4),
            ins("anchors", anchor_id="anc_t_west", place_id="plc_t_street", name="the west end", kind="feature", x_m=1.0,
                y_m=2.0),
            ins("anchors", anchor_id="anc_t_east", place_id="plc_t_street", name="the east end", kind="feature", x_m=99.0,
                y_m=2.0),
            ins("portals", portal_id="prt_t_1", place_a="plc_t_start", place_b="plc_t_street", anchor_b="anc_t_west",
                name="the start door", **door),
            ins("portals", portal_id="prt_t_2", place_a="plc_t_street", place_b="plc_t_side", anchor_a="anc_t_west",
                name="the side room's west door", **door),
            ins("portals", portal_id="prt_t_3", place_a="plc_t_street", place_b="plc_t_side", anchor_a="anc_t_east",
                name="the side room's east door", **door),
            ins("portals", portal_id="prt_t_4", place_a="plc_t_street", place_b="plc_t_far", anchor_a="anc_t_east",
                name="the far door", **door)]))
        tx.commit_event(space.move_event(tx, w.id("pc"), "plc_t_start", None, 2.0, 2.0, at, None, 0))
        tx.commit_event(space.move_event(tx, w.id("mara"), "plc_t_far", None, 2.0, 2.0, at, None, 0))
    legs = space.path(w.store, w.id("pc"), "plc_t_far")
    assert [(l.portal_id, l.place_id) for l in legs] == [("prt_t_1", "plc_t_street"), ("prt_t_4", "plc_t_far"),
                                                         (None, "plc_t_far")]
    assert legs[1].distance_m == pytest.approx(98.0)
    assert space.point_distance(w.store, w.id("pc"), w.id("mara")) == pytest.approx(98.0)
    with w.store.transaction() as tx:  # from the street itself: not back into it either
        tx.commit_event(space.move_event(tx, w.id("pc"), "plc_t_street", None, 1.0, 2.0, at, None, 0))
    legs = space.path(w.store, w.id("pc"), "plc_t_far")
    assert [(l.portal_id, l.place_id) for l in legs] == [("prt_t_4", "plc_t_far"), (None, "plc_t_far")]
    assert legs[0].distance_m == pytest.approx(98.0)


def test_places_near(scenario):
    w = scenario("metal_fence")
    S, ST, OF, AL, BL, STR = (w.id(x) for x in ("sales_floor", "storeroom", "office", "alley", "back_lot", "street"))
    assert space.places_near(w.store, S, 1) == sorted([ST, OF, STR])
    assert space.places_near(w.store, S, 2) == sorted([ST, OF, STR]) + [AL]
    assert space.places_near(w.store, S, 3)[-1] == BL


# --------------------------------------------------------------------------- events
def test_move_event_is_built_not_committed(scenario):
    w = scenario("metal_fence")
    alice, floor, cover = w.id("alice"), w.id("sales_floor"), w.id("rear_cover")
    with w.store.transaction() as tx:
        ev = space.move_event(tx, alice, floor, cover, 12.5, 8.0, at=1000, cause_event_id=None, turn_index=0)
        assert ev.type == EventType.MOVE and ev.writer == "physical.space" and ev.event_id is None
        assert ev.payload == {"body_id": alice, "from_place": floor, "to_place": floor, "from_anchor": w.id("behind_counter"),
                              "to_anchor": cover, "x_m": 12.5, "y_m": 8.0, "hidden": False}
        assert ev.actor_id == alice
        before = tx.query_one("SELECT anchor_id FROM positions WHERE body_id = ?", (alice,))[0]
        assert before == w.id("behind_counter"), "building an event changes nothing"
        tx.commit_event(ev)
    pos = w.store.query_one("SELECT * FROM positions WHERE body_id = ?", (alice,))
    assert (pos["anchor_id"], pos["x_m"], pos["y_m"], pos["since_ms"]) == (cover, 12.5, 8.0, 1000)


def test_a_move_can_hide_and_any_other_move_reveals(scenario):
    w = scenario("metal_fence")
    alice, floor, cover = w.id("alice"), w.id("sales_floor"), w.id("rear_cover")
    hidden = lambda: w.store.query_one("SELECT hidden FROM positions WHERE body_id = ?", (alice,))[0]  # noqa: E731
    with w.store.transaction() as tx:
        ev = tx.commit_event(space.move_event(tx, alice, floor, cover, 12.5, 8.0, at=1000, cause_event_id=None,
                                              turn_index=0, hidden=True))
    assert ev.payload["hidden"] is True and hidden() == 1
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, alice, floor, cover, 12.5, 8.0, at=2000, cause_event_id=None, turn_index=0))
    assert hidden() == 0, "staying put but moving again gives her away"


def test_move_to_an_anchor_elsewhere_is_refused(scenario):
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        with pytest.raises(ValueError):
            space.move_event(tx, w.id("alice"), w.id("sales_floor"), w.id("dumpster"), 9, 3, at=0, cause_event_id=None, turn_index=0)


def test_portal_changes_are_orthogonal_and_guarded(scenario):
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        ev = tx.commit_event(space.portal_change_event(tx, w.id("office_door"), {"is_open": True}, 0, w.id("mara"), None, 0))
        assert ev.payload["changes"] == {"is_open": 1} and ev.payload["before"] == {"is_open": 0}
        # locked, barricaded front door: it can be damaged or unlocked, but not opened while barricaded
        with pytest.raises(ValueError):
            space.portal_change_event(tx, w.id("front_door"), {"is_open": True}, 0, None, None, 0)
        tx.commit_event(space.portal_change_event(tx, w.id("front_door"), {"damage": 1, "is_locked": False}, 0, None, None, 0))
        with pytest.raises(ValueError):
            space.portal_change_event(tx, w.id("back_door"), {"barricade": 1}, 0, None, None, 0)  # it stands open
        with pytest.raises(ValueError):
            space.portal_change_event(tx, w.id("rear_fence"), {"is_open": True}, 0, None, None, 0)
        tx.commit_event(space.portal_change_event(tx, w.id("rear_fence"), {"damage": 2}, 0, None, None, 0))
        with pytest.raises(ValueError):
            space.portal_change_event(tx, w.id("office_door"), {"kind": "hole"}, 0, None, None, 0)
    door = w.store.query_one("SELECT is_open, is_locked, barricade, damage FROM portals WHERE portal_id = ?", (w.id("front_door"),))
    assert tuple(door) == (0, 0, 2, 1)
    assert space.admits(w.store, w.id("office_door"), w.id("pc")) == (True, "upright")
