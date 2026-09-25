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
  STORE-12 (fidelity C10, Actor v2 B5c) ``event.links`` — the causes besides the primary parent
           ``cause_event_id`` — are checked before anything is written: every link's event_id
           names an event already in the log (committed earlier, this transaction included),
           none is the event's own cause_event_id, none appears twice, and every role is in
           contracts.events.LINK_ROLES; else StoreError(rule 'STORE-12') and nothing is written.
           The events row stores ``links`` = canonical_json([link.model_dump(mode='json') ...]) in
           the given order, and kernel.events reads them back, so replay re-commits them unchanged.

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
EVENT_SELF = "$event_id"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def wall_clock_iso() -> str:
    """The engine's one wall-clock read (implemented): UTC 'YYYY-MM-DDTHH:MM:SSZ' from SQLite's own
    clock, so no engine module imports time or datetime (tools/as/gate.py --scan forbids it outside
    lanes/). Used for meta.created_at_real (Store.create) and the run manifests (service.runs) —
    never for world time, which is kernel.clock's alone (TIME-01)."""
    import sqlite3 as _sq
    conn = _sq.connect(":memory:")
    try:
        return conn.execute("SELECT strftime('%Y-%m-%dT%H:%M:%SZ', 'now')").fetchone()[0]
    finally:
        conn.close()


class Store:
    """Owns the sqlite3 connection. Construct with ``create``/``open``/``memory`` only."""

    def __init__(self, conn: sqlite3.Connection, path: str):
        self.conn = conn
        self.path = path
        self.canon: Any = None
        from ..contracts.settings import RulesConfig
        self.rules = RulesConfig()
        self._in_tx = False

    def attach(self, *, canon: Any = None, rules: Any = None) -> "Store":
        """Attach run context (implemented). Returns self."""
        if canon is not None:
            self.canon = canon
        if rules is not None:
            self.rules = rules
        return self

    @staticmethod
    def _connect(path, memory=False):
        conn = sqlite3.connect(":memory:" if memory else str(path), isolation_level=None)
        conn.row_factory = sqlite3.Row
        if not memory:
            conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    @classmethod
    def _init(cls, conn, run_id, seed, settings_json, content_hash, start_ms, rules_json, created):
        from ..contracts.narration import NarratorStyle
        from .jsoncanon import canonical_json
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.execute("CREATE TRIGGER events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'events is append-only'); END")
        conn.execute("CREATE TRIGGER events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'events is append-only'); END")
        meta = {"run_id": run_id, "seed": str(seed), "schema_version": str(SCHEMA_VERSION),
                "created_at_real": created, "content_hash": content_hash, "settings_json": settings_json,
                "rules_json": rules_json, "pc_actor_id": "", "sandbox": "0", "cheat_active": "0",
                "world_epoch_text": "Day 0 of the Fall"}
        conn.executemany("INSERT INTO meta(key, value) VALUES (?, ?)", list(meta.items()))
        conn.execute("INSERT INTO world_clock(id, now_ms, turn_index, weather, wind_level) VALUES (1, ?, 0, 'clear', 0)", (start_ms,))
        conn.execute("INSERT INTO narrator_state(id, style_json) VALUES (1, ?)", (canonical_json(NarratorStyle().model_dump(mode="json")),))

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
        from ..kernel.errors import StoreError
        p = Path(path)
        if p.exists():
            raise StoreError(f"refusing to overwrite {p}")
        conn = cls._connect(p)
        cls._init(conn, run_id, seed, settings_json, content_hash, start_ms, rules_json,
                  wall_clock_iso())
        return cls(conn, str(p))

    @classmethod
    def open(cls, path: str | Path) -> "Store":
        from ..kernel.errors import SchemaError
        conn = cls._connect(Path(path))
        row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if row is None or row[0] != str(SCHEMA_VERSION):
            conn.close()
            raise SchemaError("schema version mismatch")
        return cls(conn, str(path))

    @classmethod
    def memory(cls, *, run_id: str = "test_run", seed: int = 1, start_ms: int = 0) -> "Store":
        conn = cls._connect(None, memory=True)
        cls._init(conn, run_id, seed, "{}", "", start_ms, "{}", "1970-01-01T00:00:00Z")
        return cls(conn, ":memory:")

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def transaction(self) -> Iterator["Tx"]:
        """BEGIN IMMEDIATE ... COMMIT; ROLLBACK on any exception (re-raised). Nesting raises StoreError."""
        from ..kernel.errors import StoreError
        if self._in_tx:
            raise StoreError("nested transaction")
        self._in_tx = True
        self.conn.execute("BEGIN IMMEDIATE")
        tx = Tx(self)
        try:
            yield tx
        except BaseException:
            self.conn.execute("ROLLBACK")
            self._in_tx = False
            raise
        else:
            self.conn.execute("COMMIT")
            self._in_tx = False

    def query(self, sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def meta(self, key: str) -> str | None:
        r = self.query_one("SELECT value FROM meta WHERE key = ?", (key,))
        return None if r is None else r[0]

    def backup_to(self, path: str | Path, *, as_world: str | None = None) -> None:
        """Consistent copy via sqlite3 backup API (used by saves). P10 (RUN-09): ``as_world`` given ->
        the copy is a world's genesis: in the copy only, meta run_id becomes ``as_world`` and every
        lm_calls row is removed (a world names no run and keeps no model traffic; the live store
        is not changed)."""
        if as_world is not None:
            raise NotImplementedError("P10")
        dst = sqlite3.connect(str(path))
        self.conn.backup(dst)
        dst.close()

    def rebuild_fts(self) -> None:
        """Rebuild the episodes full-text index from ``episodes`` (implemented; used by
        service.runs.load_run, RUN-05). episodes_fts is a derived index kept by schema triggers,
        never a world table, so this is the one statement that bypasses ``Tx``."""
        self.conn.execute("INSERT INTO episodes_fts(episodes_fts) VALUES('rebuild')")


def _ser(v):
    from .jsoncanon import canonical_json
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (dict, list)):
        return canonical_json(v)
    return v


