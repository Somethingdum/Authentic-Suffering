"""The turn transaction (P7). Rules GATE-00..19 (G0..G19), L2, L4, L5, L9, L12, TIME-01..04,
SCENE-01, the rollback law. docs/as/04_TURN_PIPELINE.md is the narrative; this docstring is the
contract. Helpers: turn.select (who, how long), turn.intake (stage 1), turn.cognition (stage 6
and the reading of answers), turn.timers (due timers), lanes.requests (every request).

run_turn(session, submit, progress=None) -> TurnOutcome
  submit.mode 'ask' -> ValueError (a question is not a turn: GameService answers it, P8).
  session.busy -> RuntimeError('busy'). Otherwise busy = True until return (finally: False).
  cur = world_clock.turn_index; the turn being played is T = cur + 1.
  Pre-flight (outside any transaction):
    lanes_up = the lanes whose session.client.refresh_health() is True; none -> TurnOutcome(ok=False,
      turn_index=cur, rejected_code='no_models', rejected_message=NO_MODELS).
    session.client.check_models(); ModelSwapped -> TurnOutcome(ok=False, turn_index=cur,
      rejected_code='model_swapped', rejected_message=MODEL_SWAPPED)   (LANE-05).
    notices: lane B down -> LANE_B_DOWN; lane A down -> LANE_A_DOWN (in that order).
  Attempts (the rollback law): attempt 1 runs simulate(); any exception other than
    turn.intake.Rejected rolls the whole transaction back and attempt 2 runs in STRICT mode (at
    most 1 reaction wave; turn_ledger.run_count = 2 on the rows of stages 0-12 — stages 13-19 run
    once and always write run_count 1) through a ReuseTransport, so a code fault is retried
    without paying for the models twice. During each attempt session.client.on_call appends
    (request, response) to the attempt's call buffer; the buffer is NOT emptied before the gate
    (S12 records it but keeps it), so a gate failure can reuse it. On a failed attempt every
    buffered call whose parse_status is 'ok' adds its answer (response.raw or response.text) to
    reuse[lanes.calllog.request_hash(request)], a list in call order. On_call and transport are
    restored afterwards whatever happens.
    ReuseTransport(inner, reuse): send pops the first cached text for the request's hash and
    returns LMResponse(call_class, lane = request.lane, text, model 'reused') (the client parses
    it again); no cached text -> inner.send. list_models and health forward to ``inner``.
    Rejected -> TurnOutcome(ok=False, turn_index=cur, rejected_code, rejected_message, clarify):
      nothing is kept, no time passes, the input is not consumed. A turn.cognition.DecisionHeld
      (HOLD-01: a consequential decision whose answer could not be used) is a Rejected: the same
      outcome (rejected_code 'decision_held', HELD_MESSAGE), and in a NEW transaction
      audit.log.repair(tx, 'decision_held', 6, 'HOLD-01', {actor_id, reason: kind}, T, now) keeps
      who and why (the turn's calls roll back with it). It is never retried: a second attempt
      would ask the same model the same thing.
    asyncio.CancelledError (the Play UI's Stop, P8: GameService cancels the task running this
      coroutine before stage 12) is a BaseException, not an Exception: it is never caught here and
      is not a rollback-law failure (no retry, nothing logged). The store transaction rolls it back
      (kernel.store.Store.transaction), the finally blocks restore on_call, transport and busy, and
      it propagates to the caller.
    Attempt 2 failing too -> in a NEW transaction audit.log.repair(tx, 'rollback', None, rule =
      GateFailed.failures[0], else the exception's ``rule`` attribute, else None; detail {error:
      f"{type name}: {message}"[:500] of the second failure, first: the same for the first}, T,
      now) and
      TurnOutcome(ok=False, turn_index=cur, rejected_code='turn_failed', rejected_message=
      REJECT_FAILED). The world is exactly as it was.
  After the commit: session.extras['last_addressee'] = the addressee intake used (when there was
    one); session.extras['remainder'] = intake's remainder (or None); then after_commit(...). An
    exception escaping after_commit is caught: in a new transaction audit.log.repair(tx,
    'degraded', None, 'GATE-13', {error: f"{type name}: {message}"[:500]}, T, now), and the
    outcome is TurnOutcome(ok=True, turn_index=T, narration = the narration row of T or '',
    degraded=True, notices, died) — the committed turn stands.

simulate — stages 0-12 in ONE store transaction:
  S0 wake: t0 = now; clock.begin_turn(tx, T); turn.timers.seed_society(tx, t0, T) (P9: starts a
    settlement's clocks; nothing without settlements); turn.timers.seed_world(tx, t0, T) (P10: the
    world's day; nothing without world_params); turn.timers.fire_due(tx, rng, t0, T, t0)
    (fire, dispatch, propagate and cascade-sweep every row due by t0 — P9; before P9 each row was
    fired and dispatched only). Then
    every pending_reactions row with status 'pending' (by reaction_id): its actor joins FORCED and
    PENDING_REACTION {reaction_id, actor_id, status: 'resolved'} (writer 'turn.pipeline', at t0,
    event actor_id = that actor) updates the row. Ledger 0 {lanes_up: sorted lane values,
    timers_fired: how many rows fired, pending_reactions: sorted FORCED ids}.
  S1 intake: (pc_intent, info) = await turn.intake.intake(tx, session, submit, T, t0).
    Ledger 1 {signature, source}.
  S2 freeze: ledger 2 {full_state_hash: kernel.hashing.full_state_hash(store)}; horizon =
    turn.select.horizon(tx, pc_intent, t0).
  Waves (wave 0 at t0; STRICT caps reaction waves at 1, else SchedulerRules.max_reaction_waves):
    S3 perceive: wave 0: cands = turn.select.candidates(tx, pc, T, horizon), perceivers = cands +
       the PC; a reaction wave: cands = perceivers = the reacting holders. perception.compile_scene(
       tx, h, wave_at, T) for each perceiver (sorted). At wave 0 only: for each (holder,
       trigger_at) of action.reactions.material_holders(tx, every event of this transaction so far,
       T) whose holder is the PC: horizon = select.pull(horizon, trigger_at, the latest events.at of
       this turn).
    S3b temper (H1): for each perceiver of the wave that select.conscious (sorted; the PC included —
       its anger goes on record, it never snaps): mind.temper.take_in(tx, rng, a, T, wave_at) —
       provocations taken in, and a snap when someone reaches their breaking point (TEMPER-05);
       what a snap does is turn.cognition step 4.
    S4 select: minds = the conscious cands; for each: select.mandatory(tx, a, T, wave_at, horizon,
       pc_intent (wave 0) | None, FORCED (wave 0) | empty), select.salience(select.salience_flags(
       tx, a, minds, pc, T, wave_at), mandatory, weights); plan = lanes.scheduler.plan_cognition(
       [(a, salience, mandatory)], config, settings.turn_depth, lanes_up); plan.overrun ->
       audit.log.repair('budget_overrun', 4, 'SCHED-01', {notes}). The wave's record {wave, at,
       lod: {actor: lod value}, salience: {actor: number}, mandatory: sorted ids} goes into the
       stage-4 ledger detail {'waves': [...]} (the PC is never in it).
    S5 afford: affs = {a: enumerate_affordances(tx, a, canon affordances, wave_at, T) for a in
       plan.lod}.
    S6 cognition: intents = await turn.cognition.decide(tx, session, plan, affs, T, wave_at,
       reaction = wave > 0, answered = answered); wave 0 adds intents[pc] = (W1, D-80)
       turn.cognition.urge_pc(tx, rng, pc, pc_intent, T, wave_at) (the PC's intent goes through the
       same barrier and resolver as everyone's, L12). asks = {a: turn.cognition.asks_for(tx, a, T,
       answered) for a in sorted(intents)}.
    S7 barrier: action.intent.barrier(tx, [intents[a] for a in sorted(intents)]).
    S8 resolve: action.resolve.resolve_wave(tx, rng, those, wave_at, T, horizon_ms=horizon);
       answers = turn.cognition.record_responses(tx, intents, affs, asks, T, wave_at, the seq
       before resolving); answered += their (actor, event) pairs; the wave's events = everything
       committed since that seq.
    S9 propagate: += action.propagate.propagate(tx, events, wave_at, T).
    S10 cascade: += action.cascade.sweep(tx, events, canon cascade rules, wave_at, T).
    S11 reactions: EVERYONE = select.candidates(...) + the PC + this wave's perceivers. perceive(E):
       perception.compile_aftermath(tx, h, E, max(e.at for e in E, t0), T) for each of EVERYONE
       and (B6, SEL-07) each of select.reached(tx, E, T) — whoever E's sounds reach, anywhere,
       then the PC-material pull as in S3. perceive(the wave's events); (next_at, holders) =
       NEXT(the wave's events). Then the timers inside the window, one at a time: while
       clock.due_between(tx, -1, next_at or horizon) is not empty: fire its first row, dispatch it
       (horizon_ms = horizon), += propagate / sweep of what it committed (at = its due_at),
       EVERYONE recomputed, perceive(those events), (t2, h2) = NEXT(those events); when t2 is not
       None and (next_at is None or t2 <= next_at): next_at = t2 and holders = h2 (their union when
       t2 == next_at). A next_at beyond the (possibly pulled) horizon means no next wave. The next
       wave runs at next_at with the conscious holders; none -> the waves are over.
       NEXT(E) = action.reactions.next_wave(tx, rng, E, T, wave + 1, horizon, exclude={pc}) (the PC
       never reacts: the player answers next turn). When it returns holders with no time, or
       wave + 1 is above the wave cap, those holders are deferred (TIME-04) and NEXT returns
       (None, []): for each holder that has no 'pending' pending_reactions row yet,
       PENDING_REACTION {reaction_id (kind 'rct'), actor_id, status 'pending'} (writer
       'turn.pipeline', at = the latest at of E, event actor_id = the holder) inserting
       pending_reactions {reaction_id, actor_id, created_turn T, status 'pending', intent
       {deferred: true, trigger_turn: T}} (they are FORCED next turn). An empty holder list ends
       the waves exactly like no time.
    Ledger rows 3..11 are written once, after the last wave (stage 4 detail {'waves': …}, stage 8
    detail {'responses': [[actor, speech event, response], …]}, the others {}).
  S12 commit: repeat — final = max(horizon, the latest events.at of this turn) (a COST landing can
    complete after the horizon; G04); turn.timers.fire_one(tx, rng, the first row of
    due_between(tx, -1, final), T, final) (P9: fire, dispatch, propagate, sweep) — until none is
    left (S08). Then action.tasks.advance(tx, a, final, T) for
    each actor with an active task (sorted); physical.bodies.progress(tx, b, final, T, rng) for each
    living body (sorted); clock.advance_event(tx, final, 'turn'); perception.compile_scene(tx, pc,
    final, T) (the PC's view as the window closes: the play view and the narrator read it);
    scenes(tx, pc, T, t0, final); every buffered call -> lanes.calllog.record; g =
    audit.commit_gate.compute(tx, T); commit_gate_log row (bookkeep 'audit'); not g.passed ->
    raise GateFailed(g.failures) (-> rollback, strict retry). Ledger 12 {horizon, final, gate:
    'all 58'} (written after the gate passed: S01 checks stages 0-11). COMMIT.

scenes(tx, pc, T, t0, final)   (SCENE-01, P7 minimum: a scene is the PC's stay in one place)
  No active scene -> SCENE_START at t0. The active scene (status 'active', newest started_at, then
  highest scene_id) is in another place than the PC now -> SCENE_END {scene_id, reason: 'left'}
  (writer 'turn.pipeline', at final, event place_id = the OLD scene's place) updating the row
  (status 'ended', ended_at final, chunk_count = T - the turn_index of its SCENE_START event + 1),
  then SCENE_START at final.
  SCENE_START {scene_id (kind 'scn'), place_id, problem: 'arrival'} inserts scenes {scene_id,
  problem 'arrival', place_id, participants = the living bodies positioned there (sorted),
  started_at, agency_level 'high', chunk_count 0, chunk_estimate 3, chunk_max 12, status
  'active'}; writer 'turn.pipeline', place_id set. (Opportunity weaving, passive scenes and scene
  summaries: P11.)

after_commit — stages 13-19, each in its own transaction; a failure here never rolls back the
  world (prose and memories are projections over committed state). session.client.on_call buffers
  the calls; they are recorded in the stage-17 transaction.
  S13 aftermath: holders = the distinct holders of this turn's percepts whose bodies are alive
    (sorted); packet = mind.memory.build_aftermath(tx, h, T, now) each; only packets with at least
    one percept or utterance go on. (B5, MEM-19) Each holder that goes on has its job queued:
    key = mind.memory.queue_writeback(tx, h, T, now). The retries: the memory_jobs rows with status
    'failed', attempts < RulesConfig.memory.writeback_retries and turn_index < T, ordered
    (turn_index, holder_id), at most RulesConfig.memory.max_retry_jobs, each with its packet
    build_aftermath(tx, holder_id, its turn_index, now) — the raw evidence is still there.
    Ledger 13 {holders: the sorted holders that go on}.
  S16 PC compile: npk = narration.narrator.build_narrator_packet(tx, pc, T, t0, settings); names =
    narration.narrator.known_names(tx). Ledger 16 {lines: len(npk.lines)}.
  S17+S18 narrate + lint (lane A) run CONCURRENTLY with the S14 writeback calls (lane B)
    (asyncio.gather): narration.narrator.narrate(client, npk, canon style 'narration',
    rules.style, config=config, all_known_names=names, turn_index=T) -> (prose, findings,
    attempts, passed); writeback: one Job per mind.memory.writeback_groups(packets) group
    (packet = the group's first holder's), then (B5) one per S13 retry in its order (packet = the
    retry's; its group is [its job key]): request = lanes.requests.build_request(config,
    WRITEBACK, turn_index=T, actor_id = the packet's holder, context=WritebackContext(
    aftermath=packet), json_schema = lanes.schemas.writeback_schema(its percept handles + its
    utterance handles + (B5) its self-experience O handles, entity handles, open-loop handles),
    a=packet, cue_ids = the sorted ids of every canon cue); Job(job_id = the group's first entry,
    call_class WRITEBACK, request, output_model WritebackOutput, lane_pref = request.lane, est_s =
    SchedulerRules.estimated_call_s['writeback']). All jobs -> ONE lanes.scheduler.run_jobs call.
  S14 apply (own transaction, groups in order): an answer whose parse_status is not 'ok' ->
    audit.log.repair(kind = 'timeout' | 'lane_down' | the parse status for grammar/schema failures |
    'degraded', 14, 'MEM-02', {holders: [the packet's holder], status}) and that group writes
    nothing but (B5, MEM-19) mind.memory.finish_writeback(tx, its job key, False, now, T);
    otherwise mind.memory.apply_writeback(tx, holder, WritebackOutput, its packet, now, T,
    cue_ids=…) then finish_writeback(tx, its job key, True, now, T). Ledger 14 'degraded' when a
    group failed, else 'ok'; detail {groups, failed: the first entries of the failed groups}.
  S15 audits: the leak scan (a query): claim_holdings rows with acquired_at >= t0 and provenance
    != 'inferred' whose holder has no percept_log row for acquired_via ->
    audit.log.record(tx, 'G15-leak', 'mind.perception', 'fail' | 'pass', [{holder_id, claim_id}],
    T). Ledger 15 {leaks: the count}.
    (The retrospective portrayal audit is P11.)
  S17+S18 write: narration.narrator.write_narration(tx, T, prose, npk, passed, attempts); story
    (service.session.append_story): kind 'player' with player_inputs.raw_text (mode 'say' for a
    say, else 'do'), kind 'notice' for each notice, then kind 'narration'; not passed ->
    audit.log.repair('lint_fail', 18, 'NARR-07', {findings: each finding's model_dump}); ledger
    17 {attempts}, ledger 18 'ok' | 'degraded' {findings: the findings' rule ids}; the calls
    buffered since stage 13 are recorded here.
  S19 autosave: session.run_dir is set -> service.runs.autosave(session), ledger 19 'ok'; an
    in-memory session -> ledger 19 'skipped'. The ledger detail keeps {file: the save's file name
    or None, full_state_hash} (the hash service.replay compares, DET-02).
  Returns TurnOutcome(ok=True, turn_index=T, narration=prose, degraded = not passed or a notice or
    a writeback group failed, notices, died = the PC's body is dead).

Progress: progress(stage, STAGE_LABELS[stage], stage / 19) is called (and awaited when it returns
an awaitable) as each stage begins, in this order: 0, 1, 2; per wave 3, 4, 5, 6, 7, 8, 11 (9, 10
and 18 are never announced: they are instant); then 12, 13, 16, 17 (inside the narration task),
14, 15, 19. A strict retry announces its stages again. Player-facing strings are the constants
below; the labels never use engine terms (UI-CLARITY-01).
Stage gates, in short: G0 lanes up + models as configured; G1 the PC's intent is one of its own
options; G2 hash recorded; G3 every percept through perception.grant; G4 mandatory minds get a
call; G5 options are the body's; G6 answers are schema-valid, in the offered set, echo-free (or
repaired / fallen back); G7 barrier; G8 resolved once; G9 conservation; G10 cascades cite rules;
G11 waves time-bounded; G12 the 58 bits; G13 aftermath ⊆ percepts; G14 writeback cites only
percepts; G15 leak scan; G16 narrator packet ⊆ PC percepts; G17 prose; G18 lint; G19 autosave.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ..contracts.protocol import InTurnSubmit
    from ..service.session import Session

STAGE_LABELS: dict[int, str] = {
    0: "Checking the world…", 1: "Reading your move…", 2: "Reading your move…",
    3: "Everyone takes it in…", 4: "Everyone takes it in…", 5: "Everyone takes it in…",
    6: "People decide…", 7: "The world moves…", 8: "The world moves…", 9: "The world moves…",
    10: "The world moves…", 11: "Reactions…", 12: "Locking it in…", 13: "Memories settle…",
    14: "Memories settle…", 15: "Memories settle…", 16: "Writing it down…", 17: "Writing it down…",
    18: "Writing it down…", 19: "Saving…",
}


NO_MODELS = "No model is answering. Check that LM Studio is running with both models loaded, then try again."
MODEL_SWAPPED = ("The model loaded in LM Studio changed since this run started. Load the same model again (or pick "
                 "the new one in Settings), then try again.")
REJECT_FAILED = "Something went wrong working out that moment. Nothing changed; try again."
LANE_B_DOWN = "Your second model is offline; turns will be thinner until it is back."
LANE_A_DOWN = "Your main model is offline; the story runs on the second model until it is back."


class GateFailed(Exception):
    """The 58-bit gate did not pass (``failures`` = the zero bits): the transaction rolls back."""

    def __init__(self, failures: list[str]):
        super().__init__("commit gate: " + ", ".join(failures))
        self.failures = failures


@dataclass
class TurnOutcome:
    ok: bool
    turn_index: int
    narration: str = ""
    rejected_code: str | None = None
    rejected_message: str | None = None
    clarify: str | None = None
    degraded: bool = False
    notices: list[str] = field(default_factory=list)
    died: bool = False


ProgressFn = Callable[[int, str, float], Any]


async def run_turn(session: "Session", submit: "InTurnSubmit", progress: ProgressFn | None = None) -> TurnOutcome:
    raise NotImplementedError("P7")


def scenes(tx, pc_id: str, turn_index: int, t0: int, final: int) -> None:
    raise NotImplementedError("P7")
from ._impl_pipeline import run_turn, scenes  # noqa
