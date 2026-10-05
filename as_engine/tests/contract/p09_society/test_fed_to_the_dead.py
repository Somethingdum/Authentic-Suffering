"""Fed to the dead (D-214). action/cascade.py trigger.attacker, trigger.killer (a HARM or DEATH by the dead after a
shove to them), onlookers_of / assault_onlookers_of (judged when it was done), CAS-088.

The owner: "If I treat them like shit, or do something just absolutely evil. I do expect reactions, and proper
ones." Ray shoving Cal into the dead's reach cost him a little trust with whoever saw it and a story (CAS-022) —
and when it bit Cal, and when Cal died of it, nobody had done anything: the dead have no name to hold it against.
June, who loves Cal, felt what a stranger across the road felt. Now the bite that follows the shove and the death
that follows the bite are Ray's, and June does not forgive the shove itself.

A street at noon (as test_betrayal): Ray a step from Cal, June watching from the kerb, Nita across the road, and
one of the dead four metres past Cal.
"""

from __future__ import annotations

import copy

import pytest

import helpers
from as_engine.action import cascade
from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import bodies
from as_engine.physical.bodies import WoundSpec
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(9)

STREET = {
    "schema": "as.scenario.v1", "name": "the_street", "seed": 61, "start": {"day": 300, "time": "12:00"},
    "places": [{"id": "street", "name": "Main Street", "kind": "outdoor", "indoor": False, "material": "open_air",
                "light": 3, "width_m": 40, "depth_m": 20,
                "anchors": [{"id": "far_corner", "name": "far corner", "x": 38, "y": 18}]}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "street", "x": 36, "y": 3},
        {"id": "ray", "dossier": "core:actor/ray_delgado", "place": "street", "x": 9.5, "y": 10},
        {"id": "cal", "stub": {"name": "Cal Hobbs", "age": 30, "sex": "male"}, "place": "street", "x": 10, "y": 10},
        {"id": "june", "dossier": "core:actor/june_okafor", "place": "street", "x": 8, "y": 13},
        {"id": "nita", "dossier": "core:actor/nita_reyes", "place": "street", "x": 10, "y": 2},
        {"id": "dead", "infected": "ZOMBIE_ARCHETYPE_SHAMBLER01", "controller": "policy", "place": "street", "x": 14, "y": 10},
    ],
    "relationships": [{"from": "june", "to": "cal", "kind": "friend", "trust": 2, "affection": 2}],
    "knows": [{"holder": h, "subject": s, "name": n} for h in ("june", "nita", "cal")
              for s, n in (("ray", "Ray"), ("cal", "Cal")) if h != s],
}

SHOVE, BITE, DEATH = ["CAS-022", "CAS-023", "CAS-088"], ["CAS-036", "CAS-037", "CAS-040"], ["CAS-025", "CAS-026", "CAS-041"]


@pytest.fixture
def street(fixture_packs, core_pack_dir):
    w = load_scenario(copy.deepcopy(STREET), packs_root=fixture_packs, core_pack_dir=core_pack_dir)
    yield w
    w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def rel(w, a, b, axis):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def loops(w, who):
    return [r[0] for r in w.store.query("SELECT text FROM open_loops WHERE holder_id = ? AND status = 'open'", (w.id(who),))]


def sweep(w, ev, ids, at):
    with w.store.transaction() as tx:
        return cascade.sweep(tx, [ev], [r for r in w.canon.all("cascade") if r.id in ids], at, 0)


def seen(w, evs, at):
    with w.store.transaction() as tx:
        for who in ("june", "nita"):
            perception.compile_aftermath(tx, w.id(who), evs, at, 0)


def shove(w, t):
    """Ray wins the shove (d10 1 against 10): Cal goes down two metres from the dead."""
    i = helpers.make_intent(w, "ray", "shove_toward_dead", target="cal")
    with w.store.transaction() as tx:
        evs = resolve_wave(tx, helpers.ScriptedRng(1, 10), barrier(tx, [i]), t, 0, horizon_ms=t + 600_000)
    assert next(e for e in evs if e.type == EventType.ACTION_COMPLETE).payload["result"] == "shoved_to_the_dead"
    seen(w, evs, t + 1500)
    return next(e for e in evs if e.type == EventType.ACTION_START and e.actor_id == w.id("ray"))


def bite(w, at, severity="significant"):
    """The dead one bites Cal — its own act; the HARM carries no actor (physical.bodies.apply_harm)."""
    with w.store.transaction() as tx:
        st = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0,
                                   actor_id=w.id("dead"), payload={"actor_id": w.id("dead"), "def_id": "infected_bite",
                                                                    "verb": "attack", "target_id": w.id("cal")}))
        hurt = bodies.apply_harm(tx, w.id("cal"), WoundSpec("arm_l", "bite", severity, 3), at, st.event_id, 0, w.rng)
    seen(w, [st, *hurt], at + 500)
    harm = next(e for e in hurt if e.type == EventType.HARM)
    assert harm.payload["actor_id"] is None
    return harm


