"""What they set out to do (D-291). mind/packet.py commitments plan_goal and the WILL-C fill; contracts/mind.py
Commitments; prompts/actor_cognition.user.j2.

Mara stands at the front window because her plan is to watch it — and her prompt said "What you are in the middle
of: Nothing in particular." with a standing order under it. A raider of the gang that means to rob the stranger was
told "Nothing in particular." and "Next step of your plan: follow the stranger", never why. What a person set out to
do (a scenario's plan, worldgen's, a reflection's) is shown to them; "Nothing in particular" only when it is so.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import LOD, CallClass
from as_engine.contracts.events import Event, EventType
from as_engine.mind import mind, perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet
from as_engine.physical import bodies
from as_engine.prompts.render import render

pytestmark = pytest.mark.phase(4)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def packet_for(w, local, at):
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(local), at, 0)
        aff = enumerate_affordances(tx, w.id(local), w.canon.all("affordance"), at, 0)
        return build_packet(tx, w.id(local), LOD.HOT, aff, 0, at)


def middle(p):
    text = render(CallClass.ACTOR_COGNITION, p=p)[1].content
    return text.split("What you are in the middle of:\n", 1)[1].split("\nWho depends on you", 1)[0].splitlines()


def said_to(w, speaker, words, to, at):
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id(speaker), at=at, turn_index=0,
                              payload={"words": words, "volume": "normal", "to": [w.id(to)], "source_db": 70}))


def test_her_watch_at_the_window(scenario):
    w = scenario("metal_fence")
    p = packet_for(w, "mara", now(w))
    assert (p.commitments.current_task, p.commitments.plan_goal) == (None, "watch the front window")
    assert middle(p) == ["- What you set out to do: watch the front window",
                         "- Standing order: On loud noise: find the source and cover it."]


def test_spoken_to_she_is_still_at_it(scenario):
    w = scenario("metal_fence")
    t = now(w)
    said_to(w, "pc", "Mara, you good?", "mara", t + 500)
    p = packet_for(w, "mara", t + 1000)
    assert any(u.addressed_to_me for u in p.utterances)
    assert p.commitments.current_task is None, "she is not 'in the middle of nothing': she is watching the window"


def test_said_once(scenario):
    """A want already among her open loops ('I want: …', the owner's will) is not said again as her plan."""
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        why = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=0, payload={"what": "test"}))
        mind.open_loop(tx, w.id("mara"), "goal", "I want: watch the front window", [], 3, why.event_id, t, 0)
    p = packet_for(w, "mara", t)
    assert p.commitments.plan_goal is None
    assert any("watch the front window" in ln.text for ln in p.open_loops)


def test_nothing_in_particular_when_it_is_so(scenario):
    w = scenario("request_firewall")
    t = now(w)
    with w.store.transaction() as tx:
        bodies.wake(tx, w.id("eli"), t, None, 0)
    p = packet_for(w, "eli", t)
    assert (p.commitments.plan_goal, p.commitments.plan_step, p.commitments.standing_orders) == (None, None, [])
    assert middle(p) == ["- Nothing in particular."]
