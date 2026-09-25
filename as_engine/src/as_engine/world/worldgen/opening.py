"""WG8 — the player's character enters the world: where they stand, who knows them, what is coming for
them right now, what they have heard, and what they remember (P10). Rules WG-30, WG-33, QC-4, QC-5.
CMG §61 Parts IX-XI carried. docs/as/06_WORLD.md §1.3. Code decides everything that exists (rng
stream 'worldgen:opening'); WORLDGEN_OPENING only writes the four opening texts. Events: origin
'worldgen', turn_index 0, at = ``at``. values = params.flat_values(params); dsf =
params.days_since_fall; round = params.rnd. The PC is written exactly like anyone else (L12) — only
actors.controller 'human' and meta.pc_actor_id say who plays.

async place_pc(client, rng, tx, pc_ref, pc, params, placement, plan, region, people, canon, run_id,
               seed, qc, at) -> Opening
  1 Start place. home = people.home_settlement_id. The PC's entity has a settlement (its planned
    group's settlement) and start_relationship is 'ally' -> that settlement's site. Otherwise, in the
    start zone, the first building site by place id that is not a settlement site; none -> the first
    outdoor site; none -> the start zone's hub.
  2 The PC: physical.bodies.create (from the dossier as the scenario loader does: sex, age, height,
    mass, special, looks = appearance.looks (F1a, LOOK-01); origin 'worldgen'),
    physical.space.place_body at the start place's anchor,
    mind.actor.create (source 'pack', content_ref = pc_ref, controller 'human'), the dossier's
    starting_inventory through physical.objects.create (origin 'worldgen'; labels / containers as the
    loader), then, when looks is set, physical.objects.dress(tx, body, looks.outfit, at, None, 0,
    'worldgen') (LOOK-02: the PC starts in their own clothes),
    known_places for every place of the start zone and every road touching it (visited 1 for
    the start place), then PC_CONTROL_CHANGE {pc_actor_id} (writer 'kernel.meta'). A start place that
    is an ungenerated building gets its rooms now (physical.space.discover_layout); the start place
    is marked populated (physical.space.change_place props {populated: true}, reason 'populated')
    without spawning anything — the threat below is its danger.
    always_in_faction with an entity group -> group_members {role 'member', standing 0}.
    group_standing toward the PC: the entity group -> clamp(start_trust - 5, -5, 5); every planned
    faction named in pc.faction_standing -> that entry's standing (MATERIALIZE society.group).
  3 Contacts: the entity's settlement's quartermaster (people.roles) and its group's leader
    (people.leaders) — those that exist, in that order. For each: acquaintance both ways (known names, descriptions by describe_dossier),
    relationships both ways {kind 'acquaintance', trust = clamp(round((start_trust - 5) / 2), -2, 2)}
    (seeds, no delta).
  4 The threat (Part IX rule 2): the C-block parameter with the highest value; ties go to
    'hostile_human' when start_relationship is 'enemy', else to the first in the order hostile_human,
    runner_pressure, zombie_common, horde_pressure, lurker_pressure, ambient_danger. kind =
    atlas.THREAT_KINDS[it]; 'hostile_humans' with no planned hostile group -> 'shamblers'.
    near = the places one portal hop from the start place (not walls), by place id; far = those two
    hops away. The threat place = the first of far (else near) that is not a settlement site, not
    inside one and not inside the start place (a room of it).
      hostile_humans: n = 2 + (hostile_human >= 7) + (hostile_human >= 9) people (fewer when the band
        has fewer), materialised from the first hostile group's band cohort
        (society.population.materialise with settlement_id None, its home zone and archetype = the
        group id; PersonSeeds as WG6 on this stream — adult band, sex weighted over the band's
        cohorts, names from stream f"names:{group_id}" — and skeleton dossiers with occupation
        'raider', skills firearms 1 and brawling 1), group_members of that group (role 'member'),
        placed at the threat place; each gets PLAN_CHANGE {actor_id, goal_text 'find out what the
        stranger is carrying', steps ['follow the stranger', 'take what they carry']} (writer
        'mind.actor') upserting plans and actors.goal_text.
      shamblers: n = min(6, 3 + zombie_common // 3) ZOMBIE_ARCHETYPE_SHAMBLER01 bodies; runners: n =
        1 + runner_pressure // 5 ZOMBIE_VARIANT_ID_RUNNER01 bodies — each world.infected.spawn at the
        threat place, then world.infected.attract toward the start place (they are already coming).
      lurker_signs: 2 shamblers as above, and the trace below is claw marks.
    Telegraph: one TRACE in the start place (world.traces.create; kind 'tracks' — hostile: "Fresh
    boot prints, several people, circling back toward here."; infected: "Dragging footprints in the
    dust, many of them, heading this way." — or kind 'damage' for lurker_signs: "Deep claw gouges in
    the door frame, higher than a man could reach.").
  5 Leads (exploration magnets): candidates = building sites, not settlement sites, not the start
    place, whose archetype has at least one room with a loot table; ordered by rng.shuffle(sorted by
    place id, purpose 'magnets'), then stably re-ordered so sites in zones other than the start zone
    come first; the first 3 are the magnets. For each: a proposition {subject_type 'place', subject_id
    = site, predicate 'lead', text f"There is still something worth taking at {site name} in {zone
    name}."} held by the PC (believed 1, confidence 2, provenance 'told_by:<first contact>' or
    'common' without one) and by the first contact, and a known_places row for the PC. The bottleneck:
    the PC holds {subject_type 'place', subject_id = home's site, predicate 'shortage', text
    f"Everyone at {settlement name} is counting the {water|food}."} (the store WG4 made scarce:
    water when the water parameter <= food, else food). One PERCEIVE
    (writer 'mind.perception', seed: true) per holder.
  6 Opening texts: WORLDGEN_OPENING with WorldgenContext(stage='WG8', brief, fields={'pc': name,
    'place': start place name, 'zone': zone name, 'entities': [{'id', 'what'}] for the contacts, the
    threat bodies (or the trace for lurker signs), the magnets and the home settlement, 'params':
    {name: value} for the A and B blocks, 'placement': placement.model_dump(), 'budgets':
    tables.OPENING_BUDGETS}); the answer validates as OpeningPressure after QC-5 trims each text to
    its budget at a word boundary. QC-4: cites_entity_ids non-empty and all among the listed ids,
    cites_params non-empty and all A/B names. Failing -> one more call with fields['error'] = the
    problem; failing again -> fallback_opening(...) (code; qc patch "QC-4: opening written by code").
  7 PC survival history (WG-33): texts = the non-empty recap fields formative_incident_1,
    formative_incident_2, unresolved_complication, survival_pattern (in that order, at most 5), then
    code lines f"{first name} got through the first weeks near {start zone name}." and f"{first name}
    learned the roads around {start zone name} by heart." until there are 3; days = sorted
    rng.range_int(1, max(1, dsf - 1)) per text. Each: a history_events row {kind 'personal',
    subject_ids [the PC], truth_text = belief_text = text} (one WORLDGEN_STAGE {stage 'WG8', personal:
    n} for all of them) and an anchor
    episode for the PC {holder, at = day x DAY + 12 h, turn_index 0, summary = text, salience 95,
    anchor 1, subject_ids [the PC]} (ANCHOR_MEMORY, writer 'mind.memory').
  8 world_params.commit_json = WorldgenCommit(run_id, seed, pc_ref, params, placement,
    start_zone_type = the start zone's kind, start_district_type = the start place's archetype name
    or kind, opening, qc_result, qc_patches, skeleton — P11, D-95: the region, the plan and this
    Opening as contracts.worldgen.WorldgenCommit.skeleton describes) (WORLDGEN_STAGE {stage: 'WG8',
    commit: true}, writer 'world.worldgen').
  Opening(pc_body, start_place_id, contacts, threat_kind, threat_place_id, threat_ids, magnets,
  telegraph_trace_id, opening: OpeningPressure).

fallback_opening(pc_name, start_place_name, contacts, threat_kind, threat_ids, threat_place_name,
                 values) -> OpeningPressure   (implemented below)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ...contracts.worldgen import OpeningPressure

if TYPE_CHECKING:
    from ...contracts.dossier import PCDossier
    from ...contracts.worldgen import Placement, WorldParams
    from ...kernel.rng import Rng
    from ...kernel.store import Tx
    from .history import PolityPlan
    from .people import People
    from .region import Region


@dataclass
class Opening:
    pc_body: str
    start_place_id: str
    contacts: list[str] = field(default_factory=list)
    threat_kind: str = ""
    threat_place_id: str | None = None
    threat_ids: list[str] = field(default_factory=list)
    magnets: list[str] = field(default_factory=list)
    telegraph_trace_id: str | None = None
    opening: OpeningPressure | None = None


def _trim(text: str, n: int) -> str:
    if len(text) <= n:
        return text
    cut = text[: n - 1].rsplit(" ", 1)[0].rstrip(",;: ")
    return cut + "…"


def fallback_opening(pc_name: str, start_place_name: str, contacts: list[tuple[str, str]], threat_kind: str,
                     threat_ids: list[str], threat_place_name: str, values: dict) -> OpeningPressure:
    """The code-written opening when the model's fails QC-4 twice (implemented). ``contacts`` are
    (id, name) pairs. Cites the threat bodies (or the contacts) and the A/B parameter furthest from 5."""
    first = pc_name.split()[0]
    what = {"hostile_humans": "armed strangers", "shamblers": "infected", "runners": "fast infected",
            "lurker_signs": "infected"}.get(threat_kind, "infected")
    n = len(threat_ids)
    ab = ("atmo_visibility", "climate_heat", "climate_moisture", "instability", "social_order", "survivor_mentality",
          "faction_density", "faction_fragmentation", "faction_relations", "atrocity_capacity")
    param = max(ab, key=lambda k: (abs(int(values[k]) - 5), -ab.index(k)))
    names = ", ".join(nm for _i, nm in contacts) or "no one close"
    return OpeningPressure(
        immediate_contacts=_trim(f"{names} — the people {first} can reach before dark.", 150),
        immediate_liabilities=_trim(f"{first} is carrying finds other people want, and it shows.", 150),
        opening_pressure=_trim(f"{n} {what} are moving toward {start_place_name} from {threat_place_name}, "
                               f"and they will be here within the hour.", 200),
        first_objective=_trim(f"Get what matters out of {start_place_name} and reach cover before they arrive.", 150),
        cites_entity_ids=list(threat_ids) or [i for i, _n in contacts] or ["none"],
        cites_params=[param],
    )


async def place_pc(client, rng: "Rng", tx: "Tx", pc_ref: str, pc: "PCDossier", params: "WorldParams",
                   placement: "Placement", plan: "PolityPlan", region: "Region", people: "People", canon,
                   run_id: str, seed: int, qc, at: int) -> Opening:
    raise NotImplementedError("P10")
from ._impl_wg import place_pc  # noqa
