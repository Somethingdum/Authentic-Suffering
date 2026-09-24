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


def ambient_db(store: "Store | Tx", place_id: str) -> float:
    """The exact ambient formula above for one place (P3)."""
    raise NotImplementedError("P3")


def source_point(store: "Store | Tx", event_payload: dict, actor_id: str | None) -> Point:
    """Where a sound comes from: payload anchor_id (its point) / payload place_id + x_m, y_m /
    payload place_id alone (its centre) / else the actor's position. ValueError when none apply."""
    raise NotImplementedError("P3")


def fidelity_for_margin(margin_db: float, rules: "AcousticRules") -> Fidelity:
    """Pure band lookup (P3)."""
    raise NotImplementedError("P3")


def received_db(store: "Store | Tx", source_db: float, source: Point, listener: Point,
                rules: "AcousticRules") -> tuple[float, tuple[str, ...]]:
    raise NotImplementedError("P3")


def receptions(store: "Store | Tx", source_db: float, source: Point, at_ms: int,
               rules: "AcousticRules", *, exclude: set[str] | None = None,
               masking: dict[str, float] | None = None) -> list[Reception]:
    """One Reception per living body (bodies.alive = 1, any kind) that has an acoustic link to the
    source (same place, or any portal chain) — NONE results included, unlinked bodies omitted —
    sorted by listener_id. ``exclude`` removes bodies (the source's own body). Uses each body's
    awareness and attention at ``at_ms``. The listener point is its positions row."""
    raise NotImplementedError("P3")


def partial_words(text: str, event_id: str, listener_id: str) -> str:
    """AUD-07 deterministic fragmenting."""
    raise NotImplementedError("P3")
