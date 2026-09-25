"""Implementation of cheats/commands.py (P12)."""
from __future__ import annotations

import difflib
import json
import re

TOKEN_RE = re.compile(r'"([^"]*)"|(\S+)')
TIME_RE = re.compile(r"^\+(\d+)h$", re.IGNORECASE)
LETTERS = "SPECIAL"
MAX_QTY = 999


def _meta(tx, key):
    r = tx.query_one("SELECT value FROM meta WHERE key=?", (key,))
    return None if r is None else r[0]


def _now(tx):
    return tx.query_one("SELECT now_ms FROM world_clock")[0]


def _turn(tx):
    return tx.query_one("SELECT turn_index FROM world_clock")[0]


# ------------------------------------------------------------------------------------------ parse
def parse(text):
    from .commands import USAGE, CheatCommand, CheatParseError, SKILL_DOMAINS, WEATHER_KINDS
    t = text.strip()
    toks = [b if b else a for a, b in TOKEN_RE.findall(t[1:])] if t.startswith("/") else []
    if not toks:
        return CheatParseError("Say the word, Boss — a command after the slash. Try /help.")
    name, rest = toks[0].lower(), toks[1:]
    if name not in USAGE:
        return CheatParseError(f"No lever called '{toks[0]}', Boss. Try /help.")

    def bad():
        return CheatParseError(f"That's not how /{name} works, Boss: {USAGE[name]}.")
    args = {}
    if name in ("help", "off", "reveal"):
        pass
    elif name == "give":
        if not rest:
            return bad()
        args["item"] = rest[0]
        i = 1
        if i < len(rest) and rest[i].isdigit():
            q = int(rest[i])
            if not 1 <= q <= MAX_QTY:
                return bad()
            args["qty"] = q
            i += 1
        if i < len(rest):
            if rest[i].lower() != "to" or i + 1 >= len(rest):
                return bad()
            args["person"] = " ".join(rest[i + 1:])
    elif name == "heal":
        if rest:
            args["person"] = " ".join(rest)
    elif name == "god":
        if not rest or rest[0].lower() not in ("on", "off"):
            return bad()
        args["on"] = rest[0].lower() == "on"
        if len(rest) > 1:
            args["person"] = " ".join(rest[1:])
    elif name == "tp":
        if not rest:
            return bad()
        args["place"] = " ".join(rest)
    elif name == "set":
        if len(rest) < 2:
            return bad()
        stat = rest[0]
        if stat.upper() in LETTERS and len(stat) == 1:
            stat = stat.upper()
        elif stat.lower() in ("resolve",) + SKILL_DOMAINS:
            stat = stat.lower()
        else:
            return bad()
        try:
            v = int(rest[1])
        except ValueError:
            return bad()
        lo, hi = (1, 10) if stat in LETTERS else (0, 3) if stat != "resolve" else (0, 99)
        if not lo <= v <= hi:
            return bad()
        args.update(stat=stat, value=v)
        if len(rest) > 2:
            args["person"] = " ".join(rest[2:])
    elif name == "time":
        m = TIME_RE.match(rest[0]) if len(rest) == 1 else None
        if m is None or not 1 <= int(m.group(1)) <= 720:
            return bad()
        args["hours"] = int(m.group(1))
    elif name == "weather":
        if len(rest) != 1 or rest[0].lower() not in WEATHER_KINDS:
            return bad()
        args["kind"] = rest[0].lower()
    elif name == "rep":
        if len(rest) < 2:
            return bad()
        try:
            v = int(rest[-1])
        except ValueError:
            return bad()
        if not -5 <= v <= 5:
            return bad()
        args.update(group=" ".join(rest[:-1]), value=v)
    elif name == "spawn":
        if not rest:
            return bad()
        args.update(what=rest[0], n=1, ally=False)
        for r in rest[1:]:
            if r.lower() == "ally":
                args["ally"] = True
            elif re.fullmatch(r"[xX]\d+", r) and 1 <= int(r[1:]) <= 20:
                args["n"] = int(r[1:])
            else:
                return bad()
    elif name in ("despawn", "kill", "revive", "mind", "brief"):
        if not rest:
            return bad()
        args["target" if name == "despawn" else "person"] = " ".join(rest)
    elif name == "will":
        if len(rest) < 2:
            return bad()
        args.update(person=rest[0], want=" ".join(rest[1:]))
    elif name == "forget":
        low = [r.lower() for r in rest]
        if "about" not in low or low.index("about") in (0, len(rest) - 1):
            return bad()
        k = low.index("about")
        args.update(person=" ".join(rest[:k]), about=" ".join(rest[k + 1:]))
    elif name == "infect":
        low = [r.lower() for r in rest]
        if not rest or low[0] == "with":
            return bad()
        if "with" in low:
            k = low.index("with")
            if k != len(rest) - 2:
                return bad()
            args.update(person=" ".join(rest[:k]), pathway=low[k + 1])
        else:
            args["person"] = " ".join(rest)
    elif name == "cure":
        if not rest:
            return bad()
        args["person"] = " ".join(rest)
    elif name == "horde":
        if not rest or not rest[0].isdigit() or not 1 <= int(rest[0]) <= 500:
            return bad()
        args["n"] = int(rest[0])
        if len(rest) > 1:
            if rest[1].lower() != "at" or len(rest) < 3:
                return bad()
            args["place"] = " ".join(rest[2:])
    elif name in ("mega", "census"):
        pass
    elif name == "wonder":
        if not rest:
            return bad()
        args["what"] = " ".join(rest)
    elif name == "noise":
        if not rest or not rest[0].isdigit() or not 40 <= int(rest[0]) <= 180:
            return bad()
        args["db"] = int(rest[0])
        if len(rest) > 1:
            if rest[1].lower() == "here" and len(rest) == 2:
                pass
            elif rest[1].lower() == "at" and len(rest) > 2:
                args["anchor"] = " ".join(rest[2:])
            else:
                return bad()
    return CheatCommand(name=name, args=args, raw=t)


# ------------------------------------------------------------------------------------------ names
def _match(name, table):
    """table: [(key_lower, id)] in priority order -> (id, candidates)."""
    n = name.strip().lower()
    exact = sorted({i for k, i in table if k == n})
    if len(exact) == 1:
        return exact[0], []
    if exact:
        return None, exact
    keys = sorted({k for k, _i in table})
    close = difflib.get_close_matches(n, keys, n=5, cutoff=0.8)
    ids = sorted({i for k, i in table if k in close})
    if len(ids) == 1:
        return ids[0], []
    return None, ids


