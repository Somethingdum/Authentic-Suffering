"""Implementation: mind.affordance.enumerate_affordances."""
from __future__ import annotations

import json
import math

from ..contracts.common import ANATOMY_GROUP, Verb, age_band_for
from .affordance import AffordanceSet, BoundAffordance, Rejection, duration_words

MOVE_OUT = {"move_through_portal", "leave_place", "flee_threat", "climb_obstacle"}
_ANAT = {"head": "head", "neck": "neck", "chest": "chest", "abdomen": "belly", "back": "back", "arm_l": "left arm", "arm_r": "right arm",
         "hand_l": "left hand", "hand_r": "right hand", "leg_l": "left leg", "leg_r": "right leg", "foot_l": "left foot", "foot_r": "right foot"}
ATTACK_GROUP_VERBS = {Verb.ATTACK}
THREAT_GROUP_VERBS = {Verb.TAKE_COVER, Verb.HIDE, Verb.FLEE, Verb.ESCAPE, Verb.SURRENDER}
_GROUP_RANK_OBS = {Verb.OBSERVE, Verb.WAIT, Verb.GUARD}


def _row(s, sql, params=()):
    r = s.query_one(sql, params)
    return dict(r) if r is not None else None


class Ctx:
    pass


def _ctx(tx, actor_id, at, turn_index):
    from . import perception as P
    from ..physical import bodies
    from ._impl_p4a import fused
    c = Ctx()
    c.tx, c.me, c.at, c.turn = tx, actor_id, at, turn_index
    c.canon = tx.canon if getattr(tx, "canon", None) is not None else tx.store.canon
    c.body = _row(tx, "SELECT * FROM bodies WHERE body_id=?", (actor_id,))
    c.pos = _row(tx, "SELECT * FROM positions WHERE body_id=?", (actor_id,))
    c.place = c.pos["place_id"]
    c.actor = _row(tx, "SELECT * FROM actors WHERE actor_id=?", (actor_id,))
    c.dossier = fused(tx, actor_id)
    c.cap = bodies.capacity(tx, actor_id)
    c.skills = {s.domain.value if hasattr(s.domain, "value") else s.domain: s.rank for s in c.dossier.capability.skills}
    c.cues = set()
    for r in tx.query("SELECT cue_tags FROM lessons WHERE holder_id=? AND confidence>=1", (actor_id,)):
        c.cues |= set(json.loads(r[0]))
    c.wont = set(c.dossier.motive.moral_line.wont_tags)
    # known bodies
    c.known_bodies = []
    c.seen_clear = set()
    for r in tx.query("SELECT source_id, channel, detail FROM percept_log WHERE holder_id=? AND turn_index=? AND at<=? "
                      "AND source_id IS NOT NULL ORDER BY at, percept_id", (actor_id, turn_index, at)):   # SKULL-10
        sid = r[0]
        if not tx.query_one("SELECT 1 FROM bodies WHERE body_id=?", (sid,)) or sid == actor_id:
            continue
        lvl = json.loads(r[2]).get("level")
        if r[1] == "visual" and lvl == "clear":
            c.seen_clear.add(sid)
        if sid not in c.known_bodies:
            c.known_bodies.append(sid)
    c.known_items = []
    for r in tx.query("SELECT DISTINCT source_id FROM percept_log WHERE holder_id=? AND turn_index=? AND at<=? "
                      "AND source_id LIKE 'itm_%'", (actor_id, turn_index, at)):
        c.known_items.append((r[0], None))
    anchors = [dict(r) for r in tx.query("SELECT * FROM anchors WHERE place_id=? ORDER BY anchor_id", (c.place,))]
    c.anchors = anchors
    anchor_ids = {a["anchor_id"] for a in anchors}
    for r in tx.query("SELECT p.subject_id, p.object_value FROM claim_holdings h JOIN propositions p ON p.prop_id=h.claim_id "
                      "WHERE h.holder_id=? AND h.superseded_by IS NULL AND h.believed=1 AND p.subject_type='object' AND p.predicate='location'", (actor_id,)):
        if r[0] and (r[1] in anchor_ids or r[1] == c.place):
            c.known_items.append((r[0], r[1] if r[1] in anchor_ids else None))
    c.portals = [dict(r) for r in tx.query("SELECT * FROM portals WHERE (place_a=? OR place_b=?) AND kind!='wall' ORDER BY portal_id", (c.place, c.place))]
    # inventory
    c.held = [dict(r) for r in tx.query("SELECT * FROM items WHERE holder_body=? AND holder_slot IN ('hand_l','hand_r') ORDER BY holder_slot, item_id", (actor_id,))]
    c.carried = []

    def walk(iid, in_held_firearm):
        for ch in tx.query("SELECT * FROM items WHERE container_id=? ORDER BY item_id", (iid,)):
            ch = dict(ch)
            if in_held_firearm:
                continue
            c.carried.append(ch)
            walk(ch["item_id"], False)
    for r in tx.query("SELECT * FROM items WHERE holder_body=? ORDER BY item_id", (actor_id,)):
        r = dict(r)
        d = c.canon.get(r["def_ref"])
        if r["holder_slot"] not in ("hand_l", "hand_r"):
            c.carried.append(r)
        walk(r["item_id"], d.firearm is not None and r["holder_slot"] in ("hand_l", "hand_r"))
    c.all_mine = c.held + c.carried
    # threats
    c.threats = []
    for b in c.known_bodies:
        k = _row(tx, "SELECT kind FROM bodies WHERE body_id=?", (b,))["kind"]
        attacked = False
        for e in tx.query("SELECT e.type, e.payload, p.detail FROM events e JOIN percept_log p ON p.event_id=e.event_id "
                          "WHERE p.holder_id=? AND e.actor_id=? AND p.turn_index=? AND p.at<=?", (actor_id, b, turn_index, at)):
            pl = json.loads(e[1]) if isinstance(e[1], str) else e[1]
            dt = json.loads(e[2])
            if e[0] == "HARM" or (e[0] == "ACTION_START" and pl.get("verb") == "attack") or (e[0] == "SPEECH" and dt.get("armed_at_me")):
                attacked = True
        if k == "infected" or attacked:
            c.threats.append(b)
    c.task = _row(tx, "SELECT * FROM tasks WHERE actor_id=? AND status='active' ORDER BY task_id LIMIT 1", (actor_id,))
    hh = [r[0] for r in tx.query("SELECT household_id FROM household_members WHERE actor_id=?", (actor_id,))]
    c.household = {r[0] for r in tx.query(f"SELECT actor_id FROM household_members WHERE household_id IN ({','.join('?'*len(hh))})", hh)} - {actor_id} if hh else set()
    c.guardian_of = set()
    for r in tx.query("SELECT guardian_of FROM household_members WHERE actor_id=?", (actor_id,)):
        c.guardian_of |= set(json.loads(r[0]))
    c.groups = {r[0] for r in tx.query("SELECT group_id FROM group_members WHERE actor_id=?", (actor_id,))}
    c.P = P
    return c


