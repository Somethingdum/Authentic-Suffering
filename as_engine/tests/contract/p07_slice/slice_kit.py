"""P7 test kit (PROTECTED): the scripted "Night at Delgado's" turn (docs/as/04_TURN_PIPELINE.md
§7) and small helpers for driving whole turns with the fake model.

The fake answers each mind from ITS OWN packet (the request's context): a scripted answer names an
option by its definition and referent, and ``pick`` finds that option's handle in the packet it was
given — so a script can only choose what that mind was actually offered.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from as_engine.contracts.common import CallClass
from as_engine.contracts.protocol import InTurnSubmit


def pick(w, request, def_id, *, target=None, dest=None):
    """The handle of the option (def_id, target local id, destination local id) in this request's
    packet. KeyError (listing what WAS offered) when that mind was not offered it."""
    p = request.context.packet if hasattr(request.context, "packet") else request.context
    for a in p.affordances:
        d, t, de, _i = p.handles[a.handle].split(":")
        if d == def_id and (target is None or t == w.id(target)) and (dest is None or de == w.id(dest)):
            return a.handle
    raise KeyError(f"{w.local(p.actor_id)} was not offered {def_id} {target or ''} {dest or ''}: "
                   f"{[p.handles[a.handle] for a in p.affordances]}")


def entity(w, request, local):
    """The P-handle of a body in this request's packet (or aftermath packet)."""
    p = request.context.aftermath if hasattr(request.context, "aftermath") else request.context
    p = p.packet if hasattr(p, "packet") else p
    for e in p.entities:
        if p.handles[e.handle] == w.id(local):
            return e.handle
    raise KeyError(local)


def percept_handle(request, contains):
    """The S-handle of the first percept / utterance of an aftermath packet whose text contains ``contains``."""
    a = request.context.aftermath
    for s in a.percepts:
        if contains in s.text:
            return s.handle
    for u in a.utterances:
        if contains in (u.words or ""):
            return u.handle
    raise KeyError(f"{contains!r} not perceived by {a.holder_id}: {[s.text for s in a.percepts]}")


def cognition(choice, *, speech=None, to=("everyone",), volume="normal", goal="carry on", reason="It seemed right."):
    def answer(req):
        return {"choice": choice(req), "speech": None if speech is None else {"text": speech, "to": list(to), "volume": volume},
                "manner": "", "goal": goal, "private_reason": reason}
    return answer


def writeback(episode, salience=40, beliefs=None):
    def answer(req):
        return {"episode": episode, "salience": salience, "beliefs": beliefs(req) if beliefs else [], "relationships": [],
                "new_loops": [], "closed_loops": [], "lesson": None}
    return answer


def play(session, mode="do", text="", **kw):
    """Run one whole turn synchronously; returns the TurnOutcome."""
    from as_engine.turn.pipeline import run_turn
    return asyncio.run(run_turn(session, InTurnSubmit(mode=mode, text=text, **kw)))


def script_night_at_delgados(w, fake):
    """The anchor turn's model answers (04 §7). The player typed "I watch the front window and keep quiet."."""
    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "observe_area"), "none_reason": None, "manner": "quietly",
                                            "remainder": None, "clarify": None})
    fake.script(CallClass.ACTOR_COGNITION, actor_id=w.id("mara"),
                response=cognition(lambda r: pick(w, r, "take_cover", dest="rear_cover"), speech="Quiet.",
                                   goal="cover the back", reason="That came from the back. Whoever it is will hear us."))
    fake.script(CallClass.ACTOR_COGNITION, actor_id=w.id("june"),
                response=cognition(lambda r: pick(w, r, "go_look", dest="back_door_in"), speech="What was that?", volume="raised",
                                   goal="see what fell", reason="Something crashed out back."))
    fake.script(CallClass.ACTOR_COGNITION, actor_id=w.id("alice"),
                response=cognition(lambda r: pick(w, r, "watch_portal", target="storeroom_door"),
                                   goal="watch the storeroom door", reason="Loud means trouble, and trouble comes through that door."))
    fake.script(CallClass.ACTOR_COGNITION, actor_id=w.id("nita"),
                response=cognition(lambda r: pick(w, r, "hide", dest="dumpster"), goal="see who is there",
                                   reason="Someone is at the fence again."))
    fake.script(CallClass.ACTOR_COGNITION, actor_id=w.id("stranger"),
                response=cognition(lambda r: pick(w, r, "run_to_anchor", dest="weeds"), goal="get out of sight",
                                   reason="I knocked the sheet down. They will come looking."))
    fake.script(CallClass.ACTOR_REACTION, actor_id=w.id("nita"),
                response=cognition(lambda r: pick(w, r, "hide", dest="dumpster"), goal="stay hidden and watch him",
                                   reason="He ran when June shouted."))
    fake.script(CallClass.WRITEBACK, actor_id=w.id("mara"),
                response=writeback("Something hit the back fence hard. I told them to keep quiet and went for the back.", 50))
    fake.script(CallClass.WRITEBACK, actor_id=w.id("june"),
                response=writeback("Something crashed out back while I was counting. I went to look.", 45))
    fake.script(CallClass.WRITEBACK, actor_id=w.id("alice"),
                response=writeback("Metal crashed out back. I kept my eyes on the storeroom door.", 40))
    fake.script(CallClass.WRITEBACK, actor_id=w.id("nita"),
                response=writeback("Someone was watching the back and ran when June shouted.", 70,
                                   beliefs=lambda r: [{"about": entity(w, r, "stranger"), "claim": "The thin man ran because June shouted.",
                                                       "confidence": 3,
                                                       "because": [percept_handle(r, "What"), percept_handle(r, "moves to the tall weeds")]}]))


def events(w, type_, turn=None):
    sql = "SELECT * FROM events WHERE type = ?" + ("" if turn is None else " AND turn_index = ?") + " ORDER BY seq"
    rows = w.store.query(sql, (type_,) if turn is None else (type_, turn))
    return [dict(r, payload=json.loads(r["payload"])) for r in rows]


def ledger(w, turn, stage):
    r = w.store.query_one("SELECT * FROM turn_ledger WHERE turn_index = ? AND stage = ?", (turn, stage))
    return None if r is None else dict(r, detail=json.loads(r["detail"]))
