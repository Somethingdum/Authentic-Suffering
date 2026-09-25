"""Actor and PC dossier contracts (docs/as/09_CONTENT_PACKS.md §Dossiers).

Merges three sources of law:
  * AS Rebuild Plan §6.3 (IDENTITY/BODY/CAPABILITY/MOTIVE STACK/PERSONA/SOCIAL/LIFE/MIND/VOICE)
  * Codex Master Guide §14-15 (voice exemplars at three pressures, would-never-say,
    writer's notes, per-trait definitions, contradiction, decision stack, silence, knowledge layer)
  * Codex Master Guide §61 Part XIV (PC card + worldgen bias block)

Every list with a ``min_length`` is a *mandatory specificity* rule: a dossier that describes a
category instead of a person fails validation (rule CNT-10).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from .common import (
    Cohort,
    MoralTag,
    OpenLoopKind,
    RelationAxis,
    SkillDomain,
    Special,
    Strict,
    Verb,
)

ContentRef = str  # "<pack_id>:<kind>/<slug>", e.g. "core:actor/mara_voss"
SLUG_PATTERN = r"^[a-z0-9][a-z0-9_]{1,63}$"


class Identity(Strict):
    name: str = Field(min_length=1, max_length=80)
    aliases: list[str] = Field(default_factory=list, max_length=8)
    age: int = Field(ge=0, le=110)
    sex: Literal["female", "male", "other"]
    cohort: Cohort
    birthplace: str = Field(min_length=2)
    occupation_before: str = Field(min_length=2, description="What they did before the Fall (or as a child).")
    occupation_now: str = Field(min_length=2)
    one_line: str = Field(min_length=10, max_length=140)


class VisibleMark(Strict):
    """Something anyone can see on them: where and what — never how it came to be there (LOOK-01)."""

    where: str = Field(min_length=3, description="With its preposition: 'through the left eyebrow', 'across the "
                       "backs of both hands', 'behind the right ear'.")
    what: str = Field(min_length=3, description="'a pale crescent scar', 'a faded anchor tattoo'.")
    shows: Literal["close", "near", "far"] = Field(default="near", description="close: within 1.5 m; near: within "
                                                   "5 m; far: at any distance, when seen clearly.")


class OutfitPiece(Strict):
    """One piece of what they wear when they are first placed in the world (LOOK-02)."""

    item: ContentRef = Field(description="An item with a clothing block ('core:item/work_jacket'). Gear that is "
                             "worn — a holster, a pack — is starting_inventory's (CNT-17).")
    colour: str | None = Field(default=None, description="Overrides the item's colour word.")
    state: Literal["clean", "worn", "soiled", "torn"] = "worn"
    insignia: str | None = Field(default=None, description="A mark on it anyone can see: 'a painted white smile on "
                                 "the left shoulder'.")


class Looks(Strict):
    """What anyone can see of a person: visible facts only, no history and no inner life (LOOK-01).
    The prose fields of Appearance stay for the person's own identity card."""

    hair_colour: str = Field(description="'dark blonde', 'grey'; '' when bald or shaved.")
    hair_length: Literal["bald", "shaved", "cropped", "short", "collar", "shoulder", "long"]
    hair_style: str = Field(default="", description="'in a tight low bun', 'matted', 'slicked back'.")
    facial_hair: Literal["none", "stubble", "mustache", "beard", "full_beard"] = "none"
    facial_hair_words: str = Field(default="", description="'a waxed, curled mustache'; '' = the plain word.")
    eye_colour: str
    complexion: str = Field(pattern=r"\bskin\b", description="What the skin looks like, as a phrase that names "
                            "it: 'pale skin freckled across the nose', 'deep brown skin'.")
    marks: list[VisibleMark] = Field(default_factory=list)
    outfit: list[OutfitPiece] = Field(default_factory=list)


class Appearance(Strict):
    height_cm: int = Field(ge=45, le=230)
    mass_kg: int = Field(ge=3, le=250)
    build: str
    hair: str
    eyes: str
    skin: str
    distinguishing_marks: list[str] = Field(min_length=1)
    clothing_usual: str
    movement_under_stress: str = Field(min_length=10)
    habit_gesture: str = Field(min_length=5)
    relation_to_appearance: str = Field(min_length=5)
    looks: Looks | None = Field(default=None, description="F1a: the structured, visible version of the fields above "
                                "(what OTHER people see; LOOK-01). None: others see height and build only (CNT-17 warns).")


