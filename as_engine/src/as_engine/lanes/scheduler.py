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
  2. HOT: when lane A is up, the first min(S.max_hot[turn_depth], len) candidates of that order,
     each on lane A with est S.estimated_call_s['actor_cognition_hot'].
  3. WARM: the following candidates in order, each placed on the up lane with the smaller queued
     estimate so far (ties -> B), est S.estimated_call_s['actor_cognition_warm'], while the wave
     wall-clock estimate max(sum_A / conc_A, sum_B / conc_B) stays <= S.turn_budget_s[turn_depth]
     - S.reserve_narration_s. A mandatory candidate is placed even past the budget (overrun =
     True, note 'BUDGET_OVERRUN <actor_id>'); a non-mandatory candidate that would exceed it
     becomes COLD and so does every one after it.
  4. Everyone else COLD (no lane). No lane up -> everyone COLD, note 'NO_LANES'.
  est_wall_s = the final estimate. LOD never changes competence, knowledge or morality (LOD-01);
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
    overrun: bool = False
    est_wall_s: float = 0.0
    notes: list[str] = field(default_factory=list)


async def run_jobs(client: LaneClient, jobs: list[Job]) -> dict[str, LMResponse]:
    raise NotImplementedError("P1")


def plan_cognition(candidates: list[tuple[str, float, bool]], config: Any, turn_depth: str,
                   lanes_up: set[Lane]) -> CognitionPlan:
    raise NotImplementedError("P5")
