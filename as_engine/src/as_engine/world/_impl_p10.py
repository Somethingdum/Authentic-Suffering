"""Implementation for P10: actors, materialisation, traces, infected, world motion, decay."""
from __future__ import annotations

import json
import math

from ..contracts.events import Event, EventType, WriteOp, WriteRecord

DAY = 86_400_000
H = 3_600_000


def W(table, values, op=WriteOp.INSERT, key=None):
    return WriteRecord(op=op, table=table, key=key or {}, values=values)


def E(tx, type_, writer, at, turn_index, writes, payload, *, cause=None, actor_id=None, place_id=None, target_ids=None,
      origin="sim"):
    return tx.commit_event(Event(type=type_, writer=writer, at=at, turn_index=turn_index, origin=origin, actor_id=actor_id,
                                 place_id=place_id, cause_event_id=cause, writes=writes, payload=payload,
                                 target_ids=target_ids or []))


def _row(s, sql, params=()):
    r = s.query_one(sql, params)
    return None if r is None else dict(r)


def _j(v, default=None):
    if v is None:
        return default
    return json.loads(v) if isinstance(v, str) else v


# ------------------------------------------------------------------------------------------ mind.actor.create
def actor_create(tx, body_id, dossier, source, at, turn_index, *, content_ref=None, mind_kind="model",
                 cause_event_id=None, goal="", event_origin="sim"):
    import hashlib
    from ..contracts.dossier import ActorDossier, PCDossier
    from ..kernel.jsoncanon import canonical_json
    from ..mind.actor import resolve_max
    if tx.query_one("SELECT 1 FROM actors WHERE actor_id=?", (body_id,)) is not None:
        raise ValueError(f"{body_id} already has an actors row")
    model = PCDossier if "card" in dossier else ActorDossier
    try:
        rec = model.model_validate(dossier)
    except Exception as e:  # noqa: BLE001
        raise ValueError(str(e)) from None
    bj = canonical_json(rec.model_dump(mode="json", by_alias=True))
    did = tx.mint("dos")
    sp = rec.capability.special
    rmax = resolve_max(sp.E, sp.C, rec.capability.resolve_trait_mod, tx.rules.resolve)
    ws = [W("dossiers", {"dossier_id": did, "actor_id": body_id, "source": source, "content_ref": content_ref,
                         "baseline_json": bj, "content_hash": hashlib.sha256(bj.encode("utf-8")).hexdigest()}),
          W("actors", {"actor_id": body_id, "dossier_id": did, "controller": mind_kind, "display_name": rec.identity.name,
                       "resolve_cur": rmax, "resolve_max": rmax, "stress": 0, "goal_text": goal, "lod_hint": "cold",
                       "accepted_authority": [], "quarantine": 0})]
    return E(tx, EventType.MATERIALIZE, "mind.actor", at, turn_index, ws, {"actor_id": body_id, "source": source},
             cause=cause_event_id, actor_id=body_id, target_ids=[body_id], origin=event_origin)


# ------------------------------------------------------------------------------------------ population
def take_from_cohort(tx, settlement_id, zone_id, band, sex, at, turn_index, cause_event_id, *, archetype=None):
    from ..society.population import adjust_cohort
    if settlement_id is not None:
        r = tx.query_one("SELECT cohort_id FROM cohorts WHERE settlement_id=? AND age_band=? AND sex=? AND count>0 "
                         "ORDER BY cohort_id LIMIT 1", (settlement_id, band, sex))
    else:
        r = tx.query_one("SELECT cohort_id FROM cohorts WHERE settlement_id IS NULL AND zone_id=? AND archetype IS ? "
                         "AND age_band=? AND sex=? AND count>0 ORDER BY cohort_id LIMIT 1",
                         (zone_id, archetype, band, sex))
    if r is None:
        return None
    return adjust_cohort(tx, r[0], -1, "materialised", at, turn_index, cause_event_id)


def materialise(tx, rng, *, settlement_id, zone_id, band, sex, dossier, place_id, at, turn_index, cause_event_id,
                archetype=None, event_origin="sim"):
    from ..physical import bodies, space
    ev = take_from_cohort(tx, settlement_id, zone_id, band, sex, at, turn_index, cause_event_id, archetype=archetype)
    if ev is None:
        raise ValueError(f"nobody left in the {band} {sex} cohort to name")
    idn, ap, cap = dossier["identity"], dossier["appearance"], dossier["capability"]
    from ..contracts.dossier import Looks
    looks = Looks.model_validate(ap["looks"]) if ap.get("looks") else None     # LOOK-10 (F1a-2)
    bid = bodies.create(tx, kind="human", sex=sex, age_years=idn["age"], height_cm=ap["height_cm"], mass_kg=ap["mass_kg"],
                        special=dict(cap["special"]), at=at, turn_index=turn_index,
                        origin="worldgen" if event_origin == "worldgen" else "materialize", cause_event_id=ev.event_id,
                        looks=looks)
    _place_at_first_anchor(tx, bid, place_id, at, ev.event_id, turn_index)
    if looks is not None and looks.outfit:
        # what they wore was already in the world, only unnamed: worldgen items, events of this origin
        from ..physical import objects
        for piece in looks.outfit:
            props = {k: v for k, v in (("colour", piece.colour), ("state", piece.state), ("insignia", piece.insignia)) if v is not None}
            objects.create(tx, piece.item, 1, objects.Holder("body", bid, "worn"), "worldgen", props, at, ev.event_id, turn_index,
                           event_origin=event_origin)
    actor_create(tx, bid, dossier, "generated", at, turn_index, mind_kind="model", cause_event_id=ev.event_id,
                 event_origin=event_origin)
    E(tx, EventType.PERCEIVE, "mind.perception", at, turn_index,
      [W("known_places", {"holder_id": bid, "place_id": place_id, "first_seen": at, "last_seen": at, "visited": 1})],
      {"holder_id": bid, "seed": True}, actor_id=bid)
    return bid


def _place_at_first_anchor(tx, body_id, place_id, at, cause, turn_index, replaces=None):
    from ..physical import space
    a = tx.query_one("SELECT anchor_id, x_m, y_m FROM anchors WHERE place_id=? ORDER BY anchor_id LIMIT 1", (place_id,))
    if a is not None:
        return space.place_body(tx, body_id, place_id, a[0], a[1], a[2], at, cause, turn_index, replaces=replaces)
    p = tx.query_one("SELECT width_m, depth_m FROM places WHERE place_id=?", (place_id,))
    return space.place_body(tx, body_id, place_id, None, p[0] / 2, p[1] / 2, at, cause, turn_index, replaces=replaces)


# ------------------------------------------------------------------------------------------ traces
def trace_create(tx, place_id, kind, text, source_event_id, at, turn_index, *, locked=False, decay_days=None):
    from ..kernel import clock
    if tx.query_one("SELECT 1 FROM places WHERE place_id=?", (place_id,)) is None:
        raise ValueError(f"unknown place {place_id}")
    Wr = tx.rules.world
    if decay_days is not None:
        days = decay_days
    else:
        days = Wr.trace_decay_days.get(kind, 14)
        if not exposed(tx, place_id):
            days *= Wr.sheltered_trace_mult
    tid = tx.mint("trc")
    decays = None if locked else at + int(days * DAY)
    ev = E(tx, EventType.TRACE_CREATED, "world.traces", at, turn_index,
           [W("traces", {"trace_id": tid, "place_id": place_id, "kind": kind, "text": text,
                         "source_event": source_event_id or "", "created_at": at, "decays_at": decays, "locked": int(locked)})],
           {"trace_id": tid, "place_id": place_id, "kind": kind, "text": text, "locked": bool(locked)},
           cause=source_event_id, place_id=place_id)
    if not locked:
        clock.schedule(tx, decays, "TRACE_DECAY", tid, {"trace_id": tid}, ev.event_id)
    return tid


def trace_decay(tx, rng, row, fired, turn_index):
    p = _j(row["payload"], {})
    t = _row(tx, "SELECT * FROM traces WHERE trace_id=?", (p.get("trace_id"),))
    if t is None or t["locked"]:
        return []
    return [E(tx, EventType.TRACE_DECAYED, "world.traces", row["due_at"], turn_index,
              [W("traces", {}, WriteOp.DELETE, {"trace_id": t["trace_id"]})],
              {"trace_id": t["trace_id"], "place_id": t["place_id"], "kind": t["kind"], "reason": "time"},
              cause=fired.event_id, place_id=t["place_id"])]


def trace_washout(tx, at, turn_index, cause_event_id):
    from ..kernel import clock
    if not wet(tx):
        return []
    first = _maxseq(tx)
    Wr = tx.rules.world
    for t in [dict(r) for r in tx.query("SELECT * FROM traces WHERE locked=0 ORDER BY trace_id")]:
        if t["kind"] not in Wr.washes_out or not exposed(tx, t["place_id"]):
            continue
        ev = E(tx, EventType.TRACE_DECAYED, "world.traces", at, turn_index,
               [W("traces", {}, WriteOp.DELETE, {"trace_id": t["trace_id"]})],
               {"trace_id": t["trace_id"], "place_id": t["place_id"], "kind": t["kind"], "reason": "weather"},
               cause=cause_event_id, place_id=t["place_id"])
        for q in clock.pending_for(tx, "TRACE_DECAY", t["trace_id"]):
            clock.cancel(tx, q["queue_id"], "washed out", at, ev.event_id, turn_index)
    return _since(tx, first)


def traces_in(store, place_id):
    return [dict(r) for r in store.query("SELECT * FROM traces WHERE place_id=? ORDER BY created_at, trace_id", (place_id,))]


# ------------------------------------------------------------------------------------------ infected
SHAMBLER = "ZOMBIE_ARCHETYPE_SHAMBLER01"
CRAWLER = "ZOMBIE_ARCHETYPE_CRAWLER01"
RUNNER = "ZOMBIE_VARIANT_ID_RUNNER01"


def _inf(s, b):
    return _row(s, "SELECT * FROM infected_state WHERE body_id=?", (b,))


