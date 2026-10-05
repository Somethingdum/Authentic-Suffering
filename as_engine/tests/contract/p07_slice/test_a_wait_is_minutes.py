"""A wait is minutes (D-174). Rule HOR-01 (turn/select.py horizon: duration.max_s, until); contracts/content.py
DurationSpec.max_s; core wait_here.

"Stay where you are and do nothing yet" ran until something happened — and in a quiet place nothing does, so every
"I wait." the player typed passed eight hours: three of them were a whole day, with everyone standing where they
stood. Waiting is a few minutes now; watching ("Wait and watch") still runs until something happens.
"""

from __future__ import annotations

import helpers
import pytest
from slice_kit import pick, play

from as_engine.contracts.common import CallClass
from as_engine.turn import select

pytestmark = pytest.mark.phase(7)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def test_the_horizon_of_a_wait(scenario):
    w = scenario("metal_fence")
    t = now(w) + 60_000
    with w.store.transaction() as tx:
        assert w.canon.find("affordance", "wait_here").duration.max_s == 300
        assert select.horizon(tx, helpers.make_intent(w, "pc", "wait_here"), t) == t + 300_000
        assert select.horizon(tx, helpers.make_intent(w, "pc", "observe_area"), t) == t + select.MAX_WINDOW_MS, \
            "watching still runs until something happens"
        assert select.horizon(tx, helpers.make_intent(w, "pc", "wait_here"), t, until=t + 7_200_000) == t + 7_200_000, \
            "OUT-02: out cold, until he comes to"


def test_i_wait(scenario, fake):
    w = scenario("metal_fence")
    s = w.session()
    for _ in range(3):
        fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "wait_here"), "none_reason": None, "manner": "",
                                                "remainder": None, "clarify": None})
        t0 = now(w)
        assert play(s, "do", "I wait.").ok
        assert now(w) - t0 <= 300_000, "a few minutes, not the night"
