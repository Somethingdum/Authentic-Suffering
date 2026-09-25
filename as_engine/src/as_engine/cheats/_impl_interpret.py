"""Bodies of cheats.interpret (P12, D-103). The contract is the module docstring there."""

from __future__ import annotations

import difflib
import json

from . import _impl_cheats as C

_SEVERITIES = ("minor", "significant", "severe", "catastrophic")
_AXES = ("trust", "fear", "respect", "affection", "resentment", "obligation")
_DOOR_STATES = ("open", "closed", "locked", "unlocked", "barricaded", "unbarricaded", "broken")


class _Bad(Exception):
    pass


# ------------------------------------------------------------------------------------------ the scene (CHEAT-16)
def _scene(tx, session):
    from ..content.pack import cheat_records
    from ..contracts.calls import CheatScene, SceneEntry
    from ..mind.perception import word_for
    from ..physical.bodies import excepted
    from ..physical.space import point_distance
    from ..sense.optics import visibility
    from .commands import WEATHER_KINDS
    pc = session.pc_id
    at = C._now(tx)
    ids = {}
    here = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (pc,))
    here = here[0] if here else None
    # places
    order = [here] if here else []
    for r in tx.query("SELECT place_a, place_b FROM portals WHERE place_a=? OR place_b=? ORDER BY portal_id", (here, here)):
        other = r[1] if r[0] == here else r[0]
        if other not in order:
            order.append(other)
    for r in tx.query("SELECT place_id FROM known_places WHERE holder_id=? ORDER BY place_id", (pc,)):
        if r[0] not in order:
            order.append(r[0])
    places, where = [], {}
    for i, p in enumerate(order):
        row = tx.query_one("SELECT name, kind FROM places WHERE place_id=?", (p,))
        if row is None:
            continue
        h = f"L{i}"
        ids[h] = ("place", p)
        where[p] = h
        places.append(SceneEntry(handle=h, label=row[0], kind=row[1]))
    # people
    last = C._meta(tx, "cheat_last_named")
    att = tx.query_one("SELECT attention_target FROM actors WHERE actor_id=?", (pc,))
    att = att[0] if att else None
    seen = []
    for r in tx.query("SELECT b.body_id FROM bodies b JOIN positions q ON q.body_id=b.body_id WHERE b.body_id != ? "
                      "ORDER BY b.body_id", (pc,)):
        if visibility(tx, pc, r[0], at) != "none":
            seen.append((point_distance(tx, pc, r[0]) or 999.0, r[0]))
    seen = [b for _d, b in sorted(seen)]
    known = [r[0] for r in tx.query("SELECT subject_id FROM acquaintance WHERE holder_id=? AND known_name IS NOT NULL "
                                    "ORDER BY known_name, subject_id", (pc,)) if r[0] not in seen]
    looking = att if att in seen else (seen[0] if seen else None)
    people = []
    for i, b in enumerate(seen + known, 1):
        row = tx.query_one("SELECT kind, alive FROM bodies WHERE body_id=?", (b,))
        if row is None:
            continue
        pos = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (b,))
        notes = [n for n, on in (("looking at", b == looking), ("last named", b == last), ("dead", not row[1])) if on]
        h = f"P{i}"
        ids[h] = ("body", b)
        people.append(SceneEntry(handle=h, label=word_for(tx, pc, b), kind=row[0], where=where.get(pos[0], "") if pos else "",
                                 note=", ".join(notes)))
    ids["P0"] = ("body", pc)
    me_kind = tx.query_one("SELECT kind FROM bodies WHERE body_id=?", (pc,))[0]
    me = SceneEntry(handle="P0", label=tx.query_one("SELECT display_name FROM actors WHERE actor_id=?", (pc,))[0],
                    kind=me_kind, where="L0" if here else "")
    # doors
    doors = []
    for i, r in enumerate(tx.query("SELECT portal_id, name, kind, is_open, is_locked, barricade, damage FROM portals "
                                   "WHERE place_a=? OR place_b=? ORDER BY portal_id", (here, here)), 1):
        state = ("broken" if r[6] >= 3 else "locked" if r[4] else "barricaded" if r[5] else "open" if r[3] else "closed")
        h = f"D{i}"
        ids[h] = ("portal", r[0])
        doors.append(SceneEntry(handle=h, label=r[1], kind=r[2], note=state))
    # items
    canon = tx.canon
    items = []
    rows = [r[0] for r in tx.query("SELECT item_id FROM items WHERE holder_body=? ORDER BY item_id", (pc,))]
    rows += [r[0] for r in tx.query("SELECT item_id FROM items WHERE place_id=? ORDER BY item_id", (here,))]
    for i, it in enumerate(rows, 1):
        ref = tx.query_one("SELECT def_ref FROM items WHERE item_id=?", (it,))[0]
        h = f"I{i}"
        ids[h] = ("item", it)
        items.append(SceneEntry(handle=h, label=canon.get(ref).name))
    groups = []
    for i, r in enumerate(tx.query("SELECT group_id, name FROM groups ORDER BY group_id"), 1):
        h = f"G{i}"
        ids[h] = ("group", r[0])
        groups.append(SceneEntry(handle=h, label=r[1]))
    makeable = sorted({canon.get(r).name for r in canon.refs("item")})
    beings = {canon.get(r).identity.name: r for k in ("actor", "pc") for r in canon.refs(k)}
    for r, rec in sorted(cheat_records(session.config.content_dir).items()):
        beings.setdefault(rec.identity.name, r)
    kinds = {canon.get(r).name: canon.get(r).name.lower() for r in canon.refs("infected")}
    spawnable = sorted(set(beings) | set(kinds))
    sc = CheatScene(me=me, here=places[0] if places else SceneEntry(handle="L0", label="here"), people=people,
                    places=places, doors=doors, items=items, groups=groups, makeable=makeable, spawnable=spawnable,
                    strains=sorted(canon.get(r).id for r in canon.refs("pathway")), weather=list(WEATHER_KINDS),
                    willis=excepted(tx, pc))
    return sc, {"ids": ids, "beings": beings, "kinds": kinds}


