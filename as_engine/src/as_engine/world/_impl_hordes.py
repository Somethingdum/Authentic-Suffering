"""Implementation of world/hordes.py (P10)."""
from __future__ import annotations

import json
import math

from ..contracts.events import Event, EventType, WriteOp, WriteRecord

DAY = 86_400_000
HOUR = 3_600_000
MIN = 60_000


def _types():
    from .infected import CRAWLER, RUNNER, SHAMBLER
    return (SHAMBLER, CRAWLER, RUNNER)


def _j(v, d=None):
    if v is None:
        return d
    if isinstance(v, (dict, list)):
        return v
    return json.loads(v)


def _row(s, sql, p=()):
    r = s.query_one(sql, p)
    return dict(r) if r is not None else None


def _rows(s, sql, p=()):
    return [dict(r) for r in s.query(sql, p)]


def _E(tx, type_, at, turn_index, writes, payload, *, writer="world.hordes", cause=None, actor_id=None, place_id=None,
       origin="sim"):
    return tx.commit_event(Event(type=type_, writer=writer, at=at, turn_index=turn_index, cause_event_id=cause,
                                 actor_id=actor_id, place_id=place_id, payload=payload, writes=writes, origin=origin))


def _W(table, values, op=WriteOp.INSERT, key=None):
    return WriteRecord(op=op, table=table, key=key or {}, values=values)


def _maxseq(tx):
    return tx.query_one("SELECT COALESCE(MAX(seq),0) FROM events")[0]


def _since(tx, first):
    from ..action._impl_p5b import _events_since
    return _events_since(tx, first)


def _area(tx, turn_index):
    from ._impl_p10 import _area as area
    return area(tx, turn_index)


def _params(tx):
    from ._impl_p10 import _params as params
    return params(tx)


def _values(tx):
    from ._impl_p10 import _values as values
    return values(tx)


def _ev(v):
    return str(getattr(v, "value", v))


# ------------------------------------------------------------------------------------------ HRD-01 pools
def pool(store, zone_id):
    out = {}
    for t in _types():
        r = store.query_one("SELECT active, dormant FROM infected_pools WHERE zone_id=? AND type_id=?", (zone_id, t))
        out[t] = (r[0], r[1]) if r else (0, 0)
    return out


def total(store, zone_id):
    return sum(a + d for a, d in pool(store, zone_id).values())


def change(tx, zone_id, type_id, active_delta, dormant_delta, reason, at, turn_index, cause, *, origin="sim"):
    if active_delta == 0 and dormant_delta == 0:
        raise ValueError("a pool change must change something")
    r = tx.query_one("SELECT active, dormant FROM infected_pools WHERE zone_id=? AND type_id=?", (zone_id, type_id))
    a, d = (r[0], r[1]) if r else (0, 0)
    na, nd = a + active_delta, d + dormant_delta
    if na < 0 or nd < 0:
        raise ValueError(f"not that many dead in {zone_id} ({type_id})")
    return _E(tx, EventType.POOL_CHANGE, at, turn_index,
              [_W("infected_pools", {"zone_id": zone_id, "type_id": type_id, "active": na, "dormant": nd}, WriteOp.UPSERT,
                  {"zone_id": zone_id, "type_id": type_id})],
              {"zone_id": zone_id, "type_id": type_id, "active_delta": active_delta, "dormant_delta": dormant_delta,
               "active": na, "dormant": nd, "reason": reason}, cause=cause, origin=origin)


def seed_pools(tx, params, at):
    from .worldgen import atlas
    from .worldgen.params import flat_values
    H = tx.rules.hordes
    v = flat_values(params)
    era, diff = _ev(params.era), _ev(params.difficulty)
    SH, CR, RU = _types()
    out = []
    for z in _rows(tx, "SELECT zone_id, kind FROM zones ORDER BY zone_id"):
        if z["kind"] == "exterior":
            base, scale = H.exterior_pool[diff], 0.5 + v["zombie_common"] / 10
        else:
            base, scale = atlas.ZONE_INFECTED[z["kind"]], 0.4 + v["zombie_common"] / 10
        n = round(base * scale)
        runner = round(n * H.runner_share[era] * v["runner_pressure"] / 5)
        crawler = round(n * H.crawler_share)
        sh = n - runner - crawler
        if sh < 0:
            crawler = max(0, crawler + sh)
            sh = n - runner - crawler
            if sh < 0:
                runner = max(0, runner + sh)
                sh = n - runner - crawler
        for t, c in ((SH, sh), (CR, crawler), (RU, runner)):
            if c > 0:
                dorm = round(c * H.dormant_share[era])
                out.append(change(tx, z["zone_id"], t, c - dorm, dorm, "worldgen", at, 0, None, origin="worldgen"))
    return out


# ------------------------------------------------------------------------------------------ HRD-03 hordes
def _horde(s, horde_id):
    r = _row(s, "SELECT * FROM hordes WHERE horde_id=?", (horde_id,))
    if r is None:
        return None
    for k, d in (("composition", {}), ("route", []), ("props", {})):
        r[k] = _j(r[k], d)
    return r


def count(store, horde_id):
    h = _horde(store, horde_id)
    return 0 if h is None else sum(h["composition"].values())


