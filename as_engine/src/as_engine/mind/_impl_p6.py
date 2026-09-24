"""Implementation: P6 — mind.mind, firewall refusals/lies, memory, retrieval."""
from __future__ import annotations

import json
import re

from ..contracts.common import RELATION_AXIS_RANGE, OpenLoopKind, RelationAxis
from ..contracts.events import Event, EventType, WriteOp, WriteRecord
from ..kernel.events import committed_or_none


def _row(s, sql, p=()):
    r = s.query_one(sql, p)
    return dict(r) if r is not None else None


def _j(v):
    return json.loads(v) if isinstance(v, str) else v


# ============================================================ mind.mind
_AXES = ("trust", "fear", "respect", "affection", "resentment", "obligation")


def relate(tx, from_id, to_id, axis, delta, cause, at, turn_index):
    axis = RelationAxis(axis)
    if from_id == to_id:
        raise ValueError("nobody has a relationship with themselves")
    lo, hi = RELATION_AXIS_RANGE[axis]
    r = _row(tx, "SELECT * FROM relationships WHERE from_id=? AND to_id=?", (from_id, to_id))
    old = r[axis.value] if r else 0
    new = max(lo, min(hi, old + delta))
    if new == old:
        return None
    causes = _j(r["causes"]) if r else {}
    causes = dict(causes)
    causes[axis.value] = cause
    key = {"from_id": from_id, "to_id": to_id}
    if r is None:
        vals = {**key, **{a: 0 for a in _AXES}, axis.value: new, "kind": "acquaintance", "causes": causes, "updated_at": at}
        wr = WriteRecord(op=WriteOp.INSERT, table="relationships", values=vals)
    else:
        wr = WriteRecord(op=WriteOp.UPDATE, table="relationships", key=key, values={axis.value: new, "causes": causes, "updated_at": at})
    return tx.commit_event(Event(type=EventType.RELATION_CHANGE, writer="mind.mind", at=at, turn_index=turn_index, actor_id=from_id,
                                 cause_event_id=committed_or_none(tx, cause), writes=[wr],
                                 payload={"from_id": from_id, "to_id": to_id, "axis": axis.value, "old": old, "new": new, "delta": new - old}))


def open_loop(tx, holder_id, kind, text, subject_ids, strength, cause, at, turn_index, due_at=None):
    from .perception import norm_text, word_for
    kind = OpenLoopKind(kind)
    if not text or not text.strip():
        raise ValueError("a loop needs text")
    if not 1 <= strength <= 3:
        raise ValueError("strength 1..3")
    subject_ids = list(subject_ids or [])
    if "{subject}" in text and subject_ids:
        text = text.replace("{subject}", word_for(tx, holder_id, subject_ids[0]))
    text = text.strip()
    text = text[:1].upper() + text[1:]
    for r in tx.query("SELECT * FROM open_loops WHERE holder_id=? AND status='open' AND kind=?", (holder_id, kind.value)):
        if set(_j(r["subject_ids"])) == set(subject_ids) and norm_text(r["text"]) == norm_text(text):
            return r["loop_id"]
    lid = tx.mint("olp")
    et = EventType.PROMISE if kind in (OpenLoopKind.PROMISE_MADE, OpenLoopKind.PROMISE_OWED) else EventType.LOOP_OPENED
    ev = Event(type=et, writer="mind.mind", at=at, turn_index=turn_index, actor_id=holder_id, cause_event_id=committed_or_none(tx, cause),
               payload={"loop_id": lid, "holder_id": holder_id, "kind": kind.value, "text": text, "subject_ids": subject_ids,
                        "strength": strength, "due_at": due_at})
    # created_event must be the event's own id: mint happens in commit; patch via two-step (insert then fill)
    ev = ev.model_copy(update={"writes": [WriteRecord(op=WriteOp.INSERT, table="open_loops", values={
        "loop_id": lid, "holder_id": holder_id, "kind": kind.value, "subject_ids": subject_ids, "text": text, "strength": strength,
        "created_event": "$event_id", "created_at": at, "due_at": due_at, "status": "open", "resolved_event": None})]})
    return _commit_self(tx, ev) and lid


def _commit_self(tx, ev):
    return tx.commit_event(ev)


