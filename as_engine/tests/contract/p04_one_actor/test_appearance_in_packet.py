"""What a person sees and smells of the people around them goes into their decision (P4, the owner's
F1a and F1b). Rules LOOK-06, SMELL-04 (mind/packet.py PacketEntity.appearance;
prompts/actor_cognition.user.j2).

June stands on the porch with Mara two metres away, the revolver on Mara's hip in plain view; Owen
is at the steps with his axe in hand; Dale, a friend of June's, is inside the kitchen, out of sight.
June's packet says what she sees of each person who is here — and nothing about anyone who is not.
"""

from __future__ import annotations

import copy

import pytest

from as_engine.contracts.common import LOD, CallClass
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet
from as_engine.physical import space
from as_engine.prompts.render import render
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(4)

PORCH = {
    "schema": "as.scenario.v1", "name": "porch", "seed": 8, "start": {"day": 300, "time": "15:00"},
    "places": [
        {"id": "porch", "name": "Front porch", "kind": "outdoor", "indoor": False, "material": "open_air", "light": 3,
         "width_m": 10, "depth_m": 4, "anchors": [{"id": "porch_door", "name": "front door", "kind": "door_side", "x": 5, "y": 3.7}]},
        {"id": "kitchen", "name": "Kitchen", "light": 3, "width_m": 5, "depth_m": 4,
         "anchors": [{"id": "kitchen_door", "name": "front door", "kind": "door_side", "x": 2.5, "y": 0.3}]},
    ],
    "portals": [{"id": "front_door", "a": "porch", "b": "kitchen", "anchor_a": "porch_door", "anchor_b": "kitchen_door",
                 "kind": "door", "name": "front door", "open": False, "w": 90, "h": 200}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "porch", "x": 8, "y": 1,
         "inventory": [{"item": "core:item/fire_axe", "slot": "hand_r"}]},
        {"id": "june", "dossier": "core:actor/june_okafor", "place": "porch", "x": 2, "y": 2, "dress": True},
        {"id": "mara", "dossier": "core:actor/mara_voss", "place": "porch", "x": 4, "y": 2, "dress": True,
         "inventory": [{"item": "core:item/revolver_38", "slot": "worn"}]},
        {"id": "dale", "dossier": "core:actor/dale_pruitt", "place": "kitchen", "x": 2, "y": 2, "dress": True},
    ],
    "relationships": [{"from": "june", "to": "dale", "kind": "friend", "trust": 1, "affection": 1}],
}


@pytest.fixture
def porch(fixture_packs, core_pack_dir):
    w = load_scenario(copy.deepcopy(PORCH), packs_root=fixture_packs, core_pack_dir=core_pack_dir)
    yield w
    w.store.close()


def test_the_people_here_come_with_what_she_sees_of_them(porch):
    w = porch
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    june = w.id("june")
    with w.store.transaction() as tx:
        perception.compile_scene(tx, june, t, 0)
        aff = enumerate_affordances(tx, june, w.canon.all("affordance"), t, 0)
        p = build_packet(tx, june, LOD.HOT, aff, 0, t)
        want = perception.appearance_text(tx, june, w.id("mara"), "clear", space.point_distance(tx, june, w.id("mara")))
    ent = {w.local(p.handles[e.handle]): e for e in p.entities}
    assert set(ent) == {"pc", "mara", "dale"}
    assert ent["mara"].whereabouts == "here" and ent["mara"].appearance == want
    assert want.startswith("Shoulder-length dark blonde hair") and want.endswith("carrying a .38 revolver.")
    assert ent["pc"].whereabouts == "here" and ent["pc"].appearance == "", \
        "his looks were never recorded and the axe in his hand is the percept's to say"
    assert ent["dale"].whereabouts != "here" and ent["dale"].appearance == "", "out of sight: nothing about his looks"
    user = render(CallClass.ACTOR_COGNITION, p=p)[1].content
    assert f"— here\n  {want}\n" in user, "on its own line, under the line that names her"
    assert "scraggly" not in user and "work jacket, torn" not in user


def test_someone_smeared_with_the_dead_reeks_of_them(porch):
    """F1b: the line under a person says what she smells on them too (SMELL-04)."""
    from as_engine.physical import bodies

    w = porch
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    june = w.id("june")
    with w.store.transaction() as tx:
        bodies.soil(tx, w.id("mara"), gore=5, source="smeared", at=t, cause_event_id=None, turn_index=0)
        perception.compile_scene(tx, june, t, 0)
        aff = enumerate_affordances(tx, june, w.canon.all("affordance"), t, 0)
        p = build_packet(tx, june, LOD.HOT, aff, 0, t)
        look = perception.appearance_text(tx, june, w.id("mara"), "clear", space.point_distance(tx, june, w.id("mara")))
    [mara] = [e for e in p.entities if p.handles[e.handle] == w.id("mara")]
    assert look.endswith("; caked in gore.")
    assert mara.appearance == look + " Reeks of the dead."
