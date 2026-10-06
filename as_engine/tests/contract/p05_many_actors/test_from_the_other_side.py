"""From the other side (D-281). physical/space.py barricade_side; mind/affordance.py (unbarricade_portal binding);
action/effects.py barricade_portal (the side it is built on) and EFF-02 'wrong_side'.

The store's front door is barricaded from inside, furniture stacked against it. A stranger out on Maple Street was
offered "Clear the barricade from the front door" — no check, half a minute — as if the sofa were on his side of the
door: any hold's barricades came down from outside for the asking. A barricade is cleared from the side it was built
on; from the other side it is forced, against the check. A barricade put up from the alley is the alley's to clear.
"""

from __future__ import annotations

import pytest

import helpers
from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.physical import space

pytestmark = pytest.mark.phase(5)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def to(w, who, place, x, y):
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id(who), w.id(place), None, x, y, now(w), None, 0))


def ways(w, who, portal):
    t = now(w)
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(who), t, 0)
        a = enumerate_affordances(tx, w.id(who), w.canon.all("affordance"), t + 100, 0)
    return {o.def_id for o in [*a.options, *a.pool] if o.target_id == w.id(portal)}


def run(w, who, def_id, portal):
    t = now(w)
    with w.store.transaction() as tx:
        return resolve_wave(tx, w.rng, barrier(tx, [helpers.make_intent(w, who, def_id, target=portal)]), t, 0,
                            horizon_ms=t + 1_800_000)


def test_built_inside_cleared_inside(scenario):
    w = scenario("metal_fence")
    assert space.barricade_side(w.store, w.id("front_door")) == w.id("sales_floor"), "there from the start: the indoor side"
    assert "unbarricade_portal" in ways(w, "mara", "front_door")
    to(w, "nita", "street", 7.0, 1.0)
    got = ways(w, "nita", "front_door")
    assert "unbarricade_portal" not in got and "force_portal" in got, got


def test_cleared_from_outside_is_blocked(scenario):
    w = scenario("metal_fence")
    to(w, "nita", "street", 7.0, 1.0)
    evs = run(w, "nita", "unbarricade_portal", "front_door")
    blocked = [e for e in evs if e.type.value == "ACTION_BLOCKED"]
    assert blocked and blocked[0].payload["cause"] == "wrong_side"
    assert w.store.query_one("SELECT barricade FROM portals WHERE portal_id = ?", (w.id("front_door"),))[0] == 2


def test_put_up_from_the_alley(scenario):
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        tx.commit_event(space.portal_change_event(tx, w.id("back_door"), {"is_open": False}, now(w), None, None, 0))
    to(w, "nita", "alley", 6.0, 1.0)
    evs = run(w, "nita", "barricade_portal", "back_door")
    assert [e for e in evs if e.type.value == "PORTAL_CHANGE"][0].payload["side"] == w.id("alley")
    assert space.barricade_side(w.store, w.id("back_door")) == w.id("alley")
    assert "unbarricade_portal" in ways(w, "nita", "back_door")
    to(w, "alice", "storeroom", 5.0, 3.0)
    assert "unbarricade_portal" not in ways(w, "alice", "back_door"), "it is the alley's to clear"