def _dist_pt(c, x, y):
    return math.hypot(c.pos["x_m"] - x, c.pos["y_m"] - y)


def _body_ref(c, b):
    from . import perception as P
    n = c.tx.query_one("SELECT known_name FROM acquaintance WHERE holder_id=? AND subject_id=?", (c.me, b))
    if n and n[0]:
        return n[0]
    return P.with_article(P.describe(c.tx, c.me, b))


def _item_name(c, iid):
    it = _row(c.tx, "SELECT def_ref, qty FROM items WHERE item_id=?", (iid,))
    if not it:
        return "thing"
    d = c.canon.get(it["def_ref"])
    return d.plural if it["qty"] > 1 else d.name


def _is_mine(c, iid):
    return any(i["item_id"] == iid for i in c.all_mine)


def _target_kinds(c, b):
    r = _row(c.tx, "SELECT kind, age_years FROM bodies WHERE body_id=?", (b,))
    ks = [r["kind"]]
    if r["kind"] == "human" and r["age_years"] is not None:
        ks.append(age_band_for(r["age_years"]).value)
    return ks


def _still(c, b):
    r = _row(c.tx, "SELECT alive, awareness, posture, false_dead_until FROM bodies WHERE body_id=?", (b,))
    return r["posture"] in ("lying", "prone") and (not r["alive"] or r["awareness"] in ("unconscious", "dead") or r["false_dead_until"] is not None)


def _tags_of(c, iid):
    it = _row(c.tx, "SELECT def_ref FROM items WHERE item_id=?", (iid,))
    return set(c.canon.get(it["def_ref"]).tags) if it else set()