def scene(tx, session):
    return _scene(tx, session)[0]


# ------------------------------------------------------------------------------------------ the call
async def interpret(session, tx, text, seen):
    from ..contracts.calls import CheatInterpretContext
    from ..contracts.common import CallClass
    from ..contracts.mind import CheatPlan
    from ..lanes.calllog import record
    from ..lanes.requests import build_request
    from ..lanes.schemas import to_lm_schema
    from .commands import CheatParseError
    ctx = CheatInterpretContext(request=text, scene=seen)
    from .interpret import OP_DOCS
    req = build_request(session.config, CallClass.CHEAT_INTERPRET, turn_index=C._turn(tx), context=ctx, ctx=ctx, ops=OP_DOCS,
                        json_schema=to_lm_schema(CheatPlan))
    resp = await session.client.call(req)
    record(tx, req, resp)
    if resp.parse_status != "ok":
        return CheatParseError("That didn't come through, Boss. Say it another way.")
    try:
        data = resp.parsed if resp.parsed is not None else json.loads(resp.text or "{}")
        return CheatPlan.model_validate(data)
    except (ValueError, TypeError):
        return CheatParseError("That didn't come through, Boss. Say it another way.")


# ------------------------------------------------------------------------------------------ checking (CHEAT-17)
def _h(m, handle, kinds, what):
    if not handle:
        raise _Bad(f"no {what} named")
    got = m["ids"].get(handle.strip().upper())
    if got is None or got[0] not in kinds:
        raise _Bad(f"'{handle}' is not a {what} I can see")
    return got[1]


def _name(options, name, what):
    if not name:
        raise _Bad(f"no {what} named")
    low = {o.lower(): o for o in options}
    if name.lower() in low:
        return low[name.lower()]
    near = difflib.get_close_matches(name.lower(), list(low), n=1, cutoff=0.8)
    if not near:
        raise _Bad(f"there is no {what} called '{name}'")
    return low[near[0]]


def _n(v, lo, hi, default, what):
    v = default if v is None else v
    if not lo <= v <= hi:
        raise _Bad(f"{what} must be {lo} to {hi}")
    return v


