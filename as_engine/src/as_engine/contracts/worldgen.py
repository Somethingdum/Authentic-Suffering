"""World generation contracts (docs/as/06_WORLD.md; CMG §61 carried as WG-PARAMS).

The parameter blocks, difficulty bands, era constraints, contradiction table, key-resource
rules, placement logic and QC checks are carried from Codex Master Guide §61 unchanged except
where 06_WORLD.md records a deviation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import Difficulty, Era, Strict

P = Field(ge=1, le=10)


class ABlock(Strict):
    atmo_visibility: int = P
    climate_heat: int = P
    climate_moisture: int = P
    instability: int = P
    hazard_type: Literal["environmental", "biological", "structural", "combined"]
    hazard_severity: int = P


class BBlock(Strict):
    social_order: int = P
    survivor_mentality: int = P
    faction_density: int = P
    faction_fragmentation: int = P
    faction_relations: int = P
    atrocity_capacity: int = P


class CBlock(Strict):
    ambient_danger: int = P
    zombie_common: int = P
    horde_pressure: int = P
    runner_pressure: int = P
    lurker_pressure: int = P
    hostile_human: int = P


class DBlock(Strict):
    food: int = P
    water: int = P
    ammo: int = P
    fuel: int = P
    meds: int = P
    tech_baseline: int = P
    tech_preservation: int = P
    key_resource: str = Field(max_length=50)


class EBlock(Strict):
    mystery: int = P
    ritual_intensity: int = P
    subtle_anomaly: int = P
    lost_knowledge: int = P
    wildcard_level: int = P


class SimMechanics(Strict):
    snowball_rate: int = P
    warning_slack: int = P
    recovery_slack: int = P


class Placement(Strict):
    entity_type: Literal["faction", "group", "none"]
    faction_id: str | None = None
    faction_presence: Literal["dominant", "active", "peripheral"] | None = None
    group_descriptor: str | None = Field(default=None, max_length=60)
    start_trust: int | None = Field(default=None, ge=1, le=10)
    start_relationship: Literal["ally", "neutral", "suspicious", "indebted", "enemy", "none"]


class OpeningPressure(Strict):
    immediate_contacts: str = Field(max_length=150)
    immediate_liabilities: str = Field(max_length=150)
    opening_pressure: str = Field(max_length=200)
    first_objective: str = Field(max_length=150)
    cites_entity_ids: list[str] = Field(min_length=1, description="Real placed entities the pressure is made of.")
    cites_params: list[str] = Field(min_length=1, description="A/B-block parameter names reflected (QC-4c).")


class WorldParams(Strict):
    difficulty: Difficulty
    era: Era
    days_since_fall: int = Field(ge=1)
    a: ABlock
    b: BBlock
    c: CBlock
    d: DBlock
    e: EBlock
    sim: SimMechanics
    climate_descriptor: str = Field(max_length=35)


class WorldgenCommit(Strict):
    run_id: str
    seed: int
    pc_ref: str
    params: WorldParams
    placement: Placement
    start_zone_type: str = Field(max_length=40)
    start_district_type: str = Field(max_length=40)
    opening: OpeningPressure
    qc_result: Literal["pass", "patched", "aborted"]
    qc_patches: list[str] = Field(default_factory=list)


class WorldgenProgress(Strict):
    stage: Literal["WG0", "WG1", "WG2", "WG3", "WG4", "WG5", "WG6", "WG7", "WG8", "WG9", "COMMIT"]
    label: str
    pct: float = Field(ge=0, le=100)
    eta_s: float | None = None
    sub: str | None = None           # P10 progress v2: 'history' (WG2) / 'dossiers' (WG6)
    done: int | None = None
    total: int | None = None