def _hub(store, zone_id):
    r = store.query_one("SELECT p.place_id FROM places p JOIN zones z ON z.zone_id = p.zone_id AND z.name = p.name "
                        "WHERE p.zone_id=? AND p.kind='street' ORDER BY p.place_id LIMIT 1", (zone_id,))
    return r[0] if r else None


def _is_hub(store, place_id):
    r = store.query_one("SELECT p.kind, p.name, z.name FROM places p JOIN zones z ON z.zone_id = p.zone_id "
                        "WHERE p.place_id=?", (place_id,))
    return r is not None and r[0] == "street" and r[1] == r[2]


def _is_road(store, place_id):
    r = store.query_one("SELECT kind, parent_id FROM places WHERE place_id=?", (place_id,))
    return r is not None and r[0] == "street" and r[1] is None and not _is_hub(store, place_id)


def target(store, place_id):
    cur = place_id
    for _ in range(50):
        r = store.query_one("SELECT parent_id FROM places WHERE place_id=?", (cur,))
        if r is None or r[0] is None:
            return cur
        cur = r[0]
    return cur


def _zone(store, place_id):
    r = store.query_one("SELECT zone_id FROM places WHERE place_id=?", (target(store, place_id),))
    return r[0] if r else None


def _zone_kind(store, zone_id):
    r = store.query_one("SELECT kind FROM zones WHERE zone_id=?", (zone_id,))
    return r[0] if r else None


def _road_between(store, a, b):
    for r in store.query(
            "SELECT p.place_id FROM places p WHERE p.kind='street' AND p.parent_id IS NULL AND "
            "EXISTS (SELECT 1 FROM portals x WHERE (x.place_a=p.place_id AND x.place_b=?) OR (x.place_b=p.place_id AND x.place_a=?)) AND "
            "EXISTS (SELECT 1 FROM portals y WHERE (y.place_a=p.place_id AND y.place_b=?) OR (y.place_b=p.place_id AND y.place_a=?)) "
            "ORDER BY p.place_id", (a, a, b, b)):
        if not _is_hub(store, r[0]):
            return r[0]
    return None


def _neighbour_hubs(store, hub):
    out = []
    for r in store.query("SELECT route_id, from_place, to_place FROM routes WHERE from_place=? OR to_place=? ORDER BY route_id",
                         (hub, hub)):
        out.append(r[2] if r[1] == hub else r[1])
    return out


def path(store, from_place, to_place):
    to = target(store, to_place)
    fr = target(store, from_place)
    if fr == to:
        return []
    out = []
    start_hub = fr if _is_hub(store, fr) else _hub(store, _zone(store, fr))
    if start_hub is None:
        return None
    if start_hub != fr:
        out.append(start_hub)
    to_hub = to if _is_hub(store, to) else _hub(store, _zone(store, to))
    if to_hub is None:
        return None
    if start_hub != to_hub:
        prev = {start_hub: None}
        queue = [start_hub]
        while queue:
            h = queue.pop(0)
            if h == to_hub:
                break
            for o in _neighbour_hubs(store, h):
                if o not in prev:
                    prev[o] = h
                    queue.append(o)
        if to_hub not in prev:
            return None
        seq, cur = [], to_hub
        while prev[cur] is not None:
            seq.append((prev[cur], cur))
            cur = prev[cur]
        for a, b in reversed(seq):
            out += [_road_between(store, a, b), b]
    if to != to_hub:
        out.append(to)
    return out


def leg_ms(store, from_place, to_place, speed_m_s):
    if _is_road(store, from_place) and _is_hub(store, to_place):
        w = store.query_one("SELECT width_m FROM places WHERE place_id=?", (from_place,))[0]
        return round(w / speed_m_s * 1000)
    return 2 * MIN


def _clean(comp):
    return {t: comp[t] for t in _types() if comp.get(t, 0) > 0}


def form(tx, kind, zone_id, composition, to_place, at, turn_index, cause, *, props=None, first_leg_ms=None):
    from ..kernel import clock
    H = tx.rules.hordes
    comp = _clean(composition)
    pl = pool(tx, zone_id)
    for t, n in comp.items():
        if pl[t][0] < n:
            raise ValueError(f"only {pl[t][0]} active {t} in {zone_id}")
    hub = _hub(tx, zone_id)
    route = path(tx, hub, to_place) if hub else None
    if route is None:
        raise ValueError(f"no way from {zone_id} to {to_place}")
    for t, n in comp.items():
        change(tx, zone_id, t, -n, 0, "horde", at, turn_index, cause)
    hid = tx.mint("hrd")
    pr = dict(props or {})
    status = "moving" if route else "milling"
    if status == "milling":
        pr["until"] = at + int(H.mill_h * HOUR)
    tgt = target(tx, to_place)
    if first_leg_ms is not None:
        due = at + int(first_leg_ms)
    elif status == "moving":
        due = at + leg_ms(tx, hub, route[0], H.speed_m_s)
    else:
        due = pr["until"]
    ev = _E(tx, EventType.HORDE_FORMED, at, turn_index,
            [_W("hordes", {"horde_id": hid, "kind": kind, "composition": comp, "zone_id": zone_id, "place_id": hub,
                           "route": route, "target_place": tgt, "status": status, "origin": zone_id, "since": at,
                           "props": pr})],
            {"horde_id": hid, "kind": kind, "composition": comp, "zone_id": zone_id, "place_id": hub, "route": route,
             "target_place": tgt}, cause=cause, place_id=hub)
    clock.schedule(tx, due, "HORDE_STEP", hid, {"horde_id": hid}, ev.event_id)
    return hid


