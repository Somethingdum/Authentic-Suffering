"""Turns that stay fast (D-224). audit/commit_gate.py (history checked once: _carried / _carry); kernel/schema.sql and
kernel/store.py LATER_INDEXES (percept_log(event_id), events(actor_id, type)); mind/perception.py GONE_LOOKBACK_MS.

Every turn the commit gate decoded every event, rng draw and blob the run had ever written, and every "who saw this
event" read the whole percept log: at 50 000 events a turn took twice as long as at the start, and it only got worse.
Now the gate reads only what the last passed gate did not see — never trusting that when the history behind it has
changed — and the lookups that were reading everything have the index they needed.
"""

from __future__ import annotations

import pytest

from slice_kit import play, script_night_at_delgados

from as_engine.audit.commit_gate import compute
from as_engine.kernel.store import LATER_INDEXES, Store

pytestmark = pytest.mark.phase(11)

T = 2


@pytest.fixture
def night(scenario, fake):
    """Two turns at Delgado's, played the ordinary way (as test_commit_gate_bits)."""
    w = scenario("metal_fence")
    script_night_at_delgados(w, fake)
    s = w.session()
    play(s, "do", "I watch the front window and keep quiet.")
    play(s, "do", "I keep watching the front window.")
    return w


def one(w, statement, args=()):
    return w.store.query_one(statement, args)


def raw_event(w, **cols):
    """An events row written behind the store's back, at the next seq."""
    seq = one(w, "SELECT MAX(seq) FROM events")[0] + 1
    row = {"event_id": f"evt_9{seq:05d}", "seq": seq, "at": one(w, "SELECT now_ms FROM world_clock")[0], "type": "NOISE",
           "writer": "action.propagate", "actor_id": None, "target_ids": "[]", "place_id": None, "cause_event_id": None,
           "payload": "{}", "state_delta": "[]", "rule_cited": None, "turn_index": T, "origin": "sim", "links": "[]"}
    row.update(cols)
    w.store.conn.execute(f"INSERT INTO events ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})", tuple(row.values()))


def test_the_gate_carries_what_it_has_seen(night):
    w = night
    assert compute(w.store, T).passed
    seen = w.store._gate_seen["events"]
    assert seen[0] == one(w, "SELECT MAX(seq) FROM events")[0] and seen[1] == one(w, "SELECT COUNT(*) FROM events")[0]


def test_a_rolled_back_turn_is_not_carried(night):
    """The gate passes inside a turn that then fails and rolls back; another event takes the same seq with a bad state
    delta. The carried boundary is not that event, so the gate looks again — and sees it (G09)."""
    w = night
    with pytest.raises(RuntimeError):
        with w.store.transaction() as tx:
            raw_event(w)
            assert compute(tx, T).passed
            raise RuntimeError("the turn fails after the gate")
    raw_event(w, state_delta="not a list")
    assert compute(w.store, T).failures == ["G09"]


def test_an_old_save_gets_the_indexes(tmp_path):
    p = tmp_path / "run.sqlite"
    s = Store.create(p, run_id="r", seed=1)
    for name in ("ev_actor_type", "percept_event"):
        s.conn.execute(f"DROP INDEX {name}")
    s.close()
    s = Store.open(p)
    have = {r[0] for r in s.query("SELECT name FROM sqlite_master WHERE type='index'")}
    assert {"ev_actor_type", "percept_event"} <= have and len(LATER_INDEXES) == 2
    s.close()
