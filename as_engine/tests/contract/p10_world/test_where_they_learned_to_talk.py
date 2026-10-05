"""Where they learned to talk (D-266). world/worldgen/people.py skeleton_dossier voice.dialect_notes.

How a generated person sounds was drawn from a short list that never looked at where they came from: a grown man from
Monterrey and then Chicago had "a northern accent that thickens when angry", a man from Lagos "drops the 'g' on every
-ing", and half of everyone sounded like nothing at all. Now a grown person sounds like the town they come from, one
who was a child when it came like the camps they grew up in, and one born after it like the only world they know.
"""

from __future__ import annotations

import re

import pytest

from as_engine.world.worldgen import people

pytestmark = pytest.mark.phase(10)


def dossier(cohort, age, variant):
    return people.skeleton_dossier(people.PersonSeed(
        name="Rae Holt", age=age, sex="female", cohort=cohort, occupation="cook", skills={"medicine": 1},
        special={L: 5 for L in "SPECIAL"}, variant=variant, settlement_name="Vale", group_name="the Vale",
        days_since_fall=6200))


@pytest.mark.parametrize("variant", range(12))
def test_grown_before_the_fall(variant):
    d = dossier("pre_fall_adult", 44, variant)
    born = d["identity"]["birthplace"]
    assert d["voice"]["dialect_notes"] == people._SOUNDS[born], born


@pytest.mark.parametrize("variant", range(6))
def test_a_child_when_it_came(variant):
    assert dossier("fall_child", 22, variant)["voice"]["dialect_notes"] in people._CAMP_SOUNDS


@pytest.mark.parametrize("variant", range(6))
def test_born_after_it(variant):
    d = dossier("post_fall_born", 15, variant)
    assert d["voice"]["dialect_notes"] in people._BORN_SOUNDS
    assert d["identity"]["birthplace"] not in people._SOUNDS


def test_a_small_child_has_none():
    assert dossier("post_fall_born", 8, 3)["voice"]["dialect_notes"] == ""


def test_every_town_has_its_sound_and_every_line_reads_on_a_card():
    """Every birthplace has a sound, no two alike; and no line calls the person 'they' — the card says it to them
    ('How you sound: …') and the voicing card of them (D-251)."""
    assert set(people._BIRTHPLACES) <= set(people._SOUNDS)
    assert len(set(people._SOUNDS.values())) == len(people._SOUNDS)
    for t in list(people._SOUNDS.values()) + list(people._CAMP_SOUNDS) + list(people._BORN_SOUNDS):
        assert not re.search(r"\b(they|their|them)\b", t, re.I), t