def _state(tx, horde_id, changes, at, turn_index, cause):
    return _E(tx, EventType.HORDE_STATE, at, turn_index, [_W("hordes", changes, WriteOp.UPDATE, {"horde_id": horde_id})],
              {"horde_id": horde_id, "changes": changes}, cause=cause)


def _gone(tx, horde_id, reason, zone_id, at, turn_index, cause):
    kind = tx.query_one("SELECT kind FROM hordes WHERE horde_id=?", (horde_id,))[0]
    ev = _E(tx, EventType.HORDE_GONE, at, turn_index,
            [_W("hordes", {"status": "gone", "composition": {}}, WriteOp.UPDATE, {"horde_id": horde_id})],
            {"horde_id": horde_id, "reason": reason, "zone_id": zone_id}, cause=cause)
    if kind == "mega":
        from . import factions
        factions.passage(tx, horde_id, False, at, turn_index, ev.event_id)
    return ev


def _outdoor(tx, zone_id):
    return [r[0] for r in tx.query("SELECT place_id FROM places WHERE zone_id=? AND parent_id IS NULL AND indoor=0 "
                                   "ORDER BY place_id", (zone_id,))]


def _settlements_in(tx, zone_id):
    return [r[0] for r in tx.query("SELECT s.settlement_id FROM settlements s JOIN places p ON p.place_id = s.place_id "
                                   "WHERE p.zone_id=? ORDER BY s.settlement_id", (zone_id,))]


def step(tx, rng, row, fired, turn_index):
    from ..kernel import clock
    first = _maxseq(tx)
    p = _j(row["payload"], {})
    h = _horde(tx, p.get("horde_id"))
    if h is None or h["status"] == "gone":
        return []
    H = tx.rules.hordes
    at = row["due_at"]
    cause = fired.event_id
    hid = h["horde_id"]
    area = set(_area(tx, turn_index))
    props = dict(h["props"])
    last = cause
    if h["status"] == "moving":
        nxt = h["route"][0]
        nz = _zone(tx, nxt)
        comp = dict(h["composition"])
        strag, rall = {}, {}
        hub = _is_hub(tx, nxt)
        if hub:
            zp = pool(tx, nz)
            for t in _types():
                k = math.floor(comp.get(t, 0) * H.straggle)
                if k:
                    strag[t] = k
            for t in _types():
                if h["kind"] in ("drift", "mega"):
                    r = math.floor(zp[t][0] * H.rally)
                    if r:
                        rall[t] = r
            for t in _types():
                comp[t] = comp.get(t, 0) - strag.get(t, 0) + rall.get(t, 0)
        comp = _clean(comp)
        payload = {"horde_id": hid, "from_place": h["place_id"], "to_place": nxt, "zone_id": nz}
        if strag:
            payload["stragglers"] = strag
        if rall:
            payload["rallied"] = rall
        mv = _E(tx, EventType.HORDE_MOVED, at, turn_index,
                [_W("hordes", {"place_id": nxt, "zone_id": nz, "route": h["route"][1:], "composition": comp}, WriteOp.UPDATE,
                    {"horde_id": hid})], payload, cause=cause, place_id=nxt)
        last = mv.event_id
        for t, k in strag.items():
            change(tx, nz, t, k, 0, "straggled", at, turn_index, mv.event_id)
        for t, r in rall.items():
            change(tx, nz, t, -r, 0, "rallied", at, turn_index, mv.event_id)
        if not comp:
            _gone(tx, hid, "spent", nz, at, turn_index, mv.event_id)
            return _since(tx, first)
        h = _horde(tx, hid)
        route = h["route"]
        is_region = _zone_kind(tx, nz) != "exterior"
        if h["kind"] == "mega" and hub and is_region:
            _passage_start(tx, rng, h, nz, at, turn_index, mv.event_id)
        elif h["kind"] == "mega" and hub and nz == props.get("exit_zone"):
            for t, n in h["composition"].items():
                change(tx, nz, t, n, 0, "passed", at, turn_index, mv.event_id)
            _gone(tx, hid, "left", nz, at, turn_index, mv.event_id)
            return _since(tx, first)
        elif h["kind"] != "mega" and nxt == h["target_place"]:
            props["until"] = at + int(H.mill_h * HOUR)
            _state(tx, hid, {"status": "milling", "props": props}, at, turn_index, mv.event_id)
            if hub:
                sts = _settlements_in(tx, nz)
            else:
                sts = [r[0] for r in tx.query("SELECT settlement_id FROM settlements WHERE place_id=?", (nxt,))]
            for sid in sts:
                press(tx, rng, hid, sid, at, turn_index, mv.event_id)
        hn = _horde(tx, hid)
        if hn["kind"] == "mega" and hn["status"] == "milling":
            for pl in _outdoor(tx, nz):
                if pl in area and _horde(tx, hid)["status"] != "gone":
                    promote(tx, rng, hid, pl, at, turn_index, mv.event_id)
        elif nxt in area and hn["status"] != "gone":
            promote(tx, rng, hid, nxt, at, turn_index, mv.event_id)
    else:
        if at >= props.get("until", at):
            if h["kind"] == "mega":
                last = _passage_end(tx, rng, h, at, turn_index, cause)
            else:
                for t, n in h["composition"].items():
                    change(tx, h["zone_id"], t, n, 0, "dispersed", at, turn_index, cause)
                _gone(tx, hid, "dispersed", h["zone_id"], at, turn_index, cause)
                return _since(tx, first)
        else:
            if h["kind"] == "mega":
                if props.get("next_press") is not None and at >= props["next_press"]:
                    for sid in _settlements_in(tx, h["zone_id"]):
                        press(tx, rng, hid, sid, at, turn_index, cause)
                    props = dict(_horde(tx, hid)["props"])
                    props["next_press"] = props["next_press"] + DAY
                    _state(tx, hid, {"props": props}, at, turn_index, cause)
                for pl in _outdoor(tx, h["zone_id"]):
                    if pl in area and _horde(tx, hid)["status"] != "gone":
                        promote(tx, rng, hid, pl, at, turn_index, cause)
            elif h["place_id"] in area:
                promote(tx, rng, hid, h["place_id"], at, turn_index, cause)
    h = _horde(tx, hid)
    if h is None or h["status"] == "gone":
        return _since(tx, first)
    evs = _since(tx, first)
    last = evs[-1].event_id if evs else cause
    if h["status"] == "moving":
        due = at + leg_ms(tx, h["place_id"], h["route"][0], h["props"].get("speed_m_s") or H.speed_m_s)
    else:
        pr = h["props"]
        cands = [pr["until"]]
        if h["kind"] == "mega" and pr.get("next_press") is not None:
            cands.append(pr["next_press"])
        watched = [h["place_id"]] if h["kind"] != "mega" else _outdoor(tx, h["zone_id"])
        if any(x in area for x in watched):
            cands.append(at + int(H.tick_min * MIN))
        due = max(at + 1, min(cands))
    clock.schedule(tx, due, "HORDE_STEP", hid, {"horde_id": hid}, last)
    return _since(tx, first)


