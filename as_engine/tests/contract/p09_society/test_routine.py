"""Routines (P9). Rules ROUT-01..07, DEMO-02, SEL-06 (society/routine.py).

A settlement is not a waiting room: people sleep, work, play and walk between them on their own
clocks. Code never moves a human-controlled body.
"""

from __future__ import annotations

import pytest

from as_engine.kernel import clock
from as_engine.society import routine
from as_engine.society.routine import Step
from as_engine.turn import timers

from society_kit import H, hhmm, injure, now, rows, run

pytestmark = pytest.mark.phase(9)


def S(w, *steps):
    return [Step(a, b, act, w.id(p), w.id(wk) if wk else None, role) for a, b, act, p, wk, role in steps]


def test_a_day_worker(settle):
    w = settle
    assert routine.steps_for(w.store, w.id("hal")) == S(w, (6, 18, "work", "pump_house", "pump", "pump_operator"),
                                                        (18, 22, "free", "yard", None, None),
                                                        (22, 6, "sleep", "bunk_a", None, None))


def test_a_night_worker_sleeps_after_the_shift(settle):
    w = settle
    assert routine.steps_for(w.store, w.id("ben")) == S(w, (6, 14, "sleep", "bunk_b", None, None),
                                                        (14, 18, "free", "yard", None, None),
                                                        (18, 6, "work", "pump_house", "pump", "pump_operator"))


def test_demo_02_children_play_in_daylight_infants_stay_home(settle):
    w = settle
    assert routine.steps_for(w.store, w.id("pip")) == S(w, (7, 19, "play", "yard", None, None), (19, 7, "sleep", "bunk_a", None, None))
    assert routine.steps_for(w.store, w.id("ada")) == S(w, (7, 19, "play", "bunk_b", None, None), (19, 7, "sleep", "bunk_b", None, None))
    assert routine.steps_for(w.store, w.id("nell")) == S(w, (6, 22, "play", "yard", None, None), (22, 6, "sleep", "bunk_b", None, None))
    assert routine.steps_for(w.store, w.id("tomas")) == S(w, (6, 22, "free", "yard", None, None), (22, 6, "sleep", "bunk_a", None, None))


def test_no_routine_for_a_human_or_an_outsider(settle, scenario):
    w = settle
    assert routine.steps_for(w.store, w.id("pc")) == []            # SEL-06: code never acts for the player's body
    m = scenario("metal_fence")                                    # no settlement: nobody there has a routine
    assert routine.steps_for(m.store, m.id("mara")) == [] and routine.step_for(m.store, m.id("mara"), 12) is None
    assert routine.next_boundary(m.store, m.id("mara"), now(m)) is None


def test_step_for_and_the_next_boundary(settle):
    w = settle
    assert routine.step_for(w.store, w.id("hal"), 3).activity == "sleep"
    assert routine.step_for(w.store, w.id("hal"), 17).activity == "work"
    t = now(w)                                                     # 05:00
    assert hhmm(routine.next_boundary(w.store, w.id("hal"), t)) == "06:00"
    assert routine.next_boundary(w.store, w.id("hal"), t + H) == t + 13 * H        # exactly on a boundary -> the next one (18:00)


def test_a_double_shift_leaves_no_sleep(settle):
    w = settle
    injure(w, "hal")
    run(w, 1.5)                                                    # Ben takes Hal's day shift at 06:00
    assert routine.steps_for(w.store, w.id("ben")) == S(w, (0, 0, "work", "pump_house", "pump", "pump_operator"))   # all day


