"""LM-Studio-safe schemas and dynamic enums (P1). Rules SCHEMA-01..04 (lanes/schemas.py)."""

from __future__ import annotations

import json

import pytest

from as_engine.contracts.common import CallClass
from as_engine.contracts.mind import ActorReplyV2, WritebackOutput
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


def _branch(sch):
    """The non-null branch of a nullable schema node."""
    return next(x for x in sch["anyOf"] if x.get("type") != "null") if "anyOf" in sch else sch


def test_cognition_schema_enums():
    """SCHEMA-02 (ActorReplyV2, Actor Spec §7): the decision's choice is limited to offered handles;
    speech.to to entity handles + everyone; without consult kinds the answer can only be a decision."""
    sch = cognition_schema(["A1", "A2"], ["P1"])
    assert sch["properties"]["kind"]["enum"] == ["decision"]
    assert sch["properties"]["consultation"] == {"type": "null"}
    act = _branch(sch["properties"]["action"])
    assert act["properties"]["choice"]["enum"] == ["A1", "A2"]
    to = json.dumps(act["properties"]["speech"])
    assert '"P1"' in to and '"everyone"' in to
    assert set(act["required"]) >= {"choice", "goal"}
    assert sch["required"] == ["kind"]


def test_a_schema_offers_only_what_the_engine_can_do():
    """SCHEMA-04: gestures, attention points and writing stay null-only (no packet offers them yet);
    a consultation appears only where the packet offers one, its kinds, families and subjects as
    enums — never an enum over nothing."""
    sch = cognition_schema(["A1"], ["P1"], consult_kinds=["recall", "more_actions"], families=["movement", "access"],
                           subject_handles=["P1", "S1"])
    assert sch["properties"]["kind"]["enum"] == ["decision", "consultation"]
    act = _branch(sch["properties"]["action"])
    for k in ("gesture", "attention", "inscription"):
        assert act["properties"][k] == {"type": "null"}, k
    c = _branch(sch["properties"]["consultation"])
    assert c["properties"]["kind"]["enum"] == ["recall", "more_actions"]
    assert _branch(c["properties"]["family"])["enum"] == ["movement", "access"]
    assert c["properties"]["template"] == {"type": "null"}
    assert c["properties"]["subjects"]["items"]["enum"] == ["P1", "S1"]
    alone = _branch(cognition_schema(["A1"], [], consult_kinds=["recall"])["properties"]["consultation"])
    assert alone["properties"]["family"] == {"type": "null"} and alone["properties"]["subjects"]["maxItems"] == 0
    for node in _walk(sch):
        assert node.get("enum", ["x"]) != [], "an enum over nothing"


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
    choice = _branch(cognition_schema(["A1"], ["P1"])["properties"]["action"])["properties"]["choice"]
    assert "minLength" not in choice and "pattern" not in choice


def test_empty_handles_refused():
    """SCHEMA-03: an enum over nothing is a bug upstream, not a schema."""
    with pytest.raises(ValueError):
        cognition_schema([], ["P1"])
    with pytest.raises(ValueError):
        writeback_schema([], ["P1"], [])


def test_output_model_table_is_complete():
    assert set(OUTPUT_MODELS) == set(CallClass)
    for cc in (CallClass.ACTOR_COGNITION, CallClass.ACTOR_REACTION, CallClass.INTENT_REPAIR):
        assert OUTPUT_MODELS[cc] is ActorReplyV2, cc
    assert OUTPUT_MODELS[CallClass.WRITEBACK] is WritebackOutput
