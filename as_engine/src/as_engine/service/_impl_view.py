"""Implementation of service/view.py."""
from __future__ import annotations

import json

WEATHER_WORDS = {"clear": "Clear", "overcast": "Overcast", "rain": "Raining", "storm": "Storm", "fog": "Fog", "wind": "Windy",
                 "heat": "Hot", "snow": "Snowing"}
SEVERITY_VIEW = {"minor": "minor", "significant": "serious", "severe": "severe", "catastrophic": "critical"}
BAND_WORDS = {"clean": "clean success", "cost": "success with a cost", "fail": "failure", "break": "bad failure"}


def condition_word(c):
    return "pristine" if c >= 90 else "good" if c >= 70 else "worn" if c >= 45 else "damaged" if c >= 25 else "failing" if c >= 1 else "broken"


def resolve_word(cur, mx):
    r = cur / mx if mx else 0
    return "steady" if r >= 0.8 else "shaken" if r >= 0.6 else "fraying" if r >= 0.4 else "breaking" if r > 0 else "broken"


def bleeding_word(pct):
    return "none" if pct <= 0 else "oozing" if pct < 0.1 else "bleeding" if pct < 1.5 else "bleeding badly" if pct < 6 else "pouring"


def need_word(stage):
    return "fine" if stage <= 1 else "noticeable" if stage == 2 else "bad" if stage == 3 else "severe" if stage == 4 else "critical"


def _row(s, sql, p=()):
    r = s.query_one(sql, p)
    return dict(r) if r is not None else None


def _ref(refs, prefix, internal):
    from ..narration._impl_location import _assign
    return _assign(refs, prefix, internal, {})


def _rounds_left(tx, it):
    d = tx.canon.get(it["def_ref"])
    props = it["props"] or {}
    if d.firearm is None:
        return None
    if d.firearm.feeds_from in ("cylinder", "internal"):
        return int(props.get("rounds", 0))
    mag = [c for c in it.get("contents", []) if "rounds" in (c.get("props") or {})]
    n = sum(int(c["props"]["rounds"]) for c in mag)
    return n + (1 if props.get("chambered") else 0)


def _item_view(tx, refs, it, where):
    from ..contracts.view import ItemView
    d = tx.canon.get(it["def_ref"])
    cond = _row(tx, "SELECT condition FROM items WHERE item_id=?", (it["item_id"],))["condition"]
    detail = ""
    rl = _rounds_left(tx, it)
    if rl is not None:
        detail = f"{rl} round{'s' if rl != 1 else ''}"
    elif "rounds" in (it["props"] or {}):
        n = int(it["props"]["rounds"])
        detail = f"{n} round{'s' if n != 1 else ''}"
    actions = []
    armed = d.firearm is not None or d.melee is not None
    if where == "hand":
        actions.append("Drop")
        if armed:
            actions.append("Put away")
        if d.firearm is not None:
            actions.append("Reload")
    else:
        actions.append("Take out")
    if d.kind == "food":
        actions.append("Eat")
    elif d.kind == "water":
        actions.append("Drink")
    elif d.kind == "medical":
        actions.append("Use")
    mass = d.mass_g * it["qty"] / 1000
    return ItemView(ref=_ref(refs, "i", it["item_id"]), name=it["name"], qty=it["qty"], condition_word=condition_word(cond), detail=detail,
                    mass_text=f"{mass:.1f} kg", actions=actions)


def _container_view(tx, refs, it):
    from ..contracts.view import ContainerView
    d = tx.canon.get(it["def_ref"])
    used = sum(tx.canon.get(c["def_ref"]).bulk * c["qty"] for c in it["contents"])
    contents = []
    for c in it["contents"]:
        if tx.canon.get(c["def_ref"]).container is not None:
            contents.append(_container_view(tx, refs, c))
        else:
            contents.append(_item_view(tx, refs, c, "inside"))
    return ContainerView(item=_item_view(tx, refs, it, "worn"), bulk_used=used, bulk_max=max(1, d.container.capacity_bulk), contents=contents)


