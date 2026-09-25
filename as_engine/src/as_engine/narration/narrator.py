"""Narrator packet, narration call and the narration row (Stages 16-18). Rules NARR-01..08, L9,
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
      NarratorLine(seconds = max(0, at - t0) / 1000, kind = CHANNEL_KIND[channel], text); a speech
      line also gets speaker = detail.speaker_known_as and words = detail.words (None when empty:
      only the tone was heard).
    * the PC's own events of this turn (events.actor_id = the PC), kind 'outcome' unless noted:
        ACTION_START (not the 'speak' def) f"{pc} chose to {label}." — label = payload.label (else
          payload.def_id) with a trailing parenthetical removed (TRAILING_PAREN) and its first
          letter lower-cased ("Owen chose to climb over the high chain-link fence.");
        SPEECH  kind 'speech', text f'{pc} says, "{words}"', speaker pc, words = payload.words;
        CHECK_RESOLVED  BAND_TEXT[payload.band] (bands not listed: no line);
        ACTION_COMPLETE  RESULT_TEXT[payload.result].format(pc=pc) (results not listed: no line);
        ACTION_BLOCKED  BLOCKED_TEXT[payload.cause].format(pc=pc) (causes not listed: no line);
        MOVE (from_place not null)  f"{pc} moves {perception.to_phrase(to anchor name)}." when it
          has a to_anchor, else f"{pc} goes into {perception.place_phrase(place name)}." when the
          place changed.
      The failure is the story: a failed check is told as a failure, never softened (NARR-02).
  world_time_text  f"{format_clock(now)}, day {day} since the Fall ({part_of_day})".
  place_text       the PC's place name.       pc_name  pc.
  establish_place  turn_index == 1, or the PC has a MOVE this turn from one place to another;
                   place_details = narration.location.describe(tx, pc_id, now).description_lines then.
  people_present   the text of every latest_view row (narration.location.latest_view) whose source
                   is a body or which is a silhouette.
  pc_state_lines   per unhealed wound of the PC (created_at, wound_id): f"{SEVERITY_WORDS[severity]
                   capitalised} {type} wound to the {ANATOMY_WORDS[anatomy]}" + ', bleeding' when
                   physical.bodies.effective_bleed > 0 + '.'; then, when impairment > 0,
                   f"{pc} is {location.impairment_word(impairment)}."; then (P10) the non-empty
                   ``felt`` sentence of each stage physical.bodies.stages(pc) returns, in pathway
                   order (second person, as written: the prose puts it in the PC's body); then (W1,
                   D-80) when an INVOLUNTARY of the PC with payload kind 'compulsion' was committed
                   this turn: URGE_LINE ("Your body did it before you could stop it."); then (F1c)
                   the cold and what the PC has on, exactly as mind.packet's body_lines words them
                   (mind.packet.COLD_LINES, BARE_LINES) — the prose knows when the PC is freezing
                   or naked, and what the people who see it make of it is theirs.
  comprehension    'low' when attr_mod(P) + attr_mod(I) <= 4, 'high' when >= 8, else 'average'
                   (NARR-05: how much of a tactic the prose may explain; never which facts).
  allowed_names    sorted: pc, the PC's full display name, the PC's known_name for every source of
                   its percepts this turn, the names of the places it knows (known_places).
  choice_prompt_hint  the LAST speech percept of the turn addressed to the PC at EXACT or PARTIAL ->
                   f"answer {speaker_known_as or 'them'}" (percepts ordered by (at, percept_id));
                   else, when mind.cues.cues_of(tx, pc_id, turn_index, now) includes threat_seen or
                   weapon_pointed, "decide what to do about the threat"; else None.
  style = narrator_state; banned_phrases = the canon 'narration' style list; length / person /
  tense / intensity from settings; player_input_echo_block = narration.lint.echo_block(tx,
  turn_index, rules.style).

narrate(client, packet, style_rules, numbers, *, config, all_known_names, turn_index)
    -> (prose, findings, attempts, passed)   (NARR-06..08)
  Up to numbers.max_narration_attempts attempts, each ONE NARRATION call (lanes.requests
  .build_request(config, NARRATION, turn_index=turn_index, context=packet, k=packet, words =
  numbers.narration_words[packet.length], fix = a list of the last draft's errors as f"{rule}:
  {detail}" — [] until a draft has failed), sent with client.call(request) (no output model).
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
