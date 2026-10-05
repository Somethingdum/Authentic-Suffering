"""The mouth rules (D-193). Lore contamination_culture's `when` (LORE-03, mind/retrieval.py lore_lines).

"Your bottle, your spoon, your smoke. Nobody else's. Ever." and "Nobody who's been in quarantine and failed comes back
out." came to mind only on a spreader's signs: its entities are laws, which nobody sees, so the moment everyone
thinks of them — a fresh bite on someone standing next to you — brought nothing but the wet strain's own lore.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception, retrieval
from as_engine.mind.cues import cues_of
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec

pytestmark = pytest.mark.phase(9)


def test_a_bite_beside_you_brings_the_mouth_rules_to_mind(scenario):
    w = scenario("metal_fence")
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        for who, x in (("june", 5.0), ("mara", 6.0)):
            tx.commit_event(space.move_event(tx, w.id(who), w.id("sales_floor"), None, x, 4.0, t, None, 0))
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=0, payload={"what": "test"}))
        bodies.apply_harm(tx, w.id("june"), WoundSpec(Anatomy.ARM_L, WoundType.BITE, WoundSeverity.SIGNIFICANT), t, c.event_id, 0, w.rng)
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id("mara"), t + 1000, 0)
        assert "bite_wound_seen" in cues_of(tx, w.id("mara"), 0, t + 1000)
        said = {x["lore_id"] for x in retrieval.lore_lines(tx, w.id("mara"), 0, t + 1000, 6)}
    assert {"core:lore/wet_strain", "core:lore/contamination_culture"} <= said, said


def test_she_remembers_it_as_she_was_raised_to(scenario):
    """D-196: the memory of what she saw is written with what she grew up hearing about it in mind."""
    from as_engine.contracts.common import CallClass
    from as_engine.mind import memory
    from as_engine.prompts.render import render
    w = scenario("metal_fence")
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        for who, x in (("june", 5.0), ("mara", 6.0)):
            tx.commit_event(space.move_event(tx, w.id(who), w.id("sales_floor"), None, x, 4.0, t, None, 0))
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=0, payload={"what": "test"}))
        bodies.apply_harm(tx, w.id("june"), WoundSpec(Anatomy.ARM_L, WoundType.BITE, WoundSeverity.SIGNIFICANT), t, c.event_id, 0, w.rng)
        perception.compile_scene(tx, w.id("mara"), t + 1000, 0)
        a = memory.build_aftermath(tx, w.id("mara"), 0, t + 1000)
    assert a.lore and any("bite" in x.lower() for x in a.lore), a.lore
    user = render(CallClass.WRITEBACK, a=a, cue_ids=["bite_wound_seen"])[1].content
    assert "WHAT THEY GREW UP HEARING ABOUT THIS (belief, not fact)\n- " in user
    with w.store.transaction() as tx:
        memory.queue_writeback(tx, w.id("mara"), 0, t + 1000)
    ((turn, texts),) = memory.unprocessed(w.store, w.id("mara"))
    assert turn == 0 and texts, "a memory not yet written is still read back raw, from the store"


def test_what_owen_was_always_told(scenario):
    """D-197: the story lets what the player's character grew up hearing come to mind — the turn it first comes up,
    not every turn the bitten woman is still standing there."""
    from as_engine.contracts.common import CallClass
    from as_engine.narration.narrator import build_narrator_packet
    from as_engine.prompts.render import render
    w = scenario("metal_fence")
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        for who, x in (("june", 5.0), ("pc", 6.0)):
            tx.commit_event(space.move_event(tx, w.id(who), w.id("sales_floor"), None, x, 4.0, t, None, 0))
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=1, payload={"what": "test"}))
        bodies.apply_harm(tx, w.id("june"), WoundSpec(Anatomy.ARM_L, WoundType.BITE, WoundSeverity.SIGNIFICANT), t, c.event_id, 1, w.rng)
        perception.compile_scene(tx, w.id("pc"), t + 1000, 1)
        first = build_narrator_packet(tx, w.id("pc"), 1, t, w.session().settings)
        perception.compile_scene(tx, w.id("pc"), t + 2000, 2)
        second = build_narrator_packet(tx, w.id("pc"), 2, t + 1000, w.session().settings)
    assert first.pc_beliefs and any("bite" in b.lower() for b in first.pc_beliefs), first.pc_beliefs
    user = render(CallClass.NARRATION, k=first, words=w.store.rules.style.narration_words[first.length], fix=[])[1].content
    assert "What Owen grew up hearing about this" in user
    assert second.pc_beliefs == [], "it came to mind once; she is still there, and it is not said again"


def test_what_people_say_about_that_crowd(scenario):
    """D-201: a faction's belief_text — what ordinary survivors say about them — comes to mind on seeing one of them;
    nobody thinks it of their own."""
    w = scenario("metal_fence")
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        for who, x in (("stranger", 5.0), ("mara", 6.0), ("june", 7.0)):
            tx.commit_event(space.move_event(tx, w.id(who), w.id("sales_floor"), None, x, 4.0, t, None, 0))
        for who in ("stranger", "june"):
            perception.compile_scene(tx, w.id(who), t + 1000, 0)
        theirs = retrieval.lore_lines(tx, w.id("stranger"), 0, t + 1000, 6)
        ours = retrieval.lore_lines(tx, w.id("june"), 0, t + 1000, 6)
    crew = w.canon.get("core:faction/delgados_crew").belief_text
    assert {"lore_id": "core:faction/delgados_crew", "belief": 0, "text": crew, "confidence": 2, "provenance": "common"} in theirs
    assert all(x["lore_id"] != "core:faction/delgados_crew" for x in ours), "not of your own"
