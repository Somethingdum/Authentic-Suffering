"""A card about you (D-251). world/worldgen/people.py skeleton_dossier (where they come from, what they did before
the Fall, what they tell people, who they stand with, the decision stack's exception and the time it held, what they
are in the middle of, a skill's history, how well they read; every text said of the person in the right person).

Every decision a generated person makes reads their identity card ("You are ..."). Seventeen of eighteen cards in a
world said "You come from somewhere in the region.", "Except: a raid on the settlement.", "Once, when it mattered:
stayed on the wall during a raid instead of running home." and "Who you really stand with: their own people."; most
said "What you are working on: keeping up with the work at <their hold>." and the pump mechanic had been a pump
mechanic before the Fall, the leader a leader. And the card called the person it speaks to 'they': "You won't: break
their word.", "What you want most: get their sister back", "You go quiet when: they are praised".
"""

from __future__ import annotations

import asyncio
import collections
import re

import pytest

from as_engine.contracts.dossier import ActorDossier
from as_engine.contracts.settings import EngineConfig, RunSettings
from as_engine.mind import identity
from as_engine.mind.actor import fused
from as_engine.testing.fake_lm import FakeTransport
from as_engine.world.worldgen import people

pytestmark = pytest.mark.phase(10)

SELF = re.compile(r"\b(they|their|them|themself|themselves|theirs)\b", re.I)


def seed(i, age, occupation="pump mechanic", dsf=621, **kw):
    a = age - dsf / 365
    cohort = "post_fall_born" if a < 0 else "fall_child" if a < 18 else "pre_fall_adult"
    return people.PersonSeed(name=f"Rowan{i} Pike", age=age, sex="female" if i % 2 else "male", cohort=cohort,
                             occupation=occupation if age >= 16 else "child",
                             skills={"mechanics": 2} if age >= 16 else {}, special={L: 5 for L in "SPECIAL"},
                             variant=(i * 37) % 1000, settlement_name="Pumpwell", group_name="The Vale People",
                             days_since_fall=dsf, **kw)


def value(d, path):
    for part in re.findall(r"[^.\[\]]+|\[\d+\]", path):
        d = d[int(part[1:-1])] if part.startswith("[") else d[part]
    return d


def texts(v):
    return [v] if isinstance(v, str) else [x for x in v if isinstance(x, str)] if isinstance(v, list) else []


@pytest.mark.parametrize("age, dsf", [(6, 621), (9, 3650), (14, 621), (19, 621), (35, 621), (35, 9000), (70, 621)])
def test_said_of_you_as_you(age, dsf):
    """Every text the card says of the person ('What you want most: ...', 'You won't: ...') calls them nothing but
    'you' — never 'they', 'their' or 'them' (a quoted word is their own)."""
    bad = set()
    for i in range(80):
        for occupation in ("pump mechanic", "watch guard", "leader", "raider", "trader"):
            d = people.skeleton_dossier(seed(i, age, occupation, dsf))
            for sec in identity.compile_identity(ActorDossier.model_validate(d)).sections:
                for ln in sec.lines:
                    for path in ln.sources:
                        if path.startswith(("voice.exemplars", "voice.would_never_say")):
                            continue                                           # their own words, quoted on the card
                        for t in texts(value(d, path)):
                            if SELF.search(re.sub(r"'[^']*'|\"[^\"]*\"", "", t)):
                                bad.add(t)
    assert sorted(bad) == []


def test_what_they_were_doing_when_it_came():
    """What they did before the Fall follows from when they were born: not yet born, the school they were in, a first
    job, a retirement — or work, often the work their trade grew out of; a skill that grew out of it says so."""
    assert people.skeleton_dossier(seed(1, 1))["identity"]["occupation_before"] == "not yet born"
    assert people.skeleton_dossier(seed(1, 4))["identity"]["occupation_before"] == "too little to remember it"
    assert people.skeleton_dossier(seed(1, 10))["identity"]["occupation_before"] == "in grade school"
    assert people.skeleton_dossier(seed(1, 18))["identity"]["occupation_before"] == "in high school"
    assert people.skeleton_dossier(seed(1, 20))["identity"]["occupation_before"] in people._JOBS_YOUNG
    assert people.skeleton_dossier(seed(1, 75))["identity"]["occupation_before"] in people._JOBS_RETIRED
    befores = [people.skeleton_dossier(seed(i, 40)) for i in range(60)]
    assert len({d["identity"]["occupation_before"] for d in befores}) >= 15
    assert not any(d["identity"]["occupation_before"] == "pump mechanic" for d in befores), "nobody mended a settlement pump before"
    fits = [d for d in befores if d["identity"]["occupation_before"] in people._FIT_BEFORE["pump mechanic"]]
    assert fits, "a trade often grew out of the work before"
    for d in fits:
        assert d["capability"]["skills"][0]["evidence"] == f"Years of it before the Fall, as {people._a(d['identity']['occupation_before'])}."
    for d in befores:
        assert "Rowan" not in d["capability"]["skills"][0]["evidence"], "the card does not call them by name"


