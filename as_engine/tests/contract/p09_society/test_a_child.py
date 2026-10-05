"""A child (D-148). action/cascade.py selectors left_in_danger_by and saw_child_left_by; core CAS-063..065;
world/rumours.py claims 'hurt_a_child' and 'left_their_child'.

Killing a child broke something in the killer and cost everything (D-123); hurting one was any other blow. And a
parent could run from a room where the dead were, or where blood had just been spilled, and leave their child
there, and it cost nothing — not with the child, not with anyone who saw them go.
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec

pytestmark = pytest.mark.phase(9)

EYES = ("pc", "mara", "alice", "june", "eli")


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def rel(w, a, b, axis="trust"):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def stress(w, who):
    return w.store.query_one("SELECT stress FROM actors WHERE actor_id = ?", (w.id(who),))[0]


def claims_of(w, who):
    return [r[0] for r in w.store.query("SELECT p.predicate FROM rumours r JOIN propositions p ON p.prop_id = r.prop_id "
                                        "WHERE r.origin_holder = ?", (w.id(who),))]


def everyone_on_the_floor(w):
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        for k, who in enumerate(("june", "eli")):
            tx.commit_event(space.move_event(tx, w.id(who), w.id("sales_floor"), None, 4.0 + k, 4.0, t, None, 0))
        bodies.wake(tx, w.id("eli"), t, None, 0)
    return t + 1000


def hit(w, who, whom, at):
    with w.store.transaction() as tx:
        st = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0, actor_id=w.id(who),
                                   payload={"actor_id": w.id(who), "def_id": "punch", "verb": "attack", "target_id": w.id(whom)}))
        hurt = bodies.apply_harm(tx, w.id(whom), WoundSpec(Anatomy.ARM_L, WoundType.BLUNT, WoundSeverity.MINOR), at + 300,
                                 st.event_id, 0, w.rng)
        for x in EYES:
            if x != whom:
                perception.compile_aftermath(tx, w.id(x), [st] + hurt, at + 800, 0)
    return next(e for e in hurt if e.type == EventType.HARM)


def walk_out(w, who, at):
    with w.store.transaction() as tx:
        ev = tx.commit_event(space.move_event(tx, w.id(who), w.id("storeroom"), None, 2.0, 1.0, at, None, 0))
        for x in EYES:
            if x != who:
                perception.compile_aftermath(tx, w.id(x), [ev], at + 200, 0)
    return ev


def sweep(w, evs, at, ids):
    with w.store.transaction() as tx:
        return cascade.sweep(tx, list(evs), [r for r in w.canon.all("cascade") if r.id in ids], at, 0)


def test_owen_hits_eli(scenario):
    w = scenario("metal_fence")
    t = everyone_on_the_floor(w)
    trust, s0 = rel(w, "june", "pc"), stress(w, "june")
    harm = hit(w, "pc", "eli", t)
    sweep(w, [harm], t + 1000, ("CAS-063",))
    assert (rel(w, "june", "pc"), stress(w, "june")) == (max(-3, trust - 1), min(10, s0 + 1))
    assert "hurt_a_child" in claims_of(w, "june")


def test_mara_runs_and_leaves_eli(scenario):
    """Blood has just been spilled on the floor; Mara runs into the storeroom and leaves Eli there."""
    w = scenario("metal_fence")
    t = everyone_on_the_floor(w)
    hit(w, "alice", "june", t)
    eli, june = rel(w, "eli", "mara"), rel(w, "june", "mara")
    ev = walk_out(w, "mara", t + 5000)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "left_in_danger_by(trigger.event_id)", ev) == [w.id("eli")]
        assert w.id("june") in cascade.select(tx, "saw_child_left_by(trigger.event_id)", ev)
    sweep(w, [ev], t + 6000, ("CAS-064", "CAS-065"))
    assert rel(w, "eli", "mara") == max(-3, eli - 2)
    assert w.store.query("SELECT strength FROM open_loops WHERE holder_id = ? AND kind = 'grudge' AND text LIKE ?",
                         (w.id("eli"), "%left you behind%"))[0][0] == 3
    assert rel(w, "june", "mara") == max(-3, june - 1) and "left_their_child" in claims_of(w, "june")


def test_a_quiet_room_is_no_danger(scenario):
    w = scenario("metal_fence")
    t = everyone_on_the_floor(w)
    ev = walk_out(w, "mara", t + 5000)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "left_in_danger_by(trigger.event_id)", ev) == []
        assert cascade.select(tx, "saw_child_left_by(trigger.event_id)", ev) == []