def _body(s, b):
    return _row(s, "SELECT * FROM bodies WHERE body_id=?", (b,))


def _canon(s):
    return s.canon


def _states(r):
    return list(_j(r["states"], []))


def active(store, body_id):
    b = _body(store, body_id)
    r = _inf(store, body_id)
    return bool(b and r and b["kind"] == "infected" and b["alive"] and b["core_intact"] and b["awareness"] != "unconscious"
                and r.get("folded_at") is None and "dormant" not in _states(r))


def threshold(store, body_id):
    r = _inf(store, body_id)
    t = _canon(store).find("infected", r["type_id"])
    v = t.senses.hearing_threshold_db
    for st in _states(r):
        v += _canon(store).find("infected_state", st).hearing_threshold_delta_db
    return float(v)


def speed(store, body_id):
    r = _inf(store, body_id)
    t = _canon(store).find("infected", r["type_id"])
    v = t.speed_m_s
    for st in _states(r):
        v *= _canon(store).find("infected_state", st).speed_mult
    return 0.0 if "dormant" in _states(r) else float(v)


def _excluded(store, target_id, at, *, sight):
    for inf in store.query("SELECT pathway, stage, exposed_at FROM infections WHERE body_id=?", (target_id,)):
        if inf[0] == "lurker_deep":
            first = _canon(store).find("pathway", "lurker_deep").stages[0].name
            if inf[1] != first:
                return True
        pass
    return False


def sees(store, body_id, target_id, at):
    from ..physical.space import point_distance
    t = _body(store, target_id)
    if t is None or not t["alive"] or t["awareness"] == "unconscious" or t["kind"] == "infected":
        return False
    pa = store.query_one("SELECT place_id FROM positions WHERE body_id=?", (body_id,))
    pb = store.query_one("SELECT place_id FROM positions WHERE body_id=?", (target_id,))
    if pa is None or pb is None or pa[0] != pb[0]:
        return False
    if _excluded(store, target_id, at, sight=True):
        return False
    r = _inf(store, body_id)
    ty = _canon(store).find("infected", r["type_id"])
    R = store.rules.infected
    if t["gore"] >= R.gore_mask_min and ty.senses.vision_mode != "thermal":
        w = R.mask_window_s * 1000
        gave = False
        for typ, pl in store.query("SELECT type, payload FROM events WHERE at > ? AND at <= ? AND actor_id=? "
                                   "AND type IN ('NOISE','SPEECH','ACTION_START')", (at - w, at, target_id)):
            pl = json.loads(pl) if isinstance(pl, str) else pl
            if typ in ("NOISE", "SPEECH") and (pl.get("source_db") or 0) >= R.mask_break_db:
                gave = True
            if typ == "ACTION_START" and pl.get("target_id"):
                k = store.query_one("SELECT kind FROM bodies WHERE body_id=?", (pl["target_id"],))
                if k is not None and k[0] == "infected":
                    gave = True
        if not gave:
            return False
    rng_m = ty.senses.vision_range_m
    for inf in store.query("SELECT pathway, exposed_at FROM infections WHERE body_id=?", (target_id,)):
        if inf[0] == "wet" and at - inf[1] >= store.rules.infected.wet_ignore_after_h * H:
            rng_m = rng_m / 2
    if point_distance(store, body_id, target_id) > rng_m:
        return False
    mode = ty.senses.vision_mode
    if mode == "motion_contrast":
        from .infected import STILL_VERBS
        w = store.rules.infected.motion_window_s * 1000
        for typ, pl in store.query("SELECT type, payload FROM events INDEXED BY ev_at WHERE at > ? AND at <= ? "
                                   "AND actor_id=? AND type IN ('MOVE','ACTION_START')", (at - w, at, target_id)):
            if typ == "MOVE":
                return True
            pl = json.loads(pl) if isinstance(pl, str) else pl
            if pl.get("verb") not in STILL_VERBS:
                return True
        return False
    if mode in ("shape", "full"):
        return True
    pl = _row(store, "SELECT * FROM places WHERE place_id=?", (pa[0],))
    return pl["light_level"] <= 1 or bool(pl["indoor"])


def _grips_on(tx, target):
    from ..physical.bodies import grips_on
    return grips_on(tx, target)


def attract(tx, body_id, target_id, at, cause_event_id, turn_index, *, reason):
    from ..kernel import clock
    b = _body(tx, body_id)
    r = _inf(tx, body_id)
    if b is None or r is None or b["kind"] != "infected" or not b["alive"] or not b["core_intact"] or b["awareness"] == "unconscious":
        return None
    cur_t = r["target_id"]
    if cur_t and cur_t != target_id:
        ct = _body(tx, cur_t)
        R_ = tx.rules.infected
        if ct is not None and ((ct["alive"] and body_id in _grips_on(tx, cur_t))
                               or (not ct["alive"] and ct["dead_at"] is not None and at - ct["dead_at"] < R_.feed_on_dead_min * 60_000)):
            return None
    tb = _body(tx, target_id)
    if tb is not None:
        if tb["kind"] == "infected" or _excluded(tx, target_id, at, sight=False):
            return None
        kind = "body"
    else:
        kind = "place"
    pa = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (body_id,))
    if kind == "place" and r["target_id"]:
        cur = _body(tx, r["target_id"])
        if cur and cur["alive"] and cur["kind"] != "infected":
            pc = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (r["target_id"],))
            if pa and pc and pa[0] == pc[0]:
                return None
    if target_id == r["target_id"] and clock.pending_for(tx, "INFECTED_STEP", body_id):
        return None
    if kind == "place" and pa and pa[0] == target_id:
        for q in tx.query("SELECT b.body_id FROM bodies b JOIN positions p ON p.body_id=b.body_id WHERE p.place_id=? "
                          "AND b.alive=1 AND b.kind != 'infected' ORDER BY b.body_id", (target_id,)):
            if sees(tx, body_id, q[0], at):
                return attract(tx, body_id, q[0], at, cause_event_id, turn_index, reason="sight")
        return None
    states = _states(r)
    woke = "dormant" in states
    new_states = [s for s in states if s != "dormant"]
    idle = not clock.pending_for(tx, "INFECTED_STEP", body_id)
    vals = {"target_id": target_id, "states": new_states}
    if idle:
        vals["charged_at"] = at      # INF-03: standing still cost nothing
    ev = E(tx, EventType.INFECTED_DRIFT, "world.infected", at, turn_index,
           [W("infected_state", vals, WriteOp.UPDATE, {"body_id": body_id})],
           {"body_id": body_id, "target_id": target_id, "target_kind": kind, "reason": reason, "woke": woke},
           cause=cause_event_id, actor_id=body_id)
    if idle:
        clock.schedule(tx, at + round(tx.rules.infected.step_min_s * 1000), "INFECTED_STEP", body_id,
                       {"body_id": body_id, "leg": None}, ev.event_id)
    return ev


def _energy_states(R, energy, states):
    s = [x for x in states if x not in ("starved", "overfed")]
    if energy < R.starved_below:
        s.append("starved")
    elif energy > R.overfed_above:
        s.append("overfed")
    return s


def _state_ev(tx, body_id, changes, before, at, turn_index, cause):
    return E(tx, EventType.INFECTED_STATE, "world.infected", at, turn_index,
             [W("infected_state", changes, WriteOp.UPDATE, {"body_id": body_id})],
             {"body_id": body_id, "changes": changes, "before": before}, cause=cause, actor_id=body_id)