def resolve(tx, pc_id, kind, name):
    """-> (id, None) or (None, the persona line saying why not)."""
    if kind == "person":
        if name.strip().lower() in ("me", "myself", "self"):
            return pc_id, None
        known = [(r[0].lower(), r[1]) for r in tx.query(
            "SELECT known_name, subject_id FROM acquaintance WHERE holder_id=? AND known_name IS NOT NULL ORDER BY subject_id", (pc_id,))]
        known += [(r[0].lower(), r[1]) for r in tx.query(
            "SELECT description, subject_id FROM acquaintance WHERE holder_id=? AND description IS NOT NULL ORDER BY subject_id", (pc_id,))]
        every = [(r[0].lower(), r[1]) for r in tx.query("SELECT display_name, actor_id FROM actors ORDER BY actor_id")]
        every += [(r[0].split()[0].lower(), r[1]) for r in tx.query("SELECT display_name, actor_id FROM actors ORDER BY actor_id")
                  if r[0].split()]
        tables = (known, every)
        label = "anyone"
    elif kind == "place":
        known = [(r[0].lower(), r[1]) for r in tx.query(
            "SELECT pl.name, pl.place_id FROM known_places k JOIN places pl ON pl.place_id=k.place_id WHERE k.holder_id=? "
            "ORDER BY pl.place_id", (pc_id,))]
        every = [(r[0].lower(), r[1]) for r in tx.query("SELECT name, place_id FROM places ORDER BY place_id")]
        tables = (known, every)
        label = "anywhere"
    elif kind == "group":
        tables = ([(r[0].lower(), r[1]) for r in tx.query("SELECT name, group_id FROM groups ORDER BY group_id")],)
        label = "any group"
    elif kind == "item_def":
        tbl = []
        for ref in tx.canon.refs("item"):
            rec = tx.canon.get(ref)
            tbl += [(ref.lower(), ref), (ref.rsplit("/", 1)[1].lower(), ref), (rec.name.lower(), ref), (rec.plural.lower(), ref)]
        tables = (tbl,)
        label = "any such thing"
    elif kind == "item":
        tables = ([(tx.canon.get(r[0]).name.lower(), r[1]) for r in tx.query("SELECT def_ref, item_id FROM items ORDER BY item_id")],)
        label = "any such thing"
    else:
        raise ValueError(kind)
    cands = []
    for t in tables:
        got, c = _match(name, t)
        if got is not None:
            return got, None
        cands = cands or c
    if cands:
        return None, f"Too many of those, Boss: {', '.join(_name(tx, c) for c in cands[:5])}. Be specific."
    return None, f"Never heard of {label} called '{name}', Boss."


def _name(tx, i):
    for sql in ("SELECT display_name FROM actors WHERE actor_id=?", "SELECT name FROM places WHERE place_id=?",
                "SELECT name FROM groups WHERE group_id=?"):
        r = tx.query_one(sql, (i,))
        if r is not None:
            return r[0]
    r = tx.query_one("SELECT def_ref FROM items WHERE item_id=?", (i,))
    if r is not None:
        return tx.canon.get(r[0]).name
    if tx.canon.has(i):
        return tx.canon.get(i).name
    return i


# ------------------------------------------------------------------------------------------ effects
def _ev(tx, writer, writes, payload, at, T, **kw):
    from ..contracts.events import Event, EventType
    return tx.commit_event(Event(type=EventType.CHEAT_OVERRIDE, writer=writer, origin="cheat", at=at, turn_index=T,
                                 writes=writes, payload=payload, **kw))


def _W(table, values, op, key=None):
    from ..contracts.events import WriteOp, WriteRecord
    return WriteRecord(op=WriteOp(op), table=table, values=values, key=key or {})


def god_bodies(tx):
    try:
        return set(json.loads(_meta(tx, "god_bodies") or "[]"))
    except (ValueError, TypeError):
        return set()


def _person(tx, s, args, key="person"):
    if key not in args:
        return s.pc_id, None
    return resolve(tx, s.pc_id, "person", args[key])


def _alive(tx, b):
    r = tx.query_one("SELECT alive, kind FROM bodies WHERE body_id=?", (b,))
    return r is not None and r[0] == 1, (r[1] if r else None)


def _heal_writes(tx, b, at, revive=False):
    ws = []
    for w in tx.query("SELECT wound_id FROM wounds WHERE body_id=? AND healed_at IS NULL ORDER BY wound_id", (b,)):
        ws.append(_W("wounds", {"healed_at": at, "clotted": 1}, "update", {"wound_id": w[0]}))
    vals = {"blood_loss_pct": 0.0, "pain": 0, "impairment": 0}
    aw = tx.query_one("SELECT awareness FROM bodies WHERE body_id=?", (b,))[0]
    if revive or aw == "unconscious":
        vals.update(awareness="awake", posture="standing")
    if revive:
        vals.update(alive=1, dead_at=None, death_event=None, false_dead_until=None)
    ws.append(_W("bodies", vals, "update", {"body_id": b}))
    if tx.query_one("SELECT 1 FROM needs WHERE body_id=?", (b,)) is not None:
        ws.append(_W("needs", {"thirst_stage": 0, "hunger_stage": 0, "fatigue_stage": 0, "last_drink_ms": at, "last_meal_ms": at,
                               "last_sleep_ms": at, "cold_stage": 0, "heat_stage": 0, "chill": 0}, "update", {"body_id": b}))
    return ws


async def _give(tx, s, a, at, T):
    from ..physical import objects
    ref, why = resolve(tx, s.pc_id, "item_def", a["item"])
    if ref is None:
        return False, why, "", []
    who, why = _person(tx, s, a)
    if who is None:
        return False, why, "", []
    d = tx.canon.get(ref)
    qty = a.get("qty", 1)
    units = [qty] if (d.stackable or qty == 1) else [1] * qty
    evs = [objects.create(tx, ref, q, objects.Holder("body", who, "pack"), "cheat", {}, at, None, T, event_origin="cheat")
           for q in units]
    return True, f"gave {qty} {d.plural if qty > 1 else d.name} to {_name(tx, who)}", "", evs


async def _heal(tx, s, a, at, T):
    who, why = _person(tx, s, a)
    if who is None:
        return False, why, "", []
    alive, _k = _alive(tx, who)
    if not alive:
        return False, "They're past a bandage, Boss. Try /revive.", "", []
    ev = _ev(tx, "physical.bodies", _heal_writes(tx, who, at), {"command": "heal", "body_id": who}, at, T, target_ids=[who])
    return True, f"healed {_name(tx, who)}", "", [ev]


async def _god(tx, s, a, at, T):
    who, why = _person(tx, s, a)
    if who is None:
        return False, why, "", []
    g = god_bodies(tx)
    g = (g | {who}) if a["on"] else (g - {who})
    ev = _ev(tx, "kernel.meta", [_W("meta", {"key": "god_bodies", "value": json.dumps(sorted(g))}, "upsert", {"key": "god_bodies"})],
             {"command": "god", "body_id": who, "on": a["on"]}, at, T)
    return True, f"god mode {'on' if a['on'] else 'off'} for {_name(tx, who)}", "", [ev]


async def _tp(tx, s, a, at, T):
    pid, why = resolve(tx, s.pc_id, "place", a["place"])
    if pid is None:
        return False, why, "", []
    an = tx.query_one("SELECT anchor_id, x_m, y_m FROM anchors WHERE place_id=? ORDER BY anchor_id LIMIT 1", (pid,))
    if an is not None:
        vals = {"place_id": pid, "anchor_id": an[0], "x_m": an[1], "y_m": an[2]}
    else:
        p = tx.query_one("SELECT width_m, depth_m FROM places WHERE place_id=?", (pid,))
        vals = {"place_id": pid, "anchor_id": None, "x_m": p[0] / 2, "y_m": p[1] / 2}
    vals.update(since_ms=at, hidden=0)
    ev = _ev(tx, "physical.space", [_W("positions", vals, "update", {"body_id": s.pc_id})],
             {"command": "tp", "body_id": s.pc_id, "to_place": pid}, at, T, place_id=pid)
    return True, f"moved you to {_name(tx, pid)}", "", [ev]


