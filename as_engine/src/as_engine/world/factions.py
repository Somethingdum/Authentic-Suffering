"""What a faction does beyond its settlements and daily operations (P10): enclaves, councils, the
route watch and DECON. Rules FAC-01..06. Owner 'world.factions' (no table: it commits its own
record events and calls the owners). Source: Ghosts_6, the Major Faction Dossier (core faction
'ghosts'); docs/as/06_WORLD.md §2.

A faction record's ``behaviour`` block (contracts.content.FactionBehaviour) says which of these it
has; the Ghosts have all four. B = that block. Nothing here reads a mind (L1): a council decides by
code, from the record and the world, and people learn of it the way they learn of anything —
seeing, hearing, being told. rng stream 'factions'. DAY = 86_400_000 ms, HOUR = 3_600_000. Every
function that returns an Event has committed it (at and turn_index as given; writer
'world.factions' unless said otherwise). A faction GROUP = a groups row whose content_ref is the
faction's ref; its SEAT HOLDERS = its group_members rows whose role is a seat of the record's
leaders (Leader.seat), living (bodies.alive 1), by (the seat's position among the leaders, actor_id).

FAC-01 Enclaves (B.enclave; worldgen WG-18 places one, WG-23 / WG-27 build it). enclave(store,
  group_id) -> str | None: the settlement_id of the group's settlement when its record has an
  enclave block, else None. An enclave is SEALED: world.hordes HRD-08 never breaches it (the crowd
  presses the gate and nothing more), world.infected.populate never fills it (it is a settlement
  site), and while its settlements.lockdown is 1 nobody leaves it on an operation (world.worldmove
  OPS-01) — lockdown(...) below sets it.
  lockdown(tx, settlement_id, on, reason, at, turn_index, cause) -> Event | None: society.settlement.
  set_lockdown (STL-13) — the one door shut, or open again.
FAC-02 The council (B.council). The seats of B.council.seats meet every B.council.every_days days
  at B.council.hour — the first meeting on the first day d >= 1 with d % every_days == 0 — for
  B.council.hours hours, at the enclave's site (the council room anchor, else the site's first
  anchor by anchor_id).
  next_meeting(at, council) -> int: the first t > at with t = d x DAY + council.hour x HOUR, d >= 1,
    d % council.every_days == 0.
  ensure_timers(tx, at, turn_index) -> list[str]   (turn.timers.seed_world)
    Per faction group (by group_id) whose record has a council and whose enclave exists: no
    pending COUNCIL row for the group -> kernel.clock.schedule(tx, next_meeting(at, council),
    'COUNCIL', group_id, {'group_id': group_id, 'step': 'convene'}, None). Returns the queue ids.
  step(tx, rng, row, fired, turn_index) -> list[Event]   (the COUNCIL handler; at = row.due_at,
    cause = fired.event_id)
    'convene': present = the seat holders of B.council.seats outside the active area
      (turn.select.active_area around meta.pc_actor_id) and in no active operation, plus those
      already at the site; every present one not at the site MOVEs there (physical.space.move_event
      to the council anchor's point, cause the TIMER_FIRED); COUNCIL_MEETING {group_id,
      settlement_id, present: [ids], absent: [the other seat holders' ids]} (place_id = the site);
      then the council's business, in this order, each caused by the meeting: DECON (FAC-04);
      kernel.clock.schedule(tx, at + round(B.council.hours x HOUR), 'COUNCIL', group_id,
      {'group_id', 'step': 'adjourn', 'meeting': the COUNCIL_MEETING id}, the meeting id).
    'adjourn': COUNCIL_ADJOURNED {group_id, meeting} (cause the TIMER_FIRED); schedule the next
      'convene' at next_meeting(at, council).
    No seat holder alive -> the meeting is not held (no event) and the next one is scheduled.
  in_session(store, group_id, at) -> str | None: the id of the group's latest COUNCIL_MEETING at or
    before ``at`` with no COUNCIL_ADJOURNED naming it at or before ``at`` (the cheats and the
    developer panel read it: "in the middle of a meeting").
FAC-03 The route watch (B.route_watch; Ghosts_6: route-watch operators see movement before movement
  becomes a problem). sighted(tx, horde_id, at, turn_index, cause) -> list[Event]: world.hordes
  HRD-12 calls it right after a Mega Horde forms. Per faction group (by group_id) with route_watch
  and an enclave: ROUTE_WATCH_REPORT {group_id, horde_id, gateway_hub, eta_at} (gateway_hub = the
  hub of the region zone its road in leads to; eta_at from the horde's props) and, for every seat
  holder (in seat order), world.rumours.seed(tx, holder, gateway_hub, 'horde_coming', at,
  turn_index, the report's id, subject_type='place') — days before any bird flies (HRD-13 'birds'
  comes at 7 days out at most).
  passage(tx, horde_id, on, at, turn_index, cause) -> list[Event]: world.hordes HRD-14 calls it when
  a Mega Horde begins its FIRST region passage (on = True) and when it is gone (on = False): every
  enclave of a route_watch faction -> lockdown(tx, it, on, 'mega horde' | 'horde gone', ...).
FAC-04 DECON (B.decon; Ghosts_6: "If any Ghost is confirmed killed by human action, DECON
  retaliation triggers ... Full DECON requires Black Top Hat approval and typically Council
  awareness" — so the council orders it). At each 'convene', per DEATH event (by seq) committed
  after the group's previous COUNCIL_MEETING (every one before the first) whose body is a member of
  the group (a group_members row, any status): killer = the actor_id of the latest HARM event (by
  seq, at or before the DEATH) whose payload body_id is the dead body and whose actor is a body of
  kind 'human' that is not a member of the group; no such HARM, the killer dead, or a 'decon'
  operation of the group already active against that killer -> nothing. Else team(tx, rng, group,
  at, turn_index, meeting) and world.worldmove.launch(tx, group_id, 'decon', team, the enclave
  site, target(the killer's place), at, turn_index, the meeting id, target_id = killer).
  team(tx, rng, group_id, at, turn_index, cause) -> list[str]: B.decon.team people, one at a time
  (k = 0..): sex = 'female' when rng.chance(tx, 'factions', f"decon_sex:{cause}:{k}",
  B.decon.women_share) else 'male' (that sex has no adult left in the enclave's cohorts -> the
  other; neither -> the team stops there); society.population.materialise(tx, rng, settlement_id =
  the enclave, zone_id = its zone, band 'adult', sex, dossier = operator_dossier(rng, tx, group_id,
  k, sex, cause), place_id = the enclave site, at, turn_index, cause);
  then one MATERIALIZE (writer 'society.group') inserting their group_members rows {group_id,
  actor_id, role 'operator', standing 1, since at, status 'member'}. Returns their ids (a team of
  none launches nothing).
  operator_dossier(rng, tx, group_id, k, sex, cause) -> dict: world.worldgen.people.skeleton_dossier
  of a PersonSeed — name = given (the first canon names record's given names for ``sex``) and
  family, drawn on stream f"names:{enclave}" with purposes f"decon_given:{cause}:{k}" and
  f"decon_family:{cause}:{k}"; age = rng.range_int(tx, 'factions', f"decon_age:{cause}:{k}", 22,
  45); cohort from the age at the Fall (as WG-27); occupation = B.decon.occupation; skills
  {'firearms': 2, 'melee': 1, 'athletics': 1}; special = 4 + rng.range_int(..., f"decon_special:
  {cause}:{k}:{letter}", 0, 3) per letter; variant = rng.range_int(..., f"decon_variant:{cause}:
  {k}", 0, 999); the enclave's and the group's names — then id += f"_{k}_{cause[-6:]}",
  appearance.clothing_usual = B.decon.appearance, appearance.distinguishing_marks = ['a small smile
  stitched at the left chest'], social.memberships = [{faction: the record's ref, role 'operator',
  standing 1, since 'born inside'}].
FAC-05 Where the decon team goes (world.worldmove OPS-02 for kind 'decon'; the killer =
  operations.target_id): at 'arrive' the team goes where the killer IS now (world.hordes.target(its
  place)); the killer outside the active area -> physical.bodies.die(tx, rng, killer, at, cause,
  turn_index, cause='decon'), a TRACE 'mark' B.decon.mark at the killer's place (source = that
  DEATH), and the team returns ('return' as usual); the killer in the active area (the PC, or
  anyone the player is with) -> the team MOVEs into the killer's place and is on screen now: each
  member gets PLAN_CHANGE {actor_id, goal_text = B.decon.goal with {target} =
  mind.perception.describe(tx, member, killer), steps []} (writer 'mind.actor', updating plans and
  actors.goal_text) and the operation's step becomes 'hunt': every W.op_leg_h hours it checks —
  the killer dead, or every member dead or gone -> 'return' (the living come home); else it waits.
  A team member killed by the same hand is another dead Ghost: the next meeting sends another team
  (Ghosts_6: "Will not allow a dead Ghost to become an acceptable cost to the person responsible").
FAC-06 Nothing here makes a Ghost appear where nobody could be: teams are materialised at the
  enclave (from its counted people, CONSERVE-04) and walk there like any operation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.rng import Rng
    from ..kernel.store import Store, Tx


def enclave(store: "Store | Tx", group_id: str) -> str | None:
    raise NotImplementedError("P10")


def lockdown(tx: "Tx", settlement_id: str, on: bool, reason: str, at: int, turn_index: int,
             cause: str | None) -> "Event | None":
    raise NotImplementedError("P10")


def next_meeting(at: int, council) -> int:
    raise NotImplementedError("P10")


def ensure_timers(tx: "Tx", at: int, turn_index: int) -> list[str]:
    raise NotImplementedError("P10")


def step(tx: "Tx", rng: "Rng", row: dict, fired: "Event", turn_index: int) -> list["Event"]:
    raise NotImplementedError("P10")


def in_session(store: "Store | Tx", group_id: str, at: int) -> str | None:
    raise NotImplementedError("P10")


def sighted(tx: "Tx", horde_id: str, at: int, turn_index: int, cause: str | None) -> list["Event"]:
    raise NotImplementedError("P10")


def passage(tx: "Tx", horde_id: str, on: bool, at: int, turn_index: int, cause: str | None) -> list["Event"]:
    raise NotImplementedError("P10")


def team(tx: "Tx", rng: "Rng", group_id: str, at: int, turn_index: int, cause: str | None) -> list[str]:
    raise NotImplementedError("P10")


def operator_dossier(rng: "Rng", tx: "Tx", group_id: str, k: int, sex: str, cause: str | None) -> dict:
    raise NotImplementedError("P10")
