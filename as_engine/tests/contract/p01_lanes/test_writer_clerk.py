"""The Writer and the Clerk (D-111): lane A writes what the player reads, lane B answers what code can check.

The Writer is a Gemma 4 (the owner's Boulesis v2.1 26B-A4B): it thinks only when ``<|think|>`` opens the system
prompt and returns its reasoning in a thought channel. The Clerk (Nemotron 3.5 Lightning) takes the WARM minds and
the checks. These tests pin the thinking switch, the thought channel and the default regimes.
"""

from __future__ import annotations

import json

import httpx
import pytest

from as_engine.contracts.common import CallClass, Lane
from as_engine.contracts.lanes import ChatMessage, LMRequest
from as_engine.contracts.settings import EngineConfig, LaneConfig, default_regimes
from as_engine.lanes.parse import strip_think
from as_engine.lanes.transport import HttpTransport

pytestmark = pytest.mark.phase(1)

WRITER = {CallClass.NARRATION, CallClass.THE_VOICE, CallClass.WILLIS_ROAST, CallClass.RECAP, CallClass.SCENE_SUMMARY,
          CallClass.SAY_MY_WAY, CallClass.WORLDGEN_HISTORY, CallClass.WORLDGEN_ACTOR, CallClass.WORLDGEN_OPENING,
          CallClass.DOSSIER_INTAKE, CallClass.PC_QUICKMAKE}


def req(messages, thinking):
    return LMRequest(call_class=CallClass.NARRATION, lane=Lane.A, messages=messages, thinking=thinking, deadline_s=60)


async def sent_messages(mode, messages, thinking):
    cap = []

    def handler(request):
        cap.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
    t = HttpTransport(transport=httpx.MockTransport(handler))
    try:
        await t.send(LaneConfig(name="a", base_url="http://x/v1", model="m", thinking_mode=mode), req(messages, thinking))
    finally:
        await t.aclose()
    return cap[0]["messages"]


SYS = [ChatMessage(role="system", content="You tell the story."), ChatMessage(role="user", content="Go.")]


# ------------------------------------------------------------------------- the Writer's thinking switch


async def test_gemma_thinks_only_when_the_think_token_opens_the_system_prompt():
    on = await sent_messages("system_think_token", SYS, True)
    assert on[0] == {"role": "system", "content": "<|think|>\nYou tell the story."} and on[1]["content"] == "Go."
    off = await sent_messages("system_think_token", SYS, False)
    assert off == [m.model_dump() for m in SYS]                        # thinking off: sent exactly as written


async def test_the_think_token_makes_a_system_message_when_there_is_none():
    on = await sent_messages("system_think_token", [ChatMessage(role="user", content="Go.")], True)
    assert on == [{"role": "system", "content": "<|think|>"}, {"role": "user", "content": "Go."}]


async def test_no_other_mode_sends_the_think_token():
    for mode in ("native", "system_no_think", "chat_template_kwargs", "prefill_empty_think", "none"):
        for thinking in (True, False):
            assert all("<|think|>" not in m["content"] for m in await sent_messages(mode, SYS, thinking)), mode


def test_the_thinking_mode_setting_accepts_the_think_token():
    assert LaneConfig(name="a", thinking_mode="system_think_token").thinking_mode == "system_think_token"


# ------------------------------------------------------------------------- the thought channel


def test_a_gemma_thought_channel_is_reasoning_not_story():
    assert strip_think("<|channel>thought\nShe would run.<channel|>She runs.") == ("She runs.", "She would run.")
    assert strip_think("<|channel>thought\nstill weighing it") == ("", "still weighing it")     # cut off mid-thought
    assert strip_think("<|channel>thought\n<channel|>Rain.") == ("Rain.", "")                  # an empty thought
    assert strip_think("<think>a</think>b") == ("b", "a") and strip_think("Plain.") == ("Plain.", None)


# ------------------------------------------------------------------------- the split


def test_the_writer_writes_the_story_and_the_clerk_does_the_rest():
    regs = default_regimes()
    assert {cc for cc, r in regs.items() if r.lane == Lane.A} == WRITER
    for cc in (CallClass.NARRATION, CallClass.THE_VOICE, CallClass.WILLIS_ROAST, CallClass.RECAP, CallClass.SCENE_SUMMARY,
               CallClass.SAY_MY_WAY):
        assert regs[cc].thinking, f"{cc.value}: the Writer thinks before it writes"


def test_the_hot_minds_think_on_the_writer_the_rest_on_the_clerk_and_the_judges_think_too():
    cfg = EngineConfig()
    assert cfg.hot_cognition.lane == Lane.A and cfg.hot_cognition.thinking
    assert cfg.regimes[CallClass.ACTOR_COGNITION].lane == Lane.B
    for cc in (CallClass.RENDER_LINT, CallClass.PORTRAYAL_AUDIT, CallClass.CHEAT_INTERPRET):
        assert cfg.regimes[cc].lane == Lane.B and cfg.regimes[cc].thinking, cc.value


def test_a_call_that_thinks_has_room_to():
    cfg = EngineConfig()
    for cc, r in list(cfg.regimes.items()) + [("hot_cognition", cfg.hot_cognition)]:
        if r.thinking:
            assert r.max_tokens >= 2000, f"{cc}: thinking counts against max_tokens"
