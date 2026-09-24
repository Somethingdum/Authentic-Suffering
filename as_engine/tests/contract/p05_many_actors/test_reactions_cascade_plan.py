"""Reaction gate (action/reactions.py), cascade table (action/cascade.py) and the cognition plan
(lanes/scheduler.plan_cognition). Rules REACT-01..04, TIME-02/04, CAS-01..09, G10, LOD-01."""

from __future__ import annotations

import json

import pytest

import helpers
from as_engine.action import cascade, reactions
from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.contracts.common import LOD, Lane
from as_engine.contracts.content import CascadeRuleDef
from as_engine.contracts.events import Event, EventType
from as_engine.contracts.settings import EngineConfig
from as_engine.lanes.scheduler import plan_cognition
from as_engine.mind import perception

pytestmark = pytest.mark.phase(5)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def commit(w, **ev):
    with w.store.transaction() as tx:
        return tx.commit_event(Event(turn_index=0, **ev))


def perceive_all(w, events, at, locals_):
    with w.store.transaction() as tx:
        for x in locals_:
            perception.compile_aftermath(tx, w.id(x), events, at, 0)


EVERYONE = ("pc", "mara", "alice", "june", "eli", "nita", "stranger")


# --------------------------------------------------------------------------- materiality
def test_a_loud_crash_is_material_to_everyone_who_heard_it_well(scenario):
    w = scenario("metal_fence")
    ev = commit(w, type=EventType.NOISE, writer="action.propagate", at=now(w),
                payload={"source_db": 98, "kind": "metal_crash", "text": "a loud metal crash",
                         "place_id": w.id("alley"), "anchor_id": w.id("fence_sheet")})
    perceive_all(w, [ev], now(w) + 100, EVERYONE)
    with w.store.transaction() as tx:
        got = reactions.material_holders(tx, [ev], 0)
    who = {w.local(h) for h, _t in got}
    heard_well = {w.local(r["holder_id"]) for r in w.store.query(
        "SELECT holder_id FROM percept_log WHERE event_id = ? AND fidelity IN ('exact','partial')", (ev.event_id,))}
    assert who == heard_well and "nita" in who and "stranger" in who
    assert all(t == ev.at for _h, t in got) and got == sorted(got, key=lambda x: (x[1], x[0]))


def test_speech_is_material_only_to_whom_it_was_addressed(scenario):
    w = scenario("metal_fence")
    ev = commit(w, type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("mara"), at=now(w),
                payload={"words": "June, stay where you are.", "volume": "normal", "to": [w.id("june")], "source_db": 60})
    perceive_all(w, [ev], now(w) + 100, EVERYONE)
    with w.store.transaction() as tx:
        got = [w.local(h) for h, _t in reactions.material_holders(tx, [ev], 0)]
    assert "june" in got or not w.store.query_one(
        "SELECT 1 FROM percept_log WHERE holder_id = ? AND event_id = ? AND fidelity IN ('exact','partial')", (w.id("june"), ev.event_id))
    assert "mara" not in got, "never your own event"
    assert "alice" not in got and "pc" not in got, "overheard, not addressed"


def test_seeing_a_gun_raised_at_you(scenario):
    w = scenario("empty_gun")
    with w.store.transaction() as tx:
        evs = resolve_wave(tx, w.rng, barrier(tx, [helpers.make_intent(w, "reggie", "shoot_center_mass", target="carl",
                                                                       item="pistol")]), now(w), 0, horizon_ms=now(w) + 5000)
    perceive_all(w, evs, now(w) + 1000, ("carl", "pc"))
    with w.store.transaction() as tx:
        got = dict(reactions.material_holders(tx, evs, 0))
    assert w.id("carl") in got and got[w.id("carl")] == evs[0].at, "the raised gun, at the start"


def test_reaction_time_and_waves(scenario):
    w = scenario("metal_fence")
    ev = commit(w, type=EventType.NOISE, writer="action.propagate", at=now(w),
                payload={"source_db": 98, "kind": "metal_crash", "text": "a loud metal crash",
                         "place_id": w.id("alley"), "anchor_id": w.id("fence_sheet")})
    perceive_all(w, [ev], now(w) + 100, EVERYONE)
    with w.store.transaction() as tx:
        assert reactions.reaction_time(tx, helpers.ScriptedRng(200), w.id("nita"), ev.at) == ev.at + 200
        assert reactions.reaction_time(tx, helpers.ScriptedRng(200), w.id("mara"), ev.at) == ev.at + 200
        t, holders = reactions.next_wave(tx, w.rng, [ev], 0, 1, now(w) + 60_000)
        assert t is not None and ev.at + 150 <= t <= ev.at + 250 and w.id("nita") in holders
        t2, over = reactions.next_wave(tx, w.rng, [ev], 0, 4, now(w) + 60_000)
        assert t2 is None and set(over) == set(holders), "past the cap: nobody is dropped, the caller parks them"
        t3, none = reactions.next_wave(tx, w.rng, [ev], 0, 1, ev.at + 100)
        assert (t3, none) == (None, []), "reactions after the horizon wait for the next transaction"