def _check(tx, sc, m, op):
    """-> (op name, resolved args) or _Bad."""
    o = op.op
    body = ("body",)
    if o == "teleport":
        return o, {"who": _h(m, op.who or "P0", body, "person"), "to": _h(m, op.to, ("place", "body"), "place or person")}
    if o == "give":
        return o, {"item": _name(sc.makeable, op.item, "thing"), "qty": _n(op.n, 1, 999, 1, "the number"),
                   "who": _h(m, op.who or "P0", body, "person")}
    if o == "make":
        return o, {"item": _name(sc.makeable, op.item, "thing"), "qty": _n(op.n, 1, 999, 1, "the number"),
                   "to": _h(m, op.to or "L0", ("place",), "place")}
    if o == "destroy":
        return o, {"target": _h(m, op.target, ("item",), "thing")}
    if o == "spawn":
        return o, {"what": _name(sc.spawnable, op.item, "being"), "n": _n(op.n, 1, 20, 1, "the number"),
                   "to": _h(m, op.to, ("place", "body"), "place or person") if op.to else None,
                   "ally": (op.state or "").lower() == "ally"}
    if o == "despawn":
        return o, {"target": _h(m, op.target or op.who, body, "person")}
    if o in ("kill", "revive", "heal", "brief", "cure", "mind"):
        return o, {"who": _h(m, op.who or op.target, body, "person")}
    if o == "hurt":
        sev = (op.state or "severe").lower()
        if sev not in _SEVERITIES:
            raise _Bad(f"'{sev}' is not how bad a wound can be")
        return o, {"who": _h(m, op.who or op.target, body, "person"), "severity": sev}
    if o == "god":
        return o, {"who": _h(m, op.who or "P0", body, "person"), "on": (op.state or "on").lower() != "off"}
    if o == "set":
        return o, {"who": _h(m, op.who or "P0", body, "person"), "stat": (op.stat or "").strip(), "value": op.n}
    if o == "time":
        return o, {"hours": _n(op.n, 1, 720, None, "the hours")}
    if o == "weather":
        from .commands import WEATHER_KINDS
        k = (op.state or op.text or "").lower()
        if k not in WEATHER_KINDS:
            raise _Bad(f"'{k}' is not weather")
        return o, {"kind": k}
    if o == "noise":
        return o, {"db": _n(op.n, 40, 180, 120, "the loudness"), "to": _h(m, op.to or "L0", ("place",), "place")}
    if o == "will":
        if not op.text:
            raise _Bad("what they should want is missing")
        return o, {"who": _h(m, op.who or op.target, body, "person"), "want": op.text.strip()}
    if o == "forget":
        return o, {"who": _h(m, op.who, body, "person"), "about": _h(m, op.target, ("body", "place"), "person or place")}
    if o == "believe":
        if not op.text:
            raise _Bad("what they should believe is missing")
        return o, {"who": _h(m, op.who, body, "person"), "text": op.text.strip(),
                   "about": _h(m, op.target, ("body", "place"), "person or place") if op.target else None}
    if o == "feel":
        axis = (op.stat or "").lower()
        if axis not in _AXES:
            raise _Bad(f"'{axis}' is not a feeling I can set")
        return o, {"who": _h(m, op.who, body, "person"), "toward": _h(m, op.target, body, "person"), "axis": axis,
                   "delta": _n(op.n, -6, 6, None, "the change")}
    if o == "rep":
        return o, {"group": _h(m, op.target, ("group",), "group"), "value": _n(op.n, -5, 5, None, "the standing")}
    if o == "infect":
        s = (op.state or "wet").lower()
        if s not in sc.strains:
            raise _Bad(f"there is no strain called '{s}'")
        return o, {"who": _h(m, op.who or op.target, body, "person"), "pathway": s}
    if o == "horde":
        return o, {"n": _n(op.n, 1, 500, 20, "the number"), "to": _h(m, op.to or "L0", ("place",), "place")}
    if o in ("mega", "census", "reveal"):
        return o, {}
    if o == "force":
        who = _h(m, op.who or op.target, body, "person or creature")
        if who == m["ids"]["P0"][1]:
            raise _Bad("that one's yours — just do it")
        if not op.text:
            raise _Bad("what they should do is missing")
        return o, {"who": who, "act": op.text.strip().rstrip("."), "minutes": _n(op.n, 1, 600, 10, "the minutes")}
    if o == "reshape":
        st = (op.state or "").lower() or None
        if st not in (None, "lit", "dark"):
            raise _Bad(f"'{st}' is not lit or dark")
        return o, {"place": _h(m, op.target or op.to or "L0", ("place",), "place"), "name": (op.text or "").strip() or None,
                   "light": st}
    if o == "door":
        st = (op.state or "").lower()
        if st not in _DOOR_STATES:
            raise _Bad(f"a door cannot be '{st}'")
        return o, {"door": _h(m, op.target, ("portal",), "door"), "state": st}
    if o == "blast":
        return o, {"at": _h(m, op.to or op.target or "L0", ("place", "body", "portal"), "place, person or door"),
                   "size": op.size or "large"}
    if o == "show":
        if not op.text:
            raise _Bad("what should be seen is missing")
        return o, {"text": op.text.strip().rstrip(".")}
    raise _Bad(f"I don't know how to '{o}'")


