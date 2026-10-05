"""A word not left on its own (D-239). action/intent.py segments (SEG-01).

Speech goes out eight words at a time. "I ask the nearest person what's going on here." went out as the first
eight words and then, three seconds later and to everyone who heard it, "here." — a word on its own, an utterance
of its own in every listener's memory and in the story. When nothing in the eight ends a clause and only a few
words would be left over, the speech is cut in half instead.
"""

from __future__ import annotations

import pytest

from as_engine.action.intent import SEGMENT_WORDS, segments

pytestmark = pytest.mark.phase(5)


@pytest.mark.parametrize("text,expected", [
    ("I ask the nearest person what's going on here.", ["I ask the nearest person", "what's going on here."]),
    ("stay low and keep away from that window now", ["stay low and keep away", "from that window now"]),
    ("stay low and keep away from that window because they can see the light from outside or",
     ["stay low and keep away from that window", "because they can see the", "light from outside or"]),
])
def test_no_word_left_on_its_own(text, expected):
    assert segments(text) == expected
    assert all(len(s.split()) <= SEGMENT_WORDS for s in segments(text))
    assert " ".join(segments(text)) == " ".join(text.split())


def test_every_tail_has_company():
    """However long the speech, no segment after the first is shorter than four words unless the whole speech
    is that short."""
    words = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen".split()
    for n in range(1, len(words) + 1):
        segs = segments(" ".join(words[:n]))
        assert all(len(s.split()) >= 4 for s in segs[1:]), (n, segs)
