"""Kindness is remembered (D-195). Core CAS-076 (a gift), CAS-077 (wounds tended); action/cascade.py selectors
given_to and cared_for_by.

Everything cruel left a mark on the people it was done to (D-126, D-129, D-194); nothing kind did. Owen could share
his last food with a starving woman, or kneel in the blood and bandage a man's leg while he watched, and only the
memory model — when it was asked, if it noticed — might write that it mattered. Now a gift earns a little trust and
tended wounds earn trust, warmth and a debt the one tended carries. A day's gifts or a day's care count once; the
one tended has to be awake to know who did it; and nothing is written into the player's character (C06).
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.physical import bodies, objects
from as_engine.physical.bodies import WoundSpec
from as_engine.physical.objects import Holder

pytestmark = pytest.mark.phase(9)

DAY = 86_400_000


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def rel(w, a, b, axis):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def rules(w, rid):
    return [r for r in w.canon.all("cascade") if r.id == rid]


def give(w, giver, to, at):
    with w.store.transaction() as tx:
        made = objects.create(tx, "core:item/jerky_pack", 1, Holder("body", w.id(giver), "pocket"), "scenario", {}, at, None, 0)
        item = made.payload["item_id"]
        ev = objects.transfer(tx, item, Holder("body", w.id(to), "pocket"), None, at, w.id(giver), None, 0)
        cascade.sweep(tx, [ev], rules(w, "CAS-076"), at + 100, 0)
    return ev


def wound(w, who, at):
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=at, turn_index=0, payload={"what": "test"}))
        hurt = bodies.apply_harm(tx, w.id(who), WoundSpec(Anatomy.LEG_L, WoundType.CUT, WoundSeverity.SIGNIFICANT), at,
                                 c.event_id, 0, w.rng)
    return next(e for e in hurt if e.type == EventType.HARM).payload["wound_id"]


def tend(w, by, who, wid, method, at):
    with w.store.transaction() as tx:
        ev = bodies.treat(tx, w.id(who), wid, method, w.id(by), at, None, 0)
        cascade.sweep(tx, [ev], rules(w, "CAS-077"), at + 100, 0)
    return ev


def test_a_gift(scenario):
    w = scenario("metal_fence")
    t = now(w)
    trust = rel(w, "mara", "pc", "trust")
    give(w, "pc", "mara", t)
    assert rel(w, "mara", "pc", "trust") == min(3, trust + 1)
    give(w, "pc", "mara", t + 60_000)
    assert rel(w, "mara", "pc", "trust") == min(3, trust + 1), "a day's gifts count once"
    give(w, "pc", "mara", t + DAY)
    assert rel(w, "mara", "pc", "trust") == min(3, trust + 2), "and the next day's again"


def test_a_gift_to_the_player_s_character_writes_nothing_into_him(scenario):
    w = scenario("metal_fence")
    t = now(w)
    before = rel(w, "pc", "mara", "trust")
    give(w, "mara", "pc", t)
    assert rel(w, "pc", "mara", "trust") == before


def test_taking_is_not_a_gift(scenario):
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        item = objects.create(tx, "core:item/jerky_pack", 1, Holder("body", w.id("mara"), "pocket"), "scenario", {}, t, None, 0
                              ).payload["item_id"]
        ev = objects.transfer(tx, item, Holder("body", w.id("pc"), "pocket"), None, t, w.id("pc"), None, 0)
        assert cascade.select(tx, "given_to(trigger.event_id)", ev) == []


def awake(w, who, at):
    with w.store.transaction() as tx:
        bodies.posture_event(tx, w.id(who), "sitting", at, None, 0, awareness="awake")


def test_hands_that_tend_you(scenario):
    w = scenario("metal_fence")
    t = now(w)
    awake(w, "alice", t)
    w.store.conn.execute("DELETE FROM relationships WHERE from_id = ? AND to_id = ?", (w.id("alice"), w.id("june")))
    wid = wound(w, "alice", t)
    tend(w, "june", "alice", wid, "pressure", t + 1000)
    assert (rel(w, "alice", "june", "trust"), rel(w, "alice", "june", "affection")) == (1, 1)
    loops = [tuple(r) for r in w.store.query("SELECT kind, text, strength FROM open_loops WHERE holder_id = ? AND status = 'open' "
                                             "AND kind = 'debt_owing'", (w.id("alice"),))]
    assert loops == [("debt_owing", "June tended your wounds. You owe them.", 2)]
    tend(w, "june", "alice", wid, "bandage", t + 2000)
    assert rel(w, "alice", "june", "trust") == 1, "the day's care counts once"
    tend(w, "june", "alice", wid, "clean", t + DAY)
    assert rel(w, "alice", "june", "trust") == 2, "the next day's again"
    assert loops_of(w, "alice") == [("debt_owing", "June tended your wounds. You owe them.", 3)], "and the debt deepens (D-194)"


def loops_of(w, who):
    return [tuple(r) for r in w.store.query("SELECT kind, text, strength FROM open_loops WHERE holder_id = ? AND status = 'open' "
                                            "AND kind = 'debt_owing'", (w.id(who),))]


def test_asleep_she_never_knew_who(scenario):
    w = scenario("metal_fence")
    t = now(w)
    wid = wound(w, "alice", t)
    with w.store.transaction() as tx:
        bodies.posture_event(tx, w.id("alice"), "lying", t + 500, None, 0, awareness="asleep")
    w.store.conn.execute("DELETE FROM relationships WHERE from_id = ? AND to_id = ?", (w.id("alice"), w.id("june")))
    tend(w, "june", "alice", wid, "bandage", t + 1000)
    assert rel(w, "alice", "june", "trust") == 0 and loops_of(w, "alice") == []
    with w.store.transaction() as tx:
        ev = bodies.treat(tx, w.id("alice"), wid, "clean", w.id("alice"), t + 2000, None, 0)
        assert cascade.select(tx, "cared_for_by(trigger.event_id)", ev) == [], "tending yourself is no kindness owed"