# ------------------------------------------------------------------------------------------ doing
async def _do(tx, s, o, a, at, T):
    """-> (ok, outcome, line, events)."""
    from ..physical import bodies, objects, space

    def via(name, args, line=None):
        return name, args, line
    if o == "teleport":
        who, to = a["who"], a["to"]
        if to.startswith("act_"):
            p = tx.query_one("SELECT place_id, anchor_id, x_m, y_m FROM positions WHERE body_id=?", (to,))
            if p is None:
                return False, f"{C._name(tx, to)} isn't anywhere I can put anyone beside, Boss.", "", []
            place, anchor, x, y = p[0], p[1], p[2] + 1.0, p[3]
        else:
            place = to
            an = tx.query_one("SELECT anchor_id, x_m, y_m FROM anchors WHERE place_id=? ORDER BY anchor_id LIMIT 1", (to,))
            if an is not None:
                anchor, x, y = an
            else:
                w, d = tx.query_one("SELECT width_m, depth_m FROM places WHERE place_id=?", (to,))
                anchor, x, y = None, w / 2, d / 2
        evs = []
        if tx.query_one("SELECT 1 FROM positions WHERE body_id=?", (who,)) is not None:
            evs.append(space.remove_body(tx, who, at, None, T))
        evs.append(space.place_body(tx, who, place, anchor, x, y, at, None, T))
        return True, f"moved {C._name(tx, who)} to {C._name(tx, place)}", f"{C._name(tx, who)} is at {C._name(tx, place)} now.", evs
    if o == "give":
        ref = next(r for r in tx.canon.refs("item") if tx.canon.get(r).name == a["item"])
        return await _handler(tx, s, "give", {"item": ref, "qty": a["qty"], "person": a["who"]}, at, T)
    if o == "make":
        ref = next(r for r in tx.canon.refs("item") if tx.canon.get(r).name == a["item"])
        an = tx.query_one("SELECT anchor_id FROM anchors WHERE place_id=? ORDER BY anchor_id LIMIT 1", (a["to"],))
        d = tx.canon.get(ref)
        n = a["qty"]
        evs = []
        if d.stackable or n == 1:
            evs.append(objects.create(tx, ref, n, objects.Holder("place", a["to"], anchor_id=an[0] if an else None), "cheat", {},
                                      at, None, T, event_origin="cheat"))
        else:
            for _i in range(n):
                evs.append(objects.create(tx, ref, 1, objects.Holder("place", a["to"], anchor_id=an[0] if an else None), "cheat",
                                          {}, at, None, T, event_origin="cheat"))
        what = d.plural if n > 1 else d.name
        return True, f"made {n} {what} at {C._name(tx, a['to'])}", f"{n} {what} now lie at {C._name(tx, a['to'])}.", evs
    if o == "destroy":
        nm = C._name(tx, a["target"])
        return True, f"unmade {nm}", f"The {nm} is gone.", [objects.destroy(tx, a["target"], at, None, T)]
    if o == "spawn":
        beings, kinds = s.extras["_cheat_scene_map"]["beings"], s.extras["_cheat_scene_map"]["kinds"]
        what = kinds.get(a["what"]) or beings.get(a["what"])
        res = await _handler(tx, s, "spawn", {"what": what, "n": a["n"], "ally": a["ally"]}, at, T, keep=True)
        ok, outcome, line, evs, made = res
        if ok is not True:
            return ok, outcome, line, evs
        if a["to"] and made:
            for b in made:
                await _do(tx, s, "teleport", {"who": b, "to": a["to"]}, at, T)
        return True, outcome, line, evs
    if o == "despawn":
        return await _handler(tx, s, "despawn", {"target": a["target"]}, at, T)
    if o in ("kill", "revive", "heal", "brief", "cure", "mind"):
        return await _handler(tx, s, o, {"person": a["who"]}, at, T)
    if o == "hurt":
        from ..action.effects import CENTRE_MASS
        if not C._alive(tx, a["who"])[0]:
            return False, f"{C._name(tx, a['who'])} is past hurting, Boss.", "", []
        anat = s.rng.weighted(tx, "cheats", f"hurt:{a['who']}:{at}", list(CENTRE_MASS))
        cause = C._ev(tx, "cheats", [], {"command": "hurt", "body_id": a["who"], "severity": a["severity"]}, at, T)
        hs = bodies.apply_harm(tx, a["who"], bodies.WoundSpec(anat, "blunt", a["severity"], 0), at, cause.event_id, T, s.rng)
        nm = C._name(tx, a["who"])
        return True, f"hurt {nm} ({a['severity']})", f"{nm} is hurt: a {a['severity']} wound.", [cause, *hs]
    if o == "god":
        return await _handler(tx, s, "god", {"person": a["who"], "on": a["on"]}, at, T)
    if o == "set":
        return await _handler(tx, s, "set", {"person": a["who"], "stat": a["stat"], "value": a["value"]}, at, T)
    if o == "time":
        return await _handler(tx, s, "time", {"hours": a["hours"]}, at, T)
    if o == "weather":
        return await _handler(tx, s, "weather", {"kind": a["kind"]}, at, T)
    if o == "noise":
        an = tx.query_one("SELECT name FROM anchors WHERE place_id=? ORDER BY anchor_id LIMIT 1", (a["to"],))
        pc_place = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (s.pc_id,))[0]
        args = {"db": a["db"]}
        if a["to"] != pc_place and an is not None:
            args["anchor"] = an[0]
        return await _handler(tx, s, "noise", args, at, T)
    if o == "will":
        return await _handler(tx, s, "will", {"person": a["who"], "want": a["want"]}, at, T)
    if o == "forget":
        return await _handler(tx, s, "forget", {"person": a["who"], "about": a["about"]}, at, T)
    if o == "believe":
        from ..mind import perception
        from ..mind.perception import BeliefFromPercept
        if a["about"] is None:
            about = ("body", a["who"])
        elif a["about"].startswith("act_"):
            about = ("body", a["about"])
        else:
            about = ("place", a["about"])
        ev = C._ev(tx, "cheats", [], {"command": "believe", "actor_id": a["who"], "text": a["text"]}, at, T)
        perception.grant(tx, a["who"], event_id=ev.event_id, channel="visual", fidelity="exact", text="You simply know it.",
                         source_id=None, at=at, turn_index=T, confidence=3,
                         beliefs=[BeliefFromPercept(subject_type=about[0], subject_id=about[1], predicate="cheat_belief",
                                                    text=a["text"])],
                         detail={"cheat": True}, provenance="cheat")
        nm = C._name(tx, a["who"])
        return True, f"{nm} now believes: {a['text']}", f"{nm} believes it now.", [ev]
    if o == "feel":
        from ..mind import mind as mind_mod
        cause = C._ev(tx, "cheats", [], {"command": "feel", "from": a["who"], "to": a["toward"], "axis": a["axis"]}, at, T)
        e = mind_mod.relate(tx, a["who"], a["toward"], a["axis"], a["delta"], cause.event_id, at, T)
        nm, tn = C._name(tx, a["who"]), C._name(tx, a["toward"])
        return True, f"{nm}'s {a['axis']} toward {tn} changed by {a['delta']}", f"{nm} feels differently about {tn}.", \
            [cause] + ([e] if e else [])
    if o == "rep":
        return await _handler(tx, s, "rep", {"group": a["group"], "value": a["value"]}, at, T)
    if o == "infect":
        return await _handler(tx, s, "infect", {"person": a["who"], "pathway": a["pathway"]}, at, T)
    if o == "horde":
        return await _handler(tx, s, "horde", {"n": a["n"], "place": a["to"]}, at, T)
    if o in ("mega", "census", "reveal"):
        return await _handler(tx, s, o, {}, at, T)
    if o == "force":
        cause = C._ev(tx, "cheats", [], {"command": "force", "body_id": a["who"], "act": a["act"], "minutes": a["minutes"]}, at, T)
        ev = bodies.force_act(tx, a["who"], a["act"], at + a["minutes"] * 60_000, at, T, cause.event_id)
        nm = C._name(tx, a["who"])
        mins = a["minutes"]
        return True, f"{nm} {a['act']} for {mins} minutes", f"{nm[:1].upper() + nm[1:]} {a['act']} for {mins} minute{'s' * (mins != 1)}.", \
            [cause, ev]
    if o == "reshape":
        ch = {}
        if a["name"]:
            ch["name"] = a["name"]
        if a["light"]:
            ch["light_level"] = 3 if a["light"] == "lit" else 0
        if not ch:
            return False, "Reshape it into what, Boss?", "", []
        old = C._name(tx, a["place"])
        ev = space.change_place(tx, a["place"], ch, "cheat", at, None, T)
        return True, f"reshaped {old}", f"{old} is {a['name'] or old} now{', ' + a['light'] if a['light'] else ''}.", [ev]
    if o == "door":
        st = a["state"]
        ch = {"open": {"is_open": 1}, "closed": {"is_open": 0}, "locked": {"is_open": 0, "is_locked": 1},
              "unlocked": {"is_locked": 0}, "barricaded": {"is_open": 0, "barricade": 3}, "unbarricaded": {"barricade": 0},
              "broken": {"damage": 3, "is_open": 1, "is_locked": 0, "barricade": 0}}[st]
        ev = space.portal_change_event(tx, a["door"], ch, at, None, None, T)
        nm = C._name(tx, a["door"])
        return True, f"the {nm} is {st}", f"The {nm} is {st} now.", [ev]
    if o == "blast":
        cause = C._ev(tx, "cheats", [], {"command": "blast", "at": a["at"], "size": a["size"]}, at, T)
        evs = bodies.blast(tx, s.rng, a["at"], a["size"], at, T, cause.event_id)
        where = C._name(tx, a["at"])
        return True, f"a {a['size']} blast at {where}", f"A {a['size']} blast tears through {where}.", [cause] + evs
    if o == "show":
        from ..physical.bodies import excepted
        if excepted(tx, s.pc_id):
            ok, outcome, line, evs = await _handler(tx, s, "wonder", {"what": a["text"]}, at, T)
            return ok, outcome, line, evs
        cur = json.loads(C._meta(tx, "pending_shows") or "[]")
        ev = C._ev(tx, "kernel.meta", [C._W("meta", {"key": "pending_shows", "value": json.dumps(cur + [a["text"]])}, "upsert",
                                            {"key": "pending_shows"})], {"command": "show", "text": a["text"]}, at, T)
        return True, f"{a['text']} (a show)", \
            f"{a['text'][:1].upper() + a['text'][1:]} — as the next moment begins (a show: the world has no way to do more than let it be seen).", [ev]
    return False, f"I don't know how to '{o}', Boss.", "", []