# ------------------------------------------------------------------------------------------ HRD-07 promote
def promote(tx, rng, horde_id, place_id, at, turn_index, cause):
    from ..physical import space
    from . import infected
    H = tx.rules.hordes
    h = _horde(tx, horde_id)
    if h is None or h["status"] == "gone":
        return []
    present = tx.query_one(
        "SELECT COUNT(*) FROM infected_state i JOIN positions q ON q.body_id = i.body_id JOIN bodies b ON b.body_id = i.body_id "
        "WHERE i.horde_id=? AND q.place_id=? AND b.alive=1", (horde_id, place_id))[0]
    cnt = sum(h["composition"].values())
    n = min(H.local_cap - present, cnt)
    if n <= 0:
        return []
    pr = tx.query_one("SELECT portal_id FROM portals WHERE place_a=? OR place_b=? ORDER BY portal_id LIMIT 1", (place_id, place_id))
    if pr is not None:
        x, y = space.portal_point(tx, pr[0], place_id)
    else:
        d = tx.query_one("SELECT width_m, depth_m FROM places WHERE place_id=?", (place_id,))
        x, y = d[0] / 2, d[1] / 2
    comp = dict(h["composition"])
    ids = []
    for t in _types():
        m = min(comp.get(t, 0), n - len(ids))
        for _ in range(m):
            ids.append(infected.spawn(tx, rng, place_id, t, at, turn_index, cause, x_m=x, y_m=y, origin="materialize",
                                      horde_id=horde_id))
        if m:
            comp[t] -= m
    comp = _clean(comp)
    ev = _E(tx, EventType.HORDE_PROMOTED, at, turn_index,
            [_W("hordes", {"composition": comp}, WriteOp.UPDATE, {"horde_id": horde_id})],
            {"horde_id": horde_id, "place_id": place_id, "bodies": ids, "composition": comp}, cause=cause, place_id=place_id)
    if not comp:
        _gone(tx, horde_id, "spent", h["zone_id"], at, turn_index, ev.event_id)
    living = [r[0] for r in tx.query("SELECT b.body_id FROM bodies b JOIN positions q ON q.body_id=b.body_id WHERE q.place_id=? "
                                     "AND b.alive=1 AND b.kind != 'infected' ORDER BY b.body_id", (place_id,))]
    for b in ids:
        seen = next((x for x in living if infected.sees(tx, b, x, at)), None)
        if seen is not None:
            infected.attract(tx, b, seen, at, ev.event_id, turn_index, reason="sight")
        elif h["status"] == "moving" and h["route"]:
            infected.attract(tx, b, h["route"][0], at, ev.event_id, turn_index, reason="horde")
    return ids


# ------------------------------------------------------------------------------------------ HRD-08 press
_BAND_RANK = {"infant": 0, "child": 1, "preteen": 2, "teen": 3, "elder": 4, "adult": 5}


