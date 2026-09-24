"""Off-screen motion (P10). Owner 'world.worldmove' (operations). Rules WORLD-02..06, OPS-01..07.
docs/as/06_WORLD.md §3. The world moves without the player: people go out for supplies, walk
patrols, trade, raid and leave; they are hurt, go hungry and die of what happens to them; and what
they do leaves the marks it leaves (WORLD-03). Code only, COLD, no model call. W =
RulesConfig().world; rng stream 'offscreen'. Every function that returns an Event has committed it
(at and turn_index as given).

WORLD-02 Nothing here ticks by itself: WORLD_DAY (daily at W.world_hour) and OPERATION_STEP rows
  are event_queue rows (background types, kernel.clock) that turn.timers.seed_world starts and
  turn.timers fires, in a turn's window or the off-screen step alike. A run without a world_params
  row (every hand-made scenario) gets none of it.
WORLD-04 The active area: off-screen code never kills, moves or sends away a body that stands in
  turn.select.active_area(tx, meta.pc_actor_id, turn_index) — what the player could see happen is
  simulated by the turn, not decided here. (Infected are the exception: their steps are the same
  physics on-screen and off, world.infected INF-12.)
WORLD-05 Named characters are not protected during play: an off-screen death can take anyone the
  player is not with.
WORLD-06 The narrator never writes 'while you were gone' (narration lint); the world shows it.

ensure_timers(tx, at, turn_index) -> list[str]: no pending WORLD_DAY row -> kernel.clock.schedule(
  tx, society.settlement.next_hour(at, W.world_hour), 'WORLD_DAY', None, {}, None).

day(tx, rng, row, fired, turn_index) -> list[Event]   (the WORLD_DAY handler)
  at = row.due_at; d = at // DAY; WD = WORLD_DAY {day: d} (writer 'world.worldmove', cause fired).
  Everything below has cause WD, in this order:
  1 Weather: rng.chance(tx, 'offscreen', f"weather:{d}", W.weather_change_chance) -> kind =
    rng.weighted(..., f"weather_kind:{d}", weather_weights(values)) and wind = rng.range_int(...,
    f"wind:{d}", 1, 3) for 'wind' / 'storm' else 0 -> WEATHER_CHANGE {weather, wind_level} (writer
    'kernel.clock') updating world_clock — only when it differs from the current weather. Then
    world.traces.washout(tx, at, turn_index, WD) (rain, storm or snow erase exposed tracks and
    blood).
  2 The unseen dead (C01 — there is no death lottery: people die of what happens to them, wounds
    and illness running their course and thirst and hunger in physical.bodies.progress (every turn
    and every off-screen step), what meets them on an operation (OPS-03), raids, the infected, and
    — for the unnamed — privation (society.settlement STL-03 step 2b)): every DEATH event (by
    seq) committed after the previous WORLD_DAY event (every one before the first), of a body of
    kind 'human' that has an actors row and whose positions place is outside the active area ->
    OFFSCREEN_DEATH {body_id, place_id, cause: the DEATH payload's cause} (actor_id = the body,
    place_id, cause_event_id = that DEATH event) — the world's notice that nobody on screen saw it
    (core CAS-013: a stain where it happened, and talk among those who would hear of it; CAS-007
    already turned the DEATH into grief and a vacancy).
  3 Operations (OPS-01): plan_operations(tx, rng, at, turn_index, WD).
  4 Departures (OPS-06): depart(tx, rng, at, turn_index, WD).
  5 world.decay.day(tx, rng, at, turn_index, WD) (physical wear); 6 world.infected.day(tx, rng, at,
    turn_index, WD), then world.hordes.day(tx, rng, at, turn_index, WD) (the dead in numbers:
    lifecycle, drifting crowds, the Mega Horde).
  7 kernel.clock.schedule(tx, at + DAY, 'WORLD_DAY', None, {}, WD).
  Returns every event committed, in seq order.
weather_weights(values) -> list[tuple[str, float]]   (implemented below)

OPS-01 plan_operations(tx, rng, at, turn_index, cause) -> list[Event]
  At most one new operation per settlement per day, and one raid per hostile group. Per settlement
  (by id) whose site is outside the active area, with a governing group, and not in lockdown
  (settlements.lockdown 0; P10, world.factions FAC-01: a sealed enclave sends nobody out): crew =
  its named members (group_members status 'member') who are alive, able (society.work.able for
  'watcher'), not human-controlled, not seat holders (P10: role = the ``seat`` of one of the
  group's record's leaders — a council does not go scavenging), outside the active area and in
  no active operation, sorted by (their daily work hours, id). For kind in ('scavenge', 'patrol',
  'trade_run'): chance = W.op_chance[kind] x
  (2 when the settlement has a shortage, for scavenge) x (social_order / 5, for patrol) x
  (faction_relations / 5, for trade_run; 0 without another settlement); the first kind whose
  rng.chance(tx, 'offscreen', f"op:{settlement}:{kind}:{d}", chance) holds starts, with n =
  rng.range_int(..., f"party:{settlement}:{d}", *W.op_party) people (fewer when the crew is smaller;
  none -> no operation). Destination: scavenge -> rng.choice over building sites (not settlement
  sites) of other zones, else of any zone; patrol -> the far hub of a route touching the
  settlement's zone (rng.choice); trade_run -> rng.choice over the other settlements' sites.
  (P10: an exterior zone is never a destination: no site stands there and no patrol walks to one.)
  Per
  hostile group (by id) with 2+ named living members outside the active area: rng.chance(...,
  f"raid:{group}:{d}", W.op_chance['raid'] x hostile_human / 5) -> a raid on rng.choice(the
  settlements) by all of them. A new operation is launch(...) (OPS-08).
OPS-08 launch(tx, group_id, kind, participants, origin, destination, at, turn_index, cause, *,
       target_id=None) -> str   (OPS-01's daily plan and world.factions FAC-04 DECON)
  op_id = tx.mint('ops'); FACTION_OPERATION {op_id, group_id, kind, participants, destination,
  status: 'active', step: 'depart'} (plus target_id when given) inserting operations {op_id,
  group_id, kind, status 'active', route [origin place, destination place], participants,
  next_due_at = at + W.op_leg_h h, outcome NULL, target_id}; every participant MOVEs
  (physical.space.move_event, cause the FACTION_OPERATION) to its zone's hub (leaving);
  kernel.clock.schedule(next_due_at, 'OPERATION_STEP', op_id, {'op_id': op_id, 'step': 'arrive'},
  the FACTION_OPERATION id). Returns op_id.
OPS-02 step(tx, rng, row, fired, turn_index) -> list[Event]   (the OPERATION_STEP handler)
  The operation (status 'active'; otherwise []). movers = participants alive and outside the active
  area (those in it are on-screen now: the turn moves them, they drop out of the operation's moves).
  'arrive': movers MOVE to the destination (world.worldmove.on_arrival for each); outcome(...);
    the hurt are packed (OPS-07); FACTION_OPERATION {op_id, step: 'arrive', outcome} updating
    operations.outcome and next_due_at = at + W.op_dwell_h h (+ W.op_leg_h h instead when anyone
    was packed); schedule 'return'.
  'return': movers MOVE to the origin; resolve the stores (below); the hurt are sutured (OPS-07);
    FACTION_OPERATION {op_id, step: 'return', status: 'done'} updating status 'done', next_due_at
    NULL.
  Kind 'decon' (P10, world.factions FAC-05) replaces 'arrive' with: the killer = operations.
    target_id; dest = world.hordes.target(the killer's place); the killer outside the active area
    -> movers MOVE to dest, physical.bodies.die(tx, rng, killer, at, the step's event, turn_index,
    cause='decon'), TRACE 'mark' (the faction's decon.mark) at dest (source = that DEATH),
    FACTION_OPERATION {op_id, step: 'arrive', outcome: {'killed': killer}} and 'return' at at +
    W.op_leg_h h; the killer in the active area -> movers MOVE to dest (on screen now), each gets
    the PLAN_CHANGE of FAC-05, FACTION_OPERATION {op_id, step: 'hunt'} and 'hunt' at at +
    W.op_leg_h h; the killer dead or gone -> 'return' at once. 'hunt': the killer dead, or no
    participant alive -> FACTION_OPERATION {op_id, step: 'hunt', outcome: {'killer_dead': bool}}
    and 'return' now; else 'hunt' again at at + W.op_leg_h h. A decon party finds no haul and
    leaves no other trace; its OPS-03 harm roll does not apply (it moves in a van).
OPS-03 outcome(...) at the destination, stream 'offscreen', purposes f"{op}:<what>":
  every mover: rng.chance(world.hordes.density(the destination's zone) / 20) (P10: how thick the
  district's dead actually are — a cleared district is safe) -> physical.bodies.apply_harm (a
  'minor' or 'significant' laceration on a CENTRE_MASS anatomy, weighted; cause the arrive event).
  scavenge: found = rng.chance(0.6); when the destination is discovered and holds loose items, up to
  3 of them (by item_id) are transferred to the movers' packs (physical.objects.transfer) and a
  TRACE 'missing_stock' "Shelves pulled out; whatever was here is gone." is left; a TRACE 'tracks'
  "Boot prints in the dust, a few people, coming and going." always; found adds {food: 2..8 x
  movers, water: 2..8 x movers} to the outcome's haul.
  patrol: a TRACE 'tracks' on the way ("Boot prints in a loose line, walking a route.").
  trade_run: the haul is a swap: 10 % (rounded) of the origin's most plentiful of food / water
  given for the same amount of the other (both settlements' stores change on 'return', reason
  'trade'); TRADE {op_id, from, to, gave, got}; a TRACE 'tracks'.
  raid (RAID {op_id, group_id, settlement_id, success}): success = rng.chance(0.5 + (hostile_human -
  target defences) / 20, clamped 0.1..0.9); success -> the target loses 10..25 % (rng) of food and
  water (society.settlement.receive, reason 'raid'), morale -1 (society.settlement.adjust), TRACEs
  'damage' "Broken boards and a forced door." and 'blood' at the target site, and the target's
  group gains tension +20 toward the raiders (society.group.adjust_tension); failure -> one raider
  takes a 'significant' gunshot wound and a TRACE 'blood'.
  On 'return' the haul goes into the origin settlement's stores (society.settlement.receive, reason
  'scavenged' / 'trade').
OPS-07 The hurt are tended (C01: a wound kills when nobody could stop it, not because the party was
  off-screen). Right after outcome(...) at 'arrive': per mover (by id), per unhealed wound of theirs
  (by wound_id) that is not minor and still bleeds (physical.bodies.effective_bleed > 0):
  physical.bodies.treat(tx, mover, wound, 'packing', by_actor = the first other living mover by
  id, else the mover, at, cause, turn_index). When anyone was packed the party heads home now:
  the 'return' step is due at at + W.op_leg_h h instead of at + W.op_dwell_h h (the haul is what
  outcome() found). On 'return', after the MOVEs and the haul: per mover and per wound as above
  whose severity is 'significant' (a suture holds only minor and significant wounds, and a minor
  one clots by itself), while the origin settlement's stores hold medicine >= 1:
  society.settlement.receive(tx, s, {'medicine': -1}, 'treatment', at, turn_index, cause) and
  treat(..., 'suture', by_actor as for packing, ...). Without medicine the wound stays packed and
  bleeds slowly; a severe or catastrophic wound cannot be sutured. physical.bodies.progress
  decides the rest.
OPS-04 WORLD-03 (fidelity C11): evidence comes from what happened. An operation leaves the traces
  its own steps make (OPS-03) and nothing else; no share of off-screen events is required to leave
  one, and no clue is guaranteed to last (tracks fade and wash out, TRACE-02 / TRACE-06).
OPS-05 on_arrival(tx, rng, body_id, place_id, at, cause_event_id, turn_index) -> list[Event]
  (called after a MOVE into a new place by action.effects, society.routine, this module and
  world.worldgen; not for infected bodies, and not in a run without a world_params row — every
  hand-made scenario keeps its places exactly as written — [].) A building place not yet generated ->
  physical.space.discover_layout(...), and when it is not held a TRACE 'damage' "Old damage: this
  place was picked over long ago." in its entrance room (the archetype's entrance_room). Then
  world.infected.populate(tx, rng, place_id, ...). Returns every event committed.
OPS-06 depart(tx, rng, at, turn_index, cause) -> list[Event]   (the loyalty plan acted on)
  Per actor (by id) with an open loop of kind 'plan' whose text starts with "Leave " and whose
  created_at <= at - W.defect_after_days x DAY, not human-controlled, alive and outside the active
  area, whose group (the group named in the loop: group_members of the actor with status 'member')
  still has society.group.defection_pressure >= the dossier's motive.risk_threshold: DEFECTION
  {actor_id, group_id, loop_id} (writer 'society.group', actor_id) updating group_members status
  'departed'; society.household.apply_change(..., 'member_left', ...) for their household;
  for each of their work_assignments rows (key order) ROLE_RELEASED {workplace_id, role, actor_id,
  shift_start_hh, covering_for, reason: 'left'} (writer 'society.work') deleting it, then
  society.settlement.add_vacancy(...) for that post; mind.mind.close_loop(tx, the loop, 'fulfilled',
  the DEFECTION id, at, turn_index); they MOVE to the hub of the region zone farthest (by route
  hops, ties by zone id) from their settlement's zone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.rng import Rng
    from ..kernel.store import Tx


def weather_weights(values: dict) -> list[tuple[str, float]]:
    """Weather odds from the world's A block (implemented; 06_WORLD.md §3)."""
    heat, wet = int(values["climate_heat"]), int(values["climate_moisture"])
    vis, unstable = int(values["atmo_visibility"]), int(values["instability"])
    cold = heat <= 3
    return [("clear", 4.0), ("overcast", 3.0), ("rain", 0.0 if cold else 2.0 * wet / 5),
            ("storm", 0.5 * wet / 5 * unstable / 5), ("fog", (10 - vis) / 5), ("wind", 1.0),
            ("heat", 2.0 if heat >= 8 else 0.0), ("snow", 2.0 if cold else 0.0)]


def ensure_timers(tx: "Tx", at: int, turn_index: int) -> list[str]:
    raise NotImplementedError("P10")


def day(tx: "Tx", rng: "Rng", row: dict, fired: "Event", turn_index: int) -> list["Event"]:
    raise NotImplementedError("P10")


def plan_operations(tx: "Tx", rng: "Rng", at: int, turn_index: int, cause_event_id: str | None) -> list["Event"]:
    raise NotImplementedError("P10")


def step(tx: "Tx", rng: "Rng", row: dict, fired: "Event", turn_index: int) -> list["Event"]:
    raise NotImplementedError("P10")


def on_arrival(tx: "Tx", rng: "Rng", body_id: str, place_id: str, at: int, cause_event_id: str | None,
               turn_index: int) -> list["Event"]:
    raise NotImplementedError("P10")


def depart(tx: "Tx", rng: "Rng", at: int, turn_index: int, cause_event_id: str | None) -> list["Event"]:
    raise NotImplementedError("P10")


def launch(tx: "Tx", group_id: str, kind: str, participants: list[str], origin: str, destination: str, at: int,
           turn_index: int, cause: str | None, *, target_id: str | None = None) -> str:
    raise NotImplementedError("P10")
