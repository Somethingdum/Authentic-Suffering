"""Of him (D-170). narration/narrator.py lines (third_limited).

The story's own lines about the player's character said "Owen chose to hit it", but what he perceived came as it
was perceived — "A walker lunges and grabs at you.", "sinks its teeth into you" — so the Writer was handed one man
in two persons, and the plain telling the player reads when the Writer fails mixed them. Now, in a third-person
story, what Owen perceived is told of Owen too; quoted words stay as they were said.
"""

from __future__ import annotations

import pytest

from as_engine.mind import perception
from as_engine.narration.narrator import build_narrator_packet

pytestmark = pytest.mark.phase(7)


def lines(w, settings, texts):
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        for i, x in enumerate(texts):
            perception.grant(tx, w.id("pc"), event_id=f"test:{i}", channel="visual", fidelity="exact", text=x, source_id=None,
                             at=t + i, turn_index=0)
        return [ln.text for ln in build_narrator_packet(tx, w.id("pc"), 0, t, settings).lines]


def test_told_of_owen(scenario):
    w = scenario("metal_fence")
    sex = w.store.query_one("SELECT sex FROM bodies WHERE body_id = ?", (w.id("pc"),))[0]
    him, his = {"male": ("him", "his"), "female": ("her", "her")}.get(sex, ("them", "their"))
    got = lines(w, w.session().settings, ["A walker lunges and grabs at you.", "Its teeth close on your left arm.",
                                          'Someone wrote on the wall: "you are next".'])
    assert f"A walker lunges and grabs at {him}." in got
    assert f"Its teeth close on {his} left arm." in got
    assert 'Someone wrote on the wall: "you are next".' in got, "quoted words are left as they were written"


def test_a_second_person_story_keeps_you(scenario):
    w = scenario("metal_fence")
    s = w.session()
    got = lines(w, s.settings.model_copy(update={"narration_person": "second"}), ["A walker lunges and grabs at you."])
    assert "A walker lunges and grabs at you." in got
