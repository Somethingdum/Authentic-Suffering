"""Stage 1: the player's input becomes the PC's intent (P7). Rules INTAKE-01..06, PARSE-05, SYM-02,
L12, S03, ECHO-01. docs/as/04_TURN_PIPELINE.md §2.

The PC's intent is built exactly like an Actor's: from the PC's own packet and AffordanceSet
(mind.packet.build_packet at LOD WARM), through action.intent.to_intent (source 'human'), from the
same decision payload an Actor answers with (contracts.mind.ActionPayload; Actor Spec §17 A6: the
player's words reach the same action vocabulary). The player chooses; code binds. Translation may
change manner (colour only) and pace (where the option supports it), never the verb, the target or
a refusal.

intake(tx, session, submit, turn_index, t0) -> (Intent, info)       raises Rejected
  INTAKE-01 (1) perception.compile_scene(tx, pc, t0, turn_index); aff =
     mind.affordance.enumerate_affordances(tx, pc, tx.canon.all('affordance'), t0, turn_index);
     packet = build_packet(tx, pc, LOD.WARM, aff, turn_index, t0). info = {'remainder': None,
     'addressee': None}. text = (submit.text or '').strip() — every later use of "the text" means
     this stripped text.
  INTAKE-02 (2) A suggestion chip (submit.suggestion_ref): entry =
     session.extras['suggestions'][ref] (service.view writes them) — missing ->
     Rejected('suggestion_stale', "That option is gone; things have changed.").
     * an entry with a non-empty 'remainder': continue below as mode 'do' with that remainder as
       the text, whatever submit.mode was (recorded as a 'do' input: words the player typed
       earlier, offered back as a chip; a re-simulation replays them as typed text).
     * {'signature': sig, 'label': …}: the option of ``aff`` with that signature (re-validated
       against the fresh AffordanceSet; gone -> 'suggestion_stale'). A 'speak' option needs words:
       empty text -> Rejected('empty', "Type what you want to say."); otherwise a speech intent to
       the option's target (below), info['addressee'] = that target, record_pc_input(text),
       record_input(mode 'say', text, {signature, words: text, addressee: target}). Any other
       option -> to_intent(packet, aff, ActionPayload(choice = its handle, goal = its label,
       private_reason = PLAYER_REASON), lod WARM, source 'human') (an IntentError ->
       'suggestion_stale'); record_input(mode 'suggestion', raw_text = the entry's label (else the
       option's ui_label), {signature}); no echo record (the player typed nothing).
  INTAKE-03 (3) Empty text -> Rejected('empty', "Type something first.").
  INTAKE-04 (4) mode 'say': words = the text; with settings.pc_voice == 'my_way' one SAY_MY_WAY call
     (lanes.requests.build_request(config, SAY_MY_WAY, turn_index = T, actor_id = the PC, context
     and ctx = SayMyWayContext(packet, seed_text = text, behavior_notes =
     mind.actor.fused(tx, pc).behavior_law's [topic_handling, plan_carry, distortion, pressure]
     when it has one, else []), json_schema = lanes.schemas.to_lm_schema(SayMyWayOutput)), output SayMyWayOutput) and
     words = its ``line`` when parse_status is 'ok' (else the text as typed). addressee =
     addressee_for(...); the speech intent; info['addressee'] = addressee; record_pc_input(text)
     (what the player typed, not the rewritten line); record_input(mode, text, {signature, words,
     addressee}).
  INTAKE-05 (5) mode 'do': quotes = lanes.parse.extract_quotes(text); rest = the text with every
     quoted span ("…" or “…”) replaced by ' ', stripped; addressee = addressee_for(...) — ALWAYS
     called here, before anything else, so a replay's forced_addressee is consumed on every 'do'
     turn. Quotes and no ASCII letter ([A-Za-z]) left in rest -> a speech intent with the quotes
     joined by ' ' (each stripped) to that addressee, info['addressee'] = addressee. Otherwise ONE
     INTAKE call (build_request(config, INTAKE, turn_index = T, actor_id = the PC, context and ctx =
     IntakeContext(packet, player_text = text, quoted_speech = quotes), json_schema =
     lanes.schemas.intake_schema(the packet's affordance handles)), output IntakeOutput):
       parse_status != 'ok' -> Rejected('intake_failed', "That didn't come through clearly. Try
         saying it another way.");
       choice 'NONE' -> Rejected(none_reason or 'unclear', NONE_MESSAGES[that code],
         clarify = output.clarify) — no time passes, the input is not consumed;
       with quotes -> to_intent(packet, aff, ActionPayload(choice, pace = output.pace when the
         chosen option's paces contain it, else 'normal', speech {text: the joined quotes, to:
         [the addressee's entity handle] or ['everyone'], volume 'normal'}, goal = manner or the
         label of the packet affordance with that handle (else the handle), private_reason =
         PLAYER_REASON), WARM, 'human') with its manner set to output.manner
         (dataclasses.replace), and info['addressee'] = addressee;
       without -> to_intent(packet, aff, the IntakeOutput, WARM, 'human');
       an IntentError -> Rejected('unclear', NONE_MESSAGES['unclear'], output.clarify).
     info['remainder'] = output.remainder (the pipeline offers it as the first chip next turn:
     "Continue: …"). record_pc_input(text); record_input(mode, text, {signature, addressee:
     info['addressee']}) (None for a do without speech).
  "mode" in record_input is 'do' when the text came from a remainder chip, else submit.mode.
  INTAKE-06 Rejected leaves the transaction to roll back: nothing of the turn is kept, no time
  passes and the input is not consumed (the player can rephrase).

Speech intent (a helper): the 'speak' option bound to the addressee, else the target-less 'speak'
  option (none -> Rejected('impossible', NONE_MESSAGES['impossible'])); to_intent(packet, aff,
  ActionPayload(choice = its handle, speech {text: words, to: [addressee's entity handle] or
  ['everyone'], volume 'normal'}, goal = the option's label, private_reason = PLAYER_REASON),
  WARM, 'human'); an IntentError -> Rejected('unclear', NONE_MESSAGES['unclear']).
addressee_for(session, packet, submit) -> body id | None
  session.extras.pop('forced_addressee') when present (service.replay sets it: a re-simulated say
  goes to whom it went to); else the first submit.addressee_refs entry whose view ref
  (session.extras['view_refs']) maps to a body that is an entity of the packet; else
  session.extras['last_addressee'] when it is an entity of the packet; else None ('everyone').
record_input(tx, turn_index, mode, raw_text, mapped) -> Event
  PLAYER_INPUT {mode, received_hash} (writer 'turn.pipeline', at = world_clock.now_ms) inserting
  player_inputs {turn_index, mode, raw_text, received_hash = sha256(raw_text utf-8) hex (S03),
  mapped}.
record_pc_input = narration.lint.record_pc_input(tx, turn_index, text, tx.rules.style) — the echo
  ledger keeps the player's own phrasing so no Actor and no narration parrots it back (ECHO-01..03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..action.intent import Intent
    from ..contracts.events import Event
    from ..contracts.mind import SkullPacket
    from ..contracts.protocol import InTurnSubmit
    from ..kernel.store import Tx
    from ..service.session import Session

NONE_MESSAGES: dict[str, str] = {
    "impossible": "That can't be done from where you are.",
    "not_here": "That isn't here.",
    "not_holding": "You're not holding that.",
    "not_trained": "You don't know how to do that.",
    "unclear": "It isn't clear what you want to do.",
    "not_an_action": "That isn't something you do in the world. Use Ask for questions.",
}
PLAYER_REASON = "The player chose this."


class Rejected(Exception):
    """The input cannot become an intent. ``code`` is the TurnOutcome.rejected_code, ``message`` the
    plain sentence the player sees, ``clarify`` the INTAKE model's question (when it asked one)."""

    def __init__(self, code: str, message: str, clarify: str | None = None):
        super().__init__(message)
        self.code, self.message, self.clarify = code, message, clarify


async def intake(tx: "Tx", session: "Session", submit: "InTurnSubmit", turn_index: int, t0: int) -> tuple["Intent", dict[str, Any]]:
    raise NotImplementedError("P7")


def addressee_for(session: "Session", packet: "SkullPacket", submit: "InTurnSubmit") -> str | None:
    raise NotImplementedError("P7")


def record_input(tx: "Tx", turn_index: int, mode: str, raw_text: str, mapped: dict) -> "Event":
    raise NotImplementedError("P7")
from ._impl_intake import *  # noqa
