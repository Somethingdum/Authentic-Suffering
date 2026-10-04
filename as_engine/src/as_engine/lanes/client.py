"""LaneClient (P1): one call = transport + parse + validate + call log. Rules LANE-01..08.

    client = LaneClient(config: EngineConfig, transport: Transport)
    resp = await client.call(request, output_model=None)

Behaviour:
  1. If the lane is marked down (``mark_down``) -> return parse_status 'lane_error' immediately.
  2. ``await transport.send(lane_cfg, request)`` with NO deadline (LANE-10, D-110): a call that is slow
     but moving is never cut off. LaneStalled (no progress for the lane's ``stall_window_s``) and any other
     LaneTimeout -> 'timeout' (the error says 'no progress for N s'; the lane is not marked down);
     LaneUnavailable -> 'lane_error' and the lane is marked down until ``health`` succeeds again.
     ``request.deadline_s`` is only the call's EXPECTED time: it sets the ``slow`` flag in the progress
     snapshot and nothing else. A cancelled call (the Stop button) closes its connection, which stops the model.
  3. ``strip_think`` the text; reasoning from the transport (if any) is kept in ``reasoning``.
  4. If ``output_model`` is given: extract_json -> None => 'grammar_fail';
     validate fails => 'schema_fail' (error set); success => parsed = instance.model_dump(mode='json').
     Empty visible text => 'empty'.
  5. ``raw`` is kept only when parse_status != 'ok'.
  6. Every call (any status) is appended to the call log via ``on_call`` callback if set:
     ``on_call(request, response)`` — the turn pipeline wires this to lanes.calllog.

Progress (LANE-11): ``client.live`` maps each call in flight (by ``id(request)``) to its latest snapshot
(lanes/progress.py: phase 'waiting'/'prefill'/'thinking'/'writing', elapsed_s, quiet_s, slow, the prompt
counters and the chars of reasoning and text so far), and ``client.on_progress(request, snapshot)``, when
set, is called as the transport reports it (about once a second), and once more as
``on_progress(request, None)`` when the call ends, whatever the outcome (D-114). Both are for display only.
The transport's one ``sink`` is a dispatcher every client shares (``LaneClient.dispatch``): each report goes
to the client that made that call, so several clients over one transport — the turn's, the quiet hours'
jobs', the bench's — each see only their own calls (D-114: a second client used to take the sink over).

Model-swap guard (LANE-05): ``check_models()`` lists models on each lane and raises ModelSwapped
if the configured model id is not present. The turn pipeline calls it before T0.

Ablation (LANE-09, P11; 08 §4 ablation duty): ``client.ablated`` is a set of CallClass (empty by
default). A call of an ablated class never reaches the transport: it returns parse_status
'cancelled' with error 'ablated' at once, logged through ``on_call`` like any other call, so every
caller takes the fallback path it already has for a call that did not come back
(tools/as/eval.py --ablate).
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
        self.ablated: set = set()
        self.on_progress: Callable[[LMRequest, dict | None], None] | None = None
        self.live: dict[int, dict] = {}
        if hasattr(transport, "sink"):
            transport.sink = LaneClient.dispatch

    _owners: dict[int, "LaneClient"] = {}       # calls in flight, any client: id(request) -> the client that sent it

    @staticmethod
    def dispatch(request: LMRequest, prog) -> None:
        """The transport's sink (LANE-11): hand a progress report to the client that made the call."""
        owner = LaneClient._owners.get(id(request))
        if owner is not None:
            owner._on_sink(request, prog)

    async def call(self, request: LMRequest, output_model: type[BaseModel] | None = None) -> LMResponse:
        import asyncio, time
        from .errors import LaneTimeout, LaneUnavailable
        from .parse import strip_think, extract_json, validate
        base = dict(call_class=request.call_class, lane=request.lane)
        if request.call_class in self.ablated:
            resp = LMResponse(**base, parse_status="cancelled", error="ablated")
            self._log(request, resp); return resp
        if self.is_down(request.lane):
            resp = LMResponse(**base, parse_status="lane_error", error="lane down")
            self._log(request, resp); return resp
        lane_cfg = self.config.lanes[request.lane]
        t0 = time.monotonic()
        LaneClient._owners[id(request)] = self
        try:
            got = await self.transport.send(lane_cfg, request)
        except (LaneTimeout, asyncio.TimeoutError) as e:
            resp = LMResponse(**base, parse_status="timeout", error=str(e) or "timeout")
            self._log(request, resp); return resp
        except LaneUnavailable as e:
            self.mark_down(request.lane)
            resp = LMResponse(**base, parse_status="lane_error", error=str(e))
            self._log(request, resp); return resp
        finally:
            self.live.pop(id(request), None)
            if LaneClient._owners.get(id(request)) is self:
                del LaneClient._owners[id(request)]
            if self.on_progress:
                self.on_progress(request, None)
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

    def _on_sink(self, request: LMRequest, prog) -> None:
        snap = prog.snapshot()
        self.live[id(request)] = snap
        if self.on_progress:
            self.on_progress(request, snap)

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
