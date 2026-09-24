"""The Store (P0). Rules STORE-01..11. kernel/store.py docstring is the contract."""

from __future__ import annotations

import json
import sqlite3

import pytest

from as_engine.audit.commit_gate import REQUIRED_META_KEYS
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.contracts.settings import RulesConfig
from as_engine.kernel.errors import SchemaError, ScopeError, StoreError, UnknownEventType
from as_engine.kernel.store import EVENT_SELF, SCHEMA_VERSION, Store

pytestmark = pytest.mark.phase(0)


def zone_insert(zid: str, name: str = "Downtown", danger=None) -> WriteRecord:
    return WriteRecord(op=WriteOp.INSERT, table="zones",
                       values={"zone_id": zid, "name": name, "kind": "downtown", "danger": danger or {}})


def test_memory_store_has_required_meta_and_clock(store):
    """STORE-10 / G02: a fresh store carries every required meta key and the world clock row."""
    for key in REQUIRED_META_KEYS:
        assert store.meta(key) is not None, key
    assert store.meta("run_id") == "t"
    assert store.meta("seed") == "1"
    assert store.meta("schema_version") == str(SCHEMA_VERSION)
    assert store.meta("created_at_real") == "1970-01-01T00:00:00Z"  # memory stores are deterministic
    assert store.meta("sandbox") == "0" and store.meta("cheat_active") == "0"
    row = store.query_one("SELECT now_ms, turn_index FROM world_clock WHERE id = 1")
    assert (row["now_ms"], row["turn_index"]) == (0, 0)
    assert store.query_one("SELECT id FROM narrator_state WHERE id = 1") is not None


def test_run_context_defaults_and_attach(store):
    """STORE-10: modules read canon/rules from the store they are handed."""
    assert store.canon is None
    assert store.rules == RulesConfig()
    marker = object()
    custom = RulesConfig()
    store.attach(canon=marker, rules=custom)
    with store.transaction() as tx:
        assert tx.canon is marker and tx.rules is custom


def test_commit_event_applies_writes_and_assigns_seq_and_id(store, make_event):
    """STORE-01: world tables change through commit_event; seq starts at 1; ids are minted 'evt'."""
    with store.transaction() as tx:
        e1 = tx.commit_event(make_event(type=EventType.PLACE_DISCOVERED, writer="physical.space",
                                        writes=[zone_insert("zon_000001")]))
        e2 = tx.commit_event(make_event(type=EventType.PLACE_DISCOVERED, writer="physical.space",
                                        writes=[zone_insert("zon_000002", "Riverside")]))
    assert (e1.seq, e2.seq) == (1, 2)
    assert e1.event_id == "evt_000001" and e2.event_id == "evt_000002"
    assert [r["zone_id"] for r in store.query("SELECT zone_id FROM zones ORDER BY zone_id")] == ["zon_000001", "zon_000002"]
    row = store.query_one("SELECT state_delta, writer, type FROM events WHERE seq = 1")
    assert row["writer"] == "physical.space" and row["type"] == "PLACE_DISCOVERED"
    delta = json.loads(row["state_delta"])
    assert delta[0]["table"] == "zones" and delta[0]["op"] == "insert"


def test_a_write_can_name_its_own_event(store, make_event):
    """STORE-11: a value equal to EVENT_SELF ('$event_id') becomes the committing event's id — in
    the row and in the recorded state_delta (so replay rebuilds the same row)."""
    assert EVENT_SELF == "$event_id"
    loop = {"loop_id": "olp_000001", "holder_id": "act_000001", "kind": "goal", "text": "Find water",
            "created_event": EVENT_SELF, "created_at": 0}
    with store.transaction() as tx:
        tx.commit_event(make_event(type=EventType.PLACE_DISCOVERED, writer="physical.space", writes=[zone_insert("zon_000001")]))
        ev = tx.commit_event(make_event(type=EventType.LOOP_OPENED, writer="mind.mind",
                                        writes=[WriteRecord(op=WriteOp.INSERT, table="open_loops", values=loop)]))
    assert ev.event_id == "evt_000002"
    assert store.query_one("SELECT created_event FROM open_loops")["created_event"] == "evt_000002"
    delta = json.loads(store.query_one("SELECT state_delta FROM events WHERE seq = 2")["state_delta"])
    assert delta[0]["values"]["created_event"] == "evt_000002"
    assert ev.writes[0].values["created_event"] == "evt_000002", "the returned event carries the writes as applied"


