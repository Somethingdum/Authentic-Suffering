"""Gone when you wake (D-213). mind.perception GONE-01 (compile_scene, compile_aftermath, a sound that wakes them);
action.cascade found_things_gone; core CAS-086 / CAS-087.

Robbing someone in their sleep cost nothing: a theft nobody saw was never found. Mara went to sleep with her jerky
in her pocket and her pack on her back, Owen took the jerky and the water bottle out of her pack while she slept, and
in the morning she never knew. Now waking up, or coming to, is when a person checks what they carry: whatever someone
else took from them, or from a bag still on them, while they were out — and that they never saw go — is "gone", and
they set themselves to finding out who. They do not know who; seeing it go is a theft seen (D-129), not this.

A back room at night (a dict scenario): Mara asleep on a cot with her pack; Owen beside her; June across the room.
"""

from __future__ import annotations

import copy

import pytest

from as_engine.action import cascade
from as_engine.mind import perception
from as_engine.physical import bodies, objects
from as_engine.physical.objects import Holder
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(9)

ROOM = {
    "schema": "as.scenario.v1", "name": "back_room_night", "seed": 5, "start": {"day": 400, "time": "02:00"},
    "places": [{"id": "room", "name": "Back room", "material": "brick", "light": 2, "width_m": 8, "depth_m": 6,
                "anchors": [{"id": "cot", "name": "cot", "x": 2, "y": 2}]}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "room", "x": 3, "y": 2},
        {"id": "mara", "stub": {"name": "Mara Voss", "age": 38, "sex": "female"}, "place": "room", "anchor": "cot",
         "inventory": [{"item": "core:item/jerky_pack", "slot": "pocket", "label": "jerky"},
                       {"item": "core:item/daypack", "slot": "worn", "label": "pack"},
                       {"item": "core:item/water_bottle", "container": "pack", "label": "bottle"}]},
        {"id": "june", "stub": {"name": "June Okafor", "age": 29, "sex": "female"}, "place": "room", "x": 7, "y": 5},
    ],
}


@pytest.fixture
def room(fixture_packs, core_pack_dir):
    worlds = []

    def _load():
        w = load_scenario(copy.deepcopy(ROOM), packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        return w

    yield _load
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def asleep(w, who, at):
    with w.store.transaction() as tx:
        bodies.posture_event(tx, w.id(who), "lying", at, None, 0, awareness="asleep")


def take(w, thief, label, at):
    with w.store.transaction() as tx:
        return objects.transfer(tx, w.id(label), Holder("body", w.id(thief), "pocket"), None, at, w.id(thief), None, 0)


def wake(w, who, at):
    """She wakes; she takes in her own waking; the rules about it are swept."""
    with w.store.transaction() as tx:
        ev = bodies.wake(tx, w.id(who), at, None, 0)
        got = perception.compile_aftermath(tx, w.id(who), [ev], at, 0)
        cascade.sweep(tx, [ev], [r for r in w.canon.all("cascade") if r.id in ("CAS-086", "CAS-087")], at, 0)
    texts = [r[0] for r in w.store.query("SELECT text FROM percept_log WHERE holder_id = ? AND channel = 'tactile' ORDER BY at, "
                                         "percept_id", (w.id(who),))]
    return got, texts


def goals(w, who):
    return [r[0] for r in w.store.query("SELECT text FROM open_loops WHERE holder_id = ? AND kind = 'goal' AND status = 'open'",
                                        (w.id(who),))]


def test_she_wakes_to_find_it_gone(room):
    w = room()
    t = now(w)
    asleep(w, "mara", t)
    take(w, "pc", "jerky", t + 60_000)
    take(w, "pc", "bottle", t + 120_000)
    _got, texts = wake(w, "mara", t + 3_600_000)
    assert texts == ["Your pack of jerky is gone.", "Your bottle of water is gone."], "from her pocket and from the pack still on her"
    assert goals(w, "mara") == ["Someone went through your things while you were out. Find out who."]
    assert w.store.query_one("SELECT COUNT(*) FROM relationships WHERE from_id = ? AND to_id = ? AND (trust != 0 OR resentment != 0)",
                             (w.id("mara"), w.id("pc")))[0] == 0, "she does not know who"


def test_found_once(room):
    w = room()
    t = now(w)
    asleep(w, "mara", t)
    take(w, "pc", "jerky", t + 60_000)
    wake(w, "mara", t + 3_600_000)
    asleep(w, "mara", t + 4_000_000)
    _got, texts = wake(w, "mara", t + 8_000_000)
    assert texts == ["Your pack of jerky is gone."], "the same loss is not found twice"


def test_what_she_saw_go_or_gave_is_not_gone(room):
    w = room()
    t = now(w)
    ev = take(w, "june", "jerky", t)
    with w.store.transaction() as tx:
        perception.compile_aftermath(tx, w.id("mara"), [ev], t + 500, 0)
    asleep(w, "mara", t + 60_000)
    with w.store.transaction() as tx:
        objects.transfer(tx, w.id("bottle"), Holder("body", w.id("mara"), "hand_r"), None, t + 70_000, w.id("mara"), None, 0)
    _got, texts = wake(w, "mara", t + 3_600_000)
    assert texts == [] and goals(w, "mara") == [], "the jerky was taken in front of her; the bottle she moved herself"


def test_a_sound_that_wakes_her_and_she_checks(room):
    """GONE-01 at the waking a sound causes (perception wakes her and she finds it at once)."""
    from as_engine.contracts.events import Event, EventType
    w = room()
    t = now(w)
    asleep(w, "mara", t)
    take(w, "pc", "jerky", t + 60_000)
    with w.store.transaction() as tx:
        bang = tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", at=t + 600_000, turn_index=0,
                                     actor_id=w.id("june"), place_id=w.id("room"),
                                     payload={"source_db": 95, "kind": "slam", "text": "a door slamming", "place_id": w.id("room"),
                                              "x_m": 7.0, "y_m": 5.0}))
        perception.compile_aftermath(tx, w.id("mara"), [bang], t + 600_000, 0)
    assert w.store.query_one("SELECT awareness FROM bodies WHERE body_id = ?", (w.id("mara"),))[0] == "awake"
    assert [r[0] for r in w.store.query("SELECT text FROM percept_log WHERE holder_id = ? AND channel = 'tactile'",
                                        (w.id("mara"),))] == ["Your pack of jerky is gone."]


def test_the_player_finds_it_too_and_decides_for_himself(room):
    w = room()
    t = now(w)
    asleep(w, "pc", t)
    with w.store.transaction() as tx:
        objects.create(tx, "core:item/jerky_pack", 1, Holder("body", w.id("pc"), "pocket"), "scenario", {}, t, None, 0)
    item = w.store.query_one("SELECT item_id FROM items WHERE holder_body = ? AND def_ref = 'core:item/jerky_pack'", (w.id("pc"),))[0]
    with w.store.transaction() as tx:
        objects.transfer(tx, item, Holder("body", w.id("june"), "pocket"), None, t + 60_000, w.id("june"), None, 0)
    _got, texts = wake(w, "pc", t + 3_600_000)
    assert texts == ["Your pack of jerky is gone."] and goals(w, "pc") == [], "the story tells him; what he makes of it is his (C06)"
