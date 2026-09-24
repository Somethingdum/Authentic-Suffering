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
        Lane.A: LaneConfig(name="Main model — Nemotron Cascade 2 30B-A3B",
                           model="nemotron-cascade-2-30b-a3b"),
        Lane.B: LaneConfig(name="Second model — Nemotron 3.5 Lightning 30B-A3B",
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
    # [SAND] Actor Spec §5: 6000 deliberating, 4000 routine, 3000 a reaction, fixed text included
    token_budget: dict[str, int] = Field(default_factory=lambda: {"hot": 6000, "warm": 4000, "reaction": 3000})
    max_beliefs: int = 12
    max_memories: int = 6
    max_open_loops: int = 8
    max_recent_lines: int = 5
    max_affordances: int = 24       # [SAND] Actor Spec §8: a short, diverse first menu of 24; more on request
    min_affordances: int = 3
    max_heard_chars: int = 800     # [SAND] Actor Spec §5: heard words past this are cut, ' …' (packet, aftermath)


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
    """P10 physical wear (world.decay WEAR-01..04; fidelity C02: things wear, none is forgotten)."""
    rust_kinds: tuple[str, ...] = ("firearm", "magazine", "ammo", "melee", "tool", "key")
    rot_kinds: tuple[str, ...] = ("clothing", "container", "food")
    rust_per_wet_day: int = 1      # [SAND] condition lost per wet day by metal lying in the open
    pulp_per_wet_day: int = 25     # [SAND] paper in the rain
    rot_per_wet_day: int = 2       # [SAND] cloth, packs and food left out in the rain
    # Retired by the P10 fidelity revision (the salvaged Memory Fade): nothing reads these; they
    # stay only so a run made before it still loads its frozen rules.
    weights: tuple[float, float, float, float] = (0.4, 0.2, 0.3, 0.1)
    tier1_below: int = 20
    tier2_below: int = 35
    tier3_unvisited_days: int = 30


class WorldRules(Strict):
    offscreen_tick_h: float = 6.0
    trace_decay_days: dict[str, float] = Field(default_factory=lambda: {
        "tracks": 2, "blood": 7, "corpse": 30, "graffiti": 365, "missing_stock": 14, "damage": 180,
    })  # in the open; under a roof x sheltered_trace_mult (TRACE-01)
    sheltered_trace_mult: float = 4.0     # [SAND] a mark indoors lasts this many times longer
    washes_out: tuple[str, ...] = ("tracks", "blood", "smoke")   # rain, storm or snow erases outdoors
    # Retired by the P10 fidelity revision (C01 no death lottery, C11 no trace quota; DECISIONS D-52):
    # nothing reads these — not even the P11 release audit; they stay only so a run made before it
    # still loads its frozen rules.
    base_daily_mortality: dict[str, float] = Field(default_factory=lambda: {
        "bitch_mode": 0.0005, "easy": 0.001, "normal": 0.002, "realism": 0.004,
        "actually_hell": 0.008, "fuck_you": 0.016,
    })
    min_offscreen_trace_ratio: float = 0.7
    # P10 — world motion (world.worldmove) and worldgen numbers; docs/as/06_WORLD.md §1, §3
    start_hour: int = Field(default=8, ge=0, le=23)          # the clock time a generated world starts at
    world_hour: int = Field(default=4, ge=0, le=23)          # WORLD_DAY: the world's daily tick
    mortality_mult: dict[str, float] = Field(default_factory=lambda: {
        "scavenge": 3.0, "patrol": 2.0, "raid": 3.0, "trade_run": 2.0, "sick": 5.0, "child": 1.5,
        "elder": 2.0,
    })  # retired with base_daily_mortality (nothing reads it)
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
    energy_period_s: dict[str, int] = Field(default_factory=lambda: {   # INF-03: 1 energy per this many
        "ZOMBIE_ARCHETYPE_SHAMBLER01": 60, "ZOMBIE_ARCHETYPE_CRAWLER01": 120,     # seconds active (60 unlisted)
        "ZOMBIE_VARIANT_ID_RUNNER01": 20,
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
    push_min: int = 3              # INF-13: this many infected at a closed portal make it give
    portal_holds_min: dict[str, int] = Field(default_factory=lambda: {
        "door": 30, "window": 10, "gate": 45, "hatch": 30, "opening": 0})   # [SAND] minutes of pressure
    barricade_min: int = 30        # every barricade level holds this much longer
    lock_min: int = 15             # every point of lock quality holds this much longer
    # The wet strain's living spreaders (lore §3.2; physical.objects / mind.cues / turn.cognition)
    saliva_hours: float = 12.0     # [SAND] a spreader's mouth on a bottle stays infective this long
    sign_range_m: float = 3.0      # a host's stage signs (fever, spreader signs, a bite) are seen this close
    compulsion_cooldown_min: int = 10   # a week-3 spreader's involuntary offer, at most once per this
    # F1b gore camouflage (INF-14): a living body caked in gore moves among them as one of them
    gore_mask_min: int = 4         # [SAND] bodies.gore at or above this masks the living
    mask_window_s: int = 30        # [SAND] giving yourself away is remembered this long
    mask_break_db: float = 55.0    # [SAND] a sound of your own this loud gives you away (a run, a strike, a normal voice)


class OlfactionRules(Strict):
    """F1b smell numbers (sense.olfaction; SMELL-01..03)."""
    range_m: dict[int, float] = Field(default_factory=lambda: {1: 1.0, 2: 2.0, 3: 5.0, 4: 10.0, 5: 20.0})  # [SAND]
    outdoor_mult: float = 0.5      # [SAND] open air carries a smell off: ranges outdoors are this much of indoors
    death_hours: tuple[float, float, float] = (6.0, 24.0, 72.0)   # [SAND] a corpse smells of death at 2 / 3 / 4 from these hours


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
    privation_days: dict[str, int] = Field(default_factory=lambda: {"water": 3, "food": 21})
    # P10 (C01): unnamed people short of a resource on this many daily draws in a row die of it
    rumour_tells_per_day: int = 2
    rumour_quiet_days: int = 14        # a rumour older than this is no longer passed on
    loyalty_recheck_days: int = 3
    grief_ease_days: int = 7


class HordeRules(Strict):
    """P10 the region's dead in numbers, hordes, the exterior and the Mega Horde (world.hordes
    HRD-01..17; fidelity E01-E03, W04). Per-difficulty / per-era keys are Difficulty / Era values."""
    exterior_pool: dict[str, int] = Field(default_factory=lambda: {
        "bitch_mode": 20_000, "easy": 40_000, "normal": 80_000, "realism": 120_000,
        "actually_hell": 200_000, "fuck_you": 400_000})       # [SAND] the dead past each map edge
    dormant_share: dict[str, float] = Field(default_factory=lambda: {
        "early": 0.2, "established": 0.5, "mature": 0.7})     # standing still, waiting ("statues")
    runner_share: dict[str, float] = Field(default_factory=lambda: {
        "early": 0.25, "established": 0.05, "mature": 0.01})  # x runner_pressure / 5: fresh dead
    crawler_share: float = 0.2
    runner_days: float = 30.0      # a pooled Runner becomes a Shambler after about this long (INF-10)
    density_full: int = 2000       # active dead at which a district's density reads 10
    populate_scale: float = 20.0   # a place shows 1 in this many of its share of the district's dead
    speed_m_s: float = 0.25        # a horde's walking pace (about 0.9 km/h)
    mill_h: float = 6.0            # a drift or drawn horde stays this long where it went, then scatters
    tick_min: float = 5.0          # while a horde is in sight it keeps the street full this often
    local_cap: int = 40            # bodies one horde shows in one place at once
    straggle: float = 0.02         # left behind at every hub
    rally: float = 0.05            # of a hub zone's active dead join a drifting or mega horde
    drift_min: int = 50            # a district needs this many active dead to send a crowd off
    drift_chance: float = 0.15     # [SAND] per district per day, x horde_pressure / 5
    drift_share: float = 0.05
    draw_db: float = 130.0         # a sound this loud at its source draws the district's dead
    draw_share: float = 0.01       # of the district's active dead, per 10 dB at or above draw_db
    draw_minutes: int = 30         # until the drawn dead start arriving
    draw_cooldown_h: float = 6.0
    breach_scale: float = 40.0     # dead per point of defence (+1) that make a breach likely
    breach_kill: float = 0.02      # unnamed killed per infected in a breach
    breach_bite: float = 0.25      # chance each named person at the site is bitten in a breach
    mega_daily_chance: dict[str, float] = Field(default_factory=lambda: {
        "bitch_mode": 0.0005, "easy": 0.001, "normal": 0.004, "realism": 0.006,
        "actually_hell": 0.012, "fuck_you": 0.02})           # [SAND] x horde_pressure / 5 x the ramp
    mega_ramp_days: int = 60       # the chance grows from 0 over the run's first this-many days
    mega_size: dict[str, tuple[int, int]] = Field(default_factory=lambda: {
        "bitch_mode": (8_000, 20_000), "easy": (12_000, 40_000), "normal": (20_000, 80_000),
        "realism": (30_000, 120_000), "actually_hell": (50_000, 200_000),
        "fuck_you": (80_000, 300_000)})
    mega_eta_days: tuple[int, int] = (3, 10)   # from forming to reaching the region's edge
    mega_speed_m_s: float = 0.15
    mega_throughput_per_day: int = 20_000       # how many pass through one district in a day
    mega_ambient_db: float = 85.0               # a district the Mega Horde is in never goes quiet


class BackgroundRules(Strict):
    """P10 quiet-hours numbers (service.background BG-02; Actor Spec AC12, fidelity C07)."""
    material_salience: int = Field(default=60, ge=0, le=100)  # this salient (or an anchor): material
    rest_min_episodes: int = 3     # a night's sleep needs at least this many new episodes to mull
    max_reflections: int = 2       # per turn boundary
    max_retellings: int = 4        # per turn boundary
    max_episodes: int = 8          # the newest new episodes a reflection is shown


class RulesConfig(Strict):
    checks: CheckRules = Field(default_factory=CheckRules)
    acoustics: AcousticRules = Field(default_factory=AcousticRules)
    olfaction: OlfactionRules = Field(default_factory=OlfactionRules)
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
    background: BackgroundRules = Field(default_factory=BackgroundRules)
    hordes: HordeRules = Field(default_factory=HordeRules)


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
