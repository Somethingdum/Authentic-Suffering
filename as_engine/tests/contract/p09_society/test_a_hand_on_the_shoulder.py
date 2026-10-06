"""A hand on the shoulder (D-292). Core touch_shoulder / embrace / kiss; contracts/content.py AffordanceRequires.adults_only;
mind/affordance.py (the gate, AFF-07: last in the hold group); mind/perception.py (a touch is felt: TACTILE);
action/cascade.py welcome_touch and unwelcome_touched; mind/temper.py touched_unwanted / kissed_unwanted; core
CAS-123..125.

"I hug June" and "I kiss Mara" found nothing to do: there was no way to put a hand on anyone but to hit, shove, grab
or tie them. Now there is — a hand on a shoulder, arms around someone, a kiss between grown-ups — and it is felt,
in the dark too. Whether it is welcome is the one touched's own: from a partner, a friend, family, it is; from a
stranger it is not, and a kiss forced on someone costs trust, frightens, and is held against the one who did it.
A touch is never a blow.

A back room at noon (a dict scenario): Owen, his partner Mara, his friend June, Dale whom he has never met, and a
boy, Eli, all within arm's reach.
"""

from __future__ import annotations

import copy

import pytest

import helpers
from as_engine.action import cascade
from as_engine.action.resolve import resolve_wave
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.mind import perception, temper
from as_engine.mind.affordance import enumerate_affordances
from as_engine.physical import space
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(9)

MIN = 60_000
TOUCH = ("touch_shoulder", "embrace", "kiss")
RULES = ("CAS-123", "CAS-124", "CAS-125")

ROOM = {
    "schema": "as.scenario.v1", "name": "back_room", "seed": 3, "start": {"day": 400, "time": "12:00"},
    "places": [{"id": "room", "name": "Back room", "material": "brick", "light": 4, "width_m": 8, "depth_m": 6,
                "anchors": [{"id": "shelf", "name": "shelf", "x": 7, "y": 5}]}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "room", "x": 2, "y": 2},
        {"id": "mara", "stub": {"name": "Mara Voss", "age": 38, "sex": "female"}, "place": "room", "x": 3, "y": 2},
        {"id": "june", "stub": {"name": "June Okafor", "age": 29, "sex": "female"}, "place": "room", "x": 2, "y": 3},
        {"id": "dale", "stub": {"name": "Dale Pruitt", "age": 52, "sex": "male"}, "place": "room", "x": 2.8, "y": 1.2},
        {"id": "eli", "stub": {"name": "Eli Voss", "age": 9, "sex": "male"}, "place": "room", "x": 1, "y": 2},
    ],
    "relationships": [
        {"from": "mara", "to": "pc", "kind": "partner", "trust": 2, "affection": 3},
        {"from": "june", "to": "pc", "kind": "friend", "trust": 2, "affection": 1},
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


def rel(w, who):
    r = w.store.query_one("SELECT trust, resentment, fear FROM relationships WHERE from_id = ? AND to_id = ?",
                          (w.id(who), w.id("pc")))
    return tuple(r) if r else (0, 0, 0)


def touch(w, def_id, whom):
    """Owen does it; the one touched takes it in; the touch rules are swept; what it provoked in them."""
    at = now(w) + 1000
    with w.store.transaction() as tx:
        evs = resolve_wave(tx, w.rng, [helpers.make_intent(w, "pc", def_id, target=whom)], at, 1, horizon_ms=at + 10 * MIN)
        perception.compile_aftermath(tx, w.id(whom), evs, at + 1000, 1)
        cascade.sweep(tx, evs, [r for r in w.canon.all("cascade") if r.id in RULES], at + 1000, 1)
        kinds = [p.kind for p in temper.provocations(tx, w.id(whom), 1, at + 1000)]
        start = next(e for e in evs if e.type == EventType.ACTION_START)
        felt = [dict(r) for r in tx.query("SELECT channel, text, source_id FROM percept_log WHERE holder_id = ? AND event_id = ?",
                                          (w.id(whom), start.event_id))]
    return felt, kinds


def test_within_reach_and_between_grownups(room):
    w = room()
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id("pc"), now(w), 0)
        aff = enumerate_affordances(tx, w.id("pc"), w.canon.all("affordance"), now(w), 0)
    got = {(o.def_id, w.local(o.target_id)) for o in aff.pool if o.def_id in TOUCH}
    for who in ("mara", "june", "dale"):
        assert {(d, who) for d in TOUCH} <= got, who
    assert ("embrace", "eli") in got and ("touch_shoulder", "eli") in got
    assert ("kiss", "eli") not in got, "a kiss is between grown-ups"
    menu = [o.def_id in TOUCH for o in aff.options]
    assert menu == sorted(menu), "a hand on someone never crowds out doing something"


def test_felt_in_the_dark(room):
    w = room()
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("room"), {"light_level": 0}, "test", now(w), None, 0)
    felt, _ = touch(w, "touch_shoulder", "mara")
    assert [(p["channel"], p["text"], p["source_id"]) for p in felt] == [("tactile", "Someone puts a hand on your shoulder.", None)]
    w = room()
    felt, _ = touch(w, "kiss", "mara")
    assert [(p["channel"], p["source_id"]) for p in felt] == [("tactile", w.id("pc"))]
    assert felt[0]["text"].endswith(" kisses you.")


@pytest.mark.parametrize("def_id, whom, want", [
    ("kiss", "mara", (2, 0, 0)),          # her partner
    ("embrace", "june", (2, 0, 0)),       # a friend
    ("touch_shoulder", "june", (2, 0, 0)),
])
def test_welcome(room, def_id, whom, want):
    w = room()
    felt, kinds = touch(w, def_id, whom)
    assert felt and rel(w, whom) == want
    assert kinds == [], "nothing to be angry about"
    with w.store.transaction() as tx:
        assert cascade.welcome_touch(tx, w.id(whom), w.id("pc"), def_id)


@pytest.mark.parametrize("def_id, whom, want, kind", [
    ("touch_shoulder", "dale", (0, 1, 0), "touched_unwanted"),     # a stranger's hand
    ("embrace", "dale", (-1, 1, 0), "touched_unwanted"),
    ("kiss", "dale", (-2, 2, 1), "kissed_unwanted"),
    ("kiss", "june", (0, 2, 1), "kissed_unwanted"),                 # a friend is not someone who may kiss you
])
def test_unwelcome(room, def_id, whom, want, kind):
    w = room()
    felt, kinds = touch(w, def_id, whom)
    assert felt and rel(w, whom) == want
    assert kinds == [kind], "a touch is never a blow"


def test_from_someone_you_fear(room):
    w = room()
    key = {"from_id": w.id("mara"), "to_id": w.id("pc")}
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.RELATION_CHANGE, writer="mind.mind", at=now(w), turn_index=0,
                              writes=[WriteRecord(op=WriteOp.UPDATE, table="relationships", key=key, values={"fear": 2})],
                              payload={**key, "axis": "fear", "delta": 2}))
    felt, kinds = touch(w, "embrace", "mara")
    assert kinds == ["touched_unwanted"] and rel(w, "mara") == (1, 1, 2)
