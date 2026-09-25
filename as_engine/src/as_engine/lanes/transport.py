"""Transports (P1). docs/as/08_LLM_CALLS.md §HTTP.

Transport protocol::

    class Transport(Protocol):
        async def send(self, lane: LaneConfig, request: LMRequest) -> LMResponse: ...
        async def list_models(self, lane_id: Lane, lane: LaneConfig) -> list[str]: ...
        async def health(self, lane_id: Lane, lane: LaneConfig) -> bool: ...

``send`` returns an LMResponse with ``text``/``reasoning``/token counts filled and
parse_status 'ok' (parsing happens in the client), or raises LaneUnavailable / LaneTimeout.

HttpTransport request (OpenAI-compatible, LM Studio):
  POST {lane.base_url}/chat/completions   (base_url already ends in /v1)
  headers: Authorization: Bearer {lane.api_key}
  body:
    model, messages (after thinking-mode transform), temperature, top_p, max_tokens, stream=false
    + response_format = {"type": "json_schema", "json_schema": {"name": schema_name,
        "strict": true, "schema": json_schema}}  when request.json_schema is set AND
        lane.structured_mode == 'json_schema' AND (not request.thinking OR
        lane.structured_with_thinking == 'supported')
  Thinking-mode transform (thinking.apply):
    native               -> unchanged
    system_no_think      -> when thinking is False, append "\n/no_think" to the system message
    chat_template_kwargs -> body["chat_template_kwargs"] = {"enable_thinking": thinking}
    prefill_empty_think  -> when thinking is False, append {"role":"assistant","content":"<think></think>"}
    none                 -> unchanged
  Response: text = choices[0].message.content or ""; reasoning = message.reasoning_content or
  message.reasoning or None; usage.prompt_tokens / completion_tokens (0 when absent).
  HTTP errors / connection refused -> LaneUnavailable; timeout (request.deadline_s) -> LaneTimeout.
GET {base_url}/models -> [m["id"] for m in data]. health = list_models succeeds within 5 s.
The client never reads proxies or certificates from the environment (httpx trust_env False; SEAL-04,
D-104): a proxy would carry the game's words off the machine.
"""

from __future__ import annotations

from typing import Protocol

from ..contracts.common import Lane
from ..contracts.lanes import LMRequest, LMResponse
from ..contracts.settings import LaneConfig


class Transport(Protocol):
    async def send(self, lane: LaneConfig, request: LMRequest) -> LMResponse: ...

    async def list_models(self, lane_id: Lane, lane: LaneConfig) -> list[str]: ...

    async def health(self, lane_id: Lane, lane: LaneConfig) -> bool: ...


class HttpTransport:
    """``HttpTransport(transport=None)``: ``transport`` is passed to ``httpx.AsyncClient(transport=...)``
    so tests can inject ``httpx.MockTransport`` (real runs pass nothing)."""

    def __init__(self, transport: object | None = None) -> None:
        import httpx
        self._c = (httpx.AsyncClient(transport=transport, trust_env=False) if transport is not None
                   else httpx.AsyncClient(trust_env=False))

    async def send(self, lane: LaneConfig, request: LMRequest) -> LMResponse:
        import httpx, time
        from .errors import LaneTimeout, LaneUnavailable
        msgs = [m.model_dump() for m in request.messages]
        body = dict(model=lane.model, temperature=request.temperature, top_p=request.top_p,
                    max_tokens=request.max_tokens, stream=False)
        mode = lane.thinking_mode
        if mode == "system_no_think" and not request.thinking:
            for m in msgs:
                if m["role"] == "system":
                    m["content"] += "\n/no_think"; break
        elif mode == "chat_template_kwargs":
            body["chat_template_kwargs"] = {"enable_thinking": request.thinking}
        elif mode == "prefill_empty_think" and not request.thinking:
            msgs.append({"role": "assistant", "content": "<think></think>"})
        body["messages"] = msgs
        if request.json_schema is not None and lane.structured_mode == "json_schema" and (
                not request.thinking or lane.structured_with_thinking == "supported"):
            body["response_format"] = {"type": "json_schema", "json_schema": {
                "name": request.schema_name or "output", "strict": True, "schema": request.json_schema}}
        t0 = time.monotonic()
        try:
            r = await self._c.post(f"{lane.base_url}/chat/completions", json=body,
                                   headers={"Authorization": f"Bearer {lane.api_key}"}, timeout=request.deadline_s)
        except httpx.TimeoutException as e:
            raise LaneTimeout(str(e)) from e
        except httpx.HTTPError as e:
            raise LaneUnavailable(str(e)) from e
        if r.status_code >= 400:
            raise LaneUnavailable(f"HTTP {r.status_code}")
        data = r.json()
        msg = data["choices"][0]["message"]
        usage = data.get("usage") or {}
        return LMResponse(call_class=request.call_class, lane=request.lane, text=msg.get("content") or "",
                          reasoning=msg.get("reasoning_content") or msg.get("reasoning") or None,
                          prompt_tokens=usage.get("prompt_tokens", 0), completion_tokens=usage.get("completion_tokens", 0),
                          latency_ms=int((time.monotonic() - t0) * 1000), model=lane.model)

    async def list_models(self, lane_id: Lane, lane: LaneConfig) -> list[str]:
        import httpx
        from .errors import LaneUnavailable
        try:
            r = await self._c.get(f"{lane.base_url}/models", headers={"Authorization": f"Bearer {lane.api_key}"}, timeout=5)
        except httpx.HTTPError as e:
            raise LaneUnavailable(str(e)) from e
        if r.status_code >= 400:
            raise LaneUnavailable(f"HTTP {r.status_code}")
        return [m["id"] for m in r.json()["data"]]

    async def health(self, lane_id: Lane, lane: LaneConfig) -> bool:
        from .errors import LaneUnavailable
        try:
            await self.list_models(lane_id, lane); return True
        except LaneUnavailable:
            return False

    async def aclose(self) -> None:
        await self._c.aclose()
