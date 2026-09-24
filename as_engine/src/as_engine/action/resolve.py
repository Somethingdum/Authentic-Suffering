"""Resolution (Stage 8, P5). Rules RESOLVE-01..06, G8. The resolver is the only place intents
turn into state change (L2). Writer of ACTION_START / ACTION_COMPLETE / ACTION_BLOCKED /
ACTION_INTERRUPT / CHECK_RESOLVED: 'action.resolve' (no table writes of its own).

resolve_wave(tx, rng, intents, wave_at, turn_index, *, horizon_ms) -> list[Event]
  ``intents`` come from action.intent.barrier (an intent with .blocked set is not started).
  1. Starts, in actor_id order, all at wave_at:
     * blocked -> ACTION_BLOCKED {actor_id, def_id, cause: intent.blocked}; nothing else.
     * the actor's pending ACTION_LAND queue rows (kernel.clock.pending_for) are cancelled
       (clock.cancel, reason 'new_action') and an ACTION_INTERRUPT {actor_id, def_id of the
       cancelled action, cause: 'new_action'} is committed — unless the new intent has the same
       signature as the pending one (the actor carries on: no new start, the old landing stands).
     * ACTION_START (effects module docstring payload; cause = none).
     * speech (intent.speech): SPEECH {words, volume, to: [ids] | ['everyone'], source_db =
       AcousticRules.speech_db[volume], armed: the actor holds an item with a firearm or melee
       block in a hand} (writer 'action.propagate', actor_id = the speaker, cause = the start).
       Speech takes time: the intent's est_duration_s already includes it (to_intent).
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


def land_pending(tx: "Tx", rng: "Rng", row: dict, turn_index: int, *, horizon_ms: int) -> list["Event"]:
    raise NotImplementedError("P5")
