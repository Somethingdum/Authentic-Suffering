"""Talk already answered (D-252). turn/select.py SEL-03 talk_last_turn and decided_at; turn/pipeline.py S4 (the one
the PC speaks to waits to hear it) and S6 (listening: no line of the room from them); turn/cognition.py AMB-02.

Every turn of a conversation cost the one the player was talking to two model calls: one at the start of the turn —
on the Writer, with thinking — because something had been said the turn before and a question was still open, made
before the player's new words had reached them; and another when the words landed. What was said the turn before
they had already heard and answered in the reaction wave. And, made to wait, they said a line to the room.
"""

from __future__ import annotations

import json

import pytest
from slice_kit import play

from as_engine.contracts.common import CallClass
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.turn import select

pytestmark = pytest.mark.phase(7)

T = 3


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def heard(w, t):
    """At turn T - 1 Mara asks June something and June hears it at t + 300."""
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("mara"), at=t + 300,
                                   turn_index=T - 1, payload={"words": "Did you lock the back?", "volume": "normal",
                                                              "to": [w.id("june")], "source_db": 60, "armed": False}))
        perception.grant(tx, w.id("june"), event_id=ev.event_id, channel="speech", fidelity="exact",
                         text='Mara says to you, "Did you lock the back?"', source_id=w.id("mara"), at=t + 300,
                         turn_index=T - 1, detail={"words": "Did you lock the back?", "volume": "normal", "addressed_to_me": True})


def decided(w, waves, status="ok"):
    """June decided with a model in turn T - 1 in these waves (at, lod)."""
    w.store.conn.execute("INSERT INTO turn_ledger (turn_index, stage, status, detail) VALUES (?, 4, 'ok', ?)",
                         (T - 1, json.dumps({"waves": [{"wave": i, "at": at, "lod": {w.id("june"): lod}, "salience": {},
                                                        "mandatory": []} for i, (at, lod) in enumerate(waves)]})))
    w.store.conn.execute("INSERT INTO lm_calls (turn_index, seq, call_class, lane, actor_id, status, latency_ms, request_hash, "
                         "response_text) VALUES (?, 1, 'actor_reaction', 'B', ?, ?, 1, 'h', '{}')", (T - 1, w.id("june"), status))


def talk(w, who="june"):
    with w.store.transaction() as tx:
        return select.salience_flags(tx, w.id(who), [w.id(who)], w.id("pc"), T, now(w))["talk_last_turn"]


def test_answered_when_she_heard_it(scenario):
    w = scenario("metal_fence")
    t = now(w)
    heard(w, t)
    decided(w, [(t, "cold"), (t + 476, "warm")])
    assert not talk(w), "she reacted after it reached her: it is taken in"
    with w.store.transaction() as tx:
        assert select.decided_at(tx, w.id("june"), T - 1) == t + 476


def test_said_after_she_decided(scenario):
    w = scenario("metal_fence")
    t = now(w)
    heard(w, t)
    decided(w, [(t, "warm")])
    assert talk(w), "it reached her after she decided: still to be taken in"


def test_said_in_the_wave_she_decided_in(scenario):
    w = scenario("metal_fence")
    t = now(w)
    heard(w, t)
    decided(w, [(t + 300, "warm")])
    assert talk(w), "what is said in the wave she decides in lands after her decision"


def test_a_call_that_failed_took_nothing_in(scenario):
    w = scenario("metal_fence")
    t = now(w)
    heard(w, t)
    decided(w, [(t, "cold"), (t + 476, "warm")], status="failed")
    assert talk(w)
    with w.store.transaction() as tx:
        assert select.decided_at(tx, w.id("june"), T - 1) is None


def test_the_one_spoken_to_waits_to_hear_it(scenario, fake):
    """Two turns of the player talking to June: on the second, nothing she would decide before the words arrive is
    asked of a model for the talk alone, and she says no line to the room; the words reach her and she answers."""
    w = scenario("metal_fence")
    s = w.session()
    for words in ("June, did you hear that?", "June. Are you sure?"):
        s.extras["forced_addressee"] = w.id("june")
        out = play(s, "say", words)
        assert out.ok
    turn = out.turn_index
    led = json.loads(w.store.query_one("SELECT detail FROM turn_ledger WHERE turn_index=? AND stage=4", (turn,))[0])
    first = led["waves"][0]
    assert first["salience"][w.id("june")] == 0 and first["lod"][w.id("june")] == "cold", \
        "nothing else is going on for her: the talk alone waits for the words"
    assert not [r for r in fake.calls(CallClass.AMBIENT_LINE, actor_id=w.id("june")) if r.turn_index == turn]
    assert [r for r in fake.calls(CallClass.ACTOR_REACTION, actor_id=w.id("june")) if r.turn_index == turn], \
        "the words reach her and she answers"
