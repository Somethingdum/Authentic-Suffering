"""A promise kept or broken is answered (D-125). turn/pipeline.py S14 (the writebacks' events are swept),
service/background.py commit (BG-04, the same in the quiet hours); core CAS-011 (a broken promise) and
CAS-029 (a promise kept).

A promise is closed by the person it was made to, in their writeback — after the turn's commit, where
no sweep ever ran. So until D-125 a broken promise never cost the one who broke it anything, and a kept
one gave nothing back: CAS-011 and CAS-029 worked only when a test swept them by hand.
"""

from __future__ import annotations

import pytest
from slice_kit import pick, play

from as_engine.contracts.common import CallClass
from as_engine.mind import mind

pytestmark = pytest.mark.phase(7)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def trust(w, a, b):
    r = w.store.query_one("SELECT trust FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def closes(loop, status):
    """June's writeback: the promise is ``status``, because of the first thing she perceived."""
    def answer(r):
        a = r.context.aftermath
        lh = next(line.handle for line in a.open_loops if a.handles[line.handle] == loop)
        because = (list(a.percepts) + list(a.utterances))[0].handle
        return {"episode": "The lamp. Mara and the lamp.", "salience": 40, "beliefs": [], "relationships": [], "new_loops": [],
                "closed_loops": [{"loop": lh, "status": status, "because": because}], "lesson": None}
    return answer


def turn(w, fake):
    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "wait_here"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    assert play(w.session(), "do", "I wait.").ok


def test_a_broken_promise_costs_the_one_who_broke_it(scenario, fake):
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        loop = mind.open_loop(tx, w.id("june"), "promise_owed", "Mara said she would bring the lamp.", [w.id("mara")],
                              2, None, t, 0)
    before = trust(w, "june", "mara")
    fake.script(CallClass.WRITEBACK, closes(loop, "broken"), actor_id=w.id("june"))
    turn(w, fake)
    assert w.store.query("SELECT 1 FROM events WHERE type = 'PROMISE_BROKEN'"), "she closed it as broken"
    assert trust(w, "june", "mara") == max(-3, before - 2), "CAS-011, answered in the turn it was broken"
    assert w.store.query("SELECT 1 FROM open_loops WHERE holder_id = ? AND kind = 'grudge' AND text LIKE '%broke a promise%'",
                         (w.id("june"),))


def test_a_promise_kept_gives_its_keeper_something_back(scenario, fake):
    w = scenario("metal_fence")
    t = now(w)
    w.store.conn.execute("UPDATE actors SET resolve_cur = 1 WHERE actor_id = ?", (w.id("mara"),))
    with w.store.transaction() as tx:
        loop = mind.open_loop(tx, w.id("june"), "promise_owed", "Mara said she would bring the lamp.", [w.id("mara")],
                              2, None, t, 0)
    fake.script(CallClass.WRITEBACK, closes(loop, "fulfilled"), actor_id=w.id("june"))
    turn(w, fake)
    assert w.store.query_one("SELECT resolve_cur FROM actors WHERE actor_id = ?", (w.id("mara"),))[0] == 2, "CAS-029"


def test_in_the_quiet_hours_too(scenario):
    """BG-04: Mara, thinking between moments, decides Eli broke his promise to her (CAS-011)."""
    from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
    from as_engine.contracts.mind import LoopClose, ReflectionOutput
    from as_engine.kernel import clock
    from as_engine.service import background as bg
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        clock.advance_event(tx, now(w) + 3_600_000, "test")
        clock.begin_turn(tx, 1)
    t = now(w)
    with w.store.transaction() as tx:
        eid = tx.mint("epi")
        tx.commit_event(Event(type=EventType.EPISODE_WRITTEN, writer="mind.memory", at=t, turn_index=1, actor_id=w.id("mara"),
                              payload={"episode_id": eid, "holder_id": w.id("mara"), "salience": 70, "anchor": 0},
                              writes=[WriteRecord(op=WriteOp.INSERT, table="episodes", key={"episode_id": eid}, values={
                                  "episode_id": eid, "holder_id": w.id("mara"), "at": t, "turn_index": 1, "place_id": None,
                                  "summary": "Eli was meant to watch the back.", "salience": 70, "percept_ids": [],
                                  "subject_ids": [], "anchor": 0, "decayed": 0, "quarantined": 0})]))
        loop = mind.open_loop(tx, w.id("mara"), "promise_owed", "Eli said he would watch the back.", [w.id("eli")], 2,
                              None, t, 1)
    before = trust(w, "mara", "eli")
    job = next(j for j in bg.jobs(w.store, 1) if j.subject_id == w.id("mara"))
    out = ReflectionOutput(goals_add=[], loops_close=[LoopClose(loop="L1", status="broken", because="S1")], lesson=None,
                           plan_goal=None, plan_steps=[])
    with w.store.transaction() as tx:
        evs = bg.commit(tx, job, bg.JobResult(job=job, answer={"output": out, "handles": {"L1": loop}}), t, 1)
    assert "PROMISE_BROKEN" in [str(getattr(e.type, "value", e.type)) for e in evs]
    assert trust(w, "mara", "eli") == max(-3, before - 2), "answered in the quiet hours as in a turn"
