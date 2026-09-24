"""Bounded repair (P1). Rule LANE-06: at most one repair call per failed structured call."""

from __future__ import annotations

import pytest

from as_engine.contracts.common import CallClass, Lane
from as_engine.contracts.lanes import ChatMessage, LMRequest
from as_engine.contracts.mind import SayMyWayOutput
from as_engine.lanes.repair import call_with_repair

pytestmark = pytest.mark.phase(1)


def _req():
    return LMRequest(call_class=CallClass.SAY_MY_WAY, lane=Lane.B, messages=[ChatMessage(role="user", content="x")])


def _repair(request, resp):
    return LMRequest(call_class=CallClass.INTENT_REPAIR, lane=Lane.B, temperature=0.1,
                     messages=[ChatMessage(role="user", content=f"fix: {resp.error}")])


async def test_success_needs_no_repair(client, fake):
    fake.script(CallClass.SAY_MY_WAY, {"line": "ok", "survived": "intact"})
    r, repaired = await call_with_repair(client, _req(), SayMyWayOutput, repair_builder=_repair)
    assert r.parse_status == "ok" and repaired is False
    assert fake.calls(CallClass.INTENT_REPAIR) == []


async def test_one_repair_then_give_up(client, fake):
    """LANE-06: a failed structured call gets exactly one repair; a second failure is returned, not retried."""
    fake.fail(CallClass.SAY_MY_WAY, "grammar_fail")
    fake.fail(CallClass.INTENT_REPAIR, "schema_fail")
    r, repaired = await call_with_repair(client, _req(), SayMyWayOutput, repair_builder=_repair)
    assert repaired is True and r.parse_status == "schema_fail"
    assert len(fake.calls(CallClass.INTENT_REPAIR)) == 1


async def test_repair_can_succeed(client, fake):
    fake.fail(CallClass.SAY_MY_WAY, "schema_fail")
    fake.script(CallClass.INTENT_REPAIR, {"line": "fixed", "survived": "garbled"})
    r, repaired = await call_with_repair(client, _req(), SayMyWayOutput, repair_builder=_repair)
    assert repaired and r.parse_status == "ok" and r.parsed["line"] == "fixed"


async def test_timeouts_are_not_repaired(client, fake):
    """Only grammar/schema failures are repairable; a timeout is returned as is."""
    fake.fail(CallClass.SAY_MY_WAY, "timeout")
    r, repaired = await call_with_repair(client, _req(), SayMyWayOutput, repair_builder=_repair)
    assert r.parse_status == "timeout" and repaired is False
