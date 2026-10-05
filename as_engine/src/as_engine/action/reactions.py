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
      are always news, and a watch ends when they do — (D-233) the first such move of any of the
      dead the holder sees this turn (no visual percept of the holder's, this turn_index, of an
      earlier MOVE — by seq — of an infected body that ended within 20 m of where the holder is now),
      and after it only a move ending within DEAD_NEAR_M of the holder: the dead already seen coming
      are news again when one is upon them, not at every step nor with every one that follows;
    (D-137) a visual percept of an ACTION_START of equip_item whose item is a weapon (its def has a
      firearm or a melee block) by a body within 20 m of the holder (a weapon drawn);
    a visual percept of an ACTION_START with verb 'manipulate' whose target is the holder or a
      bonded body (something done to you or yours: clothes pulled off, gore smeared, a body cut);
    a visual percept of an ITEM_TRANSFER that takes what the holder knows is theirs (action.cascade's
      theft victims, D-129: into another's hands, the holder believing it theirs, their household's or
      their group's);
    a visual percept of a GESTURE made toward the holder (payload target_id the holder);
    a visual percept of a surrender (an ACTION_START with verb 'surrender', or a GESTURE
      'empty_hands') by a body the holder was fighting: an ACTION_START with verb 'attack' by either
      of them at the other in the 60 s up to it.
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

DEAD_NEAR_M: float = 5.0      # D-233: one of the dead already seen coming is news again this close

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
from ._impl_p5b import material_holders, reaction_time, next_wave  # noqa
