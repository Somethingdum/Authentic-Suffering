"""What you really want, said once (D-268). mind/identity.py compile_identity (the private life section).

A generated person's hidden goal is what they want most, and their card said it twice — "What you want most: keep
Crossroads Hold running, whatever breaks." and, further down, "What you really want: keep Crossroads Hold running,
whatever breaks." — as if it were a secret it isn't. A want or an allegiance is said once; a hidden one that differs
from the open one is the point of the line, and stays.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.dossier import ActorDossier
from as_engine.mind import identity
from as_engine.world.worldgen import people

pytestmark = pytest.mark.phase(10)


def card(d):
    return [ln.text for sec in identity.compile_identity(ActorDossier.model_validate(d)).sections for ln in sec.lines]


def generated():
    return people.skeleton_dossier(people.PersonSeed(
        name="Jolene Hale", age=50, sex="female", cohort="pre_fall_adult", occupation="pump mechanic",
        skills={"mechanics": 2}, special={L: 5 for L in "SPECIAL"}, variant=5, settlement_name="Crossroads Hold",
        group_name="the Diallo People", days_since_fall=620))


def test_the_same_want_is_said_once():
    d = generated()
    assert d["persona"]["private"]["true_goals"] == [d["motive"]["motive"]]
    got = card(d)
    assert [t for t in got if t.startswith("What you want most: ")]
    assert not [t for t in got if t.startswith("What you really want")]


def test_a_hidden_want_stays():
    d = generated()
    d["persona"]["private"]["true_goals"] = [d["motive"]["motive"], "get out before the winter"]
    assert "What you really want: get out before the winter." in card(d)


def test_an_allegiance_said_once():
    d = generated()
    d["persona"]["private"]["real_affiliation"] = d["persona"]["public"]["presented_affiliation"].lower()
    assert not [t for t in card(d) if t.startswith("Who you really stand with")]
    d["persona"]["private"]["real_affiliation"] = "whoever keeps the hold fed"
    assert "Who you really stand with: whoever keeps the hold fed." in card(d)


def test_the_pack_people_keep_theirs(canon):
    """No authored card loses a line: their hidden wants and allegiances are their own."""
    for ref in ("core:actor/mara_voss", "core:actor/june_okafor", "core:actor/reggie_tate"):
        d = canon.get(ref)
        got = [ln.text for sec in identity.compile_identity(d).sections for ln in sec.lines]
        assert bool([t for t in got if t.startswith("What you really want")]) == bool(d.persona.private.true_goals)
