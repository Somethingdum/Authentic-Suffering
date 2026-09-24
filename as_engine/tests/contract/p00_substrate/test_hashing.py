"""State hashing (P0). Rules DET-01, DET-02 (hash definitions)."""

from __future__ import annotations

import pytest

from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.kernel.hashing import full_state_hash, table_digest, world_state_hash
from as_engine.kernel.rng import Rng
from as_engine.kernel.store import Store

pytestmark = pytest.mark.phase(0)


def _zone(tx, zid):
    tx.commit_event(Event(type=EventType.PLACE_DISCOVERED, writer="physical.space", at=0, turn_index=0,
                          writes=[WriteRecord(op=WriteOp.INSERT, table="zones",
                                              values={"zone_id": zid, "name": "Z", "kind": "rural", "danger": {}})]))


def test_hashes_are_hex_sha256_and_deterministic():
    a, b = Store.memory(run_id="r", seed=3), Store.memory(run_id="r", seed=3)
    for s in (a, b):
        with s.transaction() as tx:
            _zone(tx, "zon_000001")
    for fn in (world_state_hash, full_state_hash):
        ha, hb = fn(a), fn(b)
        assert ha == hb and len(ha) == 64 and all(c in "0123456789abcdef" for c in ha)
    assert table_digest(a, "zones") == table_digest(b, "zones")
    a.close()
    b.close()


def test_bookkeeping_is_outside_world_hash_but_inside_full_hash():
    """DET-01 vs DET-02: an rng draw (bookkeeping) changes full_state_hash, not world_state_hash;
    a world write changes both."""
    s = Store.memory(run_id="r", seed=3)
    w0, f0 = world_state_hash(s), full_state_hash(s)
    with s.transaction() as tx:
        Rng(3).d10(tx, "test", "x")
    w1, f1 = world_state_hash(s), full_state_hash(s)
    assert w1 == w0 and f1 != f0
    with s.transaction() as tx:
        _zone(tx, "zon_000001")
    assert world_state_hash(s) != w1 and full_state_hash(s) != f1
    s.close()


def test_hash_depends_on_row_content():
    a, b = Store.memory(run_id="r", seed=3), Store.memory(run_id="r", seed=3)
    with a.transaction() as tx:
        _zone(tx, "zon_000001")
    with b.transaction() as tx:
        _zone(tx, "zon_000002")
    assert world_state_hash(a) != world_state_hash(b)
    a.close()
    b.close()