def _press_portal(tx, body, portal_id, pos, at, turn_index, cause):
    # INF-13: a crowd leaning on a closed portal breaks it, a minute of pressure at a time.
    from ..physical import space
    R = tx.rules.infected
    pr = _row(tx, "SELECT * FROM portals WHERE portal_id=?", (portal_id,))
    if pr is None or pr["is_open"]:
        return []
    px, py = space.portal_point(tx, portal_id, pos["place_id"])
    n = 0
    for r in tx.query("SELECT q.body_id, q.x_m, q.y_m FROM positions q JOIN bodies b ON b.body_id = q.body_id "
                      "WHERE q.place_id=? AND b.kind='infected' AND b.alive=1", (pos["place_id"],)):
        if ((r[1] - px) ** 2 + (r[2] - py) ** 2) ** 0.5 <= 2.0:
            n += 1
    if n < R.push_min:
        return []
    last = tx.query_one("SELECT MAX(at) FROM events WHERE type='PORTAL_CHANGE' AND json_extract(payload,'$.portal_id')=? "
                        "AND json_extract(payload,'$.changes.strain_min') IS NOT NULL", (portal_id,))[0]
    if last is not None and at - last < 60_000:
        return []
    out = []
    strain = pr["strain_min"] + 1
    holds = R.portal_holds_min.get(pr["kind"], 20) + R.barricade_min * pr["barricade"] + R.lock_min * pr["lock_quality"]
    ch = {"strain_min": strain}
    lvl = min(3, strain * 3 // max(1, holds))
    if lvl > pr["damage"]:
        ch["damage"] = lvl
    out.append(tx.commit_event(space.portal_change_event(tx, portal_id, ch, at, None, cause, turn_index)))
    sealed = any(json.loads((_row(tx, "SELECT props FROM places WHERE place_id=?", (x,)) or {"props": "{}"})["props"] or "{}")
                 .get("enclave") for x in (pr["place_a"], pr["place_b"]))
    if strain >= holds and not sealed:
        ev2 = space.portal_change_event(tx, portal_id, {"barricade": 0, "is_locked": 0, "is_open": 1, "damage": 3}, at, None,
                                        cause, turn_index)
        out.append(tx.commit_event(ev2))
        out.append(E(tx, EventType.NOISE, "action.propagate", at, turn_index, [],
                     {"source_db": 95, "kind": "breaking", "text": "Wood splits and something gives way.",
                      "place_id": pos["place_id"], "x_m": px, "y_m": py}, cause=cause, actor_id=body, place_id=pos["place_id"]))
    return out


def _parkour_leg(tx, rng, b, pr, leg, at, turn_index, cause):
    """Across a climb, a gap, an edge or a fence — or the fall (D-108)."""
    from ..kernel import clock
    from ..physical import bodies, space
    R = tx.rules.infected
    pk = _canon(tx).find("infected", _inf(tx, b)["type_id"]).parkour
    here = _row(tx, "SELECT place_id FROM positions WHERE body_id=?", (b,))["place_id"]
    out = []
    lo, hi = pk.fall_pct if pk is not None else (100, 100)
    pct = rng.range_int(tx, "infected", f"parkour_p:{b}:{at}", lo, hi)
    if rng.chance(tx, "infected", f"parkour:{b}:{at}", pct / 100):
        other = leg["to_place"]
        if pr["kind"] in ("gap", "edge"):
            land = space._landing(tx, pr)
            height = space.drop_m(tx, pr["portal_id"], here)
            p = _row(tx, "SELECT width_m, depth_m FROM places WHERE place_id=?", (land,))
            x, y = p["width_m"] / 2, p["depth_m"] / 2
        else:
            eh = _row(tx, "SELECT elevation_m FROM places WHERE place_id=?", (here,))["elevation_m"]
            eo = _row(tx, "SELECT elevation_m FROM places WHERE place_id=?", (other,))["elevation_m"]
            land = here if eh <= eo else other
            height = abs(eh - eo) / 2 if pr["kind"] == "climb" else pr["height_cm"] / 100 / 2
            x, y = space.portal_point(tx, pr["portal_id"], land)
        out.append(tx.commit_event(space.move_event(tx, b, land, None, x, y, at, cause, turn_index)))
        out += bodies.fall(tx, rng, b, height, at, turn_index, out[-1].event_id)
    else:
        out.append(tx.commit_event(space.move_event(tx, b, leg["to_place"], None, leg["x_m"], leg["y_m"], at, cause, turn_index)))
    if active(tx, b):
        clock.schedule(tx, at + round(R.step_min_s * 1000), "INFECTED_STEP", b, {"body_id": b}, out[-1].event_id)
    return out


def step(tx, rng, row, fired, turn_index):
    from ..action.intent import Intent
    from ..action.resolve import resolve_wave
    from ..contracts.common import LOD
    from ..kernel import clock
    from ..mind.affordance import BoundAffordance
    from ..physical import bodies, space
    from ..physical.space import point_distance
    p = _j(row["payload"], {})
    b, at = p["body_id"], row["due_at"]
    cause = fired.event_id
    if not active(tx, b):
        return []
    from .hordes import fold
    folded = fold(tx, b, at, turn_index, cause)
    if folded:
        return folded
    R = tx.rules.infected
    act = bodies.forced(tx, b, at)
    if act:                                   # CHEAT-19 (D-103): it does that, and nothing else
        ev = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=turn_index, actor_id=b,
                                   cause_event_id=cause,
                                   payload={"actor_id": b, "def_id": "forced_act", "verb": "wait", "target_id": None,
                                            "destination_id": None, "item_id": None, "est_duration_s": R.step_min_s,
                                            "visible": True, "seen": act, "continues_task": False, "label": act, "goal": "",
                                            "attention": None}))
        clock.schedule(tx, at + round(R.step_min_s * 1000), "INFECTED_STEP", b, {"body_id": b}, ev.event_id)
        return [ev]
    out = []
    leg = p.get("leg")
    if leg:
        ok = True
        if leg.get("portal_id"):
            pr = _row(tx, "SELECT * FROM portals WHERE portal_id=?", (leg["portal_id"],))
            if pr is not None and pr["kind"] in ("climb", "gap", "edge", "fence"):   # INF-20 (D-108)
                return out + _parkour_leg(tx, rng, b, pr, leg, at, turn_index, cause)
            ok = bool(pr and pr["is_open"] and space.admits(tx, leg["portal_id"], b))
        if ok:
            out.append(tx.commit_event(space.move_event(tx, b, leg["to_place"], None, leg["x_m"], leg["y_m"], at, cause,
                                                        turn_index)))
        else:
            pos = _row(tx, "SELECT * FROM positions WHERE body_id=?", (b,))
            if leg.get("portal_id"):
                px, py = space.portal_point(tx, leg["portal_id"], pos["place_id"])
                if math.hypot(px - pos["x_m"], py - pos["y_m"]) > 0.5:
                    out.append(tx.commit_event(space.move_event(tx, b, pos["place_id"], None, px, py, at, cause,
                                                                turn_index)))
                    pos = _row(tx, "SELECT * FROM positions WHERE body_id=?", (b,))
            bang = E(tx, EventType.NOISE, "action.propagate", at, turn_index, [],
                     {"source_db": R.bang_db, "kind": "banging", "text": "something heavy bangs against the door",
                      "place_id": pos["place_id"], "x_m": pos["x_m"], "y_m": pos["y_m"]}, cause=cause, actor_id=b,
                     place_id=pos["place_id"])
            out.append(bang)
            if leg.get("portal_id"):
                out += _press_portal(tx, b, leg["portal_id"], pos, at, turn_index, bang.event_id)
    r = _inf(tx, b)
    before = {"energy": r["energy"], "states": _states(r), "target_id": r["target_id"], "charged_at": r["charged_at"]}
    energy, charged = r["energy"], r["charged_at"]
    if charged is None:
        charged = at
    else:
        period = R.energy_period_s.get(r["type_id"], 60) * 1000
        m = (at - charged) // period
        energy -= m
        charged += m * period
    states = _states(r)
    target = r["target_id"]
    if energy <= 0:
        energy, target = 0, None
        if "dormant" not in states:
            states.append("dormant")
    states = _energy_states(R, energy, states)
    changes = {k: v for k, v in (("energy", energy), ("states", states), ("target_id", target), ("charged_at", charged))
               if before[k] != v}
    if changes:
        out.append(_state_ev(tx, b, changes, {k: before[k] for k in changes}, at, turn_index, cause))
    if "dormant" in states:
        return out
    if target is None:
        return out
    tb = _body(tx, target)
    newleg, delay = None, None
    mypos = _row(tx, "SELECT * FROM positions WHERE body_id=?", (b,))
    if tb is not None and tb["alive"]:
        out += bodies.progress(tx, target, at, turn_index, rng)
        tb = _body(tx, target)
    if tb is not None:
        tpos = _row(tx, "SELECT * FROM positions WHERE body_id=?", (target,))
        _feeding_dead = (not tb["alive"] and tpos is not None and tb["dead_at"] is not None
                         and at - tb["dead_at"] < R.feed_on_dead_min * 60_000 and tpos["place_id"] == mypos["place_id"]
                         and (point_distance(tx, b, target) or 99) <= 1.5)
        if (not tb["alive"] and not _feeding_dead) or tpos is None or tb["kind"] == "infected" or _excluded(tx, target, at, sight=False):
            out.append(_state_ev(tx, b, {"target_id": None}, {"target_id": target}, at, turn_index, cause))
            return out
        if tpos["place_id"] == mypos["place_id"]:
            d = point_distance(tx, b, target)
            if d <= 1.5:
                c = min([tx.canon.find("infected_state", x).bite_commitment for x in states] or [1.0])
                holding = b in bodies.grips_on(tx, target) or not tb["alive"]
                if not holding and c < 1 and not rng.chance(tx, "infected", f"commit:{b}:{at}", c):
                    out.append(_state_ev(tx, b, {"target_id": None}, {"target_id": target}, at, turn_index, cause))
                    if b in bodies.grips_on(tx, target):
                        out.append(bodies.release_event(tx, b, target, at, cause, turn_index))
                    return out
                did = "infected_bite" if (b in bodies.grips_on(tx, target) or not tb["alive"]) else "infected_grab"
                ddef = tx.canon.find("affordance", did)
                word = "someone"
                ba = BoundAffordance(def_id=ddef.id, verb=ddef.verb, label=ddef.label.replace("{target}", word),
                                     ui_label=ddef.ui_label.replace("{target}", word), target_id=target,
                                     est_duration_s=ddef.duration.base_s, noise_db=ddef.noise_db, check=ddef.check,
                                     tags=tuple(ddef.tags))
                it = Intent(actor_id=b, bound=ba, speech=None, manner="", goal="", private_reason="", source="reflex",
                            lod=LOD.COLD)
                out += resolve_wave(tx, rng, [it], at, turn_index, horizon_ms=at + 60_000)
                delay = max(R.step_min_s, ddef.duration.base_s)
            else:
                newleg = {"to_place": mypos["place_id"], "x_m": tpos["x_m"], "y_m": tpos["y_m"], "portal_id": None}
                sp = speed(tx, b) or 0.1
                delay = d / sp + 0.5
            dest = None
        else:
            dest = tpos["place_id"]
    else:
        dest = target
        if mypos["place_id"] == dest:
            for r in tx.query("SELECT b.body_id FROM bodies b JOIN positions p ON p.body_id=b.body_id WHERE p.place_id=? "
                              "AND b.alive=1 AND b.kind != 'infected' ORDER BY b.body_id", (dest,)):
                if sees(tx, b, r[0], at):
                    ev = attract(tx, b, r[0], at, cause, turn_index, reason="sight")
                    if ev:
                        out.append(ev)
                    return out
            out.append(_state_ev(tx, b, {"target_id": None}, {"target_id": target}, at, turn_index, cause))
            return out
    if delay is None:
        pth = space.path(tx, b, dest) or space.path(tx, b, dest, allow_closed=True) or \
            space.path(tx, b, dest, allow_locked=True)
        pk = _canon(tx).find("infected", r["type_id"]).parkour if not pth else None
        if pk is not None:   # INF-20 (D-108): the dead that climb
            pth = space.path(tx, b, dest, parkour={"climb_cm": pk.climb_cm, "gap_cm": pk.gap_cm, "edge_m": pk.edge_m})
        if not pth:
            out.append(_state_ev(tx, b, {"target_id": None}, {"target_id": target}, at, turn_index, cause))
            return out
        first = pth[0]
        x, y = space.portal_point(tx, first.portal_id, first.place_id)
        mx, my = space.portal_point(tx, first.portal_id, mypos["place_id"])
        newleg = {"to_place": first.place_id, "x_m": x, "y_m": y, "portal_id": first.portal_id}
        sp = speed(tx, b) or 0.1
        delay = math.hypot(mx - mypos["x_m"], my - mypos["y_m"]) / sp + 1.0
    last = out[-1].event_id if out else cause
    clock.schedule(tx, at + round(max(R.step_min_s, delay) * 1000), "INFECTED_STEP", b, {"body_id": b, "leg": newleg}, last)
    return out


