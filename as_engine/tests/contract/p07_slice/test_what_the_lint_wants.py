"""What the lint wants, said first (D-154). prompts narration.* (NARR-12); narration/lint.py.

The code lint throws a narration away for three sentences in a row that start with the same word, for too many
sentences built on 'was' or 'were' and a participle, for a mood named in the abstract and for a proper name the
character does not know — and the Writer was never told any of it: not the rules, not the names. Each throw is a
whole new draft on the slow lane (about a minute). Now the prompt says them before the first draft.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import CallClass
from as_engine.contracts.narration import NarratorLine, NarratorPacket
from as_engine.prompts.render import render

pytestmark = pytest.mark.phase(7)


def packet(**kw):
    base = dict(turn_index=3, world_time_text="23:14, day 18 since the Fall (night)", place_text="Sales floor", pc_name="Owen",
                lines=[NarratorLine(seconds=0.0, kind="sound", text="A loud metal crash came from the rear alley.")],
                allowed_names=["Mara", "Owen", "Owen Marsh", "Sales floor"])
    base.update(kw)
    return NarratorPacket(**base)


def test_the_rules_come_first():
    system, user = (m.content for m in render(CallClass.NARRATION, k=packet(), words=(160, 350), fix=None))
    assert 'Never start three sentences in a row with the same word' in system
    assert "Use the active voice" in system and "was or were" in system
    assert "Do not name moods" in system


def test_the_names_owen_knows():
    user = render(CallClass.NARRATION, k=packet(), words=(160, 350), fix=None)[1].content
    assert "Names Owen knows (use no other proper name outside quoted speech; describe anyone else): Mara, Owen, Owen Marsh, " \
           "Sales floor" in user
    alone = render(CallClass.NARRATION, k=packet(allowed_names=[]), words=(160, 350), fix=None)[1].content
    assert "Names Owen knows" not in alone


def test_words_lost_are_never_none():
    """D-157: a line of which only the tone was heard showed as 'a woman said: "None"' — the Writer was handed the
    word None to quote. Now it shows what was heard; a speaker is written with a capital first letter."""
    lost = NarratorLine(seconds=0.2, kind="speech", text="A woman says quietly; the words are lost.", speaker="a woman", words=None)
    said = NarratorLine(seconds=1.0, kind="speech", text='A woman says, "Forty-one."', speaker="a woman", words="Forty-one.")
    user = render(CallClass.NARRATION, k=packet(lines=[lost, said]), words=(160, 350), fix=None)[1].content
    assert "(speech): A woman says quietly; the words are lost." in user and '"None"' not in user
    assert '(speech): A woman said: "Forty-one."' in user


def test_the_judge_is_not_shown_none_either():
    from as_engine.contracts.calls import LintContext
    lost = NarratorLine(seconds=0.2, kind="speech", text="A woman says quietly; the words are lost.", speaker="a woman", words=None)
    ctx = LintContext(packet=packet(lines=[lost]), prose="She said something too low to catch.", sentences=["She said something too low to catch."])
    user = render(CallClass.RENDER_LINT, ctx=ctx)[1].content
    assert "A woman says quietly; the words are lost." in user and '"None"' not in user
