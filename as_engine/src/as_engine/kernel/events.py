"""Event log readers and event-apply replay (P0). Rules DET-01, DET-02; STORE-12 (links).

Every reader returns events with their ``links`` (fidelity C10, Actor v2 B5c): the events row's
``links`` column parsed back into EventLinks, so replay re-commits them unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..contracts.events import Event

if TYPE_CHECKING:
    from .store import Store


def _row_to_event(r):
    import json
    from ..contracts.events import Event, WriteRecord
    return Event(event_id=r["event_id"], seq=r["seq"], at=r["at"], type=r["type"], writer=r["writer"], actor_id=r["actor_id"],
                 target_ids=json.loads(r["target_ids"]), place_id=r["place_id"], cause_event_id=r["cause_event_id"],
                 payload=json.loads(r["payload"]), writes=[WriteRecord(**w) for w in json.loads(r["state_delta"])],
                 rule_cited=r["rule_cited"], turn_index=r["turn_index"], origin=r["origin"])


def get(store: "Store", event_id: str) -> Event:
    """Load one event as the contract model (writes parsed back into WriteRecords)."""
    return _row_to_event(store.query_one("SELECT * FROM events WHERE event_id=?", (event_id,)))


def since(store: "Store", turn_index: int) -> list[Event]:
    """All events with turn_index >= given, ordered by seq."""
    return [_row_to_event(r) for r in store.query("SELECT * FROM events WHERE turn_index >= ? ORDER BY seq", (turn_index,))]


def children(store: "Store", cause_event_id: str) -> list[Event]:
    return [_row_to_event(r) for r in store.query("SELECT * FROM events WHERE cause_event_id=? ORDER BY seq", (cause_event_id,))]


def cause_chain(store: "Store", event_id: str) -> list[Event]:
    """The event and its causes up to the root (first element = the event itself), following the
    primary parent ``cause_event_id`` only (the other causes are links: ``causes``)."""
    out = []
    cur = event_id
    while cur:
        e = get(store, cur)
        out.append(e)
        cur = e.cause_event_id
    return out


def causes(store: "Store", event_id: str) -> list[tuple[str, str]]:
    """C10 (STORE-12): every recorded cause of the event, as (event id, role): (cause_event_id,
    'primary') first when it is set, then (link.event_id, link.role) for each link in stored
    order."""
    raise NotImplementedError("P0")


def effects(store: "Store", event_id: str) -> list[Event]:
    """C10 (STORE-12): every event that names ``event_id`` as a cause — its cause_event_id or one
    of its links — by seq, each once."""
    raise NotImplementedError("P0")


def replay_world(src: "Store", dst_path: str | Path | None = None) -> "Store":
    """Event-apply replay (DET-01): create a fresh store (file at dst_path, or memory when None)
    with the same meta rows as ``src``, then re-apply every event's WriteRecords in seq order
    using ``Tx.commit_event`` semantics (ids and seq preserved exactly, no new minting).
    Afterwards rebuild derived indexes (episodes_fts). The result must satisfy
    ``world_state_hash(result) == world_state_hash(src)``."""
    from .store import Store
    from .ownership import BOOKKEEPING_TABLES
    meta = {r["key"]: r["value"] for r in src.query("SELECT key, value FROM meta")}
    start = src.query_one("SELECT now_ms FROM events ORDER BY seq LIMIT 1") if False else None
    first_clock = None
    if dst_path is None:
        dst = Store.memory(run_id=meta["run_id"], seed=int(meta["seed"]))
    else:
        dst = Store.create(dst_path, run_id=meta["run_id"], seed=int(meta["seed"]))
    # meta rows copied verbatim; world_clock reset to the source's genesis clock
    dst.conn.execute("DELETE FROM meta")
    dst.conn.executemany("INSERT INTO meta(key,value) VALUES (?,?)", list(meta.items()))
    # genesis clock: the clock before the first CLOCK_ADVANCE = source's first advance 'from' or its current if none
    import json
    first_adv = src.query_one("SELECT payload FROM events WHERE type='CLOCK_ADVANCE' ORDER BY seq LIMIT 1")
    g = json.loads(first_adv["payload"])["from"] if first_adv else src.query_one("SELECT now_ms FROM world_clock")[0]
    dst.conn.execute("UPDATE world_clock SET now_ms=?", (g,))
    with dst.transaction() as tx:
        for r in src.query("SELECT * FROM events ORDER BY seq"):
            tx.commit_event(_row_to_event(r), _replay=True)
        # counters replicate ids (bookkeeping) so later minting continues
        for r in src.query("SELECT kind, next FROM counters"):
            dst.conn.execute("INSERT OR REPLACE INTO counters(kind,next) VALUES (?,?)", (r[0], r[1]))
    return dst


def committed_or_none(store: "Store | Tx", ref: str | None) -> str | None:
    """``ref`` when an events row has that id, else None (implemented). A standing-view percept's
    event_id is the reference 'scene:<turn>', not an event: anything that needs a cause_event_id
    (a FOREIGN KEY to events) passes a percept's event reference through here first."""
    if not ref:
        return None
    return ref if store.query_one("SELECT 1 FROM events WHERE event_id = ?", (ref,)) is not None else None