class Skill(Strict):
    domain: SkillDomain
    rank: int = Field(ge=1, le=3, description="1 trained, 2 skilled, 3 expert. Absent domain = rank 0.")
    evidence: str = Field(min_length=10, description="Where it came from. A skill with no history is a category.")


class TrainedResponse(Strict):
    cue: str = Field(description="Cue tag from the cue registry, e.g. 'gunshot_close', 'grabbed_from_behind'.")
    verb: Verb
    note: str = ""


class Capability(Strict):
    special: Special
    skills: list[Skill] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list, description="Capability tags; each gives +2 on checks listing it.")
    trained_responses: list[TrainedResponse] = Field(default_factory=list)
    literacy: int = Field(ge=0, le=3)
    tech_literacy: int = Field(ge=0, le=3)
    resolve_trait_mod: int = Field(default=0, ge=-2, le=2)

    @field_validator("skills")
    @classmethod
    def _unique_domains(cls, v: list[Skill]) -> list[Skill]:
        seen = [s.domain for s in v]
        if len(seen) != len(set(seen)):
            raise ValueError("a skill domain may appear once")
        return v


class MoralLine(Strict):
    will: list[str] = Field(min_length=1)
    wont: list[str] = Field(min_length=1)
    wont_tags: list[MoralTag] = Field(default_factory=list, description="Machine-checkable subset of 'wont'.")


class MotiveStack(Strict):
    """IRONCLAD Step 5 motive stack, verbatim shape."""

    motive: str = Field(min_length=10)
    method: str = Field(min_length=10)
    moral_line: MoralLine
    inner_conflict: str = Field(min_length=10)
    past_wound: str = Field(min_length=10)
    signature_behaviour: str = Field(min_length=10)
    risk_threshold: int = Field(ge=1, le=10)
    risk_text: str = Field(min_length=5)
    resource_constraints: str = Field(min_length=5)


class PublicPersona(Strict):
    shown_traits: list[str] = Field(min_length=1)
    claimed_history: str
    presented_affiliation: str


class PrivatePersona(Strict):
    true_goals: list[str] = Field(min_length=1)
    concealed_history: str
    real_affiliation: str


class Persona(Strict):
    public: PublicPersona
    private: PrivatePersona


class TraitDef(Strict):
    """CMG §15.1: every trait individually defined."""

    tag: str
    manifests: str = Field(min_length=10)
    triggers: str = Field(min_length=5)
    causes: str = Field(min_length=5)
    costs: str = Field(min_length=5)
    example: str = Field(min_length=10)


class Contradiction(Strict):
    belief_a: str
    belief_b: str
    a_wins_when: str
    b_wins_when: str


class DecisionStack(Strict):
    layers: list[str] = Field(min_length=4, description="Highest priority first.")
    inversion_conditions: list[str] = Field(min_length=1)
    past_example: str = Field(min_length=20)


class Silence(Strict):
    goes_quiet_when: list[str] = Field(min_length=2)
    body_when_silent: str
    refuses_to_discuss: list[str] = Field(default_factory=list)
    comfortable_vs_uncomfortable: str


class KnowledgeSeed(Strict):
    """Seed beliefs; converted to claim_holdings with provenance at worldgen (WG6)."""

    knows: list[str] = Field(default_factory=list)
    does_not_know: list[str] = Field(default_factory=list)
    knows_but_hides: list[str] = Field(default_factory=list)
    cues: list[str] = Field(
        default_factory=list,
        description="Belief cues this person starts with (cue registry ids, CNT-05), e.g. "
        "'knows_headshot_rule'. Each becomes a lessons row (confidence 3) at worldgen or scenario "
        "load; a cue is 'held' when a lessons row carries it with confidence >= 1 (AFF-10).")


class VoiceExemplars(Strict):
    low_stakes: str = Field(min_length=5)
    under_pressure: str = Field(min_length=5)
    at_the_limit: str = Field(min_length=5)