def close_loop(tx, loop_id, status, cause, at, turn_index):
    r = _row(tx, "SELECT * FROM open_loops WHERE loop_id=?", (loop_id,))
    if r is None or r["status"] != "open":
        raise ValueError("no open loop")
    if status not in ("fulfilled", "broken", "abandoned", "expired"):
        raise ValueError("bad status")
    subj = _j(r["subject_ids"])
    if r["kind"] == "promise_owed" and status in ("fulfilled", "broken"):
        et = EventType.PROMISE_KEPT if status == "fulfilled" else EventType.PROMISE_BROKEN
        payload = {"loop_id": loop_id, "holder_id": r["holder_id"], "status": status, "promisee_id": r["holder_id"],
                   "promiser_id": subj[0] if subj else None}
    else:
        et = EventType.LOOP_CLOSED
        payload = {"loop_id": loop_id, "holder_id": r["holder_id"], "kind": r["kind"], "status": status}
    ev = Event(type=et, writer="mind.mind", at=at, turn_index=turn_index, actor_id=r["holder_id"], cause_event_id=committed_or_none(tx, cause),
               payload=payload, writes=[WriteRecord(op=WriteOp.UPDATE, table="open_loops", key={"loop_id": loop_id},
                                                    values={"status": status, "resolved_event": "$event_id"})])
    return _commit_self(tx, ev)


def learn(tx, holder_id, cue_tags, text, expectation, outcome, cause, at, turn_index):
    from .perception import norm_text
    if not cue_tags or any(not t for t in cue_tags) or not text or not text.strip():
        raise ValueError("a lesson needs cue tags and text")
    tags = sorted(set(cue_tags))
    for r in tx.query("SELECT * FROM lessons WHERE holder_id=? ORDER BY lesson_id", (holder_id,)):
        if sorted(set(_j(r["cue_tags"]))) == tags and norm_text(r["text"]) == norm_text(text):
            if r["confidence"] >= 3:
                return r["lesson_id"]
            c = r["confidence"] + 1
            tx.commit_event(Event(type=EventType.LESSON_LEARNED, writer="mind.mind", at=at, turn_index=turn_index, actor_id=holder_id,
                                  cause_event_id=committed_or_none(tx, cause),
                                  payload={"lesson_id": r["lesson_id"], "holder_id": holder_id, "confidence": c, "reinforced": True},
                                  writes=[WriteRecord(op=WriteOp.UPDATE, table="lessons", key={"lesson_id": r["lesson_id"]}, values={"confidence": c})]))
            return r["lesson_id"]
    lid = tx.mint("lsn")
    ev = Event(type=EventType.LESSON_LEARNED, writer="mind.mind", at=at, turn_index=turn_index, actor_id=holder_id,
               cause_event_id=committed_or_none(tx, cause),
               payload={"lesson_id": lid, "holder_id": holder_id, "cue_tags": tags, "text": text.strip(), "expectation": expectation,
                        "outcome": outcome, "confidence": 2, "reinforced": False},
               writes=[WriteRecord(op=WriteOp.INSERT, table="lessons", values={
                   "lesson_id": lid, "holder_id": holder_id, "cue_tags": tags, "text": text.strip(), "expectation": expectation,
                   "outcome": outcome, "confidence": 2, "source_event": "$event_id", "at": at})])
    _commit_self(tx, ev)
    return lid


# ============================================================ firewall (P6)
def negotiable_target_penalty(times_asked):
    if times_asked < 1:
        raise ValueError("times_asked >= 1")
    return -(times_asked - 1)


