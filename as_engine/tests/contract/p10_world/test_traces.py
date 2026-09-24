"""Marks left behind, and who can see them (P10). Rules TRACE-01, TRACE-02, TRACE-04, TRACE-05
(world/traces.py; mind/perception.py compile_scene). The decay and washout by weather are in
test_world_day.py.

A trace is what someone can perceive of something that happened while they were not there: blood
on a step, boot prints in the dust. A carved name stays; everything else fades on its own clock.
People see the marks where they stand when there is light to see them by — and they see them
through their own eyes (percepts), never by reading the world's table.
"""

from __future__ import annotations

import json

import pytest

from as_engine.contracts.events import Event, EventType
from as_engine.kernel import clock
from as_engine.mind import perception
from as_engine.physical import space
from as_engine.turn import timers
from as_engine.world import traces

pytestmark = pytest.mark.phase(10)

DAY = 24 * 3_600_000


def now(w) -> int:
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def one(w, sql, p=()):
    r = w.store.query_one(sql, p)
    return None if r is None else dict(r)


def mark(w, place, text, kind="blood", **kw) -> str:
    with w.store.transaction() as tx:
        return traces.create(tx, w.id(place), kind, text, None, now(w), 0, **kw)


def clock_event(w):
    """A committed stand-in for the TIMER_FIRED a decay row would carry."""
    return Event(type=EventType.OVERRIDE, writer="audit", at=now(w), turn_index=0, payload={"what": "timer stand-in"})


def trace_percepts(w, who) -> list[dict]:
    with w.store.transaction() as tx:
        got = perception.compile_scene(tx, w.id(who), now(w), 0)
    marks = {r[0] for r in w.store.query("SELECT trace_id FROM traces")}
    out = []
    for pid in got:
        r = one(w, "SELECT * FROM percept_log WHERE percept_id = ?", (pid,))
        if r["source_id"] in marks:
            out.append(r)
    return out


# =========================================================================== TRACE-01 / 02
def test_a_carved_mark_never_fades(scenario):
    """TRACE-01: locked -> no decays_at and no decay clock; TRACE-02: a decay row for it (were one
    to fire) does nothing."""
    w = scenario("metal_fence")
    t = mark(w, "alley", "A name carved into the dumpster lid.", kind="graffiti", locked=True)
    r = one(w, "SELECT * FROM traces WHERE trace_id = ?", (t,))
    assert (r["locked"], r["decays_at"], r["source_event"], r["created_at"]) == (1, None, "", now(w))
    assert clock.pending_for(w.store, "TRACE_DECAY", t) == []
    with w.store.transaction() as tx:
        ev = tx.commit_event(clock_event(w))
        assert traces.decay(tx, w.rng, {"payload": {"trace_id": t}, "due_at": now(w)}, ev, 0) == []
    assert one(w, "SELECT 1 FROM traces WHERE trace_id = ?", (t,)) is not None



def test_a_given_lifetime_is_used_as_it_is(scenario):
    """TRACE-01: decay_days given -> that many days, roof or no roof; the decay clock is set for then."""
    w = scenario("metal_fence")
    t = mark(w, "office", "Boot prints in the dust.", kind="tracks", decay_days=2)
    r = one(w, "SELECT * FROM traces WHERE trace_id = ?", (t,))
    assert r["decays_at"] == now(w) + 2 * DAY
    [row] = clock.pending_for(w.store, "TRACE_DECAY", t)
    assert row["due_at"] == r["decays_at"] and json.loads(row["payload"]) == {"trace_id": t}
    ev = one(w, "SELECT * FROM events WHERE type = 'TRACE_CREATED' ORDER BY seq DESC LIMIT 1")
    assert json.loads(ev["payload"]) == {"trace_id": t, "place_id": w.id("office"), "kind": "tracks",
                                         "text": "Boot prints in the dust.", "locked": False}
    assert (ev["writer"], ev["place_id"]) == ("world.traces", w.id("office"))
    with w.store.transaction() as tx:
        timers.run_offscreen(tx, w.rng, r["decays_at"] + 1000, 0)
    assert one(w, "SELECT 1 FROM traces WHERE trace_id = ?", (t,)) is None


def test_a_mark_needs_a_place(scenario):
    w = scenario("metal_fence")
    with w.store.transaction() as tx, pytest.raises(ValueError):
        traces.create(tx, "plc_999999", "blood", "Blood.", None, now(w), 0)


# =========================================================================== TRACE-04 / 05
def test_traces_in_lists_a_place_s_marks_oldest_first(scenario):
    """TRACE-04: by (created_at, trace_id); another place's marks are not listed."""
    w = scenario("metal_fence")
    a = mark(w, "sales_floor", "Blood on the floor by the counter.")
    with w.store.transaction() as tx:
        clock.advance_event(tx, now(w) + 1000, "test")
    b = mark(w, "sales_floor", "A smear on the door frame.")
    mark(w, "alley", "Drag marks toward the fence.")
    got = traces.traces_in(w.store, w.id("sales_floor"))
    assert [r["trace_id"] for r in got] == [a, b]
    assert got[0]["text"] == "Blood on the floor by the counter." and got[0]["place_id"] == w.id("sales_floor")


def test_marks_are_seen_where_there_is_light(scenario):
    """TRACE-05: one VISUAL percept per mark in the holder's place (traces_in order), its text the
    mark's and its source the mark — when there is light where the holder stands; in the dark,
    none."""
    w = scenario("metal_fence")
    a = mark(w, "sales_floor", "Blood on the floor by the counter.")
    b = mark(w, "sales_floor", "Glass swept into a corner.", kind="damage")
    mark(w, "office", "Scratches around the door handle.", kind="claw_marks")
    seen = trace_percepts(w, "pc")
    assert [(p["source_id"], p["text"], p["channel"]) for p in seen] == [
        (a, "Blood on the floor by the counter.", "visual"), (b, "Glass swept into a corner.", "visual")]
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("office"), None, 2.0, 1.5, now(w), None, 0))
    assert trace_percepts(w, "june") == [], "the office is dark"
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("office"), {"light_level": 2}, "test", now(w), None, 0)
        clock.advance_event(tx, now(w) + 1000, "test")      # a new moment: a new look around
    assert [p["text"] for p in trace_percepts(w, "june")] == ["Scratches around the door handle."]
