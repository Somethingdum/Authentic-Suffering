"""Bodies of service/death.py (D-105)."""

from __future__ import annotations

import json
from collections import deque

HOUR_MS = 3_600_000
DAY_MS = 86_400_000
CHAIN_LIMIT = 200


def _j(v, default):
    if v is None:
        return default
    if not isinstance(v, str):
        return v
    try:
        return json.loads(v)
    except ValueError:
        return default


def _death(store, pc_id):
    r = store.query_one("SELECT event_id, seq, at, turn_index, payload, cause_event_id, links FROM events "
                        "WHERE type='DEATH' AND json_extract(payload, '$.body_id') = ? ORDER BY seq DESC LIMIT 1", (pc_id,))
    if r is None:
        raise ValueError(f"no death for {pc_id}")
    return {"event_id": r[0], "seq": r[1], "at": r[2], "turn_index": r[3], "payload": _j(r[4], {}), "cause": r[5],
            "links": _j(r[6], [])}


def _starts(d, role=None):
    out = [d["cause"]] if d["cause"] else []
    out += [lk["event_id"] for lk in d["links"] if lk.get("event_id") and (role is None or lk.get("role") == role)]
    return out


def _chain(store, d):
    """The events reached walking back from the DEATH (cause_event_id and links), breadth first."""
    seen, out, q = set(), [], deque(_starts(d))
    while q and len(out) < CHAIN_LIMIT:
        eid = q.popleft()
        if eid in seen:
            continue
        seen.add(eid)
        r = store.query_one("SELECT event_id, seq, type, actor_id, payload, cause_event_id, links FROM events WHERE event_id=?", (eid,))
        if r is None:
            continue
        out.append({"event_id": r[0], "seq": r[1], "type": r[2], "actor_id": r[3], "payload": _j(r[4], {})})
        if r[5]:
            q.append(r[5])
        for lk in _j(r[6], []):
            if lk.get("event_id"):
                q.append(lk["event_id"])
    return out


def _sentence(text):
    t = (text or "").strip()
    return t if not t or t.endswith((".", "!", "?", "…", '"', "”")) else t + "."


def _seen(store, pc_id, d):
    ids = _starts(d, "contributed")
    if not ids:
        return []
    rows = []
    for eid in ids:
        for r in store.query("SELECT p.text, p.at, e.seq FROM percept_log p JOIN events e ON e.event_id = p.event_id "
                             "WHERE p.holder_id=? AND p.event_id=?", (pc_id, eid)):
            rows.append((r[1], r[2], r[0]))
    out = []
    for _at, _seq, text in sorted(rows, key=lambda x: (x[0], x[1])):
        s = _sentence(text)
        if s and s not in out:
            out.append(s)
    return out[:3]


def _choices(store, pc_id, d, chain):
    on_chain = sorted((c for c in chain if c["type"] == "ACTION_START" and c["actor_id"] == pc_id),
                      key=lambda c: -c["seq"])
    latest = [{"seq": r[0], "payload": _j(r[1], {})} for r in store.query(
        "SELECT seq, payload FROM events WHERE type='ACTION_START' AND actor_id=? AND seq < ? ORDER BY seq DESC LIMIT 20",
        (pc_id, d["seq"]))]
    out = []
    for c in on_chain + latest:
        label = (c["payload"].get("label") or "").strip()
        if label and label not in out:
            out.append(label)
        if len(out) == 5:
            break
    return out


def _ironman(store):
    s = _j(store.meta("settings_json"), {}) or {}
    return s.get("save_mode") == "ironman"


def _excepted(store):
    return set(_j(store.meta("reality_exception"), []) or [])


