"""Intent construction and the intent barrier (P4/P5). Rules INTENT-01..09, L2, L3, L5.

An Intent is what a mind attempts. It is built by CODE from a decision — the ActionPayload of an
ActorReplyV2 (Actor Spec §7) —, the player's IntakeOutput, a V1 CognitionOutput (tests and the V1
adapter's callers), or from plan continuation for COLD actors, and the packet's handle map:

    Intent(actor_id, bound: BoundAffordance, speech: SpeechAct | None, manner, goal,
           private_reason, source: 'model'|'plan'|'reflex'|'human'|'fallback'|'pending', lod,
           blocked=None, pace='normal', inscription=None)
    SpeechAct(text, to, volume, delivery='ordinary', timing='alongside')
  ``manner`` is colour only (the PC's dossier colouring, SYM-02, and the narrator): nothing
  mechanical reads it. ``pace`` is the mechanical mode (INTENT-07; action.effects.situation).

to_intent(packet, affordances, output, *, lod, source, reaction=False) -> Intent | IntentError
  (INTENT-02, INTENT-07..09). ``output`` is an ActionPayload, an IntakeOutput or a CognitionOutput.
  * output.choice 'NONE' (IntakeOutput) -> IntentError 'none_choice' (detail = none_reason).
  * output.choice must be a handle present in packet.handles AND its signature must equal the
    signature of an option of affordances.pool — the menu and whatever a consultation added are
    drawn from it (a set with an empty pool: its options) — else IntentError 'hallucinated_choice'.
  * speech.to handles must be entity handles of this packet or 'everyone' (else IntentError
    'hallucinated_target'); they map to internal ids ('everyone' stays); an empty ``to`` means
    ('everyone',).
  * INTENT-08 an Actor's answer (source 'model') with more than 100 words of speech
    (whitespace-separated), or more than 12 in a reaction (reaction=True) -> IntentError
    'speech_too_long' (Actor Spec §7: long talk goes on over further decisions). The player's own
    words are never refused for length. delivery and timing are copied into the SpeechAct (a V1
    speech: ordinary, alongside).
  * speech with a non-SPEAK choice is allowed; if it exceeds 12 words the bound option's
    est_duration_s grows by words / 2.5 seconds (speech consumes real time, TIME-05) — the
    Intent carries a copy of the BoundAffordance with the new duration. A SPEAK choice's
    duration becomes max(its est_duration_s, words / 2.5).
  * INTENT-07 pace (a decision's or the player's; a V1 answer's is 'normal'): 'normal', or one of
    the chosen option's paces (BoundAffordance.paces, copied from AffordanceDef.paces) — else
    IntentError 'unsupported_pace' (an IntakeOutput's unsupported pace is read as 'normal': the
    player's words are not a protocol). careful: est_duration_s x 1.5 and noise_db - 6 (not below 0);
    rushed: est_duration_s x 0.6 and noise_db + 6 (not above 180), applied after the speech rule
    above, on the Intent's copy of the BoundAffordance. (Its check modifier: action.effects.)
  * INTENT-09 gesture and attention must be null or a G# / F# key of packet.handles (no packet
    offers any yet) — else IntentError 'hallucinated_expression'. An inscription needs a chosen
    option tagged 'write' (no core option is one yet), at most 35 words, and a quotation_source
    that is null or an S# / E# key of packet.handles whose percept or memory text contains the
    inscription text word for word — else IntentError 'bad_inscription'.
  * a SPEAK choice with no speech -> IntentError 'empty'.
  * goal / private_reason: a decision's goal and its private_reason ('' when null), manner '';
    IntakeOutput: goal = manner or the option label, private_reason = '', its manner; V1: its
    goal, private_reason and manner.

barrier(tx, intents) -> list[Intent]   (Stage 7, L5)
  Reads only; nothing is mutated before every intent of the wave has returned (BARRIER-01: the
  pipeline calls it once, with all of them). For each intent, in the given order, every referent
  must exist NOW (at T0, before any landing) where the intent binds it:
    target / destination ids must name an existing row (bodies / items / portals / anchors /
    wounds / places); an item bound with a destination anchor (a believed location, AFF-01) must
    really lie at that anchor, and an item the actor believes it holds must really be held by it.
  A failing referent returns a copy of the intent with blocked = 'referent_missing' (the resolver
  commits ACTION_BLOCKED; nothing is dropped, HALLUC-01). The barrier never repairs an intent by
  guessing and never changes its order. Returns the list (same length, same order).

plan_continuation(tx, actor_id, affordances, at, turn_index, *, accepted_only=False) -> Intent | None
  (COLD, LOD-02) The same decision the actor made last time, still running. First match wins; the
  chosen option must be IN ``affordances`` (by def_id and referent), else the step is skipped.
  accepted_only=True (turn.cognition HOLD-01: continuing after a failed answer) keeps only what the
  person already took on — steps 1-5 and step 6's guard at the duty anchor (their watch) — and
  returns None instead of step 6's observe / wait / first-option defaults (Actor Spec §3: a
  fallback may carry on an accepted watch, meal or journey, never invent a new willingness):
  1 reflex (source 'reflex'): for each capability.trained_responses entry in dossier order whose
    cue is in mind.cues.cues_of(actor, turn_index, at): the first option (AffordanceSet order)
    whose verb equals the response verb;
  2 standing order (source 'plan'): a plans.standing_orders entry whose trigger cue is present ->
    the first option with verb OBSERVE in AffordanceSet order (the response text is for the
    model's packet; COLD code can only look);
  3 the active task (source 'plan'): the keep_working option;
  4 plans.steps[0] (source 'plan'): the first option whose label contains the step text
    case-insensitively, or whose def_id equals the step text;
  5 routine (P9, source 'plan'): st = society.routine.step_for(tx, actor_id, the hour of ``at``);
    when st is not None and society.routine.OPTION_FOR has st.activity: the first option (in
    AffordanceSet order) whose def_id is that option ('sleep' at night, 'observe_area' at work);
  6 default (source 'plan'): the 'guard_anchor' option at actors.duty_anchor when present, else
    'observe_area', else 'wait_here', else the first option.
  manner '' ; goal = actors.goal_text or the option label; private_reason ''; lod COLD.

intent_to_dict(intent) -> dict / intent_from_dict(d) -> Intent   JSON-safe round trip (queue rows,
  pending_reactions): every Intent, SpeechAct and BoundAffordance field (pace, delivery, timing and
  the inscription included; a dict without them reads as normal, ordinary, alongside, None);
  CheckSpec as its model_dump.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from ..contracts.common import LOD, Volume

if TYPE_CHECKING:
    from ..contracts.mind import ActionPayload, CognitionOutput, IntakeOutput, SkullPacket
    from ..kernel.store import Tx
    from ..mind.affordance import AffordanceSet, BoundAffordance


@dataclass(frozen=True)
class SpeechAct:
    text: str
    to: tuple[str, ...]  # internal ids, or ('everyone',)
    volume: Volume
    delivery: str = "ordinary"   # ordinary | hesitant | clipped | soothing | strained
    timing: str = "alongside"    # before | alongside | after


@dataclass(frozen=True)
class InscriptionAct:
    text: str
    quotation_source: str | None = None   # the internal id the S# / E# handle named


@dataclass(frozen=True)
class Intent:
    actor_id: str
    bound: "BoundAffordance"
    speech: SpeechAct | None
    manner: str
    goal: str
    private_reason: str
    source: Literal["model", "plan", "reflex", "human", "fallback", "pending"]
    lod: LOD
    blocked: str | None = None   # set by barrier(): 'referent_missing
    pace: str = "normal"         # normal | careful | rushed (INTENT-07)
    inscription: InscriptionAct | None = None


@dataclass(frozen=True)
class IntentError:
    kind: Literal["hallucinated_choice", "hallucinated_target", "empty", "none_choice", "speech_too_long",
                  "unsupported_pace", "hallucinated_expression", "bad_inscription"]
    detail: str


def to_intent(packet: "SkullPacket", affordances: "AffordanceSet",
              output: "ActionPayload | CognitionOutput | IntakeOutput", *, lod: LOD, source: str,
              reaction: bool = False) -> Intent | IntentError:
    raise NotImplementedError("P4")


def barrier(tx: "Tx", intents: list[Intent]) -> list[Intent]:
    raise NotImplementedError("P5")


def plan_continuation(tx: "Tx", actor_id: str, affordances: "AffordanceSet", at: int,
                      turn_index: int, *, accepted_only: bool = False) -> Intent | None:
    raise NotImplementedError("P5")


def intent_to_dict(intent: Intent) -> dict:
    raise NotImplementedError("P5")


def intent_from_dict(d: dict) -> Intent:
    raise NotImplementedError("P5")
from ._impl_intent import to_intent  # noqa
from ._impl_p5b import barrier, plan_continuation, intent_to_dict, intent_from_dict  # noqa
