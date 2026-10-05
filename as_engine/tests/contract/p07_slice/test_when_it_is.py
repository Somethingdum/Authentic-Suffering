"""When it is (D-159). mind/packet.py AMB-01 when; prompts ambient_line.*, person_voice.system.j2.

The fast lane's prompts told every room line and every written voice that the story was "years after the Fall" —
of a world eighteen days into it, where people still talk about the Fall as last month. Now a room line is told the
day as the person knows it, and nothing claims years.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import CallClass
from as_engine.mind import perception
from as_engine.mind.packet import ambient_packet
from as_engine.physical import space
from as_engine.prompts.render import PROMPT_DIR, render

pytestmark = pytest.mark.phase(7)


def test_day_eighteen(scenario):
    w = scenario("metal_fence")
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        perception.compile_scene(tx, w.id("alice"), t + 100, 0)
        pk = ambient_packet(tx, w.id("alice"), 0, t + 500, idle=True)
    assert pk is not None and pk.when == "Day 18 since the Fall (night)"
    system, user = (m.content for m in render(CallClass.AMBIENT_LINE, ctx=pk))
    assert "When: Day 18 since the Fall (night)." in user
    assert "years" not in system


def test_no_prompt_claims_years():
    for name in ("ambient_line.system.j2", "person_voice.system.j2"):
        assert "years after the Fall" not in (PROMPT_DIR / name).read_text(encoding="utf-8"), name
