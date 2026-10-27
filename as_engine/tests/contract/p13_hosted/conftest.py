"""P13 fixtures (PROTECTED): a hosted engine (as_engine.host, D-299) driven by a host the tests play.

The fake host answers the engine's model calls with the engine's own fake model (FakeTransport). The
fake model reads a request's structured context, which never crosses the bridge, so the kit keeps
each request the engine hands its transport by request hash and gives the fake that object — the
answer still travels the host's way (model.call / write -> a result dict -> the engine's client).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parent))  # so test modules can `import host_kit` (appended: never ahead of
                                                        # another phase's folder, whose tests import their own conftest)

import host_kit  # noqa: E402

from as_engine.contracts.settings import EngineConfig  # noqa: E402


@pytest.fixture
def hcfg() -> EngineConfig:
    return EngineConfig(content_dir=str(host_kit.REPO_PACKS))


@pytest.fixture
def world0(hcfg) -> bytes:
    """The metal_fence scenario at turn 0, as a world envelope."""
    return host_kit.scenario_world(hcfg)


@pytest.fixture
def host():
    """host() -> a fresh FakeHost (host_kit), may(step) True unless given."""
    return host_kit.FakeHost


@pytest.fixture
def hosted(hcfg):
    """hosted(fake_host) -> a HostService over that host, its requests kept for the fake model."""
    made = []

    def _make(h):
        s = host_kit.service(hcfg, h)
        made.append(s)
        return s
    yield _make
    for s in made:
        s._close()
