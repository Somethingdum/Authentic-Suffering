"""P10 fixtures (PROTECTED). A world generated once per test session on the fake model, copied for
every test that uses it; small helpers live in world_kit.py (import it from test modules).

The generated world: Owen Marsh, Established era, Normal, the smallest detail tier, seed 7. Nothing
in the tests depends on WHICH world seed 7 makes — only on what every generated world must be.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))  # so test modules can `import world_kit`

from as_engine.contracts.settings import EngineConfig, RunSettings  # noqa: E402
from as_engine.testing.fake_lm import FakeTransport  # noqa: E402

TESTS = Path(__file__).resolve().parents[2]
REPO_PACKS = TESTS.parent.parent / "as_content" / "packs"
FIXTURE_PACKS = TESTS / "fixtures" / "packs"

WORLD_PC = "core:pc/owen_marsh"
WORLD_SETTINGS = {"world_detail": "gotta_go_to_work_soon", "seed": 7, "era": "established", "difficulty": "normal"}


@dataclass
class MadeWorld:
    root: Path             # holds runs/ (the run folder and runs/_worlds/)
    run_id: str
    world_id: str
    report: object         # the WorldgenReport
    notices: list


@pytest.fixture(scope="session")
def made_world(tmp_path_factory) -> MadeWorld:
    """service.runs.create_run once for the whole session (P10)."""
    from as_engine.service import runs

    root = tmp_path_factory.mktemp("p10_world")
    cfg = EngineConfig(runs_dir=str(root / "runs"), content_dir=str(REPO_PACKS))
    s = asyncio.run(runs.create_run(cfg, WORLD_PC, RunSettings(**WORLD_SETTINGS), FakeTransport()))
    made = MadeWorld(root=root, run_id=s.run_id, world_id=s.store.meta("world_id"),
                     report=s.extras["worldgen_report"], notices=list(s.extras.get("notices", [])))
    s.store.close()
    return made


@pytest.fixture
def world_cfg(made_world, tmp_path) -> EngineConfig:
    """An EngineConfig whose runs_dir is a private copy of the generated world's runs folder."""
    shutil.copytree(made_world.root / "runs", tmp_path / "runs")
    return EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(REPO_PACKS))


@pytest.fixture
def gw(made_world, world_cfg):
    """The generated world, loaded (service.runs.load_run) on a fresh FakeTransport: a Session.
    ``gw.extras['fake']`` is the transport, for scripting model answers."""
    from as_engine.service import runs

    fake = FakeTransport()
    s = runs.load_run(world_cfg, made_world.run_id, fake)
    s.extras["fake"] = fake
    try:
        yield s
    finally:
        s.store.close()


@pytest.fixture
def run_cfg(tmp_path) -> EngineConfig:
    """An empty runs folder and the repository's packs, for tests that make their own runs."""
    return EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(REPO_PACKS))
