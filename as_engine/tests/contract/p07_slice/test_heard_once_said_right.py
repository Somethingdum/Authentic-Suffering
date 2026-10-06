"""Heard once, said right (D-295). mind/packet.py S1..Sn; mind/memory.py MEM-01 percept rows; mind/packet.py AMB-01;
prompts/actor_cognition.user.j2 (what you heard).

Owen called Mara a coward to her face in the dark. Her packet showed what she heard — and then, as S8, "(visual,
clearly): Owen insulted you.", the row her story of it (D-253) is granted on: a second thing perceived, and a sight in
a room where Owen was only a figure. The story is hers to believe and tell — and it is, under "What you believe".
And an order or an offer "came across as a order", "a offer".
"""

from __future__ import annotations

import pytest
from slice_kit import play

from as_engine.contracts.common import CallClass, UtteranceForm
from as_engine.mind import memory

pytestmark = pytest.mark.phase(7)


def insulted(w, fake):
    s = w.session()
    s.extras["forced_addressee"] = w.id("mara")
    assert play(s, "say", "Quiet.").ok                       # the crash out back has come and gone
    n = len(fake.calls(CallClass.ACTOR_REACTION))
    s.extras["forced_addressee"] = w.id("mara")
    o = play(s, "say", "Mara, you're a useless coward.")
    assert o.ok
    (r,) = [x for x in fake.calls(CallClass.ACTOR_REACTION)[n:] if x.actor_id == w.id("mara")]
    return o, r


def test_the_story_is_a_belief_not_a_sight(scenario, fake):
    w = scenario("metal_fence")
    o, r = insulted(w, fake)
    assert w.store.query("SELECT 1 FROM percept_log WHERE holder_id = ? AND event_id LIKE 'rumour:%'", (w.id("mara"),)), \
        "the story is hers"
    p = r.context.packet if hasattr(r.context, "packet") else r.context
    u = r.messages[-1].content
    assert not any(x.text.endswith("insulted you.") for x in p.perceived_now), p.perceived_now
    assert any(b.text.endswith("insulted you.") for b in p.beliefs), p.beliefs
    at = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        a = memory.build_aftermath(tx, w.id("mara"), o.turn_index, at)
    assert not any(x.text.endswith("insulted you.") for x in a.percepts)
    assert u.count("insulted you.") == 1, "said once"


def test_an_order(scenario, fake):
    w = scenario("metal_fence")
    o, r = insulted(w, fake)
    p = r.context.packet if hasattr(r.context, "packet") else r.context
    from as_engine.prompts.render import render
    for form, want in ((UtteranceForm.ORDER, "an order"), (UtteranceForm.OFFER, "an offer"), (UtteranceForm.THREAT, "a threat")):
        q = p.model_copy(update={"utterances": [x.model_copy(update={"form": form}) for x in p.utterances]})
        text = render(CallClass.ACTOR_REACTION, p=q)[1].content
        assert f"It came across as {want}." in text, text
