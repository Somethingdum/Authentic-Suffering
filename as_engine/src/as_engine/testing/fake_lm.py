"""FakeTransport: a deterministic stand-in for LM Studio (IMPLEMENTED, protected test infra).

It satisfies lanes.transport.Transport. It never parses prompt text: it reads the structured
``LMRequest.context`` object (contracts/calls.py) and answers with a schema-valid JSON string (or
plain text for text-output call classes).

Usage in tests::

    fake = FakeTransport()
    fake.script(CallClass.ACTOR_COGNITION, actor_id="act_000002",
                response={"choice": "A3", "goal": "check the noise", "private_reason": "I heard glass"})
    fake.fail(CallClass.WRITEBACK, "timeout", times=1)
    fake.down(Lane.B)
    ... run the engine with LaneClient(config, fake) ...
    assert fake.calls(CallClass.NARRATION)

Scripted responses are consumed FIFO per (call_class, actor_id) then per (call_class, None);
when none remain the default policy answers. ``response`` may be a dict (dumped to JSON), a str
(returned verbatim — use it to simulate malformed output) or a callable(request) -> dict|str.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Callable, Literal

from ..contracts.calls import (
    AuditContext,
    GuideContext,
    IntakeContext,
    LintContext,
    RepairContext,
    SayMyWayContext,
    SummaryContext,
    WritebackContext,
)
from ..contracts.common import CallClass, Lane, Verb
from ..contracts.lanes import LMRequest, LMResponse
from ..contracts.mind import SkullPacket
from ..contracts.narration import NarratorPacket
from ..contracts.settings import LaneConfig
from ..lanes.errors import LaneTimeout, LaneUnavailable

Response = dict | str | Callable[[LMRequest], "dict | str"]
FailKind = Literal["timeout", "lane_error", "grammar_fail", "empty", "schema_fail"]

_WORD = re.compile(r"[a-z0-9']+")
_STOP = {
    "the", "a", "an", "to", "of", "and", "or", "in", "on", "at", "for", "with", "my", "your", "i",
    "me", "it", "is", "go", "get", "about", "this", "that", "then", "up", "down", "into", "from",
}


@dataclass
class _Fail:
    kind: FailKind


def _content_words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2}


def default_cognition(packet: SkullPacket) -> dict:
    """Deterministic policy: keep doing the current task; else wait/observe; else the first option."""
    order = [Verb.CONTINUE_TASK, Verb.WAIT, Verb.OBSERVE, Verb.GUARD]
    chosen = None
    for verb in order:
        for opt in packet.affordances:
            if opt.verb == verb:
                chosen = opt
                break
        if chosen:
            break
    if chosen is None:
        chosen = packet.affordances[0]
    return {"choice": chosen.handle, "speech": None, "manner": "", "goal": "carry on as before",
            "private_reason": "Nothing here changes what I was doing."}


def default_intake(ctx: IntakeContext) -> dict:
    words = _content_words(ctx.player_text)
    best, best_score = None, 0
    for opt in ctx.packet.affordances:
        score = len(words & _content_words(opt.label))
        if score > best_score:
            best, best_score = opt, score
    if best is None:
        return {"choice": "NONE", "none_reason": "unclear", "manner": "", "remainder": None,
                "clarify": "What do you want to do?"}
    return {"choice": best.handle, "none_reason": None, "manner": "", "remainder": None, "clarify": None}


def default_writeback(ctx: WritebackContext) -> dict:
    a = ctx.aftermath
    first = a.percepts[0].text if a.percepts else "nothing I could make sense of"
    return {"episode": f"I noticed this: {first}", "salience": 20, "beliefs": [], "relationships": [],
            "new_loops": [], "closed_loops": [], "lesson": None}


def default_worldgen(cc: CallClass, ctx: Any) -> dict:
    """P10 defaults (deterministic): history keeps the skeleton facts and adds a belief layer; an
    actor answer is the code skeleton unchanged; the opening is built from the listed entities."""
    fields = getattr(ctx, "fields", {}) or {}
    if cc == CallClass.WORLDGEN_HISTORY:
        out = []
        for e in fields.get("events", []):
            text = str(e.get("skeleton", "Something happened."))
            rest = text.split(": ", 1)[1] if ": " in text else text
            out.append({"id": e["id"], "truth": text + " Nobody who was there tells it the same way.",
                        "belief": "They say " + rest[:1].lower() + rest[1:]})
        return {"events": out}
    if cc == CallClass.WORLDGEN_ACTOR:
        return dict(fields.get("skeleton", {}))
    ents = fields.get("entities", []) or [{"id": "none", "what": "trouble"}]
    params = sorted((fields.get("params") or {"instability": 5}).items())
    first = ents[0]
    pc = str(fields.get("pc", "They")).split()[0]
    return {"immediate_contacts": f"{pc} can reach the people nearby before dark."[:150],
            "immediate_liabilities": f"{pc} is carrying more than is safe to show."[:150],
            "opening_pressure": f"{first.get('what', 'Trouble')} close to {fields.get('place', 'here')}, and closing."[:200],
            "first_objective": f"Get clear of {fields.get('place', 'here')} before it arrives."[:150],
            "cites_entity_ids": [first["id"]], "cites_params": [params[0][0]]}


def default_narration(packet: NarratorPacket) -> str:
    parts: list[str] = []
    if packet.establish_place:
        parts.append(f"{packet.place_text}.")
    for line in packet.lines:
        if line.kind == "speech" and line.words:
            who = line.speaker or "Someone"
            parts.append(f'{who} says, "{line.words}"')
        else:
            text = line.text.strip()
            parts.append(text if text.endswith((".", "!", "?")) else text + ".")
    if not parts:
        parts.append(f"{packet.place_text}. Nothing moves.")
    return " ".join(parts)


class FakeTransport:
    def __init__(self, latency_ms: int = 1, models: dict[Lane, list[str]] | None = None):
        self.latency_ms = latency_ms
        self.requests: list[LMRequest] = []
        self._scripts: dict[tuple[CallClass, str | None], deque] = defaultdict(deque)
        self._down: set[Lane] = set()
        self._models = models or {
            Lane.A: ["nemotron-cascade-2-30b-a3b"],
            Lane.B: ["nvidia-nemotron-3.5-lightning-30b-a3b"],
        }

    # ------------------------------------------------------------------ scripting
    def script(self, call_class: CallClass, response: Response | None = None, *,
               actor_id: str | None = None, times: int = 1) -> "FakeTransport":
        if response is None:
            raise ValueError("response required")
        for _ in range(times):
            self._scripts[(call_class, actor_id)].append(response)
        return self

    def fail(self, call_class: CallClass, kind: FailKind, *, actor_id: str | None = None,
             times: int = 1) -> "FakeTransport":
        for _ in range(times):
            self._scripts[(call_class, actor_id)].append(_Fail(kind))
        return self

    def down(self, lane: Lane, is_down: bool = True) -> "FakeTransport":
        (self._down.add if is_down else self._down.discard)(lane)
        return self

    def set_models(self, lane: Lane, models: list[str]) -> None:
        self._models[lane] = models

    def calls(self, call_class: CallClass | None = None, actor_id: str | None = None) -> list[LMRequest]:
        out = self.requests
        if call_class is not None:
            out = [r for r in out if r.call_class == call_class]
        if actor_id is not None:
            out = [r for r in out if r.actor_id == actor_id]
        return out

    # ------------------------------------------------------------------ Transport protocol
    async def list_models(self, lane_id: Lane, lane: LaneConfig) -> list[str]:
        if lane_id in self._down:
            raise LaneUnavailable(f"lane {lane_id} is down (fake)")
        return list(self._models.get(lane_id, []))

    async def health(self, lane_id: Lane, lane: LaneConfig) -> bool:
        try:
            await self.list_models(lane_id, lane)
            return True
        except LaneUnavailable:
            return False

    async def send(self, lane: LaneConfig, request: LMRequest) -> LMResponse:
        self.requests.append(request)
        if request.lane in self._down:
            raise LaneUnavailable(f"lane {request.lane} is down (fake)")
        await asyncio.sleep(self.latency_ms / 1000)
        scripted = self._pop(request)
        if isinstance(scripted, _Fail):
            if scripted.kind == "timeout":
                raise LaneTimeout("fake timeout")
            if scripted.kind == "lane_error":
                raise LaneUnavailable("fake lane error")
            text = {"grammar_fail": "I think I'll just do something. {not json",
                    "empty": "",
                    "schema_fail": json.dumps({"unexpected": True})}[scripted.kind]
            return self._resp(request, text)
        if scripted is not None:
            value = scripted(request) if callable(scripted) else scripted
        else:
            value = self._default(request)
        text = value if isinstance(value, str) else json.dumps(value)
        return self._resp(request, text)

    # ------------------------------------------------------------------ internals
    def _pop(self, request: LMRequest):
        for key in ((request.call_class, request.actor_id), (request.call_class, None)):
            q = self._scripts.get(key)
            if q:
                return q.popleft()
        return None

    def _resp(self, request: LMRequest, text: str) -> LMResponse:
        return LMResponse(call_class=request.call_class, lane=request.lane, text=text,
                          prompt_tokens=sum(len(m.content) // 4 for m in request.messages),
                          completion_tokens=len(text) // 4, latency_ms=self.latency_ms,
                          model="fake-" + request.lane.value)

    def _default(self, request: LMRequest) -> dict | str:
        ctx: Any = request.context
        cc = request.call_class
        if cc in (CallClass.ACTOR_COGNITION, CallClass.ACTOR_REACTION):
            return default_cognition(ctx)
        if cc == CallClass.INTENT_REPAIR:
            pkt = ctx.packet if isinstance(ctx, RepairContext) else ctx
            return default_cognition(pkt)
        if cc == CallClass.INTAKE:
            return default_intake(ctx)
        if cc == CallClass.WRITEBACK:
            return default_writeback(ctx)
        if cc == CallClass.PORTRAYAL_AUDIT:
            assert isinstance(ctx, AuditContext) or ctx is None
            return {"verdict": "fits", "reasons": [], "cites": []}
        if cc == CallClass.NARRATION:
            # a bare request (no packet) gets a neutral line, so lane mechanics can be tested alone
            return default_narration(ctx) if isinstance(ctx, NarratorPacket) else "Nothing moves."
        if cc == CallClass.RENDER_LINT:
            assert isinstance(ctx, LintContext) or ctx is None
            return {"unsupported": []}
        if cc == CallClass.GUIDE:
            if isinstance(ctx, GuideContext) and ctx.cheat_query:
                return "The words mean nothing here. Whatever you think you heard, the world has not heard of it."
            return "Here is what you know: " + ("; ".join(ctx.pc_facts[:3]) if isinstance(ctx, GuideContext) and ctx.pc_facts else "not much yet.")
        if cc in (CallClass.SCENE_SUMMARY, CallClass.RECAP):
            lines = ctx.lines if isinstance(ctx, SummaryContext) else []
            return " ".join(lines[:5]) or "Nothing worth remembering happened."
        if cc == CallClass.SAY_MY_WAY:
            seed = ctx.seed_text if isinstance(ctx, SayMyWayContext) else "..."
            return {"line": seed, "survived": "intact"}
        if cc == CallClass.RUMOUR_DISTORT:
            return {"operation": "none", "retold_claim": getattr(ctx, "claim_text", "something happened")}
        if cc == CallClass.CASCADE_ADVISORY:
            return {"suggestions": []}
        if cc == CallClass.REFLECTION:
            return {"goals_add": [], "loops_close": [], "lesson": None, "plan_goal": None, "plan_steps": []}
        if cc == CallClass.CHEAT_PERSONA:
            return "Done, Boss. Reality bent exactly as ordered."
        if cc == CallClass.PROBE:
            return {"ok": True}
        if cc in (CallClass.WORLDGEN_HISTORY, CallClass.WORLDGEN_ACTOR, CallClass.WORLDGEN_OPENING):
            return default_worldgen(cc, ctx)
        # intake / quickmake: tests must script these explicitly
        raise AssertionError(f"FakeTransport has no default for {cc}; script it in the test")
