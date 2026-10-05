"""A word said is not a deed done (D-242). mind/memory.py build_aftermath self_experiences.

What a person did and felt this turn is written into their memory call line by line — and everything they said
ended with "I did it.": the speech's own completion, with no band to tell how it went, after the words themselves.
Speaking is said by the words.
"""

from __future__ import annotations

import helpers
import pytest

from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.mind import memory

pytestmark = pytest.mark.phase(6)


def test_she_said_it(scenario):
    w = scenario("metal_fence")
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    i = helpers.make_intent(w, "june", "speak", speech=("Quiet. Something's out back.", ["everyone"], "low"))
    with w.store.transaction() as tx:
        evs = resolve_wave(tx, w.rng, barrier(tx, [i]), t, 0, horizon_ms=t + 30_000)
        assert any(e.type == "ACTION_COMPLETE" for e in evs)
        a = memory.build_aftermath(tx, w.id("june"), 0, t + 30_000)
    said = [x.text for x in a.self_experiences]
    assert said == ['I said: "Quiet. Something\'s out back."']
