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


def _tables(store):
    return [r[0] for r in store.query("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'episodes_fts%' ORDER BY name")]


def _digest_into(h, store, t):
    from .jsoncanon import canonical_json
    cols = store.query(f"PRAGMA table_info({t})")
    pk = [c[1] for c in sorted([c for c in cols if c[5]], key=lambda c: c[5])]
    order = ",".join(pk) if pk else "rowid"
    h.update(b"T:" + t.encode() + b"\n")
    for row in store.query(f"SELECT * FROM {t} ORDER BY {order}"):
        h.update(canonical_json(list(row)).encode() + b"\n")


def _hash(store, excluded):
    import hashlib
    h = hashlib.sha256()
    for t in _tables(store):
        if t in excluded:
            continue
        _digest_into(h, store, t)
    return h.hexdigest()


def world_state_hash(store: "Store") -> str:
    from .ownership import WORLD_HASH_EXCLUDED
    return _hash(store, WORLD_HASH_EXCLUDED)


def full_state_hash(store: "Store") -> str:
    from .ownership import FULL_HASH_EXCLUDED
    return _hash(store, FULL_HASH_EXCLUDED)


def table_digest(store: "Store", table: str) -> str:
    """sha256 of one table (same row encoding). Used by the commit gate and diagnostics."""
    import hashlib
    h = hashlib.sha256()
    _digest_into(h, store, table)
    return h.hexdigest()