def record_refusal(tx, actor_id, requester_id, signature, summary, reason_code, reason_event_ids, cost_cited, entrenched,
                   at, turn_index, cause_event_id):
    from .firewall import REASON_CODES
    if reason_code not in REASON_CODES:
        raise ValueError(f"reason_code {reason_code}")
    ex = None
    if signature != "*:*":
        ex = _row(tx, "SELECT * FROM refusals WHERE actor_id=? AND requester_id=? AND request_signature=? AND status IN ('standing','reopened') "
                      "ORDER BY created_at, refusal_id", (actor_id, requester_id, signature))
    if ex is None:
        rid = tx.mint("ref")
        ev = Event(type=EventType.REFUSAL, writer="mind.mind", at=at, turn_index=turn_index, actor_id=actor_id,
                   cause_event_id=committed_or_none(tx, cause_event_id),
                   payload={"refusal_id": rid, "actor_id": actor_id, "requester_id": requester_id, "signature": signature, "summary": summary,
                            "reason_code": reason_code, "reason_event_ids": list(reason_event_ids), "cost_cited": cost_cited,
                            "entrenched": bool(entrenched), "times_asked": 1, "repeat": False},
                   writes=[WriteRecord(op=WriteOp.INSERT, table="refusals", values={
                       "refusal_id": rid, "actor_id": actor_id, "requester_id": requester_id, "request_summary": summary,
                       "request_signature": signature, "reason_code": reason_code, "reason_event_ids": list(reason_event_ids),
                       "cost_cited": cost_cited, "entrenched": int(bool(entrenched)), "expires_when": "never", "created_event": "$event_id",
                       "created_at": at, "times_asked": 1, "status": "standing"})])
        e = _commit_self(tx, ev)
        if entrenched:
            relate(tx, actor_id, requester_id, RelationAxis.TRUST, -1, e.event_id, at, turn_index)
        return rid
    n = ex["times_asked"] + 1
    ent = bool(ex["entrenched"]) or bool(entrenched)
    e = tx.commit_event(Event(type=EventType.REFUSAL, writer="mind.mind", at=at, turn_index=turn_index, actor_id=actor_id,
                              cause_event_id=committed_or_none(tx, cause_event_id),
                              payload={"refusal_id": ex["refusal_id"], "actor_id": actor_id, "requester_id": requester_id, "signature": signature,
                                       "times_asked": n, "entrenched": ent, "repeat": True},
                              writes=[WriteRecord(op=WriteOp.UPDATE, table="refusals", key={"refusal_id": ex["refusal_id"]},
                                                  values={"times_asked": n, "entrenched": int(ent)})]))
    if n >= 3:
        relate(tx, actor_id, requester_id, RelationAxis.RESENTMENT, 1, e.event_id, at, turn_index)
    return ex["refusal_id"]


def record_lie(tx, liar_id, to_id, signature, words, speech_event_id, at, turn_index):
    return tx.commit_event(Event(type=EventType.LIE_TOLD, writer="mind.mind", at=at, turn_index=turn_index, actor_id=liar_id,
                                 cause_event_id=committed_or_none(tx, speech_event_id),
                                 payload={"liar_id": liar_id, "to_id": to_id, "signature": signature, "words": words}))


# ============================================================ shared selection (the packet's)
def select_percepts(tx, holder, turn_index, at):
    rows = [dict(r) for r in tx.query("SELECT * FROM percept_log WHERE holder_id=? AND turn_index=? AND at<=? "
                                      "ORDER BY at, percept_id", (holder, turn_index, at))]   # SKULL-10
    scene_at = max((p["at"] for p in rows if str(p["event_id"]).startswith("scene:")), default=None)
    return [p for p in rows if not str(p["event_id"]).startswith("scene:") or p["at"] == scene_at]


def entity_ids(tx, holder, rows):
    body_ids = {r[0] for r in tx.query("SELECT body_id FROM bodies")}
    ents = []

    def add(b):
        if b and b != holder and b in body_ids and b not in ents:
            ents.append(b)
    for p in rows:
        add(p["source_id"])
    for r in tx.query("SELECT to_id FROM relationships WHERE from_id=? ORDER BY to_id", (holder,)):
        add(r[0])
    for h in tx.query("SELECT household_id FROM household_members WHERE actor_id=?", (holder,)):
        for r in tx.query("SELECT actor_id FROM household_members WHERE household_id=? ORDER BY actor_id", (h[0],)):
            add(r[0])
    return ents


# ============================================================ memory
_PAREN = re.compile(r"\s*\([^()]*\)$")


