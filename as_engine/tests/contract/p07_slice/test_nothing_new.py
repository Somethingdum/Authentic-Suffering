"""Nothing new (D-189, D-190). Rules MEM-20 (mind/memory.py worth_writing; turn.pipeline S13), SEL-03 'restless' and
'talk_last_turn' (turn/select.py), lanes/scheduler.py plan_cognition (salience 0 is COLD).

Counting the calls of ten ordinary turns at Delgado's: every person in the building was asked, every turn, to
decide what to do and then to put into words what they had lived through — the man watching the office window
alone, with nothing but "The office door is closed." for the fifth time, and having stayed where he was for the
fifth time. A third of the memory calls and two thirds of the deciding were about nothing. Now someone with
nothing new is not asked to remember it, and decides with a model when something is happening to them, when
there is talk, or every third turn to take stock.
"""

from __future__ import annotations

import pytest
from slice_kit import play, script_night_at_delgados

from as_engine.contracts.common import LOD, CallClass, Lane
from as_engine.contracts.settings import EngineConfig
from as_engine.lanes.scheduler import plan_cognition
from as_engine.mind import memory
from as_engine.turn import select

pytestmark = pytest.mark.phase(7)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def test_nothing_to_remember_is_not_sent(scenario):
    w = scenario("metal_fence")
    s = w.session()
    assert play(s, "do", "I look around carefully.").ok
    assert play(s, "do", "I look around carefully.").ok
    T = w.store.query_one("SELECT MAX(turn_index) FROM percept_log")[0]
    holders = {r[0] for r in w.store.query("SELECT DISTINCT holder_id FROM percept_log WHERE turn_index = ?", (T,))}
    sent = {r[0] for r in w.store.query("SELECT holder_id FROM memory_jobs WHERE turn_index = ?", (T,))}
    quiet = holders - sent
    assert quiet and sent, (quiet, sent)
    for h in quiet:
        was = {tuple(r) for r in w.store.query("SELECT channel, text FROM percept_log WHERE holder_id = ? AND turn_index = ?",
                                               (h, T - 1))}
        now_ = {tuple(r) for r in w.store.query("SELECT channel, text FROM percept_log WHERE holder_id = ? AND turn_index = ?",
                                                (h, T))}
        assert now_ <= was, f"{w.local(h)} saw nothing that was not there before"
    with w.store.transaction() as tx:
        for h in sent:
            assert memory.worth_writing(tx, h, memory.build_aftermath(tx, h, T, now(w)), T)


def test_nothing_new_nothing_to_decide():
    cfg = EngineConfig()
    p = plan_cognition([("mara", 1.0, False), ("eli", 0.0, False), ("june", 0.0, True)], cfg, "balanced", {Lane.A, Lane.B})
    assert p.lod == {"june": LOD.HOT, "mara": LOD.WARM, "eli": LOD.COLD}, "a mandatory mind thinks whatever its salience"
    assert p.order == ["june", "mara", "eli"], "and the room's lines still go by the same order (AMB-02)"


def test_now_and_then_they_take_stock(scenario):
    w = scenario("metal_fence")
    t = now(w)

    def restless(turn):
        with w.store.transaction() as tx:
            return select.salience_flags(tx, w.id("eli"), [w.id("eli")], w.id("pc"), turn, t)["restless"]

    assert restless(5), "never thought with a model"
    w.store.conn.execute("INSERT INTO lm_calls (turn_index, seq, call_class, lane, actor_id, status, latency_ms, request_hash, "
                         "response_text) VALUES (4, 1, 'actor_cognition', 'B', ?, 'ok', 1, 'h', '{}')", (w.id("eli"),))
    assert [restless(n) for n in (5, 6, 7)] == [False, False, True], "every third turn (SchedulerRules.rethink_turns)"
    assert select.salience({"restless": True}, False, EngineConfig().rules.scheduler.salience_weights) > 0


def test_talk_is_taken_in_the_next_turn(scenario, fake):
    """Mara's "Quiet." and June's "What was that?" were said after the others had decided: the next turn, everyone who
    heard any of it — and June, who asked — takes it in."""
    w = scenario("metal_fence")
    s = w.session()
    script_night_at_delgados(w, fake)
    assert play(s, "do", "I watch the front window and keep quiet.").ok
    T = w.store.query_one("SELECT MAX(turn_index) FROM percept_log")[0]
    with w.store.transaction() as tx:
        for who in ("june", "alice", "mara"):
            assert select.salience_flags(tx, w.id(who), [w.id(who)], w.id("pc"), T + 1, now(w))["talk_last_turn"], who
    called = {r.actor_id for r in fake.calls(CallClass.ACTOR_COGNITION)}
    assert {w.id("june"), w.id("alice")} <= called


def test_what_they_now_want_is_acted_on(scenario):
    """D-191: a goal formed since someone last decided — Mae's quarantine goal, a plan from what was said — gives
    them something to decide the next turn, not three turns on."""
    from as_engine.mind import mind
    w = scenario("metal_fence")
    t = now(w)

    def fresh(turn):
        with w.store.transaction() as tx:
            return select.salience_flags(tx, w.id("eli"), [w.id("eli")], w.id("pc"), turn, t)["fresh_loop"]

    assert not fresh(4)
    with w.store.transaction() as tx:
        lid = mind.open_loop(tx, w.id("eli"), "goal", "Find out who has been at the water.", [], 2, "test:1", t, 3)
    assert [fresh(n) for n in (3, 4, 5)] == [False, True, False], "the turn after it was formed"
    with w.store.transaction() as tx:
        mind.close_loop(tx, lid, "abandoned", "test:2", t, 3)
    assert not fresh(4), "a loop let go is nothing to act on"


def test_a_body_that_needs_something_decides(scenario):
    """D-198: with nothing else going on, someone starving or dead on their feet still has a decision to make — the
    COLD default would have them keep watching the door."""
    from as_engine.mind.affordance import NEED_PRESSING
    w = scenario("metal_fence")
    t = now(w)

    def flags():
        with w.store.transaction() as tx:
            return select.salience_flags(tx, w.id("june"), [w.id("june")], w.id("pc"), 3, t)

    assert flags()["pressing_need"] is False
    w.store.conn.execute("UPDATE needs SET fatigue_stage = ? WHERE body_id = ?", (NEED_PRESSING, w.id("june")))
    assert flags()["pressing_need"] is True
    assert select.salience(flags(), False, EngineConfig().rules.scheduler.salience_weights) > 0
