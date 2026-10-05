"""Watching on (D-230). action/effects.py ACTION_START payload 'seen'; action.resolve.

Someone who goes on watching, waiting or standing guard turn after turn was seen to start it again every turn: with
the player in a room of twelve, every quiet turn told him twelve times over that "a man stops and watches", and the
Writer got the same scenery as news. A holding act carried on — the same act, at the same thing, as the actor's last
— is not a new act to see; where they are and what they look like is still in everyone's standing view.
"""

from __future__ import annotations

import helpers
import pytest

from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.mind import perception
from as_engine.physical import space

pytestmark = pytest.mark.phase(5)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def lit(w):
    """June and Mara on the sales floor with the lights up."""
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        for who, x in (("june", 5.0), ("mara", 8.0)):
            tx.commit_event(space.move_event(tx, w.id(who), w.id("sales_floor"), None, x, 4.0, t, None, 0))
    return w


def act(w, intent, at, turn):
    with w.store.transaction() as tx:
        evs = resolve_wave(tx, w.rng, barrier(tx, [intent]), at, turn, horizon_ms=at + 30_000)
        start = next(e for e in evs if e.type == "ACTION_START")
        perception.compile_aftermath(tx, w.id("mara"), evs, at + 30_000, turn)
    seen = [r[0] for r in w.store.query("SELECT text FROM percept_log WHERE holder_id = ? AND event_id = ?",
                                        (w.id("mara"), start.event_id))]
    return start, seen


def test_she_is_seen_to_start_watching_once(scenario):
    w = lit(scenario("metal_fence"))
    t = now(w)
    first, seen = act(w, helpers.make_intent(w, "june", "observe_area"), t, 1)
    assert first.payload["seen"] and seen, "she stops and watches"
    again, seen = act(w, helpers.make_intent(w, "june", "observe_area"), t + 60_000, 2)
    assert again.payload["seen"] is None and seen == [], "watching on is not a new act"
    other, seen = act(w, helpers.make_intent(w, "june", "watch_portal", target="storeroom_door"), t + 120_000, 3)
    assert other.payload["seen"] and seen, "watching the storeroom door is something new"


def test_only_holding_acts(scenario):
    """Doing anything else twice is seen twice: reaching for the same door again is reaching for it again."""
    w = lit(scenario("metal_fence"))
    t = now(w)
    act(w, helpers.make_intent(w, "june", "crouch"), t, 1)
    again, _seen = act(w, helpers.make_intent(w, "june", "crouch"), t + 60_000, 2)
    assert again.payload["seen"]
