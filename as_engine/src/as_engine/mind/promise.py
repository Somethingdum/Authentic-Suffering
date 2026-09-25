"""Promises as each person understands them (P6, Actor v2 B5d — Actor Spec §12). Rules PROM-01..07.
Owner 'mind.promise' (promises). Writer of PROMISE_HELD, PROMISE_STATUS, AGREEMENT (writer
'mind.promise', turn_index as given; actor_id = the holder, for AGREEMENT the promiser).

A promise has two layers. The words are objective: the SPEECH event that said them (speaker, the
words, who they were to, when). What was promised is each person's own understanding: who
promised what to whom, the target or item when known, on what condition, where they heard it and
how it stands now. Two people can understand the same words differently, and a private intention
and a public assurance can disagree. Nothing here decides who lied: that stays each mind's own,
evidence-backed interpretation (mind.memory writeback), never a fact announced to the room. 'I
promise' moves no stock and binds nobody's hands.

PROM-01 CATEGORIES and STATUSES below. A status moves only along NEXT:
    proposed    -> understood, accepted, withdrawn
    understood  -> accepted, in_progress, fulfilled, failed, withdrawn
    accepted    -> in_progress, fulfilled, failed, withdrawn
    in_progress -> fulfilled, failed, withdrawn
    fulfilled, failed -> disputed (PROM-06 only)
    withdrawn, disputed -> nothing
  CATEGORY_OF_DEF: what an ask's def (the first part of a mind.firewall request signature)
  promises; a def not listed -> 'assist'.

PROM-02 hold(tx, holder_id, *, promiser_id, promisee_id, category, text, object_id, condition,
  source_event_id, loop_id, status, at, turn_index) -> promise_id (kind 'prm'). The holder's
  understanding of a promise made in ``source_event_id``. ValueError unless: category is in
  CATEGORIES; status is 'proposed', 'understood', 'accepted' or 'in_progress'; text is non-empty
  after strip; source_event_id is a SPEECH event whose actor_id is promiser_id; and the holder
  said it (holder_id == promiser_id) or heard its words (a percept_log row of the holder for that
  event at fidelity 'exact' or 'partial'): a mind cannot hold a promise it never heard (Skull
  Law). The same holder, promiser, promisee, category and source_event_id again -> that
  promise's id, nothing committed. Else PROMISE_HELD {promise_id, holder_id, promiser_id,
  promisee_id, category, text, object_id, condition, status} (cause = the SPEECH) inserting the
  promises row (text stripped, created_at = updated_at = at, agreement_id NULL); then PROM-03.

PROM-03 agreement: after a hold, when the promiser and the promisee each hold an understanding of
  the same source_event_id with the same promiser and promisee (so the words were said by one and
  heard by the other, PROM-02), neither has an agreement yet nor a status 'withdrawn' or
  'disputed', and the two agree — the same
  category, and object_ids equal or one of them NULL: AGREEMENT {agreement_id (kind 'agr'),
  promiser_id, promisee_id, category, object_id (the one that is not NULL, else NULL),
  promise_ids: [the promiser's, the promisee's]} (cause = the SPEECH) setting agreement_id on both
  rows, and status 'accepted' (updated_at = at) on each that was 'proposed' or 'understood'.
  Understandings that do not agree get no agreement; each keeps its own.

PROM-04 set_status(tx, promise_id, status, cause, at, turn_index) -> Event | None: the promise's
  current status -> None, nothing committed. A move NEXT does not allow -> ValueError. Else
  PROMISE_STATUS {promise_id, holder_id, old, new} updating status and updated_at.

PROM-05 on_loop_closed(tx, loop_id, status, cause, at, turn_index) -> list[Event] — mind.mind
  close_loop calls it after committing the loop's own event. The holder's promise carried by that
  loop (promises.loop_id; none -> []) moves: loop 'fulfilled' -> 'fulfilled'; 'broken' or
  'expired' -> 'failed'; 'abandoned' -> 'withdrawn' when the holder is the promiser, else 'failed'
  (a move NEXT does not allow -> nothing). Then PROM-06. Returns the events committed, in order.

PROM-06 disputed: when that promise has an agreement and the other party's promise of the same
  agreement is 'fulfilled' while this one is now 'failed', or the other way round, both become
  'disputed' — the promiser's PROMISE_STATUS first. The two remember it differently. Nobody is
  called a liar and nobody's trust moves here; what a broken promise costs the promisee stays
  cascade content on PROMISE_BROKEN (mind.mind LOOP-04, core CAS-011).

PROM-07 suffix(store, loop_id) -> str: how a promise the loop carries stands, for the packet
  line of that loop (mind.packet open_loops): '' when the loop carries no promise or its status
  is terminal; else SUFFIX_WORDS[status] — for 'accepted' with an agreement,
  SUFFIX_WORDS['agreed'].
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..contracts.events import Event

if TYPE_CHECKING:
    from ..kernel.store import Store, Tx

CATEGORIES: tuple[str, ...] = ("deliver", "guard", "return", "disclose", "refrain", "assist")
STATUSES: tuple[str, ...] = ("proposed", "understood", "accepted", "in_progress", "fulfilled", "failed", "withdrawn",
                             "disputed")
NEXT: dict[str, tuple[str, ...]] = {
    "proposed": ("understood", "accepted", "withdrawn"),
    "understood": ("accepted", "in_progress", "fulfilled", "failed", "withdrawn"),
    "accepted": ("in_progress", "fulfilled", "failed", "withdrawn"),
    "in_progress": ("fulfilled", "failed", "withdrawn"),
    "fulfilled": ("disputed",),
    "failed": ("disputed",),
    "withdrawn": (),
    "disputed": (),
}
CATEGORY_OF_DEF: dict[str, str] = {
    "give_item": "deliver",
    "guard_anchor": "guard",
    "drop_item": "refrain",
    "wait_here": "refrain",
    "hide": "refrain",
}
SUFFIX_WORDS: dict[str, str] = {
    "proposed": " (not answered yet)",
    "understood": " (as you understood it)",
    "accepted": " (you took it on)",
    "agreed": " (agreed between you)",
    "in_progress": " (under way)",
}


def _row(s, sql, p=()):
    r = s.query_one(sql, p)
    return dict(r) if r is not None else None


def heard(tx, holder_id, promiser_id, source_event_id):
    ev = _row(tx, "SELECT type, actor_id FROM events WHERE event_id=?", (source_event_id,))
    if ev is None or ev["type"] != "SPEECH" or ev["actor_id"] != promiser_id:
        return False
    if holder_id == promiser_id:
        return True
    return tx.query_one("SELECT 1 FROM percept_log WHERE holder_id=? AND event_id=? AND fidelity IN ('exact','partial')",
                        (holder_id, source_event_id)) is not None


def hold(tx: "Tx", holder_id: str, *, promiser_id: str, promisee_id: str | None, category: str, text: str,
         object_id: str | None, condition: str | None, source_event_id: str, loop_id: str | None, status: str,
         at: int, turn_index: int) -> str:
    from ..contracts.events import EventType, WriteOp, WriteRecord
    if category not in CATEGORIES:
        raise ValueError("category")
    if status not in ("proposed", "understood", "accepted", "in_progress"):
        raise ValueError("status")
    if not text or not text.strip():
        raise ValueError("text")
    if not heard(tx, holder_id, promiser_id, source_event_id):
        raise ValueError("never heard")
    r = tx.query_one("SELECT promise_id FROM promises WHERE holder_id=? AND promiser_id=? AND promisee_id IS ? AND category=? "
                     "AND source_event_id=?", (holder_id, promiser_id, promisee_id, category, source_event_id))
    if r is not None:
        return r[0]
    pid = tx.mint("prm")
    tx.commit_event(Event(type=EventType.PROMISE_HELD, writer="mind.promise", at=at, turn_index=turn_index, actor_id=holder_id,
                          cause_event_id=source_event_id,
                          writes=[WriteRecord(op=WriteOp.INSERT, table="promises", values={
                              "promise_id": pid, "holder_id": holder_id, "promiser_id": promiser_id, "promisee_id": promisee_id,
                              "category": category, "text": text.strip(), "object_id": object_id, "condition": condition,
                              "source_event_id": source_event_id, "loop_id": loop_id, "status": status, "agreement_id": None,
                              "created_at": at, "updated_at": at})],
                          payload={"promise_id": pid, "holder_id": holder_id, "promiser_id": promiser_id, "promisee_id": promisee_id,
                                   "category": category, "text": text.strip(), "object_id": object_id, "condition": condition,
                                   "status": status}))
    _agree(tx, pid, at, turn_index)
    return pid


def _agree(tx, pid, at, turn_index):
    from ..contracts.events import EventType, WriteOp, WriteRecord
    me = _row(tx, "SELECT * FROM promises WHERE promise_id=?", (pid,))
    if me["promisee_id"] is None or me["agreement_id"] is not None or me["status"] in ("withdrawn", "disputed"):
        return
    other_holder = me["promisee_id"] if me["holder_id"] == me["promiser_id"] else (
        me["promiser_id"] if me["holder_id"] == me["promisee_id"] else None)
    if other_holder is None:
        return
    for o in tx.query("SELECT * FROM promises WHERE holder_id=? AND promiser_id=? AND promisee_id=? AND source_event_id=? "
                      "AND agreement_id IS NULL AND status NOT IN ('withdrawn','disputed') ORDER BY created_at, promise_id",
                      (other_holder, me["promiser_id"], me["promisee_id"], me["source_event_id"])):
        o = dict(o)
        if o["category"] != me["category"]:
            continue
        if me["object_id"] and o["object_id"] and me["object_id"] != o["object_id"]:
            continue
        mine, theirs = (me, o) if me["holder_id"] == me["promiser_id"] else (o, me)
        aid = tx.mint("agr")
        writes = []
        for x in (mine, theirs):
            vals = {"agreement_id": aid}
            if x["status"] in ("proposed", "understood"):
                vals.update({"status": "accepted", "updated_at": at})
            writes.append(WriteRecord(op=WriteOp.UPDATE, table="promises", key={"promise_id": x["promise_id"]}, values=vals))
        tx.commit_event(Event(type=EventType.AGREEMENT, writer="mind.promise", at=at, turn_index=turn_index, actor_id=me["promiser_id"],
                              cause_event_id=me["source_event_id"], writes=writes,
                              payload={"agreement_id": aid, "promiser_id": me["promiser_id"], "promisee_id": me["promisee_id"],
                                       "category": me["category"], "object_id": me["object_id"] or o["object_id"],
                                       "promise_ids": [mine["promise_id"], theirs["promise_id"]]}))
        return


def set_status(tx: "Tx", promise_id: str, status: str, cause: str | None, at: int, turn_index: int) -> Event | None:
    from ..contracts.events import EventType, WriteOp, WriteRecord
    from ..kernel.events import committed_or_none
    r = _row(tx, "SELECT * FROM promises WHERE promise_id=?", (promise_id,))
    if r["status"] == status:
        return None
    if status not in NEXT[r["status"]]:
        raise ValueError(f"{r['status']} -> {status}")
    return tx.commit_event(Event(type=EventType.PROMISE_STATUS, writer="mind.promise", at=at, turn_index=turn_index, actor_id=r["holder_id"],
                                 cause_event_id=committed_or_none(tx, cause),
                                 writes=[WriteRecord(op=WriteOp.UPDATE, table="promises", key={"promise_id": promise_id},
                                                     values={"status": status, "updated_at": at})],
                                 payload={"promise_id": promise_id, "holder_id": r["holder_id"], "old": r["status"], "new": status}))


def on_loop_closed(tx: "Tx", loop_id: str, status: str, cause: str | None, at: int, turn_index: int) -> list[Event]:
    r = _row(tx, "SELECT * FROM promises WHERE loop_id=?", (loop_id,))
    if r is None:
        return []
    new = {"fulfilled": "fulfilled", "broken": "failed", "expired": "failed"}.get(status)
    if status == "abandoned":
        new = "withdrawn" if r["holder_id"] == r["promiser_id"] else "failed"
    out = []
    if new in NEXT[r["status"]]:
        e = set_status(tx, r["promise_id"], new, cause, at, turn_index)
        if e is not None:
            out.append(e)
    r = _row(tx, "SELECT * FROM promises WHERE promise_id=?", (r["promise_id"],))
    if r["agreement_id"] and r["status"] in ("fulfilled", "failed"):
        o = _row(tx, "SELECT * FROM promises WHERE agreement_id=? AND promise_id<>?", (r["agreement_id"], r["promise_id"]))
        if o is not None and {o["status"], r["status"]} == {"fulfilled", "failed"}:
            first, second = (r, o) if r["holder_id"] == r["promiser_id"] else (o, r)
            out.append(set_status(tx, first["promise_id"], "disputed", cause, at, turn_index))
            out.append(set_status(tx, second["promise_id"], "disputed", cause, at, turn_index))
    return out


def suffix(store: "Store | Tx", loop_id: str) -> str:
    r = store.query_one("SELECT status, agreement_id FROM promises WHERE loop_id=?", (loop_id,))
    if r is None or r[0] not in SUFFIX_WORDS:
        return ""
    if r[0] == "accepted" and r[1]:
        return SUFFIX_WORDS["agreed"]
    return SUFFIX_WORDS[r[0]]
