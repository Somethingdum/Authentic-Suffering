"""Faction and group placement, the plausibility gate and the hard-fail protocol (P10, WG0 steps
9 and 12). Rules WG-10..14. CMG §61 Parts X and XII carried; tables in world/worldgen/tables.py.
docs/as/06_WORLD.md §1.3. Pure code: no model call. rng stream 'worldgen:placement'.

``values`` below is params.flat_values(params) (names -> ints, plus hazard_type); ``pc`` is the PC's
PCDossier. A faction's ``ref`` is its content ref ('core:faction/mafia_remnants').

WG-10 eligible_factions(canon, values) -> list[tuple[str, FactionDossier]]
  (ref, record) for every canon faction record whose kind is 'faction' and whose
  presence.presence_conditions ALL evaluate true (conditions.evaluate(expr, values)), sorted by ref.

WG-11 place(rng, tx, values, pc, canon) -> Placement   (Part X steps 1-4)
  t = pc.faction_start_type; E = eligible_factions(canon, values); density = values['faction_density'];
  pref = pc.start_constraints.faction_present_preferred.
  entity_type:
    always_in_faction  'faction' (even with E empty: faction_id None, which QC-2's
                       faction-protection rule catches);
    usually_adjacent   'faction' when E and density >= 3 and pref != 'no', else 'group';
    outsider_tied      'faction' when E and pref != 'no', else 'none';
    outsider_solo      'group' when density >= 2, else 'none'.
  faction (entity_type 'faction' and E not empty): faction_id = rng.choice(tx, 'worldgen:placement',
    'faction', [ref for ref, _ in E]); faction_presence = the first of tables.START_TYPE_PRESENCE[t]
    whose tables.PRESENCE_MIN_DENSITY <= density, else the last of them (QC-3 then patches the
    density). With E empty: faction_id None, faction_presence None.
  group (entity_type 'group'): group_descriptor = descriptor(rng, tx, hostile=False).
  start_relationship: 'none' when entity_type is 'none'; else pc.start_constraints.
    start_relationship_default when it is not 'none', else tables.START_TYPE_RELATIONSHIP[t] (and
    'neutral' when that is 'none' too).
  start_trust (entity_type not 'none'): lo, hi = tables.TRUST_RANGES[relationship] intersected with
    pc.start_constraints.start_trust_range and, for a faction, with the faction record's
    presence.start_trust_ranges[relationship] when it has one; an empty intersection falls back to
    the TRUST_RANGES range; start_trust = rng.range_int(tx, 'worldgen:placement', 'start_trust', lo, hi).
    entity_type 'none' -> start_trust None.
  Draw order: faction, descriptor (its three picks), start_trust — each only when it applies.

WG-12 descriptor(rng, tx, hostile) -> str   (Part X step 3: [dynamic] + [location type] + [rule])
  Three rng.choice draws on 'worldgen:placement' (purposes 'dynamic', 'location', 'rule') from
  atlas.GROUP_DYNAMICS / GROUP_LOCATIONS / GROUP_RULES (hostile: HOSTILE_DYNAMICS / HOSTILE_LOCATIONS /
  HOSTILE_RULES); f"{dynamic} {location} {rule}" cut to 60 characters at a word boundary.

WG-13 plausibility(values, placement, pc) -> 'pass' | 'fail' | 'hard_fail'   (QC-2, sub-question 1)
  v = values + {'entity_type': placement.entity_type, 'start_trust': placement.start_trust or 0}.
  'hard_fail' when pc.plausibility_gate.hard_fail_all is set and evaluates true, or (the faction
  protection rule) the method is 'faction_protection', pc.faction_start_type is 'always_in_faction'
  and there is no faction to be inside (entity_type != 'faction', or faction_id None); else 'pass'
  when ANY pass_any expression evaluates true; else 'fail'.

WG-14 qc(rng, tx, params, placement, pc, canon, difficulty) -> QCResult   (Part XII + hard-fail protocol)
  QCResult(params, placement, result 'pass' | 'patched' | 'aborted', patches: list[str]).
  patches starts with generate_params' contradiction patches (the caller passes them in params_patches).
  QC-2 (only when difficulty is in tables.QC2_ENFORCED): p = plausibility(...). 'fail' or 'hard_fail'
    -> the world is patched (Part XII): faction_density = max(2, density) (patch "QC-2:
    faction_density <old>-><new>" when it changed); for 'hard_fail' placement = place(...) again
    with the patched values (Steps 9-11 re-run; patch "QC-2: placed again"); then, when entity_type is 'none', the placement
    becomes a procedural group at 'neutral' (group_descriptor = descriptor(..., hostile=False),
    start_trust drawn as in place() for 'neutral' with no faction) (patch "QC-2: procedural group
    added"). Re-evaluate: 'hard_fail' -> result 'aborted' (nothing else runs); 'fail' after a
    first 'fail' -> patch "QC-2: soft fail kept" and continue.
  QC-3: entity_type 'faction' with a presence whose PRESENCE_MIN_DENSITY is above faction_density ->
    faction_density = that minimum (patch "QC-3: faction_density <old>-><new>"); start_trust outside
    TRUST_RANGES[start_relationship] -> clamped into it (patch "QC-3: start_trust <old>-><new>").
  A density patch changes params.b.faction_density (a new WorldParams, the rest unchanged).
  result: 'aborted' as above, else 'patched' when patches is not empty, else 'pass'.
  Abort message (WorldgenAborted, code 'hopeless_start'): f"{name} cannot survive the start this
  world gives them at {atlas.DIFFICULTY_LABELS[difficulty]}. Try one difficulty lower, another
  character, or another era." (name = the PC's identity name)
  (Part XII's automatic era shift and retries are the player's choices in the New Life wizard.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from ...contracts.worldgen import Placement, WorldParams

if TYPE_CHECKING:
    from ...contracts.common import Difficulty
    from ...contracts.content import FactionDossier
    from ...contracts.dossier import PCDossier
    from ...kernel.rng import Rng
    from ...kernel.store import Tx


@dataclass(frozen=True)
class QCResult:
    params: WorldParams
    placement: Placement
    result: Literal["pass", "patched", "aborted"]
    patches: list[str]


def eligible_factions(canon, values: dict) -> list[tuple[str, "FactionDossier"]]:
    raise NotImplementedError("P10")


def place(rng: "Rng", tx: "Tx", values: dict, pc: "PCDossier", canon) -> Placement:
    raise NotImplementedError("P10")


def descriptor(rng: "Rng", tx: "Tx", hostile: bool) -> str:
    raise NotImplementedError("P10")


def plausibility(values: dict, placement: Placement, pc: "PCDossier") -> Literal["pass", "fail", "hard_fail"]:
    raise NotImplementedError("P10")


def qc(rng: "Rng", tx: "Tx", params: WorldParams, placement: Placement, pc: "PCDossier", canon,
       difficulty: "Difficulty", params_patches: list[str]) -> QCResult:
    raise NotImplementedError("P10")
