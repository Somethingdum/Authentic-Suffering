"""PlayView builder (P7). Rules UI-SKULL-01, UI-CLARITY-01, UI-REF-01, UI-SUG-01, UI-SUG-02.
MUST NOT import kernel.truth: every field comes from the PC's own body, inventory, percepts,
beliefs, acquaintance, open loops and lessons. docs/as/10_UI.md §5 (word tables).

build_view(tx, session) -> PlayView   (reads only)
  refs: a new dict ref -> internal id, stored as session.extras['view_refs'] BEFORE anything is
    assigned, and filled as the view is built (narration.location's rule: prefix + next number;
    'p' people, 'i' items and things, 'x' exits, 'm' map places). No internal id reaches the view.
  clock    ClockView(day, time_text = format_clock(now), part_of_day, weather_text =
           WEATHER_WORDS.get(world_clock.weather, the raw weather), light_text =
           LIGHT_WORDS[location.light_of(...)] capitalised).
  location narration.location.describe(tx, pc, now, refs).
  inventory  physical.objects.inventory_tree(tx, pc): hand_l / hand_r items -> hands; items whose
           def has a container block -> containers; the rest -> worn (worn / pocket / pack).
           ItemView(ref 'i', name (the tree's name), qty, condition_word(items.condition), detail,
           mass_text = f"{mass_g x qty / 1000:.1f} kg", actions). detail: a firearm -> its rounds
           left (cylinder / internal: props.rounds; magazine-fed: the rounds of its magazine
           contents + 1 when props.chambered) as f"{n} round" + 's' unless 1; any other item with
           props.rounds -> the same wording; else ''. actions: in a hand 'Drop', then 'Put away'
           for a firearm or melee weapon, then 'Reload' for a firearm; elsewhere 'Take out'; then
           'Eat' (kind food) / 'Drink' (water) / 'Use' (medical). ContainerView(item = its
           ItemView, bulk_used = sum(bulk x qty) of its contents, bulk_max = max(1,
           container.capacity_bulk), contents: nested containers as ContainerView, else ItemView).
           carried_mass_kg = round(objects.carried_mass_kg, 2); load_word = objects.load_word.
  body     wounds (unhealed, (created_at, wound_id)): WoundView(where = ANATOMY_WORDS[anatomy],
           what = f"{type} wound", severity_word = SEVERITY_VIEW[severity], bleeding_word(
           effective_bleed), treated = treatment is a non-empty list). needs: Thirst, Hunger,
           Tiredness from the needs row (level = min(5, stage), word = need_word(stage); no needs
           row: none of the three), then Pain (p = bodies.pain or 0: level = min(5, p), word =
           need_word(p)). impairment_word(physical.bodies.impairment). resolve = ResolveView(cur,
           max, resolve_word). status_words: the posture when not 'standing', the awareness when
           not 'awake', 'hidden' when positions.hidden.
  people   one PersonView per acquaintance row of the PC, ordered (last_seen desc, subject_id):
           label = known_name or description; relation_words from the PC's relationships row
           toward them, in this order: trust >= 2 'you trust them', trust <= -2 'you distrust
           them', affection >= 2 'you care about them', respect >= 2 'you respect them', fear >= 2
           'you fear them', resentment >= 2 'you resent them', obligation >= 2 'you owe them',
           obligation <= -2 'they owe you'; last_seen_text: 'here now' when they are a source of the
           PC's latest standing view, 'not seen yet' when the PC has never had a percept of them,
           else f"last seen day {day}, {HH:MM}" (+ f", {place name}" when acquaintance
           .last_seen_place is set) from the PC's latest percept of them (MAX(at) over every
           turn); what_you_know: the text of up to 5 of the PC's believed, not superseded holdings
           whose proposition has subject_type 'body' and subject_id them, ordered (acquired_at
           desc, claim_id); promises: the text of the PC's open promise_made / promise_owed loops
           whose subject_ids contain them, by (created_at, loop_id); alive_known:
           'alive' when in view now, else 'unknown'.
  journal  the PC's open loops by (created_at, loop_id): promises_made, promises_owed, goals
           (kinds goal, plan, desire); rumours: the proposition text of the PC's holdings that are
           not superseded (believed or not: a rumour you doubt is still one you heard) with
           provenance 'rumour:…', or acquired_via 'rumour:…' or a RUMOUR_SPREAD event
           (world.rumours, P9), by (acquired_at, claim_id); lessons (at, lesson_id). (all lists
           are texts; reputation_heard: P10, when talk can reach the one it is about; the_dead:
           P12.)
  map      one MapPlace per known_places row of the PC, ordered (name, place_id): ref 'm', label,
           visited, here, exits_known = the names of non-wall portals joining it to another known
           place (by portal_id).
  suggestions (UI-SUG-01/02) and session.extras['suggestions'] (ref -> entry):
           1. a remainder in session.extras['remainder'] -> 's1': label f"Continue: {remainder}",
              mode 'do', entry {'remainder', 'label'};
           2. the PC's AffordanceSet (enumerate_affordances(tx, pc, canon affordances, now,
              world_clock.turn_index)) in enumerator order, without
              WAIT options and without 'observe_area', and (P10) without an option whose ui_label
              repeats an earlier suggestion's (three of the dead read alike; the nearest comes
              first): the first 5 (4 after a remainder) -> label = ui_label, mode 'say' for SPEAK
              options else 'do', entry {'signature', 'label'};
           3. last, 'Wait and watch': the 'observe_area' option (else the first WAIT option),
              mode 'do', entry {'signature', 'label': 'Wait and watch'}.
           Refs 's1', 's2', … in that order. Suggestions are only the PC's own bound options —
           never story directions (UI-SUG-02).
  lanes    LanesView(A = LaneStatus('Main model', ok = not client.is_down(A), model), B =
           LaneStatus('Second model', …)).
  mechanics  settings.show_mechanics 'off' -> None; else MechanicsReceipt(lines): one line per
           CHECK_RESOLVED of the PC this turn (by seq): f"{what}: {BAND_WORDS[band]}" where what =
           the ui_label of canon affordance payload.def_id up to its first '{', stripped (empty:
           the def id with underscores as spaces); the defender's side of an opposed check
           (def_id f"{d}:defend", action.checks.opposed — something grabbed or shoved the PC)
           reads f"Resisting {what of d, lower-cased}" ('Resisting grab'); 'full' adds
           f" (needed {target} or less, rolled {draw})".
  run_id, turn_index, pc_name (display name), alive, sandbox (meta.sandbox == '1').
Word helpers (10_UI.md §5; play/words.js holds the same tables): condition_word (>=90 pristine,
>=70 good, >=45 worn, >=25 damaged, >=1 failing, else broken); resolve_word by cur/max (>=0.8
steady, >=0.6 shaken, >=0.4 fraying, >0 breaking, else broken); bleeding_word by %/min (0 none, <0.1
oozing, <1.5 bleeding, <6 bleeding badly, else pouring); need_word by stage (<=1 fine, 2
noticeable, 3 bad, 4 severe, else critical).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..contracts.view import PlayView

if TYPE_CHECKING:
    from ..kernel.store import Tx
    from .session import Session

WEATHER_WORDS: dict[str, str] = {"clear": "Clear", "overcast": "Overcast", "rain": "Raining", "storm": "Storm", "fog": "Fog",
                                 "wind": "Windy", "heat": "Hot", "snow": "Snowing"}
SEVERITY_VIEW: dict[str, str] = {"minor": "minor", "significant": "serious", "severe": "severe", "catastrophic": "critical"}
BAND_WORDS: dict[str, str] = {"clean": "clean success", "cost": "success with a cost", "fail": "failure", "break": "bad failure"}


def condition_word(condition: int) -> str:
    raise NotImplementedError("P7")


def resolve_word(cur: int, mx: int) -> str:
    raise NotImplementedError("P7")


def bleeding_word(pct_per_min: float) -> str:
    raise NotImplementedError("P7")


def need_word(stage: int) -> str:
    raise NotImplementedError("P7")


def build_view(tx: "Tx", session: "Session") -> PlayView:
    raise NotImplementedError("P7")
