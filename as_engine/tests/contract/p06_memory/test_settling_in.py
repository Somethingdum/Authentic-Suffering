"""Settling in (D-263). mind/memory.py worth_writing (MEM-20).

Eleven people in one room on a quiet night; two of them lay down to rest, and on the next turn the other eight were
each sent to write a memory: "Kevin Barnes lies at the front." Someone they had been looking at all along sitting
down, getting up or lying down is not something to remember — their standing view changed only in how they hold
themselves. A body going still, a weapon in a hand, someone bleeding badly, or someone new, still is.
"""

from __future__ import annotations

import pytest

from as_engine.mind import memory, perception

pytestmark = pytest.mark.phase(6)

T = 3


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def looked(w, was, now_text, *, source="mara"):
    """June saw Mara (or ``source``) standing by the counter last turn; this turn she sees ``now_text``."""
    t = now(w)
    with w.store.transaction() as tx:
        perception.grant(tx, w.id("june"), event_id=f"scene:{T - 1}", channel="visual", fidelity="exact", text=was,
                         source_id=w.id("mara"), at=t - 5000, turn_index=T - 1, detail={"level": "clear"})
        perception.grant(tx, w.id("june"), event_id=f"scene:{T}", channel="visual", fidelity="exact", text=now_text,
                         source_id=w.id(source), at=t + 100, turn_index=T, detail={"level": "clear"})
        a = memory.build_aftermath(tx, w.id("june"), T, t + 1000)
        assert now_text in [p.text for p in a.percepts]
        return memory.worth_writing(tx, w.id("june"), a, T)


@pytest.mark.parametrize("text", ["Mara sits by the counter.", "Mara lies by the counter.", "Mara crouches by the counter.",
                                  "Mara lies flat by the counter."])
def test_sat_down_or_lay_down(scenario, text):
    assert not looked(scenario("metal_fence"), "Mara stands by the counter.", text)


@pytest.mark.parametrize("text", ["Mara lies still by the counter.",
                                  "Mara stands by the counter, a .38 revolver in the right hand.",
                                  "Mara sits by the counter, bleeding badly.",
                                  "Mara stands at the back door."])
def test_what_is_still_news(scenario, text):
    assert looked(scenario("metal_fence"), "Mara stands by the counter.", text)


def test_someone_she_had_not_seen(scenario):
    """Alice sitting by the counter is news to June when it was Mara she saw there last turn."""
    assert looked(scenario("metal_fence"), "Mara stands by the counter.", "Alice sits by the counter.", source="alice")
