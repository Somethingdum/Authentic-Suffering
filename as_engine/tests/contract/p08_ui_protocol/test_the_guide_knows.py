"""What the character grew up hearing (D-140). Rule GUIDE-04 (service/guide.py pc_knows, answer).

The guide answered "What do people say about crawlers?" from the screen and the rules text alone, though Owen
grew up hearing plenty about them and knows where they hide. Now the lore he holds and the lessons he has learned
reach the guide when the question touches them — what he believes, wrong or right, never the world's truth.
"""

from __future__ import annotations

import pytest

from as_engine.service.guide import MAX_LORE, pc_knows

pytestmark = pytest.mark.phase(8)

SAYS = "People say (what you grew up hearing, not what you saw): "


def held(w, ref):
    return [w.canon.get(ref).beliefs[r[0]].text for r in w.store.query(
        "SELECT belief FROM lore_held WHERE holder_id = ? AND lore_ref = ? ORDER BY confidence DESC, belief", (w.id("pc"), ref))]


def test_crawlers(scenario):
    w = scenario("metal_fence")
    out = pc_knows(w.store, w.id("pc"), "What do people say about crawlers?")
    lore = [x[len(SAYS):] for x in out if x.startswith(SAYS)]
    assert lore and set(lore) <= set(held(w, "core:lore/crawlers")), "only what he holds, of what was asked"
    assert any(x.startswith("You know: ") and "crawlers" in x for x in out), "and what he has learned"
    assert not any("Knows: " in x for x in out)


def test_only_what_the_question_touches(scenario):
    w = scenario("metal_fence")
    assert pc_knows(w.store, w.id("pc"), "How does bleeding work?") == []


def test_what_he_believes_not_what_is_true(scenario):
    """Asked whether the head matters, he is told what he heard — the wrong saying too."""
    w = scenario("metal_fence")
    out = pc_knows(w.store, w.id("pc"), "Does the head matter? What's the headshot rule?")
    lore = [x[len(SAYS):] for x in out if x.startswith(SAYS)]
    assert 1 <= len(lore) <= MAX_LORE
    every = {t for r in w.store.query("SELECT DISTINCT lore_ref FROM lore_held WHERE holder_id = ?", (w.id("pc"),))
             for t in held(w, r[0])}
    assert set(lore) <= every


def test_nothing_he_does_not_hold(scenario):
    """Lore he never heard stays out, however it is asked for."""
    w = scenario("metal_fence")
    pc = w.id("pc")
    w.store.conn.execute("DELETE FROM lore_held WHERE holder_id = ?", (pc,))
    w.store.conn.execute("DELETE FROM lessons WHERE holder_id = ?", (pc,))
    assert pc_knows(w.store, pc, "What do people say about crawlers under the car?") == []
