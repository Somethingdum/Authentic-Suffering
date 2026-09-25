"""Implementation: action.effects handlers."""
from __future__ import annotations

import json
import math

from ..contracts.common import ANATOMY_GROUP, CheckBand, attr_mod
from ..contracts.content import CheckSpec
from ..contracts.events import Event, EventType


def _row(s, sql, p=()):
    r = s.query_one(sql, p)
    return dict(r) if r is not None else None


def _canon(tx):
    return tx.canon if getattr(tx, "canon", None) is not None else tx.store.canon


def _def(tx, def_id):
    return _canon(tx).find("affordance", def_id)


def _pos(tx, b):
    return _row(tx, "SELECT * FROM positions WHERE body_id=?", (b,))


def _body(tx, b):
    return _row(tx, "SELECT * FROM bodies WHERE body_id=?", (b,))


def _item(tx, i):
    r = _row(tx, "SELECT * FROM items WHERE item_id=?", (i,))
    if r:
        r["props"] = json.loads(r["props"]) if isinstance(r["props"], str) else r["props"]
    return r


def _idef(tx, item):
    return _canon(tx).get(item["def_ref"])


def _held(tx, actor):
    return [dict(r) for r in tx.query("SELECT * FROM items WHERE holder_body=? AND holder_slot IN ('hand_r','hand_l') ORDER BY holder_slot DESC", (actor,))]


def _free_hand(tx, actor):
    from ..physical.bodies import capacity
    if capacity(tx, actor).hands_free <= 0:
        return None
    used = {r["holder_slot"] for r in _held(tx, actor)}
    disabled = _disabled_hands(tx, actor)
    for h in ("hand_r", "hand_l"):
        if h not in used and h not in disabled:
            return h
    return None


def _disabled_hands(tx, actor):
    from ..contracts.common import ANATOMY_SIDE
    out = set()
    for w in tx.query("SELECT anatomy FROM wounds WHERE body_id=? AND healed_at IS NULL AND function_loss>=2", (actor,)):
        a = w[0]
        if ANATOMY_GROUP.get(a) in ("arm", "hand"):
            out.add("hand_" + ANATOMY_SIDE[a])
    return out


def _carries(tx, actor, item_id):
    it = _row(tx, "SELECT * FROM items WHERE item_id=?", (item_id,))
    seen = 0
    while it and seen < 10:
        if it["holder_body"] == actor:
            return True
        if it["container_id"]:
            it = _row(tx, "SELECT * FROM items WHERE item_id=?", (it["container_id"],))
        else:
            return False
        seen += 1
    return False


def _anchor(tx, a):
    return _row(tx, "SELECT * FROM anchors WHERE anchor_id=?", (a,))


def _portal(tx, p):
    return _row(tx, "SELECT * FROM portals WHERE portal_id=?", (p,))


def _place_centre(tx, place_id):
    pl = _row(tx, "SELECT width_m, depth_m FROM places WHERE place_id=?", (place_id,))
    return (pl["width_m"] / 2, pl["depth_m"] / 2)


def _noise(tx, intent, effect, db, at, ctx, *, point=None):
    from ..action.effects import NOISE_TEXT
    if db <= 0:
        return None
    pos = _pos(tx, intent.actor_id)
    if point is None:
        place, anchor, x, y = pos["place_id"], pos["anchor_id"], pos["x_m"], pos["y_m"]
    else:
        place, anchor, x, y = point
    pl = _row(tx, "SELECT indoor FROM places WHERE place_id=?", (place,))
    return tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", at=at, turn_index=ctx.turn_index,
                                 actor_id=intent.actor_id, cause_event_id=ctx.start_event_id, place_id=place,
                                 payload={"source_db": db, "kind": effect, "def_id": intent.bound.def_id, "text": NOISE_TEXT.get(effect, "a noise"),
                                          "place_id": place, "anchor_id": anchor, "x_m": x, "y_m": y, "outdoor": not pl["indoor"]}))


def _move(tx, actor, place, anchor, x, y, at, ctx, hidden=False):
    from ..physical.space import move_event
    before = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (actor,))
    ev = tx.commit_event(move_event(tx, actor, place, anchor, x, y, at, ctx.start_event_id, ctx.turn_index, hidden=hidden))
    if before is not None and before[0] != place:
        from ..world.worldmove import on_arrival
        on_arrival(tx, ctx.rng if hasattr(ctx, "rng") else _RNG[0], actor, place, at, ev.event_id, ctx.turn_index)
    return ev


def _walk_to(tx, intent, point, at, ctx, limit=1.0):
    """point = (place, anchor, x, y)."""
    pos = _pos(tx, intent.actor_id)
    place, anchor, x, y = point
    if pos["place_id"] == place and math.hypot(pos["x_m"] - x, pos["y_m"] - y) <= limit:
        return None
    return _move(tx, intent.actor_id, place, anchor, x, y, at, ctx)


def _anchor_point(tx, a):
    an = _anchor(tx, a)
    return (an["place_id"], a, an["x_m"], an["y_m"])


def _body_point(tx, b):
    p = _pos(tx, b)
    return (p["place_id"], p["anchor_id"], p["x_m"], p["y_m"])


def _item_point(tx, item_id):
    it = _item(tx, item_id)
    if it["place_id"]:
        if it["anchor_id"]:
            return _anchor_point(tx, it["anchor_id"])
        cx, cy = _place_centre(tx, it["place_id"])
        return (it["place_id"], None, cx, cy)
    if it["container_id"]:
        return _item_point(tx, it["container_id"])
    if it["holder_body"]:
        return _body_point(tx, it["holder_body"])
    return None


def _portal_side_point(tx, portal_id, place_id):
    from ..physical.space import portal_point
    p = _portal(tx, portal_id)
    anchor = p["anchor_a"] if p["place_a"] == place_id else p["anchor_b"]
    x, y = portal_point(tx, portal_id, place_id)
    return (place_id, anchor, x, y)


def _far(tx, portal_id, place_id):
    p = _portal(tx, portal_id)
    return p["place_b"] if p["place_a"] == place_id else p["place_a"]


# ------------------------------------------------------------------ situation / resistance
def situation(tx, intent, land_at):
    from ..sense.optics import light_at
    d = _def(tx, intent.bound.def_id)
    s = 0
    if d.check is not None and (str(d.check.attribute) in ("P",) or getattr(d.check.attribute, "value", None) == "P" or "ranged" in d.tags):
        subj = intent.bound.target_id if (intent.bound.target_id or "").startswith("act_") else intent.actor_id
        light = light_at(tx, subj, land_at)
        s += {0: -3, 1: -2, 2: -1}.get(light, 0)
    pace = getattr(intent, "pace", "normal")        # the explicit pace, never manner words (Actor Spec §14)
    if pace == "careful":
        s += 1
    if pace == "rushed" or intent.bound.def_id == "run_to_anchor":
        s -= 1
    if intent.bound.def_id == "force_portal" and any("pry" in _idef(tx, h).tags for h in _held(tx, intent.actor_id)):
        s += 1
    if intent.bound.def_id == "pick_lock":
        if any("lockpick" in _canon(tx).get(r[0]).tags for r in _carried_defs(tx, intent.actor_id)):
            s += 1
    t = intent.bound.target_id
    if "negotiable" in d.tags and t and t.startswith("act_"):
        r = tx.query_one("SELECT MAX(times_asked) FROM refusals WHERE actor_id=? AND requester_id=? AND status IN ('standing','reopened')",
                         (t, intent.actor_id))
        if r is not None and r[0]:
            from ..mind.firewall import negotiable_target_penalty
            s += negotiable_target_penalty(r[0])
    return max(-3, min(3, s))


def _carried_defs(tx, actor):
    out = []
    frontier = [r[0] for r in tx.query("SELECT item_id FROM items WHERE holder_body=?", (actor,))]
    while frontier:
        i = frontier.pop()
        it = _row(tx, "SELECT def_ref FROM items WHERE item_id=?", (i,))
        out.append((it["def_ref"],))
        frontier += [r[0] for r in tx.query("SELECT item_id FROM items WHERE container_id=?", (i,))]
    return out


def _moved_recently(tx, body, at):
    for r in tx.query("SELECT payload FROM events WHERE type='MOVE' AND actor_id=? AND at>? AND at<=?", (body, at - 1000, at)):
        if json.loads(r[0]).get("from_place") is not None:
            return True
    return False


def resistance(tx, intent, key, land_at):
    from ..action.effects import range_band
    from ..physical.space import point_distance
    if not key:
        return 0
    b = intent.bound
    if key == "range_band":
        d = point_distance(tx, intent.actor_id, b.target_id) or 0.0
        gun = _item(tx, b.item_id)
        rng_m = _idef(tx, gun).firearm.effective_range_m if gun else 50.0
        r = range_band(d, rng_m)
        tb = _body(tx, b.target_id)
        tp = _pos(tx, b.target_id)
        if tp["anchor_id"] and tb["posture"] in ("crouched", "prone"):
            r += _anchor(tx, tp["anchor_id"])["cover"]
        if _moved_recently(tx, b.target_id, land_at):
            r += 1
        if "head" in b.tags:
            r += 2
        return r
    if key.startswith("portal."):
        p = _portal(tx, b.target_id)
        if key == "portal.lock_quality":
            return p["lock_quality"]
        if key == "portal.barricade":
            return p["barricade"]
        if key == "portal.lock_and_barricade":
            return p["lock_quality"] + p["barricade"]
    if key.startswith("target.attr_mod."):
        letter = key.rsplit(".", 1)[1]
        return attr_mod(json.loads(_body(tx, b.target_id)["special"])[letter])
    if key == "obstacle.class":
        h = _portal(tx, b.target_id)["height_cm"]
        return 1 if h <= 120 else 3 if h <= 200 else 5
    if key == "wound.severity":
        w = _row(tx, "SELECT severity FROM wounds WHERE wound_id=?", (b.target_id,))
        return {"minor": 0, "significant": 1, "severe": 2, "catastrophic": 4}[w["severity"]]
    if key == "observer.best_perception":
        return _best_observer(tx, intent, land_at)
    raise ValueError(f"unknown resistance key {key}")


