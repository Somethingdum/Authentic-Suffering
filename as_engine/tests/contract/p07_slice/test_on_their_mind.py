"""On their mind (D-257). Rule AMB-01 (mind/packet.py ambient_packet: mind); prompts/ambient_line.user.j2.

In a quiet moment the people past the model budget may say something idle (D-150) — but the call knew only how they
talk and who was there, so a room's small talk came out of nowhere: the cold, the weather, the same few words. Now it
knows what might be on their mind — what they are working on, what weighs on them, what they fear, what people here
say happened and what they grew up hearing — two of these, a different two from turn to turn.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import CallClass
from as_engine.mind import perception
from as_engine.mind.packet import ambient_packet
from as_engine.physical import space
from as_engine.prompts.render import render

pytestmark = pytest.mark.phase(7)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def quiet(w, turn):
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, turn)
        for x in ("mara", "alice"):
            perception.compile_scene(tx, w.id(x), t + 100, turn)
        return ambient_packet(tx, w.id("alice"), turn, t + 500, idle=True)


KINDS = ("What you are working on: ", "On your mind: ", "What you are afraid of: ", "Something people here say: ",
         "Something you grew up hearing: ")


def test_a_quiet_moment_has_something_on_her_mind(scenario):
    w = scenario("metal_fence")
    pk = quiet(w, 0)
    assert pk is not None and not pk.reached
    assert len(pk.mind) == 2 and all(m.startswith(KINDS) for m in pk.mind), pk.mind
    _system, user = (m.content for m in render(CallClass.AMBIENT_LINE, ctx=pk))
    assert "What might be on your mind (bring it up, or not):\n- " + pk.mind[0] in user


def test_a_different_thing_from_turn_to_turn(scenario):
    w = scenario("metal_fence")
    seen = {tuple(quiet(w, turn).mind) for turn in range(4)}
    assert len(seen) >= 2


def test_not_when_something_reached_her(scenario):
    """Something said to her is what she answers; her mind is not given then."""
    from as_engine.contracts.events import Event, EventType
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("mara"), at=t, turn_index=0,
                                   payload={"words": "Back door's shut?", "volume": "normal", "to": [w.id("alice")],
                                            "source_db": 60, "armed": False}))
        perception.grant(tx, w.id("alice"), event_id=ev.event_id, channel="speech", fidelity="exact",
                         text='Mara says to you, "Back door\'s shut?"', source_id=w.id("mara"), at=t + 100, turn_index=0,
                         detail={"words": "Back door's shut?", "volume": "normal", "addressed_to_me": True})
        pk = ambient_packet(tx, w.id("alice"), 0, t + 500)
    assert pk is not None and pk.reached and pk.mind == []