def feed(tx, body_id, at, cause_event_id, turn_index):
    r = _inf(tx, body_id)
    if r is None:
        return None
    R = tx.rules.infected
    energy = min(100, r["energy"] + R.energy_per_feed)
    states = _energy_states(R, energy, _states(r))
    before = {"energy": r["energy"], "states": _states(r)}
    ch = {k: v for k, v in (("energy", energy), ("states", states)) if before[k] != v}
    if not ch:
        return None
    return _state_ev(tx, body_id, ch, {k: before[k] for k in ch}, at, turn_index, cause_event_id)


def seed_quirks(tx, rng, body_id, type_id):
    pool = sorted([q for q in tx.canon.all("quirk") if type_id in q.applies_to], key=lambda q: q.id)
    n = rng.range_int(tx, "quirks", f"count:{body_id}", 0, tx.rules.infected.quirks_max)
    out = []
    for k in range(min(n, len(pool))):
        q = rng.weighted(tx, "quirks", f"quirk:{body_id}:{k}", [(x, x.seed_weight) for x in pool])
        pool.remove(q)
        out.append(q.id)
    return out


def _state_row(tx, rng, body, type_id, at, *, dormant=False, risen_from=None, horde_id=None):
    R = tx.rules.infected
    degrade = None
    if type_id == RUNNER:
        lo, hi = R.runner_degrade_days
        degrade = at + rng.range_int(tx, "infected", f"degrade:{body}", lo, hi) * DAY
    return {"body_id": body, "type_id": type_id, "states": ["dormant"] if dormant else [], "energy": R.energy_start,
            "quirks": seed_quirks(tx, rng, body, type_id), "target_id": None, "lurker_clan": None, "risen_from": risen_from,
            "since": at, "degrade_at": degrade, "horde_id": horde_id, "charged_at": at}


def spawn(tx, rng, place_id, type_id, at, turn_index, cause_event_id, *, dormant=False, x_m=None, y_m=None,
          origin="materialize", horde_id=None):
    from ..physical import bodies, space
    t = tx.canon.find("infected", type_id)
    b = bodies.create(tx, kind="infected", sex=None, age_years=None, height_cm=170, mass_kg=65,
                      special={k: (v.lo + v.hi) // 2 for k, v in t.special.items()}, at=at, turn_index=turn_index,
                      origin=origin, cause_event_id=cause_event_id)
    if x_m is None:
        pl = tx.query_one("SELECT width_m, depth_m FROM places WHERE place_id=?", (place_id,))
        x_m = rng.range_int(tx, "infected", f"x:{b}", 1, max(1, int(pl[0]) - 1))
        y_m = rng.range_int(tx, "infected", f"y:{b}", 1, max(1, int(pl[1]) - 1))
    space.place_body(tx, b, place_id, None, float(x_m), float(y_m), at, cause_event_id, turn_index)
    E(tx, EventType.MATERIALIZE, "world.infected", at, turn_index,
      [W("infected_state", _state_row(tx, rng, b, type_id, at, dormant=dormant, horde_id=horde_id))],
      {"body_id": b, "type_id": type_id},
      cause=cause_event_id, actor_id=b, origin="worldgen" if origin == "worldgen" else "sim")
    return b


def populate(tx, rng, place_id, at, turn_index, cause_event_id):
    from ..physical import space
    pl = _row(tx, "SELECT * FROM places WHERE place_id=?", (place_id,))
    props = _j(pl["props"], {})
    if props.get("populated"):
        return []
    stl_places = {r[0] for r in tx.query("SELECT place_id FROM settlements")}
    stl_zones = {r[0] for r in tx.query("SELECT p.zone_id FROM settlements s JOIN places p ON p.place_id = s.place_id")}
    is_hub = pl["kind"] == "street" and tx.query_one(
        "SELECT 1 FROM zones WHERE zone_id=? AND name=?", (pl["zone_id"], pl["name"])) is not None
    if place_id in stl_places or pl["parent_id"] in stl_places or (is_hub and pl["zone_id"] in stl_zones):
        space.change_place(tx, place_id, {"props": {"populated": True}}, "populated", at, cause_event_id, turn_index)
        return []
    from . import hordes
    top = hordes.target(tx, place_id)
    z = tx.query_one("SELECT zone_id FROM places WHERE place_id=?", (top,))[0]
    f = tx.rules.infected.place_factor.get(pl["kind"], 0.5)
    R = tx.rules.infected
    Hs = tx.rules.hordes
    out = []
    if z is not None:
        nz = tx.query_one("SELECT COUNT(*) FROM places WHERE zone_id=? AND parent_id IS NULL", (z,))[0]
        for ty, (act, dorm) in hordes.pool(tx, z).items():
            made = {"active": 0, "dormant": 0}
            for which, c in (("active", act), ("dormant", dorm)):
                if c <= 0:
                    continue
                x = c * f / (max(1, nz) * Hs.populate_scale)
                k = math.floor(x) + (1 if rng.chance(tx, "infected", f"{which}:{place_id}:{ty}", x - math.floor(x)) else 0)
                k = min(R.populate_max, c, k)
                for _ in range(k):
                    out.append(spawn(tx, rng, place_id, ty, at, turn_index, cause_event_id, dormant=(which == "dormant")))
                made[which] = k
            if made["active"] or made["dormant"]:
                hordes.change(tx, z, ty, -made["active"], -made["dormant"], "populated", at, turn_index, cause_event_id)
    space.change_place(tx, place_id, {"props": {"populated": True}}, "populated", at, cause_event_id, turn_index)
    return out


def rise(tx, rng, row, fired, turn_index):
    from ..physical import bodies, objects
    p = _j(row["payload"], {})
    corpse, pathway = p.get("body_id"), p.get("pathway")
    at = row["due_at"]
    c = _body(tx, corpse)
    if c is None or c["alive"] or c["kind"] != "human":
        return []
    pos = _row(tx, "SELECT * FROM positions WHERE body_id=?", (corpse,))
    if pos is None:
        return []
    if tx.query_one("SELECT COUNT(*) FROM wounds WHERE body_id=? AND type='bite'", (corpse,))[0] >= tx.rules.infected.devoured_bites:
        return []
    for w in tx.query("SELECT anatomy, severity FROM wounds WHERE body_id=? AND healed_at IS NULL", (corpse,)):
        if w[1] == "catastrophic" and w[0] in ("head", "neck"):
            return []
    pw = tx.canon.find("pathway", pathway)
    ty = rng.choice(tx, "infected", f"rise:{corpse}:type", list(pw.rise_as))
    new = bodies.rise(tx, corpse, ty, at, fired.event_id, turn_index)
    from ..physical import space
    out = []
    out.append(space.place_body(tx, new, pos["place_id"], pos["anchor_id"], pos["x_m"], pos["y_m"], at, fired.event_id,
                                turn_index, replaces=corpse))
    for it in tx.query("SELECT item_id, qty, holder_slot FROM items WHERE holder_body=? ORDER BY item_id", (corpse,)):
        out.append(objects.transfer(tx, it[0], objects.Holder("body", new, it[2] or "pack"), it[1], at, None, fired.event_id,
                                    turn_index))
    out.append(E(tx, EventType.MATERIALIZE, "world.infected", at, turn_index,
                 [W("infected_state", _state_row(tx, rng, new, ty, at, risen_from=corpse))],
                 {"body_id": new, "type_id": ty, "risen_from": corpse}, cause=fired.event_id, actor_id=new))
    for r in tx.query("SELECT b.body_id FROM bodies b JOIN positions p ON p.body_id=b.body_id WHERE p.place_id=? AND b.alive=1 "
                      "AND b.kind != 'infected' ORDER BY b.body_id", (pos["place_id"],)):
        if sees(tx, new, r[0], at):
            ev = attract(tx, new, r[0], at, fired.event_id, turn_index, reason="sight")
            if ev:
                out.append(ev)
            break
    return out


def infected_day(tx, rng, at, turn_index, cause_event_id):
    R = tx.rules.infected
    out = []
    for r in tx.query("SELECT * FROM infected_state WHERE folded_at IS NULL ORDER BY body_id"):
        r = dict(r)
        ch, before = {}, {}
        states = _states(r)
        if "dormant" in states and r["energy"] < 100:
            ch["energy"] = min(100, r["energy"] + R.idle_recover_per_day)
            ns = _energy_states(R, ch["energy"], states)
            if ns != states:
                ch["states"] = ns
        if r["type_id"] == RUNNER and r["degrade_at"] is not None and r["degrade_at"] <= at:
            ch["type_id"] = rng.choice(tx, "infected", f"degrade:{r['body_id']}:type", [SHAMBLER, CRAWLER])
            ch["degrade_at"] = None
        if ch:
            before = {k: (r[k] if k != "states" else states) for k in ch}
            out.append(_state_ev(tx, r["body_id"], ch, before, at, turn_index, cause_event_id))
    return out


# ------------------------------------------------------------------------------------------ propagate (P10)
def _t(e):
    return str(getattr(e.type, "value", e.type))


def propagate(tx, outcome_events, at, turn_index):
    from ..physical.space import portal_point  # noqa: F401
    from ..action._impl_p5b import _events_since
    from ..sense import acoustics
    first = tx.query_one("SELECT COALESCE(MAX(seq),0) FROM events")[0]
    out = []
    evs = sorted(outcome_events, key=lambda e: e.seq if getattr(e, "seq", None) is not None else 0)
    for e in evs:
        t = _t(e)
        p = e.payload or {}
        if t in ("NOISE", "SPEECH") and p.get("source_db") is not None:
            try:
                src = acoustics.source_point(tx, p, e.actor_id)
            except ValueError:
                continue
            excl = {e.actor_id} if e.actor_id else set()
            for rec in acoustics.receptions(tx, p["source_db"], src, e.at, tx.rules.acoustics, exclude=excl):
                if not active(tx, rec.listener_id):
                    continue
                if rec.received_db < threshold(tx, rec.listener_id):
                    continue
                tgt = e.actor_id if t == "SPEECH" else (p.get("place_id") or src.place_id)
                if not tgt or tgt == rec.listener_id:
                    continue
                ev = attract(tx, rec.listener_id, tgt, e.at, e.event_id, turn_index, reason="noise")
                if ev:
                    out.append(ev)
            if t == "NOISE" and p["source_db"] >= tx.rules.hordes.draw_db and p.get("place_id"):
                from . import hordes
                hordes.draw(tx, p["place_id"], p["source_db"], e.at, turn_index, e.event_id)
        elif t == "MOVE":
            mover = p.get("body_id") or e.actor_id
            mb = _body(tx, mover)
            if mb is None or mb["kind"] == "infected":
                continue
            to = p.get("to_place")
            for r in tx.query("SELECT i.body_id, i.target_id FROM infected_state i JOIN positions q ON q.body_id=i.body_id "
                              "WHERE q.place_id=? ORDER BY i.body_id", (to,)):
                if not active(tx, r[0]):
                    continue
                if r[1]:
                    tb = _body(tx, r[1])
                    tp = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (r[1],))
                    if tb and tb["alive"] and tp and tp[0] == to:
                        continue
                if sees(tx, r[0], mover, e.at):
                    ev = attract(tx, r[0], mover, e.at, e.event_id, turn_index, reason="sight")
                    if ev:
                        out.append(ev)
        elif t == "HARM":
            if p.get("bleed_pct_per_min", 0) >= 1:
                w = tx.query_one("SELECT clotted FROM wounds WHERE wound_id=?", (p.get("wound_id"),))
                pos = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (p.get("body_id"),))
                if w is not None and not w[0] and pos is not None:
                    trace_create(tx, pos[0], "blood", "Blood on the ground, still wet.", e.event_id, e.at, turn_index)
        elif t == "PORTAL_CHANGE":
            ch, bf = p.get("changes") or {}, p.get("before") or {}
            if "damage" in ch and ch["damage"] > bf.get("damage", 0) and bf.get("damage", 0) == 0:
                pr = _row(tx, "SELECT * FROM portals WHERE portal_id=?", (p.get("portal_id"),))
                side = pr["place_a"]
                if e.actor_id:
                    ap = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (e.actor_id,))
                    if ap and ap[0] in (pr["place_a"], pr["place_b"]):
                        side = ap[0]
                trace_create(tx, side, "damage", f"The {pr['name']} has been forced.", e.event_id, e.at, turn_index)
        elif t == "DEATH":
            if p.get("cause") != "offscreen":
                pos = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (p.get("body_id"),))
                if pos is not None:
                    trace_create(tx, pos[0], "corpse", "A body lies here.", e.event_id, e.at, turn_index)
    return _events_since(tx, first)


