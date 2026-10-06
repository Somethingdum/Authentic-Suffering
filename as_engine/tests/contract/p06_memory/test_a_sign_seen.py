"""A sign seen (D-275). mind/retrieval.py LORE-03 (what people say comes to mind at a trace); core lore lurkers, shamblers.

Everyone grows up hearing "Scratches, piled bones, marks on the walls — that's lurker ground. Leave." — and a person
standing in front of deep claw gouges in a door frame, higher than a man could reach, never once thought of it: lore
came to mind from words heard and from the people and things it names, never from a sign left behind. Now a trace seen
brings what people say about it to mind, as surely as hearing it named.
"""

from __future__ import annotations

import pytest

from as_engine.mind import perception
from as_engine.mind.retrieval import lore_lines
from as_engine.physical import space
from as_engine.world import traces

pytestmark = pytest.mark.phase(6)

LURKER_GROUND = "Scratches, piled bones, marks on the walls — that's lurker ground. Leave."


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def mara_sees(w, text):
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        if text:
            traces.create(tx, w.id("sales_floor"), "damage", text, None, t, 0)
        perception.compile_scene(tx, w.id("mara"), t + 100, 0)
        return [x["text"] for x in lore_lines(tx, w.id("mara"), 0, t + 200, 6)]


def test_claw_gouges_are_lurker_ground(scenario):
    w = scenario("metal_fence")
    assert LURKER_GROUND not in mara_sees(w, None), "nothing in front of her brings it to mind"
    w = scenario("metal_fence")
    assert LURKER_GROUND in mara_sees(w, "Deep claw gouges in the door frame, higher than a man could reach.")


def test_dragging_footprints_bring_the_dead_to_mind(scenario):
    w = scenario("metal_fence")
    got = mara_sees(w, "Dragging footprints in the dust, many of them, heading this way.")
    assert "Noise brings them. Always." in got, got


def test_the_ghosts_signature(scenario):
    w = scenario("metal_fence")
    got = mara_sees(w, "A small, neat smile has been cut into the body — deliberate, a signature, a warning.")
    assert "If you find a body with a smile cut into it, somebody crossed the Ghosts." in got, got


def test_a_horde_at_the_barricade_is_not_lurker_ground(scenario):
    """The dead clawing at a barricade leave marks too; only the lurkers' own gouges are lurker ground."""
    w = scenario("metal_fence")
    assert LURKER_GROUND not in mara_sees(w, "Claw marks and dents all along the barricade.")
