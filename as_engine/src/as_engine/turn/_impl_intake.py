"""Implementation of turn/intake.py."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re

NONE_MESSAGES = {
    "impossible": "That can't be done from where you are.",
    "not_here": "That isn't here.",
    "not_holding": "You're not holding that.",
    "not_trained": "You don't know how to do that.",
    "unclear": "It isn't clear what you want to do.",
    "not_an_action": "That isn't something you do in the world. Use Ask for questions.",
}
PLAYER_REASON = "The player chose this."
QUOTE_SPAN = re.compile(r'"[^"]*"|“[^”]*”')


class Rejected(Exception):
    def __init__(self, code, message, clarify=None):
        super().__init__(message)
        self.code, self.message, self.clarify = code, message, clarify


def _handle_of(packet, option):
    for h, v in packet.handles.items():
        if h.startswith("A") and v == option.signature:
            return h
    raise KeyError(option.signature)


def _entity_handle(packet, body_id):
    for h, v in packet.handles.items():
        if h.startswith("P") and v == body_id:
            return h
    return None


def _speak_option(aff, addressee):
    if addressee is not None:
        for o in aff.options:
            if o.def_id == "speak" and o.target_id == addressee:
                return o
    for o in aff.options:
        if o.def_id == "speak" and o.target_id is None:
            return o
    return None


def addressee_for(session, packet, submit):
    if "forced_addressee" in session.extras:
        return session.extras.pop("forced_addressee")
    refs = session.extras.get("view_refs", {})
    for r in submit.addressee_refs:
        b = refs.get(r)
        if b and _entity_handle(packet, b):
            return b
    named = _named_first(packet, submit)
    if named:
        return named
    last = session.extras.get("last_addressee")
    if last and _entity_handle(packet, last):
        return last
    return None


def _named_first(packet, submit):
    import re as _re
    text = submit.text or ""
    if submit.mode == "do":
        q = _re.search(r'["\u201c]([^"\u201d]*)["\u201d]', text)
        text = q.group(1) if q else ""
    m = _re.match(r"\s*([A-Za-z][\w'-]*)\s*[,:]", text)
    if not m:
        return None
    word = m.group(1).lower()
    hits = [e for e in packet.entities if e.known_name and word in (e.known_name.lower(), e.known_name.split()[0].lower())]
    return packet.handles.get(hits[0].handle) if len(hits) == 1 else None


def _speech_intent(packet, aff, words, addressee, lod):
    from ..action.intent import IntentError, to_intent
    from ..contracts.mind import ActionPayload
    opt = _speak_option(aff, addressee)
    if opt is None:
        raise Rejected("impossible", NONE_MESSAGES["impossible"])
    eh = _entity_handle(packet, addressee) if addressee else None
    out = ActionPayload(choice=_handle_of(packet, opt), speech={"text": words, "to": [eh] if eh else ["everyone"], "volume": "normal"},
                        goal=opt.label, private_reason=PLAYER_REASON)
    it = to_intent(packet, aff, out, lod=lod, source="human")
    if isinstance(it, IntentError):
        raise Rejected("unclear", NONE_MESSAGES["unclear"])
    return it


def record_input(tx, turn_index, mode, raw_text, mapped):
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    from ..kernel.clock import now
    h = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    return tx.commit_event(Event(type=EventType.PLAYER_INPUT, writer="turn.pipeline", at=now(tx), turn_index=turn_index,
                                 payload={"mode": mode, "received_hash": h},
                                 writes=[WriteRecord(op=WriteOp.INSERT, table="player_inputs",
                                                     values={"turn_index": turn_index, "mode": mode, "raw_text": raw_text,
                                                             "received_hash": h, "mapped": mapped})]))


def doom_words(text):
    from .intake import DOOM_WORDS_RE
    return DOOM_WORDS_RE.search(text) is not None


async def _tells(session, text, turn_index):
    """Does this pass on anything about the end of life that ordinary people don't know? (DOOM-07)"""
    from ..contracts.calls import DoomGuardContext
    from ..contracts.common import CallClass
    from ..contracts.mind import DoomGuardOutput
    from ..lanes.requests import build_request
    from ..lanes.schemas import to_lm_schema
    ctx = DoomGuardContext(text=text[:2000])
    try:
        req = build_request(session.config, CallClass.DOOM_GUARD, turn_index=turn_index, actor_id=session.pc_id, context=ctx,
                            ctx=ctx, json_schema=to_lm_schema(DoomGuardOutput))
        resp = await session.client.call(req)
        if resp.parse_status == "ok":
            data = resp.parsed if resp.parsed is not None else json.loads(resp.text or "{}")
            return DoomGuardOutput.model_validate(data).tells
    except Exception:  # noqa: BLE001 — the fallback check below
        pass
    return doom_words(text)


