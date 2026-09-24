"""Implementation of mind.mind group standing (P9)."""
from __future__ import annotations

import json

from ..contracts.events import Event, EventType, WriteOp, WriteRecord


def standing_toward(store, group_id, actor_id):
    r = store.query_one("SELECT standing FROM group_standing WHERE group_id=? AND actor_id=?", (group_id, actor_id))
    return r[0] if r else 0


def adjust_group_standing(tx, group_id, actor_id, delta, cause_event_id, at, turn_index):
    if tx.query_one("SELECT 1 FROM groups WHERE group_id=?", (group_id,)) is None:
        raise ValueError(f"unknown group {group_id}")
    r = tx.query_one("SELECT standing, reasons FROM group_standing WHERE group_id=? AND actor_id=?", (group_id, actor_id))
    old = r[0] if r else 0
    new = max(-5, min(5, old + int(delta)))
    if new == old:
        return None
    reasons = json.loads(r[1]) if r else []
    if cause_event_id is not None:
        reasons = (reasons + [cause_event_id])[-10:]
    return tx.commit_event(Event(type=EventType.STANDING_CHANGE, writer="society.group", at=at, turn_index=turn_index, actor_id=actor_id,
                                 cause_event_id=cause_event_id,
                                 payload={"group_id": group_id, "actor_id": actor_id, "old": old, "new": new, "delta": new - old},
                                 writes=[WriteRecord(op=WriteOp.UPSERT, table="group_standing", key={"group_id": group_id, "actor_id": actor_id},
                                                     values={"standing": new, "reasons": reasons})]))
