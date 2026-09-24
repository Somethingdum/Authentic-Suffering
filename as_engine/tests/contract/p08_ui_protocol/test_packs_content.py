"""Your characters & world: the pack list and the validator (P8). Rules CNT-*, UI-CLARITY-06
(service/game_service.py: on_packs_list, on_content_validate).
"""

from __future__ import annotations

import shutil

import pytest

from as_engine.contracts.settings import EngineConfig
from as_engine.service import game_service
from as_engine.service.game_service import GameService
from conftest import REPO_PACKS
from protocol_kit import error_code, only, send

pytestmark = pytest.mark.phase(8)

PACK_YAML = """schema: as.pack.v1
id: my_content
name: My content
version: 0.1.0
description: Things I made.
depends_on: [core]
"""

BROKEN_ITEM = """schema: as.item.v1
id: bent_spoon
name: bent spoon
kind: tool
mass_g: nope
"""


@pytest.fixture
def packs(tmp_path):
    root = tmp_path / "packs"
    shutil.copytree(REPO_PACKS / "core", root / "core")
    return root


@pytest.fixture
def csvc(packs, tmp_path, gated, monkeypatch):
    monkeypatch.setattr(game_service, "_SERVICE", None)
    return GameService(EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(packs)), gated,
                       config_path=str(tmp_path / "as_config.yaml"))


async def test_the_core_pack_is_listed_and_clean(csvc):
    listed = only(await send(csvc, "packs_list"), "packs")["packs"]
    assert [p["pack_id"] for p in listed] == ["core"]
    core = listed[0]
    assert core["core"] is True and core["records"] > 100 and core["version"]
    report = only(await send(csvc, "content_validate", pack_id="core"), "content_report")
    assert report["ok"] is True and report["errors"] == []
    assert report["counts"]["item"] > 0 and report["counts"]["affordance"] > 0
    assert sum(report["counts"].values()) == core["records"]
    assert all(v > 0 for v in report["counts"].values())


async def test_a_broken_pack_is_reported_in_plain_words(csvc, packs):
    mine = packs / "my_content"
    (mine / "items").mkdir(parents=True)
    (mine / "pack.yaml").write_text(PACK_YAML, encoding="utf-8")
    (mine / "items" / "bent_spoon.yaml").write_text(BROKEN_ITEM, encoding="utf-8")
    listed = only(await send(csvc, "packs_list"), "packs")["packs"]
    assert [(p["pack_id"], p["core"]) for p in listed] == [("core", True), ("my_content", False)]
    assert listed[1]["records"] == 0, "the broken item is not loaded"
    report = only(await send(csvc, "content_validate", pack_id="my_content"), "content_report")
    assert report["ok"] is False and report["errors"]
    assert all(e.startswith("items/bent_spoon.yaml") for e in report["errors"]), report["errors"]
    assert report["counts"] == {}


async def test_an_unknown_pack(csvc):
    r = await send(csvc, "content_validate", pack_id="nope")
    assert error_code(r) == "not_found"
    assert only(r, "error")["message"] == game_service.PACK_NOT_FOUND.format(pack_id="nope")