async def intake(tx, session, submit, turn_index, t0, calls=None):
    """Returns (Intent, info) where info = {'remainder': str|None, 'addressee': id|None, 'mode': ...}."""
    from ..action.intent import IntentError, to_intent
    from ..contracts.calls import IntakeContext, SayMyWayContext
    from ..contracts.common import LOD, CallClass
    from ..contracts.mind import ActionPayload, IntakeOutput, SayMyWayOutput
    from ..lanes.parse import extract_quotes
    from ..lanes.requests import build_request
    from ..lanes.schemas import intake_schema
    from ..mind import perception
    from ..mind.actor import fused
    from ..mind.affordance import enumerate_affordances
    from ..mind.packet import build_packet
    from ..narration.lint import record_pc_input
    pc = session.pc_id
    perception.compile_scene(tx, pc, t0, turn_index)
    aff = enumerate_affordances(tx, pc, tx.canon.all("affordance"), t0, turn_index)
    pkt = build_packet(tx, pc, LOD.WARM, aff, turn_index, t0)
    lod = LOD.WARM
    info = {"remainder": None, "addressee": None}
    text = (submit.text or "").strip()
    mode = submit.mode
    if text and mode in ("do", "say"):
        from ..physical import bodies
        if bodies.doomed(tx, pc) is not None and tx.query_one("SELECT alive FROM bodies WHERE body_id=?", (pc,))[0] == 1:
            if await _tells(session, text, turn_index):
                from .intake import DOOMED_WORDS
                raise Rejected("doomed_words", DOOMED_WORDS)
    if submit.suggestion_ref:
        entry = session.extras.get("suggestions", {}).get(submit.suggestion_ref)
        if entry is None:
            raise Rejected("suggestion_stale", "That option is gone; things have changed.")
        if entry.get("remainder"):
            text, mode = entry["remainder"], "do"
            raw_mode = "do"   # typed words offered back as a chip: replayed as text
        else:
            opt = next((o for o in aff.options if o.signature == entry["signature"]), None)
            if opt is None:
                raise Rejected("suggestion_stale", "That option is gone; things have changed.")
            if opt.def_id == "speak":
                if not text:
                    raise Rejected("empty", "Type what you want to say.")
                it = _speech_intent(pkt, aff, text, opt.target_id, lod)
                info["addressee"] = opt.target_id
                record_pc_input(tx, turn_index, text, tx.rules.style)
                record_input(tx, turn_index, "say", text, {"signature": it.bound.signature, "words": text, "addressee": opt.target_id})
                return it, info
            out = ActionPayload(choice=_handle_of(pkt, opt), goal=opt.label, private_reason=PLAYER_REASON)
            it = to_intent(pkt, aff, out, lod=lod, source="human")
            if isinstance(it, IntentError):
                raise Rejected("suggestion_stale", "That option is gone; things have changed.")
            record_input(tx, turn_index, "suggestion", entry.get("label", opt.ui_label), {"signature": opt.signature})
            return it, info
    else:
        raw_mode = mode
    if not text:
        raise Rejected("empty", "Type something first.")
    if mode == "say":
        words = text
        if session.settings.pc_voice == "my_way":
            d = fused(tx, pc)
            bl = getattr(d, "behavior_law", None)
            notes = [bl.topic_handling, bl.plan_carry, bl.distortion, bl.pressure] if bl else []
            ctx = SayMyWayContext(packet=pkt, seed_text=text, behavior_notes=notes)
            from ..lanes.schemas import to_lm_schema
            req = build_request(session.config, CallClass.SAY_MY_WAY, turn_index=turn_index, actor_id=pc, context=ctx,
                                json_schema=to_lm_schema(SayMyWayOutput), ctx=ctx)
            resp = await session.client.call(req, SayMyWayOutput)
            if resp.parse_status == "ok":
                words = resp.parsed["line"]
        addressee = addressee_for(session, pkt, submit)
        it = _speech_intent(pkt, aff, words, addressee, lod)
        info["addressee"] = addressee
        record_pc_input(tx, turn_index, text, tx.rules.style)
        record_input(tx, turn_index, raw_mode, text, {"signature": it.bound.signature, "words": words, "addressee": addressee})
        return it, info
    # do
    quotes = extract_quotes(text)
    rest = QUOTE_SPAN.sub(" ", text).strip()
    addressee = addressee_for(session, pkt, submit)
    if quotes and not re.search(r"[A-Za-z]", rest):
        it = _speech_intent(pkt, aff, " ".join(q.strip() for q in quotes), addressee, lod)
        info["addressee"] = addressee
    else:
        ctx = IntakeContext(packet=pkt, player_text=text, quoted_speech=quotes)
        req = build_request(session.config, CallClass.INTAKE, turn_index=turn_index, actor_id=pc, context=ctx,
                            json_schema=intake_schema([a.handle for a in pkt.affordances]), ctx=ctx)
        resp = await session.client.call(req, IntakeOutput)
        if resp.parse_status != "ok":
            raise Rejected("intake_failed", "That didn't come through clearly. Try saying it another way.")
        out = IntakeOutput.model_validate(resp.parsed)
        if out.choice == "NONE":
            code = out.none_reason or "unclear"
            raise Rejected(code, NONE_MESSAGES[code], out.clarify)
        if quotes:
            eh = _entity_handle(pkt, addressee) if addressee else None
            sig = pkt.handles.get(out.choice)
            chosen = next((o for o in (aff.pool or aff.options) if o.signature == sig), None)
            pace = out.pace if chosen is not None and out.pace in chosen.paces else "normal"
            co = ActionPayload(choice=out.choice, pace=pace,
                               speech={"text": " ".join(q.strip() for q in quotes), "to": [eh] if eh else ["everyone"],
                                       "volume": "normal"},
                               goal=(out.manner or _label(pkt, out.choice)), private_reason=PLAYER_REASON)
            it = to_intent(pkt, aff, co, lod=lod, source="human")
            if not isinstance(it, IntentError):
                it = dataclasses.replace(it, manner=out.manner)
            info["addressee"] = addressee
        else:
            it = to_intent(pkt, aff, out, lod=lod, source="human")
        if isinstance(it, IntentError):
            raise Rejected("unclear", NONE_MESSAGES["unclear"], out.clarify)
        info["remainder"] = out.remainder
    record_pc_input(tx, turn_index, text, tx.rules.style)
    record_input(tx, turn_index, raw_mode, text, {"signature": it.bound.signature, "addressee": info["addressee"]})
    return it, info


def _label(pkt, handle):
    for a in pkt.affordances:
        if a.handle == handle:
            return a.label
    return handle