def press(tx, rng, horde_id, settlement_id, at, turn_index, cause):
    from ..physical import bodies
    from ..physical.bodies import WoundSpec
    from ..society import population
    from ..society import settlement as stl
    from . import traces
    H = tx.rules.hordes
    N = count(tx, horde_id)
    s = _row(tx, "SELECT * FROM settlements WHERE settlement_id=?", (settlement_id,))
    D = s["defences"]
    pressure = N / (H.breach_scale * (1 + D))
    p = min(0.95, max(0.0, pressure - 0.5))
    from . import factions
    if s["group_id"] and factions.enclave(tx, s["group_id"]) == settlement_id:
        p = 0.0          # FAC-01: sealed underground
    breached = rng.chance(tx, "hordes", f"breach:{horde_id}:{settlement_id}:{at}", p)
    killed, bitten, deaths = 0, [], []
    if breached:
        cohorts = _rows(tx, "SELECT cohort_id, age_band, count FROM cohorts WHERE settlement_id=? AND count > 0", (settlement_id,))
        unnamed = sum(c["count"] for c in cohorts)
        killed = min(unnamed, math.ceil(N * H.breach_kill))
        rest = killed
        for c in sorted(cohorts, key=lambda c: (_BAND_RANK[c["age_band"]], c["cohort_id"]), reverse=True):
            m = min(c["count"], rest)
            if m:
                deaths.append((c["cohort_id"], m))
                rest -= m
            if rest == 0:
                break
        area = set(_area(tx, turn_index))
        site = s["place_id"]
        under = {site} | {r[0] for r in tx.query("SELECT place_id FROM places WHERE parent_id=?", (site,))}
        members = [r[0] for r in tx.query(
            "SELECT m.actor_id FROM group_members m JOIN bodies b ON b.body_id = m.actor_id JOIN positions q ON q.body_id = m.actor_id "
            "WHERE m.group_id=? AND m.status IN ('member','probation') AND b.alive=1 ORDER BY m.actor_id",
            (s["group_id"],))] if s["group_id"] else []
        for a in members:
            pl = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (a,))[0]
            if pl not in under or pl in area:
                continue
            if rng.chance(tx, "hordes", f"bite:{horde_id}:{a}:{at}", H.breach_bite):
                bitten.append(a)
    ev = _E(tx, EventType.HORDE_PRESSED, at, turn_index, [],
            {"horde_id": horde_id, "settlement_id": settlement_id, "count": N, "pressure": round(pressure, 2),
             "breached": breached, "killed": killed, "bitten": bitten}, cause=cause, place_id=s["place_id"])
    E_ = ev.event_id
    if not breached:
        if N >= H.breach_scale:
            stl.adjust(tx, settlement_id, "defences", -1, at, turn_index, E_, reason="horde")
            stl.adjust(tx, settlement_id, "morale", -1, at, turn_index, E_, reason="horde")
            traces.create(tx, s["place_id"], "damage", "Claw marks and dents all along the barricade.", E_, at, turn_index)
        return ev
    stl.adjust(tx, settlement_id, "defences", -2, at, turn_index, E_, reason="horde")
    stl.adjust(tx, settlement_id, "morale", -2, at, turn_index, E_, reason="horde")
    for cid, m in deaths:
        population.adjust_cohort(tx, cid, -m, "horde", at, turn_index, E_)
    if killed:
        schedule_rise(tx, rng, _zone(tx, s["place_id"]), killed, "wet", at, turn_index, E_)
    for a in bitten:
        arm = rng.choice(tx, "hordes", f"bite_arm:{horde_id}:{a}:{at}", ["arm_l", "arm_r"])
        bodies.apply_harm(tx, a, WoundSpec(arm, "bite", "significant", 3), at, E_, turn_index, rng)
        bodies.expose(tx, rng, a, "wet", "bite", at, E_, turn_index)
    traces.create(tx, s["place_id"], "damage", "Barricades torn down; the gate hangs open.", E_, at, turn_index)
    traces.create(tx, s["place_id"], "blood", "Blood everywhere, and drag marks.", E_, at, turn_index)
    return ev


# ------------------------------------------------------------------------------------------ HRD-09 draw
def draw(tx, place_id, source_db, at, turn_index, cause):
    H = tx.rules.hordes
    if tx.query_one("SELECT 1 FROM places WHERE place_id=?", (place_id,)) is None:
        return None
    z = _zone(tx, place_id)
    if z is None or _zone_kind(tx, z) in (None, "exterior"):
        return None
    if tx.query_one("SELECT 1 FROM hordes WHERE kind='drawn' AND origin=? AND since > ?",
                    (z, at - int(H.draw_cooldown_h * HOUR))) is not None:
        return None
    comp = {}
    for t, (a, _d) in pool(tx, z).items():
        n = math.floor(a * H.draw_share * (source_db - H.draw_db + 10) / 10)
        if n > 0:
            comp[t] = n
    if not comp:
        return None
    return form(tx, "drawn", z, comp, place_id, at, turn_index, cause, first_leg_ms=H.draw_minutes * MIN)


