"""Quiet-hours work between turns (P10): reflection and rumour retelling. Rules BG-01..07, INFO-06.
docs/as/05_ACTORS.md §9.2, 06_WORLD.md §6. People build their own inner lives between moments:
new goals and grudges, a lesson drawn, a plan changed; and the words a rumour will be passed on in.

BG-07 (Actor Spec AC12, fidelity C07) Simulated time decides, never the player's reading speed.
  Which jobs a turn boundary has is a function of the world as the turn left it (BG-02); the time
  the player spends reading and typing only lets their model calls happen early. Every job of a
  boundary is committed (or has failed) before the next turn begins, so a player who answers at
  once and one who waits an hour get the same people thinking about the same things.
BG-01 When: after a turn's result has been pushed, when EngineConfig.background_cognition is true
  and the PC is alive, GameService starts the runner (BackgroundRunner.start). It runs the jobs of
  pending(store, T) (T = world_clock.turn_index) in order, one at a time — run_job, then commit
  in its own transaction — while the player reads (a builder may overlap a lane A job with a lane
  B job; never more than one model call in flight per lane). Before the next turn begins, the turn
  task awaits catch_up(session, progress) first: a running task is awaited (never cancelled),
  then every job of pending(store, T) the runner has not tried at this boundary is run and
  committed the same way, in order. run_close, run_load and run_new cancel the runner instead
  (cancel(): task.cancel(), then awaited): a job whose answer arrived before the cancel is
  committed, a job cancelled mid-call leaves nothing behind, and the run's next catch_up (the
  next turn, after a load) finishes the boundary's remaining jobs. Jobs never run during a turn,
  so a turn's transaction never sees half of one.
BG-02 jobs(store, turn_index) -> list[Job]   (pure read; order is the run order)
  The boundary's plan, read from the world as turn T = turn_index left it: every REFLECTION and
  RUMOUR_DISTORTED event of turn T (the boundary's own commits) is ignored, so the list is the
  same before, while and after the boundary's jobs are committed.
  R = RulesConfig.background (BackgroundRules). Eligible people: bodies.alive 1 and
  actors.controller not 'human'.
  Reflection (AC12: after a material experience or a night's sleep, once per eligibility key),
  for each eligible actor holding an episode: prev = the actor's newest REFLECTION event (by seq)
  of a turn before T, or none. NEW episodes = the actor's episodes (holder_id) with quarantined 0
  (Actor v2 B5b, MEM-18: a memory naming someone they never learned the name of is never thought
  over) whose turn_index is greater than prev's turn_index (all of them when there is no prev), by
  (at, episode_id). The
  actor reflects when
    material: a new episode has salience >= R.material_salience or anchor 1 -> eligibility key
      'm:' + the episode_id of the newest such episode (by (at, episode_id)); else
    rest: there are at least R.rest_min_episodes new episodes, and needs.last_sleep_ms is later
      than the oldest new episode's at and, when there is a prev, than prev's at — a night's
      sleep (society.routine's waking refreshes fatigue) since the new experiences began ->
      key 's:' + str(needs.last_sleep_ms).
  Reflecting actors are sorted by (the newest new episode's at, descending; actor id); at most
  R.max_reflections.
  Retelling: for each rumours row (by rumour_id) with created_at >= kernel.clock.now -
  SocietyRules.rumour_quiet_days days, each holder (world.rumours.holders, confidence >= 1) who
  is eligible and has no entry in the row's distortions — an entry whose RUMOUR_DISTORTED event
  (rumour_id, holder_id) is of turn T does not count — by holder id; at most R.max_retellings (the
  first in that order). Reflections come first in the list, then retellings.
  Job(kind 'reflection' | 'retelling', subject_id (actor id / holder id), rumour_id (retelling),
  request_key = 'reflection:' + actor + ':' + the eligibility key, or 'retelling:' + holder +
  ':' + rumour id).
pending(store, turn_index) -> list[Job]: jobs(store, turn_index) without the jobs already
  committed: a reflection whose request_key is the payload.request_key of a REFLECTION event of
  turn T, a retelling with a RUMOUR_DISTORTED event of turn T for its (rumour_id, holder_id).
BG-03 async run_job(session, job) -> JobResult   (no store writes; the model call only)
  (JobResult.answer: reflection {'output': ReflectionOutput, 'handles': packet.handles};
  retelling the RumourDistortion). T = world_clock.turn_index. Every call goes through its own
  LaneClient(session.config, session.client.transport, on_call = a collector), so the job's calls,
  and only its calls, end up in JobResult.calls as (request, response) pairs in call order.
  reflection: in one read transaction, at = kernel.clock.now, affordances =
  mind.affordance.enumerate_affordances(tx, actor, canon affordances, at, T), packet =
  mind.packet.build_packet(tx, actor, LOD.WARM, affordances, T, at), and the new episodes (BG-02;
  the newest R.max_episodes of them, oldest first). The call happens after that transaction has
  ended: ReflectionContext(packet, recent_episodes = those summaries); request =
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

class BackgroundRunner — GameService's handle on the quiet hours (BG-01), built with asyncio.
  running (bool: a task exists and is not done).
  start(session): running -> nothing; else a task running each job of pending(store, T) in
    order, where T = world_clock.turn_index when the task starts.
  async catch_up(session, progress=None): awaits the running task (its exceptions logged and
    swallowed), then T = world_clock.turn_index and, for each job of pending(store, T) not tried
    at this boundary, in order: progress(done, total) (awaited when it returns an awaitable;
    total = those jobs, done = how many already finished) before it, then the job.
  async cancel(): cancels the task and awaits it (CancelledError swallowed; nothing running ->
    returns at once), then empties the tried set.
  A job (both paths): result = await run_job(session, job) — an exception other than cancellation
  is logged and the job skipped — then in its own transaction commit(tx, job, result,
  kernel.clock.now(tx), T). Tried = the request_keys whose run_job finished (answered, failed or
  raised) at boundary T under this runner, so a failed job is not asked twice at one boundary; a
  job cancelled mid-call is not tried; a different T empties the set first.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.store import Store, Tx


QUIET_HOURS = "Everyone else catches up…"   # the progress label while a turn waits on them (BG-01)


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


def pending(store: "Store | Tx", turn_index: int) -> list[Job]:
    raise NotImplementedError("P10")


async def run_job(session, job: Job) -> JobResult:
    raise NotImplementedError("P10")


def commit(tx: "Tx", job: Job, result: JobResult, at: int, turn_index: int) -> list["Event"]:
    raise NotImplementedError("P10")


class BackgroundRunner:
    """BG-01. start(session) runs the boundary's jobs as an asyncio task; catch_up(session,
    progress) finishes them before a turn; cancel() stops the task and waits."""

    running: bool = False

    def start(self, session) -> None:
        raise NotImplementedError("P10")

    async def catch_up(self, session, progress=None) -> None:
        raise NotImplementedError("P10")

    async def cancel(self) -> None:
        raise NotImplementedError("P10")
from ._impl_background import jobs, pending, run_job, commit, BackgroundRunner  # noqa
