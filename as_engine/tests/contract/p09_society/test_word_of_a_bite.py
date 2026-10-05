"""Word of a bite (D-217). action/cascade.py saw_the_bite, and the D-202 note (a believed 'bitten' holding);
core CAS-103, CAS-104.

The most important thing anyone can know about a person in this world was never told: a bite seen started no
story ('bitten' was in the rumour vocabulary, and nothing made it), and Mara, told by June that Alice was bitten,
held Owen putting Alice down against him as a murder. Now whoever saw the bite carries the story, whoever believes
the telling is afraid of the bitten one, and knowing it, seen or told, makes putting them down a precaution
(D-202), as long as they knew it before it was done.
"""

from __future__ import annotations

import pytest
from test_a_killing_seen import kill, lit, now, rel

from as_engine.action import cascade
from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec
from as_engine.world import rumours

pytestmark = pytest.mark.phase(9)


def june_on_the_floor(w, at):
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("sales_floor"), None, 7.0, 4.0, at, None, 0))


def bitten(w, at):
    """Alice bitten on the arm in front of June and Owen; the bite is swept as the pipeline would."""
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=at, turn_index=0, payload={"what": "test"}))
        hurt = bodies.apply_harm(tx, w.id("alice"), WoundSpec(Anatomy.ARM_L, WoundType.BITE, WoundSeverity.MINOR), at,
                                 c.event_id, 0, w.rng)
        for x in ("june", "pc"):
            perception.compile_aftermath(tx, w.id(x), hurt, at + 500, 0)
        harm = next(e for e in hurt if e.type == EventType.HARM)
        cascade.sweep(tx, [harm], [r for r in tx.canon.all("cascade") if r.id == "CAS-103"], at + 600, 0)
    return harm


def told(w, at):
    """June tells Mara."""
    rid = w.store.query_one("SELECT rumour_id FROM rumours WHERE origin_holder = ?", (w.id("june"),))[0]
    with w.store.transaction() as tx:
        rs = rumours.spread_one(tx, rid, w.id("june"), w.id("mara"), at, 0, None)
        cascade.sweep(tx, [rs], [r for r in tx.canon.all("cascade") if r.id == "CAS-104"], at, 0)
    return rs


def holds_bitten(w, who):
    return w.store.query_one("SELECT 1 FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id WHERE h.holder_id = ? "
                             "AND h.believed = 1 AND p.subject_id = ? AND p.predicate = 'bitten'", (w.id(who), w.id("alice"))) is not None


def test_whoever_saw_it_tells_it(scenario):
    w = scenario("metal_fence")
    lit(w)
    t = now(w)
    june_on_the_floor(w, t)
    harm = bitten(w, t)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "saw_the_bite(trigger.event_id)", harm) == [w.id("june")], "never Alice, never Owen"
    told_by = [r[0] for r in w.store.query("SELECT r.origin_holder FROM rumours r JOIN propositions p ON p.prop_id = r.prop_id "
                                           "WHERE p.predicate = 'bitten' AND p.subject_id = ?", (w.id("alice"),))]
    assert told_by == [w.id("june")]
    fear = rel(w, "mara", "alice", "fear")
    rs = told(w, t + 10_000)
    assert rs.payload["believed"] is True and holds_bitten(w, "mara")
    assert rel(w, "mara", "alice", "fear") == min(3, fear + 1), "told she was bitten, Mara is afraid of her"


def test_told_before_it_was_done_is_knowing(scenario):
    """Owen puts Alice down a minute later: June saw the bite, Mara was told it — neither holds it against him."""
    w = scenario("metal_fence")
    lit(w)
    t = now(w)
    june_on_the_floor(w, t)
    bitten(w, t)
    told(w, t + 10_000)
    death = kill(w, "pc", "alice", t + 60_000)
    with w.store.transaction() as tx:
        judged = cascade.select(tx, "onlookers_of(trigger.event_id)", death)
    assert w.id("june") not in judged and w.id("mara") not in judged


def test_told_after_is_too_late(scenario):
    """Told after Owen did it, Mara saw a killing when it happened."""
    w = scenario("metal_fence")
    lit(w)
    t = now(w)
    june_on_the_floor(w, t)
    bitten(w, t)
    death = kill(w, "pc", "alice", t + 60_000)
    told(w, t + 120_000)
    with w.store.transaction() as tx:
        judged = cascade.select(tx, "onlookers_of(trigger.event_id)", death)
    assert w.id("mara") in judged and w.id("june") not in judged
