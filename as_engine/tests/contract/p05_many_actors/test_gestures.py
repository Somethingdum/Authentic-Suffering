"""A gesture is seen, never heard; eyes on one thing miss others (P5, Actor v2 — Actor Spec §9).
action/resolve.py GEST-03 and the start's attention; mind/perception.py GESTURE; sense/optics.py
FOCUS-02.

A dim store room (a dict scenario, light 2): Mara in the middle, June a few steps off, Dale half
hidden behind the crates; the player outside in the yard, the door shut.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

import helpers
from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.mind import perception
from as_engine.sense.optics import visibility
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(5)

STORE = {
    "schema": "as.scenario.v1", "name": "dim_store", "seed": 19, "start": {"day": 400, "time": "12:00"},
    "places": [
        {"id": "store", "name": "Store room", "material": "brick", "light": 2, "width_m": 8, "depth_m": 6,
         "anchors": [{"id": "door_in", "name": "yard door", "kind": "door_side", "x": 7.7, "y": 3},
                     {"id": "crates", "name": "crates", "kind": "cover", "x": 6, "y": 5, "cover": 1, "concealment": 1}]},
        {"id": "yard", "name": "Yard", "kind": "outdoor", "indoor": False, "material": "open_air", "light": 3,
         "width_m": 20, "depth_m": 20, "anchors": [{"id": "door_out", "name": "yard door", "kind": "door_side", "x": 0.3, "y": 10}]},
    ],
    "portals": [{"id": "yard_door", "a": "store", "b": "yard", "anchor_a": "door_in", "anchor_b": "door_out",
                 "kind": "door", "name": "yard door", "w": 90, "h": 200}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "yard", "x": 3, "y": 10},
        {"id": "mara", "stub": {"name": "Mara Voss", "age": 38, "sex": "female"}, "place": "store", "x": 3, "y": 3},
        {"id": "june", "stub": {"name": "June Okafor", "age": 29, "sex": "female"}, "place": "store", "x": 4.5, "y": 3},
        {"id": "dale", "stub": {"name": "Dale Pruitt", "age": 52, "sex": "male"}, "place": "store", "anchor": "crates"},
        {"id": "eli", "stub": {"name": "Eli Ward", "age": 70, "sex": "male", "special": {"P": 1}}, "place": "store",
         "x": 1, "y": 5},
    ],
}


@pytest.fixture
def store(fixture_packs, core_pack_dir):
    worlds = []

    def _load():
        w = load_scenario(STORE, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        return w

    yield _load
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def wave(w, intent, at=None):
    t = now(w) if at is None else at
    with w.store.transaction() as tx:
        return resolve_wave(tx, helpers.ScriptedRng(), barrier(tx, [intent]), t, 0, horizon_ms=t + 10_000)


def waiting(w, *, gesture=None, attention=None, local="mara"):
    it = helpers.make_intent(w, local, "wait_here")
    return dataclasses.replace(it, gesture=gesture, attention=attention)


def of(evs, type_):
    return [e for e in evs if e.type == type_]


def seen(w, holder, at):
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(holder), at, 0)
    return [(r[0], r[1]) for r in w.store.query(
        "SELECT p.channel, p.text FROM percept_log p JOIN events e ON e.event_id = p.event_id "
        "WHERE p.holder_id = ? AND e.type = 'GESTURE' ORDER BY p.at", (w.id(holder),))]


# --------------------------------------------------------------------------- GEST-03
def test_a_gesture_goes_out_with_the_attempt(store):
    w = store()
    evs = wave(w, waiting(w, gesture=("point_at", w.id("june"))))
    (start,) = of(evs, "ACTION_START")
    (g,) = of(evs, "GESTURE")
    assert g.payload == {"actor_id": w.id("mara"), "gesture": "point_at", "target_id": w.id("june")}
    assert (g.cause_event_id, g.at, g.writer) == (start.event_id, start.at, "action.propagate")
    assert [e.type for e in evs].index(start.type) < [e.type for e in evs].index(g.type)


def test_she_sees_it_pointed_at_her(store):
    """GESTURE: visual, for those who see the actor at clear or partial; 'you' for its target."""
    w = store()
    t = now(w)
    wave(w, waiting(w, gesture=("point_at", w.id("june"))))
    ((channel, text),) = seen(w, "june", t)
    assert channel == "visual" and text.endswith(" points at you.")


def test_nobody_hears_a_gesture(store):
    """The player outside the shut door hears Mara if she speaks — never a gesture; old Eli, whose
    eyes make her out only as a figure, does not read it either."""
    w = store()
    t = now(w)
    assert visibility(w.store, w.id("eli"), w.id("mara"), t) == "silhouette"
    wave(w, waiting(w, gesture=("empty_hands", None)))
    assert seen(w, "pc", t) == [] and seen(w, "eli", t) == []
    ((_, text),) = seen(w, "june", t)
    assert text.endswith(" holds up empty hands.")


# --------------------------------------------------------------------------- FOCUS-02
def test_eyes_on_one_thing_miss_others(store):
    """Her eyes on June: June +1 (partial -> clear), everything else -1 (Dale behind the crates,
    partial -> silhouette); the next attempt without attention ends it."""
    w = store()
    t = now(w)
    mara, june, dale = w.id("mara"), w.id("june"), w.id("dale")
    assert (visibility(w.store, mara, june, t), visibility(w.store, mara, dale, t)) == ("partial", "partial")
    evs = wave(w, waiting(w, attention=june))
    assert of(evs, "ACTION_START")[0].payload["attention"] == june
    assert (visibility(w.store, mara, june, t + 1), visibility(w.store, mara, dale, t + 1)) == ("clear", "silhouette")
    wave(w, waiting(w), at=t + 2000)
    assert (visibility(w.store, mara, june, t + 2001), visibility(w.store, mara, dale, t + 2001)) == ("partial", "partial")


def test_watching_the_door_is_watching_whoever_stands_in_it(store):
    """A portal kept in view: whoever stands at either of its sides is seen better."""
    w = store()
    t = now(w)
    mara, june = w.id("mara"), w.id("june")
    with w.store.transaction() as tx:
        from as_engine.physical.space import move_event
        a = tx.query_one("SELECT x_m, y_m FROM anchors WHERE anchor_id = ?", (w.id("door_in"),))
        tx.commit_event(move_event(tx, june, w.id("store"), w.id("door_in"), a[0], a[1], t, None, 0))
    base = visibility(w.store, mara, june, t + 1500)
    wave(w, waiting(w, attention=w.id("yard_door")), at=t + 2000)
    order = ["none", "silhouette", "partial", "clear"]
    assert order.index(visibility(w.store, mara, june, t + 3000)) == order.index(base) + 1
