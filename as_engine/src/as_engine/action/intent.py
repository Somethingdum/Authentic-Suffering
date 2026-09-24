"""Intent construction and the intent barrier (P4/P5). Rules INTENT-01..06, L2, L3, L5.

An Intent is what a mind attempts. It is built by CODE from a model's CognitionOutput/IntakeOutput
(or from plan continuation for COLD actors) and the packet's handle map:

    Intent(actor_id, bound: BoundAffordance, speech: SpeechAct | None, manner, goal,
           private_reason, source: 'model'|'plan'|'reflex'|'human'|'fallback', lod)

to_intent(packet, affordances, output) -> Intent | IntentError   (INTENT-02)
  * output.choice 'NONE' (IntakeOutput) -> IntentError 'none_choice' (detail = none_reason).
  * output.choice must be a handle present in packet.handles AND its signature must equal the
    signature of an option of the AffordanceSet (else IntentError 'hallucinated_choice').
  * speech.to handles must be entity handles of this packet or 'everyone' (else IntentError
    'hallucinated_target'); they map to internal ids ('everyone' stays); an empty ``to`` means
    ('everyone',).
  * speech with a non-SPEAK choice is allowed; if it exceeds 12 words the bound option's
    est_duration_s grows by words / 2.5 seconds (speech consumes real time, TIME-05) — the
    Intent carries a copy of the BoundAffordance with the new duration. A SPEAK choice's
    duration becomes max(its est_duration_s, words / 2.5).
  * a SPEAK choice with no speech -> IntentError 'empty'.
  * manner / goal / private_reason copied (IntakeOutput has no goal: goal = manner or the option
    label, private_reason = '').

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

plan_continuation(tx, actor_id, affordances, at, turn_index) -> Intent   (COLD, LOD-02)
  The same decision the actor made last time, still running. First match wins; the chosen option
  must be IN ``affordances`` (by def_id and referent), else the step is skipped:
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
  pending_reactions): every Intent and BoundAffordance field; CheckSpec as its model_dump.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from ..contracts.common import LOD, Volume

if TYPE_CHECKING:
    from ..contracts.mind import CognitionOutput, IntakeOutput, SkullPacket
    from ..kernel.store import Tx
    from ..mind.affordance import AffordanceSet, BoundAffordance


@dataclass(frozen=True)
class SpeechAct:
    text: str
    to: tuple[str, ...]  # internal ids, or ('everyone',)
    volume: Volume


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


@dataclass(frozen=True)
class IntentError:
    kind: Literal["hallucinated_choice", "hallucinated_target", "empty", "none_choice"]
    detail: str


def to_intent(packet: "SkullPacket", affordances: "AffordanceSet",
              output: "CognitionOutput | IntakeOutput", *, lod: LOD, source: str) -> Intent | IntentError:
    raise NotImplementedError("P4")


def barrier(tx: "Tx", intents: list[Intent]) -> list[Intent]:
    raise NotImplementedError("P5")


def plan_continuation(tx: "Tx", actor_id: str, affordances: "AffordanceSet", at: int,
                      turn_index: int) -> Intent:
    raise NotImplementedError("P5")


def intent_to_dict(intent: Intent) -> dict:
    raise NotImplementedError("P5")


def intent_from_dict(d: dict) -> Intent:
    raise NotImplementedError("P5")
