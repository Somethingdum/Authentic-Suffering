"""Audibility compiler (P3). THE highest-leverage code in the game. Rules AUD-01..08.

received_db(source_db, source point, listener point):
  same place:  received = source_db - k * log2(max(d, 1))
               k = indoor_attenuation_per_doubling_db (4.5) if the place is indoor, else
                   attenuation_per_doubling_db (6.0); d = euclidean metres.
  other place: find the path of minimum TOTAL LOSS over portals INCLUDING walls/fences
               (Dijkstra; loss per portal = open_loss_db if is_open else effective seal
                = seal_db * (1 - damage/4); tie -> fewer portals, then portal_id order).
               d_total = sum of leg distances along that path (source point -> portal point ->
               ... -> listener point).
               received = source_db - k_src * log2(max(d_total, 1)) - sum(portal losses)
               where k_src is chosen by the SOURCE place's indoor flag.
  unreachable (no link at all): -inf (fidelity none).

margin = received - max(ambient_db(listener place), masking_db) - attention_penalty
  ambient_db(place) = exactly:
      a = place.ambient_db
      if place is outdoor: a += world_clock.wind_level * 8; if weather == 'rain': a = max(a, 50);
                           if weather == 'storm': a = max(a, 65)
      a -= (warning_slack - 5)          (world_params sim.warning_slack; 5 when the run has no
                                         world_params row, e.g. scenarios -> 0)
      ambient = max(a, 20)
  — symmetric for every listener (AUD-06).
  masking_db = the loudest OTHER sound reaching the listener in the same 1-second window, minus 3 —
  the CALLER computes it and passes ``masking`` {listener_id: masking_db}; absent -> no masking.
  attention_penalty = divided_attention_penalty_db (4) when the listener is SPEAKING (it is the
  actor of a SPEECH event with at_ms - 2000 < at <= at_ms) or has an active task with focus = 1,
  else 0.
awareness: ASLEEP listeners register only when received >= asleep_threshold_db (55) AND margin >=
  tone_margin_db: fidelity is then TONE_ONLY (never better) and an AWARENESS_CHANGE (wake) follows;
  otherwise NONE and they sleep on. DROWSY: margin -= drowsy_penalty_db.
  UNCONSCIOUS/DEAD: NONE.
fidelity: margin >= exact_margin_db -> EXACT; >= partial_margin_db -> PARTIAL; >= tone_margin_db ->
  TONE_ONLY; else NONE.
Privacy is physical (AUD-05 / CROWD-02): nothing in the words of an utterance changes any of the above.

PARTIAL speech rendering (AUD-07): words = text.split() (whitespace split, punctuation stays
attached); keep word i iff
  hashlib.blake2b(f"{event_id}:{listener_id}:{i}".encode()).digest()[0] < 150   (default 64-byte
  digest; ≈59% kept)
emit kept words in order and ONE "…" for each maximal run of dropped words; join with single
spaces. Deterministic, per listener, so two partial listeners hear different fragments
(vectors: tests/fixtures/vectors/acoustics.json 'partial_words'). TONE_ONLY renders as '' with a tone description from the volume.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..contracts.common import Fidelity

if TYPE_CHECKING:
    from ..contracts.settings import AcousticRules
    from ..kernel.store import Store, Tx


@dataclass(frozen=True)
class Point:
    place_id: str
    x_m: float
    y_m: float


@dataclass(frozen=True)
class Reception:
    listener_id: str
    received_db: float
    margin_db: float
    fidelity: Fidelity
    path_portals: tuple[str, ...]
    wakes: bool = False



import hashlib as _hashlib
import heapq as _heapq
import json as _json
import math as _math


def _row(s, sql, params=()):
    r = s.query_one(sql, params)
    return dict(r) if r is not None else None


def _params(s):
    r = s.query_one("SELECT params_json FROM world_params WHERE id=1")
    if r is None:
        return 5
    return _json.loads(r[0])["sim"]["warning_slack"]


def ambient_db(store: "Store | Tx", place_id: str) -> float:
    """The exact ambient formula above for one place (P3)."""
    p = _row(store, "SELECT * FROM places WHERE place_id=?", (place_id,))
    c = _row(store, "SELECT * FROM world_clock WHERE id=1")
    a = p["ambient_db"]
    if not p["indoor"]:
        a += c["wind_level"] * 8
        if c["weather"] == "rain":
            a = max(a, 50)
        if c["weather"] == "storm":
            a = max(a, 65)
    a -= (_params(store) - 5)
    return max(a, 20)


def source_point(store: "Store | Tx", event_payload: dict, actor_id: str | None) -> Point:
    """Where a sound comes from: payload anchor_id (its point) / payload place_id + x_m, y_m /
    payload place_id alone (its centre) / else the actor's position. ValueError when none apply."""
    payload = event_payload   # the contract names it event_payload
    from ..physical.space import _place_centre
    if payload.get("anchor_id"):
        a = _row(store, "SELECT place_id, x_m, y_m FROM anchors WHERE anchor_id=?", (payload["anchor_id"],))
        return Point(a["place_id"], a["x_m"], a["y_m"])
    if payload.get("place_id"):
        if payload.get("x_m") is not None:
            return Point(payload["place_id"], payload["x_m"], payload["y_m"])
        x, y = _place_centre(store, payload["place_id"])
        return Point(payload["place_id"], x, y)
    if actor_id:
        r = _row(store, "SELECT place_id, x_m, y_m FROM positions WHERE body_id=?", (actor_id,))
        if r:
            return Point(r["place_id"], r["x_m"], r["y_m"])
    raise ValueError("sound without a source point")


