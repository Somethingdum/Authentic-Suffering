"""A card at odds with itself (D-276). world/worldgen/people.py skeleton_dossier (voice.would_never_say, skill evidence).

A soft-spoken leader's card gave his voice as "Would you pass that, please. Thank you." and "Behind me. Quietly. Thank
you." — and three lines down, that he would never say anything like "Thank you." A devout woman who prays before
every meal would never say "God is good."; a man who says sorry too much would never say "I'm sorry."; and a man of
twenty-seven when the Fall came learned to lead "watching the grown-ups who knew how". What someone would never say is
not what their own voice and ways have them say, and a grown man learned from the ones who knew how.
"""

from __future__ import annotations

import pytest

from as_engine.world.worldgen import people

pytestmark = pytest.mark.phase(10)

NAMES = ("Victor Marsh", "Rae Holt", "Ana Lopez")


def cards(age, cohort):
    for name in NAMES:
        for v in range(200):
            yield people.skeleton_dossier(people.PersonSeed(
                name=name, age=age, sex="male", cohort=cohort, occupation="leader", skills={"leadership": 3, "medicine": 1},
                special={L: 5 for L in "SPECIAL"}, variant=v, settlement_name="Crossroads Hold",
                group_name="the Diallo People", days_since_fall=621))


def words(text):
    return "".join(c if c.isalpha() or c == "'" else " " for c in text.casefold().replace("’", "'")).split()


def said_in(line, text):
    w, t = words(line), words(text)
    return any(t[i:i + len(w)] == w for i in range(len(t) - len(w) + 1))


@pytest.mark.parametrize("age,cohort", [(29, "pre_fall_adult"), (70, "pre_fall_adult"), (14, "fall_child"), (8, "fall_child")])
def test_never_said_is_not_in_their_own_lines(age, cohort):
    bad = [(d["identity"]["name"], x, line) for d in cards(age, cohort) for x in d["voice"]["would_never_say"]
           for line in d["voice"]["exemplars"].values() if said_in(x, line)]
    assert not bad, bad[:3]


WAYS = {
    "God is good.": lambda d: "devout" in [t["tag"] for t in d["traits"]] or any("scripture" in x for x in d["voice"]["speech_tendencies"]),
    "I was wrong. I'm sorry.": lambda d: any("sorry" in x or "apologises" in x for x in d["voice"]["speech_tendencies"]),
    "Thank you.": lambda d: any("polite" in x for x in d["voice"]["speech_tendencies"]),
    "Take my share, I don't need it.": lambda d: "generous" in [t["tag"] for t in d["traits"]],
    "Keep it. It's yours.": lambda d: "generous" in [t["tag"] for t in d["traits"]],
}


def test_never_said_is_not_their_way():
    seen = 0
    for d in cards(40, "pre_fall_adult"):
        for line, theirs in WAYS.items():
            if theirs(d):
                seen += 1
                assert line not in d["voice"]["would_never_say"], (d["identity"]["name"], line)
    assert seen > 50, "the table has people of every one of these ways"


def test_grown_when_it_came():
    grown = [s["evidence"] for d in cards(29, "pre_fall_adult") for s in d["capability"]["skills"]]
    assert not [x for x in grown if "grown-ups" in x]
    assert any("Picked up in the camps, watching the ones who knew how." == x for x in grown)
    young = [s["evidence"] for d in cards(14, "fall_child") for s in d["capability"]["skills"]]
    assert any("grown-ups" in x for x in young), "a child when it came did learn from the grown-ups"
