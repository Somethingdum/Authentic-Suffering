"""The wave resolver and the intent barrier (P5). Rules RESOLVE-01..06, G7, G8, BARRIER-01,
HALLUC-01, TIME-05 (action/resolve.py, action/intent.py barrier)."""

from __future__ import annotations

import dataclasses
import json

import pytest

import helpers
from as_engine.action.intent import barrier, intent_from_dict, intent_to_dict
from as_engine.action.resolve import land_pending, resolve_wave
from as_engine.kernel import clock

pytestmark = pytest.mark.phase(5)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def wave(w, intents, *, at=None, horizon=60_000, rng=None):
    t = now(w) if at is None else at
    with w.store.transaction() as tx:
        return resolve_wave(tx, rng or w.rng, barrier(tx, intents), t, 0, horizon_ms=t + horizon)


def types(evs, actor=None):
    return [e.type for e in evs if actor is None or e.actor_id == actor]


# --------------------------------------------------------------------------- barrier
def test_barrier_mutates_nothing_and_keeps_order(scenario):
    """BARRIER-01: validation reads only; every intent comes back, in order."""
    w = scenario("empty_gun")
    ints = [helpers.make_intent(w, "reggie", "pick_up_item", target="crowbar", destination="workbench"),
            helpers.make_intent(w, "carl", "wait_here")]
    n = w.store.query_one("SELECT COUNT(*) FROM events")[0]
    with w.store.transaction() as tx:
        out = barrier(tx, ints)
    assert w.store.query_one("SELECT COUNT(*) FROM events")[0] == n
    assert [i.actor_id for i in out] == [i.actor_id for i in ints]
    assert out[0].blocked == "referent_missing", "the crowbar is in the tool room, not on the workbench"
    assert out[1].blocked is None and out[1] == ints[1]


def test_a_believed_item_that_is_not_there_is_blocked_not_conjured(scenario):
    """HALLUC-01: reaching for the believed crowbar ends in ACTION_BLOCKED; no crowbar moves."""
    w = scenario("empty_gun")
    evs = wave(w, [helpers.make_intent(w, "reggie", "pick_up_item", target="crowbar", destination="workbench")])
    (blk,) = [e for e in evs if e.type == "ACTION_BLOCKED"]
    assert blk.payload == {"actor_id": w.id("reggie"), "def_id": "pick_up_item", "cause": "referent_missing"}
    assert types(evs) == ["ACTION_BLOCKED"], "not started, not landed"
    it = w.store.query_one("SELECT place_id, anchor_id FROM items WHERE item_id = ?", (w.id("crowbar"),))
    assert tuple(it) == (w.id("tool_room"), w.id("hooks"))


def test_a_referent_that_never_existed(scenario):
    w = scenario("metal_fence")
    i = helpers.make_intent(w, "pc", "shoot_center_mass", target="act_999999", item="glock")
    with w.store.transaction() as tx:
        assert barrier(tx, [i])[0].blocked == "referent_missing"


# --------------------------------------------------------------------------- order and time
def test_starts_first_then_landings_in_time_order(scenario):
    w = scenario("metal_fence")
    t = now(w)
    june = helpers.make_intent(w, "june", "go_look", destination="back_door_in")          # 4.2 s
    alice = helpers.make_intent(w, "alice", "crouch")                                      # 1 s
    evs = wave(w, [june, alice])
    starts = [e for e in evs if e.type == "ACTION_START"]
    assert [e.actor_id for e in starts] == sorted([w.id("june"), w.id("alice")]) and all(e.at == t for e in starts)
    completes = [e for e in evs if e.type == "ACTION_COMPLETE"]
    assert [e.actor_id for e in completes] == [w.id("alice"), w.id("june")]
    assert [e.at for e in completes] == [t + 1000, t + 4202]
    assert [e.seq for e in evs] == sorted(e.seq for e in evs)


def test_speech_is_heard_at_the_start(scenario):
    """Talking while acting: the words go out at T; the action lands later."""
    w = scenario("metal_fence")
    t = now(w)
    i = helpers.make_intent(w, "mara", "close_portal", target="storeroom_door",
                            speech=("June, stay where you are.", ["june"], "raised"))
    evs = wave(w, [i])
    sp = [e for e in evs if e.type == "SPEECH"][0]
    assert sp.at == t and sp.writer == "action.propagate" and sp.actor_id == w.id("mara")
    (start,) = [e for e in evs if e.type == "ACTION_START"]
    assert sp.payload == {"words": "June, stay where you are.", "volume": "raised", "to": [w.id("june")],
                          "source_db": 70.0, "armed": False, "utterance_id": start.event_id, "segment": 1, "segments": 1}
    assert types(evs)[:2] == ["ACTION_START", "SPEECH"]


