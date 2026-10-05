"""Words only (D-151). Rule INTENT-10 (action/intent.py to_intent).

A model asked what a person says often writes what they do as well — "*sighs* Fine. (She looks away.)" — and
the narration then had to quote the stage directions as speech. Now a model's speech is what is said aloud:
asterisks, brackets and parentheses are dropped. The player's own words are never touched.
"""

from __future__ import annotations

import pytest

import helpers
from as_engine.action.intent import Intent, IntentError, to_intent
from as_engine.contracts.common import LOD
from as_engine.contracts.events import Event, EventType
from as_engine.contracts.mind import ActionPayload, SpeechOut
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet

pytestmark = pytest.mark.phase(4)


@pytest.fixture
def june(scenario):
    w = scenario("metal_fence")
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=t + 1500, turn_index=0,
                              actor_id=w.id("mara"), payload={"words": "June, stay where you are.", "volume": "raised",
                                                             "to": [w.id("june")], "source_db": 70}))
        perception.compile_scene(tx, w.id("june"), t + 2000, 0)
        aff = enumerate_affordances(tx, w.id("june"), w.canon.all("affordance"), t + 2000, 0)
        pkt = build_packet(tx, w.id("june"), LOD.HOT, aff, 0, t + 2000)
    return pkt, aff


def say(pkt, aff, text, choice="speak", source="model"):
    h = helpers.handle_for(pkt, choice)
    return to_intent(pkt, aff, ActionPayload(choice=h, goal="Answer her", speech=SpeechOut(text=text, to=["everyone"])),
                     lod=LOD.HOT, source=source)


@pytest.mark.parametrize("raw, said", [
    ("*sighs* Fine. I'm staying.", "Fine. I'm staying."),
    ('"Okay." (She looks at the door.) [quietly] "Okay."', "Okay. Okay."),
    ("  Where   is   everybody?  ", "Where is everybody?"),
])
def test_only_the_words_are_said(june, raw, said):
    pkt, aff = june
    it = say(pkt, aff, raw)
    assert isinstance(it, Intent) and it.speech.text == said


def test_nothing_but_a_direction_is_nothing_said(june):
    pkt, aff = june
    it = say(pkt, aff, "*nods slowly*")
    assert isinstance(it, IntentError) and it.kind == "empty"
    it2 = say(pkt, aff, "*nods*", choice="wait_here")
    assert isinstance(it2, Intent) and it2.speech is None


def test_the_players_words_are_their_own(june):
    pkt, aff = june
    it = say(pkt, aff, "*waves* Hi.", source="human")
    assert isinstance(it, Intent) and it.speech.text == "*waves* Hi."