# ------------------------------------------------------------------------------------------ worldmove
def _since(tx, first):
    from ..action._impl_p5b import _events_since
    return _events_since(tx, first)


def _maxseq(tx):
    return tx.query_one("SELECT COALESCE(MAX(seq),0) FROM events")[0]


def _params(tx):
    from ..contracts.worldgen import WorldParams
    r = tx.query_one("SELECT params_json FROM world_params WHERE id=1")
    return None if r is None else WorldParams.model_validate_json(r[0])


def _values(tx):
    from .worldgen.params import flat_values
    return flat_values(_params(tx))


def _area(tx, turn_index):
    from ..turn.select import active_area
    pc = tx.query_one("SELECT value FROM meta WHERE key='pc_actor_id'")
    if pc is None or not pc[0]:
        return set()
    if tx.query_one("SELECT 1 FROM positions WHERE body_id=?", (pc[0],)) is None:
        return set()
    return set(active_area(tx, pc[0], turn_index))


def _place_of(tx, b):
    r = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (b,))
    return None if r is None else r[0]


def _hub_of_zone(tx, zone_id):
    r = tx.query_one("SELECT p.place_id FROM places p JOIN zones z ON z.zone_id=p.zone_id AND z.name=p.name "
                     "WHERE p.zone_id=? AND p.kind='street' ORDER BY p.place_id LIMIT 1", (zone_id,))
    return None if r is None else r[0]


def _zone_of_place(tx, place_id):
    r = tx.query_one("SELECT zone_id FROM places WHERE place_id=?", (place_id,))
    return None if r is None else r[0]


def _move_to(tx, body, place, at, cause, turn_index):
    from ..physical import space
    p = tx.query_one("SELECT width_m, depth_m FROM places WHERE place_id=?", (place,))
    return tx.commit_event(space.move_event(tx, body, place, None, p[0] / 2, p[1] / 2, at, cause, turn_index))


def ensure_timers(tx, at, turn_index):
    from ..kernel import clock
    from ..society.settlement import next_hour
    if tx.query_one("SELECT 1 FROM event_queue WHERE type='WORLD_DAY' AND status='pending'") is not None:
        return []
    return [clock.schedule(tx, next_hour(at, tx.rules.world.world_hour), "WORLD_DAY", None, {}, None)]


def weather_step(tx, rng, at, d, cause, turn_index, values):
    from .worldmove import weather_weights
    Wr = tx.rules.world
    if not rng.chance(tx, "offscreen", f"weather:{d}", Wr.weather_change_chance):
        return
    kind = rng.weighted(tx, "offscreen", f"weather_kind:{d}", weather_weights(values))
    wind = rng.range_int(tx, "offscreen", f"wind:{d}", 1, 3) if kind in ("wind", "storm") else 0
    cur = tx.query_one("SELECT weather, wind_level FROM world_clock WHERE id=1")
    if (cur[0], cur[1]) == (kind, wind):
        return
    E(tx, EventType.WEATHER_CHANGE, "kernel.clock", at, turn_index,
      [W("world_clock", {"weather": kind, "wind_level": wind}, WriteOp.UPDATE, {"id": 1})],
      {"weather": kind, "wind_level": wind}, cause=cause)


def _active_op_of(tx, body):
    for r in tx.query("SELECT kind, participants FROM operations WHERE status='active' ORDER BY op_id"):
        if body in _j(r[1], []):
            return r[0]
    return None


def worldmove_day(tx, rng, row, fired, turn_index):
    from ..kernel import clock
    from . import decay as decay_mod
    from . import traces as traces_mod
    first = _maxseq(tx)
    at = row["due_at"]
    d = at // DAY
    prev = tx.query_one("SELECT MAX(seq) FROM events WHERE type='WORLD_DAY'")[0]
    wd = E(tx, EventType.WORLD_DAY, "world.worldmove", at, turn_index, [], {"day": d}, cause=fired.event_id)
    WD = wd.event_id
    values = _values(tx)
    weather_step(tx, rng, at, d, WD, turn_index, values)
    traces_mod.washout(tx, at, turn_index, WD)
    area = _area(tx, turn_index)
    for r in [dict(x) for x in tx.query(
            "SELECT e.event_id, e.payload FROM events e WHERE e.type='DEATH' AND e.seq > ? ORDER BY e.seq",
            (prev if prev is not None else 0,))]:
        pl = _j(r["payload"], {})
        body = pl.get("body_id")
        b = tx.query_one("SELECT b.kind FROM bodies b JOIN actors a ON a.actor_id=b.body_id WHERE b.body_id=?", (body,))
        if b is None or b[0] != "human":
            continue
        place = _place_of(tx, body)
        if place is None or place in area:
            continue
        E(tx, EventType.OFFSCREEN_DEATH, "world.worldmove", at, turn_index, [],
          {"body_id": body, "place_id": place, "cause": pl.get("cause")}, cause=r["event_id"], actor_id=body, place_id=place)
    plan_operations(tx, rng, at, turn_index, WD)
    depart(tx, rng, at, turn_index, WD)
    _wild_card_wanders(tx, rng, at, d, turn_index, WD, area)          # WORLD-07 (D-102)
    decay_mod.day(tx, rng, at, turn_index, WD)
    infected_day(tx, rng, at, turn_index, WD)
    from . import hordes
    hordes.day(tx, rng, at, turn_index, WD)
    clock.schedule(tx, at + DAY, "WORLD_DAY", None, {}, WD)
    return _since(tx, first)


def _wild_card_wanders(tx, rng, at, d, turn_index, cause, area):
    from ..physical import space
    for (b,) in [tuple(r) for r in tx.query("SELECT body_id FROM bodies WHERE origin='wildcard' AND alive=1 ORDER BY body_id")]:
        here = _place_of(tx, b)
        if here is None or here in area:
            continue
        cands = [r[0] for r in tx.query("SELECT place_id FROM places WHERE parent_id IS NULL ORDER BY place_id")
                 if r[0] != here and r[0] not in area]
        if not cands:
            continue
        to = rng.choice(tx, "offscreen", f"wildcard:{b}:{d}", cands)
        space.remove_body(tx, b, at, cause, turn_index)
        _place_at_first_anchor(tx, b, to, at, cause, turn_index)


def _work_hours(tx, actor):
    h = 0
    for r in tx.query("SELECT shift_start_hh, shift_end_hh FROM work_assignments WHERE actor_id=?", (actor,)):
        h += (r[1] - r[0]) % 24 or 24
    return h


def launch(tx, group_id, kind, participants, origin, destination, at, turn_index, cause, *, target_id=None):
    # OPS-08.
    return _new_op(tx, group_id, kind, participants, origin, destination, at, turn_index, cause, target_id=target_id).payload["op_id"]


