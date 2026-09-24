"""Perception compiler and THE single knowledge writer (P3). Rules SKULL-01..06, L1.
Owner 'mind.perception'. May import kernel.truth, sense.*, physical.*.

grant(tx, holder_id, *, event_id, channel, fidelity, text, source_id, at, turn_index,
      beliefs=[], detail={}, confidence=None) -> str (percept_id)
  The ONLY function in the engine that inserts percept_log or claim_holdings rows. It commits
  one PERCEIVE event (writer 'mind.perception', actor_id = holder, cause_event_id = event_id when
  event_id names a committed event — standing-view percepts use event_id f'scene:{turn_index}'
  and cause NULL) holding:
    * one percept_log insert (percept id kind 'pct'; granted_by = 'perception.grant' — schema
      CHECK enforces it; detail = the ``detail`` dict, see DETAIL below);
    * per BeliefFromPercept: a propositions insert (prop id kind 'prp', text, subject_type,
      subject_id, predicate, object_value, matches_claim, created_event = event_id) and a claim_holdings insert
      for it with
      provenance = 'witnessed' for EXACT/PARTIAL visual/auditory/tactile, 'overheard' for speech
      not addressed to the holder, f'told_by:{source_id}' for speech addressed to the holder,
      fidelity copied, confidence 3/2/1 for exact/partial/tone_only (visual_only: 2) — P9: when
      ``confidence`` is given (0..3, else ValueError), min(that, the given value): second-hand news
      is held less surely than it was heard (world.rumours, INFO-02) — believed
      from the BeliefFromPercept, acquired_at = last_confirmed = at, acquired_via = event_id.
  A new belief on the same (subject_type, subject_id, predicate) as a live holding (superseded_by
  NULL) the holder already has — compared through the holdings' propositions — supersedes it: the
  OLD holding's superseded_by = the new prop id (never deleted; W15 holds). Unknown channel or fidelity 'none' -> ValueError (nothing is
  granted for NONE).

DETAIL (percept_log.detail, JSON) — what later stages need without re-reading events:
  speech:   {words, volume, addressed_to_me, speaker_known_as, received_db, via_portal, armed_at_me}
            words = the exact words (EXACT), partial_words(...) (PARTIAL) or '' (TONE_ONLY);
            speaker_known_as = the Ref used in the text, or null when 'Someone';
            armed_at_me = SPEECH payload.armed is true (action.propagate sets it when the speaker
            holds a firearm or melee weapon in a hand) AND addressed_to_me AND the holder sees
            the speaker at clear or partial — what makes an imperative a THREAT (WILL-10)
  auditory: {received_db (2 decimals), direction, via_portal}
            via_portal = the last portal of the acoustic path (the one nearest the listener), or
            null when the source is in the listener's place
  visual:   {level}  ('clear' | 'partial' | 'silhouette')
  tactile:  {wound_id}

Which events are sensory (SENSORY_TYPES) and how each is perceived:
  NOISE    auditory. Source point = acoustics.source_point(payload, actor_id); source_db =
           payload.source_db; receptions via acoustics (the source body excluded). Text:
           render_sound. source_id = the actor when the holder can see the actor's body
           (optics >= silhouette), else NULL.
  SPEECH   speech. payload {words, volume ('whisper'|'low'|'normal'|'raised'|'shout'),
           to: [body ids] or ['everyone'], source_db, armed (optional, default false)}; the speaker is event.actor_id; source point
           = the speaker's position. Text: render_speech. The speaker's Ref: the known name when
           the holder knows it (acquaintance.known_name) AND (it sees the speaker at clear OR the
           fidelity is EXACT — a known voice); else with_article(describe(...)) when it sees the
           speaker at clear/partial; else 'Someone'. source_id = the speaker when it is named or
           seen at clear/partial, else NULL.
  MOVE, PORTAL_CHANGE, ACTION_START, ACTION_COMPLETE, HARM, DEATH, FALSE_DEATH, ITEM_TRANSFER
           visual, for holders who can see the event's body (MOVE/ACTION_*/ITEM_TRANSFER: the
           actor; HARM/DEATH/FALSE_DEATH: the harmed body; PORTAL_CHANGE: holders in either place
           of the portal within line of sight rules for its point, i.e. same place as the portal
           side, or seeing through it) at visibility >= silhouette, evaluated at the event's at.
           Fidelity: clear -> exact, partial -> partial, silhouette -> visual_only. Text:
           render_event. source_id = the body for clear/partial, NULL for silhouette (for
           PORTAL_CHANGE: the actor when visible, else NULL).
           ACTION_* events are visual only when payload.visible is true (effects set it from
           AffordanceDef.visible_act) AND payload.seen is not null (ACTION_COMPLETE carries
           visible false: results are perceived through the state events they caused).
  HARM also grants the harmed body itself a TACTILE exact percept (when conscious after the
           harm): render_pain; source_id = the event's actor when the holder can see it, else NULL.
  The holder never perceives its own MOVE / ACTION_* / ITEM_TRANSFER / SPEECH / NOISE-it-caused
  events (it knows what it did through its own action record, mind.memory).
  Unconscious and dead holders perceive nothing; asleep holders only sounds, per acoustics. When a
  reception has wakes = True, perception grants the TONE_ONLY percept and then calls
  physical.bodies.wake(tx, holder, at, cause_event_id = the sound's event, turn_index).
  Dedup: a holder receives at most ONE percept per (event_id, channel) — granting again is a
  no-op returning the existing percept_id. This is what lets the per-wave scene compile and the
  aftermath share events without double counting.

compile_scene(tx, holder_id, at, turn_index) -> list[str]   (Stage 3, every wave)
  1. The standing view (skip when the holder is not conscious): for every other body B (alive or
     not) with optics.visibility(holder, B, at) != 'none', in body_id order, grant a VISUAL
     percept (event_id f'scene:{turn_index}', fidelity as above) with text render_visual(holder,
     B, level); for every item lying in the holder's place (items.place_id) whose point (its
     anchor or the place centre) would be at least 'partial' for a still, unhidden subject there,
     one VISUAL percept "<Item name> at the <anchor name>." / "<Item name> on the floor."
     (source_id = item id); for every non-wall portal of the holder's place one VISUAL percept
     render_portal (source_id = portal id); P10 (TRACE-05): when the light where the holder stands
     (optics.light_at(holder)) is above 0, one VISUAL percept per trace in the holder's place (world.traces.traces_in order),
     text = the trace's text, source_id = the trace id. Standing-view percepts are NOT deduplicated across
     moments: each compile describes the present — but a compile at the same ``at`` as a
     standing view the holder already got this turn grants no standing view again.
  2. Every sensory event of this turn (events.turn_index == turn_index, at <= at) the holder has
     not perceived yet, in seq order, as described above.
  3. Bookkeeping in the same PERCEIVE events: known_places upsert for the holder's place
     (last_seen = at, visited = 1); acquaintance.last_seen / last_seen_place for every body seen
     at clear or partial that the holder has a row for; a NEW acquaintance row (known_name NULL,
     description = describe(B)) for a body seen at clear or partial for the first time.
  Returns the percept ids granted by this call, in grant order.

infer(tx, holder_id, *, about, text, confidence, because, at, turn_index) -> str (prop_id)   (P6)
  The belief a mind writes for itself in writeback (mind.memory, MEM-05) — the one other way,
  besides grant, that claim_holdings rows appear. ``about`` is ('body', body_id), ('self', None)
  -> ('body', holder_id), or ('place', None) -> ('place', the holder's place now, positions).
  ``because`` = the percept ids the belief cites: non-empty, every one a percept_log row of THIS
  holder — else ValueError. Commits BELIEF_FORM (writer 'mind.perception', actor_id = holder,
  cause_event_id = committed_or_none(the first cited percept's event_id)) holding:
    * propositions INSERT: prop id kind 'prp', subject_type / subject_id from ``about``,
      predicate = 'inferred:' + norm_text(text), object_value NULL, text = text.strip(),
      matches_claim NULL, created_event = the first cited percept's event_id (may be 'scene:N');
    * claim_holdings INSERT: believed 1, confidence = min(confidence, 2) (a guess is never as sure
      as seeing it), provenance 'inferred', fidelity = the weakest fidelity among the cited
      percepts (exact > partial > visual_only > tone_only), acquired_at = last_confirmed = at,
      acquired_via = created_event;
    * the same supersession rule as grant: a live holding on the same (subject_type, subject_id,
      predicate) — i.e. the same guess made again — gets superseded_by = the new prop id.
  Payload {prop_id, holder_id, because (the percept ids, in the order given), superseded (the
  claim ids superseded, sorted)}.

word_for(tx, holder_id, body_id) -> str   (implemented)
  How the holder names a body: acquaintance.known_name, else — P10 — for an infected body that
  rose from a corpse (infected_state.risen_from) the holder knew by name: f"what was left of
  {that known_name}", else with_article(describe(...)).
norm_text(text) -> str   (implemented)
  Lowercase, whitespace collapsed to single spaces, stripped, trailing '.', '!', '?' removed:
  the comparison form for "the same text" (loops, lessons, inferred beliefs).

compile_aftermath(tx, holder_id, events, at, turn_index) -> list[str]   (Stage 13)
  Grants any not-yet-granted percepts for ``events`` (step 2 above, restricted to them) and
  returns the ids of ALL the holder's percepts whose event_id is one of ``events`` (granted now or
  earlier this turn), ordered by (at, percept_id). Percepts of other events never appear.

Text rendering — plain English, never an internal id (SKULL-06), never a name the holder does
not know (a known name = acquaintance.known_name; the holder's own name is never needed):
  ref(holder, B, level): clear + known name -> the name; clear or partial otherwise ->
      with_article(describe(B)) ('a tall, thin man'); silhouette -> 'a figure'. describe(B) = the
      acquaintance description when the holder has one, else describe_dossier(B's baseline
      dossier) (implemented below: height and build words from the numbers, never the prose
      fields), else for infected bodies 'shambling figure' (Shambler / Crawler) / 'fast figure'
      (Runner) — the type name is NEVER used, because what a thing is has to be learned.
  Phrase helpers (implemented below, so every module words places the same way): with_article,
      at_phrase(anchor name) ('at the counter', 'behind the counter', 'at the doors'),
      from_phrase(anchor or place name) ('from the counter', 'from behind the counter'),
      to_phrase(anchor name) ('to the counter', 'behind the counter', 'to the doors'),
      place_phrase, thing_phrase.
  render_visual(holder, B, level), present tense, one sentence:
      clear:   f'{Ref} {posture_verb} {where}{held}{wounds}.'  held = ', <item name> in the
               <left|right> hand' per held item (hand_l, hand_r order); wounds = ', bleeding
               badly' when an unhealed wound is severe or catastrophic and not clotted.
      partial: f'{Ref} {posture_verb} {where}.'
      silhouette: f'A figure {moving|still} {where}.' (moving = moved this second)
      posture_verb: standing 'stands', crouched 'crouches', sitting 'sits', lying 'lies',
      prone 'lies flat'; a dead body or a false-dead body: 'lies still'.
      where: ' ' + at_phrase(anchor name) when B has an anchor in the holder's place;
      ' in ' + place_phrase(place name) when in another place; else '' (same place, no anchor). silhouette 'moving' = moved this second (the optics rule), else 'still'.
  render_sound(received_db, fidelity, text, direction), past tense:
      EXACT: f'{Text} came {direction}.' (Text = payload.text with a capital first letter)
      PARTIAL: f'A {loud}noise came {direction}.'   loud = 'loud ' when received_db >= 70,
               'faint ' when < 45, else ''.
      TONE_ONLY: f'A sound came {direction}.'
  render_speech(ref_or_someone, volume, fidelity, words, partial_text, direction):
      verb by volume: whisper 'whispers', low 'says quietly', normal 'says', raised 'calls out',
      shout 'shouts'. EXACT: f'{Ref} {verb}{dir}, "{words}"'; PARTIAL: f'{Ref} {verb}{dir}, not
      all of it clear: "{partial_words(...)}"'; TONE_ONLY: f'{Ref} {verb}{dir}; the words are
      lost.' where dir = '' when the speaker is seen (clear/partial), else ' ' + direction, and
      Ref is the speaker's Ref above (capitalised).
  direction (from the acoustic path): same place -> from_phrase(anchor name) when the source point
      is exactly an anchor's point, else 'close by'; other place with every portal on the path
      open -> 'from ' + place_phrase(source place name); otherwise -> 'from the other side of '
      + thing_phrase(name of the closed portal nearest the listener) (walls and fences count as
      closed).
  render_event(ref, event): f'{Ref} {seen}.' when the payload carries 'seen' (a short present-
      tense verb phrase from action.effects.SEEN, e.g. 'raises {item} toward {target}'), with the
      placeholders filled for THIS holder: "{target}'s" -> 'your' when payload.target_id is the
      holder, else f"{ref}'s"; {target} -> 'you' when it is the holder, else the holder's Ref for a
      body (ref at the level the holder sees it now; 'someone' when it cannot see it), or
      thing_phrase(name) for an item / portal / anchor; a wound id -> the wounded body as a body;
      {destination} -> thing_phrase(anchor name) or place_phrase(place name); {item} ->
      with_article(item name). ('Owen raises a Glock 19 toward you.') Else by
      type: MOVE f'{Ref} moves {to_phrase(to_anchor name)}' when the MOVE has a to_anchor (in any
      place: a body seen through a doorway moving to the far side of it is seen going there),
      else f'{Ref} moves away' when to_place is not the holder's place, else f'{Ref} moves',
      PORTAL_CHANGE f'The <portal name>
      {opens|closes|is barricaded|is unbarricaded|is damaged}', HARM f'{Ref} is hurt', DEATH /
      FALSE_DEATH f'{Ref} goes down and does not move', ITEM_TRANSFER f'{Ref} handles <item
      name>'. (Past or present is fixed per phrase above.)
  render_pain(wound): f'Pain: {SEVERITY_WORDS[severity]} {type} wound to the
      {ANATOMY_WORDS[anatomy]}.' (contracts.common; e.g. 'Pain: a deep stab wound to the left arm.').
  render_portal(portal): f'The {name} is {open|closed}{, barricaded}{, damaged}.' — never
      'locked' (a lock is not visible, GEO-01); a fence: f'The {name} is {intact|damaged}.'
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..contracts.common import Channel, Fidelity

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.store import Tx


@dataclass(frozen=True)
class BeliefFromPercept:
    subject_type: str
    subject_id: str | None
    predicate: str
    text: str
    matches_claim: str | None = None
    believed: bool = True
    object_value: str | None = None


def grant(tx: "Tx", holder_id: str, *, event_id: str, channel: Channel, fidelity: Fidelity,
          text: str, source_id: str | None, at: int, turn_index: int,
          confidence: int | None = None,
          beliefs: list[BeliefFromPercept] | None = None, detail: dict | None = None) -> str:
    raise NotImplementedError("P3")


def infer(tx: "Tx", holder_id: str, *, about: tuple[str, str | None], text: str, confidence: int,
          because: list[str], at: int, turn_index: int) -> str:
    raise NotImplementedError("P6")


def word_for(tx: "Tx", holder_id: str, body_id: str) -> str:
    """The holder's word for a body (implemented; see the module docstring)."""
    row = tx.query_one("SELECT known_name FROM acquaintance WHERE holder_id = ? AND subject_id = ?",
                       (holder_id, body_id))
    if row is not None and row[0]:
        return row[0]
    risen = tx.query_one("SELECT a.known_name FROM infected_state i JOIN acquaintance a ON a.subject_id = i.risen_from "
                         "WHERE i.body_id = ? AND a.holder_id = ? AND a.known_name IS NOT NULL", (body_id, holder_id))
    if risen is not None and risen[0]:
        return f"what was left of {risen[0]}"
    return with_article(describe(tx, holder_id, body_id))