def _best_observer(tx, intent, land_at):
    """Highest attr_mod(P) among conscious bodies that can see the actor where it will stand."""
    from ..sense.optics import visibility
    actor = intent.actor_id
    pos = _pos(tx, actor)
    best = 0
    dest = intent.bound.destination_id
    for r in tx.query("SELECT body_id FROM positions WHERE place_id=? AND body_id!=? ORDER BY body_id", (pos["place_id"], actor)):
        o = r[0]
        ob = _body(tx, o)
        if not ob["alive"] or ob["awareness"] not in ("alert", "awake", "drowsy"):
            continue
        if visibility(tx, o, actor, land_at) == "none" and dest is None:
            continue
        v = attr_mod(json.loads(ob["special"])["P"])
        heard = tx.query_one("SELECT 1 FROM percept_log p JOIN events e ON e.event_id=p.event_id WHERE p.holder_id=? AND p.turn_index=? "
                             "AND p.channel IN ('auditory','speech') AND p.fidelity IN ('exact','partial')", (o, _turn(tx)))
        best = max(best, v + (1 if heard else 0))
    return best


def _turn(tx):
    from ..kernel.clock import turn_index
    return turn_index(tx)


# ------------------------------------------------------------------ legality
_DEAD_OK = {"smear_gore", "strip_clothing", "finish_downed", "watch_target", "infected_bite", "butcher_carcass"}


def _legal(tx, intent, land_at):
    from ..physical.bodies import capacity
    from ..physical.space import admits, point_distance
    from ..sense.optics import visibility
    b = intent.bound
    d = _def(tx, b.def_id)
    me = _body(tx, intent.actor_id)
    cap = capacity(tx, intent.actor_id)
    if not me["alive"] or not cap.conscious or (d.requires.mobile and not cap.mobile):
        return "incapable"
    pos = _pos(tx, intent.actor_id)
    t = b.target_id
    if t and t.startswith("act_"):
        tp = _pos(tx, t)
        if tp is None or tp["place_id"] != pos["place_id"]:
            ok = False
            if d.range == "visible" and visibility(tx, intent.actor_id, t, land_at) != "none":
                ok = True
            if d.range == "audible" and tp is not None and tx.query_one(
                    "SELECT 1 FROM portals WHERE is_open=1 AND ((place_a=? AND place_b=?) OR (place_a=? AND place_b=?))",
                    (pos["place_id"], tp["place_id"], tp["place_id"], pos["place_id"])):
                ok = True
            if not ok:
                return "target_gone"
        if d.range == "visible" and visibility(tx, intent.actor_id, t, land_at) == "none":
            return "target_gone"
        if not _body(tx, t)["alive"] and b.def_id not in _DEAD_OK:
            return "target_dead"
    if t and t.startswith("wnd_"):
        w = _row(tx, "SELECT body_id, healed_at FROM wounds WHERE wound_id=?", (t,))
        wp = _pos(tx, w["body_id"])
        if wp["place_id"] != pos["place_id"]:
            return "target_gone"
    if t and t.startswith("prt_"):
        p = _portal(tx, t)
        if pos["place_id"] not in (p["place_a"], p["place_b"]):
            return "target_gone"
    dest = b.destination_id
    if dest and dest.startswith("anc_") and d.binds not in ("item_reachable",) and _anchor(tx, dest)["place_id"] != pos["place_id"]:
        return "target_gone"
    # items
    if d.binds == "item_held" and b.item_id:
        it = _item(tx, b.item_id)
        if not it or it["holder_body"] != intent.actor_id or it["holder_slot"] not in ("hand_l", "hand_r"):
            return "item_gone"
    if d.binds == "item_carried" and b.item_id:
        if not _item(tx, b.item_id) or not _carries(tx, intent.actor_id, b.item_id):
            return "item_gone"
    if d.effect == "shoot" or d.effect == "strike_melee" and b.item_id:
        it = _item(tx, b.item_id) if b.item_id else None
        if b.item_id and (not it or it["holder_body"] != intent.actor_id or it["holder_slot"] not in ("hand_l", "hand_r")):
            return "item_gone"
    if d.binds == "item_reachable":
        it = _item(tx, t)
        if not it or it["place_id"] != pos["place_id"] or (dest and it["anchor_id"] != dest):
            return "item_gone"
    if d.effect == "take_from":
        it = _item(tx, b.item_id)
        if not it or it["container_id"] != t:
            return "item_gone"
    if d.effect == "put_into":
        it = _item(tx, b.item_id)
        if not it or it["holder_body"] != intent.actor_id:
            return "item_gone"
    if d.effect == "move_through_portal":
        p = _portal(tx, t)
        if not p["is_open"]:
            return "portal_closed"
        ok, _why = admits(tx, t, intent.actor_id)
        if not ok:
            return "not_admitted"
    if d.effect == "peek_portal" and _portal(tx, t)["is_open"]:
        return "portal_open"
    if d.range == "touch" and t and (t.startswith("act_") or t.startswith("wnd_")):
        tb = t if t.startswith("act_") else _row(tx, "SELECT body_id FROM wounds WHERE wound_id=?", (t,))["body_id"]
        if tb != intent.actor_id:
            dd = point_distance(tx, intent.actor_id, tb)
            if dd is None or dd > 1.5:
                return "out_of_reach"
    if d.effect in ("pick_up", "take_from", "equip") and _free_hand(tx, intent.actor_id) is None:
        return "hands_full"
    return None


# ------------------------------------------------------------------ the dispatcher
_RNG = [None]


def land(tx, rng, intent, land_at, ctx):
    from ..action.effects import Landing
    _RNG[0] = rng
    d = _def(tx, intent.bound.def_id)
    why = intent.blocked or _legal(tx, intent, land_at)
    if why:
        return Landing(result="blocked", blocked=why)
    h = HANDLERS[d.effect]
    return h(tx, rng, intent, land_at, ctx, d)


def _check(tx, rng, intent, d, land_at, ctx, *, spec=None, sit_delta=0, res_key=None):
    from ..action.checks import roll
    spec = spec or d.check
    return roll(tx, rng, intent.actor_id, intent.bound.def_id, spec,
                situation=max(-3, min(3, situation(tx, intent, land_at) + sit_delta)),
                resistance=resistance(tx, intent, res_key if res_key is not None else spec.resistance, land_at),
                at=land_at, turn_index=ctx.turn_index, cause_event_id=ctx.start_event_id)


def _cost_time(intent, land_at, band):
    if band == CheckBand.COST:
        return land_at + math.ceil(0.5 * intent.bound.est_duration_s * 1000)
    return None


def _done(result, band=None, complete_at=None):
    from ..action.effects import Landing
    return Landing(result=result, band=band, complete_at=complete_at)


# ---- movement
def h_move_to_anchor(tx, rng, intent, land_at, ctx, d):
    b = intent.bound
    hidden = False
    band = None
    if d.check is not None:
        r = _check(tx, rng, intent, d, land_at, ctx)
        band = r.band
        hidden = r.margin >= 3
    pl, an, x, y = _anchor_point(tx, b.destination_id)
    _move(tx, intent.actor_id, pl, an, x, y, land_at, ctx, hidden=hidden)
    _noise(tx, intent, "move_to_anchor", d.noise_db, land_at, ctx)
    return _done("done", band)


def h_move_through_portal(tx, rng, intent, land_at, ctx, d):
    from ..physical.space import admits
    b = intent.bound
    pos = _pos(tx, intent.actor_id)
    far = _far(tx, b.target_id, pos["place_id"])
    pl, an, x, y = _portal_side_point(tx, b.target_id, far)
    _move(tx, intent.actor_id, pl, an, x, y, land_at, ctx)
    _noise(tx, intent, "move_through_portal", d.noise_db, land_at, ctx)
    ok, why = admits(tx, b.target_id, intent.actor_id)
    if why == "crawl":
        walk_ms = math.ceil(max(0.0, intent.bound.est_duration_s - d.duration.base_s) * 1000)
        return _done("done", None, land_at + 3 * walk_ms)
    return _done("done")


def h_follow_body(tx, rng, intent, land_at, ctx, d):
    pl, an, x, y = _body_point(tx, intent.bound.target_id)
    _move(tx, intent.actor_id, pl, an, x, y, land_at, ctx)
    _noise(tx, intent, "follow_body", d.noise_db, land_at, ctx)
    return _done("done")


