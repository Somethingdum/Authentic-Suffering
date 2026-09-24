"""Deterministic ids (P0). Rule STORE-06."""

from __future__ import annotations

import pytest

from as_engine.kernel.ids import ID_KINDS, format_id

pytestmark = pytest.mark.phase(0)


def test_format_id_pins_the_format():
    """STORE-06: '<kind>_<6 digits>'."""
    assert format_id("act", 12) == "act_000012"
    assert format_id("plc", 3) == "plc_000003"
    with pytest.raises(ValueError):
        format_id("nope", 1)


def test_mint_is_per_kind_and_sequential(store):
    """STORE-06: n starts at 1 per kind; counters persist across transactions."""
    with store.transaction() as tx:
        assert [tx.mint("act") for _ in range(3)] == ["act_000001", "act_000002", "act_000003"]
        assert tx.mint("plc") == "plc_000001"
    with store.transaction() as tx:
        assert tx.mint("act") == "act_000004"
    row = store.query_one("SELECT next FROM counters WHERE kind = 'act'")
    assert row["next"] == 5


def test_every_kind_mints(store):
    with store.transaction() as tx:
        for k in ID_KINDS:
            assert tx.mint(k) == f"{k}_000001"


def test_mint_rejects_unknown_kind(store):
    with pytest.raises(ValueError):
        with store.transaction() as tx:
            tx.mint("xyz")
