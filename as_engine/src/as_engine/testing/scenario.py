"""Scenario fixtures: the format (IMPLEMENTED, protected) and the loader (P2 — implement it).
Human-readable guide: docs/as/12_TESTING.md §Scenario format. Fixtures: tests/fixtures/scenarios/*.yaml.

``ScenarioSpec`` (implemented below) is the machine contract of the YAML. ``parse_scenario`` reads
and validates a file or dict against it — tests and tools may call it today.

load_scenario(path_or_dict, *, packs_root, core_pack_dir, rules=None, transport=None) -> ScenarioWorld
  (P2; the parts that need later modules are marked with the phase that makes them available)
  1. spec = parse_scenario(...). Store.memory(run_id=spec.name, seed=spec.seed,
     start_ms=spec.start.ms()); meta.settings_json = RunSettings(**spec.settings).model_dump_json(),
     meta.rules_json = the effective RulesConfig JSON and meta.content_hash = canon.content_hash,
     written by ONE kernel.meta SETTINGS_CHANGE event (meta is a world table: it changes through
     events like every other world table).
  2. canon = load_canon([core_pack_dir] + [packs_root / p for p in spec.packs]) (any error-severity
     issue -> ValueError); store.attach(canon=canon, rules=RulesConfig defaults deep-merged with
     spec.rules, then with ``rules`` — of which only the explicitly set fields count,
     rules.model_dump(exclude_unset=True), so RulesConfig(harm={...}) overrides just that).
  3. Write the world through events with origin 'system' (functions that build events take
     event_origin='system': objects.create, clock.schedule), turn_index 0, each written by its owning
     module (writer = TABLE_OWNERS[table]); one event per owner-group in this order:
       world_clock weather            (kernel.clock, WEATHER_CHANGE)
       places + anchors + portals     (physical.space, PLACE_DISCOVERED per place; places get
                                       layout_generated = 1 — fixture rooms are already known)
       bodies + needs + wounds        (physical.bodies, MATERIALIZE per body; bodies.origin 'scenario';
                                       needs last_* = start - stage * stage_hours; F1a: bodies.looks
                                       as below, and an ``infected:`` body's grime / blood / gore
                                       5 / 3 / 5 as physical.bodies.create writes them)
       positions                      (physical.space, MOVE per body)
       infected_state                 (world.infected, MATERIALIZE; for bodies with `infected:`)
       actors + dossiers + plans      (mind.actor, MATERIALIZE per actor; dossiers.baseline_json =
                                       the referenced dossier record's JSON, source 'pack',
                                       content_hash = sha256(baseline_json); resolve_max from
                                       mind.actor.resolve_max; resolve_cur = spec.resolve if set
                                       else resolve_max; display_name = identity.name)
       items                          (physical.objects, ITEM_CREATED per item, origin 'scenario')
       tasks                          (action.tasks, TASK_STEP per task with steps_done preset)
       relationships                  (mind.mind, RELATION_CHANGE per pair)
       acquaintance / known_places    (mind.perception, one PERCEIVE event per holder that writes
                                       the rows directly — seeded knowledge is not a percept, so
                                       no percept_log rows; this is the same at every phase).
                                       Every body with a dossier or stub gets a known_places row
                                       for the place it stands in and for every place adjacent to
                                       it through a portal whose kind is not 'wall' or 'fence'
                                       (fixture rooms are home ground), so W09 holds at turn 0.
       beliefs                        (propositions + claim_holdings in the holder's PERCEIVE
                                       event; truth claims in a kernel.truth MATERIALIZE event)
       lessons                        (mind.mind, one LESSON_LEARNED per holder with cues)
       households, groups             (society.household / society.group — tables exist from P0)
       settlements + laws_active      (society.settlement, one event per settlement)
       workplaces + work_assignments  (society.work; next_due_at = first_cycle_at or start + cycle_h)
       event_queue entries            (kernel.clock.schedule)
       narrator_state                 (narration.narrator)
  Stub bodies (``stub:``) get dossiers.baseline_json = stub_dossier(local_id, stub) (source
  'fixture', ActorDossier-valid; the loader validates it) and no content ref.
  F1a (LOOK-01/02): a body with ``dress: true`` is created with looks = its ``looks`` (a
  contracts.dossier.Looks mapping) when given, else its dossier's appearance.looks (neither ->
  ValueError: nothing to dress it in); after every fixture item exists, physical.objects.dress
  (origin 'scenario') puts the looks' outfit on it — unless its inventory already has worn
  clothing — body by body in the order listed (so every fixture id stays as it was). ``looks``
  without ``dress`` sets the looks and dresses nobody: with nothing worn that covers them, that
  body is naked to anyone who sees it. A body with neither has bodies.looks NULL: others see
  height and build only, and no claim is made about its clothes (every scenario written before
  F1a stays exactly as it was).
  4. meta.pc_actor_id = the body with controller 'human' (exactly one; else ValueError), written by
     a kernel.meta PC_CONTROL_CHANGE event {pc_actor_id} — the last event of the load.
  The loaded world passes the 58-bit commit gate at turn 0 (audit.commit_gate.compute(store, 0)).
  Ids of these kinds are minted UP FRONT, before any event is written, in fixture order: every
  place, then every anchor (place order, then anchor order), every portal, every body, every item
  (each body's inventory in body order, then the loose items), every task. ``ScenarioWorld.ids``
  maps every fixture-local id (places, anchors, portals, bodies, item labels / loose item ids) to
  its real id. Other ids (events, dossiers, wounds, propositions, claims, queue entries, lessons,
  households, groups, settlements, workplaces) are minted as they are written, in the order above.
  Unknown content refs (dossier, item, law, group content_ref) -> ValueError naming the fixture
  field; a dossier whose days_since_fall_range excludes the scenario's start day is ALSO a
  ValueError (WG-34: the fixture would put a person in a world they cannot be in).
Row details (what the P2 loader tests read):
  world_clock: now_ms = start, turn_index 0, weather/wind_level from the spec.
  places: layout_generated 1, held from the spec, light_level = spec light; anchors capacity 4.
  portals: every PortalSpec field maps to its column (open -> is_open, locked -> is_locked,
    w/h -> aperture_w_cm/aperture_h_cm, height -> height_cm).
  bodies: kind 'human' for dossier/stub bodies ('lurker' when the dossier's tags contain 'lurker'),
    'infected' for ``infected:`` bodies (an infected type with alive: true — a Lurker — is a
    ValueError here: Lurkers are people with dossiers); content_ref = the dossier ref (NULL for
    stubs/infected);
    sex / age_years / age_band (contracts.common.age_band_for) / height_cm / mass_kg / special
    from the dossier (identity, appearance, capability.special); infected bodies: sex and age NULL,
    height 170, mass 65, special = {letter: (lo + hi) // 2} from the type's SPECIAL ranges;
    (I1) ``animal:`` bodies: kind 'animal', content_ref = the AnimalDef ref, sex and age NULL,
    height_cm / mass_kg from the def, special {}; no actors row and no dossier —
    they are prey and meat, not minds (world.infected INF-18; action.effects butcher);
    awareness / posture / blood_loss_pct / pain from the spec; progressed_at = start;
    (F1c) washed_at = start (everyone starts the scenario clean — LOOK-08 counts from it);
    impairment = physical.bodies.impairment() of the loaded body; origin 'scenario'.
  needs: stage from the spec; last_drink_ms = start - thirst x thirst_stage_every_h hours, and the
    same for last_meal_ms (hunger) and last_sleep_ms (fatigue).
  wounds: one per WoundSpecY, exactly as physical.bodies would create it at ``start`` (bleed,
    pain, function_loss rules) with treatment = the spec's treated list and cause_event = the
    body's MATERIALIZE event id.
  positions: at the anchor's point when ``anchor`` is given (x/y ignored), else at (x, y), else the
    place centre; facing 0; since_ms = start.
  infected_state: type_id = the spec's infected id, states '[]', energy 50, quirks '[]'.
  actors: dossier_id = the dossier row; controller from the spec; display_name = identity.name;
    resolve_max = mind.actor.resolve_max(E, C, capability.resolve_trait_mod); resolve_cur =
    spec.resolve if set else resolve_max; goal_text = spec.goal or plan.goal or ''; duty_anchor and
    accepted_authority (JSON list of real ids) from the spec.
  dossiers: baseline_json = canonical_json(record.model_dump(mode='json', by_alias=True)),
    content_hash = sha256(baseline_json utf-8) hex, source 'pack' (or 'fixture' for stubs).
  plans: one row per body with ``plan`` (goal_text, steps, standing_orders as JSON lists of
    {trigger, response}); updated_at = start.
  items: inventory items with holder_body + holder_slot (a ``container:`` label puts the item
    inside that labelled item instead); loose items at place/anchor or in a container. Each is
    created through physical.objects.create(origin 'scenario'), so ITEM_CREATED payloads carry
    def_ref and qty (gate bit W04 holds).
  tasks: status 'active', started_at = start - steps_done x step_s s, next_due_at = start + step_s s,
    interrupt_on / target_ids as JSON lists (targets mapped to real ids), focus = BodySpec.focus
    (a body with focus: true and no task -> ValueError). One TASK_STEP per task (writer
    action.tasks) whose payload has the action.tasks shape {task_id, actor_id, kind, label,
    steps_done, steps_total, status: 'active'} plus seed: true.
  relationships: one RELATION_CHANGE per RelationshipSpec with payload {from_id, to_id, kind,
    axes, seed: true} and NO 'delta' key (a seeded relationship is not a change; E10 holds);
    updated_at = start; causes '{}'.
  acquaintance: one row per KnowsSpec: known_name = name, description = the spec's description,
    else mind.perception.describe_dossier(subject's dossier) (e.g. 'tall, thin man'); first_met =
    last_seen = start; last_seen_place = the subject's place.
  known_places: see step 3 (holder's place + places adjacent through a portal whose kind is not
    'wall' or 'fence'); first_seen = last_seen = start; visited = 1 for the holder's own place.
  beliefs: each BeliefSpec becomes a propositions row (text, subject_type, subject_id, predicate,
    object_value = the value mapped through ids when it is a fixture-local id, else the literal) and a
    claim_holdings row (believed, confidence, provenance with 'told_by:<local>' mapped to the real
    id, fidelity 'exact', acquired_at = start, acquired_via = the PERCEIVE event id). When
    true_in_world is True the loader also writes a truth claim (writer 'kernel.truth', a
    MATERIALIZE event, subject/predicate from the spec, object_value = the text; claims.origin_event
    and propositions.created_event are the literal 'scenario' — a seed has no causing event) and sets
    propositions.matches_claim to it; when False or None, matches_claim stays NULL and no claim is
    written. Dossier knowledge.cues and BodySpec.cues become lessons rows (writer 'mind.mind',
    one row per cue in order, cue_tags [cue], text 'Knows: <cue description>', confidence 3,
    source_event = the holder's mind.actor MATERIALIZE event id, at = start).
  households / household_members, groups / group_members (standing, since = start, status
    'member') / group_standing (standing_toward), settlements (stores JSON, ration_level, morale,
    cohesion) + laws_active (since = start), workplaces (+ work_assignments) with next_due_at =
    first_cycle_at resolved on the start day ('HH:MM', or '+Nh' from start), else start + cycle_h.
  event_queue: one row per DueEventSpec, due_at = the clock time on the start day or start +
    offset, subject_id = the mapped subject, payload = the spec payload plus place_id / anchor_id
    (real ids) when given; status 'pending'.
  narrator_state: the spec's narrator_state merged over NarratorStyle() defaults (the row itself
    already exists from Store.memory); written only when the spec sets it.
ScenarioWorld exposes: store, canon, rng (Rng(seed)), ids, pc_id, config (EngineConfig whose rules
are the effective rules), transport (FakeTransport unless given), client (LaneClient(config,
transport)), spec, and session() -> service.session.Session over this world (P7; run_dir = a temp
dir; settings from spec.settings).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field, model_validator

from ..contracts.common import Awareness, Posture, Strict
from ..kernel.clock import MS_PER_DAY, MS_PER_H, MS_PER_MIN, MS_PER_S, QUEUE_TYPES

LocalId = str  # fixture-local id, e.g. 'mara', 'front_window'


class StartTime(Strict):
    day: int = Field(ge=0)
    time: str = Field(pattern=r"^\d{2}:\d{2}(:\d{2})?$", description="'HH:MM' or 'HH:MM:SS'")

    def ms(self) -> int:
        parts = [int(x) for x in self.time.split(":")]
        hh, mm, ss = (parts + [0])[:3]
        return self.day * MS_PER_DAY + hh * MS_PER_H + mm * MS_PER_MIN + ss * MS_PER_S


class WeatherSpec(Strict):
    kind: Literal["clear", "overcast", "rain", "storm", "fog", "wind", "heat", "snow"] = "clear"
    wind_level: int = Field(default=0, ge=0, le=3)


_PREPOSITION_WORDS = frozenset({
    "behind", "under", "by", "near", "in", "on", "at", "beside", "inside", "outside", "beyond",
    "between", "across", "above", "below", "along", "against", "atop", "underneath", "to", "from",
})


def _noun_phrase(name: str) -> str:
    """Anchor names are noun phrases ('counter', 'gap behind the counter'), never 'behind the
    counter': code builds 'at the ...', 'to the ...', 'from the ...' around them."""
    first = name.split(" ", 1)[0].lower()
    if first in _PREPOSITION_WORDS:
        raise ValueError(f"anchor name '{name}' must be a noun phrase (e.g. 'gap {name}' or 'far side of ...'), not start with '{first}'")
    return name


