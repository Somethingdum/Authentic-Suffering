"""Quiet-hours work between turns (P10): reflection and rumour retelling. Rules BG-01..06, INFO-06.
docs/as/05_ACTORS.md §9.2, 06_WORLD.md §6. People build their own inner lives while the player reads:
new goals and grudges, a lesson drawn, a plan changed; and the words a rumour will be passed on in.

BG-01 When: GameService starts a background task after it has pushed a turn's result and the lanes
  are idle, only when EngineConfig.background_cognition is true and the run has a PC who is alive.
  It runs jobs(session) one at a time (one model call in flight per lane: jobs of the two call classes
  go to their regimes' lanes, lane A jobs and lane B jobs may overlap). A turn_submit (or run_close,
  run_load, quit) CANCELS it first (task.cancel(), then awaited); a job whose answer arrived before
  the cancel is committed, a job cancelled mid-call leaves nothing behind. Jobs never run during a
  turn, so a turn's transaction never sees half of one.
BG-02 jobs(store, turn_index) -> list[Job]   (pure read; order is the run order)
  Reflection: actors (alive, not human-controlled, awareness not 'dead') whose lod was 'hot' or
  'warm' in any wave of the last 3 turns (turn_ledger stage 4 detail 'waves') and who have at least
  3 episodes newer than their newest REFLECTION event (all their episodes when they never reflected),
  sorted by (the newest of those episodes' at, descending; actor id) — at most 2 per idle period.
  Retelling: for each rumours row (by id) with created_at within SocietyRules.rumour_quiet_days, each
  holder (world.rumours.holders, confidence >= 1) who is not human-controlled, is alive, and has no
  entry in rumours.distortions yet, by holder id — at most 4 per idle period.
  Job(kind 'reflection' | 'retelling', subject_id (actor id / holder id), rumour_id (retelling),
  request_key = kind + ':' + subject + ':' + (rumour id or the newest episode id)).
BG-03 async run_job(session, job) -> JobResult   (no store writes; the model call only)
  (JobResult.answer: reflection {'output': ReflectionOutput, 'handles': packet.handles};
  retelling the RumourDistortion)
  reflection: packet = mind.packet.build_packet(tx in a read transaction, actor, LOD.WARM, its
  affordances, turn_index) and ReflectionContext(packet, recent_episodes = the summaries of those
  episodes in order); a REFLECTION call (lanes.repair.call_with_repair) answering
  ReflectionOutput. retelling: RumourContext(teller_identity = the holder's display name,
  claim_text = world.rumours.claim_sentence(claim, the holder's word for the subject),
  teller_confidence) and a RUMOUR_DISTORT call answering RumourDistortion. A failed call ->
  JobResult(failed=True) (committed as nothing).
BG-04 commit(tx, job, result, at, turn_index) -> list[Event]   (its own transaction, between turns)
  reflection: first REFLECTION {actor_id, request_key, output: the answer as JSON, handles: the
  packet's handle map} (writer
  'mind.mind', actor_id, origin 'sim') — the recorded external input replay re-applies; then, each
  citing it: goals_add (kinds 'promise_made' / 'promise_owed' dropped: nobody promises in their
  sleep) -> mind.mind.open_loop(kind, text, subject = the packet's entity for a 'P' handle else [],
  strength); loops_close for 'L' handles of still-open loops -> mind.mind.close_loop(status);
  lesson (cue tags filtered to the registry; none left -> dropped) -> mind.mind.learn; plan_goal
  given -> PLAN_CHANGE {actor_id, goal_text, steps} (writer 'mind.actor') upserting plans and
  actors.goal_text. Items that name handles the packet does not have are dropped (audit.log.repair
  'hallucinated_ref', stage None, rule 'BG-04').
  retelling: world.rumours.retell(tx, job.rumour_id, job.subject_id, result.answer, at, turn_index).
BG-05 Replay: service.replay.resimulate re-commits every REFLECTION and RUMOUR_DISTORTED event of the
  recorded run between the same turns as they were, from their payloads (no model call).
BG-06 Nothing here reads the truth layer; a reflection packet is the actor's own (Skull law).

class BackgroundRunner — GameService's handle on the task: start(session), cancel() (async; awaits
  the task), running (bool). Implemented by the builder with asyncio; the contract is BG-01.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.store import Store, Tx


@dataclass(frozen=True)
class Job:
    kind: Literal["reflection", "retelling"]
    subject_id: str
    rumour_id: str | None
    request_key: str


@dataclass(frozen=True)
class JobResult:
    job: Job
    answer: Any = None
    failed: bool = False


def jobs(store: "Store | Tx", turn_index: int) -> list[Job]:
    raise NotImplementedError("P10")


async def run_job(session, job: Job) -> JobResult:
    raise NotImplementedError("P10")


def commit(tx: "Tx", job: Job, result: JobResult, at: int, turn_index: int) -> list["Event"]:
    raise NotImplementedError("P10")


class BackgroundRunner:
    """BG-01. start(session) begins the job loop as an asyncio task; cancel() stops it and waits."""

    running: bool = False

    def start(self, session) -> None:
        raise NotImplementedError("P10")

    async def cancel(self) -> None:
        raise NotImplementedError("P10")
