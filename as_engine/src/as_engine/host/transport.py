"""The transport of a hosted engine: every call goes to the host, which picks the model (D-299).
Rules HOST-10..HOST-13, LANE-12.

HostTransport(link, *, recorded=None)   — a lanes.transport.Transport with ``routed = True``
  link: anything with ``async request(type, payload) -> dict`` (as_engine.host.bridge's Link).
  ``governor``: the turn's as_engine.host.governor.Governor, set by the host service per turn (None
  outside a turn: the guide, worldgen, the quiet hours).
  ``recorded``: answers the host already gave, to be used before asking again (HOST-13).

HOST-10 send(lane_cfg, request) -> LMResponse. ``lane_cfg`` is never read: no address, model, key
  or thinking switch of the engine's reaches a host (the host's own presets set sampling).
  T = request.turn_index or 0; h = lanes.calllog.request_hash(request).
  step = STEP[call_class] — for ACTOR_COGNITION / ACTOR_REACTION the governor's step for
  request.actor_id (its focus or mind step of the wave being played), else f"mind:{actor}";
  INTENT_REPAIR f"repair:{actor}".
  author (HOST-05): PORTRAYAL_AUDIT -> the call id of request.actor_id's last decision in turn T;
  RENDER_LINT -> the call id of turn T's last narration draft; else None.
  1. a recorded answer for (T, h) not used yet -> that answer (below), without asking the host.
  2. an optional call (host.work.OPTIONAL_AT_CALL) with a governor that answers may(step) False ->
     CallSkipped('not enough time left') — it answers 'cancelled', as an ablated call does.
  3. a NARRATION call in a turn whose writing was stopped -> LaneRefused('stopped') without asking
     (the narrator then tells the moment plainly instead of drafting again, HOST-12).
  4. call_id = f"c{n}" (n counts this transport's calls from 1). NARRATION goes as
     'write' {call_id, request_hash, work, messages, attempt: its draft number in turn T (1, 2, …)},
     every other class as 'model.call' {call_id, request_hash, work, messages, schema:
     request.json_schema}; messages = [{role, content}] as the engine built them, the stable system
     prompt first (PROMPT-01); work = host.work.work_for(request, step=step, author=author).
  HOST-11 the answer {text, reasoning?, prompt_tokens?, completion_tokens?, latency_ms?, failed?,
  why?}: failed 'refused' -> LaneRefused(why); 'skipped' -> CallSkipped(why); 'timeout' ->
  LaneTimeout(why); 'stopped' -> LaneRefused('stopped') and, for a write, turn T's writing is
  stopped (3.); anything else -> LMResponse(call_class, lane, text, reasoning, the token counts,
  latency_ms, model 'host') — the client parses it as it would any model's answer. Which model
  answered is never kept by the engine (IFACE-01): the host knows it by call_id.
  Decisions (ACTOR_COGNITION / ACTOR_REACTION by actor) and narration drafts (by turn) remember
  their call_id for HOST-05.
HOST-12 Stop while writing: the world was committed at stage 12, so it stands; a stopped write ends
  the drafting and the turn is told plainly (narration.narrator's NARR-FALLBACK), never drafted
  again behind the player's back.
HOST-13 recorded answers: a list of {turn_index, request_hash, result} — the host's own earlier
  answers, each the dict it returned. The first unused one with the call's (turn_index,
  request_hash) is the answer (read as HOST-11), so a turn or a world interrupted by a crash plays
  again with no model call made twice. list_models -> [lane.model]; health -> True (the host
  answers for availability, LANE-12).
"""

from __future__ import annotations

from ..contracts.common import CallClass, Lane
from ..contracts.lanes import LMRequest, LMResponse
from .work import OPTIONAL_AT_CALL, work_for

STEP: dict[CallClass, str] = {
    CallClass.INTAKE: "intake", CallClass.SAY_MY_WAY: "intake", CallClass.DOOM_GUARD: "intake",
    CallClass.NARRATION: "write", CallClass.RENDER_LINT: "judge", CallClass.AMBIENT_LINE: "ambient",
    CallClass.PORTRAYAL_AUDIT: "audit:portrayal", CallClass.WRITEBACK: "memory",
    CallClass.SCENE_SUMMARY: "journal", CallClass.RECAP: "journal", CallClass.GUIDE: "guide",
    CallClass.REFLECTION: "quiet", CallClass.RUMOUR_DISTORT: "quiet", CallClass.PERSON_VOICE: "quiet",
    CallClass.CASCADE_ADVISORY: "advice", CallClass.WILLIS_ROAST: "death", CallClass.THE_VOICE: "doom",
    CallClass.CHEAT_PERSONA: "console", CallClass.CHEAT_INTERPRET: "console",
}
DECISIONS = (CallClass.ACTOR_COGNITION, CallClass.ACTOR_REACTION)


