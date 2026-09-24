"""Smell (P3, the owner's F1b). Rules SMELL-01..05 (sense/olfaction.py odour_of, smell_range_m,
smells; mind/perception.py smell_text and the standing view's smell).

Smell matters: a person smeared with the dead reeks of them, blood and a long-unwashed body carry,
a corpse smells of death after some hours, and the dead themselves can be smelled in the dark
before they are seen. Nobody smells themselves — you get used to your own.

The world here is a long dark cellar (indoor, light 0) and a yard outside (open air, light 3).
"""

from __future__ import annotations

import copy
import json

import pytest

from as_engine.mind import perception
from as_engine.physical import bodies, space
from as_engine.sense import olfaction, optics
from as_engine.sense.olfaction import Odour
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(3)

H = 3_600_000

WORLD = {
    "schema": "as.scenario.v1", "name": "cellar_and_yard", "seed": 17, "start": {"day": 300, "time": "12:00"},
    "places": [
        {"id": "cellar", "name": "Cellar", "material": "concrete", "light": 0, "width_m": 30, "depth_m": 8},
        {"id": "yard", "name": "Back yard", "kind": "outdoor", "indoor": False, "material": "open_air", "light": 3,
         "width_m": 30, "depth_m": 10},
    ],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "yard", "x": 1, "y": 5},
        {"id": "sam", "stub": {"name": "Sam Rourke", "age": 30, "sex": "male"}, "place": "yard", "x": 4, "y": 5},
        {"id": "june", "dossier": "core:actor/june_okafor", "place": "cellar", "x": 1, "y": 4},
        {"id": "dead1", "infected": "ZOMBIE_ARCHETYPE_SHAMBLER01", "controller": "policy", "place": "cellar", "x": 7, "y": 4},
        {"id": "dead2", "infected": "ZOMBIE_ARCHETYPE_SHAMBLER01", "controller": "policy", "place": "cellar", "x": 8, "y": 4},
    ],
}


@pytest.fixture
def world(fixture_packs, core_pack_dir):
    worlds = []

    def _load(change=None):
        spec = copy.deepcopy(WORLD)
        if change is not None:
            change(spec)
        w = load_scenario(spec, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        return w

    yield _load
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def soil(w, local, **amounts):
    with w.store.transaction() as tx:
        bodies.soil(tx, w.id(local), source="smeared", at=now(w), cause_event_id=None, turn_index=0, **amounts)


def put(w, local, place, x, y):
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id(local), w.id(place), None, x, y, now(w), None, 0))


def odour(w, local, at=None):
    return olfaction.odour_of(w.store, w.id(local), now(w) if at is None else at)


def smells(w, holder, source):
    return olfaction.smells(w.store, w.id(holder), w.id(source), now(w))


def smell_rows(w, holder):
    return [dict(r) for r in w.store.query("SELECT * FROM percept_log WHERE holder_id = ? AND channel = 'olfactory' "
                                           "ORDER BY percept_id", (w.id(holder),))]


def scene(w, holder):
    with w.store.transaction() as tx:
        return perception.compile_scene(tx, w.id(holder), now(w), 0)


# --------------------------------------------------------------------------- SMELL-01 what a body smells of
def test_what_is_on_someone_is_what_they_smell_of(world):
    w = world()
    assert odour(w, "sam") is None, "clean: nothing to smell"
    soil(w, "sam", grime=2, blood=2, gore=1)
    assert odour(w, "sam") is None, "a little of each is nothing yet"
    soil(w, "sam", blood=-2, gore=-1)
    soil(w, "sam", grime=1)
    assert odour(w, "sam") == Odour("unwashed", 1)
    soil(w, "sam", grime=2, blood=3)
    assert odour(w, "sam") == Odour("unwashed", 3), "grime 5 (3) over blood 3 (2)"
    soil(w, "sam", blood=1)
    assert odour(w, "sam") == Odour("blood", 3), "blood 4 (3) ties grime 5 (3): blood comes first"
    soil(w, "sam", gore=2)
    assert odour(w, "sam") == Odour("blood", 3)
    soil(w, "sam", gore=2)
    assert odour(w, "sam") == Odour("dead", 4)
    assert odour(w, "dead1") == Odour("dead", 5), "the dead reek of the dead"


def test_a_corpse_smells_of_death_after_some_hours(world):
    w = world()
    t = now(w)
    with w.store.transaction() as tx:
        bodies.die(tx, w.rng, w.id("sam"), t, None, 0)
    assert odour(w, "sam", t + 5 * H) is None
    assert odour(w, "sam", t + 6 * H) == Odour("death", 2)
    assert odour(w, "sam", t + 24 * H) == Odour("death", 3)
    assert odour(w, "sam", t + 72 * H) == Odour("death", 4)
    soil(w, "sam", blood=5)
    assert odour(w, "sam", t + 7 * H) == Odour("blood", 4), "fresh blood is stronger than a body a few hours dead"


