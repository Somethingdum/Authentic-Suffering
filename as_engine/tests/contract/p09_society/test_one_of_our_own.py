"""One of our own (D-144). action/cascade.py selectors kin_group_of and kin_onlookers_of; core CAS-060;
society.group GRP-08 loyalty_check.

A killing seen cost the killer the onlookers' trust (D-119) and nothing more, even when the killer and the dead
were of one crew: the rest of the crew watched one of their own put down by one of their own and went on as if
the crew were what it had been. Now their grievance with the group rises, and within the hour each of them weighs
whether to stay (leaving starts as a plan, never at once).
"""

from __future__ import annotations

import json

import pytest

from as_engine.action import cascade
from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec
from as_engine.society import group
from as_engine.turn import timers

pytestmark = pytest.mark.phase(9)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def kill(w, who, whom):
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("sales_floor"), None, 4.0, 4.0, t, None, 0))
        st = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=t + 500, turn_index=0, actor_id=w.id(who),
                                   payload={"actor_id": w.id(who), "def_id": "strike_melee", "verb": "attack", "target_id": w.id(whom)}))
        hurt = bodies.apply_harm(tx, w.id(whom), WoundSpec(Anatomy.NECK, WoundType.CUT, WoundSeverity.CATASTROPHIC), t + 800,
                                 st.event_id, 0, w.rng)
        death = [e for e in hurt if e.type == EventType.DEATH]
        if not death:
            harm = next(e for e in hurt if e.type == EventType.HARM)
            death = [bodies.kill(tx, w.id(whom), "blood_loss", t + 900, 0, w.rng, cause_event_id=harm.event_id)]
        for x in ("pc", "mara", "alice", "june"):
            if x != whom:
                perception.compile_aftermath(tx, w.id(x), [st] + hurt + death, t + 1500, 0)
    return death[-1], t + 2000


def test_owen_kills_alice_in_front_of_the_crew(scenario):
    w = scenario("metal_fence")
    crew = w.id("crew")
    death, at = kill(w, "pc", "alice")
    with w.store.transaction() as tx:
        assert cascade.select(tx, "kin_group_of(trigger.event_id)", death) == [crew]
        assert cascade.select(tx, "kin_onlookers_of(trigger.event_id)", death) == sorted([w.id("june"), w.id("mara")])
    before = {x: group.tension_of(w.store, w.id(x), crew) for x in ("june", "mara")}
    with w.store.transaction() as tx:
        cascade.sweep(tx, [death], [r for r in w.canon.all("cascade") if r.id == "CAS-060"], at, 0)
    assert {x: group.tension_of(w.store, w.id(x), crew) for x in ("june", "mara")} == {x: min(100, v + 20) for x, v in before.items()}
    due = [r for r in w.store.query("SELECT due_at, subject_id, payload FROM event_queue WHERE type = 'CASCADE_EFFECT' AND "
                                    "status = 'pending' ORDER BY subject_id") if json.loads(r[2]).get("rule_id") == "CAS-060"]
    assert [(r[1], r[0] - at) for r in due] == sorted([(w.id("june"), 3_600_000), (w.id("mara"), 3_600_000)])
    with w.store.transaction() as tx:
        timers.fire_due(tx, w.rng, at + 3_600_000, 0, at + 3_600_000)
    checks = {json.loads(r[0])["actor_id"]: json.loads(r[0]) for r in w.store.query(
        "SELECT payload FROM events WHERE type = 'LOYALTY_CHECK' ORDER BY seq")}
    assert set(checks) == {w.id("june"), w.id("mara")}
    assert all(c["group_id"] == crew and c["reason"] == "killed_one_of_us" for c in checks.values())


def test_a_stranger_killed_is_not_one_of_ours(scenario):
    """Mara kills the stranger at the fence: he was never one of the crew."""
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        t = now(w)
        tx.commit_event(space.move_event(tx, w.id("stranger"), w.id("sales_floor"), None, 5.0, 5.0, t, None, 0))
    death, _at = kill(w, "mara", "stranger")
    with w.store.transaction() as tx:
        assert cascade.select(tx, "kin_group_of(trigger.event_id)", death) == []
        assert cascade.select(tx, "kin_onlookers_of(trigger.event_id)", death) == []
