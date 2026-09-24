"""P7 fixtures (PROTECTED). The helpers live in slice_kit.py (import it from test modules)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))  # so test modules can `import slice_kit`

from slice_kit import play, script_night_at_delgados  # noqa: E402


@pytest.fixture
def metal_turn(scenario, fake):
    """metal_fence after the scripted anchor turn: SimpleNamespace(w, s, out, fake, t0)."""
    w = scenario("metal_fence")
    t0 = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    script_night_at_delgados(w, fake)
    s = w.session()
    out = play(s, "do", "I watch the front window and keep quiet.")
    return SimpleNamespace(w=w, s=s, out=out, fake=fake, t0=t0)
