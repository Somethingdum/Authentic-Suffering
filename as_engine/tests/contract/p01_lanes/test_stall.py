"""No deadline: a call ends when it finishes, fails, is cancelled, or stalls (LANE-10, LANE-11; D-110).

The owner's rule: a model that thinks for four minutes is working, not hung. So nothing is cut off for
taking long; a call is stopped only when it makes NO progress (no token, no reasoning, no prefill
advance) for the lane's whole stall window. These tests stream through httpx.MockTransport with a
scripted server body and shrink the window and the check interval to a fraction of a second.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from as_engine.contracts.common import CallClass, Lane
from as_engine.contracts.lanes import ChatMessage, LMRequest, LMResponse
from as_engine.contracts.settings import EngineConfig, LaneConfig
from as_engine.lanes import transport as T
from as_engine.lanes.client import LaneClient
from as_engine.lanes.errors import LaneStalled, LaneTimeout, LaneUnavailable
from as_engine.lanes.progress import CallProgress
from as_engine.lanes.transport import HttpTransport

pytestmark = pytest.mark.phase(1)


@pytest.fixture(autouse=True)
def fast_ticks(monkeypatch):
    monkeypatch.setattr(T, "TICK_S", 0.02)


def req(**kw):
    base = dict(call_class=CallClass.NARRATION, lane=Lane.A,
                messages=[ChatMessage(role="system", content="S"), ChatMessage(role="user", content="U")],
                deadline_s=0.05)            # the EXPECTED time: far shorter than any of these calls
    base.update(kw)
    return LMRequest(**base)


def lane(**kw):
    base = dict(name="a", base_url="http://x/v1", model="m", stall_window_s=0.3)
    base.update(kw)
    return LaneConfig(**base)


def sse(delta=None, **extra) -> bytes:
    chunk = {"choices": [{"delta": delta if delta is not None else {}}]}
    chunk.update(extra)
    return ("data: " + json.dumps(chunk) + "\n\n").encode()


DONE = b"data: [DONE]\n\n"


class Script(httpx.AsyncByteStream):
    """A server's body. Items: bytes (sent now), a number (seconds of silence), an Exception (raised)."""

    def __init__(self, items, closed: asyncio.Event | None = None, sent: asyncio.Event | None = None):
        self.items, self.closed, self.sent = items, closed, sent

    async def __aiter__(self):
        try:
            for it in self.items:
                if isinstance(it, Exception):
                    raise it
                if isinstance(it, (int, float)):
                    await asyncio.sleep(it)
                else:
                    yield it
                    if self.sent is not None:
                        self.sent.set()
        finally:
            if self.closed is not None:
                self.closed.set()

    async def aclose(self) -> None:
        return None


def server(items, capture=None, head_delay=0.0, **kw):
    async def handler(request: httpx.Request):
        if capture is not None:
            capture.append(json.loads(request.content))
        if head_delay:
            await asyncio.sleep(head_delay)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=Script(items, **kw))
    return HttpTransport(transport=httpx.MockTransport(handler))


async def run(t, ln=None, r=None, within=10):
    try:
        return await asyncio.wait_for(t.send(ln or lane(), r or req()), within)
    finally:
        await t.aclose()


# ------------------------------------------------------------------------- a call that moves is never cut off


async def test_a_call_that_keeps_moving_outlasts_the_window_and_its_expected_time():
    items = [sse({"content": "w%d " % i}) if i % 2 else sse({"reasoning_content": "t%d " % i}) for i in range(9)]
    items = [x for it in items for x in (it, 0.1)] + [sse({}, usage={"prompt_tokens": 40, "completion_tokens": 9}), DONE]
    r = await run(server(items))                               # ~0.9 s of work against a 0.3 s window and 0.05 s expectation
    assert r.text == "w1 w3 w5 w7 " and r.reasoning == "t0 t2 t4 t6 t8 "
    assert (r.prompt_tokens, r.completion_tokens) == (40, 9) and r.latency_ms >= 800


