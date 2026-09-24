"""The Request Firewall (P4). Rules WILL-00..11, L6, L7. docs/as/05_ACTORS.md §Firewall.

A request never becomes an action. It becomes an event perceived by an Actor, who then
independently chooses a response.

classify_form(text, *, weapon_pointed_at_receiver=False) -> UtteranceForm   (pure, WILL-10)
  Lowercase, strip. Checks in order, first match wins:
  THREAT   if weapon_pointed_at_receiver and the text is imperative, OR it contains any of:
           "or i'll", "or i will", "or else", "i'll kill", "i will kill", "i'll hurt", "i'll shoot",
           "don't make me", "last warning", "you'll regret"
  OFFER    if it contains any of: "i'll give", "i will give", "i can give", "in exchange", "trade you",
           "i'll trade", "how about i", "i'll pay", "for your trouble"
  REQUEST  if it contains any of: "please", "could you", "can you", "would you", "will you",
           "would you mind", "i need you to", "help me"
  (imperative) = the first word — or the second when the first ends with a comma (a name:
           "June, stay put") — with every character that is not a letter or apostrophe removed,
           is in IMPERATIVE_VERBS ("Quiet." "Don't move!" "Stay there.")
  ORDER    if imperative (standing decides VALID_ORDER vs DEMAND later: ORDER form is only kept
           when standing == VALID_ORDER, otherwise the form becomes DEMAND)
  QUESTION if it ends with "?"
  STATEMENT otherwise.

classify_standing(tx, speaker_id, receiver_id, text) -> Standing   (WILL-04)
  Read ONLY the receiver's mind (accepted_authority, relationships, acquaintance, group standing).
  Precedence (first true wins):
    HOSTILE            receiver's relationship to speaker has trust <= -2 or fear >= 2, or the
                       receiver's group stance toward the speaker's group is hostile/war
    VALID_ORDER        speaker id in receiver.accepted_authority
    SUBORDINATE        receiver id in speaker.accepted_authority
    CLAIMED_AUTHORITY  text contains "i'm in charge", "i am in charge", "that's an order",
                       "orders", "i'm the boss", "you work for me"
    PEER               receiver knows the speaker: an acquaintance row with a known_name, or a
                       relationships row toward them (having merely SEEN someone — an acquaintance
                       row with no name — still leaves them a STRANGER)
    STRANGER           otherwise
  Claims never create authority: standing comes from the RECEIVER's record, never the speaker's words.

request_signature(text, speaker_id, receiver_id, perceived_entities) -> str   (WILL-08)
  Normalise: lowercase; strip every character that is not a letter, digit, space or apostrophe;
  collapse spaces; drop a leading '<word> ' when the first word is followed by a comma in the
  original (a name: "June, open the door"); then drop leading politeness repeatedly until none is
  left — at each step the first of 'would you mind ', 'please ', 'could you ', 'can you ',
  'would you ', 'will you ' that the text starts with ("could you please open it" -> "open it")
  — and one trailing ' please'. Then the first matching
  REQUEST_PATTERNS entry (a regex over the normalised text) gives '<def_id>:<target>', where
  {speaker} is speaker_id and {x} is lookup(x): perceived_entities maps lowercase phrases (names,
  descriptions, item / portal / anchor names the receiver knows) to ids; lookup returns the id of
  the longest key equal to x or contained in x, else '*'. Unmatched -> '*:*'.

classify_response(signature, chosen: BoundAffordance, speech_text, resolve_cur, entrenched_block)
  -> ResponseClass  (WILL-09):
  chosen matches signature (same def_id; the target part equals the option's target, destination
  or item id; '*' in either part matches anything — but the unmatched signature '*:*' never
  matches, because an ask the code could not read cannot be complied with by accident):
     COERCED_COMPLIANCE if the utterance form was THREAT and resolve_cur == 0,
     READY_COMPLIANCE   if resolve was not drained this turn and no cost_note,
     else RELUCTANT_COMPLIANCE
  not matching:
     ENTRENCHED_REFUSAL if the requested def was removed by the moral gate (entrenched_block;
                        the duty gate removes nothing, C05)
     FALSE_COMPLIANCE   if speech_text contains an ASSENT_TOKENS entry as a whole word or phrase
                        (case-insensitive, regex word boundaries: 'yes' matches "Yes, sure." but
                        not "yesterday") — deception is logged (LIE_TOLD, P6)
     COUNTER_OFFER      if speech_text classifies as OFFER
     REFUSAL            otherwise
Refusals and lies (P6; events written with writer 'mind.mind', the owner of refusals; "the event
id" in a row is kernel.store.EVENT_SELF, STORE-11).
WILL-07 record_refusal(tx, actor_id, requester_id, signature, summary, reason_code,
  reason_event_ids, cost_cited, entrenched, at, turn_index, cause_event_id) -> refusal_id
  reason_code must be one of REASON_CODES, else ValueError. ``summary`` is how the refuser would
  put the ask in words ("hand over the revolver"); it becomes the packet line f'You refused:
  {summary}.'. A repeat is a row with the same (actor_id, requester_id, request_signature) and
  status 'standing' or 'reopened'; the unreadable signature '*:*' is never a repeat (the code
  cannot tell two unreadable asks apart).
  * New: REFUSAL {refusal_id, actor_id, requester_id, signature, summary, reason_code,
    reason_event_ids, cost_cited, entrenched, times_asked: 1, repeat: false}; refusals INSERT
    (refusal id kind 'ref', times_asked 1, status 'standing', expires_when 'never',
    created_event = the event id, created_at = at). cause_event_id = the ask's event.
  * Repeat: REFUSAL {refusal_id, actor_id, requester_id, signature, times_asked (the new count),
    entrenched (the row's, after this call), repeat: true}; refusals UPDATE times_asked + 1 and
    entrenched = old OR new (once entrenched, always entrenched). Returns the existing id.
WILL-06 Asking has consequences even when refused: a NEW refusal with entrenched = true (the ask
  needed something the moral gate removes — one of the refuser's own immutable lines, such as
  abandoning a dependent, leaving a post or betraying its own when those are on its wont list)
  also commits mind.mind.relate(actor_id, requester_id, TRUST, -1, cause = the REFUSAL event id).
WILL-07 Friction: the repeat that brings times_asked to 3, and every later one, also commits
  mind.mind.relate(actor_id, requester_id, RESENTMENT, +1, cause = the REFUSAL event id).
WILL-05 negotiable_target_penalty(times_asked) = -(times_asked - 1) for times_asked >= 1 (else
  ValueError): asking again is never better. action.effects.situation applies it to the check of
  a 'negotiable' def (calm_person in the core pack) against a body that has refused the actor:
  times_asked = the largest times_asked among that body's refusals with requester_id = the actor
  and status 'standing' or 'reopened' (no such row: no penalty). Someone who has already said no
  to you is harder to talk round, whatever you ask next.
WILL-11 record_lie(tx, liar_id, to_id, signature, words, speech_event_id, at, turn_index) -> Event
  A FALSE_COMPLIANCE response (says yes, does something else) is a lie: LIE_TOLD {liar_id, to_id,
  signature, words} (writer 'mind.mind', actor_id = liar_id, cause_event_id = the liar's SPEECH
  event; no table writes — the world records "X claimed Y"; being caught is LIE_DISCOVERED,
  later phases).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..contracts.common import ResponseClass, Standing, UtteranceForm

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.store import Tx
    from .affordance import BoundAffordance

IMPERATIVE_VERBS: frozenset[str] = frozenset({
    "come", "go", "get", "give", "take", "drop", "put", "open", "close", "shut", "stop", "wait",
    "stay", "leave", "run", "follow", "guard", "watch", "help", "hold", "grab", "bring", "move",
    "sit", "stand", "kneel", "tell", "show", "hand", "lock", "unlock", "hide", "shoot", "kill",
    "keep", "let", "look", "listen", "carry", "fetch", "find", "search", "check", "fix", "back",
    "quiet", "freeze", "don't", "hurry", "duck", "down", "shush", "turn", "step", "throw", "lower",
})

REQUEST_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"^(come with me|follow me|come here|come on)\b", "follow_body:{speaker}"),
    (r"^guard (the )?(?P<x>.+)$", "guard_anchor:{x}"),
    (r"^give (me|it to me|that to me)\b", "give_item:{speaker}"),
    (r"^hand (me|it over|that over)\b", "give_item:{speaker}"),
    (r"^(drop|put down) (it|that|the (?P<x>.+))$", "drop_item:*"),
    (r"^put (it|that|the (?P<x>.+)) down$", "drop_item:*"),
    (r"^open (the )?(?P<x>.+)$", "open_portal:{x}"),
    (r"^close (the )?(?P<x>.+)$", "close_portal:{x}"),
    (r"^(get out|leave|go away|get lost)\b", "leave_place:*"),
    (r"^(stop|wait|freeze|stay (here|there|put)|don't move|hold on)\b", "wait_here:*"),
    (r"^(quiet|be quiet|keep quiet|shut up|shh+)\b", "wait_here:*"),
    (r"^(hide|get down)\b", "hide:*"),
    (r"^(run|go go go)\b", "flee_threat:*"),
    (r"^(look|check) (at )?(the )?(?P<x>.+)$", "watch_target:{x}"),
)

REASON_CODES: tuple[str, ...] = ("duty", "dependent", "resource", "fear", "moral", "identity", "loyalty",
                                 "cost", "distrust")

ASSENT_TOKENS: tuple[str, ...] = ("yes", "sure", "okay", "ok", "fine", "alright", "all right",
                                  "on my way", "i will", "i'll do it")


def classify_form(text: str, *, weapon_pointed_at_receiver: bool = False) -> UtteranceForm:
    raise NotImplementedError("P4")


def classify_standing(tx: "Tx", speaker_id: str, receiver_id: str, text: str) -> Standing:
    raise NotImplementedError("P4")


def effective_form(form: UtteranceForm, standing: Standing) -> UtteranceForm:
    """ORDER survives only with VALID_ORDER standing; otherwise ORDER -> DEMAND (implemented)."""
    if form == UtteranceForm.ORDER and standing != Standing.VALID_ORDER:
        return UtteranceForm.DEMAND
    return form


def request_signature(text: str, speaker_id: str, receiver_id: str,
                      perceived_entities: dict[str, str]) -> str:
    raise NotImplementedError("P4")


def classify_response(signature: str, chosen: "BoundAffordance", speech_text: str | None,
                      resolve_cur: int, form: UtteranceForm, *, entrenched_block: bool,
                      resolve_drained_this_turn: bool) -> ResponseClass:
    raise NotImplementedError("P4")


def record_refusal(tx: "Tx", actor_id: str, requester_id: str, signature: str, summary: str,
                   reason_code: str, reason_event_ids: list[str], cost_cited: str, entrenched: bool,
                   at: int, turn_index: int, cause_event_id: str) -> str:
    """Returns refusal_id (existing standing row id when this is a repeat)."""
    raise NotImplementedError("P6")


def negotiable_target_penalty(times_asked: int) -> int:
    raise NotImplementedError("P6")


def record_lie(tx: "Tx", liar_id: str, to_id: str, signature: str, words: str, speech_event_id: str,
               at: int, turn_index: int) -> "Event":
    raise NotImplementedError("P6")
from ._impl_p4a import classify_form, classify_standing, request_signature, classify_response  # noqa
from ._impl_p6 import record_refusal, negotiable_target_penalty, record_lie  # noqa