def _exits(tx, actor):
    from ..physical.space import admits
    pos = _pos(tx, actor)
    out = []
    for p in tx.query("SELECT * FROM portals WHERE (place_a=? OR place_b=?) AND kind NOT IN ('wall','fence') ORDER BY portal_id", (pos["place_id"], pos["place_id"])):
        p = dict(p)
        if not p["is_open"]:
            continue
        if not admits(tx, p["portal_id"], actor)[0]:
            continue
        near = _portal_side_point(tx, p["portal_id"], pos["place_id"])
        far = _portal_side_point(tx, p["portal_id"], _far(tx, p["portal_id"], pos["place_id"]))
        out.append((p["portal_id"], math.hypot(near[2] - pos["x_m"], near[3] - pos["y_m"]), far))
    return out


def h_leave_place(tx, rng, intent, land_at, ctx, d):
    ex = _exits(tx, intent.actor_id)
    if not ex:
        from ..action.effects import Landing
        return Landing(result="blocked", blocked="portal_closed")
    ex.sort(key=lambda e: (e[1], e[0]))
    pl, an, x, y = ex[0][2]
    _move(tx, intent.actor_id, pl, an, x, y, land_at, ctx)
    _noise(tx, intent, "leave_place", d.noise_db, land_at, ctx)
    return _done("done")


def h_flee(tx, rng, intent, land_at, ctx, d):
    from ..physical.space import distance_to_point
    threat = intent.bound.target_id
    ex = _exits(tx, intent.actor_id)
    if ex:
        def far_from_threat(e):
            pl, an, x, y = e[2]
            return -(_dist_body_point(tx, threat, pl, x, y))
        ex.sort(key=lambda e: (far_from_threat(e), e[0]))
        pl, an, x, y = ex[0][2]
    else:
        pos = _pos(tx, intent.actor_id)
        anchors = [dict(r) for r in tx.query("SELECT * FROM anchors WHERE place_id=? ORDER BY anchor_id", (pos["place_id"],))]
        if not anchors:
            from ..action.effects import Landing
            return Landing(result="blocked", blocked="portal_closed")
        anchors.sort(key=lambda a: (-_dist_body_point(tx, threat, a["place_id"], a["x_m"], a["y_m"]), a["anchor_id"]))
        a = anchors[0]
        pl, an, x, y = a["place_id"], a["anchor_id"], a["x_m"], a["y_m"]
    _move(tx, intent.actor_id, pl, an, x, y, land_at, ctx)
    _noise(tx, intent, "flee", d.noise_db, land_at, ctx)
    return _done("done")


def _dist_body_point(tx, body, place, x, y):
    from ..physical.space import distance_to_point
    v = distance_to_point(tx, body, place, x, y)
    return 999.0 if v is None else v


def h_climb(tx, rng, intent, land_at, ctx, d):
    from ..physical.bodies import WoundSpec, apply_harm, posture_event
    r = _check(tx, rng, intent, d, land_at, ctx)
    b = intent.bound
    p = _portal(tx, b.target_id)
    pos = _pos(tx, intent.actor_id)
    if r.band in (CheckBand.CLEAN, CheckBand.COST):
        far = _far(tx, b.target_id, pos["place_id"])
        pl, an, x, y = _portal_side_point(tx, b.target_id, far)
        _move(tx, intent.actor_id, pl, an, x, y, land_at, ctx)
        _noise(tx, intent, "climb", d.noise_db, land_at, ctx)
        if r.band == CheckBand.COST:
            apply_harm(tx, intent.actor_id, WoundSpec("hand_r", "cut", "minor", 0), land_at, ctx.start_event_id, ctx.turn_index, rng)
        return _done("done", r.band)
    _noise(tx, intent, "climb", d.noise_db, land_at, ctx)
    if r.band == CheckBand.FAIL:
        return _done("no_progress", r.band)
    sev = "significant" if p["height_cm"] > 200 else "minor"
    apply_harm(tx, intent.actor_id, WoundSpec("leg_l", "blunt", sev, 0), land_at, ctx.start_event_id, ctx.turn_index, rng)
    if _body(tx, intent.actor_id)["alive"] and _body(tx, intent.actor_id)["awareness"] not in ("unconscious", "dead"):
        posture_event(tx, intent.actor_id, "lying", land_at, ctx.start_event_id, ctx.turn_index)
    return _done("fell", r.band)


# ---- portals
def _pchange(tx, intent, changes, land_at, ctx):
    from ..physical.space import portal_change_event
    return tx.commit_event(portal_change_event(tx, intent.bound.target_id, changes, land_at, intent.actor_id, ctx.start_event_id, ctx.turn_index))


def _walk_portal(tx, intent, land_at, ctx):
    pos = _pos(tx, intent.actor_id)
    _walk_to(tx, intent, _portal_side_point(tx, intent.bound.target_id, pos["place_id"]), land_at, ctx)


def h_open_portal(tx, rng, intent, land_at, ctx, d):
    _walk_portal(tx, intent, land_at, ctx)
    p = _portal(tx, intent.bound.target_id)
    if p["is_locked"] or p["barricade"] > 0:
        return _done("blocked_by_lock")
    _pchange(tx, intent, {"is_open": True}, land_at, ctx)
    _noise(tx, intent, "open_portal", d.noise_db, land_at, ctx)
    return _done("done")


def h_close_portal(tx, rng, intent, land_at, ctx, d):
    _walk_portal(tx, intent, land_at, ctx)
    _pchange(tx, intent, {"is_open": False}, land_at, ctx)
    _noise(tx, intent, "close_portal", d.noise_db, land_at, ctx)
    return _done("done")


def _has_key(tx, actor):
    return any("key" in _canon(tx).get(r[0]).tags for r in _carried_defs(tx, actor))


def h_lock_portal(tx, rng, intent, land_at, ctx, d):
    _walk_portal(tx, intent, land_at, ctx)
    if not _has_key(tx, intent.actor_id):
        return _done("no_key")
    _pchange(tx, intent, {"is_locked": True}, land_at, ctx)
    _noise(tx, intent, "lock_portal", d.noise_db, land_at, ctx)
    return _done("done")


def h_unlock_portal(tx, rng, intent, land_at, ctx, d):
    _walk_portal(tx, intent, land_at, ctx)
    if intent.bound.def_id == "pick_lock":
        r = _check(tx, rng, intent, d, land_at, ctx)
        _noise(tx, intent, "unlock_portal", d.noise_db + (10 if r.band == CheckBand.COST else 0), land_at, ctx)
        if r.band in (CheckBand.CLEAN, CheckBand.COST):
            _pchange(tx, intent, {"is_locked": False}, land_at, ctx)
            return _done("done", r.band, _cost_time(intent, land_at, r.band))
        if r.band == CheckBand.BREAK:
            from ..physical.space import portal_change_event  # noqa: F401
            p = _portal(tx, intent.bound.target_id)
            _lock_quality_up(tx, intent, p, land_at, ctx)
            return _done("jammed", r.band)
        return _done("no_progress", r.band)
    if not _has_key(tx, intent.actor_id):
        return _done("no_key")
    _pchange(tx, intent, {"is_locked": False}, land_at, ctx)
    _noise(tx, intent, "unlock_portal", d.noise_db, land_at, ctx)
    return _done("done")


def _lock_quality_up(tx, intent, p, land_at, ctx):
    # lock_quality is not a portal_change key: a jam is recorded as damage + 0 (no state) in P5
    return None


def h_barricade(tx, rng, intent, land_at, ctx, d):
    _walk_portal(tx, intent, land_at, ctx)
    p = _portal(tx, intent.bound.target_id)
    _pchange(tx, intent, {"barricade": min(3, p["barricade"] + 1)}, land_at, ctx)
    _noise(tx, intent, "barricade_portal", d.noise_db, land_at, ctx)
    return _done("done")


def h_unbarricade(tx, rng, intent, land_at, ctx, d):
    _walk_portal(tx, intent, land_at, ctx)
    p = _portal(tx, intent.bound.target_id)
    _pchange(tx, intent, {"barricade": max(0, p["barricade"] - 1)}, land_at, ctx)
    _noise(tx, intent, "unbarricade_portal", d.noise_db, land_at, ctx)
    return _done("done")


def h_force(tx, rng, intent, land_at, ctx, d):
    from ..physical.bodies import WoundSpec, apply_harm
    _walk_portal(tx, intent, land_at, ctx)
    r = _check(tx, rng, intent, d, land_at, ctx)
    p = _portal(tx, intent.bound.target_id)
    _noise(tx, intent, "force_portal", d.noise_db + (10 if r.band == CheckBand.COST else 0), land_at, ctx)
    if r.band in (CheckBand.CLEAN, CheckBand.COST):
        _pchange(tx, intent, {"is_locked": False, "barricade": 0, "is_open": True, "damage": min(4, p["damage"] + 1)}, land_at, ctx)
        return _done("done", r.band, _cost_time(intent, land_at, r.band))
    if r.band == CheckBand.BREAK:
        apply_harm(tx, intent.actor_id, WoundSpec("arm_r", "blunt", "minor", 0), land_at, ctx.start_event_id, ctx.turn_index, rng)
    return _done("held", r.band)


def h_peek(tx, rng, intent, land_at, ctx, d):
    _walk_portal(tx, intent, land_at, ctx)
    _noise(tx, intent, "peek_portal", d.noise_db, land_at, ctx)
    return _done("peeked")


# ---- items
def _to_hand(tx, actor, hand):
    from ..physical.objects import Holder
    return Holder(kind="body", id=actor, slot=hand)


