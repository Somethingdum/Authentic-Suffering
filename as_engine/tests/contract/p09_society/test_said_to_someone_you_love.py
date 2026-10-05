"""Said to someone you love (D-262). mind/temper.py TEMPER-03 threatened_bonded, insulted_bonded; action/cascade.py
loved_ones_threatened_bare, loved_ones_insulted; core CAS-115, CAS-116, CAS-117.

The owner: "If I treat them like shit ... I do expect reactions, and proper ones." Hurt someone in front of the
people who love them and they hated you for it; hold a gun on them and it cost you. But call a woman's friend a
useless bitch to her face, or tell her you'll break her arm with nothing in your hand, and the woman beside her stood
there and felt nothing about you. Now it gets under her skin, and she holds it against you — once an hour, however
often it is said.
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception, temper
from as_engine.mind.temper import Provocation
from as_engine.physical import space

pytestmark = pytest.mark.phase(9)

RULES = ("CAS-115", "CAS-116", "CAS-117")


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def rel(w, a, b, axis):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def room(scenario):
    """The sales floor, lit; June brought out of the storeroom to stand by Owen. Mara loves her (affection 2);
    Alice, at the counter, is nothing to her."""
    w = scenario("metal_fence")
    pc = w.store.query_one("SELECT place_id, x_m, y_m FROM positions WHERE body_id=?", (w.id("pc"),))
    w.store.conn.execute("UPDATE positions SET place_id=?, anchor_id=NULL, x_m=?, y_m=? WHERE body_id=?",
                         (pc[0], (pc[1] or 0) + 1.0, pc[2] or 0, w.id("june")))
    w.store.conn.commit()
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", now(w), None, 0)
    return w


def heard(w, ev, at):
    """Each of them takes in the room (as every wave does) and what was said or done in it."""
    with w.store.transaction() as tx:
        for x in ("june", "mara", "alice", "pc"):
            perception.compile_scene(tx, w.id(x), at, 0)
            perception.compile_aftermath(tx, w.id(x), [ev], at + 500, 0)


def say(w, who, to, words, at, *, armed=False):
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id(who), at=at, turn_index=0,
                                   payload={"words": words, "volume": "normal", "to": [w.id(to)], "source_db": 60,
                                            "armed": armed}))
    heard(w, ev, at)
    return ev


def gesture(w, who, at_whom, kind, at):
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.GESTURE, writer="action.propagate", actor_id=w.id(who), at=at, turn_index=0,
                                   payload={"gesture": kind, "target_id": w.id(at_whom)}))
    heard(w, ev, at)
    return ev


def provoked(w, holder, at):
    with w.store.transaction() as tx:
        return temper.provocations(tx, w.id(holder), 0, at)


def chosen(w, fn, ev):
    with w.store.transaction() as tx:
        return cascade.select(tx, f"{fn}(trigger.event_id)", ev)


def sweep(w, ev, at):
    with w.store.transaction() as tx:
        return cascade.sweep(tx, [ev], [r for r in w.canon.all("cascade") if r.id in RULES], at, 0)


def test_her_friend_called_names_in_front_of_her(scenario):
    w = room(scenario)
    t = now(w)
    grudge = rel(w, "mara", "pc", "resentment")
    ev = say(w, "pc", "june", "June, you useless bitch.", t)
    assert provoked(w, "mara", t + 1000) == [Provocation(w.id("pc"), "insulted_bonded", ev.event_id)]
    assert provoked(w, "alice", t + 1000) == [], "June is nothing to Alice"
    assert chosen(w, "loved_ones_insulted", ev) == [w.id("mara")]
    assert [e.rule_cited for e in sweep(w, ev, t + 1000)] == ["CAS-116"]
    assert rel(w, "mara", "pc", "resentment") == min(3, grudge + 1)
    again = say(w, "pc", "june", "You heard me. Useless.", t + 60_000)
    assert chosen(w, "loved_ones_insulted", again) == [], "once an hour"


def test_her_friend_threatened_with_nothing_in_his_hand(scenario):
    w = room(scenario)
    t = now(w)
    trust, grudge = rel(w, "mara", "pc", "trust"), rel(w, "mara", "pc", "resentment")
    ev = say(w, "pc", "june", "June, I'll break your arm.", t)
    assert provoked(w, "mara", t + 1000) == [Provocation(w.id("pc"), "threatened_bonded", ev.event_id)]
    assert chosen(w, "loved_ones_threatened_bare", ev) == [w.id("mara")]
    assert sorted(e.rule_cited for e in sweep(w, ev, t + 1000)) == ["CAS-115", "CAS-115"]
    assert rel(w, "mara", "pc", "trust") == max(-3, trust - 1)
    assert rel(w, "mara", "pc", "resentment") == min(3, grudge + 1)
    with w.store.transaction() as tx:
        stress = tx.query_one("SELECT stress FROM actors WHERE actor_id=?", (w.id("mara"),))[0]
        temper.take_in(tx, w.rng, w.id("mara"), 0, t + 1000)
        assert tx.query_one("SELECT stress FROM actors WHERE actor_id=?", (w.id("mara"),))[0] == stress + 1
        assert temper.heat(tx, w.id("mara"), w.id("pc"), t + 1000) >= 3


def test_an_order_is_not_a_threat_unless_the_gun_is_on_her(scenario):
    """"Come here." to June angers Mara only said with a weapon in hand where Mara sees it — as June herself reads it
    (armed_at_me, WILL-10); and a threat at gunpoint is CAS-055's, not the bare-handed rule's."""
    w = room(scenario)
    t = now(w)
    say(w, "pc", "june", "June, come here.", t)
    assert provoked(w, "mara", t + 1000) == []
    order = say(w, "pc", "june", "June, come here.", t + 5000, armed=True)
    with w.store.transaction() as tx:
        d = tx.query_one("SELECT json_extract(detail,'$.armed_at_me') FROM percept_log WHERE event_id=? AND holder_id=? "
                         "AND channel='speech'", (order.event_id, w.id("june")))
    assert d is not None and d[0], "she sees the gun on her"
    assert provoked(w, "mara", t + 6000) == [Provocation(w.id("pc"), "threatened_bonded", order.event_id)]
    gun = say(w, "pc", "june", "Hand it over or I'll shoot you.", t + 10_000, armed=True)
    assert chosen(w, "loved_ones_threatened_bare", gun) == []
    assert chosen(w, "loved_ones_threatened", gun) == [w.id("mara")]


def test_spat_at_in_front_of_her(scenario):
    w = room(scenario)
    t = now(w)
    ev = gesture(w, "pc", "june", "spit_at", t)
    assert provoked(w, "mara", t + 1000) == [Provocation(w.id("pc"), "insulted_bonded", ev.event_id)]
    assert chosen(w, "loved_ones_insulted", ev) == [w.id("mara")]
    assert [e.rule_cited for e in sweep(w, ev, t + 1000)] == ["CAS-117"]


def test_never_the_player_character(scenario):
    """Alice calls Mara names in front of Owen; whatever he makes of it is his (C06) — and Mara, the one it was said
    to, has her own (TEMPER-03 insulted, D-219), not this."""
    w = room(scenario)
    t = now(w)
    w.store.conn.execute("INSERT OR REPLACE INTO relationships (from_id, to_id, kind, trust, affection, respect, fear, "
                         "resentment, updated_at) VALUES (?, ?, 'friend', 2, 3, 0, 0, 0, ?)", (w.id("pc"), w.id("mara"), t))
    w.store.conn.commit()
    ev = say(w, "alice", "mara", "Mara, you useless bitch.", t)
    assert w.id("pc") not in chosen(w, "loved_ones_insulted", ev)
    assert w.id("mara") not in chosen(w, "loved_ones_insulted", ev)
    assert [p.kind for p in provoked(w, "pc", t + 1000)] == ["insulted_bonded"], "his anger is real and on record"
