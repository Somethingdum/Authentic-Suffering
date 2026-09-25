"""Parkour: height, and the lines only a few can take (P12). Rules PARKOUR-01..08, FALL-01, INF-20;
DECISIONS D-108 (physical/space.py; physical/bodies.py fall; action/effects.py climb_face, jump_gap,
drop_down, flee; mind/affordance.py; narration/location.py; world/infected.py; affordances
movement.yaml; buildings roofs; scenario rooftops).

The owner: "You also have to account for how to simulate Addison Flores. She parkours." Her card:
"Goes up and away — to a ledge, a fence, a roof — before she has decided anything; her feet decide
first." The world she moves in (tests/fixtures/scenarios/rooftops.yaml): the market roof (4.5 m), a
1.6 m gap up to the warehouse roof (6 m), a 2.8 m gap on to the apartments (6.5 m), a drainpipe and
the roof edges down to Hardy Street, one of the dead at the foot of the pipe and a runner in the
street.
"""

from __future__ import annotations

import json

import helpers
import pytest

from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.contracts.events import Event, EventType
from as_engine.mind.affordance import enumerate_affordances
from as_engine.narration.location import describe
from as_engine.physical import bodies, space
from as_engine.world import infected

pytestmark = pytest.mark.phase(12)

HORIZON = 60_000


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def run(w, *intents, rng=None):
    t = now(w)
    with w.store.transaction() as tx:
        return resolve_wave(tx, rng or w.rng, barrier(tx, list(intents)), t, 0, horizon_ms=t + HORIZON)


def one(evs, type_):
    got = [e for e in evs if e.type == type_]
    assert len(got) == 1, [(e.type, e.payload) for e in evs]
    return got[0]


def where(w, local="pc"):
    return dict(w.store.query_one("SELECT * FROM positions WHERE body_id = ?", (w.id(local),)))


def wounds(w, local="pc"):
    return [(r[0], r[1], r[2]) for r in w.store.query("SELECT anatomy, type, severity FROM wounds WHERE body_id = ? "
                                                      "ORDER BY wound_id", (w.id(local),))]


def menu(w, local="pc"):
    with w.store.transaction() as tx:
        a = enumerate_affordances(tx, w.id(local), tx.canon.all("affordance"), now(w), 0)
    return a


# =========================================================================== height and the lines
def test_the_roofs_have_height(scenario):
    """PARKOUR-01/02: elevations, drops and rises; nobody walks a climb, a gap or an edge."""
    w = scenario("rooftops")
    s = w.store
    assert s.query_one("SELECT kind, elevation_m FROM places WHERE place_id = ?", (w.id("market_roof"),))[:] == ("roof", 4.5)
    assert space.drop_m(s, w.id("market_gap"), w.id("market_roof")) == 4.5, "into the alley"
    assert space.rise_m(s, w.id("market_gap"), w.id("market_roof")) == 1.5
    assert space.drop_m(s, w.id("market_edge"), w.id("market_roof")) == 4.5
    for pid in ("drainpipe", "market_gap", "market_edge"):
        assert space.admits(s, w.id(pid), w.id("pc")) == (False, "wall")
    assert space.path(s, w.id("pc"), w.id("warehouse_roof")) is None, "no walking there"


def test_addison_sees_the_lines(scenario):
    """PARKOUR-04..06 on the menu: the pipe, the gap, the edge — and nothing to open or walk through."""
    w = scenario("rooftops")
    got = {(o.def_id, o.target_id) for o in menu(w).pool}
    assert ("climb_face", w.id("drainpipe")) in got
    assert ("jump_gap", w.id("market_gap")) in got
    assert ("drop_down", w.id("market_edge")) in got
    for pid in ("drainpipe", "market_gap", "market_edge"):
        assert not {d for d, t in got if t == w.id(pid)} & {"move_through_portal", "open_portal", "force_portal", "climb_obstacle"}