def _delta(tx, who, path, value, at, T):
    return _W("dossier_deltas", {"delta_id": tx.mint("ddl"), "actor_id": who, "event_id": "cheat", "path": path, "op": "set",
                                 "value_json": json.dumps(value), "at": at}, "insert")


async def _set(tx, s, a, at, T):
    from ..mind.actor import fused
    who, why = _person(tx, s, a)
    if who is None:
        return False, why, "", []
    stat, v = a["stat"], a["value"]
    has_actor = tx.query_one("SELECT resolve_max FROM actors WHERE actor_id=?", (who,))
    if stat in LETTERS:
        sp = json.loads(tx.query_one("SELECT special FROM bodies WHERE body_id=?", (who,))[0])
        evs = [_ev(tx, "physical.bodies", [_W("bodies", {"special": {**sp, stat: v}}, "update", {"body_id": who})],
                   {"command": "set", "body_id": who, "stat": stat, "value": v}, at, T, target_ids=[who])]
        if has_actor is not None:
            evs.append(_ev(tx, "mind.actor", [_delta(tx, who, f"capability.special.{stat}", v, at, T)],
                           {"command": "set", "actor_id": who, "path": f"capability.special.{stat}"}, at, T))
        return True, f"set {stat} to {v} for {_name(tx, who)}", "", evs
    if has_actor is None:
        return False, f"{_name(tx, who)} has no mind to set that in, Boss.", "", []
    if stat == "resolve":
        v = max(0, min(v, has_actor[0]))
        ev = _ev(tx, "mind.actor", [_W("actors", {"resolve_cur": v}, "update", {"actor_id": who})],
                 {"command": "set", "actor_id": who, "stat": "resolve", "value": v}, at, T)
        return True, f"set resolve to {v} for {_name(tx, who)}", "", [ev]
    skills = [x for x in fused(tx, who).capability.model_dump(mode="json")["skills"] if x["domain"] != stat]
    if v > 0:
        skills.append({"domain": stat, "rank": v, "evidence": "The Boss said so, and so it was."})
    skills.sort(key=lambda x: x["domain"])
    ev = _ev(tx, "mind.actor", [_delta(tx, who, "capability.skills", skills, at, T)],
             {"command": "set", "actor_id": who, "path": "capability.skills", "skill": stat, "value": v}, at, T)
    return True, f"set {stat} to {v} for {_name(tx, who)}", "", [ev]


async def _time(tx, s, a, at, T):
    from ..turn import timers
    evs = timers.run_offscreen(tx, s.rng, at + a["hours"] * 3_600_000, T)
    return True, f"the world lived {a['hours']} hours", "", evs


async def _weather(tx, s, a, at, T):
    wind = {"wind": 2, "storm": 3}.get(a["kind"], 0)
    ev = _ev(tx, "kernel.clock", [_W("world_clock", {"weather": a["kind"], "wind_level": wind}, "update", {"id": 1})],
             {"command": "weather", "weather": a["kind"], "wind_level": wind}, at, T)
    return True, f"the weather is {a['kind']}", "", [ev]


async def _rep(tx, s, a, at, T):
    gid, why = resolve(tx, s.pc_id, "group", a["group"])
    if gid is None:
        return False, why, "", []
    ev = _ev(tx, "society.group", [_W("group_standing", {"group_id": gid, "actor_id": s.pc_id, "standing": a["value"],
                                                         "reasons": []}, "upsert", {"group_id": gid, "actor_id": s.pc_id})],
             {"command": "rep", "group_id": gid, "value": a["value"]}, at, T)
    return True, f"{_name(tx, gid)} now regard you at {a['value']}", "", [ev]


def _cheat_records(session):
    """Every actor / pc record of the cheat_ packs under config.content_dir (CHEAT-10:
    content.pack.cheat_records) -> {ref: record}."""
    from ..content.pack import cheat_records
    return cheat_records(session.config.content_dir)


def _spawn_ref(tx, session, what):
    """(ref, record) for /spawn: a full ref or a bare id — the run's own packs first, then the
    cheat_ packs; None when there is no such dossier."""
    pools = [{r: tx.canon.get(r) for k in ("actor", "pc") for r in tx.canon.refs(k)}, _cheat_records(session)]
    for pool in pools:
        if what in pool:
            return what, pool[what]
        bare = sorted(r for r in pool if r.rsplit("/", 1)[1].lower() == what.lower())
        if bare:
            return bare[0], pool[bare[0]]
    return None, None


def _hard_line(rec):
    from ..content.safety import unsafe_terms
    d = rec.model_dump(mode="json", by_alias=True)
    try:
        age = int((d.get("identity") or {}).get("age"))
    except (TypeError, ValueError):
        return []
    if age >= 18:
        return []

    def strings(o):
        if isinstance(o, str):
            yield o
        elif isinstance(o, dict):
            for v in o.values():
                yield from strings(v)
        elif isinstance(o, list):
            for v in o:
                yield from strings(v)
    return sorted({t for x in strings(d) for t in unsafe_terms(x)})


