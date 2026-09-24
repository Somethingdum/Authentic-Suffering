"""Tasks (P5). Rules TASK-01..03, CROWD-04 (action/tasks.py).

Counted work advances with time; a conversation never resets it; pausing keeps the count.
metal_fence: June counts cans — 41 of 60 done, 10 s a step (virtual start = now - 410 s).
"""

from __future__ import annotations

import json

import pytest

import helpers
from as_engine.action import tasks

pytestmark = pytest.mark.phase(5)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def task(w, local):
    return tasks.active_task(w.store, w.id(local))


def test_active_task_row(scenario):
    w = scenario("metal_fence")
    t = task(w, "june")
    assert (t["label"], t["steps_done"], t["steps_total"], t["started_at"]) == ("counting cans", 41, 60, now(w) - 410_000)
    assert tasks.active_task(w.store, w.id("mara")) is None


def test_advance_counts_whole_steps_in_one_event(scenario):
    w = scenario("metal_fence")
    t0 = now(w)
    with w.store.transaction() as tx:
        assert tasks.advance(tx, w.id("june"), t0 + 9_999, 0) == [], "no whole step yet"
        (ev,) = tasks.advance(tx, w.id("june"), t0 + 35_000, 0)
    assert ev.type == "TASK_STEP" and ev.writer == "action.tasks"
    assert ev.payload == {"task_id": task(w, "june")["task_id"], "actor_id": w.id("june"), "kind": "count_stock",
                          "label": "counting cans", "steps_done": 44, "steps_total": 60, "status": "active"}
    assert ev.at == t0 + 30_000, "stamped when the last whole step finished"
    assert task(w, "june")["next_due_at"] == t0 + 40_000


def test_a_task_finishes(scenario):
    w = scenario("metal_fence")
    t0 = now(w)
    tid = task(w, "june")["task_id"]
    with w.store.transaction() as tx:
        (ev,) = tasks.advance(tx, w.id("june"), t0 + 3_600_000, 0)
    assert ev.payload["steps_done"] == 60 and ev.payload["status"] == "done" and ev.at == t0 + 190_000
    row = w.store.query_one("SELECT status, next_due_at FROM tasks WHERE task_id = ?", (tid,))
    assert tuple(row) == ("done", None)
    assert tasks.active_task(w.store, w.id("june")) is None


def test_pause_and_resume_keep_the_count(scenario):
    """CAS-014 in miniature: stopping to look does not reset the count."""
    w = scenario("metal_fence")
    t0 = now(w)
    tid = task(w, "june")["task_id"]
    with w.store.transaction() as tx:
        ev = tasks.pause(tx, tid, t0 + 25_000, None, 0)
    assert ev.payload["status"] == "paused" and ev.payload["steps_done"] == 43
    assert tasks.active_task(w.store, w.id("june")) is None
    with w.store.transaction() as tx:
        assert tasks.advance(tx, w.id("june"), t0 + 500_000, 0) == [], "a paused task does not advance"
        tasks.resume(tx, tid, t0 + 600_000, None, 0)
        (ev,) = tasks.advance(tx, w.id("june"), t0 + 620_000, 0)
    assert ev.payload["steps_done"] == 45, "43 + 2 steps after resuming"
    with w.store.transaction() as tx:
        with pytest.raises(ValueError):
            tasks.resume(tx, tid, t0 + 700_000, None, 0)


def test_start_pauses_the_old_task(scenario):
    w = scenario("metal_fence")
    t0 = now(w)
    old = task(w, "june")["task_id"]
    with w.store.transaction() as tx:
        new = tasks.start(tx, w.id("june"), "restack", "restacking the shelf", 5, 12.0, t0 + 1_000,
                          ["loud_noise"], [], 0)
    assert w.store.query_one("SELECT status FROM tasks WHERE task_id = ?", (old,))[0] == "paused"
    row = dict(w.store.query_one("SELECT * FROM tasks WHERE task_id = ?", (new,)))
    assert (row["status"], row["steps_done"], row["started_at"], row["next_due_at"]) == ("active", 0, t0 + 1_000, t0 + 13_000)
    assert json.loads(row["interrupt_on"]) == ["loud_noise"] and new.startswith("tsk_")
    assert [json.loads(e["payload"])["status"] for e in helpers.events_of(w.store, "TASK_STEP")][-2:] == ["paused", "active"]


def test_interrupt_is_pause(scenario):
    w = scenario("metal_fence")
    tid = task(w, "alice")["task_id"]
    with w.store.transaction() as tx:
        ev = tasks.interrupt(tx, tid, None, now(w) + 1, 0)
    assert ev.payload["status"] == "paused"
