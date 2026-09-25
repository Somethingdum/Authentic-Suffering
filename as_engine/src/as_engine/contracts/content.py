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


class ClothingProps(Strict):
    """What a piece of clothing is to the eye and to the body (F1a, LOOK-02)."""

    slot: Literal["head", "face", "neck", "torso", "body", "legs", "hands", "feet"] = Field(
        description="Where it is worn; 'body' is one piece over torso and legs (a dress, overalls).")
    layer: Literal["under", "mid", "outer"] = "mid"
    covers: list[Literal["head", "face", "neck", "torso", "arms", "groin", "legs", "hands", "feet"]] = Field(
        min_length=1)
    words: str = Field(min_length=3, description="How it reads to the eye, without colour: 'work jacket', "
                       "'thermal top', 'cargo pants'.")
    colour: str = Field(default="", description="Its usual colour word ('navy'); an item's props.colour overrides it.")
    plural: bool = Field(default=False, description="Words that take no article: 'cargo pants', 'work boots'.")
    style: list[Literal["work", "casual", "formal", "uniform", "tactical", "medical", "outdoor", "night",
                        "rags"]] = Field(default_factory=list)
    warmth: int = Field(default=0, ge=0, le=3)
    protection: int = Field(default=0, ge=0, le=3, description="Against cuts, scratches and bites to what it covers.")
    conceals: bool = Field(default=False, description="An outer layer that hides what is worn beneath it at the "
                           "torso and waist (a holstered pistol under a long coat).")


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
    clothing: ClothingProps | None = None
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
    portal_kinds: list[str] | None = Field(default=None, description="Portal kinds this may bind to (physical gate), e.g. ['door', 'window', 'gate'] for closing; None = any portal the binding offers. An 'opening' has nothing to close, lock or bar (P10).")
    actor_kinds: list[str] | None = Field(default=None, description="Body kinds that may attempt this (physical gate), e.g. ['infected'] for bite; None = any kind that has hands for the option.")
    can_run: bool = Field(default=False, description="H1: the actor must be able to run (physical.bodies capacity "
                          "can_run: no leg or foot wound that hobbles it).")
    reflex_only: bool = Field(default=False, description="W1: never offered on a menu (mind.affordance drops it "
                              "before the gates); only code builds it — the wet strain's compulsion (turn.cognition "
                              "step 3).")
    infected_within_m: float | None = Field(default=None, gt=0, description="H1: offered only while the actor sees "
                                            "one of the dead (a visual percept this turn, clear or partial, of an "
                                            "infected body) within this many metres of it.")


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


# The families of attempt a person can ask to see more of (Actor Spec §8; mind.consult CONSULT-03):
# key -> the words a prompt shows. Order is the order a packet lists them in.
AFFORDANCE_FAMILIES: dict[str, str] = {
    "attention": "watching, listening, looking closer",
    "conversation": "talking",
    "expression": "signs and gestures",
    "movement": "moving, taking cover, how you stand",
    "access": "doors, locks and ways through",
    "possessions": "picking up, handing over, searching, putting away",
    "cooperation": "working with someone",
    "care": "tending wounds, eating, drinking, resting",
    "work": "the work in hand",
    "conflict": "fighting, struggling, giving up",
    "communication": "notes, signs and radios",
    "commitments": "promises",
}
AffordanceFamily = Literal["attention", "conversation", "expression", "movement", "access", "possessions",
                           "cooperation", "care", "work", "conflict", "communication", "commitments"]


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
    paces: list[Literal["careful", "rushed"]] = Field(
        default_factory=list, description="The paces this attempt supports besides normal (Actor Spec §7; "
        "action.intent INTENT-07): careful takes 1.5 times as long and is 6 dB quieter, rushed takes 0.6 "
        "times as long and is 6 dB louder. Moves have their own careful, sneaking and running options.")
    family: AffordanceFamily | None = Field(
        default=None, description="Its family (AFFORDANCE_FAMILIES); None = the family mind.consult.family_of "
        "derives from its verb, effect, binds and tags.")
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


