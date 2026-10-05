"""The quiet hours see the whole mind (D-234). service/background.py BG-03 (ReflectionContext.cue_ids);
prompts/reflection.*.j2.

Between turns a person draws a lesson, forms a grudge, changes a plan — but the call that asks for it showed only who
they are, a few new memories and what hangs over them. A lesson must be tagged with cue words from the registry, and
the words were never given, so nearly every lesson the quiet hours drew was thrown away (BG-04); the answer had to
cite "an E label" that nothing was labelled with; and none of what the person grew up hearing, believes or feels
about the people around them was there to read their day by.
"""

from __future__ import annotations

import asyncio

import pytest
from test_background import REFLECTED, episode, next_turn, now

from as_engine.contracts.common import CallClass
from as_engine.prompts.render import render
from as_engine.service import background as bg

pytestmark = pytest.mark.phase(10)


def asked(w, fake):
    T = next_turn(w)
    episode(w, "june", salience=70, at=now(w), summary="Mara told me to keep quiet and I did.")
    fake.script(CallClass.REFLECTION, REFLECTED, actor_id=w.id("june"))
    res = asyncio.run(bg.run_job(w.session(), bg.jobs(w.store, T)[0]))
    assert not res.failed
    [req] = fake.calls(CallClass.REFLECTION)
    return req


def test_the_words_a_lesson_may_use(scenario, fake):
    w = scenario("metal_fence")
    req = asked(w, fake)
    cues = [c.id for c in w.canon.by_kind["cue"].values()]
    assert req.context.cue_ids == cues and "metal_crash" in cues
    system, user = (m.content for m in render(CallClass.REFLECTION, ctx=req.context))
    assert "Cue words a lesson may be tagged with: " + ", ".join(cues) in user


def test_her_day_read_as_she_reads_it(scenario, fake):
    w = scenario("metal_fence")
    req = asked(w, fake)
    system, user = (m.content for m in render(CallClass.REFLECTION, ctx=req.context))
    assert "- R1: Mara told me to keep quiet and I did." in user
    assert "the R label of the memory it comes from" in system and "an E label" not in system
    feelings = [r for r in req.context.packet.relationships]
    assert feelings, "June has feelings about the people around her"
    assert "How they feel about the people around them:\n- " in user
