"""In the right person (D-152). Rule TEXT-01 (mind/perception.py retell; narration/narrator.py, mind/memory.py,
service/death.py, service/voice.py).

A menu speaks to the one choosing ("Take your .38 revolver into your hand"), and its label went on word for word
into the story's own line ("Owen chose to take your .38 revolver into your hand." — what the Writer was given, and
what the player read whenever the Writer failed), into a person's own memory ("I chose to take your …") and into
what Willis is shown of everyone else's choices ("Mara Voss: Take your .38 revolver …", which reads as the player's
gun). Now each is told in its own person.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.events import Event, EventType
from as_engine.mind import memory
from as_engine.mind.perception import retell
from as_engine.narration.narrator import build_narrator_packet

pytestmark = pytest.mark.phase(7)


@pytest.mark.parametrize("label, first, he, she, they", [
    ("Take your .38 revolver into your hand", "Take my .38 revolver into my hand", "Take his .38 revolver into his hand",
     "Take her .38 revolver into her hand", "Take their .38 revolver into their hand"),
    ("Leave this place by the nearest way out you know", "Leave this place by the nearest way out I know",
     "Leave this place by the nearest way out he knows", "Leave this place by the nearest way out she knows",
     "Leave this place by the nearest way out they know"),
    ("Stay where you are and do nothing yet", "Stay where I am and do nothing yet", "Stay where he is and do nothing yet",
     "Stay where she is and do nothing yet", "Stay where they are and do nothing yet"),
    ("Keep doing what you were doing", "Keep doing what I was doing", "Keep doing what he was doing",
     "Keep doing what she was doing", "Keep doing what they were doing"),
    ("Break the man's grip on you", "Break the man's grip on me", "Break the man's grip on him",
     "Break the man's grip on her", "Break the man's grip on them"),
    ("Turn the Glock on yourself and end it", "Turn the Glock on myself and end it", "Turn the Glock on himself and end it",
     "Turn the Glock on herself and end it", "Turn the Glock on themselves and end it"),
    ("Stay put and watch everything you can see and hear", "Stay put and watch everything I can see and hear",
     "Stay put and watch everything he can see and hear", "Stay put and watch everything she can see and hear",
     "Stay put and watch everything they can see and hear"),
    ("Your call: what you never knew", "My call: what I never knew", "His call: what he never knew",
     "Her call: what she never knew", "Their call: what they never knew"),
    ("Climb over the high chain-link fence", "Climb over the high chain-link fence", "Climb over the high chain-link fence",
     "Climb over the high chain-link fence", "Climb over the high chain-link fence"),
])
def test_retell(label, first, he, she, they):
    assert [retell(label, "first"), retell(label, "third", "male"), retell(label, "third", "female"),
            retell(label, "third", None)] == [first, he, she, they]


def chose(w, who, label, def_id="equip_item"):
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=t, turn_index=0, actor_id=w.id(who),
                              payload={"actor_id": w.id(who), "def_id": def_id, "verb": "take", "label": label,
                                       "goal": "be ready"}))
    return t


def test_the_story_tells_it_of_owen(scenario):
    w = scenario("metal_fence")
    sex = w.store.query_one("SELECT sex FROM bodies WHERE body_id = ?", (w.id("pc"),))[0]
    t = chose(w, "pc", "Take your Glock 19 into your hand")
    with w.store.transaction() as tx:
        lines = [x.text for x in build_narrator_packet(tx, w.id("pc"), 0, t, w.session().settings).lines]
    told = {"male": "his", "female": "her"}.get(sex, "their")
    assert f"Owen chose to take {told} Glock 19 into {told} hand." in lines
    assert not any("your" in x for x in lines)


def test_a_memory_is_in_the_first_person(scenario):
    w = scenario("metal_fence")
    t = chose(w, "mara", "Take your .38 revolver into your hand (about 1 second)")
    with w.store.transaction() as tx:
        a = memory.build_aftermath(tx, w.id("mara"), 0, t + 1000)
    assert a.own_action_text == "Chose to take my .38 revolver into my hand."
    assert [s.text for s in a.self_experiences][:1] == ["I chose to take my .38 revolver into my hand."]
