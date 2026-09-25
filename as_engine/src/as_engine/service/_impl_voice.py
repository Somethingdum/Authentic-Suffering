"""Bodies of service/voice.py (D-106)."""

from __future__ import annotations

import json
from collections import deque

CHAIN_LIMIT = 300
MAX_BEATS = 24


def _j(v, default):
    if v is None:
        return default
    if not isinstance(v, str):
        return v
    try:
        return json.loads(v)
    except ValueError:
        return default


def _when(at):
    from ..kernel.clock import format_clock, world_time
    return f"day {world_time(at).day}, {format_clock(at)}"


def _name(store, body_id):
    from ._impl_death import _name as n
    return n(store, body_id)


def _walk(store, start_ids):
    seen, out, q = set(), [], deque(i for i in start_ids if i)
    while q and len(out) < CHAIN_LIMIT:
        eid = q.popleft()
        if eid in seen:
            continue
        seen.add(eid)
        r = store.query_one("SELECT event_id, seq, at, turn_index, type, actor_id, payload, cause_event_id, links FROM events "
                            "WHERE event_id=?", (eid,))
        if r is None:
            continue
        out.append({"event_id": r[0], "seq": r[1], "at": r[2], "turn_index": r[3], "type": r[4], "actor_id": r[5],
                    "payload": _j(r[6], {})})
        if r[7]:
            q.append(r[7])
        for lk in _j(r[8], []):
            if lk.get("event_id"):
                q.append(lk["event_id"])
    return out


def _place_name(store, place_id):
    r = store.query_one("SELECT name FROM places WHERE place_id=?", (place_id,)) if place_id else None
    return r[0] if r else "somewhere"


def _describe(store, e):
    p, t = e["payload"], e["type"]
    who = _name(store, e["actor_id"]) if e["actor_id"] else None
    if t == "ACTION_START":
        return f"{who or 'someone'}: {p.get('label') or p.get('def_id') or 'did something'}"
    if t == "MOVE":
        return f"{who or 'something'} went to the {_place_name(store, p.get('to_place'))}"
    if t == "NOISE":
        return (p.get("text") or p.get("kind") or "a noise") + (f", {round(p['source_db'])} dB" if p.get("source_db") else "")
    if t == "HARM":
        return f"{_name(store, p.get('body_id'))} was hurt"
    if t == "DEATH":
        return f"{_name(store, p.get('body_id'))} died"
    return f"{who or 'something'}: {t.lower().replace('_', ' ')}"


def _root(store, place_id):
    seen = set()
    while place_id and place_id not in seen:
        seen.add(place_id)
        r = store.query_one("SELECT parent_id FROM places WHERE place_id=?", (place_id,))
        if r is None or r[0] is None:
            return place_id
        place_id = r[0]
    return place_id


def _came_in(store, body_id, building, before_seq):
    """When the body last came into the building (its latest MOVE from outside it), else its first event."""
    for r in store.query("SELECT at, payload FROM events WHERE type='MOVE' AND actor_id=? AND seq < ? ORDER BY seq DESC",
                         (body_id, before_seq)):
        p = _j(r[1], {})
        if _root(store, p.get("to_place")) == building and _root(store, p.get("from_place")) != building:
            return r[0]
    f = store.query_one("SELECT MIN(at) FROM events WHERE actor_id=? AND seq < ?", (body_id, before_seq))
    return f[0] if f and f[0] is not None else 0


def _doom(store, pc_id):
    from ..physical import bodies
    d = bodies.doomed(store, pc_id)
    if d is None:
        raise ValueError(f"no doom for {pc_id}")
    r = store.query_one("SELECT event_id, seq, cause_event_id FROM events WHERE type='DOOM' AND actor_id=? ORDER BY seq DESC LIMIT 1",
                        (pc_id,))
    d["event_id"], d["seq"], d["doom_cause"] = (r[0], r[1], r[2]) if r else (None, 10**12, None)
    return d


