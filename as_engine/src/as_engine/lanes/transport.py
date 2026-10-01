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
    model, messages (after thinking-mode transform), temperature, top_p, max_tokens,
    stream=true, stream_options={"include_usage": true}
    + return_progress=true when lane.prefill_progress == 'supported' (llama.cpp: the server then streams
        prompt_progress {total, cache, processed} while it reads the prompt)
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
  Response: server-sent events. text = the joined delta.content; reasoning = the joined
  delta.reasoning_content (or delta.reasoning) or None; usage.prompt_tokens / completion_tokens (0, and the
  number of streamed chunks, when absent). A server that ignores ``stream`` and answers with one JSON body is
  read the old way: text = choices[0].message.content or "", the same reasoning fields.
  HTTP errors / connection refused / a dropped stream -> LaneUnavailable.

No deadline (LANE-10, D-110). Nothing ends a call because it has taken long. A call ends only when

  * it finishes;
  * the server fails (above);
  * it STALLS: no progress for ``lane.stall_window_s`` (default 300 s) -> LaneStalled (a LaneTimeout).
    Progress is a streamed token, a streamed reasoning token, or the server's prompt-processing counter
    moving forward. SSE comments, empty deltas and repeated identical counters are not progress.
    Before the first sign of life the window is ``lane.stall_window_s`` when the server reports prefill
    progress (lane.prefill_progress == 'supported'), else ``lane.silent_prefill_window_s`` (0 = no limit:
    a cold 100K-token prompt can take many minutes and the transport cannot see inside the server);
  * the caller cancels it (the Stop button): the connection is closed, which stops the model.
The 5 s ``list_models`` / ``health`` probes below are liveness checks, not call limits.

Progress (LANE-11): ``transport.sink``, when set, is called as ``sink(request, CallProgress)`` about once a
second, on a phase change, and once at the end, so the client and the UI can show whether the model is
waiting, reading the prompt, thinking or writing, and how long it has been quiet.
GET {base_url}/models -> [m["id"] for m in data]. health = list_models succeeds within 5 s.
The client never reads proxies or certificates from the environment (httpx trust_env False; SEAL-04,
D-104): a proxy would carry the game's words off the machine.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Callable, Protocol

from ..contracts.common import Lane
from ..contracts.lanes import LMRequest, LMResponse
from ..contracts.settings import LaneConfig