def dies(w, harm, at):
    with w.store.transaction() as tx:
        death = bodies.kill(tx, w.id("cal"), "blood_loss", at, 0, w.rng, cause_event_id=harm.event_id)
    seen(w, [death], at + 500)
    return death


def test_june_does_not_forgive_the_shove(street):
    w = street
    t = now(w)
    june, nita = rel(w, "june", "ray", "trust"), rel(w, "nita", "ray", "trust")
    start = shove(w, t)
    sweep(w, start, SHOVE, t + 2000)
    assert rel(w, "june", "ray", "trust") == max(-3, june - 3), "a stranger's -2, and -1 more: it was Cal"
    assert rel(w, "nita", "ray", "trust") == max(-3, nita - 2), "Nita judges it as anyone would (CAS-022)"
    assert rel(w, "june", "ray", "resentment") >= 2
    assert any("someone you love, to the dead" in x and "Cal" in x for x in loops(w, "june")), loops(w, "june")
    assert not any("someone you love" in x for x in loops(w, "nita"))
    assert not loops(w, "pc"), "never the player's character (C06)"


def test_the_bite_is_the_shovers(street):
    w = street
    t = now(w)
    shove(w, t)
    harm = bite(w, t + 30_000)
    with w.store.transaction() as tx:
        assert cascade.evaluate_precondition(tx, "trigger.attacker_provoked == false", harm)
        judged = cascade.select(tx, "assault_onlookers_of(trigger.event_id)", harm)
        hurt = cascade.select(tx, "hurt_by_someone(trigger.event_id)", harm)
        bonded = cascade.select(tx, "bonded_onlookers_of(trigger.event_id)", harm)
    assert {w.id("june"), w.id("nita")} <= set(judged) and w.id("pc") not in judged, \
        "they saw the dead bite him — after the shove: not knowing he carried it (D-202), they saw it done"
    assert hurt == [w.id("cal")] and bonded == [w.id("june")]
    sweep(w, harm, BITE, t + 32_000)
    assert any("Ray" in x and "hurt Cal" in x for x in loops(w, "june")), loops(w, "june")
    assert any("Ray" in x and "hurt you" in x for x in loops(w, "cal")), loops(w, "cal")
    second = bite(w, t + 40_000, "severe")
    with w.store.transaction() as tx:
        assert not cascade.select(tx, "hurt_by_someone(trigger.event_id)", second), "the first bite is his; the feeding is the dead's"


def test_his_death_is_the_shovers(street):
    w = street
    t = now(w)
    shove(w, t)
    bite(w, t + 30_000)
    last = bite(w, t + 150_000, "severe")
    strain = w.store.query_one("SELECT stress FROM actors WHERE actor_id = ?", (w.id("ray"),))[0]
    death = dies(w, last, t + 180_000)
    with w.store.transaction() as tx:
        assert cascade.evaluate_precondition(tx, "trigger.killer_provoked == false", death)
        judged = cascade.select(tx, "onlookers_of(trigger.event_id)", death)
    assert {w.id("june"), w.id("nita")} <= set(judged)
    sweep(w, death, DEATH, t + 182_000)
    assert any("killed Cal, someone you loved" in x and "Ray" in x for x in loops(w, "june")), loops(w, "june")
    assert any("killed someone in front of you" in x for x in loops(w, "nita")), loops(w, "nita")
    assert w.store.query_one("SELECT stress FROM actors WHERE actor_id = ?", (w.id("ray"),))[0] > strain, "he carries it (CAS-026)"
    told = [r[0] for r in w.store.query("SELECT p.predicate FROM rumours r JOIN propositions p ON p.prop_id = r.prop_id "
                                        "WHERE r.origin_holder = ?", (w.id("nita"),))]
    assert "killed_someone" in told, told


def test_the_dead_alone_are_nobodys(street):
    """Bitten three minutes after the shove — he got clear, or nobody shoved him: the dead have no name."""
    w = street
    t = now(w)
    shove(w, t)
    harm = bite(w, t + 180_000)
    death = dies(w, harm, t + 200_000)
    with w.store.transaction() as tx:
        assert not cascade.select(tx, "hurt_by_someone(trigger.event_id)", harm)
        assert not cascade.evaluate_precondition(tx, "trigger.killer_provoked == false", death), "no killer"