def _bindings(c, d):
    """Yield dicts: target_id, destination_id, item_id, dist (walk metres), kind ('body'|'item'|...)"""
    from ..physical import space
    b = d.binds
    eff = d.effect
    out = []
    if b in ("none", "self"):
        if d.id == "keep_working" and not c.task:
            return []
        if d.id == "surrender" and not c.threats:
            return []
        out.append({})
    elif b == "anchor":
        for a in c.anchors:
            if a["anchor_id"] == c.pos["anchor_id"] and eff == "move_to_anchor":
                continue
            if d.id == "take_cover" and a["cover"] < 1:
                continue
            if d.id == "hide" and a["concealment"] < 1:
                continue
            out.append({"destination_id": a["anchor_id"], "dist": _dist_pt(c, a["x_m"], a["y_m"])})
    elif b == "portal":
        for p in c.portals:
            f = d.id
            if f == "open_portal" and not (p["is_open"] == 0 and p["barricade"] == 0 and p["kind"] != "fence"):
                continue
            if f == "close_portal" and not p["is_open"]:
                continue
            if f in ("lock_portal", "unlock_portal", "pick_lock") and not (p["kind"] in ("door", "gate", "window") and p["is_open"] == 0):
                continue
            if f == "barricade_portal" and not (p["is_open"] == 0 and p["barricade"] < 3 and p["kind"] != "fence"):
                continue
            if f == "unbarricade_portal" and not p["barricade"] > 0:
                continue
            if f == "force_portal" and not (p["is_open"] == 0 and p["kind"] != "fence"):
                continue
            if f == "climb_obstacle" and not p["height_cm"] > 0:
                continue
            if f == "peek_portal" and not (p["is_open"] == 0 and p["kind"] != "fence"):
                continue
            if f == "move_through_portal" and p["kind"] == "fence":
                continue
            pt = space.portal_point(c.tx, p["portal_id"], c.place)
            other = p["place_b"] if p["place_a"] == c.place else p["place_a"]
            out.append({"target_id": p["portal_id"], "destination_id": other if f in ("move_through_portal", "climb_obstacle") else None,
                        "dist": _dist_pt(c, *pt)})
    elif b == "body":
        cands = c.threats if d.id == "flee_threat" else c.known_bodies
        if d.id == "shield_dependent":
            if not c.threats:
                return []
            fond = {r[0] for r in c.tx.query("SELECT to_id FROM relationships WHERE from_id=? AND affection>=1", (c.me,))}
            cands = [t for t in c.known_bodies if t not in c.threats and (t in c.guardian_of or t in c.household or t in fond)]
        for t in cands:
            dist = space.point_distance(c.tx, c.me, t) or 0.0
            if d.id.startswith("shoot_"):
                for it in c.held:
                    if c.canon.get(it["def_ref"]).firearm is not None:
                        out.append({"target_id": t, "item_id": it["item_id"], "dist": dist})
            elif d.id in ("strike_melee", "strike_head", "finish_downed"):
                for it in c.held:
                    if c.canon.get(it["def_ref"]).melee is not None:
                        out.append({"target_id": t, "item_id": it["item_id"], "dist": dist})
            elif eff == "strip":
                tb = _row(c.tx, "SELECT kind, age_years FROM bodies WHERE body_id=?", (t,))
                if tb["kind"] != "human" or tb["age_years"] is None or tb["age_years"] < 18:
                    continue
                from ..physical.objects import CLOTHING_LAYER_ORDER, worn
                ws = [o for o in worn(c.tx, t) if o["clothing"]]
                for o in ws:
                    li = CLOTHING_LAYER_ORDER.index(o["clothing"]["layer"])
                    if any(p["clothing"]["slot"] == o["clothing"]["slot"] and CLOTHING_LAYER_ORDER.index(p["clothing"]["layer"]) < li
                           for p in ws):
                        continue
                    out.append({"target_id": t, "item_id": o["item_id"], "dist": dist})
            else:
                out.append({"target_id": t, "dist": dist})
    elif b == "item_held":
        for it in c.held:
            if d.id == "give_item":
                for t in c.known_bodies:
                    dist = space.point_distance(c.tx, c.me, t) or 0.0
                    if dist <= 1.5:
                        out.append({"item_id": it["item_id"], "target_id": t, "dist": dist})
            elif d.id == "throw_distraction":
                if c.canon.get(it["def_ref"]).bulk <= 3 and c.canon.get(it["def_ref"]).firearm is None:
                    for a in c.anchors:
                        dd = _dist_pt(c, a["x_m"], a["y_m"])
                        if dd <= 15 and a["anchor_id"] != c.pos["anchor_id"]:
                            out.append({"item_id": it["item_id"], "destination_id": a["anchor_id"], "dist": 0.0})
            elif d.effect == "end_own_life":   # D-107: only the held thing that can do it
                if set(d.requires.held_item_tags) <= _tags_of(c, it["item_id"]):
                    out.append({"item_id": it["item_id"], "dist": 0.0})
            elif d.id == "reload_firearm":
                fd = c.canon.get(it["def_ref"]).firearm
                if fd is None:
                    continue
                for m in c.carried:
                    md = c.canon.get(m["def_ref"])
                    if fd.caliber in md.tags and md.kind in ("magazine", "ammo"):
                        out.append({"item_id": it["item_id"], "target_id": m["item_id"], "dist": 0.0})
            else:
                out.append({"item_id": it["item_id"], "dist": 0.0})
    elif b == "item_carried":
        for it in c.carried:
            dd = c.canon.get(it["def_ref"])
            if eff == "eat" and dd.food is None:
                continue
            if eff == "drink" and dd.water is None:
                continue
            if eff == "equip" and (dd.kind == "clothing" or (dd.container is not None and dd.container.worn)):
                continue
            if eff == "wash" and dd.water is None:
                continue
            if eff == "take_off" and not (dd.clothing is not None and it.get("holder_slot") == "worn" and it.get("holder_body") == c.me):
                continue
            if eff == "change_into" and not (dd.clothing is not None and it.get("holder_slot") != "worn"):
                continue
            if eff in ("take_off", "change_into") and not _f1c_adult(c):
                from ..physical.objects import worn as _worn
                ws = [o for o in _worn(c.tx, c.me) if o["clothing"]]
                if eff == "take_off":
                    cov = {x for o in ws if o["item_id"] != it["item_id"] for x in o["clothing"]["covers"]}
                else:
                    cov = {x for o in ws if not (o["clothing"]["slot"] == dd.clothing.slot and o["clothing"]["layer"] == dd.clothing.layer)
                           for x in o["clothing"]["covers"]} | set(dd.clothing.covers)
                if not {"torso", "groin"} <= cov:
                    continue
            out.append({"item_id": it["item_id"], "dist": 0.0})
        if eff == "change_into":
            for it in c.held:
                dd = c.canon.get(it["def_ref"])
                if dd.clothing is None:
                    continue
                if not _f1c_adult(c):
                    from ..physical.objects import worn as _worn
                    ws = [o for o in _worn(c.tx, c.me) if o["clothing"]]
                    cov = {x for o in ws if not (o["clothing"]["slot"] == dd.clothing.slot and o["clothing"]["layer"] == dd.clothing.layer)
                           for x in o["clothing"]["covers"]} | set(dd.clothing.covers)
                    if not {"torso", "groin"} <= cov:
                        continue
                out.append({"item_id": it["item_id"], "dist": 0.0})
    elif b == "item_reachable":
        for iid, anc in c.known_items:
            r = _row(c.tx, "SELECT * FROM items WHERE item_id=?", (iid,))
            if _is_mine(c, iid):
                continue
            if anc is None and r and r["place_id"] != c.place:
                continue
            if anc:
                a = _row(c.tx, "SELECT x_m, y_m FROM anchors WHERE anchor_id=?", (anc,))
                dist = _dist_pt(c, a["x_m"], a["y_m"])
            elif r and r["anchor_id"]:
                a = _row(c.tx, "SELECT x_m, y_m FROM anchors WHERE anchor_id=?", (r["anchor_id"],))
                dist = _dist_pt(c, a["x_m"], a["y_m"])
            else:
                dist = 0.0
            out.append({"target_id": iid, "destination_id": anc, "dist": dist})
    elif b == "container":
        conts = [i for i in c.carried if c.canon.get(i["def_ref"]).container is not None]
        for iid, anc in c.known_items:
            r = _row(c.tx, "SELECT * FROM items WHERE item_id=?", (iid,))
            if r and r["place_id"] == c.place and c.canon.get(r["def_ref"]).container is not None:
                conts.append(r)
        for ct in conts:
            if d.id == "put_into_container":
                for it in c.held:
                    if it["item_id"] != ct["item_id"]:
                        out.append({"target_id": ct["item_id"], "item_id": it["item_id"], "dist": 0.0})
            elif d.id == "take_from_container":
                for ch in c.tx.query("SELECT item_id FROM items WHERE container_id=? ORDER BY item_id", (ct["item_id"],)):
                    if _is_mine(c, ct["item_id"]) or any(ch[0] == k for k, _ in c.known_items):
                        out.append({"target_id": ct["item_id"], "item_id": ch[0], "dist": 0.0})
            else:
                out.append({"target_id": ct["item_id"], "dist": 0.0})
    elif b == "speech":
        out.append({})
        for t in c.known_bodies:
            if _row(c.tx, "SELECT kind FROM bodies WHERE body_id=?", (t,))["kind"] != "infected":   # the dead do not listen
                out.append({"target_id": t, "dist": 0.0})
    elif b == "wound":
        for w in c.tx.query("SELECT wound_id, body_id FROM wounds WHERE body_id=? AND healed_at IS NULL ORDER BY wound_id", (c.me,)):
            out.append({"wound_id": w[0], "wound_body": c.me, "dist": 0.0})
        for t in c.known_bodies:
            if _row(c.tx, "SELECT kind FROM bodies WHERE body_id=?", (t,))["kind"] == "infected":
                continue                                    # nobody dresses a wound on the dead
            if t in c.seen_clear and (space.point_distance(c.tx, c.me, t) or 99) <= 1.5:
                for w in c.tx.query("SELECT wound_id FROM wounds WHERE body_id=? AND healed_at IS NULL ORDER BY wound_id", (t,)):
                    out.append({"wound_id": w[0], "wound_body": t, "target_id": t, "dist": 0.0})
        # medical item second referent
        tagmap = {"bandage_wound": "bandage", "apply_tourniquet": "tourniquet", "suture_wound": "suture", "clean_wound": "antiseptic"}
        if d.id in tagmap:
            res = []
            for o in out:
                for it in c.all_mine:
                    if tagmap[d.id] in c.canon.get(it["def_ref"]).tags:
                        res.append({**o, "item_id": it["item_id"]})
                        break
            out = res
    for o in out:
        if "wound_id" in o:
            o["target_id"] = o["wound_id"]
    return out