def h_pick_up(tx, rng, intent, land_at, ctx, d):
    from ..physical.objects import transfer
    _walk_to(tx, intent, _item_point(tx, intent.bound.target_id), land_at, ctx)
    hand = _free_hand(tx, intent.actor_id)
    transfer(tx, intent.bound.target_id, _to_hand(tx, intent.actor_id, hand), None, land_at, intent.actor_id, ctx.start_event_id, ctx.turn_index)
    _noise(tx, intent, "pick_up", d.noise_db, land_at, ctx)
    return _done("done")


def _floor(tx, actor):
    from ..physical.objects import Holder
    pos = _pos(tx, actor)
    return Holder(kind="place", id=pos["place_id"], anchor_id=pos["anchor_id"])


def h_drop(tx, rng, intent, land_at, ctx, d):
    from ..physical.objects import transfer
    transfer(tx, intent.bound.item_id, _floor(tx, intent.actor_id), None, land_at, intent.actor_id, ctx.start_event_id, ctx.turn_index)
    _noise(tx, intent, "drop_item", d.noise_db, land_at, ctx)
    return _done("done")


def h_give(tx, rng, intent, land_at, ctx, d):
    from ..physical.objects import transfer
    hand = _free_hand(tx, intent.bound.target_id)
    if hand is None:
        return _done("refused_full_hands")
    transfer(tx, intent.bound.item_id, _to_hand(tx, intent.bound.target_id, hand), None, land_at, intent.actor_id, ctx.start_event_id, ctx.turn_index)
    _noise(tx, intent, "give_item", d.noise_db, land_at, ctx)
    return _done("done")


def h_take_from(tx, rng, intent, land_at, ctx, d):
    from ..physical.objects import transfer
    _walk_to(tx, intent, _item_point(tx, intent.bound.target_id), land_at, ctx)
    hand = _free_hand(tx, intent.actor_id)
    transfer(tx, intent.bound.item_id, _to_hand(tx, intent.actor_id, hand), None, land_at, intent.actor_id, ctx.start_event_id, ctx.turn_index)
    _noise(tx, intent, "take_from", d.noise_db, land_at, ctx)
    return _done("done")


def h_put_into(tx, rng, intent, land_at, ctx, d):
    from ..physical.objects import Holder, transfer
    _walk_to(tx, intent, _item_point(tx, intent.bound.target_id), land_at, ctx)
    transfer(tx, intent.bound.item_id, Holder(kind="container", id=intent.bound.target_id), None, land_at, intent.actor_id, ctx.start_event_id, ctx.turn_index)
    _noise(tx, intent, "put_into", d.noise_db, land_at, ctx)
    return _done("done")


def h_search(tx, rng, intent, land_at, ctx, d):
    if intent.bound.target_id:
        _walk_to(tx, intent, _item_point(tx, intent.bound.target_id), land_at, ctx)
    _noise(tx, intent, d.effect, d.noise_db, land_at, ctx)
    return _done("searched")


def h_equip(tx, rng, intent, land_at, ctx, d):
    from ..physical.objects import transfer
    hand = _free_hand(tx, intent.actor_id)
    it = _item(tx, intent.bound.item_id)
    pu = {"holstered": None} if "holstered" in it["props"] else None
    transfer(tx, intent.bound.item_id, _to_hand(tx, intent.actor_id, hand), None, land_at, intent.actor_id, ctx.start_event_id, ctx.turn_index,
             props_update=pu)
    _noise(tx, intent, "equip", d.noise_db, land_at, ctx)
    return _done("done")


def h_holster(tx, rng, intent, land_at, ctx, d):
    from ..physical.objects import Holder, transfer
    it = _item(tx, intent.bound.item_id)
    idf = _idef(tx, it)
    if idf.firearm is not None or idf.melee is not None:
        transfer(tx, intent.bound.item_id, Holder(kind="body", id=intent.actor_id, slot="worn"), None, land_at, intent.actor_id,
                 ctx.start_event_id, ctx.turn_index, props_update={"holstered": True})
    else:
        transfer(tx, intent.bound.item_id, Holder(kind="body", id=intent.actor_id, slot="pack"), None, land_at, intent.actor_id,
                 ctx.start_event_id, ctx.turn_index)
    _noise(tx, intent, "holster", d.noise_db, land_at, ctx)
    return _done("done")


def h_reload(tx, rng, intent, land_at, ctx, d):
    from ..physical.objects import Holder, transfer
    gun = _item(tx, intent.bound.item_id)
    fd = _idef(tx, gun).firearm
    extra = 0
    if fd.feeds_from == "magazine":
        cur = [dict(r) for r in tx.query("SELECT * FROM items WHERE container_id=?", (gun["item_id"],))]
        best = None
        for (i,) in _carried_items(tx, intent.actor_id):
            it = _item(tx, i)
            if it["container_id"] == gun["item_id"]:
                continue
            idf = _idef(tx, it)
            if idf.kind == "magazine" and fd.caliber in idf.tags:
                r = int(it["props"].get("rounds", 0))
                if best is None or r > best[0] or (r == best[0] and i < best[1]):
                    best = (r, i)
        if best is None:
            return _done("no_ammo")
        for m in cur:
            transfer(tx, m["item_id"], Holder(kind="body", id=intent.actor_id, slot="pack"), None, land_at, intent.actor_id, ctx.start_event_id, ctx.turn_index)
        transfer(tx, best[1], Holder(kind="container", id=gun["item_id"]), None, land_at, intent.actor_id, ctx.start_event_id, ctx.turn_index)
        from ..physical.objects import chamber
        chamber(tx, gun["item_id"], land_at, intent.actor_id, ctx.start_event_id, ctx.turn_index)
    else:
        n = int(gun["props"].get("rounds", 0))
        need = fd.capacity - n
        loaded = 0
        for (i,) in _carried_items(tx, intent.actor_id):
            if need <= 0:
                break
            it = _item(tx, i)
            idf = _idef(tx, it)
            if idf.kind == "ammo" and fd.caliber in idf.tags:
                take = min(need, it["qty"])
                from ..physical.objects import destroy
                destroy(tx, i, land_at, ctx.start_event_id, ctx.turn_index, qty=take)
                need -= take
                loaded += take
        if loaded == 0:
            return _done("no_ammo")
        from ..physical.objects import load_rounds
        load_rounds(tx, gun["item_id"], n + loaded, land_at, intent.actor_id, ctx.start_event_id, ctx.turn_index)
        extra = max(0, loaded * 2000 - math.ceil(intent.bound.est_duration_s * 1000))
    _noise(tx, intent, "reload", d.noise_db, land_at, ctx)
    return _done("done", None, land_at + extra if extra else None)


def _carried_items(tx, actor):
    out = []
    frontier = [r[0] for r in tx.query("SELECT item_id FROM items WHERE holder_body=? ORDER BY item_id", (actor,))]
    while frontier:
        i = frontier.pop(0)
        out.append((i,))
        frontier += [r[0] for r in tx.query("SELECT item_id FROM items WHERE container_id=? ORDER BY item_id", (i,))]
    return out




def h_throw(tx, rng, intent, land_at, ctx, d):
    from ..physical.objects import Holder, transfer
    pl, an, x, y = _anchor_point(tx, intent.bound.destination_id)
    transfer(tx, intent.bound.item_id, Holder(kind="place", id=pl, anchor_id=an), None, land_at, intent.actor_id, ctx.start_event_id, ctx.turn_index)
    _noise(tx, intent, "throw_distraction", 70, land_at, ctx, point=(pl, an, x, y))
    return _done("done")


def h_eat(tx, rng, intent, land_at, ctx, d):
    from ..physical.bodies import expose, refresh_need, stages
    from ..physical.objects import contaminate, contaminated, destroy
    c = contaminated(tx, intent.bound.item_id, land_at)
    if c and c.get("lasting"):
        expose(tx, rng, intent.actor_id, c["pathway"], "tainted_food" if d.effect == "eat" else "tainted_water", land_at,
               ctx.start_event_id, ctx.turn_index)
    if True:      # P10: mouth contact (lore 3.2); I1/D-77: food as well as drink
        if c and not c.get("lasting") and c["by"] != intent.actor_id:
            expose(tx, rng, intent.actor_id, c["pathway"], "mouth_contact_item", land_at, ctx.start_event_id, ctx.turn_index)
        if any(pw == "wet" and st.saliva_infectious for pw, st in stages(tx, intent.actor_id)):
            contaminate(tx, intent.bound.item_id, "wet", intent.actor_id, land_at, ctx.start_event_id, ctx.turn_index)
    src = _row(tx, "SELECT props FROM items WHERE item_id=?", (intent.bound.item_id,))
    plate = (json.loads(src["props"]) if src and isinstance(src["props"], str) else (src["props"] if src else {}) or {}).get("refills")
    destroy(tx, intent.bound.item_id, land_at, ctx.start_event_id, ctx.turn_index, qty=1)
    if plate:                                        # D-102: the endless plate — eating is the only way to a new one
        refill(tx, rng, plate, land_at, ctx.start_event_id, ctx.turn_index)
    refresh_need(tx, intent.actor_id, "hunger" if d.effect == "eat" else "thirst", land_at, ctx.start_event_id, ctx.turn_index)
    _noise(tx, intent, d.effect, d.noise_db, land_at, ctx)
    return _done("ate" if d.effect == "eat" else "drank")


