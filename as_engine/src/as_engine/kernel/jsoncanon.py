"""Canonical JSON (implemented; do not change — state hashes depend on it)."""

from __future__ import annotations

import json
from typing import Any


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, no whitespace, ensure_ascii=False, floats via repr.

    Pydantic models must be dumped with ``model_dump(mode="json")`` before calling this.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