def norm_text(text: str) -> str:
    """Comparison form of a text (implemented; see the module docstring)."""
    return " ".join(text.lower().split()).rstrip(".!? ")


def compile_scene(tx: "Tx", holder_id: str, at: int, turn_index: int) -> list[str]:
    raise NotImplementedError("P3")


def compile_aftermath(tx: "Tx", holder_id: str, events: list["Event"], at: int, turn_index: int) -> list[str]:
    raise NotImplementedError("P3")


def render_visual(tx: "Tx", holder_id: str, subject_id: str, level: str) -> str:
    raise NotImplementedError("P3")


SENSORY_TYPES: tuple[str, ...] = ("NOISE", "SPEECH", "MOVE", "PORTAL_CHANGE", "ACTION_START", "ACTION_COMPLETE",
                                  "HARM", "DEATH", "FALSE_DEATH", "ITEM_TRANSFER")


def describe(tx: "Tx", holder_id: str, subject_id: str) -> str:
    """describe(B) from the module docstring (no article)."""
    raise NotImplementedError("P3")


PREPOSITIONS: frozenset[str] = frozenset({
    "behind", "under", "by", "near", "in", "on", "at", "beside", "inside", "outside", "beyond",
    "between", "across", "above", "below", "along", "against", "atop", "underneath",
})