async def _spawn(tx, s, a, at, T):
    from ..contracts.dossier import Looks
    from ..mind import actor as actor_mod
    from ..physical import bodies, objects, space
    from .commands import RETIRED_SPAWNS
    what = a["what"].lower()
    if what in RETIRED_SPAWNS:
        return None, RETIRED_SPAWNS[what], "", []
    pos = tx.query_one("SELECT place_id, anchor_id, x_m, y_m FROM positions WHERE body_id=?", (s.pc_id,))
    place, anchor, x, y = pos
    w, dpt = tx.query_one("SELECT width_m, depth_m FROM places WHERE place_id=?", (place,))
    types = {}
    for r in tx.canon.refs("infected"):
        t = tx.canon.get(r)
        for word in (t.name.lower(), *[w.lower() for w in re.findall(r"[A-Z]+", t.id)
                                       if len(w) > 3 and w not in ("ZOMBIE", "ARCHETYPE", "VARIANT")]):
            types.setdefault(word, t)
    evs, made = [], []
    if what in types:
        from ..world import infected
        for i in range(a["n"]):
            bid = infected.spawn(tx, s.rng, place, types[what].id, at, T, None, origin="cheat",
                                 x_m=min(w, x + 1.0 + 0.5 * i), y_m=y)
            made.append(bid)
        return True, f"{a['n']} {what}{'s' if a['n'] > 1 else ''} at your place", "", evs, made
    ref, rec = _spawn_ref(tx, s, a["what"])
    if ref is None:
        return False, f"Never heard of anyone or anything called '{a['what']}', Boss.", "", []
    terms = _hard_line(rec)
    if terms:
        return "refused", "No. Not that, not ever, Boss.", "", []
    d = rec.model_dump(mode="json", by_alias=True)
    idn, ap, cap = d["identity"], d["appearance"], d["capability"]
    for i in range(a["n"]):
        looks = Looks.model_validate(ap["looks"]) if ap.get("looks") else None
        bid = bodies.create(tx, kind="lurker" if "lurker" in (d.get("tags") or []) else "human", sex=idn.get("sex"),
                            age_years=idn.get("age"), height_cm=ap["height_cm"], mass_kg=ap["mass_kg"],
                            special=dict(cap["special"]), at=at, turn_index=T, origin="cheat", content_ref=ref, looks=looks)
        space.place_body(tx, bid, place, anchor, min(w, x + 1.0 + 0.5 * i), min(dpt, y), at, None, T)
        if looks is not None:
            for piece in looks.outfit:
                props = {k: v for k, v in (("colour", piece.colour), ("state", piece.state), ("insignia", piece.insignia))
                         if v is not None}
                objects.create(tx, piece.item, 1, objects.Holder("body", bid, "worn"), "cheat", props, at, None, T,
                               event_origin="cheat")
        actor_mod.create(tx, bid, d, "cheat", at, T, content_ref=ref, mind_kind="model", event_origin="cheat")
        auth = [s.pc_id] if a["ally"] else []
        evs.append(_ev(tx, "mind.actor", [_W("actors", {"quarantine": 1, "accepted_authority": auth}, "update", {"actor_id": bid})],
                       {"command": "spawn", "actor_id": bid, "ref": ref, "ally": a["ally"]}, at, T))
        from ..contracts.events import Event, EventType
        tx.commit_event(Event(type=EventType.PERCEIVE, writer="mind.perception", origin="cheat", at=at, turn_index=T, actor_id=bid,
                              writes=[_W("known_places", {"holder_id": bid, "place_id": place, "first_seen": at, "last_seen": at,
                                                          "visited": 1}, "insert")], payload={"holder_id": bid, "seed": True}))
        if "reality_exception" in (cap.get("tags") or []):
            bodies.grant_exception(tx, bid, at, T, origin="cheat")
        if "fickle" in (d.get("tags") or []):
            from ..mind.mind import add_fickle
            add_fickle(tx, bid, at, T, origin="cheat")
        if "cheat_companion" in (d.get("tags") or []) and bodies.excepted(tx, s.pc_id):
            evs += _blend_in(tx, bid, s.pc_id, place, d, at, T)
        made.append(bid)
    return True, f"{idn['name']} x{a['n']} at your place{' (ally)' if a['ally'] else ''}", "", evs, made


async def _despawn(tx, s, a, at, T):
    from ..physical import objects
    who, why = resolve(tx, s.pc_id, "person", a["target"])
    if who is None:
        it, why2 = resolve(tx, s.pc_id, "item", a["target"])
        if it is None:
            return False, why, "", []
        if tx.query_one("SELECT origin FROM items WHERE item_id=?", (it,))[0] != "cheat":
            return False, "Only what I made, Boss. That one was here before me.", "", []
        nm = _name(tx, it)
        ev = objects.destroy(tx, it, at, None, T)
        return True, f"unmade {nm}", "", [ev], True
    if tx.query_one("SELECT origin FROM bodies WHERE body_id=?", (who,))[0] != "cheat":
        return False, "Only what I made, Boss. That one was here before me.", "", []
    nm = _name(tx, who)
    ws = [_W("bodies", {"alive": 0, "dead_at": at, "awareness": "dead", "posture": "lying"}, "update", {"body_id": who})]
    evs = [_ev(tx, "physical.bodies", ws, {"command": "despawn", "body_id": who}, at, T, target_ids=[who])]
    if tx.query_one("SELECT 1 FROM positions WHERE body_id=?", (who,)) is not None:
        evs.append(_ev(tx, "physical.space", [_W("positions", {}, "delete", {"body_id": who})],
                       {"command": "despawn", "body_id": who}, at, T))
    return True, f"unmade {nm}", "", evs, True


async def _kill(tx, s, a, at, T):
    from ..physical import bodies
    who, why = _person(tx, s, a)
    if who is None:
        return False, why, "", []
    alive, _k = _alive(tx, who)
    if not alive:
        return False, "Already dead, Boss. Thorough, though.", "", []
    if bodies.excepted(tx, who):
        return False, "Reality lost that argument a long time ago, Boss.", "", []
    ev = bodies.kill(tx, who, "cheat", at, T, s.rng)
    return True, f"killed {_name(tx, who)}", "", [ev]


async def _revive(tx, s, a, at, T):
    from ..kernel import clock
    who, why = _person(tx, s, a)
    if who is None:
        return False, why, "", []
    alive, kind = _alive(tx, who)
    if alive:
        return False, "They're still breathing, Boss.", "", []
    if kind not in ("human", "lurker", "animal"):
        return False, "That one's past saving, Boss.", "", []
    evs = [_ev(tx, "physical.bodies", _heal_writes(tx, who, at, revive=True), {"command": "revive", "body_id": who}, at, T,
               target_ids=[who])]
    for q in tx.query("SELECT queue_id FROM event_queue WHERE status='pending' AND type='REANIMATION' AND "
                      "json_extract(payload,'$.body_id')=? ORDER BY queue_id", (who,)):
        evs.append(clock.cancel(tx, q[0], "revived", at, None, T))
    return True, f"revived {_name(tx, who)} (infection untouched)", "", evs


def _here_and_next(tx, place):
    near = [place]
    for r in tx.query("SELECT place_b FROM portals WHERE place_a=? UNION SELECT place_a FROM portals WHERE place_b=? ORDER BY 1",
                      (place, place)):
        if r[0] not in near:
            near.append(r[0])
    return near


async def _reveal(tx, s, a, at, T):
    place = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (s.pc_id,))[0]
    lines = []
    for p in _here_and_next(tx, place):
        who = []
        for b in tx.query("SELECT b.body_id, b.kind, a.display_name, a.goal_text, a.current_task FROM positions p "
                          "JOIN bodies b ON b.body_id=p.body_id LEFT JOIN actors a ON a.actor_id=b.body_id "
                          "WHERE p.place_id=? AND b.alive=1 AND b.body_id != ? ORDER BY b.body_id", (p, s.pc_id)):
            held = [tx.canon.get(r[0]).name for r in tx.query("SELECT def_ref FROM items WHERE holder_body=? AND holder_slot IN "
                                                               "('hand_l','hand_r') ORDER BY item_id", (b[0],))]
            doing = b[4] or b[3] or ""
            who.append(f"{b[2] or ('one of the dead' if b[1] == 'infected' else b[1])}"
                       + (f" — {doing}" if doing else "") + (f" (holding {', '.join(held)})" if held else ""))
        lines.append(f"{_name(tx, p)}: " + ("; ".join(who) if who else "nobody"))
    return True, f"revealed {len(lines)} places", "\n".join(lines), []


