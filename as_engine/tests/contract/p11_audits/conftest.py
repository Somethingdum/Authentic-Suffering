"""P11 fixtures (PROTECTED). The audits are proved on the P7 night at Delgado's, so the P7 helpers
(slice_kit.py) are importable from here — and on a generated world (the P10 one: Owen Marsh,
Established era, Normal, the smallest detail tier, seed 7), made once per test session on the
fake model and copied for every test that uses it."""

from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "p07_slice"))  # so test modules can `import slice_kit`

from as_engine.contracts.settings import EngineConfig, RunSettings  # noqa: E402
from as_engine.testing.fake_lm import FakeTransport  # noqa: E402

REPO_PACKS = Path(__file__).resolve().parents[4] / "as_content" / "packs"
WORLD_SETTINGS = {"world_detail": "gotta_go_to_work_soon", "seed": 7, "era": "established", "difficulty": "normal"}


@pytest.fixture(scope="session")
def p11_world(tmp_path_factory):
    """(runs folder, run_id) of a world service.runs.create_run made once for the session."""
    from as_engine.service import runs
    root = tmp_path_factory.mktemp("p11_world")
    cfg = EngineConfig(runs_dir=str(root / "runs"), content_dir=str(REPO_PACKS))
    s = asyncio.run(runs.create_run(cfg, "core:pc/owen_marsh", RunSettings(**WORLD_SETTINGS), FakeTransport()))
    run_id = s.run_id
    s.store.close()
    return root / "runs", run_id


@pytest.fixture
def gen(p11_world, tmp_path):
    """The generated world loaded from a private copy (service.runs.load_run): a Session whose
    ``extras['fake']`` is its FakeTransport and ``extras['cfg']`` its EngineConfig."""
    from as_engine.service import runs
    src, run_id = p11_world
    shutil.copytree(src, tmp_path / "runs")
    cfg = EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(REPO_PACKS))
    fake = FakeTransport()
    s = runs.load_run(cfg, run_id, fake)
    s.extras["fake"], s.extras["cfg"] = fake, cfg
    try:
        yield s
    finally:
        s.store.close()
