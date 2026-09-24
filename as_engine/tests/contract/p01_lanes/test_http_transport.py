"""HttpTransport against httpx.MockTransport (P1). docs/as/08_LLM_CALLS.md §HTTP."""

from __future__ import annotations

import json

import httpx
import pytest

from as_engine.contracts.common import CallClass, Lane
from as_engine.contracts.lanes import ChatMessage, LMRequest
from as_engine.contracts.settings import LaneConfig
from as_engine.lanes.errors import LaneTimeout, LaneUnavailable
from as_engine.lanes.transport import HttpTransport

pytestmark = pytest.mark.phase(1)


def _req(**kw):
    base = dict(call_class=CallClass.ACTOR_COGNITION, lane=Lane.B,
                messages=[ChatMessage(role="system", content="SYS"), ChatMessage(role="user", content="U")],
                schema_name="cognition", json_schema={"type": "object"}, thinking=False, deadline_s=5)
    base.update(kw)
    return LMRequest(**base)


def _mock(capture, status=200, body=None, exc=None):
    def handler(request: httpx.Request):
        if exc:
            raise exc
        capture.append(request)
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "m1"}, {"id": "m2"}]})
        return httpx.Response(status, json=body or {"choices": [{"message": {"content": "{\"a\":1}", "reasoning_content": "thought"}}],
                                                   "usage": {"prompt_tokens": 7, "completion_tokens": 3}})
    return httpx.MockTransport(handler)


async def test_request_body_and_response_mapping():
    cap = []
    t = HttpTransport(transport=_mock(cap))
    lane = LaneConfig(name="b", base_url="http://x/v1", model="m1", structured_mode="json_schema", thinking_mode="native")
    r = await t.send(lane, _req())
    body = json.loads(cap[0].content)
    assert cap[0].url == httpx.URL("http://x/v1/chat/completions")
    assert cap[0].headers["authorization"] == "Bearer lm-studio"
    assert body["model"] == "m1" and body["stream"] is False
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert r.text == '{"a":1}' and r.reasoning == "thought" and (r.prompt_tokens, r.completion_tokens) == (7, 3)
    await t.aclose()


async def test_no_response_format_when_thinking_is_unsupported_with_schema():
    cap = []
    t = HttpTransport(transport=_mock(cap))
    lane = LaneConfig(name="a", model="m1", structured_with_thinking="unknown")
    await t.send(lane, _req(thinking=True))
    assert "response_format" not in json.loads(cap[0].content)
    await t.aclose()


@pytest.mark.parametrize("mode", ["system_no_think", "chat_template_kwargs", "prefill_empty_think"])
async def test_thinking_transforms(mode):
    cap = []
    t = HttpTransport(transport=_mock(cap))
    await t.send(LaneConfig(name="b", model="m1", thinking_mode=mode), _req(thinking=False))
    body = json.loads(cap[0].content)
    if mode == "system_no_think":
        assert body["messages"][0]["content"].endswith("/no_think")
    elif mode == "chat_template_kwargs":
        assert body["chat_template_kwargs"] == {"enable_thinking": False}
    else:
        assert body["messages"][-1] == {"role": "assistant", "content": "<think></think>"}
    await t.aclose()


async def test_errors_map_to_lane_errors():
    t = HttpTransport(transport=_mock([], status=500))
    with pytest.raises(LaneUnavailable):
        await t.send(LaneConfig(name="b", model="m1"), _req())
    await t.aclose()
    t = HttpTransport(transport=_mock([], exc=httpx.ReadTimeout("slow")))
    with pytest.raises(LaneTimeout):
        await t.send(LaneConfig(name="b", model="m1"), _req())
    await t.aclose()
    t = HttpTransport(transport=_mock([], exc=httpx.ConnectError("refused")))
    with pytest.raises(LaneUnavailable):
        await t.send(LaneConfig(name="b", model="m1"), _req())
    await t.aclose()


async def test_list_models_and_health():
    t = HttpTransport(transport=_mock([]))
    lane = LaneConfig(name="b", base_url="http://x/v1", model="m1")
    assert await t.list_models(Lane.B, lane) == ["m1", "m2"]
    assert await t.health(Lane.B, lane) is True
    await t.aclose()
