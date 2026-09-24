"""Worldgen tables carried VERBATIM from Codex Master Guide §61 (IMPLEMENTED DATA — canon).
Changing a number here is a canon change: record it in docs/as/DECISIONS.md first.
"""

from __future__ import annotations

from ...contracts.common import Difficulty, Era

D = Difficulty

# Part VI — difficulty bands (floor, ceiling) for difficulty-owned parameters
DIFFICULTY_BANDS: dict[str, dict[Difficulty, tuple[int, int]]] = {
    "ambient_danger": {D.BITCH_MODE: (1, 3), D.EASY: (2, 4), D.NORMAL: (4, 6), D.REALISM: (5, 8), D.ACTUALLY_HELL: (7, 9), D.FUCK_YOU: (8, 10)},
    "zombie_common": {D.BITCH_MODE: (1, 3), D.EASY: (2, 4), D.NORMAL: (3, 6), D.REALISM: (5, 7), D.ACTUALLY_HELL: (6, 9), D.FUCK_YOU: (8, 10)},
    "horde_pressure": {D.BITCH_MODE: (1, 2), D.EASY: (1, 3), D.NORMAL: (2, 5), D.REALISM: (4, 7), D.ACTUALLY_HELL: (6, 8), D.FUCK_YOU: (7, 10)},
    "runner_pressure": {D.BITCH_MODE: (1, 2), D.EASY: (1, 3), D.NORMAL: (2, 5), D.REALISM: (4, 7), D.ACTUALLY_HELL: (5, 8), D.FUCK_YOU: (7, 10)},
    "lurker_pressure": {D.BITCH_MODE: (1, 2), D.EASY: (2, 4), D.NORMAL: (3, 6), D.REALISM: (5, 7), D.ACTUALLY_HELL: (6, 9), D.FUCK_YOU: (8, 10)},
    "hostile_human": {D.BITCH_MODE: (1, 3), D.EASY: (2, 4), D.NORMAL: (3, 6), D.REALISM: (4, 7), D.ACTUALLY_HELL: (6, 9), D.FUCK_YOU: (7, 10)},
    "hazard_severity": {D.BITCH_MODE: (1, 3), D.EASY: (2, 4), D.NORMAL: (3, 6), D.REALISM: (5, 7), D.ACTUALLY_HELL: (6, 9), D.FUCK_YOU: (8, 10)},
    "food": {D.BITCH_MODE: (7, 10), D.EASY: (6, 9), D.NORMAL: (4, 7), D.REALISM: (3, 6), D.ACTUALLY_HELL: (2, 4), D.FUCK_YOU: (1, 3)},
    "water": {D.BITCH_MODE: (7, 10), D.EASY: (6, 9), D.NORMAL: (4, 7), D.REALISM: (3, 6), D.ACTUALLY_HELL: (2, 4), D.FUCK_YOU: (1, 3)},
    "ammo": {D.BITCH_MODE: (6, 9), D.EASY: (5, 8), D.NORMAL: (4, 7), D.REALISM: (2, 6), D.ACTUALLY_HELL: (1, 4), D.FUCK_YOU: (1, 2)},
    "fuel": {D.BITCH_MODE: (6, 9), D.EASY: (5, 8), D.NORMAL: (3, 7), D.REALISM: (2, 5), D.ACTUALLY_HELL: (1, 3), D.FUCK_YOU: (1, 2)},
    "meds": {D.BITCH_MODE: (6, 9), D.EASY: (5, 8), D.NORMAL: (3, 7), D.REALISM: (2, 5), D.ACTUALLY_HELL: (1, 3), D.FUCK_YOU: (1, 2)},
    "tech_baseline": {D.BITCH_MODE: (5, 10), D.EASY: (4, 9), D.NORMAL: (3, 8), D.REALISM: (2, 7), D.ACTUALLY_HELL: (1, 5), D.FUCK_YOU: (1, 3)},
    "tech_preservation": {D.BITCH_MODE: (4, 9), D.EASY: (3, 8), D.NORMAL: (2, 7), D.REALISM: (1, 6), D.ACTUALLY_HELL: (1, 4), D.FUCK_YOU: (1, 2)},
}

# Simulation mechanics (fixed by tier)
SIM_MECHANICS: dict[Difficulty, tuple[int, int, int]] = {  # snowball, warning_slack, recovery_slack
    D.BITCH_MODE: (1, 9, 9), D.EASY: (2, 7, 7), D.NORMAL: (4, 5, 5),
    D.REALISM: (6, 3, 3), D.ACTUALLY_HELL: (8, 2, 2), D.FUCK_YOU: (9, 1, 1),
}

# Era B-block constraints (floor, ceiling); missing = (1, 10). Early also caps tech_preservation at 7 (table #6).
ERA_B_CONSTRAINTS: dict[Era, dict[str, tuple[int, int]]] = {
    Era.EARLY: {"faction_density": (1, 4), "social_order": (1, 5)},
    Era.ESTABLISHED: {},
    Era.MATURE: {"faction_density": (3, 10), "social_order": (2, 10)},
}

