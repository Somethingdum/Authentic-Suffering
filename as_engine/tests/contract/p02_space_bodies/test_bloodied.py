"""What a wound leaves on you, and what your clothes keep in (P2, the owner's F1c: DECISIONS D-86).
physical/bodies.py LOOK-07 (apply_harm soils the wounded body; create's washed_at), physical/objects.py
warmth; HARM-07 (the cold stage counts toward impairment).

A store room (a dict scenario): Ada in light summer clothes, Ben in a parka and thermals, Cal who
has nothing on.
"""

from __future__ import annotations

import copy
import json

import pytest

from as_engine.contracts.events import EventType
from as_engine.physical import bodies, objects
from as_engine.physical.bodies import WoundSpec
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(2)

LIGHT = [{"item": "core:item/t_shirt"}, {"item": "core:item/jeans"}, {"item": "core:item/sneakers"}]
WARM = [{"item": "core:item/parka"}, {"item": "core:item/thermal_top"}, {"item": "core:item/cargo_pants"},
        {"item": "core:item/combat_boots"}]


def looks(outfit):
    return {"hair_colour": "brown", "hair_length": "short", "eye_colour": "grey", "complexion": "pale skin",
            "outfit": outfit}


STORE = {
    "schema": "as.scenario.v1", "name": "store_room", "seed": 5, "start": {"day": 400, "time": "10:00"},
    "places": [{"id": "store", "name": "Store room", "material": "brick", "light": 3, "width_m": 10, "depth_m": 6}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "store", "x": 9, "y": 5},
        {"id": "ada", "stub": {"name": "Ada Pike", "age": 34, "sex": "female"}, "place": "store", "x": 2, "y": 3,
         "looks": looks(LIGHT), "dress": True},
        {"id": "ben", "stub": {"name": "Ben Ruiz", "age": 40, "sex": "male"}, "place": "store", "x": 3, "y": 3,
         "looks": looks(WARM), "dress": True},
        {"id": "cal", "stub": {"name": "Cal Hobbs", "age": 30, "sex": "male"}, "place": "store", "x": 4, "y": 3,
         "looks": looks(LIGHT)},
    ],
}


@pytest.fixture
def store(fixture_packs, core_pack_dir):
    worlds = []

    def _load():
        w = load_scenario(copy.deepcopy(STORE), packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        return w

    yield _load
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def blood(w, local):
    return bodies.condition_of(w.store, w.id(local)).blood


def hurt(w, local, severity, anatomy="arm_l"):
    from as_engine.contracts.events import Event
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=now(w), turn_index=0, payload={"what": "test"}))
        return bodies.apply_harm(tx, w.id(local), WoundSpec(anatomy, "cut", severity, 0), now(w), c.event_id, 0, w.rng)


@pytest.mark.parametrize("severity,added", [("minor", 0), ("significant", 1), ("severe", 2), ("catastrophic", 3)])
def test_a_wound_bloodies_the_one_who_took_it(store, severity, added):
    """LOOK-07: the deeper the wound, the more of it is on them (a nick leaves nothing to see)."""
    w = store()
    evs = hurt(w, "ada", severity, "leg_l")
    assert blood(w, "ada") == added
    conds = [dict(r) for r in w.store.query("SELECT * FROM events WHERE type = 'BODY_CONDITION'")]
    if added:
        (c,) = conds
        assert c["cause_event_id"] == evs[0].event_id and json.loads(c["payload"])["source"] == "harm"
    else:
        assert conds == []


def test_the_blood_is_on_them_but_not_in_what_harm_returns(store):
    """apply_harm still returns the HARM, then only what the death test made: the BODY_CONDITION is
    committed after the HARM and kept out of the list (every caller that reads [0] or the types)."""
    w = store()
    evs = hurt(w, "ben", "severe")
    assert [e.type for e in evs] == [EventType.HARM]
    assert blood(w, "ben") == 2


def test_it_builds_up_and_stops_at_soaked(store):
    w = store()
    for _ in range(3):
        hurt(w, "cal", "severe")
    assert blood(w, "cal") == 5


def test_a_new_body_starts_clean_now(store):
    """create gives every body washed_at = at (and the scenario loader, the scenario's start)."""
    w = store()
    assert bodies.condition_of(w.store, w.id("ada")).washed_at == now(w)
    with w.store.transaction() as tx:
        b = bodies.create(tx, kind="human", sex="female", age_years=20, height_cm=165, mass_kg=60,
                          special={k: 5 for k in "SPECIAL"}, at=now(w) + 5000, turn_index=0, origin="materialize")
    assert bodies.condition_of(w.store, b).washed_at == now(w) + 5000


def test_warmth_is_what_they_have_on(store):
    """objects.warmth: the sum of the worn clothing's warmth — a parka and thermals keep in far more
    than a t-shirt and jeans, and nothing keeps in nothing."""
    w = store()
    assert (objects.warmth(w.store, w.id("ada")), objects.warmth(w.store, w.id("ben")),
            objects.warmth(w.store, w.id("cal"))) == (1, 6, 0)


def test_the_cold_counts_toward_impairment(store):
    """HARM-07: the cold stage stands with thirst, hunger and fatigue — stage 3 costs a step."""
    from as_engine.contracts.events import Event, WriteOp, WriteRecord
    w = store()
    cal = w.id("cal")
    assert bodies.impairment(w.store, cal) == 0
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.NEED_STAGE, writer="physical.bodies", at=now(w), turn_index=0, target_ids=[cal],
                              writes=[WriteRecord(op=WriteOp.UPDATE, table="needs", key={"body_id": cal},
                                                  values={"chill": 12, "cold_stage": 3})],
                              payload={"body_id": cal, "need": "cold", "stage": 3, "chill": 12}))
    assert bodies.impairment(w.store, cal) == 1