def test_armed_speech_is_marked(scenario):
    w = scenario("metal_fence")
    evs = wave(w, [helpers.make_intent(w, "pc", "wait_here", speech=("Nobody move.", ["everyone"], "shout"))])
    sp = [e for e in evs if e.type == "SPEECH"][0]
    assert sp.payload["armed"] is True and sp.payload["to"] == ["everyone"], "the Glock is in his hand"


# --------------------------------------------------------------------------- the horizon
def test_an_action_past_the_horizon_is_queued_then_lands(scenario):
    w = scenario("metal_fence")
    t = now(w)
    run = helpers.make_intent(w, "mara", "run_to_anchor", destination="storeroom_door_front")
    evs = wave(w, [run], horizon=3_000)
    assert types(evs) == ["ACTION_START", "TIMER_SET"], "started, not landed"
    (row,) = clock.pending_for(w.store, "ACTION_LAND", w.id("mara"))
    assert row["due_at"] == t + 4129
    payload = json.loads(row["payload"])
    assert payload["start_event_id"] == evs[0].event_id and intent_from_dict(payload["intent"]).bound == run.bound
    assert w.store.query_one("SELECT anchor_id FROM positions WHERE body_id = ?", (w.id("mara"),))[0] == w.id("front_window")
    with w.store.transaction() as tx:
        fired = clock.fire(tx, row, 1)
        out = land_pending(tx, w.rng, row, 1, horizon_ms=t + 10_000)
    assert fired.type == "TIMER_FIRED" and fired.at == t + 4129
    assert [e.type for e in out] == ["MOVE", "NOISE", "ACTION_COMPLETE"]
    assert out[-1].cause_event_id == evs[0].event_id and out[0].at == t + 4129
    assert w.store.query_one("SELECT anchor_id FROM positions WHERE body_id = ?", (w.id("mara"),))[0] == w.id("storeroom_door_front")


def test_a_new_action_interrupts_a_pending_one(scenario):
    w = scenario("metal_fence")
    t = now(w)
    wave(w, [helpers.make_intent(w, "mara", "run_to_anchor", destination="storeroom_door_front")], horizon=3_000)
    evs = wave(w, [helpers.make_intent(w, "mara", "wait_here")], at=t + 2_000, horizon=3_000)
    assert types(evs)[:3] == ["TIMER_CANCELLED", "ACTION_INTERRUPT", "ACTION_START"]
    intr = [e for e in evs if e.type == "ACTION_INTERRUPT"][0]
    assert intr.payload == {"actor_id": w.id("mara"), "def_id": "run_to_anchor", "cause": "new_action"}
    assert clock.pending_for(w.store, "ACTION_LAND", w.id("mara")) == []


def test_choosing_the_same_thing_again_carries_on(scenario):
    w = scenario("metal_fence")
    t = now(w)
    run = helpers.make_intent(w, "mara", "run_to_anchor", destination="storeroom_door_front")
    wave(w, [run], horizon=3_000)
    evs = wave(w, [run], at=t + 2_000, horizon=3_000)
    assert evs == [] and len(clock.pending_for(w.store, "ACTION_LAND", w.id("mara"))) == 1


# --------------------------------------------------------------------------- exactly once
def test_each_intent_resolves_exactly_once(scenario):
    """G8: one START and one COMPLETE/BLOCKED per intent — even when two contest one resource."""
    w = scenario("metal_fence")
    ints = [helpers.make_intent(w, "pc", "open_portal", target="office_door"),
            helpers.make_intent(w, "mara", "open_portal", target="office_door"),
            helpers.make_intent(w, "alice", "crouch")]
    evs = wave(w, ints)
    for i in ints:
        mine = [e for e in evs if e.actor_id == i.actor_id and e.type in ("ACTION_START", "ACTION_COMPLETE", "ACTION_BLOCKED")]
        assert [e.type for e in mine][0] == "ACTION_START" and len(mine) == 2, [e.type for e in mine]


def test_intent_dict_round_trip(scenario):
    w = scenario("two_skills")
    i = helpers.make_intent(w, "twin_a", "shoot_head", target="shambler", item="gun_a", manner="careful",
                            speech=("Down!", ["everyone"], "shout"))
    d = intent_to_dict(i)
    assert json.loads(json.dumps(d)) == d, "JSON-safe"
    assert intent_from_dict(d) == i
    blocked = dataclasses.replace(i, blocked="referent_missing")
    assert intent_from_dict(intent_to_dict(blocked)) == blocked
