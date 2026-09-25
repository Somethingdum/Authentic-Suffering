"""Portrayal audit (P11). Rules AUDIT-01, PORT-01..07, L13; DECISIONS D-07.

A lane-B call that did NOT produce the decision judges "would this person do that?" against their
record (prompts/portrayal_audit.*.j2: the identity card, nerve, what they perceived and heard, their
task and dependents, the choice, its words, goal and reason). The judge's call id always differs
from the producer's (the audit_log CHECK). The audit never chooses for anyone: at most the person
decides again, once, and whatever they then decide stands.

PORT-01 high_stakes(tx, actor_id, intent, turn_index, answered) -> str | None — why a decision is
  judged BEFORE it happens (D-07: only a few, so the critical path stays short), or None. Only a
  model's decision (intent.source 'model') of a HOT or WARM person; the first that applies:
    'moral'  intent.bound.tags has a contracts.common.MoralTag value (its option crosses a moral
             line of some kind — steal, harm_dependent, abandon_post, attack_unarmed, …);
    'attack' intent.bound.verb is 'attack';
    'order'  one of turn.cognition.asks_for(tx, actor_id, turn_index, answered) has
             mind.firewall.classify_standing(tx, speaker, actor_id, its words) VALID_ORDER — what
             they do now obeys or defies an order they accept.
PORT-02 payload_of(packet, intent) -> ActionPayload | None: the decision as the model gave it —
  choice = the handle of the first packet affordance whose label is intent.bound.label (none ->
  None: not a menu choice, nothing to judge); pace; speech = SpeechOut(text, to = each id of
  speech.to as its packet handle ('everyone' stays; an id with no handle is left out), volume,
  delivery, timing) or None; goal; private_reason or None.
PORT-03 call_id(request) -> str: f"{call_class}:{actor_id or '-'}:{the first 16 of
  lanes.calllog.request_hash(request)}" — how audit_log names the producer and the judge.
PORT-04 audit_request(config, packet, intent, turn_index) -> LMRequest | None: None when
  payload_of is None; else lanes.requests.build_request(config, CallClass.PORTRAYAL_AUDIT,
  turn_index=turn_index, actor_id=packet.actor_id, context=AuditContext(packet, output=that payload,
  chosen_label=intent.bound.label), json_schema=lanes.schemas.to_lm_schema(PortrayalVerdict),
  ctx=the context).
PORT-05 precheck(tx, client, config, actor_id, packet, request, intent, reason, regenerate,
  turn_index, at) -> Intent   (turn.cognition step 1b, before the barrier)
  judge = one client.call(audit_request(...), PortrayalVerdict). Its row: audit.log.record(tx,
  'G06-portrayal', producer = call_id(request), result, [{actor_id, when: 'precheck', reason,
  def_id: intent.bound.def_id, verdict, reasons, cites}], turn_index, judge = call_id(the audit
  request)), result 'pass' for fits, 'warn' for doubtful or an answer that does not read (verdict
  None, reasons [] — an audit that cannot be read judges nothing), 'fail' for out_of_character.
  Only 'out_of_character' goes further: when the decision's one repair (turn.cognition REPLY-02)
  is not spent, it2 = await regenerate(REDO + '; '.join(reasons) + '.', the payload's JSON) — that
  repair, read like any repair; it2 None (the answer did not read) -> the first intent stands and
  audit.log.repair(tx, 'portrayal_fail', 6, 'PORT-05', {actor_id, reasons, kept: 'first'},
  turn_index, at). it2 an Intent -> judged once more, the same way and recorded the same way
  (when 'precheck_again'); it stands whatever the verdict — the person decided again — and a
  second out_of_character adds audit.log.repair(..., 'portrayal_fail', ..., {actor_id, reasons:
  the second's, kept: 'second'}). The repair already spent -> the intent stands and
  'portrayal_fail' {actor_id, reasons, kept: 'first'} is logged.
PORT-06 retrospective — every other judged decision, after the fact (turn.pipeline S14/S15,
  lane B alongside the writeback calls): the decisions a wave's decide collected
  (Judged(actor_id, lod, packet, request, intent, prechecked)) that were not prechecked and are a
  HOT person's, or a WARM person's that carried speech. jobs(config, judged, turn_index) -> list
  of (Judged, LMRequest) (audit_request not None), sorted by actor_id then order collected.
  record_retrospective(tx, judged, request, response, turn_index): result as in PORT-05, gate
  'G15-portrayal', when 'retrospective', label = intent.bound.label in the finding.
PORT-07 note_for(tx, actor_id, turn_index) -> str | None: what a retrospective 'fail' leaves the
  person (D-07: a note in their next packet instead of rewriting the past) — the latest
  audit_log row (turn_index desc, audit_id desc) with gate 'G15-portrayal', result 'fail', whose
  first finding's actor_id is the actor and turn_index in [turn_index - NOTE_TURNS, turn_index -
  1] -> f"Looking back on what you did ({label}): someone who knows you would say that was not
  like you — {'; '.join(reasons) or 'it did not fit'}." (mind.packet puts it in
  SkullPacket.portrayal_note.)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from ..action.intent import Intent
    from ..contracts.lanes import LMRequest, LMResponse
    from ..contracts.mind import ActionPayload, SkullPacket
    from ..contracts.settings import EngineConfig
    from ..kernel.store import Tx

REDO = ("Someone who knows you well would say this is not like you: ")
NOTE_TURNS = 3


@dataclass
class Judged:
    actor_id: str
    lod: Any
    packet: "SkullPacket"
    request: "LMRequest"
    intent: "Intent"
    prechecked: bool


def high_stakes(tx: "Tx", actor_id: str, intent: "Intent", turn_index: int, answered) -> str | None:
    from ..contracts.common import MoralTag, Standing
    from ..mind.firewall import classify_standing
    from ..turn.cognition import asks_for
    if intent is None or intent.source != "model":
        return None
    if set(intent.bound.tags) & {m.value for m in MoralTag}:
        return "moral"
    if str(getattr(intent.bound.verb, "value", intent.bound.verb)) == "attack":
        return "attack"
    for ask in asks_for(tx, actor_id, turn_index, answered):
        words = (ask["detail"] or {}).get("words") or ""
        if words and classify_standing(tx, ask["speaker"], actor_id, words) == Standing.VALID_ORDER:
            return "order"
    return None


def payload_of(packet: "SkullPacket", intent: "Intent") -> "ActionPayload | None":
    from ..contracts.mind import ActionPayload, SpeechOut
    choice = next((o.handle for o in packet.affordances if o.label == intent.bound.label), None)
    if choice is None:
        return None
    speech = None
    if intent.speech is not None:
        back = {v: k for k, v in sorted(packet.handles.items())}
        to = [t if t == "everyone" else back[t] for t in intent.speech.to if t == "everyone" or t in back]
        speech = SpeechOut(text=intent.speech.text, to=to, volume=intent.speech.volume, delivery=intent.speech.delivery,
                           timing=intent.speech.timing)
    return ActionPayload(choice=choice, pace=intent.pace, speech=speech, goal=intent.goal or "-",
                         private_reason=intent.private_reason or None)


def call_id(request: "LMRequest") -> str:
    from ..lanes.calllog import request_hash
    cc = getattr(request.call_class, "value", request.call_class)
    return f"{cc}:{request.actor_id or '-'}:{request_hash(request)[:16]}"


def audit_request(config: "EngineConfig", packet: "SkullPacket", intent: "Intent", turn_index: int) -> "LMRequest | None":
    from ..contracts.calls import AuditContext
    from ..contracts.common import CallClass
    from ..contracts.mind import PortrayalVerdict
    from ..lanes.requests import build_request
    from ..lanes.schemas import to_lm_schema
    pl = payload_of(packet, intent)
    if pl is None:
        return None
    ctx = AuditContext(packet=packet, output=pl, chosen_label=intent.bound.label)
    return build_request(config, CallClass.PORTRAYAL_AUDIT, turn_index=turn_index, actor_id=packet.actor_id, context=ctx,
                         json_schema=to_lm_schema(PortrayalVerdict), ctx=ctx)


def _verdict(resp: "LMResponse"):
    from ..contracts.mind import PortrayalVerdict
    if resp.parse_status != "ok":
        return None
    try:
        return PortrayalVerdict.model_validate(resp.parsed)
    except Exception:  # noqa: BLE001 — an answer that does not validate judges nothing
        return None


def _record(tx, gate, when, actor_id, intent, producer, judge_req, v, turn_index, reason=None):
    from ..audit.log import record
    result = "warn" if v is None else {"fits": "pass", "doubtful": "warn", "out_of_character": "fail"}[v.verdict]
    f = {"actor_id": actor_id, "when": when, "def_id": intent.bound.def_id, "label": intent.bound.label,
         "verdict": None if v is None else v.verdict, "reasons": [] if v is None else list(v.reasons),
         "cites": [] if v is None else list(v.cites)}
    if reason is not None:
        f["reason"] = reason
    record(tx, gate, producer, result, [f], turn_index, judge=call_id(judge_req))
    return result


async def precheck(tx: "Tx", client, config: "EngineConfig", actor_id: str, packet: "SkullPacket", request: "LMRequest",
                   intent: "Intent", reason: str, regenerate: Callable[[str, str], Awaitable[Any]] | None,
                   turn_index: int, at: int) -> "Intent":
    from ..audit.log import repair as log_repair
    from ..contracts.mind import PortrayalVerdict
    q = audit_request(config, packet, intent, turn_index)
    if q is None:
        return intent
    v = _verdict(await client.call(q, PortrayalVerdict))
    if _record(tx, "G06-portrayal", "precheck", actor_id, intent, call_id(request), q, v, turn_index, reason) != "fail":
        return intent
    reasons = list(v.reasons)
    if regenerate is None:
        log_repair(tx, "portrayal_fail", 6, "PORT-05", {"actor_id": actor_id, "reasons": reasons, "kept": "first"}, turn_index, at)
        return intent
    it2 = await regenerate(REDO + ("; ".join(reasons) or "it does not fit who you are") + ".",
                           payload_of(packet, intent).model_dump_json())
    if it2 is None:
        log_repair(tx, "portrayal_fail", 6, "PORT-05", {"actor_id": actor_id, "reasons": reasons, "kept": "first"}, turn_index, at)
        return intent
    q2 = audit_request(config, packet, it2, turn_index)
    if q2 is None:
        return it2
    v2 = _verdict(await client.call(q2, PortrayalVerdict))
    if _record(tx, "G06-portrayal", "precheck_again", actor_id, it2, call_id(request), q2, v2, turn_index, reason) == "fail":
        log_repair(tx, "portrayal_fail", 6, "PORT-05", {"actor_id": actor_id, "reasons": list(v2.reasons), "kept": "second"},
                   turn_index, at)
    return it2


def jobs(config: "EngineConfig", judged: list[Judged], turn_index: int) -> list[tuple[Judged, "LMRequest"]]:
    from ..contracts.common import LOD
    out = []
    order = sorted(range(len(judged)), key=lambda i: (judged[i].actor_id, i))
    for i in order:
        j = judged[i]
        if j.prechecked or not (j.lod == LOD.HOT or (j.lod == LOD.WARM and j.intent.speech is not None)):
            continue
        q = audit_request(config, j.packet, j.intent, turn_index)
        if q is not None:
            out.append((j, q))
    return out


def record_retrospective(tx: "Tx", judged: Judged, request: "LMRequest", response: "LMResponse", turn_index: int) -> str:
    return _record(tx, "G15-portrayal", "retrospective", judged.actor_id, judged.intent, call_id(judged.request), request,
                   _verdict(response), turn_index)


def note_for(tx: "Tx", actor_id: str, turn_index: int) -> str | None:
    for r in tx.query("SELECT findings FROM audit_log WHERE gate='G15-portrayal' AND result='fail' AND turn_index BETWEEN ? AND ? "
                      "ORDER BY turn_index DESC, audit_id DESC", (turn_index - NOTE_TURNS, turn_index - 1)):
        f = (json.loads(r[0]) or [{}])[0]
        if f.get("actor_id") == actor_id:
            why = "; ".join(f.get("reasons") or []) or "it did not fit"
            return f"Looking back on what you did ({f.get('label')}): someone who knows you would say that was not like you — {why}."
    return None
