"""P9 test kit (PROTECTED): small helpers for driving a settlement without a player.

The society runs on the off-screen step (turn.timers.run_offscreen): timers fire in order,
cascades sweep what they commit, bodies are integrated. Nothing here scripts an outcome — a test
sets up a cause (an injury, a rumour, a grudge) and lets the world run.
"""

from __future__ import annotations

import json

from as_engine.action import cascade
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.physical import bodies
from as_engine.physical.bodies import WoundSpec
from as_engine.turn import timers

H = 3_600_000
DAY = 24 * H


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def hhmm(ms):
    return f"{(ms % DAY) // H:02d}:{(ms % H) // 60_000:02d}"


def accident(tx, at, what="an accident"):
    """A committed event to stand as a cause."""
    return tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=at, turn_index=0, payload={"what": what}))


def injure(w, local, anatomy="arm_r", severity="significant", *, stitched_by="vera"):
    """A significant cut, stitched at once (so it stops bleeding and the worker lives), then the
    cascade sweep of the HARM — exactly what the turn pipeline does with a committed harm.
    Returns the HARM event."""
    at = now(w)
    with w.store.transaction() as tx:
        cause = accident(tx, at, "the pump handle slipped")
        harm = bodies.apply_harm(tx, w.id(local), WoundSpec(anatomy=anatomy, type="cut", severity=severity), at, cause.event_id, 0, w.rng)[0]
        if stitched_by:
            bodies.treat(tx, w.id(local), harm.payload["wound_id"], "suture", w.id(stitched_by), at, harm.event_id, 0)
        cascade.sweep(tx, [harm], tx.canon.all("cascade"), at, 0)
    return harm


def heal(w, local):
    """Every wound of the body heals now (a test shortcut for 'two weeks later')."""
    at = now(w)
    with w.store.transaction() as tx:
        rows = tx.query("SELECT wound_id FROM wounds WHERE body_id = ? AND healed_at IS NULL", (w.id(local),))
        tx.commit_event(Event(type=EventType.WOUND_PROGRESS, writer="physical.bodies", at=at, turn_index=0,
                              payload={"body_id": w.id(local), "change": "healed"},
                              writes=[WriteRecord(op=WriteOp.UPDATE, table="wounds", key={"wound_id": r[0]}, values={"healed_at": at})
                                      for r in rows]))


def run(w, hours):
    """Let the world run ``hours`` of world time with nobody deciding. Returns the events."""
    with w.store.transaction() as tx:
        return timers.run_offscreen(tx, w.rng, now(w) + int(hours * H), 0)


def rows(w, type_):
    """Committed events of one type, oldest first, with parsed payloads."""
    out = []
    for r in w.store.query("SELECT * FROM events WHERE type = ? ORDER BY seq", (type_,)):
        d = dict(r)
        d["payload"] = json.loads(d["payload"])
        out.append(d)
    return out


def settlement(w):
    r = dict(w.store.query_one("SELECT * FROM settlements"))
    for k in ("stores", "shortages", "vacancies"):
        r[k] = json.loads(r[k])
    return r


def workplace(w, local):
    r = dict(w.store.query_one("SELECT * FROM workplaces WHERE workplace_id = ?", (w.id(local),)))
    return r


def rel(w, a, b):
    r = w.store.query_one("SELECT * FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return None if r is None else dict(r)


def cause_chain(w, event_id):
    """Event ids from ``event_id`` back to the root cause, following cause_event_id."""
    out = []
    while event_id:
        r = w.store.query_one("SELECT event_id, type, cause_event_id FROM events WHERE event_id = ?", (event_id,))
        if r is None:
            break
        out.append((r["event_id"], r["type"]))
        event_id = r["cause_event_id"]
    return out
