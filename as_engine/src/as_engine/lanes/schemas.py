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
                   subject_handles=()) -> dict   (Actor Spec §7; SCHEMA-04)
      to_lm_schema(ActorReplyV2), then:
        kind          enum ["decision"], plus "consultation" when consult_kinds is not empty;
        action        (nullable object) choice = {"type": "string", "enum": affordance_handles};
                      speech.to items = {"type": "string", "enum": entity_handles + ["everyone"]};
                      gesture, attention and inscription = {"type": "null"} (no packet offers
                      gestures, attention points or a writing attempt yet);
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
    raise NotImplementedError("P1")


def cognition_schema(affordance_handles: list[str], entity_handles: list[str], *,
                     consult_kinds: tuple[str, ...] | list[str] = (), families: tuple[str, ...] | list[str] = (),
                     subject_handles: tuple[str, ...] | list[str] = ()) -> dict[str, Any]:
    raise NotImplementedError("P1")


def intake_schema(affordance_handles: list[str]) -> dict[str, Any]:
    raise NotImplementedError("P1")


def writeback_schema(percept_handles: list[str], entity_handles: list[str], loop_handles: list[str]) -> dict[str, Any]:
    raise NotImplementedError("P1")
