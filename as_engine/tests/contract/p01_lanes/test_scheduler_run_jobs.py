"""Two-lane job runner (P1). Rules DEGRADE-01 (lanes/scheduler.run_jobs)."""

from __future__ import annotations

import pytest

from as_engine.contracts.common import CallClass, Lane
from as_engine.contracts.lanes import ChatMessage, LMRequest
from as_engine.lanes.scheduler import Job, run_jobs

pytestmark = pytest.mark.phase(1)


def _job(jid, lane_pref, thinking=True):
    r = LMRequest(call_class=CallClass.NARRATION, lane=lane_pref or Lane.B, thinking=thinking,
                  messages=[ChatMessage(role="user", content=jid)])
    return Job(job_id=jid, call_class=CallClass.NARRATION, request=r, lane_pref=lane_pref)


async def test_jobs_run_on_their_lane(client, fake):
    out = await run_jobs(client, [_job("a", Lane.A), _job("b", Lane.B)])
    assert set(out) == {"a", "b"} and all(r.parse_status == "ok" for r in out.values())
    lanes = {r.messages[0].content: r.lane for r in fake.requests}
    assert lanes == {"a": Lane.A, "b": Lane.B}


async def test_down_lane_moves_jobs_without_thinking(client, fake):
    """DEGRADE-01: a job for a down lane moves to the other lane with thinking=False."""
    fake.down(Lane.A)
    client.mark_down(Lane.A)
    out = await run_jobs(client, [_job("a", Lane.A, thinking=True)])
    assert out["a"].parse_status == "ok"
    sent = [r for r in fake.requests if r.messages[0].content == "a"][-1]
    assert sent.lane == Lane.B and sent.thinking is False


async def test_both_lanes_down(client, fake):
    fake.down(Lane.A)
    fake.down(Lane.B)
    client.mark_down(Lane.A)
    client.mark_down(Lane.B)
    out = await run_jobs(client, [_job("a", Lane.A), _job("b", None)])
    assert {r.parse_status for r in out.values()} == {"lane_error"}


async def test_unpinned_job_prefers_b_on_tie(client, fake):
    await run_jobs(client, [_job("x", None)])
    assert fake.requests[-1].lane == Lane.B
