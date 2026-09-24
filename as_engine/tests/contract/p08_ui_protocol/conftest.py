"""P8 fixtures (PROTECTED): a GameService on the fake model, runs on disk, and a transport that can
hold a call open so a test can act while a turn is in the middle of a stage."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))  # so test modules can `import protocol_kit`

from as_engine.contracts.common import CallClass  # noqa: E402
from as_engine.contracts.settings import EngineConfig  # noqa: E402
from as_engine.service import game_service  # noqa: E402
from as_engine.testing.fake_lm import FakeTransport  # noqa: E402

TESTS = Path(__file__).resolve().parents[2]
SCENARIOS = TESTS / "fixtures" / "scenarios"
FIXTURE_PACKS = TESTS / "fixtures" / "packs"
REPO_PACKS = TESTS.parent.parent / "as_content" / "packs"
CORE = REPO_PACKS / "core"


class GatedTransport(FakeTransport):
    """The fake model, except that a call of a class in ``hold`` waits until ``release`` is set.
    ``reached`` is set when the first held call arrives."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.hold: set[CallClass] = set()
        self.reached = asyncio.Event()
        self.release = asyncio.Event()

    async def send(self, lane, request):
        if request.call_class in self.hold:
            self.reached.set()
            await self.release.wait()
        return await super().send(lane, request)


@pytest.fixture
def gated():
    return GatedTransport()


@pytest.fixture
def cfg(tmp_path):
    return EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(REPO_PACKS))


@pytest.fixture
def config_path(tmp_path):
    return tmp_path / "as_config.yaml"


@pytest.fixture
def svc(cfg, gated, config_path, monkeypatch):
    """A fresh GameService with a push collector: svc.pushed is every pushed message, in order."""
    monkeypatch.setattr(game_service, "_SERVICE", None)
    s = game_service.GameService(cfg, gated, config_path=str(config_path))
    s.pushed = []

    async def collect(msg):
        s.pushed.append(msg)
    s.collect = collect
    s.subscribe(collect)
    yield s
    if s.session is not None:
        s.session.store.close()


@pytest.fixture
def make_run(cfg, gated):
    """Creates the metal_fence run on disk (closed again) and returns its run_id."""
    from as_engine.service import runs

    def _make(name="metal_fence", **kw):
        s = runs.create_run_from_scenario(cfg, SCENARIOS / f"{name}.yaml", gated, packs_root=FIXTURE_PACKS,
                                          core_pack_dir=CORE, **kw)
        s.store.close()
        return s.run_id
    return _make