# ---- combat
def _wound(tx, rng, intent, target, anatomy, wtype, severity, land_at, ctx, contamination=0):
    from ..physical.bodies import WoundSpec, apply_harm
    return apply_harm(tx, target, WoundSpec(anatomy, wtype, severity, contamination), land_at, ctx.start_event_id, ctx.turn_index, rng)


def _splash(tx, rng, intent, target, evs, land_at, ctx):
    from ..physical.bodies import contagious, expose
    harm = next((e for e in evs if e.type == EventType.HARM), None)
    if harm is None or harm.payload["severity"] not in ("significant", "severe", "catastrophic"):
        return evs
    if contagious(tx, target):
        expose(tx, rng, intent.actor_id, "wet", "fluid_splash", land_at, harm.event_id, ctx.turn_index)
    from ..physical.bodies import soil
    if _body(tx, target)["kind"] == "infected":
        soil(tx, intent.actor_id, gore=1, source="splashed", at=land_at, cause_event_id=harm.event_id, turn_index=ctx.turn_index)
    else:
        soil(tx, intent.actor_id, blood=1, source="splashed", at=land_at, cause_event_id=harm.event_id, turn_index=ctx.turn_index)
    return evs


def _centre_mass(tx, rng, actor, target):
    from ..action.effects import CENTRE_MASS
    return rng.weighted(tx, "resolve", f"anatomy:{actor}:{target}", list(CENTRE_MASS))


def _severity(klass, band, anatomy, *, firearm, margin=0):
    from ..action.effects import WEAPON_WOUNDS
    sev = WEAPON_WOUNDS[klass]["clean" if band == CheckBand.CLEAN else "cost"]
    if band == CheckBand.CLEAN and anatomy in ("head", "neck"):
        if firearm and klass == "medium":
            sev = "catastrophic"
        if not firearm and klass == "heavy" and margin >= 6:
            sev = "catastrophic"
    return sev


def h_shoot(tx, rng, intent, land_at, ctx, d, *, sit_delta=0, target=None, stray=False):
    from ..physical.objects import fire
    b = intent.bound
    target = target or b.target_id
    gun = _item(tx, b.item_id)
    fd = _idef(tx, gun).firearm
    if not stray:
        shot, ev = fire(tx, b.item_id, land_at, intent.actor_id, ctx.start_event_id, ctx.turn_index)
        if not shot:
            _noise(tx, intent, "click", 20, land_at, ctx)
            from ..action.effects import NOISE_TEXT  # noqa: F401
            return _done("click")
        _noise(tx, intent, "shoot", fd.noise_db, land_at, ctx)
    if target != b.target_id:
        import dataclasses
        from .intent import Intent  # noqa: F401
        intent = dataclasses.replace(intent, bound=dataclasses.replace(b, target_id=target))
    r = _check(tx, rng, intent, d, land_at, ctx, sit_delta=sit_delta)
    if r.band in (CheckBand.CLEAN, CheckBand.COST):
        if "head" in d.tags:
            anatomy = "head"
        elif "leg" in d.tags:
            anatomy = rng.choice(tx, "resolve", f"leg:{intent.actor_id}:{target}", ["leg_l", "leg_r"])
        else:
            anatomy = _centre_mass(tx, rng, intent.actor_id, target)
        sev = _severity(fd.damage_class, r.band, anatomy, firearm=True)
        if "leg" in d.tags and sev == "minor":
            sev = "significant"
        hev = _wound(tx, rng, intent, target, anatomy, "gunshot", sev, land_at, ctx, 1)
        if "leg" in d.tags:
            from ..physical.bodies import posture_event
            bt = _body(tx, target)
            if bt["alive"] and bt["awareness"] in ("alert", "awake", "drowsy"):
                posture_event(tx, target, "lying", land_at, hev[0].event_id, ctx.turn_index)
        return _done("hit", r.band)
    if r.band == CheckBand.BREAK and not stray:
        tp = _pos(tx, target)
        near = []
        for rr in tx.query("SELECT p.body_id, p.x_m, p.y_m FROM positions p JOIN bodies b ON b.body_id=p.body_id WHERE p.place_id=? AND b.alive=1 ORDER BY p.body_id", (tp["place_id"],)):
            if rr[0] in (intent.actor_id, target):
                continue
            if math.hypot(rr[1] - tp["x_m"], rr[2] - tp["y_m"]) <= 1.0:
                near.append(rr[0])
        if near:
            h_shoot(tx, rng, intent, land_at, ctx, d, sit_delta=-2, target=near[0], stray=True)
    return _done("miss", r.band)


def _opp_spec(spec):
    return CheckSpec(attribute=spec.opposed_attribute or spec.attribute, skill=spec.opposed_skill)


def _can_defend(tx, body):
    from ..physical.bodies import capacity
    c = capacity(tx, body)
    return c.conscious and c.mobile


def h_strike(tx, rng, intent, land_at, ctx, d):
    from ..action.checks import opposed
    from ..physical.bodies import grips_on, posture_event
    from ..physical.space import point_distance
    b = intent.bound
    t = b.target_id
    weapon = _item(tx, b.item_id) if b.item_id else None
    md = _idef(tx, weapon).melee if weapon else None
    if d.range == "reach":
        reach = md.reach_m if md else 0.5
        dd = point_distance(tx, intent.actor_id, t) or 0.0
        if dd > reach:
            pl, an, x, y = _body_point(tx, t)
            _move(tx, intent.actor_id, pl, an, x, y, land_at, ctx)
    if "bite" in d.tags:
        tb0 = _body(tx, t)
        if tb0["alive"] and intent.actor_id not in grips_on(tx, t):
            return _done("no_grip")
        from ..world import infected as _inf
        n = tx.query_one("SELECT COUNT(*) FROM events h JOIN events c ON c.event_id = h.cause_event_id WHERE h.type='HARM' "
                         "AND json_extract(h.payload,'$.body_id')=? AND json_extract(h.payload,'$.type')='bite' AND c.actor_id=?",
                         (t, intent.actor_id))[0]
        anatomy = rng.weighted(tx, "resolve", f"feed:{intent.actor_id}:{t}:{n}", list(_inf.FEED_ANATOMY))
        sev = "significant" if (n == 0 and tb0["alive"]) else "severe"
        hev = _wound(tx, rng, intent, t, anatomy, "bite", sev, land_at, ctx, 2)[0]
        from ..physical.bodies import expose
        if tb0["alive"]:
            expose(tx, rng, t, "wet", "bite", land_at, hev.event_id, ctx.turn_index)
            tb1 = _body(tx, t)
            if tb1["alive"] and tb1["kind"] == "human" and tb1["awareness"] in ("alert", "awake", "drowsy"):
                tp = _pos(tx, t)
                sc = tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", at=land_at, turn_index=ctx.turn_index,
                                           actor_id=t, cause_event_id=hev.event_id, place_id=tp["place_id"],
                                           payload={"source_db": tx.rules.infected.scream_db, "kind": "screaming",
                                                    "text": "someone screaming", "place_id": tp["place_id"],
                                                    "x_m": tp["x_m"], "y_m": tp["y_m"]}))
                _inf.draw_to_feed(tx, t, intent.actor_id, land_at, sc.event_id, ctx.turn_index)
        _inf.feed(tx, intent.actor_id, land_at, hev.event_id, ctx.turn_index)
        _inf.taint_water(tx, t, intent.actor_id, land_at, hev.event_id, ctx.turn_index)
        _noise(tx, intent, "strike_melee", d.noise_db, land_at, ctx)
        return _done("hit")
    if b.def_id == "finish_downed":
        klass = md.damage_class if md else "light"
        sev = "catastrophic" if klass in ("medium", "heavy") else "severe"
        _splash(tx, rng, intent, t, _wound(tx, rng, intent, t, "head", md.wound_types[0] if md else "blunt", sev, land_at, ctx), land_at, ctx)
        _noise(tx, intent, "strike_melee", md.noise_db if md else d.noise_db, land_at, ctx)
        return _done("hit")
    spec = d.check
    if spec.opposed and _can_defend(tx, t):
        w, ra, rb, how = opposed(tx, rng, intent.actor_id, spec, t, _opp_spec(spec), def_id=b.def_id,
                                 a_situation=situation(tx, intent, land_at), b_situation=0, at=land_at, turn_index=ctx.turn_index,
                                 cause_event_id=ctx.start_event_id)
        won = w == intent.actor_id
        band = (CheckBand.CLEAN if how == "clean" else CheckBand.COST) if won else (CheckBand.BREAK if (rb.margin - ra.margin) >= 3 else CheckBand.FAIL)
        margin = ra.margin
    else:
        r = _check(tx, rng, intent, d, land_at, ctx, res_key="")
        band, margin = r.band, r.margin
        won = band in (CheckBand.CLEAN, CheckBand.COST)
    _noise(tx, intent, "strike_melee", (md.noise_db if md else d.noise_db) + (10 if band == CheckBand.COST and won else 0), land_at, ctx)
    if not won:
        if band == CheckBand.BREAK:
            posture_event(tx, intent.actor_id, "crouched", land_at, ctx.start_event_id, ctx.turn_index)
            return _done("miss", band)
        return _done("miss", band)
    anatomy = "head" if "head" in d.tags else _centre_mass(tx, rng, intent.actor_id, t)
    if "unarmed" in d.tags:
        if band == CheckBand.CLEAN:
            _wound(tx, rng, intent, t, anatomy, "blunt", "minor", land_at, ctx)
        return _done("hit", band)
    klass = md.damage_class if md else "light"
    sev = _severity(klass, band, anatomy, firearm=False, margin=margin)
    _splash(tx, rng, intent, t, _wound(tx, rng, intent, t, anatomy, md.wound_types[0] if md else "blunt", sev, land_at, ctx), land_at, ctx)
    return _done("hit", band)


