"""P12 fixtures (PROTECTED). The surfaces are proved on the P7 night at Delgado's (slice_kit.py) and
through the GameService as P8 drives it (protocol_kit.py); both kits are importable from here."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "p07_slice"))          # slice_kit
sys.path.insert(0, str(HERE.parent / "p08_ui_protocol"))    # protocol_kit

from as_engine.contracts.settings import EngineConfig  # noqa: E402
from as_engine.service import game_service  # noqa: E402

TESTS = HERE.parents[1]
SCENARIOS = TESTS / "fixtures" / "scenarios"
FIXTURE_PACKS = TESTS / "fixtures" / "packs"
REPO_PACKS = TESTS.parent.parent / "as_content" / "packs"
CORE = REPO_PACKS / "core"


@pytest.fixture
def cfg(tmp_path):
    return EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(REPO_PACKS))


@pytest.fixture
def svc(cfg, fake, tmp_path, monkeypatch):
    """A fresh GameService on the fake model; svc.pushed collects every pushed message."""
    monkeypatch.setattr(game_service, "_SERVICE", None)
    s = game_service.GameService(cfg, fake, config_path=str(tmp_path / "as_config.yaml"))
    s.pushed = []

    async def collect(msg):
        s.pushed.append(msg)
    s.subscribe(collect)
    yield s
    if s.session is not None:
        s.session.store.close()


@pytest.fixture
def make_run(cfg, fake):
    """Creates the metal_fence run on disk (closed again) and returns its run_id."""
    from as_engine.service import runs

    def _make(name="metal_fence"):
        s = runs.create_run_from_scenario(cfg, SCENARIOS / f"{name}.yaml", fake, packs_root=FIXTURE_PACKS, core_pack_dir=CORE)
        s.store.close()
        return s.run_id
    return _make


@pytest.fixture
def night(scenario):
    """The metal_fence world and a session on it, its config reading the repository's packs (where
    the cheat_ packs live)."""
    w = scenario("metal_fence")
    s = w.session()
    s.config = s.config.model_copy(update={"content_dir": str(REPO_PACKS)})
    return w, s
