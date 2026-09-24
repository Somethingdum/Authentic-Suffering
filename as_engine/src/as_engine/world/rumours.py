"""Rumours (P9). Owner 'world.rumours' (rumours). Rules INFO-01..07. docs/as/06_WORLD.md §6.
A rumour is a proposition passed from mind to mind. Every hop is TOLD, never known: the listener
gets a percept and a claim_holdings row through mind.perception.grant (the single knowledge
writer, L1) with provenance 'told_by:<teller>' and a confidence one lower than the teller's
(INFO-02). What is passed on is 'X claims Y' — a proposition held with a confidence, never a
truth (INFO-03). Every function that returns an Event has committed it (writer 'world.rumours',
at and turn_index as given). R = RulesConfig().society, DAY = 86_400_000 ms.

CLAIM_TEXT: claim slug -> sentence template ('{about}' = the listener's own word for the subject,
  mind.perception.word_for). claim_sentence(claim, about_word) -> str: the template filled in, or
  for an unknown slug f"{about_word}: {slug with '_' as spaces}."; the first letter upper-cased.
INFO-07 seed(tx, holder_id, about_id, claim, at, turn_index, cause_event_id, confidence=3, *,
             subject_type='body') -> str
  (the cascade 'create_rumour' dispatch — core CAS-012 for a witnessed theft, CAS-013 for an
  off-screen death — and anything else that starts talk). rumour_id = tx.mint('rum'). First
  grant(tx, holder, event_id=f'rumour:{rumour_id}', channel 'speech', fidelity 'exact', text =
  'Word is: ' + sentence, source_id None, beliefs [BeliefFromPercept('body', about_id, claim,
  sentence)], detail {words: sentence, volume: 'normal', addressed_to_me: False,
  speaker_known_as: None, received_db: 60, via_portal: None, armed_at_me: False},
  confidence=confidence) — provenance 'overheard'; then RUMOUR_SPREAD {rumour_id, teller_id: null,
  listener_id: holder, about_id, claim, confidence, believed: true, hops: 0} (cause =
  cause_event_id) inserting rumours {rumour_id, prop_id: the holder's new holding's claim_id,
  origin_holder: holder, hops: 0, distortions: [], created_at: at}. Returns rumour_id.
  sentence = claim_sentence(claim, word_for(tx, holder, about_id)). P10: subject_type 'place' (talk
  about a place, not a person — world.hordes HRD-13 'horde_coming'): the belief is
  BeliefFromPercept('place', about_id, claim, sentence) and the about word is the place's name
  (places.name) with a leading 'The' lower-cased; everything else is the same.
INFO-02 spread_one(tx, rumour_id, teller_id, listener_id, at, turn_index, cause_event_id) -> Event
  The teller's live (superseded_by NULL) believed holding on the rumour's (subject_type,
  subject_id, predicate) must have confidence >= 1 — else ValueError. confidence = that - 1;
  believed = the listener's relationships row toward the teller has trust >= -1 (0 when there is
  no row); hops = the teller's hops (the payload.hops of the newest RUMOUR_SPREAD of this rumour
  whose listener_id is the teller) + 1. RS = RUMOUR_SPREAD {rumour_id, teller_id, listener_id,
  about_id, claim, confidence, believed, hops} (event actor_id = the teller, cause as given)
  writing rumours.hops = hops when it is larger than the row's. Then grant(tx, listener,
  event_id=RS, channel 'speech', fidelity 'exact', text = f'{Teller} tells you: {sentence}',
  source_id = teller, beliefs [BeliefFromPercept('body', about_id, claim, sentence, believed=
  believed)], detail {words: sentence, volume: 'normal', addressed_to_me: True,
  speaker_known_as: Teller, received_db: 60, via_portal: None, armed_at_me: False},
  confidence=confidence) where Teller = word_for(listener, teller) with its first letter
  upper-cased and sentence = claim_sentence(claim, word_for(listener, about_id)). Returns RS.
  P10: the rumour's proposition carries its subject_type; for 'place' (INFO-07) the belief is
  BeliefFromPercept('place', ...) and the about word is the place's name (as in seed); spread_day's
  "already holds a live holding on it" matches the subject_type too.
INFO-04 holders(store, rumour_id) -> list[tuple[str, int]]: (holder_id, confidence) of every live
  believed holding on the rumour's (subject_type, subject_id, predicate), sorted by holder_id.
INFO-05 spread_day(tx, group_id, at, turn_index, cause_event_id) -> list[Event]
  (society.group.day calls it.) For each rumours row (by rumour_id) with created_at > at -
  R.rumour_quiet_days * DAY: tellers = the living members of the group (society.group.members)
  whose controller is not 'human' and who hold it with confidence >= 1 (holders), in id order.
  Each teller tells at most R.rumour_tells_per_day people, taken from society.group.contacts(
  teller, group) sorted by (-(the teller's trust + affection toward them), id), skipping the
  rumour's subject and anyone who already holds a live holding on it at that moment (so somebody
  told earlier the same day is not told twice): spread_one(..., cause_event_id). Returns every
  event committed, in seq order.
INFO-01 (the law) information is neither universally known nor confined to the conversation
  partner: it moves along households, work crews and friendships, a few people a day, and fades
  (confidence 0 is held but never passed on).
INFO-06 Retelling (P10; service/background.py runs the RUMOUR_DISTORT calls between turns): what a
  holder passes on is their own version. retell(tx, rumour_id, holder_id, answer, at, turn_index) ->
  Event | None: answer is a RumourDistortion. The holder already has an entry in
  rumours.distortions -> None. The answer is refused (kept as operation 'none', text null) when its
  operation is 'none', or when retold_claim names a person or place the holder does not know: any
  display name of a living body (actors.display_name) or any place name (places.name) that appears
  in retold_claim (case-insensitive, whole words) and is not the holder's own acquaintance
  known_name or a place in the holder's known_places — the model may twist a story, never invent
  who is in it. RUMOUR_DISTORTED {rumour_id, holder_id, operation, text} (writer 'world.rumours',
  actor_id = holder) appending {holder_id, operation, text} to rumours.distortions (kept sorted by
  holder_id). spread_one (P10 amendment): when the TELLER has an entry with a text, the listener
  hears that text (sentence = that text, first letter upper-cased, ending in '.') instead of
  claim_sentence(...); the listener's proposition text is it too.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.store import Store, Tx

CLAIM_TEXT: dict[str, str] = {
    "took_what_was_not_theirs": "{about} took what was not theirs.",
    "dead": "{about} is dead.",
    "bitten": "{about} was bitten.",
    "lied": "{about} lied to people here.",
    "left": "{about} left and is not coming back.",
    "sick": "{about} is sick.",
    "horde_coming": "{about}: a horde is coming that way, more of them than anyone has seen.",
}


def retell(tx: "Tx", rumour_id: str, holder_id: str, answer, at: int, turn_index: int):
    """INFO-06 (P10): record how this holder will pass the rumour on (see the module docstring)."""
    raise NotImplementedError("P10")


def claim_sentence(claim: str, about_word: str) -> str:
    """CLAIM_TEXT filled in (implemented)."""
    tpl = CLAIM_TEXT.get(claim)
    text = tpl.format(about=about_word) if tpl else f"{about_word}: {claim.replace('_', ' ')}."
    return text[:1].upper() + text[1:]


def seed(tx: "Tx", holder_id: str, about_id: str, claim: str, at: int, turn_index: int,
         cause_event_id: str | None, confidence: int = 3, *, subject_type: str = "body") -> str:
    raise NotImplementedError("P9")


def spread_one(tx: "Tx", rumour_id: str, teller_id: str, listener_id: str, at: int, turn_index: int,
               cause_event_id: str | None) -> "Event":
    raise NotImplementedError("P9")


def holders(store: "Store | Tx", rumour_id: str) -> list[tuple[str, int]]:
    raise NotImplementedError("P9")


def spread_day(tx: "Tx", group_id: str, at: int, turn_index: int, cause_event_id: str | None) -> list["Event"]:
    raise NotImplementedError("P9")