def test_the_morning_moves_people_to_work(settle):
    w = settle
    run(w, 1.5)                                                    # 05:00 -> 06:30
    moved = {r["payload"]["actor_id"]: r["payload"] for r in rows(w, "ROUTINE_STEP") if hhmm(r["at"]) == "06:00"}
    assert moved[w.id("hal")]["outcome"] == "moved" and moved[w.id("hal")]["activity"] == "work"
    assert w.store.query_one("SELECT place_id FROM positions WHERE body_id = ?", (w.id("hal"),))[0] == w.id("pump_house")
    aw = w.store.query_one("SELECT awareness, posture FROM bodies WHERE body_id = ?", (w.id("hal"),))
    assert (aw[0], aw[1]) == ("awake", "standing")
    starts = [(r["payload"]["actor_id"], r["payload"]["role"]) for r in rows(w, "SHIFT_START") if hhmm(r["at"]) == "06:00"]
    assert (w.id("hal"), "pump_operator") in starts and (w.id("rosa"), "pump_operator") in starts
    fat = w.store.query_one("SELECT fatigue_stage FROM needs WHERE body_id = ?", (w.id("hal"),))[0]
    assert fat == 0                                                # a night's sleep refreshed him
    assert w.store.query_one("SELECT place_id FROM positions WHERE body_id = ?", (w.id("pc"),))[0] == w.id("yard")


def test_an_unfit_worker_is_not_sent_to_the_post(settle):
    w = settle
    injure(w, "hal")
    run(w, 1.5)
    step = [r for r in rows(w, "ROUTINE_STEP") if r["payload"]["actor_id"] == w.id("hal") and hhmm(r["at"]) == "06:00"][0]
    assert (step["payload"]["activity"], step["payload"]["reason"]) == ("free", "cannot work")
    assert w.store.query_one("SELECT place_id FROM positions WHERE body_id = ?", (w.id("hal"),))[0] == w.id("yard")
    assert not [r for r in rows(w, "SHIFT_START") if r["payload"]["actor_id"] == w.id("hal")]


def test_a_routine_yields_to_what_someone_is_doing(settle):
    w = settle
    from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
    with w.store.transaction() as tx:
        tid = tx.mint("tsk")
        tx.commit_event(Event(type=EventType.ACTION_START, writer="action.tasks", at=now(w), turn_index=0, actor_id=w.id("rosa"),
                              payload={"task_id": tid},
                              writes=[WriteRecord(op=WriteOp.INSERT, table="tasks", values={
                                  "task_id": tid, "actor_id": w.id("rosa"), "kind": "mend", "label": "mend a net", "steps_total": 10,
                                  "steps_done": 0, "step_s": 3600.0, "started_at": now(w), "next_due_at": now(w) + H,
                                  "interrupt_on": [], "target_ids": [], "focus": 0, "status": "active"})]))
    run(w, 1.5)
    step = [r for r in rows(w, "ROUTINE_STEP") if r["payload"]["actor_id"] == w.id("rosa") and hhmm(r["at"]) == "06:00"][0]
    assert (step["payload"]["outcome"], step["payload"]["reason"]) == ("skipped", "busy")
    assert w.store.query_one("SELECT place_id FROM positions WHERE body_id = ?", (w.id("rosa"),))[0] == w.id("bunk_a")


def test_evening_sends_children_to_bed(settle):
    w = settle
    run(w, 14.5)                                                   # to 19:30
    aw = w.store.query_one("SELECT awareness FROM bodies WHERE body_id = ?", (w.id("pip"),))[0]
    assert aw == "asleep"
    assert w.store.query_one("SELECT place_id FROM positions WHERE body_id = ?", (w.id("pip"),))[0] == w.id("bunk_a")
    played = [r for r in rows(w, "ROUTINE_STEP") if r["payload"]["actor_id"] == w.id("pip") and r["payload"]["activity"] == "play"]
    assert played and played[0]["payload"]["place_id"] == w.id("yard")


def test_rout_07_ensure_timers_is_idempotent(settle):
    w = settle
    with w.store.transaction() as tx:
        first = routine.ensure_timers(tx, w.id("pumpwell"), now(w), 0)
        again = routine.ensure_timers(tx, w.id("pumpwell"), now(w), 0)
    assert len(first) == 23 and again == []                        # everyone but the PC
    pending = w.store.query("SELECT subject_id, due_at FROM event_queue WHERE type = 'ROUTINE_STEP' AND status = 'pending'")
    due = {r[0]: r[1] for r in pending}
    assert w.id("pc") not in due and hhmm(due[w.id("hal")]) == "06:00" and hhmm(due[w.id("pip")]) == "07:00"