def chain_beats(store, pc_id, doom):
    from ..contracts.calls import ChainBeat
    walked = _walk(store, [doom.get("cause_event"), doom.get("doom_cause")])
    on_chain = {e["event_id"] for e in walked}
    mine = [{"event_id": r[0], "seq": r[1], "at": r[2], "turn_index": r[3], "type": "ACTION_START", "actor_id": pc_id,
             "payload": _j(r[4], {})}
            for r in store.query("SELECT event_id, seq, at, turn_index, payload FROM events WHERE type='ACTION_START' AND actor_id=? "
                                 "AND seq < ? ORDER BY seq DESC LIMIT 5", (pc_id, doom["seq"]))]
    events = {e["event_id"]: e for e in walked + mine}
    beats = []
    for e in sorted(events.values(), key=lambda x: x["seq"]):
        when = _when(e["at"])
        if e["type"] == "ACTION_START" and e["actor_id"] == pc_id:
            said = store.query_one("SELECT raw_text FROM player_inputs WHERE turn_index=? AND mode IN ('do','say')",
                                   (e["turn_index"],))
            label = (e["payload"].get("label") or "").strip()
            if label:
                beats.append(ChainBeat(when=when, kind="choice", text=label[:300], said=said[0][:300] if said else None))
            continue
        if e["type"] in ("DEATH", "HARM") and e["payload"].get("body_id") not in (None, pc_id):
            beats.append(ChainBeat(when=when, kind="consequence", text=_describe(store, e)[:300]))
            continue
        if e["event_id"] not in on_chain:
            continue
        clue = store.query_one("SELECT text FROM percept_log WHERE holder_id=? AND event_id=? AND source_id IS NULL "
                               "ORDER BY at LIMIT 1", (pc_id, e["event_id"]))
        if clue is not None:
            beats.append(ChainBeat(when=when, kind="clue", text=clue[0][:300]))
        elif store.query_one("SELECT 1 FROM percept_log WHERE holder_id=? AND event_id=?", (pc_id, e["event_id"])) is None:
            beats.append(ChainBeat(when=when, kind="unseen", text=_describe(store, e)[:300]))
    return beats[-MAX_BEATS:]


def _threat(store, pc_id, doom):
    from .death import lifespan_words
    who = None
    for e in _walk(store, [doom.get("cause_event"), doom.get("doom_cause")]):
        if e["actor_id"] and e["actor_id"] != pc_id and store.query_one("SELECT 1 FROM bodies WHERE body_id=?", (e["actor_id"],)):
            who = e["actor_id"]
            break
    if who is None:
        return None, None, None
    here = store.query_one("SELECT place_id FROM positions WHERE body_id=?", (pc_id,))
    there = store.query_one("SELECT place_id FROM positions WHERE body_id=?", (who,))
    near = None
    if here and there:
        building = _root(store, here[0])
        if _root(store, there[0]) == building:
            since = max(_came_in(store, who, building, doom["seq"]), _came_in(store, pc_id, building, doom["seq"]))
            near = lifespan_words(max(0, doom["doomed_at"] - since))
    return who, _name(store, who), near


def _upper_hand(store, pc_id, threat_id=None):
    out = []
    for r in store.query("SELECT i.item_id, i.def_ref FROM items i WHERE i.holder_body=? ORDER BY i.item_id", (pc_id,)):
        try:
            d = store.canon.get(r[1])
        except (KeyError, ValueError, AttributeError):
            continue
        if getattr(d, "firearm", None) is not None or getattr(d, "melee", None) is not None:
            nm = getattr(d, "name", None) or r[1]
            if nm not in out:
                out.append(nm)
    here = store.query_one("SELECT place_id FROM positions WHERE body_id=?", (pc_id,))
    if here:
        for r in store.query("SELECT a.known_name FROM acquaintance a JOIN positions p ON p.body_id = a.subject_id JOIN bodies b "
                             "ON b.body_id = a.subject_id WHERE a.holder_id=? AND p.place_id=? AND b.alive=1 AND a.known_name IS NOT NULL "
                             "AND a.subject_id != ? ORDER BY a.subject_id", (pc_id, here[0], threat_id or "")):
            if r[0] not in out:
                out.append(r[0])
    return out[:8]