def test_where_they_come_from():
    """A real town for anyone born before the Fall; a place of this world for anyone born after it."""
    before = {people.skeleton_dossier(seed(i, 40))["identity"]["birthplace"] for i in range(40)}
    assert before <= set(people._BIRTHPLACES) and len(before) >= 15
    after = {people.skeleton_dossier(seed(i, 1))["identity"]["birthplace"] for i in range(40)}
    assert after <= {x.format(settlement="Pumpwell") for x in people._BORN_AFTER} and len(after) >= 5


def test_one_line_is_not_their_name_again():
    d = people.skeleton_dossier(seed(3, 40))
    card = identity.compile_identity(ActorDossier.model_validate(d))
    first = [ln.text for ln in card.sections[0].lines][0]
    assert first.count("Rowan3") == 1 and first.startswith("You are Rowan3 Pike, 40. A") and " at Pumpwell who " in first


def test_who_cannot_read():
    """Someone whose secret is that they cannot read cannot read; the young read as their generation was taught."""
    others = tuple(x for x in people._real_secrets if "cannot read" not in x)
    hidden = [d for d in (people.skeleton_dossier(seed(i, 40, lives_taken=others)) for i in range(40))
              if "cannot read" in d["persona"]["private"]["concealed_history"]]
    assert hidden and all(d["capability"]["literacy"] == 0 for d in hidden)
    assert {people.skeleton_dossier(seed(i, 40))["capability"]["literacy"] for i in range(40)} > {2}
    assert people.skeleton_dossier(seed(2, 4))["capability"]["literacy"] == 0


def test_a_child_is_settled_as_a_child():
    for i in range(40):
        d = people.skeleton_dossier(seed(i, 8))
        assert d["temper"]["cools_down_by"] in people._KID_SETTLERS and d["temper"]["pet_peeves"][0] in people._KID_PEEVES
        assert d["appearance"]["movement_under_stress"] in people._KID_MOVES
        assert d["decision_stack"]["past_example"] in [x[2] for x in people._KID_STACKS]


def test_no_line_on_every_card(tmp_path):
    """In one world, nobody in a group shares where they come from, what they tell people, who they stand with, what
    they are in the middle of or the time their priorities held; and nobody shares a first line."""
    from as_engine.service import runs
    from conftest import REPO_PACKS
    cfg = EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(REPO_PACKS))
    s = asyncio.run(runs.create_run(cfg, "core:pc/owen_marsh", RunSettings(world_detail="standard", seed=7, era="established",
                                                                         difficulty="normal"), FakeTransport()))
    try:
        rows = s.store.query("SELECT a.actor_id, (SELECT m.group_id FROM group_members m WHERE m.actor_id = a.actor_id "
                             "ORDER BY m.group_id LIMIT 1) FROM actors a JOIN bodies b ON b.body_id = a.actor_id JOIN dossiers d "
                             "ON d.actor_id = a.actor_id WHERE b.kind = 'human' AND a.controller != 'human' AND d.source = 'generated'")
        shared, firsts = collections.Counter(), collections.Counter()
        for aid, group in rows:
            d = fused(s.store, aid)
            for what, text in (("from", d.identity.birthplace), ("told", d.persona.public.claimed_history),
                               ("stands", d.persona.private.real_affiliation), ("project", d.life.current_project),
                               ("held", d.decision_stack.past_example)):
                shared[(group, what, text)] += 1
            firsts[d.identity.one_line] += 1
            assert d.identity.birthplace != "somewhere in the region" and d.identity.occupation_before != d.identity.occupation_now
        assert len(rows) >= 12
        assert [k for k, n in shared.items() if n > 1] == []
        assert [k for k, n in firsts.items() if n > 1] == []
    finally:
        s.store.close()


def test_a_raider_tells_a_raiders_story():
    """A raider did not come to the hold early with the first families, nor stand with whoever keeps it fed."""
    for i in range(30):
        d = people.skeleton_dossier(seed(i, 30, "raider"))
        fmt = {"group": "the Vale People", "settlement": "Pumpwell"}
        assert d["persona"]["public"]["claimed_history"] in [x.format(**fmt) for x in people._RAIDER_CLAIMED]
        assert d["persona"]["private"]["real_affiliation"] in [x.format(**fmt) for x in people._RAIDER_ALLEGIANCE]
