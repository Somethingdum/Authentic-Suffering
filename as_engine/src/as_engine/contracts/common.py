"""Enumerations and small value types used everywhere.

Every enum value is lowercase snake_case text so that it serialises the same way in
SQLite, JSON, prompts and the UI protocol.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    """Base for contract models: unknown fields are errors, values are validated on assignment."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True, frozen=False)


# ---------------------------------------------------------------------------
# Model lanes and call classes
# ---------------------------------------------------------------------------


class Lane(StrEnum):
    A = "A"  # desktop, Nemotron Cascade 2 30B-A3B: deep cognition + narration
    B = "B"  # laptop, Nemotron 3.5 Lightning 30B-A3B: fast structured calls, audits


class CallClass(StrEnum):
    INTAKE = "intake"
    ACTOR_COGNITION = "actor_cognition"
    ACTOR_REACTION = "actor_reaction"
    INTENT_REPAIR = "intent_repair"
    WRITEBACK = "writeback"
    PORTRAYAL_AUDIT = "portrayal_audit"
    NARRATION = "narration"
    RENDER_LINT = "render_lint"
    RUMOUR_DISTORT = "rumour_distort"
    CASCADE_ADVISORY = "cascade_advisory"
    GUIDE = "guide"
    REFLECTION = "reflection"
    SCENE_SUMMARY = "scene_summary"
    RECAP = "recap"
    SAY_MY_WAY = "say_my_way"
    WORLDGEN_HISTORY = "worldgen_history"
    WORLDGEN_ACTOR = "worldgen_actor"
    WORLDGEN_OPENING = "worldgen_opening"
    DOSSIER_INTAKE = "dossier_intake"
    PC_QUICKMAKE = "pc_quickmake"
    CHEAT_PERSONA = "cheat_persona"
    CHEAT_INTERPRET = "cheat_interpret"   # P12, D-103: plain-words cheats (cheats.interpret)
    WILLIS_ROAST = "willis_roast"         # P12, D-105: Willis at every death (service.death.roast)
    THE_VOICE = "the_voice"               # P12, D-106: the Voice before and after a death (service.voice)
    DOOM_GUARD = "doom_guard"             # P12, D-106: the doomed cannot tell (turn.intake DOOM-07)
    PROBE = "probe"


# ---------------------------------------------------------------------------
# Perception
# ---------------------------------------------------------------------------


class Fidelity(StrEnum):
    EXACT = "exact"
    PARTIAL = "partial"
    TONE_ONLY = "tone_only"
    NONE = "none"
    VISUAL_ONLY = "visual_only"  # beliefs formed from sight alone; never returned by acoustics


class Channel(StrEnum):
    VISUAL = "visual"
    AUDITORY = "auditory"
    SPEECH = "speech"
    TACTILE = "tactile"
    OLFACTORY = "olfactory"
    VIBRATION = "vibration"


class Awareness(StrEnum):
    ALERT = "alert"
    AWAKE = "awake"
    DROWSY = "drowsy"
    ASLEEP = "asleep"
    UNCONSCIOUS = "unconscious"
    DEAD = "dead"


class Posture(StrEnum):
    STANDING = "standing"
    CROUCHED = "crouched"
    SITTING = "sitting"
    LYING = "lying"
    PRONE = "prone"


class LOD(StrEnum):
    HOT = "hot"  # model call with thinking (lane A preferred)
    WARM = "warm"  # model call, thinking off
    COLD = "cold"  # deterministic plan continuation, no call


# ---------------------------------------------------------------------------
# Action
# ---------------------------------------------------------------------------


class Verb(StrEnum):
    MOVE = "move"
    MANIPULATE = "manipulate"
    ATTACK = "attack"
    ESCAPE = "escape"
    SPEAK = "speak"
    SIGNAL = "signal"
    TREAT = "treat"
    SEARCH = "search"
    CONTINUE_TASK = "continue_task"
    GUARD = "guard"
    OBSERVE = "observe"
    WAIT = "wait"
    TAKE_COVER = "take_cover"
    HIDE = "hide"
    FLEE = "flee"
    SURRENDER = "surrender"


class CheckBand(StrEnum):
    CLEAN = "clean"  # margin >= +3
    COST = "cost"  # margin 0..+2
    FAIL = "fail"  # margin -1..-2
    BREAK = "break"  # margin <= -3


class UtteranceForm(StrEnum):
    REQUEST = "request"
    DEMAND = "demand"
    ORDER = "order"
    THREAT = "threat"
    OFFER = "offer"
    QUESTION = "question"
    STATEMENT = "statement"


class Standing(StrEnum):
    VALID_ORDER = "valid_order"
    CLAIMED_AUTHORITY = "claimed_authority"
    PEER = "peer"
    STRANGER = "stranger"
    SUBORDINATE = "subordinate"
    HOSTILE = "hostile"