def test_json_values_are_canonical(store, make_event):
    """Store serialises dict/list values with canonical JSON (sorted keys, no spaces)."""
    with store.transaction() as tx:
        tx.commit_event(make_event(type=EventType.PLACE_DISCOVERED, writer="physical.space",
                                   writes=[zone_insert("zon_000001", danger={"b": 1, "a": [2, 1]})]))
    assert store.query_one("SELECT danger FROM zones")["danger"] == '{"a":[2,1],"b":1}'


def test_scope_error_when_writer_does_not_own_table(store, make_event):
    """STORE-02: a WriteRecord's table must be owned by the event's writer."""
    with pytest.raises(ScopeError) as ei:
        with store.transaction() as tx:
            tx.commit_event(make_event(type=EventType.PLACE_DISCOVERED, writer="mind.actor",
                                       writes=[zone_insert("zon_000001")]))
    assert ei.value.rule == "STORE-02"
    assert store.query("SELECT * FROM zones") == []


def test_unknown_event_type_rejected(store):
    """STORE-05: an event whose type is not an EventType is refused."""
    bogus = Event.model_construct(type="NOT_A_TYPE", writer="audit", writes=[], at=0, turn_index=0,
                                  payload={}, target_ids=[], origin="sim", event_id=None, seq=None,
                                  actor_id=None, place_id=None, cause_event_id=None, rule_cited=None)
    with pytest.raises(UnknownEventType):
        with store.transaction() as tx:
            tx.commit_event(bogus)


def test_update_and_delete_of_missing_row_fail(store, make_event):
    """STORE-09: UPDATE / DELETE that affect zero rows raise StoreError."""
    upd = WriteRecord(op=WriteOp.UPDATE, table="zones", key={"zone_id": "zon_404"}, values={"name": "x"})
    with pytest.raises(StoreError):
        with store.transaction() as tx:
            tx.commit_event(make_event(type=EventType.PLACE_DISCOVERED, writer="physical.space", writes=[upd]))
    dele = WriteRecord(op=WriteOp.DELETE, table="zones", key={"zone_id": "zon_404"})
    with pytest.raises(StoreError):
        with store.transaction() as tx:
            tx.commit_event(make_event(type=EventType.PLACE_DISCOVERED, writer="physical.space", writes=[dele]))


def test_upsert_inserts_then_updates(store, make_event):
    """UPSERT semantics: INSERT ... ON CONFLICT(pk) DO UPDATE."""
    ups = lambda name: WriteRecord(op=WriteOp.UPSERT, table="zones", key={"zone_id": "zon_000001"},
                                   values={"name": name, "kind": "downtown", "danger": {}})
    with store.transaction() as tx:
        tx.commit_event(make_event(type=EventType.PLACE_DISCOVERED, writer="physical.space", writes=[ups("A")]))
        tx.commit_event(make_event(type=EventType.PLACE_DISCOVERED, writer="physical.space", writes=[ups("B")]))
    assert [r["name"] for r in store.query("SELECT name FROM zones")] == ["B"]


def test_duplicate_primary_key_insert_fails(store, make_event):
    """INSERT of an existing primary key raises StoreError."""
    with store.transaction() as tx:
        tx.commit_event(make_event(type=EventType.PLACE_DISCOVERED, writer="physical.space", writes=[zone_insert("zon_000001")]))
    with pytest.raises(StoreError):
        with store.transaction() as tx:
            tx.commit_event(make_event(type=EventType.PLACE_DISCOVERED, writer="physical.space", writes=[zone_insert("zon_000001")]))


def test_transaction_is_atomic_including_bookkeeping(store, make_event):
    """STORE-07: an exception inside a transaction rolls back world AND bookkeeping writes."""
    with pytest.raises(RuntimeError):
        with store.transaction() as tx:
            tx.commit_event(make_event(type=EventType.PLACE_DISCOVERED, writer="physical.space", writes=[zone_insert("zon_000001")]))
            tx.mint("act")
            raise RuntimeError("boom")
    assert store.query("SELECT * FROM zones") == []
    assert store.query("SELECT * FROM events") == []
    with store.transaction() as tx:
        assert tx.mint("act") == "act_000001"  # the rolled-back mint did not advance the counter