def _contest(tx, rng, intent, d, land_at, ctx, a_attr, a_skill, b_attr, b_skill, *, control=None):
    from ..action.checks import opposed
    a = CheckSpec(attribute=a_attr, skill=a_skill, tags=list(d.check.tags) if d.check else [])
    bb = CheckSpec(attribute=b_attr, skill=b_skill)
    w, ra, rb, how = opposed(tx, rng, intent.actor_id, a, intent.bound.target_id, bb, def_id=intent.bound.def_id,
                             a_situation=situation(tx, intent, land_at), b_situation=0, at=land_at, turn_index=ctx.turn_index,
                             cause_event_id=ctx.start_event_id, established_control=control)
    return w == intent.actor_id, how


def h_grapple(tx, rng, intent, land_at, ctx, d):
    from ..physical.bodies import grip_event
    t = intent.bound.target_id
    if _can_defend(tx, t):
        won, how = _contest(tx, rng, intent, d, land_at, ctx, "S", "brawling", "A", "brawling")
    else:
        won, how = True, "clean"
    _noise(tx, intent, "grapple", d.noise_db, land_at, ctx)
    if won:
        if not tx.query_one("SELECT 1 FROM grips WHERE holder_id=? AND target_id=?", (intent.actor_id, t)):
            grip_event(tx, intent.actor_id, t, land_at, ctx.start_event_id, ctx.turn_index)
        return _done("grabbed", CheckBand.CLEAN if how == "clean" else CheckBand.COST)
    return _done("slipped", CheckBand.FAIL)


def h_break_grip(tx, rng, intent, land_at, ctx, d):
    from ..physical.bodies import release_event
    t = intent.bound.target_id
    if not tx.query_one("SELECT 1 FROM grips WHERE holder_id=? AND target_id=?", (t, intent.actor_id)):
        return _done("free")
    won, how = _contest(tx, rng, intent, d, land_at, ctx, "S", "brawling", "S", "brawling", control=t)
    _noise(tx, intent, "break_grip", d.noise_db, land_at, ctx)
    if won:
        release_event(tx, t, intent.actor_id, land_at, ctx.start_event_id, ctx.turn_index)
        return _done("broke_free", CheckBand.CLEAN if how == "clean" else CheckBand.COST)
    return _done("held", CheckBand.FAIL)


def h_shove(tx, rng, intent, land_at, ctx, d):
    from ..physical.bodies import posture_event
    t = intent.bound.target_id
    won, how = _contest(tx, rng, intent, d, land_at, ctx, "S", "brawling", "S", None) if _can_defend(tx, t) else (True, "clean")
    _noise(tx, intent, "shove", d.noise_db, land_at, ctx)
    if won:
        if _body(tx, t)["awareness"] not in ("unconscious", "dead"):
            posture_event(tx, t, "lying", land_at, ctx.start_event_id, ctx.turn_index)
        return _done("knocked_down", CheckBand.CLEAN if how == "clean" else CheckBand.COST)
    return _done("braced", CheckBand.FAIL)


def h_shove_toward(tx, rng, intent, land_at, ctx, d):
    import math as _m
    from ..physical.bodies import posture_event
    from ..physical.space import move_event, point_distance
    from ..world.infected import active, attract
    t = intent.bound.target_id
    won, how = _contest(tx, rng, intent, d, land_at, ctx, "S", "brawling", "A", "athletics") if _can_defend(tx, t) else (True, "clean")
    _noise(tx, intent, "shove", d.noise_db, land_at, ctx)
    if not won:
        return _done("braced", CheckBand.FAIL)
    band = CheckBand.CLEAN if how == "clean" else CheckBand.COST
    tp = _pos(tx, t)
    cands = []
    for r in tx.query("SELECT p.body_id FROM positions p JOIN bodies b ON b.body_id=p.body_id WHERE p.place_id=? "
                      "AND b.kind='infected' AND p.body_id != ? ORDER BY p.body_id", (tp["place_id"], t)):
        if active(tx, r[0]):
            dd = point_distance(tx, t, r[0])
            if dd is not None:
                cands.append((dd, r[0]))
    conscious = _body(tx, t)["awareness"] not in ("unconscious", "dead")
    if not cands:
        if conscious:
            posture_event(tx, t, "lying", land_at, ctx.start_event_id, ctx.turn_index)
        return _done("knocked_down", band)
    dist, dead = min(cands)
    dp = _pos(tx, dead)
    s = min(2.0, max(0.0, dist - 0.5))
    x, y = tp["x_m"], tp["y_m"]
    if dist > 0:
        x, y = x + (dp["x_m"] - x) / dist * s, y + (dp["y_m"] - y) / dist * s
    mv = tx.commit_event(move_event(tx, t, tp["place_id"], None, x, y, land_at, ctx.start_event_id, ctx.turn_index))
    if conscious:
        posture_event(tx, t, "lying", land_at, ctx.start_event_id, ctx.turn_index)
    attract(tx, dead, t, land_at, mv.event_id, ctx.turn_index, reason="sight")
    return _done("shoved_to_the_dead", band)


def h_butcher(tx, rng, intent, land_at, ctx, d):
    import json as _j
    from ..contracts.events import WriteOp as _WO, WriteRecord as _WR
    from ..physical.objects import Holder, contaminate, create
    t = intent.bound.target_id
    b = _body(tx, t)
    special = _j.loads(b["special"]) if isinstance(b["special"], str) else (b["special"] or {})
    blade = any("blade" in _idef(tx, it).tags for it in _held(tx, intent.actor_id))
    if b is None or b["kind"] != "animal" or b["alive"] or special.get("butchered") or not blade:
        return _done("nothing_to_butcher")
    an = tx.canon.get(b["content_ref"])
    pos = _pos(tx, t)
    meat = None
    if an.meat_portions > 0:
        ev = create(tx, "core:item/raw_meat", an.meat_portions, Holder(kind="place", id=pos["place_id"], anchor_id=pos["anchor_id"]),
                    "craft", {}, land_at, ctx.start_event_id, ctx.turn_index)
        meat = ev.payload["item_id"]
    tx.commit_event(Event(type=EventType.BODY_CONDITION, writer="physical.bodies", at=land_at, turn_index=ctx.turn_index,
                          actor_id=t, cause_event_id=ctx.start_event_id,
                          writes=[_WR(op=_WO.UPDATE, table="bodies", key={"body_id": t}, values={"special": {**special, "butchered": True}})],
                          payload={"body_id": t, "butchered": True}))
    first = tx.query_one("SELECT c.actor_id FROM events h JOIN events c ON c.event_id = h.cause_event_id WHERE h.type='HARM' "
                         "AND json_extract(h.payload,'$.body_id')=? AND json_extract(h.payload,'$.type')='bite' ORDER BY h.seq LIMIT 1", (t,))
    if meat and first and first[0]:
        contaminate(tx, meat, "wet", first[0], land_at, ctx.start_event_id, ctx.turn_index, lasting=True)
    from ..physical.bodies import soil
    soil(tx, intent.actor_id, blood=2, source="butchered", at=land_at, cause_event_id=ctx.start_event_id, turn_index=ctx.turn_index)
    _noise(tx, intent, "butcher", d.noise_db, land_at, ctx)
    return _done("butchered")


def _all_mine(tx, body):
    out = []
    todo = [r[0] for r in tx.query("SELECT item_id FROM items WHERE holder_body=?", (body,))]
    while todo:
        i = todo.pop(0)
        out.append(_item(tx, i))
        todo += [r[0] for r in tx.query("SELECT item_id FROM items WHERE container_id=?", (i,))]
    return out


def h_spit(tx, rng, intent, land_at, ctx, d):
    from ..physical.bodies import expose
    from ..physical.objects import contaminate
    from ..physical.space import point_distance
    b = intent.bound
    if b.def_id == "spit_into":
        it = _item(tx, b.item_id)
        ok = it is not None and (it["holder_body"] == intent.actor_id and it["holder_slot"] in ("hand_l", "hand_r"))
        if it is not None and not ok and it["place_id"]:
            pos = _pos(tx, intent.actor_id)
            if it["anchor_id"]:
                ap = tx.query_one("SELECT x_m, y_m FROM anchors WHERE anchor_id=?", (it["anchor_id"],))
                x, y = ap[0], ap[1]
            else:
                pl = tx.query_one("SELECT width_m, depth_m FROM places WHERE place_id=?", (it["place_id"],))
                x, y = pl[0] / 2, pl[1] / 2
            ok = it["place_id"] == pos["place_id"] and math.hypot(x - pos["x_m"], y - pos["y_m"]) <= 1.5
        if not ok:
            return _done("missed")
        contaminate(tx, b.item_id, "wet", intent.actor_id, land_at, ctx.start_event_id, ctx.turn_index)
        return _done("spat")
    tb = _body(tx, b.target_id)
    dd = point_distance(tx, intent.actor_id, b.target_id)
    if tb is None or tb["awareness"] != "asleep" or dd is None or dd > 1.5:
        return _done("missed")
    expose(tx, rng, b.target_id, "wet", "mouth_contact_direct", land_at, ctx.start_event_id, ctx.turn_index)
    return _done("spat")