class AnchorSpec(Strict):
    id: LocalId
    name: str
    kind: Literal["feature", "cover", "window", "door_side", "furniture", "container", "hiding_spot", "vantage"] = "feature"
    x: float
    y: float
    cover: int = Field(default=0, ge=0, le=3)
    concealment: int = Field(default=0, ge=0, le=3)

    @model_validator(mode="after")
    def _name_is_a_noun_phrase(self) -> "AnchorSpec":
        _noun_phrase(self.name)
        return self


class PlaceSpec(Strict):
    id: LocalId
    name: str
    kind: Literal["building", "room", "street", "outdoor", "vehicle", "tunnel", "roof"] = "room"
    parent: LocalId | None = None
    width_m: float = Field(default=10, gt=0)
    depth_m: float = Field(default=10, gt=0)
    indoor: bool = True
    material: Literal["drywall", "brick", "concrete", "wood", "metal", "glass", "open_air"] = "drywall"
    light: int = Field(default=2, ge=0, le=4)
    ambient_db: float = 30.0
    held: bool = False
    elevation_m: float = Field(default=0.0, ge=0, le=200, description="D-108: the floor's height above the street")
    anchors: list[AnchorSpec] = Field(default_factory=list)


class PortalSpec(Strict):
    id: LocalId
    a: LocalId
    b: LocalId
    kind: Literal["door", "window", "hole", "stairs", "gate", "vent", "drain", "curtain", "opening", "wall", "fence",
                  "climb", "gap", "edge"]
    name: str
    anchor_a: LocalId | None = None
    anchor_b: LocalId | None = None
    open: bool = False
    locked: bool = False
    lock_quality: int = Field(default=0, ge=0, le=4)
    barricade: int = Field(default=0, ge=0, le=3)
    damage: int = Field(default=0, ge=0, le=3)
    w: int = Field(ge=0, description="aperture width cm (0 for wall/fence)")
    h: int = Field(ge=0, description="aperture height cm")
    seal_db: float = Field(default=25.0, ge=0, le=60)
    open_loss_db: float = Field(default=3.0, ge=0, le=20)
    transparent: bool = False
    height: int = Field(default=0, ge=0, le=3000, description="obstacle height cm for climb (fences, walls, windows); "
                        "D-108: a climb's or an edge's height")
    gap: int = Field(default=0, ge=0, le=1000, description="D-108: a 'gap' portal's width in cm")
    below: LocalId | None = Field(default=None, description="D-108: where a body lands when it falls off a gap or an edge")

    @model_validator(mode="after")
    def _walls_are_closed(self) -> "PortalSpec":
        if self.kind in ("wall", "fence", "climb", "gap", "edge") and (self.w != 0 or self.open):
            raise ValueError(f"portal {self.id}: a {self.kind} has aperture 0 and is never open")
        return self