def test_a_cancelled_task_rolls_back_too(store, make_event):
    """STORE-07 (P8 amendment): asyncio.CancelledError is a BaseException, not an Exception. The
    Play UI's Stop button cancels a running turn, so it must roll back like any error, and the store
    must accept the next transaction."""
    import asyncio
    with pytest.raises(asyncio.CancelledError):
        with store.transaction() as tx:
            tx.commit_event(make_event(type=EventType.PLACE_DISCOVERED, writer="physical.space", writes=[zone_insert("zon_000001")]))
            raise asyncio.CancelledError()
    assert store.query("SELECT * FROM zones") == []
    with store.transaction() as tx:
        tx.commit_event(make_event(type=EventType.PLACE_DISCOVERED, writer="physical.space", writes=[zone_insert("zon_000001")]))
    assert len(store.query("SELECT * FROM zones")) == 1


def test_nested_transaction_refused(store):
    """Nesting store.transaction() raises StoreError."""
    with pytest.raises(StoreError):
        with store.transaction():
            with store.transaction():
                pass


def test_bookkeep_refuses_world_tables(store):
    """STORE-01: bookkeep() may only touch bookkeeping tables."""
    with pytest.raises(StoreError) as ei:
        with store.transaction() as tx:
            tx.bookkeep("physical.space", "zones", WriteOp.INSERT, {}, {"zone_id": "zon_1", "name": "x", "kind": "k"})
    assert ei.value.rule in ("STORE-01", "STORE-00")


def test_bookkeep_checks_ownership(store):
    """STORE-02 for bookkeeping: only the owner may write (prng_ledger belongs to kernel.rng)."""
    with pytest.raises(ScopeError):
        with store.transaction() as tx:
            tx.bookkeep("audit", "prng_ledger", WriteOp.INSERT, {},
                        {"seq": 1, "turn_index": 0, "stream": "test", "purpose": "x", "n": 2, "value": 1})


def test_events_table_is_append_only(store, make_event):
    """STORE-08: UPDATE/DELETE on events are refused in code (StoreError) and by triggers (raw SQL)."""
    with store.transaction() as tx:
        tx.commit_event(make_event())
    with pytest.raises(StoreError):
        with store.transaction() as tx:
            tx.bookkeep("kernel.events", "events", WriteOp.UPDATE, {"event_id": "evt_000001"}, {"type": "NOISE"})
    with pytest.raises(sqlite3.DatabaseError):
        store.conn.execute("UPDATE events SET type = 'NOISE' WHERE seq = 1")
    with pytest.raises(sqlite3.DatabaseError):
        store.conn.execute("DELETE FROM events WHERE seq = 1")


def test_create_refuses_to_overwrite(tmp_path):
    """Store.create never overwrites an existing file."""
    p = tmp_path / "world.sqlite"
    s = Store.create(p, run_id="r1", seed=5)
    s.close()
    with pytest.raises(StoreError):
        Store.create(p, run_id="r2", seed=6)


def test_open_round_trip_and_schema_guard(tmp_path, make_event):
    """STORE-04: open() refuses a file whose schema_version differs; a good file reopens intact."""
    p = tmp_path / "world.sqlite"
    s = Store.create(p, run_id="r1", seed=5, start_ms=1000)
    with s.transaction() as tx:
        tx.commit_event(make_event(at=1000))
    s.close()
    s2 = Store.open(p)
    assert s2.meta("run_id") == "r1" and s2.meta("created_at_real") != "1970-01-01T00:00:00Z"
    assert len(s2.query("SELECT * FROM events")) == 1
    s2.close()
    con = sqlite3.connect(p)
    con.execute("UPDATE meta SET value = '999' WHERE key = 'schema_version'")
    con.commit()
    con.close()
    with pytest.raises(SchemaError):
        Store.open(p)


def test_backup_to_makes_a_consistent_copy(tmp_path, make_event):
    """backup_to copies the whole DB (used by saves)."""
    s = Store.create(tmp_path / "a.sqlite", run_id="r", seed=1)
    with s.transaction() as tx:
        tx.commit_event(make_event())
    s.backup_to(tmp_path / "b.sqlite")
    s.close()
    b = Store.open(tmp_path / "b.sqlite")
    assert len(b.query("SELECT * FROM events")) == 1
    b.close()