def with_article(desc: str) -> str:
    """'tall man' -> 'a tall man'; 'old woman' -> 'an old woman'; a description that already starts
    with 'a ', 'an ' or 'the ' is returned unchanged (implemented)."""
    low = desc.lower()
    if low.startswith(("a ", "an ", "the ")):
        return desc
    return ("an " if low[:1] in "aeiou" else "a ") + desc


def at_phrase(name: str) -> str:
    """Where something is, from an anchor name (implemented): 'counter' -> 'at the counter';
    'behind the counter' -> 'behind the counter'; 'the doors' -> 'at the doors'."""
    first = name.split(" ", 1)[0].lower()
    if first in PREPOSITIONS:
        return name
    if first == "the":
        return f"at {name}"
    return f"at the {name}"


def from_phrase(name: str) -> str:
    """Where a sound comes from (implemented): 'counter' -> 'from the counter';
    'behind the counter' -> 'from behind the counter'; 'the doors' -> 'from the doors'."""
    first = name.split(" ", 1)[0].lower()
    if first in PREPOSITIONS or first == "the":
        return f"from {name}"
    return f"from the {name}"


def place_phrase(name: str) -> str:
    """A place name as it reads after 'in' / 'from' / 'into' (implemented): a title-case name of
    two or more words is a proper name and keeps no article ('Maple Street', 'Bunkhouse A');
    anything else gets 'the' and a lower-case first letter ('Sales floor' -> 'the sales floor')."""
    words = name.split()
    if len(words) >= 2 and all(w[:1].isupper() for w in words):
        return name
    return "the " + name[:1].lower() + name[1:]


