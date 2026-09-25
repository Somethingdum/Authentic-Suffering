"""Resolution (Stage 8, P5). Rules RESOLVE-01..06, SEG-03..04, GEST-03, FOCUS-02, G8. The resolver is the only place intents
turn into state change (L2). Writer of ACTION_START / ACTION_COMPLETE / ACTION_BLOCKED /
ACTION_INTERRUPT / CHECK_RESOLVED: 'action.resolve' (no table writes of its own).

resolve_wave(tx, rng, intents, wave_at, turn_index, *, horizon_ms) -> list[Event]
  ``intents`` come from action.intent.barrier (an intent with .blocked set is not started).
  1. Starts, in actor_id order, all at wave_at:
     * blocked -> ACTION_BLOCKED {actor_id, def_id, cause: intent.blocked}; nothing else.
     * the actor's pending ACTION_LAND queue rows (kernel.clock.pending_for) are cancelled
       (clock.cancel, reason 'new_action') and an ACTION_INTERRUPT {actor_id, def_id of the
       cancelled action, cause: 'new_action'} is committed — unless the new intent has the same
       signature as the pending one and carries no speech (the actor carries on: no new start,
       the old landing stands; new words are a new utterance, so an intent with speech always
       starts anew). When the intent does not carry on, the actor's pending SPEECH_SEGMENT rows
       are cancelled too (reason 'new_action'; one voice, one utterance at a time), with one
       SPEECH_CUT per utterance cut (SEG-04, cause 'new_action').
     * ACTION_START (effects module docstring payload; cause = none) — (B4, FOCUS-02) its payload
       also carries attention: intent.attention (None without one).
     * GEST-03 (B4, Actor Spec §9) a gesture (intent.gesture = (g, toward)): right after the
       start, GESTURE {actor_id, gesture: g, target_id: toward} (writer 'action.propagate', no
       writes, cause = the start, at wave_at). It is seen, never heard (mind.perception), and it
       does nothing else — a touch is an attempt, never a gesture.
     * speech (intent.speech; SEG-03, Actor Spec §9): the words go out one segment at a time,
       action.intent.segments(speech.text) in order. Segment k (1-based, of n) is one SPEECH
       {words: the segment, volume, to: [ids] | ['everyone'], source_db =
       AcousticRules.speech_db[volume], armed: the actor holds an item with a firearm or melee
       block in a hand, utterance_id: this ACTION_START's event id, segment: k, segments: n}
       (writer 'action.propagate', actor_id = the speaker, cause = the start), due at say_at +
       ceil(1000 x (words in segments 1..k-1) / 2.5) ms. say_at = wave_at for a SPEAK choice and for
       timing 'before' or 'alongside'; for 'after', the action lands first — at
       effects.land_ms(wave_at, est_duration_s - words / 2.5) instead of step 2's land_at — and
       say_at is that landing time (its segments are placed when step 2 has landed or queued the
       action, so a queued landing fires before its words). Segment 1 at wave_at is committed
       right after the start;
       every other segment due at or before horizon_ms is committed at its due time among step 2's
       landings (after the landings at the same ms); one due later is queued:
       kernel.clock.schedule(tx, due, 'SPEECH_SEGMENT', speaker, {the SPEECH payload},
       source_event_id = the start).
     SEG-04 a segment is said only if, at its due time, the speaker is alive and conscious
       (physical.bodies); otherwise neither it nor any later segment of the utterance is said, and
       one SPEECH_CUT {actor_id, utterance_id, delivered: the segments said, of: n, cause: 'dead' |
       'unconscious' | 'new_action'} (writer 'action.propagate', actor_id = the speaker, cause =
       the start) records where the words stopped. Listeners perceive the segments said, one
       percept each (mind.perception) — so nobody reacts to words that were never said.
  2. Landings: land_at = effects.land_ms(wave_at, bound.est_duration_s) (condition-ended defs:
     wave_at). Order: (land_at, then within one land_at the precedence ladder for intents
     sharing a resource (conflict.precedence, groups in resource order, an intent placed at its
     first group), then actor_id).
     * land_at > horizon_ms -> kernel.clock.schedule(tx, land_at, 'ACTION_LAND', actor_id,
       {intent: intent.intent_to_dict(i), start_event_id}, source_event_id = start) — it lands
       in a later transaction (land_pending).
     * else Landing = effects.land(...); commit ACTION_BLOCKED {actor_id, def_id, cause} at land_at
       when landing.blocked, else ACTION_COMPLETE {actor_id, def_id, result, band, visible: false}
       at landing.complete_at or land_at. Cause of both = the ACTION_START.
  3. Each intent resolves exactly once (G8). Every draw is in prng_ledger (the rng does that).
  Returns every event the wave committed (including those committed by modules), in seq order.
say_pending(tx, row, turn_index) -> list[Event]   (SEG-03..04)
  The SPEECH_SEGMENT handler (kernel.clock dispatch, after TIMER_FIRED): at row.due_at, the
  segment in row.payload is said (one SPEECH, cause = the utterance's start) when SEG-04 allows;
  else the SPEECH_CUT, and the utterance's later SPEECH_SEGMENT rows are cancelled (reason
  'speech_cut'). Returns the events committed.
land_pending(tx, rng, row, turn_index, *, horizon_ms) -> list[Event]
  The ACTION_LAND handler (kernel.clock dispatch; the caller has already committed TIMER_FIRED
  via clock.fire): rebuild the Intent from row.payload, land it at row.due_at exactly as step 2
  (legality is re-checked then — the world may have changed since it started).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.rng import Rng
    from ..kernel.store import Tx
    from .intent import Intent


def resolve_wave(tx: "Tx", rng: "Rng", intents: list["Intent"], wave_at: int, turn_index: int, *,
                 horizon_ms: int) -> list["Event"]:
    raise NotImplementedError("P5")


def say_pending(tx: "Tx", row: dict, turn_index: int) -> list["Event"]:
    raise NotImplementedError("P5")


def land_pending(tx: "Tx", rng: "Rng", row: dict, turn_index: int, *, horizon_ms: int) -> list["Event"]:
    raise NotImplementedError("P5")
from ._impl_p5b import resolve_wave, land_pending  # noqa
