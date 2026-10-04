"""Eating the dead (D-133). Core affordance butcher_human (moral tag eat_human), action/effects.py butcher (a
person's body), core CAS-045..048, action/cascade.py selectors onlookers_of_act and onlookers_bonded_to_target,
world/rumours.py claim 'ate_the_dead'; CAS-022 now never written into the PC.

The owner: "If I treat them like shit, or do something just absolutely evil. I do expect reactions, and proper
ones." eat_human was always a line a person could refuse to cross (a dossier's wont_tags), and nothing in the
world let anyone cross it. Now a person's body can be cut for meat by anyone hungry or broken enough, and
whoever sees it trusts them less, fears them, is shaken and tells it; whoever loved the dead never forgives it;
the one who does it carries it.
"""

from __future__ import annotations

import pytest

import helpers
from as_engine.action import cascade
from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.physical import bodies, objects, space
from as_engine.physical.objects import Holder
from as_engine.world import rumours

pytestmark = pytest.mark.phase(9)

RULES = ("CAS-045", "CAS-046", "CAS-047")


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def rel(w, a, b, axis):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def actor_row(w, who, col):
    return w.store.query_one(f"SELECT {col} FROM actors WHERE actor_id = ?", (w.id(who),))[0]


def june_dead_on_the_floor(w):
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("sales_floor"), None, 3.2, 4.0, t, None, 0))
        bodies.kill(tx, w.id("june"), "blood_loss", t + 100, 0, w.rng)
        tx.commit_event(space.move_event(tx, w.id("alice"), w.id("sales_floor"), None, 3.0, 4.0, t + 200, None, 0))
        objects.transfer(tx, w.id("alice_ledger"), Holder("place", w.id("sales_floor"), None), None, t + 150, w.id("alice"), None, 0)
        objects.create(tx, "core:item/kitchen_knife", 1, Holder("body", w.id("alice"), "hand_r"), "scenario", {}, t + 200, None, 0)
    return t + 1000


def test_seen_loved_and_carried(scenario):
    """Alice cuts meat from June's body with Owen and Mara watching. Mara loved June."""
    w = scenario("metal_fence")
    t = june_dead_on_the_floor(w)
    trust, fear, stress = rel(w, "mara", "alice", "trust"), rel(w, "mara", "alice", "fear"), actor_row(w, "mara", "stress")
    a_stress, a_res = actor_row(w, "alice", "stress"), actor_row(w, "alice", "resolve_cur")
    owen = rel(w, "pc", "alice", "trust")
    it = helpers.make_intent(w, "alice", "butcher_human", target="june")
    with w.store.transaction() as tx:
        evs = resolve_wave(tx, helpers.ScriptedRng(), barrier(tx, [it]), t, 0, horizon_ms=t + 1000)
    ev = next(e for e in evs if e.type == EventType.ACTION_START)
    with w.store.transaction() as tx:
        for x in ("pc", "mara"):
            perception.compile_aftermath(tx, w.id(x), evs, t + 500, 0)
        assert cascade.select(tx, "onlookers_of_act(trigger.event_id)", ev) == [w.id("mara")], "never the PC (C06)"
        assert cascade.select(tx, "onlookers_bonded_to_target(trigger.event_id)", ev) == [w.id("mara")]
        cascade.sweep(tx, [ev], [r for r in w.canon.all("cascade") if r.id in RULES], t + 1000, 0)
    assert (rel(w, "mara", "alice", "trust"), rel(w, "mara", "alice", "fear")) == (max(-3, trust - 2), min(3, fear + 1))
    assert actor_row(w, "mara", "stress") == min(10, stress + 2)
    assert w.store.query("SELECT strength FROM open_loops WHERE holder_id = ? AND kind = 'grudge' AND text LIKE ?",
                         (w.id("mara"), "%cut meat from the body of someone you loved%"))[0][0] == 3
    assert w.store.query("SELECT 1 FROM rumours WHERE origin_holder = ?", (w.id("mara"),))
    assert rumours.CLAIM_TEXT["ate_the_dead"] == "{about} cut meat from a dead person's body."
    assert (actor_row(w, "alice", "stress"), actor_row(w, "alice", "resolve_cur")) == (min(10, a_stress + 2), max(0, a_res - 1))
    assert rel(w, "pc", "alice", "trust") == owen, "nothing written into Owen"


def test_the_body_gives_meat_like_any_other(scenario):
    w = scenario("metal_fence")
    t = june_dead_on_the_floor(w)
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id("alice"), t, 0)
        offered = {o.def_id: o for o in enumerate_affordances(tx, w.id("alice"), w.canon.all("affordance"), t, 0).options}
    assert "butcher_human" in offered, "anyone with a blade by a body may"
    mass = w.store.query_one("SELECT mass_kg FROM bodies WHERE body_id = ?", (w.id("june"),))[0]
    it = helpers.make_intent(w, "alice", "butcher_human", target="june")
    with w.store.transaction() as tx:
        resolve_wave(tx, helpers.ScriptedRng(), barrier(tx, [it]), t, 0, horizon_ms=t + 3_600_000)
    meat = w.store.query_one("SELECT qty FROM items WHERE def_ref = 'core:item/raw_meat'")
    assert meat is not None and meat[0] == max(1, mass // 10)


def test_cas_022_is_never_written_into_owen(scenario):
    """Shoving someone to the dead: those who saw it judge — never the player's character (C06)."""
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
    it = helpers.make_intent(w, "mara", "shove_toward_dead", target="alice")
    with w.store.transaction() as tx:
        evs = resolve_wave(tx, helpers.ScriptedRng(1, 10), barrier(tx, [it]), t, 0, horizon_ms=t + 1000)
    ev = next(e for e in evs if e.type == EventType.ACTION_START)
    with w.store.transaction() as tx:
        perception.compile_aftermath(tx, w.id("pc"), evs, t + 500, 0)
        assert w.id("pc") not in cascade.select(tx, "onlookers_of_act(trigger.event_id)", ev)
