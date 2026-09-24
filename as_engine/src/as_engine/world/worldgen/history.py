"""WG2 — what happened: the powers, the settlements they built, and the causal history that explains
them (P10). Rules WG-18..21, WORLD-01, WG-31, WG-32. docs/as/06_WORLD.md §1.3.
Code decides the facts (rng stream 'worldgen:history'); the model only writes the words
(WORLDGEN_HISTORY). WG3-WG5 then build what this plan says exists — the powers and settlements exist
BECAUSE of their history (WORLD-01), never the other way round.

values = params.flat_values(params); dsf = params.days_since_fall; names = the family names of the
first canon names record by id.

WG-18 plan_polity(rng, tx, params, placement, region, canon) -> PolityPlan
  Ids are minted here (groups 'grp', settlements 'stl') so history can name them before WG3/WG4
  write their rows.
  1 Factions: E = placement.eligible_factions(canon, values); k = min(len(E), 1 + faction_density // 4).
    The placement's faction (when there is one) first, then the rest of E in ref order, up to k.
    presence: the placement's faction keeps placement.faction_presence; each other: 'dominant' when
    faction_density >= 6 and faction_fragmentation <= 4 and no planned faction is dominant yet, else
    'active' when faction_density >= 3, else 'peripheral'. name = the record's name.
    P10 — then every ENCLAVE faction (placement.enclave_factions(canon, values), ref order; world.
    factions FAC-01) is planned too, after the k (it takes no one's place), presence 'active'.
  2 Procedural groups: g = max(0, faction_density // 3 - k); when placement.entity_type is 'group',
    the PC's group is the first of them (descriptor = placement.group_descriptor) and g = max(g, 1).
    Every other one: descriptor = placement.descriptor(rng, tx, hostile=False). Hostile groups:
    1 when hostile_human >= 5, 2 when >= 8, 0 otherwise; descriptor(..., hostile=True). Every
    procedural group's name = f"The {family} {noun}" (rng.choice of names, purpose f"group_family:{n}",
    and of atlas.GROUP_NOUNS, purpose f"group_noun:{n}", n counting procedural groups from 0).
  3 Settlements: one per planned group that is not hostile and is not a peripheral faction, in plan
    order; none at all -> one more procedural group (as in 2) and its settlement. Zones: the
    settlement of the PC's entity (placement faction or group) is in the start zone; the others take
    the other zones in index order, cycling (the start zone last when every zone has one). Site: in
    that zone, the building site whose archetype kind comes first in atlas.SETTLEMENT_SITE_KINDS
    (ties by place id) and is not yet a site; none -> the zone's hub. name = f"{zone name} {suffix}"
    (suffix: the first atlas.SETTLEMENT_SUFFIX entry whose key >= social_order), with f" ({group
    name})" appended when that name is taken. population = rng.range_int(18, 30, purpose
    f"population:{s}") + 6 x (2 dominant, 1 active, 0 otherwise).
    P10 — an enclave faction's settlement takes no turn in that zone cycle: its zone is the first
    region zone (index order) whose kind is the earliest of enclave.zone_kinds that any region zone
    has (none -> the last region zone); its site is the ENCLAVE PLACE written here (a new place id
    minted for it): one PLACE_DISCOVERED {zone_id, places: [site], source: 'worldgen'} (writer
    'physical.space', origin 'worldgen') inserting the place {kind 'tunnel', name = enclave.name,
    zone_id, parent_id NULL, width 200, depth 100, indoor 1, material 'concrete', light 3,
    ambient_db 40, layout_generated 1, held 1, props {'enclave': the faction ref, 'description':
    enclave.description}}, the anchors 'the intake crown' (feature, x 5, y 50) and 'the council
    room' (feature, x 150, y 50) (capacity 4, cover 0, concealment 0), and one portal zone hub <->
    site {kind 'door', name enclave.gate, is_open 0, is_locked 1, lock_quality 4, barricade 0,
    aperture 400 x 400, seal_db 45, anchor_a NULL, anchor_b = the intake crown}; name =
    enclave.name; population = rng.range_int(*enclave.population, purpose f"population:{s}"). It
    is never the HOME settlement (no character is placed inside one).
  4 Home zones: a settlement's group -> its settlement's zone; a hostile group -> the first zone of
    kind 'highway', else 'industrial', else the last zone; a peripheral faction -> None.
  PolityPlan(groups: [PlannedGroup(group_id, kind 'faction'|'group', name, content_ref, descriptor,
  presence, hostile, is_pc_entity, home_zone_id)], settlements: [PlannedSettlement(settlement_id,
  group_id, zone_id, site_id, name, population)]).

WG-19 skeleton(rng, tx, params, plan, region, tier) -> list[PlannedEvent]
  PlannedEvent(key, day, kind, subject_ids, cause_key, text). Mandatory events, in this order:
    the Fall: 'disaster', day 0, subjects [start zone id], zone = the start zone;
    per D-block resource food, water, ammo, fuel, meds whose value <= 3: 'epidemic' for meds, else
      'infrastructure_collapse'; day = rng.range_int(1, max(1, dsf // 3)); zone = rng.choice(zones);
      cause the Fall; subjects [zone id];
    per planned group, in plan order: a settlement's group -> 'founding' (zone = its settlement's
      zone, subjects [group_id, settlement_id], day = rng.range_int(max(1, dsf // 10), max(1, dsf - 1)));
      a hostile group -> 'battle' against rng.choice(the settlement groups) (subjects [hostile, that
      group], 'massacre' with subjects [hostile] when there is none); a peripheral faction ->
      'discovery' (subjects [group], zone = rng.choice(zones)); these days are drawn like founding;
      cause the Fall.
  Fill: while fewer than T['history_events'] events: kind = rng.choice(atlas.HISTORY_KINDS_FILL,
    without 'massacre' when atrocity_capacity < 6); day = rng.range_int(1, max(1, dsf - 1)); a =
    rng.choice(groups); b = rng.choice(the other groups) for 'battle' and 'betrayal' (a single group
    -> the kind becomes 'schism'); zone = rng.choice(zones); cause: with rng.chance(0.5) the key of
    rng.choice(the events already planned whose day <= day), else None.
  Subjects of a fill event: [a] (and b for 'battle' / 'betrayal') for battle, schism,
    deposed_leader, discovery and betrayal; [the zone id] for the others (a is drawn either way).
  Every draw's purpose names the event: f"{kind}:{n}:<what>" with n its position in creation order.
  The history horizon is dsf, never a constant (WG-31). Returned sorted by (day, creation order);
  text = atlas.HISTORY_SKELETON[kind] filled with day, a / b (group names), zone (zone name) and
  resource (atlas.SHORTAGE_RESOURCE_WORDS).

WG-20 async write_history(client, tx, events, plan, region, params, at, progress=None) -> list[str]
  (P10: await progress(done, total) after each batch's answer — or failure — in batch order.)
  hist ids (kind 'his') minted in the returned order. Text: WORLDGEN_HISTORY calls, one per batch of
  up to 8 events in order — client.call(lanes.requests.build_request(config, WORLDGEN_HISTORY,
  turn_index=0, context=ctx, json_schema=lanes.schemas.to_lm_schema(HistoryAnswer), ctx=ctx),
  HistoryAnswer), no repair call (the skeleton is the fallback); request context
  WorldgenContext(stage='WG2', brief = a code-built English summary of the region and the batch,
  fields={'events': [{'id', 'day', 'kind', 'subjects': [names], 'cause': hist id or None,
  'skeleton': text}], 'region': {'zones': [names], 'climate': climate_descriptor, 'days_since_fall':
  dsf}}); answer model HistoryAnswer {events: [{id, truth, belief}]}. An event of the batch missing
  from the answer, or with truth outside 20..600 characters or belief outside 10..400, keeps its
  skeleton: truth = text, belief = f"People say {text with 'Day N: ' removed}". A failed call (any
  parse_status but 'ok', or a lane error) does the same for its whole batch. history_events rows {hist_id, day, kind,
  subject_ids, cause_hist_id, truth_text, belief_text} are written by one WORLDGEN_STAGE {stage:
  'WG2', events: n} (writer 'world.worldgen', origin 'worldgen').
  WORLD-01: every settlement and every placed group is a subject of at least one history event.
home_settlement(plan, start_zone_id) -> PlannedSettlement   (implemented below) the HOME settlement:
  the settlement of the PC's entity, else the first planned settlement in the start zone, else the
  first planned settlement (a plan always has one). WG4 makes it the bottleneck, WG6 staffs it, WG8
  starts the PC's troubles there.
WG-21 mark_held(tx, plan, at) -> list[Event] (WG-32): every settlement site that is a building gets places.held = 1 — one PLACE_CHANGE
  {place_id, changes: {held: 1}, reason: 'history'} (writer 'physical.space') per site, in plan order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import Field

from ...contracts.common import Strict

if TYPE_CHECKING:
    from ...contracts.worldgen import Placement, WorldParams
    from ...kernel.rng import Rng
    from ...kernel.store import Tx
    from .region import Region


@dataclass(frozen=True)
class PlannedGroup:
    group_id: str
    kind: str                  # 'faction' | 'group'
    name: str
    content_ref: str | None
    descriptor: str | None
    presence: str | None
    hostile: bool
    is_pc_entity: bool
    home_zone_id: str | None


@dataclass(frozen=True)
class PlannedSettlement:
    settlement_id: str
    group_id: str
    zone_id: str
    site_id: str
    name: str
    population: int


@dataclass(frozen=True)
class PolityPlan:
    groups: tuple[PlannedGroup, ...]
    settlements: tuple[PlannedSettlement, ...]


@dataclass(frozen=True)
class PlannedEvent:
    key: int
    day: int
    kind: str
    subject_ids: tuple[str, ...]
    cause_key: int | None
    text: str


class HistoryItem(Strict):
    id: str
    truth: str
    belief: str


class HistoryAnswer(Strict):
    """The WORLDGEN_HISTORY answer schema."""
    events: list[HistoryItem] = Field(default_factory=list)


def home_settlement(plan: PolityPlan, start_zone_id: str) -> PlannedSettlement:
    """The HOME settlement (implemented; see the module docstring)."""
    pc_groups = {g.group_id for g in plan.groups if g.is_pc_entity}
    for s in plan.settlements:
        if s.group_id in pc_groups:
            return s
    for s in plan.settlements:
        if s.zone_id == start_zone_id:
            return s
    return plan.settlements[0]


def plan_polity(rng: "Rng", tx: "Tx", params: "WorldParams", placement: "Placement", region: "Region",
                canon) -> PolityPlan:
    raise NotImplementedError("P10")


def skeleton(rng: "Rng", tx: "Tx", params: "WorldParams", plan: PolityPlan, region: "Region",
             tier: dict) -> list[PlannedEvent]:
    raise NotImplementedError("P10")


async def write_history(client, tx: "Tx", events: list[PlannedEvent], plan: PolityPlan, region: "Region",
                        params: "WorldParams", at: int, progress=None) -> list[str]:
    raise NotImplementedError("P10")


def mark_held(tx: "Tx", plan: PolityPlan, at: int) -> list:
    raise NotImplementedError("P10")
