"""State hashing (P0). Implemented canonicalisation rules; table iteration is yours to write.

Hash algorithm (must be exactly this):
  sha256 over, for each included table in sorted(table name) order:
      b"T:" + name + b"\n"
      then each row ordered by the table's primary key columns (rowid order for tables without
      an explicit PK), encoded as canonical_json(list(row values in column order)) + b"\n".
  SQLite REAL values are formatted with repr(float) by canonical_json.
Excluded tables: see kernel.ownership WORLD_HASH_EXCLUDED / FULL_HASH_EXCLUDED, plus sqlite
internal tables and FTS shadow tables (names starting with 'episodes_fts').
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .store import Store


def world_state_hash(store: "Store") -> str:
    raise NotImplementedError("P0")


def full_state_hash(store: "Store") -> str:
    raise NotImplementedError("P0")


def table_digest(store: "Store", table: str) -> str:
    """sha256 of one table (same row encoding). Used by the commit gate and diagnostics."""
    raise NotImplementedError("P0")
