"""Call log and replay (P1). Rule DET-03 (lanes/calllog.py)."""

from __future__ import annotations

import hashlib

import pytest

from as_engine.contracts.common import CallClass, Lane
from as_engine.contracts.lanes import ChatMessage, LMRequest, LMResponse
from as_engine.contracts.settings import LaneConfig
from as_engine.kernel.jsoncanon import canonical_json
from as_engine.lanes.calllog import ReplayMismatch, ReplayTransport, record

pytestmark = pytest.mark.phase(1)


def _pair(text, turn=1):
    q = LMRequest(call_class=CallClass.NARRATION, lane=Lane.A, turn_index=turn,
                  messages=[ChatMessage(role="user", content=text)])
    r = LMResponse(call_class=CallClass.NARRATION, lane=Lane.A, text=f"out:{text}")
    return q, r


async def test_record_and_replay_in_order(store):
    """DET-03: every call is recorded with a request hash; replay returns them in call order."""
    pairs = [_pair("one"), _pair("two")]
    with store.transaction() as tx:
        seqs = [record(tx, q, r) for q, r in pairs]
    assert seqs == [1, 2]
    rows = store.query("SELECT request_hash FROM lm_calls ORDER BY rowid")
    exp = hashlib.sha256(canonical_json(pairs[0][0].model_dump(mode="json", exclude={"context", "seq"})).encode()).hexdigest()
    assert rows[0]["request_hash"] == exp
    rt = ReplayTransport(store)
    lane = LaneConfig(name="a")
    assert (await rt.send(lane, pairs[0][0])).text == "out:one"
    assert (await rt.send(lane, pairs[1][0])).text == "out:two"


async def test_replay_detects_divergence(store):
    q, r = _pair("one")
    with store.transaction() as tx:
        record(tx, q, r)
    rt = ReplayTransport(store)
    with pytest.raises(ReplayMismatch):
        await rt.send(LaneConfig(name="a"), _pair("different")[0])


async def test_replay_matches_by_request_not_by_position(store):
    """DET-03 (P7 amendment): concurrent calls finish in any order, so replay finds a recorded call by
    its request hash (the first not-yet-replayed row of that turn with that hash), not by position;
    a recorded failure replays as the same failure."""
    from as_engine.lanes.errors import LaneTimeout
    a, b = _pair("one"), _pair("two")
    t = _pair("three")
    with store.transaction() as tx:
        record(tx, *a)
        record(tx, *b)
        record(tx, t[0], LMResponse(call_class=CallClass.NARRATION, lane=Lane.A, parse_status="timeout", error="deadline"))
    rt = ReplayTransport(store)
    lane = LaneConfig(name="a")
    assert (await rt.send(lane, b[0])).text == "out:two"
    assert (await rt.send(lane, a[0])).text == "out:one"
    with pytest.raises(ReplayMismatch):
        await rt.send(lane, a[0])  # each recorded call replays once
    with pytest.raises(LaneTimeout):
        await rt.send(lane, t[0])