class Voice(Strict):
    capsule: str = Field(min_length=20, max_length=500)
    speech_tendencies: list[str] = Field(min_length=2)
    exemplars: VoiceExemplars
    would_never_say: list[str] = Field(min_length=3)
    profanity: Literal["none", "rare", "frequent", "constant"]
    dialect_notes: str = ""


class RelationSeed(Strict):
    target: ContentRef
    kind: Literal[
        "parent", "child", "sibling", "spouse", "partner", "friend", "rival", "mentor",
        "student", "debtor", "creditor", "enemy", "employer", "employee", "ex_partner",
        "comrade", "acquaintance",
    ] = Field(description="What the TARGET is to this person: 'child' = the target is my child, "
              "'employer' = the target employs me. Packets render it as 'your <kind>'.")
    axes: dict[RelationAxis, int] = Field(default_factory=dict)
    history: str = Field(min_length=10)


class FactionMembership(Strict):
    faction: ContentRef
    role: str
    standing: int = Field(ge=-3, le=3)
    since: str


class Secret(Strict):
    content: str = Field(min_length=10)
    who_knows: list[ContentRef] = Field(default_factory=list)
    exposure_consequence: str = Field(min_length=5)


class RoutineStep(Strict):
    start_hh: int = Field(ge=0, le=23)
    end_hh: int = Field(ge=0, le=24)
    activity: str
    place_hint: str = ""


class Social(Strict):
    household_role: str = ""
    relations: list[RelationSeed] = Field(default_factory=list)
    dependents: list[ContentRef] = Field(default_factory=list)
    guardians: list[ContentRef] = Field(default_factory=list)
    memberships: list[FactionMembership] = Field(default_factory=list)


class Life(Strict):
    aspiration: str = Field(min_length=5)
    current_project: str = Field(min_length=5)
    routine: list[RoutineStep] = Field(default_factory=list)
    obligations: list[str] = Field(default_factory=list)
    hopes: list[str] = Field(default_factory=list)
    fears: list[str] = Field(min_length=1)
    secrets: list[Secret] = Field(default_factory=list)


class Disposition(Strict):
    archetype_prior: Literal[
        "predator", "survivor", "opportunist", "civilized",
        "hider", "wanderer", "fool", "crazed", "groupie",
    ]
    toward_strangers: Literal["hostile", "wary", "neutral", "warm"]
    encounter_default: str = Field(min_length=10, description="Default action when first detecting a stranger.")


class StartingLoop(Strict):
    kind: OpenLoopKind
    text: str = Field(min_length=5)
    subject: ContentRef | None = None
    strength: int = Field(default=2, ge=0, le=3)


class ItemGrant(Strict):
    item: ContentRef
    qty: int = Field(default=1, ge=1)
    slot: Literal["hand_l", "hand_r", "worn", "pack", "pocket"] = "pack"
    container: str | None = Field(default=None, description="Local label of another grant that holds this one.")
    label: str | None = Field(default=None, description="Local label so other grants can reference this one.")
    props: dict = Field(default_factory=dict)


class Temper(Strict):
    """How this person breaks (H1, TEMPER-01; the owner: "everybody has a breaking point"). People are
    smart, but human smart: pride, fear, grief and grudges weigh as much as reasons do."""

    fuse: int = Field(default=3, ge=1, le=5, description="How much provocation it takes before they snap: "
                      "1 = a hair trigger, 5 = a saint on a good day (mind.temper: the breaking point is fuse x 2 "
                      "heat, lower the more strained they are).")
    outlet: Literal["fists", "words", "cold", "flight", "tears", "wrath"] = Field(
        default="words", description="How they blow when they do: swing at whoever pushed them; tear into them "
        "out loud; go ice-cold and cut them off; storm off; break down; (D-102, Willis) hurt them with what they "
        "can do — no reach, no hands, nothing stops it (mind.temper TEMPER-06).")
    grudge: int = Field(default=1, ge=0, le=3, description="How long they carry it: 0 = over it by the evening, "
                        "3 = never forgets.")
    pet_peeves: list[str] = Field(default_factory=list, description="Small things that get under their skin out "
                                  "of all proportion — fair or not: 'people who whistle', 'being called kid'.")
    cools_down_by: str = Field(default="", description="What actually settles them: 'a cigarette alone', "
                               "'hitting something that isn't a person', 'Eli asleep and safe'.")
    shrugs_off: list[str] = Field(default_factory=list, description="D-102 (TEMPER-10): provocation kinds that give "
                                  "them no heat at all ('struck', 'insulted', ...) — except from someone they gave a "
                                  "gift: that is ingratitude.")
    rages_at: list[Literal["worshipped", "wished_upon"]] = Field(default_factory=list, description="D-102 "
                                  "(TEMPER-10): what sends them straight past their breaking point: being worshipped; "
                                  "being asked for wonders by someone who has seen what they can do (the first time "
                                  "from each person is let pass, with a correction).")