class HostTransport:
    routed = True

    def __init__(self, link, *, recorded: list[dict] | None = None):
        self.link = link
        self.governor = None
        self.sink = None
        self._n = 0
        self._recorded: dict[tuple[int, str], list[dict]] = {}
        for r in recorded or []:
            self._recorded.setdefault((int(r.get("turn_index") or 0), str(r["request_hash"])), []).append(r["result"])
        self._decision: dict[tuple[int, str], str] = {}
        self._draft: dict[int, tuple[str, int]] = {}
        self._stopped: set[int] = set()

    def add_recorded(self, recorded: list[dict]) -> None:
        for r in recorded or []:
            self._recorded.setdefault((int(r.get("turn_index") or 0), str(r["request_hash"])), []).append(r["result"])

    def _step(self, request: LMRequest) -> str:
        cc, actor = request.call_class, request.actor_id
        if cc in DECISIONS:
            got = self.governor.step_for(actor) if self.governor is not None else None
            return got or f"mind:{actor}"
        if cc == CallClass.INTENT_REPAIR:
            return f"repair:{actor}"
        return STEP.get(cc, cc.value)

    def _author(self, request: LMRequest, T: int) -> str | None:
        if request.call_class == CallClass.PORTRAYAL_AUDIT:
            return self._decision.get((T, request.actor_id or ""))
        if request.call_class == CallClass.RENDER_LINT:
            d = self._draft.get(T)
            return d[0] if d else None
        return None

    @staticmethod
    def _answer(request: LMRequest, got: dict) -> LMResponse:
        from ..lanes.errors import CallSkipped, LaneRefused, LaneTimeout
        failed = got.get("failed")
        why = str(got.get("why") or failed or "")
        if failed == "skipped":
            raise CallSkipped(why)
        if failed == "timeout":
            raise LaneTimeout(why)
        if failed:
            raise LaneRefused(why)
        return LMResponse(call_class=request.call_class, lane=request.lane, text=str(got.get("text") or ""),
                          reasoning=got.get("reasoning") or None, prompt_tokens=int(got.get("prompt_tokens") or 0),
                          completion_tokens=int(got.get("completion_tokens") or 0),
                          latency_ms=int(got.get("latency_ms") or 0), model="host")

    async def send(self, lane, request: LMRequest) -> LMResponse:
        from ..lanes.calllog import request_hash
        from ..lanes.errors import CallSkipped, LaneRefused
        T = request.turn_index if request.turn_index is not None else 0
        h = request_hash(request)
        cc = request.call_class
        step = self._step(request)
        author = self._author(request, T)
        rec = self._recorded.get((T, h))
        if rec:
            got = rec.pop(0)
            self._remember(request, T, f"r{h[:12]}")
            return self._answer(request, got)
        if cc in OPTIONAL_AT_CALL and self.governor is not None and not await self.governor.may(step):
            raise CallSkipped("not enough time left")
        if cc == CallClass.NARRATION and T in self._stopped:
            raise LaneRefused("stopped")
        self._n += 1
        call_id = f"c{self._n}"
        payload = {"call_id": call_id, "request_hash": h, "turn_index": T,
                   "work": work_for(request, step=step, author=author),
                   "messages": [{"role": m.role, "content": m.content} for m in request.messages]}
        if cc == CallClass.NARRATION:
            prev = self._draft.get(T)
            payload["attempt"] = (prev[1] + 1) if prev else 1
            self._draft[T] = (call_id, payload["attempt"])
            kind = "write"
        else:
            payload["schema"] = request.json_schema
            kind = "model.call"
        self._remember(request, T, call_id)
        got = await self.link.request(kind, payload)
        if got.get("failed") == "stopped" and cc == CallClass.NARRATION:
            self._stopped.add(T)
        return self._answer(request, got)

    def _remember(self, request: LMRequest, T: int, call_id: str) -> None:
        if request.call_class in DECISIONS and request.actor_id:
            self._decision[(T, request.actor_id)] = call_id
        elif request.call_class == CallClass.NARRATION and T not in self._draft:
            self._draft[T] = (call_id, 1)

    async def list_models(self, lane_id: Lane, lane) -> list[str]:
        return [lane.model]

    async def health(self, lane_id: Lane, lane) -> bool:
        return True