async def test_reasoning_alone_is_progress():
    items = [x for i in range(8) for x in (sse({"reasoning_content": "hm "}), 0.1)] + [sse({"content": "ok"}), DONE]
    r = await run(server(items))
    assert r.text == "ok" and r.reasoning == "hm " * 8


async def test_the_stream_is_asked_for_with_usage():
    cap = []
    await run(server([sse({"content": "x"}), DONE], capture=cap))
    assert cap[0]["stream"] is True and cap[0]["stream_options"] == {"include_usage": True}


# ------------------------------------------------------------------------- a stall ends it


async def test_no_progress_for_the_window_is_a_stall():
    with pytest.raises(LaneStalled) as e:
        await run(server([sse({"content": "one"}), 30]))
    assert "no progress" in str(e.value) and isinstance(e.value, LaneTimeout)


async def test_keepalives_empty_deltas_and_repeated_counters_are_not_progress():
    items = [sse({"content": "hi"}), b": keep-alive\n\n", 0.12, sse({}), 0.12, b": ping\n\n", 0.12, sse({"content": "late"}), DONE]
    with pytest.raises(LaneStalled):
        await run(server(items), lane())                      # 0.36 s of nothing against a 0.3 s window


async def test_a_prefill_counter_that_stops_advancing_is_a_stall():
    pp = sse({}, prompt_progress={"total": 1000, "cache": 0, "processed": 100})
    with pytest.raises(LaneStalled):
        await run(server([pp, 0.15, pp, 0.15, pp, 0.15, pp, 30]), lane(prefill_progress="supported"))


# ------------------------------------------------------------------------- the silent wait before the first token


async def test_silent_prefill_has_no_limit_by_default():
    """A cold 100K-token prompt can take ten minutes and the server says nothing: not a stall."""
    items = [0.7, sse({"content": "ready"}), DONE]
    r = await run(server(items), lane(stall_window_s=0.2))     # 0.7 s of silence against a 0.2 s window
    assert r.text == "ready"


async def test_a_silent_response_head_has_no_limit_by_default():
    r = await run(server([sse({"content": "ready"}), DONE], head_delay=0.7), lane(stall_window_s=0.2))
    assert r.text == "ready"


async def test_silent_prefill_window_applies_when_the_owner_sets_one():
    with pytest.raises(LaneStalled):
        await run(server([30]), lane(stall_window_s=5, silent_prefill_window_s=0.2))
    with pytest.raises(LaneStalled):
        await run(server([sse({"content": "x"}), DONE], head_delay=30), lane(stall_window_s=5, silent_prefill_window_s=0.2))


async def test_prefill_progress_is_progress_and_the_window_applies_from_the_first_second():
    cap = []
    items = [x for n in range(1, 8) for x in (sse({}, prompt_progress={"total": 700, "cache": 0, "processed": n * 100}), 0.1)]
    items += [sse({"content": "done"}), DONE]
    r = await run(server(items, capture=cap), lane(prefill_progress="supported"))     # 0.7 s of prefill, 0.3 s window
    assert r.text == "done" and cap[0]["return_progress"] is True
    with pytest.raises(LaneStalled):                                                   # supported + silent = a stall
        await run(server([30]), lane(prefill_progress="supported"))


async def test_return_progress_is_asked_only_when_the_lane_is_known_to_support_it():
    cap = []
    await run(server([sse({"content": "x"}), DONE], capture=cap), lane(prefill_progress="unknown"))
    await run(server([sse({"content": "x"}), DONE], capture=cap), lane(prefill_progress="unsupported"))
    assert all("return_progress" not in b for b in cap)


# ------------------------------------------------------------------------- failures and the Stop button


