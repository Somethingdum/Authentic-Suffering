"""Nobody gives up to the dead (D-241); hands up before running (D-243). mind/affordance.py (surrender: a living
person must threaten; it ranks with shielding someone, ahead of running and cover).

With a walker in the crossroads and nobody else about, the player's list said "Show your empty hands and give up"
— the walker was a threat, so giving up was on offer. The dead take no one's surrender: what is offered in front of
them is to fight, run, hide or keep still, never to raise your hands. In front of a man with a gun it is there.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances

pytestmark = pytest.mark.phase(4)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def options(w, who, at=None):
    t = now(w) if at is None else at
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(who), t, 0)
        a = enumerate_affordances(tx, w.id(who), w.canon.all("affordance"), t, 0)
    return a


def offered(a):
    return [o.def_id for o in a.pool] + [r.def_id for r in a.rejected]


def test_hands_up_to_a_walker(scenario):
    w = scenario("two_skills")
    a = options(w, "pc")
    assert w.id("shambler") in a.threats, "the dead are still a threat"
    assert "flee_threat" in offered(a) and "surrender" not in offered(a)


def test_hands_up_to_a_man_with_a_gun(scenario):
    w = scenario("two_skills")
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("twin_a"), at=now(w), turn_index=0,
                              payload={"words": "Hands where I can see them.", "volume": "raised",
                                       "to": [w.id("pc")], "source_db": 70, "armed": True}))
    a = options(w, "pc", at=now(w) + 500)
    assert w.id("twin_a") in a.threats and "surrender" in offered(a)


def test_a_gun_on_you_hands_up_is_on_the_list(scenario):
    """(D-243) A man with a gun says "Hands where I can see them." and a walker is in the garage: the first menu
    has giving up, a way to run and cover — two ways to run and two ways to take cover had crowded it out."""
    w = scenario("two_skills")
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("twin_a"), at=now(w), turn_index=0,
                              payload={"words": "Hands where I can see them.", "volume": "raised",
                                       "to": [w.id("pc")], "source_db": 70, "armed": True}))
    menu = [o.def_id for o in options(w, "pc", at=now(w) + 500).options]
    assert {"flee_threat", "take_cover", "surrender"} <= set(menu), menu
