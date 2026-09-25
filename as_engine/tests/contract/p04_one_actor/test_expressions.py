"""A gesture and where you look go with an attempt (P4, Actor v2 — Actor Spec §9). mind/packet.py
GEST-01, FOCUS-01; action/intent.py INTENT-09 (the hand check, the Intent's gesture and attention);
mind/affordance.py BoundAffordance.hands; prompts (the lists and the answer's two fields).

One primary attempt at a time — but a shrug can go with waiting, a pointed finger with a shout, and
you can keep your eyes on the door while you talk. A gesture needs the hands the attempt leaves
free; showing both empty hands cannot go with carrying something in both. Contact is never a
gesture: a touch is an attempt of its own.

A back room (a dict scenario): Mara with nothing in her hands; June with a knife and a bottle; Dale
by the door to the yard; the player.
"""

from __future__ import annotations

import pytest

import helpers
from as_engine.action.intent import IntentError, intent_from_dict, intent_to_dict, to_intent
from as_engine.contracts.common import LOD, CallClass
from as_engine.contracts.mind import ActionPayload
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet
from as_engine.prompts.render import render
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(4)

ROOM = {
    "schema": "as.scenario.v1", "name": "back_room", "seed": 17, "start": {"day": 400, "time": "12:00"},
    "places": [
        {"id": "room", "name": "Back room", "material": "brick", "light": 3, "width_m": 8, "depth_m": 6,
         "anchors": [{"id": "door_in", "name": "yard door", "kind": "door_side", "x": 7.7, "y": 3},
                     {"id": "shelf", "name": "shelf", "x": 3.5, "y": 3.5}]},
        {"id": "yard", "name": "Yard", "kind": "outdoor", "indoor": False, "material": "open_air", "light": 3,
         "width_m": 20, "depth_m": 20, "anchors": [{"id": "door_out", "name": "yard door", "kind": "door_side", "x": 0.3, "y": 10}]},
    ],
    "portals": [{"id": "yard_door", "a": "room", "b": "yard", "anchor_a": "door_in", "anchor_b": "door_out",
                 "kind": "door", "name": "yard door", "w": 90, "h": 200}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "room", "x": 1, "y": 1},
        {"id": "mara", "stub": {"name": "Mara Voss", "age": 38, "sex": "female"}, "place": "room", "x": 3, "y": 3},
        {"id": "june", "stub": {"name": "June Okafor", "age": 29, "sex": "female"}, "place": "room", "x": 4, "y": 3,
         "inventory": [{"item": "core:item/kitchen_knife", "slot": "hand_r", "label": "knife"},
                       {"item": "core:item/water_bottle", "slot": "hand_l", "label": "bottle"}]},
        {"id": "dale", "stub": {"name": "Dale Pruitt", "age": 52, "sex": "male"}, "place": "room", "anchor": "door_in"},
        {"id": "nita", "stub": {"name": "Nita Rao", "age": 44, "sex": "female"}, "place": "room", "x": 2, "y": 5},
    ],
    "items": [{"item": "core:item/water_jug", "place": "room", "anchor": "shelf", "label": "jug"}],
}


@pytest.fixture
def room(fixture_packs, core_pack_dir):
    worlds = []

    def _load():
        w = load_scenario(ROOM, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        return w

    yield _load
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def packet(w, local, reaction=False):
    t = now(w)
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(local), t, 0)
        aff = enumerate_affordances(tx, w.id(local), w.canon.all("affordance"), t, 0)
        return build_packet(tx, w.id(local), LOD.HOT, aff, 0, t, reaction=reaction), aff


def gestures(pkt):
    return [(g.handle, pkt.handles[g.handle], g.label, g.hands) for g in pkt.gestures]


def act(choice, **kw):
    return ActionPayload(choice=choice, goal="Make myself understood", **kw)


# --------------------------------------------------------------------------- GEST-01 / FOCUS-01
def test_what_she_can_do_with_empty_hands(room):
    """Every gesture her hands allow: the untargeted ones once, the targeted ones toward each person
    here (P order); G handles in catalog order."""
    w = room()
    pkt, _ = packet(w, "mara")
    got = gestures(pkt)
    assert [g[1].split(":")[0] for g in got][:3] == ["nod", "shake_head", "shrug"]
    here = [pkt.handles[e.handle] for e in pkt.entities if e.whereabouts == "here"]
    pointed = [g[1].split(":")[1] for g in got if g[1].startswith("point_at:")]
    assert len(here) == 4 and pointed == here[:3], "toward the first three people here, no more"
    assert ("empty_hands:*" in [g[1] for g in got]) and pkt.hands_free == 2
    assert [g[0] for g in got] == [f"G{i}" for i in range(1, len(got) + 1)]
    lab = {g[1]: g[2] for g in got}
    june = next(e for e in pkt.entities if pkt.handles[e.handle] == w.id("june"))
    assert lab[f"point_at:{w.id('june')}"] == f"point at {june.description}"