# --------------------------------------------------------------------------- cascade expressions
@pytest.mark.parametrize("expr,expected", [
    ("trigger.payload.source_db >= 80", True),
    ("trigger.payload.source_db > 98", False),
    ("trigger.payload.kind == 'metal_crash'", True),
    ('trigger.payload.kind != "metal_crash"', False),
    ("trigger.payload.outdoor == true", True),
    ("trigger.payload.source_db >= 80 and trigger.payload.outdoor == false", False),
    ("trigger.payload.missing_key == 1", False),
    ("trigger.type == 'NOISE'", True),
    ("trigger.payload.source_db < 98.5", True),
])
def test_precondition_grammar(scenario, expr, expected):
    w = scenario("metal_fence")
    ev = commit(w, type=EventType.NOISE, writer="action.propagate", at=now(w),
                payload={"source_db": 98, "kind": "metal_crash", "outdoor": True, "place_id": w.id("alley")})
    with w.store.transaction() as tx:
        assert cascade.evaluate_precondition(tx, expr, ev) is expected


def test_bad_precondition(scenario):
    w = scenario("metal_fence")
    ev = commit(w, type=EventType.NOISE, writer="action.propagate", at=now(w), payload={"source_db": 1})
    with w.store.transaction() as tx:
        with pytest.raises(ValueError):
            cascade.evaluate_precondition(tx, "source_db is loud", ev)


def test_p5_selectors(scenario):
    w = scenario("metal_fence")
    start = commit(w, type=EventType.ACTION_START, writer="action.resolve", actor_id=w.id("june"), at=now(w),
                   payload={"actor_id": w.id("june"), "def_id": "go_look", "continues_task": False})
    with w.store.transaction() as tx:
        assert cascade.select(tx, "actor(trigger.actor_id)", start) == [w.id("june")]
        assert cascade.select(tx, "place_of(trigger.actor_id)", start) == [w.id("storeroom")]
        tid = tx.query_one("SELECT task_id FROM tasks WHERE actor_id = ?", (w.id("june"),))[0]
        assert cascade.select(tx, "active_task_of(trigger.actor_id)", start) == [tid]
        assert cascade.select(tx, "active_task_of(trigger.payload.nobody)", start) == [], "CAS-07: nothing selected"


def _cas014(canon):
    return [r for r in canon.all("cascade") if r.id == "CAS-014"]


def test_cas014_pauses_the_task_and_cites_the_rule(scenario, canon):
    """Starting something else in the middle of counting pauses the count where it stands."""
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        evs = resolve_wave(tx, w.rng, barrier(tx, [helpers.make_intent(w, "june", "go_look", destination="back_door_in")]),
                           now(w), 0, horizon_ms=now(w) + 60_000)
        out = cascade.sweep(tx, evs, _cas014(canon), now(w), 0)
    (step,) = [e for e in out if e.type == "TASK_STEP"]
    assert step.payload["status"] == "paused" and step.payload["steps_done"] == 41
    assert step.rule_cited == "CAS-014" and step.payload["_cascade_depth"] == 1
    row = w.store.query_one("SELECT rule_cited FROM events WHERE event_id = ?", (step.event_id,))
    assert row[0] == "CAS-014", "G10: stored on the event row"


def test_keep_working_does_not_pause(scenario, canon):
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        evs = resolve_wave(tx, w.rng, barrier(tx, [helpers.make_intent(w, "june", "keep_working")]), now(w), 0,
                           horizon_ms=now(w) + 60_000)
        out = cascade.sweep(tx, evs, _cas014(canon), now(w), 0)
    assert not [e for e in out if e.type == "TASK_STEP" and e.payload.get("status") == "paused"]


