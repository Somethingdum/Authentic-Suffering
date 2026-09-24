"""Implementation of world/rumours.py (P9)."""
from __future__ import annotations

import json

from ..contracts.events import Event, EventType, WriteOp, WriteRecord

DAY = 86_400_000


def _row(s, sql, p=()):
    r = s.query_one(sql, p)
    return dict(r) if r is not None else None


def _rows(s, sql, p=()):
    return [dict(r) for r in s.query(sql, p)]


def _maxseq(tx):
    return tx.query_one("SELECT COALESCE(MAX(seq),0) FROM events")[0]


def _since(tx, seq):
    from ..action._impl_p5b import _events_since
    return _events_since(tx, seq)


def _live_holding(s, holder, subject_id, predicate, subject_type="body"):
    return _row(s, "SELECT h.* FROM claim_holdings h JOIN propositions p ON p.prop_id=h.claim_id WHERE h.holder_id=? "
                   "AND h.superseded_by IS NULL AND p.subject_type=? AND p.subject_id=? AND p.predicate=? "
                   "ORDER BY h.acquired_at DESC, h.claim_id DESC LIMIT 1", (holder, subject_type, subject_id, predicate))


def _about_word(tx, holder, subject_type, about_id):
    from ..mind.perception import word_for
    if subject_type == "place":
        nm = tx.query_one("SELECT name FROM places WHERE place_id=?", (about_id,))[0]
        return "the " + nm[4:] if nm.startswith("The ") else nm
    return word_for(tx, holder, about_id)


def _prop(s, rumour_id):
    r = _row(s, "SELECT p.* FROM rumours r JOIN propositions p ON p.prop_id=r.prop_id WHERE r.rumour_id=?", (rumour_id,))
    if r is None:
        raise ValueError(f"unknown rumour {rumour_id}")
    return r


def _detail(words, addressed, known_as):
    return {"words": words, "volume": "normal", "addressed_to_me": addressed, "speaker_known_as": known_as,
            "received_db": 60, "via_portal": None, "armed_at_me": False}


def seed(tx, holder_id, about_id, claim, at, turn_index, cause_event_id, confidence=3, *, subject_type="body"):
    from ..mind.perception import BeliefFromPercept, grant
    from ..world.rumours import claim_sentence
    rid = tx.mint("rum")
    sentence = claim_sentence(claim, _about_word(tx, holder_id, subject_type, about_id))
    grant(tx, holder_id, event_id=f"rumour:{rid}", channel="speech", fidelity="exact", text="Word is: " + sentence, source_id=None,
          at=at, turn_index=turn_index, beliefs=[BeliefFromPercept(subject_type, about_id, claim, sentence)],
          detail=_detail(sentence, False, None), confidence=confidence)
    h = _live_holding(tx, holder_id, about_id, claim, subject_type)
    tx.commit_event(Event(type=EventType.RUMOUR_SPREAD, writer="world.rumours", at=at, turn_index=turn_index, cause_event_id=cause_event_id,
                          payload={"rumour_id": rid, "teller_id": None, "listener_id": holder_id, "about_id": about_id, "claim": claim,
                                   "confidence": h["confidence"], "believed": True, "hops": 0},
                          writes=[WriteRecord(op=WriteOp.INSERT, table="rumours", values={
                              "rumour_id": rid, "prop_id": h["claim_id"], "origin_holder": holder_id, "hops": 0, "distortions": [],
                              "created_at": at})]))
    return rid