async def _mind(tx, s, a, at, T):
    who, why = _person(tx, s, a)
    if who is None:
        return False, why, "", []
    act = tx.query_one("SELECT goal_text FROM actors WHERE actor_id=?", (who,))
    if act is None:
        return False, f"{_name(tx, who)} has no mind to read, Boss.", "", []
    out = [f"Goal: {act[0] or 'none'}"]
    pl = tx.query_one("SELECT goal_text, steps FROM plans WHERE actor_id=?", (who,))
    if pl is not None:
        out.append(f"Plan: {pl[0]} — {'; '.join(json.loads(pl[1]))}")
    bel = [r[0] for r in tx.query("SELECT p.text FROM claim_holdings h JOIN propositions p ON p.prop_id=h.claim_id "
                                  "WHERE h.holder_id=? AND h.believed=1 AND h.superseded_by IS NULL "
                                  "ORDER BY h.confidence DESC, h.acquired_at DESC, h.claim_id LIMIT 5", (who,))]
    if bel:
        out.append("Believes: " + " | ".join(bel))
    loops = [r[0] for r in tx.query("SELECT text FROM open_loops WHERE holder_id=? AND status='open' "
                                    "ORDER BY strength DESC, created_at DESC, loop_id LIMIT 5", (who,))]
    if loops:
        out.append("On their mind: " + " | ".join(loops))
    last = tx.query_one("SELECT payload FROM events WHERE type='ACTION_START' AND actor_id=? ORDER BY seq DESC LIMIT 1", (who,))
    if last is not None:
        pl2 = json.loads(last[0])
        why2 = pl2.get("private_reason") or (pl2.get("intent") or {}).get("private_reason")
        if why2:
            out.append(f"Last reason: {why2}")
    return True, f"read {_name(tx, who)}'s mind", "\n".join(out), []


def brief_beliefs(tx, holder, place):
    """The truths /brief puts in a head: who is here, where they are (and what they want), and each
    faction's aims."""
    from ..mind.perception import BeliefFromPercept
    out = []
    pname = _name(tx, place)
    for b in tx.query("SELECT b.body_id, b.kind, a.display_name, a.goal_text FROM positions p JOIN bodies b ON b.body_id=p.body_id "
                      "LEFT JOIN actors a ON a.actor_id=b.body_id WHERE p.place_id=? AND b.alive=1 AND b.body_id != ? "
                      "ORDER BY b.body_id", (place, holder)):
        nm = b[2] or ("one of the dead" if b[1] == "infected" else f"a {b[1]}")
        out.append(BeliefFromPercept("body", b[0], "location", f"{nm} is here, in {pname}.", object_value=place))
        if b[3]:
            out.append(BeliefFromPercept("body", b[0], "wants", f"{nm} wants: {b[3]}", object_value=b[3][:200]))
    for g in tx.query("SELECT group_id, name, doctrine FROM groups WHERE kind='faction' ORDER BY group_id"):
        doc = json.loads(g[2] or "{}")
        aims = doc.get("aims") or doc.get("goal") or doc.get("truth_text")
        if aims:
            out.append(BeliefFromPercept("group", g[0], "aims", f"{g[1]}: {aims}", object_value=str(aims)[:200]))
    return out


def _grant_brief(tx, holder, beliefs, cause_event_id, at, T):
    from ..contracts.common import Channel, Fidelity
    from ..mind import perception
    if not beliefs:
        return 0
    perception.grant(tx, holder, event_id=cause_event_id, channel=Channel.VISUAL, fidelity=Fidelity.EXACT,
                     text="You simply know how things stand here.", source_id=None, at=at, turn_index=T, confidence=3,
                     beliefs=beliefs, detail={"cheat": True}, provenance="cheat")
    return len(beliefs)


async def _brief(tx, s, a, at, T):
    who, why = _person(tx, s, a)
    if who is None:
        return False, why, "", []
    if tx.query_one("SELECT 1 FROM actors WHERE actor_id=?", (who,)) is None or not _alive(tx, who)[0]:
        return False, f"{_name(tx, who)} has no mind to brief, Boss.", "", []
    place = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (s.pc_id,))[0]
    ev = _ev(tx, "cheats", [], {"command": "brief", "actor_id": who}, at, T)
    n = _grant_brief(tx, who, brief_beliefs(tx, who, place), ev.event_id, at, T)
    return True, f"briefed {_name(tx, who)} ({n} truths)", "", [ev]


async def _noise(tx, s, a, at, T):
    from ..contracts.events import Event, EventType
    pos = tx.query_one("SELECT place_id, x_m, y_m FROM positions WHERE body_id=?", (s.pc_id,))
    payload = {"source_db": a["db"], "kind": "noise", "text": "a loud noise" if a["db"] >= 100 else "a noise", "place_id": pos[0],
               "x_m": pos[1], "y_m": pos[2]}
    if "anchor" in a:
        an = [(r[0].lower(), r[1]) for r in tx.query("SELECT name, anchor_id FROM anchors WHERE place_id=? ORDER BY anchor_id", (pos[0],))]
        aid, cands = _match(a["anchor"], an)
        if aid is None:
            return False, f"No '{a['anchor']}' here, Boss.", "", []
        x, y = tx.query_one("SELECT x_m, y_m FROM anchors WHERE anchor_id=?", (aid,))
        payload.update(anchor_id=aid, x_m=x, y_m=y)
    ev = tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", origin="cheat", at=at, turn_index=T,
                               place_id=pos[0], payload=payload))
    return True, f"a {a['db']} dB noise", "", [ev]


async def _off(tx, s, a, at, T):
    from ..contracts.events import Event, EventType
    ev = tx.commit_event(Event(type=EventType.CHEAT_DEACTIVATED, writer="kernel.meta", origin="cheat", at=at, turn_index=T,
                               writes=[_W("meta", {"value": "0"}, "update", {"key": "cheat_active"})], payload={}))
    return True, "deactivated", "", [ev]




# ------------------------------------------------------------------------------------------ persona
async def persona(session, tx, name, outcome):
    from ..contracts.calls import CheatPersonaContext
    from ..contracts.common import CallClass
    from ..lanes.calllog import record
    from ..lanes.requests import build_request
    from .commands import CANNED_LINES
    recent = [r[0] for r in tx.query("SELECT persona_line FROM cheat_log WHERE persona_line != '' ORDER BY rowid DESC LIMIT 5")]
    from ..physical.bodies import excepted
    ctx = CheatPersonaContext(command=f"/{name}", outcome=outcome, recent_lines=recent, willis=excepted(tx, session.pc_id))
    req = build_request(session.config, CallClass.CHEAT_PERSONA, turn_index=None, context=ctx, ctx=ctx)
    resp = await session.client.call(req)
    record(tx, req, resp)
    text = (resp.text or "").strip().splitlines()[0].strip() if resp.parse_status == "ok" and (resp.text or "").strip() else ""
    if text and text not in recent:
        return text[:300]
    pair = CANNED_LINES[name]
    last = recent[0] if recent else None
    options = [p for p in pair if p != last] or list(pair)
    return session.rng.choice(tx, "cheats", f"canned:{name}:{len(recent)}:{_now(tx)}", options)