# Part VII — contradiction table, processed in order.
# (id, higher_param or 'era=early', higher_op, higher_value, lower_param, lower_op, lower_value, override_value)
CONTRADICTIONS: tuple[tuple[int, str, str, int, str, str, int, int], ...] = (
    (1, "tech_preservation", ">=", 8, "instability", ">=", 8, 7),
    (2, "social_order", ">=", 7, "atrocity_capacity", ">=", 7, 6),
    (3, "social_order", ">=", 7, "survivor_mentality", ">=", 8, 7),
    (4, "era=early", "==", 1, "faction_density", ">=", 5, 4),
    (5, "era=early", "==", 1, "social_order", ">=", 6, 5),
    (6, "era=early", "==", 1, "tech_preservation", ">=", 8, 7),
    (7, "faction_fragmentation", ">=", 8, "faction_density", "<=", 2, 3),
    (8, "faction_density", "<=", 2, "faction_fragmentation", ">=", 6, 5),
    (9, "wildcard_level", ">=", 8, "mystery", "<=", 2, 3),
    (10, "tech_preservation", "<=", 2, "tech_baseline", ">=", 7, 6),
    (11, "social_order", "<=", 2, "faction_relations", ">=", 8, 6),
    (12, "instability", ">=", 9, "social_order", ">=", 7, 6),
)

# Draw order on rng stream 'worldgen:params' (determinism contract, WG-DET-01)
DRAW_ORDER: tuple[str, ...] = (
    "ambient_danger", "zombie_common", "horde_pressure", "runner_pressure", "lurker_pressure",
    "hostile_human", "hazard_severity", "food", "water", "ammo", "fuel", "meds", "tech_baseline",
    "tech_preservation", "atmo_visibility", "climate_heat", "climate_moisture", "instability",
    "hazard_type", "social_order", "survivor_mentality", "faction_density", "faction_fragmentation",
    "faction_relations", "atrocity_capacity", "mystery", "ritual_intensity", "subtle_anomaly",
    "lost_knowledge", "wildcard_level", "days_since_fall",
)

HAZARD_TYPE_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("environmental", 3.0), ("biological", 3.0), ("structural", 3.0), ("combined", 1.0),
)

# World detail tiers (Batch-3 ruling #4: a settings dial, not a consultation)
DETAIL_TIERS: dict[str, dict[str, int]] = {
    "gotta_go_to_work_soon": {"zones": 3, "places_per_zone": 4, "detailed_actors": 8, "llm_dossiers": 3, "history_events": 6, "est_minutes": 3},
    "quick_look": {"zones": 4, "places_per_zone": 6, "detailed_actors": 12, "llm_dossiers": 6, "history_events": 10, "est_minutes": 7},
    "standard": {"zones": 5, "places_per_zone": 8, "detailed_actors": 18, "llm_dossiers": 12, "history_events": 14, "est_minutes": 15},
    "settle_in": {"zones": 6, "places_per_zone": 10, "detailed_actors": 26, "llm_dossiers": 20, "history_events": 20, "est_minutes": 30},
    "not_using_my_laptop_today": {"zones": 8, "places_per_zone": 12, "detailed_actors": 40, "llm_dossiers": 40, "history_events": 30, "est_minutes": 60},
}

# Part X — faction and group placement (CMG §61 Part X, carried). Keys are PCDossier.faction_start_type.
START_TYPE_ENTITIES: dict[str, tuple[str, ...]] = {      # Step 1: valid entity_type values
    "always_in_faction": ("faction",),
    "usually_adjacent": ("faction", "group"),
    "outsider_tied": ("faction", "none"),               # a faction only at peripheral presence
    "outsider_solo": ("group", "none"),
}
START_TYPE_PRESENCE: dict[str, tuple[str, ...]] = {      # Step 2: permitted presence, strongest first
    "always_in_faction": ("dominant", "active"),
    "usually_adjacent": ("active", "peripheral"),
    "outsider_tied": ("peripheral",),
    "outsider_solo": (),
}
TRUST_RANGES: dict[str, tuple[int, int]] = {             # Step 4 (none -> no trust)
    "ally": (7, 10), "neutral": (4, 6), "suspicious": (2, 4), "indebted": (3, 7), "enemy": (1, 2),
}
START_TYPE_RELATIONSHIP: dict[str, str] = {              # Step 4: the start type's default
    "always_in_faction": "ally", "usually_adjacent": "neutral", "outsider_tied": "suspicious",
    "outsider_solo": "none",
}
PRESENCE_MIN_DENSITY: dict[str, int] = {"dominant": 6, "active": 3, "peripheral": 1}   # §10.3 / QC-3
# Part II §2.3 — the PC card's "Starts as" line, by faction_start_type
STARTS_AS: dict[str, str] = {
    "always_in_faction": "Inside — a sworn member of a faction",
    "usually_adjacent": "Adjacent — known and valued by local groups, not embedded",
    "outsider_tied": "Outsider — tied to a faction from the outside",
    "outsider_solo": "Alone — nobody is expecting them",
}
# Part IX — character budgets of the opening; QC-4 / QC-5 trim to these
OPENING_BUDGETS: dict[str, int] = {
    "immediate_contacts": 150, "immediate_liabilities": 150, "opening_pressure": 200, "first_objective": 150,
}
# Hard-fail protocol (Part XII): difficulties at which QC-2 is enforced
QC2_ENFORCED: tuple[Difficulty, ...] = (D.BITCH_MODE, D.EASY, D.NORMAL, D.REALISM)
