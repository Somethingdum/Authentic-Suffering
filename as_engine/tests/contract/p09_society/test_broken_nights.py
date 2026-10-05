"""Broken nights (D-146). Core CAS-061/062; action/cascade.py's AWARENESS_CHANGE dispatch (physical.bodies.wake);
narration/narrator.py BROKEN_NIGHT_LINE.

A safe night gives a little back (D-122), and nothing ever took the night from anyone: under any strain at all a
person lay down and slept six hours. Now, under heavy strain (stress 8 and up), sleep breaks three hours in — no
safe night, so nothing given back — and the player is told when it is their character who wakes.
"""

from __future__ import annotations

import json

import pytest

from as_engine.action import cascade
from as_engine.narration.narrator import BROKEN_NIGHT_LINE, build_narrator_packet
from as_engine.physical import bodies
from as_engine.turn import timers

pytestmark = pytest.mark.phase(9)

H = 3_600_000
RULES = ("CAS-021", "CAS-061", "CAS-062")


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def actor(w, who, col):
    return w.store.query_one(f"SELECT {col} FROM actors WHERE actor_id = ?", (w.id(who),))[0]


def awareness(w, who):
    return w.store.query_one("SELECT awareness FROM bodies WHERE body_id = ?", (w.id(who),))[0]


def lie_down(w, who, at, turn=0):
    with w.store.transaction() as tx:
        ev = bodies.posture_event(tx, w.id(who), "lying", at, None, turn, awareness="asleep")
        cascade.sweep(tx, [ev], [r for r in w.canon.all("cascade") if r.id in RULES], at, turn)
    return ev


def night(w, until, turn=0):
    with w.store.transaction() as tx:
        out = timers.fire_due(tx, w.rng, until, turn, until)
        cascade.sweep(tx, out, [r for r in w.canon.all("cascade") if r.id in RULES], until, turn)
    return out


def test_under_strain_the_night_breaks(scenario):
    w = scenario("metal_fence")
    t = now(w)
    w.store.conn.execute("UPDATE actors SET stress = 9, resolve_cur = 1 WHERE actor_id = ?", (w.id("mara"),))
    lie_down(w, "mara", t)
    night(w, t + 3 * H)
    assert awareness(w, "mara") == "awake"
    woke = w.store.query("SELECT payload, rule_cited FROM events WHERE type = 'AWARENESS_CHANGE' AND json_extract(payload, '$.body_id') = ?",
                         (w.id("mara"),))
    assert [(json.loads(r[0])["slept_ms"], r[1]) for r in woke] == [(3 * H, "CAS-061")]
    assert actor(w, "mara", "resolve_cur") == 1, "three hours is no safe night"


def test_steady_enough_to_sleep(scenario):
    w = scenario("metal_fence")
    t = now(w)
    w.store.conn.execute("UPDATE actors SET stress = 5 WHERE actor_id = ?", (w.id("mara"),))
    lie_down(w, "mara", t)
    night(w, t + 7 * H)
    assert awareness(w, "mara") == "asleep"


def test_a_night_already_over_is_not_broken(scenario):
    """Mara wakes on her own at two hours and lies down again: the first night's wake does nothing to the second."""
    w = scenario("metal_fence")
    t = now(w)
    w.store.conn.execute("UPDATE actors SET stress = 9 WHERE actor_id = ?", (w.id("mara"),))
    lie_down(w, "mara", t)
    with w.store.transaction() as tx:
        bodies.wake(tx, w.id("mara"), t + 2 * H, None, 0)
    w.store.conn.execute("UPDATE actors SET stress = 5 WHERE actor_id = ?", (w.id("mara"),))
    lie_down(w, "mara", t + 2 * H + 1000)
    night(w, t + 3 * H + 1000)
    assert awareness(w, "mara") == "asleep"


def test_the_player_is_told(scenario):
    w = scenario("metal_fence")
    t = now(w)
    w.store.conn.execute("UPDATE actors SET stress = 8 WHERE actor_id = ?", (w.id("pc"),))
    lie_down(w, "pc", t, turn=4)
    night(w, t + 3 * H, turn=4)
    assert awareness(w, "pc") == "awake"
    with w.store.transaction() as tx:
        assert BROKEN_NIGHT_LINE in build_narrator_packet(tx, w.id("pc"), 4, now(w), w.session().settings).pc_state_lines
        assert BROKEN_NIGHT_LINE not in build_narrator_packet(tx, w.id("pc"), 5, now(w), w.session().settings).pc_state_lines