TICK_S = 1.0          # how often a waiting call is checked for a stall and reported on (LANE-10, LANE-11)
_END = object()       # the end of a stream


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
        self.sink: Callable | None = None       # LANE-11: sink(request, CallProgress)

    # -- the watchdog ----------------------------------------------------------------------------

    @staticmethod
    def window(lane: LaneConfig, prog) -> float | None:
        """LANE-10: how long this call may stay quiet right now (None = no limit)."""
        if prog.progressed or prog.saw_prefill or lane.prefill_progress == "supported":
            return lane.stall_window_s
        return lane.silent_prefill_window_s or None

    def _report(self, request: LMRequest, prog, state: dict, force: bool = False) -> None:
        import time
        if self.sink is None:
            return
        now = time.monotonic()
        if force or prog.phase != state.get("phase") or now - state.get("at", 0.0) >= TICK_S:
            state["phase"], state["at"] = prog.phase, now
            self.sink(request, prog)

    async def _until(self, fut, lane: LaneConfig, request: LMRequest, prog, state: dict):
        """Await ``fut`` (a task), checking for a stall and reporting progress between ticks. Never cancels ``fut``."""
        from .errors import LaneStalled
        while True:
            done, _ = await asyncio.wait({fut}, timeout=TICK_S)
            if done:
                return fut.result()
            win = self.window(lane, prog)
            if win is not None and prog.quiet_s() >= win:
                raise LaneStalled(f"no progress for {win:g}s ({prog.phase}); the model may have hung")
            self._report(request, prog, state)

    # -- one call --------------------------------------------------------------------------------

    async def send(self, lane: LaneConfig, request: LMRequest) -> LMResponse:
        import httpx, time
        from .errors import LaneTimeout, LaneUnavailable
        from .progress import CallProgress
        msgs = [m.model_dump() for m in request.messages]
        body = dict(model=lane.model, temperature=request.temperature, top_p=request.top_p,
                    max_tokens=request.max_tokens, stream=True, stream_options={"include_usage": True})
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
        if lane.prefill_progress == "supported":
            body["return_progress"] = True
        if request.json_schema is not None and lane.structured_mode == "json_schema" and (
                not request.thinking or lane.structured_with_thinking == "supported"):
            body["response_format"] = {"type": "json_schema", "json_schema": {
                "name": request.schema_name or "output", "strict": True, "schema": request.json_schema}}
        prog = CallProgress(request.call_class, request.lane, expected_s=request.deadline_s)
        state: dict = {}
        t0 = time.monotonic()
        r = None
        try:
            r = await self._open(lane, body, request, prog, state)
            if r.status_code >= 400:
                await r.aread()
                raise LaneUnavailable(f"HTTP {r.status_code}")
            if "text/event-stream" in r.headers.get("content-type", ""):
                text, reasoning, usage = await self._read_events(r, lane, request, prog, state)
            else:
                text, reasoning, usage = await self._read_body(r, lane, request, prog, state)
        except httpx.ConnectTimeout as e:
            raise LaneUnavailable(str(e)) from e
        except httpx.TimeoutException as e:
            raise LaneTimeout(str(e)) from e
        except httpx.HTTPError as e:
            raise LaneUnavailable(str(e)) from e
        finally:
            if r is not None:
                with contextlib.suppress(Exception):
                    await r.aclose()
            self._report(request, prog, state, force=True)
        return LMResponse(call_class=request.call_class, lane=request.lane, text=text, reasoning=reasoning,
                          prompt_tokens=usage.get("prompt_tokens", 0),
                          completion_tokens=usage.get("completion_tokens", 0) or prog.chunks,
                          latency_ms=int((time.monotonic() - t0) * 1000), model=lane.model)

    async def _open(self, lane, body, request, prog, state):
        """POST and wait for the response head. No httpx read timeout (the watchdog is ours): only the connect
        (10 s: nobody is listening) and the write (60 s) are bounded."""
        import httpx
        req = self._c.build_request("POST", f"{lane.base_url}/chat/completions", json=body,
                                    headers={"Authorization": f"Bearer {lane.api_key}"},
                                    timeout=httpx.Timeout(None, connect=10.0, write=60.0))
        task = asyncio.ensure_future(self._c.send(req, stream=True))
        try:
            return await self._until(task, lane, request, prog, state)
        except BaseException:
            task.cancel()
            with contextlib.suppress(BaseException):
                await task
            if task.done() and not task.cancelled() and task.exception() is None:
                with contextlib.suppress(Exception):          # the head arrived in the same instant: do not leak it
                    await task.result().aclose()
            raise

    async def _read_body(self, r, lane, request, prog, state):
        """A server that answered with one JSON body (it ignored ``stream``): nothing to watch but the wait."""
        from .errors import LaneUnavailable
        raw = await self._until(asyncio.ensure_future(r.aread()), lane, request, prog, state)
        try:
            data = json.loads(raw)
            msg = data["choices"][0]["message"]
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise LaneUnavailable(f"unreadable reply: {e}") from e
        return (msg.get("content") or "", msg.get("reasoning_content") or msg.get("reasoning") or None,
                data.get("usage") or {})

    async def _read_events(self, r, lane, request, prog, state):
        """LANE-10/11: read server-sent events, noting every sign of progress."""
        from .errors import LaneUnavailable
        q: asyncio.Queue = asyncio.Queue()

        async def pump():
            try:
                async for line in r.aiter_lines():
                    q.put_nowait(line)
                q.put_nowait(_END)
            except BaseException as e:           # a dropped connection reaches the reader as an exception
                q.put_nowait(e)
        reader = asyncio.ensure_future(pump())
        text: list[str] = []
        reasoning: list[str] = []
        usage: dict = {}
        try:
            while True:
                getter = asyncio.ensure_future(q.get())
                try:
                    item = await self._until(getter, lane, request, prog, state)
                except BaseException:
                    getter.cancel()
                    raise
                if item is _END:
                    break
                if isinstance(item, BaseException):
                    raise item
                line = item.strip()
                if not line.startswith("data:"):
                    continue                      # blank lines and ': keep-alive' comments are not progress
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except ValueError:
                    continue
                if not isinstance(chunk, dict):
                    continue
                if chunk.get("error"):
                    raise LaneUnavailable(f"the server reported an error: {str(chunk['error'])[:200]}")
                pp = chunk.get("prompt_progress")
                if isinstance(pp, dict):
                    prog.note_prefill(int(pp.get("processed") or 0), int(pp.get("total") or 0), int(pp.get("cache") or 0))
                if isinstance(chunk.get("usage"), dict):
                    usage = chunk["usage"]
                for ch in chunk.get("choices") or []:
                    d = ch.get("delta") or {}
                    rc = d.get("reasoning_content") or d.get("reasoning") or ""
                    c = d.get("content") or ""
                    if rc:
                        reasoning.append(rc)
                        prog.note_reasoning(len(rc))
                    if c:
                        text.append(c)
                        prog.note_text(len(c))
                    if d.get("tool_calls"):
                        prog.note_text(1)
                if not prog.progressed:
                    prog.note_alive()             # the first chunk: the prompt has been read, generation began
                self._report(request, prog, state)
        finally:
            reader.cancel()
            with contextlib.suppress(BaseException):
                await reader
        return "".join(text), ("".join(reasoning) or None), usage

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
