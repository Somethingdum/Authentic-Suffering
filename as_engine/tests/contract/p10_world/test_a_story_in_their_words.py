"""A story in their own words (D-235). service/background.py BG-03 retelling (RumourContext); mind/retrieval.py
LORE-04 lore_about; prompts/rumour_distort.*.j2.

Between turns everyone who holds a story passes on their own version of it (INFO-06) — but the call that asked for
it knew only the teller's name and the bare claim as the engine first wrote it. A twist heard was never passed on
(each teller started again from the original); the teller's voice, what they feel about the one it is about and
what they grew up hearing were not there to tell it by; and a twist could name only people the model could not
know the teller knew, so it was thrown away.
"""

from __future__ import annotations

import asyncio

import pytest
from test_background import next_turn, now, retelling, seed

from as_engine.contracts.common import CallClass
from as_engine.contracts.mind import RumourDistortion
from as_engine.mind import actor, retrieval
from as_engine.prompts.render import render
from as_engine.service import background as bg
from as_engine.world import rumours

pytestmark = pytest.mark.phase(10)


def asked(w, fake, who, rid):
    fake.fail(CallClass.RUMOUR_DISTORT, "grammar_fail")
    res = asyncio.run(bg.run_job(w.session(), retelling(w, who, rid)))
    assert res.failed
    [req] = fake.calls(CallClass.RUMOUR_DISTORT)
    return req.context


def test_a_twist_heard_is_passed_on_twisted(scenario, fake):
    w = scenario("metal_fence")
    rid = seed(w, "mara", "stranger", "lied")
    T = next_turn(w)
    twisted = "The thin man at the fence lied to everyone here, and smiled doing it."
    job = retelling(w, "mara", rid)
    with w.store.transaction() as tx:
        bg.commit(tx, job, bg.JobResult(job=job, answer=RumourDistortion(operation="sharpen_emotion", retold_claim=twisted)),
                  now(w), T)
        rumours.spread_one(tx, rid, w.id("mara"), w.id("nita"), now(w), T, None)
    ctx = asked(w, fake, "nita", rid)
    assert ctx.claim_text == twisted, "Nita passes on what she was told, not the story as it began"


def test_she_tells_it_as_she_talks_and_feels(scenario, fake):
    w = scenario("metal_fence")
    rid = seed(w, "nita", "mara", "bitten")
    next_turn(w)
    ctx = asked(w, fake, "nita", rid)
    v = actor.fused(w.store, w.id("nita")).voice
    assert ctx.claim_text == "Mara was bitten."
    assert ctx.voice[0] == f"How they talk: {v.capsule}" and ctx.voice[1].startswith("Habits of speech: ")
    assert ctx.feeling == "She mostly trusts them; she respects them.", "Nita toward Mara: trust 1, respect 2"
    assert ctx.lore and ctx.lore[0] == "A bite is a death sentence, full stop.", "what she grew up hearing about bites"
    assert ctx.people[0] == "Mara" and {"June", "Owen"} <= set(ctx.people), "the people she knows by name"
    assert "Dale" not in " ".join(ctx.people), "the stranger is a description to her, not a name"
    system, user = (m.content for m in render(CallClass.RUMOUR_DISTORT, ctx=ctx))
    assert "How they feel about the one it is about: She mostly trusts them" in user
    assert "People they know by name: Mara, " in user
    assert "never as \"I\", \"we\" or \"you\"" in system
    assert "Keep the one it is about in it" in system and "it stays their doing" in system, \
        "a story's wrong is charged to the one it is about (D-216): a twist may not hand it to someone else"


def test_what_a_story_brings_to_mind(scenario):
    """LORE-04: the lore a story's words touch, from what the holder holds — nothing when it touches none."""
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        bitten = retrieval.lore_about(tx, w.id("nita"), "Mara was bitten.", [w.id("mara")], 3)
        lied = retrieval.lore_about(tx, w.id("nita"), "Mara lied to people here.", [w.id("mara")], 3)
    assert [x["lore_id"] for x in bitten] == ["core:lore/wet_strain"] * 2
    assert lied == []
