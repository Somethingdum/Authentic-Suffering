"""In one breath (D-283). narration/narrator.py (the packet's lines: one utterance, one speech line).

A long line is said a few words at a time (SEG-01: someone can cut in), and the narrator was handed each piece as a
remark of its own — 'Owen says, "Mara, I need you on the front window"' and then 'Owen says, "while I check the
back door."' — so the story told one sentence as two, or tripped on the second. Pieces of one utterance that follow
one another — with nothing between but what was only seen — are one line again, in the words as said.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import CallClass

from slice_kit import play

pytestmark = pytest.mark.phase(7)

WORDS = "Mara, I need you on the front window while I check the back door and the alley."


def test_said_in_one_breath(scenario, fake):
    """On a quiet turn (the crash out back has come and gone), while two of the crew settle in around him."""
    w = scenario("metal_fence")
    s = w.session()
    s.extras["forced_addressee"] = w.id("mara")
    assert play(s, "say", "Quiet.").ok
    s.extras["forced_addressee"] = w.id("mara")
    o = play(s, "say", WORDS)
    assert o.ok
    pieces = [r[0] for r in w.store.query("SELECT json_extract(payload,'$.words') FROM events WHERE type='SPEECH' AND actor_id=? "
                                          "AND turn_index=? ORDER BY seq", (w.id("pc"), o.turn_index))]
    assert len(pieces) >= 2 and " ".join(pieces) == WORDS, pieces
    (req,) = fake.calls(CallClass.NARRATION)[-1:]
    said = [ln for ln in req.context.lines if ln.kind == "speech" and ln.speaker == "Owen"]
    assert [ln.words for ln in said] == [WORDS], said
    assert said[0].text == f'Owen says, "{WORDS}"'
