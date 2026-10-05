"""Nobody to calm (D-155). mind/affordance.py physical gate requires.target_distressed (contracts/content.py);
core calm_person.

"Talk Owen down: slow, steady, keep them from panicking" was offered toward everyone in earshot, panicking or not —
one menu slot per person, on a first menu of 24 — so a quiet room's menus filled with calming people who were calm,
and the player's character lost "Go through the storeroom door" to them. Now it is offered toward someone the actor
has heard shout or scream, or seen hurt, this turn or the one before.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec

pytestmark = pytest.mark.phase(4)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def floor(w):
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("sales_floor"), None, 6.0, 4.0, t, None, 0))
        perception.compile_scene(tx, w.id("mara"), t + 100, 0)
    return t + 200


def calm_targets(w, at):
    with w.store.transaction() as tx:
        a = enumerate_affordances(tx, w.id("mara"), w.canon.all("affordance"), at, 0)
    return ({w.local(o.target_id) for o in a.options if o.def_id == "calm_person"},
            {w.local(r.target_id) for r in a.rejected if r.def_id == "calm_person" and r.gate == "physical"})


def test_a_quiet_room_has_nobody_to_calm(scenario):
    w = scenario("metal_fence")
    offered, refused = calm_targets(w, floor(w))
    assert offered == set() and {"june", "pc"} <= refused


def test_someone_shouting_or_hurt(scenario):
    w = scenario("metal_fence")
    at = floor(w)
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("june"), at=at, turn_index=0,
                                   payload={"words": "Get it off the door! Get it off!", "volume": "shout", "to": ["everyone"],
                                            "source_db": 85, "armed": False}))
        perception.compile_aftermath(tx, w.id("mara"), [ev], at + 100, 0)
    assert calm_targets(w, at + 200)[0] == {"june"}
    with w.store.transaction() as tx:
        st = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at + 300, turn_index=0,
                                   actor_id=w.id("june"), payload={"actor_id": w.id("june"), "def_id": "punch", "verb": "attack",
                                                                    "target_id": w.id("pc")}))
        hurt = bodies.apply_harm(tx, w.id("pc"), WoundSpec(Anatomy.ARM_L, WoundType.BLUNT, WoundSeverity.MINOR), at + 400,
                                 st.event_id, 0, w.rng)
        perception.compile_aftermath(tx, w.id("mara"), [st] + hurt, at + 500, 0)
    assert calm_targets(w, at + 600)[0] == {"june", "pc"}
