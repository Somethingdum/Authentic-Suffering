"""Seen, not caught (D-158). prompts/render.py PERCEPT_WORDS; mind/packet.py uncertainty.

How a percept came through was worded for speech whatever it was: a woman half seen across the room came through
"only partly, some words lost", a shape in the dark "seen, not heard", and the doubt it left was "You did not catch
all of S2." Now a sighting is made out (or not), a sound is caught (or not), and only words are lost.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import LOD, CallClass
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet
from as_engine.physical import space
from as_engine.prompts.render import render

pytestmark = pytest.mark.phase(4)


def test_a_woman_half_seen(scenario):
    w = scenario("metal_fence")
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        perception.compile_scene(tx, w.id("mara"), t + 100, 0)
        aff = enumerate_affordances(tx, w.id("mara"), w.canon.all("affordance"), t + 100, 0)
        p = build_packet(tx, w.id("mara"), LOD.HOT, aff, 0, t + 100)
    half = [s for s in p.perceived_now if s.channel.value == "visual" and s.fidelity.value == "partial"]
    assert half, "Alice, behind the counter, is only partly seen"
    h = half[0].handle
    assert f"You could not make out all of {h}." in p.uncertainty
    text = render(CallClass.ACTOR_COGNITION, p=p)[1].content
    assert f"- {h} (visual, only partly): " in text and "some words lost" not in text.split("What reaches you")[1].split("People you")[0]
