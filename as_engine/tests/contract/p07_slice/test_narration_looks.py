"""The story shows how people look and smell (P7, the owner's F1a-2). narration/narrator.py
people_looks (NARR-10); narration/location.py PersonChip.looks (the Play UI's people in the scene).

"Never judge a book by its cover is a bold-faced lie": the player reads people by how they look,
so the prose shows someone as they come into the scene — once — and the scene's people carry what
the player sees and smells of them. A kitchen at dusk: the player, and Ada, who has been
butchering and has not washed.
"""

from __future__ import annotations

import copy

import pytest

from as_engine.narration import location
from as_engine.narration.narrator import build_narrator_packet
from as_engine.physical import bodies
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(7)

PC_LOOKS = {"hair_colour": "brown", "hair_length": "short", "eye_colour": "grey", "complexion": "pale skin",
            "outfit": [{"item": "core:item/t_shirt"}, {"item": "core:item/jeans"}, {"item": "core:item/sneakers"}]}
ADA_LOOKS = {"hair_colour": "red", "hair_length": "long", "hair_style": "in a rough braid", "eye_colour": "green",
             "complexion": "fair skin freckled across the nose",
             "marks": [{"where": "across the back of the right hand", "what": "a ridged burn scar", "shows": "near"}],
             "outfit": [{"item": "core:item/thermal_top"}, {"item": "core:item/apron", "state": "soiled"},
                        {"item": "core:item/work_pants"}, {"item": "core:item/rubber_boots"}]}

KITCHEN = {
    "schema": "as.scenario.v1", "name": "dusk_kitchen", "seed": 12, "start": {"day": 400, "time": "18:00"},
    "places": [{"id": "kitchen", "name": "Kitchen", "material": "brick", "light": 3, "width_m": 8, "depth_m": 6,
                "anchors": [{"id": "table", "name": "table", "x": 3, "y": 3}, {"id": "stove", "name": "stove", "x": 5, "y": 3}]}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "kitchen", "anchor": "table",
         "looks": PC_LOOKS, "dress": True},
        {"id": "ada", "stub": {"name": "Ada Pryce", "age": 41, "sex": "female"}, "place": "kitchen", "anchor": "stove",
         "looks": ADA_LOOKS, "dress": True},
    ],
}


@pytest.fixture
def kitchen(fixture_packs, core_pack_dir):
    worlds = []

    def _load():
        w = load_scenario(copy.deepcopy(KITCHEN), packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        return w
    yield _load
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def look(w, turn):
    from as_engine.mind import perception
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id("pc"), now(w), turn)
        return build_narrator_packet(tx, w.id("pc"), turn, now(w), w.session().settings)


def test_she_is_shown_as_she_comes_in_and_only_then(kitchen):
    w = kitchen()
    with w.store.transaction() as tx:
        bodies.soil(tx, w.id("ada"), blood=3, source="butchering", at=now(w), cause_event_id=None, turn_index=0)
    first = look(w, 1)                              # the first turn establishes the place
    (line,) = first.people_looks
    assert line.startswith("a woman: ") or line.startswith("Ada")
    assert "long red hair in a rough braid" in line.lower() and "freckled" in line
    assert "apron" in line
    assert "blood" in line.lower(), "what is on her shows, and how she smells"
    assert not any(line.startswith("Owen") for line in first.people_looks), "never the player"
    later = look(w, 2)
    assert later.people_looks == [], "once: she is not new any more"


def test_the_scene_chip_carries_it(kitchen):
    w = kitchen()
    look(w, 1)
    with w.store.transaction() as tx:
        chips = location.describe(tx, w.id("pc"), now(w)).people
    (ada,) = chips
    assert "long red hair" in ada.looks.lower() and "apron" in ada.looks
