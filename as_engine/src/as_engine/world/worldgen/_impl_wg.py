"""Implementation of P10 worldgen. Written from the module docstrings."""
from __future__ import annotations

import asyncio
import inspect
import json
import math

from ...contracts.common import Difficulty, Era
from ...contracts.events import Event, EventType, WriteOp, WriteRecord
from ...contracts.worldgen import (ABlock, BBlock, CBlock, DBlock, EBlock, OpeningPressure, Placement,
                                   SimMechanics, WorldgenCommit, WorldgenProgress, WorldParams)
from ...kernel.errors import SettingsError
from . import atlas, tables
from .conditions import evaluate


def rnd(x):
    return math.floor(x + 0.5)


def flat_values(params):
    from .params import flat_values as f
    return f(params)


def climate_descriptor(h, m):
    from .params import climate_descriptor as c
    return c(h, m)

DAY = 86_400_000
H = 3_600_000
SP = "worldgen:params"
A_NAMES = ("atmo_visibility", "climate_heat", "climate_moisture", "instability")
B_NAMES = ("social_order", "survivor_mentality", "faction_density", "faction_fragmentation", "faction_relations",
           "atrocity_capacity")
E_NAMES = ("mystery", "ritual_intensity", "subtle_anomaly", "lost_knowledge", "wildcard_level")
C_NAMES = ("ambient_danger", "zombie_common", "horde_pressure", "runner_pressure", "lurker_pressure", "hostile_human")
ZOMBIE_C = ("zombie_common", "horde_pressure", "runner_pressure", "lurker_pressure")


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def W(table, values, op=WriteOp.INSERT, key=None):
    return WriteRecord(op=op, table=table, key=key or {}, values=values)


def commit(tx, type_, writer, at, writes, payload, *, origin="worldgen", actor_id=None, place_id=None, cause=None,
           turn_index=0, target_ids=None):
    return tx.commit_event(Event(type=type_, writer=writer, at=at, turn_index=turn_index, origin=origin,
                                 actor_id=actor_id, place_id=place_id, cause_event_id=cause, writes=writes,
                                 payload=payload, target_ids=target_ids or []))


# ------------------------------------------------------------------------------------------ WG0 params
def generate_params(rng, tx, difficulty, era, bias, days_since_fall, *, fall_range=None, pc_name=""):
    difficulty, era = Difficulty(difficulty), Era(era)
    v: dict = {}
    for name in tables.DRAW_ORDER:
        if name in tables.DIFFICULTY_BANDS:
            lo, hi = tables.DIFFICULTY_BANDS[name][difficulty]
            v[name] = rng.range_int(tx, SP, name, lo, hi)
        elif name in A_NAMES:
            b = getattr(bias, name, 0.0)
            v[name] = _clamp(rnd(5 + b * 5) + rng.range_int(tx, SP, name, -1, 1), 1, 10)
        elif name == "hazard_type":
            v[name] = rng.weighted(tx, SP, name, list(tables.HAZARD_TYPE_WEIGHTS))
        elif name in B_NAMES:
            fl, ce = tables.ERA_B_CONSTRAINTS[era].get(name, (1, 10))
            half = (ce - fl) / 2
            mid = fl + half
            adj = _clamp(rnd(mid + getattr(bias, name, 0.0) * half), fl, ce)
            v[name] = _clamp(adj + rng.range_int(tx, SP, name, -1, 1), fl, ce)
        elif name in E_NAMES:
            b = getattr(bias, name, 0.0)
            v[name] = _clamp(rnd(5 + b * 5) + rng.range_int(tx, SP, name, -2, 2), 1, 10)
        elif name == "days_since_fall":
            from ...contracts.settings import ERA_DAYS_RANGE
            lo, hi = ERA_DAYS_RANGE[era]
            if fall_range is not None:
                lo2, hi2 = max(lo, fall_range[0]), min(hi, fall_range[1])
            else:
                lo2, hi2 = lo, hi
            if days_since_fall is not None:
                if fall_range is not None and not (fall_range[0] <= days_since_fall <= fall_range[1]):
                    raise SettingsError(f"{pc_name}'s age and history need a world {fall_range[0] // 365}-"
                                        f"{fall_range[1] // 365} years after the Fall.", rule="WG-34")
                v[name] = days_since_fall
            else:
                if lo2 > hi2:
                    a, b = fall_range
                    raise SettingsError(f"{pc_name}'s age and history need a world {a // 365}-{b // 365} years after "
                                        f"the Fall.", rule="WG-34")
                v[name] = rng.range_int(tx, SP, name, lo2, hi2)
    v, patches = apply_contradictions(v, era)
    types = key_resource_type(v, v["hazard_type"])
    ktype = types[0] if len(types) == 1 else rng.choice(tx, SP, "key_resource_type", types)
    desc = rng.choice(tx, SP, "key_resource", list(atlas.KEY_RESOURCE_DESCRIPTORS[ktype]))
    snow, warn, rec = tables.SIM_MECHANICS[difficulty]
    params = WorldParams(
        difficulty=difficulty, era=era, days_since_fall=v["days_since_fall"],
        a=ABlock(**{k: v[k] for k in A_NAMES}, hazard_type=v["hazard_type"], hazard_severity=v["hazard_severity"]),
        b=BBlock(**{k: v[k] for k in B_NAMES}),
        c=CBlock(**{k: v[k] for k in C_NAMES}),
        d=DBlock(food=v["food"], water=v["water"], ammo=v["ammo"], fuel=v["fuel"], meds=v["meds"],
                 tech_baseline=v["tech_baseline"], tech_preservation=v["tech_preservation"],
                 key_resource=f"{ktype} — {desc}"),
        e=EBlock(**{k: v[k] for k in E_NAMES}),
        sim=SimMechanics(snowball_rate=snow, warning_slack=warn, recovery_slack=rec),
        climate_descriptor=climate_descriptor(v["climate_heat"], v["climate_moisture"]))
    return params, patches


def _cmp(a, op, b):
    return {">=": a >= b, "<=": a <= b, "==": a == b, "!=": a != b, ">": a > b, "<": a < b}[op]


def apply_contradictions(values, era):
    era = Era(era)
    v = dict(values)
    patches = []

    def flagged(row):
        _id, hp, hop, hv, lp, lop, lv, _ov = row
        hi_ok = (era == Era.EARLY) if hp == "era=early" else _cmp(v[hp], hop, hv)
        return hi_ok and _cmp(v[lp], lop, lv)

    for _pass in range(2):
        for row in tables.CONTRADICTIONS:
            if flagged(row):
                _id, _hp, _hop, _hv, lp, lop, lv, _ov = row
                old = v[lp]
                v[lp] = lv - 1 if lop == ">=" else lv + 1
                patches.append(f"#{_id}: {lp} {old}->{v[lp]}")
    for row in tables.CONTRADICTIONS:
        if flagged(row):
            v[row[4]] = row[7]
            patches.append(f"STEP 7 OVERRIDE #{row[0]}")
    return v, patches


def key_resource_type(values, hazard_type):
    v = values
    if v["food"] <= 3 or v["water"] <= 3:
        return ["supply node"]
    if v["tech_preservation"] >= 7 and v["tech_baseline"] >= 6:
        return ["infrastructure"]
    if hazard_type == "biological" and v["hazard_severity"] >= 6:
        return ["biological"]
    if v["faction_density"] >= 6 and v["faction_fragmentation"] >= 6:
        return ["territory"]
    m = max(v[k] for k in C_NAMES)
    top = [k for k in C_NAMES if v[k] == m]
    if top == ["hostile_human"]:
        return ["information source", "territory"]
    if len(top) == 1 and top[0] in ZOMBIE_C:
        return ["supply node", "infrastructure"]
    return ["supply node", "infrastructure", "biological", "territory", "information source"]


# --------------------------------------------------------------------------------------- placement
SPL = "worldgen:placement"


def _factions(canon, values, enclaves):
    out = []
    for ref in canon.refs("faction"):
        f = canon.get(ref)
        if f.kind != "faction" or (f.behaviour.enclave is not None) != enclaves:
            continue
        if all(evaluate(e, values) for e in f.presence.presence_conditions):
            out.append((ref, f))
    return out


def eligible_factions(canon, values):
    return _factions(canon, values, False)


def enclave_factions(canon, values):
    return _factions(canon, values, True)


def descriptor(rng, tx, hostile):
    dyn = rng.choice(tx, SPL, "dynamic", list(atlas.HOSTILE_DYNAMICS if hostile else atlas.GROUP_DYNAMICS))
    loc = rng.choice(tx, SPL, "location", list(atlas.HOSTILE_LOCATIONS if hostile else atlas.GROUP_LOCATIONS))
    rule = rng.choice(tx, SPL, "rule", list(atlas.HOSTILE_RULES if hostile else atlas.GROUP_RULES))
    text = f"{dyn} {loc} {rule}"
    if len(text) > 60:
        text = text[:60].rsplit(" ", 1)[0]
    return text


def _trust(rng, tx, rel, pc, faction):
    lo, hi = tables.TRUST_RANGES[rel]
    a, b = pc.start_constraints.start_trust_range
    lo2, hi2 = max(lo, a), min(hi, b)
    if faction is not None and rel in faction.presence.start_trust_ranges:
        fa, fb = faction.presence.start_trust_ranges[rel]
        lo2, hi2 = max(lo2, fa), min(hi2, fb)
    if lo2 > hi2:
        lo2, hi2 = lo, hi
    return rng.range_int(tx, SPL, "start_trust", lo2, hi2)


def place(rng, tx, values, pc, canon):
    t = pc.faction_start_type
    E = eligible_factions(canon, values)
    density = values["faction_density"]
    pref = pc.start_constraints.faction_present_preferred
    if t == "always_in_faction":
        et = "faction"
    elif t == "usually_adjacent":
        et = "faction" if (E and density >= 3 and pref != "no") else "group"
    elif t == "outsider_tied":
        et = "faction" if (E and pref != "no") else "none"
    else:
        et = "group" if density >= 2 else "none"
    fid = pres = gdesc = None
    frec = None
    if et == "faction" and E:
        fid = rng.choice(tx, SPL, "faction", [r for r, _ in E])
        frec = dict(E)[fid]
        allowed = tables.START_TYPE_PRESENCE[t]
        pres = next((p for p in allowed if tables.PRESENCE_MIN_DENSITY[p] <= density), allowed[-1] if allowed else None)
    if et == "group":
        gdesc = descriptor(rng, tx, False)
    if et == "none":
        rel = "none"
    else:
        d = pc.start_constraints.start_relationship_default
        rel = d if d != "none" else tables.START_TYPE_RELATIONSHIP[t]
        if rel == "none":
            rel = "neutral"
    trust = None if et == "none" else _trust(rng, tx, rel, pc, frec)
    return Placement(entity_type=et, faction_id=fid, faction_presence=pres, group_descriptor=gdesc,
                     start_trust=trust, start_relationship=rel)


def plausibility(values, placement, pc):
    v = dict(values)
    v["entity_type"] = placement.entity_type
    v["start_trust"] = placement.start_trust or 0
    g = pc.plausibility_gate
    if g.hard_fail_all and evaluate(g.hard_fail_all, v):
        return "hard_fail"
    if g.method == "faction_protection" and pc.faction_start_type == "always_in_faction" and (
            placement.entity_type != "faction" or placement.faction_id is None):
        return "hard_fail"
    if any(evaluate(e, v) for e in g.pass_any):
        return "pass"
    return "fail"


def _with_density(params, density):
    b = params.b.model_copy(update={"faction_density": density})
    return params.model_copy(update={"b": b})


def qc(rng, tx, params, placement, pc, canon, difficulty, params_patches):
    from .placement import QCResult
    patches = list(params_patches)
    values = flat_values(params)
    if Difficulty(difficulty) in tables.QC2_ENFORCED:
        p = plausibility(values, placement, pc)
        if p in ("fail", "hard_fail"):
            old = params.b.faction_density
            new = max(2, old)
            if new != old:
                params = _with_density(params, new)
                patches.append(f"QC-2: faction_density {old}->{new}")
            values = flat_values(params)
            if p == "fail":
                if placement.entity_type == "none":
                    gd = descriptor(rng, tx, False)
                    tr = _trust(rng, tx, "neutral", pc, None)
                    placement = Placement(entity_type="group", group_descriptor=gd, start_trust=tr,
                                          start_relationship="neutral")
                    patches.append("QC-2: procedural group added")
                if plausibility(values, placement, pc) == "fail":
                    patches.append("QC-2: soft fail kept")
            else:
                placement = place(rng, tx, values, pc, canon)
                patches.append("QC-2: placed again")
                if placement.entity_type == "none":
                    gd = descriptor(rng, tx, False)
                    tr = _trust(rng, tx, "neutral", pc, None)
                    placement = Placement(entity_type="group", group_descriptor=gd, start_trust=tr,
                                          start_relationship="neutral")
                    patches.append("QC-2: procedural group added")
                if plausibility(values, placement, pc) == "hard_fail":
                    return QCResult(params, placement, "aborted", patches)
    if placement.entity_type == "faction" and placement.faction_presence:
        need = tables.PRESENCE_MIN_DENSITY[placement.faction_presence]
        if params.b.faction_density < need:
            old = params.b.faction_density
            params = _with_density(params, need)
            patches.append(f"QC-3: faction_density {old}->{need}")
    if placement.start_trust is not None and placement.start_relationship in tables.TRUST_RANGES:
        lo, hi = tables.TRUST_RANGES[placement.start_relationship]
        if not (lo <= placement.start_trust <= hi):
            new = _clamp(placement.start_trust, lo, hi)
            patches.append(f"QC-3: start_trust {placement.start_trust}->{new}")
            placement = placement.model_copy(update={"start_trust": new})
    return QCResult(params, placement, "patched" if patches else "pass", patches)