def _pk(conn, table):
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    pk = sorted([c for c in cols if c[5]], key=lambda c: c[5])
    return [c[1] for c in pk]


def _apply(conn, w):
    from ..kernel.errors import StoreError
    t = w.table
    if w.op == WriteOp.INSERT:
        d = {**w.key, **w.values}
        cols = list(d)
        try:
            conn.execute(f"INSERT INTO {t} ({','.join(cols)}) VALUES ({','.join('?'*len(cols))})", [_ser(d[c]) for c in cols])
        except sqlite3.IntegrityError as e:
            raise StoreError(str(e))
    elif w.op == WriteOp.UPDATE:
        sets = ",".join(f"{c}=?" for c in w.values)
        where = " AND ".join(f"{c}=?" for c in w.key)
        cur = conn.execute(f"UPDATE {t} SET {sets} WHERE {where}", [_ser(v) for v in w.values.values()] + [_ser(v) for v in w.key.values()])
        if cur.rowcount == 0:
            raise StoreError("update affected zero rows", rule="STORE-09")
    elif w.op == WriteOp.UPSERT:
        d = {**w.key, **w.values}
        cols = list(d)
        pk = _pk(conn, t)
        sets = ",".join(f"{c}=excluded.{c}" for c in w.values)
        conn.execute(f"INSERT INTO {t} ({','.join(cols)}) VALUES ({','.join('?'*len(cols))}) ON CONFLICT({','.join(pk)}) DO UPDATE SET {sets}", [_ser(d[c]) for c in cols])
    elif w.op == WriteOp.DELETE:
        where = " AND ".join(f"{c}=?" for c in w.key)
        cur = conn.execute(f"DELETE FROM {t} WHERE {where}", [_ser(v) for v in w.key.values()])
        if cur.rowcount == 0:
            raise StoreError("delete affected zero rows", rule="STORE-09")


