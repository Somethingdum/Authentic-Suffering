---
name: as-store-events
description: How state changes work in as_engine - events, write records, table ownership, bookkeeping, replay.
whenToUse: Writing any function that changes the run database, or when a ScopeError / StoreError appears.
---

# Events, ownership, replay

- Every change to a WORLD table is a `WriteRecord` inside ONE `Event`, applied by
  `tx.commit_event(event)` (`kernel/store.py`). Nothing else writes world tables.
- `event.writer` must own every table the event writes (`kernel/ownership.py::TABLE_OWNERS`).
  A `ScopeError` means you wrote a table from the wrong module: call that module's API instead.
- BOOKKEEPING tables (`counters`, `prng_ledger`, `events`, `lm_calls`, `audit_log`, …) are written
  with `tx.bookkeep(owner, table, op, key, values)`, never by events. `audit/log.record` writes
  audit rows for you.
- Build-then-commit helpers (`space.move_event`, `space.portal_change_event`) return an Event; the
  caller commits it. Most other module APIs commit themselves and return the committed Event.
- An Event's `cause_event_id` names what caused it (an ACTION_START, a HARM, a TIMER_FIRED).
  `rule_cited` is set by `tx.citing(rule_id, depth)` for cascade effects.
- Replay (DET-01): `kernel.events.replay_world` re-applies every event's writes in `seq` order and
  must reproduce `world_state_hash` exactly. So: never read the clock or random inside a write, never
  depend on dict iteration order, never write derived data you did not put in an event.
- Ids: `tx.mint(kind)` → `f"{kind}_{n:06d}"`. Times: integer ms since the Fall.
- JSON columns: pass Python dicts/lists in `values`; the store canonicalises them.
