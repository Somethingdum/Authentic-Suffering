"""The Store: one SQLite file per run, the only writer (P0). docs/as/03_DATA_MODEL.md.

Rules enforced here:
  STORE-01 world tables change only through ``Tx.commit_event`` WriteRecords.
  STORE-02 a WriteRecord's table must be owned by the event's ``writer`` (else ScopeError).
  STORE-03 TABLE_OWNERS matches schema.sql OWNER comments (tested statically).
  STORE-04 ``Store.open`` refuses a file whose meta.schema_version != SCHEMA_VERSION.
  STORE-05 unknown EventType -> UnknownEventType.
  STORE-06 ids come from kernel.ids.mint only.
  STORE-07 a transaction is atomic: any exception inside ``with store.transaction()`` rolls back
           every write (world tables AND bookkeeping) made in it.
           "Any exception" includes BaseException (P8): an asyncio.CancelledError — the Play UI's Stop
           cancels a running turn — or a KeyboardInterrupt rolls back too; otherwise the connection stays
           inside an open transaction and every later BEGIN fails.
  STORE-08 ``events`` is append-only: UPDATE/DELETE on it raise StoreError.
  STORE-11 a write value equal to EVENT_SELF becomes the committing event's own id (below).

Connection settings: ``isolation_level=None`` (manual BEGIN), ``PRAGMA journal_mode=WAL``,
``PRAGMA foreign_keys=ON``, ``PRAGMA synchronous=NORMAL``, ``row_factory=sqlite3.Row``.
Memory stores (tests) use ``:memory:`` and skip WAL.

WriteRecord application (``Tx.commit_event``):
  * INSERT: ``INSERT INTO t (cols) VALUES (...)`` with key ∪ values. Duplicate PK -> StoreError.
  * UPDATE: ``UPDATE t SET values WHERE key``; zero rows affected -> StoreError (rule STORE-09).
  * UPSERT: INSERT ... ON CONFLICT(pk) DO UPDATE SET values.
  * DELETE: ``DELETE FROM t WHERE key``; zero rows -> StoreError.
  * dict/list values are serialised with jsoncanon.canonical_json; bool -> 0/1.
  * ``event_id`` is minted with kind 'evt' BEFORE the writes are applied, and a value that is
    exactly EVENT_SELF ('$event_id') — a top-level column value in ``values`` — is replaced by it
    (STORE-11): a row can name the event that made it (open_loops.created_event,
    refusals.created_event, lessons.source_event …). The replaced value is what ``state_delta``
    records, so replay re-applies the same row.
  * the events row stores ``state_delta`` = canonical_json([w.model_dump(mode='json') ...]) of the
    writes as applied.
  * ``event.seq`` = previous max seq + 1 (starting at 1).

Run context (STORE-10): modules that need content or rule numbers read them from the store they
were handed, never from globals: ``store.canon`` (content.pack.Canon, attached by Session /
ScenarioWorld / worldgen; ``None`` in kernel-only tests) and ``store.rules`` (RulesConfig; the
defaults unless attached). ``Tx`` exposes the same two attributes (``tx.canon``, ``tx.rules``).
Example: physical.objects.transfer reads container capacity from
``tx.canon.get(item.def_ref).container.capacity_bulk``.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

from ..contracts.events import Event, WriteOp

if TYPE_CHECKING:
    pass

SCHEMA_VERSION = 1
EVENT_SELF = "$event_id"   # STORE-11: a write value naming the committing event itself
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def wall_clock_iso() -> str:
    """The engine's one wall-clock read (implemented): UTC 'YYYY-MM-DDTHH:MM:SSZ' from SQLite's own
    clock, so no engine module imports time or datetime (tools/as/gate.py --scan forbids it outside
    lanes/). Used for meta.created_at_real (Store.create) and the run manifests (service.runs) —
    never for world time, which is kernel.clock's alone (TIME-01)."""
    conn = sqlite3.connect(":memory:")
    try:
        return conn.execute("SELECT strftime('%Y-%m-%dT%H:%M:%SZ', 'now')").fetchone()[0]
    finally:
        conn.close()