def build_aftermath(tx, holder_id, turn_index, at):
    from ..contracts.common import Standing
    from ..contracts.mind import AftermathPacket, LoopLine, PacketEntity, PerceivedItem, RelationshipLine, UtteranceView
    from ._impl_packet import _name_or_desc, _rel_text, _sp, cut_heard, whereabouts
    from .actor import fused
    from .firewall import classify_form, classify_standing, effective_form
    rows = select_percepts(tx, holder_id, turn_index, at)
    ents = entity_ids(tx, holder_id, rows)
    handles, ph = {}, {}
    rels = {r["to_id"]: dict(r) for r in tx.query("SELECT * FROM relationships WHERE from_id=? ORDER BY to_id", (holder_id,))}
    entities = []
    for i, b in enumerate(ents, 1):
        h = f"P{i}"
        ph[b] = h
        handles[h] = b
        kn = _row(tx, "SELECT known_name FROM acquaintance WHERE holder_id=? AND subject_id=?", (holder_id, b))
        kn = kn["known_name"] if kn else None
        rs = rels.get(b)
        entities.append(PacketEntity(handle=h, description=kn or _name_or_desc(tx, holder_id, b), known_name=kn,
                                     relation_summary=f"your {_sp(rs['kind'])}" if rs and rs["kind"] != "acquaintance" else None,
                                     whereabouts=whereabouts(tx, holder_id, b, rows, at)))
    percepts, utts = [], []
    for i, p in enumerate(rows, 1):
        h = f"S{i}"
        handles[h] = p["percept_id"]
        det = _j(p["detail"]) or {}
        if p["channel"] == "speech":
            words = det.get("words", "")
            st = classify_standing(tx, p["source_id"], holder_id, words) if p["source_id"] else Standing.STRANGER
            form = effective_form(classify_form(words, weapon_pointed_at_receiver=bool(det.get("armed_at_me"))), st)
            utts.append(UtteranceView(handle=h, speaker_handle=ph.get(p["source_id"]), words=cut_heard(words, tx.rules.packet.max_heard_chars),
                                      fidelity=p["fidelity"], form=form,
                                      standing=st, addressed_to_me=bool(det.get("addressed_to_me")), volume=det.get("volume", "normal")))
        else:
            percepts.append(PerceivedItem(handle=h, channel=p["channel"], fidelity=p["fidelity"], text=p["text"],
                                          source_handle=ph.get(p["source_id"]), seconds_ago=(at - p["at"]) / 1000))
    loops = []
    for i, r in enumerate(tx.query("SELECT * FROM open_loops WHERE holder_id=? AND status='open' ORDER BY strength DESC, created_at DESC, loop_id LIMIT ?",
                                   (holder_id, tx.rules.packet.max_open_loops)), 1):
        handles[f"L{i}"] = r["loop_id"]
        loops.append(LoopLine(handle=f"L{i}", kind=r["kind"], text=r["text"]))
    rel_lines = [RelationshipLine(handle=ph[b], text=_rel_text(rels[b])) for b in ents if b in rels]
    sentences, last_start = [], None
    for e in tx.query("SELECT type, payload FROM events WHERE actor_id=? AND turn_index=? AND type IN ('SPEECH','ACTION_START') ORDER BY seq",
                      (holder_id, turn_index)):
        pl = _j(e["payload"])
        if e["type"] == "SPEECH":
            sentences.append(f'Said: "{pl["words"]}"')
        else:
            last_start = pl
            if pl["def_id"] == "speak":
                continue
            lab = _PAREN.sub("", pl.get("label") or pl["def_id"])
            lab = lab[:1].lower() + lab[1:]
            sentences.append(f"Chose to {lab}.")
    own = " ".join(sentences) if sentences else None
    expect = None
    if last_start is not None and last_start.get("goal") and last_start.get("goal") != last_start.get("label"):
        expect = last_start["goal"]
    d = fused(tx, holder_id)
    from .identity import compile_identity
    return AftermathPacket(holder_id=holder_id, turn_index=turn_index, identity=compile_identity(d), percepts=percepts, utterances=utts, entities=entities, own_action_text=own,
                           own_expectation_text=expect, open_loops=loops, relationships=rel_lines, handles=handles)


