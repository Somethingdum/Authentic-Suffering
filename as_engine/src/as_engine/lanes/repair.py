"""Bounded repair (P1). Rule LANE-06: at most ONE repair call per failed structured call.

async def call_with_repair(client, request, output_model, *, repair_builder) -> tuple[LMResponse, bool]
  1. resp = await client.call(request, output_model)
  2. if resp.parse_status in ('grammar_fail', 'schema_fail'):
        rreq = repair_builder(request, resp)   # an INTENT_REPAIR-class request on lane B,
                                               # temperature 0.1, same json_schema, messages =
                                               # prompts/intent_repair.j2 with raw text + error
        resp2 = await client.call(rreq, output_model)
        return (resp2, True)
  3. return (resp, False)
Never salvages free text. The caller decides the fallback when the repaired response still fails
(Actors: turn.cognition HOLD-01 — a held turn, an accepted task going on, or nothing attempted;
narration: keep best passing draft).
"""

from __future__ import annotations

from typing import Callable

from pydantic import BaseModel

from ..contracts.lanes import LMRequest, LMResponse
from .client import LaneClient


async def call_with_repair(client: LaneClient, request: LMRequest, output_model: type[BaseModel],
                           *, repair_builder: Callable[[LMRequest, LMResponse], LMRequest]
                           ) -> tuple[LMResponse, bool]:
    raise NotImplementedError("P1")