class ResponseClass(StrEnum):
    """How an Actor's *chosen action* relates to a request it perceived.

    Computed by code after cognition (mind/firewall.py). Never a model output field.
    """

    READY_COMPLIANCE = "ready_compliance"
    RELUCTANT_COMPLIANCE = "reluctant_compliance"
    COUNTER_OFFER = "counter_offer"
    REFUSAL = "refusal"
    ENTRENCHED_REFUSAL = "entrenched_refusal"
    FALSE_COMPLIANCE = "false_compliance"      # never produced since AC09 (kept so old ledgers read)
    COERCED_COMPLIANCE = "coerced_compliance"
    DEFERRED_ASSENT = "deferred_assent"        # AC09: "yes, after I finish this" — a conditional yes
    CLARIFYING = "clarifying"                  # AC09: "okay, what exactly do you mean?" — not an answer yet
    PREPARING = "preparing"                    # AC09: a yes and a step toward it
    UNRESOLVED_ASSENT = "unresolved_assent"    # AC09: a yes and something else, reason unknown — never a lie by itself


class Volume(StrEnum):
    WHISPER = "whisper"
    LOW = "low"
    NORMAL = "normal"
    RAISED = "raised"
    SHOUT = "shout"


class MoralTag(StrEnum):
    KILL_HUMAN = "kill_human"
    KILL_CHILD = "kill_child"
    HARM_DEPENDENT = "harm_dependent"
    ABANDON_DEPENDENT = "abandon_dependent"
    ABANDON_POST = "abandon_post"
    LEAVE_WOUNDED = "leave_wounded"
    STEAL = "steal"
    BETRAY_GROUP = "betray_group"
    TORTURE = "torture"
    EXECUTE_PRISONER = "execute_prisoner"
    ATTACK_UNARMED = "attack_unarmed"
    BREAK_PROMISE = "break_promise"
    EAT_HUMAN = "eat_human"
    LIE_TO_FAMILY = "lie_to_family"
    FEED_TO_DEAD = "feed_to_dead"   # H1: shove someone to the dead, or leave them for them, to save yourself
    END_OWN_LIFE = "end_own_life"   # D-107: the one thing left to someone who can't take any more


# ---------------------------------------------------------------------------
# Bodies
# ---------------------------------------------------------------------------


class WoundSeverity(StrEnum):
    MINOR = "minor"
    SIGNIFICANT = "significant"
    SEVERE = "severe"
    CATASTROPHIC = "catastrophic"


class WoundType(StrEnum):
    CUT = "cut"
    STAB = "stab"
    GUNSHOT = "gunshot"
    BITE = "bite"
    SCRATCH = "scratch"
    BLUNT = "blunt"
    BURN = "burn"
    FRACTURE = "fracture"
    CRUSH = "crush"


class Anatomy(StrEnum):
    HEAD = "head"
    NECK = "neck"
    CHEST = "chest"
    ABDOMEN = "abdomen"
    BACK = "back"
    ARM_L = "arm_l"
    ARM_R = "arm_r"
    HAND_L = "hand_l"
    HAND_R = "hand_r"
    LEG_L = "leg_l"
    LEG_R = "leg_r"
    FOOT_L = "foot_l"
    FOOT_R = "foot_r"


ANATOMY_GROUP: dict[str, str] = {
    "head": "head", "neck": "neck", "chest": "torso", "abdomen": "torso", "back": "torso",
    "arm_l": "arm", "arm_r": "arm", "hand_l": "hand", "hand_r": "hand",
    "leg_l": "leg", "leg_r": "leg", "foot_l": "foot", "foot_r": "foot",
}
LIMB_GROUPS: frozenset[str] = frozenset({"arm", "hand", "leg", "foot"})
ANATOMY_SIDE: dict[str, str] = {"arm_l": "l", "hand_l": "l", "leg_l": "l", "foot_l": "l",
                                "arm_r": "r", "hand_r": "r", "leg_r": "r", "foot_r": "r"}
# How prose names a body part and a wound's size (percepts, packets, narration all use these).
ANATOMY_WORDS: dict[str, str] = {
    "head": "head", "neck": "neck", "chest": "chest", "abdomen": "belly", "back": "back",
    "arm_l": "left arm", "arm_r": "right arm", "hand_l": "left hand", "hand_r": "right hand",
    "leg_l": "left leg", "leg_r": "right leg", "foot_l": "left foot", "foot_r": "right foot",
}
SEVERITY_WORDS: dict[str, str] = {"minor": "a shallow", "significant": "a", "severe": "a deep",
                                  "catastrophic": "a terrible"}


class BodyKind(StrEnum):
    HUMAN = "human"
    INFECTED = "infected"
    LURKER = "lurker"
    ANIMAL = "animal"


class AgeBand(StrEnum):
    INFANT = "infant"  # 0-2
    CHILD = "child"  # 3-11
    PRETEEN = "preteen"  # 12-14
    TEEN = "teen"  # 15-19
    ADULT = "adult"  # 20-59
    ELDER = "elder"  # 60+


