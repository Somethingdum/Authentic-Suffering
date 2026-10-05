"""What is done to you and yours lasts (D-129). Rules CAS-039..044 (core cascade/people.yaml); action/cascade.py
selectors robbed_by, bonded_onlookers_of, humiliated_by and made_to_watch; turn/cognition.py record_responses
(doing it at the point of a threat).

The owner: "If I treat them like shit, or do something just absolutely evil. I do expect reactions, and
proper ones." A theft, an insult or a loved one hurt made a person angry (TEMPER-03), and anger fades by the
hour. Now seeing what is yours taken costs the taker your trust and leaves a grudge; seeing someone you love
hurt or killed is not forgiven; being shamed in front of others wears you down; being held and made to watch
breaks something; doing what you were told at the point of a threat costs you, and you resent who made you.
Nothing about how the player's character feels is written (C06) — only what being made to watch costs.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

import helpers
from as_engine.action import cascade
from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.physical import bodies, objects, space
from as_engine.physical.bodies import WoundSpec
from as_engine.physical.objects import Holder
from as_engine.testing.scenario import load_scenario
from as_engine.turn import cognition

pytestmark = pytest.mark.phase(9)

FENCE = yaml.safe_load((Path(__file__).resolve().parents[2] / "fixtures" / "scenarios" / "metal_fence.yaml").read_text())
SEEN = ("pc", "mara", "alice", "june")


@pytest.fixture
def store_floor(fixture_packs, core_pack_dir):
    """The metal fence world with June on the sales floor; Alice and Mara know the ledger in Alice's hand is
    hers, and Owen knows his Glock is his."""
    worlds = []

    def _load():
        spec = copy.deepcopy(FENCE)
        for b in spec["bodies"]:
            if b["id"] == "june":
                b["place"], b["anchor"] = "sales_floor", "counter"
                b.pop("task", None)
        spec["beliefs"] = spec.get("beliefs", []) + [
            {"holder": "alice", "subject_type": "object", "subject": "alice_ledger", "predicate": "owner", "value": "alice",
             "text": "The ledger is mine.", "confidence": 3, "provenance": "witnessed"},
            {"holder": "mara", "subject_type": "object", "subject": "alice_ledger", "predicate": "owner", "value": "alice",
             "text": "That ledger is Alice's.", "confidence": 3, "provenance": "witnessed"},
            {"holder": "pc", "subject_type": "object", "subject": "glock", "predicate": "owner", "value": "pc",
             "text": "The Glock is mine.", "confidence": 3, "provenance": "witnessed"}]
        w = load_scenario(spec, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        with w.store.transaction() as tx:
            space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", now(w), None, 0)
        return w
    yield _load
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def rel(w, a, b, axis):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def resolve(w, who):
    return w.store.query_one("SELECT resolve_cur FROM actors WHERE actor_id = ?", (w.id(who),))[0]


def grudges(w, who, text):
    return w.store.query("SELECT strength FROM open_loops WHERE holder_id = ? AND kind = 'grudge' AND text LIKE ?",
                         (w.id(who), f"%{text}%"))


def sweep(w, evs, at, ids):
    with w.store.transaction() as tx:
        return cascade.sweep(tx, list(evs), [r for r in w.canon.all("cascade") if r.id in ids], at, 0)


def perceive(w, tx, evs, at, who=SEEN):
    for x in who:
        perception.compile_aftermath(tx, w.id(x), list(evs), at, 0)


def take(w, taker, item, at):
    with w.store.transaction() as tx:
        ev = objects.transfer(tx, w.id(item), Holder("body", w.id(taker), "hand_l"), None, at, w.id(taker), None, 0)
        perceive(w, tx, [ev], at + 500)
    return ev


def hit(w, who, whom, at, severity=WoundSeverity.MINOR):
    with w.store.transaction() as tx:
        start = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0, actor_id=w.id(who),
                                      payload={"actor_id": w.id(who), "def_id": "punch", "verb": "attack", "target_id": w.id(whom)}))
        hurt = bodies.apply_harm(tx, w.id(whom), WoundSpec(Anatomy.ARM_L, WoundType.BLUNT, severity), at + 300, start.event_id, 0, w.rng)
        perceive(w, tx, [start] + hurt, at + 800)
    return next(e for e in hurt if e.type == EventType.HARM)


def kill(w, who, whom, at):
    with w.store.transaction() as tx:
        start = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0, actor_id=w.id(who),
                                      payload={"actor_id": w.id(who), "def_id": "strike_melee", "verb": "attack",
                                               "target_id": w.id(whom)}))
        hurt = bodies.apply_harm(tx, w.id(whom), WoundSpec(Anatomy.NECK, WoundType.CUT, WoundSeverity.CATASTROPHIC), at + 500,
                                 start.event_id, 0, w.rng)
        death = [e for e in hurt if e.type == EventType.DEATH]
        if not death:
            harm = next(e for e in hurt if e.type == EventType.HARM)
            death = [bodies.kill(tx, w.id(whom), "blood_loss", at + 1000, 0, w.rng, cause_event_id=harm.event_id)]
        perceive(w, tx, [start] + hurt + death, at + 1500, who=[x for x in SEEN if x != whom])
    return death[-1]


def say(w, who, words, to, at, heard_by):
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id(who), at=at, turn_index=0,
                                   payload={"words": words, "volume": "normal", "to": [w.id(to)], "source_db": 60, "armed": False}))
        perceive(w, tx, [ev], at + 500, who=heard_by)
    return ev


def test_seeing_what_is_yours_taken(store_floor):
    """Owen takes Alice's ledger out of her hand: she trusts him 2 less, resents him and holds it against
    him; Mara, who knows whose it is, is a witness (CAS-012), not the one robbed. Alice taking Owen's Glock
    writes nothing into Owen."""
    w = store_floor()
    t = now(w)
    trust = rel(w, "alice", "pc", "trust")
    ev = take(w, "pc", "alice_ledger", t)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "robbed_by(trigger.event_id)", ev) == [w.id("alice")]
    out = sweep(w, [ev], t + 1000, ("CAS-039",))
    assert {e.rule_cited for e in out} == {"CAS-039"}
    assert (rel(w, "alice", "pc", "trust"), rel(w, "alice", "pc", "resentment")) == (max(-3, trust - 2), 1)
    assert grudges(w, "alice", "took what was yours") and not grudges(w, "mara", "took what was yours")
    ev2 = take(w, "alice", "glock", t + 5000)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "robbed_by(trigger.event_id)", ev2) == []


def test_hurt_someone_she_loves_and_it_is_not_forgiven(store_floor):
    """Owen hits June for nothing. Mara loves June: she trusts him 2 less in all (CAS-037 and CAS-040) and
    holds it; Alice, who saw it too, only 1 less."""
    w = store_floor()
    t = now(w)
    mara, alice = rel(w, "mara", "pc", "trust"), rel(w, "alice", "pc", "trust")
    ev = hit(w, "pc", "june", t)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "bonded_onlookers_of(trigger.event_id)", ev) == [w.id("mara")]
    sweep(w, [ev], t + 1000, ("CAS-037", "CAS-040"))
    assert rel(w, "mara", "pc", "trust") == max(-3, mara - 2) and rel(w, "alice", "pc", "trust") == max(-3, alice - 1)
    assert grudges(w, "mara", "hurt June, someone you love") and not grudges(w, "alice", "someone you love")   # D-179: who


def test_killed_someone_she_loved(store_floor):
    w = store_floor()
    t = now(w)
    death = kill(w, "pc", "june", t)
    sweep(w, [death], t + 2000, ("CAS-041",))
    assert [r[0] for r in grudges(w, "mara", "killed June, someone you loved")] == [3]   # D-179: who
    assert not grudges(w, "alice", "someone you loved")


def test_shamed_in_front_of_others(store_floor):
    """Owen calls Alice useless in front of Mara: it wears her down and she resents him — once an hour, however
    often he does it. Said where nobody else hears, it is only an insult (her temper has it). Mara calling
    Owen useless in front of Alice writes nothing into Owen."""
    w = store_floor()
    t = now(w)
    r0 = resolve(w, "alice")
    alone = say(w, "pc", "You're useless.", "alice", t, ["alice"])
    with w.store.transaction() as tx:
        assert cascade.select(tx, "humiliated_by(trigger.event_id)", alone) == []
    ev = say(w, "pc", "Shut up. You're useless.", "alice", t + 5000, ["alice", "mara"])
    sweep(w, [ev], t + 6000, ("CAS-042",))
    assert (resolve(w, "alice"), rel(w, "alice", "pc", "resentment")) == (max(0, r0 - 1), 1)
    again = say(w, "pc", "Useless.", "alice", t + 60_000, ["alice", "mara"])
    assert sweep(w, [again], t + 61_000, ("CAS-042",)) == [] and resolve(w, "alice") == max(0, r0 - 1)
    back = say(w, "mara", "You're useless, Owen.", "pc", t + 70_000, ["pc", "alice"])
    with w.store.transaction() as tx:
        assert cascade.select(tx, "humiliated_by(trigger.event_id)", back) == []


def test_held_and_made_to_watch(store_floor):
    """Mara and Alice are held. Owen beats June: Mara, who loves her, loses 2 Resolve; again a minute later,
    nothing more this hour. Alice, held too, does not love June: nothing."""
    w = store_floor()
    t = now(w)
    w.store.conn.execute("UPDATE bodies SET restrained = 1 WHERE body_id IN (?, ?)", (w.id("mara"), w.id("alice")))
    w.store.conn.execute("UPDATE actors SET resolve_cur = 5 WHERE actor_id IN (?, ?)", (w.id("mara"), w.id("alice")))
    ev = hit(w, "pc", "june", t)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "made_to_watch(trigger.event_id)", ev) == [w.id("mara")]
    sweep(w, [ev], t + 1000, ("CAS-043",))
    assert (resolve(w, "mara"), resolve(w, "alice")) == (3, 5)
    ev2 = hit(w, "pc", "june", t + 60_000)
    sweep(w, [ev2], t + 61_000, ("CAS-043",))
    assert resolve(w, "mara") == 3


def test_done_at_the_point_of_a_threat(store_floor):
    """Owen, Glock in hand: "Hand me the ledger or I'll shoot you." Alice does it. It costs her a point of
    Resolve and she resents him. Asked plainly, nothing of the kind."""
    w = store_floor()
    alice = w.id("alice")

    def ask(words, at):
        with w.store.transaction() as tx:
            ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=at, turn_index=0, actor_id=w.id("pc"),
                                       payload={"words": words, "volume": "normal", "to": [alice], "source_db": 60, "armed": True}))
            perception.compile_aftermath(tx, alice, [ev], at + 300, 0)
            asks = {alice: cognition.asks_for(tx, alice, 0, set())}
            affs = {alice: enumerate_affordances(tx, alice, w.canon.all("affordance"), at + 500, 0)}
        it = helpers.make_intent(w, "alice", "give_item", target="pc", item="alice_ledger")
        with w.store.transaction() as tx:
            first = tx.query_one("SELECT COALESCE(MAX(seq), 0) FROM events")[0]
            resolve_wave(tx, helpers.ScriptedRng(), barrier(tx, [it]), at + 500, 0, horizon_ms=at + 20_000)
            return cognition.record_responses(tx, {alice: it}, affs, asks, 0, at + 500, first)
    t = now(w)
    w.store.conn.execute("UPDATE actors SET resolve_cur = 4 WHERE actor_id = ?", (alice,))
    got = ask("Hand me the ledger or I'll shoot you.", t)
    assert [r[2] for r in got] in (["ready_compliance"], ["reluctant_compliance"])
    assert (resolve(w, "alice"), rel(w, "alice", "pc", "resentment")) == (3, 1)
