"""State hashing (P0). Implemented canonicalisation rules; table iteration is yours to write.

Hash algorithm (must be exactly this; D-223 made it a hash of table digests so that a turn's hash no longer
reads the whole history):
  table digest of a table = sha256 over b"T:" + name + b"\n", then each row encoded as
      canonical_json(list(row values in column order)) + b"\n", the rows ordered by the table's
      primary key columns (rowid order for tables without an explicit PK) — except the APPEND_ONLY
      tables (rows only ever inserted: events, percept_log, prng_ledger), whose rows go in rowid
      (insertion) order, so the digest of what was already there is carried forward and only the rows
      added since are read.
  state hash = sha256 over, for each included table in sorted(table name) order:
      b"T:" + name + b"\n" + table digest (hex) + b"\n".
  SQLite REAL values are formatted with repr(float) by canonical_json.
  The carried-forward digest of an APPEND_ONLY table is used only when the row it ended on is still
  there with the same content and the table holds exactly the rows it counted plus those after it
  (a rolled-back transaction, or anything else, recomputes it whole).
Excluded tables: see kernel.ownership WORLD_HASH_EXCLUDED / FULL_HASH_EXCLUDED, plus sqlite
internal tables and FTS shadow tables (names starting with 'episodes_fts').
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .store import Store


def _tables(store):
    return [r[0] for r in store.query("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'episodes_fts%' ORDER BY name")]


APPEND_ONLY: tuple[str, ...] = ("events", "percept_log", "prng_ledger")   # D-223: rows are only ever inserted


def _digest_into(h, store, t):
    from .jsoncanon import canonical_json
    cols = store.query(f"PRAGMA table_info({t})")
    pk = [c[1] for c in sorted([c for c in cols if c[5]], key=lambda c: c[5])]
    order = ",".join(pk) if pk else "rowid"
    h.update(b"T:" + t.encode() + b"\n")
    for row in store.query(f"SELECT * FROM {t} ORDER BY {order}"):
        h.update(canonical_json(list(row)).encode() + b"\n")


def _append_digest(store, t):
    """D-223: the digest of an APPEND_ONLY table, carried forward from the last time it was taken."""
    import hashlib
    from .jsoncanon import canonical_json
    cache = store.__dict__.setdefault("_append_digests", {})
    n = store.query_one(f"SELECT COUNT(*) FROM {t}")[0]
    got = cache.get(t)
    h, start, have = None, 0, 0
    if got is not None:
        cn, crow, cbytes, ch = got
        last = store.query_one(f"SELECT * FROM {t} WHERE rowid=?", (crow,)) if crow else None
        if n >= cn and (crow == 0 or (last is not None and canonical_json(list(last)).encode() == cbytes)):
            h, start, have = ch.copy(), crow, cn
    if h is None:
        h = hashlib.sha256()
        h.update(b"T:" + t.encode() + b"\n")
    rows = store.query(f"SELECT rowid, * FROM {t} WHERE rowid>? ORDER BY rowid", (start,))
    if have + len(rows) != n:                                # not only appended: take it whole
        h = hashlib.sha256()
        h.update(b"T:" + t.encode() + b"\n")
        rows = store.query(f"SELECT rowid, * FROM {t} ORDER BY rowid")
        start = 0
    last_row, last_bytes = start, (got[2] if got is not None and start else b"")
    for r in rows:
        b = canonical_json(list(r)[1:]).encode()
        h.update(b + b"\n")
        last_row, last_bytes = r[0], b
    cache[t] = (n, last_row, last_bytes, h.copy())
    return h.hexdigest()


def _hash(store, excluded):
    import hashlib
    h = hashlib.sha256()
    for t in _tables(store):
        if t in excluded:
            continue
        h.update(b"T:" + t.encode() + b"\n" + table_digest(store, t).encode() + b"\n")
    return h.hexdigest()


def world_state_hash(store: "Store") -> str:
    from .ownership import WORLD_HASH_EXCLUDED
    return _hash(store, WORLD_HASH_EXCLUDED)


def full_state_hash(store: "Store") -> str:
    from .ownership import FULL_HASH_EXCLUDED
    return _hash(store, FULL_HASH_EXCLUDED)


def table_digest(store: "Store", table: str) -> str:
    """sha256 of one table (same row encoding). Used by the state hashes, the commit gate and diagnostics."""
    import hashlib
    if table in APPEND_ONLY:
        return _append_digest(store, table)
    h = hashlib.sha256()
    _digest_into(h, store, table)
    return h.hexdigest()
