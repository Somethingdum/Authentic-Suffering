"""Event log readers and event-apply replay (P0). Rules DET-01, STORE-01."""

from __future__ import annotations

import pytest

from as_engine.contracts.events import EventType, WriteOp, WriteRecord
from as_engine.kernel import clock, events
from as_engine.kernel.hashing import world_state_hash
from as_engine.kernel.rng import Rng
from as_engine.kernel.store import Store

pytestmark = pytest.mark.phase(0)


def build_trace(store: Store, n: int = 120) -> list[str]:
    """A synthetic trace touching several owners: zones (physical.space), claims (kernel.truth),
    timers (kernel.clock), rng draws (bookkeeping) and clock advances."""
    ids = []
    rng = Rng(int(store.meta("seed")))
    with store.transaction() as tx:
        root = tx.commit_event(__ev(EventType.WORLDGEN_STAGE, "world.worldgen", []))
        ids.append(root.event_id)
        for i in range(n):
            zid = f"zon_{i + 1:06d}"
            e = tx.commit_event(__ev(EventType.PLACE_DISCOVERED, "physical.space",
                                     [WriteRecord(op=WriteOp.INSERT, table="zones",
                                                  values={"zone_id": zid, "name": f"Z{i}", "kind": "rural",
                                                          "danger": {"shambler": rng.d10(tx, "test", f"z{i}")}})],
                                     cause=root.event_id, at=i * 10))
            ids.append(e.event_id)
            if i % 7 == 0:
                clock.advance_event(tx, i * 10 + 5, "trace")
                clock.schedule(tx, i * 10 + 1_000, "NOISE", None, {"source_db": 60 + i}, e.event_id)
            if i % 11 == 0:
                tx.commit_event(__ev(EventType.PLACE_DISCOVERED, "physical.space",
                                     [WriteRecord(op=WriteOp.UPDATE, table="zones", key={"zone_id": zid},
                                                  values={"name": f"Z{i} (renamed)"})], cause=e.event_id, at=i * 10 + 5))
    return ids


def __ev(t, writer, writes, cause=None, at=0):
    from as_engine.contracts.events import Event
    return Event(type=t, writer=writer, writes=writes, at=at, turn_index=0, cause_event_id=cause)


def test_replay_reproduces_world_hash_in_memory():
    """DET-01: event-apply replay onto a fresh store reproduces world_state_hash exactly."""
    src = Store.memory(run_id="r", seed=9)
    build_trace(src)
    dst = events.replay_world(src)
    assert world_state_hash(dst) == world_state_hash(src)
    assert [r["event_id"] for r in dst.query("SELECT event_id FROM events ORDER BY seq")] == \
           [r["event_id"] for r in src.query("SELECT event_id FROM events ORDER BY seq")]
    src.close()
    dst.close()


def test_replay_to_file_survives_process_restart(tmp_path):
    """DET-01 across a restart: replay to a file, reopen it, hash equal."""
    src = Store.create(tmp_path / "src.sqlite", run_id="r", seed=9)
    build_trace(src, 60)
    h = world_state_hash(src)
    dst = events.replay_world(src, tmp_path / "dst.sqlite")
    dst.close()
    again = Store.open(tmp_path / "dst.sqlite")
    assert world_state_hash(again) == h
    again.close()
    src.close()


def test_readers():
    """get / since / children / cause_chain return contract Events with writes parsed back."""
    s = Store.memory(run_id="r", seed=9)
    ids = build_trace(s, 12)
    first_child = events.get(s, ids[1])
    assert first_child.writes and first_child.writes[0].table == "zones"
    assert first_child.cause_event_id == ids[0]
    kids = events.children(s, ids[0])
    assert [k.event_id for k in kids][: len(ids) - 1] == ids[1:]
    chain = events.cause_chain(s, ids[1])
    assert [c.event_id for c in chain] == [ids[1], ids[0]]
    assert len(events.since(s, 0)) == len(s.query("SELECT * FROM events"))
    assert events.since(s, 1) == []
    s.close()
