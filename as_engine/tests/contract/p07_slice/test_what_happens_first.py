"""What happens first, happens first (D-177). Rule RESOLVE-08 (action/resolve.py resolve_wave land_by; turn/pipeline.py
S8), with HOR-02..03 (turn/select.py pull).

Playing a soak: "I search the alley." — a two-minute search. The search's end was committed the moment it began, at
its landing two minutes on; then a walker came round the corner two seconds in, grabbed him and bit him, again and
again — and the window could not close for the player to answer, because it may never close before something already
committed (HOR-03). He searched on for two minutes while he was eaten, and died without a say. Now a landing after the
world's next timer waits in the queue and lands in time order: the shout two seconds in comes first, the window closes
so the player can answer, and the search is still going when it does.
"""

from __future__ import annotations

import pytest
from slice_kit import pick, play

from as_engine.contracts.common import CallClass
from as_engine.kernel import clock

pytestmark = pytest.mark.phase(7)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def searching(w, fake):
    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "search_place"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})


def test_a_shout_two_seconds_into_a_long_search(scenario, fake):
    w = scenario("metal_fence")
    s = w.session()
    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "wait_here"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    assert play(s, "do", "I wait.").ok                                  # the crash out back has come and gone
    t0 = now(w)
    with w.store.transaction() as tx:
        clock.schedule(tx, t0 + 2000, "NOISE", None, {"source_db": 95, "kind": "shout", "text": "a shout",
                                                       "place_id": w.id("sales_floor"), "x_m": 3.0, "y_m": 3.0}, None)
    searching(w, fake)
    assert play(s, "do", "I search the place.").ok
    assert now(w) - t0 < 10_000, "the window closed on the shout so the player can answer, not two minutes on"
    T = w.store.query_one("SELECT MAX(turn_index) FROM turn_ledger")[0]
    done = w.store.query("SELECT 1 FROM events WHERE type = 'ACTION_COMPLETE' AND actor_id = ? AND turn_index = ? "
                         "AND json_extract(payload, '$.def_id') = 'search_place'", (s.pc_id, T))
    assert not done, "the search was not over when he heard it"
    assert w.store.query("SELECT 1 FROM event_queue WHERE type = 'ACTION_LAND' AND subject_id = ? AND status = 'pending'",
                         (s.pc_id,)), "it is still going; the player decides whether it goes on"


def test_nothing_in_the_way(scenario, fake):
    """No timer before the landing: the act lands in the wave, as it always did."""
    w = scenario("metal_fence")
    s = w.session()
    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "wait_here"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    assert play(s, "do", "I wait.").ok
    t0 = now(w)
    searching(w, fake)
    assert play(s, "do", "I search the place.").ok
    T = w.store.query_one("SELECT MAX(turn_index) FROM turn_ledger")[0]
    assert w.store.query("SELECT 1 FROM events WHERE type = 'ACTION_COMPLETE' AND actor_id = ? AND turn_index = ? "
                         "AND json_extract(payload, '$.def_id') = 'search_place'", (s.pc_id, T))
    assert now(w) - t0 >= 60_000
