"""Left behind (D-142). action/cascade.py selector left_bleeding_by; core CAS-059; seen going (D-141,
sense/optics.py leaving, mind/perception.py).

leave_wounded was a line a person's card could draw, and walking out on someone who loves you while they lie
bleeding cost nothing. Now whoever is left behind, bleeding badly and watching you go, trusts you less and does
not forget it — the player's character among those who can walk out (never one it is written into, C06).
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


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def rel(w, a, b, axis="trust"):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def grudges(w, who):
    return w.store.query("SELECT text, strength FROM open_loops WHERE holder_id = ? AND kind = 'grudge' AND text LIKE ?",
                         (w.id(who), "%left you bleeding%"))


def june_bleeding(w, severity=WoundSeverity.SEVERE):
    """June cuts her leg open on the glass climbing over the counter."""
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("sales_floor"), None, 6.0, 5.0, t, None, 0))
        glass = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=t + 50, turn_index=0,
                                      actor_id=w.id("june"), payload={"actor_id": w.id("june"), "def_id": "climb_obstacle",
                                                                      "verb": "climb", "target_id": None}))
        bodies.apply_harm(tx, w.id("june"), WoundSpec(Anatomy.LEG_L, WoundType.CUT, severity), t + 100, glass.event_id, 0, w.rng)
    return t + 1000


def walk_out(w, who, at):
    with w.store.transaction() as tx:
        ev = tx.commit_event(space.move_event(tx, w.id(who), w.id("storeroom"), None, 2.0, 1.0, at, None, 0))
        perception.compile_aftermath(tx, w.id("june"), [ev], at + 200, 0)
    return ev


def sweep(w, ev, at):
    with w.store.transaction() as tx:
        return cascade.sweep(tx, [ev], [r for r in w.canon.all("cascade") if r.id == "CAS-059"], at, 0)


def test_mara_walks_out_on_her(scenario):
    """June, bleeding from a deep cut, watches Mara — whom she loves — walk into the storeroom."""
    w = scenario("metal_fence")
    t = june_bleeding(w)
    trust = rel(w, "june", "mara")
    ev = walk_out(w, "mara", t)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "left_bleeding_by(trigger.event_id)", ev) == [w.id("june")]
    sweep(w, ev, t + 500)
    assert rel(w, "june", "mara") == max(-3, trust - 2)
    assert [g[1] for g in grudges(w, "june")] == [2]
    ev2 = walk_out(w, "mara", t + 60_000)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "left_bleeding_by(trigger.event_id)", ev2) == [], "not twice in an hour"


def test_owen_walks_out_on_her(scenario):
    """June has come to love Owen; he leaves her bleeding. What she feels is hers; nothing is written into Owen."""
    w = scenario("metal_fence")
    w.store.conn.execute("UPDATE relationships SET affection = 1 WHERE from_id = ? AND to_id = ?", (w.id("june"), w.id("pc")))
    t = june_bleeding(w)
    trust, owen = rel(w, "june", "pc"), rel(w, "pc", "june")
    sweep(w, walk_out(w, "pc", t), t + 500)
    assert rel(w, "june", "pc") == max(-3, trust - 2) and grudges(w, "june")
    assert rel(w, "pc", "june") == owen


@pytest.mark.parametrize("case", ["a_scratch", "no_love_lost", "out_cold"])
def test_nobody_left_behind(scenario, case):
    w = scenario("metal_fence")
    t = june_bleeding(w, WoundSeverity.MINOR if case == "a_scratch" else WoundSeverity.SEVERE)
    who = "alice" if case == "no_love_lost" else "mara"
    if case == "out_cold":
        w.store.conn.execute("UPDATE bodies SET awareness = 'unconscious' WHERE body_id = ?", (w.id("june"),))
    ev = walk_out(w, who, t)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "left_bleeding_by(trigger.event_id)", ev) == []
