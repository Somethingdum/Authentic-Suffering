"""Quiet-hours work between turns (P10): reflection and rumour retelling. Rules BG-01..06, INFO-06.
docs/as/05_ACTORS.md §9.2, 06_WORLD.md §6. People build their own inner lives while the player
reads: new goals and grudges, a lesson drawn, a plan changed; and the words a rumour will be passed
on in.

BG-01 When: GameService starts a background task after it has pushed a turn's result and the lanes
  are idle, only when EngineConfig.background_cognition is true and the run has a PC who is alive.
  It runs the jobs of jobs(store, turn_index) one at a time (never more than one model call in
  flight per lane; a builder may overlap a lane A job with a lane B job). A turn_submit (or
  run_close, run_load, run_new) CANCELS it first (task.cancel(), then awaited); a job whose answer
  arrived before the cancel is committed, a job cancelled mid-call leaves nothing behind. Jobs
  never run during a turn, so a turn's transaction never sees half of one.
BG-02 jobs(store, turn_index) -> list[Job]   (pure read; order is the run order)
  Eligible people: bodies.alive 1 and actors.controller not 'human'.
  Reflection: eligible actors whose lod was 'hot' or 'warm' in any wave of turns turn_index - 2 ..
  turn_index (turn_ledger stage 4 detail 'waves', each wave's 'lod' map) and who have at least 3
  NEW episodes — episodes whose turn_index is greater than that of their newest REFLECTION event
  (all their episodes when they never reflected) — sorted by (the newest new episode's at,
  descending; actor id); at most 2 per idle period.
  Retelling: for each rumours row (by rumour_id) with created_at >= kernel.clock.now -
  SocietyRules.rumour_quiet_days days, each holder (world.rumours.holders, confidence >= 1) who is
  eligible and has no entry in the row's distortions yet, by holder id; at most 4 per idle period
  (the first 4 in that order). Reflections come first in the list, then retellings.
  Job(kind 'reflection' | 'retelling', subject_id (actor id / holder id), rumour_id (retelling),
  request_key = kind + ':' + subject + ':' + (the rumour id, or the id of the newest new episode by
  (at, episode_id))).
BG-03 async run_job(session, job) -> JobResult   (no store writes; the model call only)
  (JobResult.answer: reflection {'output': ReflectionOutput, 'handles': packet.handles};
  retelling the RumourDistortion). T = world_clock.turn_index. Every call goes through its own
  LaneClient(session.config, session.client.transport, on_call = a collector), so the job's calls,
  and only its calls, end up in JobResult.calls as (request, response) pairs in call order.
  reflection: in one read transaction, at = kernel.clock.now, affordances =
  mind.affordance.enumerate_affordances(tx, actor, canon affordances, at, T), packet =
  mind.packet.build_packet(tx, actor, LOD.WARM, affordances, T, at), and the new episodes (BG-02;
  the newest 8 of them, oldest first). The call happens after that transaction has ended:
  ReflectionContext(packet, recent_episodes = those summaries); request =
  lanes.requests.build_request(config, REFLECTION, turn_index=T, actor_id, context=ctx,
  json_schema = lanes.schemas.to_lm_schema(ReflectionOutput), ctx=ctx); resp = await
  lanes.repair.call_with_repair(client, request, ReflectionOutput, repair_builder = a function
  returning lanes.requests.repair_request(config, the failed request, {raw: resp.text, error:
  resp.error or resp.parse_status}, packet, the same schema)).
  retelling: in one read transaction, p = the rumour's propositions row; RumourContext(
  teller_identity = the holder's actors.display_name, claim_text = world.rumours.claim_sentence(
  p.predicate, mind.perception.word_for(tx, holder, p.subject_id)), teller_confidence = the
  holder's confidence from world.rumours.holders); request = build_request(config,
  RUMOUR_DISTORT, turn_index=T, actor_id=holder, context=ctx, json_schema = to_lm_schema(
  RumourDistortion), ctx=ctx); resp = await client.call(request, RumourDistortion) (no repair).
  A final parse_status other than 'ok' -> JobResult(failed=True) (committed as nothing).
BG-04 commit(tx, job, result, at, turn_index) -> list[Event]   (its own transaction, between turns)
  First every pair of result.calls is recorded with lanes.calllog.record(tx, request, response)
  (turn_index T: every model call is logged, a failed one too). result.failed -> nothing else is
  written, []. Returns every event committed, in seq order.
  reflection: first REFLECTION {actor_id, request_key, output: the answer as JSON
  (model_dump(mode='json')), handles: the packet's handle map} (writer 'mind.mind', actor_id,
  origin 'sim', no writes) — the recorded external input replay re-applies; then, each with
  cause = that REFLECTION event's id, in this order:
    goals_add, in order: kinds 'promise_made' / 'promise_owed' are skipped (nobody promises in
    their sleep); subject None -> subject_ids []; a subject that is a 'P' handle of the packet ->
    [its entity id]; any other subject -> dropped; else mind.mind.open_loop(tx, actor, kind,
    text, subject_ids, strength, cause, at, turn_index).
    loops_close, in order: an 'L' handle of the packet whose loop is still 'open' ->
    mind.mind.close_loop(tx, loop id, status, cause, at, turn_index); else dropped.
    lesson: cue tags kept only when they are registry cue ids (canon cues' ids), in order; none
    left -> dropped; else mind.mind.learn(tx, actor, the kept tags, text, expectation '',
    outcome '', cause, at, turn_index).
    plan_goal given (non-empty) -> PLAN_CHANGE {actor_id, goal_text, steps} (writer 'mind.actor',
    origin 'sim', cause_event_id = cause) writing plans UPSERT {actor_id, goal_text, steps =
    plan_steps, standing_orders = the old row's ([] for a new row), updated_at = at} and actors
    UPDATE goal_text.
  A dropped item is logged with audit.log.repair(tx, 'hallucinated_ref', None, 'BG-04', {actor_id,
  item: 'goal' | 'loop_close' | 'lesson', index, ref: the offending handle or first tag},
  turn_index, at).
  retelling: world.rumours.retell(tx, job.rumour_id, job.subject_id, result.answer, at,
  turn_index) -> [its event] (or [] when it returns None).
BG-05 Replay: service.replay.resimulate re-commits every REFLECTION and RUMOUR_DISTORTED event of
  the recorded run between the same turns as they were, from their payloads (no model call; see
  service/replay.py).
BG-06 Nothing here reads the truth layer; a reflection packet is the actor's own (Skull law).

class BackgroundRunner — GameService's handle on the task: start(session), cancel() (async; awaits
  the task), running (bool). Implemented by the builder with asyncio; the contract is BG-01. The
  task: T = world_clock.turn_index; for each job of jobs(store, T) in order: result = await
  run_job(session, job) (an exception other than cancellation: logged, the job skipped), then in
  its own transaction commit(tx, job, result, kernel.clock.now(tx), T). start while running does
  nothing; cancel when nothing runs returns at once.
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
    calls: tuple = ()          # ((LMRequest, LMResponse), ...) in call order (BG-03)


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
