"""P9 fixtures (PROTECTED). The helpers live in society_kit.py (import it from test modules)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))  # so test modules can `import society_kit`


@pytest.fixture
def settle(scenario):
    """pump_settlement, freshly loaded (day 1100, 05:00; everyone asleep; stores for 3.1 days)."""
    return scenario("pump_settlement")
