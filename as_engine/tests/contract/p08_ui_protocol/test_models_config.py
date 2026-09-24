"""The Connect screen and Settings → Models (P8). Rules PROTO-10, UI-CLARITY-06, CFG-01..03
(service/game_service.py: on_models_list, on_models_test, on_config_get, on_config_set).
"""

from __future__ import annotations

import pytest
import yaml

from as_engine.contracts.common import CallClass, Lane
from as_engine.service import game_service
from protocol_kit import error_code, only, send

pytestmark = pytest.mark.phase(8)


async def test_models_list_reports_both_brains(svc, gated):
    gated.set_models(Lane.A, ["nemotron-cascade-2-30b-a3b", "other-model"])
    gated.down(Lane.B)
    r = await send(svc, "models_list")
    assert [m["action"] for m in r] == ["models", "models"]
    a, b = r[0]["data"], r[1]["data"]
    assert a == {"lane": "A", "models": ["nemotron-cascade-2-30b-a3b", "other-model"],
                 "selected": "nemotron-cascade-2-30b-a3b", "reachable": True}
    assert b == {"lane": "B", "models": [], "selected": "nvidia-nemotron-3.5-lightning-30b-a3b", "reachable": False}


async def test_models_test_working(svc, gated):
    """Two probe calls: plain, then with a JSON schema. 'Working — answered in … s.'"""
    t = only(await send(svc, "models_test", lane="A"), "model_test_result")
    assert t["ok"] is True and t["structured_ok"] is True and t["thinking_ok"] is None
    assert t["detail"] == game_service.WORKING.format(secs=t["latency_ms"] / 1000)
    probes = gated.calls(CallClass.PROBE)
    assert len(probes) == 2 and all(p.lane == Lane.A for p in probes)
    assert probes[0].json_schema is None and probes[1].json_schema == game_service.PROBE_SCHEMA


async def test_models_test_not_answering_and_model_missing(svc, gated):
    gated.down(Lane.B)
    t = only(await send(svc, "models_test", lane="B"), "model_test_result")
    assert t["ok"] is False
    assert t["detail"] == game_service.NOT_ANSWERING.format(url=svc.config.lanes[Lane.B].base_url)
    gated.set_models(Lane.A, ["something-else"])
    t = only(await send(svc, "models_test", lane="A"), "model_test_result")
    assert t["ok"] is False and t["detail"] == game_service.MODEL_MISSING.format(model="nemotron-cascade-2-30b-a3b")
    assert gated.calls(CallClass.PROBE) == [], "no probe call when the model is not there"


async def test_models_test_with_broken_structured_answers(svc, gated):
    gated.script(CallClass.PROBE, "ready")
    gated.script(CallClass.PROBE, "ready, not json")
    t = only(await send(svc, "models_test", lane="A"), "model_test_result")
    assert t["ok"] is True and t["structured_ok"] is False
    assert t["detail"].endswith(" " + game_service.NO_JSON)
    gated.fail(CallClass.PROBE, "empty")
    t = only(await send(svc, "models_test", lane="A"), "model_test_result")
    assert t["ok"] is False and t["detail"] == game_service.NO_ANSWER


async def test_config_get_and_set_lanes(svc, config_path):
    """The Connect screen edits the lanes and they are written to as_config.yaml (CFG)."""
    c = only(await send(svc, "config_get"), "config")
    assert c["lanes"]["A"]["model"] == "nemotron-cascade-2-30b-a3b" and c["background_cognition"] is True
    r = await send(svc, "config_set", patch={"lanes": {"B": {"base_url": "http://192.168.1.20:1234/v1",
                                                             "model": "lightning-q4"}},
                                             "background_cognition": False})
    c = only(r, "config")
    assert c["lanes"]["B"]["base_url"] == "http://192.168.1.20:1234/v1" and c["lanes"]["B"]["model"] == "lightning-q4"
    assert c["lanes"]["B"]["thinking_mode"] == "native", "fields not in the patch are kept"
    assert c["background_cognition"] is False
    assert svc.config.lanes[Lane.B].model == "lightning-q4"
    saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert saved["lanes"]["B"]["model"] == "lightning-q4" and saved["background_cognition"] is False


@pytest.mark.parametrize("patch", [
    {"regimes": {"narration": {"lane": "B", "temperature": 0.1, "max_tokens": 100, "deadline_s": 10}}},
    {"rules": {}},
    {"lanes": {"C": {"model": "x"}}},
    {"lanes": {"A": {"thinking_mode": "none"}}},
])
async def test_config_set_refuses_everything_else(svc, config_path, patch):
    """PROTO-10: only the lanes (address, model, name, concurrency, timeout) and background thinking.
    A regime change would alter every later request and break re-simulation (DET-02)."""
    before = svc.config
    r = await send(svc, "config_set", patch=patch)
    assert error_code(r) == "bad_request"
    assert svc.config == before and not config_path.exists(), "nothing changed, nothing written"


async def test_config_set_reaches_the_loaded_run(svc, make_run):
    """The run keeps its frozen rules, but talks to the new address from the next call on."""
    rid = make_run()
    await send(svc, "run_load", run_id=rid)
    rules = svc.session.config.rules
    await send(svc, "config_set", patch={"lanes": {"A": {"model": "cascade-q6"}}})
    assert svc.session.config.lanes[Lane.A].model == "cascade-q6"
    assert svc.session.client.config.lanes[Lane.A].model == "cascade-q6"
    assert svc.session.config.rules == rules
