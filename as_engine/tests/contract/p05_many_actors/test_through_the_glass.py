"""Through the glass (D-280). mind/affordance.py (portal bindings: climb_obstacle, vault_obstacle); action/effects.py
EFF-02 'portal_closed'.

Mara keeps watch at the store's front window: shut, boarded over twice, the dead on the far side of it. She was
offered "Climb over the boarded front window" — and climbing ignores whether a way admits anyone (it is how a fence
is crossed), so a good roll put her out on Maple Street through glass and boards. A window is climbed through its
opening: open and unboarded, or not at all. A fence is still climbed.
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

OVER = ("climb_obstacle", "vault_obstacle")


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def ways_over(w, who):
    t = now(w)
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(who), t, 0)
        a = enumerate_affordances(tx, w.id(who), w.canon.all("affordance"), t + 100, 0)
    return {(o.def_id, w.local(o.target_id)): o.label for o in [*a.options, *a.pool] if o.def_id in OVER}


def window(w, **changes):
    with w.store.transaction() as tx:
        tx.commit_event(space.portal_change_event(tx, w.id("front_window_pane"), changes, now(w), None, None, 0))


def test_not_through_the_boards(scenario):
    w = scenario("metal_fence")
    assert not {k for k in ways_over(w, "mara") if k[1] == "front_window_pane"}, "shut and boarded twice"
    window(w, barricade=0)
    assert not {k for k in ways_over(w, "mara") if k[1] == "front_window_pane"}, "shut: glass is not a way out"


def test_through_its_opening(scenario):
    w = scenario("metal_fence")
    window(w, barricade=0, is_open=True)
    got = ways_over(w, "mara")
    assert ("climb_obstacle", "front_window_pane") in got, got


def test_shut_before_she_got_there(scenario):
    w = scenario("metal_fence")
    window(w, barricade=0, is_open=True)
    it = helpers.make_intent(w, "mara", "climb_obstacle", target="front_window_pane")
    window(w, is_open=False)
    t = now(w)
    with w.store.transaction() as tx:
        evs = resolve_wave(tx, w.rng, barrier(tx, [it]), t, 0, horizon_ms=t + 1_800_000)
    blocked = [e for e in evs if e.type.value == "ACTION_BLOCKED"]
    assert blocked and blocked[0].payload["cause"] == "portal_closed"
    assert w.store.query_one("SELECT place_id FROM positions WHERE body_id = ?", (w.id("mara"),))[0] == w.id("sales_floor")


def test_a_fence_is_still_climbed(scenario):
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("nita"), w.id("alley"), None, 5.0, 5.4, now(w), None, 0))
    got = ways_over(w, "nita")
    assert ("climb_obstacle", "rear_fence") in got, got
