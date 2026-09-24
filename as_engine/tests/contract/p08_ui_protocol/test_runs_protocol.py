"""Home, Continue, Load, Save, Close, Delete (P8). Rules PROTO-01, RUN-02..06, RUN-12 through the protocol
(service/game_service.py: on_runs_list, on_run_load, on_run_save, on_run_close, on_run_delete,
on_view_get, on_story_get).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from as_engine.contracts.settings import RunSettings
from as_engine.contracts.view import PlayView
from as_engine.service import game_service
from protocol_kit import actions, error_code, only, send

pytestmark = pytest.mark.phase(8)


async def test_runs_list_and_hello_see_the_run(svc, make_run):
    rid = make_run()
    runs = only(await send(svc, "runs_list"), "runs")["runs"]
    assert [r["run_id"] for r in runs] == [rid]
    assert (runs[0]["pc_name"], runs[0]["alive"], runs[0]["day"]) == ("Owen Marsh", True, 18)
    assert only(await send(svc, "hello"), "welcome")["has_runs"] is True


async def test_run_load_opens_the_play_screen(svc, make_run):
    """run_load -> run_loaded, view, story (10_UI §4): everything the Play screen needs."""
    rid = make_run()
    r = await send(svc, "run_load", run_id=rid)
    assert actions(r) == ["run_loaded", "view", "story"]
    loaded = only(r, "run_loaded")
    assert (loaded["run_id"], loaded["pc_name"], loaded["ironman"], loaded["sandbox"]) == (rid, "Owen Marsh", False, False)
    assert loaded["notices"] == [] and RunSettings.model_validate(loaded["settings"]) == svc.session.settings
    view = PlayView.model_validate(only(r, "view")["view"])
    assert view.run_id == rid and view.turn_index == 0 and view.location.place_name
    assert only(r, "story")["entries"] == []
    assert svc.session is not None and svc.last_view == view
    assert only(await send(svc, "get_state"), "state") == {"screen": "play", "run_id": rid, "busy": False}
    assert only(await send(svc, "hello"), "welcome")["screen"] == "play", "a reloaded page returns to the game"


async def test_view_get_and_story_get(svc, make_run):
    rid = make_run()
    await send(svc, "run_load", run_id=rid)
    v = only(await send(svc, "view_get"), "view")["view"]
    assert v["pc_name"] == "Owen Marsh" and v["alive"] is True
    assert only(await send(svc, "story_get"), "story") == {"entries": []}


async def test_nothing_loaded(svc):
    for action, fields in (("view_get", {}), ("story_get", {}), ("run_save", {"slot_name": "a"}),
                           ("run_close", {}), ("settings_get", {}), ("dev_get", {"what": "trace"})):
        r = await send(svc, action, **fields)
        assert only(r, "error") == {"code": "no_run", "message": game_service.NO_RUN, "recoverable": True}, action


async def test_a_missing_run_goes_home(svc):
    r = await send(svc, "run_load", run_id="nobody_1")
    assert actions(r) == ["error", "state"]
    assert error_code(r) == "not_found" and only(r, "state")["screen"] == "home"
    assert svc.session is None


async def test_save_close_and_load_the_save(svc, make_run, cfg):
    rid = make_run()
    await send(svc, "run_load", run_id=rid)
    saved = only(await send(svc, "run_save", slot_name="Before the fence"), "saved")
    assert saved == {"slot": "before_the_fence", "label": "Before the fence", "turn_index": 0}
    assert (Path(cfg.runs_dir) / rid / "saves" / "before_the_fence.sqlite").exists()
    r = await send(svc, "run_close")
    assert actions(r) == ["state", "runs"] and only(r, "state") == {"screen": "home", "run_id": None, "busy": False}
    assert svc.session is None
    r = await send(svc, "run_load", run_id=rid, save_slot="Before the fence")
    assert actions(r) == ["run_loaded", "view", "story"]


async def test_ironman_has_no_named_saves(svc, make_run):
    rid = make_run(settings=RunSettings(save_mode="ironman"))
    loaded = only(await send(svc, "run_load", run_id=rid), "run_loaded")
    assert loaded["ironman"] is True
    assert error_code(await send(svc, "run_save", slot_name="cheat death")) == "ironman"


async def test_delete(svc, make_run, cfg):
    """RUN-12: deleting is one step for the player — the open run is closed first — and the list
    updates (test_sessions.py has the rest)."""
    rid = make_run()
    await send(svc, "run_load", run_id=rid)
    r = await send(svc, "run_delete", run_id=rid)
    assert actions(r) == ["run_deleted", "runs"]
    assert only(r, "run_deleted") == {"run_id": rid} and only(r, "runs") == {"runs": []}
    assert svc.session is None and svc.last_view is None and svc.last_story is None
    assert not (Path(cfg.runs_dir) / rid).exists()
    assert error_code(await send(svc, "run_delete", run_id=rid)) == "not_found"


async def test_loading_another_run_closes_the_first(svc, make_run):
    first = make_run()
    second = make_run()
    assert first != second
    await send(svc, "run_load", run_id=first)
    store = svc.session.store
    await send(svc, "run_load", run_id=second)
    assert svc.session.run_id == second
    with pytest.raises(Exception):
        store.query_one("SELECT 1")     # the first run's store was closed
