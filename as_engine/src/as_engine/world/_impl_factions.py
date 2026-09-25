"""Implementation of world/factions.py."""
from __future__ import annotations

import json

from ..contracts.events import Event, EventType, WriteOp, WriteRecord

DAY = 86_400_000
HOUR = 3_600_000


def _E(tx, type_, writer, at, turn_index, payload, *, writes=(), cause=None, actor_id=None, place_id=None, target_ids=None):
    return tx.commit_event(Event(type=type_, writer=writer, at=at, turn_index=turn_index, payload=payload,
                                 writes=list(writes), cause_event_id=cause, actor_id=actor_id, place_id=place_id,
                                 target_ids=target_ids or []))


def _rec(store, content_ref):
    try:
        return store.canon.get(content_ref) if content_ref else None
    except KeyError:
        return None


def _groups(store, what):
    """(group_id, faction record) for faction groups whose behaviour has ``what``, by group_id."""
    out = []
    for r in store.query("SELECT group_id, content_ref FROM groups WHERE kind='faction' ORDER BY group_id"):
        rec = _rec(store, r[1])
        if rec is None:
            continue
        b = rec.behaviour
        if (what == "route_watch" and b.route_watch) or (what != "route_watch" and getattr(b, what) is not None):
            out.append((r[0], rec))
    return out


def enclave(store, group_id):
    r = store.query_one("SELECT content_ref FROM groups WHERE group_id=?", (group_id,))
    rec = _rec(store, r[0]) if r else None
    if rec is None or rec.behaviour.enclave is None:
        return None
    s = store.query_one("SELECT settlement_id FROM settlements WHERE group_id=? ORDER BY settlement_id LIMIT 1", (group_id,))
    return s[0] if s else None


def lockdown(tx, settlement_id, on, reason, at, turn_index, cause):
    from ..society import settlement as stl
    return stl.set_lockdown(tx, settlement_id, on, reason, at, turn_index, cause)


def next_meeting(at, council):
    d = max(1, at // DAY)
    while True:
        if d % council.every_days == 0:
            t = d * DAY + council.hour * HOUR
            if t > at:
                return t
        d += 1


def _seat_holders(store, group_id, rec, seats):
    """[(seat, actor_id)] of living holders, in the record's seat order; the first leader's seat is
    the group's leader."""
    leader = store.query_one("SELECT leader_id FROM groups WHERE group_id=?", (group_id,))[0]
    first = rec.leaders[0].seat if rec.leaders else None
    out = []
    for ld in rec.leaders:
        if not ld.seat or ld.seat not in seats:
            continue
        if ld.seat == first:
            who = [leader] if leader else []
        else:
            who = [r[0] for r in store.query("SELECT actor_id FROM group_members WHERE group_id=? AND role=? ORDER BY actor_id",
                                             (group_id, ld.seat))]
        for a in who:
            b = store.query_one("SELECT alive FROM bodies WHERE body_id=?", (a,))
            if b and b[0]:
                out.append((ld.seat, a))
    return out


def ensure_timers(tx, at, turn_index):
    from ..kernel import clock
    out = []
    for gid, rec in _groups(tx, "council"):
        if enclave(tx, gid) is None:
            continue
        if clock.pending_for(tx, "COUNCIL", gid):
            continue
        out.append(clock.schedule(tx, next_meeting(at, rec.behaviour.council), "COUNCIL", gid,
                                  {"group_id": gid, "step": "convene"}, None))
    return out


def _area(tx, turn_index):
    from ._impl_p10 import _area as a
    return a(tx, turn_index)


def _since(tx, first):
    from ._impl_p10 import _since as s
    return s(tx, first)


def _maxseq(tx):
    from ._impl_p10 import _maxseq as m
    return m(tx)


def step(tx, rng, row, fired, turn_index):
    from ..kernel import clock
    from ..physical import space
    first = _maxseq(tx)
    p = json.loads(row["payload"]) if isinstance(row["payload"], str) else dict(row["payload"])
    gid = p["group_id"]
    at = row["due_at"]
    r = tx.query_one("SELECT content_ref FROM groups WHERE group_id=?", (gid,))
    rec = _rec(tx, r[0]) if r else None
    s = enclave(tx, gid)
    if rec is None or rec.behaviour.council is None or s is None:
        return []
    council = rec.behaviour.council
    site = tx.query_one("SELECT place_id FROM settlements WHERE settlement_id=?", (s,))[0]
    if p.get("step") == "adjourn":
        ev = _E(tx, EventType.COUNCIL_ADJOURNED, "world.factions", at, turn_index,
                {"group_id": gid, "meeting": p.get("meeting")}, cause=fired.event_id, place_id=site)
        clock.schedule(tx, next_meeting(at, council), "COUNCIL", gid, {"group_id": gid, "step": "convene"}, ev.event_id)
        return _since(tx, first)
    holders = _seat_holders(tx, gid, rec, set(council.seats))
    if not holders:
        clock.schedule(tx, next_meeting(at, council), "COUNCIL", gid, {"group_id": gid, "step": "convene"}, fired.event_id)
        return _since(tx, first)
    area = _area(tx, turn_index)
    busy = set()
    for q in tx.query("SELECT participants FROM operations WHERE status='active'"):
        busy |= set(json.loads(q[0] or "[]"))
    anc = tx.query_one("SELECT anchor_id, x_m, y_m FROM anchors WHERE place_id=? AND name='the council room'", (site,)) or \
        tx.query_one("SELECT anchor_id, x_m, y_m FROM anchors WHERE place_id=? ORDER BY anchor_id LIMIT 1", (site,))
    present, absent = [], []
    for _seat, a in holders:
        pos = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (a,))
        here = pos[0] if pos else None
        if here == site and a not in busy:
            present.append(a)
        elif here is not None and here not in area and a not in busy:
            present.append(a)
        else:
            absent.append(a)
    for a in present:
        pos = tx.query_one("SELECT place_id, anchor_id FROM positions WHERE body_id=?", (a,))
        if (pos[0], pos[1]) != (site, anc[0] if anc else None) and anc:
            tx.commit_event(space.move_event(tx, a, site, anc[0], anc[1], anc[2], at, fired.event_id, turn_index))
    meet = _E(tx, EventType.COUNCIL_MEETING, "world.factions", at, turn_index,
              {"group_id": gid, "settlement_id": s, "present": present, "absent": absent}, cause=fired.event_id,
              place_id=site)
    if rec.behaviour.decon is not None:
        _decon_orders(tx, rng, gid, rec, s, at, turn_index, meet)
    clock.schedule(tx, at + round(council.hours * HOUR), "COUNCIL", gid,
                   {"group_id": gid, "step": "adjourn", "meeting": meet.event_id}, meet.event_id)
    return _since(tx, first)