def _new_op(tx, gid, kind, participants, origin, dest, at, turn_index, cause, *, target_id=None):
    from ..kernel import clock
    Wr = tx.rules.world
    op = tx.mint("ops")
    nxt = at + int(Wr.op_leg_h * H)
    pl = {"op_id": op, "group_id": gid, "kind": kind, "participants": list(participants), "destination": dest,
          "status": "active", "step": "depart"}
    if target_id is not None:
        pl["target_id"] = target_id
    ev = E(tx, EventType.FACTION_OPERATION, "world.worldmove", at, turn_index,
           [W("operations", {"op_id": op, "group_id": gid, "kind": kind, "status": "active", "route": [origin, dest],
                             "participants": list(participants), "next_due_at": nxt, "outcome": None,
                             "target_id": target_id})], pl, cause=cause)
    for b in participants:
        z = _zone_of_place(tx, _place_of(tx, b))
        hub = _hub_of_zone(tx, z)
        if hub and hub != _place_of(tx, b):
            _move_to(tx, b, hub, at, ev.event_id, turn_index)
    clock.schedule(tx, nxt, "OPERATION_STEP", op, {"op_id": op, "step": "arrive"}, ev.event_id)
    return ev


def plan_operations(tx, rng, at, turn_index, cause):
    from ..society.work import able
    first = _maxseq(tx)
    d = at // DAY
    Wr = tx.rules.world
    values = _values(tx)
    area = _area(tx, turn_index)
    stls = [dict(r) for r in tx.query("SELECT * FROM settlements ORDER BY settlement_id")]
    stl_sites = {s["place_id"] for s in stls}
    busy = set()
    for r in tx.query("SELECT participants FROM operations WHERE status='active'"):
        busy |= set(_j(r[0], []))
    for s in stls:
        if s["place_id"] in area or not s["group_id"] or s.get("lockdown"):
            continue
        holders = set()
        gref = tx.query_one("SELECT content_ref FROM groups WHERE group_id=?", (s["group_id"],))[0]
        if gref:
            try:
                rec = tx.canon.get(gref)
            except KeyError:
                rec = None
            if rec is not None:
                from ._impl_factions import _seat_holders
                holders = {a for _seat, a in _seat_holders(tx, s["group_id"], rec, {ld.seat for ld in rec.leaders if ld.seat})}
        crew = []
        for r in tx.query("SELECT m.actor_id, m.role FROM group_members m JOIN bodies b ON b.body_id=m.actor_id "
                          "JOIN actors a ON a.actor_id=m.actor_id "
                          "WHERE m.group_id=? AND m.status='member' AND b.alive=1 AND a.controller != 'human' ORDER BY m.actor_id",
                          (s["group_id"],)):
            a = r[0]
            if a in holders:
                continue
            if a in busy or _place_of(tx, a) in area or _place_of(tx, a) is None:
                continue
            if not able(tx, a, "watcher")[0]:
                continue
            crew.append(a)
        crew.sort(key=lambda a: (_work_hours(tx, a), a))
        others = [o for o in stls if o["settlement_id"] != s["settlement_id"]]
        kind = None
        for k in ("scavenge", "patrol", "trade_run"):
            c = Wr.op_chance[k]
            if k == "scavenge" and _j(s["shortages"], []):
                c *= 2
            if k == "patrol":
                c *= values["social_order"] / 5
            if k == "trade_run":
                c *= values["faction_relations"] / 5 if others else 0
            if rng.chance(tx, "offscreen", f"op:{s['settlement_id']}:{k}:{d}", c):
                kind = k
                break
        if kind is None:
            continue
        n = min(rng.range_int(tx, "offscreen", f"party:{s['settlement_id']}:{d}", *Wr.op_party), len(crew))
        if n <= 0:
            continue
        sz = _zone_of_place(tx, s["place_id"])
        if kind == "scavenge":
            cands = [r[0] for r in tx.query("SELECT place_id FROM places WHERE kind='building' AND parent_id IS NULL AND zone_id != ? "
                                             "ORDER BY place_id", (sz,)) if r[0] not in stl_sites]
            if not cands:
                cands = [r[0] for r in tx.query("SELECT place_id FROM places WHERE kind='building' AND parent_id IS NULL ORDER BY place_id")
                         if r[0] not in stl_sites]
        elif kind == "patrol":
            hub = _hub_of_zone(tx, sz)
            cands = []
            for r in tx.query("SELECT from_place, to_place FROM routes ORDER BY route_id"):
                if hub in (r[0], r[1]):
                    far = r[1] if r[0] == hub else r[0]
                    if tx.query_one("SELECT z.kind FROM places p JOIN zones z ON z.zone_id = p.zone_id WHERE p.place_id=?",
                                    (far,))[0] != "exterior":
                        cands.append(far)
        else:
            cands = [o["place_id"] for o in others]
        if not cands:
            continue
        dest = rng.choice(tx, "offscreen", f"dest:{s['settlement_id']}:{d}", cands)
        _new_op(tx, s["group_id"], kind, crew[:n], s["place_id"], dest, at, turn_index, cause)
        busy |= set(crew[:n])
    for g in tx.query("SELECT group_id FROM groups ORDER BY group_id"):
        gid = g[0]
        if tx.query_one("SELECT 1 FROM settlements WHERE group_id=?", (gid,)) is not None:
            continue
        hostile = tx.query_one("SELECT 1 FROM cohorts WHERE archetype=?", (gid,)) is not None
        if not hostile:
            continue
        mem = [r[0] for r in tx.query("SELECT m.actor_id FROM group_members m JOIN bodies b ON b.body_id=m.actor_id "
                                      "WHERE m.group_id=? AND m.status='member' AND b.alive=1 ORDER BY m.actor_id", (gid,))
               if _place_of(tx, r[0]) not in area and r[0] not in busy and _place_of(tx, r[0]) is not None]
        if len(mem) < 2 or not stls:
            continue
        if rng.chance(tx, "offscreen", f"raid:{gid}:{d}", Wr.op_chance["raid"] * values["hostile_human"] / 5):
            tgt = rng.choice(tx, "offscreen", f"raid_target:{gid}:{d}", [s["settlement_id"] for s in stls])
            tsite = next(s["place_id"] for s in stls if s["settlement_id"] == tgt)
            origin = _hub_of_zone(tx, _zone_of_place(tx, _place_of(tx, mem[0])))
            _new_op(tx, gid, "raid", mem, origin, tsite, at, turn_index, cause)
    return _since(tx, first)


def _outcome(tx, rng, op, movers, dest, at, turn_index, cause):
    from ..action.effects import CENTRE_MASS
    from ..physical import bodies, objects
    from ..physical.bodies import WoundSpec
    from ..society import group as grp
    from ..society import settlement as stl
    values = _values(tx)
    o = op["op_id"]
    out = {"haul": {}}
    zone = _zone_of_place(tx, dest)
    from . import hordes
    dens = hordes.density(tx, zone) if zone else 0
    for m in movers:
        if rng.chance(tx, "offscreen", f"{o}:hurt:{m}", dens / 20):
            an = rng.weighted(tx, "offscreen", f"{o}:anatomy:{m}", list(CENTRE_MASS))
            sev = rng.choice(tx, "offscreen", f"{o}:severity:{m}", ["minor", "significant"])
            bodies.apply_harm(tx, m, WoundSpec(an, "laceration", sev, 0), at, cause, turn_index, rng)
    k = op["kind"]
    if k == "scavenge":
        found = rng.chance(tx, "offscreen", f"{o}:found", 0.6)
        pl = _row(tx, "SELECT * FROM places WHERE place_id=?", (dest,))
        if pl["layout_generated"]:
            ids = [r[0] for r in tx.query("SELECT i.item_id FROM items i JOIN places p ON p.place_id=i.place_id "
                                          "WHERE (p.place_id=? OR p.parent_id=?) ORDER BY i.item_id", (dest, dest))][:3]
            alive = [m for m in movers if tx.query_one("SELECT alive FROM bodies WHERE body_id=?", (m,))[0]]
            for i, it in enumerate(ids):
                if not alive:
                    break
                q = tx.query_one("SELECT qty FROM items WHERE item_id=?", (it,))[0]
                try:
                    objects.transfer(tx, it, objects.Holder("body", alive[i % len(alive)], "pack"), q, at, alive[i % len(alive)], cause,
                                     turn_index)
                except ValueError:
                    pass
            if ids:
                trace_create(tx, dest, "missing_stock", "Shelves pulled out; whatever was here is gone.", cause, at, turn_index)
        trace_create(tx, dest, "tracks", "Boot prints in the dust, a few people, coming and going.", cause, at, turn_index)
        if found:
            out["haul"] = {"food": rng.range_int(tx, "offscreen", f"{o}:food", 2, 8) * len(movers),
                           "water": rng.range_int(tx, "offscreen", f"{o}:water", 2, 8) * len(movers)}
    elif k == "patrol":
        trace_create(tx, dest, "tracks", "Boot prints in a loose line, walking a route.", cause, at, turn_index)
    elif k == "trade_run":
        origin = _j(op["route"], [])[0]
        so = _row(tx, "SELECT * FROM settlements WHERE place_id=?", (origin,))
        sd = _row(tx, "SELECT * FROM settlements WHERE place_id=?", (dest,))
        st = _j(so["stores"], {})
        give = "food" if st.get("food", 0) >= st.get("water", 0) else "water"
        get = "water" if give == "food" else "food"
        amt = int(math.floor(st.get(give, 0) * 0.1 + 0.5))
        out["haul"] = {give: -amt, get: amt}
        out["trade"] = {"from": so["settlement_id"], "to": sd["settlement_id"] if sd else None, "gave": {give: amt}, "got": {get: amt}}
        E(tx, EventType.TRADE, "world.worldmove", at, turn_index, [], {"op_id": o, **out["trade"]}, cause=cause)
        trace_create(tx, dest, "tracks", "Boot prints in the dust, a few people, coming and going.", cause, at, turn_index)
    elif k == "raid":
        s = _row(tx, "SELECT * FROM settlements WHERE place_id=?", (dest,))
        p = max(0.1, min(0.9, 0.5 + (values["hostile_human"] - s["defences"]) / 20))
        ok = rng.chance(tx, "offscreen", f"{o}:success", p)
        E(tx, EventType.RAID, "world.worldmove", at, turn_index, [],
          {"op_id": o, "group_id": op["group_id"], "settlement_id": s["settlement_id"], "success": ok}, cause=cause)
        if ok:
            pct = rng.range_int(tx, "offscreen", f"{o}:loss", 10, 25) / 100
            st = _j(s["stores"], {})
            stl.receive(tx, s["settlement_id"], {"food": -round(st.get("food", 0) * pct, 2), "water": -round(st.get("water", 0) * pct, 2)},
                        "raid", at, turn_index, cause)
            stl.adjust(tx, s["settlement_id"], "morale", -1, at, turn_index, cause, reason="raid")
            trace_create(tx, dest, "damage", "Broken boards and a forced door.", cause, at, turn_index)
            trace_create(tx, dest, "blood", "Blood on the ground, still wet.", cause, at, turn_index)
            if s["group_id"]:
                grp.adjust_tension(tx, s["group_id"], op["group_id"], 20, "raid", at, turn_index, cause)
        else:
            alive = [m for m in movers if tx.query_one("SELECT alive FROM bodies WHERE body_id=?", (m,))[0]]
            if alive:
                an = rng.weighted(tx, "offscreen", f"{o}:shot", list(CENTRE_MASS))
                bodies.apply_harm(tx, alive[0], WoundSpec(an, "gunshot", "significant", 0), at, cause, turn_index, rng)
            trace_create(tx, dest, "blood", "Blood on the ground, still wet.", cause, at, turn_index)
        out["success"] = ok
    return out