def _range_ok(c, d, o):
    from ..physical import space
    r = d.range
    t = o.get("target_id")
    if r == "touch" and t and t.startswith("act_"):
        return (space.point_distance(c.tx, c.me, t) or 99) <= 1.5
    if r == "same_place" and t and t.startswith("act_"):
        return _row(c.tx, "SELECT place_id FROM positions WHERE body_id=?", (t,))["place_id"] == c.place
    return True


def _physical(c, d, o):
    from ..physical import space
    q = d.requires
    if not c.cap.conscious:
        return "not conscious"
    if q.capability_tags and not set(q.capability_tags) <= set(c.dossier.capability.tags):     # D-102
        return "not something they can do"
    if q.mobile and not c.cap.mobile:
        return "cannot move"
    if q.can_run and not c.cap.can_run:
        return "cannot run"
    if q.infected_within_m is not None:
        from ..physical import space as _sp
        near = False
        for r in c.tx.query("SELECT DISTINCT p.source_id FROM percept_log p JOIN bodies b ON b.body_id = p.source_id "
                            "WHERE p.holder_id=? AND p.turn_index=? AND p.at<=? AND p.channel='visual' "
                            "AND p.fidelity IN ('exact','partial') AND b.kind='infected' ORDER BY p.source_id",
                            (c.me, c.turn, c.at)):
            dd = _sp.point_distance(c.tx, c.me, r[0])
            if dd is not None and dd <= q.infected_within_m:
                near = True
                break
        if not near:
            return "the dead are not close"
    if q.despair:   # D-107
        from ..physical.bodies import mind_of
        if mind_of(c.tx, c.me) is None and c.actor["resolve_cur"] > 0:
            return "not at the end of their rope"
    if c.cap.hands_free < q.hands_free:
        return "hands full"
    if not _range_ok(c, d, o):
        return "out of range"
    if q.held_item_tags:
        if not any(set(q.held_item_tags) <= _tags_of(c, it["item_id"]) for it in c.held):
            return "not holding " + "/".join(q.held_item_tags)
    for tag in q.carried_item_tags:
        if not any(tag in _tags_of(c, it["item_id"]) for it in c.all_mine):
            return "no " + tag
    if q.posture_any is not None and c.body["posture"] not in [str(p.value if hasattr(p, "value") else p) for p in q.posture_any]:
        return "posture"
    if q.actor_kinds is not None and c.body["kind"] not in q.actor_kinds:
        return "wrong kind of body"
    if q.actor_kinds is None and c.body["kind"] == "infected":
        return "wrong kind of body"
    t = o.get("target_id")
    if q.portal_kinds is not None and d.binds == "portal" and t:
        pk = _row(c.tx, "SELECT kind FROM portals WHERE portal_id=?", (t,))
        if pk is None or pk["kind"] not in q.portal_kinds:
            return "wrong kind of way"
    if t and t.startswith("act_") and d.binds == "body":
        if q.target_kinds is not None and not (set(_target_kinds(c, t)) & set(q.target_kinds)):
            return "wrong target"
        if q.target_alive is not None:
            if q.target_alive == _still(c, t):
                return "target state"
    if d.effect == "move_through_portal":
        ok, why = space.admits(c.tx, o["target_id"], c.me)
        if not ok:
            return why
    return None


