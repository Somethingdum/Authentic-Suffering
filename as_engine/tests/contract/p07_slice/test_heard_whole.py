"""Heard whole (D-288). mind/packet.py S1..Sn and utterances; mind/memory.py MEM-01 (the percept rows of a turn).

A long line reaches the one it is said to a few words at a time (SEG-01), and since D-287 she lets the speaker finish
— but what she was then shown was still the pieces, each its own S# and each judged on its own: "Mara, I want to know
who left the" a statement, "back door open last night, and why" another, and only the last piece a question. What was
said once is one line in what she heard, judged on the whole of it, in her decision and in her memory of the turn alike.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import CallClass, UtteranceForm
from as_engine.mind import memory

from slice_kit import play

pytestmark = pytest.mark.phase(7)

ASKED = "Mara, I want to know who left the back door open last night, and why nobody told me?"


def test_one_question_heard_as_one(scenario, fake):
    w = scenario("metal_fence")
    s = w.session()
    s.extras["forced_addressee"] = w.id("mara")
    assert play(s, "say", "Quiet.").ok                       # the crash out back has come and gone
    n = len([r for r in fake.calls(CallClass.ACTOR_REACTION) if r.actor_id == w.id("mara")])
    s.extras["forced_addressee"] = w.id("mara")
    o = play(s, "say", ASKED)
    assert o.ok
    pieces = w.store.query("SELECT COUNT(*) FROM events WHERE type='SPEECH' AND actor_id=? AND turn_index=?",
                           (w.id("pc"), o.turn_index))[0][0]
    assert pieces >= 2, "it was said in pieces"
    calls = [r for r in fake.calls(CallClass.ACTOR_REACTION) if r.actor_id == w.id("mara")][n:]
    assert len(calls) == 1
    p = calls[0].context.packet if hasattr(calls[0].context, "packet") else calls[0].context
    mine = [u for u in p.utterances if u.speaker_handle and p.handles.get(u.speaker_handle) == w.id("pc")]
    assert [(u.words, u.form) for u in mine] == [(ASKED, UtteranceForm.QUESTION)], p.utterances
    at = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        a = memory.build_aftermath(tx, w.id("mara"), o.turn_index, at)
    later = [u for u in a.utterances if u.speaker_handle and a.handles.get(u.speaker_handle) == w.id("pc")]
    assert [(u.words, u.form) for u in later] == [(ASKED, UtteranceForm.QUESTION)], "her memory agrees"
