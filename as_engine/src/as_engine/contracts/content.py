"""Content pack record contracts (docs/as/09_CONTENT_PACKS.md).

A content pack is a folder of YAML/Markdown files. The compiler validates every file against
these models, resolves cross references, runs the content linter (CNT-*) and writes
``canon.sqlite``. Nothing here is loaded whole into a prompt; it is *queried*.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from .common import MoralTag, Posture, SkillDomain, Strict, Verb
from .dossier import SLUG_PATTERN, ContentRef

SpecialLetter = Literal["S", "P", "E", "C", "I", "A", "L"]


class PackManifest(Strict):
    schema_id: Literal["as.pack.v1"] = Field(alias="schema", default="as.pack.v1")
    id: str = Field(pattern=SLUG_PATTERN)
    name: str
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    description: str
    depends_on: list[str] = Field(default_factory=list)
    authors: list[str] = Field(default_factory=list)
    overrides: list[str] = Field(default_factory=list, description="Refs from earlier packs this pack deliberately replaces (CNT-03).")
    model_config = Strict.model_config | {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


class FirearmProps(Strict):
    caliber: str = Field(pattern=r"^[a-z0-9]+$", description="Caliber TAG, e.g. '9mm', '38spl', '12ga', '308win', '22lr'. Ammo and magazines that fit carry the same tag in tags[] (reload_firearm binding, AFF-02).")
    capacity: int = Field(ge=1)
    action: Literal["semi", "pump", "bolt", "revolver", "lever", "auto"]
    noise_db: float = Field(ge=60, le=180, description="dB at 1 m, unsuppressed")
    effective_range_m: float = Field(gt=0)
    damage_class: Literal["light", "medium", "heavy"]
    feeds_from: Literal["magazine", "internal", "cylinder"] = "magazine"
    magazine_item: ContentRef | None = None


class MeleeProps(Strict):
    reach_m: float = Field(ge=0.2, le=3.0)
    damage_class: Literal["light", "medium", "heavy"]
    wound_types: list[str] = Field(min_length=1)
    noise_db: float = 40.0


class ContainerProps(Strict):
    capacity_bulk: int = Field(ge=1)
    access_time_s: float = Field(ge=0.5)
    worn: bool = False


class FoodProps(Strict):
    kcal: int = Field(ge=0)
    spoil_days: int | None = None


class WaterProps(Strict):
    ml: int = Field(ge=1)
    potable: bool = True


class MedicalProps(Strict):
    treats: list[Literal["bleeding", "wound_cleaning", "pain", "fracture", "infection_wound", "burn"]]
    uses: int = Field(ge=1)
    skill_min: int = Field(default=0, ge=0, le=3)


class ItemDef(Strict):
    schema_id: Literal["as.item.v1"] = Field(alias="schema", default="as.item.v1")
    id: str = Field(pattern=SLUG_PATTERN)
    name: str = Field(description="Used verbatim in every sentence ('your fire axe', 'the Glock 19'): common nouns in lower case, proper nouns capitalised.")
    plural: str
    kind: Literal[
        "firearm", "magazine", "ammo", "melee", "food", "water", "medical", "tool",
        "container", "clothing", "light", "fuel", "document", "key", "valuable", "misc", "infected_part",
    ]
    mass_g: int = Field(ge=0)
    bulk: int = Field(ge=0, le=20)
    tags: list[str] = Field(default_factory=list)
    stackable: bool = False
    barter_value: int = Field(default=0, ge=0)
    firearm: FirearmProps | None = None
    melee: MeleeProps | None = None
    container: ContainerProps | None = None
    food: FoodProps | None = None
    water: WaterProps | None = None
    medical: MedicalProps | None = None
    description: str = Field(min_length=5)
    model_config = Strict.model_config | {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Affordance catalog (the most important content table in the game)
# ---------------------------------------------------------------------------


class SkillReq(Strict):
    domain: SkillDomain
    min_rank: int = Field(ge=1, le=3)


class AffordanceRequires(Strict):
    mobile: bool = False
    hands_free: int = Field(default=0, ge=0, le=2)
    held_item_tags: list[str] = Field(default_factory=list)
    carried_item_tags: list[str] = Field(default_factory=list)
    skill: SkillReq | None = None
    skill_or_belief_cue: str | None = Field(
        default=None, description="Alternative to `skill`: holding a belief with this cue tag also qualifies."
    )
    belief_cues: list[str] = Field(default_factory=list)
    resolve_min: int = Field(default=0, ge=0, le=3)
    fear_exposure: bool = False
    posture_any: list[Posture] | None = None
    target_alive: bool | None = None
    target_kinds: list[str] | None = None
    actor_kinds: list[str] | None = Field(default=None, description="Body kinds that may attempt this (physical gate), e.g. ['infected'] for bite; None = any kind that has hands for the option.")


class DurationSpec(Strict):
    base_s: float = Field(ge=0)
    per_meter_s: float = Field(default=0.0, ge=0)
    condition_ended: bool = False


class CheckSpec(Strict):
    attribute: SpecialLetter
    skill: SkillDomain | None = None
    tags: list[str] = Field(default_factory=list)
    resistance: str | None = Field(default=None, description="Resistance source key, see 07_RULES.md §Resistance keys.")
    opposed: bool = False
    opposed_attribute: SpecialLetter | None = None
    opposed_skill: SkillDomain | None = None
    consequence_ladder: Literal["standard", "stealth6"] = "standard"


class AffordanceDef(Strict):
    schema_id: Literal["as.affordance.v1"] = Field(alias="schema", default="as.affordance.v1")
    id: str = Field(pattern=SLUG_PATTERN)
    verb: Verb
    label: str = Field(description="Packet label template. Placeholders: {target} {destination} {item} {distance} {duration}")
    ui_label: str = Field(description="Player-facing suggestion text template, same placeholders.")
    binds: Literal[
        "none", "self", "anchor", "portal", "body", "item_reachable", "item_held",
        "item_carried", "container", "place_adjacent", "speech", "wound",
    ]
    range: Literal["self", "touch", "reach", "same_place", "adjacent_place", "visible", "audible"]
    requires: AffordanceRequires = Field(default_factory=AffordanceRequires)
    moral_tags: list[MoralTag] = Field(default_factory=list)
    moral_tags_if_target: dict[str, list[MoralTag]] = Field(
        default_factory=dict, description="Extra moral tags keyed by target kind/age band, e.g. {'child': [kill_child]}"
    )
    duration: DurationSpec
    noise_db: float = Field(ge=0, le=180)
    visible_act: bool = True
    check: CheckSpec | None = None
    effect: str = Field(description="Resolver effect handler id (07_RULES.md §Effect handlers).")
    tags: list[str] = Field(default_factory=list)
    model_config = Strict.model_config | {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Infected
# ---------------------------------------------------------------------------


class RangeInt(Strict):
    lo: int
    hi: int


class InfectedSenses(Strict):
    hearing_threshold_db: float
    vision_range_m: float
    vision_mode: Literal["motion_contrast", "shape", "thermal", "full"]
    thermal: bool = False


class InfectedTypeDef(Strict):
    schema_id: Literal["as.infected.v1"] = Field(alias="schema", default="as.infected.v1")
    id: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$", description="Stable canon id, e.g. ZOMBIE_ARCHETYPE_SHAMBLER01")
    name: str
    rarity: Literal["common", "uncommon", "semi_rare", "rare"]
    inherits: str | None = None
    special: dict[SpecialLetter, RangeInt]
    senses: InfectedSenses
    speed_m_s: float = Field(gt=0)
    sprint_m_s: float = Field(gt=0)
    grip_strength: int = Field(ge=1, le=10)
    alive: bool = Field(description="Lurkers are alive and do not reanimate.")
    false_death: bool
    reanimation_window_h: tuple[float, float] | None = None
    true_kill: list[str] = Field(min_length=1)
    quirks: list[str] = Field(default_factory=list)
    player_facing: list[str] = Field(min_length=1)
    codex_truth: list[str] = Field(min_length=1)
    tactics: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    model_config = Strict.model_config | {"populate_by_name": True}


class InfectedStateDef(Strict):
    schema_id: Literal["as.infected_state.v1"] = Field(alias="schema", default="as.infected_state.v1")
    id: Literal["dormant", "starved", "overfed", "injured"]
    effects: list[str] = Field(min_length=1)
    speed_mult: float = Field(ge=0, description="0 = motionless while in the state (dormant).")
    hearing_threshold_delta_db: float = 0.0
    bite_commitment: float = Field(ge=0, le=1)
    model_config = Strict.model_config | {"populate_by_name": True}


class QuirkDef(Strict):
    schema_id: Literal["as.quirk.v1"] = Field(alias="schema", default="as.quirk.v1")
    id: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    applies_to: list[str] = Field(min_length=1)
    text: str = Field(min_length=15)
    trigger_cue: str | None = None
    observable_tell: str = Field(min_length=5, description="What a witness perceives.")
    seed_weight: float = Field(default=1.0, gt=0)
    model_config = Strict.model_config | {"populate_by_name": True}


class InfectionStage(Strict):
    name: str
    starts_at_h: float = Field(ge=0)
    effects: list[str] = Field(min_length=1)
    saliva_infectious: bool = False
    compulsion: int = Field(default=0, ge=0, le=3)
    impairment: int = Field(default=0, ge=0, le=6)


class InfectionPathwayDef(Strict):
    schema_id: Literal["as.pathway.v1"] = Field(alias="schema", default="as.pathway.v1")
    id: Literal["air", "wet", "lurker_deep", "cold_start"]
    canon_status: Literal["canon", "proposed"]
    exposure: dict[str, float] = Field(description="exposure kind -> probability of infection, e.g. {'bite': 0.9}")
    stages: list[InfectionStage] = Field(min_length=1)
    death_at_h: float | None = None
    rise_after_death_h: tuple[float, float] | None = None
    rise_as: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    model_config = Strict.model_config | {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Cascade, law, places, factions, lore, style
# ---------------------------------------------------------------------------


class CascadeEffect(Strict):
    kind: Literal["emit_event", "schedule_event", "adjust", "create_trace", "create_rumour", "drain_resolve"]
    event_type: str | None = None
    target: str | None = Field(default=None, description="Selector (action/cascade.py CAS-05), e.g. 'actor(trigger.actor_id)', 'settlement_of(trigger.payload.workplace_id)'")
    field: str | None = None
    amount: float | None = None
    payload: dict = Field(default_factory=dict)


class CascadeRuleDef(Strict):
    schema_id: Literal["as.cascade.v1"] = Field(alias="schema", default="as.cascade.v1")
    id: str = Field(pattern=r"^CAS-\d{3}$")
    description: str = Field(min_length=10)
    trigger_event: str
    where: dict = Field(default_factory=dict, description="Equality filters on the trigger event payload.")
    preconditions: list[str] = Field(default_factory=list)
    effects: list[CascadeEffect] = Field(min_length=1)
    delay_s: float = Field(default=0, ge=0)
    cites: list[str] = Field(default_factory=list)
    model_config = Strict.model_config | {"populate_by_name": True}


class LawEffect(Strict):
    affordance_tag: str
    effect: Literal["forbid", "cost"]
    applies_to: Literal["members", "visitors", "all"] = "all"
    cost_note: str = ""


class LawDef(Strict):
    schema_id: Literal["as.law.v1"] = Field(alias="schema", default="as.law.v1")
    id: str = Field(pattern=SLUG_PATTERN)
    name: str
    kind: Literal[
        "curfew", "weapons", "ration", "trade", "quarantine", "theft", "burial", "child_labour",
        "visitors", "noise", "patrol", "succession", "intake", "contamination",
    ]
    text: str = Field(min_length=10)
    affordance_effects: list[LawEffect] = Field(default_factory=list)
    enforcement: str
    punishment: str
    belief_text: str = Field(min_length=5, description="How locals describe the law (belief layer).")
    model_config = Strict.model_config | {"populate_by_name": True}


_PREPOSITION_WORDS = frozenset({
    "behind", "under", "by", "near", "in", "on", "at", "beside", "inside", "outside", "beyond",
    "between", "across", "above", "below", "along", "against", "atop", "underneath", "to", "from",
})


class AnchorTemplate(Strict):
    name: str = Field(description="A noun phrase ('counter', 'far side of the car') — never preposition-first; code writes 'at the ...' around it.")
    kind: Literal["feature", "cover", "window", "door_side", "furniture", "container", "hiding_spot", "vantage"]
    x_m: float
    y_m: float
    cover: int = Field(default=0, ge=0, le=3)
    concealment: int = Field(default=0, ge=0, le=3)
    container_item: ContentRef | None = None

    @field_validator("name")
    @classmethod
    def _noun_phrase(cls, v: str) -> str:
        if v.split(" ", 1)[0].lower() in _PREPOSITION_WORDS:
            raise ValueError(f"anchor name '{v}' must be a noun phrase, not start with a preposition")
        return v


class PortalTemplate(Strict):
    to_room: str
    kind: Literal["door", "window", "hole", "stairs", "gate", "vent", "drain", "curtain", "opening", "wall", "fence"]
    name: str
    lockable: bool = False
    lock_quality: int = Field(default=0, ge=0, le=4)
    aperture_w_cm: int = Field(ge=0, description="0 for 'wall' (acoustic-only link, never traversable).")
    aperture_h_cm: int = Field(ge=0)
    seal_db: float = Field(ge=0, le=60, description="Sound loss when closed.")
    open_loss_db: float = Field(default=3.0, ge=0, le=20)
    transparent: bool = False
    starts_open: bool = False
    height_cm: int = Field(default=0, ge=0, le=600, description="Obstacle height for fences/walls/windows (climb); 0 = not climbable.")


class RoomTemplate(Strict):
    id: str = Field(pattern=SLUG_PATTERN)
    name: str
    size_m2: float = Field(gt=0)
    width_m: float = Field(gt=0)
    depth_m: float = Field(gt=0)
    indoor: bool = True
    material: Literal["drywall", "brick", "concrete", "wood", "metal", "glass", "open_air"] = "drywall"
    anchors: list[AnchorTemplate] = Field(min_length=1)
    portals: list[PortalTemplate] = Field(default_factory=list)
    loot_table: str | None = None


class BuildingArchetype(Strict):
    schema_id: Literal["as.building.v1"] = Field(alias="schema", default="as.building.v1")
    id: str = Field(pattern=SLUG_PATTERN)
    name: str
    kind: str
    rooms: list[RoomTemplate] = Field(min_length=1)
    entrance_room: str
    exterior_portals: list[PortalTemplate] = Field(min_length=1)
    description: str = Field(min_length=10)
    model_config = Strict.model_config | {"populate_by_name": True}


class FactionRelation(Strict):
    faction: ContentRef
    stance: Literal["allied", "cooperative", "neutral", "wary", "hostile", "war", "unaware"]
    history: str = Field(min_length=10)


class Doctrine(Strict):
    challenge_procedure: str
    escalation_ladder: list[str] = Field(min_length=2)
    treatment_of_unknowns: str
    treatment_of_visibly_sick: str
    prisoner_policy: str
    intake_screening: list[str] = Field(default_factory=list)


class FactionPresence(Strict):
    regional_reach: str
    start_trust_ranges: dict[str, tuple[int, int]] = Field(default_factory=dict)
    era_exceptions: dict[str, str] = Field(default_factory=dict)
    presence_conditions: list[str] = Field(
        default_factory=list,
        description="Plausibility-grammar expressions over world params (world/worldgen/conditions.py, "
        "parsed at load under CNT-09). ALL must be true for WG3 to place this faction or group.")
    population_baseline: int = Field(ge=0, description="Members at world start before history modulation (WG4, Batch-3 ruling #5).")


class Leader(Strict):
    title: str
    role: str
    actor: ContentRef | None = None


class FactionDossier(Strict):
    schema_id: Literal["as.faction.v1"] = Field(alias="schema", default="as.faction.v1")
    id: str = Field(pattern=SLUG_PATTERN)
    name: str
    kind: Literal["faction", "group"]
    one_line: str = Field(min_length=10)
    wants: str = Field(min_length=10, description="What they actually want, beneath the stated purpose.")
    stated_purpose: str
    methods: str = Field(min_length=10)
    will_not_do: list[str] = Field(min_length=1)
    resources_have: list[str] = Field(min_length=1)
    resources_need: list[str] = Field(min_length=1)
    pressure: str
    leaders: list[Leader] = Field(min_length=1)
    how_leadership_is_contested: str
    fault_lines: list[str] = Field(min_length=1)
    relations: list[FactionRelation] = Field(default_factory=list)
    doctrine: Doctrine
    laws: list[ContentRef] = Field(default_factory=list)
    node_classes: list[str] = Field(default_factory=list)
    presence: FactionPresence
    member_archetypes: list[str] = Field(default_factory=list)
    belief_text: str = Field(min_length=10, description="What ordinary survivors say about them.")
    truth_text: str = Field(min_length=10, description="What is actually true (engine-only).")
    depth_reference: str | None = None
    model_config = Strict.model_config | {"populate_by_name": True}


class LoreBelief(Strict):
    held_by: str = Field(description="'common', a faction ContentRef, 'cohort:<cohort>' or 'region:<tag>'")
    text: str = Field(min_length=5)
    confidence: int = Field(ge=0, le=3)
    cues: list[str] = Field(default_factory=list, description="Belief cues granted to whoever holds this belief (seeded as lessons rows, AFF-10).")


class LoreEntry(Strict):
    schema_id: Literal["as.lore.v1"] = Field(alias="schema", default="as.lore.v1")
    id: str = Field(pattern=SLUG_PATTERN)
    title: str
    kind: Literal["history", "place", "faction", "infected", "culture", "rumour", "tech", "person"]
    truth: str = Field(min_length=10)
    beliefs: list[LoreBelief] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    entities: list[ContentRef] = Field(default_factory=list)
    body: str | None = Field(default=None, description="Set by the loader: the markdown below the front matter (depth text, pulled on demand; never put in a packet whole).")
    model_config = Strict.model_config | {"populate_by_name": True}


class StyleRules(Strict):
    schema_id: Literal["as.style.v1"] = Field(alias="schema", default="as.style.v1")
    id: str = Field(pattern=SLUG_PATTERN)
    banned_phrases: list[str] = Field(min_length=10)
    vague_timers: list[str] = Field(min_length=3)
    leak_phrases: list[str] = Field(min_length=3)
    abstract_words: list[str] = Field(min_length=10)
    adverb_exceptions: list[str] = Field(default_factory=list)
    model_config = Strict.model_config | {"populate_by_name": True}


class CueDef(Strict):
    id: str = Field(pattern=SLUG_PATTERN)
    description: str


class CueRegistry(Strict):
    schema_id: Literal["as.cues.v1"] = Field(alias="schema", default="as.cues.v1")
    cues: list[CueDef] = Field(min_length=1)
    model_config = Strict.model_config | {"populate_by_name": True}


class NameList(Strict):
    schema_id: Literal["as.names.v1"] = Field(alias="schema", default="as.names.v1")
    id: str = Field(pattern=SLUG_PATTERN)
    given_female: list[str] = Field(min_length=20)
    given_male: list[str] = Field(min_length=20)
    family: list[str] = Field(min_length=30)
    nicknames: list[str] = Field(default_factory=list)
    model_config = Strict.model_config | {"populate_by_name": True}


class LootEntry(Strict):
    item: ContentRef
    weight: float = Field(gt=0)
    qty: tuple[int, int] = (1, 1)
    condition: tuple[int, int] = (40, 100)


class LootTable(Strict):
    schema_id: Literal["as.loot.v1"] = Field(alias="schema", default="as.loot.v1")
    id: str = Field(pattern=SLUG_PATTERN)
    rolls: tuple[int, int] = (0, 3)
    entries: list[LootEntry] = Field(min_length=1)
    model_config = Strict.model_config | {"populate_by_name": True}