# --------------------------------------------------------------------------- SMELL-02/03 how far, and who
def test_open_air_carries_a_smell_off(world):
    w = world()
    indoor = [olfaction.smell_range_m(w.store, s, w.id("cellar")) for s in range(1, 6)]
    outdoor = [olfaction.smell_range_m(w.store, s, w.id("yard")) for s in range(1, 6)]
    assert indoor == [1.0, 2.0, 5.0, 10.0, 20.0]
    assert outdoor == [0.5, 1.0, 2.5, 5.0, 10.0]


@pytest.mark.parametrize("x, got", [(7.0, "exact"), (11.0, "exact"), (11.5, "partial"), (21.0, "partial"),
                                    (21.5, None)])
def test_indoors_the_dead_carry_twenty_metres(world, x, got):
    w = world()
    put(w, "dead1", "cellar", x, 4.0)
    assert smells(w, "june", "dead1") == got


def test_nobody_smells_themselves_and_a_sleeper_smells_nothing(world):
    w = world()
    soil(w, "june", gore=5)
    assert smells(w, "june", "june") is None, "you get used to your own"
    assert smells(w, "pc", "june") is None, "not in the same place"
    put(w, "sam", "yard", 5.0, 5.0)
    soil(w, "sam", gore=5)
    assert smells(w, "pc", "sam") == "exact", "4 m in the open air: within half of 10 m"
    put(w, "sam", "yard", 9.0, 5.0)
    assert smells(w, "pc", "sam") == "partial"
    put(w, "sam", "yard", 12.0, 5.0)
    assert smells(w, "pc", "sam") is None
    with w.store.transaction() as tx:
        bodies.posture_event(tx, w.id("june"), "lying", now(w), None, 0, awareness="asleep")
    assert smells(w, "june", "dead1") is None


# --------------------------------------------------------------------------- SMELL-04/05 in words
def test_the_dead_in_the_dark_are_smelled_before_they_are_seen(world):
    """SMELL-05: two of the dead in the dark, not seen: one smell for the kind, not one per body,
    and it names nobody."""
    w = world()
    for b in ("dead1", "dead2"):
        assert optics.visibility(w.store, w.id("june"), w.id(b), now(w)) in ("silhouette", "none")
    scene(w, "june")
    [row] = smell_rows(w, "june")
    assert (row["text"], row["fidelity"], row["source_id"]) == ("The reek of the dead, close by.", "exact", None)
    assert row["event_id"] == "scene:0"
    assert json.loads(row["detail"]) == {"odour": "dead", "strength": 5}
    scene(w, "june")
    assert len(smell_rows(w, "june")) == 1, "a second look at the same moment adds nothing"


def test_the_nearest_of_them_says_how_strongly_it_reaches_you(world):
    w = world()
    put(w, "dead2", "cellar", 16.0, 4.0)
    scene(w, "june")
    [row] = smell_rows(w, "june")
    assert (row["text"], row["fidelity"]) == ("The reek of the dead, close by.", "exact")


def test_far_off_in_the_dark_the_reek_is_faint(world):
    w = world()
    put(w, "dead1", "cellar", 16.0, 4.0)
    put(w, "dead2", "cellar", 18.0, 4.0)
    scene(w, "june")
    [row] = smell_rows(w, "june")
    assert (row["text"], row["fidelity"]) == ("A faint reek of the dead.", "partial")


def test_someone_seen_is_smelled_with_how_they_look(world):
    """SMELL-04: in daylight Sam is seen, so his smell goes with his look, not into a percept of
    its own."""
    w = world()
    soil(w, "sam", gore=5)
    scene(w, "pc")
    assert smell_rows(w, "pc") == []
    with w.store.transaction() as tx:
        assert perception.smell_text(tx, w.id("pc"), w.id("sam"), now(w)) == "Reeks of the dead."
    put(w, "sam", "yard", 9.0, 5.0)
    with w.store.transaction() as tx:
        assert perception.smell_text(tx, w.id("pc"), w.id("sam"), now(w)) == "Smells faintly of the dead."
    put(w, "sam", "yard", 12.0, 5.0)
    with w.store.transaction() as tx:
        assert perception.smell_text(tx, w.id("pc"), w.id("sam"), now(w)) == ""


@pytest.mark.parametrize("amounts, words", [
    ({"blood": 5}, "Smells of blood."),
    ({"grime": 5}, "Smells of sweat and dirt."),
    ({"grime": 3}, "Smells faintly of sweat and dirt."),
])
def test_blood_and_dirt_have_their_own_smell(world, amounts, words):
    w = world()
    put(w, "sam", "yard", 1.5, 5.0)
    soil(w, "sam", **amounts)
    with w.store.transaction() as tx:
        assert perception.smell_text(tx, w.id("pc"), w.id("sam"), now(w)) == words
