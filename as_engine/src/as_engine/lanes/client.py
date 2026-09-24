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
        self._down: set = set()

    async def call(self, request: LMRequest, output_model: type[BaseModel] | None = None) -> LMResponse:
        import asyncio, time
        from .errors import LaneTimeout, LaneUnavailable
        from .parse import strip_think, extract_json, validate
        base = dict(call_class=request.call_class, lane=request.lane)
        if self.is_down(request.lane):
            resp = LMResponse(**base, parse_status="lane_error", error="lane down")
            self._log(request, resp); return resp
        lane_cfg = self.config.lanes[request.lane]
        t0 = time.monotonic()
        try:
            got = await asyncio.wait_for(self.transport.send(lane_cfg, request), request.deadline_s)
        except (LaneTimeout, asyncio.TimeoutError) as e:
            resp = LMResponse(**base, parse_status="timeout", error=str(e) or "timeout")
            self._log(request, resp); return resp
        except LaneUnavailable as e:
            self.mark_down(request.lane)
            resp = LMResponse(**base, parse_status="lane_error", error=str(e))
            self._log(request, resp); return resp
        visible, reasoning = strip_think(got.text)
        reasoning = got.reasoning or reasoning
        upd = dict(text=visible, reasoning=reasoning, latency_ms=got.latency_ms or int((time.monotonic()-t0)*1000))
        if not visible.strip():
            upd.update(parse_status="empty", raw=got.text)
        elif output_model is not None:
            data = extract_json(visible)
            if data is None:
                upd.update(parse_status="grammar_fail", raw=got.text, error="no JSON object")
            else:
                inst, err = validate(data, output_model)
                if inst is None:
                    upd.update(parse_status="schema_fail", raw=got.text, error=err)
                else:
                    upd.update(parse_status="ok", parsed=inst.model_dump(mode="json", by_alias=True))
        resp = got.model_copy(update=upd)
        self._log(request, resp)
        return resp

    def _log(self, q, r):
        if self.on_call:
            self.on_call(q, r)

    def mark_down(self, lane: Lane, down: bool = True) -> None:
        (self._down.add if down else self._down.discard)(lane)

    def is_down(self, lane: Lane) -> bool:
        return lane in self._down

    async def refresh_health(self) -> dict[Lane, bool]:
        out = {}
        for lane, cfg in self.config.lanes.items():
            ok = await self.transport.health(lane, cfg)
            out[lane] = ok
            self.mark_down(lane, not ok)
        return out

    async def check_models(self) -> None:
        from .errors import ModelSwapped
        for lane, cfg in self.config.lanes.items():
            if self.is_down(lane) or not cfg.model:
                continue
            models = await self.transport.list_models(lane, cfg)
            if cfg.model not in models:
                raise ModelSwapped(f"lane {lane.value}: configured model {cfg.model!r} is not loaded (found {models})")
