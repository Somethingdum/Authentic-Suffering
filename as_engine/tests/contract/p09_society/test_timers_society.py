"""The society's clocks and the off-screen step (P9). Rules TIME-06..10, CAS-05, CAS-06, HOR-01,
ROUT-05, the P9 amendments to the turn pipeline (turn/timers.py, action/cascade.py, turn/select.py,
turn/pipeline.py, action/intent.py).

A settlement's life runs on the same timers as everything else; a world without settlements runs
exactly as it did before P9.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from as_engine.action import cascade
from as_engine.action.intent import plan_continuation
from as_engine.contracts.common import CallClass
from as_engine.contracts.events import Event, EventType
from as_engine.kernel import clock
from as_engine.kernel.errors import ClockError
from as_engine.mind.affordance import enumerate_affordances
from as_engine.physical import bodies
from as_engine.society import settlement as stl
from as_engine.turn import select, timers

from society_kit import DAY, H, accident, hhmm, now, rows, run, settlement

pytestmark = pytest.mark.phase(9)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "p07_slice"))


def test_seed_society_starts_every_clock_once(settle):
    w = settle
    with w.store.transaction() as tx:
        q = timers.seed_society(tx, now(w), 0)
        assert timers.seed_society(tx, now(w), 0) == []
    kinds = [w.store.query_one("SELECT type FROM event_queue WHERE queue_id = ?", (x,))[0] for x in q]
    assert kinds[:5] == ["SETTLEMENT_DAY", "PRODUCTION_CYCLE", "PRODUCTION_CYCLE", "PRODUCTION_CYCLE", "GROUP_DAY"]
    assert kinds[5:] == ["ROUTINE_STEP"] * 23
    due = {r[0]: r[1] for r in w.store.query("SELECT type, due_at FROM event_queue WHERE type IN ('SETTLEMENT_DAY','GROUP_DAY')")}
    assert (hhmm(due["SETTLEMENT_DAY"]), hhmm(due["GROUP_DAY"])) == ("07:00", "20:00")


def test_a_world_without_settlements_gets_nothing(scenario):
    m = scenario("metal_fence")
    with m.store.transaction() as tx:
        assert timers.seed_society(tx, now(m), 0) == []
    assert m.store.query_one("SELECT COUNT(*) FROM event_queue WHERE type IN ('ROUTINE_STEP','GROUP_DAY')")[0] == 0


def test_fire_one_dispatches_and_sweeps(settle):
    w = settle
    with w.store.transaction() as tx:
        stl.receive(tx, w.id("pumpwell"), {"water": -150}, "a leak", now(w), 0, None)
        qid = clock.schedule(tx, now(w), "PRODUCTION_CYCLE", w.id("pump"), {"workplace_id": w.id("pump")}, None)
        row = dict(tx.query_one("SELECT * FROM event_queue WHERE queue_id = ?", (qid,)))
        out = timers.fire_one(tx, w.rng, row, 0, now(w))
    types = [e.type for e in out]
    assert types[0] == EventType.TIMER_FIRED and EventType.PRODUCTION_CYCLE in types
    assert EventType.SHORTAGE in types and EventType.RATION_CHANGE in types      # the sweep ran on what the handler made
    shortage = [e for e in out if e.type == EventType.SHORTAGE][0]
    assert shortage.rule_cited == "CAS-004"


def test_fire_due_fires_in_order_and_includes_what_handlers_schedule(settle):
    w = settle
    with w.store.transaction() as tx:
        timers.seed_society(tx, now(w), 0)
        out = timers.fire_due(tx, w.rng, now(w) + 2 * H, 0, now(w) + 2 * H)
    fired = [e for e in out if e.type == EventType.TIMER_FIRED]
    ats = [e.at for e in fired]
    assert ats == sorted(ats) and max(ats) <= now(w) + 2 * H
    assert w.store.query_one("SELECT COUNT(*) FROM event_queue WHERE status = 'pending' AND due_at <= ?", (now(w) + 2 * H,))[0] == 0


def test_run_offscreen_moves_the_clock_in_windows(settle):
    w = settle
    t = now(w)
    out = run(w, 13)
    adv = [e for e in out if e.type == EventType.CLOCK_ADVANCE]
    assert [(e.payload.get("reason"), e.at) for e in adv][-1][1] == t + 13 * H
    assert [e.at for e in adv] == [t + 6 * H, t + 12 * H, t + 13 * H]          # WorldRules.offscreen_tick_h = 6
    assert now(w) == t + 13 * H
    with pytest.raises(ClockError):
        with w.store.transaction() as tx:
            timers.run_offscreen(tx, w.rng, t, 0)


def test_the_gate_holds_after_days_of_society(settle):
    from as_engine.audit import commit_gate
    w = settle
    run(w, 50)
    g = commit_gate.compute(w.store, 0)
    assert g.passed, g.failures


def test_cas_06_a_scheduled_effect_whose_rule_is_gone(settle):
    w = settle
    with w.store.transaction() as tx:
        cause = accident(tx, now(w))
        qid = clock.schedule(tx, now(w) + H, "CASCADE_EFFECT", w.id("hal"),
                             {"rule_id": "CAS-999", "effect_index": 0, "target": w.id("hal"), "trigger_event_id": cause.event_id}, cause.event_id)
    run(w, 1.5)
    notes = [r[0] for r in w.store.query("SELECT findings FROM audit_log WHERE gate = 'G10-cascade'")]
    assert any("cascade_rule_gone" in n for n in notes)


def test_cas_05_p9_selectors_and_paths(settle):
    w = settle
    with w.store.transaction() as tx:
        trig = tx.commit_event(Event(type=EventType.SHIFT_MISSED, writer="society.work", at=now(w), turn_index=0,
                                     payload={"workplace_id": w.id("pump"), "role": "pump_operator", "actor_id": w.id("hal"),
                                              "shift_start_hh": 6, "shift_end_hh": 18, "settlement_id": w.id("pumpwell")}))
        sel = lambda s: cascade.select(tx, s, trig)                                   # noqa: E731
        assert sel("settlement_of(trigger.payload.workplace_id)") == [w.id("pumpwell")]
        assert sel("workplace_of(trigger.payload.workplace_id)") == [w.id("pump")]
        assert sel("household_of(trigger.payload.actor_id)") == [w.id("brandt")]
        assert sel("work_assignments_of(trigger.payload.actor_id)") == [f"{w.id('pump')}:pump_operator:{w.id('hal')}:6"]
        assert sel("cover_candidate_for(trigger.payload.workplace_id)") == [w.id("ben")]
        assert sel("leadership_of(trigger.payload.settlement_id)") == [w.id("settlers")]
        assert sel("head_of_worst_hit_household(trigger.payload.settlement_id)") == [w.id("iris")]
        heads = sel("heads_of_households_with_dependents(trigger.payload.settlement_id)")
        assert heads == sorted(w.id(x) for x in ("hal", "rosa", "ben", "wade", "iris", "jude"))
        hear = sel("who_would_hear_of(trigger.payload.actor_id)")
        assert w.id("mae") in hear and w.id("tomas") in hear and w.id("hal") not in hear
        ev = lambda e: cascade.evaluate_precondition(tx, e, trig)                    # noqa: E731
        assert ev("settlement_of(trigger.payload.workplace_id).days_of_water > 3")
        assert ev("settlement_of(trigger.payload.workplace_id).has_shortage_water == false")
        assert ev("settlement_of(trigger.payload.workplace_id).ration_level == 3")
        assert ev("workplace_of(trigger.payload.workplace_id).efficiency == 1.0")
        assert not ev("settlement_of(trigger.payload.nothing).ration_level == 3")


def test_hor_01_the_settlements_life_is_not_news(settle):
    from helpers import make_intent
    w = settle
    with w.store.transaction() as tx:
        timers.seed_society(tx, now(w), 0)                          # background rows at 06:00, 07:00 ...
        intent = make_intent(w, "pc", "observe_area")
        h = select.horizon(tx, intent, now(w))
    assert h == now(w) + select.MAX_WINDOW_MS                       # nothing but background rows are pending
    with w.store.transaction() as tx:
        clock.schedule(tx, now(w) + H, "NOISE", None, {"source_db": 80, "kind": "shout", "text": "a shout", "place_id": w.id("yard")}, None)
        assert select.horizon(tx, intent, now(w)) == now(w) + H      # news still ends the watch


def test_rout_05_a_woken_sleeper_goes_back_to_bed(settle):
    w = settle
    run(w, 18)                                                      # 23:00
    with w.store.transaction() as tx:
        bodies.wake(tx, w.id("tomas"), now(w), None, 0)
        affs = enumerate_affordances(tx, w.id("tomas"), tx.canon.all("affordance"), now(w), 0)
        i = plan_continuation(tx, w.id("tomas"), affs, now(w), 0)
    assert (i.bound.def_id, i.source) == ("sleep", "plan")


def test_a_played_turn_in_the_settlement(settle, fake):
    from slice_kit import play, pick
    w = settle
    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "observe_area"), "none_reason": None, "manner": "", "remainder": None,
                                            "clarify": None})
    s = w.session()
    out = play(s, "do", "I wait and watch the yard.")
    assert out.ok, out
    assert hhmm(now(w)) == "13:00"                                   # 8 hours: no background row cut the window short
    led = w.store.query_one("SELECT detail FROM turn_ledger WHERE turn_index = 1 AND stage = 0")[0]
    import json
    assert json.loads(led)["timers_fired"] == 0
    assert len(rows(w, "ROUTINE_STEP")) >= 20 and len(rows(w, "SETTLEMENT_DAY")) == 1
    assert w.store.query_one("SELECT passed FROM commit_gate_log WHERE turn_index = 1")[0] == 1
    assert w.store.query_one("SELECT place_id FROM positions WHERE body_id = ?", (w.id("pc"),))[0] == w.id("yard")


def test_det_01_the_same_settlement_lives_the_same_life(scenario):
    """DET-01 across the society: two loads of one world, the same injury, the same forty hours —
    the same events and the same world, rng draws (drift, animosity) included."""
    from as_engine.kernel.hashing import world_state_hash
    from society_kit import injure
    out = []
    for _ in range(2):
        w = scenario("pump_settlement")
        injure(w, "hal")
        run(w, 40)
        evs = [(r[0], r[1], r[2]) for r in w.store.query("SELECT type, at, payload FROM events ORDER BY seq")]
        out.append((world_state_hash(w.store), evs))
    assert out[0][1] == out[1][1]
    assert out[0][0] == out[1][0]
