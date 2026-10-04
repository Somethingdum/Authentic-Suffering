"""Work put down can be taken up again (D-118). action/tasks.py put_down, resume; mind/affordance.py
keep_working; action/effects.py continue_task; mind/packet.py commitments. Rules TASK-02, CAS-014.

June is counting stock when the fence crashes. Going to look pauses the count where it stands
(CAS-014). Until D-118 nothing could start it again: "Keep going" was offered only for a task still
running, and the count dropped out of what she was in the middle of. Now she remembers it as put down,
is offered to pick it up, and goes on from where she stood — never from zero.
"""

from __future__ import annotations

import pytest

import helpers
from as_engine.action import cascade, tasks
from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.contracts.common import LOD
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet

pytestmark = pytest.mark.phase(5)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def interrupted(scenario, canon):
    """metal_fence: June goes to look, and CAS-014 pauses her count."""
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        evs = resolve_wave(tx, w.rng, barrier(tx, [helpers.make_intent(w, "june", "go_look", destination="back_door_in")]),
                           t, 0, horizon_ms=t + 60_000)
        cascade.sweep(tx, evs, [r for r in canon.all("cascade") if r.id == "CAS-014"], t, 0)
    return w, t + 60_000


def menu(w, who, at):
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(who), at, 0)
        return enumerate_affordances(tx, w.id(who), w.canon.all("affordance"), at, 0)


def test_she_remembers_the_count_and_is_offered_to_pick_it_up(scenario, canon):
    w, at = interrupted(scenario, canon)
    with w.store.transaction() as tx:
        assert tasks.active_task(tx, w.id("june")) is None
        put = tasks.put_down(tx, w.id("june"))
    assert put["status"] == "paused" and put["steps_done"] == 41
    aff = menu(w, "june", at)
    (keep,) = [o for o in aff.options if o.def_id == "keep_working"]
    assert put["label"] in keep.label, "the menu names the work she put down"
    with w.store.transaction() as tx:
        p = build_packet(tx, w.id("june"), LOD.HOT, aff, 0, at)
    assert p.commitments.current_task == f"{put['label']} (41 of {put['steps_total']} done, put down for now)"


def test_she_goes_on_from_where_she_stood(scenario, canon):
    w, at = interrupted(scenario, canon)
    with w.store.transaction() as tx:
        put = tasks.put_down(tx, w.id("june"))
        step_ms = round(put["step_s"] * 1000)
        resolve_wave(tx, w.rng, barrier(tx, [helpers.make_intent(w, "june", "keep_working")]), at, 0,
                     horizon_ms=at + 10 * step_ms)
        row = dict(tx.query_one("SELECT * FROM tasks WHERE task_id = ?", (put["task_id"],)))
    assert row["status"] == "active" and row["steps_done"] >= 41 + 9, "resumed, and counting again from 41"
    assert row["started_at"] <= at - 41 * step_ms, "the steps already done still count (TASK-02: never from zero)"
    with w.store.transaction() as tx:
        assert tasks.put_down(tx, w.id("june")) is None


def test_nothing_put_down_nothing_offered(scenario):
    w = scenario("metal_fence")
    w.store.conn.execute("UPDATE tasks SET status = 'done' WHERE actor_id = ?", (w.id("june"),))   # her count is finished
    with w.store.transaction() as tx:
        assert tasks.put_down(tx, w.id("june")) is None and tasks.active_task(tx, w.id("june")) is None
    assert not [o for o in menu(w, "june", now(w)).options if o.def_id == "keep_working"], \
        "finished work is not offered again"
