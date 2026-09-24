"""Resolve pool (P4). Rules RES-01..05. Resolve gates affordances; it never modifies a roll.

drain(tx, actor_id, reason, cause_event_id, at, turn_index) -> Event | None
  reason must be a key of RulesConfig.resolve.drains (else ValueError); amount = drains[reason];
  RESOLVE_CHANGE event (writer 'mind.actor' because resolve_cur lives in `actors`) with payload
  {actor_id, reason, delta (negative), resolve (new value)}; clamp at 0; a drain that changes
  nothing (already 0) -> None, no event. Coercion drains Resolve (L7) — it never rolls against
  personality.
recover(tx, actor_id, reason, ...) -> Event | None   reasons: safe_night -> recover_per_safe_night,
  fulfilled_obligation -> recover_fulfilled_obligation, protected_dependent ->
  recover_protected_dependent (else ValueError); clamp at resolve_max; no change -> None.

gate(resolve_cur, definition, authority_name=None) -> (allowed: bool, cost_note: str | None)  (RES-03)
  0: allowed only verbs FLEE, ESCAPE, SURRENDER, WAIT, and defs tagged 'protect_dependent' or
     'comply_under_threat'.
  1: everything EXCEPT defs with requires.fear_exposure = true.
  2: everything; defs tagged 'opposes_authority' get cost_note
     f"It means going against {authority_name or 'the people in charge'}."
  3+: everything, no note. (Pure: no reads, no writes.)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..contracts.content import AffordanceDef
from ..contracts.events import Event

if TYPE_CHECKING:
    from ..kernel.store import Tx


def drain(tx: "Tx", actor_id: str, reason: str, cause_event_id: str | None, at: int,
          turn_index: int) -> Event | None:
    raise NotImplementedError("P4")


def recover(tx: "Tx", actor_id: str, reason: str, cause_event_id: str | None, at: int,
            turn_index: int) -> Event | None:
    raise NotImplementedError("P4")


def gate(resolve_cur: int, definition: AffordanceDef, authority_name: str | None = None) -> tuple[bool, str | None]:
    raise NotImplementedError("P4")