class Store:
    """Owns the sqlite3 connection. Construct with ``create``/``open``/``memory`` only."""

    def __init__(self, conn: sqlite3.Connection, path: str):
        self.conn = conn
        self.path = path
        self.canon: Any = None  # content.pack.Canon (STORE-10)
        from ..contracts.settings import RulesConfig
        self.rules: RulesConfig = RulesConfig()

    def attach(self, *, canon: Any = None, rules: Any = None) -> "Store":
        """Attach run context (implemented). Returns self."""
        if canon is not None:
            self.canon = canon
        if rules is not None:
            self.rules = rules
        return self

    @classmethod
    def create(cls, path: str | Path, *, run_id: str, seed: int, settings_json: str = "{}",
               content_hash: str = "", start_ms: int = 0, rules_json: str = "{}") -> "Store":
        """Create a new run DB: apply schema.sql, write meta rows (run_id, seed, schema_version,
        created_at_real (= wall_clock_iso(), the ONLY wall-clock value in the DB), content_hash,
        settings_json, rules_json, pc_actor_id='', sandbox='0', cheat_active='0',
        world_epoch_text='Day 0 of the Fall'), world_clock row (1, start_ms, 0, 'clear', 0) and
        narrator_state row (1, canonical_json(NarratorStyle().model_dump(mode='json'))) — the only
        world rows written outside events, because every store starts with them. Refuses to
        overwrite an existing file (StoreError). ``rules_json`` freezes the RulesConfig the run
        was created with (SET-03): later edits to as_config.yaml rules apply to NEW runs only, so
        replay stays exact. ``memory()`` writes the same meta rows (created_at_real =
        '1970-01-01T00:00:00Z' so tests are deterministic)."""
        raise NotImplementedError("P0")

    @classmethod
    def open(cls, path: str | Path) -> "Store":
        raise NotImplementedError("P0")

    @classmethod
    def memory(cls, *, run_id: str = "test_run", seed: int = 1, start_ms: int = 0) -> "Store":
        raise NotImplementedError("P0")

    def close(self) -> None:
        raise NotImplementedError("P0")

    @contextmanager
    def transaction(self) -> Iterator["Tx"]:
        """BEGIN IMMEDIATE ... COMMIT; ROLLBACK on any exception (re-raised). Nesting raises StoreError."""
        raise NotImplementedError("P0")
        yield  # pragma: no cover

    def query(self, sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
        raise NotImplementedError("P0")

    def query_one(self, sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
        raise NotImplementedError("P0")

    def meta(self, key: str) -> str | None:
        raise NotImplementedError("P0")

    def backup_to(self, path: str | Path) -> None:
        """Consistent copy via sqlite3 backup API (used by saves)."""
        raise NotImplementedError("P0")

    def rebuild_fts(self) -> None:
        """Rebuild the episodes full-text index from ``episodes`` (implemented; used by
        service.runs.load_run, RUN-05). episodes_fts is a derived index kept by schema triggers,
        never a world table, so this is the one statement that bypasses ``Tx``."""
        self.conn.execute("INSERT INTO episodes_fts(episodes_fts) VALUES('rebuild')")


class Tx:
    """A live transaction. All writes go through ``commit_event`` or ``bookkeep``."""

    def __init__(self, store: Store):
        self.store = store
        self.events: list[Event] = []  # events committed in this transaction, in order

    @property
    def canon(self) -> Any:
        return self.store.canon

    @property
    def rules(self) -> Any:
        return self.store.rules

    def commit_event(self, event: Event) -> Event:
        """Validate + apply ``event.writes`` + append the events row. Returns a copy with
        ``event_id`` and ``seq`` filled. See module docstring for rules."""
        raise NotImplementedError("P0")

    def citing(self, rule_id: str, depth: int):
        """P5 (cascade, G10). Context manager: every event committed inside the ``with`` block
        whose rule_cited is None gets rule_cited = rule_id and payload['_cascade_depth'] = depth
        (nested blocks: the innermost wins). Used by action.cascade around each dispatch so owner
        modules need no cascade parameters."""
        raise NotImplementedError("P5")

    def bookkeep(self, owner: str, table: str, op: WriteOp, key: dict[str, Any], values: dict[str, Any]) -> None:
        """Direct write to a BOOKKEEPING table (ownership checked; world tables -> StoreError STORE-01)."""
        raise NotImplementedError("P0")

    def mint(self, kind: str) -> str:
        raise NotImplementedError("P0")

    def query(self, sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
        raise NotImplementedError("P0")

    def query_one(self, sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
        raise NotImplementedError("P0")