class ItemSpec(Strict):
    item: str = Field(description="Content ref, e.g. core:item/glock_19")
    qty: int = Field(default=1, ge=1)
    condition: int = Field(default=100, ge=0, le=100)
    slot: Literal["hand_l", "hand_r", "worn", "pocket", "pack"] | None = None
    container: LocalId | None = Field(default=None, description="label of another item in the same fixture")
    label: LocalId | None = None
    props: dict[str, Any] = Field(default_factory=dict)


class LooseItemSpec(ItemSpec):
    id: LocalId | None = None
    place: LocalId | None = None
    anchor: LocalId | None = None

    @model_validator(mode="after")
    def _one_location(self) -> "LooseItemSpec":
        if (self.place is None) == (self.container is None):
            raise ValueError("a loose item needs exactly one of place or container")
        return self


class WoundSpecY(Strict):
    anatomy: str
    type: str
    severity: Literal["minor", "significant", "severe", "catastrophic"]
    treated: list[str] = Field(default_factory=list)


class NeedsSpec(Strict):
    thirst: int = Field(default=0, ge=0, le=6)
    hunger: int = Field(default=0, ge=0, le=6)
    fatigue: int = Field(default=0, ge=0, le=6)


class TaskSpec(Strict):
    kind: str
    label: str
    steps_total: int = Field(ge=1)
    steps_done: int = Field(default=0, ge=0)
    step_s: float = Field(gt=0)
    interrupt_on: list[str] = Field(default_factory=list)
    targets: list[LocalId] = Field(default_factory=list)