def _skill(c, d):
    q = d.requires
    if q.skill is not None:
        dom = q.skill.domain.value if hasattr(q.skill.domain, "value") else q.skill.domain
        if c.skills.get(dom, 0) >= q.skill.min_rank:
            return None
        if q.skill_or_belief_cue and q.skill_or_belief_cue in c.cues:
            return None
        return "untrained"
    if q.skill_or_belief_cue and q.skill_or_belief_cue not in c.cues:
        return "does not know how"
    return None


def _moral_tags(c, d, o):
    tags = [str(t.value if hasattr(t, "value") else t) for t in d.moral_tags]
    t = o.get("target_id")
    if t and t.startswith("act_") and d.binds == "body":
        for k in _target_kinds(c, t):
            tags += [str(x.value if hasattr(x, "value") else x) for x in d.moral_tags_if_target.get(k, [])]
        if d.verb == Verb.ATTACK:
            if t in c.guardian_of or t in c.household:
                tags.append("harm_dependent")
            kind = _row(c.tx, "SELECT kind FROM bodies WHERE body_id=?", (t,))["kind"]
            if kind == "human":
                armed = t in c.seen_clear and any((lambda dd: dd.firearm is not None or dd.melee is not None)(c.canon.get(r[0]))
                                                  for r in c.tx.query("SELECT def_ref FROM items WHERE holder_body=? AND holder_slot IN ('hand_l','hand_r')", (t,)))
                if not armed:
                    tags.append("attack_unarmed")
    if t and t.startswith("itm_") and d.binds in ("item_reachable", "container"):
        hh = {r[0] for r in c.tx.query("SELECT household_id FROM household_members WHERE actor_id=?", (c.me,))}
        owners = [r[0] for r in c.tx.query(
            "SELECT p.object_value FROM claim_holdings h JOIN propositions p ON p.prop_id=h.claim_id WHERE h.holder_id=? "
            "AND h.superseded_by IS NULL AND h.believed=1 AND p.subject_type='object' AND p.subject_id=? AND p.predicate='owner'",
            (c.me, t))]
        if any(o and o != c.me and o not in hh and o not in c.groups for o in owners):
            tags += [str(x.value if hasattr(x, "value") else x) for x in d.moral_tags_if_target.get("owned", [])]
    if d.id in MOVE_OUT:
        here = {r[0] for r in c.tx.query("SELECT body_id FROM positions WHERE place_id=?", (c.place,))} & set(c.known_bodies)
        if c.threats and (c.guardian_of & here):
            tags.append("abandon_dependent")
        for b in c.seen_clear:
            if b in here:
                aff = _row(c.tx, "SELECT affection FROM relationships WHERE from_id=? AND to_id=?", (c.me, b))
                if aff and aff["affection"] >= 1 and c.tx.query_one(
                        "SELECT 1 FROM wounds WHERE body_id=? AND healed_at IS NULL AND clotted=0 AND severity IN ('severe','catastrophic')", (b,)):
                    tags.append("leave_wounded")
    return tags


