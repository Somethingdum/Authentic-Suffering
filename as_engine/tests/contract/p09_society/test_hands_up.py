"""Hands up (D-135). action/cascade.py path trigger.victim_yielded; core CAS-052..054; computed moral tag
execute_prisoner for killing someone this actor saw give up (mind/affordance.py); world/rumours.py claims
'hit_one_who_gave_up' and 'killed_one_who_gave_up'.

Someone who gave up — the surrender option, or holding up empty hands — and has not swung since is no fighter any
more. Hitting them is seen for what it is; killing them is killing a prisoner, even when they had been fighting
before they gave up; and a card that says never takes the killing blow off the menu. A surrender made in the same
instant as an attack is a feint, and one followed by an attack is over.
"""

from __future__ import annotations

import json

import pytest

from as_engine.action import cascade
from as_engine.action.effects import SEEN
from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.physical import bodies, objects, space
from as_engine.physical.bodies import WoundSpec
from as_engine.physical.objects import Holder

pytestmark = pytest.mark.phase(9)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def rel(w, a, b, axis):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def stress(w, who):
    return w.store.query_one("SELECT stress FROM actors WHERE actor_id = ?", (w.id(who),))[0]


def claims_of(w, who):
    return [r[0] for r in w.store.query("SELECT p.predicate FROM rumours r JOIN propositions p ON p.prop_id = r.prop_id "
                                        "WHERE r.origin_holder = ?", (w.id(who),))]


def lights_and_june(w):
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("sales_floor"), None, 4.0, 4.0, t, None, 0))
    return t + 10_000


def gesture(w, who, at):
    with w.store.transaction() as tx:
        return tx.commit_event(Event(type=EventType.GESTURE, writer="action.propagate", at=at, turn_index=0, actor_id=w.id(who),
                                     payload={"actor_id": w.id(who), "gesture": "empty_hands", "target_id": None}))


def start(w, who, verb, def_id, at, target=None):
    with w.store.transaction() as tx:
        return tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0, actor_id=w.id(who),
                                     payload={"actor_id": w.id(who), "def_id": def_id, "verb": verb, "visible": True,
                                              "seen": SEEN[def_id], "target_id": w.id(target) if target else None}))


def blow(w, who, whom, at, severity=WoundSeverity.MINOR, anatomy=Anatomy.ARM_L, kill=False):
    with w.store.transaction() as tx:
        st = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0, actor_id=w.id(who),
                                   payload={"actor_id": w.id(who), "def_id": "punch", "verb": "attack", "target_id": w.id(whom)}))
        hurt = bodies.apply_harm(tx, w.id(whom), WoundSpec(anatomy, WoundType.BLUNT, severity), at + 300, st.event_id, 0, w.rng)
        harm = next(e for e in hurt if e.type == EventType.HARM)
        if kill and not any(e.type == EventType.DEATH for e in hurt):
            hurt.append(bodies.kill(tx, w.id(whom), "head_wound", at + 400, 0, w.rng, cause_event_id=harm.event_id))
        for x in ("pc", "alice", "june"):
            perception.compile_aftermath(tx, w.id(x), [st] + hurt, at + 800, 0)
    return harm, next((e for e in hurt if e.type == EventType.DEATH), None)


def sweep(w, evs, at, ids):
    with w.store.transaction() as tx:
        return cascade.sweep(tx, list(evs), [r for r in w.canon.all("cascade") if r.id in ids], at, 0)


def test_hit_with_her_hands_up(scenario):
    w = scenario("metal_fence")
    t = lights_and_june(w)
    gesture(w, "mara", t - 3000)
    trust, s0 = rel(w, "june", "pc", "trust"), stress(w, "june")
    harm, _ = blow(w, "pc", "mara", t)
    with w.store.transaction() as tx:
        assert cascade.evaluate_precondition(tx, "trigger.victim_yielded == true and trigger.victim_held == false", harm)
    sweep(w, [harm], t + 1000, ("CAS-049", "CAS-052"))
    assert (rel(w, "june", "pc", "trust"), stress(w, "june")) == (max(-3, trust - 1), min(10, s0 + 1)), "answered once"
    assert "hit_one_who_gave_up" in claims_of(w, "june")


