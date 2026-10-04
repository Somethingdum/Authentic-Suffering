"""The room talks (D-128). Rules AMB-01 (mind/packet.py ambient_packet) and AMB-02..03 (turn/cognition.py
decide); CallClass.AMBIENT_LINE on lane B.

The owner: "We have a very very fast model. You might be able to use it for insignificant NPC dialogue."
and "If they all talk the same. If they're all the same, I'll crash out." Past the model budget a person
was moved by code (COLD) and never said a word, however many were in the room. Now the most salient of
them in the player's place get one short line each on lane B, in their own voice, about what reached them
— or say nothing. Their act stays code's; only their words were asked for, so a failed line is silence,
never a held decision.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.contracts.common import LOD, CallClass, Lane
from as_engine.contracts.events import Event, EventType
from as_engine.lanes.scheduler import CognitionPlan
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.physical import space
from as_engine.turn.cognition import decide

pytestmark = pytest.mark.phase(7)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def owen_asks(w, at, words="Anyone seen my lighter?"):
    """Owen asks the floor; Mara and Alice hear it."""
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", at, None, 0)
        ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("pc"), at=at, turn_index=0,
                                   payload={"words": words, "volume": "normal", "to": ["everyone"], "source_db": 60,
                                            "armed": False}))
        for x in ("mara", "alice"):
            perception.compile_scene(tx, w.id(x), at, 0)
            perception.compile_aftermath(tx, w.id(x), [ev], at + 500, 0)
    return ev


def moment(w, at, *, cold=("mara", "alice"), depth=None, b_down=False):
    """One wave (decide) at ``at`` with ``cold`` past the budget, most salient first."""
    s = w.session()
    if depth is not None:
        s.settings = s.settings.model_copy(update={"turn_depth": depth})
    if b_down:
        s.client.mark_down(Lane.B)
    ids = [w.id(a) for a in cold]
    with s.store.transaction() as tx:
        affs = {a: enumerate_affordances(tx, a, w.canon.all("affordance"), at, 0) for a in ids}
    plan = CognitionPlan(lod={a: LOD.COLD for a in ids}, order=ids)

    async def go():
        with s.store.transaction() as tx:
            return await decide(tx, s, plan, affs, 0, at, reaction=False)
    return s, asyncio.run(go())


def mara_says(w, line, to="pc", volume="normal"):
    def answer(r):
        h = next((k for k, v in r.context.handles.items() if v == w.id(to)), None) if to else None
        return {"line": line, "to": h, "volume": volume}
    return answer


def test_a_cold_person_says_one_line_in_her_own_voice(scenario, fake):
    w = scenario("metal_fence")
    t = now(w)
    owen_asks(w, t)
    fake.script(CallClass.AMBIENT_LINE, mara_says(w, "Check your pockets before you accuse anybody."), actor_id=w.id("mara"))
    _s, out = moment(w, t + 1000)
    mara, alice = out[w.id("mara")], out[w.id("alice")]
    assert mara.source == "ambient" and mara.speech.text == "Check your pockets before you accuse anybody."
    assert mara.speech.to == (w.id("pc"),) and mara.lod == LOD.COLD
    assert alice.speech is None and alice.source != "ambient", "unscripted, she keeps quiet"
    asked = fake.calls(CallClass.AMBIENT_LINE, actor_id=w.id("mara"))
    assert len(asked) == 1 and asked[0].lane == Lane.B
    pk = asked[0].context
    assert any("Anyone seen my lighter?" in r for r in pk.reached), pk.reached
    with w.store.transaction() as tx:
        from as_engine.mind.actor import fused
        assert fused(tx, w.id("mara")).voice.capsule in pk.voice
    assert w.id("pc") in pk.handles.values() and pk.where


def test_the_line_is_said_and_heard(scenario, fake):
    w = scenario("metal_fence")
    t = now(w)
    owen_asks(w, t)
    fake.script(CallClass.AMBIENT_LINE, mara_says(w, "Ask Alice. She smokes.", to=None, volume="raised"), actor_id=w.id("mara"))
    _s, out = moment(w, t + 1000)
    with w.store.transaction() as tx:
        resolve_wave(tx, w.rng, barrier(tx, [out[a] for a in sorted(out)]), t + 1000, 0, horizon_ms=t + 60_000)
    said = [json.loads(r[0]) for r in w.store.query("SELECT payload FROM events WHERE type = 'SPEECH' AND actor_id = ?",
                                                     (w.id("mara"),))]
    assert [(p["words"], p["to"], p["volume"]) for p in said] == [("Ask Alice. She smokes.", ["everyone"], "raised")]
    assert w.store.query("SELECT 1 FROM voice_lines WHERE actor_id = ? AND text = 'Ask Alice. She smokes.'", (w.id("mara"),))


def test_quotes_and_stage_directions_are_not_words(scenario, fake):
    w = scenario("metal_fence")
    t = now(w)
    owen_asks(w, t)
    fake.script(CallClass.AMBIENT_LINE, mara_says(w, '*shrugs* "Not my problem."'), actor_id=w.id("mara"))
    _s, out = moment(w, t + 1000)
    assert out[w.id("mara")].speech.text == "Not my problem."


def test_a_failed_line_is_silence_not_a_held_decision(scenario, fake):
    w = scenario("metal_fence")
    t = now(w)
    owen_asks(w, t)
    fake.fail(CallClass.AMBIENT_LINE, "timeout", actor_id=w.id("mara"))
    fake.script(CallClass.AMBIENT_LINE, lambda r: {"line": "*stares*", "to": None, "volume": "normal"}, actor_id=w.id("alice"))
    _s, out = moment(w, t + 1000)
    assert out[w.id("mara")].speech is None and out[w.id("alice")].speech is None
    assert not w.store.query("SELECT 1 FROM events WHERE type = 'DEGRADED_FALLBACK'")
    assert not w.store.query("SELECT 1 FROM error_repair_log")


def test_at_most_the_depth_allows_most_salient_first(scenario, fake):
    w = scenario("metal_fence")
    t = now(w)
    owen_asks(w, t)
    moment(w, t + 1000, cold=("alice", "mara"), depth="quick")
    assert [r.actor_id for r in fake.calls(CallClass.AMBIENT_LINE)] == [w.id("alice")]


def test_nobody_talks_to_the_air(scenario, fake):
    """Nothing reached them: no call. Lane B down: no call (never the Writer's time). Spoken already this
    turn: no second line."""
    w = scenario("metal_fence")
    t = now(w)
    moment(w, t + 1000)
    assert fake.calls(CallClass.AMBIENT_LINE) == []
    owen_asks(w, t + 2000)
    s, _out = moment(w, t + 3000, b_down=True)
    assert fake.calls(CallClass.AMBIENT_LINE) == []
    s.client.mark_down(Lane.B, False)
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("alice"), at=t + 2500, turn_index=0,
                              payload={"words": "Mm.", "volume": "low", "to": ["everyone"], "source_db": 45, "armed": False}))
    moment(w, t + 3000)
    assert [r.actor_id for r in fake.calls(CallClass.AMBIENT_LINE)] == [w.id("mara")]
