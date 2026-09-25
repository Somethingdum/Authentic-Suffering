"""A sound goes as far as it goes (P7, Actor v2 B6 — fidelity C08: wake distant recipients by
causal reach). Rule SEL-07 (turn/select.py reached; turn/pipeline.py S11).

Owen is in the back room of a row of rooms; a shot goes off in the yard two doors away. The
moment's area stops at the street — but Wren, in the shop past the street, hears the shot all the
same, so she perceives it and may react. Nobody thinks for the rest of the city.
"""

from __future__ import annotations

import copy

import pytest

from as_engine.contracts.common import CallClass
from as_engine.contracts.events import Event, EventType
from as_engine.testing.scenario import load_scenario
from as_engine.turn import select
from slice_kit import pick, play

pytestmark = pytest.mark.phase(7)

ROW = {
    "schema": "as.scenario.v1", "name": "row_of_rooms", "seed": 17, "start": {"day": 400, "time": "15:00"},
    "places": [
        {"id": "room", "name": "Back room", "material": "brick", "light": 3, "width_m": 6, "depth_m": 5,
         "anchors": [{"id": "chair", "name": "chair", "x": 3, "y": 2}]},
        {"id": "hall", "name": "Hall", "material": "brick", "light": 3, "width_m": 8, "depth_m": 3},
        {"id": "yard", "name": "Yard", "kind": "outdoor", "indoor": False, "material": "open_air", "light": 3,
         "width_m": 12, "depth_m": 10},
        {"id": "street", "name": "Street", "kind": "outdoor", "indoor": False, "material": "open_air", "light": 3,
         "width_m": 20, "depth_m": 8},
        {"id": "shop", "name": "Corner shop", "material": "brick", "light": 3, "width_m": 8, "depth_m": 6},
        {"id": "cellar", "name": "Cellar", "material": "concrete", "light": 1, "width_m": 6, "depth_m": 6},
    ],
    "portals": [
        {"id": "p1", "a": "room", "b": "hall", "kind": "door", "name": "room door", "open": True, "w": 90, "h": 200},
        {"id": "p2", "a": "hall", "b": "yard", "kind": "door", "name": "yard door", "open": True, "w": 90, "h": 200},
        {"id": "p3", "a": "yard", "b": "street", "kind": "gate", "name": "yard gate", "open": True, "w": 200, "h": 200},
        {"id": "p4", "a": "street", "b": "shop", "kind": "door", "name": "shop door", "open": True, "w": 90, "h": 200},
    ],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "room", "anchor": "chair"},
        {"id": "wren", "stub": {"name": "Wren Adair", "age": 34, "sex": "female"}, "place": "shop", "x": 4, "y": 3},
        {"id": "sol", "stub": {"name": "Sol Baptiste", "age": 60, "sex": "male"}, "place": "cellar", "x": 3, "y": 3},
    ],
    "events_due": [{"at": "+2s", "type": "NOISE", "place": "yard",
                    "payload": {"source_db": 130, "kind": "gunshot", "text": "a gunshot"}}],
}


@pytest.fixture
def row(fixture_packs, core_pack_dir):
    worlds = []

    def _load():
        w = load_scenario(copy.deepcopy(ROW), packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        return w
    yield _load
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def test_the_moment_ends_at_the_street_but_the_shot_does_not(row):
    w = row()
    t = now(w)
    with w.store.transaction() as tx:
        shot = tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", at=t, turn_index=0,
                                     payload={"source_db": 130, "kind": "gunshot", "text": "a gunshot", "place_id": w.id("yard")}))
        assert w.id("shop") not in select.active_area(tx, w.id("pc"), 0)
        assert w.id("wren") not in select.candidates(tx, w.id("pc"), 0, t + 60_000)
        heard = select.reached(tx, [shot], 0)
    assert w.id("wren") in heard, "the shot reaches the shop"
    assert w.id("sol") not in heard, "the cellar has no way in: nothing reaches it"
    assert w.id("pc") in heard, "the one who hears it where he sits"


def test_she_hears_it_and_it_is_hers(row, fake):
    w = row()
    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "observe_area"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    s = w.session()
    play(s, "do", "I sit and listen.")
    shot = w.store.query_one("SELECT event_id FROM events WHERE type = 'NOISE' AND json_extract(payload, '$.kind') = 'gunshot'")[0]
    got = w.store.query("SELECT fidelity FROM percept_log WHERE holder_id = ? AND event_id = ?", (w.id("wren"), shot))
    assert got and got[0][0] in ("exact", "partial"), "Wren perceived the shot from the shop"
    assert not w.store.query("SELECT 1 FROM percept_log WHERE holder_id = ? AND event_id = ?", (w.id("sol"), shot))