def age_band_for(age_years: int) -> AgeBand:
    """Canonical age -> band mapping (docs/as/05_ACTORS.md §Demographics)."""
    if age_years <= 2:
        return AgeBand.INFANT
    if age_years <= 11:
        return AgeBand.CHILD
    if age_years <= 14:
        return AgeBand.PRETEEN
    if age_years <= 19:
        return AgeBand.TEEN
    if age_years <= 59:
        return AgeBand.ADULT
    return AgeBand.ELDER


class Cohort(StrEnum):
    PRE_FALL_ADULT = "pre_fall_adult"
    FALL_CHILD = "fall_child"
    POST_FALL_BORN = "post_fall_born"


class SkillDomain(StrEnum):
    FIREARMS = "firearms"
    MELEE = "melee"
    BRAWLING = "brawling"
    ATHLETICS = "athletics"
    STEALTH = "stealth"
    MEDICINE = "medicine"
    MECHANICS = "mechanics"
    ELECTRONICS = "electronics"
    SCAVENGING = "scavenging"
    SURVIVAL = "survival"
    TRACKING = "tracking"
    NAVIGATION = "navigation"
    PERSUASION = "persuasion"
    DECEPTION = "deception"
    INTIMIDATION = "intimidation"
    LEADERSHIP = "leadership"
    TRADE = "trade"
    COOKING = "cooking"
    FARMING = "farming"
    BUILDING = "building"
    DRIVING = "driving"
    INFECTED_LORE = "infected_lore"
    CHILDCARE = "childcare"
    ANIMAL_HANDLING = "animal_handling"


class RelationAxis(StrEnum):
    TRUST = "trust"  # -3 .. +3
    FEAR = "fear"  # 0 .. 3
    RESPECT = "respect"  # -3 .. +3
    AFFECTION = "affection"  # -3 .. +3 ("attachment" in the rebuild plan)
    RESENTMENT = "resentment"  # 0 .. 3
    OBLIGATION = "obligation"  # -3 .. +3 (positive: I owe them; negative: they owe me)


RELATION_AXIS_RANGE: dict[RelationAxis, tuple[int, int]] = {
    RelationAxis.TRUST: (-3, 3),
    RelationAxis.FEAR: (0, 3),
    RelationAxis.RESPECT: (-3, 3),
    RelationAxis.AFFECTION: (-3, 3),
    RelationAxis.RESENTMENT: (0, 3),
    RelationAxis.OBLIGATION: (-3, 3),
}


class OpenLoopKind(StrEnum):
    PROMISE_MADE = "promise_made"
    PROMISE_OWED = "promise_owed"
    DEBT_OWING = "debt_owing"
    DEBT_OWED = "debt_owed"
    GRUDGE = "grudge"
    GOAL = "goal"
    DESIRE = "desire"
    FEAR = "fear"
    QUESTION = "question"
    PLAN = "plan"
    SECRET_KEPT = "secret_kept"


class LoopStatus(StrEnum):
    OPEN = "open"
    FULFILLED = "fulfilled"
    BROKEN = "broken"
    ABANDONED = "abandoned"
    EXPIRED = "expired"


# ---------------------------------------------------------------------------
# World generation
# ---------------------------------------------------------------------------


class Difficulty(StrEnum):
    BITCH_MODE = "bitch_mode"
    EASY = "easy"
    NORMAL = "normal"
    REALISM = "realism"
    ACTUALLY_HELL = "actually_hell"
    FUCK_YOU = "fuck_you"


class Era(StrEnum):
    EARLY = "early"
    ESTABLISHED = "established"
    MATURE = "mature"


class WorldDetail(StrEnum):
    GOTTA_GO_TO_WORK_SOON = "gotta_go_to_work_soon"
    QUICK_LOOK = "quick_look"
    STANDARD = "standard"
    SETTLE_IN = "settle_in"
    NOT_USING_MY_LAPTOP_TODAY = "not_using_my_laptop_today"


class Special(Strict):
    """Fallout-style SPECIAL, 1..10 each (lore §4 scale)."""

    S: int = Field(ge=1, le=10)
    P: int = Field(ge=1, le=10)
    E: int = Field(ge=1, le=10)
    C: int = Field(ge=1, le=10)
    I: int = Field(ge=1, le=10)  # noqa: E741  (canonical letter)
    A: int = Field(ge=1, le=10)
    L: int = Field(ge=1, le=10)


def attr_mod(value: int) -> int:
    """SPECIAL value -> check modifier. 1-2:1, 3-4:2, 5-6:3, 7-8:4, 9-10:5 (07_RULES.md §Checks)."""
    if not 1 <= value <= 10:
        raise ValueError(f"SPECIAL value out of range: {value}")
    return (value + 1) // 2