def build_death_view(store, pc_id):
    from ..contracts.view import DeathView
    from ..kernel.clock import format_clock, world_time
    from .death import CAUSE_WORDS
    d = _death(store, pc_id)
    cause_text = " ".join([CAUSE_WORDS.get(d["payload"].get("cause"), "You died.")] + _seen(store, pc_id, d))
    name = store.query_one("SELECT display_name FROM actors WHERE actor_id=?", (pc_id,))
    last = [r[0] for r in store.query("SELECT text FROM narration ORDER BY turn_index DESC LIMIT 3")][::-1]
    stored = roast_stored(store, pc_id)
    iron = _ironman(store)
    return DeathView(pc_name=name[0] if name else pc_id, cause_text=cause_text, day=world_time(d["at"]).day,
                     time_text=format_clock(d["at"]), last_turns=last, contributing=_choices(store, pc_id, d, _chain(store, d)),
                     willis=stored or [], willis_pending=stored is None, can_new_life_here=not iron, can_load=not iron,
                     world_id=store.meta("world_id"))


def lifespan_words(ms):
    from ..mind.affordance import duration_words
    ms = max(0, int(ms))
    if ms < HOUR_MS:
        return duration_words(ms / 1000)
    if ms < 2 * DAY_MS:
        h = max(1, round(ms / HOUR_MS))
        return "1 hour" if h == 1 else f"{h} hours"
    return f"{ms // DAY_MS} days"


def roast_facts(store, pc_id):
    from ..contracts.calls import RoastFacts
    d = _death(store, pc_id)
    dv = build_death_view(store, pc_id)
    ctl = store.query_one("SELECT seq FROM events WHERE type='PC_CONTROL_CHANGE' AND json_extract(payload, '$.pc_actor_id') = ? "
                          "AND seq < ? ORDER BY seq DESC LIMIT 1", (pc_id, d["seq"]))
    from_seq = ctl[0] if ctl else 0
    first = store.query_one("SELECT at, turn_index FROM events WHERE type='PLAYER_INPUT' AND seq > ? AND seq < ? ORDER BY seq LIMIT 1",
                            (from_seq, d["seq"]))
    turns = store.query_one("SELECT COUNT(*) FROM events WHERE type='PLAYER_INPUT' AND seq > ? AND seq < ?", (from_seq, d["seq"]))[0]
    typed = []
    if first is not None:
        typed = [r[0] for r in store.query(
            "SELECT raw_text FROM player_inputs WHERE turn_index >= ? AND turn_index <= ? AND mode IN ('do','say') "
            "ORDER BY turn_index DESC LIMIT 5", (first[1], d["turn_index"]))][::-1]
    exc = _excepted(store)
    met = bool(exc) and any(store.query_one("SELECT 1 FROM acquaintance WHERE holder_id=? AND subject_id=?", (pc_id, b))
                            for b in sorted(exc))
    by_him = bool(exc) and any(c["actor_id"] in exc for c in _chain(store, d))
    return RoastFacts(pc_name=dv.pc_name, lived=lifespan_words(d["at"] - (first[0] if first else d["at"])), turns=turns,
                      cause_text=dv.cause_text, choices=dv.contributing, typed=[t[:300] for t in typed],
                      bent_rules=store.meta("sandbox") == "1", ironman=_ironman(store),
                      rises=bool(d["payload"].get("rise_pending")), met_him=met, by_his_hand=by_him)


def roast_stored(store, pc_id):
    try:
        d = _death(store, pc_id)
    except ValueError:
        return None
    rows = [r[0] for r in store.query("SELECT text FROM story_log WHERE kind='willis' AND turn_index=? ORDER BY entry_id",
                                      (d["turn_index"],))]
    return rows or None


def fallback_roast(facts):
    first = facts.cause_text.split(". ")[0].rstrip(".") + "."
    head = ["Ha! Oh, that was beautiful. Do it again."]
    if facts.typed:
        head.append(f"\"{facts.typed[-1]}\" — that's what you went with. Incredible.")
    head.append(f"{first} I've watched mayflies plan better.")
    extra = []
    if facts.by_his_hand:
        extra.append("And yes, that was me. You had it coming, and I had a free minute.")
    if facts.bent_rules:
        extra.append("You bent the rules of reality and STILL managed this. I'm genuinely impressed.")
    if facts.rises:
        extra.append("Don't worry, you'll be back on your feet in a few hours. Just not as you.")
    last = ("Anyway. Coffee's getting cold. That was your only one, by the way." if facts.ironman
            else "Anyway. Coffee's getting cold. Go on, try again. I'll be watching.")
    lines = head + extra
    return lines[:5] + [last]


