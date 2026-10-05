"""News is new (D-176). Rule SEL-03 unique_info (turn/select.py salience_flags).

Nita alone sees the man in the lot: that is news, and it makes her mind matter more this turn (with D-175, the
main model thinks for her). But she saw him the turn before too, and the turn before that — and every five
minutes the same man counted as news nobody else had, so she was the main model's every turn for an hour of
watching him stand there.
"""

from __future__ import annotations

import pytest

from as_engine.mind import perception
from as_engine.physical import space
from as_engine.turn import select

pytestmark = pytest.mark.phase(5)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def sees(w, turn, at):
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id("nita"), at, turn)
        return select.salience_flags(tx, w.id("nita"), [w.id("nita")], w.id("pc"), turn, at)["unique_info"]


def test_the_man_in_the_lot(scenario):
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("back_lot"), {"light_level": 4}, "test", t, None, 0)
    assert sees(w, 1, t + 1000), "the first time she sees him, it is news"
    assert not sees(w, 2, t + 301_000), "the same man the next turn is not"
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("stranger"), w.id("street"), None, 2.0, 2.0, t + 400_000, None, 2))
    assert not sees(w, 3, t + 601_000)
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("stranger"), w.id("back_lot"), None, 5.0, 0.3, t + 700_000, None, 3))
    assert sees(w, 4, t + 901_000), "back after she lost sight of him: news again"
