"""Shared fixtures for every test tier (PROTECTED — docs/as/12_TESTING.md §4).

Fixtures that need an unbuilt phase raise that phase's NotImplementedError at setup time; that is
expected before the phase and is how the test report tells you where you are.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
ENGINE_DIR = TESTS_DIR.parent
REPO_DIR = ENGINE_DIR.parent
sys.path.insert(0, str(TESTS_DIR))  # so contract tests can `import helpers`

from as_engine.contracts.events import Event, EventType, WriteRecord  # noqa: E402
from as_engine.contracts.settings import EngineConfig, RulesConfig  # noqa: E402
from as_engine.kernel.rng import Rng  # noqa: E402
from as_engine.testing.fake_lm import FakeTransport  # noqa: E402
from as_engine.testing.scenario import parse_scenario  # noqa: E402

SCENARIOS_DIR = TESTS_DIR / "fixtures" / "scenarios"
VECTORS_DIR = TESTS_DIR / "fixtures" / "vectors"
FIXTURE_PACKS_DIR = TESTS_DIR / "fixtures" / "packs"
CORE_PACK_DIR = REPO_DIR / "as_content" / "packs" / "core"
CHEAT_PACK_DIR = REPO_DIR / "as_content" / "packs" / "cheat_admin"


@pytest.fixture
def rules() -> RulesConfig:
    return RulesConfig()


@pytest.fixture
def config() -> EngineConfig:
    return EngineConfig()


@pytest.fixture
def store():
    from as_engine.kernel.store import Store

    s = Store.memory(run_id="t", seed=1, start_ms=0)
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def rng() -> Rng:
    return Rng(1)


@pytest.fixture
def fake() -> FakeTransport:
    return FakeTransport()


@pytest.fixture
def client(config, fake):
    from as_engine.lanes.client import LaneClient

    return LaneClient(config, fake)


@pytest.fixture(scope="session")
def core_pack_dir() -> Path:
    return CORE_PACK_DIR


@pytest.fixture(scope="session")
def cheat_pack_dir() -> Path:
    return CHEAT_PACK_DIR


@pytest.fixture(scope="session")
def fixture_packs() -> Path:
    return FIXTURE_PACKS_DIR


@pytest.fixture(scope="session")
def canon():
    """The compiled core pack (P2+). Session-scoped; any error-severity issue fails loudly."""
    from as_engine.content.pack import load_canon

    c, issues = load_canon([CORE_PACK_DIR])
    errors = [i for i in issues if i.severity == "error"]
    assert not errors, "core pack has content errors:\n" + "\n".join(f"{i.code} {i.file}: {i.message}" for i in errors)
    return c


@pytest.fixture
def spec_of():
    """spec_of('metal_fence') -> validated ScenarioSpec (works before P2)."""

    def _spec(name: str):
        return parse_scenario(SCENARIOS_DIR / f"{name}.yaml")

    return _spec


@pytest.fixture
def scenario(fake):
    """scenario('metal_fence', rules=None) -> ScenarioWorld loaded with ``fake`` as transport (P2+)."""
    from as_engine.testing.scenario import load_scenario

    worlds = []

    def _load(name: str, *, rules: RulesConfig | None = None):
        w = load_scenario(SCENARIOS_DIR / f"{name}.yaml", packs_root=FIXTURE_PACKS_DIR,
                          core_pack_dir=CORE_PACK_DIR, rules=rules, transport=fake)
        worlds.append(w)
        return w

    yield _load
    for w in worlds:
        try:
            w.store.close()
        except Exception:  # noqa: BLE001 — closing twice is fine
            pass


@pytest.fixture(scope="session")
def vectors():
    """vectors('rng') -> parsed JSON from tests/fixtures/vectors/rng.json."""

    def _vec(name: str):
        return json.loads((VECTORS_DIR / f"{name}.json").read_text(encoding="utf-8"))

    return _vec


@pytest.fixture
def make_event():
    """make_event(type=..., writer=..., writes=[...], at=0, turn_index=0, **fields) -> Event.

    Defaults build a valid no-write OVERRIDE event from 'audit'. ``writes`` accepts WriteRecord
    objects or plain dicts."""

    def _make(type: EventType = EventType.OVERRIDE, writer: str = "audit", writes=None, at: int = 0,
              turn_index: int = 0, **fields) -> Event:
        ws = [w if isinstance(w, WriteRecord) else WriteRecord(**w) for w in (writes or [])]
        return Event(type=type, writer=writer, writes=ws, at=at, turn_index=turn_index, **fields)

    return _make
