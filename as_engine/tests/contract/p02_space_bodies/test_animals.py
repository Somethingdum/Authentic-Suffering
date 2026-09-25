"""Animals (P2, the owner's I1). contracts/content.py AnimalDef, content/pack.py (the animals
folder), testing/scenario.py (``animal:`` bodies), physical/bodies.py (kind 'animal').

The owner: the dead "will eat anything that moves, a dog, a cat, a man, a kid, a deer, a horse.
Only humans get infected, but meat can be tainted." Animals are bodies — prey and meat — never
minds: no dossier, no actor.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.content import AnimalDef
from as_engine.testing.scenario import load_scenario, parse_scenario

pytestmark = pytest.mark.phase(2)

BARN = {
    "schema": "as.scenario.v1", "name": "barn", "seed": 5, "start": {"day": 300, "time": "09:00"},
    "places": [{"id": "barn", "name": "Barn", "material": "wood", "light": 2, "width_m": 12, "depth_m": 8}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "barn", "x": 2, "y": 4},
        {"id": "nag", "animal": "core:animal/horse", "place": "barn", "x": 8, "y": 4},
        {"id": "rex", "animal": "core:animal/dog", "place": "barn", "x": 3, "y": 5},
    ],
}


def test_the_core_animals(canon):
    ids = sorted(a.id for a in canon.all("animal"))
    assert ids == ["cat", "chicken", "deer", "dog", "goat", "horse"]
    for a in canon.all("animal"):
        assert isinstance(a, AnimalDef) and a.words and a.plural and a.speed_m_s > 0
    assert canon.get("core:animal/horse").meat_portions > canon.get("core:animal/dog").meat_portions > 0
    meat = canon.get("core:item/raw_meat")
    assert meat.kind == "food" and "meat" in meat.tags


def test_an_animal_is_a_body_not_a_mind(fixture_packs, core_pack_dir, canon):
    w = load_scenario(BARN, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
    try:
        horse = canon.get("core:animal/horse")
        b = dict(w.store.query_one("SELECT * FROM bodies WHERE body_id = ?", (w.id("nag"),)))
        assert (b["kind"], b["content_ref"], b["height_cm"], b["mass_kg"], b["alive"]) == \
            ("animal", "core:animal/horse", horse.height_cm, horse.mass_kg, 1)
        assert b["sex"] is None and b["age_years"] is None
        assert w.store.query_one("SELECT 1 FROM actors WHERE actor_id = ?", (w.id("nag"),)) is None
        assert w.store.query_one("SELECT 1 FROM dossiers WHERE actor_id = ?", (w.id("rex"),)) is None
        pos = w.store.query_one("SELECT x_m, y_m FROM positions WHERE body_id = ?", (w.id("rex"),))
        assert tuple(pos) == (3, 5)
    finally:
        w.store.close()


def test_a_body_is_one_thing(fixture_packs):
    bad = dict(BARN, bodies=BARN["bodies"] + [{"id": "odd", "animal": "core:animal/dog", "stub": {"name": "Odd", "age": 3,
                                                                                                   "sex": "male"},
                                                 "place": "barn", "x": 5, "y": 5}])
    with pytest.raises(ValueError, match="exactly one of dossier, stub, infected or animal"):
        parse_scenario(bad)
