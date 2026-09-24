"""Relationships, open loops, lessons (P6). Owner 'mind.mind'. Rules REL-01..05, LOOP-01..06,
LESSON-01..03, STAND-01..02 (P9). Writer of RELATION_CHANGE, LOOP_OPENED, PROMISE, LOOP_CLOSED,
PROMISE_KEPT, PROMISE_BROKEN, LESSON_LEARNED (every event: writer 'mind.mind', actor_id = the holder,
turn_index as given, cause_event_id = kernel.events.committed_or_none(cause) — a standing-view
reference such as 'scene:4' is recorded in the row but is not an event). "The event id" in a row
below is written as kernel.store.EVENT_SELF, which the store replaces with the committing event's
own id (STORE-11).

Relationships (one row per ordered pair: what FROM feels about TO)
REL-01 relate(tx, from_id, to_id, axis, delta, cause, at, turn_index) -> Event | None changes ONE
  axis of the (from_id, to_id) row by ``delta``. A missing row is created by the same event:
  kind 'acquaintance', every axis 0, causes '{}', then the change applied.
REL-02 The new value is clamped to RELATION_AXIS_RANGE[axis]. The event records what actually
  changed; when nothing changes (delta 0, or the axis is already at the bound in that direction)
  no event is committed and None is returned. Payload {from_id, to_id, axis, old, new, delta}
  with delta = new - old. Writes: relationships INSERT (new row) or UPDATE (axis, causes,
  updated_at = at).
REL-03 Every change keeps its cause: causes[axis] = ``cause`` (the latest cause per axis, JSON
  object; the key is the axis value, e.g. 'trust').
REL-04 A relationship is one-directional: relate(from, to) never reads or writes the (to, from)
  row. from_id == to_id -> ValueError (nobody has a relationship with themselves).
REL-05 relate never changes ``kind`` (content, households and worldgen set kinds); an existing
  row keeps its kind.

Open loops (what hangs over a mind: goals, desires, grudges, fears, questions, plans, promises,
debts, kept secrets — OpenLoopKind)
LOOP-01 open_loop(tx, holder_id, kind, text, subject_ids, strength, cause, at, turn_index,
  due_at=None) -> loop_id (kind 'olp'). ``kind`` must be an OpenLoopKind value, ``text`` non-empty
  after strip, ``strength`` 1..3 — else ValueError. When ``text`` contains '{subject}' and
  subject_ids is not empty, '{subject}' is replaced by the holder's word for subject_ids[0]
  (mind.perception.word_for) — cascade content writes texts like '{subject} broke a promise to
  you.' — and the stored text is stripped with its first letter upper-cased. Event: PROMISE for kinds promise_made / promise_owed, LOOP_OPENED otherwise; payload
  {loop_id, holder_id, kind, text, subject_ids, strength, due_at}; writes open_loops INSERT
  (status 'open', created_event = the event id, created_at = at, subject_ids as given, in order).
LOOP-02 A mind does not hold the same loop twice: when the holder already has an OPEN loop with
  the same kind, the same subject_ids (as a set) and the same text after
  mind.perception.norm_text, open_loop returns that loop's id and commits nothing (its strength
  stays as it was).
LOOP-03 close_loop(tx, loop_id, status, cause, at, turn_index) -> Event. The loop must exist and
  be 'open', and status must be one of 'fulfilled', 'broken', 'abandoned', 'expired' — else
  ValueError. Writes open_loops UPDATE (status, resolved_event = this event's id).
LOOP-04 The promisee is the one who decides a promise was kept or broken. Closing a
  **promise_owed** loop (the holder is owed) as 'fulfilled' commits PROMISE_KEPT, as 'broken'
  commits PROMISE_BROKEN, with payload {loop_id, holder_id, status, promisee_id: the holder,
  promiser_id: subject_ids[0] or null}. Every other close — including a promiser closing its own
  promise_made loop as 'broken' — commits LOOP_CLOSED {loop_id, holder_id, kind, status}: it is
  private, and no other mind changes because of it (L1).
LOOP-05 close_loop writes nothing but the loop row. What a broken promise costs is cascade
  content (core CAS-011: the promisee's trust drops and it opens a grudge), applied by the
  cascade sweep to the promisee only.
LOOP-06 Loops are never deleted; only their status changes.

Lessons (what experience taught a mind; retrieved by the cues present, mind.retrieval)
LESSON-01 learn(tx, holder_id, cue_tags, text, expectation, outcome, cause, at, turn_index) ->
  lesson_id (kind 'lsn'). cue_tags must be a non-empty list of non-empty strings and text
  non-empty after strip — else ValueError. (Callers pass registry cue ids; mind.memory drops
  unknown tags before calling.) Event LESSON_LEARNED {lesson_id, holder_id, cue_tags (sorted),
  text, expectation, outcome, confidence, reinforced: false}; writes lessons INSERT (cue_tags
  sorted, confidence 2, source_event = the event id, at).
LESSON-02 Learning the same lesson again (same holder, same cue_tags as a set, same norm_text)
  reinforces it instead: confidence + 1 (at most 3), LESSON_LEARNED {lesson_id, holder_id,
  confidence, reinforced: true}; writes lessons UPDATE (confidence); returns the existing id.
  Already at 3: no event, the id is returned.
LESSON-03 Lessons are never deleted.

Group standing (P9; lives here for discoverability — the table and the writer are society.group's)
STAND-01 standing_toward(store, group_id, actor_id) -> int: group_standing.standing of the row
  (group_id, actor_id), 0 without one. It is the world's memory of a person: what a group as a
  whole thinks of them (-5..5), whatever any one member feels.
STAND-02 adjust_group_standing(tx, group_id, actor_id, delta, cause_event_id, at, turn_index) ->
  Event | None. An unknown group -> ValueError. new = clamp(old + delta, -5, 5); new == old ->
  None (nothing committed). Commits STANDING_CHANGE {group_id, actor_id, old, new, delta: new -
  old} (writer 'society.group', actor_id = actor_id, cause = cause_event_id) writing group_standing
  UPSERT (group_id, actor_id): standing = new, reasons = (the old list + [cause_event_id])[-10:]
  (unchanged when cause_event_id is None). Callers: society.settlement.apply_law (a punishing law
  costs 1); society.settlement.trade_terms reads it (SOC-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..contracts.common import OpenLoopKind, RelationAxis
from ..contracts.events import Event

if TYPE_CHECKING:
    from ..kernel.store import Store, Tx


def relate(tx: "Tx", from_id: str, to_id: str, axis: RelationAxis, delta: int, cause: str | None,
           at: int, turn_index: int) -> Event | None:
    raise NotImplementedError("P6")


def open_loop(tx: "Tx", holder_id: str, kind: OpenLoopKind, text: str, subject_ids: list[str],
              strength: int, cause: str | None, at: int, turn_index: int,
              due_at: int | None = None) -> str:
    raise NotImplementedError("P6")


def close_loop(tx: "Tx", loop_id: str, status: str, cause: str | None, at: int,
               turn_index: int) -> Event:
    raise NotImplementedError("P6")


def learn(tx: "Tx", holder_id: str, cue_tags: list[str], text: str, expectation: str, outcome: str,
          cause: str | None, at: int, turn_index: int) -> str:
    raise NotImplementedError("P6")


def standing_toward(store: "Store | Tx", group_id: str, actor_id: str) -> int:
    raise NotImplementedError("P9")


def adjust_group_standing(tx: "Tx", group_id: str, actor_id: str, delta: int, cause_event_id: str | None,
                          at: int, turn_index: int) -> Event | None:
    raise NotImplementedError("P9")
