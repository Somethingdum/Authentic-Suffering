"""A turn played again under the same number starts clean (P13, D-299). Rules HOST-12, HOST-13
(host/transport.py new_turn, host/service.py).

Ask again goes back one turn and plays it again: the writing a Stop ended the first time is asked for
again, and answers the host gave the first time are never this time's.
"""

from __future__ import annotations

import pytest
from host_kit import call, only

from as_engine.host.protocol import b64

pytestmark = pytest.mark.phase(13)


async def test_ask_again_after_a_stopped_writing(world0, host, hosted):
    h = host(fail={"narration": {"failed": "stopped", "why": "stopped"}})
    svc = hosted(h)
    await call(svc, "open", world=b64(world0))
    first = await call(svc, "turn", mode="do", text="I look over the fence.", tier=3)
    assert first["turn"] == 1
    h.fail.clear()
    back = await call(svc, "fork", base=b64(world0), head=first["world"], turn=0)
    assert "error" not in back and back["turn"] == 0
    writes = sum(1 for k, _p in h.calls if k == "write")
    again = await call(svc, "turn", mode="do", text="I look over the fence.", tier=3)
    assert again["turn"] == 1 and only(again, "turn_result")["narration"]
    assert sum(1 for k, _p in h.calls if k == "write") > writes, "the writing is asked for again, not refused"


async def test_answers_left_from_an_earlier_try_are_not_reused(world0, host, hosted):
    first = host()
    s1 = hosted(first)
    await call(s1, "open", world=b64(world0))
    await call(s1, "turn", mode="do", text="I look over the fence.", tier=3)
    h = host()
    svc = hosted(h)
    await call(svc, "open", world=b64(world0))
    leftovers = first.results[:-1]                 # a crash resume that got as far as it got …
    await call(svc, "turn", mode="do", text="I look over the fence.", tier=3, answers=leftovers)
    await call(svc, "fork", base=b64(world0), head=(await call(svc, "save"))["world"], turn=0)
    n = len(h.calls)
    await call(svc, "turn", mode="do", text="I look over the fence.", tier=3)
    assert len(h.calls) > n, "… and the next try asks the host afresh"