def writeback_groups(packets):
    def key(p):
        if p.own_action_text is not None or p.open_loops or p.relationships:
            return None
        return (tuple((x.channel, x.fidelity, x.text, p.handles.get(x.source_handle) if x.source_handle else None) for x in p.percepts),
                tuple((u.words, u.volume, u.addressed_to_me, u.fidelity, p.handles.get(u.speaker_handle) if u.speaker_handle else None) for u in p.utterances),
                tuple((p.handles[e.handle], e.description) for e in p.entities))
    groups = {}
    out = []
    for hid in sorted(packets):
        k = key(packets[hid])
        if k is None:
            out.append([hid])
        elif k in groups:
            groups[k].append(hid)
        else:
            groups[k] = [hid]
            out.append(groups[k])
    return sorted(out, key=lambda g: g[0])


def apply_writeback(tx, holder_id, output, packet, at, turn_index, *, cue_ids):
    from ..audit.log import repair
    from .memory import BONDED_KINDS
    from .perception import infer
    first = tx.query_one("SELECT MAX(seq) FROM events")[0] or 0
    H = packet.handles
    is_s = lambda h: isinstance(h, str) and h.startswith("S") and h in H  # noqa: E731
    is_p = lambda h: isinstance(h, str) and h.startswith("P") and h in H  # noqa: E731
    is_l = lambda h: isinstance(h, str) and h.startswith("L") and h in H  # noqa: E731

    def drop(item, index, ref):
        repair(tx, "hallucinated_ref", 14, "MEM-02", {"holder_id": holder_id, "item": item, "index": index, "ref": ref}, turn_index, at)

    def pev(h):
        return tx.query_one("SELECT event_id FROM percept_log WHERE percept_id=?", (H[h],))[0]

    beliefs = []
    for i, b in enumerate(output.beliefs):
        bad = next((h for h in b.because if not is_s(h)), None)
        if bad is None and not (b.about in ("self", "place") or is_p(b.about)):
            bad = b.about
        if bad is not None:
            drop("belief", i, bad)
        else:
            beliefs.append(b)
    rels = []
    for i, r in enumerate(output.relationships):
        bad = r.because if not is_s(r.because) else (r.with_ if not is_p(r.with_) else None)
        if bad is not None:
            drop("relationship", i, bad)
        else:
            rels.append(r)
    new_loops = []
    for i, lw in enumerate(output.new_loops):
        bad = lw.because if not is_s(lw.because) else (lw.subject if lw.subject is not None and not is_p(lw.subject) else None)
        if bad is not None:
            drop("new_loop", i, bad)
        else:
            new_loops.append(lw)
    closes = []
    for i, c in enumerate(output.closed_loops):
        bad = c.because if not is_s(c.because) else None
        if bad is None:
            if not is_l(c.loop):
                bad = c.loop
            else:
                st = tx.query_one("SELECT status FROM open_loops WHERE loop_id=?", (H[c.loop],))
                if st is None or st[0] != "open":
                    bad = c.loop
        if bad is not None:
            drop("closed_loop", i, bad)
        else:
            closes.append(c)
    lesson, kept = None, []
    if output.lesson is not None:
        L = output.lesson
        kept = [t for t in L.cue_tags if t in cue_ids]
        if not is_s(L.because):
            drop("lesson", 0, L.because)
        elif not kept:
            drop("lesson", 0, L.cue_tags[0])
        else:
            lesson = L
    # --- episode
    s_handles = sorted((h for h in H if h.startswith("S")), key=lambda h: int(h[1:]))
    p_handles = sorted((h for h in H if h.startswith("P")), key=lambda h: int(h[1:]))
    cause = None
    for h in s_handles:
        c = committed_or_none(tx, pev(h))
        if c:
            cause = c
            break
    anchor = 1 if output.salience >= 90 else 0
    if not anchor:
        for h in s_handles:
            pr = _row(tx, "SELECT p.source_id, e.type FROM percept_log p LEFT JOIN events e ON e.event_id = p.event_id WHERE p.percept_id=?", (H[h],))
            if pr and pr["type"] in ("DEATH", "FALSE_DEATH") and pr["source_id"]:
                r = _row(tx, "SELECT affection, kind FROM relationships WHERE from_id=? AND to_id=?", (holder_id, pr["source_id"]))
                if r and (r["affection"] >= 2 or r["kind"] in BONDED_KINDS):
                    anchor = 1
                    break
    eid = tx.mint("epi")
    place = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (holder_id,))
    tx.commit_event(Event(type=EventType.EPISODE_WRITTEN, writer="mind.memory", at=at, turn_index=turn_index, actor_id=holder_id,
                          cause_event_id=cause, payload={"episode_id": eid, "holder_id": holder_id, "salience": output.salience, "anchor": anchor},
                          writes=[WriteRecord(op=WriteOp.INSERT, table="episodes", values={
                              "episode_id": eid, "holder_id": holder_id, "at": at, "turn_index": turn_index,
                              "place_id": place[0] if place else None, "summary": output.episode.strip(), "salience": output.salience,
                              "percept_ids": [H[h] for h in s_handles], "subject_ids": [H[h] for h in p_handles], "anchor": anchor, "decayed": 0})]))
    for b in beliefs:
        about = ("self", None) if b.about == "self" else ("place", None) if b.about == "place" else ("body", H[b.about])
        infer(tx, holder_id, about=about, text=b.claim, confidence=b.confidence, because=[H[h] for h in b.because], at=at, turn_index=turn_index)
    for r in rels:
        relate(tx, holder_id, H[r.with_], r.axis, r.delta, pev(r.because), at, turn_index)
    for lw in new_loops:
        open_loop(tx, holder_id, lw.kind, lw.text, [H[lw.subject]] if lw.subject else [], lw.strength, pev(lw.because), at, turn_index)
    for c in closes:
        close_loop(tx, H[c.loop], c.status, pev(c.because), at, turn_index)
    if lesson is not None:
        outcome = tx.query_one("SELECT text FROM percept_log WHERE percept_id=?", (H[lesson.because],))[0]
        learn(tx, holder_id, kept, lesson.text, packet.own_expectation_text or "", outcome, pev(lesson.because), at, turn_index)
    return [r[0] for r in tx.query("SELECT event_id FROM events WHERE seq > ? ORDER BY seq", (first,))]


