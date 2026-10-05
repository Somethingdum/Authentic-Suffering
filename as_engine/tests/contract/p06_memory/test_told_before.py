"""Told before (D-226). mind/memory.py build_aftermath 'told' (TOLD_MAX); prompts/writeback.*.j2.

Catching someone in a lie was a rule (CAS-010) that nothing could ever start, and AC09 left it, rightly, to the mind:
whether someone deceived you is your own judgment. But the mind never had what it needed to judge: what Owen told Mara
two hours ago was nowhere in front of her memory when June walked in from where he said she had gone. Now the memory
sees what she had been told about the people in front of her, and by whom — and what she only took from someone's
words is never worded as something they told her.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import CallClass
from as_engine.contracts.events import Event, EventType
from as_engine.mind import memory, perception
from as_engine.mind.perception import BeliefFromPercept
from as_engine.physical import space
from as_engine.prompts.render import render

pytestmark = pytest.mark.phase(6)

HOUR = 3_600_000
LIE = "June went out to the back lot."


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


@pytest.fixture
def told(scenario):
    """On a lit sales floor Owen tells Mara that June went out to the back lot, and Mara believes him (her memory forms
    it from his words). Nita told her June had the watch tonight. She also saw for herself that June was tired, and Nita
    told her someone was watching from the weeds out back."""
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("storeroom"), None, 3.0, 2.0, t, None, 0))
        ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("pc"), at=t, turn_index=0,
                                   payload={"words": "June went out the back to the lot.", "volume": "normal", "to": [w.id("mara")],
                                            "source_db": 60, "armed": False}))
        perception.compile_aftermath(tx, w.id("mara"), [ev], t + 500, 0)
        heard = tx.query_one("SELECT percept_id FROM percept_log WHERE holder_id = ? AND event_id = ?", (w.id("mara"), ev.event_id))[0]
        perception.infer(tx, w.id("mara"), about=("body", w.id("june")), text=LIE, confidence=2, because=[heard], at=t + 1000,
                         turn_index=0)
        perception.grant(tx, w.id("mara"), event_id="scene:test_watch", channel="speech", fidelity="exact",
                         text="June has the watch tonight.", source_id=w.id("nita"), at=t + 500, turn_index=0,
                         detail={"words": "June has the watch tonight.", "addressed_to_me": True},
                         beliefs=[BeliefFromPercept("body", w.id("june"), "duty", "June has the watch tonight.")])
        perception.grant(tx, w.id("mara"), event_id="scene:test_tired", channel="visual", fidelity="exact", text="June looks worn out.",
                         source_id=w.id("june"), at=t + 1000, turn_index=0,
                         beliefs=[BeliefFromPercept("body", w.id("june"), "tired", "June is worn out.")])
        perception.grant(tx, w.id("mara"), event_id="scene:test_weeds", channel="speech", fidelity="exact",
                         text="Someone is watching from the weeds.", source_id=w.id("nita"), at=t + 1000, turn_index=0,
                         detail={"words": "Someone is watching from the weeds.", "addressed_to_me": True},
                         beliefs=[BeliefFromPercept("body", w.id("stranger"), "whereabouts", "Someone is watching from the weeds.")])
    return w, t


def june_walks_in(w, t):
    """Two hours later June comes back onto the sales floor, in front of Mara."""
    at = t + 2 * HOUR
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("sales_floor"), None, 5.0, 4.0, at, None, 1))
        perception.compile_scene(tx, w.id("mara"), at, 1)
        return memory.build_aftermath(tx, w.id("mara"), 1, at + 1000), at + 1000


def test_her_memory_sees_what_she_was_told_about_june(told):
    w, t = told
    a, _at = june_walks_in(w, t)
    owen = next((h for h, v in a.handles.items() if v == w.id("pc")), None)
    nita = next((h for h, v in a.handles.items() if v == w.id("nita")), "Nita")
    assert owen is not None, "Owen is in front of her too"
    assert a.told == [f"From what {owen} said 2 hours ago, they believed: {LIE}",
                      f"{nita} told them 2 hours ago: June has the watch tonight."], a.told
    system, user = (m.content for m in render(CallClass.WRITEBACK, a=a, cue_ids=["bite_wound_seen"]))
    assert "WHAT THEY HAD BEEN TOLD BEFORE (it may not have been so)\n- " + a.told[0] + "\n- " + a.told[1] + "\n" in user
    assert "whether the one who told them lied or was only wrong is their own judgment" in system


def test_only_what_she_was_told_and_only_about_who_is_here(told):
    """What she saw for herself is not something she was told; what Nita said about the man in the weeds, who is not
    here, is not brought up by June walking in."""
    w, t = told
    a, _at = june_walks_in(w, t)
    assert w.id("stranger") not in a.handles.values()
    assert not any("worn out" in x or "weeds" in x for x in a.told), a.told


def test_said_this_turn_is_not_told_before(told):
    """In the turn it was said it is in front of her already, as what she heard."""
    w, t = told
    with w.store.transaction() as tx:
        a = memory.build_aftermath(tx, w.id("mara"), 0, t + 1500)
    assert a.told == []