def in_session(store, group_id, at):
    r = store.query_one("SELECT event_id FROM events WHERE type='COUNCIL_MEETING' AND json_extract(payload,'$.group_id')=? "
                        "AND at <= ? ORDER BY seq DESC LIMIT 1", (group_id, at))
    if r is None:
        return None
    done = store.query_one("SELECT 1 FROM events WHERE type='COUNCIL_ADJOURNED' AND json_extract(payload,'$.meeting')=? AND at <= ?",
                           (r[0], at))
    return None if done else r[0]


def _gateway_hub(tx, horde_id):
    h = tx.query_one("SELECT route FROM hordes WHERE horde_id=?", (horde_id,))
    route = json.loads(h[0] or "[]")
    return route[1] if len(route) > 1 else (route[0] if route else None)


def sighted(tx, horde_id, at, turn_index, cause):
    from ._impl_rumours import seed
    first = _maxseq(tx)
    h = tx.query_one("SELECT props FROM hordes WHERE horde_id=?", (horde_id,))
    props = json.loads(h[0] or "{}")
    gate = _gateway_hub(tx, horde_id)
    for gid, rec in _groups(tx, "route_watch"):
        if enclave(tx, gid) is None:
            continue
        ev = _E(tx, EventType.ROUTE_WATCH_REPORT, "world.factions", at, turn_index,
                {"group_id": gid, "horde_id": horde_id, "gateway_hub": gate, "eta_at": props.get("eta_at")}, cause=cause)
        for _seat, a in _seat_holders(tx, gid, rec, {ld.seat for ld in rec.leaders if ld.seat}):
            seed(tx, a, gate, "horde_coming", at, turn_index, ev.event_id, subject_type="place")
    return _since(tx, first)


def passage(tx, horde_id, on, at, turn_index, cause):
    first = _maxseq(tx)
    for gid, _rec in _groups(tx, "route_watch"):
        s = enclave(tx, gid)
        if s is not None:
            lockdown(tx, s, on, "mega horde" if on else "horde gone", at, turn_index, cause)
    return _since(tx, first)


