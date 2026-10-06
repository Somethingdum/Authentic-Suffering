"""Holding down the bitten (D-286). action/cascade.py knew_infected, bonded_onlookers_unknowing; mind/temper.py
TEMPER-03 manhandled_bonded; core CAS-119..122.

The owner: "An infected person is a threat to every non infected. It is a safety precaution." Putting down someone
known to be bitten is not a killing to whoever knew (D-202) — but D-282 made pinning them, or tying them hand and
foot, a wrong to the people who love them, and held against the one who did it. Mara watched June bitten; when Owen
grabs June and ties her, Mara is not provoked and holds nothing against him. Whoever did not see the bite still does.
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception, temper
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec

pytestmark = pytest.mark.phase(9)

RULES = ("CAS-119", "CAS-120", "CAS-121", "CAS-122")


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def rel(w, who, axis):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(who), w.id("pc")))
    return r[0] if r else 0


def room(w, *, bitten_seen_by):
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("sales_floor"), None, 5.0, 2.0, t, None, 0))
        tx.commit_event(space.move_event(tx, w.id("pc"), w.id("sales_floor"), None, 5.6, 2.0, t, None, 0))
        for who in ("mara", "alice"):
            perception.compile_scene(tx, w.id(who), t, 0)
        why = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=0, payload={"what": "test"}))
        bite = bodies.apply_harm(tx, w.id("june"), WoundSpec("arm_l", "bite", "significant", 0), t + 100, why.event_id, 0, w.rng)[0]
        for who in bitten_seen_by:
            perception.compile_aftermath(tx, w.id(who), [bite], t + 200, 0)
    return t + 1000


def held_down(w, def_id, at):
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0, actor_id=w.id("pc"),
                                   payload={"actor_id": w.id("pc"), "def_id": def_id, "verb": "manipulate",
                                            "target_id": w.id("june"), "label": f"{def_id} June", "visible": True,
                                            "seen": "takes hold of {target}"}))
        perception.compile_aftermath(tx, w.id("mara"), [ev], at + 500, 0)
        got = [p.kind for p in temper.provocations(tx, w.id("mara"), 0, at + 1000)]
        cascade.sweep(tx, [ev], [r for r in w.canon.all("cascade") if r.id in RULES], at + 1000, 0)
    return got


@pytest.mark.parametrize("def_id", ["grapple", "tie_up"])
def test_she_saw_the_bite(scenario, def_id):
    w = scenario("metal_fence")
    at = room(w, bitten_seen_by=("mara",))
    with w.store.transaction() as tx:
        assert cascade.knew_infected(tx, w.id("mara"), w.id("june"), at)
    before = rel(w, "mara", "trust"), rel(w, "mara", "resentment")
    assert "manhandled_bonded" not in held_down(w, def_id, at)
    assert (rel(w, "mara", "trust"), rel(w, "mara", "resentment")) == before, "a safety precaution"


def test_she_did_not(scenario):
    w = scenario("metal_fence")
    at = room(w, bitten_seen_by=())
    with w.store.transaction() as tx:
        assert not cascade.knew_infected(tx, w.id("mara"), w.id("june"), at)
    before = rel(w, "mara", "resentment")
    assert "manhandled_bonded" in held_down(w, "grapple", at)
    assert rel(w, "mara", "resentment") == before + 1