class StandingOrderSpec(Strict):
    trigger: str = Field(description="cue id, e.g. 'loud_noise'")
    response: str


class PlanSpec(Strict):
    goal: str
    steps: list[str] = Field(default_factory=list)
    standing_orders: list[StandingOrderSpec] = Field(default_factory=list)


class StubSpec(Strict):
    """A fixture-only person for crowd/settlement scenarios (expanded by stub_dossier)."""

    name: str
    age: int = Field(ge=0, le=110)
    sex: Literal["female", "male", "other"]
    occupation: str = "settler"
    cohort: Literal["pre_fall_adult", "fall_child", "post_fall_born"] = "pre_fall_adult"
    skills: dict[str, int] = Field(default_factory=dict, description="skill domain -> rank 1..3")
    special: dict[str, int] = Field(default_factory=dict, description="SPECIAL overrides; others 5")


class BodySpec(Strict):
    id: LocalId
    dossier: str | None = Field(default=None, description="actor/pc content ref; None for infected bodies")
    stub: StubSpec | None = Field(default=None, description="fixture-only person (see stub_dossier)")
    infected: str | None = Field(default=None, description="infected type id, e.g. ZOMBIE_ARCHETYPE_SHAMBLER01")
    animal: str | None = Field(default=None, description="I1: an animal content ref, e.g. core:animal/dog")
    controller: Literal["human", "model", "policy"] = "model"
    place: LocalId
    anchor: LocalId | None = None
    x: float | None = None
    y: float | None = None
    awareness: Awareness = Awareness.AWAKE
    posture: Posture = Posture.STANDING
    resolve: int | None = Field(default=None, ge=0)
    blood_loss_pct: float = Field(default=0, ge=0, le=100)
    pain: int = Field(default=0, ge=0, le=6)
    wounds: list[WoundSpecY] = Field(default_factory=list)
    needs: NeedsSpec = Field(default_factory=NeedsSpec)
    duty_anchor: LocalId | None = None
    accepted_authority: list[LocalId] = Field(default_factory=list)
    goal: str | None = None
    plan: PlanSpec | None = None
    task: TaskSpec | None = None
    inventory: list[ItemSpec] = Field(default_factory=list)
    cues: list[str] = Field(default_factory=list, description="belief cues held in addition to the dossier's knowledge.cues (AFF-10)")
    focus: bool = Field(default=False, description="doing a focused task (divided-attention penalty)")
    looks: dict[str, Any] | None = Field(default=None, description="F1a: a contracts.dossier.Looks mapping that "
                                         "replaces the dossier's (stubs have none)")
    dress: bool = Field(default=False, description="F1a: dress the body in its looks' outfit")

    @model_validator(mode="after")
    def _kind(self) -> "BodySpec":
        if sum(x is not None for x in (self.dossier, self.infected, self.stub, self.animal)) != 1:
            raise ValueError(f"body {self.id}: exactly one of dossier, stub, infected or animal")
        if self.infected is not None and self.controller != "policy":
            raise ValueError(f"body {self.id}: infected bodies are controller 'policy' (Lurkers use a dossier)")
        return self


