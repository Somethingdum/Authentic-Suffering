"""A person's lines sound like the person (D-143). Rule GEN-01 (world/worldgen/people.py skeleton_dossier).

D-127 drew every field on its own, the voice and its sample lines too: a woman who talks to fill a silence and
tells stories about before spoke a devout fatalist's lines, a watcher said "Pump's running", an old man said
"Let an old woman fuss", a man who swears when he is nervous never swore, and people born after the Fall told
stories about the world before it. Now a voice and its lines are one draw, and what a person says follows it.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.dossier import ActorDossier
from as_engine.world.worldgen import people

pytestmark = pytest.mark.phase(10)


def person(i, age, cohort):
    return people.skeleton_dossier(people.PersonSeed(
        name=f"Person{i} Vale", age=age, sex="female" if i % 2 else "male", cohort=cohort,
        occupation="watcher" if age >= 16 else "child", skills={"firearms": 1} if age >= 16 else {},
        special={L: 5 for L in "SPECIAL"}, variant=(i * 31) % 1000, settlement_name="Vale", group_name="the Vale"))


def voice_of(d):
    return tuple(d["voice"]["speech_tendencies"]), tuple(d["voice"]["exemplars"].values())


@pytest.mark.parametrize("age,cohort,voices,lines", [
    (35, "pre_fall_adult", people._VOICES, people._EXEMPLARS),
    (8, "post_fall_born", people._KID_VOICES, people._KID_EXEMPLARS),
    (15, "post_fall_born", people._TEEN_VOICES, people._TEEN_EXEMPLARS),
    (70, "pre_fall_adult", people._VOICES + people._ELDER_VOICES, people._EXEMPLARS + people._ELDER_EXEMPLARS),
])
def test_the_lines_belong_to_the_voice(age, cohort, voices, lines):
    assert len(voices) == len(lines)
    for i in range(120):
        d = person(i, age, cohort)
        ActorDossier.model_validate(d)
        tend, ex = voice_of(d)
        assert lines[voices.index(tend)] == ex, (tend, ex)


def test_elders_are_not_only_their_age():
    assert len({voice_of(person(i, 72, "pre_fall_adult"))[0] for i in range(100)}) >= 12


def test_born_after_the_fall_remembers_nothing_before_it():
    for i in range(200):
        d = person(i, 22, "post_fall_born")
        text = " ".join(d["voice"]["speech_tendencies"]) + " " + " ".join(d["voice"]["exemplars"].values())
        assert "before" not in text and "old world" not in text and "used to say" not in text, text


def test_what_they_say_follows_how_they_talk():
    for i in range(300):
        d = person(i, 40, "pre_fall_adult")
        tend = " ".join(d["voice"]["speech_tendencies"])
        if "swears" in tend:
            assert d["voice"]["profanity"] in ("frequent", "constant")
        if "scripture" in tend or "polite to a fault" in tend:
            assert d["voice"]["profanity"] == "none"


def test_nobody_says_another_trade_s_line():
    assert not [x for set_ in people._EXEMPLARS + people._ELDER_EXEMPLARS for x in set_ if "Pump" in x or "old woman" in x]
