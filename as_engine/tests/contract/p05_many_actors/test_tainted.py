"""Tainted meat and water, and butchering (P5, the owner's I1). action/effects.py eat / drink (a
lasting mark) and butcher; physical/objects.py contaminate(lasting=) / contaminated; the core
butcher_carcass affordance.

The owner: "Only humans get infected, but meat can be tainted. Water can be tainted too, fluids and
all." Meat from something the dead fed on looks and smells like any meat; it carries the strain
into whoever eats it. A kitchen yard at noon (a dict scenario): Irene with a knife, two dead dogs —
one the dead fed on — and supper.
"""

from __future__ import annotations

import copy
import json

import pytest

import helpers
from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.physical import bodies, objects
from as_engine.physical.bodies import WoundSpec
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(5)

KITCHEN = {
    "schema": "as.scenario.v1", "name": "kitchen_yard", "seed": 91, "start": {"day": 3100, "time": "12:00"},
    "places": [{"id": "yard", "name": "Kitchen yard", "kind": "outdoor", "indoor": False, "material": "open_air", "light": 3,
                "width_m": 12, "depth_m": 10, "anchors": [{"id": "block", "name": "chopping block", "x": 4, "y": 5}]}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "yard", "x": 10, "y": 8},
        {"id": "irene", "dossier": "core:actor/irene_kowalski", "place": "yard", "x": 4, "y": 5,
         "inventory": [{"item": "core:item/kitchen_knife", "slot": "hand_r", "label": "knife"},
                       {"item": "core:item/raw_meat", "slot": "pack", "label": "bad_meat"},
                       {"item": "core:item/raw_meat", "slot": "pack", "label": "good_meat"},
                       {"item": "core:item/water_bottle", "slot": "pack", "label": "bottle"}]},
        {"id": "bitten_dog", "animal": "core:animal/dog", "place": "yard", "x": 4.5, "y": 5},
        {"id": "clean_dog", "animal": "core:animal/dog", "place": "yard", "x": 3.5, "y": 5},
        {"id": "dead", "infected": "ZOMBIE_ARCHETYPE_SHAMBLER01", "controller": "policy", "place": "yard", "x": 11, "y": 1},
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


def cause(tx, at, actor=None):
    return tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=at, turn_index=0, payload={"what": "test"}))


def fed_on_and_dead(w, dog, biter=None):
    """The dead fed on the dog (a bite whose cause is the biter's action), and it died."""
    t = now(w)
    with w.store.transaction() as tx:
        if biter is not None:
            start = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", actor_id=w.id(biter), at=t,
                                          turn_index=0, payload={"actor_id": w.id(biter), "def_id": "infected_bite",
                                                                 "verb": "attack", "target_id": w.id(dog), "destination_id": None,
                                                                 "item_id": None, "est_duration_s": 1.0, "visible": True}))
            bodies.apply_harm(tx, w.id(dog), WoundSpec("abdomen", "bite", "severe", 2), t, start.event_id, 0, w.rng)
        if tx.query_one("SELECT alive FROM bodies WHERE body_id = ?", (w.id(dog),))[0]:
            bodies.die(tx, w.rng, w.id(dog), t, cause(tx, t).event_id, 0, cause="test")


def run(w, *intents, rng=None):
    t = now(w)
    with w.store.transaction() as tx:
        return resolve_wave(tx, rng or w.rng, barrier(tx, list(intents)), t, 0, horizon_ms=t + 3_600_000)


def of(evs, type_):
    return [e for e in evs if e.type == type_]


def meat_on_floor(w):
    return [dict(r, props=json.loads(r["props"])) for r in w.store.query(
        "SELECT * FROM items WHERE def_ref = 'core:item/raw_meat' AND place_id IS NOT NULL ORDER BY item_id")]


# --------------------------------------------------------------------------- lasting marks
def test_a_lasting_mark_never_dries(kitchen):
    w = kitchen()
    t = now(w)
    with w.store.transaction() as tx:
        ev = objects.contaminate(tx, w.id("bad_meat"), "wet", w.id("dead"), t, cause(tx, t).event_id, 0, lasting=True)
    assert ev.payload == {"item_id": w.id("bad_meat"), "pathway": "wet", "by": w.id("dead"), "lasting": True}
    years = t + 5 * 365 * 24 * 3_600_000
    assert objects.contaminated(w.store, w.id("bad_meat"), years) == {"pathway": "wet", "by": w.id("dead"), "at": t,
                                                                       "lasting": True}
    with w.store.transaction() as tx:
        objects.contaminate(tx, w.id("bad_meat"), "wet", w.id("irene"), t + 1000, cause(tx, t + 1000).event_id, 0)
    assert objects.contaminated(w.store, w.id("bad_meat"), years)["lasting"] is True, \
        "a passing mark never washes out a lasting one"