async def roast(session):
    from ..contracts.calls import WillisRoastContext
    from ..contracts.common import CallClass
    from ..contracts.mind import WillisRoast
    from ..kernel import clock
    from ..lanes.calllog import record
    from ..lanes.requests import build_request
    from ..lanes.schemas import to_lm_schema
    from .session import append_story
    store, pc = session.store, session.pc_id
    got = roast_stored(store, pc)
    if got is not None:
        return got
    d = _death(store, pc)
    facts = roast_facts(store, pc)
    T = clock.turn_index(store)
    ctx = WillisRoastContext(facts=facts)
    req = resp = None
    lines = []
    try:
        req = build_request(session.config, CallClass.WILLIS_ROAST, turn_index=T, context=ctx, ctx=ctx,
                            json_schema=to_lm_schema(WillisRoast))
        resp = await session.client.call(req)
        if resp.parse_status == "ok":
            data = resp.parsed if resp.parsed is not None else json.loads(resp.text or "{}")
            lines = [ln.strip()[:300] for ln in WillisRoast.model_validate(data).lines if ln and ln.strip()]
    except Exception:  # noqa: BLE001 — DEATH-13: the death screen never waits on a model that is not there
        lines = []
    if not lines:
        lines = fallback_roast(facts)
    with store.transaction() as tx:
        if req is not None and resp is not None:
            record(tx, req, resp)
        for ln in lines:
            append_story(tx, d["turn_index"], "willis", ln)
    return lines


def _name(store, body_id):
    r = store.query_one("SELECT display_name FROM actors WHERE actor_id=?", (body_id,))
    if r is not None and r[0]:
        return r[0]
    k = store.query_one("SELECT kind FROM bodies WHERE body_id=?", (body_id,))
    if k is not None and k[0] == "infected":
        return "one of the dead"
    return "someone"


def truth_reveal(store, pc_id):
    d = _death(store, pc_id)
    lines = []
    here = store.query_one("SELECT place_id FROM positions WHERE body_id=?", (pc_id,))
    if here is not None:
        places = [here[0]] + sorted({r[0] for r in store.query(
            "SELECT CASE WHEN place_a = ? THEN place_b ELSE place_a END FROM portals WHERE place_a = ? OR place_b = ?", (here[0], here[0], here[0]))} - {here[0]})
        for pl in places:
            pn = store.query_one("SELECT name FROM places WHERE place_id=?", (pl,))
            who = [_name(store, r[0]) for r in store.query(
                "SELECT p.body_id FROM positions p JOIN bodies b ON b.body_id = p.body_id WHERE p.place_id=? AND p.body_id != ? "
                "ORDER BY p.body_id", (pl, pc_id))]
            if who:
                lines.append(f"In the {pn[0] if pn else pl}: {', '.join(who)}.")
    for r in store.query("SELECT event_id, actor_id, payload FROM events WHERE type='ACTION_START' AND actor_id IS NOT NULL "
                         "AND actor_id != ? AND turn_index >= ? AND turn_index <= ? AND seq < ? ORDER BY seq",
                         (pc_id, d["turn_index"] - 1, d["turn_index"], d["seq"])):
        p = _j(r[2], {})
        label = (p.get("label") or "").strip()
        if not label:
            continue
        goal = (p.get("goal") or "").strip()
        line = f"{_name(store, r[1])}: {label}" + (f" — \"{goal}\"" if goal else "")
        if store.query_one("SELECT 1 FROM percept_log WHERE holder_id=? AND event_id=?", (pc_id, r[0])) is None:
            line = "You never saw it: " + line
        lines.append(line)
    return lines[:30]
