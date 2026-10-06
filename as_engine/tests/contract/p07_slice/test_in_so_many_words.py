"""In so many words (D-290). turn/intake.py INTAKE-04 and INTAKE-09; contracts/mind.py IntakeOutput.words.

The player typed "I ask the nearest person what's going on here." in the Say box, and Owen said, word for word, "I
ask the nearest person what's going on here." — the narrator quoted it, and his memory kept it. Typed in the Do box,
"I ask Mara where the water came from" found the option to speak to her and no words to say. People tell what their
character says as often as they quote it: the intake gives the words said aloud, and a Say line that only tells what
is said is read as the telling it is. Words the player quoted, and words that are simply words ("I say we leave
tonight."), are said as typed.
"""

from __future__ import annotations

import pytest
from slice_kit import events, pick, play

from as_engine.contracts.common import CallClass

pytestmark = pytest.mark.phase(7)

ASKED = "Mara, where did the water come from?"


def said(w, s, turn):
    return " ".join(e["payload"]["words"] for e in events(w, "SPEECH", turn) if e["actor_id"] == s.pc_id), \
        {b for e in events(w, "SPEECH", turn) if e["actor_id"] == s.pc_id for b in e["payload"]["to"]}


def asked(w, fake):
    seen = []

    def answer(r):
        seen.append(r.messages[0].content)
        return {"choice": pick(w, r, "speak", target="mara"), "none_reason": None, "manner": "", "gesture": None,
                "remainder": None, "clarify": None, "words": ASKED}
    fake.script(CallClass.INTAKE, answer)
    return seen


@pytest.mark.parametrize("mode", ["do", "say"])
def test_told_not_quoted(scenario, fake, mode):
    w = scenario("metal_fence")
    s = w.session()
    assert play(s, "say", "Quiet.").ok                       # the crash out back has come and gone
    seen = asked(w, fake)
    o = play(s, mode, "I ask Mara where the water came from.")
    assert o.ok, o.rejected_message
    assert len(seen) == 1 and '"words"' in seen[0], "the intake was asked, and told it may give the words"
    words, to = said(w, s, o.turn_index)
    assert (words, to) == (ASKED, {w.id("mara")})


def test_words_are_words(scenario, fake):
    w = scenario("metal_fence")
    s = w.session()
    assert play(s, "say", "Quiet.").ok
    seen = asked(w, fake)
    for text in ("I say we leave tonight.", "I tell you, it wasn't me."):
        o = play(s, "say", text)
        assert o.ok, o.rejected_message
        assert said(w, s, o.turn_index)[0] == text
    assert seen == [], "no intake call for words said as typed"
