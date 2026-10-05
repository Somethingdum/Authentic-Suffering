"""A safety precaution (D-202). action/cascade.py: onlookers_of, assault_onlookers_of, attack_onlookers_of leave
out whoever knew the one it was done to was infected.

The owner: "An infected person is a threat to every non infected. It is a safety precaution." Owen put down Alice,
bitten in front of June an hour before, and June held it against him as she would a murder: trust gone, afraid of
him, and the story "killed someone who was not fighting back" on her lips. Now whoever knew Alice carried it sees a
precaution; whoever did not, sees a killing — and grief is grief either way.
"""

from __future__ import annotations

import pytest
from test_a_killing_seen import kill, lit, now, rel, rules, sweep

from as_engine.action import cascade
from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec

pytestmark = pytest.mark.phase(9)


def june_on_the_floor(w, at):
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("sales_floor"), None, 7.0, 4.0, at, None, 0))


def bitten(w, who, at, seen_by):
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=at, turn_index=0, payload={"what": "test"}))
        hurt = bodies.apply_harm(tx, w.id(who), WoundSpec(Anatomy.ARM_L, WoundType.BITE, WoundSeverity.MINOR), at,
                                 c.event_id, 0, w.rng)
        for x in seen_by:
            perception.compile_aftermath(tx, w.id(x), hurt, at + 500, 0)


def test_june_saw_the_bite_mara_did_not(scenario):
    w = scenario("metal_fence")
    lit(w)
    t = now(w)
    june_on_the_floor(w, t)
    bitten(w, "alice", t, seen_by=("june",))
    june, mara = rel(w, "june", "pc", "trust"), rel(w, "mara", "pc", "trust")
    death = kill(w, "pc", "alice", t + 60_000)
    with w.store.transaction() as tx:
        judged = cascade.select(tx, "onlookers_of(trigger.event_id)", death)
        grieving = cascade.select(tx, "seen_clearly_by(trigger.event_id)", death)
    assert w.id("mara") in judged and w.id("june") not in judged, "June knew she carried it"
    assert w.id("june") in grieving, "she still saw it, and grief is grief"
    sweep(w, death, t + 62_000)
    assert rel(w, "june", "pc", "trust") == june, "a precaution, not a killing"
    assert rel(w, "mara", "pc", "trust") == max(-3, mara - 2), "Mara saw a killing"
    told = [r[0] for r in w.store.query("SELECT origin_holder FROM rumours")]
    assert w.id("june") not in told and w.id("mara") in told


def test_seen_spreading_it_is_known_too(scenario):
    """Seeing Alice spit into a sleeper's mouth is knowing she carries it (D-187's surest sign)."""
    w = scenario("metal_fence")
    lit(w)
    t = now(w)
    june_on_the_floor(w, t)
    with w.store.transaction() as tx:
        st = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=t, turn_index=0, actor_id=w.id("alice"),
                                   payload={"actor_id": w.id("alice"), "def_id": "spit_in_mouth", "verb": "manipulate",
                                            "target_id": w.id("eli"), "visible": True,
                                            "seen": "bends over {target}'s sleeping face"}))
        perception.compile_aftermath(tx, w.id("june"), [st], t + 200, 0)
    death = kill(w, "pc", "alice", t + 60_000)
    with w.store.transaction() as tx:
        assert w.id("june") in cascade.select(tx, "seen_clearly_by(trigger.event_id)", death), "she saw it"
        assert w.id("june") not in cascade.select(tx, "onlookers_of(trigger.event_id)", death)
