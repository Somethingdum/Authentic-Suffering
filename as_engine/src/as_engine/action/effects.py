"""Effect handlers (P5). One handler per AffordanceDef.effect id. Rules EFF-01..08. Owner of
ACTION_* events: writer 'action.resolve' (they carry no table writes). Every state change goes
through the owning module's API (space.move_event, space.portal_change_event, objects.transfer /
fire / destroy, bodies.apply_harm / treat / posture_event / grip_event / release_event /
wake, tasks.*); a handler never writes a foreign table and never reads ``controller`` (L12).

How an action runs (action.resolve drives it; handlers only LAND actions)
  An Intent starts at the wave time T. The resolver commits ACTION_START at T, then any speech
  (SPEECH at T), then the action LANDS at land_at = T + ceil(est_duration_s * 1000) ms (condition-
  ended actions land at T). Landing = EFFECTS[def.effect](tx, rng, intent, land_at, ctx) -> Landing.
  An action whose land_at is later than ctx.horizon_ms is not landed in this transaction: the
  resolver schedules an ACTION_LAND queue row at land_at (kernel.clock.QUEUE_TYPES) and it lands
  in a later transaction — or is interrupted first (ACTION_INTERRUPT) when the actor starts
  another action (any ACTION_START of that actor cancels its pending ACTION_LAND row).
  Bodies are where they started until their MOVE lands (no mid-walk positions).

  @dataclass EffectCtx: turn_index, horizon_ms, start_event_id (the ACTION_START event id — the
      cause_event_id of every event the landing commits), wave_start_ms.
  @dataclass Landing: result: str (below), band: CheckBand | None, events: list[Event] (committed,
      in commit order), blocked: str | None (a cause -> the resolver commits ACTION_BLOCKED instead
      of ACTION_COMPLETE), complete_at: int (ms; land_at unless a COST delayed it).
  After the handler the resolver commits ACTION_COMPLETE {actor_id, def_id, result, band,
  visible: false} at complete_at, or ACTION_BLOCKED {actor_id, def_id, cause} at land_at.

ACTION_START payload: {actor_id, def_id, verb, target_id, destination_id, item_id,
  est_duration_s, visible (= AffordanceDef.visible_act), seen (= SEEN[def_id] or null),
  continues_task (true only for keep_working), label (= intent.bound.label, the option as the
  actor was offered it), goal (= intent.goal), attention (B4 FOCUS-02: intent.attention, None
  without one)}. label and goal are the actor's own record of what
  it chose and why (mind.memory builds its aftermath from them); perception never renders them. Perception renders it for observers as
  f'{Ref} {seen}.' with {target} / {destination} / {item} filled for THAT observer (a body: 'you'
  when it is the observer — "{target}'s" becomes 'your' — else its Ref; a thing: thing_phrase of
  its name; a wound: the wounded body), and grants nothing when seen is null.

Legality at landing (EFF-02) — the state as it stands NOW (earlier landings already applied);
  the FIRST failing test is the cause (ACTION_BLOCKED, no state change, no NOISE):
  'incapable'    the actor is dead, not conscious, or not mobile for a def with requires.mobile
  'target_gone'  a body target not in the actor's place — except range 'visible' (any place, as
                 long as sense.optics.visibility(actor, target) != 'none' now) and range 'audible'
                 (the actor's place or a place joined to it by an OPEN portal); for range
                 'visible' also a target in the actor's place that it can no longer see; an anchor
                 destination not in the actor's place
  'target_dead'  a body target that is dead (alive 0), for every def except finish_downed,
                 watch_target and (I1) infected_bite (the dead feed on the dead: world.infected,
                 rule INF-16) and butcher_carcass, and (F1c) smear_gore and strip_clothing
  'item_gone'    the bound item is no longer where it was bound (held/carried by the actor for
                 item_held / item_carried; lying at the bound place/anchor for item_reachable;
                 inside the container for take_from)
  'referent_missing'  set by the barrier (a believed referent that never existed at T0)
  'portal_closed'     move_through_portal / peek through a portal that is closed (peek needs it
                      closed: blocked 'portal_open' when it is open) / flee path blocked
  'not_admitted'      space.admits() false for the actor
  'out_of_reach'      a touch-range target farther than 1.5 m at landing
  'hands_full'        pick_up / take_from / equip with no free hand (hand_r, then hand_l)

Walking to the referent (range 'reach'; the est_duration_s already paid for it): before its
  own state change a landing commits a MOVE of the actor to the referent's point when the actor
  is farther than 1.0 m from it — an item's anchor point (the place centre when it lies loose), a
  portal's point on the actor's side, a container's point; strike_* / finish_downed walk to the
  target body's point only when it is farther than the weapon's reach_m. The MOVE's to_anchor is
  that anchor when there is one, else null (a free point).

Checks (action.checks.roll at land_at; CHECK_RESOLVED committed before the state change). The
  situation modifier (07_RULES.md §1.1) is computed by ``situation(tx, intent, land_at)``: light
  of the target's (or, with no target, the actor's) place via sense.optics.light_at for defs whose
  check attribute is P or whose tags include 'ranged' (light 0 -3, 1 -2, 2 -1); intent.pace
  'careful' +1, 'rushed' (or the def is run_to_anchor) -1 — the explicit pace, never words in
  intent.manner (Actor Spec §14: a manner has no mechanical channel); the right tool +1 (force_portal with a held item tagged 'pry';
  pick_lock with a carried item tagged 'lockpick'); a def tagged 'negotiable' with a body target
  that has refused the actor: + mind.firewall.negotiable_target_penalty(n), n = the largest
  times_asked among that body's refusals with requester_id = the actor and status 'standing' or
  'reopened' (WILL-05; no such row, no term — refusal rows exist from P6); clamp -3..+3.
  Resistance comes from
  CheckSpec.resistance (07_RULES.md §1.2): 'range_band' = range band of the point distance
  (<= 5 m 0, <= 15 m 1, <= 30 m 2, <= 60 m 3; beyond the firearm's effective_range_m 5) + the
  target's cover (its anchor's cover when its posture is crouched or prone, else 0) + 1 when the
  target moved in the last 1000 ms + 2 for defs tagged 'head'; 'portal.lock_quality',
  'portal.barricade', 'portal.lock_and_barricade' from the portals row; 'target.attr_mod.<X>'
  from the target body; 'obstacle.class' by the portal height_cm (<= 120 -> 1, <= 200 -> 3,
  else 5); 'wound.severity' (minor 0, significant 1, severe 2, catastrophic 4);
  'observer.best_perception' = the highest attr_mod(P) among conscious bodies that can see the
  actor's destination point now (optics against the actor as it will stand), + 1 if that body
  perceived a sound of this turn at PARTIAL or better; 0 with no observer.
  Bands: CLEAN and COST succeed, FAIL and BREAK fail. COST, unless the effect says otherwise:
  complete_at = land_at + ceil(0.5 * est_duration_s * 1000) and the effect's NOISE is +10 dB.
  No free miss: a FAIL never hurts anyone by itself; BREAK complications are listed per effect.

NOISE (writer 'action.propagate', no writes): {source_db, kind: def_id, text: NOISE_TEXT[effect],
  place_id, anchor_id, x_m, y_m, outdoor: bool} at the actor's point after the landing's state
  change, at land_at, when source_db > 0 (def.noise_db, or the weapon's for shots and strikes,
  +10 on COST). Not for blocked actions.

Per effect (result strings in quotes; 'done' unless noted):
  move_to_anchor     MOVE to the destination anchor's point. sneak_to_anchor has a stealth6 check
                     ('observer.best_perception'): margin >= 3 -> the MOVE sets hidden = 1.
  move_through_portal  admits() must pass; MOVE to the far-side point (space.portal_point of the
                     far place); crawl reason -> complete_at += 3 x the walking part.
  follow_body / shield_dependent  MOVE to the target's current anchor (or point) in the actor's
                     place; target elsewhere -> 'target_gone'.
  leave_place        the nearest open, admitting portal of the actor's place by walking distance
                     (ties: portal_id): MOVE to its far side. None -> 'portal_closed'.
  flee               like leave_place but choosing the portal whose far-side point is farthest from
                     the threat (target); none -> MOVE to the anchor of the place farthest from it.
  climb              A + athletics check vs obstacle.class. CLEAN/COST: MOVE to the far side (COST
                     also a minor 'cut' to hand_r instead of the time cost); FAIL: 'no_progress';
                     BREAK: 'fell' — a blunt wound to leg_l, significant when height_cm > 200 else
                     minor, and posture 'lying'. Ignores admits(): climbing is how a fence is crossed.
  open_portal / close_portal   portal_change_event {is_open: true/false}; open on a locked or
                     barricaded portal -> 'blocked_by_lock' (a result, not ACTION_BLOCKED: you
                     tried the handle and learned something).
  lock_portal / unlock_portal  needs a carried item tagged 'key' -> {is_locked}; else 'no_key'.
  pick_lock          check vs portal.lock_quality; success -> {is_locked: false}; FAIL
                     'no_progress'; BREAK 'jammed' (no state change; the noise is the cost).
  barricade_portal / unbarricade_portal  {barricade: +1 / -1}.
  force_portal       S check vs lock_and_barricade; success -> {is_locked: false, barricade: 0,
                     is_open: true, damage: +1}; FAIL 'held'; BREAK 'held' + a minor blunt wound to
                     arm_r of the actor.
  peek_portal        no state; result 'peeked' (what the peek shows is a P7 perception matter).
  pick_up            objects.transfer to the first free hand; stackables move whole.
  drop_item          objects.transfer to the actor's place at its anchor.
  give_item          objects.transfer into the target's first free hand; none free ->
                     'refused_full_hands' (a result).
  take_from / put_into   objects.transfer out of / into the container.
  search_container / search_place   no state in P5; result 'searched' (P10 loot and discovery).
  equip              objects.transfer from worn/pocket/pack/container to the first free hand
                     (hand_r, then hand_l); the item's props.holstered is dropped by the transfer
                     (objects.transfer(..., props_update={'holstered': False}) — P5 addition).
  holster            objects.transfer from the hand to 'worn' with props_update {'holstered':
                     True} for a firearm or a melee weapon; anything else to 'pack'.
  reload             firearm with a magazine: the fullest carried magazine of its caliber (ties:
                     lowest item id; none -> 'no_ammo') replaces the one inside (old one to 'pack',
                     new one into the gun), then objects.chamber. Cylinder / internal: loose ammo
                     of its caliber (carried, item-id order) up to capacity, consumed with
                     objects.destroy(qty=n), then objects.load_rounds; complete_at = land_at +
                     max(0, n x 2000 - the option's duration in ms) later ('no_ammo' when n = 0).
  shoot              legality + the item must still be in a hand. objects.fire: 'click' -> NOISE
                     20 dB with kind 'click' ('a dry click') and result 'click' (no check, no hit;
                     a click is never a gunshot cue). 'fired' -> NOISE at
                     the firearm's noise_db ('a gunshot'), then P + firearms check vs 'range_band'.
                     Hit (CLEAN/COST): anatomy 'head' for defs tagged 'head', (H1) for defs tagged
                     'leg' rng.choice('resolve', f'leg:{actor}:{target}', ['leg_l', 'leg_r']), else
                     rng.weighted('resolve', f'anatomy:{actor}:{target}', CENTRE_MASS); severity by
                     WEAPON_WOUNDS[damage_class][band] (+ head/neck upgrade), type 'gunshot',
                     contamination 1; bodies.apply_harm -> result 'hit'. (H1) A 'leg' hit is at least
                     'significant' (function_loss 1: the target can walk, not run — bodies can_run),
                     and a target still alive and conscious after it goes down:
                     bodies.posture_event(target, 'lying', land_at, the HARM id, turn_index) — shot in
                     the leg and left for the dead. FAIL 'miss'. BREAK 'miss'
                     and, when another living body stands within 1 m of the target's point, the
                     lowest-id such body is resolved as a fresh shot at situation - 2 ('stray').
  strike_melee       walks to the target first when it is farther than the weapon's reach (MOVE to
                     the target's point). Opposed when CheckSpec.opposed and the target is conscious
                     and mobile: attacker S + melee (or brawling for tag 'unarmed') vs the target's
                     opposed_attribute + opposed_skill (action.checks.opposed). A still target never
                     draws: a plain roll vs resistance 0. Winner attacker by 'clean' -> CLEAN, any
                     other win -> COST; defender wins -> 'miss'. Wound: weapon damage_class via
                     WEAPON_WOUNDS, type = the weapon's wound_types[0]; tag 'unarmed' -> 'blunt'
                     one step below light (CLEAN minor, COST no wound, result 'hit'); tag 'head' ->
                     anatomy head; finish_downed: no check, anatomy head, catastrophic for medium /
                     heavy weapons, severe for light. Bite (tag 'bite'; I1 — the dead eat people
                     alive, world.infected INF-15/16): the attacker must hold a grip on a living
                     target (grips row); a dead target needs none — else 'no_grip'. No check.
                     anatomy = rng.weighted('resolve', f'feed:{attacker}:{target}:{n}',
                     world.infected.FEED_ANATOMY) (never the head or the neck), n = the target's
                     HARMs of type 'bite' whose cause event's actor_id is the attacker; severity
                     'significant' for n = 0 on a living target, else 'severe' (flesh torn away);
                     type 'bite', contamination 2 (bodies.apply_harm). Then, the target alive:
                     physical.bodies.expose(tx, rng, target, 'wet', 'bite', land_at, the HARM id,
                     turn_index) (it takes only humans), and when the target is a conscious human
                     after the bite, NOISE {source_db: RulesConfig.infected.scream_db, kind
                     'screaming', text 'someone screaming', place_id / x_m / y_m: the target's
                     point} (writer 'action.propagate', actor_id = the target, at = land_at) — the
                     sound that brings the rest of them: world.infected.draw_to_feed(tx, target,
                     attacker, land_at, the NOISE id, turn_index) (INF-15). Then
                     world.infected.feed(tx, attacker,
                     land_at, the HARM id, turn_index), world.infected.taint_water(tx, target,
                     attacker, land_at, the HARM id, turn_index), the attacker's NOISE as before;
                     'hit'. W1 (D-77): any other melee wound of severity 'significant' or worse
                     landed on a contagious body (physical.bodies.contagious) -> bodies.expose(tx,
                     rng, attacker, 'wet', 'fluid_splash', land_at, the HARM id, turn_index): their
                     blood in your eyes and mouth. F1c (LOOK-07): any such wound (significant or
                     worse, bite excepted) also soils the attacker — bodies.soil(attacker, gore = 1
                     when the target is of kind 'infected', else blood = 1, source 'splashed', cause
                     the HARM) — after the exposure. BREAK (attacker lost):
                     the attacker's posture becomes 'crouched' ('stumbled').
  grapple            opposed S + brawling vs target A + brawling; attacker wins -> grip_event.
                     'grabbed' / 'slipped'.
  break_grip         opposed S + brawling vs the gripper's S + brawling; wins -> release_event.
  shove              opposed S + brawling vs S; wins -> target posture 'lying' ('knocked_down').
  shove_toward       (H1 — shove_toward_dead) the def's opposed check: S + brawling vs the target's
                     A + athletics (keeping your feet); a target that is not conscious and mobile does
                     not defend and loses. NOISE as shove. The attacker loses -> 'braced' (FAIL).
                     Wins -> D = the active infected body (world.infected.active) in the target's place,
                     other than the target, nearest to it (space.point_distance; ties by body_id); none
                     -> as shove
                     ('knocked_down'). Else: the target is pushed along the line from its point to D's,
                     s = min(2.0, max(0.0, distance - 0.5)) metres (it lands at most 2 m from where
                     it stood and never closer than 0.5 m to D): space.move_event(tx, target, its
                     place, None, x, y, land_at, the ACTION_START, turn_index) committed; then
                     bodies.posture_event(target, 'lying', ...) when it is conscious; then
                     world.infected.attract(tx, D, target, land_at, the MOVE's id, turn_index,
                     reason='sight'); result 'shoved_to_the_dead' (CLEAN/COST as shove).
  disarm             opposed A + brawling vs A + brawling; wins -> the target's held weapon
                     (firearm first, then melee; hand_r first) is transferred to the floor at the
                     target's anchor ('disarmed').
  take_cover / hide  MOVE to the anchor, then posture 'crouched'; hide: stealth6 check
                     ('observer.best_perception'); margin >= 1 -> hidden = 1 on the MOVE.
  crouch / stand / go_prone   bodies.posture_event 'crouched' / 'standing' / 'prone'.
  observe / wait / guard / sleep / rest   condition-ended: land at T with result 'holding';
                     sleep -> bodies.posture_event('lying', awareness='asleep'); rest ->
                     posture_event('sitting').
  continue_task      action.tasks.advance(actor, horizon) inside the landing; result 'working'.
  speak              the SPEECH was committed by the resolver at T; result 'said'.
  calm_person        C + persuasion check vs target.attr_mod.I; success -> mind.actor.adjust_stress
                     (target, -2 CLEAN / -1 COST); BREAK -> +1.
  signal             result 'signalled' (visible ACTION_START only).
  surrender          every held item dropped at the actor's anchor (hand_l, then hand_r), then
                     posture 'crouched'; result 'surrendered'.
  treat_wound        bodies.treat(target wound, method = the def's tag among pressure / bandage /
                     suture / clean / packing); suture has a medicine check vs 'wound.severity'
                     (FAIL and BREAK 'no_progress': medicine failures cost time, not blood).
                     The wound must be unhealed and its body within touch ('out_of_reach').
                     Medical items are not used up in P5 (P9 adds wear).
                     W1 (D-77): when the wound's body is not the actor and is contagious
                     (physical.bodies.contagious) and the treatment went on (a TREATMENT was
                     committed) -> bodies.expose(tx, rng, actor, 'wet', 'fluid_contact', land_at,
                     the TREATMENT id, turn_index): a host's blood on the hands that stop it.
                     F1c (LOOK-07): a treatment that went on to a wound of severity 'significant'
                     or worse on someone else soils the actor: bodies.soil(actor, blood = 1,
                     source 'treated', cause the TREATMENT) — after the exposure.
  apply_tourniquet   bodies.treat(..., 'tourniquet'); W1 and F1c as treat_wound.
  eat / drink        objects.destroy(item, qty=1) (cause = the start event), then
                     bodies.refresh_need(actor, 'hunger' | 'thirst'); result 'ate' / 'drank'.
                     P10, drink is mouth contact (lore §3.2), BEFORE the destroy: c =
                     objects.contaminated(item, land_at); c with c.by != actor ->
                     bodies.expose(tx, rng, actor, c.pathway, 'mouth_contact_item', land_at, the
                     start event, turn_index); then, when a stage physical.bodies.stages(actor)
                     returns for 'wet' has saliva_infectious -> objects.contaminate(item, 'wet',
                     actor, land_at, the start event, turn_index).
                     I1 — tainted food and water, and (D-77) every fluid of a host: eat is checked
                     exactly as drink, BEFORE the destroy. A LASTING mark (c.lasting: the dead's
                     fluids in meat or water, world.infected INF-18/19) -> expose(..., c.pathway,
                     'tainted_food' for eat / 'tainted_water' for drink, ...), whoever made it; a
                     passing mark by someone else -> 'mouth_contact_item' as above (food a host
                     ate from carries it as a bottle does); and an eater at a saliva-infectious
                     stage marks the food it ate from (objects.contaminate, passing).
  butcher            (I1) the target is a dead animal body (bodies.kind 'animal', alive 0) that has
                     not been butchered (bodies.special has no 'butchered') and the actor holds an
                     item tagged 'blade' in a hand — else 'nothing_to_butcher'. meat = the AnimalDef's
                     meat_portions (canon, by bodies.content_ref); objects.create(core:item/raw_meat,
                     qty = meat, on the floor at the carcass's point (its anchor, else its place),
                     origin 'craft', props {} ...); then BODY_CONDITION {body_id, butchered: true}
                     (writer 'physical.bodies', cause = the start event) updating bodies.special
                     with 'butchered': true (the body stays: a carcass). When the carcass carries any HARM of type 'bite'
                     (the dead fed on it) the new meat is tainted: objects.contaminate(meat, 'wet',
                     the actor of the first such bite's cause event, land_at, the start event,
                     turn_index, lasting=True) — it looks and smells like any meat; then (F1c)
                     bodies.soil(actor, blood = 2, source 'butchered', cause the start event);
                     result 'butchered'.
  spit               (W1, D-77 — the wet strain's compulsion; defs tagged 'compulsion' are
                     reflex_only: never on a menu, built by turn.cognition step 3). spit_into: the
                     bound item (water or food) must still be in the actor's hand or lying loose
                     within touch — objects.contaminate(tx, item, 'wet', actor, land_at, the start
                     event, turn_index) (a passing mark: saliva). spit_in_mouth: the target must be
                     asleep and within touch — bodies.expose(tx, rng, target, 'wet',
                     'mouth_contact_direct', land_at, the start event, turn_index). Otherwise
                     'missed'; result 'spat'. Quiet (the def's noise_db).
  wash               (F1c, D-86) the bound item (a water item, carried or held) — its ItemDef.water
                     .ml >= C.wash_full_ml (C = RulesConfig().condition) is a full wash, less is a
                     wipe. The water is tried first as mouth contact is: c = objects.contaminated(
                     item, land_at), c with c.by != actor -> bodies.expose(tx, rng, actor,
                     c.pathway, 'fluid_contact', land_at, the start event, turn_index) (their fluids
                     all over you, in the eyes and the mouth). Then objects.destroy(item, qty=1)
                     (cause = the start event) and bodies.wash(actor, full=...); result 'washed' /
                     'wiped'.
  smear              (F1c; the owner's trick: covered in the dead to walk among them) the target is
                     a dead body of kind 'infected' (alive 0) within touch — else
                     'nothing_to_smear'. bodies.soil(actor, gore = C.smear_gore, blood = 1, grime =
                     1, source 'smeared', cause = the start event); then the strain (D-77: the dead's
                     fluids carry it) — bodies.expose(tx, rng, actor, 'wet', 'gore_in_wound' when the
                     actor has an unhealed wound whose treatment has no 'bandage' (it goes in
                     through the wound), else 'gore_smear', land_at, the BODY_CONDITION id,
                     turn_index); result 'smeared'.
  take_off           (F1c) the bound worn clothing piece goes to the actor's first free hand (hand_r,
                     then hand_l), else its pack slot (objects.transfer; Holder('body', actor,
                     'pack')); result 'took_off'. CNT-11: when the actor's age_years is not >= 18
                     and physical.objects.coverage without the piece lacks 'torso' or 'groin',
                     nothing moves — result 'kept_on' (nobody under 18 is ever left bare; the menu
                     never offers it either, mind.affordance).
  change_into        (F1c) the bound clothing piece (carried, not worn) goes on — objects.transfer
                     to Holder('body', actor, 'worn') — after every worn clothing piece at the same
                     slot and layer comes off to where the new piece was (its hand, else the pack),
                     in item_id order: one action, never bare in between. The same CNT-11 guard on
                     the coverage after the change -> 'kept_on'. Result 'changed'.
  strip              (F1c; clothes off the dead, and off those who cannot stop you) the target must
                     be a human with age_years >= 18 (CNT-11: never anyone younger, alive or dead,
                     and never a body of unknown age) that is dead, unconscious or false-dead,
                     within touch, and the bound item still worn by it — else
                     'kept_on'. The piece goes to the actor's first free hand, else its pack
                     slot; result 'stripped'.
  throw_distraction  objects.transfer to the destination anchor; NOISE 70 dB 'something clattering'
                     at the LANDING POINT (not the thrower).

CENTRE_MASS = [('chest', 30), ('abdomen', 20), ('arm_l', 10), ('arm_r', 10), ('leg_l', 10),
               ('leg_r', 10), ('head', 10)]
WEAPON_WOUNDS[damage_class][band]: light {clean: significant, cost: minor}; medium {clean: severe,
  cost: significant}; heavy {clean: catastrophic, cost: severe}. Head/neck upgrade: a medium
  firearm CLEAN on head or neck -> catastrophic; a heavy melee CLEAN with margin >= 6 on head or
  neck -> catastrophic.

P10 — arriving somewhere new: after any handler commits a MOVE whose to_place differs from its
  from_place, it calls world.worldmove.on_arrival(tx, rng, mover, to_place, the MOVE's at, the MOVE
  id, turn_index) and adds what that committed to its Landing.events (a building's rooms appear the
  first time anyone arrives, and the infected of a place are there when the first person is).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from ..contracts.common import CheckBand

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.rng import Rng
    from ..kernel.store import Tx
    from .intent import Intent


@dataclass(frozen=True)
class EffectCtx:
    turn_index: int
    horizon_ms: int
    start_event_id: str
    wave_start_ms: int


@dataclass
class Landing:
    result: str
    band: CheckBand | None = None
    events: list["Event"] = field(default_factory=list)
    blocked: str | None = None
    complete_at: int | None = None   # None -> land_at


EffectHandler = Callable[["Tx", "Rng", "Intent", int, EffectCtx], Landing]
EFFECTS: dict[str, EffectHandler] = {}

EFFECT_IDS: tuple[str, ...] = (
    "move_to_anchor", "move_through_portal", "follow_body", "leave_place", "open_portal",
    "close_portal", "lock_portal", "unlock_portal", "barricade_portal", "unbarricade_portal",
    "force_portal", "peek_portal", "pick_up", "drop_item", "give_item", "take_from", "put_into",
    "search_container", "search_place", "equip", "holster", "reload", "strike_melee", "shoot",
    "grapple", "break_grip", "shove", "disarm", "take_cover", "hide", "crouch", "stand",
    "go_prone", "observe", "wait", "guard", "speak", "signal", "treat_wound", "apply_tourniquet",
    "eat", "drink", "sleep", "rest", "continue_task", "flee", "surrender", "climb",
    "throw_distraction", "shove_toward", "butcher", "spit", "wash", "smear", "take_off", "change_into",
    "strip",
)

CENTRE_MASS: tuple[tuple[str, int], ...] = (
    ("chest", 30), ("abdomen", 20), ("arm_l", 10), ("arm_r", 10), ("leg_l", 10), ("leg_r", 10), ("head", 10),
)

WEAPON_WOUNDS: dict[str, dict[str, str]] = {
    "light": {"clean": "significant", "cost": "minor"},
    "medium": {"clean": "severe", "cost": "significant"},
    "heavy": {"clean": "catastrophic", "cost": "severe"},
}

@dataclass(frozen=True)
class Gesture:
    """B4 (Actor Spec §9, GEST-01): a small expression that goes with an attempt. Never contact — a
    touch, a grab or covering a mouth is an attempt of its own."""
    label: str        # what the menu says ('point at {target}')
    seen: str         # what an observer sees ('points at {target}')
    hands: int        # free hands it needs (0, 1 or 2)
    targeted: bool    # made toward someone seen


GESTURES: dict[str, Gesture] = {
    "nod": Gesture("nod", "nods", 0, False),
    "shake_head": Gesture("shake your head", "shakes their head", 0, False),
    "shrug": Gesture("shrug", "shrugs", 0, False),
    "point_at": Gesture("point at {target}", "points at {target}", 1, True),
    "beckon": Gesture("beckon {target} over", "beckons {target} over", 1, True),
    "wave_off": Gesture("wave {target} off", "waves {target} off", 1, True),
    "hush": Gesture("put a finger to your lips", "puts a finger to their lips", 1, False),
    "empty_hands": Gesture("show your empty hands", "holds up empty hands", 2, False),
}

# What an observer sees when the action STARTS (perception fills the placeholders per holder).
SEEN: dict[str, str | None] = {
    "shoot_center_mass": "raises {item} toward {target}",
    "shoot_head": "takes careful aim at {target}'s head with {item}",
    "shoot_leg": "aims {item} low at {target}'s legs",
    "shove_toward_dead": "shoves {target} toward the dead",
    "strike_melee": "swings {item} at {target}",
    "strike_head": "brings {item} down at {target}'s head",
    "finish_downed": "stands over {target} with {item} raised",
    "punch": "throws a punch at {target}",
    "grapple": "grabs for {target}",
    "infected_grab": "lunges and grabs at {target}",
    "infected_bite": "sinks its teeth into {target}",
    "butcher_carcass": "cuts into {target} with a knife",
    "spit_into": "leans low over {item}",
    "spit_in_mouth": "bends over {target}'s sleeping face",
    "wash_self": "washes with {item}",
    "smear_gore": "smears the gore of {target} over themselves",
    "take_off_clothing": "takes off {item}",
    "change_into": "changes into {item}",
    "strip_clothing": "pulls {item} off {target}",
    "break_grip": "twists against {target}'s grip",
    "shove": "shoves {target}",
    "disarm": "grabs for {target}'s weapon",
    "pick_up_item": "reaches for {target}",
    "drop_item": "drops {item}",
    "give_item": "holds out {item} to {target}",
    "take_from_container": "reaches into {target}",
    "put_into_container": "puts {item} into {target}",
    "search_container": "searches {target}",
    "search_place": "starts searching the place",
    "equip_item": "takes out {item}",
    "holster_item": "puts away {item}",
    "reload_firearm": "reloads {item}",
    "throw_distraction": "throws {item} toward {destination}",
    "eat_food": "eats",
    "drink_water": "drinks",
    "move_to_anchor": "walks toward {destination}",
    "go_look": "goes to look toward {destination}",
    "sneak_to_anchor": "creeps toward {destination}",
    "run_to_anchor": "runs toward {destination}",
    "move_through_portal": "heads for {target}",
    "follow_body": "follows {target}",
    "shield_dependent": "moves to shield {target}",
    "leave_place": "heads for the way out",
    "flee_threat": "runs from {target}",
    "climb_obstacle": "climbs {target}",
    "take_cover": "takes cover at {destination}",
    "hide": "slips toward {destination}",
    "crouch": "crouches",
    "stand_up": "stands up",
    "go_prone": "drops flat",
    "open_portal": "reaches for {target}",
    "close_portal": "reaches for {target}",
    "lock_portal": "locks {target}",
    "unlock_portal": "unlocks {target}",
    "pick_lock": "works at the lock of {target}",
    "barricade_portal": "starts barricading {target}",
    "unbarricade_portal": "starts pulling the barricade off {target}",
    "force_portal": "throws a shoulder into {target}",
    "peek_portal": "looks through {target}",
    "speak": None,
    "calm_person": "talks to {target} slowly and steadily",
    "signal": "signals to {target}",
    "surrender": "raises empty hands",
    "apply_pressure": "presses on {target}'s wound",
    "bandage_wound": "bandages {target}",
    "apply_tourniquet": "ties a tourniquet on {target}",
    "suture_wound": "stitches {target}",
    "clean_wound": "cleans {target}'s wound",
    "sleep": "lies down to sleep",
    "rest": "sits down to rest",
    "observe_area": "stops and watches",
    "watch_target": "watches {target}",
    "watch_portal": "watches {target}",
    "wait_here": None,
    "guard_anchor": "takes up a guard at {destination}",
    "keep_working": None,
}

NOISE_TEXT: dict[str, str] = {
    "move_to_anchor": "footsteps", "move_through_portal": "footsteps", "follow_body": "footsteps",
    "leave_place": "footsteps", "flee": "running feet", "climb": "metal rattling",
    "open_portal": "a door opening", "close_portal": "a door closing", "lock_portal": "a lock turning",
    "unlock_portal": "a lock turning", "barricade_portal": "hammering and scraping",
    "unbarricade_portal": "boards being pulled away", "force_portal": "something slamming against a door",
    "peek_portal": "a faint creak", "pick_up": "something being picked up", "drop_item": "something dropping",
    "give_item": "a shuffle", "take_from": "rummaging", "put_into": "rummaging", "search_container": "rummaging",
    "search_place": "things being moved about", "equip": "a rustle", "holster": "a rustle",
    "reload": "the metallic clack of a gun being loaded", "strike_melee": "a blow landing", "shoot": "a gunshot",
    "grapple": "a scuffle", "break_grip": "a scuffle", "shove": "a scuffle", "disarm": "a scuffle",
    "take_cover": "a scramble", "hide": "a soft movement", "crouch": "a soft movement", "stand": "a soft movement",
    "go_prone": "a body hitting the floor", "speak": "a voice", "treat_wound": "a sharp breath",
    "apply_tourniquet": "a sharp breath", "eat": "eating", "drink": "drinking", "sleep": "a sigh",
    "rest": "a sigh", "continue_task": "someone working", "surrender": "something dropping",
    "throw_distraction": "something clattering", "click": "a dry click",
    "wash": "water splashing", "smear": "a wet slapping", "take_off": "a rustle of clothes",
    "change_into": "a rustle of clothes", "strip": "a rustle of clothes",
}


def register(effect_id: str) -> Callable[[EffectHandler], EffectHandler]:
    def deco(fn: EffectHandler) -> EffectHandler:
        if effect_id not in EFFECT_IDS:
            raise ValueError(f"unknown effect id {effect_id}")
        EFFECTS[effect_id] = fn
        return fn

    return deco


def land(tx: "Tx", rng: "Rng", intent: "Intent", land_at: int, ctx: EffectCtx) -> Landing:
    """Legality (EFF-02) then EFFECTS[def.effect]. Implement the handlers below this line (one
    @register per id); the resolver calls only this function."""
    raise NotImplementedError("P5")


def situation(tx: "Tx", intent: "Intent", land_at: int) -> int:
    """The situation modifier described above (-3..+3)."""
    raise NotImplementedError("P5")


def resistance(tx: "Tx", intent: "Intent", key: str | None, land_at: int) -> int:
    """The resistance for CheckSpec.resistance key described above (0 when key is None)."""
    raise NotImplementedError("P5")


def range_band(distance_m: float, effective_range_m: float) -> int:
    """<= 5 m 0, <= 15 m 1, <= 30 m 2, <= 60 m 3; beyond effective_range_m 5 (implemented)."""
    if distance_m > effective_range_m:
        return 5
    for limit, band in ((5, 0), (15, 1), (30, 2), (60, 3)):
        if distance_m <= limit:
            return band
    return 5


def land_ms(start_ms: int, est_duration_s: float) -> int:
    """start + ceil(seconds x 1000) (implemented; every duration rounds UP to the next ms)."""
    return start_ms + math.ceil(est_duration_s * 1000)
from ._impl_effects import land, situation, resistance  # noqa
