"""Resolve pool (P4; D-107). Rules RES-01..07. Resolve gates affordances; it never modifies a roll.

drain(tx, actor_id, reason, cause_event_id, at, turn_index) -> Event | None
  reason must be a key of RulesConfig.resolve.drains (else ValueError); amount = drains[reason];
  RESOLVE_CHANGE event (writer 'mind.actor' because resolve_cur lives in `actors`) with payload
  {actor_id, reason, delta (negative), resolve (new value)}; clamp at 0; a drain that changes
  nothing (already 0) -> None, no event. Coercion drains Resolve (L7) — it never rolls against
  personality.
recover(tx, actor_id, reason, ...) -> Event | None   reasons: safe_night -> recover_per_safe_night,
  fulfilled_obligation -> recover_fulfilled_obligation, protected_dependent ->
  recover_protected_dependent, shock_passes -> recover_shock_passes (D-107) (else ValueError);
  clamp at resolve_max, and at ceiling(tx, actor_id) (RES-07); no change -> None.

the_talk(tx, actor_id, mind, cause_event_id, at, turn_index) -> Event | None
  RES-06 (D-107) What the Voice leaves in a doomed mind (physical.bodies DOOM-10): 'shattered' ->
  resolve_cur 0; 'broken' -> min(resolve_cur, 1); 'held' -> the drain 'the_talk' (drains['the_talk']).
  One RESOLVE_CHANGE (writer 'mind.actor') with payload {actor_id, reason 'the_talk', delta,
  resolve}; no change, or no actors row (a body nobody plays or models) -> None.

ceiling(store_or_tx, actor_id) -> int | None
  RES-07 (D-107) How far a doomed mind can come back: its dooms row's mind 'shattered' -> 0 until
  shock_over is 1, then 1; 'broken' -> 1; otherwise (held, instant, no doom) None — no ceiling.

gate(resolve_cur, definition, authority_name=None) -> (allowed: bool, cost_note: str | None)  (RES-03)
  0: (Actor Spec §10, AC08: zero Resolve is fear and impairment, never obedience) allowed only
     verbs FLEE, ESCAPE, SURRENDER, WAIT, OBSERVE, SPEAK, TAKE_COVER and HIDE (retreat, escape,
     surrender, silence and freezing, keeping your eyes open, your own voice, protecting
     yourself), and defs tagged 'protect_dependent', 'comply_under_threat', 'low_exposure' or
     'despair' (D-107: the one thing left to someone who can't take any more).
     Compliance is one option among these, never chosen for anyone.
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


def the_talk(tx: "Tx", actor_id: str, mind: str, cause_event_id: str | None, at: int, turn_index: int) -> Event | None:
    raise NotImplementedError("P12")


def ceiling(store_or_tx, actor_id: str) -> int | None:
    raise NotImplementedError("P12")
from ._impl_p4a import drain, recover, gate  # noqa
from ._impl_p4a import ceiling, the_talk  # noqa
