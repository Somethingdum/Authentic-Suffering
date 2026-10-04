"""Putting down the dead is not hurting anyone (D-132). action/cascade.py trigger.attacker; core CAS-036, CAS-037,
CAS-040, CAS-043; lore cold_start ("Put every body down proper — head, or fire — inside three days, bitten or
not.").

Everyone in this world knows the dead must be put down. finish_downed — destroying the head of a body that is
already dead — lands a HARM like any blow, and the reactions to being hurt (D-126, D-129) read it as hurting
someone who was not fighting back: onlookers trusted the one doing the duty less and told it, and a friend of
the dead held a grudge for it. A body dead before the blow is no one hurt.
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec

pytestmark = pytest.mark.phase(9)

RULES = ("CAS-036", "CAS-037", "CAS-040", "CAS-043")


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def strike(w, who, whom, at, *, def_id="strike_melee", severity=WoundSeverity.CATASTROPHIC, anatomy=Anatomy.HEAD):
    with w.store.transaction() as tx:
        start = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0, actor_id=w.id(who),
                                      payload={"actor_id": w.id(who), "def_id": def_id, "verb": "attack", "target_id": w.id(whom)}))
        hurt = bodies.apply_harm(tx, w.id(whom), WoundSpec(anatomy, WoundType.BLUNT, severity), at + 300, start.event_id, 0, w.rng)
        if w.store.query_one("SELECT alive FROM bodies WHERE body_id = ?", (w.id(whom),))[0] and def_id == "strike_melee":
            harm = next(e for e in hurt if e.type == EventType.HARM)
            hurt.append(bodies.kill(tx, w.id(whom), "head_wound", at + 400, 0, w.rng, cause_event_id=harm.event_id))
        for x in ("pc", "mara", "alice"):
            perception.compile_aftermath(tx, w.id(x), [start] + hurt, at + 800, 0)
    return next(e for e in hurt if e.type == EventType.HARM)


def test_the_dead_put_down_is_no_one_hurt(scenario):
    """June is dead. A minute later Alice destroys her head, as everyone must: Mara, who loved June, watches —
    nobody trusts Alice less, nobody tells it, Mara holds nothing against her."""
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("sales_floor"), None, 4.0, 4.0, t, None, 0))
        bodies.kill(tx, w.id("june"), "blood_loss", t + 100, 0, w.rng)
    trust = w.store.query_one("SELECT trust FROM relationships WHERE from_id = ? AND to_id = ?", (w.id("mara"), w.id("pc")))
    ev = strike(w, "alice", "june", t + 60_000, def_id="finish_downed")
    with w.store.transaction() as tx:
        assert cascade.select(tx, "actor(trigger.attacker)", ev) == []
        assert cascade.select(tx, "assault_onlookers_of(trigger.event_id)", ev) == []
        assert cascade.select(tx, "bonded_onlookers_of(trigger.event_id)", ev) == []
        out = cascade.sweep(tx, [ev], [r for r in w.canon.all("cascade") if r.id in RULES], t + 61_000, 0)
    assert out == []
    assert not w.store.query("SELECT 1 FROM open_loops WHERE holder_id = ? AND kind = 'grudge'", (w.id("mara"),))
    assert not w.store.query("SELECT 1 FROM rumours WHERE origin_holder IN (?, ?)", (w.id("mara"), w.id("pc")))
    assert w.store.query_one("SELECT trust FROM relationships WHERE from_id = ? AND to_id = ?", (w.id("mara"), w.id("pc"))) == trust


def test_a_killing_blow_still_hurt_someone(scenario):
    """The blow that kills lands on someone alive: it is still someone hurt."""
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
    ev = strike(w, "pc", "alice", t)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "actor(trigger.attacker)", ev) == [w.id("pc")]


def test_nor_does_it_anger_or_alarm_the_ones_who_loved_her(scenario):
    """Mara loved June: the put-down is no 'harmed_bonded' provocation and no 'bonded_hurt' cue."""
    from as_engine.mind import cues, temper
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("sales_floor"), None, 4.0, 4.0, t, None, 0))
        bodies.kill(tx, w.id("june"), "blood_loss", t + 100, 0, w.rng)
    strike(w, "alice", "june", t + 60_000, def_id="finish_downed")
    with w.store.transaction() as tx:
        assert not [p for p in temper.provocations(tx, w.id("mara"), 0, t + 61_000) if p.kind == "harmed_bonded"]
        assert "bonded_hurt" not in cues.cues_of(tx, w.id("mara"), 0, t + 61_000)