# ------------------------------------------------------------------------------------------ activate / execute
def activate(session):
    from ..contracts.events import Event, EventType
    from ..service.session import append_story
    from .commands import ACTIVATION_LINE, SHIMMER_NOTICE, CheatResult
    store = session.store
    with store.transaction() as tx:
        T = _turn(tx)
        ids = []
        if _meta(tx, "cheat_active") != "1":
            ev = tx.commit_event(Event(type=EventType.CHEAT_ACTIVATED, writer="kernel.meta", origin="cheat", at=_now(tx),
                                       turn_index=T, writes=[_W("meta", {"value": "1"}, "update", {"key": "cheat_active"})],
                                       payload={}))
            ids.append(ev.event_id)
        append_story(tx, T, "notice", SHIMMER_NOTICE)
        append_story(tx, T, "cheat", ACTIVATION_LINE)
    return CheatResult(ok=True, persona_line=ACTIVATION_LINE, detail=SHIMMER_NOTICE, event_ids=ids)


async def execute(session, command):
    from .commands import CheatResult
    try:
        return await _execute(session, command)
    except _Refuse as r:                     # found impossible after a write: rolled back, nothing happened
        return CheatResult(ok=False, persona_line=str(r), detail="")


async def _execute(session, command):
    from ..service.session import append_story
    from .commands import HELP_TEXT, SANDBOX_EXEMPT, CheatResult
    store = session.store
    name = command.name
    with store.transaction() as tx:
        at, T = _now(tx), _turn(tx)
        if name == "help":
            line = await persona(session, tx, "help", "listed the commands")
            append_story(tx, T, "cheat", f"{command.raw}\n{line}")
            return CheatResult(ok=True, persona_line=line, detail=HELP_TEXT)
        res = await HANDLERS[name](tx, session, command.args, at, T)
        ok, outcome, detail, evs = res[0], res[1], res[2], res[3]
        reconciliation = len(res) > 4 and res[4] is True
        if ok is False:
            append_story(tx, T, "cheat", f"{command.raw}\n{outcome}")
            return CheatResult(ok=False, persona_line=outcome, detail="")
        if ok is None:                       # a retired legend: a line, nothing else
            append_story(tx, T, "cheat", f"{command.raw}\n{outcome}")
            return CheatResult(ok=True, persona_line=outcome, detail="")
        if ok == "refused":                  # CHEAT-08: the one hard line — refused and logged
            _log(tx, command, "refused: the hard line", outcome, None, at, T, refused=True)
            append_story(tx, T, "cheat", f"{command.raw}\n{outcome}")
            return CheatResult(ok=False, persona_line=outcome, detail="")
        from .commands import DEACTIVATION_LINE
        line = DEACTIVATION_LINE if name == "off" else await persona(session, tx, name, outcome)
        ids = [e.event_id for e in evs if getattr(e, "event_id", None)]
        if name not in SANDBOX_EXEMPT:
            _log(tx, command, outcome, line, ids[0] if ids else None, at, T, reconciliation=reconciliation)
            if _meta(tx, "sandbox") != "1":
                _ev(tx, "kernel.meta", [_W("meta", {"value": "1"}, "update", {"key": "sandbox"})], {"sandbox": True}, at, T)
        append_story(tx, T, "cheat", f"{command.raw}\n{line}")
    return CheatResult(ok=True, persona_line=line, detail=detail or outcome, event_ids=ids)


def _log(tx, command, outcome, line, first_event, at, T, *, reconciliation=False, refused=False):
    payload = {"command": command.name, "raw": command.raw, "outcome": outcome}
    if reconciliation:
        payload["reconciliation"] = True
    if refused:
        payload["refused"] = True
    return _ev(tx, "cheats", [_W("cheat_log", {"entry_id": tx.mint("cht"), "turn_index": T, "command": command.raw,
                                               "outcome": outcome, "persona_line": line, "event_id": first_event}, "insert")],
               payload, at, T)


# ------------------------------------------------------------------------------------------ standing brief (CHEAT-11)
def standing_brief(tx, actor_id, turn_index, at):
    from ..mind.actor import fused
    if "standing_brief" not in (fused(tx, actor_id).model_dump(mode="json").get("tags") or []):
        return 0
    pos = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (actor_id,))
    if pos is None:
        return 0
    beliefs = brief_beliefs(tx, actor_id, pos[0])
    from ..mind.perception import BeliefFromPercept
    from ..physical.space import places_near
    for p in sorted(set(places_near(tx, pos[0], 2)) | {pos[0]}):
        n = tx.query_one("SELECT COUNT(*) FROM positions q JOIN bodies b ON b.body_id=q.body_id WHERE q.place_id=? "
                         "AND b.kind='infected' AND b.alive=1", (p,))[0]
        if n:
            beliefs.append(BeliefFromPercept("place", p, "infected_count", f"{n} of the dead are at {_name(tx, p)}.",
                                             object_value=str(n)))
    ev = _ev(tx, "cheats", [], {"standing_brief": actor_id}, at, turn_index)
    return _grant_brief(tx, actor_id, beliefs, ev.event_id, at, turn_index)


# ------------------------------------------------------------------------------------------ the owner's additions (P12b)
def _living_actor(tx, who):
    r = tx.query_one("SELECT b.alive FROM actors a JOIN bodies b ON b.body_id=a.actor_id WHERE a.actor_id=?", (who,))
    return r is not None and r[0] == 1


async def _will(tx, s, a, at, T):
    from ..mind import mind as mind_mod
    who, why = _person(tx, s, a)
    if who is None:
        return False, why, "", []
    if who == s.pc_id:
        return False, "That one's yours already, Boss.", "", []
    if not _living_actor(tx, who):
        return False, f"{_name(tx, who)} has no will left to bend, Boss.", "", []
    want = a["want"]
    ev = _ev(tx, "mind.actor", [_W("actors", {"goal_text": want}, "update", {"actor_id": who}),
                                _W("plans", {"actor_id": who, "goal_text": want, "steps": [], "standing_orders": [],
                                             "updated_at": at}, "upsert", {"actor_id": who})],
             {"command": "will", "actor_id": who, "want": want}, at, T)
    evs = [ev]
    for lp in tx.query("SELECT loop_id FROM open_loops WHERE holder_id=? AND status='open' AND kind IN ('goal','plan') "
                       "ORDER BY loop_id", (who,)):
        evs.append(mind_mod.close_loop(tx, lp[0], "abandoned", ev.event_id, at, T))
    mind_mod.open_loop(tx, who, "goal", f"I want: {want}", [], 3, ev.event_id, at, T)
    return True, f"{_name(tx, who)} now wants: {want}", "", evs