def test_the_where_panel_says_how_hard(scenario):
    """narration.location: how high, how far, which way."""
    w = scenario("rooftops")
    with w.store.transaction() as tx:
        v = describe(tx, w.id("pc"), now(w))
    words = {x.label: x.state_words for x in v.exits}
    assert words["drainpipe"] == ["a climb of about 5 metres"]
    assert words["gap between the roofs"] == ["about 1.6 metres across, higher on the far side"]
    assert words["front edge of the market roof"] == ["a drop of about 5 metres"]
    with w.store.transaction() as tx:   # from the street the edge is out of reach
        tx.commit_event(space.move_event(tx, w.id("pc"), w.id("street"), w.id("market_front"), 6, 0.5, now(w), None, 0))
    with w.store.transaction() as tx:
        v = describe(tx, w.id("pc"), now(w))
    words = {x.label: x.state_words for x in v.exits}
    assert words["front edge of the market roof"] == ["about 5 metres up, out of reach"]
    assert words["drainpipe"] == ["a climb of about 5 metres"]


@pytest.mark.parametrize("portal,frm,key,cls", [
    ("drainpipe", "street", "climb.class", 3), ("drainpipe", "market_roof", "climb.class", 2),
    ("market_gap", "market_roof", "gap.class", 4), ("market_gap", "warehouse_roof", "gap.class", 2),
    ("long_gap", "warehouse_roof", "gap.class", 5), ("market_edge", "market_roof", "drop.class", 2),
    ("warehouse_edge", "warehouse_roof", "drop.class", 3)])
def test_how_hard_each_line_is(scenario, portal, frm, key, cls):
    """action.effects resistance keys (D-108)."""
    from as_engine.action._impl_effects import _parkour_class
    w = scenario("rooftops")
    with w.store.transaction() as tx:
        assert _parkour_class(tx, key, w.id(portal), w.id(frm)) == cls


# =========================================================================== the moves
def test_she_makes_the_jump(scenario):
    """PARKOUR-05 CLEAN: across, on her feet."""
    w = scenario("rooftops")
    evs = run(w, helpers.make_intent(w, "pc", "jump_gap", target="market_gap", destination="warehouse_roof"),
              rng=helpers.ScriptedRng(1))
    chk = one(evs, "CHECK_RESOLVED").payload
    assert chk["resistance"] == 4 and chk["band"] == "clean"
    assert one(evs, "ACTION_COMPLETE").payload["result"] == "done"
    assert where(w)["place_id"] == w.id("warehouse_roof") and where(w)["anchor_id"] == w.id("warehouse_west")
    assert wounds(w) == []


def test_she_balks_at_the_edge(scenario):
    """PARKOUR-05 FAIL: pulled up short; no progress, no harm."""
    w = scenario("rooftops")
    evs = run(w, helpers.make_intent(w, "pc", "jump_gap", target="market_gap", destination="warehouse_roof"),
              rng=helpers.ScriptedRng(8))
    assert one(evs, "CHECK_RESOLVED").payload["band"] == "fail"
    assert one(evs, "ACTION_COMPLETE").payload["result"] == "balked"
    assert where(w)["place_id"] == w.id("market_roof") and wounds(w) == []


def test_short_is_a_fall_into_the_alley(scenario):
    """PARKOUR-05 BREAK, FALL-01: 4.5 m into the alley — a leg and an arm, and she is down."""
    w = scenario("rooftops")
    evs = run(w, helpers.make_intent(w, "pc", "jump_gap", target="market_gap", destination="warehouse_roof"),
              rng=helpers.ScriptedRng(10, True))
    assert one(evs, "ACTION_COMPLETE").payload["result"] == "fell"
    assert where(w)["place_id"] == w.id("alley")
    assert wounds(w) == [("leg_l", "blunt", "significant"), ("arm_l", "blunt", "minor")]
    assert w.store.query_one("SELECT posture FROM bodies WHERE body_id = ?", (w.id("pc"),))[0] == "lying"
    noise = [e for e in evs if e.type == EventType.NOISE and e.payload.get("kind") == "fall"]
    assert noise and noise[0].payload["source_db"] == pytest.approx(55 + 3 * 4.5)