class ActorDossier(Strict):
    schema_id: Literal["as.actor.v1"] = Field(alias="schema", default="as.actor.v1")
    id: str = Field(pattern=SLUG_PATTERN)
    generation: Literal["authored", "generated", "imported", "cheat"] = "authored"
    identity: Identity
    appearance: Appearance
    capability: Capability
    motive: MotiveStack
    persona: Persona
    traits: list[TraitDef] = Field(min_length=2)
    contradictions: list[Contradiction] = Field(min_length=1)
    decision_stack: DecisionStack
    silence: Silence
    knowledge: KnowledgeSeed
    voice: Voice
    temper: Temper | None = Field(default=None, description="H1: how this person breaks (None: the default "
                                  "Temper — a middling fuse that comes out in words).")
    social: Social
    life: Life
    disposition: Disposition
    starting_loops: list[StartingLoop] = Field(default_factory=list)
    starting_inventory: list[ItemGrant] = Field(default_factory=list)
    days_since_fall_range: tuple[int, int] | None = Field(
        default=None,
        description="WG-34: the world ages this person's recorded age, cohort and history fit, as "
        "(min, max) days since the Fall. Worldgen places an authored person only when the world's "
        "days_since_fall is inside it, and for a PC it narrows the draw (and the era choices). "
        "None = fits any world age.")
    writers_notes: str | None = Field(default=None, description="Human-only. The model never writes this field.")
    depth_reference: str | None = Field(default=None, description="Long-form markdown, pulled only on demand.")
    tags: list[str] = Field(default_factory=list)

    model_config = Strict.model_config | {"populate_by_name": True}

    @model_validator(mode="after")
    def _fall_range(self) -> "ActorDossier":
        r = self.days_since_fall_range
        if r is not None and not (1 <= r[0] <= r[1]):
            raise ValueError("days_since_fall_range must be (min, max) with 1 <= min <= max")
        return self


class PCCard(Strict):
    display_name: str
    one_line_identity: str = Field(min_length=10, max_length=120)
    pc_card_survival: str = Field(min_length=10, max_length=120)
    pc_selection_note: str = Field(min_length=10, max_length=160)


class WorldgenBias(Strict):
    """CMG §61 Part XIV. Decimal fractions in [-1, 1]; 0.0 = no bias."""

    climate_heat: float = Field(default=0.0, ge=-1, le=1)
    climate_moisture: float = Field(default=0.0, ge=-1, le=1)
    atmo_visibility: float = Field(default=0.0, ge=-1, le=1)
    instability: float = Field(default=0.0, ge=-1, le=1)
    faction_density: float = Field(default=0.0, ge=-1, le=1)
    social_order: float = Field(default=0.0, ge=-1, le=1)
    survivor_mentality: float = Field(default=0.0, ge=-1, le=1)
    faction_fragmentation: float = Field(default=0.0, ge=-1, le=1)
    faction_relations: float = Field(default=0.0, ge=-1, le=1)
    atrocity_capacity: float = Field(default=0.0, ge=-1, le=1)
    mystery: float = Field(default=0.0, ge=-1, le=1)
    ritual_intensity: float = Field(default=0.0, ge=-1, le=1)
    subtle_anomaly: float = Field(default=0.0, ge=-1, le=1)
    lost_knowledge: float = Field(default=0.0, ge=-1, le=1)
    wildcard_level: float = Field(default=0.0, ge=-1, le=1)


