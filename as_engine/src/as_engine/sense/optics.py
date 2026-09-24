"""Visual observation (P3). Rules VIS-01..05. Separate from audibility (plan §7.3).

visibility(observer, subject) -> 'clear' | 'partial' | 'silhouette' | 'none'
  none if the observer is dead or not alive, or its awareness is asleep / unconscious / dead, or
  not space.line_of_sight(observer, subject).
  light = the SUBJECT's place light_level (0..4) — what lights the subject; outdoor places
          (indoor = 0) use clock.daylight_level(at_ms, world_clock.weather) instead of their stored
          value; any body in the subject's place holding (hand_l / hand_r) an item of kind 'light'
          whose props.on is true raises light to max(light, 3) when the subject is within 6 m of
          that body (the holder lights itself too).
  distance_m = physical.space.point_distance (along the portal path when in different places).
  thermal observers (lurker, or infected type with senses.thermal) treat light as 4 when light <= 1.
  score = light + (attr_mod(observer P) - 3) - floor(distance_m / 10) - subject_concealment
          - (2 if the subject is hidden) + (1 if the subject moved this second)
  attr_mod = contracts.common.attr_mod; observer P = bodies.special['P'].
  subject_concealment = anchor.concealment of the subject's anchor (0 when none), + 1 when the
          subject posture is prone or crouched AND that anchor's cover >= 2.
  hidden = positions.hidden = 1. moved = the subject is the body (actor_id) of a MOVE event
          with at_ms - 1000 < at <= at_ms whose payload.from_place is not null (being placed by
          the scenario loader or worldgen is not movement).
  clear >= 3; partial >= 1; silhouette >= -1; else none.
What each level reveals (VIS-03): clear = identity if known to the observer, held items, wounds
visible (severe+), action; partial = rough description (build, clothing colour), gross action;
silhouette = 'a figure', moving or still.

observed_social(observer, subjects, behaviour) (VIS-04): leaning close, whispering, passing an item
low, a sudden silence — produce VISUAL percepts with an inference hint even when speech was NONE
(CROWD-05).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from ..kernel.store import Store, Tx

Visibility = Literal["clear", "partial", "silhouette", "none"]


def light_at(store: "Store | Tx", body_id: str, at_ms: int) -> int:
    """P5 (checks need it; factor it out of ``visibility``): the light that falls on this body —
    the 'light' rule of the module docstring for a subject, without the thermal substitution."""
    raise NotImplementedError("P5")


def visibility(store: "Store | Tx", observer_id: str, subject_id: str, at_ms: int) -> Visibility:
    raise NotImplementedError("P3")


def visibility_score(light: int, observer_p: int, distance_m: float, concealment: int,
                     hidden: bool, moved: bool) -> int:
    """Pure formula from the module docstring (P3)."""
    raise NotImplementedError("P3")


def band(score: int) -> Visibility:
    raise NotImplementedError("P3")