async def _forget(tx, s, a, at, T):
    from ..mind import mind as mind_mod
    who, why = _person(tx, s, a)
    if who is None:
        return False, why, "", []
    if not _living_actor(tx, who):
        return False, f"{_name(tx, who)} has nothing left to forget, Boss.", "", []
    subj, why = resolve(tx, s.pc_id, "person", a["about"])
    if subj is None:
        subj, why2 = resolve(tx, s.pc_id, "place", a["about"])
        if subj is None:
            return False, why, "", []
    like = f'%"{subj}"%'
    eps = [r[0] for r in tx.query("SELECT episode_id FROM episodes WHERE holder_id=? AND quarantined=0 AND "
                                  "(subject_ids LIKE ? OR place_id=?) ORDER BY episode_id", (who, like, subj))]
    bel = [r[0] for r in tx.query("SELECT h.claim_id FROM claim_holdings h JOIN propositions p ON p.prop_id=h.claim_id "
                                  "WHERE h.holder_id=? AND h.superseded_by IS NULL AND (p.subject_id=? OR p.object_value=?) "
                                  "ORDER BY h.claim_id", (who, subj, subj))]
    loops = [r[0] for r in tx.query("SELECT loop_id FROM open_loops WHERE holder_id=? AND status='open' AND subject_ids LIKE ? "
                                    "ORDER BY loop_id", (who, like))]
    ev = _ev(tx, "cheats", [], {"command": "forget", "actor_id": who, "about": subj}, at, T)
    evs = [ev]
    if eps:
        evs.append(_ev(tx, "mind.memory", [_W("episodes", {"quarantined": 1}, "update", {"episode_id": e}) for e in eps],
                       {"command": "forget", "actor_id": who, "episodes": eps}, at, T))
    ws = [_W("claim_holdings", {"superseded_by": c}, "update", {"holder_id": who, "claim_id": c}) for c in bel]
    if tx.query_one("SELECT 1 FROM acquaintance WHERE holder_id=? AND subject_id=?", (who, subj)) is not None:
        ws.append(_W("acquaintance", {}, "delete", {"holder_id": who, "subject_id": subj}))
    if ws:
        evs.append(_ev(tx, "mind.perception", ws, {"command": "forget", "actor_id": who, "beliefs": bel}, at, T))
    for lp in loops:
        evs.append(mind_mod.close_loop(tx, lp, "abandoned", ev.event_id, at, T))
    mind_mod.open_loop(tx, who, "question", "There's a gap in my memory I can't account for.", [], 1, ev.event_id, at, T)
    return True, (f"{_name(tx, who)} forgot {_name(tx, subj)}: {len(eps)} memories, {len(bel)} beliefs, "
                  f"{len(loops)} things on their mind"), "", evs


async def _infect(tx, s, a, at, T):
    from ..world import factions
    who, why = _person(tx, s, a)
    if who is None:
        return False, why, "", []
    alive, kind = _alive(tx, who)
    if not alive or kind not in ("human", "lurker"):
        return False, "There's nothing in there left to infect, Boss.", "", []
    pw = a.get("pathway", "wet")
    try:
        rec = tx.canon.find("pathway", pw)
    except KeyError:
        return False, f"No strain called '{pw}', Boss.", "", []
    if tx.query_one("SELECT 1 FROM infections WHERE body_id=? AND pathway=?", (who, pw)) is not None:
        return False, "Already carrying it, Boss.", "", []
    ev = _ev(tx, "cheats", [], {"command": "infect", "body_id": who, "pathway": pw}, at, T)
    ev2 = _ev(tx, "physical.bodies", [_W("infections", {"body_id": who, "pathway": pw, "exposed_at": at,
                                                         "stage": rec.stages[0].name, "cause_event": ev.event_id,
                                                         "known_to_self": 0}, "insert")],
              {"command": "infect", "body_id": who, "pathway": pw}, at, T, target_ids=[who], cause_event_id=ev.event_id)
    where = ""
    for g in tx.query("SELECT group_id FROM group_members WHERE actor_id=? ORDER BY group_id", (who,)):
        if factions.in_session(tx, g[0], at) is not None:
            where = " — in the middle of the council's meeting"
            break
    return True, f"{_name(tx, who)} carries the {pw} strain now{where}", "", [ev, ev2]


def _risen_from(tx, who):
    r = tx.query_one("SELECT body_id FROM infected_state WHERE risen_from=? ORDER BY body_id LIMIT 1", (who,))
    return None if r is None else r[0]


async def _cure(tx, s, a, at, T):
    from ..physical import bodies
    who, why = _person(tx, s, a)
    if who is None:
        return False, why, "", []
    alive, kind = _alive(tx, who)
    if not alive:
        risen = _risen_from(tx, who)
        if risen is None or not _alive(tx, risen)[0]:
            return False, "Dead and staying dead, Boss. Nothing to cure.", "", []
        ev = bodies.kill(tx, risen, "cured", at, T, s.rng, extra={"core_intact": 0})
        return True, f"cured what {_name(tx, who)} became: it dies at once", "", [ev]
    rows = [r[0] for r in tx.query("SELECT pathway FROM infections WHERE body_id=? ORDER BY pathway", (who,))]
    if not rows:
        return False, "Nothing in them to cure, Boss.", "", []
    ev = _ev(tx, "physical.bodies", [_W("infections", {}, "delete", {"body_id": who, "pathway": p}) for p in rows],
             {"command": "cure", "body_id": who, "pathways": rows}, at, T, target_ids=[who])
    return True, f"cured {_name(tx, who)} of {', '.join(rows)}", "", [ev]


async def _horde(tx, s, a, at, T):
    from ..world import hordes
    if "place" in a:
        place, why = resolve(tx, s.pc_id, "place", a["place"])
        if place is None:
            return False, why, "", []
    else:
        place = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (s.pc_id,))[0]
    zone = tx.query_one("SELECT zone_id FROM places WHERE place_id=?", (place,))[0]
    pool = hordes.pool(tx, zone) if zone else {}
    comp, left = {}, a["n"]
    for tid, (act, _dorm) in sorted(pool.items(), key=lambda kv: (-kv[1][0], kv[0])):
        k = min(act, left)
        if k > 0:
            comp[tid] = k
            left -= k
    if not comp:
        return False, "No dead to call up around there, Boss.", "", []
    ev = _ev(tx, "cheats", [], {"command": "horde", "place_id": place, "composition": comp}, at, T)
    try:
        hid = hordes.form(tx, "drawn", zone, comp, place, at, T, ev.event_id)
    except ValueError as e:
        raise _Refuse(f"They won't come, Boss: {e}.") from e
    return True, f"{sum(comp.values())} of the dead gathered, heading for {_name(tx, place)}", "", [ev], hid


async def _mega(tx, s, a, at, T):
    from ..world import hordes
    if tx.query_one("SELECT 1 FROM hordes WHERE kind='mega' AND status != 'gone'") is not None:
        return False, "One's already coming, Boss. Patience.", "", []
    ev = _ev(tx, "cheats", [], {"command": "mega"}, at, T)
    hid = hordes.mega(tx, s.rng, at, T, ev.event_id)
    if hid is None:
        raise _Refuse("There aren't enough dead out there to make one, Boss.")
    return True, "the Mega Horde has set out", "", [ev]


async def _census(tx, s, a, at, T):
    from ..society import population
    from ..world import hordes
    c = hordes.census(tx)
    lines = [f"The dead: {c['total']} — {c['bodies']} walking about, {sum(h['count'] for h in c['hordes'])} in "
             f"{len(c['hordes'])} hordes, the rest in the districts."]
    for zid, types in sorted(c["pools"].items()):
        act = sum(v[0] for v in types.values())
        dorm = sum(v[1] for v in types.values())
        lines.append(f"  {_zone_name(tx, zid)}: {act} on their feet, {dorm} still")
    for h in c["hordes"]:
        lines.append(f"  Horde {h['horde_id']} ({h['kind']}): {h['count']} at {_name(tx, h['place_id'])}, {h['status']}")
    for st in tx.query("SELECT settlement_id, name FROM settlements ORDER BY settlement_id"):
        cs = population.census(tx, st[0])
        lines.append(f"The living at {st[1]}: {cs.total} ({len(cs.named)} named)")
    return True, f"counted {c['total']} dead", "\n".join(lines), []