def _duty(c, d, o, tags):
    from .identity import end
    duty = c.actor["duty_anchor"]
    notes = []
    if duty:
        da = _row(c.tx, "SELECT name, x_m, y_m, place_id FROM anchors WHERE anchor_id=?", (duty,))
        away = False
        if d.id in MOVE_OUT:
            away = True
        elif d.binds == "anchor" and d.verb in (Verb.MOVE, Verb.TAKE_COVER, Verb.HIDE) and o.get("destination_id"):
            a = _row(c.tx, "SELECT x_m, y_m FROM anchors WHERE anchor_id=?", (o["destination_id"],))
            away = math.hypot(a["x_m"] - da["x_m"], a["y_m"] - da["y_m"]) > 5
        if away:
            tags.append("abandon_post")
            notes.append(f"It means leaving your post at {c.P.thing_phrase(da['name'])}.")
    # laws the actor KNOWS (AFF-11: a law it does not know changes nothing it is offered)
    for st in c.tx.query("SELECT settlement_id, group_id, place_id FROM settlements WHERE place_id=? ORDER BY settlement_id", (c.place,)):
        member = bool(st["group_id"]) and c.tx.query_one(
            "SELECT 1 FROM group_members WHERE group_id=? AND actor_id=? AND status IN ('member','probation')",
            (st["group_id"], c.me)) is not None
        for (lr,) in c.tx.query("SELECT law_ref FROM laws_active WHERE settlement_id=? ORDER BY law_ref", (st["settlement_id"],)):
            told = c.tx.query_one(
                "SELECT 1 FROM claim_holdings h JOIN propositions p ON p.prop_id=h.claim_id WHERE h.holder_id=? "
                "AND h.superseded_by IS NULL AND h.believed=1 AND p.subject_type='place' AND p.subject_id=? "
                "AND p.predicate='law' AND p.object_value=?", (c.me, st["place_id"], lr)) is not None
            if not (member or told):
                continue
            law = c.canon.get(lr)
            for e in law.affordance_effects:
                if e.applies_to == "members" and not member:
                    continue
                if e.applies_to == "visitors" and member:
                    continue
                if e.affordance_tag in d.tags or e.affordance_tag in tags:
                    n = e.cost_note or end(law.belief_text)
                    if n not in notes:
                        notes.append(n)
    return notes


