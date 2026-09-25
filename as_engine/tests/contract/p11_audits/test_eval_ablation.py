"""Every call earns its place (P11). Rules LANE-09 (lanes/client.py ablated), the ablation duty
(docs/as/08_LLM_CALLS.md §4; tools/as/eval.py).

On the fake model, the night at Delgado's is played plain and with one call class switched off. A
switched-off call never reaches the model; whoever made it takes the path they already have for a
call that did not come back, and the eval says what changed.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

from as_engine.contracts.common import CallClass
from as_engine.contracts.lanes import LMRequest
from as_engine.lanes.client import LaneClient
from as_engine.testing.fake_lm import FakeTransport

pytestmark = pytest.mark.phase(11)

TOOLS = Path(__file__).resolve().parents[4] / "tools" / "as"


@pytest.fixture(scope="module")
def ev():
    sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location("as_eval_tool", TOOLS / "eval.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_an_ablated_call_never_reaches_the_model():
    from as_engine.contracts.settings import EngineConfig
    fake, seen = FakeTransport(), []
    client = LaneClient(EngineConfig(), fake, on_call=lambda q, r: seen.append(r.parse_status))
    client.ablated = {CallClass.NARRATION}
    q = LMRequest(call_class=CallClass.NARRATION, lane="A", messages=[{"role": "user", "content": "x"}])
    r = asyncio.run(client.call(q))
    assert (r.parse_status, r.error) == ("cancelled", "ablated") and fake.calls() == [] and seen == ["cancelled"]


def test_switching_off_writeback_is_measured(ev):
    plain = asyncio.run(ev.play("metal_fence", 2, None, fake=True))
    off = asyncio.run(ev.play("metal_fence", 2, "writeback", fake=True))
    assert plain["ok_turns"] == off["ok_turns"] == 2, "the world goes on without it"
    assert plain["ablated_calls"] == 0 and off["ablated_calls"] > 0
    assert plain["memory_jobs_failed"] == 0 and off["memory_jobs_failed"] > 0
    c = ev.compare(plain, off)
    assert c["verdict"] == "degrades" and "memory_jobs_failed" in c["changed"]


def test_a_call_that_changes_nothing_is_named_for_removal(ev):
    plain = {"scenario": "x", "ablated": None, "turns": 2, "calls": 9, "ablated_calls": 0, "mean_turn_s": 1.0, "refusals": 0}
    same = dict(plain, ablated="cascade_advisory", calls=7, ablated_calls=2, mean_turn_s=0.8)
    assert ev.compare(plain, same) == {"scenario": "x", "ablated": "cascade_advisory", "changed": {},
                                       "verdict": "removal candidate: nothing measurable changed"}
