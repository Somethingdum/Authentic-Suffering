"""Reaction gate and waves (Stage 11, P5). Rules TIME-02, TIME-04, REACT-01..04.

material_holders(tx, new_events, turn_index) -> list[tuple[str, int]]
  For each LIVING, conscious actor (actors row; not controller-dependent — the PC is included and
  the pipeline decides what to do with it, L12) that holds a percept of one of ``new_events``
  (percept_log.event_id in their ids), the percept is MATERIAL (REACT-01) when any of:
    a speech percept addressed to the holder at EXACT or PARTIAL;
    an auditory percept of a NOISE whose payload source_db >= 80, or whose source point is within
      10 m of the holder, at PARTIAL or better;
    a visual percept of a HARM, DEATH or FALSE_DEATH on the holder or on a bonded body (affection
      >= 2 toward it, or the same household), or of an ACTION_START with verb 'attack' whose
      target is the holder or a bonded body;
    a visual percept of an ACTION_START of shoot_center_mass / shoot_head targeting the holder
      (a weapon pointed), or a speech percept with detail.armed_at_me;
    a TACTILE percept (the holder's own wound);
    a visual percept of a MOVE by a body the holder has no acquaintance known_name for, made by a
      run_to_anchor / flee / leave_place action (the MOVE's cause is an ACTION_START with that
      def), ending within 20 m of the holder (a sentinel noticing a stranger);
    (P10) a visual percept of a MOVE by an infected body (bodies.kind 'infected'), however made,
      ending within 20 m of the holder (physical.space.distance_to_point): the dead coming near
      are always news, and a watch ends when they do.
  (Visual percepts count at level clear or partial, as the detail records them.)
  Returns (holder_id, trigger_at) pairs sorted by (trigger_at, holder_id), trigger_at = the
  earliest material percept's ``at`` for that holder. A holder whose own event is the trigger is
  never included (it knows what it did).
reaction_time(tx, rng, holder_id, trigger_at) -> int
  trigger_at + rng.range_int(tx, 'resolve', f'react:{holder_id}:{trigger_at}', lo, hi) with (lo,
  hi) = AcousticRules.reaction_window_ms, + 400 when the holder is drowsy or has an active task
  with focus = 1 (REACT-02). The next wave's time is the earliest reaction_time among holders;
  holders whose reaction_time exceeds the horizon do not react in this transaction.
next_wave(tx, rng, new_events, turn_index, wave_index, horizon_ms, *, exclude=frozenset())
    -> tuple[int | None, list[str]]
  Holders in ``exclude`` are dropped before anything is drawn (P7: the turn pipeline passes the
  PC — the player answers next turn, and no draw is spent on its reaction time).
  wave_index is the index the next wave would have (1..). Material holders with reaction_time <=
  horizon_ms: when wave_index <= SchedulerRules.max_reaction_waves -> (earliest reaction time,
  those holders sorted); otherwise (None, those holders sorted): the caller defers them (P7,
  turn.pipeline: pending_reactions, TIME-04). No holders -> (None, []).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.rng import Rng
    from ..kernel.store import Tx


def material_holders(tx: "Tx", new_events: list["Event"], turn_index: int) -> list[tuple[str, int]]:
    raise NotImplementedError("P5")


def reaction_time(tx: "Tx", rng: "Rng", holder_id: str, trigger_at: int) -> int:
    raise NotImplementedError("P5")


def next_wave(tx: "Tx", rng: "Rng", new_events: list["Event"], turn_index: int, wave_index: int,
              horizon_ms: int, *, exclude: frozenset[str] | set[str] = frozenset()) -> tuple[int | None, list[str]]:
    raise NotImplementedError("P5")
