"""Let him finish (D-287). action/reactions.py REACT-01 (a speech percept addressed to the holder).

A long line reaches the one it is said to a few words at a time (SEG-01), and the first eight words were enough to
make her decide: Mara answered "Mara, I need you on the front window" before "while I check the back door and the
alley, and then the office" had been said — and, having answered, was not asked again (D-252). People let the
speaker finish and answer the whole of it; only words that already wound — a threat, an insult — make them cut in.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import CallClass

from slice_kit import play

pytestmark = pytest.mark.phase(7)

LONG = "Mara, I need you on the front window while I check the back door and the alley, and then the office."
THREAT = "Mara, I'll break your arm if you move, so stay right there by the window and keep your mouth shut."


def said_to_mara(w, fake, words):
    s = w.session()
    s.extras["forced_addressee"] = w.id("mara")
    assert play(s, "say", "Quiet.").ok                       # the crash out back has come and gone
    n = len([r for r in fake.calls(CallClass.ACTOR_REACTION) if r.actor_id == w.id("mara")])
    s.extras["forced_addressee"] = w.id("mara")
    o = play(s, "say", words)
    assert o.ok
    pieces = [r[0] for r in w.store.query("SELECT json_extract(payload,'$.words') FROM events WHERE type='SPEECH' AND "
                                          "actor_id=? AND turn_index=? ORDER BY seq", (w.id("pc"), o.turn_index))]
    assert len(pieces) >= 2, pieces
    calls = [r for r in fake.calls(CallClass.ACTOR_REACTION) if r.actor_id == w.id("mara")][n:]
    return pieces, calls


def heard(req):
    p = req.context.packet if hasattr(req.context, "packet") else req.context
    return [u.words for u in p.utterances]


def test_she_hears_him_out(scenario, fake):
    w = scenario("metal_fence")
    pieces, calls = said_to_mara(w, fake, LONG)
    assert len(calls) == 1, "one answer"
    assert heard(calls[0]) == [" ".join(pieces)], "to the whole of it, as one line (D-288)"


def test_a_threat_she_cuts_into(scenario, fake):
    w = scenario("metal_fence")
    pieces, calls = said_to_mara(w, fake, THREAT)
    assert calls and heard(calls[0]) == pieces[:1], "the threat is enough"
