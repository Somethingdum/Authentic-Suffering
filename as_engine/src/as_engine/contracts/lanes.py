"""Lane client contracts (docs/as/08_LLM_CALLS.md §Adapter boundary).

Nothing above this boundary knows which model answered (IFACE-01).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .common import CallClass, Lane, Strict


class ChatMessage(Strict):
    role: Literal["system", "user", "assistant"]
    content: str


class LMRequest(Strict):
    call_class: CallClass
    lane: Lane
    messages: list[ChatMessage] = Field(min_length=1)
    schema_name: str | None = None
    json_schema: dict[str, Any] | None = None
    temperature: float = 0.7
    top_p: float = 0.95
    max_tokens: int = 512
    thinking: bool = False
    deadline_s: float = 60.0
    cache_key: str = Field(default="", description="sha256 of the stable prompt prefix (system message).")
    actor_id: str | None = None
    turn_index: int | None = None
    seq: int | None = Field(default=None, description="Per-turn call sequence number, assigned by the call log.")
    context: Any = Field(default=None, exclude=True, description="Structured object the messages were rendered from. In-process only; never sent over HTTP. Fakes read it.")


ParseStatus = Literal["ok", "grammar_fail", "schema_fail", "empty", "timeout", "lane_error", "cancelled"]


class LMResponse(Strict):
    call_class: CallClass
    lane: Lane
    text: str = ""
    reasoning: str | None = None
    parsed: dict[str, Any] | None = None
    parse_status: ParseStatus = "ok"
    error: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    model: str = ""
    raw: str | None = Field(default=None, description="Raw body retained on failure only.")
