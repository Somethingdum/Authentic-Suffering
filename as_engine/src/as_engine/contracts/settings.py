"""Configuration contracts.

* ``EngineConfig``  — install-wide (as_config.yaml): model lanes, paths, rules tunables.
* ``RunSettings``   — chosen per run in the New Life wizard; stored in the run's ``meta`` table.
* ``RulesConfig``   — every tunable number in the game. Values marked [SAND] are engineering
  estimates that a named benchmark (tools/as/bench.py) is expected to replace. Tests that depend
  on a number read it from ``RulesConfig()`` defaults, never from a literal, unless the test is
  specifically pinning the default.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import CallClass, Difficulty, Era, Lane, Strict, WorldDetail


# ---------------------------------------------------------------------------
# Lanes
# ---------------------------------------------------------------------------


class LaneConfig(Strict):
    name: str
    base_url: str = "http://localhost:1234/v1"
    model: str = ""
    api_key: str = "lm-studio"
    max_concurrency: int = Field(default=1, ge=1, le=8)
    request_timeout_s: float = Field(default=240.0, gt=0)
    thinking_mode: Literal["native", "system_no_think", "chat_template_kwargs", "prefill_empty_think", "none"] = "native"
    structured_mode: Literal["json_schema", "prompt_only"] = "json_schema"
    structured_with_thinking: Literal["supported", "unsupported", "unknown"] = "unknown"


def default_lanes() -> dict[Lane, LaneConfig]:
    return {
        Lane.A: LaneConfig(name="Storyteller brain (desktop) — Nemotron Cascade 2 30B-A3B",
                           model="nemotron-cascade-2-30b-a3b"),
        Lane.B: LaneConfig(name="Fast brain (laptop) — Nemotron 3.5 Lightning 30B-A3B",
                           model="nvidia-nemotron-3.5-lightning-30b-a3b"),
    }


class CallRegime(Strict):
    lane: Lane
    temperature: float = Field(ge=0, le=2)
    top_p: float = Field(default=0.95, gt=0, le=1)
    max_tokens: int = Field(ge=16)
    thinking: bool = False
    deadline_s: float = Field(gt=0)


def default_regimes() -> dict[CallClass, CallRegime]:
    """Default lane + sampling per call class (08_LLM_CALLS.md §Call table)."""
    A, B = Lane.A, Lane.B
    return {
        CallClass.INTAKE: CallRegime(lane=B, temperature=0.2, max_tokens=400, deadline_s=30),
        CallClass.ACTOR_COGNITION: CallRegime(lane=B, temperature=0.7, max_tokens=500, deadline_s=45),
        CallClass.ACTOR_REACTION: CallRegime(lane=B, temperature=0.6, max_tokens=300, deadline_s=25),
        CallClass.INTENT_REPAIR: CallRegime(lane=B, temperature=0.1, max_tokens=300, deadline_s=20),
        CallClass.WRITEBACK: CallRegime(lane=B, temperature=0.5, max_tokens=700, deadline_s=45),
        CallClass.PORTRAYAL_AUDIT: CallRegime(lane=B, temperature=0.1, max_tokens=250, deadline_s=25),
        CallClass.NARRATION: CallRegime(lane=A, temperature=0.8, max_tokens=1400, deadline_s=90),
        CallClass.RENDER_LINT: CallRegime(lane=B, temperature=0.0, max_tokens=400, deadline_s=25),
        CallClass.RUMOUR_DISTORT: CallRegime(lane=B, temperature=0.7, max_tokens=200, deadline_s=20),
        CallClass.CASCADE_ADVISORY: CallRegime(lane=B, temperature=0.4, max_tokens=400, deadline_s=30),
        CallClass.GUIDE: CallRegime(lane=B, temperature=0.3, max_tokens=500, deadline_s=30),
        CallClass.REFLECTION: CallRegime(lane=B, temperature=0.6, max_tokens=700, deadline_s=60),
        CallClass.SCENE_SUMMARY: CallRegime(lane=B, temperature=0.3, max_tokens=500, deadline_s=40),
        CallClass.RECAP: CallRegime(lane=B, temperature=0.4, max_tokens=500, deadline_s=40),
        CallClass.SAY_MY_WAY: CallRegime(lane=B, temperature=0.8, max_tokens=200, deadline_s=20),
        CallClass.WORLDGEN_HISTORY: CallRegime(lane=A, temperature=0.8, max_tokens=2500, deadline_s=240, thinking=True),
        CallClass.WORLDGEN_ACTOR: CallRegime(lane=A, temperature=0.9, max_tokens=3500, deadline_s=240),
        CallClass.WORLDGEN_OPENING: CallRegime(lane=A, temperature=0.7, max_tokens=800, deadline_s=120, thinking=True),
        CallClass.DOSSIER_INTAKE: CallRegime(lane=A, temperature=0.2, max_tokens=6000, deadline_s=600),
        CallClass.PC_QUICKMAKE: CallRegime(lane=A, temperature=0.8, max_tokens=4000, deadline_s=300),
        CallClass.CHEAT_PERSONA: CallRegime(lane=B, temperature=0.9, max_tokens=150, deadline_s=15),
        CallClass.PROBE: CallRegime(lane=B, temperature=0.0, max_tokens=64, deadline_s=30),
    }


# ---------------------------------------------------------------------------
# Rules tunables
# ---------------------------------------------------------------------------


class CheckRules(Strict):
    tag_bonus: int = 2
    target_min: int = 1
    target_max: int = 9
    die_sides: int = 10
    clean_margin: int = 3
    fail_margin_min: int = -2  # margins -1..-2 are FAIL
    break_margin_max: int = -3


class AcousticRules(Strict):
    """07_RULES.md §Audibility. dB values are sound pressure level at 1 m."""

    exact_margin_db: float = 12.0  # [SAND] BENCH-07
    partial_margin_db: float = 5.0  # [SAND]
    tone_margin_db: float = 0.0
    attenuation_per_doubling_db: float = 6.0  # inverse-square in free field
    indoor_attenuation_per_doubling_db: float = 4.5  # reverberant rooms lose less
    open_portal_loss_db: float = 3.0
    material_loss_db: dict[str, float] = Field(default_factory=lambda: {
        "open_air": 0.0, "glass": 20.0, "drywall": 30.0, "wood": 25.0,
        "brick": 45.0, "concrete": 50.0, "metal": 40.0,
    })
    divided_attention_penalty_db: float = 4.0
    asleep_threshold_db: float = 55.0  # a sleeper registers only sounds whose received dB >= this
    drowsy_penalty_db: float = 8.0
    speech_db: dict[str, float] = Field(default_factory=lambda: {
        "whisper": 30.0, "low": 50.0, "normal": 60.0, "raised": 70.0, "shout": 85.0,
    })
    ambient_db_default: dict[str, float] = Field(default_factory=lambda: {
        "indoor_quiet": 30.0, "indoor_busy": 50.0, "street": 45.0, "wind": 55.0, "rain": 50.0, "storm": 65.0,
    })
    reaction_window_ms: tuple[int, int] = (150, 250)


class HarmRules(Strict):
    bleed_pct_per_min: dict[str, float] = Field(default_factory=lambda: {
        "minor": 0.05, "significant": 1.0, "severe": 3.0, "catastrophic": 12.0,
    })
    pressure_mult: float = 0.25
    tourniquet_mult: float = 0.02
    packing_mult: float = 0.1
    bandage_mult: float = 0.5
    suture_mult: float = 0.0  # minor and significant wounds only
    function_loss: dict[str, int] = Field(default_factory=lambda: {
        "minor": 0, "significant": 1, "severe": 2, "catastrophic": 2,
    })  # limbs only (ANATOMY_GROUP arm/hand/leg/foot); torso, head and neck wounds carry 0
    infected_false_death_at_blood_loss_pct: float = 60.0
    minor_clot_min: float = 10.0
    unconscious_at_blood_loss_pct: float = 30.0
    death_at_blood_loss_pct: float = 40.0
    impairment_from_blood_loss: list[tuple[float, int]] = Field(default_factory=lambda: [(15.0, 1), (25.0, 2)])
    impairment_max: int = 6
    pain_per_severity: dict[str, int] = Field(default_factory=lambda: {
        "minor": 0, "significant": 1, "severe": 2, "catastrophic": 3,
    })
    heal_days_per_severity: dict[str, float] = Field(default_factory=lambda: {
        "minor": 3, "significant": 14, "severe": 45, "catastrophic": 120,
    })


class NeedsRules(Strict):
    thirst_stage_every_h: float = 12.0  # [SAND] heat multiplies by (1 + (climate_heat-5)*0.08)
    hunger_stage_every_h: float = 84.0
    fatigue_stage_every_h: float = 8.0
    death_stage: int = 6
    impairment_at_stage: dict[int, int] = Field(default_factory=lambda: {3: 1, 4: 2, 5: 3})


class ResolveRules(Strict):
    base: int = 3
    divisor: int = 4  # max = base + floor((E + C) / divisor) + trait_mod
    drains: dict[str, int] = Field(default_factory=lambda: {
        "witness_bonded_death": 2, "sustained_fear_scene": 1, "humiliated_publicly": 1, "severe_pain": 1,
        "betrayed": 2, "first_kill": 1, "killed_child": 3, "starving_day": 1, "sleepless_night": 1,
        "lost_dependent": 3, "made_to_watch": 2, "coerced": 1,
    })
    recover_per_safe_night: int = 1
    recover_fulfilled_obligation: int = 1
    recover_protected_dependent: int = 1


class SchedulerRules(Strict):
    turn_budget_s: dict[str, float] = Field(default_factory=lambda: {"quick": 40.0, "balanced": 75.0, "deep": 150.0})
    reserve_narration_s: float = 25.0
    max_hot: dict[str, int] = Field(default_factory=lambda: {"quick": 1, "balanced": 2, "deep": 3})
    max_reaction_waves: int = 3
    estimated_call_s: dict[str, float] = Field(default_factory=lambda: {
        "intake": 2.3, "actor_cognition_hot": 21.2, "actor_cognition_warm": 3.6, "actor_reaction": 2.5,
        "writeback": 3.7, "portrayal_audit": 2.6, "narration": 18.6, "render_lint": 2.1,
    })  # [SAND] BENCH-01 replaces these with measured means per lane
    salience_weights: dict[str, float] = Field(default_factory=lambda: {
        "mandatory": 100.0, "unique_info": 3.0, "loudest_percept": 2.0, "addressed": 4.0, "in_conflict": 3.0,
        "interrupt_trigger": 5.0, "open_loop_with_pc": 1.0, "dependent_present": 1.0, "visible_to_pc": 1.0,
    })


class PacketRules(Strict):
    token_budget: dict[str, int] = Field(default_factory=lambda: {"hot": 3500, "warm": 2200, "reaction": 1400})
    max_beliefs: int = 12
    max_memories: int = 6
    max_open_loops: int = 8
    max_recent_lines: int = 5
    max_affordances: int = 18
    min_affordances: int = 3


class StyleRulesNumbers(Strict):
    echo_n: int = 4
    echo_min_content_tokens: int = 2
    echo_window_turns: int = 20
    max_passive_ratio: float = 0.20
    max_adverb_ratio: float = 0.08
    max_similes_per_200w: float = 1.0
    max_abstract_ratio: float = 0.03
    max_same_opener_bigram: int = 2
    max_consecutive_same_first_word: int = 2
    narration_words: dict[str, tuple[int, int]] = Field(default_factory=lambda: {
        "short": (80, 180), "medium": (160, 350), "long": (300, 600),
    })
    max_narration_attempts: int = 3


class DecayRules(Strict):
    weights: tuple[float, float, float, float] = (0.4, 0.2, 0.3, 0.1)
    tier1_below: int = 20
    tier2_below: int = 35
    tier3_unvisited_days: int = 30


class WorldRules(Strict):
    offscreen_tick_h: float = 6.0
    base_daily_mortality: dict[str, float] = Field(default_factory=lambda: {
        "bitch_mode": 0.0005, "easy": 0.001, "normal": 0.002, "realism": 0.004,
        "actually_hell": 0.008, "fuck_you": 0.016,
    })  # [SAND] BENCH-06: probability a COLD adult dies on a given day with no other risk
    trace_decay_days: dict[str, float] = Field(default_factory=lambda: {
        "tracks": 2, "blood": 7, "corpse": 30, "graffiti": 365, "missing_stock": 14, "damage": 180,
    })
    min_offscreen_trace_ratio: float = 0.7
    # P10 — world motion (world.worldmove) and worldgen numbers; docs/as/06_WORLD.md §1, §3
    start_hour: int = Field(default=8, ge=0, le=23)          # the clock time a generated world starts at
    world_hour: int = Field(default=4, ge=0, le=23)          # WORLD_DAY: the world's daily tick
    mortality_mult: dict[str, float] = Field(default_factory=lambda: {
        "scavenge": 3.0, "patrol": 2.0, "raid": 3.0, "trade_run": 2.0, "sick": 5.0, "child": 1.5,
        "elder": 2.0,
    })
    op_chance: dict[str, float] = Field(default_factory=lambda: {
        "scavenge": 0.3, "patrol": 0.25, "trade_run": 0.15, "raid": 0.1,
    })  # [SAND] daily chance a settlement (a hostile group for 'raid') starts an operation of that kind
    op_party: tuple[int, int] = (2, 3)
    op_leg_h: float = 2.0          # off-screen travel time along one route
    op_dwell_h: float = 3.0        # time spent at the destination
    defect_after_days: int = 3     # a plan to leave carried this long, pressure still on, is acted on
    weather_change_chance: float = 0.35


class InfectedRules(Strict):
    """P10 infected ecology numbers (world.infected; docs/as/06_WORLD.md §5)."""
    energy_start: int = 60
    energy_per_step: dict[str, int] = Field(default_factory=lambda: {
        "ZOMBIE_ARCHETYPE_SHAMBLER01": 1, "ZOMBIE_ARCHETYPE_CRAWLER01": 1, "ZOMBIE_VARIANT_ID_RUNNER01": 3,
    })
    energy_per_feed: int = 40      # a bite that lands
    starved_below: int = 20        # energy under this -> state 'starved'
    overfed_above: int = 90        # energy over this -> state 'overfed'
    idle_recover_per_day: int = 5  # a dormant body regains this much a day (it can reboot later)
    motion_window_s: int = 10      # 'moving' for motion-contrast sight: a MOVE or ACTION_START in the last N s
    step_min_s: float = 2.0        # the shortest INFECTED_STEP interval
    bang_db: float = 70.0          # a body stopped by a closed portal bangs on it
    runner_degrade_days: tuple[int, int] = (20, 40)   # INF-10: a Runner becomes a Shambler or a Crawler
    wet_ignore_after_h: float = 336.0                  # INF-07: week-3 wet hosts are not hunted by sight
    populate_max: int = 6          # infected bodies of one type put in one place at most
    place_factor: dict[str, float] = Field(default_factory=lambda: {
        "street": 1.0, "outdoor": 0.7, "building": 0.5, "room": 0.3, "tunnel": 1.2, "vehicle": 0.2,
    })
    quirks_max: int = 2


class SocietyRules(Strict):
    """P9 society numbers (docs/as/06_WORLD.md §2). Keys of the per-band tables are AgeBand values."""
    water_per_day: dict[str, float] = Field(default_factory=lambda: {
        "infant": 1.0, "child": 1.0, "preteen": 3.0, "teen": 3.0, "adult": 3.0, "elder": 3.0})
    food_per_day: dict[str, float] = Field(default_factory=lambda: {
        "infant": 0.5, "child": 1.0, "preteen": 2.0, "teen": 2.0, "adult": 2.0, "elder": 2.0})
    ration_mult: dict[int, float] = Field(default_factory=lambda: {0: 0.25, 1: 0.5, 2: 0.75, 3: 1.0, 4: 1.25})
    shortage_days: float = 3.0         # a store under this many days of need is short (content CAS-004)
    recovery_days: float = 7.0         # every rationed store at or above this many days ...
    recovery_streak: int = 3           # ... on this many daily draws in a row -> ration +1 (up to 3)
    draw_hour: int = Field(default=7, ge=0, le=23)     # SETTLEMENT_DAY
    group_hour: int = Field(default=20, ge=0, le=23)   # GROUP_DAY
    morale_baseline: int = 5
    pyramid: dict[str, tuple[float, float]] = Field(default_factory=lambda: {
        "young": (0.10, 0.30), "youth": (0.08, 0.20), "adults": (0.40, 0.70), "elders": (0.03, 0.15)})
    demo_min_population: int = 15
    role_skill: dict[str, tuple[str, int]] = Field(default_factory=lambda: {
        "pump_operator": ("mechanics", 1), "mechanic": ("mechanics", 1), "cook": ("cooking", 1),
        "medic": ("medicine", 1), "gardener": ("farming", 1), "builder": ("building", 1),
        "quartermaster": ("trade", 1), "teacher": ("childcare", 1)})
    manual_roles: tuple[str, ...] = ("pump_operator", "mechanic", "cook", "gardener", "builder", "laundry")
    condition_full_at: int = 50        # machinery at or above this condition runs at full output
    efficiency_recovery: float = 0.25  # per production cycle once no worker of the place is covering
    sleep_h: int = 8
    child_sleep: tuple[int, int] = (19, 7)
    adult_sleep: tuple[int, int] = (22, 6)
    min_sleep_h: int = 4
    boiling_point: int = 70
    tension_decay_per_day: int = 5
    ration_strain_tension: int = 5
    drift_bond: float = 0.25           # [SAND] daily chance a working/household tie gains trust
    drift_household: float = 0.2       # [SAND] daily chance housemates gain affection
    drift_friction: float = 0.3        # [SAND] daily chance a sour tie gains resentment
    drift_cap: int = 2                 # drift never pushes trust or affection above this
    rumour_tells_per_day: int = 2
    rumour_quiet_days: int = 14        # a rumour older than this is no longer passed on
    loyalty_recheck_days: int = 3
    grief_ease_days: int = 7


class RulesConfig(Strict):
    checks: CheckRules = Field(default_factory=CheckRules)
    acoustics: AcousticRules = Field(default_factory=AcousticRules)
    harm: HarmRules = Field(default_factory=HarmRules)
    needs: NeedsRules = Field(default_factory=NeedsRules)
    resolve: ResolveRules = Field(default_factory=ResolveRules)
    scheduler: SchedulerRules = Field(default_factory=SchedulerRules)
    packet: PacketRules = Field(default_factory=PacketRules)
    style: StyleRulesNumbers = Field(default_factory=StyleRulesNumbers)
    decay: DecayRules = Field(default_factory=DecayRules)
    world: WorldRules = Field(default_factory=WorldRules)
    society: SocietyRules = Field(default_factory=SocietyRules)
    infected: InfectedRules = Field(default_factory=InfectedRules)


class EngineConfig(Strict):
    schema_id: Literal["as.config.v1"] = Field(alias="schema", default="as.config.v1")
    runs_dir: str = "as_runs"
    content_dir: str = "as_content/packs"
    compiled_dir: str = "as_content/_compiled"
    lanes: dict[Lane, LaneConfig] = Field(default_factory=default_lanes)
    regimes: dict[CallClass, CallRegime] = Field(default_factory=default_regimes)
    rules: RulesConfig = Field(default_factory=RulesConfig)
    hot_cognition: CallRegime = Field(default_factory=lambda: CallRegime(
        lane=Lane.A, temperature=0.7, max_tokens=3000, thinking=True, deadline_s=75))
    background_cognition: bool = True
    model_config = Strict.model_config | {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Per-run settings (New Life wizard)
# ---------------------------------------------------------------------------


class RunSettings(Strict):
    difficulty: Difficulty = Difficulty.NORMAL
    era: Era = Era.MATURE
    days_since_fall: int | None = Field(default=None, ge=1, le=20000)
    world_detail: WorldDetail = WorldDetail.STANDARD
    seed: int | None = Field(default=None, ge=0, le=2**63 - 1)
    save_mode: Literal["free", "ironman"] = "free"
    narration_length: Literal["short", "medium", "long"] = "medium"
    narration_person: Literal["third_limited", "second"] = "third_limited"
    narration_tense: Literal["past", "present"] = "past"
    turn_depth: Literal["quick", "balanced", "deep"] = "balanced"
    pc_voice: Literal["exact", "my_way"] = "exact"
    intensity: Literal["full", "softer"] = "full"
    show_mechanics: Literal["off", "summary", "full"] = "summary"
    read_aloud: bool = False
    dev_mode: bool = False
    autosave_ring: int = Field(default=5, ge=1, le=50)
    pack_ids: list[str] = Field(default_factory=lambda: ["core"])


ERA_DAYS_RANGE: dict[Era, tuple[int, int]] = {
    Era.EARLY: (14, 330),
    Era.ESTABLISHED: (400, 1460),
    Era.MATURE: (1830, 3650),
}