def _label(c, d, o, tmpl, ui):
    P = c.P
    t = o.get("target_id")
    parts = {}
    if d.id == "keep_working" and c.task:
        parts["target"] = c.task["label"]
    elif t is None and getattr(d.binds, "value", d.binds) == "speech":
        parts["target"] = "anyone who can hear"
    elif t and t.startswith("act_"):
        parts["target"] = _body_ref(c, t)
    elif t and t.startswith("wnd_"):
        w = _row(c.tx, "SELECT anatomy, body_id FROM wounds WHERE wound_id=?", (t,))
        parts["target"] = f"the wound on your {_ANAT[w['anatomy']]}" if w["body_id"] == c.me else f"the wound on {_body_ref(c, w['body_id'])}'s {_ANAT[w['anatomy']]}"
    elif t and t.startswith("itm_"):
        parts["target"] = P.thing_phrase(_item_name(c, t))
    elif t and t.startswith("prt_"):
        parts["target"] = P.thing_phrase(_row(c.tx, "SELECT name FROM portals WHERE portal_id=?", (t,))["name"])
    dest = o.get("destination_id")
    if dest and dest.startswith("anc_"):
        parts["destination"] = P.thing_phrase(_row(c.tx, "SELECT name FROM anchors WHERE anchor_id=?", (dest,))["name"])
    elif dest and dest.startswith("plc_"):
        parts["destination"] = P.place_phrase(_row(c.tx, "SELECT name FROM places WHERE place_id=?", (dest,))["name"])
    it = o.get("item_id")
    if it:
        nm = _item_name(c, it)
        parts["item"] = nm if ui else (f"your {nm}" if _is_mine(c, it) else P.thing_phrase(nm))
    parts["distance"] = f"{max(1, round(o.get('dist', 0.0)))} m"
    parts["duration"] = duration_words(o["est"])
    for k in ("target", "destination", "item"):
        parts.setdefault(k, "")
    return tmpl.format(**parts)


def _attention(c):
    from ..physical import space
    best = None
    for r in c.tx.query("SELECT p.detail, e.payload, e.actor_id FROM percept_log p JOIN events e ON e.event_id=p.event_id "
                        "WHERE p.holder_id=? AND p.turn_index=? AND p.at<=? AND p.channel IN ('auditory','speech')",
                        (c.me, c.turn, c.at)):
        d = json.loads(r[0])
        db = d.get("received_db", -1e9)
        if best is None or db > best[0]:
            best = (db, d, json.loads(r[1]), r[2])
    if best is None:
        return (c.pos["x_m"], c.pos["y_m"])
    _, d, payload, actor = best
    if d.get("via_portal"):
        return space.portal_point(c.tx, d["via_portal"], c.place)
    from ..sense.acoustics import source_point
    sp = source_point(c.tx, payload, actor)
    return (sp.x_m, sp.y_m)


def _opt_distance(c, ba, att, dist_from_me):
    from ..physical import space
    ref = ba.destination_id if (ba.destination_id and ba.destination_id.startswith("anc_")) else ba.target_id
    if ref and ref.startswith("anc_"):
        a = _row(c.tx, "SELECT x_m, y_m FROM anchors WHERE anchor_id=?", (ref,))
        return math.hypot(a["x_m"] - att[0], a["y_m"] - att[1])
    if ref and ref.startswith("prt_"):
        pt = space.portal_point(c.tx, ref, c.place)
        return math.hypot(pt[0] - att[0], pt[1] - att[1])
    return dist_from_me


def _group(c, opt):
    v = opt.verb
    if v == Verb.CONTINUE_TASK:
        return 0
    if c.threats and (v == Verb.ATTACK or "threat_response" in opt.tags):
        return 1
    if "posture" in opt.tags:
        return 6
    if v == Verb.SPEAK:
        return 2
    if v in (Verb.MOVE, Verb.FLEE):
        return 3
    if v in (Verb.MANIPULATE, Verb.SEARCH, Verb.TREAT, Verb.SIGNAL, Verb.TAKE_COVER, Verb.HIDE, Verb.SURRENDER, Verb.ESCAPE):
        return 4
    if v == Verb.ATTACK:
        return 5
    return 6