class RelationshipSpec(Strict):
    from_: LocalId = Field(alias="from")
    to: LocalId
    kind: str = Field(default="acquaintance", description="What ``to`` is to ``from`` (RelationSeed.kind vocabulary): from mother to son is 'child'.")
    trust: int = Field(default=0, ge=-3, le=3)
    fear: int = Field(default=0, ge=0, le=3)
    respect: int = Field(default=0, ge=-3, le=3)
    affection: int = Field(default=0, ge=-3, le=3)
    resentment: int = Field(default=0, ge=0, le=3)
    obligation: int = Field(default=0, ge=-3, le=3)
    model_config = Strict.model_config | {"populate_by_name": True}


class KnowsSpec(Strict):
    holder: LocalId
    subject: LocalId
    name: str | None = Field(default=None, description="None = known only by description")
    description: str | None = None


class BeliefSpec(Strict):
    holder: LocalId
    subject_type: Literal["body", "place", "object", "group", "event", "fact"]
    subject: LocalId | None = None
    predicate: str
    text: str
    confidence: int = Field(ge=0, le=3)
    provenance: str = Field(description="witnessed | overheard | told_by:<local id> | common | childhood | rumour | inferred")
    believed: bool = True
    value: str | None = Field(default=None, description="Machine value (propositions.object_value): a fixture-local id (mapped) or a literal, e.g. the anchor an item is believed to be at.")
    true_in_world: bool | None = Field(default=None, description="When set, the loader also writes (or does not write) a matching truth claim so tests can build false beliefs.")


class HouseholdMemberSpec(Strict):
    actor: LocalId
    role: Literal["head", "partner", "child", "elder", "dependent", "lodger"]
    guardian_of: list[LocalId] = Field(default_factory=list)


class HouseholdSpec(Strict):
    id: LocalId
    dwelling: LocalId | None = None
    members: list[HouseholdMemberSpec] = Field(min_length=1)


