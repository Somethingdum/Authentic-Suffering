"""Parameter generation WG0 (P10). Rules WG-01..09 (CMG §61 Parts III-VIII carried).

Rounding everywhere in this module: rnd(x) = floor(x + 0.5)  (NOT Python's banker's round).
All draws use rng stream 'worldgen:params' in tables.DRAW_ORDER order; each named draw happens
exactly once even if the value is later patched (determinism, WG-DET-01).

generate_params(rng, tx, difficulty, era, bias: WorldgenBias, days_since_fall|None, *, fall_range=None,
                pc_name='') -> (WorldParams, patches)   (fall_range = the PC's days_since_fall_range)
  Step 3 difficulty-owned: value = rng.range_int(floor, ceiling)  (C-block, hazard_severity, D-block
         shortages, tech_baseline, tech_preservation). Sim mechanics fixed from SIM_MECHANICS.
  Step 5/6 A-block (atmo_visibility, climate_heat, climate_moisture, instability):
         value = clamp(rnd(5 + bias*5) + rng.range_int(-1, 1), 1, 10)
         hazard_type = rng.weighted(HAZARD_TYPE_WEIGHTS)
  Step 4/5/6 B-block with era (floor, ceiling) (default (1,10)):
         band_half = (ceiling - floor) / 2 ; midpoint = floor + band_half
         adjusted = clamp(rnd(midpoint + bias*band_half), floor, ceiling)
         value = clamp(adjusted + rng.range_int(-1, 1), floor, ceiling)
  E-block: value = clamp(rnd(5 + bias*5) + rng.range_int(-2, 2), 1, 10)
  days_since_fall: given, else rng.range_int(lo, hi) where (lo, hi) = ERA_DAYS_RANGE[era]
         intersected with ``fall_range`` (WG-34). A given value outside fall_range, or an empty
         intersection, raises kernel.errors.SettingsError(rule='WG-34') with the plain message
         f"{pc_name}'s age and history need a world {a // 365}-{b // 365} years after the Fall."
         ((a, b) = fall_range)
         (the New Life wizard never offers such a combination, so this is a guard, not a flow).
  Step 7 contradictions: see apply_contradictions (on the flat values, after every draw above).
  key_resource (P10): types = key_resource_type(values, hazard_type); type = types[0] when the
         list has exactly one, else rng.choice(tx, 'worldgen:params', 'key_resource_type', types);
         descriptor = rng.choice(tx, 'worldgen:params', 'key_resource',
         atlas.KEY_RESOURCE_DESCRIPTORS[type]); key_resource = f"{type} — {descriptor}". These draws
         come after days_since_fall (and after apply_contradictions, which draws nothing).
  climate_descriptor = climate_descriptor(climate_heat, climate_moisture) (below).
  The returned patches are apply_contradictions' patches. Every parameter makes exactly one draw
  (days_since_fall none when it is given), in DRAW_ORDER, and its purpose is the parameter's name.

climate_descriptor(heat, moisture) -> str   (implemented) atlas.CLIMATE_DESCRIPTORS[(band(heat), band(
  moisture))] with bands 1-3 cold/dry, 4-7 mild/moderate, 8-10 hot/wet.
flat_values(params: WorldParams) -> dict[str, int | str]   (implemented) every A-E block field and
  every sim mechanic by name, plus days_since_fall — the names world/worldgen/conditions.py reads.

apply_contradictions(values: dict, era) -> (values, patches: list[str])
  Pass 1: for each row in CONTRADICTIONS order, when BOTH conditions hold, set the lower param to
  the nearest value that clears its condition (">= v" -> v-1; "<= v" -> v+1) and record
  f"#{id}: {lower} {old}->{new}". Pass 2: repeat the whole table once. Any row still flagged after
  pass 2 -> set lower to the override value, record f"STEP 7 OVERRIDE #{id}".

key_resource_type(values, hazard_type) -> list[str] candidate types by Part VIII rule order:
  1 food<=3 or water<=3 -> ['supply node']; 2 tech_preservation>=7 and tech_baseline>=6 ->
  ['infrastructure']; 3 hazard_type=='biological' and hazard_severity>=6 -> ['biological'];
  4 faction_density>=6 and faction_fragmentation>=6 -> ['territory']; 5 otherwise by the highest
  of the six C-block values: hostile_human strictly highest -> ['information source', 'territory'];
  one of zombie_common, horde_pressure, runner_pressure, lurker_pressure strictly highest ->
  ['supply node', 'infrastructure']; anything else (a tie at the top, or ambient_danger highest) ->
  all five: ['supply node', 'infrastructure', 'biological', 'territory', 'information source'].
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...contracts.common import Difficulty, Era
from ...contracts.dossier import WorldgenBias
from ...contracts.worldgen import WorldParams

if TYPE_CHECKING:
    from ...kernel.rng import Rng
    from ...kernel.store import Tx


def rnd(x: float) -> int:
    """floor(x + 0.5) (implemented)."""
    import math

    return math.floor(x + 0.5)


def generate_params(rng: "Rng", tx: "Tx", difficulty: Difficulty, era: Era, bias: WorldgenBias,
                    days_since_fall: int | None, *, fall_range: tuple[int, int] | None = None,
                    pc_name: str = "") -> tuple[WorldParams, list[str]]:
    raise NotImplementedError("P10")


def apply_contradictions(values: dict[str, int], era: Era) -> tuple[dict[str, int], list[str]]:
    raise NotImplementedError("P10")


def key_resource_type(values: dict[str, int], hazard_type: str) -> list[str]:
    raise NotImplementedError("P10")


def climate_descriptor(heat: int, moisture: int) -> str:
    """atlas.CLIMATE_DESCRIPTORS by heat and moisture band (implemented)."""
    from .atlas import CLIMATE_DESCRIPTORS

    def band(v: int, words: tuple[str, str, str]) -> str:
        return words[0] if v <= 3 else words[1] if v <= 7 else words[2]

    return CLIMATE_DESCRIPTORS[(band(heat, ("cold", "mild", "hot")), band(moisture, ("dry", "moderate", "wet")))]


def flat_values(params: WorldParams) -> dict[str, int | str]:
    """Every block field and sim mechanic by name, plus days_since_fall (implemented)."""
    out: dict[str, int | str] = {"days_since_fall": params.days_since_fall}
    for block in (params.a, params.b, params.c, params.d, params.e, params.sim):
        out.update(block.model_dump())
    return out
from ._impl_wg import generate_params, apply_contradictions, key_resource_type  # noqa