# ------------------------------------------------------------------------------------------ HRD-10 day
def day(tx, rng, at, turn_index, cause):
    first = _maxseq(tx)
    H = tx.rules.hordes
    d = at // DAY
    SH, CR, RU = _types()
    for r in _rows(tx, "SELECT zone_id, active, dormant FROM infected_pools WHERE type_id=? AND active + dormant > 0 "
                       "ORDER BY zone_id", (RU,)):
        runners = r["active"] + r["dormant"]
        x = runners / H.runner_days
        n = math.floor(x) + (1 if rng.chance(tx, "hordes", f"degrade:{r['zone_id']}:{d}", x - math.floor(x)) else 0)
        n = min(n, runners)
        if n > 0:
            a = min(n, r["active"])
            b = n - a
            change(tx, r["zone_id"], RU, -a, -b, "degraded", at, turn_index, cause)
            change(tx, r["zone_id"], SH, a, b, "degraded", at, turn_index, cause)
    v = _values(tx)
    hp = v["horde_pressure"]
    for z in _rows(tx, "SELECT zone_id FROM zones WHERE kind != 'exterior' ORDER BY zone_id"):
        zid = z["zone_id"]
        zp = pool(tx, zid)
        act = sum(a for a, _ in zp.values())
        if act < H.drift_min:
            continue
        if not rng.chance(tx, "hordes", f"drift:{zid}:{d}", H.drift_chance * hp / 5):
            continue
        comp = _clean({t: math.floor(a * H.drift_share) for t, (a, _d) in zp.items()})
        if not comp:
            continue
        hub = _hub(tx, zid)
        hubs = sorted(o for o in _neighbour_hubs(tx, hub) if _zone_kind(tx, _zone(tx, o)) != "exterior")
        if not hubs:
            continue
        to = rng.choice(tx, "hordes", f"drift_to:{zid}:{d}", hubs)
        form(tx, "drift", zid, comp, to, at, turn_index, cause)
    _mega_form(tx, rng, at, turn_index, cause)
    _mega_signs(tx, at, turn_index, cause)
    return _since(tx, first)


# ------------------------------------------------------------------------------------------ HRD-11 census
def census(store):
    pools = {}
    for r in store.query("SELECT zone_id, type_id, active, dormant FROM infected_pools WHERE active + dormant > 0 "
                         "ORDER BY zone_id, type_id"):
        pools.setdefault(r[0], {})[r[1]] = [r[2], r[3]]
    hordes = []
    for r in _rows(store, "SELECT * FROM hordes WHERE status != 'gone' ORDER BY horde_id"):
        comp = _j(r["composition"], {})
        hordes.append({"horde_id": r["horde_id"], "kind": r["kind"], "count": sum(comp.values()), "zone_id": r["zone_id"],
                       "place_id": r["place_id"], "status": r["status"], "target_place": r["target_place"]})
    bodies = store.query_one("SELECT COUNT(*) FROM bodies b JOIN infected_state i ON i.body_id=b.body_id "
                             "WHERE b.kind='infected' AND b.alive=1 AND i.folded_at IS NULL")[0]
    tot = sum(a + d for z in pools.values() for a, d in z.values()) + sum(h["count"] for h in hordes) + bodies
    return {"pools": pools, "hordes": hordes, "bodies": bodies, "total": tot}


def density(store, zone_id):
    act = sum(a for a, _d in pool(store, zone_id).values())
    return min(10, round(10 * act / store.rules.hordes.density_full))


# ------------------------------------------------------------------------------------------ HRD-12..14 the Mega Horde
def _gateway(tx, exterior_zone):
    hub = _hub(tx, exterior_zone)
    for o in _neighbour_hubs(tx, hub):
        z = _zone(tx, o)
        if _zone_kind(tx, z) != "exterior":
            return z
    return None


def _hops(tx, from_zone, to_zone):
    a, b = _hub(tx, from_zone), _hub(tx, to_zone)
    if a == b:
        return 0
    seen, frontier, k = {a}, [a], 0
    while frontier:
        k += 1
        nxt = []
        for h in frontier:
            for o in _neighbour_hubs(tx, h):
                if o == b:
                    return k
                if o not in seen and _zone_kind(tx, _zone(tx, o)) != "exterior":
                    seen.add(o)
                    nxt.append(o)
        frontier = nxt
    return 10 ** 6


def mega(tx, rng, at, turn_index, cause):
    return _mega_form(tx, rng, at, turn_index, cause, force=True)


def _mega_form(tx, rng, at, turn_index, cause, force=False):
    from ..society.population import census as people
    H = tx.rules.hordes
    d = at // DAY
    if tx.query_one("SELECT 1 FROM hordes WHERE kind='mega' AND status != 'gone'") is not None:
        return None
    params = _params(tx)
    diff = _ev(params.difficulty)
    hp = _values(tx)["horde_pressure"]
    days = tx.query_one("SELECT COUNT(*) FROM events WHERE type='WORLD_DAY'")[0]
    p = H.mega_daily_chance[diff] * hp / 5 * min(1.0, days / H.mega_ramp_days)
    if not force and not rng.chance(tx, "hordes", f"mega:{d}", p):
        return None
    ext = [(r[0], sum(a for a, _d in pool(tx, r[0]).values()))
           for r in tx.query("SELECT zone_id FROM zones WHERE kind='exterior' ORDER BY zone_id")]
    ext = [(z, a) for z, a in ext if a > 0]
    if not ext:
        return None
    entry = rng.weighted(tx, "hordes", f"mega_entry:{d}", ext)
    ep = pool(tx, entry)
    ea = sum(a for a, _d in ep.values())
    size = min(ea, rng.range_int(tx, "hordes", f"mega_size:{d}", *H.mega_size[diff]))
    SH = _types()[0]
    comp = {t: math.floor(size * a / ea) for t, (a, _d) in ep.items()}
    comp[SH] += size - sum(comp.values())
    comp = _clean(comp)
    best, target_zone = -1, None
    for r in tx.query("SELECT zone_id FROM zones WHERE kind != 'exterior' ORDER BY zone_id"):
        n = sum(people(tx, sid).total for sid in _settlements_in(tx, r[0]))
        if n > best:
            best, target_zone = n, r[0]
    if best <= 0:
        target_zone = _gateway(tx, entry)
    exits = []
    for r in tx.query("SELECT zone_id FROM zones WHERE kind='exterior' AND zone_id != ? ORDER BY zone_id", (entry,)):
        g = _gateway(tx, r[0])
        exits.append((-_hops(tx, g, target_zone), r[0]))
    exit_zone = sorted(exits)[0][1] if exits else entry
    eta = rng.range_int(tx, "hordes", f"mega_eta:{d}", *H.mega_eta_days)
    hid = form(tx, "mega", entry, comp, _hub(tx, target_zone), at, turn_index, cause,
               props={"exit_zone": exit_zone, "eta_at": at + eta * DAY, "signs": [], "speed_m_s": H.mega_speed_m_s,
                      "passage": {}}, first_leg_ms=eta * DAY)
    from . import factions
    formed = tx.query_one("SELECT event_id FROM events WHERE type='HORDE_FORMED' AND json_extract(payload,'$.horde_id')=?",
                          (hid,))[0]
    factions.sighted(tx, hid, at, turn_index, formed)
    return hid