class AnimalDef(Strict):
    """I1 (D-85): an animal — prey for the dead and meat for the living (world.infected INF-18;
    action.effects butcher). Only people take the strain: an animal is eaten, never turned."""
    schema_id: Literal["as.animal.v1"] = Field(alias="schema", default="as.animal.v1")
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(description="What it is, lower case, no article: 'dog'")
    plural: str
    words: str = Field(description="How it reads to someone who sees it, no article: 'scrawny grey dog' "
                       "(mind.perception describe)")
    size: Literal["small", "medium", "large"]
    height_cm: int = Field(ge=5, le=250)
    mass_kg: float = Field(gt=0, le=1200)
    speed_m_s: float = Field(gt=0)
    meat_portions: int = Field(ge=0, description="What butchering it yields: this many core:item/raw_meat")
    sound: str = Field(default="", description="The sound it makes, for the narrator: 'a dog barking'")
    model_config = Strict.model_config | {"populate_by_name": True}


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
    felt: str = Field(default="", description="P10: what the host feels at this stage, one full "
                      "sentence in the second person — a feeling, never the stage's name (packet "
                      "body_lines, the narrator's pc_state_lines). Empty: nothing felt.")
    signs: list[str] = Field(default_factory=list, description="P10: registry cue ids an observer "
                             "who sees the host clearly and close gets (mind.cues; CNT-05).")


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
    kind: Literal["emit_event", "schedule_event", "adjust", "create_trace", "create_rumour", "drain_resolve",
                  "adjust_stress"]
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
    """What a law means to a person who KNOWS it (mind/affordance.py, the duty gate; Actor v2, C05):
    options tagged ``affordance_tag`` carry ``cost_note`` (or the law's belief_text when it is
    empty). 'forbid' and 'cost' both add the note and neither removes an option — a law is a cost
    a person weighs; the world answers when it is broken."""

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
    seat: str | None = Field(default=None, pattern=SLUG_PATTERN, description="P10: a SEAT — an office "
                             "worldgen fills with a person of its own in the faction's settlement (WG-27; "
                             "group_members.role = the seat). The first leader always leads.")
    age: tuple[int, int] | None = Field(default=None, description="P10: the seat holder's age range "
                                        "(the Front Man is about forty by design).")


class EnclaveDef(Strict):
    """P10 (world.factions FAC-01): the faction lives sealed underground — one settlement of many
    thousands behind one locked gate."""
    population: tuple[int, int]
    zone_kinds: list[str] = Field(min_length=1, description="Where it stands, in preference order.")
    name: str = Field(min_length=2, description="The place's name as outsiders know it.")
    gate: str = Field(min_length=2, description="The one way in, as a portal name.")
    description: str = Field(min_length=10)


class CouncilDef(Strict):
    """P10 (FAC-02): the seats that meet, and when — every ``every_days`` days at ``hour``."""
    seats: list[str] = Field(min_length=1)
    every_days: int = Field(default=7, ge=1)
    hour: int = Field(default=20, ge=0, le=23)
    hours: float = Field(default=2.0, gt=0)


class DeconDef(Strict):
    """P10 (FAC-04): what the faction does when one of its own is killed by a human hand."""
    team: int = Field(default=5, ge=1, description="Five Ghosts fit in a van.")
    women_share: float = Field(default=0.35, ge=0, le=1)
    occupation: str = Field(min_length=2)
    appearance: str = Field(min_length=10, description="How a team member looks (their dossier).")
    goal: str = Field(min_length=10, description="The team's goal on screen; {target} = how the killer is described.")
    mark: str = Field(min_length=10, description="The trace left on a body they leave as a warning.")


class FactionBehaviour(Strict):
    """P10 (world.factions): what the faction DOES beyond its settlements and operations. Every block
    is optional; the Ghosts have all four."""
    enclave: EnclaveDef | None = None
    council: CouncilDef | None = None
    route_watch: bool = False
    decon: DeconDef | None = None


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
    behaviour: FactionBehaviour = Field(default_factory=FactionBehaviour)
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


class QuipList(Strict):
    """P10: the loading bar's lines (service.progress PROG-06/07; CNT-16). Keys: a progress plan
    ('turn'), a phase ('turn.minds') or a sub-phase ('turn.minds.decide'); several packs' lists
    for one key are added together."""
    schema_id: Literal["as.quips.v1"] = Field(alias="schema", default="as.quips.v1")
    id: str = Field(pattern=SLUG_PATTERN)
    lines: dict[str, list[str]] = Field(min_length=1)
    model_config = Strict.model_config | {"populate_by_name": True}


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