@pytest.mark.parametrize("case", ["feint", "swung_after", "long_ago"])
def test_a_surrender_that_does_not_stand(scenario, case):
    """A surrender in the same instant as an attack is a feint; one followed by an attack is over; one more than
    10 minutes before the blow is not this fight."""
    w = scenario("metal_fence")
    t = lights_and_june(w)
    if case == "feint":
        gesture(w, "mara", t - 2000)
        start(w, "mara", "attack", "punch", t - 2000, target="pc")
    elif case == "swung_after":
        gesture(w, "mara", t - 3000)
        start(w, "mara", "attack", "punch", t - 2000, target="pc")
    else:
        gesture(w, "mara", t - 700_000)
    harm, _ = blow(w, "pc", "mara", t)
    with w.store.transaction() as tx:
        assert not cascade.evaluate_precondition(tx, "trigger.victim_yielded == true", harm)
        assert cascade.evaluate_precondition(tx, "trigger.victim_yielded == false", harm)


def test_killed_after_giving_up(scenario):
    """Mara swung at Owen, then gave up (the surrender option); then Owen killed her. CAS-025 asks whether she was
    fighting (she was); CAS-054 asks whether she had given up."""
    w = scenario("metal_fence")
    t = lights_and_june(w)
    start(w, "mara", "attack", "punch", t - 5000, target="pc")
    start(w, "mara", "surrender", "surrender", t - 2000)
    trust, s0 = rel(w, "june", "pc", "trust"), stress(w, "june")
    _harm, death = blow(w, "pc", "mara", t, WoundSeverity.CATASTROPHIC, Anatomy.HEAD, kill=True)
    with w.store.transaction() as tx:
        assert cascade.evaluate_precondition(tx, "trigger.killer_provoked == true", death)
        assert cascade.evaluate_precondition(tx, "trigger.victim_yielded == true", death)
    out = sweep(w, [death], t + 2000, ("CAS-025", "CAS-050", "CAS-051", "CAS-053", "CAS-054"))
    assert {e.rule_cited for e in out} & {"CAS-025", "CAS-050", "CAS-051"} == set()
    assert (rel(w, "june", "pc", "trust"), stress(w, "june")) == (max(-3, trust - 2), min(10, s0 + 1))
    assert "killed_one_who_gave_up" in claims_of(w, "june")


def test_a_card_that_says_never_holds_the_blade(scenario):
    """Mara's card says she would never kill a prisoner. Knife in hand, Alice within reach: she may cut her down —
    until she sees Alice hold up empty hands; once Alice swings at her, she may again. Hitting her stays offered."""
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        tx.commit_event(space.move_event(tx, w.id("alice"), w.id("sales_floor"), None, 3.4, 3.0, t, None, 0))
        tx.commit_event(space.move_event(tx, w.id("mara"), w.id("sales_floor"), None, 3.8, 3.0, t, None, 0))
        objects.create(tx, "core:item/kitchen_knife", 1, Holder("body", w.id("mara"), "hand_r"), "scenario", {}, t, None, 0)
    row = w.store.query_one("SELECT dossier_id, baseline_json FROM actors a JOIN dossiers d USING (dossier_id) WHERE a.actor_id = ?",
                            (w.id("mara"),))
    d = json.loads(row[1])
    d["motive"]["moral_line"]["wont_tags"] = ["execute_prisoner"]
    w.store.conn.execute("UPDATE dossiers SET baseline_json = ? WHERE dossier_id = ?", (json.dumps(d), row[0]))

    def menu(at):
        with w.store.transaction() as tx:
            perception.compile_scene(tx, w.id("mara"), at, 0)
            a = enumerate_affordances(tx, w.id("mara"), w.canon.all("affordance"), at, 0)
        offered = {o.def_id for o in a.options if o.target_id == w.id("alice")}
        refused = {r.def_id for r in a.rejected if r.target_id == w.id("alice") and r.gate == "moral"
                   and "execute_prisoner" in r.detail}
        return "strike_melee" in offered, "strike_melee" in refused, "punch" in offered

    assert menu(t + 500) == (True, False, True)
    g = gesture(w, "alice", t + 600)
    with w.store.transaction() as tx:
        perception.compile_aftermath(tx, w.id("mara"), [g], t + 700, 0)
    assert menu(t + 1000) == (False, True, True)
    swing = start(w, "alice", "attack", "punch", t + 1200, target="mara")
    with w.store.transaction() as tx:
        perception.compile_aftermath(tx, w.id("mara"), [swing], t + 1300, 0)
    assert menu(t + 1500) == (True, False, True)
