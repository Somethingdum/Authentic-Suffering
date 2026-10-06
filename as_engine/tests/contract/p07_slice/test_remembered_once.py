"""Remembered once (D-285). mind/memory.py MEM-01 (own_action_text, self_experiences: what the holder did itself).

Owen said one thing to Mara; his memory of the turn was handed it as three — 'O1: I said: "Mara, I need you on the
front window"', 'O2: I said: "while I check the back"', 'O3: I said: "door and the alley."' — three of the things he
did, to cite one by one, for one sentence. What he said once, he remembers saying once.
"""

from __future__ import annotations

import pytest

from as_engine.mind import memory

from slice_kit import play

pytestmark = pytest.mark.phase(7)

WORDS = "Mara, I need you on the front window while I check the back door and the alley."


def test_one_sentence_remembered_once(scenario):
    w = scenario("metal_fence")
    s = w.session()
    s.extras["forced_addressee"] = w.id("mara")
    assert play(s, "say", "Quiet.").ok
    s.extras["forced_addressee"] = w.id("mara")
    o = play(s, "say", WORDS)
    assert o.ok
    assert w.store.query("SELECT COUNT(*) FROM events WHERE type='SPEECH' AND actor_id=? AND turn_index=?",
                         (w.id("pc"), o.turn_index))[0][0] >= 2, "it was said in pieces"
    at = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        a = memory.build_aftermath(tx, w.id("pc"), o.turn_index, at)
    assert a.own_action_text == f'Said: "{WORDS}"', a.own_action_text
    said = [x for x in a.self_experiences if x.text.startswith("I said")]
    assert [x.text for x in said] == [f'I said: "{WORDS}"'], a.self_experiences
