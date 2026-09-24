"""Perception compiler and THE single knowledge writer (P3). Rules SKULL-01..06, L1, LOOK-03.
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
      place: a body seen through a doorway moving to the far side of it is seen going there);
      else, with here = the holder's place (P10): from_place is here and to_place is not ->
      f'{Ref} moves away'; to_place is here and from_place is not -> f'{Ref} arrives'; neither
      is here (seen through a doorway or across an open way) -> f'{Ref} moves into
      {place_phrase(to_place name)}'; else f'{Ref} moves',
      PORTAL_CHANGE f'The <portal name>
      {opens|closes|is barricaded|is unbarricaded|is damaged}', HARM f'{Ref} is hurt', DEATH /
      FALSE_DEATH f'{Ref} goes down and does not move', ITEM_TRANSFER f'{Ref} handles <item
      name>'. (Past or present is fixed per phrase above.)
  render_pain(wound): f'Pain: {SEVERITY_WORDS[severity]} {type} wound to the
      {ANATOMY_WORDS[anatomy]}.' (contracts.common; e.g. 'Pain: a deep stab wound to the left arm.').
  render_portal(portal): f'The {name} is {open|closed}{, barricaded}{, damaged}.' — never
      'locked' (a lock is not visible, GEO-01); a fence: f'The {name} is {intact|damaged}.'

F1a — what someone looks like to this holder (the owner: appearance helps you judge the situation
and people).
LOOK-03 appearance_text(tx, holder_id, subject_id, level, distance_m) -> str: what the holder sees of
  the subject beyond describe()'s Ref, never naming what cannot be seen; built from L =
  physical.bodies.looks_of(subject), C = condition_of(subject), W = physical.objects.worn, cov =
  coverage, G = visible_gear. level 'silhouette' or 'none' -> ''.
  features  (level 'clear' and L not None), in this order:
            hair — hair_length 'bald' -> 'bald'; 'shaved' -> 'a shaved head'; else
              f"{LENGTH} {hair_colour} hair" + (' ' + hair_style when set), LENGTH = cropped
              'cropped', short 'short', collar 'collar-length', shoulder 'shoulder-length', long
              'long';
            facial hair — facial_hair_words, else mustache 'a mustache', beard 'a beard',
              full_beard 'a full beard', stubble 'stubble' (none: nothing); stubble only within
              5 m, the others at any distance;
            within 5 m: complexion, as written ('pale skin freckled across the nose');
            each mark whose shows is 'far', or 'near' within 5 m, or 'close' within 1.5 m, in the
              order given: f"{what} {where}";
            within 1.5 m: f"{eye_colour} eyes".
            Joined with ', '. 'Within d m' is distance_m <= d.
  clothes   (L not None — a body whose looks are not recorded makes no claim about its clothes;
            levels 'clear' and 'partial'). naked = 'torso' and 'groin' both not in cov; half =
            'torso' not in cov and 'groin' in cov. A piece reads f"{state }{colour }{words}" with
            state 'torn ' / 'soiled ' for those states (else nothing) and colour as worn() gives it
            (nothing when ''), with_article unless the clothing block's plural is true ('cargo
            pants', 'work boots': no article).
            SHOWN = per slot of CLOTHING_SLOT_ORDER, the worn clothing piece of the outermost
              layer at that slot (a tie: the first in worn() order) — except that a 'body' piece
              fills 'torso' and 'legs' too: a torso or legs piece is SHOWN only when its layer is
              outer to (before, in CLOTHING_LAYER_ORDER) the SHOWN 'body' piece's layer.
            clear: naked -> 'naked' + (' but for ' + the
              SHOWN pieces joined as a list when any); else (half -> 'bare to the waist, ') +
              'in ' + the SHOWN pieces as a list. A list: 'a'; 'a and b'; 'a, b and c' (no
              comma before 'and').
            partial: naked -> 'naked'; half -> 'bare to the waist'; else 'in ' + the SHOWN piece
              at 'torso', else the SHOWN 'body' piece (neither: nothing), and nothing more.
  insignia  (level 'clear'): the insignia of the SHOWN pieces that carry one, in SHOWN order,
            joined with ', '.
  gear      (level 'clear'): 'carrying ' + with_article(ItemDef.name) of each item in G that is
            not in a hand (hands are render_visual's), as a list.
  condition (level 'clear'; at 'partial' only the gore and blood words for values >= 4): gore
            2-3 'smeared with gore', 4-5 'caked in gore'; blood 3-4 'bloodied', 5 'soaked in blood';
            grime 3 'grimy', 4-5 'filthy'; wet 2-3 'soaked through'; in that order, joined ', '.
  The non-empty parts, in the order features, clothes, insignia, gear, condition, joined with '; ',
  the first letter capitalised, ending with '.'; nothing to say -> ''. Deterministic: the same world
  and the same arguments give the same text.
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



import json as _json

from ..contracts.events import Event as _Event, EventType as _ET, WriteOp as _Op, WriteRecord as _W

SENSORY_TYPES: tuple[str, ...] = ("NOISE", "SPEECH", "MOVE", "PORTAL_CHANGE", "ACTION_START", "ACTION_COMPLETE",
                                  "HARM", "DEATH", "FALSE_DEATH", "ITEM_TRANSFER")
_CONF = {"exact": 3, "partial": 2, "tone_only": 1, "visual_only": 2}
_LEVEL_FID = {"clear": "exact", "partial": "partial", "silhouette": "visual_only"}


def _row(s, sql, params=()):
    r = s.query_one(sql, params)
    return dict(r) if r is not None else None


def _canon(tx):
    return tx.canon if getattr(tx, "canon", None) is not None else tx.store.canon


def grant(tx: "Tx", holder_id: str, *, event_id: str, channel: Channel, fidelity: Fidelity,
          text: str, source_id: str | None, at: int, turn_index: int,
          confidence: int | None = None,
          beliefs: list[BeliefFromPercept] | None = None, detail: dict | None = None) -> str:
    if confidence is not None and not (0 <= int(confidence) <= 3):
        raise ValueError('confidence must be 0..3')
    ch = Channel(channel)
    fid = Fidelity(fidelity)
    if fid == Fidelity.NONE:
        raise ValueError("nothing is granted for NONE")
    is_evt = event_id is not None and tx.query_one("SELECT 1 FROM events WHERE event_id=?", (event_id,)) is not None
    if not str(event_id).startswith("scene:"):
        ex = tx.query_one("SELECT percept_id FROM percept_log WHERE holder_id=? AND event_id=? AND channel=?", (holder_id, event_id, ch.value))
        if ex is not None:
            return ex[0]
    pid = tx.mint("pct")
    writes = [_W(op=_Op.INSERT, table="percept_log", values={
        "percept_id": pid, "holder_id": holder_id, "event_id": event_id, "channel": ch.value, "fidelity": fid.value,
        "at": at, "text": text, "source_id": source_id, "detail": detail or {}, "granted_by": "perception.grant",
        "turn_index": turn_index})]
    for b in beliefs or []:
        prp = tx.mint("prp")
        writes.append(_W(op=_Op.INSERT, table="propositions", values={"prop_id": prp, "subject_type": b.subject_type,
                         "subject_id": b.subject_id, "predicate": b.predicate, "object_value": b.object_value, "text": b.text, "matches_claim": b.matches_claim,
                         "created_event": event_id}))
        if ch == Channel.SPEECH:
            addressed = bool((detail or {}).get("addressed_to_me"))
            prov = f"told_by:{source_id}" if addressed and source_id else "overheard"
        else:
            prov = "witnessed"
        for o in tx.query("SELECT h.claim_id FROM claim_holdings h JOIN propositions p ON p.prop_id=h.claim_id "
                          "WHERE h.holder_id=? AND h.superseded_by IS NULL AND p.subject_type=? AND p.subject_id IS ? AND p.predicate=?",
                          (holder_id, b.subject_type, b.subject_id, b.predicate)):
            writes.append(_W(op=_Op.UPDATE, table="claim_holdings", key={"holder_id": holder_id, "claim_id": o[0]}, values={"superseded_by": prp}))
        writes.append(_W(op=_Op.INSERT, table="claim_holdings", values={
            "holder_id": holder_id, "claim_id": prp, "believed": int(b.believed), "confidence": _CONF[fid.value] if confidence is None else min(_CONF[fid.value], int(confidence)),
            "provenance": prov, "fidelity": fid.value, "acquired_at": at, "acquired_via": event_id, "last_confirmed": at, "superseded_by": None}))
    tx.commit_event(_Event(type=_ET.PERCEIVE, writer="mind.perception", at=at, turn_index=turn_index, actor_id=holder_id,
                           cause_event_id=event_id if is_evt else None, writes=writes,
                           payload={"holder_id": holder_id, "percept_id": pid, "channel": ch.value, "fidelity": fid.value}))
    return pid


def _known_name(tx, holder, subject):
    r = _row(tx, "SELECT known_name FROM acquaintance WHERE holder_id=? AND subject_id=?", (holder, subject))
    return r["known_name"] if r else None


def describe(tx: "Tx", holder_id: str, subject_id: str) -> str:
    """describe(B) from the module docstring (no article)."""
    r = _row(tx, "SELECT description FROM acquaintance WHERE holder_id=? AND subject_id=?", (holder_id, subject_id))
    if r:
        return r["description"]
    b = _row(tx, "SELECT kind FROM bodies WHERE body_id=?", (subject_id,))
    if b["kind"] == "infected":
        st = _row(tx, "SELECT type_id FROM infected_state WHERE body_id=?", (subject_id,))
        return "fast figure" if "RUNNER" in st["type_id"] else "shambling figure"
    a = _row(tx, "SELECT d.baseline_json FROM actors a JOIN dossiers d ON d.dossier_id=a.dossier_id WHERE a.actor_id=?", (subject_id,))
    return describe_dossier(_json.loads(a["baseline_json"]))


def _art(s):
    return with_article(s)


def ref(tx, holder, subject, level):
    if level == "silhouette":
        return "a figure"
    if level == "clear":
        n = _known_name(tx, holder, subject)
        if n:
            return n
    return _art(describe(tx, holder, subject))


def _cap(s):
    return s[:1].upper() + s[1:]


_POSTURE = {"standing": "stands", "crouched": "crouches", "sitting": "sits", "lying": "lies", "prone": "lies flat"}


def _lc(name):
    return name[:1].lower() + name[1:]


def _where(tx, holder, subject):
    hp = _row(tx, "SELECT place_id FROM positions WHERE body_id=?", (holder,))
    sp = _row(tx, "SELECT place_id, anchor_id FROM positions WHERE body_id=?", (subject,))
    if sp["place_id"] == hp["place_id"]:
        if sp["anchor_id"]:
            a = _row(tx, "SELECT name FROM anchors WHERE anchor_id=?", (sp["anchor_id"],))
            return " " + at_phrase(a["name"])
        return ""
    pl = _row(tx, "SELECT name FROM places WHERE place_id=?", (sp["place_id"],))
    return " in " + place_phrase(pl["name"])


def render_visual(tx: "Tx", holder_id: str, subject_id: str, level: str) -> str:
    b = _row(tx, "SELECT * FROM bodies WHERE body_id=?", (subject_id,))
    where = _where(tx, holder_id, subject_id)
    if level == "silhouette":
        now = tx.query_one("SELECT now_ms FROM world_clock WHERE id=1")[0]
        moved = tx.query_one("SELECT 1 FROM events WHERE type='MOVE' AND actor_id=? AND at>? AND at<=? AND json_extract(payload,'$.from_place') IS NOT NULL", (subject_id, now - 1000, now)) is not None
        return f"A figure {'moving' if moved else 'still'}{where}."
    still = (not b["alive"]) or b["false_dead_until"] is not None
    verb = "lies still" if still else _POSTURE[b["posture"]]
    r = _cap(ref(tx, holder_id, subject_id, level))
    if level == "partial":
        return f"{r} {verb}{where}."
    held = ""
    canon = _canon(tx)
    for slot, side in (("hand_l", "left"), ("hand_r", "right")):
        it = _row(tx, "SELECT def_ref FROM items WHERE holder_body=? AND holder_slot=?", (subject_id, slot))
        if it:
            held += f", {_art(canon.get(it['def_ref']).name)} in the {side} hand"
    wounds = ""
    if tx.query_one("SELECT 1 FROM wounds WHERE body_id=? AND healed_at IS NULL AND clotted=0 AND severity IN ('severe','catastrophic')", (subject_id,)):
        wounds = ", bleeding badly"
    return f"{r} {verb}{where}{held}{wounds}."


def render_portal(tx, portal_id):
    p = _row(tx, "SELECT * FROM portals WHERE portal_id=?", (portal_id,))
    if p["kind"] == "fence":
        return f"The {p['name']} is {'damaged' if p['damage'] else 'intact'}."
    s = f"The {p['name']} is {'open' if p['is_open'] else 'closed'}"
    if p["barricade"]:
        s += ", barricaded"
    if p["damage"]:
        s += ", damaged"
    return s + "."


def render_sound(received_db: float, fidelity: Fidelity, text: str, direction: str) -> str:
    f = Fidelity(fidelity)
    if f == Fidelity.EXACT:
        return f"{_cap(text)} came {direction}."
    if f == Fidelity.PARTIAL:
        loud = "loud " if received_db >= 70 else "faint " if received_db < 45 else ""
        return f"A {loud}noise came {direction}."
    return f"A sound came {direction}."


_VERB = {"whisper": "whispers", "low": "says quietly", "normal": "says", "raised": "calls out", "shout": "shouts"}


def render_speech(ref: str, volume: str, fidelity: Fidelity, words: str, partial_text: str,
                  direction: str, visible: bool) -> str:
    ref_ = ref   # the contract names it ref
    f = Fidelity(fidelity)
    d = "" if visible else " " + direction
    v = _VERB[volume]
    if f == Fidelity.EXACT:
        return f'{_cap(ref_)} {v}{d}, "{words}"'
    if f == Fidelity.PARTIAL:
        return f'{_cap(ref_)} {v}{d}, not all of it clear: "{partial_text}"'
    return f"{_cap(ref_)} {v}{d}; the words are lost."


def _direction(tx, source, listener_place, path):
    if source.place_id == listener_place:
        a = tx.query_one("SELECT name FROM anchors WHERE place_id=? AND abs(x_m-?)<1e-6 AND abs(y_m-?)<1e-6", (source.place_id, source.x_m, source.y_m))
        return from_phrase(a[0]) if a else "close by"
    ports = [_row(tx, "SELECT * FROM portals WHERE portal_id=?", (pid,)) for pid in path]
    if all(p["is_open"] for p in ports):
        pl = _row(tx, "SELECT name FROM places WHERE place_id=?", (source.place_id,))
        return "from " + place_phrase(pl["name"])
    closed = [p for p in ports if not p["is_open"]]
    return "from the other side of " + thing_phrase(closed[-1]["name"])


_SEV = {"minor": "a shallow", "significant": "a", "severe": "a deep", "catastrophic": "a terrible"}
_ANAT = {"head": "head", "neck": "neck", "chest": "chest", "abdomen": "belly", "back": "back", "arm_l": "left arm", "arm_r": "right arm",
         "hand_l": "left hand", "hand_r": "right hand", "leg_l": "left leg", "leg_r": "right leg", "foot_l": "left foot", "foot_r": "right foot"}


def _conscious(tx, holder):
    b = _row(tx, "SELECT alive, awareness FROM bodies WHERE body_id=?", (holder,))
    return b["alive"] and b["awareness"] in ("alert", "awake", "drowsy")


def _perceive_event(tx, holder, ev, turn_index):
    from ..sense import acoustics, optics
    out = []
    t = ev["type"]
    payload = _json.loads(ev["payload"]) if isinstance(ev["payload"], str) else ev["payload"]
    b = _row(tx, "SELECT alive, awareness FROM bodies WHERE body_id=?", (holder,))
    if not b or not b["alive"] or b["awareness"] in ("unconscious", "dead"):
        return out
    actor = ev["actor_id"]
    rules = tx.rules.acoustics
    if t in ("NOISE", "SPEECH"):
        if actor == holder:
            return out
        src = acoustics.source_point(tx, payload, actor)
        hp = _row(tx, "SELECT place_id, x_m, y_m FROM positions WHERE body_id=?", (holder,))
        if t == "SPEECH":
            db = payload.get("source_db", rules.speech_db.get(payload.get("volume", "normal"), 60.0))
        else:
            db = payload["source_db"]
        recs = [r for r in acoustics.receptions(tx, db, src, ev["at"], rules, exclude={actor} if actor else set()) if r.listener_id == holder]
        if not recs or recs[0].fidelity == Fidelity.NONE:
            return out
        r = recs[0]
        direction = _direction(tx, src, hp["place_id"], r.path_portals)
        vis = optics.visibility(tx, holder, actor, ev["at"]) if actor else "none"
        if t == "NOISE":
            text = render_sound(r.received_db, r.fidelity, payload.get("text", "a noise"), direction)
            sid = actor if (actor and vis != "none") else None
            out.append(grant(tx, holder, event_id=ev["event_id"], channel="auditory", fidelity=r.fidelity, text=text, source_id=sid,
                             at=ev["at"], turn_index=turn_index, detail={"received_db": round(r.received_db, 2), "direction": direction,
                                     "via_portal": r.path_portals[-1] if r.path_portals else None}))
            if r.wakes:
                from ..physical.bodies import wake
                wake(tx, holder, ev["at"], ev["event_id"], turn_index)
        else:
            to = payload.get("to", ["everyone"])
            addressed = holder in to
            visible = vis in ("clear", "partial")
            kn = _known_name(tx, holder, actor)
            if kn and (vis == "clear" or r.fidelity == Fidelity.EXACT):
                rf, sid = kn, actor
            elif visible:
                rf, sid = with_article(describe(tx, holder, actor)), actor
            else:
                rf, sid = "someone", None
            words = payload.get("words", "")
            pw = acoustics.partial_words(words, ev["event_id"], holder) if r.fidelity == Fidelity.PARTIAL else ""
            text = render_speech(rf, payload.get("volume", "normal"), r.fidelity, words, pw, direction, visible)
            wd = words if r.fidelity == Fidelity.EXACT else pw if r.fidelity == Fidelity.PARTIAL else ""
            out.append(grant(tx, holder, event_id=ev["event_id"], channel="speech", fidelity=r.fidelity, text=text, source_id=sid,
                             at=ev["at"], turn_index=turn_index,
                             detail={"words": wd, "volume": payload.get("volume", "normal"), "addressed_to_me": addressed,
                                     "speaker_known_as": None if rf == "someone" else rf, "received_db": round(r.received_db, 2),
                                     "via_portal": r.path_portals[-1] if r.path_portals else None,
                                     "armed_at_me": bool(payload.get("armed")) and addressed and visible}))
            if r.wakes:
                from ..physical.bodies import wake
                wake(tx, holder, ev["at"], ev["event_id"], turn_index)
        return out
    if not _conscious(tx, holder):
        return out
    if t in ("MOVE", "ACTION_START", "ACTION_COMPLETE", "ITEM_TRANSFER"):
        if actor is None or actor == holder:
            return out
        if t.startswith("ACTION_") and not (payload.get("visible") and payload.get("seen")):
            return out
        if t == "MOVE" and payload.get("from_place") is None:
            return out
        subj = actor
    elif t in ("HARM", "DEATH", "FALSE_DEATH"):
        subj = payload.get("body_id")
    elif t == "PORTAL_CHANGE":
        subj = None
    else:
        return out
    if t == "PORTAL_CHANGE":
        pr = _row(tx, "SELECT * FROM portals WHERE portal_id=?", (payload["portal_id"],))
        hp = _row(tx, "SELECT place_id FROM positions WHERE body_id=?", (holder,))
        if hp["place_id"] not in (pr["place_a"], pr["place_b"]):
            return out
        ch = payload.get("changes", {})
        if "is_open" in ch:
            what = "opens" if ch["is_open"] else "closes"
        elif "barricade" in ch:
            what = "is barricaded" if ch["barricade"] > payload.get("before", {}).get("barricade", 0) else "is unbarricaded"
        else:
            what = "is damaged"
        vis = optics.visibility(tx, holder, actor, ev["at"]) if actor and actor != holder else "none"
        out.append(grant(tx, holder, event_id=ev["event_id"], channel="visual", fidelity="exact", text=f"The {pr['name']} {what}.",
                         source_id=actor if vis in ("clear", "partial") else None, at=ev["at"], turn_index=turn_index, detail={"level": "clear"}))
        return out
    if subj == holder and t == "HARM":
        w = _row(tx, "SELECT * FROM wounds WHERE wound_id=?", (payload["wound_id"],))
        sid = actor if (actor and optics.visibility(tx, holder, actor, ev["at"]) != "none") else None
        text = f"Pain: {_SEV[w['severity']]} {w['type']} wound to the {_ANAT[w['anatomy']]}."
        if _conscious(tx, holder):
            out.append(grant(tx, holder, event_id=ev["event_id"], channel="tactile", fidelity="exact", text=text, source_id=sid,
                             at=ev["at"], turn_index=turn_index, detail={"wound_id": w["wound_id"]}))
        return out
    if subj is None or subj == holder:
        return out
    lvl = optics.visibility(tx, holder, subj, ev["at"])
    if lvl == "none":
        return out
    rf = _cap(ref(tx, holder, subj, lvl))
    if payload.get("seen"):
        text = f"{rf} {_fill_seen(tx, holder, payload, ev['at'])}."
    elif t == "MOVE":
        to_a = payload.get("to_anchor")
        if to_a:
            text = f"{rf} moves {to_phrase(_row(tx, 'SELECT name FROM anchors WHERE anchor_id=?', (to_a,))['name'])}."
        else:
            here = _row(tx, "SELECT place_id FROM positions WHERE body_id=?", (holder,))["place_id"]
            fp, tp = payload.get("from_place"), payload["to_place"]
            if fp == here and tp != here:
                text = f"{rf} moves away."
            elif tp == here and fp != here:
                text = f"{rf} arrives."
            elif tp != here:
                text = f"{rf} moves into {place_phrase(_row(tx, 'SELECT name FROM places WHERE place_id=?', (tp,))['name'])}."
            else:
                text = f"{rf} moves."
    elif t == "HARM":
        text = f"{rf} is hurt."
    elif t in ("DEATH", "FALSE_DEATH"):
        text = f"{rf} goes down and does not move."
    elif t == "ITEM_TRANSFER":
        it = _row(tx, "SELECT def_ref FROM items WHERE item_id=?", (payload["item_id"],))
        nm = _canon(tx).get(it["def_ref"]).name if it else "something"
        text = f"{rf} handles {_art(nm)}."
    else:
        text = f"{rf} does something."
    out.append(grant(tx, holder, event_id=ev["event_id"], channel="visual", fidelity=_LEVEL_FID[lvl], text=text,
                     source_id=subj if lvl in ("clear", "partial") else None, at=ev["at"], turn_index=turn_index, detail={"level": lvl}))
    return out


def _events_rows(tx, turn_index, at):
    ph = ",".join("?" * len(SENSORY_TYPES))
    return [dict(r) for r in tx.query(f"SELECT * FROM events WHERE turn_index=? AND at<=? AND type IN ({ph}) ORDER BY seq", (turn_index, at, *SENSORY_TYPES))]


def compile_scene(tx: "Tx", holder_id: str, at: int, turn_index: int) -> list[str]:
    from ..sense import optics
    from ..physical.space import _place_centre
    out = []
    ev_id = f"scene:{turn_index}"
    again = tx.query_one("SELECT 1 FROM percept_log WHERE holder_id=? AND event_id=? AND at=?", (holder_id, ev_id, at)) is not None
    if _conscious(tx, holder_id) and not again:
        hp = _row(tx, "SELECT place_id FROM positions WHERE body_id=?", (holder_id,))
        seen = []
        for r in tx.query("SELECT b.body_id FROM bodies b JOIN positions p ON p.body_id=b.body_id WHERE b.body_id != ? ORDER BY b.body_id", (holder_id,)):
            lvl = optics.visibility(tx, holder_id, r[0], at)
            if lvl == "none":
                continue
            out.append(grant(tx, holder_id, event_id=ev_id, channel="visual", fidelity=_LEVEL_FID[lvl], text=render_visual(tx, holder_id, r[0], lvl),
                             source_id=r[0] if lvl in ("clear", "partial") else None, at=at, turn_index=turn_index, detail={"level": lvl}))
            if lvl in ("clear", "partial"):
                seen.append(r[0])
        # items lying in the place
        canon = _canon(tx)
        pl = _row(tx, "SELECT * FROM places WHERE place_id=?", (hp["place_id"],))
        ob = _row(tx, "SELECT special FROM bodies WHERE body_id=?", (holder_id,))
        for it in tx.query("SELECT * FROM items WHERE place_id=? ORDER BY item_id", (hp["place_id"],)):
            it = dict(it)
            if it["anchor_id"]:
                a = _row(tx, "SELECT * FROM anchors WHERE anchor_id=?", (it["anchor_id"],))
                pt, conc, where = (a["x_m"], a["y_m"]), a["concealment"], f"at the {a['name']}"
            else:
                pt, conc, where = _place_centre(tx, hp["place_id"]), 0, "on the floor"
            me = _row(tx, "SELECT x_m, y_m FROM positions WHERE body_id=?", (holder_id,))
            from ..kernel.clock import daylight_level
            light = pl["light_level"] if pl["indoor"] else daylight_level(at, _row(tx, "SELECT weather FROM world_clock")["weather"])
            d = ((pt[0] - me["x_m"]) ** 2 + (pt[1] - me["y_m"]) ** 2) ** 0.5
            sc = optics.visibility_score(light, _json.loads(ob["special"])["P"], d, conc, False, False)
            if optics.band(sc) in ("clear", "partial"):
                nm = canon.get(it["def_ref"]).name
                out.append(grant(tx, holder_id, event_id=ev_id, channel="visual", fidelity=_LEVEL_FID[optics.band(sc)],
                                 text=f"{_cap(nm)} {where}.", source_id=it["item_id"], at=at, turn_index=turn_index, detail={"level": optics.band(sc)}))
        for pr in tx.query("SELECT portal_id FROM portals WHERE (place_a=? OR place_b=?) AND kind != 'wall' ORDER BY portal_id", (hp["place_id"], hp["place_id"])):
            out.append(grant(tx, holder_id, event_id=ev_id, channel="visual", fidelity="exact", text=render_portal(tx, pr[0]),
                             source_id=pr[0], at=at, turn_index=turn_index, detail={"level": "clear"}))
        if optics.light_at(tx, holder_id, at) > 0:
            for tr in tx.query("SELECT trace_id, text FROM traces WHERE place_id=? ORDER BY created_at, trace_id", (hp["place_id"],)):
                out.append(grant(tx, holder_id, event_id=ev_id, channel="visual", fidelity="exact", text=tr[1],
                                 source_id=tr[0], at=at, turn_index=turn_index, detail={"level": "clear"}))
        # bookkeeping
        ws = [_W(op=_Op.UPSERT, table="known_places", key={"holder_id": holder_id, "place_id": hp["place_id"]},
                 values={"first_seen": at, "last_seen": at, "visited": 1})]
        for s in seen:
            sp = _row(tx, "SELECT place_id FROM positions WHERE body_id=?", (s,))
            if tx.query_one("SELECT 1 FROM acquaintance WHERE holder_id=? AND subject_id=?", (holder_id, s)):
                ws.append(_W(op=_Op.UPDATE, table="acquaintance", key={"holder_id": holder_id, "subject_id": s}, values={"last_seen": at, "last_seen_place": sp["place_id"]}))
            else:
                ws.append(_W(op=_Op.INSERT, table="acquaintance", values={"holder_id": holder_id, "subject_id": s, "known_name": None,
                             "description": describe(tx, holder_id, s), "first_met": at, "last_seen": at, "last_seen_place": sp["place_id"]}))
        existing = tx.query_one("SELECT first_seen FROM known_places WHERE holder_id=? AND place_id=?", (holder_id, hp["place_id"]))
        if existing:
            ws[0] = _W(op=_Op.UPDATE, table="known_places", key={"holder_id": holder_id, "place_id": hp["place_id"]}, values={"last_seen": at, "visited": 1})
        tx.commit_event(_Event(type=_ET.PERCEIVE, writer="mind.perception", at=at, turn_index=turn_index, actor_id=holder_id, writes=ws,
                               payload={"holder_id": holder_id, "bookkeeping": True}))
    for ev in _events_rows(tx, turn_index, at):
        out += [p for p in _perceive_event(tx, holder_id, ev, turn_index) if p not in out]
    return out


def compile_aftermath(tx: "Tx", holder_id: str, events: list["Event"], at: int, turn_index: int) -> list[str]:
    ids = []
    for e in events:
        eid = e.event_id if hasattr(e, "event_id") else e["event_id"]
        row = _row(tx, "SELECT * FROM events WHERE event_id=?", (eid,))
        if row and row["type"] in SENSORY_TYPES:
            _perceive_event(tx, holder_id, row, turn_index)
        ids.append(eid)
    if not ids:
        return []
    ph = ",".join("?" * len(ids))
    return [r[0] for r in tx.query(f"SELECT percept_id FROM percept_log WHERE holder_id=? AND event_id IN ({ph}) ORDER BY at, percept_id", (holder_id, *ids))]


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



def to_phrase(name: str) -> str:
    """Where something goes, from an anchor name (implemented): 'counter' -> 'to the counter';
    'behind the counter' -> 'behind the counter'; 'the doors' -> 'to the doors'."""
    first = name.split(" ", 1)[0].lower()
    if first in PREPOSITIONS:
        return name
    if first == "the":
        return f"to {name}"
    return f"to the {name}"


PROPER_NAME_JOINS = frozenset({"and", "of", "on", "by", "at", "in", "upon", "over", "under", "de", "la", "le", "el"})


def place_phrase(name: str) -> str:
    """A place name as it reads after 'in' / 'from' / 'into' (implemented): a name that already
    starts with an article keeps it, 'The' lower-cased ('The Trujillo house' -> 'the Trujillo
    house', 'a clearing' -> 'a clearing'); a name of two or more words whose first word is
    capitalised and whose every word is capitalised, a number, a '(k)' or a joining word
    (PROPER_NAME_JOINS) is a proper name and keeps no article ('Maple Street', 'Bunkhouse A', 'Main
    and Fifth', 'Exit 14'); anything else gets 'the' and a lower-case first letter ('Sales floor'
    -> 'the sales floor')."""
    words = name.split()
    if not words:
        return name
    first = words[0].lower()
    if first == "the":
        return "the" + name[len(words[0]):]
    if first in ("a", "an"):
        return first + name[len(words[0]):]
    if len(words) >= 2 and words[0][:1].isupper() and all(
            w[:1].isupper() or w[:1].isdigit() or w[:1] == "(" or w.lower() in PROPER_NAME_JOINS for w in words):
        return name
    return "the " + name[:1].lower() + name[1:]


def thing_phrase(name: str) -> str:
    """'counter' -> 'the counter'; a name that already starts with 'the ' is unchanged (implemented)."""
    return name if name.lower().startswith("the ") else f"the {name}"



def _fill_seen(tx, holder, payload, at):
    from ..sense import optics
    seen = payload["seen"]

    def body_ref(b):
        if b == holder:
            return "you"
        lvl = optics.visibility(tx, holder, b, at)
        if lvl == "none":
            return "someone"
        return ref(tx, holder, b, lvl)
    t = payload.get("target_id")
    tb, tphrase = None, None
    if t and t.startswith("wnd_"):
        tb = _row(tx, "SELECT body_id FROM wounds WHERE wound_id=?", (t,))["body_id"]
    elif t and t.startswith("act_"):
        tb = t
    elif t and t.startswith("itm_"):
        it = _row(tx, "SELECT def_ref FROM items WHERE item_id=?", (t,))
        tphrase = thing_phrase(_canon(tx).get(it["def_ref"]).name) if it else "something"
    elif t and t.startswith("prt_"):
        tphrase = thing_phrase(_row(tx, "SELECT name FROM portals WHERE portal_id=?", (t,))["name"])
    elif t and t.startswith("anc_"):
        tphrase = thing_phrase(_row(tx, "SELECT name FROM anchors WHERE anchor_id=?", (t,))["name"])
    if tb is not None:
        seen = seen.replace("{target}'s", "your" if tb == holder else body_ref(tb) + "'s")
        tphrase = body_ref(tb)
    seen = seen.replace("{target}", tphrase or "something")
    d = payload.get("destination_id")
    if d and d.startswith("anc_"):
        seen = seen.replace("{destination}", thing_phrase(_row(tx, "SELECT name FROM anchors WHERE anchor_id=?", (d,))["name"]))
    elif d and d.startswith("plc_"):
        seen = seen.replace("{destination}", place_phrase(_row(tx, "SELECT name FROM places WHERE place_id=?", (d,))["name"]))
    i = payload.get("item_id")
    if i:
        it = _row(tx, "SELECT def_ref FROM items WHERE item_id=?", (i,))
        seen = seen.replace("{item}", with_article(_canon(tx).get(it["def_ref"]).name) if it else "something")
    return seen.replace("{destination}", "somewhere").replace("{item}", "something")


# ---------------------------------------------------------------- P6 additions
_FID_RANK = {"exact": 3, "partial": 2, "visual_only": 1, "tone_only": 0}


def norm_text(text: str) -> str:
    """Comparison form of a text (implemented; see the module docstring)."""
    return " ".join(text.lower().split()).rstrip(".!? ")


def word_for(tx: "Tx", holder_id: str, body_id: str) -> str:
    """The holder's word for a body (implemented; see the module docstring)."""
    row = tx.query_one("SELECT known_name FROM acquaintance WHERE holder_id = ? AND subject_id = ?", (holder_id, body_id))
    if row is not None and row[0]:
        return row[0]
    risen = tx.query_one("SELECT a.known_name FROM infected_state i JOIN acquaintance a ON a.subject_id = i.risen_from "
                         "WHERE i.body_id = ? AND a.holder_id = ? AND a.known_name IS NOT NULL", (body_id, holder_id))
    if risen is not None and risen[0]:
        return f"what was left of {risen[0]}"
    return with_article(describe(tx, holder_id, body_id))


def infer(tx: "Tx", holder_id: str, *, about: tuple[str, str | None], text: str, confidence: int,
          because: list[str], at: int, turn_index: int) -> str:
    from ..kernel.events import committed_or_none
    if not because:
        raise ValueError("a belief cites at least one percept")
    rows = []
    for pid in because:
        r = _row(tx, "SELECT * FROM percept_log WHERE percept_id=?", (pid,))
        if r is None or r["holder_id"] != holder_id:
            raise ValueError(f"not this holder's percept: {pid}")
        rows.append(r)
    st, sid = about
    if st == "self":
        st, sid = "body", holder_id
    elif st == "place":
        st, sid = "place", tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (holder_id,))[0]
    pred = "inferred:" + norm_text(text)
    created = rows[0]["event_id"]
    fid = min((r["fidelity"] for r in rows), key=lambda f: _FID_RANK[f])
    prp = tx.mint("prp")
    writes = [_W(op=_Op.INSERT, table="propositions", values={"prop_id": prp, "subject_type": st, "subject_id": sid, "predicate": pred,
                                                               "object_value": None, "text": text.strip(), "matches_claim": None, "created_event": created})]
    sup = []
    for o in tx.query("SELECT h.claim_id FROM claim_holdings h JOIN propositions p ON p.prop_id=h.claim_id "
                      "WHERE h.holder_id=? AND h.superseded_by IS NULL AND p.subject_type=? AND p.subject_id IS ? AND p.predicate=?",
                      (holder_id, st, sid, pred)):
        sup.append(o[0])
        writes.append(_W(op=_Op.UPDATE, table="claim_holdings", key={"holder_id": holder_id, "claim_id": o[0]}, values={"superseded_by": prp}))
    writes.append(_W(op=_Op.INSERT, table="claim_holdings", values={
        "holder_id": holder_id, "claim_id": prp, "believed": 1, "confidence": min(confidence, 2), "provenance": "inferred",
        "fidelity": fid, "acquired_at": at, "acquired_via": created, "last_confirmed": at, "superseded_by": None}))
    tx.commit_event(_Event(type=_ET.BELIEF_FORM, writer="mind.perception", at=at, turn_index=turn_index, actor_id=holder_id,
                           cause_event_id=committed_or_none(tx, created), writes=writes,
                           payload={"prop_id": prp, "holder_id": holder_id, "because": list(because), "superseded": sorted(sup)}))
    return prp


def appearance_text(tx: "Tx", holder_id: str, subject_id: str, level: str, distance_m: float) -> str:
    raise NotImplementedError("P3")