def voice_facts(store, pc_id, moment):
    from ..contracts.calls import VoiceFacts
    from .death import build_death_view, lifespan_words
    d = _doom(store, pc_id)
    name = store.query_one("SELECT display_name FROM actors WHERE actor_id=?", (pc_id,))
    ctl = store.query_one("SELECT seq FROM events WHERE type='PC_CONTROL_CHANGE' AND json_extract(payload, '$.pc_actor_id') = ? "
                          "AND seq < ? ORDER BY seq DESC LIMIT 1", (pc_id, d["seq"]))
    first = store.query_one("SELECT at FROM events WHERE type='PLAYER_INPUT' AND seq > ? AND seq < ? ORDER BY seq LIMIT 1",
                            (ctl[0] if ctl else 0, d["seq"]))
    threat_id, threat, near = _threat(store, pc_id, d)
    manner, said = None, []
    if moment == "after":
        manner = build_death_view(store, pc_id).cause_text
        said = [r[0] for r in store.query("SELECT text FROM story_log WHERE kind='voice' AND turn_index=? ORDER BY entry_id",
                                          (scene_turn(store, pc_id),))][:3]
    return VoiceFacts(pc_name=name[0] if name else pc_id,
                      lived=lifespan_words(d["doomed_at"] - (first[0] if first else d["doomed_at"])),
                      seconds_left=max(0, (d["expected_at"] - d["doomed_at"]) // 1000) if moment == "before" else 0,
                      chain=chain_beats(store, pc_id, d), threat=threat, threat_near=near,
                      upper_hand=_upper_hand(store, pc_id, threat_id), manner=manner, said_before=said)


def scene_turn(store, pc_id):
    from ..physical import bodies
    d = bodies.doomed(store, pc_id)
    if d is None:
        return None
    return store.query_one("SELECT MIN(turn_index) FROM story_log WHERE kind='doom' AND turn_index >= ?", (d["turn_index"],))[0]


def when_words(seconds):
    s = max(0, int(seconds))
    if s == 0:
        return "this very instant"
    if s < 10:
        return "a few seconds"
    if s < 90:
        return f"about {s} seconds"
    if s < 5400:
        m = round(s / 60)
        return "about a minute" if m == 1 else f"about {m} minutes"
    return f"about {round(s / 3600)} hours"


def _and(xs):
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def fallback_voice(moment, facts):
    from .voice import ARCHITECT
    if moment == "after":
        return [f"And that is how. {facts.manner or 'You died.'} Every piece had a cause. Every piece was mine."]
    walk = []
    for b in facts.chain[-8:]:
        text = b.text.rstrip(" .!?")
        if b.kind == "choice":
            walk.append(f"{b.when}: you chose to {text[:1].lower() + text[1:]}" + (f', thinking "{b.said}"' if b.said else "") + ".")
        elif b.kind == "consequence":
            walk.append(f"{b.when}: {text}.")
        elif b.kind == "unseen":
            walk.append(f"{b.when}: {text}. You never saw it.")
        else:
            walk.append(f'There was "{text}". You noticed it. You did nothing.')
    hand = f" I gave you {_and(facts.upper_hand)}." if facts.upper_hand else ""
    second = " ".join(walk + [f"I didn't have to touch you once.{hand} And still."]).strip()
    third = []
    if facts.threat:
        third.append(f"Did you know {facts.threat} has been in here with you?"
                     + (f" For {facts.threat_near}." if facts.threat_near else "") + " You never noticed.")
    third.append(f"In {when_words(facts.seconds_left)} you are going to die. I won't tell you how. "
                 "You should have paid more attention. Like I did.")
    return [ARCHITECT, second, " ".join(third)]


async def voice(session, moment):
    from ..contracts.calls import VoiceContext
    from ..contracts.common import CallClass
    from ..contracts.mind import VoiceMessage
    from ..kernel import clock
    from ..lanes.requests import build_request
    from ..lanes.schemas import to_lm_schema
    facts = voice_facts(session.store, session.pc_id, moment)
    ctx = VoiceContext(moment=moment, facts=facts)
    out = []
    try:
        req = build_request(session.config, CallClass.THE_VOICE, turn_index=clock.turn_index(session.store), context=ctx, ctx=ctx,
                            json_schema=to_lm_schema(VoiceMessage))
        resp = await session.client.call(req)
        if resp.parse_status == "ok":
            data = resp.parsed if resp.parsed is not None else json.loads(resp.text or "{}")
            out = [p.strip()[:2000] for p in VoiceMessage.model_validate(data).paragraphs if p and p.strip()]
    except Exception:  # noqa: BLE001 — VOICE-06: the Voice always speaks
        out = []
    return out or fallback_voice(moment, facts)


def scene(store, pc_id, willis_lines, voice_paragraphs):
    from ..contracts.protocol import DoomBeat
    from ..physical import bodies
    from .voice import (
        ALONE_TEXT,
        DARK_PAUSE_MS,
        DARK_TEXT,
        FIGHT_TEXT,
        FREEZE_TEXT,
        RESUME_INSTANT_TEXT,
        RESUME_TEXT,
        SNATCH_PAUSE_MS,
        SNATCH_TEXT,
        STEPS_TEXT,
    )
    d = bodies.doomed(store, pc_id)
    gripped = store.query_one("SELECT 1 FROM grips WHERE holder_id=? OR target_id=?", (pc_id, pc_id)) is not None
    beats = [DoomBeat(kind="scene", text=FREEZE_TEXT + (" " + FIGHT_TEXT if gripped else ""), pause_ms=0),
             DoomBeat(kind="scene", text=DARK_TEXT, pause_ms=DARK_PAUSE_MS),
             DoomBeat(kind="scene", text=STEPS_TEXT, pause_ms=1500)]
    beats += [DoomBeat(kind="willis", text=ln, pause_ms=900) for ln in willis_lines]
    beats += [DoomBeat(kind="snatch", text=SNATCH_TEXT, pause_ms=SNATCH_PAUSE_MS),
              DoomBeat(kind="scene", text=ALONE_TEXT, pause_ms=2000)]
    beats += [DoomBeat(kind="voice", text=p, pause_ms=1200) for p in voice_paragraphs]
    beats.append(DoomBeat(kind="scene", text=RESUME_INSTANT_TEXT if d and d["kind"] == "instant" else RESUME_TEXT, pause_ms=1500))
    return beats


async def doom_scene(session):
    from .death import roast
    lines = await roast(session)
    paragraphs = await voice(session, "before")
    return scene(session.store, session.pc_id, lines, paragraphs)