class Tx:
    """A live transaction. All writes go through ``commit_event`` or ``bookkeep``."""
    def __init__(self, store: Store):
        self.store = store
        self.events = []
        self._cite = []

    def citing(self, rule_id: str, depth: int):
        """P5 (cascade, G10). Context manager: every event committed inside the ``with`` block
        whose rule_cited is None gets rule_cited = rule_id and payload['_cascade_depth'] = depth
        (nested blocks: the innermost wins). Used by action.cascade around each dispatch so owner
        modules need no cascade parameters."""
        import contextlib

        @contextlib.contextmanager
        def _cm():
            self._cite.append((rule_id, depth))
            try:
                yield
            finally:
                self._cite.pop()
        return _cm()

    @property
    def canon(self) -> Any:
        return self.store.canon

    @property
    def rules(self) -> Any:
        return self.store.rules

    def commit_event(self, event, *, _replay=False):
        """Validate + apply ``event.writes`` + append the events row. Returns a copy with
        ``event_id`` and ``seq`` filled. See module docstring for rules."""
        from ..contracts.events import EventType
        from .errors import ScopeError, StoreError, UnknownEventType
        from .jsoncanon import canonical_json
        from .ownership import BOOKKEEPING_TABLES, TABLE_OWNERS
        try:
            EventType(event.type)
        except ValueError:
            raise UnknownEventType(f"unknown event type {event.type}")
        for w in event.writes:
            if w.table not in TABLE_OWNERS:
                raise StoreError(f"unknown table {w.table}")
            if w.table == "events":
                raise StoreError("events is append-only", rule="STORE-08")
            if TABLE_OWNERS[w.table] != event.writer:
                raise ScopeError(f"{event.writer} does not own {w.table}")
            if w.table in BOOKKEEPING_TABLES:
                raise StoreError("bookkeeping tables are not written by events", rule="STORE-01")
        if self._cite and event.rule_cited is None and not _replay:
            rid, dep = self._cite[-1]
            event = event.model_copy(update={"rule_cited": rid, "payload": {**event.payload, "_cascade_depth": dep}})
        conn = self.store.conn
        if _replay:
            eid, seq = event.event_id, event.seq
        else:
            seq = (conn.execute("SELECT COALESCE(MAX(seq), 0) FROM events").fetchone()[0]) + 1
            eid = self.mint("evt")
        writes = [w.model_copy(update={"values": {k: (eid if v == "$event_id" else v) for k, v in w.values.items()}}) for w in event.writes]
        for w in writes:
            _apply(conn, w)
        ev = event.model_copy(update={"event_id": eid, "seq": seq, "writes": writes})
        conn.execute("INSERT INTO events(event_id, seq, at, type, writer, actor_id, target_ids, place_id, cause_event_id, payload, state_delta, rule_cited, turn_index, origin) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (eid, seq, ev.at, str(ev.type), ev.writer, ev.actor_id, canonical_json(ev.target_ids), ev.place_id, ev.cause_event_id,
                      canonical_json(ev.payload), canonical_json([w.model_dump(mode="json") for w in ev.writes]), ev.rule_cited, ev.turn_index, ev.origin))
        self.events.append(ev)
        return ev

    def bookkeep(self, owner: str, table: str, op: WriteOp, key: dict[str, Any], values: dict[str, Any]) -> None:
        """Direct write to a BOOKKEEPING table (ownership checked; world tables -> StoreError STORE-01)."""
        from ..contracts.events import WriteRecord
        from .errors import ScopeError, StoreError
        from .ownership import BOOKKEEPING_TABLES, TABLE_OWNERS
        if table not in BOOKKEEPING_TABLES:
            raise StoreError(f"{table} is a world table", rule="STORE-01")
        if TABLE_OWNERS[table] != owner:
            raise ScopeError(f"{owner} does not own {table}")
        if table == "events" and op in (WriteOp.UPDATE, WriteOp.DELETE, WriteOp.UPSERT):
            raise StoreError("events is append-only", rule="STORE-08")
        _apply(self.store.conn, WriteRecord(op=op, table=table, key=key, values=values))

    def mint(self, kind: str) -> str:
        from .ids import mint
        return mint(self, kind)

    def query(self, sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
        return self.store.conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
        return self.store.conn.execute(sql, params).fetchone()