def thing_phrase(name: str) -> str:
    """'counter' -> 'the counter'; a name that already starts with 'the ' is unchanged (implemented)."""
    return name if name.lower().startswith("the ") else f"the {name}"



def to_phrase(name: str) -> str:
    """Where something goes, from an anchor name (implemented): 'counter' -> 'to the counter';
    'behind the counter' -> 'behind the counter'; 'the doors' -> 'to the doors'."""
    first = name.split(" ", 1)[0].lower()
    if first in PREPOSITIONS:
        return name
    if first == "the":
        return f"to {name}"
    return f"to the {name}"


def describe_dossier(d: dict) -> str:
    """A stranger's-eye description from a dossier dict (implemented; the scenario loader and
    describe() both use it). Words come from NUMBERS, never from the prose fields:
      height (adults 16+): < 160 cm 'short', > 183 cm 'tall', else none;
      build from BMI = mass_kg / (height_m ** 2): < 18.5 'thin', >= 27 'heavyset', else none;
      noun: under 16 'boy' / 'girl' / 'child'; 60+ 'old man' / 'old woman' / 'old person';
            else 'man' / 'woman' / 'person' (sex 'other' -> person/child).
    Joined as f"{', '.join(words)} {noun}" or just the noun: 'tall, thin man', 'short woman',
    'girl', 'heavyset old man'."""
    ident, app = d["identity"], d["appearance"]
    age, sex = ident["age"], ident["sex"]
    h, m = app["height_cm"], app["mass_kg"]
    words = []
    if age >= 16:
        if h < 160:
            words.append("short")
        elif h > 183:
            words.append("tall")
    bmi = m / ((h / 100) ** 2)
    if bmi < 18.5:
        words.append("thin")
    elif bmi >= 27:
        words.append("heavyset")
    if age < 16:
        noun = {"male": "boy", "female": "girl"}.get(sex, "child")
    elif age >= 60:
        noun = "old " + {"male": "man", "female": "woman"}.get(sex, "person")
    else:
        noun = {"male": "man", "female": "woman"}.get(sex, "person")
    return f"{', '.join(words)} {noun}" if words else noun


def render_sound(received_db: float, fidelity: Fidelity, text: str, direction: str) -> str:
    raise NotImplementedError("P3")


def render_speech(ref: str, volume: str, fidelity: Fidelity, words: str, partial_text: str,
                  direction: str, visible: bool) -> str:
    raise NotImplementedError("P3")
