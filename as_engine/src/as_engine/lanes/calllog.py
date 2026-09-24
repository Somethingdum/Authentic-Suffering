"""Call log (P1): every LM call is recorded in ``lm_calls`` (bookkeeping, owner 'lanes') with the
full response text so ReplayTransport can reproduce a turn byte for byte (DET-03).

record(tx, request, response) -> seq
  Written with tx.bookkeep('lanes', 'lm_calls', WriteOp.INSERT, {}, {...}).
  turn_index = request.turn_index, or 0 for calls outside a turn (worldgen, probes; INTAKE and
  SAY_MY_WAY run inside the turn and carry its index).
  seq = count of calls already recorded for that turn_index + 1.
  request_hash = sha256(canonical_json(request.model_dump(mode='json', exclude={'context','seq'}))).
  response_text = response.raw when it is set (a failed parse keeps the body it failed on), else
  response.text — so a replayed call fails or succeeds exactly as the original did.
  status = response.parse_status.

request_hash(request) -> str   (implemented below; the one hash every caller uses)

ReplayTransport(store): ``send`` returns the recorded answer of the FIRST row of lm_calls with the
request's turn_index (0 when None) and the same request_hash that this transport has not replayed
yet (rows in seq order); each row replays once. Concurrent calls finish in any order, so a call is
found by what was asked, not by position (P7). No such row -> ReplayMismatch (the simulation
diverged before this call). A row recorded with status 'timeout' raises LaneTimeout and one with
'lane_error' raises LaneUnavailable (a replayed failure fails the same way); any other row returns
LMResponse(call_class, lane, text = response_text, prompt_tokens, completion_tokens, latency_ms,
model 'replay') — the client parses it again exactly as it did the first time. list_models
returns [lane.model]; health is always True.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..contracts.common import Lane
from ..contracts.lanes import LMRequest, LMResponse
from ..contracts.settings import LaneConfig
from ..kernel.errors import ASError

if TYPE_CHECKING:
    from ..kernel.store import Store, Tx


class ReplayMismatch(ASError):
    rule = "DET-03"


def request_hash(request: LMRequest) -> str:
    """sha256 hex of canonical_json(request.model_dump(mode='json', exclude={'context', 'seq'}))."""
    import hashlib

    from ..kernel.jsoncanon import canonical_json
    return hashlib.sha256(canonical_json(request.model_dump(mode="json", exclude={"context", "seq"})).encode("utf-8")).hexdigest()


def record(tx: "Tx", request: LMRequest, response: LMResponse) -> int:
    raise NotImplementedError("P1")


class ReplayTransport:
    def __init__(self, store: "Store"):
        raise NotImplementedError("P1")

    async def send(self, lane: LaneConfig, request: LMRequest) -> LMResponse:
        raise NotImplementedError("P1")

    async def list_models(self, lane_id: Lane, lane: LaneConfig) -> list[str]:
        raise NotImplementedError("P1")

    async def health(self, lane_id: Lane, lane: LaneConfig) -> bool:
        raise NotImplementedError("P1")