def _tend(tx, movers, method, at, turn_index, cause, *, settlement=None):
    # OPS-07: pack every bleeding non-minor wound at once; suture the significant ones at home
    # while the settlement has medicine. Returns True when anything was treated.
    from ..physical import bodies
    from ..society import settlement as stl
    done = False
    alive = [m for m in sorted(movers) if tx.query_one("SELECT alive FROM bodies WHERE body_id=?", (m,))[0]]
    for m in alive:
        by = next((x for x in alive if x != m), m)
        for w in [dict(r) for r in tx.query("SELECT wound_id, severity FROM wounds WHERE body_id=? AND healed_at IS NULL "
                                            "ORDER BY wound_id", (m,))]:
            if w["severity"] == "minor" or bodies.effective_bleed(tx, w["wound_id"]) <= 0:
                continue
            if method == "suture":
                if w["severity"] != "significant":
                    continue
                if (_j(tx.query_one("SELECT stores FROM settlements WHERE settlement_id=?", (settlement,))[0], {})
                        .get("medicine", 0)) < 1:
                    continue
                stl.receive(tx, settlement, {"medicine": -1}, "treatment", at, turn_index, cause)
            bodies.treat(tx, m, w["wound_id"], method, by, at, cause, turn_index)
            done = True
    return done


def worldmove_step(tx, rng, row, fired, turn_index):
    from ..kernel import clock
    from ..society import settlement as stl
    first = _maxseq(tx)
    p = _j(row["payload"], {})
    op = _row(tx, "SELECT * FROM operations WHERE op_id=?", (p.get("op_id"),))
    if op is None or op["status"] != "active":
        return []
    at = row["due_at"]
    Wr = tx.rules.world
    area = _area(tx, turn_index)
    movers = [m for m in _j(op["participants"], []) if tx.query_one("SELECT alive FROM bodies WHERE body_id=?", (m,))[0]
              and _place_of(tx, m) not in area]
    origin, dest = _j(op["route"], [None, None])
    if op["kind"] == "decon" and p.get("step") in ("arrive", "hunt"):
        _decon_step(tx, rng, op, p.get("step"), movers, at, turn_index, fired)
        return _since(tx, first)
    if p.get("step") == "arrive":
        for m in movers:
            if _place_of(tx, m) != dest:
                mv = _move_to(tx, m, dest, at, fired.event_id, turn_index)
                on_arrival(tx, rng, m, dest, at, mv.event_id, turn_index)
        oc = _outcome(tx, rng, op, movers, dest, at, turn_index, fired.event_id)
        packed = _tend(tx, movers, "packing", at, turn_index, fired.event_id)
        nxt = at + int((Wr.op_leg_h if packed else Wr.op_dwell_h) * H)
        ev = E(tx, EventType.FACTION_OPERATION, "world.worldmove", at, turn_index,
               [W("operations", {"outcome": oc, "next_due_at": nxt}, WriteOp.UPDATE, {"op_id": op["op_id"]})],
               {"op_id": op["op_id"], "step": "arrive", "outcome": oc}, cause=fired.event_id)
        clock.schedule(tx, nxt, "OPERATION_STEP", op["op_id"], {"op_id": op["op_id"], "step": "return"}, ev.event_id)
    else:
        for m in movers:
            if _place_of(tx, m) != origin:
                _move_to(tx, m, origin, at, fired.event_id, turn_index)
        oc = _j(op["outcome"], {}) or {}
        haul = {k: v for k, v in (oc.get("haul") or {}).items() if v}
        so = tx.query_one("SELECT settlement_id FROM settlements WHERE place_id=?", (origin,))
        if haul and so is not None:
            stl.receive(tx, so[0], haul, "trade" if op["kind"] == "trade_run" else "scavenged", at, turn_index, fired.event_id)
            if op["kind"] == "trade_run" and oc.get("trade", {}).get("to"):
                stl.receive(tx, oc["trade"]["to"], {k: -v for k, v in haul.items()}, "trade", at, turn_index, fired.event_id)
        if so is not None:
            _tend(tx, movers, "suture", at, turn_index, fired.event_id, settlement=so[0])
        E(tx, EventType.FACTION_OPERATION, "world.worldmove", at, turn_index,
          [W("operations", {"status": "done", "next_due_at": None}, WriteOp.UPDATE, {"op_id": op["op_id"]})],
          {"op_id": op["op_id"], "step": "return", "status": "done"}, cause=fired.event_id)
    return _since(tx, first)


def _decon_step(tx, rng, op, step, movers, at, turn_index, fired):
    # OPS-02 'decon' (world.factions FAC-05).
    from ..kernel import clock
    from ..mind.perception import describe
    from ..physical import bodies
    from . import hordes
    Wr = tx.rules.world
    killer = op["target_id"]
    oid = op["op_id"]
    kb = _body(tx, killer) if killer else None
    everyone = _j(op["participants"], [])
    alive = [m for m in everyone if tx.query_one("SELECT alive FROM bodies WHERE body_id=?", (m,))[0]]
    kp = _place_of(tx, killer) if killer else None

    def go_home(outcome):
        ev = E(tx, EventType.FACTION_OPERATION, "world.worldmove", at, turn_index,
               [W("operations", {"outcome": outcome, "next_due_at": at}, WriteOp.UPDATE, {"op_id": oid})],
               {"op_id": oid, "step": step, "outcome": outcome}, cause=fired.event_id)
        clock.schedule(tx, at, "OPERATION_STEP", oid, {"op_id": oid, "step": "return"}, ev.event_id)

    if kb is None or not kb["alive"] or kp is None:
        go_home({"killer_dead": True})
        return
    if step == "hunt":
        if not alive:
            go_home({"killer_dead": False})
            return
        ev = E(tx, EventType.FACTION_OPERATION, "world.worldmove", at, turn_index,
               [W("operations", {"next_due_at": at + int(Wr.op_leg_h * H)}, WriteOp.UPDATE, {"op_id": oid})],
               {"op_id": oid, "step": "hunt"}, cause=fired.event_id)
        clock.schedule(tx, at + int(Wr.op_leg_h * H), "OPERATION_STEP", oid, {"op_id": oid, "step": "hunt"}, ev.event_id)
        return
    dest = hordes.target(tx, kp)
    area = _area(tx, turn_index)
    rec = tx.canon.get(tx.query_one("SELECT content_ref FROM groups WHERE group_id=?", (op["group_id"],))[0])
    D = rec.behaviour.decon
    for m in movers:
        if _place_of(tx, m) != dest:
            _move_to(tx, m, dest if killer not in area else kp, at, fired.event_id, turn_index)
    if kp not in area and killer not in area:
        dev = bodies.die(tx, rng, killer, at, fired.event_id, turn_index, cause="decon")
        trace_create(tx, kp, "mark", D.mark, dev.event_id if dev else fired.event_id, at, turn_index)
        nxt = at + int(Wr.op_leg_h * H)
        ev = E(tx, EventType.FACTION_OPERATION, "world.worldmove", at, turn_index,
               [W("operations", {"outcome": {"killed": killer}, "next_due_at": nxt}, WriteOp.UPDATE, {"op_id": oid})],
               {"op_id": oid, "step": "arrive", "outcome": {"killed": killer}}, cause=fired.event_id)
        clock.schedule(tx, nxt, "OPERATION_STEP", oid, {"op_id": oid, "step": "return"}, ev.event_id)
        return
    for m in alive:
        goal = D.goal.replace("{target}", describe(tx, m, killer))
        E(tx, EventType.PLAN_CHANGE, "mind.actor", at, turn_index,
          [W("plans", {"actor_id": m, "goal_text": goal, "steps": [], "standing_orders": [], "updated_at": at}, WriteOp.UPSERT,
             {"actor_id": m}),
           W("actors", {"goal_text": goal}, WriteOp.UPDATE, {"actor_id": m})],
          {"actor_id": m, "goal_text": goal, "steps": []}, cause=fired.event_id, actor_id=m)
    nxt = at + int(Wr.op_leg_h * H)
    ev = E(tx, EventType.FACTION_OPERATION, "world.worldmove", at, turn_index,
           [W("operations", {"next_due_at": nxt}, WriteOp.UPDATE, {"op_id": oid})],
           {"op_id": oid, "step": "hunt"}, cause=fired.event_id)
    clock.schedule(tx, nxt, "OPERATION_STEP", oid, {"op_id": oid, "step": "hunt"}, ev.event_id)