SurvivalMethod = Literal[
    "mobility_scavenging_barter",
    "combat",
    "stealth_evasion",
    "information_social",
    "faction_protection",
]


class PlausibilityGate(Strict):
    """Conditions use the tiny expression language in world/worldgen/conditions.py:
    ``<param> <op> <int>`` joined by `` and ``; ``entity_type = faction`` is allowed.
    ``pass_any`` is OR-joined, ``hard_fail_all`` is AND-joined inside one string."""

    method: SurvivalMethod
    pass_any: list[str] = Field(min_length=1)
    hard_fail_all: str | None = None
    patch_on_fail: str = ""


class StartConstraints(Strict):
    start_trust_range: tuple[int, int] = (4, 7)
    start_relationship_default: Literal["ally", "neutral", "suspicious", "indebted", "enemy", "none"] = "neutral"
    faction_present_preferred: Literal["yes", "no", "either"] = "either"


class Recap(Strict):
    origin_tag: str | None = None
    survival_pattern: str | None = None
    known_reputation: str | None = None
    formative_incident_1: str | None = None
    formative_incident_2: str | None = None
    unresolved_complication: str | None = None
    open_ambiguity: str | None = None
    provisional: list[str] = Field(default_factory=list, description="Names of recap fields not yet confirmed canon.")


class BehaviorLaw(Strict):
    """CMG §54 localized behavior law. Used by SAY_MY_WAY (the Dialogue Seed Protocol) and by the
    PC's manner colouring (SYM-02): how this person carries an idea into the world. Each field is
    one or two sentences about THIS person, never a category."""

    approach: str = Field(min_length=10, description="How they approach strangers, authority, attraction, suspicion, fear, physically imposing people.")
    topic_handling: str = Field(min_length=10, description="How they raise needs, accusations, plans, shameful topics, requests, warnings.")
    risk_flight_escalation: str = Field(min_length=10, description="What makes them push, hesitate, bail, commit, posture, or flee too early or too late.")
    plan_carry: str = Field(min_length=10, description="How well they carry abstract plans, practical plans, warnings, politics, logistics.")
    distortion: str = Field(min_length=10, description="How they ruin good ideas: overtalking, underexplaining, sounding rude, freezing, the wrong half.")
    pressure: str = Field(min_length=10, description="How they change under embarrassment, crowding, confinement, attraction, injury, sleep debt, humiliation.")
    knowledge_boundary: str = Field(min_length=10, description="What they can know, suspect, misread, or never infer cleanly.")
    performance: str = Field(min_length=10, description="What mocking, joking, flirting, fake familiarity and post-adrenaline behaviour look like for them.")


class PCDossier(ActorDossier):
    """A playable character. Same record as any Actor (L12) plus selection/worldgen fields.

    The PC may omit motive and persona (the player supplies them by playing)."""

    schema_id: Literal["as.pc.v1"] = Field(alias="schema", default="as.pc.v1")  # type: ignore[assignment]
    motive: MotiveStack | None = None  # type: ignore[assignment]
    persona: Persona | None = None  # type: ignore[assignment]
    card: PCCard
    primary_survival_method: SurvivalMethod
    faction_start_type: Literal["always_in_faction", "usually_adjacent", "outsider_tied", "outsider_solo"]
    worldgen_bias: WorldgenBias = Field(default_factory=WorldgenBias)
    plausibility_gate: PlausibilityGate
    start_constraints: StartConstraints = Field(default_factory=StartConstraints)
    locked_start_facts: list[str] = Field(default_factory=list)
    faction_standing: list[FactionMembership] = Field(default_factory=list, description="Relations to factions without membership, e.g. protected external asset.")
    recap: Recap = Field(default_factory=Recap)
    behavior_law: BehaviorLaw | None = Field(default=None, description="CMG §54; strongly recommended for every authored PC.")

    @model_validator(mode="after")
    def _card_name_matches(self) -> "PCDossier":
        if self.card.display_name.strip().lower() != self.identity.name.strip().lower():
            raise ValueError("card.display_name must equal identity.name")
        return self