def test_hands_full_leaves_only_what_needs_none(room):
    w = room()
    pkt, _ = packet(w, "june")
    assert pkt.hands_free == 0
    assert {g[1].split(":")[0] for g in gestures(pkt)} == {"nod", "shake_head", "shrug"}
    assert all(g[3] == 0 for g in gestures(pkt))


def test_where_she_may_keep_her_eyes(room):
    """F handles: each person here, then each door of the room she sees."""
    w = room()
    pkt, _ = packet(w, "mara")
    here = [pkt.handles[e.handle] for e in pkt.entities if e.whereabouts == "here"]
    points = [(f.handle, pkt.handles[f.handle], f.label) for f in pkt.attention_points]
    assert [p[1] for p in points] == here + [w.id("yard_door")]
    assert points[-1][2] == "Watch the yard door"
    assert all(p[2].startswith("Keep your eyes on ") for p in points[:-1])


def test_a_reaction_offers_neither(room):
    w = room()
    pkt, _ = packet(w, "mara", reaction=True)
    assert pkt.gestures == [] and pkt.attention_points == []


def test_the_prompt_lists_them_and_the_answer_may_name_one_of_each(room):
    w = room()
    pkt, _ = packet(w, "mara")
    system, user = (m.content for m in render(CallClass.ACTOR_COGNITION, p=pkt))
    assert "A gesture that may go with it (optional)" in user and "Where you may keep your eyes (optional)" in user
    assert f"- {pkt.gestures[0].handle}: {pkt.gestures[0].label}" in user
    assert '"gesture": null, or the handle of one gesture' in system and '"attention": null, or the handle' in system
    bare, _ = packet(w, "mara", reaction=True)
    _, quiet = (m.content for m in render(CallClass.ACTOR_REACTION, p=bare))
    assert "A gesture that may go with it" not in quiet and "Where you may keep your eyes" not in quiet


# --------------------------------------------------------------------------- INTENT-09
def test_a_gesture_and_a_look_go_into_the_intent(room):
    w = room()
    pkt, aff = packet(w, "mara")
    g = next(x.handle for x in pkt.gestures if pkt.handles[x.handle] == f"point_at:{w.id('dale')}")
    f = next(x.handle for x in pkt.attention_points if pkt.handles[x.handle] == w.id("yard_door"))
    it = to_intent(pkt, aff, act(helpers.handle_for(pkt, "wait_here"), gesture=g, attention=f), lod=LOD.HOT, source="model")
    assert it.gesture == ("point_at", w.id("dale")) and it.attention == w.id("yard_door")
    back = intent_from_dict(intent_to_dict(it))
    assert back.gesture == it.gesture and back.attention == it.attention and back.bound.hands == it.bound.hands
    shrug = next(x.handle for x in pkt.gestures if pkt.handles[x.handle] == "shrug:*")
    assert to_intent(pkt, aff, act(helpers.handle_for(pkt, "wait_here"), gesture=shrug), lod=LOD.HOT, source="model").gesture == ("shrug", None)


def test_a_gesture_needs_the_hands_the_attempt_leaves(room):
    """BoundAffordance.hands is the def's requires.hands_free: picking up the jug takes a hand, so
    showing both empty hands cannot go with it ('no_free_hand'); pointing (one hand) and a nod
    (none) can."""
    w = room()
    pkt, aff = packet(w, "mara")
    h = helpers.handle_for(pkt, "pick_up_item", "jug", w)
    opt = next(o for o in aff.pool if o.def_id == "pick_up_item")
    assert opt.hands == 1
    need = next(x.handle for x in pkt.gestures if pkt.handles[x.handle] == "empty_hands:*")
    err = to_intent(pkt, aff, act(h, gesture=need), lod=LOD.HOT, source="model")
    assert isinstance(err, IntentError) and err.kind == "no_free_hand"
    point = next(x.handle for x in pkt.gestures if pkt.handles[x.handle] == f"point_at:{w.id('dale')}")
    assert to_intent(pkt, aff, act(h, gesture=point), lod=LOD.HOT, source="model").gesture == ("point_at", w.id("dale"))
    nod = next(x.handle for x in pkt.gestures if pkt.handles[x.handle] == "nod:*")
    assert to_intent(pkt, aff, act(h, gesture=nod), lod=LOD.HOT, source="model").gesture == ("nod", None)


def test_a_look_is_not_a_gesture_nor_a_gesture_a_look(room):
    """INTENT-09: the gesture field takes only G handles, attention only F handles."""
    w = room()
    pkt, aff = packet(w, "mara")
    wait = helpers.handle_for(pkt, "wait_here")
    g, f = pkt.gestures[0].handle, pkt.attention_points[0].handle
    for kw in ({"gesture": f}, {"attention": g}):
        err = to_intent(pkt, aff, act(wait, **kw), lod=LOD.HOT, source="model")
        assert isinstance(err, IntentError) and err.kind == "hallucinated_expression", kw
