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
  FOCUS-02 (B4, Actor Spec §9; built with P5's resolver) attention: A = payload.attention of the
          observer's latest ACTION_START (by seq) with at <= at_ms (none, or None: no attention).
          The subject is A, or A is a portal and the subject's anchor is that portal's anchor_a
          or anchor_b -> score + 1; A is set and the subject is not -> score - 1 (eyes on one
          thing miss others). A new attempt without attention ends it.
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



import json as _json
import math as _math


def visibility_score(light: int, observer_p: int, distance_m: float, concealment: int,
                     hidden: bool, moved: bool) -> int:
    """Pure formula from the module docstring (P3)."""
    from ..contracts.common import attr_mod
    return light + (attr_mod(observer_p) - 3) - _math.floor(distance_m / 10) - concealment - (2 if hidden else 0) + (1 if moved else 0)


def band(score: int) -> Visibility:
    return "clear" if score >= 3 else "partial" if score >= 1 else "silhouette" if score >= -1 else "none"


def _row(s, sql, params=()):
    r = s.query_one(sql, params)
    return dict(r) if r is not None else None


def _thermal(store, body_id):
    b = _row(store, "SELECT kind FROM bodies WHERE body_id=?", (body_id,))
    if b["kind"] == "lurker":
        return True
    if b["kind"] == "infected":
        st = _row(store, "SELECT type_id FROM infected_state WHERE body_id=?", (body_id,))
        canon = store.canon if getattr(store, "canon", None) is not None else store.store.canon
        if st:
            return bool(canon.find("infected", st["type_id"]).senses.thermal)
    return False


def light_at(store: "Store | Tx", body_id: str, at_ms: int) -> int:
    """P5 (checks need it; factor it out of ``visibility``): the light that falls on this body —
    the 'light' rule of the module docstring for a subject, without the thermal substitution."""
    subject_id = body_id   # the contract names it body_id
    from ..kernel.clock import daylight_level
    from ..physical.space import distance_m
    pos = _row(store, "SELECT * FROM positions WHERE body_id=?", (subject_id,))
    pl = _row(store, "SELECT * FROM places WHERE place_id=?", (pos["place_id"],))
    if pl["indoor"]:
        light = pl["light_level"]
    else:
        c = _row(store, "SELECT weather FROM world_clock WHERE id=1")
        light = daylight_level(at_ms, c["weather"])
    canon = store.canon if getattr(store, "canon", None) is not None else store.store.canon
    for r in store.query("SELECT i.def_ref, i.props, p.x_m, p.y_m FROM items i JOIN positions p ON p.body_id=i.holder_body "
                         "WHERE p.place_id=? AND i.holder_slot IN ('hand_l','hand_r')", (pos["place_id"],)):
        d = canon.get(r[0])
        if d.kind == "light" and _json.loads(r[1]).get("on") and distance_m(r[2], r[3], pos["x_m"], pos["y_m"]) <= 6.0:
            light = max(light, 3)
    return light


def visibility(store: "Store | Tx", observer_id: str, subject_id: str, at_ms: int) -> Visibility:
    from ..physical.space import line_of_sight, point_distance
    ob = _row(store, "SELECT * FROM bodies WHERE body_id=?", (observer_id,))
    if not ob["alive"] or ob["awareness"] in ("asleep", "unconscious", "dead"):
        return "none"
    if not line_of_sight(store, observer_id, subject_id):
        return "none"
    light = light_at(store, subject_id, at_ms)
    if _thermal(store, observer_id) and light <= 1:
        light = 4
    p = _json.loads(ob["special"])["P"]
    d = point_distance(store, observer_id, subject_id) or 0.0
    pos = _row(store, "SELECT * FROM positions WHERE body_id=?", (subject_id,))
    sb = _row(store, "SELECT posture FROM bodies WHERE body_id=?", (subject_id,))
    conc = 0
    if pos["anchor_id"]:
        a = _row(store, "SELECT cover, concealment FROM anchors WHERE anchor_id=?", (pos["anchor_id"],))
        conc = a["concealment"]
        if sb["posture"] in ("prone", "crouched") and a["cover"] >= 2:
            conc += 1
    moved = store.query_one("SELECT 1 FROM events WHERE type='MOVE' AND actor_id=? AND at>? AND at<=? AND json_extract(payload,'$.from_place') IS NOT NULL", (subject_id, at_ms - 1000, at_ms)) is not None
    sc = visibility_score(light, p, d, conc, bool(pos["hidden"]), moved)
    r = store.query_one("SELECT json_extract(payload,'$.attention') FROM events WHERE type='ACTION_START' AND actor_id=? AND at<=? "
                        "ORDER BY seq DESC LIMIT 1", (observer_id, at_ms))
    A = r[0] if r else None
    if A:
        hit = subject_id == A
        if not hit and str(A).startswith("prt_") and pos["anchor_id"]:
            pr = store.query_one("SELECT anchor_a, anchor_b FROM portals WHERE portal_id=?", (A,))
            hit = pr is not None and pos["anchor_id"] in (pr[0], pr[1])
        sc += 1 if hit else -1
    return band(sc)
