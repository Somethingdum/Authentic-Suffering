"""JSON schemas for constrained decoding (P1). Rules SCHEMA-01..04.

OUTPUT_MODELS maps each CallClass to its pydantic output model, or None for plain-text calls.

LM-Studio-safe schema (SCHEMA-01): ``to_lm_schema(model)`` returns
``model.model_json_schema()`` post-processed so that:
  * every "$ref" is inlined from "$defs" (recursively) and "$defs" is removed;
  * "title" keys are removed everywhere; "default" keys are removed everywhere;
  * every object gets "additionalProperties": false;
  * "required" lists every property that has no default in the model (pydantic already does this);
  * "anyOf": [X, {"type": "null"}] is kept as-is (nullable).

Dynamic enums (SCHEMA-02):
  cognition_schema(affordance_handles, entity_handles, *, consult_kinds=(), families=(),
                   subject_handles=(), gesture_handles=(), attention_handles=()) -> dict
                   (Actor Spec §7; SCHEMA-04)
      to_lm_schema(ActorReplyV2), then:
        kind          enum ["decision"], plus "consultation" when consult_kinds is not empty;
        action        (nullable object) choice = {"type": "string", "enum": affordance_handles};
                      speech.to items = {"type": "string", "enum": entity_handles + ["everyone"]};
                      gesture = {"anyOf": [{"type": "string", "enum": gesture_handles},
                      {"type": "null"}]} when gesture_handles is not empty, else {"type": "null"};
                      attention the same with attention_handles (B4: the packet's G# and F#
                      handles); inscription = {"type": "null"} (no packet offers a writing
                      attempt yet);
        consultation  {"type": "null"} when consult_kinds is empty; else nullable, with kind =
                      {"type": "string", "enum": consult_kinds}; family = the enum of families
                      (nullable), or {"type": "null"} when families is empty; template =
                      {"type": "null"} (no templates are offered yet); subjects items = the enum
                      of subject_handles (the packet's P# and S# handles), or "maxItems": 0 when
                      there are none.
      A reaction passes no consult_kinds: its answer can only be a decision.
  intake_schema(affordance_handles): IntakeOutput with choice enum = affordance_handles + ["NONE"].
  writeback_schema(percept_handles, entity_handles, loop_handles): every "because" field
      (string or list items) restricted to percept_handles; "about" to entity_handles + ["self","place"];
      "with" to entity_handles; LoopClose.loop to loop_handles. When loop_handles is empty,
      closed_loops gets "maxItems": 0; when entity_handles is empty (the mind was alone),
      relationships gets "maxItems": 0 — an enum over nothing is never emitted.
  Replacing a string field with an enum drops its minLength/maxLength/pattern; a list field keeps
  its minItems/maxItems and gets items = {"type": "string", "enum": [...]}; a nullable field
  (anyOf [X, null]) gets the enum on X and keeps the null branch.
SCHEMA-03: affordance_handles (cognition, intake) and percept_handles (writeback) must be
non-empty — empty -> ValueError, because the packet builder should never offer a mind nothing to
choose or nothing to cite (the WAIT affordance and the actor's own-state percept always exist).
SCHEMA-04: a schema offers only what the engine can do: a field whose handles or attempt the
packet does not offer is null-only, never an enum over nothing and never a free string.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from ..contracts.common import CallClass
from ..contracts.mind import (
    ActorReplyV2,
    CascadeSuggestion,
    IntakeOutput,
    PortrayalVerdict,
    ReflectionOutput,
    RumourDistortion,
    SayMyWayOutput,
    WritebackOutput,
)
from ..contracts.narration import RenderLintJudgement

OUTPUT_MODELS: dict[CallClass, type[BaseModel] | None] = {
    CallClass.INTAKE: IntakeOutput,
    CallClass.ACTOR_COGNITION: ActorReplyV2,
    CallClass.ACTOR_REACTION: ActorReplyV2,
    CallClass.INTENT_REPAIR: ActorReplyV2,
    CallClass.WRITEBACK: WritebackOutput,
    CallClass.PORTRAYAL_AUDIT: PortrayalVerdict,
    CallClass.NARRATION: None,
    CallClass.RENDER_LINT: RenderLintJudgement,
    CallClass.RUMOUR_DISTORT: RumourDistortion,
    CallClass.CASCADE_ADVISORY: CascadeSuggestion,
    CallClass.GUIDE: None,
    CallClass.REFLECTION: ReflectionOutput,
    CallClass.SCENE_SUMMARY: None,
    CallClass.RECAP: None,
    CallClass.SAY_MY_WAY: SayMyWayOutput,
    CallClass.WORLDGEN_HISTORY: None,  # model set by world.worldgen per stage
    CallClass.WORLDGEN_ACTOR: None,
    CallClass.WORLDGEN_OPENING: None,
    CallClass.DOSSIER_INTAKE: None,
    CallClass.PC_QUICKMAKE: None,
    CallClass.CHEAT_PERSONA: None,
    CallClass.PROBE: None,
}


def to_lm_schema(model: type[BaseModel]) -> dict[str, Any]:
    from ._impl_schemas import _inline, _close
    raw = model.model_json_schema()
    defs = raw.get("$defs", {})
    return _close(_inline(raw, defs))


def _set_enum_everywhere(node, key, enum):
    """Set enum on property `key` wherever it appears (string or array of strings)."""
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict) and key in props:
            props[key] = _enumify(props[key], enum)
        for k, v in node.items():
            _set_enum_everywhere(v, key, enum)
    elif isinstance(node, list):
        for v in node:
            _set_enum_everywhere(v, key, enum)


def _enumify(sch, enum):
    if "anyOf" in sch:
        return {"anyOf": [_enumify(s, enum) if s.get("type") != "null" else s for s in sch["anyOf"]]}
    if sch.get("type") == "array":
        out = dict(sch); out["items"] = {"type": "string", "enum": list(enum)}; return out
    out = {k: v for k, v in sch.items() if k not in ("minLength", "maxLength", "pattern")}
    out["type"] = "string"; out["enum"] = list(enum); return out


def _branch(sch):
    """The non-null branch of a nullable schema (the node itself when it is not nullable)."""
    if "anyOf" in sch:
        return next(x for x in sch["anyOf"] if x.get("type") != "null")
    return sch


def cognition_schema(affordance_handles: list[str], entity_handles: list[str], *,
                     consult_kinds: tuple[str, ...] | list[str] = (), families: tuple[str, ...] | list[str] = (),
                     subject_handles: tuple[str, ...] | list[str] = (), gesture_handles: tuple[str, ...] | list[str] = (),
                     attention_handles: tuple[str, ...] | list[str] = ()) -> dict[str, Any]:
    if not affordance_handles:
        raise ValueError("SCHEMA-03: no affordance handles")
    sch = to_lm_schema(ActorReplyV2)
    props = sch["properties"]
    props["kind"] = {"type": "string", "enum": ["decision"] + (["consultation"] if consult_kinds else [])}
    act = _branch(props["action"])
    ap = act["properties"]
    ap["choice"] = {"type": "string", "enum": list(affordance_handles)}
    sp = _branch(ap["speech"])
    to = dict(sp["properties"]["to"])
    to["items"] = {"type": "string", "enum": list(entity_handles) + ["everyone"]}
    sp["properties"]["to"] = to
    for k in ("gesture", "attention", "inscription"):
        ap[k] = {"type": "null"}                       # SCHEMA-04: nothing of the kind is offered yet
    if not consult_kinds:
        props["consultation"] = {"type": "null"}
    else:
        cp = _branch(props["consultation"])["properties"]
        cp["kind"] = {"type": "string", "enum": list(consult_kinds)}
        cp["family"] = ({"anyOf": [{"type": "string", "enum": list(families)}, {"type": "null"}]} if families
                        else {"type": "null"})
        cp["template"] = {"type": "null"}
        subj = dict(cp["subjects"])
        if subject_handles:
            subj["items"] = {"type": "string", "enum": list(subject_handles)}
        else:
            subj["maxItems"] = 0
        cp["subjects"] = subj
    return sch


def intake_schema(affordance_handles: list[str]) -> dict[str, Any]:
    if not affordance_handles:
        raise ValueError("SCHEMA-03")
    sch = to_lm_schema(IntakeOutput)
    sch["properties"]["choice"] = {"type": "string", "enum": list(affordance_handles) + ["NONE"]}
    return sch


def writeback_schema(percept_handles: list[str], entity_handles: list[str], loop_handles: list[str]) -> dict[str, Any]:
    if not percept_handles:
        raise ValueError("SCHEMA-03")
    sch = to_lm_schema(WritebackOutput)
    _set_enum_everywhere(sch, "because", percept_handles)
    _set_enum_everywhere(sch, "about", list(entity_handles) + ["self", "place"])
    if entity_handles:
        _set_enum_everywhere(sch, "with", list(entity_handles))
    else:
        sch["properties"]["relationships"]["maxItems"] = 0
    if loop_handles:
        _set_enum_everywhere(sch["properties"]["closed_loops"], "loop", loop_handles)
    else:
        sch["properties"]["closed_loops"]["maxItems"] = 0
    return sch
