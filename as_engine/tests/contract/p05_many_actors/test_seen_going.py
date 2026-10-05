"""Seen going (D-141). Rule VIS-06 (sense/optics.py leaving) and mind/perception.py's MOVE.

A body was seen where it was after it moved: whoever walked through a shut door, or into a dark room, was never
seen leaving by the people left behind — June could watch Mara cross the floor to the storeroom and not see her
go. Now those left behind see the body go at the doorway it went through.
"""

from __future__ import annotations

import pytest

from as_engine.mind import perception
from as_engine.physical import space
from as_engine.sense import optics

pytestmark = pytest.mark.phase(5)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def lit_floor(w):
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("sales_floor"), None, 6.0, 5.0, t, None, 0))
    return t + 1000


def go(w, who, at, *, watcher="june"):
    with w.store.transaction() as tx:
        ev = tx.commit_event(space.move_event(tx, w.id(who), w.id("storeroom"), None, 2.0, 1.0, at, None, 0))
        perception.compile_aftermath(tx, w.id(watcher), [ev], at + 200, 0)
        return ev, tx.query("SELECT text, source_id FROM percept_log WHERE holder_id = ? AND event_id = ?",
                            (w.id(watcher), ev.event_id))


def test_june_sees_mara_go(scenario):
    w = scenario("metal_fence")
    t = lit_floor(w)
    with w.store.transaction() as tx:
        assert optics.visibility(tx, w.id("june"), w.id("mara"), t) != "none"
    ev, seen = go(w, "mara", t)
    with w.store.transaction() as tx:
        assert optics.visibility(tx, w.id("june"), w.id("mara"), t) == "none", "where she went, June cannot see"
        assert optics.leaving(tx, w.id("june"), w.id("mara"), w.id("sales_floor"), w.id("storeroom"), t) == "clear"
    assert [(r[0], r[1]) for r in seen] == [("Mara moves away.", w.id("mara"))]


def test_nobody_left_to_see(scenario):
    """Asleep, or somewhere else: nobody sees anyone go."""
    w = scenario("metal_fence")
    t = lit_floor(w)
    with w.store.transaction() as tx:
        assert optics.leaving(tx, w.id("eli"), w.id("mara"), w.id("sales_floor"), w.id("storeroom"), t) == "none"
    w.store.conn.execute("UPDATE bodies SET awareness = 'asleep' WHERE body_id = ?", (w.id("june"),))
    _ev, seen = go(w, "mara", t)
    assert seen == []
