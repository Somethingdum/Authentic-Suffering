"""Breaking points (P5, the owner's H1). Rules TEMPER-01..08. docs/as/05_ACTORS.md §7.1.
Owner 'mind.temper' (tempers). R = RulesConfig().temper.

The owner: people here are smart, but human smart. Hunger, grief, the daily dread of turning, of
being eaten alive, exhaustion and old grudges wear everyone down, and everybody has a breaking
point: disrespect the wrong person too much and you get decked in the jaw. A person can be furious
for a reason that is not fair and mean it with their whole heart; not every consequence is violence
(a cold shoulder, a grudge, a word to the leader, a door shut in your face).

Nothing here tells a mind to make trouble (Actor Spec §10). This module keeps the pressures true —
the anger each person carries toward each other person, and how close they are to breaking — and
makes the snap, when it comes, a caused, code-owned act (05_ACTORS §7: an involuntary act is caused,
timed and owned by code), the way a trained response is. What a person says when they snap is
still their own words (TEMPER-06 'words').

TEMPER-01 temper_of(store, actor_id) -> Temper: the actor's fused dossier temper
  (mind.actor.fused(store, actor_id).temper), else Temper() — fuse 3, outlet 'words', grudge 1.
TEMPER-02 Heat is anger at one person, now: tempers (holder_id, toward_id, heat 0..20, updated_at,
  last_kind). heat(store, holder_id, toward_id, at) -> int = the row's heat minus one per
  R.heat_decay_min minutes since updated_at (floor division), never below 0 — nor below the
  strength of an open 'grudge' loop of the holder whose subject_ids contain toward_id (a grudge
  keeps it warm); no row -> that floor (0 without a grudge).
  threshold(store, actor_id) -> int = max(1, temper_of(actor).fuse x 2 - actors.stress // 3): the
  more strained a person is, the shorter their fuse.
TEMPER-03 provocations(tx, holder_id, turn_index, at) -> list[Provocation]: read from the
  holder's OWN percept rows (percept_log) of this turn or the one before (turn_index - 1: what
  reached it after the last wave of the last turn), at <= ``at`` (SKULL-10), at fidelity exact or
  partial, in (at, percept_id) order; a percept whose event_id already has a
  TEMPER_CHANGE of this holder is skipped (each event provokes once). Provocation(toward_id,
  kind, event_id = the percept's event_id); toward_id is the percept's source_id — a body other
  than the holder (someone it can tell did it) — except for harmed_bonded. Kinds, each at most once
  per event, in this order:
    struck         a tactile percept (the holder was hurt by the source)
    shoved         a visual percept of an ACTION_START by the source whose payload target_id is the
                   holder and whose payload def_id is 'shove'; grabbed: def_id 'grapple' or 'disarm'
    threatened     a speech percept with detail.addressed_to_me whose form
                   (mind.firewall.classify_form(detail.words, weapon_pointed_at_receiver =
                   detail.armed_at_me)) is THREAT
    ordered_about  the same, form ORDER or DEMAND, when the source is not in the holder's
                   actors.accepted_authority
    insulted       a speech percept with detail.addressed_to_me whose words contain an entry of
                   INSULT_WORDS as whole words (case-insensitive) — a hint, never proof of motive
                   (Actor Spec §10); how the person reads it later (writeback) is what lasts
    harmed_bonded  a visual percept of a HARM (its source is the one hurt) whose payload body_id is
                   a body the holder has affection >= 2 toward (relationships from the holder) and
                   whose payload actor_id is set, is not the holder, and is the source of a visual
                   percept of the holder in the same window (it saw who did it): toward_id = that
                   actor_id
    stole_from     a visual percept of an ITEM_TRANSFER by the source of an item the holder
                   believes it owns (a live believed 'owner' claim holding of the holder whose
                   object_value is the holder — as mind.affordance reads ownership)
  ('quarreled' is society.settlement STL-15's kind: a row off-screen, provoked directly.)
TEMPER-04 provoke(tx, holder_id, toward_id, kind, event_id, at, turn_index) -> Event:
  heat = min(20, heat(tx, holder, toward, at) + R.provocation_heat[kind]); TEMPER_CHANGE
  {holder_id, toward_id, kind, event_id, heat} (writer 'mind.temper', actor_id = holder,
  cause_event_id = kernel.events.committed_or_none(tx, event_id)) upserting tempers {holder_id,
  toward_id, heat, updated_at = at, last_kind = kind}; then, when R.stress_from has the kind,
  mind.actor.adjust_stress(tx, holder, that amount, the TEMPER_CHANGE's id, at, turn_index).
  Returns the TEMPER_CHANGE.
TEMPER-05 take_in(tx, rng, holder_id, turn_index, at) -> Outburst | None   (turn.pipeline stage 3b:
  every conscious perceiver of the wave, sorted, the PC included)
  provoke() for each provocation (TEMPER-03, in order, then TEMPER-09's). None when there were none, or when the holder
  is the PC (meta pc_actor_id: its anger is real and on record, but the player's hand is never
  taken). Otherwise T =
  the provoked person with the highest heat now (ties: the one provoked last); heat(T) <
  threshold(holder) -> None. Else the breaking point:
    hold it in: rng.chance(tx, 'mind', f"hold:{holder_id}:{E}", min(R.hold_max, R.hold_per_resolve
      x actors.resolve_cur)), E = the event_id of the last provocation by T -> it swallows it:
      mind.resolve.drain(tx, holder, 'held_temper', E, at, turn_index) and None;
    else it snaps: INVOLUNTARY {actor_id: holder, kind: 'outburst', outlet: temper_of(holder).outlet,
      toward_id: T} (writer 'mind.temper', actor_id = holder, cause = E, at); the heat is halved
      (TEMPER_CHANGE kind 'vented', heat = heat // 2) and adjust_stress(-1); TEMPER-07; returns
      Outburst(toward_id = T, outlet, event_id = E).
TEMPER-06 What an outburst does — turn.cognition applies it (its step 4). Like a reflex or the
  wet strain's compulsion it is code's act: it replaces what the actor would have decided this
  wave, it is built from a core affordance def rather than picked from the menu (no resolve gate —
  a snap is the moment nerve runs out; a person who swears they never hit an unarmed man can still
  deck one), and the resolver resolves it like any intent:
    fists   punch T when T is within R.fists_reach_m and a hand is free — never a child, never
            someone in the person's care; otherwise as 'words'
    words   the actor thinks this wave (turn.select SEL-02: an outburst is mandatory); its packet
            says it has snapped (TEMPER-08) and its answer must carry speech to T at volume
            'raised' or 'shout' — else the one repair, and after that 'flight'. The words are the
            person's own.
    cold    walk out ('leave_place'), else to the far end of the place from T ('move_to_anchor')
    flight  as cold
    tears   sit down and break down ('rest')
TEMPER-07 A breaking point leaves a grudge unless temper.grudge is 0: the first open 'grudge' loop
  of the holder naming T (by created_at, loop_id) deepens — mind.mind.strengthen_loop(tx, it, +1,
  the outburst) (max 3); with none, mind.mind.open_loop(tx, holder, 'grudge',
  f"{perception.word_for(holder, T)} pushed me too far", [T], strength = temper.grudge, the
  outburst). And mind.mind.relate(tx, holder, T, 'resentment', +1, the outburst) (the axis clamps).
TEMPER-08 What the person knows of their own state goes into their packet (mind.packet):
  body_lines gains, by actors.stress, as its last line (after 'Unhurt.' when that is the only
  other): 7-8 "You are close to breaking."; 9-10 "You are at the end of your rope.";
  PacketEntity.feeling, per entity (h = heat toward it, th = threshold(holder)):
  h >= th -> "you are furious with them"; 0 < h and h >= th // 2 -> "they are getting under your
  skin"; else an open grudge loop naming it -> "you hold a grudge against them"; else ''. An
  outburst of outlet 'words' this wave (TEMPER-05, INVOLUNTARY at ``at``) -> SkullPacket.outburst =
  f"You snap. You are going to have it out with {the P-handle of T} — now, to their face."; else
  None.
TEMPER-09 (F1c, D-86) What people cannot stand to be near — the owner: smeared in the dead "I'm going
  to smell like hell, look like hell. And people aren't gonna want to be around me for very long
  till I shower"; and walking around naked "should be an issue for most people. Like 'What the
  fuck?'". exposures(tx, holder_id, turn_index, at) -> list[Provocation]: for a holder of kind
  'human', per other living body S of kind 'human' (sorted by body_id), each kind at most once:
    reeked  sense.olfaction.smells(tx, holder, S, at) == 'exact' and odour_of(S, at).kind == 'dead'
            (the reek of the dead on a living person, close enough to gag on)
    bared   a visual percept of the holder, of this turn or the one before (as TEMPER-03), at <=
            ``at``, fidelity exact or partial, whose source_id is S, where S's age_years >= 18,
            bodies.looks is not NULL and physical.objects.coverage(S) has neither 'torso' nor
            'groin' — a naked adult in plain sight (mind.cues 'naked')
  event_id None. A kind is skipped when a TEMPER_CHANGE of this holder toward S of that kind was
  committed at > at - C.reek_every_min ('reeked') / C.bared_every_min ('bared') minutes (C =
  RulesConfig().condition): standing next to it grates again every few minutes, and the reek
  builds heat faster than it fades. provoke() takes event_id None (cause None). What they do with
  it is theirs (the packet already says how the person looks and smells, and how they feel about
  them, TEMPER-08) — until it boils over like any heat.
Off-screen friction between the people of a settlement is society.settlement STL-15 (P9).

INSULT_WORDS is implemented data (a routing hint, TEMPER-03).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.dossier import Temper
    from ..contracts.events import Event
    from ..kernel.rng import Rng
    from ..kernel.store import Store, Tx

INSULT_WORDS: tuple[str, ...] = (
    "idiot", "moron", "stupid", "dumbass", "coward", "useless", "pathetic", "worthless", "loser", "freak",
    "shut up", "screw you", "fuck you", "fuck off", "asshole", "bastard", "bitch", "prick", "piece of shit",
)


@dataclass(frozen=True)
class Provocation:
    toward_id: str
    kind: str        # struck | shoved | grabbed | threatened | ordered_about | insulted | harmed_bonded | stole_from | reeked | bared
    event_id: str | None     # None for TEMPER-09's (what they are, not something they did)


@dataclass(frozen=True)
class Outburst:
    toward_id: str
    outlet: str      # fists | words | cold | flight | tears
    event_id: str


def temper_of(store: "Store | Tx", actor_id: str) -> "Temper":
    raise NotImplementedError("P5")


def heat(store: "Store | Tx", holder_id: str, toward_id: str, at: int) -> int:
    raise NotImplementedError("P5")


def threshold(store: "Store | Tx", actor_id: str) -> int:
    raise NotImplementedError("P5")


def provocations(tx: "Tx", holder_id: str, turn_index: int, at: int) -> list[Provocation]:
    raise NotImplementedError("P5")


def exposures(tx: "Tx", holder_id: str, turn_index: int, at: int) -> list[Provocation]:
    raise NotImplementedError("P5")


def provoke(tx: "Tx", holder_id: str, toward_id: str, kind: str, event_id: str | None, at: int,
            turn_index: int) -> "Event":
    raise NotImplementedError("P5")


def take_in(tx: "Tx", rng: "Rng", holder_id: str, turn_index: int, at: int) -> Outburst | None:
    raise NotImplementedError("P5")
