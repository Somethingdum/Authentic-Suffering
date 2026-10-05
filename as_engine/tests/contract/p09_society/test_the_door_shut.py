"""The door shut on them (D-163). action/cascade.py selectors shut_out_by and saw_them_shut_out; core CAS-069/070;
world/rumours.py claim 'shut_someone_out'.

Mara's own secret is a door she kept shut on a begging neighbour. In the game, shutting a door on someone with the
dead on their side of it cost nothing: not with them, not with anyone who loved them and watched it done.
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import space
from as_engine.world import infected

pytestmark = pytest.mark.phase(9)

EARS = ("nita", "mara", "alice", "june")


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def rel(w, a, b, axis):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def stage(w, *, dead=True):
    t = now(w)
    with w.store.transaction() as tx:
        for p in ("storeroom", "alley"):
            space.change_place(tx, w.id(p), {"light_level": 4}, "test", t, None, 0)
        for who, x in (("mara", 3.0), ("alice", 5.0)):
            tx.commit_event(space.move_event(tx, w.id(who), w.id("storeroom"), None, x, 3.0, t, None, 0))
        tx.commit_event(space.move_event(tx, w.id("nita"), w.id("alley"), None, 6.0, 1.5, t, None, 0))
        if dead:
            why = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=0, payload={"what": "test"}))
            infected.spawn(tx, w.rng, w.id("alley"), "ZOMBIE_ARCHETYPE_SHAMBLER01", t, 0, why.event_id, x_m=10.0, y_m=3.0)
    w.store.conn.execute("UPDATE relationships SET affection = 1 WHERE from_id = ? AND to_id = ?", (w.id("mara"), w.id("nita")))
    return t + 1000


def shut(w, at, changes=None):
    with w.store.transaction() as tx:
        ev = tx.commit_event(space.portal_change_event(tx, w.id("back_door"), changes or {"is_open": False}, at, w.id("june"), None, 0))
        for x in EARS:
            perception.compile_aftermath(tx, w.id(x), [ev], at + 200, 0)
    return ev


def sweep(w, ev, at):
    with w.store.transaction() as tx:
        return cascade.sweep(tx, [ev], [r for r in w.canon.all("cascade") if r.id in ("CAS-069", "CAS-070")], at, 0)


def test_june_shuts_nita_out(scenario):
    w = scenario("metal_fence")
    at = stage(w)
    ev = shut(w, at)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "shut_out_by(trigger.event_id)", ev) == [w.id("nita")]
        assert cascade.select(tx, "saw_them_shut_out(trigger.event_id)", ev) == [w.id("mara")], "Alice does not love her"
    nita, mara = rel(w, "nita", "june", "trust"), rel(w, "mara", "june", "trust")
    sweep(w, ev, at + 1000)
    assert (rel(w, "nita", "june", "trust"), rel(w, "nita", "june", "resentment")) == (max(-3, nita - 2), 2)
    assert [tuple(r) for r in w.store.query("SELECT text, strength FROM open_loops WHERE holder_id = ? AND kind = 'grudge'",
                                            (w.id("nita"),))] == [("June shut the door on you and left you out there.", 3)]
    assert (rel(w, "mara", "june", "trust"), rel(w, "mara", "june", "resentment")) == (max(-3, mara - 1), 1)
    claims = [r[0] for r in w.store.query("SELECT p.predicate FROM rumours r JOIN propositions p ON p.prop_id = r.prop_id "
                                          "WHERE r.origin_holder = ?", (w.id("mara"),))]
    assert claims == ["shut_someone_out"]
    lock = shut(w, at + 3000, {"is_locked": True})
    with w.store.transaction() as tx:
        assert cascade.select(tx, "shut_out_by(trigger.event_id)", lock) == [], "locking it after is the same act"


def test_no_danger_no_wrong(scenario):
    w = scenario("metal_fence")
    at = stage(w, dead=False)
    ev = shut(w, at)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "shut_out_by(trigger.event_id)", ev) == []
