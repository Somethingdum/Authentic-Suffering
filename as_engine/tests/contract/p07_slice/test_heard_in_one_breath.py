"""Heard in one breath (D-284). mind/packet.py THREAD-01 (the conversation thread).

Owen asked Mara one long question; it reached her a few words at a time (SEG-01), and her thread kept the pieces:
'Owen to you: "Mara, is the water from the pump house"', then the middle of it, then 'Owen to you: "we boil it
first?"' — three of her eight lines for one question, each fragment weighed on its own. What was said as one thing is heard as one thing.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import LOD
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet

from slice_kit import play

pytestmark = pytest.mark.phase(7)

WORDS = "Mara, is the water from the pump house safe to drink, or should we boil it first?"


def test_one_question_one_line(scenario):
    w = scenario("metal_fence")
    s = w.session()
    s.extras["forced_addressee"] = w.id("mara")
    assert play(s, "say", "Quiet.").ok
    s.extras["forced_addressee"] = w.id("mara")
    o = play(s, "say", WORDS)
    assert o.ok
    pieces = w.store.query("SELECT COUNT(*) FROM events WHERE type='SPEECH' AND actor_id=? AND turn_index=?",
                           (w.id("pc"), o.turn_index))[0][0]
    assert pieces >= 2, "it was said in pieces"
    at = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id("mara"), at, o.turn_index + 1)
        aff = enumerate_affordances(tx, w.id("mara"), w.canon.all("affordance"), at, o.turn_index + 1)
        p = build_packet(tx, w.id("mara"), LOD.HOT, aff, o.turn_index + 1, at)
    owen = [x for x in p.thread if x.speaker != "you" and x.words != "Quiet."]
    assert [(x.words, x.to_me) for x in owen] == [(WORDS, True)], p.thread
    assert owen[0].unanswered == (not any(x.speaker == "you" for x in p.thread)), "one question, waiting on one answer"