def build_view(tx, session):
    from ..contracts.common import ANATOMY_WORDS, Lane, Verb
    from ..contracts.view import (BodyView, ClockView, InventoryView, JournalView, LaneStatus, LanesView, MapPlace, MapView,
                                  MechanicsReceipt, NeedView, PersonView, PlayView, ResolveView, SuggestionView, WoundView)
    from ..kernel.clock import format_clock, now, turn_index, world_time
    from ..mind.affordance import enumerate_affordances
    from ..narration._impl_location import LIGHT_WORDS, impairment_word, latest_view, light_of
    from ..narration.location import describe
    from ..physical import objects
    from ..physical.bodies import effective_bleed, impairment
    pc = session.pc_id
    refs = {}
    session.extras["view_refs"] = refs
    at = now(tx)
    T = turn_index(tx)
    wt = world_time(at)
    pos = _row(tx, "SELECT place_id FROM positions WHERE body_id=?", (pc,))
    place = _row(tx, "SELECT * FROM places WHERE place_id=?", (pos["place_id"],))
    wc = _row(tx, "SELECT weather FROM world_clock")
    clock_v = ClockView(day=wt.day, time_text=format_clock(at), part_of_day=wt.part_of_day, weather_text=WEATHER_WORDS.get(wc["weather"], wc["weather"]),
                        light_text=LIGHT_WORDS[light_of(tx, place, at)].capitalize())
    loc = describe(tx, pc, at, refs)
    # inventory
    tree = objects.inventory_tree(tx, pc)
    hands, worn, conts = [], [], []
    for it in tree:
        d = tx.canon.get(it["def_ref"])
        if it["slot"] in ("hand_l", "hand_r"):
            hands.append(_item_view(tx, refs, it, "hand"))
        elif d.container is not None:
            conts.append(_container_view(tx, refs, it))
        else:
            worn.append(_item_view(tx, refs, it, "worn"))
    inv = InventoryView(hands=hands, worn=worn, containers=conts, carried_mass_kg=round(objects.carried_mass_kg(tx, pc), 2),
                        load_word=objects.load_word(tx, pc))
    # body
    b = _row(tx, "SELECT * FROM bodies WHERE body_id=?", (pc,))
    wounds = []
    for w in tx.query("SELECT * FROM wounds WHERE body_id=? AND healed_at IS NULL ORDER BY created_at, wound_id", (pc,)):
        w = dict(w)
        wounds.append(WoundView(where=ANATOMY_WORDS[w["anatomy"]], what=f"{w['type']} wound", severity_word=SEVERITY_VIEW[w["severity"]],
                                bleeding_word=bleeding_word(effective_bleed(tx, w["wound_id"])), treated=json.loads(w["treatment"]) != []))
    n = _row(tx, "SELECT * FROM needs WHERE body_id=?", (pc,))
    needs = []
    if n:
        for label, col in (("Thirst", "thirst_stage"), ("Hunger", "hunger_stage"), ("Tiredness", "fatigue_stage")):
            needs.append(NeedView(name=label, level=min(5, n[col]), word=need_word(n[col])))
    pain = b.get("pain", 0) or 0
    needs.append(NeedView(name="Pain", level=min(5, pain), word=need_word(pain)))
    a = _row(tx, "SELECT * FROM actors WHERE actor_id=?", (pc,))
    st = []
    if b["posture"] != "standing":
        st.append(b["posture"])
    if b["awareness"] != "awake":
        st.append(b["awareness"])
    if _row(tx, "SELECT hidden FROM positions WHERE body_id=?", (pc,))["hidden"]:
        st.append("hidden")
    body = BodyView(wounds=wounds, needs=needs, impairment_word=impairment_word(impairment(tx, pc)),
                    resolve=ResolveView(cur=a["resolve_cur"], max=a["resolve_max"], word=resolve_word(a["resolve_cur"], a["resolve_max"])),
                    status_words=st)
    # people
    view_now = {p["source_id"] for p in latest_view(tx, pc) if p["source_id"]}
    people = []
    for r in tx.query("SELECT * FROM acquaintance WHERE holder_id=? ORDER BY last_seen DESC, subject_id", (pc,)):
        r = dict(r)
        s = r["subject_id"]
        label = r["known_name"] or r["description"]
        rel = _row(tx, "SELECT * FROM relationships WHERE from_id=? AND to_id=?", (pc, s))
        rw = []
        if rel:
            if rel["trust"] >= 2: rw.append("you trust them")
            if rel["trust"] <= -2: rw.append("you distrust them")
            if rel["affection"] >= 2: rw.append("you care about them")
            if rel["respect"] >= 2: rw.append("you respect them")
            if rel["fear"] >= 2: rw.append("you fear them")
            if rel["resentment"] >= 2: rw.append("you resent them")
            if rel["obligation"] >= 2: rw.append("you owe them")
            if rel["obligation"] <= -2: rw.append("they owe you")
        last = tx.query_one("SELECT MAX(at) FROM percept_log WHERE holder_id=? AND source_id=?", (pc, s))[0]
        if s in view_now:
            seen = "here now"
        elif last is None:
            seen = "not seen yet"
        else:
            pn = _row(tx, "SELECT name FROM places WHERE place_id=?", (r.get("last_seen_place"),)) if r.get("last_seen_place") else None
            seen = f"last seen day {world_time(last).day}, {format_clock(last)}" + (f", {pn['name']}" if pn else "")
        know = [x[0] for x in tx.query("SELECT p.text FROM claim_holdings h JOIN propositions p ON p.prop_id=h.claim_id WHERE h.holder_id=? "
                                        "AND h.believed=1 AND h.superseded_by IS NULL AND p.subject_type='body' AND p.subject_id=? "
                                        "ORDER BY h.acquired_at DESC, h.claim_id LIMIT 5", (pc, s))]
        prom = [x[0] for x in tx.query("SELECT text FROM open_loops WHERE holder_id=? AND status='open' AND kind IN ('promise_made','promise_owed') "
                                        "AND subject_ids LIKE ? ORDER BY created_at, loop_id", (pc, f'%"{s}"%'))]
        alive = "alive" if s in view_now else "unknown"
        people.append(PersonView(ref=_ref(refs, "p", s), label=label, relation_words=rw, last_seen_text=seen, what_you_know=know,
                                 promises=prom, alive_known=alive))
    # journal
    def loops(kinds):
        ph = ",".join("?" * len(kinds))
        return [x[0] for x in tx.query(f"SELECT text FROM open_loops WHERE holder_id=? AND status='open' AND kind IN ({ph}) "
                                       "ORDER BY created_at, loop_id", (pc, *kinds))]
    rum = [x[0] for x in tx.query("SELECT p.text FROM claim_holdings h JOIN propositions p ON p.prop_id=h.claim_id WHERE h.holder_id=? "
                                  "AND h.superseded_by IS NULL AND (h.provenance LIKE 'rumour:%' OR h.acquired_via LIKE 'rumour:%' OR h.acquired_via IN "
                                  "(SELECT event_id FROM events WHERE type = 'RUMOUR_SPREAD')) ORDER BY h.acquired_at, h.claim_id", (pc,))]
    journal = JournalView(promises_made=loops(("promise_made",)), promises_owed=loops(("promise_owed",)),
                          goals=loops(("goal", "plan", "desire")), rumours=rum,
                          lessons=[x[0] for x in tx.query("SELECT text FROM lessons WHERE holder_id=? ORDER BY at, lesson_id", (pc,))])
    # map
    known = [dict(r) for r in tx.query("SELECT k.*, p.name FROM known_places k JOIN places p ON p.place_id=k.place_id WHERE k.holder_id=? "
                                       "ORDER BY p.name, k.place_id", (pc,))]
    kset = {k["place_id"] for k in known}
    places = []
    for k in known:
        ex = [x[0] for x in tx.query("SELECT name FROM portals WHERE kind != 'wall' AND ((place_a=? AND place_b IN (%s)) OR (place_b=? AND place_a IN (%s))) "
                                     "ORDER BY portal_id" % (",".join("?" * len(kset)), ",".join("?" * len(kset))),
                                     (k["place_id"], *sorted(kset), k["place_id"], *sorted(kset)))]
        places.append(MapPlace(ref=_ref(refs, "m", k["place_id"]), label=k["name"], visited=bool(k["visited"]), here=k["place_id"] == pos["place_id"],
                               exits_known=ex))
    # suggestions
    sugg, smap = [], {}
    aff = enumerate_affordances(tx, pc, tx.canon.all("affordance"), at, T)
    rem = session.extras.get("remainder")
    if rem:
        smap["s1"] = {"remainder": rem, "label": f"Continue: {rem}"}
        sugg.append(SuggestionView(ref="s1", label=f"Continue: {rem}", mode="do"))
    top, seen_labels = [], set()
    for o in aff.options:
        if o.verb == Verb.WAIT or o.def_id == "observe_area" or o.ui_label in seen_labels:
            continue
        seen_labels.add(o.ui_label)
        top.append(o)
    top = top[: (5 if not rem else 4)]
    for o in top:
        r = f"s{len(sugg) + 1}"
        smap[r] = {"signature": o.signature, "label": o.ui_label}
        sugg.append(SuggestionView(ref=r, label=o.ui_label, mode="say" if o.verb == Verb.SPEAK else "do"))
    wait = next((o for o in aff.options if o.def_id == "observe_area"), None) or next((o for o in aff.options if o.verb == Verb.WAIT), None)
    if wait is not None:
        r = f"s{len(sugg) + 1}"
        smap[r] = {"signature": wait.signature, "label": "Wait and watch"}
        sugg.append(SuggestionView(ref=r, label="Wait and watch", mode="do"))
    session.extras["suggestions"] = smap
    # lanes
    c = session.client
    lanes = LanesView(A=LaneStatus(label="Main model", ok=not c.is_down(Lane.A), model=session.config.lanes[Lane.A].model),
                      B=LaneStatus(label="Second model", ok=not c.is_down(Lane.B), model=session.config.lanes[Lane.B].model))
    mech = None
    if session.settings.show_mechanics != "off":
        lines = []
        for e in tx.query("SELECT payload FROM events WHERE type='CHECK_RESOLVED' AND actor_id=? AND turn_index=? ORDER BY seq", (pc, T)):
            p = json.loads(e[0])
            base, _, side = p["def_id"].partition(":")
            d = tx.canon.find("affordance", base)
            what = d.ui_label.split('{')[0].strip() or d.id.replace('_', ' ')
            if side == "defend":
                what = "Resisting " + what.lower()
            line = f"{what}: {BAND_WORDS[p['band']]}"
            if session.settings.show_mechanics == "full":
                line += f" (needed {p['target']} or less, rolled {p['draw']})"
            lines.append(line)
        mech = MechanicsReceipt(lines=lines)
    return PlayView(run_id=session.run_id, turn_index=T, pc_name=a["display_name"], alive=bool(b["alive"]), clock=clock_v, location=loc,
                    inventory=inv, body=body, people=people, journal=journal, map=MapView(places=places), suggestions=sugg, lanes=lanes,
                    sandbox=tx.query_one("SELECT value FROM meta WHERE key='sandbox'")[0] == "1", mechanics=mech)
