"""P10 test kit (PROTECTED): small read helpers for generated worlds, and a way to let the world run.

Nothing here scripts an outcome. A test sets up a cause (a noise, a death, a day passing) and reads
what the world did about it.
"""

from __future__ import annotations

import json

from as_engine.contracts.events import Event, EventType
from as_engine.turn import timers

H = 3_600_000
DAY = 24 * H


def now(s) -> int:
    return s.store.query_one("SELECT now_ms FROM world_clock")[0]


def turn(s) -> int:
    return s.store.query_one("SELECT turn_index FROM world_clock")[0]


def one(s, sql, params=()):
    r = s.store.query_one(sql, params)
    return None if r is None else dict(r)


def all_rows(s, sql, params=()) -> list[dict]:
    return [dict(r) for r in s.store.query(sql, params)]


def rows(s, type_: str) -> list[dict]:
    """Committed events of one type, oldest first, with parsed payloads."""
    out = []
    for r in s.store.query("SELECT * FROM events WHERE type = ? ORDER BY seq", (type_,)):
        d = dict(r)
        d["payload"] = json.loads(d["payload"])
        out.append(d)
    return out


def params(s) -> dict:
    """The world's WorldParams as a dict (world_params.params_json)."""
    return json.loads(s.store.query_one("SELECT params_json FROM world_params WHERE id = 1")[0])


def commit_json(s) -> dict:
    return json.loads(s.store.query_one("SELECT commit_json FROM world_params WHERE id = 1")[0])


def place_of(s, body_id: str) -> str | None:
    r = s.store.query_one("SELECT place_id FROM positions WHERE body_id = ?", (body_id,))
    return None if r is None else r[0]


def place(s, place_id: str) -> dict:
    r = one(s, "SELECT * FROM places WHERE place_id = ?", (place_id,))
    r["props"] = json.loads(r["props"] or "{}")
    return r


def settlement(s, settlement_id: str | None = None) -> dict:
    if settlement_id is None:
        r = one(s, "SELECT * FROM settlements ORDER BY settlement_id LIMIT 1")
    else:
        r = one(s, "SELECT * FROM settlements WHERE settlement_id = ?", (settlement_id,))
    for k in ("stores", "shortages", "vacancies"):
        r[k] = json.loads(r[k])
    return r


def holds(s, holder: str, subject_type: str, subject_id: str, predicate: str) -> dict | None:
    """The holder's live, believed holding of a proposition, or None."""
    return one(s, "SELECT h.*, p.text FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id "
                  "WHERE h.holder_id = ? AND h.superseded_by IS NULL AND h.believed = 1 AND p.subject_type = ? "
                  "AND p.subject_id = ? AND p.predicate = ?", (holder, subject_type, subject_id, predicate))


def cause(tx, at: int, what: str = "a test cause") -> Event:
    """A committed event to stand as a cause."""
    return tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=at, turn_index=0, payload={"what": what}))


def run(s, hours: float) -> list:
    """Let the world run ``hours`` of world time with nobody deciding (turn.timers.run_offscreen).
    Returns the events it committed."""
    with s.store.transaction() as tx:
        return timers.run_offscreen(tx, s.rng, now(s) + int(hours * H), turn(s))