# --------------------------------------------------------------------------- eating and drinking it
def test_tainted_meat_carries_it_into_whoever_eats_it(kitchen):
    w = kitchen()
    t = now(w)
    with w.store.transaction() as tx:
        objects.contaminate(tx, w.id("bad_meat"), "wet", w.id("dead"), t, cause(tx, t).event_id, 0, lasting=True)
    rng = helpers.ScriptedRng(True)
    evs = run(w, helpers.make_intent(w, "irene", "eat_food", item="bad_meat"), rng=rng)
    (exp,) = of(evs, "INFECTION_EXPOSURE")
    assert (exp.payload["body_id"], exp.payload["pathway"], exp.payload["exposure"], exp.payload["infected"]) == \
        (w.id("irene"), "wet", "tainted_food", True)
    assert ("chance", "infected", f"exposure:{w.id('irene')}:{exp.cause_event_id}") in rng.asked


def test_clean_meat_is_just_supper(kitchen):
    w = kitchen()
    evs = run(w, helpers.make_intent(w, "irene", "eat_food", item="good_meat"), rng=helpers.ScriptedRng())
    assert not of(evs, "INFECTION_EXPOSURE")
    assert [e.payload["result"] for e in of(evs, "ACTION_COMPLETE")] == ["ate"]


def test_food_someone_else_ate_from_is_mouth_contact(kitchen):
    """D-77: anything a host's fluids touched carries it — food someone ate from is a bottle someone
    drank from ('mouth_contact_item'); your own mark is nothing."""
    w = kitchen()
    t = now(w)
    with w.store.transaction() as tx:
        objects.contaminate(tx, w.id("good_meat"), "wet", w.id("pc"), t, cause(tx, t).event_id, 0)
        objects.contaminate(tx, w.id("bad_meat"), "wet", w.id("irene"), t, cause(tx, t).event_id, 0)
    evs = run(w, helpers.make_intent(w, "irene", "eat_food", item="good_meat"), rng=helpers.ScriptedRng(False))
    (exp,) = of(evs, "INFECTION_EXPOSURE")
    assert (exp.payload["exposure"], exp.payload["infected"]) == ("mouth_contact_item", False)
    evs = run(w, helpers.make_intent(w, "irene", "eat_food", item="bad_meat"), rng=helpers.ScriptedRng())
    assert not of(evs, "INFECTION_EXPOSURE"), "her own mouth"


def test_fouled_water_carries_it_too(kitchen):
    w = kitchen()
    t = now(w)
    with w.store.transaction() as tx:
        objects.contaminate(tx, w.id("bottle"), "wet", w.id("dead"), t, cause(tx, t).event_id, 0, lasting=True)
    evs = run(w, helpers.make_intent(w, "irene", "drink_water", item="bottle"), rng=helpers.ScriptedRng(False))
    (exp,) = of(evs, "INFECTION_EXPOSURE")
    assert (exp.payload["exposure"], exp.payload["infected"]) == ("tainted_water", False)


# --------------------------------------------------------------------------- butchering
def test_a_dead_animal_can_be_butchered_with_a_blade(kitchen):
    w = kitchen()
    fed_on_and_dead(w, "clean_dog")
    t = now(w)
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id("irene"), t, 0)
        aff = enumerate_affordances(tx, w.id("irene"), w.canon.all("affordance"), t, 0)
    targets = sorted(w.local(o.target_id) for o in aff.pool if o.def_id == "butcher_carcass")
    assert targets == ["clean_dog"], "the living dog is not meat yet; the dead one is"


def test_butchering_makes_meat_and_leaves_a_carcass(kitchen, canon):
    w = kitchen()
    fed_on_and_dead(w, "clean_dog")
    evs = run(w, helpers.make_intent(w, "irene", "butcher_carcass", target="clean_dog"))
    (done,) = of(evs, "ACTION_COMPLETE")
    assert done.payload["result"] == "butchered"
    meat = meat_on_floor(w)
    assert sum(m["qty"] for m in meat) == canon.get("core:animal/dog").meat_portions
    assert all(m["place_id"] == w.id("yard") for m in meat)
    assert not any(m["props"].get("contaminated") for m in meat)
    special = json.loads(w.store.query_one("SELECT special FROM bodies WHERE body_id = ?", (w.id("clean_dog"),))[0])
    assert special.get("butchered") is True
    again = run(w, helpers.make_intent(w, "irene", "butcher_carcass", target="clean_dog"))
    assert of(again, "ACTION_COMPLETE")[0].payload["result"] == "nothing_to_butcher"


def test_meat_from_what_the_dead_fed_on_is_tainted(kitchen):
    w = kitchen()
    fed_on_and_dead(w, "bitten_dog", biter="dead")
    run(w, helpers.make_intent(w, "irene", "butcher_carcass", target="bitten_dog"))
    meat = meat_on_floor(w)
    assert meat
    for m in meat:
        mark = objects.contaminated(w.store, m["item_id"], now(w) + 10 ** 12)
        assert mark is not None and mark["lasting"] is True and mark["by"] == w.id("dead")