async def _handler(tx, s, name, args, at, T, keep=False):
    res = await C.HANDLERS[name](tx, s, args, at, T)
    ok, outcome, detail, evs = res[0], res[1], res[2], res[3]
    if ok is False or ok is None or ok == "refused":
        return (ok, outcome, "", evs) + ((None,) if keep else ())
    line = detail or (outcome[:1].upper() + outcome[1:] + ".")
    return (True, outcome, line, evs) + ((res[4] if len(res) > 4 else None,) if keep else ())


# ------------------------------------------------------------------------------------------ run
async def run(session, text):
    from .commands import CheatResult
    try:
        return await _run(session, text)
    except C._Refuse as r:
        return CheatResult(ok=False, persona_line=str(r), detail="")


async def _run(session, text):
    from ..service.session import append_story
    from .commands import CheatParseError, CheatResult
    store = session.store
    with store.transaction() as tx:
        at, T = C._now(tx), C._turn(tx)
        sc, m = _scene(tx, session)
        session.extras["_cheat_scene_map"] = m
        plan = await interpret(session, tx, text, sc)
        if isinstance(plan, CheatParseError):
            return CheatResult(ok=False, persona_line=plan.message, detail="")
        if plan.clarify:
            return CheatResult(ok=False, persona_line=plan.clarify, detail="")
        if not plan.ops:
            return CheatResult(ok=False, persona_line="Nothing to do there, Boss.", detail="")
        checked = []
        for i, op in enumerate(plan.ops, 1):
            try:
                checked.append(_check(tx, sc, m, op))
            except _Bad as b:
                return CheatResult(ok=False, persona_line=f"I got tangled up at step {i}, Boss: {b}.", detail="")
        evs, lines, outcomes, named = [], [], [], None
        for o, a in checked:
            ok, outcome, line, e = await _do(tx, session, o, a, at, T)
            if ok is not True:
                raise C._Refuse(outcome)
            evs += [x for x in e if x is not None]
            lines.append(line)
            outcomes.append(outcome)
            if named is None:
                for k in ("who", "target", "despawn", "toward"):
                    v = a.get(k)
                    if isinstance(v, str) and v.startswith("act_") and v != session.pc_id:
                        named = v
                        break
        line = await C.persona(session, tx, "plain", "; ".join(outcomes))
        ids = [e.event_id for e in evs if getattr(e, "event_id", None)]
        C._ev(tx, "cheats", [C._W("cheat_log", {"entry_id": tx.mint("cht"), "turn_index": T, "command": text,
                                                "outcome": "; ".join(outcomes)[:1000], "persona_line": line,
                                                "event_id": ids[0] if ids else None}, "insert")],
              {"command": "plain", "raw": text, "outcome": "; ".join(outcomes)[:1000]}, at, T)
        if C._meta(tx, "sandbox") != "1":
            C._ev(tx, "kernel.meta", [C._W("meta", {"value": "1"}, "update", {"key": "sandbox"})], {"sandbox": True}, at, T)
        if named:
            C._ev(tx, "kernel.meta", [C._W("meta", {"key": "cheat_last_named", "value": named}, "upsert",
                                           {"key": "cheat_last_named"})], {"cheat_last_named": named}, at, T)
        append_story(tx, T, "cheat", f"{text}\n{line}")
    return CheatResult(ok=True, persona_line=line, detail="\n".join(lines), event_ids=ids)


# ------------------------------------------------------------------------------------------ shows
def take_shows(tx, pc_id, turn_index, at):
    from ..mind import perception
    shows = json.loads(C._meta(tx, "pending_shows") or "[]")
    if not shows:
        return []
    here = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (pc_id,))
    here = here[0] if here else None
    out = []
    for text in shows:
        ev = C._ev(tx, "cheats", [], {"show": text}, at, turn_index)
        who = [r[0] for r in tx.query("SELECT b.body_id FROM bodies b JOIN positions q ON q.body_id=b.body_id WHERE q.place_id=? "
                                      "AND b.alive=1 AND b.awareness IN ('alert','awake','drowsy') ORDER BY b.body_id", (here,))]
        if pc_id not in who:
            who.append(pc_id)
        for b in sorted(who):
            out.append(perception.grant(tx, b, event_id=ev.event_id, channel="visual", fidelity="exact",
                                        text=text[:1].upper() + text[1:] + ".", source_id=None, at=at, turn_index=turn_index,
                                        detail={"show": True}))
    C._ev(tx, "kernel.meta", [C._W("meta", {"key": "pending_shows", "value": "[]"}, "upsert", {"key": "pending_shows"})],
          {"shows": "done"}, at, turn_index)
    return out