def _mega_signs(tx, at, turn_index, cause):
    from . import rumours
    h = _row(tx, "SELECT horde_id FROM hordes WHERE kind='mega' AND status != 'gone'")
    if h is None:
        return
    h = _horde(tx, h["horde_id"])
    if h["place_id"] != _hub(tx, h["origin"]) or len(h["route"]) < 2:
        return
    props = dict(h["props"])
    left = math.ceil((props["eta_at"] - at) / DAY)
    gateway = _zone(tx, h["route"][1])
    target_zone = _zone(tx, h["target_place"])
    for sign, cond in (("birds", left <= 7), ("talk", left <= 5), ("roar", left <= 2)):
        if not cond or sign in props["signs"]:
            continue
        props["signs"] = props["signs"] + [sign]
        ev = _E(tx, EventType.HORDE_SIGN, at, turn_index, [_W("hordes", {"props": props}, WriteOp.UPDATE, {"horde_id": h["horde_id"]})],
                {"horde_id": h["horde_id"], "sign": sign}, cause=cause)
        if sign == "birds":
            for pl in _outdoor(tx, gateway):
                _noise(tx, pl, 70, "birds", "A whole flock goes over at once, all of it heading the same way: away.", at,
                       turn_index, ev.event_id)
        elif sign == "talk":
            zones = {gateway} | {_zone(tx, o) for o in _neighbour_hubs(tx, _hub(tx, gateway))}
            zones = {z for z in zones if _zone_kind(tx, z) != "exterior"}
            sts = sorted(sid for z in zones for sid in _settlements_in(tx, z))
            for sid in sts:
                holder = _speaker(tx, sid)
                if holder:
                    rumours.seed(tx, holder, _hub(tx, gateway), "horde_coming", at, turn_index, ev.event_id,
                                 subject_type="place")
        else:
            for z in dict.fromkeys([gateway, target_zone]):
                for pl in _outdoor(tx, z):
                    _noise(tx, pl, 95, "distant_roar", "A low roar, far off, that never stops.", at, turn_index, ev.event_id)


def _noise(tx, place_id, db, kind, text, at, turn_index, cause):
    p = tx.query_one("SELECT width_m, depth_m FROM places WHERE place_id=?", (place_id,))
    return _E(tx, EventType.NOISE, at, turn_index, [],
              {"source_db": db, "kind": kind, "text": text, "place_id": place_id, "x_m": p[0] / 2, "y_m": p[1] / 2},
              writer="action.propagate", cause=cause, place_id=place_id)


def _speaker(tx, settlement_id):
    s = _row(tx, "SELECT group_id FROM settlements WHERE settlement_id=?", (settlement_id,))
    if not s or not s["group_id"]:
        return None
    g = _row(tx, "SELECT leader_id FROM groups WHERE group_id=?", (s["group_id"],))
    if g and g["leader_id"] and tx.query_one("SELECT alive FROM bodies WHERE body_id=?", (g["leader_id"],))[0] == 1:
        return g["leader_id"]
    r = tx.query_one("SELECT m.actor_id FROM group_members m JOIN bodies b ON b.body_id = m.actor_id WHERE m.group_id=? "
                     "AND m.status IN ('member','probation') AND b.alive=1 ORDER BY m.actor_id LIMIT 1", (s["group_id"],))
    return r[0] if r else None


def _passage_start(tx, rng, h, zone, at, turn_index, cause):
    from ..physical import space
    from . import traces
    H = tx.rules.hordes
    hid = h["horde_id"]
    cnt = sum(h["composition"].values())
    dwell_h = math.ceil(cnt / H.mega_throughput_per_day * 24)
    props = dict(h["props"])
    old = {}
    for pl in _outdoor(tx, zone):
        amb = tx.query_one("SELECT ambient_db FROM places WHERE place_id=?", (pl,))[0]
        old[pl] = amb
    passage = dict(props.get("passage") or {})
    first_passage = not passage
    passage[zone] = old
    props.update({"until": at + dwell_h * HOUR, "passage": passage, "next_press": at + DAY})
    if first_passage:
        from . import factions
        factions.passage(tx, hid, True, at, turn_index, cause)
    _state(tx, hid, {"status": "milling", "props": props}, at, turn_index, cause)
    for pl, amb in old.items():
        space.change_place(tx, pl, {"ambient_db": max(amb, H.mega_ambient_db)}, "horde", at, cause, turn_index)
        traces.create(tx, pl, "tracks", "The ground is churned to mud by thousands of feet.", cause, at, turn_index)
    for sid in _settlements_in(tx, zone):
        press(tx, rng, hid, sid, at, turn_index, cause)