def on_arrival(tx, rng, body_id, place_id, at, cause_event_id, turn_index):
    from ..physical import space
    first = _maxseq(tx)
    b = _body(tx, body_id)
    if b is None or b["kind"] == "infected" or tx.query_one("SELECT 1 FROM world_params WHERE id=1") is None:
        return []
    pl = _row(tx, "SELECT * FROM places WHERE place_id=?", (place_id,))
    if pl["kind"] == "building" and pl["archetype_ref"] and not pl["layout_generated"]:
        space.discover_layout(tx, rng, place_id, at, turn_index)
        if not pl["held"]:
            a = tx.canon.get(pl["archetype_ref"])
            er = next((r for r in a.rooms if r.id == a.entrance_room), a.rooms[0])
            room = tx.query_one("SELECT place_id FROM places WHERE parent_id=? AND name=? ORDER BY place_id LIMIT 1",
                                (place_id, er.name))
            if room:
                trace_create(tx, room[0], "damage", "Old damage: this place was picked over long ago.", cause_event_id, at,
                             turn_index)
    populate(tx, rng, place_id, at, turn_index, cause_event_id)
    return _since(tx, first)


def depart(tx, rng, at, turn_index, cause):
    from ..mind.mind import close_loop
    from ..society import settlement as stl
    from ..society.group import defection_pressure
    from ..society.household import apply_change, household_of
    first = _maxseq(tx)
    Wr = tx.rules.world
    area = _area(tx, turn_index)
    for r in tx.query("SELECT loop_id, holder_id, text FROM open_loops WHERE kind='plan' AND status='open' AND text LIKE 'Leave %' "
                      "AND created_at <= ? ORDER BY holder_id, loop_id", (at - Wr.defect_after_days * DAY,)):
        loop, actor, text = r[0], r[1], r[2]
        a = _row(tx, "SELECT * FROM actors WHERE actor_id=?", (actor,))
        b = _body(tx, actor)
        if a is None or a["controller"] == "human" or b is None or not b["alive"] or _place_of(tx, actor) in area:
            continue
        gs = [dict(x) for x in tx.query("SELECT g.group_id, g.name FROM group_members m JOIN groups g ON g.group_id=m.group_id "
                                        "WHERE m.actor_id=? AND m.status='member' ORDER BY g.group_id", (actor,))]
        g = next((x for x in gs if text.startswith(f"Leave {x['name']} ")), gs[0] if gs else None)
        if g is None:
            continue
        doss = _j(tx.query_one("SELECT baseline_json FROM dossiers WHERE actor_id=?", (actor,))[0], {})
        thr = (doss.get("motive") or {}).get("risk_threshold", 5)
        if defection_pressure(tx, actor, g["group_id"]).value < thr:
            continue
        dv = E(tx, EventType.DEFECTION, "society.group", at, turn_index,
               [W("group_members", {"status": "departed"}, WriteOp.UPDATE, {"group_id": g["group_id"], "actor_id": actor})],
               {"actor_id": actor, "group_id": g["group_id"], "loop_id": loop}, cause=cause, actor_id=actor)
        hh = household_of(tx, actor)
        if hh:
            apply_change(tx, hh, "member_left", actor, at, turn_index, dv.event_id)
        for w in tx.query("SELECT * FROM work_assignments WHERE actor_id=? ORDER BY workplace_id, role, shift_start_hh", (actor,)):
            w = dict(w)
            E(tx, EventType.ROLE_RELEASED, "society.work", at, turn_index,
              [W("work_assignments", {}, WriteOp.DELETE, {"workplace_id": w["workplace_id"], "actor_id": actor, "role": w["role"],
                                                         "shift_start_hh": w["shift_start_hh"]})],
              {"workplace_id": w["workplace_id"], "role": w["role"], "actor_id": actor, "shift_start_hh": w["shift_start_hh"],
               "covering_for": w["covering_for"], "reason": "left"}, cause=dv.event_id, actor_id=actor)
            sid = tx.query_one("SELECT settlement_id FROM workplaces WHERE workplace_id=?", (w["workplace_id"],))[0]
            if sid:
                stl.add_vacancy(tx, sid, w["workplace_id"], w["role"], actor, at, turn_index, dv.event_id)
        close_loop(tx, loop, "fulfilled", dv.event_id, at, turn_index)
        home = tx.query_one("SELECT s.place_id FROM settlements s WHERE s.group_id=? ORDER BY settlement_id LIMIT 1", (g["group_id"],))
        z0 = _zone_of_place(tx, home[0] if home else _place_of(tx, actor))
        far = _farthest_zone(tx, z0)
        hub = _hub_of_zone(tx, far) if far else None
        if hub and hub != _place_of(tx, actor):
            _move_to(tx, actor, hub, at, dv.event_id, turn_index)
    return _since(tx, first)


def _farthest_zone(tx, z0):
    edges = {}
    ext = {r[0] for r in tx.query("SELECT zone_id FROM zones WHERE kind='exterior'")}
    for r in tx.query("SELECT from_place, to_place FROM routes"):
        a, b = _zone_of_place(tx, r[0]), _zone_of_place(tx, r[1])
        if a in ext or b in ext:
            continue
        edges.setdefault(a, set()).add(b)
        edges.setdefault(b, set()).add(a)
    dist = {z0: 0}
    q = [z0]
    while q:
        u = q.pop(0)
        for v in sorted(edges.get(u, ())):
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    if len(dist) <= 1:
        return None
    return sorted(dist.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


# ------------------------------------------------------------------------------------------ wear (C02)
def exposed(store, place_id):
    r = store.query_one("SELECT indoor FROM places WHERE place_id=?", (place_id,))
    if r is None:
        raise ValueError(f"unknown place {place_id}")
    return r[0] == 0


def wet(store):
    return store.query_one("SELECT weather FROM world_clock WHERE id=1")[0] in ("rain", "storm", "snow")


def _wear(tx, it, cause, loss, at, turn_index, cause_event_id, *, spoiled=False):
    before = it["condition"]
    after = 0 if spoiled else max(0, before - loss)
    vals = {"condition": after}
    if spoiled:
        props = _j(it["props"], {})
        props["spoiled"] = True
        vals["props"] = props
    return E(tx, EventType.ITEM_WEAR, "physical.objects", at, turn_index,
             [W("items", vals, WriteOp.UPDATE, {"item_id": it["item_id"]})],
             {"item_id": it["item_id"], "cause": cause, "condition_before": before, "condition": after},
             cause=cause_event_id, place_id=it["place_id"])


def decay_day(tx, rng, at, turn_index, cause_event_id):
    from ..physical import objects
    first = _maxseq(tx)
    D = tx.rules.decay
    canon = _canon(tx)
    if wet(tx):
        for it in [dict(r) for r in tx.query("SELECT * FROM items WHERE place_id IS NOT NULL AND condition > 0 ORDER BY item_id")]:
            if not exposed(tx, it["place_id"]):
                continue
            kind = canon.get(it["def_ref"]).kind
            if kind in D.rust_kinds:
                cause, loss = "rust", D.rust_per_wet_day
            elif kind == "document":
                cause, loss = "pulp", D.pulp_per_wet_day
            elif kind in D.rot_kinds:
                cause, loss = "rot", D.rot_per_wet_day
            else:
                continue
            ev = _wear(tx, it, cause, loss, at, turn_index, cause_event_id)
            if kind == "document" and ev.payload["condition"] == 0:
                objects.destroy(tx, it["item_id"], at, ev.event_id, turn_index)
    for it in [dict(r) for r in tx.query("SELECT * FROM items ORDER BY item_id")]:
        d = canon.get(it["def_ref"])
        if d.food is None or d.food.spoil_days is None:
            continue
        props = _j(it["props"], {})
        if props.get("made_at") is None or props.get("spoiled"):
            continue
        if at - props["made_at"] >= d.food.spoil_days * DAY:
            _wear(tx, it, "spoiled", 0, at, turn_index, cause_event_id, spoiled=True)
    return _since(tx, first)


# ------------------------------------------------------------------------------------------ rumours retell (P10)
def retell(tx, rumour_id, holder_id, answer, at, turn_index):
    import re
    r = _row(tx, "SELECT * FROM rumours WHERE rumour_id=?", (rumour_id,))
    dist = _j(r["distortions"], [])
    if any(x.get("holder_id") == holder_id for x in dist):
        return None
    op, text = answer.operation, answer.retold_claim
    refused = op == "none"
    if not refused:
        known = {(x[0] or "").lower() for x in tx.query("SELECT known_name FROM acquaintance WHERE holder_id=?", (holder_id,))}
        kplaces = {x[0] for x in tx.query("SELECT place_id FROM known_places WHERE holder_id=?", (holder_id,))}
        low = text.lower()
        for x in tx.query("SELECT a.display_name FROM actors a JOIN bodies b ON b.body_id=a.actor_id WHERE b.alive=1"):
            nm = (x[0] or "").lower()
            if nm and re.search(r"\b" + re.escape(nm) + r"\b", low) and nm not in known:
                refused = True
                break
        if not refused:
            for x in tx.query("SELECT place_id, name FROM places"):
                nm = (x[1] or "").lower()
                if nm and re.search(r"\b" + re.escape(nm) + r"\b", low) and x[0] not in kplaces:
                    refused = True
                    break
    entry = {"holder_id": holder_id, "operation": "none" if refused else op, "text": None if refused else text}
    new = sorted(dist + [entry], key=lambda x: x["holder_id"])
    return E(tx, EventType.RUMOUR_DISTORTED, "world.rumours", at, turn_index,
             [W("rumours", {"distortions": new}, WriteOp.UPDATE, {"rumour_id": rumour_id})],
             {"rumour_id": rumour_id, "holder_id": holder_id, "operation": entry["operation"], "text": entry["text"]},
             actor_id=holder_id)
