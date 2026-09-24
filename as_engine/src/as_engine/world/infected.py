"""Infected ecology (P10). Canon: Lore v1.0 §2-4, CMG §42. Rules INF-01..12. Owner 'world.infected'
(infected_state). docs/as/06_WORLD.md §5. R = RulesConfig().infected; types and states are canon
records (InfectedTypeDef by id, InfectedStateDef by id). Every function that returns an Event has
committed it (writer 'world.infected' unless said otherwise; at and turn_index as given). rng stream
'infected' (quirks: 'quirks').

The baseline infected (Shambler, Crawler, Runner) are bodies of kind 'infected' with an
infected_state row and NO actors row: code drives them, always, the same way on-screen and off
(COLD). Lurkers are alive, have dossiers and think like people (they are actors of body kind
'lurker'); nothing here drives them.
  INF-01 Types and states are orthogonal: states is a JSON list over dormant / starved / overfed /
    injured; the type is infected_state.type_id.
  INF-02 Senses: hearing = the type's hearing_threshold_db plus every state's
    hearing_threshold_delta_db (threshold()); sight = sees().
  INF-03 Energy: every step costs R.energy_per_step[type] (1 when unlisted); at 0 the body goes
    dormant (motionless) and forgets its target; a stimulus reboots it (attract); a bite that lands
    feeds it (feed). energy < R.starved_below -> 'starved'; > R.overfed_above -> 'overfed'.
  INF-04 False death and reanimation are physical.bodies' (a false-dead body is 'unconscious' and
    takes no steps); the dead that RISE are this module's (rise).
  INF-05 An infected never targets an infected body.
  INF-06 A body with a 'lurker_deep' infections row past its first stage is never a target.
  INF-07 A body with a 'wet' infection at least R.wet_ignore_after_h hours old is not SEEN as prey
    (sound still draws infected to where it is).
  INF-08 Quirks are seeded per body (seed_quirks, stream 'quirks'): the same seed gives the same
    quirks to the same body.
  INF-09 Noise steers: a sound above a body's threshold makes it walk toward the sound's place
    (attract, called by action.propagate).
  INF-10 Lifecycle: a Runner becomes a Shambler or a Crawler after R.runner_degrade_days; never the
    reverse (CMG §42.17).
  INF-11 Infected in a place come from its zone's danger the first time a person arrives (populate).
  INF-12 The same rules run everywhere: an INFECTED_STEP timer moves a body one leg at a time, in a
    turn's window or off-screen alike.

active(store, body_id) -> bool: bodies.kind 'infected', alive 1, core_intact 1, awareness not
  'unconscious' (false-dead), an infected_state row, and 'dormant' not in states.
threshold(store, body_id) -> float; speed(store, body_id) -> float: the type's speed_m_s x every
  state's speed_mult (0 when dormant).
sees(store, body_id, target_id, at) -> bool   (INF-02, INF-05..07)
  False unless the target is a living, conscious body in the same place, not of kind 'infected', not
  excluded by INF-06 / INF-07. Then the type's senses: distance (straight line) <= vision_range_m and
  vision_mode 'motion_contrast' -> the target MOVEd or started an action (MOVE / ACTION_START with
  actor_id = the target) in (at - R.motion_window_s s, at]; 'shape' and 'full' -> True; 'thermal' ->
  the place's light_level <= 1 or it is indoor.

attract(tx, body_id, target_id, at, cause_event_id, turn_index, *, reason) -> Event | None   (INF-03/09)
  ``target_id`` is a body id or a place id; reason in 'noise' | 'sight' | 'opening' | 'feed'. None
  (nothing committed) when: the body is not infected, dead, core-destroyed or false-dead; the target
  is an infected body (INF-05) or excluded (INF-06); or the body already hunts a living body in its own
  place and the new target is a place (prey in reach beats a noise). Otherwise INFECTED_DRIFT
  {body_id, target_id, target_kind: 'body' | 'place', reason, woke: 'dormant' was in states}
  (actor_id = body_id, cause as given) updating infected_state target_id and states without
  'dormant'; then, when no INFECTED_STEP row is pending for the body (kernel.clock.pending_for),
  kernel.clock.schedule(tx, at + round(R.step_min_s x 1000), 'INFECTED_STEP', body_id, {'body_id':
  body_id, 'leg': None}, the drift id).

step(tx, rng, row, fired, turn_index) -> list[Event]   (the INFECTED_STEP handler, INF-12)
  b = payload.body_id, at = row.due_at, cause = fired. Not active -> [] (no new row).
  1 Arrive: payload.leg {to_place, x_m, y_m, portal_id} (None -> skip): the portal (when there is
    one) must be open and admit the body (physical.space.admits) -> commit physical.space.move_event(
    tx, b, to_place, None, x_m, y_m, at, cause, turn_index); otherwise NOISE {source_db: R.bang_db,
    kind: 'banging', text: 'something heavy bangs against the door', place_id: b's place, x_m, y_m}
    (writer 'action.propagate', actor_id b) and no move.
  2 Energy: energy -= R.energy_per_step[type]; energy <= 0 -> energy 0, states + 'dormant',
    target None; states 'starved' / 'overfed' recomputed from energy. INFECTED_STATE {body_id,
    changes, before} (updating infected_state) when anything changed. Dormant -> stop (no new row).
  3 Decide (target = infected_state.target_id):
      none -> stop (it stands where it is until something draws it);
      a body that is dead, gone, infected or excluded -> target None (INFECTED_STATE), stop;
      a body in b's place, within 1.5 m -> a reflex Intent (source 'reflex', lod COLD, bound = the
        core affordance 'infected_bite' when b grips it (physical.bodies.grips_on), else
        'infected_grab', target = it) resolved with action.resolve.resolve_wave(tx, rng, [intent], at,
        turn_index, horizon_ms = at + 60 000); delay = max(R.step_min_s, the def's base_s);
      a body in b's place, farther -> leg = {to_place: b's place, x_m / y_m = the target's point,
        portal_id None}; delay = distance / speed(b) + 0.5 s;
      a body elsewhere or a place: dest = its place; b already in dest and it is a place (it has
        arrived) -> the first living body there (by body_id) that sees(b, it) holds becomes the
        target (attract, reason 'sight' — it schedules the next step), else target None; stop; else path = physical.space.path(tx, b, dest) (open ways only), and when
        None physical.space.path(..., allow_closed=True) (it will stand at the door and bang); no
        path at all -> target None, stop; the first leg: to_place = that leg's place, x/y =
        physical.space.portal_point(tx, leg.portal_id, leg.place_id), portal_id = leg.portal_id;
        delay = (distance from b to the portal point on its side) / speed(b) + 1 s.
  4 kernel.clock.schedule(tx, at + round(max(R.step_min_s, delay) x 1000), 'INFECTED_STEP', b,
    {'body_id': b, 'leg': leg or None}, the last event committed here or fired).
  Returns every event committed, in seq order.

feed(tx, body_id, at, cause_event_id, turn_index) -> Event | None   (a bite landed; action.effects)
  energy = min(100, energy + R.energy_per_feed); states recomputed; INFECTED_STATE; None when not
  infected.

seed_quirks(tx, rng, body_id, type_id) -> list[str]   (INF-08)
  pool = canon quirk records whose applies_to contains type_id, by id; n = rng.range_int(tx,
  'quirks', f"count:{body_id}", 0, R.quirks_max); n draws without replacement, each rng.weighted
  over the rest by seed_weight (purpose f"quirk:{body_id}:{k}"). Returns the ids in draw order.

spawn(tx, rng, place_id, type_id, at, turn_index, cause_event_id, *, dormant=False, x_m=None, y_m=None,
      origin='materialize') -> str
  physical.bodies.create(kind 'infected', sex None, age_years None, height_cm 170, mass_kg 65,
  special = {letter: (lo + hi) // 2} of the type, origin, awareness 'awake', posture 'standing');
  x / y given, else x = rng.range_int(tx, 'infected', f"x:{body}", 1, max(1, int(width_m) - 1)) and y
  likewise over depth_m; physical.space.place_body(...); MATERIALIZE {body_id, type_id} (writer
  'world.infected') inserting infected_state {body_id, type_id, states ['dormant'] when dormant else
  [], energy R.energy_start, quirks seed_quirks(...), target_id NULL, lurker_clan NULL, risen_from
  NULL, since = at, degrade_at = at + rng.range_int(tx, 'infected', f"degrade:{body}", lo, hi) x DAY
  for a Runner (lo, hi = R.runner_degrade_days), else NULL}. Returns the body id.

populate(tx, rng, place_id, at, turn_index, cause_event_id) -> list[str]   (INF-11)
  props.populated is true -> []. The place is a settlement's place, inside one (its parent is), or
  a zone hub with a settlement in the zone -> only physical.space.change_place(props {populated:
  true}, reason 'populated'), []. Otherwise danger = the zones.danger of the place's zone (a room:
  its building's); f = R.place_factor[the place's kind]; for key, type in (('shambler',
  SHAMBLER), ('runner', RUNNER), ('crawler', CRAWLER)): n = min(R.populate_max, floor(danger[key] x
  f / 3) + (1 when rng.chance(tx, 'infected', f"extra:{place_id}:{key}", danger[key] / 20))); on a
  street add floor(danger['horde'] x f / 4) to the shamblers (capped the same); each body: spawn(...,
  dormant = rng.chance(..., f"dormant:{place_id}:{key}:{k}", 0.5)). Then change_place(props
  {populated: true}). Returns the new body ids in spawn order.

rise(tx, rng, row, fired, turn_index) -> list[Event]   (the REANIMATION handler for corpses, INF-04)
  corpse = payload.body_id, pathway = payload.pathway. Nothing (return []) when the corpse is not a
  dead human, has no positions row any more, or has since taken an unhealed catastrophic head or
  neck wound. type = rng.choice(tx, 'infected', f"rise:{corpse}:type", the canon pathway's rise_as).
  new = physical.bodies.rise(tx, corpse, type, at, fired.event_id, turn_index);
  physical.space.place_body(tx, new, the corpse's place / anchor / point, replaces = corpse); every
  item the corpse holds (holder_body = corpse, by item_id) -> physical.objects.transfer to new, same
  slot; MATERIALIZE inserting infected_state as spawn does, with risen_from = corpse; then attract(
  new, every living non-infected body it sees(...) in that place — the first by id, reason 'sight').
  (mind.perception.word_for gives it the words "what was left of <name>" for anyone who knew the
  dead.)

day(tx, rng, at, turn_index, cause_event_id) -> list[Event]   (world.worldmove.day calls it)
  Every body with an infected_state row (by body_id): dormant -> energy + R.idle_recover_per_day
  (cap 100); a Runner whose degrade_at <= at -> type_id = rng.choice(tx, 'infected',
  f"degrade:{body}:type", [SHAMBLER, CRAWLER]) and degrade_at NULL (INF-10). One INFECTED_STATE per
  body that changed.

INFECTED_STATE {body_id, changes, before} updates infected_state columns states / energy /
target_id / type_id / degrade_at only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.rng import Rng
    from ..kernel.store import Store, Tx

SHAMBLER = "ZOMBIE_ARCHETYPE_SHAMBLER01"
CRAWLER = "ZOMBIE_ARCHETYPE_CRAWLER01"
RUNNER = "ZOMBIE_VARIANT_ID_RUNNER01"
LURKER = "ZOMBIE_VARIANT_ID_LURKER01"


def active(store: "Store | Tx", body_id: str) -> bool:
    raise NotImplementedError("P10")


def threshold(store: "Store | Tx", body_id: str) -> float:
    raise NotImplementedError("P10")


def speed(store: "Store | Tx", body_id: str) -> float:
    raise NotImplementedError("P10")


def sees(store: "Store | Tx", body_id: str, target_id: str, at: int) -> bool:
    raise NotImplementedError("P10")


def attract(tx: "Tx", body_id: str, target_id: str, at: int, cause_event_id: str | None, turn_index: int, *,
            reason: str) -> "Event | None":
    raise NotImplementedError("P10")


def step(tx: "Tx", rng: "Rng", row: dict, fired: "Event", turn_index: int) -> list["Event"]:
    raise NotImplementedError("P10")


def feed(tx: "Tx", body_id: str, at: int, cause_event_id: str | None, turn_index: int) -> "Event | None":
    raise NotImplementedError("P10")


def seed_quirks(tx: "Tx", rng: "Rng", body_id: str, type_id: str) -> list[str]:
    raise NotImplementedError("P10")


def spawn(tx: "Tx", rng: "Rng", place_id: str, type_id: str, at: int, turn_index: int, cause_event_id: str | None, *,
          dormant: bool = False, x_m: float | None = None, y_m: float | None = None, origin: str = "materialize") -> str:
    raise NotImplementedError("P10")


def populate(tx: "Tx", rng: "Rng", place_id: str, at: int, turn_index: int, cause_event_id: str | None) -> list[str]:
    raise NotImplementedError("P10")


def rise(tx: "Tx", rng: "Rng", row: dict, fired: "Event", turn_index: int) -> list["Event"]:
    raise NotImplementedError("P10")


def day(tx: "Tx", rng: "Rng", at: int, turn_index: int, cause_event_id: str | None) -> list["Event"]:
    raise NotImplementedError("P10")