def h_disarm(tx, rng, intent, land_at, ctx, d):
    from ..physical.objects import transfer
    t = intent.bound.target_id
    won, how = _contest(tx, rng, intent, d, land_at, ctx, "A", "brawling", "A", "brawling") if _can_defend(tx, t) else (True, "clean")
    _noise(tx, intent, "disarm", d.noise_db, land_at, ctx)
    if not won:
        return _done("held_on", CheckBand.FAIL)
    held = _held(tx, t)
    weapons = [h for h in held if _idef(tx, h).firearm is not None] + [h for h in held if _idef(tx, h).firearm is None and _idef(tx, h).melee is not None]
    if not weapons:
        return _done("nothing_to_take", CheckBand.CLEAN if how == "clean" else CheckBand.COST)
    transfer(tx, weapons[0]["item_id"], _floor(tx, t), None, land_at, intent.actor_id, ctx.start_event_id, ctx.turn_index)
    return _done("disarmed", CheckBand.CLEAN if how == "clean" else CheckBand.COST)


# ---- posture / cover
def h_take_cover(tx, rng, intent, land_at, ctx, d):
    from ..physical.bodies import posture_event
    band = None
    hidden = False
    if d.effect == "hide":
        r = _check(tx, rng, intent, d, land_at, ctx)
        band = r.band
        hidden = r.margin >= 1
    pl, an, x, y = _anchor_point(tx, intent.bound.destination_id)
    _move(tx, intent.actor_id, pl, an, x, y, land_at, ctx, hidden=hidden)
    posture_event(tx, intent.actor_id, "crouched", land_at, ctx.start_event_id, ctx.turn_index)
    _noise(tx, intent, d.effect, d.noise_db, land_at, ctx)
    return _done("done", band)


def h_posture(tx, rng, intent, land_at, ctx, d):
    from ..physical.bodies import posture_event
    posture_event(tx, intent.actor_id, {"crouch": "crouched", "stand": "standing", "go_prone": "prone"}[d.effect], land_at,
                  ctx.start_event_id, ctx.turn_index)
    _noise(tx, intent, d.effect, d.noise_db, land_at, ctx)
    return _done("done")


def h_hold(tx, rng, intent, land_at, ctx, d):
    from ..physical.bodies import posture_event
    if d.effect == "sleep":
        posture_event(tx, intent.actor_id, "lying", land_at, ctx.start_event_id, ctx.turn_index, awareness="asleep")
    elif d.effect == "rest":
        posture_event(tx, intent.actor_id, "sitting", land_at, ctx.start_event_id, ctx.turn_index)
    return _done("holding")


def h_continue(tx, rng, intent, land_at, ctx, d):
    from .tasks import active_task, advance
    advance(tx, intent.actor_id, ctx.horizon_ms, ctx.turn_index)
    t = _row(tx, "SELECT status FROM tasks WHERE actor_id=? ORDER BY started_at DESC, task_id DESC LIMIT 1", (intent.actor_id,))
    _noise(tx, intent, "continue_task", d.noise_db, land_at, ctx)
    if active_task(tx, intent.actor_id) is None and t and t["status"] == "done":
        return _done("task_done")
    return _done("working")


def h_speak(tx, rng, intent, land_at, ctx, d):
    from ..mind.actor import adjust_stress
    if d.check is None:
        return _done("said")
    r = _check(tx, rng, intent, d, land_at, ctx)
    t = intent.bound.target_id
    if tx.query_one("SELECT 1 FROM actors WHERE actor_id=?", (t,)):
        delta = {CheckBand.CLEAN: -2, CheckBand.COST: -1, CheckBand.FAIL: 0, CheckBand.BREAK: 1}[r.band]
        adjust_stress(tx, t, delta, ctx.start_event_id, land_at, ctx.turn_index)
    return _done("said", r.band)


def h_signal(tx, rng, intent, land_at, ctx, d):
    return _done("signalled")


def h_surrender(tx, rng, intent, land_at, ctx, d):
    from ..physical.bodies import posture_event
    from ..physical.objects import transfer
    for h in sorted(_held(tx, intent.actor_id), key=lambda r: r["holder_slot"]):
        transfer(tx, h["item_id"], _floor(tx, intent.actor_id), None, land_at, intent.actor_id, ctx.start_event_id, ctx.turn_index)
    posture_event(tx, intent.actor_id, "crouched", land_at, ctx.start_event_id, ctx.turn_index)
    _noise(tx, intent, "surrender", d.noise_db, land_at, ctx)
    return _done("surrendered")


_TREAT = ("pressure", "bandage", "suture", "clean", "packing")


def h_treat(tx, rng, intent, land_at, ctx, d):
    from ..physical.bodies import treat
    w = _row(tx, "SELECT * FROM wounds WHERE wound_id=?", (intent.bound.target_id,))
    if w["healed_at"] is not None:
        return _done("nothing_to_treat")
    method = "tourniquet" if d.effect == "apply_tourniquet" else next(t for t in d.tags if t in _TREAT)
    band = None
    if method == "suture" and d.check is not None:
        r = _check(tx, rng, intent, d, land_at, ctx)
        band = r.band
        if r.band in (CheckBand.FAIL, CheckBand.BREAK):
            return _done("no_progress", band)
    try:
        tev = treat(tx, w["body_id"], w["wound_id"], method, intent.actor_id, land_at, ctx.start_event_id, ctx.turn_index)
    except ValueError:
        return _done("cannot_treat", band)
    from ..physical.bodies import contagious, expose
    if tev is not None and w["body_id"] != intent.actor_id and contagious(tx, w["body_id"]):
        expose(tx, rng, intent.actor_id, "wet", "fluid_contact", land_at, tev.event_id, ctx.turn_index)
    if tev is not None and w["body_id"] != intent.actor_id and w["severity"] != "minor":
        from ..physical.bodies import soil
        soil(tx, intent.actor_id, blood=1, source="treated", at=land_at, cause_event_id=tev.event_id, turn_index=ctx.turn_index)
    _noise(tx, intent, d.effect, d.noise_db, land_at, ctx)
    return _done("done", band, _cost_time(intent, land_at, band) if band else None)


def _stow(tx, actor):
    from ..physical.objects import Holder
    hand = _free_hand(tx, actor)
    return _to_hand(tx, actor, hand) if hand else Holder(kind="body", id=actor, slot="pack")


def _adult(tx, body_id):
    a = _body(tx, body_id)["age_years"]
    return a is not None and a >= 18


def _bare_after(tx, body_id, off=(), on=None):
    covers = set()
    for o in _worn_clothes(tx, body_id):
        if o["item_id"] in off:
            continue
        covers |= set(o["clothing"]["covers"])
    if on is not None:
        covers |= set(_idef(tx, _item(tx, on)).clothing.covers)
    return not ({"torso", "groin"} <= covers)


def _worn_clothes(tx, body_id):
    from ..physical.objects import worn
    return [o for o in worn(tx, body_id) if o["clothing"]]


def h_wash(tx, rng, intent, land_at, ctx, d):
    from ..physical.bodies import expose, wash
    from ..physical.objects import contaminated, destroy
    it = _item(tx, intent.bound.item_id)
    ml = _idef(tx, it).water.ml
    c = contaminated(tx, it["item_id"], land_at)
    if c and c.get("by") != intent.actor_id:
        expose(tx, rng, intent.actor_id, c["pathway"], "fluid_contact", land_at, ctx.start_event_id, ctx.turn_index)
    destroy(tx, it["item_id"], land_at, ctx.start_event_id, ctx.turn_index, qty=1)
    full = ml >= tx.rules.condition.wash_full_ml
    wash(tx, intent.actor_id, full=full, at=land_at, cause_event_id=ctx.start_event_id, turn_index=ctx.turn_index)
    _noise(tx, intent, "wash", d.noise_db, land_at, ctx)
    return _done("washed" if full else "wiped")


def h_smear(tx, rng, intent, land_at, ctx, d):
    from ..physical.bodies import expose, soil
    from ..physical.space import point_distance
    t = intent.bound.target_id
    tb = _body(tx, t)
    dd = point_distance(tx, intent.actor_id, t)
    if tb["kind"] != "infected" or tb["alive"] or dd is None or dd > 1.5:
        return _done("nothing_to_smear")
    ev = soil(tx, intent.actor_id, gore=tx.rules.condition.smear_gore, blood=1, grime=1, source="smeared", at=land_at,
              cause_event_id=ctx.start_event_id, turn_index=ctx.turn_index)
    import json as _j
    open_wound = any("bandage" not in _j.loads(w["treatment"] or "[]")
                     for w in tx.query("SELECT treatment FROM wounds WHERE body_id=? AND healed_at IS NULL", (intent.actor_id,)))
    expose(tx, rng, intent.actor_id, "wet", "gore_in_wound" if open_wound else "gore_smear", land_at,
           ev.event_id if ev is not None else ctx.start_event_id, ctx.turn_index)
    _noise(tx, intent, "smear", d.noise_db, land_at, ctx)
    return _done("smeared")