class GroupMemberSpec(Strict):
    actor: LocalId
    role: str
    standing: int = Field(default=0, ge=-3, le=3)


class GroupSpec(Strict):
    id: LocalId
    kind: Literal["faction", "group", "household_cluster", "lurker_clan"] = "group"
    name: str
    content_ref: str | None = None
    members: list[GroupMemberSpec] = Field(default_factory=list)
    standing_toward: dict[LocalId, int] = Field(default_factory=dict, description="group_standing rows: body -> -5..5")


class WorkAssignmentSpec(Strict):
    """shift_end_hh < shift_start_hh means an overnight shift (e.g. 18 -> 6)."""

    actor: LocalId
    role: str
    shift_start_hh: int = Field(ge=0, le=23)
    shift_end_hh: int = Field(ge=0, le=24)


class WorkplaceSpec(Strict):
    id: LocalId
    settlement: LocalId
    place: LocalId
    site_type: Literal["water_pump", "kitchen", "garden", "workshop", "clinic", "watch", "laundry", "school"]
    cycle_h: float = Field(gt=0)
    inputs: dict[str, float] = Field(default_factory=dict)
    outputs: dict[str, float] = Field(default_factory=dict, description="units per cycle at full staffing")
    required_roles: list[str] = Field(default_factory=list)
    machinery_condition: int = Field(default=70, ge=0, le=100)
    efficiency: float = Field(default=1.0, ge=0, le=2)
    first_cycle_at: str | None = Field(default=None, description="'HH:MM' on the start day or '+Nh'; None = start + cycle_h")
    assignments: list[WorkAssignmentSpec] = Field(default_factory=list)


class SettlementSpec(Strict):
    id: LocalId
    name: str
    place: LocalId
    group: LocalId | None = None
    stores: dict[str, float] = Field(default_factory=dict)
    ration_level: int = Field(default=3, ge=0, le=4)
    morale: int = 5
    cohesion: int = 5
    laws: list[str] = Field(default_factory=list, description="law content refs made active")


class DueEventSpec(Strict):
    at: str = Field(pattern=r"^\d{2}:\d{2}(:\d{2})?$|^\+\d+(ms|s|m|h)$", description="clock time on the start day, or an offset like '+3s'")
    type: str = Field(description="a kernel.clock.QUEUE_TYPES key")
    subject: LocalId | None = None
    place: LocalId | None = None
    anchor: LocalId | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _known_type(self) -> "DueEventSpec":
        if self.type not in QUEUE_TYPES:
            raise ValueError(f"events_due type '{self.type}' is not a kernel.clock.QUEUE_TYPES key (TIME-06)")
        return self


