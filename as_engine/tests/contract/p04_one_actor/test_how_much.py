"""How much (D-165). mind/packet.py relationships (and the room's feeling, AMB-01, and the aftermath, MEM-01).

A feeling about someone was worded by which way it went and never by how far: trusting someone a little and with
your life both read "You trust them"; unease and terror both "you fear them"; a grudge that will never be forgiven
"you resent them". After someone tries to kill you, the model could not tell it from a cold shoulder.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import LOD
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet
from as_engine.physical import space

pytestmark = pytest.mark.phase(4)


def feeling(w, who, whom, **axes):
    sets = ", ".join(f"{k} = {v}" for k, v in axes.items())
    w.store.conn.execute(f"UPDATE relationships SET {sets} WHERE from_id = ? AND to_id = ?", (w.id(who), w.id(whom)))
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)   # he is here and seen: pinned
        perception.compile_scene(tx, w.id(who), t + 100, 0)
        aff = enumerate_affordances(tx, w.id(who), w.canon.all("affordance"), t + 100, 0)
        p = build_packet(tx, w.id(who), LOD.WARM, aff, 0, t + 100)
    return {p.handles[r.handle]: r.text for r in p.relationships}[w.id(whom)]


@pytest.mark.parametrize("axes, text", [
    ({"trust": -3, "fear": 3, "resentment": 3}, "You do not trust them at all; you are terrified of them; you will not forgive them."),
    ({"trust": -1, "fear": 1, "resentment": 1}, "You are wary of them; they make you uneasy; something they did still rankles."),
    ({"trust": 1, "respect": -3, "affection": -3}, "You mostly trust them; you despise them; you hate them."),
    ({"trust": 0, "obligation": 3}, "You owe them your life."),
    ({"trust": 0, "obligation": -2}, "They owe you a great deal."),
])
def test_how_far_it_went(scenario, axes, text):
    w = scenario("metal_fence")
    assert feeling(w, "mara", "pc", **axes) == text
