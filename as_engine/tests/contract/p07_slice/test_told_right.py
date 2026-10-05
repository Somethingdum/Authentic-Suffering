"""Told right (D-236). Rule TEXT-01 (mind/perception.py retell: RETELL_OBJECT_AFTER, RETELL_ADVERBS, RETELL_PAST).

What is written to "you" is told again of someone else — the player's own doings in the story's lines, a menu label in
a memory, how a person feels about someone in the quiet hours. A "you" after a verb was taken for the one doing it:
"Mara tells you to get down" came out "Mara tells she toes get down", "they owe you their life" came out "they owe she
theirs life", and "you mostly trust them" came out "she mostlies trust them"; "before you could" came out "before her
could". A "you" a verb acts on is its object; a "you" a modal follows is the one doing it.
"""

from __future__ import annotations

import pytest

from as_engine.mind.perception import retell

pytestmark = pytest.mark.phase(7)


@pytest.mark.parametrize("said, she, me", [
    ("Mara tells you to get down", "Mara tells her to get down", "Mara tells me to get down"),
    ("they owe you their life", "they owe her their life", "they owe me their life"),
    ("they make you uneasy", "they make her uneasy", "they make me uneasy"),
    ("you mostly trust them", "she mostly trusts them", "I mostly trust them"),
    ("before you could move", "before she could move", "before I could move"),
    ("more than you can carry", "more than she can carry", "more than I can carry"),
    ("before you're seen", "before she's seen", "before I'm seen"),
    ("what you grew up hearing", "what she grew up hearing", "what I grew up hearing"),
    ("Push the man away from you", "Push the man away from her", "Push the man away from me"),
])
def test_told_right(said, she, me):
    assert [retell(said, "third", "female"), retell(said, "first")] == [she, me]


FEELINGS = ("you would trust them with your life", "you trust them", "you mostly trust them", "you are wary of them",
            "you distrust them", "you do not trust them at all", "they make you uneasy", "you fear them",
            "you are terrified of them", "you think well of them", "you respect them", "you look up to them",
            "you think little of them", "you look down on them", "you despise them", "you like them", "you care about them",
            "you love them", "you dislike them", "you can't stand them", "you hate them", "you resent them",
            "you will not forgive them", "you owe them", "you owe them a great deal", "you owe them your life",
            "they owe you", "they owe you a great deal", "they owe you their life")


def test_every_feeling_told_of_someone_else():
    """Each of the packet's words for a feeling (mind/packet.py relationships, D-165), told of a woman, reads as
    English: 'she' only where she is the one feeling it, no word given an -s it should not have."""
    bad = []
    for text in FEELINGS:
        told = retell(text, "third", "female")
        if (" she " in f" {told} " and not told.startswith("she ")) or any(w in f"{told} " for w in ("ies ", "theirs ", " as ")):
            bad.append((text, told))
    assert bad == []
