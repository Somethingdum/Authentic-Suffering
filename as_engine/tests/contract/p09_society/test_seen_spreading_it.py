"""Seen spreading it (D-186). Core CAS-072 (spit_in_mouth seen), CAS-073 (spit_into seen); world/rumours.py claims
'spat_in_a_mouth' (with whom) and 'spoiled_the_food'.

The wet strain makes its host spit into sleepers' mouths and into what people eat and drink (W1, D-77) — code's act,
never a choice. Until now anyone who saw it happen shrugged it off: nothing changed for them, nobody told anyone, and
the mother of the boy it was done to held nothing against the one who did it.
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import bodies, space

pytestmark = pytest.mark.phase(9)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def rel(w, a, b, axis):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def lit_room(w):
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        for who, x in (("june", 7.0), ("mara", 3.0), ("eli", 5.0), ("alice", 5.5)):
            tx.commit_event(space.move_event(tx, w.id(who), w.id("sales_floor"), None, x, 4.0, t, None, 0))
        bodies.posture_event(tx, w.id("eli"), "lying", t, None, 0, awareness="asleep")
    return t + 1000


def act(w, who, def_id, at, *, target=None, item=None, seen=None):
    with w.store.transaction() as tx:
        st = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0, actor_id=w.id(who),
                                   payload={"actor_id": w.id(who), "def_id": def_id, "verb": "manipulate",
                                            "target_id": w.id(target) if target else None, "item_id": item,
                                            "visible": True, "seen": seen}))
        for x in ("june", "mara", "pc"):
            perception.compile_aftermath(tx, w.id(x), [st], at + 200, 0)
        cascade.sweep(tx, [st], [r for r in w.canon.all("cascade") if r.id in ("CAS-072", "CAS-073")], at + 500, 0)
    return st


def test_alice_spits_into_the_sleeping_boy_s_mouth(scenario):
    w = scenario("metal_fence")
    t = lit_room(w)
    trust, fear = rel(w, "june", "alice", "trust"), rel(w, "june", "alice", "fear")
    act(w, "alice", "spit_in_mouth", t, target="eli", seen="bends over {target}'s sleeping face")
    assert (rel(w, "june", "alice", "trust"), rel(w, "june", "alice", "fear")) == (max(-3, trust - 2), min(3, fear + 1))
    (text,) = [r[0] for r in w.store.query("SELECT p.text FROM rumours r JOIN percept_log p ON p.event_id = 'rumour:' || r.rumour_id "
                                           "WHERE r.origin_holder = ?", (w.id("june"),))]
    assert text == "Alice spat into the mouth of Eli while they slept."
    assert [tuple(r) for r in w.store.query("SELECT text, strength FROM open_loops WHERE holder_id = ? AND kind = 'grudge'",
                                            (w.id("mara"),))] == [("Alice spat into the mouth of Eli, someone you love, while they slept.", 3)]
    assert not w.store.query("SELECT 1 FROM rumours WHERE origin_holder = ?", (w.id("pc"),)), "never the player's character (C06)"


def test_alice_spits_into_the_water(scenario):
    w = scenario("metal_fence")
    t = lit_room(w)
    trust = rel(w, "june", "alice", "trust")
    act(w, "alice", "spit_into", t, seen="leans low over the water")
    assert rel(w, "june", "alice", "trust") == max(-3, trust - 2)
    claims = [r[0] for r in w.store.query("SELECT p.predicate FROM rumours r JOIN propositions p ON p.prop_id = r.prop_id "
                                          "WHERE r.origin_holder = ?", (w.id("june"),))]
    assert claims == ["spoiled_the_food"]
