"""Code-rendered location description (P7). Rules UI-LOC-01, UI-SKULL-01, UI-REF-01, GEO-01.
Used by the Play UI's "Where you are" panel (service.view) AND by the narrator's place
establishment. NO model call (UI-LOC-01): the player always has a reliable description of where
they are, built from the PC's own perception. Reads only; MUST NOT import kernel.truth.
docs/as/10_UI.md §6 shows the templates.

latest_view(tx, pc_id) -> list[dict]
  The PC's latest standing view: its percept_log rows whose event_id starts with 'scene:' and whose
  (turn_index, at) is the greatest such pair, ordered by percept_id.
light_of(tx, place_row, at) -> int
  Indoor places: places.light_level. Outdoor: kernel.clock.daylight_level(at, world_clock.weather).
impairment_word(n) -> str
  0 or less 'clear-headed', 1 'slowed', 2-3 'impaired', 4-5 'badly impaired', 6+ 'barely functioning'.

describe(tx, pc_id, at, refs=None) -> LocationView
  place = the PC's place (positions). area_name = the parent place's name when places.parent_id is
  set and the PC has a known_places row for it; else the zone's name when zone_id is set; else ''.
  description_lines (at most 6), in this order:
    1  f"{Cap(with_article(words))}, {LIGHT_WORDS[light]}." — words = the non-empty of: size
       ('small' under 15 m²; nothing from 15 to 60 m²; above 60 m² 'long' when the longer side is at
       least twice the shorter, else 'large'), material (indoor places only, not 'open_air',
       underscores as spaces), KIND_WORDS.get(kind, kind with underscores as spaces); light =
       light_of(...). ("A large brick room, dim.")
    2  AMBIENT[(indoor, weather)] — except when that key is missing, or the weather is 'wind' with
       wind_level < 1: then by places.ambient_db: < 35 "It is quiet.", < 50 "There is a low
       background noise.", else "It is noisy."
    3  (only when light > 0) the first three anchors of the place, by anchor_id, whose kind is in
       NOTABLE_KINDS: one "There is {a} here."; two "There are {a} and {b} here."; three "There are
       {a}, {b} and {c} here." (each with_article of the anchor name).
    4  (P10) traces: the texts of the latest_view rows whose source is a trace ('trc_…'), in that
       order, joined with ' ' — what the PC's own standing view showed of what happened here
       (nothing when there is none; never read from the traces table).
    5  occupancy: the distinct bodies (source ids 'act_…') of latest_view(...) that are positioned
       in the PC's place: 0 "You're alone."; 1 "One other person is here."; n
       f"{NUMBER_WORDS[n]} other people are here." (digits past twelve).
    6  (only when light > 0) cover: the anchor with cover >= 2 (highest cover, then anchor_id) ->
       f"The {name} would stop a bullet." when its cover is 3 or more, else f"The {name} gives
       some cover.";
       the anchor with cover <= 1 and concealment >= 2 (highest concealment, then anchor_id) ->
       f"The {name} would hide you."; both sentences on one line when both exist.
  can_see: per latest_view row whose source is an item ('itm_…'): SeenThing(ref, name = the
    ItemDef name (no items row: 'something'), detail = the rest of the percept text after the name,
    stripped, then every trailing '.' removed (str.rstrip('.')), when the text starts with the name
    (case-insensitive), else '').
  people: per latest_view VISUAL row, in row order: a body (source 'act_…', each body once) ->
    PersonChip(ref, label = the PC's known_name for it, else with_article(perception.word_for(...)),
    status_words, known = a known_name exists); status_words only at level 'clear', in this order:
    'asleep' (alive and awareness 'asleep'), 'down' (dead or unconscious), 'armed' (a firearm or
    melee item in hand_l / hand_r), 'hurt' (an unhealed wound that is severe or catastrophic, or
    not clotted). (F1a-2) looks = what mind.packet LOOK-06 gives an entity here (appearance_text at
    the best level of the PC's latest view of it and space.point_distance, then smell_text, the
    non-empty ones joined with one space). A silhouette (no source, detail.level 'silhouette') ->
    PersonChip(ref for the internal id f"figure:{percept_id}", label 'a figure', [], known False).
  exits: every portal of the place except walls, by portal_id -> ExitView(ref, label = portal
    name, state_words, leads_to = the far place's name when the PC has a known_places row for it,
    else 'unknown'). state_words, orthogonal (GEO-01): 'open' / 'closed' (not for fences);
    'locked' only when is_locked AND the PC has an ACTION_COMPLETE with result 'blocked_by_lock'
    caused by an ACTION_START of the PC targeting this portal (you learn a lock by trying it);
    'barricaded' when barricade > 0; 'broken' when damage >= 2.
  dangers: the PC's live believed holdings (believed 1, superseded_by NULL) whose proposition
    predicate is 'threat', by (acquired_at, claim_id): f"{text} ({PROVENANCE_WORDS[provenance
    before ':'] or 'you believe it'})".
  noise_text: level = the largest of places.ambient_db and the received_db of the PC's auditory and
    speech percepts of the current turn: < 45 'quiet', < 70 'some noise', < 95 'noisy', else
    'deafening'.
  Refs (UI-REF-01): ``refs`` is the view's dict ref -> internal id (service.view passes
  session.extras['view_refs']): an internal id that already has a ref with the prefix keeps it; a
  new one gets prefix + (1 + the number of refs with that prefix). Prefixes: 'p' people, 'i'
  things, 'x' exits. refs None: numbering per prefix from 1 for this call only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..contracts.view import LocationView

if TYPE_CHECKING:
    from ..kernel.store import Tx

LIGHT_WORDS: dict[int, str] = {0: "pitch dark", 1: "dim", 2: "low light", 3: "lit", 4: "bright"}
KIND_WORDS: dict[str, str] = {"room": "room", "building": "building", "street": "street", "outdoor": "open space",
                              "vehicle": "vehicle", "tunnel": "tunnel"}
NUMBER_WORDS: list[str] = ["no", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven",
                           "Twelve"]
AMBIENT: dict[tuple[bool, str], str] = {
    (True, "wind"): "Wind pushes at the building.", (True, "rain"): "Rain drums on the roof.",
    (True, "storm"): "A storm batters the building.", (False, "wind"): "Wind gusts through.",
    (False, "rain"): "Rain falls steadily.", (False, "storm"): "A storm tears through.",
    (False, "snow"): "Snow is falling.", (False, "fog"): "Fog hangs low.", (False, "heat"): "The heat presses down.",
}
NOTABLE_KINDS: tuple[str, ...] = ("cover", "furniture", "hiding_spot", "window")
PROVENANCE_WORDS: dict[str, str] = {"witnessed": "you saw it", "overheard": "you overheard it", "told_by": "you were told",
                                    "inferred": "your guess", "rumour": "a rumour", "read": "you read it",
                                    "common": "everyone knows", "childhood": "you've always known"}


def latest_view(tx: "Tx", pc_id: str) -> list[dict]:
    raise NotImplementedError("P7")


def light_of(tx: "Tx", place: dict, at: int) -> int:
    raise NotImplementedError("P7")


def impairment_word(n: int) -> str:
    raise NotImplementedError("P7")


def describe(tx: "Tx", pc_id: str, at: int, refs: dict[str, str] | None = None) -> LocationView:
    raise NotImplementedError("P7")
from ._impl_location import describe, latest_view, light_of, impairment_word  # noqa
