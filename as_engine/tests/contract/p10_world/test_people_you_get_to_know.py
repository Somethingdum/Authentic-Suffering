"""People you get to know (D-149). Rules BG-02..05 (service/background.py voicing; service/replay.py).

Most of a world's people are sketched by code (D-127, D-143), and a sketch plays as a sketch. Now, in the quiet
hours, someone generated whom the player's character has really talked with has their voice written by a model —
from the lines they actually said and what they went through with the PC — once.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from as_engine.contracts.common import CallClass
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.kernel import clock
from as_engine.mind.actor import fused
from as_engine.service import background as bg

pytestmark = pytest.mark.phase(10)

H = 3_600_000
VOICED = {"capsule": "June counts under her breath and only looks up when the sum is wrong.",
          "tendencies": ["answers with numbers", "says 'fine' when it is not"],
          "low_stakes": "Forty-one cans. Forty. Somebody ate one.", "under_pressure": "Count the doors. Now.",
          "at_the_limit": "It doesn't add up. None of it adds up any more."}


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def turn(w):
    return w.store.query_one("SELECT turn_index FROM world_clock")[0]


def next_turn(w):
    with w.store.transaction() as tx:
        clock.advance_event(tx, now(w) + H, "test")
        clock.begin_turn(tx, turn(w) + 1)
    return turn(w)


def generated(w, who):
    row = w.store.query_one("SELECT d.dossier_id, d.baseline_json FROM actors a JOIN dossiers d USING (dossier_id) "
                            "WHERE a.actor_id = ?", (w.id(who),))
    d = json.loads(row[1])
    d["generation"] = "generated"
    w.store.conn.execute("UPDATE dossiers SET baseline_json = ? WHERE dossier_id = ?", (json.dumps(d), row[0]))


def talk(w, who, to, words):
    t = now(w)
    with w.store.transaction() as tx:
        uid = tx.mint("evt")
        tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=t, turn_index=turn(w), actor_id=w.id(who),
                              payload={"words": words, "volume": "normal", "to": [w.id(to)], "source_db": 60, "armed": False,
                                       "utterance_id": uid},
                              writes=[WriteRecord(op=WriteOp.INSERT, table="voice_lines", values={
                                  "line_id": tx.mint("vln"), "actor_id": w.id(who), "text": words, "at": t, "event_id": uid,
                                  "pinned": 0})]))


def got_to_know(w):
    generated(w, "june")
    talk(w, "pc", "june", "How many cans left?")
    talk(w, "june", "pc", "Forty-one. I counted twice.")
    talk(w, "pc", "june", "Count them again.")


def voicing(jobs):
    return [j for j in jobs if j.kind == "voicing"]


def test_june_is_voiced_once(scenario, fake):
    w = scenario("metal_fence")
    got_to_know(w)
    T = next_turn(w)
    (job,) = voicing(bg.jobs(w.store, T))
    assert (job.subject_id, job.request_key) == (w.id("june"), f"voicing:{w.id('june')}")
    seen = {}

    def answer(r):
        seen["ctx"] = r.context
        return VOICED
    fake.script(CallClass.PERSON_VOICE, answer)
    res = asyncio.run(bg.run_job(w.session(), job))
    with w.store.transaction() as tx:
        bg.commit(tx, job, res, clock.now(tx), T)
    ctx = seen["ctx"]
    assert ctx.name == "June" and ctx.lines_said == ["Forty-one. I counted twice."]
    assert any(c.startswith("How they talk: ") for c in ctx.card)
    v = fused(w.store, w.id("june")).voice
    assert (v.capsule, v.speech_tendencies, v.exemplars.under_pressure) == (VOICED["capsule"], VOICED["tendencies"],
                                                                           VOICED["under_pressure"])
    assert voicing(bg.pending(w.store, T)) == [], "done at this boundary"
    assert voicing(bg.jobs(w.store, next_turn(w))) == [], "once each"


def test_unanswered_the_card_stands(scenario):
    """The fake model has nothing to say (every field null): the card stays, and she is not asked again."""
    w = scenario("metal_fence")
    got_to_know(w)
    before = fused(w.store, w.id("june")).voice
    T = next_turn(w)
    (job,) = voicing(bg.jobs(w.store, T))
    res = asyncio.run(bg.run_job(w.session(), job))
    with w.store.transaction() as tx:
        evs = bg.commit(tx, job, res, clock.now(tx), T)
    assert [e.type for e in evs] == [EventType.VOICE_WRITTEN]
    assert fused(w.store, w.id("june")).voice == before
    assert voicing(bg.jobs(w.store, next_turn(w))) == []


@pytest.mark.parametrize("case", ["authored", "barely_spoke"])
def test_who_is_not_voiced(scenario, case):
    w = scenario("metal_fence")
    if case == "authored":
        talk(w, "pc", "june", "How many cans left?")
        talk(w, "june", "pc", "Forty-one.")
        talk(w, "pc", "june", "Again.")
    else:
        generated(w, "june")
        talk(w, "pc", "june", "Hey.")
    assert voicing(bg.jobs(w.store, next_turn(w))) == []
