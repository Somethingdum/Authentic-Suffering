"""Being hurt leaves a mark (D-126). Rules CAS-036..038 (core cascade/people.yaml); action/cascade.py paths
trigger.attacker and trigger.attacker_provoked, selectors hurt_by_someone, assault_onlookers_of and
threatened_by; world/rumours.py claim 'hurt_someone'.

The owner: "If I treat them like shit, or do something just absolutely evil. I do expect reactions, and
proper ones." A blow made someone angry (TEMPER-02), and anger fades by the hour; nothing lasting was written
unless they snapped. Now being hurt by someone you were not fighting costs them your trust, leaves you afraid
of them and holding it against them; whoever saw it trusts them less and tells it; a threat made at weapon
point leaves its target afraid. Never for a fight both sides were in, and never written into the player's
character (C06).
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec
from as_engine.world import rumours

pytestmark = pytest.mark.phase(9)

RULES = ("CAS-036", "CAS-037", "CAS-038")


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def lit(w):
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", now(w), None, 0)


def rel(w, a, b, axis):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def rules(w):
    return [r for r in w.canon.all("cascade") if r.id in RULES]


def hit(w, who, whom, at):
    """``who`` punches ``whom`` (a bruise); everyone on the floor perceives it. Returns the HARM."""
    with w.store.transaction() as tx:
        start = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0,
                                      actor_id=w.id(who), payload={"actor_id": w.id(who), "def_id": "punch", "verb": "attack",
                                                                   "target_id": w.id(whom)}))
        hurt = bodies.apply_harm(tx, w.id(whom), WoundSpec(Anatomy.ARM_L, WoundType.BLUNT, WoundSeverity.MINOR), at + 300,
                                 start.event_id, 0, w.rng)
        for x in ("pc", "mara", "alice"):
            perception.compile_aftermath(tx, w.id(x), [start] + hurt, at + 800, 0)
    return next(e for e in hurt if e.type == EventType.HARM)


def sweep(w, ev, at):
    with w.store.transaction() as tx:
        return cascade.sweep(tx, [ev], rules(w), at, 0)


def test_owen_hits_alice_for_nothing_with_mara_watching(scenario):
    w = scenario("metal_fence")
    lit(w)
    t = now(w)
    trust, fear, mara = rel(w, "alice", "pc", "trust"), rel(w, "alice", "pc", "fear"), rel(w, "mara", "pc", "trust")
    ev = hit(w, "pc", "alice", t)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "actor(trigger.attacker)", ev) == [w.id("pc")]
        assert cascade.select(tx, "hurt_by_someone(trigger.event_id)", ev) == [w.id("alice")]
        assert cascade.select(tx, "assault_onlookers_of(trigger.event_id)", ev) == [w.id("mara")]
    out = sweep(w, ev, t + 1000)
    assert {e.rule_cited for e in out} == {"CAS-036", "CAS-037"}
    assert (rel(w, "alice", "pc", "trust"), rel(w, "alice", "pc", "fear")) == (max(-3, trust - 2), min(3, fear + 1))
    assert w.store.query("SELECT 1 FROM open_loops WHERE holder_id = ? AND kind = 'grudge' AND text LIKE '%hurt you%'",
                         (w.id("alice"),)), "she holds it against him"
    assert rel(w, "mara", "pc", "trust") == max(-3, mara - 1)
    assert w.store.query("SELECT 1 FROM rumours WHERE origin_holder = ?", (w.id("mara"),)), "and she tells it"
    assert rumours.CLAIM_TEXT["hurt_someone"] == "{about} hurt someone who was not fighting back."


def test_a_fight_she_started_is_not_that(scenario):
    w = scenario("metal_fence")
    lit(w)
    t = now(w)
    hit(w, "alice", "pc", t)
    trust = rel(w, "alice", "pc", "trust")
    ev = hit(w, "pc", "alice", t + 5000)
    with w.store.transaction() as tx:
        assert cascade.evaluate_precondition(tx, "trigger.attacker_provoked == true", ev)
    assert sweep(w, ev, t + 6000) == [] and rel(w, "alice", "pc", "trust") == trust


def test_nothing_is_written_into_owen(scenario):
    """Mara hits Owen for nothing: what he feels about it is the player's (C06). Alice, watching, still judges her."""
    w = scenario("metal_fence")
    lit(w)
    t = now(w)
    ev = hit(w, "mara", "pc", t)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "hurt_by_someone(trigger.event_id)", ev) == []
        assert cascade.select(tx, "assault_onlookers_of(trigger.event_id)", ev) == [w.id("alice")]
    sweep(w, ev, t + 1000)
    assert rel(w, "pc", "mara", "trust") == 0 and not w.store.query(
        "SELECT 1 FROM open_loops WHERE holder_id = ? AND kind = 'grudge'", (w.id("pc"),))


def test_a_threat_at_gunpoint_is_remembered_and_a_hushing_is_not(scenario):
    """Owen holds his Glock (metal_fence: right hand). To Alice: "Hand it over or I'll shoot you." — she is afraid of
    him after. "Quiet." with the same gun in hand is not a threat to remember."""
    w = scenario("metal_fence")
    lit(w)
    t = now(w)
    fear = rel(w, "alice", "pc", "fear")

    def say(words, at):
        with w.store.transaction() as tx:
            ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("pc"), at=at, turn_index=0,
                                       payload={"words": words, "volume": "normal", "to": [w.id("alice")], "source_db": 60,
                                                "armed": True}))
            perception.compile_aftermath(tx, w.id("alice"), [ev], at + 500, 0)
        return ev
    hush = say("Quiet.", t)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "threatened_by(trigger.event_id)", hush) == []
    threat = say("Hand it over or I'll shoot you.", t + 5000)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "threatened_by(trigger.event_id)", threat) == [w.id("alice")]
    assert [e.rule_cited for e in sweep(w, threat, t + 6000)] == ["CAS-038"]
    assert rel(w, "alice", "pc", "fear") == min(3, fear + 1)
