"""LaneClient (P1). Rules LANE-01, LANE-02, LANE-05, PARSE-* wiring (lanes/client.py)."""

from __future__ import annotations

import pytest

from as_engine.contracts.common import CallClass, Lane
from as_engine.contracts.lanes import ChatMessage, LMRequest
from as_engine.contracts.mind import SayMyWayOutput
from as_engine.lanes.errors import ModelSwapped

pytestmark = pytest.mark.phase(1)


def req(cc=CallClass.SAY_MY_WAY, lane=Lane.B, deadline=5.0):
    return LMRequest(call_class=cc, lane=lane, messages=[ChatMessage(role="user", content="x")], deadline_s=deadline)


async def test_ok_parse(client, fake):
    fake.script(CallClass.SAY_MY_WAY, {"line": "Stay in.", "survived": "softened"})
    r = await client.call(req(), SayMyWayOutput)
    assert r.parse_status == "ok" and r.parsed == {"line": "Stay in.", "survived": "softened"}
    assert r.raw is None


async def test_think_blocks_are_stripped_before_parsing(client, fake):
    """PARSE-01 inside the client: reasoning kept apart from the visible text."""
    fake.script(CallClass.SAY_MY_WAY, '<think>hmm</think>{"line": "Go.", "survived": "intact"}')
    r = await client.call(req(), SayMyWayOutput)
    assert r.parse_status == "ok" and r.reasoning == "hmm" and r.parsed["line"] == "Go."


@pytest.mark.parametrize("kind,status", [("grammar_fail", "grammar_fail"), ("schema_fail", "schema_fail"),
                                         ("empty", "empty"), ("timeout", "timeout"), ("lane_error", "lane_error")])
async def test_failures_are_statuses_not_exceptions(client, fake, kind, status):
    """LANE-01/02: model failures become parse statuses; raw text kept only on failure."""
    fake.fail(CallClass.SAY_MY_WAY, kind)
    r = await client.call(req(), SayMyWayOutput)
    assert r.parse_status == status
    if status in ("grammar_fail", "schema_fail"):
        assert r.raw is not None


async def test_lane_error_marks_lane_down_until_health(client, fake):
    """LANE-01: after a LaneUnavailable the lane is down; later calls short-circuit; health revives it."""
    fake.fail(CallClass.SAY_MY_WAY, "lane_error")
    await client.call(req(), SayMyWayOutput)
    assert client.is_down(Lane.B)
    before = len(fake.requests)
    r = await client.call(req(), SayMyWayOutput)
    assert r.parse_status == "lane_error" and len(fake.requests) == before  # not even sent
    health = await client.refresh_health()
    assert health[Lane.B] is True and not client.is_down(Lane.B)


async def test_plain_text_call_without_model(client, fake):
    fake.script(CallClass.NARRATION, "The crash came from out back.")
    r = await client.call(req(CallClass.NARRATION, Lane.A))
    assert r.parse_status == "ok" and r.text == "The crash came from out back." and r.parsed is None


async def test_on_call_sees_every_call(config, fake):
    from as_engine.lanes.client import LaneClient

    seen = []
    c = LaneClient(config, fake, on_call=lambda q, r: seen.append((q.call_class, r.parse_status)))
    fake.fail(CallClass.SAY_MY_WAY, "schema_fail")
    await c.call(req(), SayMyWayOutput)
    await c.call(req(), SayMyWayOutput)
    assert seen == [(CallClass.SAY_MY_WAY, "schema_fail"), (CallClass.SAY_MY_WAY, "ok")]


async def test_model_swap_guard(client, fake, config):
    """LANE-05: a lane whose configured model is not loaded is a hard stop."""
    await client.check_models()  # defaults match the fake
    fake.set_models(Lane.A, ["some-other-model"])
    with pytest.raises(ModelSwapped):
        await client.check_models()