# ------------------------------------------------------------------------------------------- WG1 region
SR = "worldgen:region"


def _first_names_record(canon):
    return canon.get(canon.refs("names")[0])


def build_region(rng, tx, params, detail, canon, at):
    from .region import Region, Route, Zone, danger
    T = tables.DETAIL_TIERS[detail]
    values = flat_values(params)
    n = T["zones"]
    kinds = [rng.weighted(tx, SR, "start_kind", list(atlas.START_ZONE_WEIGHTS))]
    for i in range(1, n):
        k = rng.weighted(tx, SR, f"kind:{i}", list(atlas.ZONE_WEIGHTS))
        if k == "wilds" and "wilds" in kinds:       # at most one zone without buildings (WG-35 1)
            k = rng.weighted(tx, SR, f"kind:{i}:again", [(x, w) for x, w in atlas.ZONE_WEIGHTS if x != "wilds"])
        kinds.append(k)
    used, names = set(), []
    for i, k in enumerate(kinds):
        pool = [x for x in atlas.ZONE_NAMES[k] if x not in used]
        nm = rng.choice(tx, SR, f"name:{i}", pool)
        used.add(nm)
        names.append(nm)
    fam = list(_first_names_record(canon).family)
    zones = []
    for i, (k, nm) in enumerate(zip(kinds, names)):
        zid = tx.mint("zon")
        ws = [W("zones", {"zone_id": zid, "name": nm, "kind": k, "content_ref": None, "danger": danger(values, k)})]
        hub = tx.mint("plc")
        ws.append(W("places", {"place_id": hub, "zone_id": zid, "parent_id": None, "kind": "street", "name": nm,
                               "archetype_ref": None, "width_m": 60.0, "depth_m": 20.0, "indoor": 0,
                               "material": "open_air", "light_level": 3, "ambient_db": 35.0, "layout_generated": 1,
                               "held": 0, "props": {}}))
        ws.append(W("anchors", {"anchor_id": tx.mint("anc"), "place_id": hub, "name": "the middle of the street",
                                "kind": "feature", "x_m": 30.0, "y_m": 10.0, "cover": 0, "concealment": 0, "capacity": 4}))
        arch = [r for r in canon.refs("building") if canon.get(r).kind in atlas.ZONE_BUILDING_KINDS[k]]
        sites, seen = [], {}
        for j in range(T["places_per_zone"]):
            sid = tx.mint("plc")
            if not arch:
                name = rng.choice(tx, SR, f"outdoor:{i}:{j}", list(atlas.OUTDOOR_PLACE_NAMES))
                vals = {"place_id": sid, "zone_id": zid, "parent_id": None, "kind": "outdoor", "archetype_ref": None,
                        "width_m": 20.0, "depth_m": 20.0, "indoor": 0, "material": "open_air", "light_level": 3,
                        "ambient_db": 30.0, "layout_generated": 1, "held": 0, "props": {}}
                anc = ("the middle", 10.0, 10.0)
            else:
                ref = rng.choice(tx, SR, f"building:{i}:{j}", arch)
                a = canon.get(ref)
                if a.kind in ("house", "apartment"):
                    f = rng.choice(tx, SR, f"family:{i}:{j}", fam)
                    name = f"The {f} {'house' if a.kind == 'house' else 'apartment'}"
                else:
                    name = a.name
                vals = {"place_id": sid, "zone_id": zid, "parent_id": None, "kind": "building", "archetype_ref": ref,
                        "width_m": 15.0, "depth_m": 10.0, "indoor": 0, "material": "open_air", "light_level": 3,
                        "ambient_db": 32.0, "layout_generated": 0, "held": 0, "props": {}}
                anc = ("the front", 7.5, 1.0)
            seen[name] = seen.get(name, 0) + 1
            if seen[name] > 1:
                name = f"{name} ({seen[name]})"
            vals["name"] = name
            ws.append(W("places", vals))
            aid = tx.mint("anc")
            ws.append(W("anchors", {"anchor_id": aid, "place_id": sid, "name": anc[0], "kind": "feature", "x_m": anc[1],
                                    "y_m": anc[2], "cover": 0, "concealment": 0, "capacity": 4}))
            from ...mind.perception import place_phrase
            fid = tx.mint("anc")
            front = (f"the front of {place_phrase(name)}" if arch else f"the path to {place_phrase(name)}")
            ws.append(W("anchors", {"anchor_id": fid, "place_id": hub, "name": front, "kind": "feature",
                                    "x_m": round(60.0 * (j + 0.5) / T["places_per_zone"], 1),
                                    "y_m": 1.0 if j % 2 == 0 else 19.0, "cover": 0, "concealment": 0, "capacity": 4}))
            pname = name[0].lower() + name[1:] if name.startswith("The ") else name
            ws.append(W("portals", _opening(tx, hub, sid, fid, aid, f"the way to {pname}", 300)))
            sites.append(sid)
        ev = commit(tx, EventType.PLACE_DISCOVERED, "physical.space", at, ws,
                    {"zone_id": zid, "places": [hub] + sites, "source": "worldgen"})
        zones.append(Zone(zid, k, nm, hub, tuple(sites)))
    pairs = [(i, (i + 1) % n) for i in range(n)]
    pairs = [(min(a, b), max(a, b)) for a, b in pairs]
    ring = list(dict.fromkeys(pairs))
    chords = []
    for i in range(n):
        for j in range(i + 1, n):
            if (i, j) in ring:
                continue
            if rng.chance(tx, SR, f"chord:{i}:{j}", atlas.CHORD_CHANCE):
                chords.append((i, j))
    routes = []
    for i, j in ring + chords:
        dist = rng.range_int(tx, SR, f"distance:{i}:{j}", *atlas.ROUTE_DISTANCE_M)
        za, zb = zones[i], zones[j]
        A, B = za.name, zb.name
        road, rid = tx.mint("plc"), tx.mint("rte")
        ae, be = tx.mint("anc"), tx.mint("anc")
        ws = [W("places", {"place_id": road, "zone_id": za.zone_id, "parent_id": None, "kind": "street",
                           "name": f"The road from {A} to {B}", "archetype_ref": None, "width_m": float(dist),
                           "depth_m": 8.0, "indoor": 0, "material": "open_air", "light_level": 3, "ambient_db": 30.0,
                           "layout_generated": 1, "held": 0, "props": {}}),
              W("anchors", {"anchor_id": ae, "place_id": road, "name": f"the {A} end", "kind": "feature", "x_m": 0.5,
                            "y_m": 4.0, "cover": 0, "concealment": 0, "capacity": 4}),
              W("anchors", {"anchor_id": be, "place_id": road, "name": f"the {B} end", "kind": "feature",
                            "x_m": float(dist) - 0.5, "y_m": 4.0, "cover": 0, "concealment": 0, "capacity": 4}),
              W("portals", _opening(tx, za.hub_id, road, None, ae, f"the {A} end of the road to {B}", 400)),
              W("portals", _opening(tx, road, zb.hub_id, be, None, f"the {B} end of the road to {A}", 400))]
        dz = lambda z: json.loads(tx.query_one("SELECT danger FROM zones WHERE zone_id=?", (z,))[0])["shambler"]  # noqa: E731
        ws.append(W("routes", {"route_id": rid, "from_place": za.hub_id, "to_place": zb.hub_id, "distance_m": float(dist),
                               "terrain": "road", "danger": max(dz(za.zone_id), dz(zb.zone_id)), "known_by_default": 1}))
        commit(tx, EventType.PLACE_DISCOVERED, "physical.space", at, ws, {"route_id": rid, "place_id": road, "source": "worldgen"})
        routes.append(Route(rid, za.zone_id, zb.zone_id, road))
    exterior = []
    for k, dr in enumerate(atlas.EXTERIOR_DIRECTIONS):
        zid, nm = tx.mint("zon"), atlas.EXTERIOR_NAMES[dr]
        hub = tx.mint("plc")
        ws = [W("zones", {"zone_id": zid, "name": nm, "kind": "exterior", "content_ref": None,
                          "danger": {key: 10 for key in danger(values, "residential")}}),
              W("places", {"place_id": hub, "zone_id": zid, "parent_id": None, "kind": "street", "name": nm,
                           "archetype_ref": None, "width_m": 80.0, "depth_m": 30.0, "indoor": 0, "material": "open_air",
                           "light_level": 3, "ambient_db": 40.0, "layout_generated": 1, "held": 0, "props": {}}),
              W("anchors", {"anchor_id": tx.mint("anc"), "place_id": hub, "name": "the middle of the road", "kind": "feature",
                            "x_m": 40.0, "y_m": 15.0, "cover": 0, "concealment": 0, "capacity": 4})]
        commit(tx, EventType.PLACE_DISCOVERED, "physical.space", at, ws, {"zone_id": zid, "places": [hub], "source": "worldgen"})
        g = zones[(k * n) // 4]
        dist = rng.range_int(tx, SR, f"exterior:{dr}", *atlas.EXTERIOR_DISTANCE_M)
        A, B = g.name, nm
        road, rid = tx.mint("plc"), tx.mint("rte")
        ae, be = tx.mint("anc"), tx.mint("anc")
        ws = [W("places", {"place_id": road, "zone_id": g.zone_id, "parent_id": None, "kind": "street",
                           "name": f"The road {dr} out of {A}", "archetype_ref": None, "width_m": float(dist),
                           "depth_m": 8.0, "indoor": 0, "material": "open_air", "light_level": 3, "ambient_db": 30.0,
                           "layout_generated": 1, "held": 0, "props": {}}),
              W("anchors", {"anchor_id": ae, "place_id": road, "name": f"the {A} end", "kind": "feature", "x_m": 0.5,
                            "y_m": 4.0, "cover": 0, "concealment": 0, "capacity": 4}),
              W("anchors", {"anchor_id": be, "place_id": road, "name": f"the {B} end", "kind": "feature",
                            "x_m": float(dist) - 0.5, "y_m": 4.0, "cover": 0, "concealment": 0, "capacity": 4}),
              W("portals", _opening(tx, g.hub_id, road, None, ae, f"the {A} end of the road to {B}", 400)),
              W("portals", _opening(tx, road, hub, be, None, f"the {B} end of the road to {A}", 400)),
              W("routes", {"route_id": rid, "from_place": g.hub_id, "to_place": hub, "distance_m": float(dist),
                           "terrain": "road", "danger": 10, "known_by_default": 1})]
        commit(tx, EventType.PLACE_DISCOVERED, "physical.space", at, ws, {"route_id": rid, "place_id": road, "source": "worldgen"})
        routes.append(Route(rid, g.zone_id, zid, road))
        exterior.append(Zone(zid, "exterior", nm, hub, ()))
    from .. import hordes
    hordes.seed_pools(tx, params, at)
    return Region(tuple(zones), tuple(routes), zones[0].zone_id, exterior=tuple(exterior))


def _opening(tx, a, b, anchor_a, anchor_b, name, size):
    return {"portal_id": tx.mint("prt"), "place_a": a, "place_b": b, "anchor_a": anchor_a, "anchor_b": anchor_b,
            "kind": "opening", "name": name, "is_open": 1, "is_locked": 0, "lock_quality": 0, "barricade": 0, "damage": 0,
            "aperture_w_cm": size, "aperture_h_cm": size, "seal_db": 0.0, "open_loss_db": 0.0, "transparent": 1,
            "height_cm": 0}


def _route_edges(store, region):
    hub_zone = {z.hub_id: z.zone_id for z in region.zones}
    out = []
    for r in store.query("SELECT from_place, to_place FROM routes ORDER BY route_id"):
        if r[0] in hub_zone and r[1] in hub_zone:
            out.append((hub_zone[r[0]], hub_zone[r[1]]))
    return out


def _edge_disjoint_paths(edges, start, goal):
    # max-flow with unit capacities over the undirected zone graph (the routes rows)
    count = 0
    used = set()
    for _ in range(3):
        # BFS over edges not yet used, undirected
        prev = {start: None}
        q = [start]
        while q:
            u = q.pop(0)
            for k, (a, b) in enumerate(edges):
                if k in used:
                    continue
                for x, y in ((a, b), (b, a)):
                    if x == u and y not in prev:
                        prev[y] = (u, k)
                        q.append(y)
        if goal not in prev:
            break
        v = goal
        while prev[v] is not None:
            u, k = prev[v]
            used.add(k)
            v = u
        count += 1
    return count


def assert_region(store, region):
    from .pipeline import WorldgenAssertion
    places = [z.hub_id for z in region.zones] + [s for z in region.zones for s in z.site_ids] + [r.road_id for r in region.routes]
    start = next(z.hub_id for z in region.zones if z.zone_id == region.start_zone_id)
    seen, q = {start}, [start]
    while q:
        u = q.pop()
        for r in store.query("SELECT place_a, place_b FROM portals WHERE kind != 'wall' AND (place_a=? OR place_b=?)", (u, u)):
            v = r[1] if r[0] == u else r[0]
            if v not in seen:
                seen.add(v)
                q.append(v)
    missing = [p for p in places if p not in seen]
    if missing:
        raise WorldgenAssertion("WG1", f"{len(missing)} places cannot be reached")
    if not any(_edge_disjoint_paths(_route_edges(store, region), region.start_zone_id, z.zone_id) >= 2
               for z in region.zones if z.zone_id != region.start_zone_id):
        raise WorldgenAssertion("WG1", "the start zone has only one way out")


# ------------------------------------------------------------------------------------------ WG2 history
SH = "worldgen:history"


def _family_names(canon):
    return list(_first_names_record(canon).family)


def _proc_name(rng, tx, canon, n):
    fam = rng.choice(tx, SH, f"group_family:{n}", _family_names(canon))
    noun = rng.choice(tx, SH, f"group_noun:{n}", list(atlas.GROUP_NOUNS))
    return f"The {fam} {noun}"


def plan_polity(rng, tx, params, placement, region, canon):
    from .history import PlannedGroup, PlannedSettlement, PolityPlan
    values = flat_values(params)
    dens, frag = values["faction_density"], values["faction_fragmentation"]
    E = eligible_factions(canon, values)
    k = min(len(E), 1 + dens // 4)
    order = []
    if placement.faction_id:
        order.append(placement.faction_id)
    order += [r for r, _ in E if r not in order]
    order = order[:k]
    recs = dict(E)
    for r, rec in enclave_factions(canon, values):       # P10 enclaves, on top of the k
        recs[r] = rec
        order.append(r)
    groups = []   # dicts, frozen at the end
    dominant = False
    for ref in order:
        if recs[ref].behaviour.enclave is not None:
            pres = "active"
        elif ref == placement.faction_id:
            pres = placement.faction_presence
        elif dens >= 6 and frag <= 4 and not dominant:
            pres = "dominant"
        elif dens >= 3:
            pres = "active"
        else:
            pres = "peripheral"
        dominant = dominant or pres == "dominant"
        groups.append({"group_id": tx.mint("grp"), "kind": "faction", "name": recs[ref].name, "content_ref": ref,
                       "descriptor": None, "presence": pres, "hostile": False,
                       "is_pc_entity": placement.entity_type == "faction" and ref == placement.faction_id})
    g = max(0, dens // 3 - k)
    descs = []
    if placement.entity_type == "group":
        g = max(g, 1)
        descs.append((placement.group_descriptor, True))
    while len(descs) < g:
        descs.append((descriptor(rng, tx, False), False))
    hh = values["hostile_human"]
    nh = 2 if hh >= 8 else 1 if hh >= 5 else 0
    n = 0
    for d, pc_entity in descs:
        groups.append({"group_id": tx.mint("grp"), "kind": "group", "name": _proc_name(rng, tx, canon, n), "content_ref": None,
                       "descriptor": d, "presence": None, "hostile": False, "is_pc_entity": pc_entity})
        n += 1
    for _ in range(nh):
        d = descriptor(rng, tx, True)
        groups.append({"group_id": tx.mint("grp"), "kind": "group", "name": _proc_name(rng, tx, canon, n), "content_ref": None,
                       "descriptor": d, "presence": None, "hostile": True, "is_pc_entity": False})
        n += 1
    stl_groups = [gg for gg in groups if not gg["hostile"] and gg["presence"] != "peripheral"]
    if not stl_groups:
        gg = {"group_id": tx.mint("grp"), "kind": "group", "name": _proc_name(rng, tx, canon, n), "content_ref": None,
              "descriptor": descriptor(rng, tx, False), "presence": None, "hostile": False, "is_pc_entity": False}
        groups.append(gg)
        stl_groups = [gg]
    zones = list(region.zones)
    start = next(z for z in zones if z.zone_id == region.start_zone_id)
    seq = [z for z in zones if z.zone_id != start.zone_id] + [start]
    used_sites, used_names, settlements = set(), set(), []
    so = values["social_order"]
    suffix = next(sf for key, sf in atlas.SETTLEMENT_SUFFIX if key >= so)
    i = 0
    for gg in stl_groups:
        enc = recs[gg["content_ref"]].behaviour.enclave if gg["content_ref"] in recs else None
        if enc is not None:
            z = None
            for kind in enc.zone_kinds:
                z = next((zz for zz in zones if zz.kind == kind), None)
                if z is not None:
                    break
            z = z or zones[-1]
            site = _enclave_place(tx, z, gg["content_ref"], enc)
            sid = tx.mint("stl")
            pop = rng.range_int(tx, SH, f"population:{sid}", *enc.population)
            settlements.append(PlannedSettlement(sid, gg["group_id"], z.zone_id, site, enc.name, pop))
            used_names.add(enc.name)
            gg["_zone"] = z.zone_id
            continue
        if gg["is_pc_entity"]:
            z = start
        else:
            z = seq[i % len(seq)]
            i += 1
        cands = []
        for sid in z.site_ids:
            if sid in used_sites:
                continue
            r = tx.query_one("SELECT kind, archetype_ref FROM places WHERE place_id=?", (sid,))
            if r[0] != "building" or not r[1]:
                continue
            ak = canon.get(r[1]).kind
            if ak in atlas.SETTLEMENT_SITE_KINDS:
                cands.append((atlas.SETTLEMENT_SITE_KINDS.index(ak), sid))
        site = min(cands)[1] if cands else z.hub_id
        used_sites.add(site)
        name = f"{z.name} {suffix}"
        if name in used_names:
            name = f"{name} ({gg['name']})"
        used_names.add(name)
        sid = tx.mint("stl")
        bonus = {"dominant": 2, "active": 1}.get(gg["presence"] or "", 0)
        pop = rng.range_int(tx, SH, f"population:{sid}", 18, 30) + 6 * bonus
        settlements.append(PlannedSettlement(sid, gg["group_id"], z.zone_id, site, name, pop))
        gg["_zone"] = z.zone_id
    kinds = {z.kind: z.zone_id for z in reversed(zones)}
    out = []
    for gg in groups:
        if gg.get("_zone"):
            hz = gg["_zone"]
        elif gg["hostile"]:
            hz = kinds.get("highway") or kinds.get("industrial") or zones[-1].zone_id
        else:
            hz = None
        out.append(PlannedGroup(gg["group_id"], gg["kind"], gg["name"], gg["content_ref"], gg["descriptor"], gg["presence"],
                                gg["hostile"], gg["is_pc_entity"], hz))
    return PolityPlan(tuple(out), tuple(settlements))


def _enclave_place(tx, z, faction_ref, enc):
    # P10 WG-18: the enclave's own sealed place behind one locked gate.
    at = tx.query_one("SELECT now_ms FROM world_clock")[0]
    site = tx.mint("plc")
    crown, council = tx.mint("anc"), tx.mint("anc")
    ws = [W("places", {"place_id": site, "zone_id": z.zone_id, "parent_id": None, "kind": "tunnel", "name": enc.name,
                       "archetype_ref": None, "width_m": 200.0, "depth_m": 100.0, "indoor": 1, "material": "concrete",
                       "light_level": 3, "ambient_db": 40.0, "layout_generated": 1, "held": 1,
                       "props": {"enclave": faction_ref, "description": enc.description}}),
          W("anchors", {"anchor_id": crown, "place_id": site, "name": "the intake crown", "kind": "feature", "x_m": 5.0,
                        "y_m": 50.0, "cover": 0, "concealment": 0, "capacity": 4}),
          W("anchors", {"anchor_id": council, "place_id": site, "name": "the council room", "kind": "feature",
                        "x_m": 150.0, "y_m": 50.0, "cover": 0, "concealment": 0, "capacity": 4})]
    gate = _opening(tx, z.hub_id, site, None, crown, enc.gate, 400)
    gate.update({"kind": "door", "is_open": 0, "is_locked": 1, "lock_quality": 4, "seal_db": 45.0})
    ws.append(W("portals", gate))
    commit(tx, EventType.PLACE_DISCOVERED, "physical.space", at, ws,
           {"zone_id": z.zone_id, "places": [site], "source": "worldgen"})
    return site


def skeleton(rng, tx, params, plan, region, tier):
    from .history import PlannedEvent
    values = flat_values(params)
    dsf = params.days_since_fall
    zones = list(region.zones)
    zname = {z.zone_id: z.name for z in zones}
    gname = {g.group_id: g.name for g in plan.groups}
    stl_of = {s.group_id: s for s in plan.settlements}
    evs = []   # (key, day, kind, subjects, cause, fmt)

    def add(day, kind, subjects, cause, a=None, b=None, zone=None, resource=None):
        key = len(evs)
        text = atlas.HISTORY_SKELETON[kind].format(day=day, a=gname.get(a, ""), b=gname.get(b, ""),
                                                   zone=zname.get(zone, ""), resource=resource or "")
        evs.append(PlannedEvent(key, day, kind, tuple(subjects), cause, text))

    add(0, "disaster", [region.start_zone_id], None, zone=region.start_zone_id)
    for res in ("food", "water", "ammo", "fuel", "meds"):
        if values[res] <= 3:
            kind = "epidemic" if res == "meds" else "infrastructure_collapse"
            n = len(evs)
            day = rng.range_int(tx, SH, f"{kind}:{n}:day", 1, max(1, dsf // 3))
            z = rng.choice(tx, SH, f"{kind}:{n}:zone", [zz.zone_id for zz in zones])
            add(day, kind, [z], 0, zone=z, resource=atlas.SHORTAGE_RESOURCE_WORDS[res])
    stl_groups = [g.group_id for g in plan.groups if g.group_id in stl_of]
    for g in plan.groups:
        n = len(evs)
        if g.group_id in stl_of:
            s = stl_of[g.group_id]
            day = rng.range_int(tx, SH, f"founding:{n}:day", max(1, dsf // 10), max(1, dsf - 1))
            add(day, "founding", [g.group_id, s.settlement_id], 0, a=g.group_id, zone=s.zone_id)
        elif g.hostile:
            if stl_groups:
                other = rng.choice(tx, SH, f"battle:{n}:against", stl_groups)
                day = rng.range_int(tx, SH, f"battle:{n}:day", max(1, dsf // 10), max(1, dsf - 1))
                add(day, "battle", [g.group_id, other], 0, a=g.group_id, b=other, zone=stl_of[other].zone_id)
            else:
                day = rng.range_int(tx, SH, f"massacre:{n}:day", max(1, dsf // 10), max(1, dsf - 1))
                add(day, "massacre", [g.group_id], 0, a=g.group_id, zone=g.home_zone_id)
        else:
            z = rng.choice(tx, SH, f"discovery:{n}:zone", [zz.zone_id for zz in zones])
            day = rng.range_int(tx, SH, f"discovery:{n}:day", max(1, dsf // 10), max(1, dsf - 1))
            add(day, "discovery", [g.group_id], 0, a=g.group_id, zone=z)
    kinds = [k for k in atlas.HISTORY_KINDS_FILL if values["atrocity_capacity"] >= 6 or k != "massacre"]
    gids = [g.group_id for g in plan.groups]
    while len(evs) < tier["history_events"]:
        n = len(evs)
        kind = rng.choice(tx, SH, f"fill:{n}:kind", kinds)
        day = rng.range_int(tx, SH, f"{kind}:{n}:day", 1, max(1, dsf - 1))
        a = rng.choice(tx, SH, f"{kind}:{n}:a", gids)
        b = None
        if kind in ("battle", "betrayal"):
            others = [x for x in gids if x != a]
            if others:
                b = rng.choice(tx, SH, f"{kind}:{n}:b", others)
            else:
                kind = "schism"
        z = rng.choice(tx, SH, f"{kind}:{n}:zone", [zz.zone_id for zz in zones])
        cause = None
        if rng.chance(tx, SH, f"{kind}:{n}:caused", 0.5):
            prior = [e.key for e in evs if e.day <= day]
            if prior:
                cause = rng.choice(tx, SH, f"{kind}:{n}:cause", prior)
        if kind in ("battle", "schism", "deposed_leader", "discovery", "betrayal"):
            subj = [a] + ([b] if b else [])
        else:
            subj = [z]
        add(day, kind, subj, cause, a=a, b=b, zone=z)
    return sorted(evs, key=lambda e: (e.day, e.key))


def _brief_history(region, batch, params):
    zones = ", ".join(z.name for z in region.zones)
    return (f"A region of {len(region.zones)} districts ({zones}); climate {params.climate_descriptor}; "
            f"{params.days_since_fall} days since the Fall. Write {len(batch)} events of its history: "
            f"what really happened, and what survivors say happened.")


async def write_history(client, tx, events, plan, region, params, at, progress=None):
    from ...contracts.calls import WorldgenContext
    from ...contracts.common import CallClass
    from ...lanes import schemas
    from ...lanes.requests import build_request
    from .history import HistoryAnswer
    hid = {e.key: tx.mint("his") for e in events}
    names = {g.group_id: g.name for g in plan.groups}
    names.update({s.settlement_id: s.name for s in plan.settlements})
    names.update({z.zone_id: z.name for z in region.zones})
    words = {}
    nb = (len(events) + 7) // 8
    for i in range(0, len(events), 8):
        batch = events[i:i + 8]
        ctx = WorldgenContext(stage="WG2", brief=_brief_history(region, batch, params), fields={
            "events": [{"id": hid[e.key], "day": e.day, "kind": e.kind, "subjects": [names.get(s, s) for s in e.subject_ids],
                        "cause": hid.get(e.cause_key) if e.cause_key is not None else None, "skeleton": e.text}
                       for e in batch],
            "region": {"zones": [z.name for z in region.zones], "climate": params.climate_descriptor,
                       "days_since_fall": params.days_since_fall}})
        got = {}
        try:
            req = build_request(client.config, CallClass.WORLDGEN_HISTORY, turn_index=0, context=ctx,
                                json_schema=schemas.to_lm_schema(HistoryAnswer), ctx=ctx)
            resp = await client.call(req, HistoryAnswer)
            if resp.parse_status == "ok" and resp.parsed is not None:
                for it in HistoryAnswer.model_validate(resp.parsed).events:
                    got[it.id] = it
        except Exception:  # noqa: BLE001  lane errors fall back to the skeleton
            got = {}
        for e in batch:
            it = got.get(hid[e.key])
            if it is not None and 20 <= len(it.truth) <= 600 and 10 <= len(it.belief) <= 400:
                words[e.key] = (it.truth, it.belief)
            else:
                rest = e.text.split(": ", 1)[1] if e.text.startswith("Day ") and ": " in e.text else e.text
                words[e.key] = (e.text, f"People say {rest}")
        if progress is not None:
            r = progress(i // 8 + 1, nb)
            if inspect.isawaitable(r):
                await r
    ws = [W("history_events", {"hist_id": hid[e.key], "day": e.day, "kind": e.kind, "subject_ids": list(e.subject_ids),
                               "cause_hist_id": hid.get(e.cause_key) if e.cause_key is not None else None,
                               "truth_text": words[e.key][0], "belief_text": words[e.key][1]}) for e in events]
    commit(tx, EventType.WORLDGEN_STAGE, "world.worldgen", at, ws, {"stage": "WG2", "events": len(events)})
    return [hid[e.key] for e in events]


def mark_held(tx, plan, at):
    from ...physical.space import change_place
    out = []
    for s in plan.settlements:
        r = tx.query_one("SELECT kind FROM places WHERE place_id=?", (s.site_id,))
        if r and r[0] == "building":
            out.append(change_place(tx, s.site_id, {"held": 1}, "history", at, None, 0))
    return out


# ------------------------------------------------------------------------------------------ WG3-5, WG7 polity
SPO = "worldgen:polity"
BANDS = ("infant", "child", "preteen", "teen", "adult", "elder")
TYPICAL_AGE = {"infant": 1, "child": 7, "preteen": 13, "teen": 17, "adult": 35, "elder": 68}


def cohort_kind(age, dsf):
    a = age - dsf / 365
    return "post_fall_born" if a < 0 else "fall_child" if a < 18 else "pre_fall_adult"


def _cohesion(values):
    return _clamp(5 + (values["social_order"] - 5) // 2, 0, 10)


def write_groups(tx, plan, params, canon, at):
    values = flat_values(params)
    out = []
    for g in plan.groups:
        doctrine = canon.get(g.content_ref).doctrine.model_dump(mode="json") if g.content_ref else {}
        out.append(commit(tx, EventType.MATERIALIZE, "society.group", at, [W("groups", {
            "group_id": g.group_id, "kind": g.kind, "name": g.name, "content_ref": g.content_ref, "descriptor": g.descriptor,
            "presence": g.presence, "doctrine": doctrine, "cohesion": _cohesion(values), "morale": 5, "leader_id": None,
            "next_due_at": None})], {"group_id": g.group_id, "source": "worldgen"}))
    base = _clamp((6 - values["faction_relations"]) * 10, 0, 100)
    bp = tx.rules.society.boiling_point
    ws = []
    for a in plan.groups:
        for b in plan.groups:
            if a.group_id == b.group_id:
                continue
            score = min(100, base + (30 if (a.hostile or b.hostile) else 0))
            if score > 0:
                ws.append(W("tension", {"a_id": a.group_id, "b_id": b.group_id, "score": score, "boiling_point": bp, "causes": []}))
    if ws:
        out.append(commit(tx, EventType.MATERIALIZE, "society.group", at, ws, {"tension": len(ws)}))
    return out


def _first_cycle(at, h0, cycle_h):
    day0 = at - at % DAY
    k = 0
    while True:
        t = day0 + int(h0 * H) + int(k * cycle_h * H)
        if t > at:
            return t
        k += 1


def write_settlements(rng, tx, plan, params, region, at):
    from .history import home_settlement
    values = flat_values(params)
    home = home_settlement(plan, region.start_zone_id)
    zkind = {z.zone_id: z.kind for z in region.zones}
    out = []
    for s in plan.settlements:
        P = s.population
        stores = {"water": rnd(3 * P * (3 + values["water"])), "food": rnd(2 * P * (3 + values["food"])),
                  "medicine": values["meds"] * 2, "fuel": values["fuel"] * 5, "ammunition": values["ammo"] * 10}
        if s.settlement_id == home.settlement_id:
            res = "water" if values["water"] <= values["food"] else "food"
            need = 3 * P if res == "water" else 2 * P
            stores[res] = rnd(need * (2 + rng.range_int(tx, SPO, f"bottleneck:{s.settlement_id}", 0, 3)))
        pr = tx.query_one("SELECT props FROM places WHERE place_id=?", (s.site_id,))
        enclave = bool(pr and json.loads(pr[0] or "{}").get("enclave"))
        out.append(commit(tx, EventType.MATERIALIZE, "society.settlement", at, [W("settlements", {
            "settlement_id": s.settlement_id, "name": s.name, "place_id": s.site_id, "group_id": s.group_id,
            "stores": dict(sorted(stores.items())), "morale": 5, "cohesion": _cohesion(values),
            "defences": 10 if enclave else _clamp(values["social_order"] // 2 + 1, 0, 10),
            "sanitation": 10 if enclave else _clamp(values["tech_preservation"] // 2, 0, 10),
            "power": 1 if (enclave or values["tech_baseline"] >= 6) else 0,
            "ration_level": 3, "shortages": [], "vacancies": [], "next_due_at": None, "lockdown": 0})],
            {"settlement_id": s.settlement_id, "source": "worldgen"}, place_id=s.site_id))
        sites = ["water_pump", "kitchen", "watch"]
        if values["meds"] >= 4:
            sites.append("clinic")
        if zkind[s.zone_id] in ("rural", "riverside"):
            sites.append("garden")
        for st in sites:
            cyc, roles, _res, h0 = atlas.WORKPLACE_PLANS[st]
            if st == "water_pump":
                outs = {"water": math.ceil(P * 3 * (0.7 + 0.06 * values["water"]) * cyc / 24)}
            elif st == "kitchen":
                outs = {"food": math.ceil(P * 2 * (0.7 + 0.06 * values["food"]) * cyc / 24)}
            elif st == "garden":
                outs = {"food": math.ceil(P * 0.3)}
            else:
                outs = {}
            wid = tx.mint("wkp")
            out.append(commit(tx, EventType.MATERIALIZE, "society.work", at, [W("workplaces", {
                "workplace_id": wid, "settlement_id": s.settlement_id, "place_id": s.site_id, "site_type": st, "inputs": {},
                "outputs": outs, "cycle_h": cyc, "required_roles": [],
                "machinery_condition": min(100, 40 + 5 * values["tech_preservation"]), "efficiency": 1.0,
                "stall_reasons": [], "next_due_at": _first_cycle(at, h0, cyc)})], {"workplace_id": wid, "source": "worldgen"},
                place_id=s.site_id))
    return out


def _split(rng, tx, sid, band, count):
    extra = count % 2 if rng.chance(tx, SPO, f"sex:{sid}:{band}", 0.5) else 0
    f = count // 2 + extra
    return f, count - f


def write_cohorts(rng, tx, plan, params, at):
    values = flat_values(params)
    dsf = params.days_since_fall
    pyr = tx.rules.society.pyramid
    zone_of = {s.settlement_id: s.zone_id for s in plan.settlements}
    out = []
    for s in plan.settlements:
        P = s.population
        shares = {}
        for grp, base in (("young", 0.20), ("youth", 0.14), ("elders", 0.11)):
            shares[grp] = base + rng.range_int(tx, SPO, f"share:{s.settlement_id}:{grp}", -3, 3) / 100
        cnt = {}
        for grp in ("young", "youth", "elders"):
            lo, hi = pyr[grp]
            cnt[grp] = _clamp(rnd(P * shares[grp]), math.ceil(P * lo), math.floor(P * hi))
        adults = P - cnt["young"] - cnt["youth"] - cnt["elders"]
        bands = {"infant": cnt["young"] * 2 // 5, "child": cnt["young"] - cnt["young"] * 2 // 5,
                 "preteen": cnt["youth"] // 2, "teen": cnt["youth"] - cnt["youth"] // 2, "adult": adults,
                 "elder": cnt["elders"]}
        ws = []
        for band in BANDS:
            f, m = _split(rng, tx, s.settlement_id, band, bands[band])
            for sex, c in (("female", f), ("male", m)):
                if c > 0:
                    ws.append(W("cohorts", {"cohort_id": tx.mint("coh"), "settlement_id": s.settlement_id,
                                            "zone_id": zone_of[s.settlement_id], "age_band": band, "sex": sex,
                                            "cohort_kind": cohort_kind(TYPICAL_AGE[band], dsf), "count": c,
                                            "archetype": None}))
        out.append(commit(tx, EventType.MATERIALIZE, "society.population", at, ws,
                          {"settlement_id": s.settlement_id, "cohorts": len(ws)}))
    for g in plan.groups:
        if not g.hostile:
            continue
        n = rng.range_int(tx, SPO, f"band:{g.group_id}", 6, 12)
        f, m = _split(rng, tx, g.group_id, "adult", n)
        ws = [W("cohorts", {"cohort_id": tx.mint("coh"), "settlement_id": None, "zone_id": g.home_zone_id, "age_band": "adult",
                            "sex": sex, "cohort_kind": cohort_kind(35, dsf), "count": c, "archetype": g.group_id})
              for sex, c in (("female", f), ("male", m)) if c > 0]
        out.append(commit(tx, EventType.MATERIALIZE, "society.population", at, ws, {"settlement_id": None, "group_id": g.group_id,
                                                                                    "cohorts": len(ws)}))
    return out


def write_laws(tx, plan, params, canon, at):
    values = flat_values(params)
    by_group = {g.group_id: g for g in plan.groups}
    out = []
    for s in plan.settlements:
        g = by_group[s.group_id]
        laws = {"core:law/ration_law", "core:law/theft_law"}
        if g.kind == "faction" and g.content_ref:
            for ref in canon.get(g.content_ref).laws:
                try:
                    canon.get(ref)
                    laws.add(ref)
                except Exception:  # noqa: BLE001
                    pass
        else:
            if values["hostile_human"] >= 6:
                laws.add("core:law/nightfall_curfew")
            if values["social_order"] >= 6:
                laws.add("core:law/firearms_discipline")
            if values["zombie_common"] >= 6:
                laws |= {"core:law/intake_screening", "core:law/contamination_quarantine"}
        ws = [W("laws_active", {"settlement_id": s.settlement_id, "law_ref": r, "since": at}) for r in sorted(laws)]
        out.append(commit(tx, EventType.MATERIALIZE, "society.settlement", at, ws, {"settlement_id": s.settlement_id,
                                                                                   "laws": len(ws)}, place_id=s.site_id))
    return out


# ------------------------------------------------------------------------------------------ WG6 people
SPE = "worldgen:people"
BAND_AGE = {"infant": (0, 2), "child": (3, 11), "preteen": (12, 14), "teen": (15, 19), "adult": (20, 59), "elder": (60, 80)}
POSTS = (("pump_operator", "water_pump", 6, 18), ("pump_operator", "water_pump", 18, 6), ("cook", "kitchen", 6, 20),
         ("quartermaster", None, None, None), ("watcher", "watch", 6, 18), ("watcher", "watch", 18, 6),
         ("medic", "clinic", 8, 20), ("gardener", "garden", 6, 18))
LOCKED = ("id", "generation", "identity", "days_since_fall_range", "tags")


def _brief_person(seed, role):
    return (f"{seed.name}, {seed.age}, {seed.sex}, lives at {seed.settlement_name} with {seed.group_name}; "
            f"works as {role}. Write their dossier: how they look, move, speak and decide.")


async def _actor_answer(client, seed, skel, role, history):
    from ...contracts.calls import WorldgenContext
    from ...contracts.common import CallClass
    from ...contracts.dossier import ActorDossier
    from ...lanes import schemas
    from ...lanes.requests import build_request
    ctx = WorldgenContext(stage="WG6", brief=_brief_person(seed, role), fields={
        "skeleton": skel, "settlement": seed.settlement_name, "group": seed.group_name, "role": role, "history": history})
    try:
        req = build_request(client.config, CallClass.WORLDGEN_ACTOR, turn_index=0, context=ctx,
                            json_schema=schemas.to_lm_schema(ActorDossier), ctx=ctx)
        resp = await client.call(req, None)
        if resp.parse_status != "ok":
            return skel
        from ...lanes.parse import extract_json
        ans = extract_json(resp.text)
        if not isinstance(ans, dict):
            return skel
        merged = dict(ans)
        for k in LOCKED:
            merged[k] = skel.get(k)
        cap = dict(merged.get("capability") or {})
        cap["special"] = skel["capability"]["special"]
        cap["skills"] = skel["capability"]["skills"]
        merged["capability"] = cap
        # LOOK-10 (F1a-2): how they look and what they wear stays the skeleton's
        merged["appearance"] = {**(merged.get("appearance") or {}), "looks": skel["appearance"].get("looks")}
        merged["schema"] = "as.actor.v1"
        ActorDossier.model_validate(merged)
        return merged
    except Exception:  # noqa: BLE001
        return skel


def _taken_names(tx):
    return {r[0] for r in tx.query("SELECT a.display_name FROM actors a JOIN bodies b ON b.body_id = a.actor_id WHERE b.alive = 1")}


async def write_people(client, rng, tx, plan, region, params, canon, detail, at, progress=None):
    import asyncio as _aio
    from ...contracts.common import age_band_for
    from ...mind.perception import describe_dossier
    from ...physical import bodies
    from .. import _impl_p10 as P
    from .history import home_settlement
    from .people import People, PersonSeed, skeleton_dossier
    T = tables.DETAIL_TIERS[detail]
    dsf = params.days_since_fall
    home = home_settlement(plan, region.start_zone_id)
    stl = {s.settlement_id: s for s in plan.settlements}
    stl_of_group = {s.group_id: s for s in plan.settlements}
    groups = {g.group_id: g for g in plan.groups}
    planned_f = {g.content_ref: g for g in plan.groups if g.content_ref}
    res = People(home_settlement_id=home.settlement_id)
    # local cohort counts (what is left to name)
    counts = {}
    for r in tx.query("SELECT settlement_id, age_band, sex, count FROM cohorts WHERE settlement_id IS NOT NULL"):
        counts[(r[0], r[1], r[2])] = counts.get((r[0], r[1], r[2]), 0) + r[3]

    def take(sid, band, sex):
        if counts.get((sid, band, sex), 0) > 0:
            counts[(sid, band, sex)] -= 1
            return True
        return False
    # WG-26 pack actors
    pack = []
    cyc = 0
    for ref in canon.refs("actor"):
        rec = canon.get(ref)
        rr = rec.days_since_fall_range
        if rr and not (rr[0] <= dsf <= rr[1]):
            res.skipped.append((ref, f"needs a world {rr[0] // 365}-{rr[1] // 365} years after the Fall"))
            continue
        fms = [m.faction for m in rec.social.memberships if ":faction/" in m.faction]
        s = None
        if fms:
            planned = [f for f in fms if f in planned_f]
            if not planned:
                res.skipped.append((ref, "their faction is not in this region"))
                continue
            s = stl_of_group.get(planned_f[planned[0]].group_id)
        if s is None:
            s = plan.settlements[cyc % len(plan.settlements)]
            cyc += 1
        pack.append((ref, rec, s))
        take(s.settlement_id, age_band_for(rec.identity.age).value, rec.identity.sex)
    # WG-27 slots
    home_sites = {r[0] for r in tx.query("SELECT site_type FROM workplaces WHERE settlement_id=?", (home.settlement_id,))}
    slots = [("post", home, role, site, sh) for role, site, *sh in POSTS if site is None or site in home_sites]
    pack_leaders = {}
    order = [home] + [s for s in plan.settlements if s.settlement_id != home.settlement_id]
    for s in order:
        g = groups[s.group_id]
        leaders = canon.get(g.content_ref).leaders if g.content_ref else []
        lref = leaders[0].actor if leaders else None
        if lref and any(p[0] == lref and p[2].settlement_id == s.settlement_id for p in pack):
            pack_leaders[g.group_id] = lref
        else:
            slots.append(("leader", s, "leader", None, None))
        for ld in leaders[1:]:          # P10: the seats (the Top-Hat Council, the Front Man)
            if ld.seat and not (ld.actor and any(p[0] == ld.actor and p[2].settlement_id == s.settlement_id for p in pack)):
                slots.append(("seat", s, ld.seat, None, (ld.title, ld.age)))
    generated = max(T["detailed_actors"] - len(pack), len(slots))
    taken = _taken_names(tx)
    nrec = _first_names_record(canon)
    seeds = []   # (slot, seed, band)
    empty = set()
    ri = 0
    n = 0
    fixed = list(slots)
    while len(seeds) < generated:
        if fixed:
            kind, s, role, site, sh = fixed.pop(0)
        else:
            live = [x for x in order if x.settlement_id not in empty]
            if not live:
                break
            s = live[ri % len(live)]
            ri += 1
            kind, role, site, sh = "resident", None, None, None
        sid = s.settlement_id
        bands = {b: counts.get((sid, b, "female"), 0) + counts.get((sid, b, "male"), 0) for b in BANDS}
        if sum(bands.values()) == 0:
            empty.add(sid)
            n += 1
            continue
        if kind == "resident":
            band = rng.weighted(tx, SPE, f"band:{n}", [(b, float(c)) for b, c in bands.items() if c > 0])
        else:
            band = "adult" if bands["adult"] > 0 else max(BANDS, key=lambda b: (bands[b], -BANDS.index(b)))
        sexes = [(x, float(counts.get((sid, band, x), 0))) for x in ("female", "male") if counts.get((sid, band, x), 0) > 0]
        sex = rng.weighted(tx, SPE, f"sex:{n}", sexes)
        take(sid, band, sex)
        ns = f"names:{sid}"
        given = list(nrec.given_female if sex == "female" else nrec.given_male)
        for _t in range(9):
            name = f"{rng.choice(tx, ns, f'given:{n}', given)} {rng.choice(tx, ns, f'family:{n}', list(nrec.family))}"
            if name not in taken:
                break
        taken.add(name)
        lo, hi = BAND_AGE[band]
        if kind == "seat" and sh[1]:
            age = rng.range_int(tx, SPE, f"seat_age:{n}", *sh[1])
        else:
            age = rng.range_int(tx, SPE, f"age:{n}", lo, hi)
        if kind == "post":
            occ, dom, rank = atlas.ROLE_PEOPLE[role]
            skills = {dom: rank}
        elif kind == "leader":
            occ, skills = "leader", {"leadership": 2}
        elif kind == "seat":
            occ, skills = sh[0], {"leadership": 2}
        elif band in ("adult", "elder", "teen") and age >= 16:
            occ, dom, rank = rng.choice(tx, SPE, f"occupation:{n}", list(atlas.FREE_OCCUPATIONS))
            skills = {dom: rank}
        else:
            occ, skills = "child", {}
        special = {L: 3 + rng.range_int(tx, SPE, f"special:{n}:{L}", 0, 4) for L in "SPECIAL"}
        variant = rng.range_int(tx, SPE, f"variant:{n}", 0, 999)
        seed = PersonSeed(name=name, age=age, sex=sex, cohort=cohort_kind(age, dsf), occupation=occ, skills=skills,
                          special=special, variant=variant, settlement_name=s.name, group_name=groups[s.group_id].name,
                          climate_heat=params.a.climate_heat)
        seeds.append(((kind, s, role, site, sh), seed, band))
        n += 1
    # WORLDGEN_ACTOR for the first llm_dossiers
    hist = [(json.loads(r[1]), r[2]) for r in tx.query("SELECT hist_id, subject_ids, belief_text FROM history_events ORDER BY day, hist_id")]
    skels = [skeleton_dossier(sd) for _slot, sd, _b in seeds]
    k = min(T["llm_dossiers"], len(seeds))

    def hist_for(gid):
        return [b for subj, b in hist if gid in subj]
    finished = {"n": 0}

    async def one(i):
        a = await _actor_answer(client, seeds[i][1], skels[i], seeds[i][1].occupation, hist_for(seeds[i][0][1].group_id))
        finished["n"] += 1
        if progress is not None:
            r = progress(finished["n"], k)
            if inspect.isawaitable(r):
                await r
        return a
    answers = await _aio.gather(*[one(i) for i in range(k)])
    dossiers = list(answers) + skels[k:]
    # WG-28 writing: pack actors
    named = []   # (actor_id, settlement, dossier dict, slot kind, role, sh, band, workplace site)
    for ref, rec, s in pack:
        band = age_band_for(rec.identity.age).value
        ev = P.take_from_cohort(tx, s.settlement_id, None, band, rec.identity.sex, at, 0, None)
        kind = "lurker" if "lurker" in rec.tags else "human"
        bid = bodies.create(tx, kind=kind, sex=rec.identity.sex, age_years=rec.identity.age,
                            height_cm=rec.appearance.height_cm, mass_kg=rec.appearance.mass_kg,
                            special=rec.capability.special.model_dump(mode="json"), at=at, turn_index=0, origin="worldgen",
                            cause_event_id=ev.event_id if ev else None, content_ref=ref)
        P._place_at_first_anchor(tx, bid, s.site_id, at, None, 0)
        d = rec.model_dump(mode="json", by_alias=True)
        P.actor_create(tx, bid, d, "pack", at, 0, content_ref=ref, event_origin="worldgen")
        res.pack_placed.append(bid)
        named.append((bid, s, d, "pack", None, None, band, None, ref))
    for (slot, seed, band), d in zip(seeds, dossiers):
        kind, s, role, site, sh = slot
        bid = P.materialise(tx, rng, settlement_id=s.settlement_id, zone_id=s.zone_id, band=band, sex=seed.sex, dossier=d,
                            place_id=s.site_id, at=at, turn_index=0, cause_event_id=None, event_origin="worldgen")
        res.generated.append(bid)
        if kind in ("post", "leader", "seat"):
            res.roles[bid] = role
        named.append((bid, s, d, kind, role, sh, band, site, None))
    # per settlement: members, leaders, households, work
    for s in plan.settlements:
        mine = [x for x in named if x[1].settlement_id == s.settlement_id]
        g = groups[s.group_id]
        leader = None
        if g.group_id in pack_leaders:
            leader = next(x[0] for x in mine if x[8] == pack_leaders[g.group_id])
        else:
            leader = next((x[0] for x in mine if x[3] == "leader"), None)
        if leader:
            res.leaders[g.group_id] = leader
        ws = []
        for x in mine:
            st = 0
            if x[3] == "pack" and g.content_ref:
                for m in x[2].get("social", {}).get("memberships", []):
                    if m.get("faction") == g.content_ref:
                        st = m.get("standing", 0)
                        break
            role = "leader" if x[0] == leader else (x[4] if x[3] == "seat" else "member")
            ws.append(W("group_members", {"group_id": g.group_id, "actor_id": x[0], "role": role,
                                          "standing": st, "since": at, "status": "member"}))
        if leader:
            ws.append(W("groups", {"leader_id": leader}, WriteOp.UPDATE, {"group_id": g.group_id}))
        if ws:
            commit(tx, EventType.MATERIALIZE, "society.group", at, ws, {"group_id": g.group_id, "members": len(mine)})
        # households
        hh = []
        prev = None   # the household of the previous 'adult'-band person while it is still one person
        for x in mine:
            if x[6] in ("infant", "child", "preteen"):
                continue
            sex = x[2]["identity"]["sex"]
            if x[6] == "adult" and prev is not None and prev["partner"] is None and prev["sex"] != sex and                     rng.chance(tx, SPE, f"pair:{prev['head']}:{x[0]}", 0.5):
                prev["partner"] = x[0]
                prev = None
                continue
            h = {"head": x[0], "sex": sex, "partner": None, "kids": [], "adult": x[6] == "adult"}
            hh.append(h)
            if x[6] == "adult":
                prev = h
        for x in mine:
            if x[6] not in ("infant", "child", "preteen") or not hh:
                continue
            tgt = next((h for h in hh if h["adult"] and not h["kids"]), hh[0])
            tgt["kids"].append(x[0])
        for h in hh:
            hid = tx.mint("hh")
            ws = [W("households", {"household_id": hid, "dwelling_place": s.site_id, "shared_stores": {}, "grief_state": 0,
                                   "settlement_id": s.settlement_id}),
                  W("household_members", {"household_id": hid, "actor_id": h["head"], "role": "head",
                                          "guardian_of": list(h["kids"]), "protection_priority": 0})]
            if h["partner"]:
                ws.append(W("household_members", {"household_id": hid, "actor_id": h["partner"], "role": "partner", "guardian_of": [],
                                                  "protection_priority": 0}))
            for c in h["kids"]:
                ws.append(W("household_members", {"household_id": hid, "actor_id": c, "role": "child", "guardian_of": [],
                                                  "protection_priority": 0}))
            commit(tx, EventType.MATERIALIZE, "society.household", at, ws, {"household_id": hid, "source": "worldgen"})
        # work
        wps = {r[1]: r[0] for r in tx.query("SELECT workplace_id, site_type FROM workplaces WHERE settlement_id=? ORDER BY workplace_id",
                                            (s.settlement_id,))}
        per_wp = {}
        for x in mine:
            if x[3] == "post" and x[7] in wps:
                per_wp.setdefault(wps[x[7]], []).append(x)
        for wid in sorted(per_wp):
            ws = [W("work_assignments", {"workplace_id": wid, "actor_id": x[0], "role": x[4], "shift_start_hh": x[5][0],
                                         "shift_end_hh": x[5][1], "covering_for": None}) for x in per_wp[wid]]
            ws.append(W("workplaces", {"required_roles": list(dict.fromkeys(x[4] for x in per_wp[wid]))}, WriteOp.UPDATE, {"workplace_id": wid}))
            commit(tx, EventType.MATERIALIZE, "society.work", at, ws, {"workplace_id": wid, "source": "worldgen"})
    # WG-29 ties and knowledge
    road_touch = {}
    for r in region.routes:
        for z in (r.a_zone, r.b_zone):
            road_touch.setdefault(z, []).append(r.road_id)
    hh_of = {}
    for r in tx.query("SELECT household_id, actor_id FROM household_members"):
        hh_of[r[1]] = r[0]
    for s in plan.settlements:
        mine = [x for x in named if x[1].settlement_id == s.settlement_id]
        zplaces = [r[0] for r in tx.query("SELECT place_id FROM places WHERE zone_id=? AND parent_id IS NULL ORDER BY place_id",
                                          (s.zone_id,))]
        zplaces += [p for p in road_touch.get(s.zone_id, []) if p not in zplaces]
        subj_ok = {s.group_id, s.settlement_id, s.zone_id}
        beliefs = [(r[0], r[1]) for r in tx.query("SELECT hist_id, belief_text, subject_ids FROM history_events ORDER BY day, hist_id")
                   if subj_ok & set(json.loads(r[2]))]
        for x in mine:
            ws = [W("known_places", {"holder_id": x[0], "place_id": p, "first_seen": at, "last_seen": at,
                                     "visited": 1 if p == s.site_id else 0}, WriteOp.UPSERT, {"holder_id": x[0], "place_id": p})
                  for p in zplaces]
            for y in mine:
                if y[0] == x[0]:
                    continue
                ws.append(W("acquaintance", {"holder_id": x[0], "subject_id": y[0], "known_name": y[2]["identity"]["name"],
                                             "description": describe_dossier(y[2]), "first_met": at, "last_seen": at,
                                             "last_seen_place": s.site_id}))
            props = []
            for hid_, text in beliefs:
                pid = tx.mint("prp")
                props.append(pid)
                ws.append(W("propositions", {"prop_id": pid, "subject_type": "event", "subject_id": hid_, "predicate": "history",
                                             "text": text, "matches_claim": None, "created_event": "worldgen", "object_value": None}))
            ev = commit(tx, EventType.PERCEIVE, "mind.perception", at, ws, {"holder_id": x[0], "seed": True}, actor_id=x[0])
            if props:
                commit(tx, EventType.PERCEIVE, "mind.perception", at, [
                    W("claim_holdings", {"holder_id": x[0], "claim_id": pid, "believed": 1, "confidence": 2, "provenance": "common",
                                         "fidelity": "exact", "acquired_at": at, "acquired_via": ev.event_id}) for pid in props],
                    {"holder_id": x[0], "seed": True, "beliefs": len(props)}, actor_id=x[0])
        ids = sorted(x[0] for x in mine)
        _gen = set(res.generated)
        _feud = False
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                if hh_of.get(a) and hh_of.get(a) == hh_of.get(b):
                    rel = ("family", {"trust": 2, "affection": 2})
                else:
                    kind = rng.weighted(tx, SPE, f"rel:{a}:{b}", [("positive", 0.2), ("stranger", 0.6), ("rival", 0.2)])
                    rel = {"positive": ("friend", {"trust": 1, "affection": 1}), "rival": ("rival", {"trust": -1, "resentment": 1}),
                           "stranger": None}[kind]
                    if kind == "rival" and not _feud and a in _gen and b in _gen:
                        rel = ("rival", {"trust": -2, "resentment": 2})
                        _feud = True
                if rel is None:
                    continue
                for f, t in ((a, b), (b, a)):
                    axes = {k2: 0 for k2 in ("trust", "fear", "respect", "affection", "resentment", "obligation")}
                    axes.update(rel[1])
                    commit(tx, EventType.RELATION_CHANGE, "mind.mind", at, [W("relationships", {"from_id": f, "to_id": t, "kind": rel[0],
                                                                                              **axes, "causes": {}, "updated_at": at})],
                           {"from_id": f, "to_id": t, "kind": rel[0], "axes": axes, "seed": True})
    return res


# ------------------------------------------------------------------------------------------ WG8 opening
SO = "worldgen:opening"
TIE_ORDER = ("hostile_human", "runner_pressure", "zombie_common", "horde_pressure", "lurker_pressure", "ambient_danger")
AB_NAMES = A_NAMES + B_NAMES


def _hops(tx, start):
    seen, near, far = {start}, [], []
    for r in tx.query("SELECT place_a, place_b FROM portals WHERE kind != 'wall' AND (place_a=? OR place_b=?)", (start, start)):
        o = r[1] if r[0] == start else r[0]
        if o not in seen:
            seen.add(o)
            near.append(o)
    for p in sorted(near):
        for r in tx.query("SELECT place_a, place_b FROM portals WHERE kind != 'wall' AND (place_a=? OR place_b=?)", (p, p)):
            o = r[1] if r[0] == p else r[0]
            if o not in seen:
                seen.add(o)
                far.append(o)
    return sorted(near), sorted(far)


def _qc4(ans, ids):
    if not ans.get("cites_entity_ids"):
        return "cites_entity_ids is empty"
    bad = [i for i in ans["cites_entity_ids"] if i not in ids]
    if bad:
        return f"cites_entity_ids names things that are not listed: {bad}"
    if not ans.get("cites_params"):
        return "cites_params is empty"
    badp = [p for p in ans["cites_params"] if p not in AB_NAMES]
    if badp:
        return f"cites_params must be A or B block names: {badp}"
    return None


async def _opening_call(client, ctx):
    from ...contracts.common import CallClass
    from ...contracts.worldgen import OpeningPressure
    from ...lanes import schemas
    from ...lanes.parse import extract_json
    from ...lanes.requests import build_request
    from .opening import _trim
    try:
        req = build_request(client.config, CallClass.WORLDGEN_OPENING, turn_index=0, context=ctx,
                            json_schema=schemas.to_lm_schema(OpeningPressure), ctx=ctx)
        resp = await client.call(req, None)
    except Exception as e:  # noqa: BLE001
        return None, f"the call failed: {e}"
    if resp.parse_status != "ok":
        return None, f"the call failed: {resp.parse_status}"
    ans = extract_json(resp.text)
    if not isinstance(ans, dict):
        return None, "the answer was not a JSON object"
    for k, n in tables.OPENING_BUDGETS.items():
        if isinstance(ans.get(k), str):
            ans[k] = _trim(ans[k], n)
    try:
        op = OpeningPressure.model_validate(ans)
    except Exception as e:  # noqa: BLE001
        return None, f"the answer does not fit: {str(e)[:200]}"
    return op, None


async def place_pc(client, rng, tx, pc_ref, pc, params, placement, plan, region, people, canon, run_id, seed, qc, at):
    from ...contracts.calls import WorldgenContext
    from ...contracts.worldgen import WorldgenCommit
    from ...kernel.jsoncanon import canonical_json
    from ...mind.perception import describe_dossier
    from ...physical import bodies, objects, space
    from .. import _impl_p10 as P
    from .opening import Opening, fallback_opening
    from .people import PersonSeed, skeleton_dossier
    values = flat_values(params)
    dsf = params.days_since_fall
    zones = {z.zone_id: z for z in region.zones}
    sz = zones[region.start_zone_id]
    stl_sites = {s.site_id for s in plan.settlements}
    ent = next((g for g in plan.groups if g.is_pc_entity), None)
    ent_stl = next((s for s in plan.settlements if ent and s.group_id == ent.group_id), None)
    kinds = {r[0]: dict(r) for r in tx.query("SELECT * FROM places")}
    # 1 start place
    if ent_stl is not None and placement.start_relationship == "ally":
        start = ent_stl.site_id
    else:
        bl = sorted(p for p in sz.site_ids if kinds[p]["kind"] == "building" and p not in stl_sites)
        ol = sorted(p for p in sz.site_ids if kinds[p]["kind"] == "outdoor")
        start = bl[0] if bl else ol[0] if ol else sz.hub_id
    # 2 the PC
    pcd = pc.model_dump(mode="json", by_alias=True)
    body = bodies.create(tx, kind="human", sex=pc.identity.sex, age_years=pc.identity.age, height_cm=pc.appearance.height_cm,
                         mass_kg=pc.appearance.mass_kg, special=pc.capability.special.model_dump(mode="json"), at=at,
                         turn_index=0, origin="worldgen", content_ref=pc_ref, looks=pc.appearance.looks)
    if kinds[start]["kind"] == "building" and not kinds[start]["layout_generated"]:
        space.discover_layout(tx, rng, start, at, 0)
    P._place_at_first_anchor(tx, body, start, at, None, 0)
    space.change_place(tx, start, {"props": {"populated": True}}, "populated", at, None, 0)
    P.actor_create(tx, body, pcd, "pack", at, 0, content_ref=pc_ref, mind_kind="human", event_origin="worldgen")
    labels = {}
    grants = list(pc.starting_inventory)
    for g in [g for g in grants if not g.container] + [g for g in grants if g.container]:
        to = objects.Holder("container", labels[g.container]) if g.container else objects.Holder("body", body, g.slot)
        ev = objects.create(tx, g.item, g.qty, to, "worldgen", dict(g.props), at, None, 0, event_origin="worldgen")
        if g.label:
            labels[g.label] = ev.payload["item_id"]
    if pc.appearance.looks is not None:
        objects.dress(tx, body, pc.appearance.looks.outfit, at, None, 0, "worldgen")
    road_touch = [r.road_id for r in region.routes if region.start_zone_id in (r.a_zone, r.b_zone)]
    zpl = [r[0] for r in tx.query("SELECT place_id FROM places WHERE zone_id=? AND parent_id IS NULL ORDER BY place_id",
                                  (sz.zone_id,))]
    zpl += [p for p in road_touch if p not in zpl]
    commit(tx, EventType.PERCEIVE, "mind.perception", at, [
        W("known_places", {"holder_id": body, "place_id": p, "first_seen": at, "last_seen": at, "visited": 1 if p == start else 0},
          WriteOp.UPSERT, {"holder_id": body, "place_id": p}) for p in zpl], {"holder_id": body, "seed": True}, actor_id=body)
    commit(tx, EventType.PC_CONTROL_CHANGE, "kernel.meta", at, [W("meta", {"value": body}, WriteOp.UPDATE, {"key": "pc_actor_id"})],
           {"pc_actor_id": body}, origin="worldgen")
    gws = []
    if pc.faction_start_type == "always_in_faction" and ent is not None:
        gws.append(W("group_members", {"group_id": ent.group_id, "actor_id": body, "role": "member", "standing": 0, "since": at,
                                       "status": "member"}))
    if ent is not None and placement.start_trust is not None:
        gws.append(W("group_standing", {"group_id": ent.group_id, "actor_id": body,
                                        "standing": _clamp(placement.start_trust - 5, -5, 5), "reasons": []}))
    by_ref = {g.content_ref: g for g in plan.groups if g.content_ref}
    for m in pc.faction_standing:
        g = by_ref.get(m.faction)
        if g is not None and not (ent is not None and g.group_id == ent.group_id):
            gws.append(W("group_standing", {"group_id": g.group_id, "actor_id": body, "standing": m.standing, "reasons": []}))
    if gws:
        commit(tx, EventType.MATERIALIZE, "society.group", at, gws, {"actor_id": body, "source": "worldgen"})
    # 3 contacts
    contacts = []
    if ent_stl is not None:
        q = next((a for a, r in sorted(people.roles.items()) if r == "quartermaster"), None)
        if q:
            contacts.append(q)
        ld = people.leaders.get(ent.group_id)
        if ld and ld not in contacts:
            contacts.append(ld)

    def doss(aid):
        return json.loads(tx.query_one("SELECT d.baseline_json FROM dossiers d WHERE d.actor_id=?", (aid,))[0])

    def name_of(aid):
        return tx.query_one("SELECT display_name FROM actors WHERE actor_id=?", (aid,))[0]
    st = placement.start_trust if placement.start_trust is not None else 5
    trust = _clamp(rnd((st - 5) / 2), -2, 2)
    if contacts:
        commit(tx, EventType.PERCEIVE, "mind.perception", at, [
            W("acquaintance", {"holder_id": body, "subject_id": c, "known_name": name_of(c), "description": describe_dossier(doss(c)),
                               "first_met": at, "last_seen": at, "last_seen_place": ent_stl.site_id}) for c in contacts],
            {"holder_id": body, "seed": True}, actor_id=body)
        for c in contacts:
            commit(tx, EventType.PERCEIVE, "mind.perception", at, [
                W("acquaintance", {"holder_id": c, "subject_id": body, "known_name": pc.identity.name,
                                   "description": describe_dossier(pcd), "first_met": at, "last_seen": at, "last_seen_place": start},
                  WriteOp.UPSERT, {"holder_id": c, "subject_id": body})], {"holder_id": c, "seed": True}, actor_id=c)
            for f, t in ((body, c), (c, body)):
                axes = {"trust": trust, "fear": 0, "respect": 0, "affection": 0, "resentment": 0, "obligation": 0}
                commit(tx, EventType.RELATION_CHANGE, "mind.mind", at, [W("relationships", {"from_id": f, "to_id": t,
                                                                                          "kind": "acquaintance", **axes,
                                                                                          "causes": {}, "updated_at": at})],
                       {"from_id": f, "to_id": t, "kind": "acquaintance", "axes": axes, "seed": True})
    # 4 the threat
    m = max(values[k] for k in C_NAMES)
    top = [k for k in C_NAMES if values[k] == m]
    if "hostile_human" in top and placement.start_relationship == "enemy":
        param = "hostile_human"
    else:
        param = next(k for k in TIE_ORDER if k in top)
    tkind = atlas.THREAT_KINDS[param]
    hostiles = [g for g in plan.groups if g.hostile]
    if tkind == "hostile_humans" and not hostiles:
        tkind = "shamblers"
    near, far = _hops(tx, start)
    places = {r[0]: dict(r) for r in tx.query("SELECT * FROM places")}

    def ok(p):
        return p not in stl_sites and places[p]["parent_id"] not in stl_sites and places[p]["parent_id"] != start and p != start
    tplace = next((p for p in far if ok(p)), None) or next((p for p in near if ok(p)), None) or near[0]
    threat_ids = []
    if tkind == "hostile_humans":
        g = hostiles[0]
        n = 2 + (values["hostile_human"] >= 7) + (values["hostile_human"] >= 9)
        nrec = _first_names_record(canon)
        taken = _taken_names(tx)
        for i in range(n):
            cs = [(r[0], float(r[1])) for r in tx.query("SELECT sex, count FROM cohorts WHERE settlement_id IS NULL AND zone_id=? "
                                                       "AND archetype=? AND age_band='adult' AND count>0 ORDER BY sex",
                                                       (g.home_zone_id, g.group_id))]
            if not cs:
                break
            sex = rng.weighted(tx, SO, f"raider_sex:{i}", cs)
            given = list(nrec.given_female if sex == "female" else nrec.given_male)
            for _t in range(9):
                nm = f"{rng.choice(tx, f'names:{g.group_id}', f'given:{i}', given)} " \
                     f"{rng.choice(tx, f'names:{g.group_id}', f'family:{i}', list(nrec.family))}"
                if nm not in taken:
                    break
            taken.add(nm)
            age = rng.range_int(tx, SO, f"raider_age:{i}", 20, 59)
            sd = PersonSeed(name=nm, age=age, sex=sex, cohort=cohort_kind(age, dsf), occupation="raider",
                            skills={"brawling": 1, "firearms": 1},
                            special={L: 3 + rng.range_int(tx, SO, f"raider_special:{i}:{L}", 0, 4) for L in "SPECIAL"},
                            variant=rng.range_int(tx, SO, f"raider_variant:{i}", 0, 999),
                            settlement_name=zones[g.home_zone_id].name, group_name=g.name, climate_heat=params.a.climate_heat)
            aid = P.materialise(tx, rng, settlement_id=None, zone_id=g.home_zone_id, band="adult", sex=sex,
                                dossier=skeleton_dossier(sd), place_id=tplace, at=at, turn_index=0, cause_event_id=None,
                                archetype=g.group_id, event_origin="worldgen")
            threat_ids.append(aid)
        if threat_ids:
            commit(tx, EventType.MATERIALIZE, "society.group", at, [
                W("group_members", {"group_id": g.group_id, "actor_id": a, "role": "member", "standing": 0, "since": at,
                                    "status": "member"}) for a in threat_ids], {"group_id": g.group_id, "members": len(threat_ids)})
            for a in threat_ids:
                goal = "find out what the stranger is carrying"
                steps = ["follow the stranger", "take what they carry"]
                commit(tx, EventType.PLAN_CHANGE, "mind.actor", at, [
                    W("plans", {"actor_id": a, "goal_text": goal, "steps": steps, "standing_orders": [], "updated_at": at},
                      WriteOp.UPSERT, {"actor_id": a}),
                    W("actors", {"goal_text": goal}, WriteOp.UPDATE, {"actor_id": a})],
                    {"actor_id": a, "goal_text": goal, "steps": steps}, actor_id=a)
        else:
            tkind = "shamblers"
    if tkind != "hostile_humans":
        if tkind == "shamblers":
            spec = [(P.SHAMBLER, min(6, 3 + values["zombie_common"] // 3))]
        elif tkind == "runners":
            spec = [(P.RUNNER, 1 + values["runner_pressure"] // 5)]
        else:
            spec = [(P.SHAMBLER, 2)]
        for ty, n in spec:
            for _i in range(n):
                b = P.spawn(tx, rng, tplace, ty, at, 0, None, origin="worldgen")
                P.attract(tx, b, start, at, None, 0, reason="noise")
                threat_ids.append(b)
    if tkind == "hostile_humans":
        tk, tt = "tracks", "Fresh boot prints, several people, circling back toward here."
    elif tkind == "lurker_signs":
        tk, tt = "damage", "Deep claw gouges in the door frame, higher than a man could reach."
    else:
        tk, tt = "tracks", "Dragging footprints in the dust, many of them, heading this way."
    trace_id = P.trace_create(tx, start, tk, tt, None, at, 0)
    # 5 leads
    cands = []
    for z in region.zones:
        for p in z.site_ids:
            pl = places[p]
            if pl["kind"] != "building" or not pl["archetype_ref"] or p in stl_sites or p == start:
                continue
            if any(r.loot_table for r in canon.get(pl["archetype_ref"]).rooms):
                cands.append(p)
    order = rng.shuffle(tx, SO, "magnets", sorted(cands))
    order = sorted(order, key=lambda p: places[p]["zone_id"] == region.start_zone_id)
    magnets = order[:3]
    first = contacts[0] if contacts else None
    home = next(s for s in plan.settlements if s.settlement_id == people.home_settlement_id)
    res_word = "water" if values["water"] <= values["food"] else "food"
    held = {body: [], **({first: []} if first else {})}
    pws = {body: [], **({first: []} if first else {})}
    for p in magnets:
        text = f"There is still something worth taking at {places[p]['name']} in {zones[places[p]['zone_id']].name}."
        for h in held:
            pid = tx.mint("prp")
            pws[h].append(W("propositions", {"prop_id": pid, "subject_type": "place", "subject_id": p, "predicate": "lead", "text": text,
                                             "matches_claim": None, "created_event": "worldgen", "object_value": None}))
            prov = ("told_by:" + first) if (h == body and first) else "common"
            held[h].append((pid, prov))
        pws[body].append(W("known_places", {"holder_id": body, "place_id": p, "first_seen": at, "last_seen": at, "visited": 0},
                           WriteOp.UPSERT, {"holder_id": body, "place_id": p}))
    pid = tx.mint("prp")
    pws[body].append(W("propositions", {"prop_id": pid, "subject_type": "place", "subject_id": home.site_id, "predicate": "shortage",
                                        "text": f"Everyone at {home.name} is counting the {res_word}.", "matches_claim": None,
                                        "created_event": "worldgen", "object_value": None}))
    held[body].append((pid, "common"))
    for h in held:
        ev = commit(tx, EventType.PERCEIVE, "mind.perception", at, pws[h], {"holder_id": h, "seed": True}, actor_id=h)
        commit(tx, EventType.PERCEIVE, "mind.perception", at, [
            W("claim_holdings", {"holder_id": h, "claim_id": q, "believed": 1, "confidence": 2, "provenance": prov, "fidelity": "exact",
                                 "acquired_at": at, "acquired_via": ev.event_id}) for q, prov in held[h]],
            {"holder_id": h, "seed": True, "beliefs": len(held[h])}, actor_id=h)
    # 6 opening texts
    role_of = people.roles
    ents = [{"id": c, "what": f"{name_of(c)}, {role_of.get(c, 'leader')}"} for c in contacts]
    if tkind == "lurker_signs":
        ents.append({"id": trace_id, "what": "claw marks at the start place"})
    else:
        ents += [{"id": t, "what": "raider" if tkind == "hostile_humans" else "infected"} for t in threat_ids]
    ents += [{"id": p, "what": places[p]["name"]} for p in magnets]
    ents.append({"id": home.settlement_id, "what": home.name})
    ids = {e["id"] for e in ents}
    fields = {"pc": pc.identity.name, "place": places[start]["name"], "zone": sz.name, "entities": ents,
              "params": {k: values[k] for k in AB_NAMES}, "placement": placement.model_dump(mode="json"),
              "budgets": dict(tables.OPENING_BUDGETS)}
    brief = (f"{pc.identity.name} starts at {places[start]['name']} in {sz.name}, {dsf} days after the Fall. "
             f"Write what is pressing on them right now, citing the listed entities and parameters.")
    patches = list(qc.patches)
    opening, err = await _opening_call(client, WorldgenContext(stage="WG8", brief=brief, fields=fields))
    if opening is not None:
        err = _qc4(opening.model_dump(), ids)
    if err is not None:
        opening, err2 = await _opening_call(client, WorldgenContext(stage="WG8", brief=brief, fields={**fields, "error": err}))
        if opening is not None:
            err2 = _qc4(opening.model_dump(), ids)
        if err2 is not None:
            tname = places[tplace]["name"]
            opening = fallback_opening(pc.identity.name, places[start]["name"], [(c, name_of(c)) for c in contacts], tkind,
                                       threat_ids, tname, values)
            patches.append("QC-4: opening written by code")
    # 7 survival history
    fn = pc.identity.name.split()[0]
    texts = [t for t in (pc.recap.formative_incident_1, pc.recap.formative_incident_2, pc.recap.unresolved_complication,
                         pc.recap.survival_pattern) if t][:5]
    extra = [f"{fn} got through the first weeks near {sz.name}.", f"{fn} learned the roads around {sz.name} by heart."]
    while len(texts) < 3:
        texts.append(extra.pop(0))
    days = sorted(rng.range_int(tx, SO, f"personal:{i}", 1, max(1, dsf - 1)) for i in range(len(texts)))
    hws, ews = [], []
    for d, t in zip(days, texts):
        hws.append(W("history_events", {"hist_id": tx.mint("his"), "day": d, "kind": "personal", "subject_ids": [body],
                                        "cause_hist_id": None, "truth_text": t, "belief_text": t}))
        ews.append(W("episodes", {"episode_id": tx.mint("epi"), "holder_id": body, "at": d * DAY + 12 * H, "turn_index": 0,
                                  "place_id": None, "summary": t, "salience": 95, "percept_ids": [], "subject_ids": [body],
                                  "anchor": 1, "decayed": 0}))
    commit(tx, EventType.WORLDGEN_STAGE, "world.worldgen", at, hws, {"stage": "WG8", "personal": len(hws)})
    commit(tx, EventType.ANCHOR_MEMORY, "mind.memory", at, ews, {"holder_id": body, "anchors": len(ews), "seed": True}, actor_id=body)
    # 8 commit json
    arch = places[start]["archetype_ref"]
    district = canon.get(arch).name if arch else places[start]["kind"]
    wc = WorldgenCommit(run_id=run_id, seed=seed, pc_ref=pc_ref, params=params, placement=placement, start_zone_type=sz.kind,
                        start_district_type=district[:40], opening=opening,
                        qc_result="patched" if patches else "pass", qc_patches=patches)
    commit(tx, EventType.WORLDGEN_STAGE, "world.worldgen", at, [
        W("world_params", {"commit_json": canonical_json(wc.model_dump(mode="json"))}, WriteOp.UPDATE, {"id": 1})],
        {"stage": "WG8", "commit": True})
    return Opening(pc_body=body, start_place_id=start, contacts=contacts, threat_kind=tkind, threat_place_id=tplace,
                   threat_ids=threat_ids, magnets=magnets, telegraph_trace_id=trace_id, opening=opening)


# ------------------------------------------------------------------------------------------ WG9 checks
def _holds(store, holder, predicate, subject=None):
    sql = ("SELECT p.subject_id FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id WHERE h.holder_id=? "
           "AND h.superseded_by IS NULL AND h.believed=1 AND p.predicate=?")
    return {r[0] for r in store.query(sql, (holder, predicate))}


def assert_world(store, region, plan, opening):
    from ...audit.commit_gate import compute
    from ...physical.space import places_near
    from ...society.population import census, demographic_issues
    from ...society.settlement import days_of
    out = []
    pc = store.query_one("SELECT value FROM meta WHERE key='pc_actor_id'")[0]
    leads = _holds(store, pc, "lead")
    if not (len(opening.magnets) >= 3 and all(m in leads for m in opening.magnets)):
        out.append("Fewer than three places worth the risk.")
    short = any(days_of(store, s.settlement_id, r) < 7 for s in plan.settlements for r in ("food", "water"))
    if not (short and _holds(store, pc, "shortage")):
        out.append("No settlement is short of anything.")
    here = store.query_one("SELECT place_id FROM positions WHERE body_id=?", (pc,))[0]
    near = set(places_near(store, here, 2)) | {here}
    okt = bool(opening.threat_ids)
    for t in opening.threat_ids:
        a = store.query_one("SELECT alive FROM bodies WHERE body_id=?", (t,))
        p = store.query_one("SELECT place_id FROM positions WHERE body_id=?", (t,))
        okt = okt and a is not None and a[0] == 1 and p is not None and p[0] in near
    if not okt:
        out.append("Nothing dangerous is near the start.")
    if store.query_one("SELECT 1 FROM traces WHERE trace_id=? AND place_id=?", (opening.telegraph_trace_id, here)) is None:
        out.append("Nothing warns of the danger.")
    if not any(_edge_disjoint_paths(_route_edges(store, region), region.start_zone_id, z.zone_id) >= 2
               for z in region.zones if z.zone_id != region.start_zone_id):
        out.append("The start zone has only one way out.")
    named = set()
    for r in store.query("SELECT subject_ids FROM history_events"):
        named |= set(json.loads(r[0]))
    for s in plan.settlements:
        if s.settlement_id not in named:
            out.append(f"{s.name} has no history.")
    for g in plan.groups:
        if g.group_id not in named:
            out.append(f"{g.name} has no history.")
    rules = store.rules.society
    for s in plan.settlements:
        for issue in demographic_issues(census(store, s.settlement_id), rules):
            out.append(f"{s.name}: {issue}")
    gr = compute(store, 0)
    if not gr.passed:
        out.append(f"The world fails its own checks: {', '.join(gr.failures)}.")
    return out


# ------------------------------------------------------------------------------------------ pipeline
STAGE_STREAMS = {"WG0": ("worldgen:params", "worldgen:placement"), "WG1": ("worldgen:region",),
                 "WG2": ("worldgen:history", "worldgen:placement"), "WG4": ("worldgen:polity",),
                 "WG5": ("worldgen:polity",), "WG6": ("worldgen:people",), "WG8": ("worldgen:opening",)}


async def run_worldgen(store, client, canon, pc_ref, settings, config, *, run_id, world_id, world_dir, progress=None):
    import inspect
    from pathlib import Path
    from ...kernel import clock
    from ...kernel.rng import Rng
    from ...kernel.store import wall_clock_iso
    from ...lanes import calllog
    from . import checks as checks_mod, history as history_mod, opening as opening_mod, params as params_mod
    from . import people as people_mod, placement as placement_mod, polity as polity_mod, region as region_mod
    from .history import home_settlement  # noqa: F401
    from .pipeline import WorldgenAborted, WorldgenAssertion, WorldgenReport
    seed = int(store.meta("seed"))
    rng = Rng(seed)
    pc = canon.get(pc_ref)
    detail = str(getattr(settings.world_detail, "value", settings.world_detail))
    T = tables.DETAIL_TIERS[detail]
    report = WorldgenReport(world_id=world_id)
    state = {"tx": None}
    old_on_call = getattr(client, "on_call", None)

    def on_call(req, resp):
        report.model_calls += 1
        if state["tx"] is not None:
            calllog.record(state["tx"], req, resp)
    client.on_call = on_call
    ctx = {}

    async def say(stage):
        if progress is None:
            return
        i = atlas.STAGES.index(stage)
        pct = float(sum(atlas.STAGE_SHARE[s] for s in atlas.STAGES[:i]))
        eta = (100 - pct) * T["est_minutes"] * 60 / 100
        r = progress(WorldgenProgress(stage=stage, label=atlas.STAGE_LABELS[stage], pct=pct, eta_s=eta))
        if inspect.isawaitable(r):
            await r

    def sub(stage, name):
        async def report(done, total):
            if progress is None or not total:
                return
            i = atlas.STAGES.index(stage)
            start = float(sum(atlas.STAGE_SHARE[s] for s in atlas.STAGES[:i]))
            pct = round(start + atlas.STAGE_SHARE[stage] * done / total, 1)
            eta = (100 - pct) * T["est_minutes"] * 60 / 100
            r = progress(WorldgenProgress(stage=stage, label=atlas.STAGE_LABELS[stage], pct=pct, eta_s=eta, sub=name,
                                          done=done, total=total))
            if inspect.isawaitable(r):
                await r
        return report

    async def run_stage(stage, fn):
        await say(stage)
        for attempt in range(2):
            try:
                with store.transaction() as tx:
                    state["tx"] = tx
                    if attempt == 1:
                        for st in STAGE_STREAMS.get(stage, ()):
                            rng.draw(tx, st, "retry", 2)
                    r = fn(tx)
                    if inspect.isawaitable(r):
                        r = await r
                    at = ctx.get("at", 0)
                    commit(tx, EventType.WORLDGEN_STAGE, "world.worldgen", at, [], {"stage": stage})
                state["tx"] = None
                report.stages.append(stage)
                return r
            except WorldgenAssertion as e:
                state["tx"] = None
                if attempt == 1:
                    raise WorldgenAborted("stage_failed", f"{atlas.STAGE_LABELS[stage]} failed twice: {e}") from None
                report.retries.append(stage)
            finally:
                state["tx"] = None
    try:
        def wg0(tx):
            params, patches = params_mod.generate_params(rng, tx, settings.difficulty, settings.era, pc.worldgen_bias,
                                              settings.days_since_fall, fall_range=pc.days_since_fall_range,
                                              pc_name=pc.identity.name)
            values = flat_values(params)
            pl = placement_mod.place(rng, tx, values, pc, canon)
            q = placement_mod.qc(rng, tx, params, pl, pc, canon, settings.difficulty, patches)
            if q.result == "aborted":
                raise WorldgenAborted("hopeless_start",
                                      f"{pc.identity.name} cannot survive the start this world gives them at "
                                      f"{atlas.DIFFICULTY_LABELS[str(Difficulty(settings.difficulty).value)]}. Try one difficulty "
                                      f"lower, another character, or another era.",
                                      ["difficulty_lower", "change_character", "change_era"])
            from ...kernel.jsoncanon import canonical_json
            commit(tx, EventType.WORLDGEN_STAGE, "world.worldgen", clock.now(tx), [
                W("world_params", {"id": 1, "params_json": canonical_json(q.params.model_dump(mode="json")), "commit_json": "{}"})],
                {"stage": "WG0", "patches": len(q.patches)})
            to = q.params.days_since_fall * DAY + tx.rules.world.start_hour * H
            clock.advance_event(tx, to, "worldgen")
            ctx["at"] = to
            ctx["params"], ctx["qc"] = q.params, q
            ctx["placement"] = q.placement
            report.qc_result, report.qc_patches = q.result, list(q.patches)
        await run_stage("WG0", wg0)
        params, at = ctx["params"], ctx["at"]

        def wg1(tx):
            region = region_mod.build_region(rng, tx, params, detail, canon, at)
            region_mod.assert_region(tx, region)
            ctx["region"] = region
        await run_stage("WG1", wg1)
        region = ctx["region"]

        async def wg2(tx):
            plan = history_mod.plan_polity(rng, tx, params, ctx["placement"], region, canon)
            evs = history_mod.skeleton(rng, tx, params, plan, region, T)
            await history_mod.write_history(client, tx, evs, plan, region, params, at, progress=sub("WG2", "history"))
            history_mod.mark_held(tx, plan, at)
            ctx["plan"] = plan
        await run_stage("WG2", wg2)
        plan = ctx["plan"]
        await run_stage("WG3", lambda tx: polity_mod.write_groups(tx, plan, params, canon, at))
        await run_stage("WG4", lambda tx: polity_mod.write_settlements(rng, tx, plan, params, region, at))
        await run_stage("WG5", lambda tx: polity_mod.write_cohorts(rng, tx, plan, params, at))

        async def wg6(tx):
            ctx["people"] = await people_mod.write_people(client, rng, tx, plan, region, params, canon, detail, at,
                                                          progress=sub("WG6", "dossiers"))
        await run_stage("WG6", wg6)
        people = ctx["people"]
        report.skipped_actors = list(people.skipped)
        await run_stage("WG7", lambda tx: polity_mod.write_laws(tx, plan, params, canon, at))
        # genesis
        wd = Path(world_dir)
        wd.mkdir(parents=True, exist_ok=True)
        store.backup_to(wd / "genesis.sqlite")
        era = str(Era(settings.era).value)
        cd = params.climate_descriptor
        wj = {"world_id": world_id, "title": f"{cd[:1].upper() + cd[1:]} — {atlas.ERA_LABELS[era]}, day {params.days_since_fall}",
              "difficulty": str(Difficulty(settings.difficulty).value), "era": era, "day_at_genesis": params.days_since_fall,
              "climate_text": cd, "factions": [g.name for g in plan.groups if g.kind == "faction"],
              "created_real": wall_clock_iso(), "source": "generated", "seed": seed, "detail": detail}
        (wd / "world.json").write_text(json.dumps(wj, sort_keys=True, indent=2), encoding="utf-8")

        async def wg8(tx):
            ctx["opening"] = await opening_mod.place_pc(client, rng, tx, pc_ref, pc, params, ctx["placement"], plan, region, people, canon,
                                            run_id, seed, ctx["qc"], at)
        await run_stage("WG8", wg8)
        opening = ctx["opening"]
        if opening.opening is not None:
            wc = json.loads(store.query_one("SELECT commit_json FROM world_params WHERE id=1")[0])
            report.qc_patches = list(wc.get("qc_patches", report.qc_patches))
            report.qc_result = wc.get("qc_result", report.qc_result)

        def wg9(tx):
            fails = checks_mod.assert_world(tx, region, plan, opening)
            if fails:
                raise WorldgenAborted("invariant", "The world did not hold together: "
                                      + "; ".join(f.rstrip(".") for f in fails) + ".")
        await run_stage("WG9", wg9)
        await say("COMMIT")
        with store.transaction() as tx:
            commit(tx, EventType.WORLDGEN_STAGE, "world.worldgen", at, [], {"stage": "COMMIT", "world_id": world_id})
        report.stages.append("COMMIT")
        return report
    finally:
        client.on_call = old_on_call
