"""World clock and timer queue (P0). Rules TIME-01, TIME-06."""

from __future__ import annotations

import pytest

from as_engine.kernel import clock
from as_engine.kernel.clock import MS_PER_DAY, MS_PER_H, QUEUE_TYPES, daylight_level, format_clock, world_time
from as_engine.kernel.errors import ClockError, ValidationFailure
from as_engine.kernel.store import Store

pytestmark = pytest.mark.phase(0)


def test_world_time_helpers_pin_the_calendar():
    """Implemented helpers (pins the defaults): day 18 23:14:03 = late 'night'."""
    ms = 18 * MS_PER_DAY + 23 * MS_PER_H + 14 * 60_000 + 3_000
    t = world_time(ms)
    assert (t.day, t.hour, t.minute, t.second, t.part_of_day) == (18, 23, 14, 3, "night")
    assert format_clock(ms) == "23:14"
    assert daylight_level(ms, "wind") == 1
    assert daylight_level(12 * MS_PER_H, "clear") == 4 and daylight_level(12 * MS_PER_H, "storm") == 2
    with pytest.raises(ValueError):
        world_time(-1)


def test_now_and_advance():
    """TIME-01: advance_event commits a CLOCK_ADVANCE; zero advance commits nothing; going back raises."""
    s = Store.memory(run_id="r", seed=1, start_ms=5_000)
    with s.transaction() as tx:
        assert clock.now(tx) == 5_000
        ev = clock.advance_event(tx, 8_000, "test")
        assert ev is not None and ev.type == "CLOCK_ADVANCE" and ev.writer == "kernel.clock"
        assert clock.now(tx) == 8_000
        assert clock.advance_event(tx, 8_000, "noop") is None
        with pytest.raises(ClockError):
            clock.advance_event(tx, 7_999, "back")
    assert s.query_one("SELECT now_ms FROM world_clock")["now_ms"] == 8_000
    s.close()


def test_schedule_and_queue_queries():
    """TIME-06: schedule accepts only QUEUE_TYPES; due_between/next_due order by (due_at, queue_id)."""
    s = Store.memory(run_id="r", seed=1, start_ms=1_000)
    with s.transaction() as tx:
        q2 = clock.schedule(tx, 3_000, "NOISE", None, {"source_db": 90}, None)
        q1 = clock.schedule(tx, 2_000, "NOISE", None, {"source_db": 80}, None)
        q3 = clock.schedule(tx, 3_000, "TRACE_DECAY", None, {"trace_id": "trc_000001"}, None)
        with pytest.raises(ValidationFailure) as ei:
            clock.schedule(tx, 4_000, "NOT_A_TIMER", None, {}, None)
        assert ei.value.rule == "TIME-06"
        with pytest.raises(ClockError):
            clock.schedule(tx, 500, "NOISE", None, {}, None)
    assert q1.startswith("que_") and q2 != q1
    rows = clock.due_between(s, 1_000, 3_000)
    assert [r["queue_id"] for r in rows] == [q1] + sorted([q2, q3])
    assert clock.next_due(s, 1_000) == 2_000
    assert clock.next_due(s, 3_000) is None
    assert set(QUEUE_TYPES) >= {"NOISE", "WEATHER_CHANGE", "CASCADE_EFFECT", "PRODUCTION_CYCLE", "LOYALTY_CHECK"}
    s.close()


def test_schedule_is_an_event():
    """STORE-01: the queue row is written by a TIMER_SET event (writer kernel.clock)."""
    s = Store.memory(run_id="r", seed=1)
    with s.transaction() as tx:
        clock.schedule(tx, 10, "NOISE", None, {}, None)
    ev = s.query_one("SELECT type, writer FROM events ORDER BY seq DESC LIMIT 1")
    assert (ev["type"], ev["writer"]) == ("TIMER_SET", "kernel.clock")
    s.close()
