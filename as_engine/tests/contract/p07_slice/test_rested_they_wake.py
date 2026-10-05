"""Rested, they wake (D-183). Rule SLEEP-04 (physical/bodies.py rested_at, progress); contracts NeedsRules.min_sleep_h.

The people in the store have no timetable — they are a crew, not a settlement. One who lay down to sleep slept until
a sound woke them: in a quiet place, for ever. Now a sleeper wakes once the night has paid what they owed. The
player's character still wakes when the player says (SLEEP-02).
"""

from __future__ import annotations

import pytest

from as_engine.contracts.events import EventType
from as_engine.physical import bodies

pytestmark = pytest.mark.phase(7)

H = 3_600_000


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def lie_down(w, who, at, awake_for_h):
    w.store.conn.execute("UPDATE needs SET last_sleep_ms = ?, fatigue_stage = ? WHERE body_id = ?",
                         (at - awake_for_h * H, min(6, awake_for_h // 8), w.id(who)))
    with w.store.transaction() as tx:
        bodies.posture_event(tx, w.id(who), "lying", at, None, 0, awareness="asleep")


def awareness(w, who):
    return w.store.query_one("SELECT awareness FROM bodies WHERE body_id = ?", (w.id(who),))[0]


def test_june_sleeps_her_night_and_wakes(scenario):
    w = scenario("metal_fence")
    t = now(w)
    lie_down(w, "june", t, 16)
    with w.store.transaction() as tx:
        assert bodies.rested_at(tx, w.id("june")) == t + 8 * H, "sixteen hours awake, eight asleep"
        evs = bodies.progress(tx, w.id("june"), t + 10 * H, 0, w.rng)
    up = [e for e in evs if e.type == EventType.AWARENESS_CHANGE]
    assert [(e.at, e.payload["awareness"], e.payload["slept_ms"]) for e in up] == [(t + 8 * H, "awake", 8 * H)]
    assert awareness(w, "june") == "awake"
    assert w.store.query_one("SELECT fatigue_stage FROM needs WHERE body_id = ?", (w.id("june"),))[0] == 0


def test_a_nap_is_at_least_an_hour(scenario):
    w = scenario("metal_fence")
    t = now(w)
    lie_down(w, "june", t, 0)
    with w.store.transaction() as tx:
        assert bodies.rested_at(tx, w.id("june")) == t + H


def test_the_player_decides(scenario):
    w = scenario("metal_fence")
    t = now(w)
    lie_down(w, "pc", t, 16)
    with w.store.transaction() as tx:
        assert bodies.rested_at(tx, w.id("pc")) is None
        bodies.progress(tx, w.id("pc"), t + 10 * H, 0, w.rng)
    assert awareness(w, "pc") == "asleep", "SLEEP-02: the player wakes him"
