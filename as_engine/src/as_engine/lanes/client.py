"""LaneClient (P1): one call = transport + parse + validate + call log. Rules LANE-01..08.

    client = LaneClient(config: EngineConfig, transport: Transport)
    resp = await client.call(request, output_model=None)

Behaviour:
  1. If the lane is marked down (``mark_down``) -> return parse_status 'lane_error' immediately.
  2. ``await asyncio.wait_for(transport.send(lane_cfg, request), request.deadline_s)``;
     LaneTimeout / asyncio.TimeoutError -> 'timeout'; LaneUnavailable -> 'lane_error' and the lane
     is marked down until ``health`` succeeds again.
  3. ``strip_think`` the text; reasoning from the transport (if any) is kept in ``reasoning``.
  4. If ``output_model`` is given: extract_json -> None => 'grammar_fail';
     validate fails => 'schema_fail' (error set); success => parsed = instance.model_dump(mode='json').
     Empty visible text => 'empty'.
  5. ``raw`` is kept only when parse_status != 'ok'.
  6. Every call (any status) is appended to the call log via ``on_call`` callback if set:
     ``on_call(request, response)`` — the turn pipeline wires this to lanes.calllog.

Model-swap guard (LANE-05): ``check_models()`` lists models on each lane and raises ModelSwapped
if the configured model id is not present. The turn pipeline calls it before T0.
"""

from __future__ import annotations

from typing import Callable

from pydantic import BaseModel

from ..contracts.common import Lane
from ..contracts.lanes import LMRequest, LMResponse
from ..contracts.settings import EngineConfig
from .transport import Transport


class LaneClient:
    def __init__(self, config: EngineConfig, transport: Transport,
                 on_call: Callable[[LMRequest, LMResponse], None] | None = None):
        self.config = config
        self.transport = transport
        self.on_call = on_call

    async def call(self, request: LMRequest, output_model: type[BaseModel] | None = None) -> LMResponse:
        raise NotImplementedError("P1")

    def mark_down(self, lane: Lane, down: bool = True) -> None:
        raise NotImplementedError("P1")

    def is_down(self, lane: Lane) -> bool:
        raise NotImplementedError("P1")

    async def refresh_health(self) -> dict[Lane, bool]:
        raise NotImplementedError("P1")

    async def check_models(self) -> None:
        raise NotImplementedError("P1")
