"""Names called (D-192). Rule TEMPER-03 'insulted' (mind/temper.py INSULT_WORDS).

The player called Mara a whore, told June to go to hell and Eli he was a waste of space, and nobody's temper
moved: the list of what wounds held nineteen words and phrases, and none of those. Now the common names people are
called and the things said to hurt are on it — and ordinary words that only sound like them are not.
"""

from __future__ import annotations

import pytest

from as_engine.mind.temper import INSULT_WORDS, _words_have

pytestmark = pytest.mark.phase(5)


def wounds(words):
    return any(_words_have(words, x) for x in INSULT_WORDS)


@pytest.mark.parametrize("words", [
    "You're a whore, Mara.", "Go to hell, June.", "Eli, you're a waste of space.", "Drop dead.", "You scum.",
    "Listen to me, you halfwit.", "Piss off.", "Nobody wants you here.", "You disgust me.", "Shut your mouth, you maggot.",
    "You motherfucker.", "Son of a bitch.", "You're nothing.", "You\u2019re nothing.",
])
def test_said_to_wound(words):
    assert wounds(words), words


@pytest.mark.parametrize("words", [
    "Take the garbage out back.", "The water's filthy.", "Drop the bag.", "Go to the hall.", "That was dumb luck.",
    "Kill the light.", "Is anybody there?", "A scummy film on the water.", "Don't fool around.", "Vermin got into the stores.",
])
def test_ordinary_words_are_not(words):
    assert not wounds(words), words