def fidelity_for_margin(margin_db: float, rules: "AcousticRules") -> Fidelity:
    """Pure band lookup (P3)."""
    if margin_db >= rules.exact_margin_db:
        return Fidelity.EXACT
    if margin_db >= rules.partial_margin_db:
        return Fidelity.PARTIAL
    if margin_db >= rules.tone_margin_db:
        return Fidelity.TONE_ONLY
    return Fidelity.NONE


def _loss(p):
    return p["open_loss_db"] if p["is_open"] else p["seal_db"] * (1 - p["damage"] / 4)


def _min_loss_path(store, src_place, dst_place):
    portals = [dict(r) for r in store.query("SELECT * FROM portals ORDER BY portal_id")]
    heap = [(0.0, 0, (), src_place, ())]
    best = {}
    while heap:
        loss, n, key, place, seq = _heapq.heappop(heap)
        if place == dst_place:
            return loss, seq
        if place in best:
            continue
        best[place] = (loss, n, key)
        for p in portals:
            if place not in (p["place_a"], p["place_b"]):
                continue
            other = p["place_b"] if p["place_a"] == place else p["place_a"]
            if other in best:
                continue
            _heapq.heappush(heap, (loss + _loss(p), n + 1, key + (p["portal_id"],), other, seq + ((p, place, other),)))
    return None


def received_db(store: "Store | Tx", source_db: float, source: Point, listener: Point,
                rules: "AcousticRules") -> tuple[float, tuple[str, ...]]:
    from ..physical.space import portal_point
    sp = _row(store, "SELECT indoor FROM places WHERE place_id=?", (source.place_id,))
    k = rules.indoor_attenuation_per_doubling_db if sp["indoor"] else rules.attenuation_per_doubling_db
    if source.place_id == listener.place_id:
        d = _math.dist((source.x_m, source.y_m), (listener.x_m, listener.y_m))
        return source_db - k * _math.log2(max(d, 1)), ()
    r = _min_loss_path(store, source.place_id, listener.place_id)
    if r is None:
        return float("-inf"), ()
    loss, seq = r
    d = 0.0
    cur = (source.x_m, source.y_m)
    for p, a, b in seq:
        d += _math.dist(cur, portal_point(store, p["portal_id"], a))
        cur = portal_point(store, p["portal_id"], b)
    d += _math.dist(cur, (listener.x_m, listener.y_m))
    return source_db - k * _math.log2(max(d, 1)) - loss, tuple(p["portal_id"] for p, _, _ in seq)


def _linked(store, a, b):
    if a == b:
        return True
    return _min_loss_path(store, a, b) is not None


def receptions(store: "Store | Tx", source_db: float, source: Point, at_ms: int,
               rules: "AcousticRules", *, exclude: set[str] | None = None,
               masking: dict[str, float] | None = None) -> list[Reception]:
    """One Reception per living body (bodies.alive = 1, any kind) that has an acoustic link to the
    source (same place, or any portal chain) — NONE results included, unlinked bodies omitted —
    sorted by listener_id. ``exclude`` removes bodies (the source's own body). Uses each body's
    awareness and attention at ``at_ms``. The listener point is its positions row."""
    exclude = exclude or set()
    masking = masking or {}
    out = []
    for r in store.query("SELECT b.body_id, b.awareness, p.place_id, p.x_m, p.y_m FROM bodies b JOIN positions p ON p.body_id=b.body_id WHERE b.alive=1 ORDER BY b.body_id"):
        bid = r[0]
        if bid in exclude:
            continue
        if not _linked(store, source.place_id, r[2]):
            continue
        lis = Point(r[2], r[3], r[4])
        rec, path = received_db(store, source_db, source, lis, rules)
        amb = max(ambient_db(store, r[2]), masking.get(bid, float("-inf")))
        pen = 0.0
        if store.query_one("SELECT 1 FROM events WHERE type='SPEECH' AND actor_id=? AND at>? AND at<=?", (bid, at_ms - 2000, at_ms)) or \
           store.query_one("SELECT 1 FROM tasks WHERE actor_id=? AND status='active' AND focus=1", (bid,)):
            pen = rules.divided_attention_penalty_db
        margin = rec - amb - pen
        aw = r[1]
        wakes = False
        if aw in ("unconscious", "dead"):
            fid = Fidelity.NONE
        elif aw == "asleep":
            if rec >= rules.asleep_threshold_db and margin >= rules.tone_margin_db:
                fid = Fidelity.TONE_ONLY
                wakes = True
            else:
                fid = Fidelity.NONE
        else:
            if aw == "drowsy":
                margin -= rules.drowsy_penalty_db
            fid = fidelity_for_margin(margin, rules)
        out.append(Reception(bid, rec, margin, fid, path, wakes))
    return out


def partial_words(text: str, event_id: str, listener_id: str) -> str:
    """AUD-07 deterministic fragmenting."""
    words = text.split()
    out = []
    dropping = False
    for i, w in enumerate(words):
        keep = _hashlib.blake2b(f"{event_id}:{listener_id}:{i}".encode()).digest()[0] < 150
        if keep:
            out.append(w)
            dropping = False
        elif not dropping:
            out.append("…")
            dropping = True
    return " ".join(out)
