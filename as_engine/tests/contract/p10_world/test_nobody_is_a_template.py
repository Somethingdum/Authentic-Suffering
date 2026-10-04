"""Nobody is a template (D-127). Rule GEN-01 (world/worldgen/people.py skeleton_dossier).

The owner: "If they all talk the same. If they're all the same, I'll crash out." Most of a world's people
are never written by a model — everyone past the first few at worldgen, every raider, every faction's
team — and until D-127 their skeleton gave them all one motive, one past wound, one inner conflict, one
hope, the same three things they would never say, one of four voices and four sets of lines; a child of
five spoke like a pump mechanic, and children born after the Fall had lost their families in its first
week. Now every field is its own draw, for their age, cohort and work.
"""

from __future__ import annotations

import pytest

from as_engine.content.safety import unsafe_terms
from as_engine.contracts.dossier import ActorDossier
from as_engine.world.worldgen import people

pytestmark = pytest.mark.phase(10)


def person(name, age, variant, cohort=None, occupation="pump operator"):
    cohort = cohort or ("post_fall_born" if age < 12 else "fall_child" if age < 30 else "pre_fall_adult")
    return people.skeleton_dossier(people.PersonSeed(
        name=name, age=age, sex="female" if variant % 2 else "male", cohort=cohort,
        occupation=occupation if age >= 16 else "child", skills={"mechanics": 1} if age >= 16 else {},
        special={L: 5 for L in "SPECIAL"}, variant=variant, settlement_name="Pumpwell", group_name="the settlers"))


def strings(x):
    if isinstance(x, dict):
        for v in x.values():
            yield from strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from strings(v)
    elif isinstance(x, str):
        yield x


def inner_life(d):
    return (d["voice"]["capsule"].split(" ", 1)[1], d["voice"]["exemplars"]["low_stakes"], tuple(d["voice"]["would_never_say"]),
            d["motive"]["motive"], d["motive"]["past_wound"], d["motive"]["inner_conflict"], d["life"]["aspiration"],
            d["motive"]["signature_behaviour"])


def test_a_settlement_of_strangers_not_clones():
    """Twenty adults of one settlement, one trade: no two share a voice and an inner life, and each part of
    it varies on its own."""
    town = [person(f"Settler{i} Hale", 25 + i, (i * 53) % 1000) for i in range(20)]
    for d in town:
        ActorDossier.model_validate(d)
    assert len({inner_life(d) for d in town}) == 20
    for part in range(len(inner_life(town[0]))):
        assert len({inner_life(d)[part] for d in town}) >= 6, f"part {part} barely varies"


def test_children_talk_like_children():
    kid = person("Pip Brandt", 6, 401)
    adult_lines = {ex for set_ in people._EXEMPLARS for ex in set_}
    assert kid["voice"]["exemplars"]["low_stakes"] not in adult_lines
    assert kid["voice"]["profanity"] == "none" and kid["voice"]["dialect_notes"] == ""
    assert kid["persona"]["private"]["concealed_history"] == "none worth telling"


def test_what_you_can_remember_losing_depends_on_when_you_were_born():
    born_after = [person(f"Kid{i} Oduya", 7, i * 11) for i in range(30)]
    assert not any("first week of the Fall" in d["motive"]["past_wound"] for d in born_after)
    assert all(d["motive"]["past_wound"] in people._WOUNDS["post_fall_born"] for d in born_after)


def test_valid_and_safe_for_every_age():
    """CNT-10 and CNT-11 for a thousand people of every age."""
    for i in range(1000):
        age = (1, 4, 9, 13, 16, 25, 47, 66, 80)[i % 9]
        d = person(f"Name{i} Family{i % 13}", age, (i * 37) % 1000)
        ActorDossier.model_validate(d)
        if age < 18:
            assert not [t for s in strings(d) for t in unsafe_terms(s)], f"age {age}"


def test_the_same_person_is_the_same_person():
    assert person("Rosa Quintero", 36, 512) == person("Rosa Quintero", 36, 512), "deterministic"