class ScenarioSpec(Strict):
    schema_id: Literal["as.scenario.v1"] = Field(alias="schema", default="as.scenario.v1")
    name: str = Field(pattern=r"^[a-z0-9_]+$")
    description: str = ""
    seed: int = Field(ge=0)
    start: StartTime
    weather: WeatherSpec = Field(default_factory=WeatherSpec)
    packs: list[str] = Field(default_factory=list, description="extra packs under tests/fixtures/packs")
    settings: dict[str, Any] = Field(default_factory=dict, description="RunSettings fields")
    rules: dict[str, Any] = Field(default_factory=dict, description="RulesConfig overrides (deep merge)")
    places: list[PlaceSpec] = Field(min_length=1)
    portals: list[PortalSpec] = Field(default_factory=list)
    bodies: list[BodySpec] = Field(min_length=1)
    items: list[LooseItemSpec] = Field(default_factory=list)
    relationships: list[RelationshipSpec] = Field(default_factory=list)
    knows: list[KnowsSpec] = Field(default_factory=list)
    beliefs: list[BeliefSpec] = Field(default_factory=list)
    households: list[HouseholdSpec] = Field(default_factory=list)
    groups: list[GroupSpec] = Field(default_factory=list)
    settlements: list[SettlementSpec] = Field(default_factory=list)
    workplaces: list[WorkplaceSpec] = Field(default_factory=list)
    events_due: list[DueEventSpec] = Field(default_factory=list)
    narrator_state: dict[str, Any] | None = None
    notes: list[str] = Field(default_factory=list, description="Human notes; never read by code.")
    model_config = Strict.model_config | {"populate_by_name": True}

    @model_validator(mode="after")
    def _references(self) -> "ScenarioSpec":
        place_ids = [p.id for p in self.places]
        anchor_ids = [a.id for p in self.places for a in p.anchors]
        body_ids = [b.id for b in self.bodies]
        labels = [i.label for b in self.bodies for i in b.inventory if i.label] + \
                 [i.id for i in self.items if i.id] + [i.label for i in self.items if i.label]
        all_ids = place_ids + anchor_ids + body_ids + [p.id for p in self.portals]
        dupes = {x for x in all_ids if all_ids.count(x) > 1}
        if dupes:
            raise ValueError(f"duplicate fixture ids: {sorted(dupes)}")
        humans = [b.id for b in self.bodies if b.controller == "human"]
        if len(humans) != 1:
            raise ValueError(f"exactly one body must have controller 'human' (found {humans})")

        def need(kind: str, value: str | None, pool: list[str]) -> None:
            if value is not None and value not in pool:
                raise ValueError(f"unknown {kind} '{value}'")

        for p in self.places:
            need("place", p.parent, place_ids)
        for pt in self.portals:
            need("place", pt.a, place_ids)
            need("place", pt.b, place_ids)
            need("anchor", pt.anchor_a, anchor_ids)
            need("anchor", pt.anchor_b, anchor_ids)
        for b in self.bodies:
            need("place", b.place, place_ids)
            need("anchor", b.anchor, anchor_ids)
            need("anchor", b.duty_anchor, anchor_ids)
            for a in b.accepted_authority:
                need("body", a, body_ids)
            for i in b.inventory:
                need("container label", i.container, labels)
            if b.task:
                for t in b.task.targets:
                    need("target", t, all_ids + labels)
        for i in self.items:
            need("place", i.place, place_ids)
            need("anchor", i.anchor, anchor_ids)
            need("container label", i.container, labels)
        for r in self.relationships:
            need("body", r.from_, body_ids)
            need("body", r.to, body_ids)
        for k in self.knows:
            need("body", k.holder, body_ids)
            need("body", k.subject, body_ids)
        for bl in self.beliefs:
            need("body", bl.holder, body_ids)
            need("subject", bl.subject, all_ids + labels)
        for h in self.households:
            need("place", h.dwelling, place_ids)
            for m in h.members:
                need("body", m.actor, body_ids)
                for g in m.guardian_of:
                    need("body", g, body_ids)
        for g in self.groups:
            for m in g.members:
                need("body", m.actor, body_ids)
            for k in g.standing_toward:
                need("body", k, body_ids)
        settlement_ids = [s.id for s in self.settlements]
        group_ids = [g.id for g in self.groups]
        for s in self.settlements:
            need("place", s.place, place_ids)
            need("group", s.group, group_ids)
        for w in self.workplaces:
            need("settlement", w.settlement, settlement_ids)
            need("place", w.place, place_ids)
            for a in w.assignments:
                need("body", a.actor, body_ids)
        for e in self.events_due:
            need("place", e.place, place_ids)
            need("anchor", e.anchor, anchor_ids)
            need("subject", e.subject, all_ids + labels)
        return self

    def local_ids(self) -> list[str]:
        return [p.id for p in self.places] + [a.id for p in self.places for a in p.anchors] + \
               [p.id for p in self.portals] + [b.id for b in self.bodies]