def h_take_off(tx, rng, intent, land_at, ctx, d):
    from ..physical.objects import transfer
    iid = intent.bound.item_id
    if not _adult(tx, intent.actor_id) and _bare_after(tx, intent.actor_id, off=(iid,)):
        return _done("kept_on")
    transfer(tx, iid, _stow(tx, intent.actor_id), None, land_at, intent.actor_id, ctx.start_event_id, ctx.turn_index)
    _noise(tx, intent, "take_off", d.noise_db, land_at, ctx)
    return _done("took_off")


def h_change_into(tx, rng, intent, land_at, ctx, d):
    from ..physical.objects import Holder, location_of, transfer
    iid = intent.bound.item_id
    cl = _idef(tx, _item(tx, iid)).clothing
    off = sorted(o["item_id"] for o in _worn_clothes(tx, intent.actor_id)
                 if o["clothing"]["slot"] == cl.slot and o["clothing"]["layer"] == cl.layer)
    if not _adult(tx, intent.actor_id) and _bare_after(tx, intent.actor_id, off=off, on=iid):
        return _done("kept_on")
    was = location_of(tx, iid)
    transfer(tx, iid, Holder(kind="body", id=intent.actor_id, slot="worn"), None, land_at, intent.actor_id,
             ctx.start_event_id, ctx.turn_index)
    for o in off:
        dest = was if (was.kind == "body" and was.slot in ("hand_l", "hand_r")
                       and not tx.query_one("SELECT 1 FROM items WHERE holder_body=? AND holder_slot=?", (was.id, was.slot))) \
            else Holder(kind="body", id=intent.actor_id, slot="pack")
        transfer(tx, o, dest, None, land_at, intent.actor_id, ctx.start_event_id, ctx.turn_index)
    _noise(tx, intent, "change_into", d.noise_db, land_at, ctx)
    return _done("changed")


def h_strip(tx, rng, intent, land_at, ctx, d):
    from ..physical.objects import transfer
    from ..physical.space import point_distance
    t = intent.bound.target_id
    tb = _body(tx, t)
    it = _item(tx, intent.bound.item_id) if intent.bound.item_id else None
    still = (not tb["alive"]) or tb["awareness"] == "unconscious" or tb["false_dead_until"] is not None
    dd = point_distance(tx, intent.actor_id, t)
    if (tb["kind"] != "human" or not _adult(tx, t) or not still or dd is None or dd > 1.5
            or it is None or it["holder_body"] != t or it["holder_slot"] != "worn"):
        return _done("kept_on")
    transfer(tx, it["item_id"], _stow(tx, intent.actor_id), None, land_at, intent.actor_id, ctx.start_event_id, ctx.turn_index)
    _noise(tx, intent, "strip", d.noise_db, land_at, ctx)
    return _done("stripped")


# ---- P12 (D-102): Willis's wonders — no check, nothing stops them
def h_wonder_smite(tx, rng, intent, land_at, ctx, d):
    from ..physical.bodies import excepted, kill
    t = intent.bound.target_id
    b = _body(tx, t)
    if b is None or not b["alive"] or excepted(tx, t):
        return _done("unmoved")
    kill(tx, t, "wonder", land_at, ctx.turn_index, rng, cause_event_id=ctx.start_event_id)
    return _done("smitten")


def h_wonder_hurt(tx, rng, intent, land_at, ctx, d):
    from ..action.effects import CENTRE_MASS
    t = intent.bound.target_id
    b = _body(tx, t)
    if b is None or not b["alive"]:
        return _done("unmoved")
    anatomy = rng.weighted(tx, "resolve", f"wonder_hurt:{intent.actor_id}:{ctx.start_event_id}", list(CENTRE_MASS))
    _wound(tx, rng, intent, t, anatomy, "blunt", "severe", land_at, ctx)
    return _done("hurt")


def h_wonder_gift(tx, rng, intent, land_at, ctx, d):
    from ..physical.objects import Holder, create
    t = intent.bound.target_id
    canon = _canon(tx)
    gifts = sorted(r for r in canon.refs("item") if "willis_gift" in canon.get(r).tags)
    if not gifts or _body(tx, t) is None:
        return _done("nothing")
    ref = rng.choice(tx, "loot", f"wonder_gift:{intent.actor_id}:{ctx.start_event_id}", gifts)
    mine = _body(tx, intent.actor_id)["origin"]
    origin = mine if mine in ("cheat", "wildcard") else "cheat"
    to = {t}
    for g in tx.query("SELECT group_id FROM group_members WHERE actor_id=? AND status='member' ORDER BY group_id", (t,)):
        for m in tx.query("SELECT m.actor_id FROM group_members m JOIN bodies b ON b.body_id=m.actor_id "
                          "WHERE m.group_id=? AND m.status='member' AND b.alive=1", (g[0],)):
            to.add(m[0])
    free = [s for s in ("hand_r", "hand_l")
            if _row(tx, "SELECT 1 FROM items WHERE holder_body=? AND holder_slot=?", (t, s)) is None]
    if free:
        holder = Holder("body", t, free[0])
    else:
        p = _pos(tx, t)
        holder = Holder("place", p["place_id"], anchor_id=p["anchor_id"])
    create(tx, ref, 1, holder, origin, {"gift_from": intent.actor_id, "gift_to": sorted(to)}, land_at,
           ctx.start_event_id, ctx.turn_index)
    return _done("given")


def h_wonder_vanish(tx, rng, intent, land_at, ctx, d):
    from ..physical.space import place_body, remove_body
    me = intent.actor_id
    here = _pos(tx, me)["place_id"]
    places = [r[0] for r in tx.query("SELECT place_id FROM places WHERE parent_id IS NULL AND place_id != ? ORDER BY place_id",
                                     (here,))]
    if not places:
        return _done("stayed")
    to = rng.choice(tx, "resolve", f"wonder_vanish:{me}:{ctx.start_event_id}", places)
    remove_body(tx, me, land_at, ctx.start_event_id, ctx.turn_index)
    a = _row(tx, "SELECT anchor_id, x_m, y_m FROM anchors WHERE place_id=? ORDER BY anchor_id LIMIT 1", (to,))
    if a is not None:
        place_body(tx, me, to, a["anchor_id"], a["x_m"], a["y_m"], land_at, ctx.start_event_id, ctx.turn_index)
    else:
        p = _row(tx, "SELECT width_m, depth_m FROM places WHERE place_id=?", (to,))
        place_body(tx, me, to, None, p["width_m"] / 2, p["depth_m"] / 2, land_at, ctx.start_event_id, ctx.turn_index)
    return _done("gone")


def refill(tx, rng, container_id, at, cause_event_id, turn_index):
    from ..physical.objects import Holder, create
    c = _row(tx, "SELECT def_ref, origin FROM items WHERE item_id=?", (container_id,))
    if c is None:
        return None
    canon = _canon(tx)
    tags = canon.get(c["def_ref"]).tags
    tag = next((x.split(":", 1)[1] for x in tags if x.startswith("refill:")), None)
    if "endless" not in tags or not tag:
        return None
    if _row(tx, "SELECT 1 FROM items WHERE container_id=?", (container_id,)) is not None:
        return None
    pool = sorted(r for r in canon.refs("item") if tag in canon.get(r).tags)
    if not pool:
        return None
    ref = rng.choice(tx, "loot", f"refill:{container_id}:{cause_event_id}", pool)
    return create(tx, ref, 1, Holder("container", container_id), c["origin"], {"refills": container_id}, at,
                  cause_event_id, turn_index)


HANDLERS = {
    "move_to_anchor": h_move_to_anchor, "move_through_portal": h_move_through_portal, "follow_body": h_follow_body,
    "leave_place": h_leave_place, "flee": h_flee, "climb": h_climb,
    "open_portal": h_open_portal, "close_portal": h_close_portal, "lock_portal": h_lock_portal, "unlock_portal": h_unlock_portal,
    "barricade_portal": h_barricade, "unbarricade_portal": h_unbarricade, "force_portal": h_force, "peek_portal": h_peek,
    "pick_up": h_pick_up, "drop_item": h_drop, "give_item": h_give, "take_from": h_take_from, "put_into": h_put_into,
    "search_container": h_search, "search_place": h_search, "equip": h_equip, "holster": h_holster, "reload": h_reload,
    "strike_melee": h_strike, "shoot": h_shoot, "grapple": h_grapple, "break_grip": h_break_grip, "shove": h_shove, "shove_toward": h_shove_toward, "butcher": h_butcher, "spit": h_spit, "wash": h_wash, "smear": h_smear, "take_off": h_take_off,
    "change_into": h_change_into, "strip": h_strip,
    "disarm": h_disarm, "take_cover": h_take_cover, "hide": h_take_cover, "crouch": h_posture, "stand": h_posture,
    "go_prone": h_posture, "observe": h_hold, "wait": h_hold, "guard": h_hold, "sleep": h_hold, "rest": h_hold,
    "continue_task": h_continue, "speak": h_speak, "signal": h_signal, "surrender": h_surrender,
    "treat_wound": h_treat, "apply_tourniquet": h_treat, "eat": h_eat, "drink": h_eat, "throw_distraction": h_throw,
    "wonder_smite": h_wonder_smite, "wonder_hurt": h_wonder_hurt, "wonder_gift": h_wonder_gift, "wonder_vanish": h_wonder_vanish,
}


def _register_all():
    from .effects import EFFECTS
    for eid, h in HANDLERS.items():
        EFFECTS[eid] = (lambda tx, rng, i, la, ctx, _h=h: _h(tx, rng, i, la, ctx, _def(tx, i.bound.def_id)))


_register_all()
