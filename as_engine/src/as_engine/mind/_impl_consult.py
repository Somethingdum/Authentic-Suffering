"""Implementation: mind.consult (Actor v2 consultations)."""
from __future__ import annotations

import json
import re

from ..contracts.content import AFFORDANCE_FAMILIES


def check(packet, consultation):
    if consultation.kind not in packet.consult_kinds:
        return "not_offered"
    for h in consultation.subjects:
        if h[:1] not in ("P", "S") or h not in packet.handles:
            return "hallucinated_ref"
    if consultation.kind == "recall" and not (consultation.query or "").strip() and not consultation.subjects:
        return "empty"
    if consultation.kind == "more_actions" and consultation.family not in packet.families:
        return "not_offered"
    return None


def families(affordances, defs):
    from .consult import family_of
    shown = {o.signature for o in affordances.options}
    have = {family_of(defs[o.def_id]) for o in affordances.pool if o.signature not in shown}
    return [f for f in AFFORDANCE_FAMILIES if f in have]


def more_actions(affordances, family, subject_ids, defs):
    from .consult import MAX_MORE, family_of
    shown = {o.signature for o in affordances.options}
    want = set(subject_ids)
    out = []
    for o in affordances.pool:
        if o.signature in shown or family_of(defs[o.def_id]) != family:
            continue
        if want and not ({o.target_id, o.destination_id, o.item_id} & want):
            continue
        out.append(o)
        if len(out) >= MAX_MORE:
            break
    return out


def _prov(tx, holder, prov):
    from ._impl_packet import _PROV, _name_or_desc
    if prov.startswith("told_by:"):
        return f"{_name_or_desc(tx, holder, prov.split(':', 1)[1])} told you"
    if prov.startswith("read:"):
        return "you read it"
    if prov.startswith("rumour"):
        return "a rumour"
    return _PROV.get(prov, "you are not sure where from")


def recall(tx, packet, query, subject_ids, turn_index, at):
    from ._impl_p6 import _content_words
    from ._impl_packet import _age
    from .consult import MAX_RECALL
    holder = packet.actor_id
    shown_eps = {v for k, v in packet.handles.items() if k.startswith("E")}
    shown_beliefs = {b.text for b in packet.beliefs}
    words = _content_words([query]) if (query or "").strip() else []
    subj = set(subject_ids)
    match = set()
    if words:
        q = " OR ".join(f'"{w}"' for w in words)
        match = {r[0] for r in tx.query("SELECT rowid FROM episodes_fts WHERE episodes_fts MATCH ?", (q,))}
    lines = []
    for e in tx.query("SELECT rowid, * FROM episodes WHERE holder_id=? AND decayed=0 AND quarantined=0 ORDER BY salience DESC, at DESC, episode_id",
                      (holder,)):
        e = dict(e)
        if e["episode_id"] in shown_eps:
            continue
        if e["rowid"] in match or (subj & set(json.loads(e["subject_ids"]))):
            lines.append(f"You remember ({_age(at - e['at'])}): {e['summary']}")
    pats = [re.compile(r"(?<![\w'])" + re.escape(w) + r"(?![\w'])", re.I) for w in words]
    for r in tx.query("SELECT h.*, p.text AS ptext, p.subject_id AS psub, c.predicate AS cpred, c.object_value AS cval, "
                      "c.subject_id AS csub FROM claim_holdings h LEFT JOIN propositions p ON p.prop_id=h.claim_id "
                      "LEFT JOIN claims c ON c.claim_id=h.claim_id WHERE h.holder_id=? AND h.believed=1 AND "
                      "h.superseded_by IS NULL ORDER BY h.confidence DESC, h.acquired_at DESC, h.claim_id", (holder,)):
        text = r["ptext"] if r["ptext"] is not None else f"{r['cpred']} {r['cval'] or ''}".strip()
        sub = r["psub"] if r["ptext"] is not None else r["csub"]
        if text in shown_beliefs:
            continue
        if sub in subj or any(p.search(text) for p in pats):
            lines.append(f"You believe ({_prov(tx, holder, r['provenance'])}, {_age(at - r['acquired_at'])}): {text}")
    return lines[:MAX_RECALL] or ["Nothing more comes back to you."]


def answer(tx, packet, affordances, consultation, defs, turn_index, at):
    from .consult import Consulted
    ids = []
    for h in consultation.subjects:
        if h.startswith("P"):
            ids.append(packet.handles[h])
        elif h.startswith("S"):
            r = tx.query_one("SELECT source_id FROM percept_log WHERE percept_id=?", (packet.handles[h],))
            if r and r[0]:
                ids.append(r[0])
    if consultation.kind == "recall":
        return Consulted("recall", lines=recall(tx, packet, consultation.query, ids, turn_index, at))
    more = more_actions(affordances, consultation.family, ids, defs)
    words = AFFORDANCE_FAMILIES[consultation.family]
    n = len(affordances.options)
    if more:
        line = f"More ways of {words}: {', '.join(f'A{n + i}' for i in range(1, len(more) + 1))}."
    else:
        line = f"Nothing more of that kind comes to mind ({words})."
    return Consulted("more_actions", lines=[line], options=more)
