"""Narrator packet, narration call and the narration row (Stages 16-18). Rules NARR-01..08, NARR-10..12, L9,
DISC-01..04. Owner 'narration.narrator' (writes the narration row only). MUST NOT import
kernel.truth: the narrator is a mind whose skull is the PC's.

pc_first_name(tx, pc_id) -> str: the first word of actors.display_name ('Owen').
known_names(tx) -> set[str]
  Every name somebody in the run could write: all acquaintance.known_name values, every
  actors.display_name and its first word, every places.name (empty strings dropped). lint's
  DISC-NAME checks prose against this set minus the packet's allowed_names.

build_narrator_packet(tx, pc_id, turn_index, t0, settings) -> NarratorPacket   (NARR-01..05, L9)
  Reads only; pc = pc_first_name; now = world_clock.now_ms.
  lines — two sources, merged and sorted by (at, seq, percept_id) (seq of the underlying event, 0
    when none; an event line's percept_id is '' so it comes first on a tie):
    * the PC's percept_log rows of this turn EXCEPT standing views (event_id 'scene:…'):
      NarratorLine(seconds = max(0, at - t0) / 1000, kind = CHANNEL_KIND[channel], text) — (D-170)
      with settings.narration_person 'third_limited' a line that is not speech is told of the PC,
      as every line about the PC's own doing is: mind.perception.retell(text, 'third', the PC's
      bodies.sex) outside double quotes ("A walker lunges and grabs at him.", never "at you" beside
      "Owen chose to hit it"); a speech
      line also gets speaker = detail.speaker_known_as and words = detail.words (None when empty:
      only the tone was heard).
    * the PC's own events of this turn (events.actor_id = the PC), kind 'outcome' unless noted:
        ACTION_START (not the 'speak' def) f"{pc} chose to {label}." — label = payload.label (else
          payload.def_id) with a trailing parenthetical removed (TRAILING_PAREN), told of the PC
          (D-152, TEXT-01: mind.perception.retell(label, 'third', the PC's bodies.sex) — the menu
          spoke to the player, the line speaks of the character) and its first letter lower-cased
          ("Owen chose to climb over the high chain-link fence.", "Owen chose to take his .38
          revolver into his hand."); the 'wonder' def
          (P12, CHEAT-14: the Boss's wonder, cheats.commands.take_wonder) f"{pc} {seen}." — it is
          not chosen and tried, it happens ("Willis walks straight through the wall.");
        SPEECH  kind 'speech', text f'{pc} says, "{words}"', speaker pc, words = payload.words;
        CHECK_RESOLVED  BAND_TEXT[payload.band] (bands not listed: no line);
        ACTION_COMPLETE  RESULT_TEXT[payload.result].format(pc=pc) (results not listed: no line);
        ACTION_BLOCKED  BLOCKED_TEXT[payload.cause].format(pc=pc) (causes not listed: no line);
        MOVE (from_place not null)  f"{pc} goes into {perception.place_phrase(place name)}." when the
          place changed (D-178: going out the side door is going into the yard, whatever anchor he
          arrives at), else f"{pc} moves {perception.to_phrase(to anchor name)}." when it has a
          to_anchor.
        (D-171, SLEEP-03) sleeping and waking — the PC's POSTURE_CHANGE whose payload awareness is
          'asleep', and every AWARENESS_CHANGE of this turn whose payload body_id is the PC (it
          carries no actor_id): to 'asleep' f"{pc} fell asleep."; 'asleep' -> 'awake'
          f"{pc} woke after about {affordance.duration_words(slept_ms / 1000)} asleep." (under a
          minute: f"{pc} woke."); 'unconscious' -> 'awake' f"{pc} came to."; to 'unconscious'
          f"{pc} blacked out."; any other change no line. The prose knows the night passed.
      The failure is the story: a failed check is told as a failure, never softened (NARR-02).
  world_time_text  f"{format_clock(now)}, day {day} since the Fall ({part_of_day})" — (D-172) prefixed
                   f"{format_clock(t0)} to " when the turn took LONG_TURN_MS or more (a night slept,
                   an hour's wait: the prose is told when it began, not only where it ended).
  ASLEEP AT THE END (D-172, SLEEP-03) when the PC ends the turn alive and asleep or unconscious it
                   perceives nobody: people_present and people_looks are empty, and
                   choice_prompt_hint is f"{pc} asleep" (unconscious: f"{pc} senseless") whatever
                   was said — nothing to answer, nothing faced.
  place_text       the PC's place name.       pc_name  pc.
  establish_place  turn_index == 1, or the PC has a MOVE this turn from one place to another;
                   place_details = narration.location.describe(tx, pc_id, now).description_lines then
                   — (D-178) with settings.narration_person 'third_limited' each told of the PC as the
                   lines are (retell by the PC's sex: "He's alone.", "The gap would hide him."), and
                   so is people_present ("A walker shambles toward him.").
  people_present   the text of every latest_view row (narration.location.latest_view) whose source
                   is a body or which is a silhouette.
  people_looks     (F1a-2, NARR-10: the prose shows how people look and smell) for each body other
                   than the PC that the PC sees at clear or partial in its latest view, each once,
                   in row order — all of them when establish_place, else only those it had no
                   VISUAL percept of at 'exact' or 'partial' before this turn (someone just come
                   into the scene): f"{label}: {text}", label = the PC's known_name for it, else
                   with_article(perception.word_for(...)), text = what mind.packet LOOK-06 gives an
                   entity here (appearance_text at the best level and the distance, then
                   smell_text); none when text is empty. The prompt asks the prose to show someone
                   like that when they come in, and never to add to it.
  pc_state_lines   (D-208) first what has hold of the PC: per body that grips them (physical.bodies
                   .grips_on, by id) f"{word_for(pc, it) capitalised} has hold of {pc}."; then, when
                   physical.bodies.tied(pc), f"{pc}'s hands and feet are tied."; then
                   per unhealed wound of the PC (created_at, wound_id): f"{SEVERITY_WORDS[severity]
                   capitalised} {type} wound to the {ANATOMY_WORDS[anatomy]}" + ', bleeding' when
                   physical.bodies.effective_bleed > 0 + '.'; then, when impairment > 0,
                   f"{pc} is {location.impairment_word(impairment)}."; then (P10) the non-empty
                   ``felt`` sentence of each stage physical.bodies.stages(pc) returns, in pathway
                   order (second person, as written: the prose puts it in the PC's body); then (W1,
                   D-80) when an INVOLUNTARY of the PC with payload kind 'compulsion' was committed
                   this turn: URGE_LINE ("Your body did it before you could stop it."); then (F1c)
                   the cold and what the PC has on, exactly as mind.packet's body_lines words them
                   (mind.packet.COLD_LINES, BARE_LINES) — the prose knows when the PC is freezing
                   or naked, and what the people who see it make of it is theirs; then (D-145,
                   NARR-11) what comes back: when the PC's actors.stress >= INTRUSION_STRESS and
                   turn_index % (11 - stress) == 0, INTRUSION_LINE with the text of the PC's own
                   latest visual EXACT or PARTIAL percept, of a turn before this one and within
                   INTRUSION_MS of now, of a DEATH of a human, a HARM of type 'bite' (someone
                   eaten) or an ACTION_START of butcher_human — the worst things seen come back
                   unasked, oftener the worse the strain (a memory, not a feeling: what the PC
                   makes of it is the player's); then (D-146) BROKEN_NIGHT_LINE when the PC woke
                   this turn from a night broken under strain: an AWARENESS_CHANGE of the PC to
                   'awake' whose cause event is the PC's own falling asleep (action.cascade's
                   scheduled wake, core CAS-061/062).
  comprehension    'low' when attr_mod(P) + attr_mod(I) <= 4, 'high' when >= 8, else 'average'
                   (NARR-05: how much of a tactic the prose may explain; never which facts).
  allowed_names    sorted: pc, the PC's full display name, the PC's known_name for every source of
                   its percepts this turn, the names of the places it knows (known_places), and
                   (D-145) the PC's known_name for the bodies of what came back (NARR-11); (D-264) with
                   each such known_name of a person, its first word — "Marcus" of "Marcus Castillo":
                   a man known by his full name is called by his first.
  pc_beliefs       (D-197) the texts of mind.retrieval.lore_lines(tx, pc_id, turn_index, now,
                   PacketRules.max_lore) that are not among the texts of lore_lines(tx, pc_id,
                   turn_index - 1, now, the same n): what the PC grew up hearing about what is in front
                   of them, on the turn it first comes up — the prose may let it come to mind as the
                   PC's belief (which can be wrong), never tell it as the story's fact.
  choice_prompt_hint  the LAST speech percept of the turn addressed to the PC at EXACT or PARTIAL ->
                   f"answer {speaker_known_as or 'them'}" (percepts ordered by (at, percept_id));
                   else, when mind.cues.cues_of(tx, pc_id, turn_index, now) includes threat_seen or
                   weapon_pointed, "decide what to do about the threat"; else None.
  style = narrator_state; banned_phrases = the canon 'narration' style list; length / person /
  tense / intensity from settings; player_input_echo_block = narration.lint.echo_block(tx,
  turn_index, rules.style) — (D-169) minus every n-gram the packet's own words hold
  (content_ngrams of each line's text and words — but the PC's own speech lines, which are the
  player's words — the place details, the people present and their looks, with the same n and
  minimum): what the world says itself ("goes through the back door into the rear alley") is the
  narrator's to use, even when the player happened to type it too.

narrate(client, packet, style_rules, numbers, *, config, all_known_names, turn_index)
    -> (prose, findings, attempts, passed)   (NARR-06..08)
  Up to numbers.max_narration_attempts attempts, each ONE NARRATION call (lanes.requests
  .build_request(config, NARRATION, turn_index=turn_index, context=packet, k=packet, words =
  numbers.narration_words[packet.length], fix = a list of the last draft's errors as f"{rule}:
  {detail}" — [] until a draft has failed), sent with client.call(request) (no output model).
  (D-154, NARR-12) The prompt says what the lint throws a draft away for before the first draft is
  written, not only after: never three sentences in a row starting with the same word, the active
  voice (few sentences of was / were and a participle), no mood named in the abstract, and a
  person named only by a name of packet.allowed_names — listed as f"Names {pc} knows (use no other
  proper name outside quoted speech; describe anyone else): {', '.join(allowed_names)}" when not
  empty. Every draft thrown away is a whole new one on the slow lane. (D-157) A speech line shows
  its speaker with a capital first letter and its exact words; one whose words are None (only
  the tone was heard) shows its text ("A woman says quietly; the words are lost.") — never a
  quoted "None" for the prose to put in someone's mouth.
  A call whose parse_status is not 'ok' or whose text is empty after strip() still counts as an
  attempt and leaves ``fix`` as it was. The draft is the text stripped. Each draft: report =
  lint.lint_prose(draft, packet, style_rules, numbers, all_known_names); when the code lint
  passed, ONE RENDER_LINT call (build_request(config, RENDER_LINT, turn_index=turn_index, context
  and ctx = LintContext(packet, prose, sentences = lanes.parse.split_sentences(prose)),
  json_schema = to_lm_schema(RenderLintJudgement)), output RenderLintJudgement) whose every
  unsupported sentence (index in range) ADDS an error LintFinding('DISC-JUDGE', f"{reason}:
  {sentence}", sentence_index) — the judge can fail a draft, never pass one; a judge call that
  does not parse adds nothing (the code lint's verdict stands). A draft with no errors is returned
  at once (prose, its findings, attempts, True). Otherwise the draft with the fewest errors so far
  is kept (the earliest on a tie) and,
  after the last attempt, returned with passed False — the world is never rolled back for prose.
  No draft at all -> (code_render(packet), [LintFinding('NARR-FALLBACK', 'no draft came back; the
  moment is told plainly', severity 'warning')], attempts, False).
code_render(packet) -> str
  The moment told plainly by code: the place details when establishing, then each line — a speech
  line with words as f'{speaker or "Someone"}: "{words}"', any other line's text — joined by ' '
  (nothing at all: f"{place_text}. Nothing changes.").
packet_hash(packet) -> sha256 hex of canonical_json(packet.model_dump(mode='json')).
write_narration(tx, turn_index, prose, packet, passed, attempts) -> Event
  NARRATION {turn_index, packet_hash, lint_passed, attempts} (writer 'narration.narrator', at =
  now) inserting narration {turn_index, text = prose, packet_hash, lint_passed, attempts}.

Output shape (NARR-08): one uninterrupted scene — no headings, labels, stat blocks, lists or
'Options:' menus (the prompt says so; mechanics receipts are the UI's, never the prose's).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..contracts.narration import NarratorPacket

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..contracts.narration import LintFinding
    from ..contracts.settings import EngineConfig, RunSettings
    from ..kernel.store import Tx
    from ..lanes.client import LaneClient

URGE_LINE = "Your body did it before you could stop it."   # W1 (D-80): pc_state_lines
INTRUSION_LINE = "It comes back unasked: {text}"             # D-145 (NARR-11): pc_state_lines
INTRUSION_STRESS = 7
BROKEN_NIGHT_LINE = "You come awake in the dark, a few hours in, and you are not rested."   # D-146: pc_state_lines
INTRUSION_MS = 3 * 24 * 3600 * 1000
LONG_TURN_MS = 10 * 60 * 1000                                   # D-172: world_time_text tells when it began
CHANNEL_KIND: dict[str, str] = {"visual": "sight", "auditory": "sound", "speech": "speech", "tactile": "touch",
                                "olfactory": "smell", "vibration": "sound"}
BAND_TEXT: dict[str, str] = {"clean": "It goes cleanly.", "cost": "It works, at a cost.", "fail": "It doesn't work.",
                             "break": "It goes badly wrong."}
RESULT_TEXT: dict[str, str] = {
    "no_progress": "No progress.", "fell": "{pc} falls.", "blocked_by_lock": "It won't open.", "no_key": "There is no key for it.",
    "held": "It holds.", "jammed": "The lock jams.", "click": "A dry click. The gun does not fire.", "hit": "A hit.",
    "miss": "A miss.", "refused_full_hands": "Their hands are full.", "no_ammo": "There is no ammunition for it.",
    "grabbed": "{pc} gets a grip.", "slipped": "The grab slips.", "knocked_down": "They go down.", "disarmed": "The weapon comes free.",
    "stumbled": "{pc} stumbles.", "task_done": "The work is finished.", "surrendered": "{pc} gives up.",
}
BLOCKED_TEXT: dict[str, str] = {
    "incapable": "{pc} can't manage it.", "target_gone": "What {pc} went for is not there any more.",
    "target_dead": "They are already dead.", "item_gone": "It isn't there any more.",
    "referent_missing": "It isn't where {pc} thought it was.", "portal_closed": "The way is shut.",
    "not_admitted": "{pc} can't fit through.", "out_of_reach": "It's out of reach.", "hands_full": "{pc}'s hands are full.",
    "portal_open": "It's already open.",
}
TRAILING_PAREN = re.compile(r"\s*\([^()]*\)\s*$")


def pc_first_name(tx: "Tx", pc_id: str) -> str:
    raise NotImplementedError("P7")


def known_names(tx: "Tx") -> set[str]:
    raise NotImplementedError("P7")


def build_narrator_packet(tx: "Tx", pc_id: str, turn_index: int, t0: int, settings: "RunSettings") -> NarratorPacket:
    raise NotImplementedError("P7")


async def narrate(client: "LaneClient", packet: NarratorPacket, style_rules, numbers, *, config: "EngineConfig",
                  all_known_names: set[str], turn_index: int) -> tuple[str, list["LintFinding"], int, bool]:
    raise NotImplementedError("P7")


def code_render(packet: NarratorPacket) -> str:
    raise NotImplementedError("P7")


def packet_hash(packet: NarratorPacket) -> str:
    raise NotImplementedError("P7")


def write_narration(tx: "Tx", turn_index: int, prose: str, packet: NarratorPacket, passed: bool, attempts: int) -> "Event":
    raise NotImplementedError("P7")
from ._impl_narrator import pc_first_name, build_narrator_packet, narrate, known_names, write_narration, code_render, packet_hash  # noqa
