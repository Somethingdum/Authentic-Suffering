"""Implementation of narration/location.py."""
from __future__ import annotations

import json

LIGHT_WORDS = {0: "pitch dark", 1: "dim", 2: "low light", 3: "lit", 4: "bright"}
KIND_WORDS = {"room": "room", "building": "building", "street": "street", "outdoor": "open space", "vehicle": "vehicle",
              "tunnel": "tunnel"}
NUMBER_WORDS = ["no", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve"]
AMBIENT = {  # (indoor, weather) -> sentence
    (True, "wind"): "Wind pushes at the building.", (True, "rain"): "Rain drums on the roof.",
    (True, "storm"): "A storm batters the building.", (False, "wind"): "Wind gusts through.",
    (False, "rain"): "Rain falls steadily.", (False, "storm"): "A storm tears through.",
    (False, "snow"): "Snow is falling.", (False, "fog"): "Fog hangs low.", (False, "heat"): "The heat presses down.",
}
NOTABLE_KINDS = ("cover", "furniture", "hiding_spot", "window")
DB_WORDS = ((45, "quiet"), (70, "some noise"), (95, "noisy"))


def _row(s, sql, p=()):
    r = s.query_one(sql, p)
    return dict(r) if r is not None else None


def _art(s):
    from ..mind.perception import with_article
    return with_article(s)


def _cap(s):
    return s[:1].upper() + s[1:] if s else s


def next_ref(refs, prefix):
    if refs is None:
        return None
    n = 1 + sum(1 for k in refs if k.startswith(prefix) and k[len(prefix):].isdigit())
    return f"{prefix}{n}"


def _assign(refs, prefix, internal, local_counter):
    if refs is None:
        local_counter[prefix] = local_counter.get(prefix, 0) + 1
        return f"{prefix}{local_counter[prefix]}"
    for k, v in refs.items():
        if v == internal and k.startswith(prefix):
            return k
    r = next_ref(refs, prefix)
    refs[r] = internal
    return r


def light_of(tx, place, at):
    from ..kernel.clock import daylight_level
    if place["indoor"]:
        return place["light_level"]
    w = _row(tx, "SELECT weather FROM world_clock")["weather"]
    return daylight_level(at, w)


def latest_view(tx, pc_id):
    """The PC's latest standing-view rows (event_id 'scene:…' with the greatest at, then turn)."""
    r = _row(tx, "SELECT turn_index, at FROM percept_log WHERE holder_id=? AND event_id LIKE 'scene:%' ORDER BY turn_index DESC, at DESC LIMIT 1",
             (pc_id,))
    if r is None:
        return []
    return [dict(x) for x in tx.query("SELECT * FROM percept_log WHERE holder_id=? AND event_id LIKE 'scene:%' AND turn_index=? AND at=? "
                                      "ORDER BY percept_id", (pc_id, r["turn_index"], r["at"]))]


def describe(tx, pc_id, at, refs=None):
    from ..contracts.view import ExitView, LocationView, PersonChip, SeenThing
    from ..mind.perception import word_for
    local = {}
    pos = _row(tx, "SELECT * FROM positions WHERE body_id=?", (pc_id,))
    place = _row(tx, "SELECT * FROM places WHERE place_id=?", (pos["place_id"],))
    known = {r[0] for r in tx.query("SELECT place_id FROM known_places WHERE holder_id=?", (pc_id,))}
    area = ""
    if place["parent_id"] and place["parent_id"] in known:
        area = _row(tx, "SELECT name FROM places WHERE place_id=?", (place["parent_id"],))["name"]
    elif place["zone_id"]:
        area = _row(tx, "SELECT name FROM zones WHERE zone_id=?", (place["zone_id"],))["name"]
    lines = []
    # 1 size + material + kind + light
    m2 = place["width_m"] * place["depth_m"]
    lo, hi = sorted((place["width_m"], place["depth_m"]))
    size = "small" if m2 < 15 else ("" if m2 <= 60 else ("long" if hi >= 2 * lo else "large"))
    mat = place["material"] if place["indoor"] and place["material"] not in ("open_air",) else ""
    kind = KIND_WORDS.get(place["kind"], place["kind"].replace("_", " "))
    light = light_of(tx, place, at)
    words = " ".join(w for w in (size, mat.replace("_", " "), kind) if w)
    lines.append(f"{_cap(_art(words))}, {LIGHT_WORDS[light]}.")
    # 2 ambient
    wc = _row(tx, "SELECT weather, wind_level FROM world_clock")
    amb = AMBIENT.get((bool(place["indoor"]), wc["weather"]))
    if amb is None or (wc["weather"] == "wind" and wc["wind_level"] < 1):
        amb = "It is quiet." if place["ambient_db"] < 35 else ("There is a low background noise." if place["ambient_db"] < 50 else "It is noisy.")
    lines.append(amb)
    # 3 notable anchors
    if light > 0:
        an = [r["name"] for r in tx.query("SELECT name, kind FROM anchors WHERE place_id=? ORDER BY anchor_id", (place["place_id"],))
              if r["kind"] in NOTABLE_KINDS][:3]
        if len(an) == 1:
            lines.append(f"There is {_art(an[0])} here.")
        elif len(an) == 2:
            lines.append(f"There are {_art(an[0])} and {_art(an[1])} here.")
        elif len(an) == 3:
            lines.append(f"There are {_art(an[0])}, {_art(an[1])} and {_art(an[2])} here.")
    view = latest_view(tx, pc_id)
    # 4 traces (P10)
    tr = [p["text"] for p in view if p["source_id"] and str(p["source_id"]).startswith("trc_")]
    if tr:
        lines.append(" ".join(tr))
    # 5 occupancy
    here = []
    for p in view:
        s = p["source_id"]
        if s and s.startswith("act_") and s not in here:
            bp = _row(tx, "SELECT place_id FROM positions WHERE body_id=?", (s,))
            if bp and bp["place_id"] == place["place_id"]:
                here.append(s)
    n = len(here)
    if n == 0:
        lines.append("You're alone.")
    elif n == 1:
        lines.append("One other person is here.")
    else:
        lines.append(f"{NUMBER_WORDS[n] if n < len(NUMBER_WORDS) else n} other people are here.")
    # 6 cover
    if light > 0:
        anc = [dict(r) for r in tx.query("SELECT * FROM anchors WHERE place_id=? ORDER BY anchor_id", (place["place_id"],))]
        best = sorted([a for a in anc if a["cover"] >= 2], key=lambda a: (-a["cover"], a["anchor_id"]))
        hide = sorted([a for a in anc if a["cover"] <= 1 and a["concealment"] >= 2], key=lambda a: (-a["concealment"], a["anchor_id"]))
        parts = []
        if best:
            b = best[0]
            parts.append(f"The {b['name']} would stop a bullet." if b["cover"] >= 3 else f"The {b['name']} gives some cover.")
        if hide:
            parts.append(f"The {hide[0]['name']} would hide you.")
        if parts:
            lines.append(" ".join(parts))
    # can_see
    can_see, people = [], []
    canon = tx.canon
    for p in view:
        s = p["source_id"]
        if s and s.startswith("itm_"):
            it = _row(tx, "SELECT def_ref FROM items WHERE item_id=?", (s,))
            name = canon.get(it["def_ref"]).name if it else "something"
            detail = p["text"][len(name):].strip().rstrip(".") if p["text"].lower().startswith(name.lower()) else ""
            can_see.append(SeenThing(ref=_assign(refs, "i", s, local), name=name, detail=detail))
    seen_bodies = []
    for p in view:
        s = p["source_id"]
        det = json.loads(p["detail"])
        if p["channel"] != "visual":
            continue
        if s and s.startswith("act_"):
            if s in seen_bodies:
                continue
            seen_bodies.append(s)
            kn = _row(tx, "SELECT known_name FROM acquaintance WHERE holder_id=? AND subject_id=?", (pc_id, s))
            label = kn["known_name"] if kn and kn["known_name"] else _art(word_for(tx, pc_id, s))
            status = []
            if det.get("level") == "clear":
                b = _row(tx, "SELECT alive, awareness FROM bodies WHERE body_id=?", (s,))
                if b["alive"] and b["awareness"] == "asleep":
                    status.append("asleep")
                if not b["alive"] or b["awareness"] == "unconscious":
                    status.append("down")
                for it in tx.query("SELECT def_ref FROM items WHERE holder_body=? AND holder_slot IN ('hand_l','hand_r') ORDER BY item_id", (s,)):
                    d = canon.get(it[0])
                    if (d.firearm is not None or d.melee is not None) and "armed" not in status:
                        status.append("armed")
                if tx.query_one("SELECT 1 FROM wounds WHERE body_id=? AND healed_at IS NULL AND (severity IN ('severe','catastrophic') OR clotted=0)", (s,)):
                    status.append("hurt")
            from ..mind._impl_packet import seen_appearance
            people.append(PersonChip(ref=_assign(refs, "p", s, local), label=label, status_words=status, known=bool(kn and kn["known_name"]),
                                     looks=seen_appearance(tx, pc_id, s, view, at)))
        elif s is None and det.get("level") == "silhouette":
            people.append(PersonChip(ref=_assign(refs, "p", f"figure:{p['percept_id']}", local), label="a figure", status_words=[], known=False))
    # exits
    exits = []
    for pr in tx.query("SELECT * FROM portals WHERE (place_a=? OR place_b=?) AND kind != 'wall' ORDER BY portal_id",
                       (place["place_id"], place["place_id"])):
        pr = dict(pr)
        other = pr["place_b"] if pr["place_a"] == place["place_id"] else pr["place_a"]
        st = []
        if pr["kind"] in ("climb", "gap", "edge"):   # D-108: how hard, not open or closed
            st.append(_parkour_words(tx, pr, place["place_id"]))
        elif pr["kind"] != "fence":
            st.append("open" if pr["is_open"] else "closed")
        tried = tx.query_one("SELECT 1 FROM events e WHERE e.type='ACTION_COMPLETE' AND e.actor_id=? AND json_extract(e.payload,'$.result')='blocked_by_lock' "
                             "AND e.cause_event_id IN (SELECT event_id FROM events WHERE type='ACTION_START' AND actor_id=? "
                             "AND json_extract(payload,'$.target_id')=?)", (pc_id, pc_id, pr["portal_id"]))
        if tried and pr["is_locked"]:
            st.append("locked")
        if pr["barricade"] > 0:
            st.append("barricaded")
        if pr["damage"] >= 2:
            st.append("broken")
        leads = _row(tx, "SELECT name FROM places WHERE place_id=?", (other,))["name"] if other in known else "unknown"
        exits.append(ExitView(ref=_assign(refs, "x", pr["portal_id"], local), label=pr["name"], state_words=st, leads_to=leads))
    # dangers
    dangers = []
    for r in tx.query("SELECT p.text, h.provenance FROM claim_holdings h JOIN propositions p ON p.prop_id=h.claim_id "
                      "WHERE h.holder_id=? AND h.believed=1 AND h.superseded_by IS NULL AND p.predicate='threat' ORDER BY h.acquired_at, h.claim_id",
                      (pc_id,)):
        dangers.append(f"{r[0]} ({PROVENANCE_WORDS.get(r[1].split(':')[0], 'you believe it')})")
    # noise
    t = _row(tx, "SELECT turn_index FROM world_clock")["turn_index"]
    dbs = [json.loads(p["detail"]).get("received_db") or 0 for p in
           (dict(x) for x in tx.query("SELECT detail FROM percept_log WHERE holder_id=? AND turn_index=? AND channel IN ('auditory','speech')", (pc_id, t)))]
    level = max([place["ambient_db"]] + dbs)
    noise = next((w for lim, w in DB_WORDS if level < lim), "deafening")
    return LocationView(place_name=place["name"], area_name=area, description_lines=lines[:6], can_see=can_see, people=people,
                        exits=exits, dangers=dangers, noise_text=noise)


PROVENANCE_WORDS = {"witnessed": "you saw it", "overheard": "you overheard it", "told_by": "you were told", "inferred": "your guess",
                    "rumour": "a rumour", "read": "you read it", "common": "everyone knows", "childhood": "you've always known"}


def impairment_word(n):
    return "clear-headed" if n <= 0 else "slowed" if n == 1 else "impaired" if n <= 3 else "badly impaired" if n <= 5 else "barely functioning"


def _parkour_words(tx, pr, here):
    """D-108: a climb, a gap or an edge, in the words of someone looking at it."""
    from ..physical import space
    other = pr["place_b"] if pr["place_a"] == here else pr["place_a"]
    eh = tx.query_one("SELECT elevation_m FROM places WHERE place_id=?", (here,))[0]
    eo = tx.query_one("SELECT elevation_m FROM places WHERE place_id=?", (other,))[0]
    if pr["kind"] == "climb":
        return f"a climb of about {max(1, int(pr['height_cm'] / 100 + 0.5))} metres"
    if pr["kind"] == "gap":
        w = f"about {pr['gap_cm'] / 100:.1f} metres across"
        if eo - eh >= 0.5:
            w += ", higher on the far side"
        elif eh - eo >= 0.5:
            w += ", lower on the far side"
        return w
    d = space.drop_m(tx, pr["portal_id"], here)
    if d > 0:
        return f"a drop of about {max(1, int(d + 0.5))} metres"
    return f"about {max(1, int(pr['height_cm'] / 100 + 0.5))} metres up, out of reach"
