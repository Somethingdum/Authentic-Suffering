"""The world's words (D-169). narration/narrator.py player_input_echo_block; narration/lint.py ECHO-01.

The echo rule keeps the story from parroting the player ("quoted back a thousand times"). But the player who typed
"I go out the back door into the alley" was given a story line of the world's own — "Owen chose to go through the
back door into the rear alley." — and every draft that used it was thrown away for echoing "the back door into".
What the world says itself is the narrator's to use; the player's own turns of phrase still are not.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.events import Event, EventType
from as_engine.narration import lint
from as_engine.narration.narrator import build_narrator_packet

pytestmark = pytest.mark.phase(7)


def test_the_back_door_is_the_worlds(scenario):
    w = scenario("metal_fence")
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        lint.record_pc_input(tx, 0, "I go out the back door into the alley, quick as a stray cat.", tx.rules.style)
        tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=t, turn_index=0, actor_id=w.id("pc"),
                              payload={"actor_id": w.id("pc"), "def_id": "move_through_portal", "verb": "move",
                                       "label": "Go through the back door into the rear alley (about 4 seconds)"}))
        k = build_narrator_packet(tx, w.id("pc"), 0, t, w.session().settings)
    assert any("back door" in x.text for x in k.lines)
    assert not any(g in ("back door into the", "the back door into") for g in k.player_input_echo_block), k.player_input_echo_block
    assert any("stray cat" in g for g in k.player_input_echo_block), "the player's own words are still theirs"
