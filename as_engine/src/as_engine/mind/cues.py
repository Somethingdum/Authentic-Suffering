"""Cue detection (P5). Which registry cues (as_content/packs/*/cues.yaml) are PRESENT for one mind
this turn, computed from that mind's own percepts and body only — never the truth layer (the
same knowledge rule as the packet, SKULL-02; MUST NOT import kernel.truth).

Used by: task interrupts (tasks.interrupt_on), standing orders (plans.standing_orders trigger ->
the 'interrupt_trigger' salience flag), trained responses (capability.trained_responses ->
action.intent.plan_continuation reflexes), and lesson retrieval (P6).

cues_of(tx, holder_id, turn_index, at) -> set[str]
  Over the holder's percept_log rows with this turn_index and at <= ``at`` (P = one percept; its
  event is events[P.event_id] when that is a committed event; 'visible' = a VISUAL percept at
  clear or partial; dist(x) = space.point_distance(holder, x) now):
  loud_noise        an auditory or speech P at PARTIAL or better whose event payload source_db >= 80,
                    or any P with detail.received_db >= 80
  gunshot_close     an auditory P of a NOISE with payload.kind 'shoot' whose source point
                    (acoustics.source_point) is within 30 m of the holder
                    (space.distance_to_point)
  gunshot_distant   the same, farther than 30 m
  glass_break / metal_crash   an auditory P of a NOISE whose payload.kind is that cue id
  footsteps_close   an auditory P of a NOISE whose kind is a movement effect (move_to_anchor,
                    move_through_portal, follow_body, leave_place, flee) with its source within
                    5 m, from a body the holder has no visible P of this turn
  voice_unknown     a speech P whose detail.speaker_known_as is null or is not an
                    acquaintance.known_name of the holder
  addressed_by_name a speech P with detail.addressed_to_me whose words contain (word match,
                    case-insensitive) the first word of the holder's own identity.name or any of
                    its dossier aliases
  grabbed_from_behind  a CONTROL_ESTABLISH event of this turn whose target is the holder and whose
                    holder body has no visible P of this turn at an earlier ``at``
  weapon_pointed    a visible P of an ACTION_START whose def is shoot_center_mass / shoot_head
                    with target_id = the holder, or a speech P with detail.armed_at_me
  threat_seen       weapon_pointed, or a visible P of a HARM / ACTION_START with payload verb
                    'attack', or a visible P whose source body is infected
  infected_seen     a visible P whose source body kind is 'infected'
  infected_close    infected_seen with that body within 2 m now
  blood_seen        a visible P of a HARM whose wound is severe or catastrophic, or a standing-view
                    P whose text contains 'bleeding badly'
  corpse_seen       a visible P whose source body is dead (alive 0) or false-dead
  dark_room         optics.light_at(holder) <= 1
  door_forced       an auditory P of a NOISE with kind 'force_portal', or a visual P of a
                    PORTAL_CHANGE whose changes include damage
  bonded_hurt       a visible P of a HARM on a body the holder has affection >= 2 toward or shares
                    a household with
  dependent_in_danger  bonded_hurt or threat_seen where the body concerned (harmed / targeted /
                    within 5 m of the threat) is one the holder is guardian_of
  stranger_approaching  a visible P of a MOVE, inside the holder's place, by a body with no
                    acquaintance known_name for the holder, whose to-point is closer to the holder
                    than its from_anchor's point (no from_anchor -> not detected)
  promise_broken (P6) a PROMISE_BROKEN event of this turn with payload.promisee_id = the holder
                    (its own conclusion, mind.mind.close_loop, LOOP-04 — no percept needed)
  P10 — what an infection shows (lore §3.2, the intake doctrine's "inspect wounds and mouth"). A
  SIGHTING = a VISUAL percept at CLEAR of a body B (its source) that is alive, of kind 'human', not
  the holder, and within RulesConfig.infected.sign_range_m of the holder now:
  bite_wound_seen   a sighting of a B with an unhealed wound of type 'bite';
  (stage signs)     every cue id in the ``signs`` of each stage physical.bodies.stages(B) returns
                    (content: fever_seen, spreader_signs, ...), for a sighting of that B.
  Not detected before their phase (never present until then): scream, fire_seen, smoke_smell (no
  fire or scream model yet); whisper_seen, sudden_silence (P7 observed_social); shift_change,
  ration_cut (P9). Belief cues ('knows_*') are HELD, not present: mind.affordance reads them from
  lessons (AFF-10).
  F1a: plus appearance_cues(tx, holder_id, B, level, physical.space.point_distance(holder, B))
  for every other body B that is the source_id of one of the holder's visual percept_log rows of
  this turn (turn_index, at <= ``at``) at level clear or partial — level = the best of them
  ('clear' over 'partial').
  SMELL-06 (F1b): plus SMELL_CUES[kind] for the detail.odour of each of the holder's olfactory
  percept_log rows of this turn (turn_index, at <= ``at``), and for each such seen body B that
  sense.olfaction.smells(holder, B, at) is not None: SMELL_CUES[odour_of(B, at).kind].
Returns the set; pure (reads only).

LOOK-05 appearance_cues(tx, holder_id, subject_id, level, distance_m) -> list[str]   (F1a)
  What the subject's appearance tells the holder at a glance, sorted, from the same facts as
  mind.perception.appearance_text (level 'silhouette' / 'none' -> []). KEY = the SHOWN piece at
  'torso', else the SHOWN 'body' piece (appearance_text's SHOWN; None without looks):
  visibly_armed      clear only (a partial look shows no hands, VIS-03): an item of
                     physical.objects.visible_gear whose ItemDef has a firearm or melee block
  uniformed          clear or partial: KEY's style has 'uniform' or 'tactical'
  formally_dressed   clear or partial: KEY's style has 'formal'
  wearing_insignia   clear only: a SHOWN piece carries an insignia
  bloodied           blood >= 3 at clear, >= 4 at partial
  gore_covered       gore >= 2 at clear, >= 4 at partial
  filthy             clear only: grime >= 4
  soaked             clear only: wet >= 2
  half_dressed       clear or partial: looks recorded, 'torso' not covered, 'groin' covered
  naked              clear or partial: looks recorded, neither 'torso' nor 'groin' covered
  (A body whose looks are not recorded is never half_dressed or naked.) The cue ids are in the
  core registry (as_content/packs/core/cues.yaml).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..kernel.store import Tx

SENSORY_CUES_P5: frozenset[str] = frozenset({
    "loud_noise", "gunshot_close", "gunshot_distant", "glass_break", "metal_crash", "footsteps_close",
    "voice_unknown", "addressed_by_name", "grabbed_from_behind", "weapon_pointed", "threat_seen",
    "infected_seen", "infected_close", "blood_seen", "corpse_seen", "dark_room", "door_forced",
    "bonded_hurt", "dependent_in_danger", "stranger_approaching",
})


SMELL_CUES: dict[str, str] = {    # F1b, SMELL-06: sense.olfaction kind -> registry cue
    "dead": "reek_of_dead", "death": "smell_of_death", "blood": "blood_smell", "unwashed": "unwashed_smell",
}


APPEARANCE_CUES: frozenset[str] = frozenset({
    "visibly_armed", "uniformed", "formally_dressed", "wearing_insignia", "bloodied", "gore_covered",
    "filthy", "soaked", "half_dressed", "naked",
})


def cues_of(tx: "Tx", holder_id: str, turn_index: int, at: int) -> set[str]:
    raise NotImplementedError("P5")


def appearance_cues(tx: "Tx", holder_id: str, subject_id: str, level: str, distance_m: float) -> list[str]:
    raise NotImplementedError("P3")
from ..action._impl_p5a import cues_of  # noqa