def _zone_name(tx, zid):
    r = tx.query_one("SELECT name FROM zones WHERE zone_id=?", (zid,))
    return r[0] if r else zid


class _Refuse(Exception):
    """A command that turned out not to be possible after something was written: the transaction
    is rolled back and the persona line says why."""


HANDLERS = {"give": _give, "heal": _heal, "god": _god, "tp": _tp, "set": _set, "time": _time, "weather": _weather,
            "rep": _rep, "spawn": _spawn, "despawn": _despawn, "kill": _kill, "revive": _revive, "reveal": _reveal,
            "mind": _mind, "brief": _brief, "noise": _noise, "off": _off,
            "will": _will, "forget": _forget, "infect": _infect, "cure": _cure, "horde": _horde, "mega": _mega,
            "census": _census}


# ------------------------------------------------------------------------------------------ Willis (D-79, D-102)
def _blend_in(tx, bid, pc, place, d, at, T):
    """Fredrick blends in whenever Willis is blending in: whoever knows the PC knows him, and feels
    about him as they feel about the PC; he joins the PC's groups."""
    from ..contracts.events import Event, EventType
    from ..mind.perception import describe_dossier
    name = tx.query_one("SELECT display_name FROM actors WHERE actor_id=?", (bid,))[0]
    desc = describe_dossier(d)
    axes = ("trust", "fear", "respect", "affection", "resentment", "obligation")
    evs = []
    for (holder,) in [tuple(r) for r in tx.query("SELECT holder_id FROM acquaintance WHERE subject_id=? AND holder_id != ? "
                                                 "ORDER BY holder_id", (pc, bid))]:
        evs.append(tx.commit_event(Event(type=EventType.PERCEIVE, writer="mind.perception", origin="cheat", at=at, turn_index=T,
                                         actor_id=holder, payload={"holder_id": holder, "seed": True, "blend_in": bid},
                                         writes=[_W("acquaintance", {"holder_id": holder, "subject_id": bid, "known_name": name,
                                                                     "description": desc, "first_met": at, "last_seen": at,
                                                                     "last_seen_place": place}, "upsert",
                                                    {"holder_id": holder, "subject_id": bid})])))
        r = tx.query_one(f"SELECT {', '.join(axes)} FROM relationships WHERE from_id=? AND to_id=?", (holder, pc))
        if r is not None:
            vals = {"from_id": holder, "to_id": bid, **{a: r[i] for i, a in enumerate(axes)}, "kind": "acquaintance",
                    "causes": {}, "updated_at": at}
            evs.append(tx.commit_event(Event(type=EventType.RELATION_CHANGE, writer="mind.mind", origin="cheat", at=at,
                                             turn_index=T, actor_id=holder,
                                             payload={"from_id": holder, "to_id": bid, "blend_in": True},
                                             writes=[_W("relationships", vals, "upsert", {"from_id": holder, "to_id": bid})])))
    gs = [r[0] for r in tx.query("SELECT group_id FROM group_members WHERE actor_id=? AND status='member' ORDER BY group_id", (pc,))]
    ws = [_W("group_members", {"group_id": g, "actor_id": bid, "role": "member", "standing": 0, "since": at, "status": "member"},
             "upsert", {"group_id": g, "actor_id": bid}) for g in gs]
    if ws:
        evs.append(_ev(tx, "society.group", ws, {"command": "spawn", "actor_id": bid, "blend_in": gs}, at, T))
    return evs


_WONDER_ME = re.compile(r"^(i|i'm|i'll|my)\b", re.I)
_WONDER_HIM = re.compile(r"^(willis|he)\s+", re.I)


async def _wonder(tx, s, a, at, T):
    from ..physical import bodies
    if not bodies.excepted(tx, s.pc_id):
        return False, "You're not him, Boss.", "", []
    what = a["what"].strip().replace("{", "").replace("}", "").strip()
    what = _WONDER_HIM.sub("", what.rstrip(".").strip()).strip()
    if not what or _WONDER_ME.match(what):
        return False, "Say it the way they'd see it, Boss: /wonder walks through the wall", "", []
    if _meta(tx, "pending_wonder"):
        return False, "One wonder at a time, Boss. The last one hasn't happened yet.", "", []
    ev = _ev(tx, "kernel.meta", [_W("meta", {"key": "pending_wonder", "value": what}, "upsert", {"key": "pending_wonder"})],
             {"command": "wonder", "what": what}, at, T)
    return True, f"{what}, as the next moment begins", "", [ev]


HANDLERS["wonder"] = _wonder


def take_wonder(tx, pc_id, turn_index, at):
    from ..contracts.events import Event, EventType
    what = _meta(tx, "pending_wonder")
    if not what:
        return None
    ev = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", origin="cheat", at=at, turn_index=turn_index,
                               actor_id=pc_id,
                               payload={"actor_id": pc_id, "def_id": "wonder", "verb": "wonder", "target_id": None,
                                        "destination_id": None, "item_id": None, "est_duration_s": 0, "visible": True,
                                        "seen": what, "continues_task": False, "label": what, "goal": "", "attention": None}))
    _ev(tx, "kernel.meta", [_W("meta", {"key": "pending_wonder", "value": ""}, "upsert", {"key": "pending_wonder"})],
        {"wonder": "done"}, at, turn_index)
    return ev


def start_life(tx, pc_id, record):
    from ..contracts.events import Event, EventType
    from ..physical import bodies
    at, T = _now(tx), 0
    evs = [tx.commit_event(Event(type=EventType.CHEAT_ACTIVATED, writer="kernel.meta", origin="cheat", at=at, turn_index=T,
                                 payload={"start": True},
                                 writes=[_W("meta", {"key": "cheat_active", "value": "1"}, "upsert", {"key": "cheat_active"})]))]
    evs.append(_ev(tx, "kernel.meta", [_W("meta", {"key": "sandbox", "value": "1"}, "upsert", {"key": "sandbox"})],
                   {"sandbox": True}, at, T))
    evs.append(_ev(tx, "mind.actor", [_W("actors", {"quarantine": 1}, "update", {"actor_id": pc_id})],
                   {"command": "start", "actor_id": pc_id}, at, T))
    if "reality_exception" in record.capability.tags:
        evs.append(bodies.grant_exception(tx, pc_id, at, T, origin="cheat"))
    if "fickle" in (record.tags or []):
        from ..mind.mind import add_fickle
        evs.append(add_fickle(tx, pc_id, at, T, origin="cheat"))
    evs.append(_ev(tx, "cheats", [_W("cheat_log", {"entry_id": tx.mint("cht"), "turn_index": T, "command": "start",
                                                   "outcome": f"began a life as {record.identity.name}", "persona_line": "",
                                                   "event_id": evs[0].event_id}, "insert")],
                   {"command": "start", "raw": "start", "outcome": f"began a life as {record.identity.name}"}, at, T))
    return [e for e in evs if e is not None]
