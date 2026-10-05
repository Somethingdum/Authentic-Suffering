"""A hash that keeps up (D-223). kernel/hashing.py APPEND_ONLY, table_digest, the state hashes.

Every turn took full_state_hash twice (pipeline S2 and S19), and it read every event, percept and rng draw of the
whole run: a thousand turns in, the hashes alone cost seconds a turn. Now the digest of a table that is only ever
added to is carried forward and only what was added since is read — and it is always the same digest a cold
reading gives.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.events import Event, EventType
from as_engine.kernel import hashing
from as_engine.kernel.rng import Rng
from as_engine.kernel.store import Store

pytestmark = pytest.mark.phase(0)


def note(tx, what, at=0):
    tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=at, turn_index=0, payload={"what": what}))


def cold(s):
    s.__dict__.pop("_append_digests", None)
    return hashing.full_state_hash(s), hashing.world_state_hash(s)


def warm(s):
    return hashing.full_state_hash(s), hashing.world_state_hash(s)


def test_carried_forward_is_what_a_cold_reading_gives():
    s = Store.memory(run_id="r", seed=3)
    with s.transaction() as tx:
        for i in range(20):
            note(tx, f"first {i}", i)
    warm(s)
    with s.transaction() as tx:
        for i in range(5):
            note(tx, f"then {i}", 100 + i)
        Rng(3).d10(tx, "test", "x")
    w = warm(s)
    assert s._append_digests["events"][0] == s.query_one("SELECT COUNT(*) FROM events")[0], "carried, not reread"
    assert w == cold(s)
    s.close()


def test_a_rolled_back_turn_is_not_carried():
    """The S2 hash is taken inside the turn's transaction; when the turn is rolled back and other events take the same
    rows, the carried digest must not survive it."""
    s = Store.memory(run_id="r", seed=3)
    with s.transaction() as tx:
        note(tx, "before")
    warm(s)
    with pytest.raises(RuntimeError):
        with s.transaction() as tx:
            note(tx, "a turn that fails", 5)
            hashing.full_state_hash(s)
            raise RuntimeError("the turn fails")
    with s.transaction() as tx:
        note(tx, "what happened instead", 6)
    assert warm(s) == cold(s)
    s.close()


def test_order_and_content_still_count():
    a, b = Store.memory(run_id="r", seed=3), Store.memory(run_id="r", seed=3)
    with a.transaction() as tx:
        note(tx, "one")
        note(tx, "two")
    with b.transaction() as tx:
        note(tx, "one")
        note(tx, "three")
    warm(a), warm(b)
    assert hashing.full_state_hash(a) != hashing.full_state_hash(b)
    assert hashing.table_digest(a, "events") != hashing.table_digest(b, "events")
    a.close()
    b.close()