def enumerate_affordances(tx, actor_id, catalog, at, turn_index):
    from .resolve import gate as rgate
    c = _ctx(tx, actor_id, at, turn_index)
    res = AffordanceSet(actor_id=actor_id)
    auth = None
    aa = json.loads(c.actor["accepted_authority"])
    if aa:
        n = tx.query_one("SELECT known_name FROM acquaintance WHERE holder_id=? AND subject_id=?", (actor_id, aa[0]))
        auth = n[0] if n and n[0] else None
    cands = []
    for order, d in enumerate(catalog):
        if d.requires.reflex_only:
            continue
        for o in _bindings(c, d):
            t = o.get("target_id")
            why = _physical(c, d, o)
            if why:
                res.rejected.append(Rejection(d.id, t, "physical", why)); continue
            why = _skill(c, d)
            if why:
                res.rejected.append(Rejection(d.id, t, "skill", why)); continue
            if any(cue not in c.cues for cue in d.requires.belief_cues):
                res.rejected.append(Rejection(d.id, t, "belief", "does not believe it would work")); continue
            ok, rnote = rgate(c.actor["resolve_cur"], d, auth)
            if not ok:
                res.rejected.append(Rejection(d.id, t, "resolve", "cannot bring themselves to")); continue
            if d.effect == "shoot":
                gun = o.get("item_id")
                empty = tx.query_one("SELECT 1 FROM claim_holdings h JOIN propositions p ON p.prop_id=h.claim_id WHERE h.holder_id=? AND h.superseded_by IS NULL "
                                     "AND p.subject_type='object' AND p.subject_id=? AND p.predicate='loaded' AND h.believed=0", (actor_id, gun))
                if empty:
                    res.rejected.append(Rejection(d.id, t, "resource", "believes it is empty")); continue
            if d.binds == "wound" and o.get("item_id"):
                pr = json.loads(_row(tx, "SELECT props FROM items WHERE item_id=?", (o["item_id"],))["props"])
                if "uses" in pr and pr["uses"] <= 0:
                    res.rejected.append(Rejection(d.id, t, "resource", "used up")); continue
            tags = _moral_tags(c, d, o)
            notes = _duty(c, d, o, tags)             # the duty gate never rejects (C05)
            if rnote and rnote not in notes:
                notes.append(rnote)
            if set(tags) & c.wont:
                res.rejected.append(Rejection(d.id, t, "moral", ",".join(sorted(set(tags) & c.wont)))); continue
            walk = o.get("dist", 0.0) if d.range in ("reach", "same_place") else 0.0
            o["est"] = d.duration.base_s + d.duration.per_meter_s * walk
            label = _label(c, d, o, d.label, False)
            ui = _label(c, d, o, d.ui_label, True)
            ba = BoundAffordance(def_id=d.id, verb=d.verb, label=label, ui_label=ui, target_id=t,
                                 destination_id=o.get("destination_id"), item_id=o.get("item_id"), est_duration_s=o["est"],
                                 noise_db=d.noise_db, cost_note=" ".join(notes) or None, risk_note=None, check=d.check,
                                 tags=tuple(list(d.tags) + [x for x in tags if x not in d.tags]),
                                 paces=tuple(d.paces), hands=d.requires.hands_free)
            cands.append((order, o.get("dist", 0.0), ba))
    att = _attention(c)

    def inner(ba):
        g = _group(c, ba)
        if g == 1:
            if ba.verb == Verb.ATTACK and ba.target_id in c.threats:
                return 0
            if "protect_dependent" in ba.tags:
                return 1
            if ba.verb in (Verb.FLEE, Verb.ESCAPE):
                return 2
            if "feed_to_dead" in ba.tags:
                return 3
            if ba.verb in (Verb.TAKE_COVER, Verb.HIDE):
                return 4
            if ba.verb == Verb.SURRENDER:
                return 5
            return 6
        if g != 6:
            return 0
        if "freeze" in ba.tags:
            return 0
        if ba.verb == Verb.OBSERVE:
            return 1
        if ba.verb == Verb.GUARD:
            return 2
        return 3
    key = lambda x: (_group(c, x[2]), inner(x[2]), _opt_distance(c, x[2], att, x[1]), x[0], x[2].target_id or "")  # noqa: E731
    cands.sort(key=key)
    rules = tx.rules.packet
    groups = {}
    per_def = {}
    for x in cands:
        g = _group(c, x[2])
        n = per_def.get(x[2].def_id, 0)
        if n >= 3:
            continue
        per_def[x[2].def_id] = n + 1
        groups.setdefault(g, []).append(x)
    taken = []
    idx = 0
    while len(taken) < rules.max_affordances:
        added = False
        for g in sorted(groups):
            if idx < len(groups[g]) and len(taken) < rules.max_affordances:
                taken.append(groups[g][idx]); added = True
        if not added:
            break
        idx += 1
    taken.sort(key=key)
    keep = [x[2] for x in taken]
    if len(keep) < rules.min_affordances:
        for x in cands:
            if x[2].verb in (Verb.WAIT, Verb.OBSERVE) and x[2] not in keep:
                keep.append(x[2])
    # final order = selection order (group, distance, catalog, target)
    res.options = keep
    res.pool = [x[2] for x in cands]            # every survivor, sort-key order (CONSULT-03/04); keep ⊆ pool
    res.threats = list(c.threats)
    return res


def _f1c_adult(c):
    r = _row(c.tx, "SELECT age_years FROM bodies WHERE body_id=?", (c.me,))
    return r["age_years"] is not None and r["age_years"] >= 18
