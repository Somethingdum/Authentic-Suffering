"""How they spoke (D-166). prompts/render.py VOLUME_WORDS; prompts/actor_cognition.user.j2.

Every line a mind heard was written "P1 (peer) spoke normal to you", "spoke shout", "spoke whisper" — broken English
in every actor's prompt, every turn. Now: whispered, spoke quietly, spoke, called out, shouted. And (D-168) the
speaker's standing was the raw enum — "(peer)", "(valid order)" — now "(someone you know)", "(someone whose orders you
follow)".
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import LOD, CallClass
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet
from as_engine.prompts.render import render

pytestmark = pytest.mark.phase(4)


@pytest.mark.parametrize("volume, verb", [("normal", "spoke"), ("raised", "called out"), ("shout", "shouted")])
def test_called_out(scenario, volume, verb):
    w = scenario("metal_fence")
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("mara"), at=t + 100, turn_index=0,
                                   payload={"words": "June, stay where you are.", "volume": volume, "to": [w.id("june")],
                                            "source_db": 70, "armed": False}))
        perception.compile_aftermath(tx, w.id("june"), [ev], t + 300, 0)
        aff = enumerate_affordances(tx, w.id("june"), w.canon.all("affordance"), t + 400, 0)
        p = build_packet(tx, w.id("june"), LOD.HOT, aff, 0, t + 400)
    text = render(CallClass.ACTOR_COGNITION, p=p)[1].content
    line = next(x for x in text.splitlines() if "June, stay where you are." in x)
    assert f") {verb} to you, and you heard it" in line, line
    assert " spoke " + volume not in line
    assert "(someone you know)" in line and "(peer)" not in line, "D-168: who they are to her, in words"
