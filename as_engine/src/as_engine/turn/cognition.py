"""Stage 6 (cognition) and the stage-8 reading of answers (P7). Rules LOD-01/02, LANE-06, INTENT-02,
ECHO-02, WILL-04..11, REPLY-01..02, HOLD-01..02, L6, L7. docs/as/04_TURN_PIPELINE.md §3.3.

decide(tx, session, plan, affs, turn_index, at, *, reaction, answered=frozenset()) -> dict[actor_id, Intent]
  ``answered`` = the pipeline's set of (actor, speech event) pairs already answered this turn (HOLD-02
  reads it).
  One intent for every actor in plan.lod, keyed by actor id — except an actor held in place
  by HOLD-01, which has none this wave (nothing is attempted for it).
  1. Requests, actors in sorted order: COLD -> none. HOT / WARM -> packet = mind.packet.build_packet(
     tx, actor, lod, affs[actor], turn_index, at, reaction=reaction); request =
     cognition_request(session.config, packet, lod, plan.lane[actor], reaction=reaction,
     turn_index=turn_index); a lanes.scheduler.Job(job_id=actor, call_class=request.call_class,
     request, output_model=ActorReplyV2, lane_pref=plan.lane[actor], est_s=SchedulerRules
     .estimated_call_s['actor_cognition_hot' | 'actor_cognition_warm']). All jobs go to ONE
     lanes.scheduler.run_jobs call (both lanes fill at once; LOD changes who thinks with a model,
     never what anyone can do or knows — LOD-01).
  REPLY-01 reading an answer (Actor Spec §7): parse_status 'ok' -> ActorReplyV2.model_validate(
     parsed) (its V1 adapter reads a V1 answer; a validation error is a failure of kind
     'schema_fail'). A decision -> action.intent.to_intent(packet, affs[actor], reply.action,
     lod=lod, source='model', reaction=reaction); an IntentError is a failure whose kind is
     'empty_speech' for IntentError 'empty', else the IntentError kind. A consultation ->
     mind.consult.check(packet, reply.consultation); a reason is a failure of kind
     'bad_consultation', None means it is answered (REPLY-02). Any other parse_status is a failure
     of that kind.
  REPLY-02 at most two decision calls and one repair per decision (Actor Spec §7): an actor whose
     first answer is a valid consultation gets it answered — consulted = mind.consult.answer(tx,
     packet, affs[actor], reply.consultation, the canon affordance defs by id, turn_index, at) —
     and a SECOND request, cognition_request(... build_packet(tx, actor, lod, affs[actor],
     turn_index, at, reaction=reaction, consulted=consulted) ...): the same snapshot (the same
     ``at`` and AffordanceSet), whose schema offers no consultation. All second requests go to one
     more run_jobs call, actors in sorted order. The second answer is read as above (a
     consultation there is a failure of kind 'bad_consultation').
     A failure of kind grammar_fail / schema_fail / empty / hallucinated_choice /
     hallucinated_target / empty_speech / speech_too_long / unsupported_pace /
     hallucinated_expression / bad_inscription / bad_consultation gets ONE repair per decision
     (LANE-06), of whichever call failed: await session.client.call(lanes.requests.repair_request(
     config, the failed request, {raw: resp.raw or resp.text, error: resp.error or kind}, the
     packet of that call, that call's schema without the consultation — the schema
     cognition_schema builds with no consult_kinds), ActorReplyV2), read like a second answer: a
     repair always answers with a decision (Actor Spec §14: it keeps a clearly recoverable choice
     and words and never picks a safer, kinder or more obedient act; the repair prompt says so).
     Repaired ->
     audit.log.repair(tx, FALLBACK_KIND[kind], 6, 'LANE-06', {actor_id, reason: kind},
     turn_index, at, repaired=True). Still failing, a second failure after the repair was spent,
     or a timeout / lane_error / cancelled (no repair: the lane is the problem) -> HOLD-01 with the
     FIRST failure's kind.
  HOLD-01 a failed answer never becomes a choice (Actor Spec AC15, §14; AR10). When the decision is
     consequential (HOLD-02) -> raise DecisionHeld(actor, kind): turn.pipeline rolls the turn back
     — nothing happens, no time passes, the input is not consumed — and tells the player it was not
     played. Otherwise continuation = action.intent.plan_continuation(tx, actor, affs[actor], at,
     turn_index, accepted_only=True): an Intent -> that intent with source 'fallback' and
     DEGRADED_FALLBACK {actor_id, reason: kind, path: 'continued'} (what they already took on goes
     on); None -> NO intent for the actor this wave and DEGRADED_FALLBACK {actor_id, reason: kind,
     path: 'held'} (the body stays as it is; nothing is attempted, perceived or narrated as a
     choice); either way (writer 'turn.pipeline', actor_id, at) and audit.log.repair(tx,
     FALLBACK_KIND.get(kind, 'degraded'), 6, 'LANE-06', {actor_id, reason: kind, path},
     turn_index, at).
  HOLD-02 consequential(tx, actor_id, affs[actor], turn_index, answered) -> bool: someone asked it
     something it has not answered (asks_for(tx, actor_id, turn_index, answered) is not empty) or
     it perceived a threat this turn (affs[actor].threats is not empty) — a new moment where
     consent, refusal, surrender or violence could be at stake, which only the person may decide.
  2. ECHO-02, for every model intent (repaired included) that carries speech: hits =
     narration.lint.check_line(tx, speech.text, RulesConfig.style); non-empty and the decision's
     repair not yet spent -> one repair call (as above; raw = the speech text, error = 'Do not
     repeat these phrases the other person used: ' + '; '.join(sorted(hits))). The new intent is
     kept when it has no speech or its speech is clean (audit.log.repair(..., 'echo_reject', 6,
     'ECHO-02', {actor_id, ngrams}, ..., repaired=True)); otherwise — the repair spent, a repair
     answer that does not read, or one that still echoes — the ORIGINAL intent stands, speech and
     all ('echo_reject', not repaired: a quality issue on record; Actor Spec §11 — a repair that
     fails is not a reason to silence a person, and no committed speech is rewritten).
  3. P10 / W1 — the wet strain's compulsion (the owner, D-77: the urge is to CONTAMINATE — spit
     into water and food, and into the mouths of people asleep; the host is sickened by it, and it
     grows without limit until death. Lore §3.2: by week three nothing stops compliance; 05_ACTORS
     §7: an involuntary act is caused, timed and owned by code). Actors in sorted order, never the
     PC (for the player, urge_pc below): a 'wet' stage from physical.bodies.stages(actor) with
     compulsion >= 2; h = hours since that infection's exposed_at; gap = max(R.compulsion_min_gap_min,
     R.compulsion_cooldown_min x 336 / max(h, 1)) minutes (it comes ever more often as the weeks
     go by); no INVOLUNTARY with actor_id = actor and payload kind 'compulsion' or 'urge' within
     gap minutes before ``at``. The act, the first that is at hand (R = RulesConfig.infected):
       mouth  the nearest living human body in its place within 1.5 m whose awareness is 'asleep'
              (space.point_distance; ties by body_id) -> the core 'spit_in_mouth' def at it;
       give   an item of kind 'water' in one of its hands (hand_l, then hand_r) and the nearest
              living human body within 1.5 m -> the core 'give_item' def (as before: {item} = the
              item's canon name, {target} = 'someone');
       spit   an item of kind 'water' or 'food' in one of its hands (hand_l, then hand_r), else one
              lying loose in its place within 1.5 m of it (by item_id) -> the core 'spit_into' def
              with that item;
     nothing at hand -> nothing happens (its packet already told it how much it wants to).
     Compulsion 3 (weeks three and four): it happens — INVOLUNTARY {actor_id, kind: 'compulsion',
     pathway: 'wet', act, item_id, target_id} (writer 'turn.pipeline', actor_id, at; item_id /
     target_id None where the act has none) and the actor's intent becomes that def built from the
     core affordance record, not its menu: BoundAffordance(def_id, its verb, label / ui_label with
     {item} = the item's canon name and {target} = 'someone', target_id, item_id, est_duration_s
     = duration.base_s, noise_db, check, tags from the def), source 'reflex', speech None, manner
     '', goal '', private_reason '', the same lod — what it had decided is dropped. And it is
     sickened by what it did: mind.actor.adjust_stress(tx, actor, +1, the INVOLUNTARY, at,
     turn_index) and mind.resolve.drain(tx, actor, 'self_disgust', the INVOLUNTARY, at,
     turn_index). Compulsion 2 (week two): it only wants to — INVOLUNTARY {actor_id, kind: 'urge',
     pathway: 'wet', act, item_id, target_id} and mind.resolve.drain(tx, actor, 'resisting_urge',
     that event, at, turn_index): holding back costs; its intent stands.
  4. H1 — breaking points (mind.temper TEMPER-06). Actors of plan.lod in sorted order with an
     INVOLUNTARY event of this turn at ``at`` whose actor_id is the actor and payload kind is
     'outburst' (never the PC: take_in never snaps it); T = its toward_id. A snap is code's act, like the
     compulsion: the intent is built from a core affordance def, not picked from the menu —
     BoundAffordance(def_id, its verb, label / ui_label = the def's own (unfilled: a reflex is
     never shown as an option), target_id, destination_id, item_id None, est_duration_s,
     noise_db, check, tags from the def) — with source 'reflex', speech None, manner '', goal '',
     private_reason '', lod = plan.lod[actor], and it replaces whatever the actor had decided (a
     snap is not a choice). Neither the resolve gate nor the menu applies: a snap is the moment
     nerve runs out. By payload outlet:
       fists   'punch' at T (est_duration_s = duration.base_s) when the actor is conscious with a
               hand free (physical.bodies.capacity hands_free >= 1), T is within
               RulesConfig.temper.fists_reach_m (space.point_distance), and T is not a child
               (bodies.age_band infant, child or preteen) nor a body the actor is guardian_of
               (household_members.guardian_of) — else as 'words'.
       words   the intent the model gave must carry speech whose ``to`` contains T at volume
               'raised' or 'shout' — then it stands; when it does not and the decision's repair is
               not spent -> one repair (error: "You have snapped at <P#>: say what you say to them,
               raised or shouted.", P# = T's handle in its packet); still not — or no model
               decided for it this wave — -> as 'flight'.
       cold    only when the actor is mobile (capacity): a portal of its place that is open and
       flight  admits it (space.admits) -> 'leave_place' (no referent; est_duration_s =
               duration.base_s; effects leave_place takes the nearest way out); else the anchor of
               its place whose point is farthest from T's point (ties by anchor_id) ->
               'move_to_anchor' to it (est_duration_s = duration.base_s + duration.per_meter_s x
               the straight-line distance from the actor to the anchor); else, or not mobile, no
               intent this wave (it stays, seething).
       tears   'rest' (est_duration_s = duration.base_s): it sits down and breaks down.
  Every call is logged by the pipeline through LaneClient.on_call; nothing here writes lm_calls.

urge_pc(tx, rng, pc_id, intent, turn_index, at) -> Intent   (W1, D-80: actions pass through)
  What the player typed mostly happens. The PC with a 'wet' stage of compulsion 3, outside step 3's
  gap, with an act at hand (step 3's order) -> rng.chance(tx, 'mind', f"pc_urge:{pc_id}:{at}",
  RulesConfig.infected.pc_urge_share.get(that stage's name, 0.0)): true -> the act happens exactly
  as step 3's compulsion 3 (INVOLUNTARY with payload pc: true as well, the stress and the
  self_disgust drain) and it returns the act's reflex Intent (source 'reflex', lod = intent.lod);
  the story says it was not their choice (narration.narrator pc_state_lines). Otherwise, or with no
  stage, no act or the gap not passed, it returns ``intent`` unchanged.

cognition_request(config, packet, lod, lane, *, reaction, turn_index) -> LMRequest
  call class ACTOR_REACTION when reaction else ACTOR_COGNITION; json_schema =
  lanes.schemas.cognition_schema(affordance handles, entity handles, consult_kinds =
  packet.consult_kinds, families = packet.families, subject_handles = the packet's P# handles then
  its S# handles, each in number order (none when it offers no consultation), gesture_handles /
  attention_handles = the handles of packet.gestures / packet.attention_points (B4)) — a
  reaction's packet offers no consultation, gesture or attention point. HOT: regime =
  config.hot_cognition and the schema is attached only when config.lanes[Lane.A]
  .structured_with_thinking == 'supported' or the regime has thinking off (otherwise the JSON is
  extracted from the text and a failure is repaired, LANE-06); WARM: regime = config.regimes[call
  class] (build_request's default), schema attached. The call is
  lanes.requests.build_request(config, call class, turn_index=turn_index, actor_id=packet.actor_id,
  context=packet, json_schema=…, regime=… (HOT only), lane=lane, p=packet) — actor_id is required:
  lm_calls.actor_id is how a call is traced to the mind that made it.

FALLBACK_KIND: {grammar_fail: grammar_fail, schema_fail: schema_fail, empty: grammar_fail,
  timeout: timeout, lane_error: lane_down, cancelled: timeout, hallucinated_choice:
  hallucinated_ref, hallucinated_target: hallucinated_ref, empty_speech: schema_fail,
  speech_too_long: schema_fail, unsupported_pace: schema_fail, hallucinated_expression:
  hallucinated_ref, bad_inscription: schema_fail, bad_consultation: schema_fail} — the
  error_repair_log kind for each failure (commit gate S11 checks kinds against ERROR_KINDS).

DecisionHeld(actor_id, kind)   (HOLD-01) a turn.intake.Rejected with code 'decision_held' and message
  HELD_MESSAGE (out of the world: it names nobody — who it was is in the audit row the pipeline
  writes).

--- Answers to asks (the firewall at work; L6: a request never becomes an action) ---
asks_for(tx, actor_id, turn_index, answered) -> list[dict]
  The actor's speech percepts of this turn with detail.addressed_to_me, fidelity EXACT or PARTIAL
  and non-empty detail.words, whose (actor_id, event_id) is not in ``answered``; ordered (at,
  percept_id). Each dict is the percept row with ``detail`` parsed and ``speaker`` = the SPEECH
  event's actor_id. The pipeline collects them for every actor with an intent (the PC included —
  the player can refuse an Actor too, L12) BEFORE the barrier: what each mind had heard when it
  decided.
perceived_entities(tx, actor_id, turn_index) -> dict[str, str]
  The lookup mind.firewall.request_signature needs, lowercase phrase -> id, first entry wins, in
  this order: the actor's acquaintance rows by subject_id (known_name, then description); the
  anchors of its place by anchor_id (name); the portals of its place by portal_id (name); the
  items it perceived this turn (percept source_id 'itm_…', by id) then the items it holds (by id),
  each by its ItemDef name. (B5) Besides, every anchor and portal of its place also under
  f'anchor|{name}' / f'portal|{name}' (by id, first entry wins within each kind) — what
  request_signature needs when a door and its anchors share a name.
record_responses(tx, intents, affs, asks, turn_index, wave_at, first_seq) -> list[tuple]
  Called right after stage 8 resolved the wave (``first_seq`` = the last event seq before it).
  For each actor in sorted(asks) with an intent, for each of its asks in order: form =
  firewall.classify_form(words, weapon_pointed_at_receiver = detail.armed_at_me); standing =
  firewall.classify_standing(tx, speaker, actor, words); effective = firewall.effective_form(form,
  standing). Not one of ASK_FORMS ('request', 'order', 'demand', 'threat') -> (actor, event_id,
  'not_an_ask'). Otherwise signature = firewall.request_signature(words, speaker, actor,
  perceived_entities(...)); entrenched_block = an affs[actor].rejected entry whose def_id is the
  signature's def id (its text before the first ':') and whose gate is 'moral' — an immutable
  line; the duty gate rejects nothing, C05 — (False when the actor has no AffordanceSet);
  response = firewall.classify_response(signature, intent.bound, the intent's speech text or
  None, actors.resolve_cur, effective, entrenched_block=…, resolve_drained_this_turn = a
  RESOLVE_CHANGE event of this turn by the actor with payload.delta < 0, steps_toward = (AC09) where
  the signature's target is: a portal's anchor_a and anchor_b, the anchor_id of a body's position
  or of an item lying loose; empty for '*') -> (actor, event_id, response.value), and:
    REFUSAL / ENTRENCHED_REFUSAL -> firewall.record_refusal(tx, actor, speaker, signature,
      perception.norm_text(words) (the summary: 'hand me the revolver'), reason, [event_id],
      intent.private_reason[:200] (the cost it cites), entrenched = ENTRENCHED_REFUSAL, wave_at,
      turn_index, event_id), reason = the blocking gate for an entrenched refusal; else 'fear'
      when the actor's relationship toward the speaker has fear >= 2; else 'distrust' when it has
      no relationship row toward the speaker or trust <= -1 (a stranger); else 'cost'.
    (AC09 — the words are recorded first; no yes is a lie by itself)
    READY / RELUCTANT / COERCED_COMPLIANCE -> firewall.revise_refusal(tx, actor, speaker, signature,
      wave_at, turn_index, event_id) (a person can change their mind: WILL-12).
    DEFERRED_ASSENT -> mind.mind.open_loop(tx, actor, 'promise_made', f'I said I would:
      {perception.norm_text(words)} — "{the speech text}"', [speaker], strength 1, cause = the
      actor's first SPEECH event with seq > first_seq (else the ask's event), wave_at,
      turn_index, links = [EventLink(the ask's event id, 'answered')] when the cause is that SPEECH
      (B5c, C10)): their own understanding of what they promised (Actor Spec §12; the asker's
      understanding is the asker's). (B5d) When that SPEECH exists, also mind.promise.hold(tx,
      actor, promiser_id = actor, promisee_id = speaker, category = mind.promise.CATEGORY_OF_DEF
      .get(the signature's def, 'assist'), text = the loop's text, object_id = the signature's
      target (None for '*'), condition = the speech text, source_event_id = that SPEECH, loop_id =
      the loop, status 'accepted', wave_at, turn_index).
    PREPARING -> (B5d) a yes and a step toward it: when the actor's SPEECH exists,
      mind.promise.hold as for DEFERRED_ASSENT (text f'I said I would: {norm_text(words)} —
      "{the speech text}"') but with no loop (loop_id None), condition None and status
      'in_progress'.
    UNRESOLVED_ASSENT -> firewall.record_unmet_assent(tx, actor, speaker, signature, the speech
      text, intent.bound.def_id, that SPEECH event's id, wave_at, turn_index, ask_event_id = the
      ask's event id).
    CLARIFYING -> nothing more (the ledger has it).
  The pipeline adds (actor, event_id) to its answered set (an ask is answered once, in the wave
  its hearer first decided after hearing it) and writes the list into turn_ledger stage 8 detail
  {'responses': [[actor, event_id, response], ...]}.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .intake import Rejected

if TYPE_CHECKING:
    from ..action.intent import Intent
    from ..contracts.common import LOD, Lane
    from ..contracts.lanes import LMRequest
    from ..contracts.mind import SkullPacket
    from ..contracts.settings import EngineConfig
    from ..kernel.rng import Rng
    from ..kernel.store import Tx
    from ..lanes.scheduler import CognitionPlan
    from ..mind.affordance import AffordanceSet
    from ..service.session import Session

HELD_MESSAGE = ("Someone's decision at a moment that matters could not be read (the model's answer was unusable "
                "twice), so this turn was not played. Nothing has happened. Send it again to try once more.")

FALLBACK_KIND: dict[str, str] = {
    "grammar_fail": "grammar_fail", "schema_fail": "schema_fail", "empty": "grammar_fail", "timeout": "timeout",
    "lane_error": "lane_down", "cancelled": "timeout", "hallucinated_choice": "hallucinated_ref",
    "hallucinated_target": "hallucinated_ref", "empty_speech": "schema_fail", "speech_too_long": "schema_fail",
    "unsupported_pace": "schema_fail", "hallucinated_expression": "hallucinated_ref", "bad_inscription": "schema_fail",
    "bad_consultation": "schema_fail",
}
ASK_FORMS: tuple[str, ...] = ("request", "order", "demand", "threat")


class DecisionHeld(Rejected):
    """HOLD-01 (implemented): a consequential decision whose answer could not be used. The turn is
    not played; the player is told, out of the world."""

    def __init__(self, actor_id: str, kind: str):
        super().__init__("decision_held", HELD_MESSAGE)
        self.actor_id, self.kind = actor_id, kind


async def decide(tx: "Tx", session: "Session", plan: "CognitionPlan", affs: dict, turn_index: int, at: int, *,
                 reaction: bool, answered: set | frozenset = frozenset()) -> dict[str, "Intent"]:
    raise NotImplementedError("P7")


def cognition_request(config: "EngineConfig", packet: "SkullPacket", lod: "LOD", lane: "Lane", *, reaction: bool,
                      turn_index: int) -> "LMRequest":
    raise NotImplementedError("P7")


def urge_pc(tx: "Tx", rng: "Rng", pc_id: str, intent: "Intent", turn_index: int, at: int) -> "Intent":
    raise NotImplementedError("P10")


def consequential(tx: "Tx", actor_id: str, affordances: "AffordanceSet", turn_index: int, answered: set) -> bool:
    raise NotImplementedError("P7")


def asks_for(tx: "Tx", actor_id: str, turn_index: int, answered: set) -> list[dict]:
    raise NotImplementedError("P7")


def perceived_entities(tx: "Tx", actor_id: str, turn_index: int) -> dict[str, str]:
    raise NotImplementedError("P7")


def record_responses(tx: "Tx", intents: dict[str, "Intent"], affs: dict, asks: dict[str, list[dict]], turn_index: int,
                     wave_at: int, first_seq: int) -> list[tuple[str, str, Any]]:
    raise NotImplementedError("P7")
from ._impl_cognition import *  # noqa
