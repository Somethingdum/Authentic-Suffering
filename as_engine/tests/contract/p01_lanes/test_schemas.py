"""LM-Studio-safe schemas and dynamic enums (P1). Rules SCHEMA-01..03 (lanes/schemas.py)."""

from __future__ import annotations

import json

import pytest

from as_engine.contracts.common import CallClass
from as_engine.contracts.mind import CognitionOutput, WritebackOutput
from as_engine.lanes.schemas import OUTPUT_MODELS, cognition_schema, intake_schema, to_lm_schema, writeback_schema

pytestmark = pytest.mark.phase(1)


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


@pytest.mark.parametrize("model", sorted({m for m in OUTPUT_MODELS.values() if m is not None}, key=lambda m: m.__name__))
def test_lm_schema_is_flat_and_closed(model):
    """SCHEMA-01: no $ref/$defs, no title/default keys, every object closed."""
    sch = to_lm_schema(model)
    text = json.dumps(sch)
    assert "$ref" not in text and "$defs" not in text
    for node in _walk(sch):
        assert "title" not in node and "default" not in node
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False


def test_cognition_schema_enums():
    """SCHEMA-02: choice limited to offered handles; speech.to limited to entity handles + everyone."""
    sch = cognition_schema(["A1", "A2"], ["P1"])
    assert sch["properties"]["choice"]["enum"] == ["A1", "A2"]
    to = json.dumps(sch["properties"]["speech"])
    assert '"P1"' in to and '"everyone"' in to
    assert set(sch["required"]) >= {"choice", "goal", "private_reason"}


def test_intake_schema_enum_includes_none():
    assert intake_schema(["A1"])["properties"]["choice"]["enum"] == ["A1", "NONE"]


def test_writeback_schema_enums():
    """SCHEMA-02: because -> percept handles; about -> entities + self/place; loops closed when none."""
    sch = writeback_schema(["S1", "S2"], ["P1"], [])
    text = json.dumps(sch)
    assert '"S1"' in text and '"self"' in text and '"place"' in text
    assert sch["properties"]["closed_loops"]["maxItems"] == 0


def test_writeback_schema_for_a_mind_alone():
    """A mind with nobody in view can still write memories, but no relationship rows."""
    sch = writeback_schema(["S1"], [], ["L1"])
    assert sch["properties"]["relationships"]["maxItems"] == 0
    assert '"L1"' in json.dumps(sch["properties"]["closed_loops"])


def test_enum_replaces_string_limits():
    """SCHEMA-02: an enum-restricted string keeps no minLength/pattern (LM Studio rejects the mix)."""
    sch = cognition_schema(["A1"], ["P1"])
    assert "minLength" not in sch["properties"]["choice"] and "pattern" not in sch["properties"]["choice"]


def test_empty_handles_refused():
    """SCHEMA-03: an enum over nothing is a bug upstream, not a schema."""
    with pytest.raises(ValueError):
        cognition_schema([], ["P1"])
    with pytest.raises(ValueError):
        writeback_schema([], ["P1"], [])


def test_output_model_table_is_complete():
    assert set(OUTPUT_MODELS) == set(CallClass)
    assert OUTPUT_MODELS[CallClass.ACTOR_COGNITION] is CognitionOutput
    assert OUTPUT_MODELS[CallClass.WRITEBACK] is WritebackOutput