def _passage_end(tx, rng, h, at, turn_index, cause):
    from ..physical import space
    hid = h["horde_id"]
    props = dict(h["props"])
    zone = h["zone_id"]
    for pl, amb in (props.get("passage") or {}).get(zone, {}).items():
        space.change_place(tx, pl, {"ambient_db": amb}, "horde gone", at, cause, turn_index)
    route = list(h["route"])
    if not route:
        route = path(tx, h["place_id"], _hub(tx, props["exit_zone"])) or []
    props.pop("until", None)
    props.pop("next_press", None)
    ev = _state(tx, hid, {"status": "moving", "route": route, "props": props}, at, turn_index, cause)
    return ev.event_id


# ------------------------------------------------------------------------------------------ HRD-16 rise
def schedule_rise(tx, rng, zone_id, count, pathway, at, turn_index, cause):
    from ..kernel import clock
    pw = tx.canon.find("pathway", pathway)
    lo, hi = pw.rise_after_death_h
    m = rng.range_int(tx, "hordes", f"rise:{cause}:{zone_id}", int(lo * 60), int(hi * 60))
    return clock.schedule(tx, at + m * MIN, "POOL_RISE", zone_id, {"zone_id": zone_id, "count": count, "pathway": pathway},
                          cause)


def rise(tx, rng, row, fired, turn_index):
    first = _maxseq(tx)
    p = _j(row["payload"], {})
    pw = tx.canon.find("pathway", p["pathway"])
    types = list(pw.rise_as)
    c = int(p["count"])
    shares = [c - c // 4, c // 4] if len(types) > 1 else [c]
    for t, n in zip(types, shares):
        if n > 0:
            change(tx, p["zone_id"], t, n, 0, "risen", row["due_at"], turn_index, fired.event_id)
    return _since(tx, first)


# ------------------------------------------------------------------------------------------ HRD-18 fold
def fold(tx, body_id, at, turn_index, cause):
    from ..kernel import clock
    from ..physical import bodies as B
    from ..physical import space
    b = _row(tx, "SELECT * FROM bodies WHERE body_id=?", (body_id,))
    i = _row(tx, "SELECT * FROM infected_state WHERE body_id=?", (body_id,))
    pos = _row(tx, "SELECT * FROM positions WHERE body_id=?", (body_id,))
    if not (b and i and pos) or b["kind"] != "infected" or not b["alive"] or not b["core_intact"]:
        return []
    if b["origin"] != "materialize" or i.get("folded_at") is not None:
        return []
    if tx.query_one("SELECT 1 FROM wounds WHERE body_id=?", (body_id,)):
        return []
    if B.grips_on(tx, body_id) or tx.query_one("SELECT 1 FROM grips WHERE holder_id=?", (body_id,)):
        return []
    h = _row(tx, "SELECT * FROM hordes WHERE horde_id=?", (i["horde_id"],)) if i.get("horde_id") else None
    live = h if (h and h["status"] != "gone") else None
    tgt = i.get("target_id")
    if tgt and not (live and (tgt == live["place_id"] or tgt in _j(live["route"], []))):
        return []  # somewhere of its own to be: it walks on as a body
    if tx.query_one("SELECT 1 FROM positions p JOIN bodies x ON x.body_id=p.body_id WHERE p.place_id=? AND x.alive=1 "
                    "AND x.kind != 'infected'", (pos["place_id"],)):
        return []
    if pos["place_id"] in _area(tx, turn_index):
        return []
    first = _maxseq(tx)
    t = i["type_id"]
    dormant = "dormant" in _j(i["states"], [])
    if live:
        h = live
        comp = dict(_j(h["composition"], {}))
        comp[t] = comp.get(t, 0) + 1
        comp = {k: comp[k] for k in _types() if comp.get(k, 0) > 0}
        _E(tx, EventType.HORDE_REJOINED, at, turn_index,
           [_W("hordes", {"composition": comp}, WriteOp.UPDATE, {"horde_id": h["horde_id"]})],
           {"horde_id": h["horde_id"], "body_id": body_id, "type_id": t, "composition": comp}, cause=cause)
    else:
        change(tx, _zone(tx, pos["place_id"]), t, 0 if dormant else 1, 1 if dormant else 0, "folded", at, turn_index, cause)
    before = {"folded_at": i.get("folded_at"), "target_id": i.get("target_id")}
    st = tx.commit_event(Event(type=EventType.INFECTED_STATE, writer="world.infected", at=at, turn_index=turn_index,
                               cause_event_id=cause, actor_id=body_id,
                               payload={"body_id": body_id, "changes": {"folded_at": at, "target_id": None}, "before": before},
                               writes=[_W("infected_state", {"folded_at": at, "target_id": None}, WriteOp.UPDATE,
                                          {"body_id": body_id})]))
    for q in tx.query("SELECT queue_id FROM event_queue WHERE type='INFECTED_STEP' AND subject_id=? AND status='pending' "
                      "ORDER BY queue_id", (body_id,)):
        clock.cancel(tx, q[0], "folded", at, st.event_id, turn_index)
    space.remove_body(tx, body_id, at, st.event_id, turn_index)
    return _since(tx, first)
