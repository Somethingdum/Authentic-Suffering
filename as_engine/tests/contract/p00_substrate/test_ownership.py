"""Table ownership (P0). Rules STORE-03, SCOPE-01."""

from __future__ import annotations

import re

import pytest

from as_engine.kernel.ownership import (
    BOOKKEEPING_TABLES,
    FULL_HASH_EXCLUDED,
    MODULES,
    TABLE_OWNERS,
    WORLD_HASH_EXCLUDED,
)
from as_engine.kernel.store import SCHEMA_PATH

pytestmark = pytest.mark.phase(0)


def _schema_owners() -> dict[str, str]:
    owners, pending = {}, None
    for line in SCHEMA_PATH.read_text(encoding="utf-8").splitlines():
        m = re.match(r"--\s*OWNER\s+([a-z_.]+)", line.strip())
        if m:
            pending = m.group(1)
            continue
        t = re.match(r"CREATE\s+TABLE\s+(\w+)", line.strip(), re.I)
        if t:
            owners[t.group(1)] = pending
            pending = None
    return owners


def test_schema_owner_comments_match_table_owners():
    """STORE-03: every CREATE TABLE has an OWNER comment and the map equals TABLE_OWNERS."""
    so = _schema_owners()
    missing = [t for t, o in so.items() if o is None]
    assert not missing, f"tables without an OWNER comment: {missing}"
    assert so == TABLE_OWNERS


def test_hash_exclusion_sets_are_consistent():
    assert BOOKKEEPING_TABLES <= set(TABLE_OWNERS)
    assert WORLD_HASH_EXCLUDED == BOOKKEEPING_TABLES
    assert FULL_HASH_EXCLUDED < BOOKKEEPING_TABLES
    assert "events" not in FULL_HASH_EXCLUDED and "prng_ledger" not in FULL_HASH_EXCLUDED
    assert set(MODULES) == set(TABLE_OWNERS.values())
