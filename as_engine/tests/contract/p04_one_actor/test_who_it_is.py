"""Who it is (D-277). prompts/actor_cognition.user.j2 (What reaches you; What remains uncertain); prompts/render.py;
prompts/writeback.user.j2 (WHAT THEY PERCEIVED).

A man in a pump house with eight people he knows was told "S1: A woman stands at the front." … "S8: A heavyset man
stands at the front." and, further down, "P1: Jolene Hale — here" … "P8: Andre Vargas — here" — and nothing said which
was which, so the one with the axe in her hand was nobody in particular. Then eight lines of "You could not make out
all of S1." … "of S8." Their memory was told the same way: "S1: A walker moves into the crossroads." and "P1: a
walker". What reaches someone from a person they can account for says who it is; and the doubts are said once.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import LOD, CallClass
from as_engine.mind import memory, perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet
from as_engine.physical import space
from as_engine.prompts.render import render

pytestmark = pytest.mark.phase(4)


def mara(w):
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        perception.compile_scene(tx, w.id("mara"), t + 100, 0)
        aff = enumerate_affordances(tx, w.id("mara"), w.canon.all("affordance"), t + 100, 0)
        return build_packet(tx, w.id("mara"), LOD.HOT, aff, 0, t + 100)


def section(text, head, nxt):
    return text.split(f"\n{head}\n", 1)[1].split(f"\n{nxt}", 1)[0]


def test_what_reaches_her_says_who_it_is(scenario):
    w = scenario("metal_fence")
    p = mara(w)
    people = [s for s in p.perceived_now if s.source_handle]
    assert len(people) >= 2, "she sees the people on the floor"
    text = render(CallClass.ACTOR_COGNITION, p=p)[1].content
    lines = section(text, "What reaches you", "People you").splitlines()
    for s in p.perceived_now:
        (ln,) = [x for x in lines if x.startswith(f"- {s.handle} (")]
        assert ln.endswith(f" ({s.source_handle})") == bool(s.source_handle), ln
    for s in people:
        assert f"\n- {s.source_handle}: " in text, "and that handle is someone she can account for"


def test_the_doubts_said_once(scenario):
    w = scenario("metal_fence")
    p = mara(w).model_copy(update={"uncertainty": [
        "You could not make out all of S1.", "You could not make out all of S2.", "You did not catch all of S3.",
        "You could not make out all of S5.", "You don't know what made the crash."]})
    text = render(CallClass.ACTOR_COGNITION, p=p)[1].content
    doubts = section(text, "What remains uncertain", "Possibilities").strip().splitlines()
    assert doubts == ["- You could not make out S1, S2 or S5 in full.", "- You did not catch all of S3.",
                      "- You don't know what made the crash."], doubts


def test_and_in_what_they_remember(scenario):
    w = scenario("metal_fence")
    mara(w)
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        a = memory.build_aftermath(tx, w.id("mara"), 0, t + 200)
    people = [s for s in a.percepts if s.source_handle]
    assert people, "her memory has the people she saw"
    text = render(CallClass.WRITEBACK, a=a, cue_ids=[])[1].content
    lines = section(text, "WHAT THEY PERCEIVED", "PEOPLE").splitlines()
    for s in a.percepts:
        (ln,) = [x for x in lines if x.startswith(f"- {s.handle} (")]
        assert ln.endswith(f" ({s.source_handle})") == bool(s.source_handle), ln
        if s.source_handle:
            assert f"\n- {s.source_handle}: " in text
