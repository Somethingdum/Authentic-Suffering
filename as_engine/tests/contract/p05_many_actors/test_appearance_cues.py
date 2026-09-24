"""What people look like is a cue for the people who see them (P5, the owner's F1a). Rule LOOK-05
(mind/cues.py cues_of + appearance_cues).

Two people on a porch and one out of sight in the kitchen: only a body seen this turn, clearly or
partly, lends its look to the cues — a revolver on a hip, blood on a coat, nothing at all.
"""

from __future__ import annotations

import copy

import pytest

from as_engine.mind import cues, perception
from as_engine.physical import bodies, objects
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(5)

PORCH = {
    "schema": "as.scenario.v1", "name": "porch_cues", "seed": 9, "start": {"day": 300, "time": "15:00"},
    "places": [
        {"id": "porch", "name": "Front porch", "kind": "outdoor", "indoor": False, "material": "open_air", "light": 3,
         "width_m": 10, "depth_m": 4, "anchors": [{"id": "porch_door", "name": "front door", "kind": "door_side", "x": 5, "y": 3.7}]},
        {"id": "kitchen", "name": "Kitchen", "light": 3, "width_m": 5, "depth_m": 4,
         "anchors": [{"id": "kitchen_door", "name": "front door", "kind": "door_side", "x": 2.5, "y": 0.3}]},
    ],
    "portals": [{"id": "front_door", "a": "porch", "b": "kitchen", "anchor_a": "porch_door", "anchor_b": "kitchen_door",
                 "kind": "door", "name": "front door", "open": False, "w": 90, "h": 200}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "kitchen", "x": 4, "y": 3},
        {"id": "june", "dossier": "core:actor/june_okafor", "place": "porch", "x": 2, "y": 2, "dress": True},
        {"id": "mara", "dossier": "core:actor/mara_voss", "place": "porch", "x": 4, "y": 2, "dress": True,
         "inventory": [{"item": "core:item/revolver_38", "slot": "worn", "label": "revolver"}]},
        {"id": "dale", "dossier": "core:actor/dale_pruitt", "place": "kitchen", "x": 2, "y": 2, "dress": True},
    ],
}


@pytest.fixture
def porch(fixture_packs, core_pack_dir):
    worlds = []

    def _load():
        w = load_scenario(copy.deepcopy(PORCH), packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
        with w.store.transaction() as tx:
            perception.compile_scene(tx, w.id("june"), t, 0)
        return w, t

    yield _load
    for w in worlds:
        w.store.close()


def cues_now(w, t, local="june"):
    with w.store.transaction() as tx:
        return cues.cues_of(tx, w.id(local), 0, t)


def soil(w, t, local, **amounts):
    with w.store.transaction() as tx:
        bodies.soil(tx, w.id(local), source="smeared", at=t, cause_event_id=None, turn_index=0, **amounts)


def test_a_gun_on_a_hip_in_plain_view_is_a_cue(porch):
    w, t = porch()
    got = cues_now(w, t)
    assert "visibly_armed" in got
    assert got.isdisjoint({"bloodied", "gore_covered", "filthy", "soaked", "naked", "half_dressed"})
    with w.store.transaction() as tx:
        objects.transfer(tx, w.id("revolver"), objects.Holder("body", w.id("mara"), "pocket"), None, t, w.id("mara"),
                         None, 0)
    assert "visibly_armed" not in cues_now(w, t), "out of sight in a pocket"


def test_only_someone_seen_lends_a_cue(porch):
    w, t = porch()
    soil(w, t, "dale", blood=5, gore=5)
    got = cues_now(w, t)
    assert "bloodied" not in got and "gore_covered" not in got, "Dale is behind a closed door"
    soil(w, t, "mara", blood=5)
    assert "bloodied" in cues_now(w, t)


def test_your_own_look_is_no_cue_to_you(porch):
    w, t = porch()
    soil(w, t, "june", blood=5, gore=5, grime=5, wet=3)
    assert cues_now(w, t).isdisjoint({"bloodied", "gore_covered", "filthy", "soaked"})
