"""Two-lane scheduler (P1 mechanics, P5 policy). docs/as/04_TURN_PIPELINE.md §Stage 4.

Concepts:
  Job(job_id, call_class, lane_pref: Lane|None, est_s, mandatory, request, output_model)
  LanePool: per-lane asyncio.Semaphore(max_concurrency); jobs for a lane run concurrently up to it.

run_jobs(client, jobs) -> dict[job_id, LMResponse]   (P1)
  * Jobs with lane_pref run on that lane. lane_pref None -> the lane with the smaller current
    queued estimate (ties -> B). If the preferred lane is down, the job moves to the other lane
    with thinking=False (DEGRADE-01). If both lanes are down, every job returns 'lane_error'.
  * Returns when all jobs finish; never raises for model errors.

plan_cognition(candidates, config, turn_depth, lanes_up) -> CognitionPlan   (P5)
  candidates: list of (actor_id, salience, mandatory: bool); config: EngineConfig (rules.scheduler
  S, lanes[*].max_concurrency); lanes_up: the lanes whose probe passed this turn.
  1. Order: mandatory candidates first, then the rest; each part by (salience desc, actor_id).
  Lanes are roles, not a pool (D-111): lane A is the Writer, lane B the Clerk, and a mind's call
  goes to the lane its regime names — it never spills onto the other lane to balance the load.
  2. HOT: when the hot lane (config.hot_cognition.lane; A by default) is up, the first
     min(S.max_hot[turn_depth], len) candidates of that order, each on that lane with est
     S.estimated_call_s['actor_cognition_hot'] — (D-175) stopping at the first that is not
     mandatory and whose salience is below S.hot_min_salience: a moment with nothing at stake for
     someone is decided on the fast lane, and the Writer keeps its time for the people something
     is happening to (and for the story). Hot lane down -> no HOT.
  3. WARM: the following candidates in order, each on the warm lane (config.regimes
     [ACTOR_COGNITION].lane; when that lane is down, the up lane, B first — DEGRADE-01), est
     S.estimated_call_s['actor_cognition_warm'], while the wave wall-clock estimate
     max(sum_A / conc_A, sum_B / conc_B) stays <= S.turn_budget_s[turn_depth]
     - S.reserve_narration_s. A mandatory candidate is placed even past the budget (overrun =
     True, note 'BUDGET_OVERRUN <actor_id>'); a non-mandatory candidate that would exceed it
     becomes COLD and so does every one after it.
  4. Everyone else COLD (no lane). No lane up -> everyone COLD, note 'NO_LANES'.
  est_wall_s = the final estimate; order = the actor ids in step 1's order (D-128: turn.cognition
  AMB-02 gives the room's lines to the COLD people in it). LOD never changes competence, knowledge or morality (LOD-01);
  it only changes who calls a model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from ..contracts.common import LOD, CallClass, Lane
from ..contracts.lanes import LMRequest, LMResponse
from .client import LaneClient


@dataclass
class Job:
    job_id: str
    call_class: CallClass
    request: LMRequest
    output_model: type[BaseModel] | None = None
    lane_pref: Lane | None = None
    est_s: float = 5.0
    mandatory: bool = False


@dataclass
class CognitionPlan:
    lod: dict[str, LOD] = field(default_factory=dict)
    lane: dict[str, Lane] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)   # D-128: step 1's order (mandatory first, salience desc)
    overrun: bool = False
    est_wall_s: float = 0.0
    notes: list[str] = field(default_factory=list)


async def run_jobs(client: LaneClient, jobs: list[Job]) -> dict[str, LMResponse]:
    import asyncio
    sems = {lane: asyncio.Semaphore(max(1, cfg.max_concurrency)) for lane, cfg in client.config.lanes.items()}
    queued = {Lane.A: 0.0, Lane.B: 0.0}
    planned = []
    for j in jobs:
        lane = j.lane_pref
        if lane is None:
            lane = Lane.A if queued[Lane.A] < queued[Lane.B] else Lane.B
        req = j.request.model_copy(update={"lane": lane})
        if client.is_down(lane):
            other = Lane.B if lane == Lane.A else Lane.A
            if not client.is_down(other):
                lane = other
                req = j.request.model_copy(update={"lane": other, "thinking": False})
        queued[lane] += j.est_s
        planned.append((j, req))

    async def one(j, req):
        async with sems[req.lane]:
            return j.job_id, await client.call(req, j.output_model)
    res = await asyncio.gather(*(one(j, r) for j, r in planned))
    return dict(res)


def plan_cognition(candidates: list[tuple[str, float, bool]], config: Any, turn_depth: str,
                   lanes_up: set[Lane]) -> CognitionPlan:
    from ..action._impl_p5b import plan_cognition as _p
    return _p(candidates, config, turn_depth, lanes_up)
