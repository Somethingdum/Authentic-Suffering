"""The Play UI's test fixtures are real protocol messages (P8). Rules PROTO-01, UI-CLARITY-02.

talemate_frontend/src/play/__tests__/fixtures/*.json feed the vitest specs. Each one must be a message
this engine could send, so the UI is tested against the protocol, not against a guess of it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from as_engine.contracts.protocol import OUT_MODELS

pytestmark = pytest.mark.phase(8)

FIXTURES = Path(__file__).resolve().parents[4] / "talemate_frontend" / "src" / "play" / "__tests__" / "fixtures"
INTERNAL_ID = re.compile(r"\b(act|plc|anc|prt|itm|evt|clm|prp|pct)_\d{6}\b")


def files():
    return sorted(FIXTURES.glob("*.json"))


def test_the_fixtures_are_there():
    assert len(files()) >= 20, f"expected the vitest fixtures in {FIXTURES}"


@pytest.mark.parametrize("path", files(), ids=lambda p: p.stem)
def test_each_fixture_is_a_valid_message(path):
    msg = json.loads(path.read_text(encoding="utf-8"))
    assert set(msg) == {"type", "action", "data"} and msg["type"] == "as_game"
    model = OUT_MODELS[msg["action"]]
    assert model is not None, f"{path.name}: {msg['action']} has no model yet"
    model.model_validate(msg["data"])
    if msg["action"] not in ("dev_data",):
        assert not INTERNAL_ID.search(json.dumps(msg)), f"{path.name}: an internal id in a player-facing message"