def stub_dossier(local_id: str, stub: StubSpec) -> dict:
    """Expand a StubSpec into a VALID ActorDossier dict (implemented; deterministic; fixture-only).

    Stub people are plain on purpose: a generic but specific-enough record that passes CNT-10,
    tagged 'fixture_stub', generation 'generated'. Tests that care about voice use real dossiers."""
    first = stub.name.split()[0]
    special = {k: stub.special.get(k, 5) for k in "SPECIAL"}
    skills = [{"domain": d, "rank": r, "evidence": f"{first} has done this work for years in the settlement."}
              for d, r in sorted(stub.skills.items())]
    return {
        "schema": "as.actor.v1", "id": f"stub_{local_id}", "generation": "generated",
        "identity": {"name": stub.name, "age": stub.age, "sex": stub.sex, "cohort": stub.cohort,
                     "birthplace": "the settlement's county", "occupation_before": stub.occupation,
                     "occupation_now": stub.occupation,
                     "one_line": f"{stub.name}, a {stub.occupation} in the settlement."},
        "appearance": {"height_cm": 170 if stub.age >= 16 else 120, "mass_kg": 70 if stub.age >= 16 else 25,
                       "build": "ordinary", "hair": "brown", "eyes": "brown", "skin": "weathered",
                       "distinguishing_marks": [f"a scar {first} never explains"],
                       "clothing_usual": "patched work clothes",
                       "movement_under_stress": "moves quickly and keeps to the walls",
                       "habit_gesture": "rubs the back of the neck",
                       "relation_to_appearance": "does not think about it"},
        "capability": {"special": special, "skills": skills, "literacy": 2, "tech_literacy": 1},
        "motive": {"motive": "keep the settlement fed and safe", "method": "does the work assigned, and some more",
                   "moral_line": {"will": ["work a double shift"], "wont": ["steal from the common store"],
                                  "wont_tags": ["steal"]},
                   "inner_conflict": "wants to leave and cannot abandon the others",
                   "past_wound": "lost family in the first week of the Fall",
                   "signature_behaviour": "counts the water jugs every evening",
                   "risk_threshold": 4, "risk_text": "takes risks only for family",
                   "resource_constraints": "owns what fits in one bag"},
        "persona": {"public": {"shown_traits": ["steady"], "claimed_history": "came in the first winter",
                               "presented_affiliation": "the settlement"},
                    "private": {"true_goals": ["keep the family alive"], "concealed_history": "none worth telling",
                                "real_affiliation": "the family"}},
        "traits": [
            {"tag": "dutiful", "manifests": "turns up for every shift early", "triggers": "a job needing doing",
             "causes": "takes on extra work", "costs": "is always tired", "example": "covered two shifts in the storm week"},
            {"tag": "worried", "manifests": "asks about the stores every day", "triggers": "low water",
             "causes": "hoards a little", "costs": "people find it tiring", "example": "kept a spare jug under the bed"}],
        "contradictions": [{"belief_a": "the settlement comes first", "belief_b": "family comes first",
                            "a_wins_when": "the stores are full", "b_wins_when": "the stores are low"}],
        "decision_stack": {"layers": ["family", "own safety", "the settlement", "strangers"],
                           "inversion_conditions": ["a raid on the settlement"],
                           "past_example": "stayed on the wall during the raid instead of running home"},
        "silence": {"goes_quiet_when": ["the dead are mentioned", "leaders argue"],
                    "body_when_silent": "arms folded, looking at the floor",
                    "comfortable_vs_uncomfortable": "comfortable at work, uncomfortable in meetings"},
        "knowledge": {"knows": ["where the pump and the kitchen are"]},
        "voice": {"capsule": f"{first} talks plainly and briefly, like someone who works with their hands.",
                  "speech_tendencies": ["short sentences", "talks about the work"],
                  "exemplars": {"low_stakes": "Pump's running fine today.",
                                "under_pressure": "Get the kids inside. Now.",
                                "at_the_limit": "I can't do another shift. I can't."},
                  "would_never_say": ["Let them starve.", "Not my problem.", "Whatever you say, boss."],
                  "profanity": "rare"},
        "social": {"household_role": "", "relations": [], "dependents": [], "guardians": [], "memberships": []},
        "life": {"aspiration": "a quiet year", "current_project": "keeping up with the shifts",
                 "fears": ["the pump failing"]},
        "disposition": {"archetype_prior": "civilized", "toward_strangers": "wary",
                        "encounter_default": "calls for the watch and keeps distance"},
        "tags": ["fixture_stub"],
    }


def parse_scenario(path_or_dict: str | Path | dict) -> ScenarioSpec:
    """Read + validate a scenario (implemented)."""
    if isinstance(path_or_dict, dict):
        data = path_or_dict
    else:
        data = yaml.safe_load(Path(path_or_dict).read_text(encoding="utf-8"))
    return ScenarioSpec.model_validate(data)


@dataclass
class ScenarioWorld:
    name: str
    store: Any
    canon: Any
    rng: Any
    config: Any
    transport: Any
    client: Any
    pc_id: str
    spec: ScenarioSpec | None = None
    ids: dict[str, str] = field(default_factory=dict)

    def id(self, local: str) -> str:
        return self.ids[local]

    def local(self, real_id: str) -> str:
        """Reverse of id(): the fixture-local id for an internal id (implemented; tests and
        tooling print these). Unknown ids come back unchanged."""
        for k, v in self.ids.items():
            if v == real_id:
                return k
        return real_id

    def session(self, run_dir=None):
        """P7. The loaded world as a service.session.Session: run_id = meta.run_id, run_dir (None:
        in-memory, the turn pipeline skips the autosave), this world's store / canon / config / rng /
        client / pc_id, settings = RunSettings from meta.settings_json. A new Session each call
        (they share the store)."""
        raise NotImplementedError("P7")


def load_scenario(path_or_dict: str | Path | dict, *, packs_root: str | Path, core_pack_dir: str | Path,
                  rules: Any = None, transport: Any = None) -> ScenarioWorld:
    raise NotImplementedError("P2")
from ._impl_loader import load_scenario  # noqa: E402,F811
def _session(self, run_dir=None):
    from ..service._impl_session import session_from_world
    return session_from_world(self, run_dir)
ScenarioWorld.session = _session  # noqa