def spread_one(tx, rumour_id, teller_id, listener_id, at, turn_index, cause_event_id):
    from ..mind.perception import BeliefFromPercept, grant, word_for
    from ..world.rumours import claim_sentence
    p = _prop(tx, rumour_id)
    th = _live_holding(tx, teller_id, p["subject_id"], p["predicate"], p["subject_type"])
    if th is None or not th["believed"] or th["confidence"] < 1:
        raise ValueError("the teller does not hold this rumour firmly enough to pass it on")
    conf = th["confidence"] - 1
    rel = _row(tx, "SELECT trust FROM relationships WHERE from_id=? AND to_id=?", (listener_id, teller_id))
    believed = (rel["trust"] if rel else 0) >= -1
    prev = tx.query_one("SELECT payload FROM events WHERE type='RUMOUR_SPREAD' AND json_extract(payload,'$.rumour_id')=? "
                        "AND json_extract(payload,'$.listener_id')=? ORDER BY seq DESC LIMIT 1", (rumour_id, teller_id))
    hops = (json.loads(prev[0])["hops"] if prev else 0) + 1
    r = _row(tx, "SELECT hops FROM rumours WHERE rumour_id=?", (rumour_id,))
    writes = [WriteRecord(op=WriteOp.UPDATE, table="rumours", key={"rumour_id": rumour_id}, values={"hops": hops})] if hops > r["hops"] else []
    rs = tx.commit_event(Event(type=EventType.RUMOUR_SPREAD, writer="world.rumours", at=at, turn_index=turn_index, actor_id=teller_id,
                               cause_event_id=cause_event_id, writes=writes,
                               payload={"rumour_id": rumour_id, "teller_id": teller_id, "listener_id": listener_id,
                                        "about_id": p["subject_id"], "claim": p["predicate"], "confidence": conf, "believed": believed,
                                        "hops": hops}))
    teller = word_for(tx, listener_id, teller_id)
    teller = teller[:1].upper() + teller[1:]
    sentence = claim_sentence(p["predicate"], _about_word(tx, listener_id, p["subject_type"], p["subject_id"]))
    import json as _json
    _d = _json.loads(tx.query_one("SELECT distortions FROM rumours WHERE rumour_id=?", (rumour_id,))[0])
    _mine = next((x for x in _d if x.get("holder_id") == teller_id and x.get("text")), None)
    if _mine:
        t_ = _mine["text"].strip()
        sentence = t_[:1].upper() + t_[1:] + ("" if t_.endswith(".") else ".")
    grant(tx, listener_id, event_id=rs.event_id, channel="speech", fidelity="exact", text=f"{teller} tells you: {sentence}",
          source_id=teller_id, at=at, turn_index=turn_index,
          beliefs=[BeliefFromPercept(p["subject_type"], p["subject_id"], p["predicate"], sentence, believed=believed)],
          detail=_detail(sentence, True, teller), confidence=conf)
    return rs


def holders(store, rumour_id):
    p = _prop(store, rumour_id)
    return [(r["holder_id"], r["confidence"]) for r in _rows(
        store, "SELECT h.holder_id, h.confidence FROM claim_holdings h JOIN propositions p ON p.prop_id=h.claim_id "
               "WHERE h.superseded_by IS NULL AND h.believed=1 AND p.subject_type=? AND p.subject_id IS ? AND p.predicate=? "
               "ORDER BY h.holder_id", (p["subject_type"], p["subject_id"], p["predicate"]))]


def spread_day(tx, group_id, at, turn_index, cause_event_id):
    from ..society._impl_society import _controller, contacts, g_members
    first = _maxseq(tx)
    R = tx.rules.society
    for rum in _rows(tx, "SELECT * FROM rumours WHERE created_at > ? ORDER BY rumour_id", (at - R.rumour_quiet_days * DAY,)):
        p = _prop(tx, rum["rumour_id"])
        held = dict(holders(tx, rum["rumour_id"]))
        tellers = [m for m in g_members(tx, group_id) if _controller(tx, m) != "human" and held.get(m, 0) >= 1]
        for t in tellers:
            def close(c):
                r = _row(tx, "SELECT trust, affection FROM relationships WHERE from_id=? AND to_id=?", (t, c))
                return -((r["trust"] + r["affection"]) if r else 0)
            told = 0
            for c in sorted(contacts(tx, t, group_id), key=lambda c: (close(c), c)):
                if told >= R.rumour_tells_per_day:
                    break
                if c == p["subject_id"] or _live_holding(tx, c, p["subject_id"], p["predicate"], p["subject_type"]) is not None:
                    continue
                spread_one(tx, rum["rumour_id"], t, c, at, turn_index, cause_event_id)
                told += 1
    return _since(tx, first)
