"""Settings → Gameplay and the Developer panel (P8). Rules PROTO-10, SET-01, SET-02, DET-02
(service/session.change_settings, service/replay.resimulate, service/game_service.py:
on_settings_get, on_settings_set, on_dev_get).
"""

from __future__ import annotations

import json

import pytest

from as_engine.contracts.settings import RunSettings
from as_engine.service import game_service
from as_engine.service.replay import resimulate
from as_engine.service.session import CHANGEABLE_SETTINGS
from protocol_kit import actions, error_code, only, send

pytestmark = pytest.mark.phase(8)


async def loaded(svc, make_run):
    rid = make_run()
    await send(svc, "run_load", run_id=rid)
    return rid


def settings_events(svc):
    return [json.loads(r["payload"]) for r in svc.session.store.query(
        "SELECT payload FROM events WHERE type = 'SETTINGS_CHANGE' ORDER BY seq")]


async def test_settings_get_lists_what_may_change(svc, make_run):
    await loaded(svc, make_run)
    s = only(await send(svc, "settings_get"), "settings")
    assert RunSettings.model_validate(s["settings"]) == svc.session.settings
    assert s["changeable"] == list(CHANGEABLE_SETTINGS)
    assert "difficulty" not in s["changeable"] and "save_mode" not in s["changeable"]


async def test_settings_set_commits_one_event_per_field(svc, make_run):
    """SET-01: each changed field is one SETTINGS_CHANGE {field, old, new}; meta follows; the receipt
    disappears from the view at once when Show dice goes off."""
    await loaded(svc, make_run)
    before = settings_events(svc)
    r = await send(svc, "settings_set", patch={"show_mechanics": "off", "narration_length": "long", "dev_mode": False})
    assert actions(r) == ["settings", "view"]
    new = settings_events(svc)[len(before):]
    assert new == [{"field": "narration_length", "old": "medium", "new": "long"},
                   {"field": "show_mechanics", "old": "summary", "new": "off"}], "CHANGEABLE_SETTINGS order; unchanged fields make no event"
    s = svc.session.settings
    assert (s.narration_length, s.show_mechanics) == ("long", "off")
    assert RunSettings.model_validate_json(svc.session.store.meta("settings_json")) == s
    assert only(r, "view")["view"]["mechanics"] is None
    assert only(r, "settings")["settings"]["narration_length"] == "long"


@pytest.mark.parametrize("patch,code", [({"difficulty": "easy"}, "locked"), ({"save_mode": "free"}, "locked"),
                                        ({"narration_length": "epic"}, "bad_request"), ({"nonsense": 1}, "bad_request")])
async def test_locked_or_wrong_settings_change_nothing(svc, make_run, patch, code):
    """SET-02: what defines the world is chosen once."""
    await loaded(svc, make_run)
    before = (svc.session.settings, settings_events(svc))
    r = await send(svc, "settings_set", patch=patch)
    assert error_code(r) == code
    if code == "locked":
        assert only(r, "error")["message"] == game_service.LOCKED.format(field=next(iter(patch)))
    assert (svc.session.settings, settings_events(svc)) == before


async def test_replay_repeats_a_settings_change(svc, make_run, cfg, gated):
    """SET-01 + DET-02: a longer scene length chosen between two turns is re-applied at the same point
    when the run is re-simulated, so every turn still comes out the same."""
    rid = await loaded(svc, make_run)
    await send(svc, "turn_submit", mode="do", text="I watch the front door.")
    await svc.idle()
    await send(svc, "settings_set", patch={"narration_length": "long"})
    await send(svc, "turn_submit", mode="say", text="Keep it down.")
    await svc.idle()
    await send(svc, "run_close")
    report = await resimulate(cfg, rid)
    assert [(e["turn_index"], e["ok"]) for e in report] == [(1, True), (2, True)]


async def test_developer_data_needs_developer_mode(svc, make_run):
    await loaded(svc, make_run)
    r = await send(svc, "dev_get", what="trace")
    assert only(r, "error") == {"code": "dev_mode_off", "message": game_service.DEV_MODE_OFF, "recoverable": True}


async def test_developer_data_after_a_turn(svc, make_run):
    """The one place engine vocabulary may appear: stage timeline, events, gate bits, model traffic."""
    await loaded(svc, make_run)
    await send(svc, "settings_set", patch={"dev_mode": True})
    await send(svc, "turn_submit", mode="do", text="I watch the front door.")
    await svc.idle()
    trace = only(await send(svc, "dev_get", what="trace"), "dev_data")
    assert trace["turn_index"] == 1 and trace["what"] == "trace"
    assert [row["stage"] for row in trace["rows"]] == list(range(20))
    assert isinstance(trace["rows"][4]["detail"]["waves"], list), "JSON columns arrive parsed"
    gate = only(await send(svc, "dev_get", what="gate", turn_index=1), "dev_data")["rows"]
    assert len(gate) == 1 and gate[0]["passed"] == 1 and len(gate[0]["world_bits"]) == 16
    events = only(await send(svc, "dev_get", what="events"), "dev_data")["rows"]
    assert events and [e["seq"] for e in events] == sorted(e["seq"] for e in events)
    assert all(isinstance(e["payload"], dict) for e in events)
    intents = only(await send(svc, "dev_get", what="intents"), "dev_data")["rows"]
    assert {e["type"] for e in intents} <= {"ACTION_START", "ACTION_BLOCKED", "DEGRADED_FALLBACK", "SPEECH"}
    assert "ACTION_START" in {e["type"] for e in intents}
    calls = only(await send(svc, "dev_get", what="calls"), "dev_data")["rows"]
    assert {"intake", "narration"} <= {c["call_class"] for c in calls}
    minds = only(await send(svc, "dev_get", what="packets"), "dev_data")["rows"]
    assert {c["call_class"] for c in minds} <= {"actor_cognition", "actor_reaction", "intent_repair"}
    errors = only(await send(svc, "dev_get", what="errors"), "dev_data")["rows"]
    assert isinstance(errors, list)
