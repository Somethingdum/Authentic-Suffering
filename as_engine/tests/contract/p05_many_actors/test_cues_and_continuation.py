"""Cues present to a mind (mind/cues.py) and COLD plan continuation (action/intent.py). Rules
LOD-01/02: a COLD actor keeps doing what it decided — a reflex first, then its standing order,
its task, its plan, its post."""

from __future__ import annotations

import pytest

from as_engine.action.intent import plan_continuation
from as_engine.contracts.events import Event, EventType
from as_engine.contracts.settings import PacketRules, RulesConfig
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.cues import SENSORY_CUES_P5, cues_of

pytestmark = pytest.mark.phase(5)

WIDE = RulesConfig(packet=PacketRules(max_affordances=200))


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def commit(w, **ev):
    with w.store.transaction() as tx:
        return tx.commit_event(Event(turn_index=0, **ev))


def crash(w, at=None):
    return commit(w, type=EventType.NOISE, writer="action.propagate", at=now(w) if at is None else at,
                  payload={"source_db": 98, "kind": "metal_crash", "text": "a loud metal crash",
                           "place_id": w.id("alley"), "anchor_id": w.id("fence_sheet")})


def cues(w, local, at):
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(local), at, 0)
        return cues_of(tx, w.id(local), 0, at)


def test_the_crash_is_loud_and_metal(scenario):
    w = scenario("metal_fence")
    crash(w)
    for local in ("june", "mara", "nita"):
        c = cues(w, local, now(w) + 500)
        assert {"loud_noise", "metal_crash"} <= c, (local, c)
        assert c <= SENSORY_CUES_P5
    assert "dark_room" in cues(w, "june", now(w) + 500), "the stockroom's light is 1"


def test_being_called_by_name(scenario):
    w = scenario("metal_fence")
    commit(w, type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("mara"), at=now(w),
           payload={"words": "June, stay where you are.", "volume": "raised", "to": [w.id("june")], "source_db": 70})
    c = cues(w, "june", now(w) + 500)
    assert "addressed_by_name" in c and "voice_unknown" not in c
    commit(w, type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("stranger"), at=now(w) + 600,
           payload={"words": "Hey. You in there.", "volume": "shout", "to": ["everyone"], "source_db": 85})
    assert "voice_unknown" in cues(w, "nita", now(w) + 1_000)


def test_a_weapon_pointed_is_a_threat(scenario):
    w = scenario("request_firewall")
    commit(w, type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("pc"), at=now(w),
           payload={"words": "Put it down.", "volume": "raised", "to": [w.id("mara")], "source_db": 70, "armed": True})
    c = cues(w, "mara", now(w) + 500)
    assert {"weapon_pointed", "threat_seen"} <= c


def test_seeing_an_infected(scenario):
    w = scenario("two_skills")
    c = cues(w, "twin_a", now(w))
    assert {"infected_seen", "threat_seen"} <= c and "infected_close" not in c, "4.6 m away"


def test_cues_read_only(scenario):
    w = scenario("metal_fence")
    crash(w)
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id("june"), now(w) + 500, 0)
    n = w.store.query_one("SELECT COUNT(*) FROM events")[0]
    with w.store.transaction() as tx:
        cues_of(tx, w.id("june"), 0, now(w) + 500)
    assert w.store.query_one("SELECT COUNT(*) FROM events")[0] == n


# --------------------------------------------------------------------------- plan continuation
def cont(w, local, at):
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(local), at, 0)
        aff = enumerate_affordances(tx, w.id(local), w.canon.all("affordance"), at, 0)
        return plan_continuation(tx, w.id(local), aff, at, 0)


def test_a_reflex_comes_first(scenario):
    """Alice's training: a loud noise -> take cover (dossier trained_responses)."""
    w = scenario("metal_fence", rules=WIDE)
    crash(w)
    i = cont(w, "alice", now(w) + 500)
    assert (i.source, i.bound.verb.value, i.lod.value) == ("reflex", "take_cover", "cold")


def test_a_standing_order_when_the_reflex_has_no_option(scenario):
    """Mara's reflex is 'guard'; with no guard option offered, her standing order (loud noise ->
    find the source) makes her watch."""
    w = scenario("metal_fence")
    crash(w)
    i = cont(w, "mara", now(w) + 500)
    assert (i.source, i.bound.def_id) == ("plan", "observe_area")


def test_the_task_goes_on(scenario):
    w = scenario("metal_fence")
    i = cont(w, "june", now(w))
    assert (i.source, i.bound.def_id) == ("plan", "keep_working")
    assert i.goal and i.manner == "" and i.private_reason == ""


def test_nothing_to_do_means_watching(scenario):
    w = scenario("metal_fence")
    i = cont(w, "nita", now(w))
    assert i.bound.def_id in ("observe_area", "wait_here")
    assert i.goal == "finish the perimeter walk", "actors.goal_text"
