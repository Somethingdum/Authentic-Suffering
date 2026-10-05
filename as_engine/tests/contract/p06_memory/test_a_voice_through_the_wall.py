"""A voice through the wall (D-227). mind/memory.py worth_writing (MEM-20).

When Owen spoke in the pump house's back room, the ten people in the front room caught only that someone was talking
— the tone of a voice through the door, not one word — and every one of them was sent to the memory model to write it
down: ten calls and twenty-four thousand tokens of prompt to remember a muffled voice next door. A voice they could not
make out, not raised and not said to them, is not by itself worth a memory; it stays in what they perceived.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.events import Event, EventType
from as_engine.mind import memory, perception

pytestmark = pytest.mark.phase(6)

T = 3


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def heard(w, *, fidelity="tone_only", volume="normal", to_me=False, words="We leave at first light."):
    """Mara hears Owen speak, at turn T, and nothing else happens to her that turn; her aftermath."""
    t = now(w)
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("pc"), at=t, turn_index=T,
                                   payload={"words": words, "volume": volume, "to": [w.id("mara") if to_me else "everyone"],
                                            "source_db": 60, "armed": False}))
        text = "Someone is talking on the other side of the door." if fidelity == "tone_only" else f'Someone says, "{words}"'
        perception.grant(tx, w.id("mara"), event_id=ev.event_id, channel="speech", fidelity=fidelity, text=text, source_id=w.id("pc"),
                         at=t + 300, turn_index=T,
                         detail={"words": "" if fidelity == "tone_only" else words, "volume": volume, "addressed_to_me": to_me})
        a = memory.build_aftermath(tx, w.id("mara"), T, t + 1000)
        assert [u.fidelity.value for u in a.utterances] == [fidelity] and not a.percepts
        return memory.worth_writing(tx, w.id("mara"), a, T)


def test_a_muffled_voice_next_door_is_not_worth_a_memory(scenario):
    assert not heard(scenario("metal_fence"))


@pytest.mark.parametrize("change", [{"fidelity": "partial"}, {"fidelity": "exact"}, {"volume": "shout"}, {"volume": "raised"},
                                    {"to_me": True}])
def test_words_made_out_a_raised_voice_or_said_to_her_are(scenario, change):
    assert heard(scenario("metal_fence"), **change)
