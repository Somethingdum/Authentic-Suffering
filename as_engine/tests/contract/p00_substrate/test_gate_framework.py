"""The 58-bit commit gate framework (P0). Rule AUDIT-01 (the fault-injection proof is P11)."""

from __future__ import annotations

import pytest

from as_engine.audit.commit_gate import ALL_BITS, ENTITY_BITS, GLOBAL_BITS, SESSION_BITS, WORLD_BITS, compute

pytestmark = pytest.mark.phase(0)


def test_bit_catalogue_shape():
    """AUDIT-01: 12 + 16 + 16 + 14 = 58 bits with unique ids."""
    assert (len(SESSION_BITS), len(WORLD_BITS), len(ENTITY_BITS), len(GLOBAL_BITS)) == (12, 16, 16, 14)
    ids = [b.id for b in ALL_BITS]
    assert len(set(ids)) == 58


def test_empty_world_passes_every_bit(store):
    """AUDIT-01: on a fresh store at turn 0 every check is vacuously true (genesis rules)."""
    with store.transaction() as tx:
        r = compute(tx, 0)
    assert (len(r.session), len(r.world), len(r.entities), len(r.global_)) == (12, 16, 16, 14)
    assert set(r.session + r.world + r.entities + r.global_) == {"1"}, r.failures
    assert r.passed and r.failures == []
    assert r.bit("W08") == 1 and r.bit("G12") == 1


def test_gate_is_computed_by_code_on_the_store_only(store):
    """L13: compute takes a store/tx and a turn index — no model, no transport."""
    import inspect

    params = list(inspect.signature(compute).parameters)
    assert params == ["store_or_tx", "turn_index"]