# ============================================================ retrieval
def recency_bonus(hours_since):
    return max(0.0, 20.0 - max(0.0, hours_since) / 6.0)


_WORD = re.compile(r"[a-z']+")


def _content_words(texts):
    from .retrieval import STOPWORDS
    out = []
    for t in texts:
        for w in _WORD.findall(t.lower()):
            if sum(c.isalpha() for c in w) >= 4 and w not in STOPWORDS and w not in out:
                out.append(w)
    return out


def retrieve(tx, holder_id, turn_index, at, *, max_beliefs, max_memories, max_loops):
    from .cues import cues_of
    from .retrieval import MAX_LESSONS, Retrieved
    out = Retrieved()
    rows = select_percepts(tx, holder_id, turn_index, at)
    K = set()
    pos = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (holder_id,))
    if pos:
        K.add(pos[0])
    body_ids = {r[0] for r in tx.query("SELECT body_id FROM bodies")}
    for p in rows:
        if p["source_id"] in body_ids:
            K.add(p["source_id"])
    speech = [(_j(p["detail"]) or {}).get("words", "") for p in rows if p["channel"] == "speech"]
    speech = [w for w in speech if w]
    for r in tx.query("SELECT subject_id, known_name FROM acquaintance WHERE holder_id=? AND known_name IS NOT NULL", (holder_id,)):
        name = r[1]
        pats = [name]
        fw = name.split()[0]
        if len(fw) >= 3:
            pats.append(fw)
        for w in speech:
            if any(re.search(r"(?<![\w])" + re.escape(pp) + r"(?![\w])", w, re.I) for pp in pats):
                K.add(r[0])
                break
    act = _row(tx, "SELECT current_task FROM actors WHERE actor_id=?", (holder_id,))
    task = _row(tx, "SELECT * FROM tasks WHERE task_id=?", (act["current_task"],)) if act and act["current_task"] else None
    if task is None:
        task = _row(tx, "SELECT * FROM tasks WHERE actor_id=? AND status='active' ORDER BY started_at, task_id", (holder_id,))
    if task:
        K.update(_j(task["target_ids"]))
    M = set(K)
    loops_open = [dict(r) for r in tx.query("SELECT * FROM open_loops WHERE holder_id=? AND status='open'", (holder_id,))]
    for l in loops_open:
        K.update(_j(l["subject_ids"]))
    out.keys, out.moment_keys = K, M
    # beliefs
    bl = []
    for r in tx.query("SELECT h.*, p.text AS ptext, p.subject_id AS psub, c.predicate AS cpred, c.object_value AS cval, c.subject_id AS csub "
                      "FROM claim_holdings h LEFT JOIN propositions p ON p.prop_id=h.claim_id LEFT JOIN claims c ON c.claim_id=h.claim_id "
                      "WHERE h.holder_id=? AND h.believed=1 AND h.superseded_by IS NULL", (holder_id,)):
        subj = r["psub"] if r["ptext"] is not None else r["csub"]
        score = r["confidence"] * 10 + recency_bonus((at - r["acquired_at"]) / 3_600_000) + (15 if subj in K else 0)
        text = r["ptext"] if r["ptext"] is not None else f"{r['cpred']} {r['cval'] or ''}".strip()
        bl.append({"claim_id": r["claim_id"], "text": text, "confidence": r["confidence"], "provenance": r["provenance"],
                   "acquired_at": r["acquired_at"], "score": score})
    bl.sort(key=lambda b: (-b["score"], b["claim_id"]))
    out.beliefs = bl[:max_beliefs]
    # episodes
    eps = [dict(r, rowid=r["rowid"]) for r in tx.query("SELECT rowid, * FROM episodes WHERE holder_id=? AND decayed=0", (holder_id,))]
    anchors = sorted([e for e in eps if e["anchor"]], key=lambda e: (-e["salience"], -e["at"], e["episode_id"]))[:2]
    words = _content_words(speech)
    match = set()
    if words:
        q = " OR ".join(f'"{w}"' for w in words)
        match = {r[0] for r in tx.query("SELECT rowid FROM episodes_fts WHERE episodes_fts MATCH ?", (q,))}
    rest = []
    for e in eps:
        if e in anchors:
            continue
        score = e["salience"] + (20 if set(_j(e["subject_ids"])) & K else 0) + (15 if e["rowid"] in match else 0) + recency_bonus((at - e["at"]) / 3_600_000)
        rest.append((score, e))
    rest.sort(key=lambda x: (-x[0], x[1]["episode_id"]))
    chosen = [(None, e) for e in anchors] + rest
    out.episodes = [{"episode_id": e["episode_id"], "summary": e["summary"], "at": e["at"], "salience": e["salience"], "anchor": e["anchor"],
                     "score": s} for s, e in chosen[:max_memories]]
    # lessons
    cues = cues_of(tx, holder_id, turn_index, at)
    ls = [dict(r) for r in tx.query("SELECT * FROM lessons WHERE holder_id=?", (holder_id,)) if set(_j(r["cue_tags"])) & cues]
    ls.sort(key=lambda r: (-r["confidence"], -r["at"], r["lesson_id"]))
    out.lessons = [{"lesson_id": r["lesson_id"], "text": r["text"], "confidence": r["confidence"], "cue_tags": _j(r["cue_tags"])} for r in ls[:MAX_LESSONS]]
    # loops
    ordk = lambda l: (-l["strength"], -l["created_at"], l["loop_id"])  # noqa: E731
    ink = sorted([l for l in loops_open if set(_j(l["subject_ids"])) & M], key=ordk)
    notk = sorted([l for l in loops_open if not set(_j(l["subject_ids"])) & M], key=ordk)
    out.loops = [{"loop_id": l["loop_id"], "kind": l["kind"], "text": l["text"], "strength": l["strength"], "subject_ids": _j(l["subject_ids"])}
                 for l in (ink + notk)[:max_loops]]
    # refusals
    out.refusals = [{"refusal_id": r["refusal_id"], "requester_id": r["requester_id"], "summary": r["request_summary"],
                     "times_asked": r["times_asked"], "created_at": r["created_at"]}
                    for r in tx.query("SELECT * FROM refusals WHERE actor_id=? AND status IN ('standing','reopened') ORDER BY created_at, refusal_id", (holder_id,))
                    if r["requester_id"] in M]
    return out
