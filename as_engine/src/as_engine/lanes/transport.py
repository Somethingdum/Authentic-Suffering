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
        raise NotImplementedError("P1 — see module docstring")

    async def send(self, lane: LaneConfig, request: LMRequest) -> LMResponse:
        raise NotImplementedError("P1")

    async def list_models(self, lane_id: Lane, lane: LaneConfig) -> list[str]:
        raise NotImplementedError("P1")

    async def health(self, lane_id: Lane, lane: LaneConfig) -> bool:
        raise NotImplementedError("P1")

    async def aclose(self) -> None:
        raise NotImplementedError("P1")
