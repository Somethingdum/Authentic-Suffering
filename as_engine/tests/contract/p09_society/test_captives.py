"""Captives (D-134). Computed moral tags torture and execute_prisoner (mind/affordance.py); action/cascade.py path
trigger.victim_held; core CAS-049..051; world/rumours.py claims 'beat_a_captive' and 'killed_a_captive'.

torture and execute_prisoner were always lines a dossier could draw, and nothing ever counted as crossing them.
Now hurting someone held — gripped or tied, unable to fight back or get away — is torture, and killing them is
executing a prisoner: off the menu of anyone whose card says never. Whoever sees a captive beaten trusts the one
doing it less, is shaken and tells it; whoever sees a captive killed is shaken and tells it — and trusts the killer
less even when the captive had been fighting before they were taken.
"""

from __future__ import annotations

import json

import pytest

from as_engine.action import cascade
from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec

pytestmark = pytest.mark.phase(9)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def rel(w, a, b, axis):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def stress(w, who):
    return w.store.query_one("SELECT stress FROM actors WHERE actor_id = ?", (w.id(who),))[0]


def setup(w):
    """Lights on; June on the floor; Alice holds Mara fast."""
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("sales_floor"), None, 4.0, 4.0, t, None, 0))
        bodies.grip_event(tx, w.id("alice"), w.id("mara"), t + 100, None, 0)
    return t + 1000


def blow(w, who, whom, at, severity=WoundSeverity.MINOR, anatomy=Anatomy.ARM_L, kill=False):
    with w.store.transaction() as tx:
        start = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0, actor_id=w.id(who),
                                      payload={"actor_id": w.id(who), "def_id": "punch", "verb": "attack", "target_id": w.id(whom)}))
        hurt = bodies.apply_harm(tx, w.id(whom), WoundSpec(anatomy, WoundType.BLUNT, severity), at + 300, start.event_id, 0, w.rng)
        harm = next(e for e in hurt if e.type == EventType.HARM)
        if kill and not any(e.type == EventType.DEATH for e in hurt):
            hurt.append(bodies.kill(tx, w.id(whom), "head_wound", at + 400, 0, w.rng, cause_event_id=harm.event_id))
        for x in ("pc", "alice", "june"):
            perception.compile_aftermath(tx, w.id(x), [start] + hurt, at + 800, 0)
    return harm, next((e for e in hurt if e.type == EventType.DEATH), None)


def sweep(w, evs, at, ids):
    with w.store.transaction() as tx:
        return cascade.sweep(tx, list(evs), [r for r in w.canon.all("cascade") if r.id in ids], at, 0)


def test_a_captive_beaten(scenario):
    w = scenario("metal_fence")
    t = setup(w)
    trust, s0 = rel(w, "june", "pc", "trust"), stress(w, "june")
    harm, _ = blow(w, "pc", "mara", t)
    with w.store.transaction() as tx:
        assert cascade.evaluate_precondition(tx, "trigger.victim_held == true", harm)
        assert cascade.select(tx, "assault_onlookers_of(trigger.event_id)", harm) == [w.id("alice"), w.id("june")]
    sweep(w, [harm], t + 1000, ("CAS-049",))
    assert (rel(w, "june", "pc", "trust"), stress(w, "june")) == (max(-3, trust - 1), min(10, s0 + 1))
    claims = [r[0] for r in w.store.query("SELECT p.predicate FROM rumours r JOIN propositions p ON p.prop_id = r.prop_id "
                                          "WHERE r.origin_holder = ?", (w.id("june"),))]
    assert "beat_a_captive" in claims


def test_a_captive_killed_after_a_fight_still_costs_the_killer(scenario):
    """Mara swung at Owen, was taken and held; then Owen killed her. CAS-025 asks whether she was fighting (she
    was); CAS-051 asks only whether she was held."""
    w = scenario("metal_fence")
    t = setup(w)
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=t - 500, turn_index=0, actor_id=w.id("mara"),
                              payload={"actor_id": w.id("mara"), "def_id": "punch", "verb": "attack", "target_id": w.id("pc")}))
    trust, s0 = rel(w, "june", "pc", "trust"), stress(w, "june")
    _harm, death = blow(w, "pc", "mara", t, WoundSeverity.CATASTROPHIC, Anatomy.HEAD, kill=True)
    with w.store.transaction() as tx:
        assert cascade.evaluate_precondition(tx, "trigger.killer_provoked == true", death)
        assert cascade.evaluate_precondition(tx, "trigger.victim_held == true", death)
    out = sweep(w, [death], t + 2000, ("CAS-025", "CAS-050", "CAS-051"))
    assert "CAS-025" not in {e.rule_cited for e in out}
    assert (rel(w, "june", "pc", "trust"), stress(w, "june")) == (max(-3, trust - 2), min(10, s0 + 1))
    assert "killed_a_captive" in [r[0] for r in w.store.query(
        "SELECT p.predicate FROM rumours r JOIN propositions p ON p.prop_id = r.prop_id WHERE r.origin_holder = ?", (w.id("june"),))]


def test_a_card_that_says_never_takes_it_off_the_menu(scenario):
    """June's card says she would never torture: with Mara held she is offered no blow at her; with Mara free she is."""
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("sales_floor"), None, 3.4, 3.0, t, None, 0))
        tx.commit_event(space.move_event(tx, w.id("mara"), w.id("sales_floor"), None, 3.8, 3.0, t, None, 0))
    row = w.store.query_one("SELECT dossier_id, baseline_json FROM actors a JOIN dossiers d USING (dossier_id) WHERE a.actor_id = ?",
                            (w.id("june"),))
    d = json.loads(row[1])
    d["motive"]["moral_line"]["wont_tags"] = ["torture"]
    w.store.conn.execute("UPDATE dossiers SET baseline_json = ? WHERE dossier_id = ?", (json.dumps(d), row[0]))

    def punch_mara(at):
        with w.store.transaction() as tx:
            perception.compile_scene(tx, w.id("june"), at, 0)
            a = enumerate_affordances(tx, w.id("june"), w.canon.all("affordance"), at, 0)
        offered = any(o.def_id == "punch" and o.target_id == w.id("mara") for o in a.options)
        refused = any(r.def_id == "punch" and r.target_id == w.id("mara") and r.gate == "moral" for r in a.rejected)
        return offered, refused
    assert punch_mara(t + 500) == (True, False)
    with w.store.transaction() as tx:
        bodies.grip_event(tx, w.id("alice"), w.id("mara"), t + 600, None, 0)
    assert punch_mara(t + 1000) == (False, True)
