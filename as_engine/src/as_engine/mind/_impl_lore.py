"""Implementation: mind.actor lore_rows / seed_lore (LORE-02) and mind.retrieval.lore_lines (LORE-03), D-130."""
from __future__ import annotations

import json
import re

from ..contracts.events import Event, EventType, WriteOp, WriteRecord


def lore_rows(tx, holder_id, cohort, group_refs, at):
    # LORE-02: lore_held rows for what this person would hold and does not yet, in (lore ref, belief) order
    cohort = getattr(cohort, "value", cohort)
    have = {(r[0], r[1]) for r in tx.query("SELECT lore_ref, belief FROM lore_held WHERE holder_id=?", (holder_id,))}
    out = []
    for ref in tx.canon.refs("lore"):
        for i, b in enumerate(tx.canon.get(ref).beliefs):
            who = b.held_by
            if who == "common":
                prov = "common"
            elif who.startswith("cohort:"):
                if who.split(":", 1)[1] != cohort:
                    continue
                prov = "childhood" if cohort == "post_fall_born" else "common"
            elif not who.startswith("region:") and who in group_refs:
                prov = "group"
            else:
                continue
            if (ref, i) not in have:
                out.append(WriteRecord(op=WriteOp.INSERT, table="lore_held", values={
                    "holder_id": holder_id, "lore_ref": ref, "belief": i, "confidence": b.confidence, "provenance": prov,
                    "acquired_at": at}))
    return out


def group_refs_of(tx, holder_id):
    return {r[0] for r in tx.query("SELECT g.content_ref FROM group_members m JOIN groups g ON g.group_id = m.group_id WHERE "
                                   "m.actor_id=? AND m.status IN ('member','probation') AND g.content_ref IS NOT NULL", (holder_id,))}


def seed_lore(tx, holder_id, at, turn_index, *, origin="sim"):
    # LORE-02 (D-130): what everyone around them says, for someone who already exists (their groups' words)
    from .actor import fused
    body = tx.query_one("SELECT b.kind FROM actors a JOIN bodies b ON b.body_id = a.actor_id WHERE a.actor_id=?", (holder_id,))
    if body is None or body[0] != "human":
        return None
    ws = lore_rows(tx, holder_id, fused(tx, holder_id).identity.cohort, group_refs_of(tx, holder_id), at)
    if not ws:
        return None
    return tx.commit_event(Event(type=EventType.MATERIALIZE, writer="mind.actor", at=at, turn_index=turn_index, actor_id=holder_id,
                                 origin=origin, writes=ws, payload={"actor_id": holder_id, "source": "lore", "beliefs": len(ws)}))


def _says(words, phrase):
    return re.search(r"(?<![\w])" + re.escape(phrase.lower()) + r"(?![\w])", words.lower()) is not None


def lore_lines(tx, holder_id, turn_index, at, n):
    # LORE-03 (D-130): what people say about what is in front of the holder
    from ._impl_p6 import select_percepts
    from .cues import cues_of
    held = [dict(r) for r in tx.query("SELECT lore_ref, belief, confidence, provenance FROM lore_held WHERE holder_id=?", (holder_id,))]
    if not held:
        return []
    rows = select_percepts(tx, holder_id, turn_index, at)
    speech = []
    for p in rows:
        if p["channel"] == "speech":
            d = json.loads(p["detail"]) if isinstance(p["detail"], str) else (p["detail"] or {})
            if d.get("words"):
                speech.append(d["words"])
    seen = set()
    for p in rows:
        if p["channel"] != "visual" or p["fidelity"] not in ("exact", "partial") or not p["source_id"]:
            continue
        r = tx.query_one("SELECT content_ref FROM bodies WHERE body_id=?", (p["source_id"],))
        if r is not None:
            from .perception import thing_ref
            ref = thing_ref(tx, p["source_id"])                  # D-160: the dead are known by their type
            if ref:
                seen.add(ref)
            seen |= group_refs_of(tx, p["source_id"])
            continue
        r = tx.query_one("SELECT def_ref FROM items WHERE item_id=?", (p["source_id"],))
        if r is not None:
            seen.add(r[0])
    cues = None
    hit = {}
    out = []
    for h in held:
        ref = h["lore_ref"]
        if not tx.canon.has(ref):
            continue
        e = tx.canon.get(ref)
        if ref not in hit:
            hit[ref] = any(_says(w, a) for w in speech for a in e.about) or bool(set(e.entities) & seen)
            if not hit[ref] and e.when:
                if cues is None:
                    cues = cues_of(tx, holder_id, turn_index, at)
                hit[ref] = bool(set(e.when) & cues)
        if hit[ref] and h["belief"] < len(e.beliefs):
            out.append({"lore_id": ref, "belief": h["belief"], "text": e.beliefs[h["belief"]].text, "confidence": h["confidence"],
                        "provenance": h["provenance"]})
    by = {}
    for x in sorted(out, key=lambda x: (-x["confidence"], x["belief"])):
        by.setdefault(x["lore_id"], []).append(x)
    order = sorted(by, key=lambda r: (-by[r][0]["confidence"], r))        # each thing once before any twice
    picked, k = [], 0
    while len(picked) < n and any(len(by[r]) > k for r in order):
        picked += [by[r][k] for r in order if len(by[r]) > k][:n - len(picked)]
        k += 1
    return picked
