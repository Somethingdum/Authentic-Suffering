"""Implementation of service/guide.py."""
from __future__ import annotations

import re


def rules_for(question):
    from .guide import GENERAL, GUIDE_TOPICS, MAX_TOPICS
    words = set(re.findall(r"[a-z]+", question.lower()))
    out = [text for kws, text in GUIDE_TOPICS if words & set(kws)][:MAX_TOPICS]
    return out or [GENERAL]


def pc_facts(view, last_narration):
    from .guide import MAX_FACTS
    loc = view.location
    f = [f"Where you are: {loc.place_name}" + (f", {loc.area_name}" if loc.area_name else "") + "."]
    f += list(loc.description_lines)
    if loc.can_see:
        f.append("You can see: " + ", ".join(t.name + (f" ({t.detail})" if t.detail else "") for t in loc.can_see) + ".")
    for p in loc.people:
        f.append(f"{p.label} is here" + (f" ({', '.join(p.status_words)})" if p.status_words else "") + ".")
    for e in loc.exits:
        f.append(f"Way out: {e.label}" + (f" ({', '.join(e.state_words)})" if e.state_words else "")
                 + (f", leads to {e.leads_to}" if e.leads_to != "unknown" else "") + ".")
    for d in loc.dangers:
        f.append(f"Danger you know about: {d}.")
    for i in view.inventory.hands:
        f.append(f"In your hands: {i.name}" + (f" ({i.detail})" if i.detail else "") + ".")
    for w in view.body.wounds:
        f.append(f"Wound: {w.severity_word} {w.what} on the {w.where}, bleeding: {w.bleeding_word}" + (", treated" if w.treated else "") + ".")
    for n in view.body.needs:
        if n.level >= 2:
            f.append(f"{n.name}: {n.word}.")
    if view.body.impairment_word != "clear-headed":
        f.append(f"You feel {view.body.impairment_word}.")
    r = view.body.resolve
    f.append(f"Resolve: {r.cur} of {r.max} ({r.word}).")
    if last_narration is not None:
        f.append(f"What just happened: {last_narration}")
    return f[:MAX_FACTS]


async def answer(session, question, view):
    from ..contracts.calls import GuideContext
    from ..contracts.common import CallClass
    from ..lanes.calllog import record
    from ..lanes.requests import build_request
    from .guide import GUIDE_DOWN
    from .session import append_story
    st = session.store
    row = st.query_one("SELECT text FROM story_log WHERE kind='narration' ORDER BY entry_id DESC LIMIT 1")
    last = row[0] if row else None
    turn = st.query_one("SELECT turn_index FROM world_clock")[0]
    ctx = GuideContext(question=question, pc_name=view.pc_name, pc_facts=pc_facts(view, last), rules_snippets=rules_for(question),
                       cheat_query=False)
    req = build_request(session.config, CallClass.GUIDE, turn_index=None, context=ctx, ctx=ctx)
    resp = await session.client.call(req)
    text = resp.text.strip() if resp.parse_status == "ok" and resp.text and resp.text.strip() else GUIDE_DOWN
    with st.transaction() as tx:
        record(tx, req, resp)
        append_story(tx, turn, "player", question, "ask")
        append_story(tx, turn, "guide", text)
    return text