def test_cascade_depth_stops_at_three(scenario):
    """CAS-02: a rule that feeds itself fires three times, not forever."""
    w = scenario("metal_fence")
    rule = CascadeRuleDef.model_validate({
        "schema": "as.cascade.v1", "id": "CAS-900", "description": "Test: every Resolve loss causes another.",
        "trigger_event": "RESOLVE_CHANGE", "where": {}, "preconditions": [],
        "effects": [{"kind": "drain_resolve", "target": "actor(trigger.actor_id)", "amount": 1, "payload": {"cause": "coerced"}}]})
    with w.store.transaction() as tx:
        from as_engine.mind.resolve import drain
        first = drain(tx, w.id("mara"), "coerced", None, now(w), 0)
        out = cascade.sweep(tx, [first], [rule], now(w), 0)
    drains = [e for e in out if e.type == "RESOLVE_CHANGE"]
    assert [e.payload["_cascade_depth"] for e in drains] == [1, 2, 3]
    assert all(e.rule_cited == "CAS-900" for e in drains)


def test_an_unbuilt_owner_is_audited_not_fatal(scenario, monkeypatch):
    """CAS-09: when an owner or selector is not built yet (NotImplementedError), the dispatch is
    recorded in audit_log and skipped — the sweep goes on."""
    w = scenario("metal_fence")
    rule = CascadeRuleDef.model_validate({
        "schema": "as.cascade.v1", "id": "CAS-901", "description": "Test: grief reaches the household.",
        "trigger_event": "NOISE", "where": {}, "preconditions": [],
        "effects": [{"kind": "emit_event", "event_type": "HOUSEHOLD_CHANGE", "target": "household_of(trigger.actor_id)",
                     "payload": {"change": "test"}}]})

    def unbuilt(*_a, **_k):
        raise NotImplementedError("P9")
    monkeypatch.setattr(cascade, "select", unbuilt)
    ev = commit(w, type=EventType.NOISE, writer="action.propagate", actor_id=w.id("nita"), at=now(w), payload={"source_db": 30})
    with w.store.transaction() as tx:
        out = cascade.sweep(tx, [ev], [rule], now(w), 0)
    assert out == []
    (row,) = [dict(r) for r in w.store.query("SELECT * FROM audit_log WHERE gate = 'G10-cascade'")]
    assert (row["producer"], row["result"]) == ("action.cascade", "warn")
    assert json.loads(row["findings"])[0]["kind"] == "cascade_unbuilt" and json.loads(row["findings"])[0]["rule_id"] == "CAS-901"


# --------------------------------------------------------------------------- cognition plan
def test_plan_cognition_fills_hot_then_warm_then_cold():
    cfg = EngineConfig()
    cands = [("a1", 5.0, False), ("a2", 9.0, False), ("a3", 1.0, True), ("a4", 7.0, False), ("a5", 3.0, False)]
    p = plan_cognition(cands, cfg, "balanced", {Lane.A, Lane.B})
    # mandatory a3 first, then a2 (9): max_hot balanced = 2
    assert [a for a, l in p.lod.items() if l == LOD.HOT] == ["a3", "a2"] and all(p.lane[a] == Lane.A for a in ("a3", "a2"))
    assert p.lod["a4"] == LOD.WARM and p.lane["a4"] == Lane.B, "the idle lane first"
    assert set(p.lod) == {"a1", "a2", "a3", "a4", "a5"}
    assert p.est_wall_s <= cfg.rules.scheduler.turn_budget_s["balanced"] - cfg.rules.scheduler.reserve_narration_s or p.overrun


def test_plan_cognition_without_lane_a_has_no_hot():
    p = plan_cognition([("a1", 5.0, True), ("a2", 1.0, False)], EngineConfig(), "deep", {Lane.B})
    assert LOD.HOT not in p.lod.values() and p.lod["a1"] == LOD.WARM and p.lane["a1"] == Lane.B


def test_plan_cognition_budget_and_mandatory_overrun():
    cfg = EngineConfig()
    many = [(f"m{i:02d}", 1.0, True) for i in range(30)]
    p = plan_cognition(many, cfg, "quick", {Lane.A, Lane.B})
    assert all(l in (LOD.HOT, LOD.WARM) for l in p.lod.values()), "mandatory actors always get a call"
    assert p.overrun and any(n.startswith("BUDGET_OVERRUN") for n in p.notes)
    optional = [(f"o{i:02d}", 1.0, False) for i in range(30)]
    q = plan_cognition(optional, cfg, "quick", {Lane.A, Lane.B})
    assert not q.overrun and LOD.COLD in q.lod.values()


def test_no_lanes_everyone_cold():
    p = plan_cognition([("a", 1.0, True)], EngineConfig(), "balanced", set())
    assert p.lod == {"a": LOD.COLD} and "NO_LANES" in p.notes