def test_a_roll_takes_the_drop_out(scenario):
    """PARKOUR-06: a clean drop and roll from 4.5 m costs nothing; a bad one takes all of it; the
    worst — only from higher, she is that good — lands head first, one band worse."""
    w = scenario("rooftops")
    run(w, helpers.make_intent(w, "pc", "drop_down", target="market_edge", destination="street"), rng=helpers.ScriptedRng(1))
    assert where(w)["place_id"] == w.id("street") and wounds(w) == []
    w2 = scenario("rooftops")
    evs = run(w2, helpers.make_intent(w2, "pc", "drop_down", target="market_edge", destination="street"),
              rng=helpers.ScriptedRng(10, False))
    assert one(evs, "CHECK_RESOLVED").payload["band"] == "fail"
    assert wounds(w2) == [("leg_r", "blunt", "significant"), ("arm_r", "blunt", "minor")], "all 4.5 m of it"
    w3 = scenario("rooftops")
    with w3.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w3.id("pc"), w3.id("warehouse_roof"), w3.id("warehouse_front_edge"), 10, 0.3,
                                         now(w3), None, 0))
    evs = run(w3, helpers.make_intent(w3, "pc", "drop_down", target="warehouse_edge", destination="street"),
              rng=helpers.ScriptedRng(10, False))
    assert one(evs, "CHECK_RESOLVED").payload["band"] == "break"
    assert one(evs, "ACTION_COMPLETE").payload["result"] == "fell"
    assert wounds(w3) == [("leg_r", "crush", "severe"), ("chest", "blunt", "significant")], "6 m, head first"


def test_down_the_drainpipe(scenario):
    """PARKOUR-04: climbing down is one class easier; she lands at its foot."""
    w = scenario("rooftops")
    evs = run(w, helpers.make_intent(w, "pc", "climb_face", target="drainpipe", destination="street"),
              rng=helpers.ScriptedRng(1))
    assert one(evs, "CHECK_RESOLVED").payload["resistance"] == 2
    assert where(w)["place_id"] == w.id("street") and where(w)["anchor_id"] == w.id("pipe_foot")


@pytest.mark.parametrize("h,got", [
    (1.5, []), (3.0, [("foot_l", "blunt", "minor")]),
    (5.0, [("leg_l", "blunt", "significant"), ("arm_l", "blunt", "minor")]),
    (8.0, [("leg_l", "crush", "severe"), ("chest", "blunt", "significant")]),
    (20.0, [("head", "blunt", "catastrophic")])])
def test_how_a_fall_hurts(scenario, h, got):
    """FALL-01, by height; twenty metres kills."""
    w = scenario("rooftops")
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=now(w), turn_index=0, payload={"what": "fall"}))
        bodies.fall(tx, helpers.ScriptedRng(True), w.id("pc"), h, now(w), 0, c.event_id)
    assert wounds(w) == got
    alive = w.store.query_one("SELECT alive FROM bodies WHERE body_id = ?", (w.id("pc"),))[0]
    assert alive == (0 if h >= 15 else 1)


# =========================================================================== her feet decide first
def test_her_feet_decide_first(scenario):
    """PARKOUR-07: in the street with the dead at the pipe, fleeing means up."""
    w = scenario("rooftops")
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("pc"), w.id("street"), w.id("escape_foot"), 26, 0.5, now(w), None, 0))
    evs = run(w, helpers.make_intent(w, "pc", "flee_threat", target="runner"), rng=helpers.ScriptedRng(1))
    assert where(w)["place_id"] == w.id("market_roof"), "up the drainpipe, not down the street"
    assert one(evs, "CHECK_RESOLVED").payload["resistance"] == 3


