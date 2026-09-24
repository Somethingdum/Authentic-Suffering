"""Event log readers and event-apply replay (P0). Rules DET-01, DET-02."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..contracts.events import Event

if TYPE_CHECKING:
    from .store import Store, Tx


def committed_or_none(store: "Store | Tx", ref: str | None) -> str | None:
    """``ref`` when an events row has that id, else None (implemented). A standing-view percept's
    event_id is the reference 'scene:<turn>', not an event: anything that needs a cause_event_id
    (a FOREIGN KEY to events) passes a percept's event reference through here first."""
    if not ref:
        return None
    return ref if store.query_one("SELECT 1 FROM events WHERE event_id = ?", (ref,)) is not None else None


def get(store: "Store", event_id: str) -> Event:
    """Load one event as the contract model (writes parsed back into WriteRecords)."""
    raise NotImplementedError("P0")


def since(store: "Store", turn_index: int) -> list[Event]:
    """All events with turn_index >= given, ordered by seq."""
    raise NotImplementedError("P0")


def children(store: "Store", cause_event_id: str) -> list[Event]:
    raise NotImplementedError("P0")


def cause_chain(store: "Store", event_id: str) -> list[Event]:
    """The event and its causes up to the root (first element = the event itself)."""
    raise NotImplementedError("P0")


def replay_world(src: "Store", dst_path: str | Path | None = None) -> "Store":
    """Event-apply replay (DET-01): create a fresh store (file at dst_path, or memory when None)
    with the same meta rows as ``src``, then re-apply every event's WriteRecords in seq order
    using ``Tx.commit_event`` semantics (ids and seq preserved exactly, no new minting).
    Afterwards rebuild derived indexes (episodes_fts). The result must satisfy
    ``world_state_hash(result) == world_state_hash(src)``."""
    raise NotImplementedError("P0")
