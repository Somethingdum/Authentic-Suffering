"""Let them in (D-218). action/cascade.py trigger.let_in_by and saw_them_let_in; core CAS-105, CAS-106; world/rumours.py
claim 'let_the_dead_in'.

The owner: "If I treat them like shit, or do something just absolutely evil. I do expect reactions, and proper
ones." June opened the back door with one of the dead in the alley, and it walked in on Mara and Alice: nothing.
Now whoever saw who opened it, and has the dead among them, trusts that person less and holds it against them,
and the story travels. Someone let in by it, with the dead behind them, is a rescue.
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import space
from as_engine.world import infected

pytestmark = pytest.mark.phase(9)

EYES = ("mara", "alice", "pc")


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def rel(w, a, b, axis):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def stage(w):
    """The storeroom lit, Mara, Alice, June and Owen in it, the back door shut, one of the dead in the alley."""
    t = now(w)
    with w.store.transaction() as tx:
        for p in ("storeroom", "alley"):
            space.change_place(tx, w.id(p), {"light_level": 4}, "test", t, None, 0)
        for who, x in (("mara", 3.0), ("alice", 5.0), ("june", 4.0), ("pc", 2.0)):
            tx.commit_event(space.move_event(tx, w.id(who), w.id("storeroom"), None, x, 3.5, t, None, 0))
        tx.commit_event(space.move_event(tx, w.id("nita"), w.id("alley"), None, 6.0, 1.5, t, None, 0))
        tx.commit_event(space.portal_change_event(tx, w.id("back_door"), {"is_open": False}, t, None, None, 0))
        why = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=0, payload={"what": "test"}))
        dead = infected.spawn(tx, w.rng, w.id("alley"), "ZOMBIE_ARCHETYPE_SHAMBLER01", t, 0, why.event_id, x_m=8.0, y_m=1.0)
    return t + 1000, dead


def opens(w, who, at):
    with w.store.transaction() as tx:
        ev = tx.commit_event(space.portal_change_event(tx, w.id("back_door"), {"is_open": True}, at, w.id(who), None, 0))
        for x in EYES:
            perception.compile_aftermath(tx, w.id(x), [ev], at + 200, 0)
    return ev


def comes_in(w, body, at):
    with w.store.transaction() as tx:
        return tx.commit_event(space.move_event(tx, body, w.id("storeroom"), None, 4.0, 4.0, at, None, 0))


def sweep(w, ev, at):
    with w.store.transaction() as tx:
        return cascade.sweep(tx, [ev], [r for r in w.canon.all("cascade") if r.id == "CAS-105"], at, 0)


def test_june_lets_it_in(scenario):
    w = scenario("metal_fence")
    at, dead = stage(w)
    opens(w, "june", at)
    mv = comes_in(w, dead, at + 20_000)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "saw_them_let_in(trigger.event_id)", mv) == sorted([w.id("mara"), w.id("alice")]), \
            "never the one who opened it, never Owen (C06)"
    mara, alice = rel(w, "mara", "june", "trust"), rel(w, "alice", "june", "trust")
    sweep(w, mv, at + 21_000)
    assert rel(w, "mara", "june", "trust") == max(-3, mara - 2) and rel(w, "alice", "june", "trust") == max(-3, alice - 2)
    assert rel(w, "mara", "june", "resentment") >= 1
    claims = {r[0] for r in w.store.query("SELECT p.predicate FROM rumours r JOIN propositions p ON p.prop_id = r.prop_id "
                                          "WHERE r.origin_holder = ? AND p.subject_id = ?", (w.id("mara"), w.id("june")))}
    assert claims == {"let_the_dead_in"}
    with w.store.transaction() as tx:
        second = space.move_event(tx, dead, w.id("alley"), None, 6.0, 1.0, at + 30_000, None, 0)
        tx.commit_event(second)
    again = comes_in(w, dead, at + 40_000)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "saw_them_let_in(trigger.event_id)", again) == [], "the first of them through, once"


def test_owen_lets_it_in(scenario):
    """The player's character opening it is judged like anyone."""
    w = scenario("metal_fence")
    at, dead = stage(w)
    opens(w, "pc", at)
    mv = comes_in(w, dead, at + 20_000)
    with w.store.transaction() as tx:
        assert cascade.evaluate_precondition(tx, f"trigger.let_in_by == '{w.id('pc')}'", mv)
        assert w.id("june") not in cascade.select(tx, "saw_them_let_in(trigger.event_id)", mv), "June did not see it"


def test_letting_someone_in_is_a_rescue(scenario):
    """June opens it for Nita; Nita comes in with the dead behind her."""
    w = scenario("metal_fence")
    at, dead = stage(w)
    opens(w, "june", at)
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("nita"), w.id("storeroom"), None, 4.5, 4.0, at + 5_000, None, 0))
    mv = comes_in(w, dead, at + 20_000)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "saw_them_let_in(trigger.event_id)", mv) == []


def test_long_after_it_is_not_letting_in(scenario):
    w = scenario("metal_fence")
    at, dead = stage(w)
    opens(w, "june", at)
    mv = comes_in(w, dead, at + 6 * 60_000)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "saw_them_let_in(trigger.event_id)", mv) == []


def test_the_living_coming_in_is_nothing(scenario):
    w = scenario("metal_fence")
    at, _dead = stage(w)
    opens(w, "june", at)
    with w.store.transaction() as tx:
        mv = tx.commit_event(space.move_event(tx, w.id("nita"), w.id("storeroom"), None, 4.5, 4.0, at + 5_000, None, 0))
        assert cascade.select(tx, "saw_them_let_in(trigger.event_id)", mv) == []