async def test_cancelling_a_call_closes_the_stream():
    closed, sent = asyncio.Event(), asyncio.Event()
    t = server([sse({"content": "x"}), 30], closed=closed, sent=sent)
    task = asyncio.ensure_future(t.send(lane(), req()))
    await asyncio.wait_for(sent.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(closed.wait(), 5)                   # the connection was dropped, which stops the model
    await t.aclose()


async def test_an_error_event_and_a_dropped_connection_are_lane_errors_not_stalls():
    with pytest.raises(LaneUnavailable):
        await run(server([sse({"content": "x"}), b'data: {"error": {"message": "boom"}}\n\n']))
    with pytest.raises(LaneUnavailable):
        await run(server([sse({"content": "x"}), httpx.ReadError("reset")]))


async def test_a_server_that_ignores_stream_is_read_as_one_body():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "whole", "reasoning_content": "why"}}],
                                         "usage": {"prompt_tokens": 5, "completion_tokens": 2}})
    r = await run(HttpTransport(transport=httpx.MockTransport(handler)))
    assert (r.text, r.reasoning, r.prompt_tokens, r.completion_tokens) == ("whole", "why", 5, 2)


# ------------------------------------------------------------------------- LANE-11: progress is reported


async def test_progress_snapshots_show_the_phases_and_the_wait():
    seen = []
    t = server([sse({"reasoning_content": "mm "}), 0.15, sse({"content": "word"}), 0.05, DONE])
    t.sink = lambda request, prog: seen.append(prog.snapshot())
    await run(t)
    phases = [s["phase"] for s in seen]
    assert "thinking" in phases and phases[-1] == "writing"
    last = seen[-1]
    assert last["text_chars"] == 4 and last["reasoning_chars"] == 3 and last["progressed"] and last["slow"] is True
    assert any(s["quiet_s"] >= 0.1 for s in seen)              # it reported the quiet stretch too


async def test_the_client_has_no_deadline_and_reports_what_is_live():
    class Slow:
        sink = None

        async def send(self, ln, request):
            prog = CallProgress(request.call_class, request.lane, expected_s=request.deadline_s)
            await asyncio.sleep(0.3)                           # six times the expectation
            prog.note_text(3)
            self.sink(request, prog)
            return LMResponse(call_class=request.call_class, lane=request.lane, text="hi!")

    got = []
    c = LaneClient(EngineConfig(), Slow())
    c.on_progress = lambda request, snap: got.append(snap)
    r = await c.call(req(deadline_s=0.05))
    assert r.parse_status == "ok" and r.text == "hi!"
    assert got and got[0]["slow"] is True and c.live == {}     # reported, never cut off, and nothing left in flight


async def test_a_stall_comes_back_as_a_timeout_status_and_the_lane_stays_up():
    class Hung:
        async def send(self, ln, request):
            raise LaneStalled("no progress for 300s (thinking); the model may have hung")

    c = LaneClient(EngineConfig(), Hung())
    r = await c.call(req())
    assert r.parse_status == "timeout" and "no progress" in r.error and not c.is_down(Lane.A)


# ------------------------------------------------------------------------- the settings


def test_the_stall_window_defaults_to_five_minutes_and_silent_prefill_to_no_limit():
    ln = LaneConfig(name="a")
    assert ln.stall_window_s == 300.0 and ln.silent_prefill_window_s == 0.0 and ln.prefill_progress == "unknown"
    with pytest.raises(Exception):
        LaneConfig(name="a", stall_window_s=0)


def test_an_old_config_that_still_has_request_timeout_s_loads():
    ln = LaneConfig(name="a", request_timeout_s=240.0)         # D-110: retired, ignored, not an error
    assert not hasattr(ln, "request_timeout_s") and ln.stall_window_s == 300.0


def test_progress_only_moves_forward():
    p = CallProgress(CallClass.NARRATION, Lane.A, expected_s=1)
    assert p.phase == "waiting" and not p.progressed
    assert p.note_prefill(100, 1000) is True and p.phase == "prefill"
    assert p.note_prefill(100, 1000) is False and p.note_prefill(90, 1000) is False
    assert p.note_prefill(200, 1000, cache=50) is True and p.prompt_cache == 50
    p.note_reasoning(4)
    assert p.phase == "thinking"
    p.note_text(2)
    p.note_reasoning(4)
    assert p.phase == "writing"