def _decon_orders(tx, rng, gid, rec, s, at, turn_index, meet):
    from . import _impl_p10 as P
    prev = tx.query_one("SELECT MAX(seq) FROM events WHERE type='COUNCIL_MEETING' AND json_extract(payload,'$.group_id')=? "
                        "AND seq < ?", (gid, meet.seq))[0] or 0
    members = {r[0] for r in tx.query("SELECT actor_id FROM group_members WHERE group_id=?", (gid,))}
    done = set()
    for d in tx.query("SELECT seq, payload FROM events WHERE type='DEATH' AND seq > ? AND seq < ? ORDER BY seq", (prev, meet.seq)):
        body = json.loads(d[1]).get("body_id")
        if body not in members:
            continue
        killer = None
        for hrm in tx.query("SELECT actor_id FROM events WHERE type='HARM' AND json_extract(payload,'$.body_id')=? AND seq <= ? "
                            "ORDER BY seq DESC", (body, d[0])):
            k = hrm[0]
            if not k or k in members:
                continue
            kb = tx.query_one("SELECT kind, alive FROM bodies WHERE body_id=?", (k,))
            if kb and kb[0] == "human":
                killer = k
                break
        if killer is None or killer in done:
            continue
        if not tx.query_one("SELECT alive FROM bodies WHERE body_id=?", (killer,))[0]:
            continue
        if tx.query_one("SELECT 1 FROM operations WHERE kind='decon' AND status='active' AND group_id=? AND target_id=?",
                        (gid, killer)):
            continue
        crew = team(tx, rng, gid, at, turn_index, meet.event_id)
        if not crew:
            continue
        site = tx.query_one("SELECT place_id FROM settlements WHERE settlement_id=?", (s,))[0]
        from . import hordes
        kp = P._place_of(tx, killer)
        P.launch(tx, gid, "decon", crew, site, hordes.target(tx, kp) if kp else site, at, turn_index, meet.event_id,
                 target_id=killer)
        done.add(killer)


def team(tx, rng, group_id, at, turn_index, cause):
    from . import _impl_p10 as P
    r = tx.query_one("SELECT content_ref FROM groups WHERE group_id=?", (group_id,))
    rec = _rec(tx, r[0])
    D = rec.behaviour.decon
    s = enclave(tx, group_id)
    stl = tx.query_one("SELECT place_id FROM settlements WHERE settlement_id=?", (s,))[0]
    zone = tx.query_one("SELECT zone_id FROM places WHERE place_id=?", (stl,))[0]
    out = []
    for k in range(D.team):
        sex = "female" if rng.chance(tx, "factions", f"decon_sex:{cause}:{k}", D.women_share) else "male"
        left = {x: (tx.query_one("SELECT COALESCE(SUM(count),0) FROM cohorts WHERE settlement_id=? AND age_band='adult' AND sex=?",
                                 (s, x))[0]) for x in ("female", "male")}
        if left[sex] <= 0:
            sex = "male" if sex == "female" else "female"
        if left[sex] <= 0:
            break
        d = operator_dossier(rng, tx, group_id, k, sex, cause)
        bid = P.materialise(tx, rng, settlement_id=s, zone_id=zone, band="adult", sex=sex, dossier=d, place_id=stl, at=at,
                            turn_index=turn_index, cause_event_id=cause)
        out.append(bid)
    if out:
        _E(tx, EventType.MATERIALIZE, "society.group", at, turn_index, {"group_id": group_id, "members": len(out)},
           writes=[WriteRecord(op=WriteOp.INSERT, table="group_members", values={
               "group_id": group_id, "actor_id": b, "role": "operator", "standing": 1, "since": at, "status": "member"})
               for b in out], cause=cause)
    return out


def operator_dossier(rng, tx, group_id, k, sex, cause):
    from ..world.worldgen.people import PersonSeed, skeleton_dossier
    r = tx.query_one("SELECT content_ref, name FROM groups WHERE group_id=?", (group_id,))
    rec = _rec(tx, r[0])
    D = rec.behaviour.decon
    s = enclave(tx, group_id)
    sname = tx.query_one("SELECT name FROM settlements WHERE settlement_id=?", (s,))[0]
    nrec = tx.canon.get(tx.canon.refs("names")[0])
    ns = f"names:{s}"
    given = rng.choice(tx, ns, f"decon_given:{cause}:{k}", list(nrec.given_female if sex == "female" else nrec.given_male))
    family = rng.choice(tx, ns, f"decon_family:{cause}:{k}", list(nrec.family))
    age = rng.range_int(tx, "factions", f"decon_age:{cause}:{k}", 22, 45)
    special = {L: 4 + rng.range_int(tx, "factions", f"decon_special:{cause}:{k}:{L}", 0, 3) for L in "SPECIAL"}
    from .worldgen._impl_wg import cohort_kind
    wp = json.loads(tx.query_one("SELECT params_json FROM world_params WHERE id=1")[0])
    dsf = wp["days_since_fall"]
    seed = PersonSeed(name=f"{given} {family}", age=age, sex=sex, cohort=cohort_kind(age, dsf), occupation=D.occupation,
                      skills={"firearms": 2, "melee": 1, "athletics": 1}, special=special,
                      variant=rng.range_int(tx, "factions", f"decon_variant:{cause}:{k}", 0, 999),
                      settlement_name=sname, group_name=r[1], climate_heat=int((wp.get("a") or {}).get("climate_heat", 5)))
    d = skeleton_dossier(seed)
    d["id"] = d["id"] + f"_{k}_{(cause or 'x')[-6:]}"
    d["appearance"]["clothing_usual"] = D.appearance
    d["appearance"]["distinguishing_marks"] = ["a small smile stitched at the left chest"]
    d["social"]["memberships"] = [{"faction": r[0], "role": "operator", "standing": 1, "since": "born inside"}]
    return d