# =========================================================================== the dead
def test_the_dead_below_cannot_follow(scenario):
    """INF-20: a shambler has no way up; a runner has the drainpipe."""
    w = scenario("rooftops")
    s = w.store
    assert space.path(s, w.id("shambler"), w.id("market_roof")) is None
    pk = s.canon.find("infected", "ZOMBIE_VARIANT_ID_RUNNER01").parkour
    assert pk is not None and s.canon.find("infected", "ZOMBIE_ARCHETYPE_SHAMBLER01").parkour is None
    legs = space.path(s, w.id("runner"), w.id("market_roof"), parkour={"climb_cm": pk.climb_cm, "gap_cm": pk.gap_cm,
                                                                       "edge_m": pk.edge_m})
    assert [leg.portal_id for leg in legs if leg.portal_id] == [w.id("drainpipe")]
    assert space.path(s, w.id("runner"), w.id("apartment_roof")) is not None, "anyone walks a fire escape"


@pytest.mark.parametrize("falls", [False, True])
def test_the_runner_climbs_and_sometimes_falls(scenario, falls):
    """INF-20: a 25-40% chance of a spectacular fall on the way up."""
    w = scenario("rooftops")
    r = w.id("runner")
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, r, w.id("street"), w.id("pipe_foot"), 2, 0.3, now(w), None, 0))
        fired = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=now(w), turn_index=0, payload={"what": "step"}))
        x, y = space.portal_point(tx, w.id("drainpipe"), w.id("market_roof"))
        row = {"queue_id": "que_test", "type": "INFECTED_STEP", "due_at": now(w),
               "payload": json.dumps({"body_id": r, "leg": {"to_place": w.id("market_roof"), "x_m": x, "y_m": y,
                                                            "portal_id": w.id("drainpipe")}})}
        infected.step(tx, helpers.ScriptedRng(30, falls, True, True, True), row, fired, 0)
    if falls:
        assert where(w, "runner")["place_id"] == w.id("street")
        assert wounds(w, "runner") == [("foot_l", "blunt", "minor")], "half the pipe: 2.25 m"
    else:
        assert where(w, "runner")["place_id"] == w.id("market_roof") and wounds(w, "runner") == []


# =========================================================================== roofs in the world
def test_roofs_come_with_their_buildings(scenario):
    """PARKOUR-08: a roof with its hatch, its drainpipe and its edge; the block's roofs get a gap."""
    w = scenario("rooftops")
    s = w.store
    s.rules = s.rules.model_copy(update={"parkour": s.rules.parkour.model_copy(update={"gap_chance": 1.0})})
    s.conn.execute("INSERT INTO zones (zone_id, name, kind) VALUES ('zon_test', 'Hardy block', 'downtown')")
    for pid, name in (("plc_site_a", "Delgado's Market"), ("plc_site_b", "Corner Grocery")):
        s.conn.execute("INSERT INTO places (place_id, zone_id, kind, name, archetype_ref, indoor, material) "
                       "VALUES (?, 'zon_test', 'building', ?, 'core:building/corner_market', 0, 'open_air')", (pid, name))
        s.conn.execute("INSERT INTO anchors (anchor_id, place_id, name, kind, x_m, y_m) VALUES (?, ?, 'forecourt', 'feature', 5, 5)",
                       (pid.replace("plc", "anc"), pid))
    with s.transaction() as tx:
        space.discover_layout(tx, w.rng, "plc_site_a", now(w), 0)
        space.discover_layout(tx, w.rng, "plc_site_b", now(w), 0)
    roof = dict(s.query_one("SELECT * FROM places WHERE parent_id = 'plc_site_a' AND kind = 'roof'"))
    assert (roof["name"], roof["elevation_m"], roof["indoor"]) == ("Delgado's Market roof", 4.5, 0)
    kinds = {r[0]: r[1] for r in s.query("SELECT kind, height_cm FROM portals WHERE place_a = ? OR place_b = ?",
                                        (roof["place_id"], roof["place_id"]))}
    assert kinds.get("climb") == 450 and kinds.get("edge") == 450 and "hole" in kinds and "gap" in kinds
    gap = dict(s.query_one("SELECT * FROM portals WHERE kind = 'gap' AND (place_a = ? OR place_b = ?)",
                           (roof["place_id"], roof["place_id"])))
    lo, hi = s.rules.parkour.gap_cm
    assert lo <= gap["gap_cm"] <= hi and gap["below_id"] == "plc_site_a"
