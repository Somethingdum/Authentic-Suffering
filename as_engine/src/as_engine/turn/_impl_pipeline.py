"""Implementation of turn/pipeline.py."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from .pipeline import (GateFailed, LANE_A_DOWN, LANE_B_DOWN, MODEL_SWAPPED, NO_MODELS,  # noqa: E402
                       REJECT_FAILED)


@dataclass
class Ctx:
    session: object
    submit: object
    strict: bool
    lanes_up: set
    T: int = 0
    t0: int = 0
    horizon: int = 0
    pc_intent: object = None
    info: dict = field(default_factory=dict)
    calls: list = field(default_factory=list)
    answered: set = field(default_factory=set)
    judged: list = field(default_factory=list)   # PORT-06: audit.portrayal.Judged, every wave
    briefed: set = field(default_factory=set)    # CHEAT-11: standing briefs given this turn
    ledger: dict = field(default_factory=dict)
    progress: object = None
    final: int = 0


def _ledger(tx, T, stage, status="ok", detail=None, run_count=1):
    from ..contracts.events import WriteOp
    tx.bookkeep("turn.pipeline", "turn_ledger", WriteOp.UPSERT, {"turn_index": T, "stage": stage},
                {"run_count": run_count, "status": status, "detail": detail or {}})


async def _progress(ctx, stage):
    from .pipeline import STAGE_LABELS
    if ctx.progress is not None:
        r = ctx.progress(stage, STAGE_LABELS[stage], stage / 19)
        if hasattr(r, "__await__"):
            await r


def _last_at(tx, T):
    return tx.query_one("SELECT COALESCE(MAX(at), 0) FROM events WHERE turn_index=?", (T,))[0]


def _events_after(tx, seq):
    from ..action._impl_p5b import _events_since
    return _events_since(tx, seq)


def _max_seq(tx):
    return tx.query_one("SELECT COALESCE(MAX(seq),0) FROM events")[0]


async def simulate(ctx):
    """Stages 0-12 inside ONE transaction. Raises Rejected / GateFailed / anything."""
    from ..action import cascade, reactions
    from ..action.intent import barrier, intent_from_dict
    from ..action.propagate import propagate
    from ..action.resolve import resolve_wave
    from ..action import tasks
    from ..audit import commit_gate
    from ..audit.log import repair as log_repair
    from ..contracts.common import LOD
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    from ..kernel import clock, hashing
    from ..lanes.calllog import record as record_call
    from ..lanes.scheduler import plan_cognition
    from ..mind import perception
    from ..mind.affordance import enumerate_affordances
    from ..physical import bodies
    from . import cognition, intake, select, timers
    s = ctx.session
    store = s.store
    rng = s.rng
    cfg = s.config
    with store.transaction() as tx:
        # ---------------- 0 wake
        await _progress(ctx, 0)
        T = clock.turn_index(tx) + 1
        t0 = clock.now(tx)
        turn_first_seq = _max_seq(tx)
        ctx.T, ctx.t0 = T, t0
        clock.begin_turn(tx, T)
        timers.seed_society(tx, t0, T)
        timers.seed_world(tx, t0, T)
        fired_n = sum(1 for e in timers.fire_due(tx, rng, t0, T, t0) if e.type == EventType.TIMER_FIRED)
        forced = set()
        for r in tx.query("SELECT * FROM pending_reactions WHERE status='pending' ORDER BY reaction_id"):
            r = dict(r)
            forced.add(r["actor_id"])
            tx.commit_event(Event(type=EventType.PENDING_REACTION, writer="turn.pipeline", at=t0, turn_index=T, actor_id=r["actor_id"],
                                  payload={"reaction_id": r["reaction_id"], "actor_id": r["actor_id"], "status": "resolved"},
                                  writes=[WriteRecord(op=WriteOp.UPDATE, table="pending_reactions", key={"reaction_id": r["reaction_id"]},
                                                      values={"status": "resolved"})]))
        from ..cheats.commands import take_wonder
        take_wonder(tx, s.pc_id, T, t0)          # CHEAT-14: the Boss's wonder, seen from wave 0
        from ..cheats.interpret import take_shows
        take_shows(tx, s.pc_id, T, t0)           # CHEAT-18: what the world cannot hold, seen by everyone here
        _ledger(tx, T, 0, "ok", {"lanes_up": sorted(l.value for l in ctx.lanes_up), "timers_fired": fired_n,
                                 "pending_reactions": sorted(forced)}, 2 if ctx.strict else 1)
        # ---------------- 1 intake
        await _progress(ctx, 1)
        ctx.pc_intent, ctx.info = await intake.intake(tx, s, ctx.submit, T, t0)
        _ledger(tx, T, 1, "ok", {"signature": ctx.pc_intent.bound.signature, "source": ctx.pc_intent.source}, 2 if ctx.strict else 1)
        # ---------------- 2 freeze
        await _progress(ctx, 2)
        _ledger(tx, T, 2, "ok", {"full_state_hash": hashing.full_state_hash(store)}, 2 if ctx.strict else 1)
        ctx.horizon = select.horizon(tx, ctx.pc_intent, t0)
        # ---------------- waves
        wave_idx, wave_at, reacting = 0, t0, None
        catalog = tx.canon.all("affordance")
        rules = tx.canon.all("cascade")
        max_waves = 1 if ctx.strict else tx.rules.scheduler.max_reaction_waves
        plans = []
        responses = []
        while True:
            await _progress(ctx, 3)
            if reacting is None:
                cands = select.candidates(tx, s.pc_id, T, ctx.horizon)
                perceivers = sorted(set(cands) | {s.pc_id})
            else:
                cands = list(reacting)
                perceivers = sorted(set(cands))
            for h in perceivers:
                perception.compile_scene(tx, h, wave_at, T)
            if wave_idx == 0:
                for h, trig in reactions.material_holders(tx, _events_after(tx, turn_first_seq), T):
                    if h == s.pc_id:
                        ctx.horizon = select.pull(ctx.horizon, trig, _last_at(tx, T))
            from ..mind import temper as _temper
            for h in perceivers:
                if select.conscious(tx, h) and tx.query_one("SELECT 1 FROM actors WHERE actor_id=?", (h,)) is not None:
                    _temper.take_in(tx, rng, h, T, wave_at)
            # 4 select
            await _progress(ctx, 4)
            minds = [c for c in cands if select.conscious(tx, c)]
            sel = []
            for a in minds:
                mand = select.mandatory(tx, a, T, wave_at, ctx.horizon, ctx.pc_intent if wave_idx == 0 else None,
                                        forced if wave_idx == 0 else frozenset())
                flags = select.salience_flags(tx, a, minds, s.pc_id, T, wave_at)
                sel.append((a, select.salience(flags, mand, tx.rules.scheduler.salience_weights), mand))
            plan = plan_cognition(sel, cfg, s.settings.turn_depth, ctx.lanes_up)
            if plan.overrun:
                log_repair(tx, "budget_overrun", 4, "SCHED-01", {"notes": plan.notes}, T, wave_at)
            plans.append({"wave": wave_idx, "at": wave_at, "lod": {a: l.value for a, l in plan.lod.items()},
                          "salience": {a: sc for a, sc, _m in sel}, "mandatory": sorted(a for a, _s, m in sel if m)})
            # CHEAT-11: a standing-brief actor (always cheat-made: quarantine 1) is briefed once a turn
            from ..cheats.commands import standing_brief
            from ..contracts.common import LOD as _LOD
            for a in sorted(plan.lod):
                if plan.lod[a] in (_LOD.HOT, _LOD.WARM) and a not in ctx.briefed:
                    ctx.briefed.add(a)
                    q = tx.query_one("SELECT quarantine FROM actors WHERE actor_id=?", (a,))
                    if q is not None and q[0] == 1:
                        standing_brief(tx, a, T, wave_at)
            # 5 afford
            await _progress(ctx, 5)
            affs = {a: enumerate_affordances(tx, a, catalog, wave_at, T) for a in plan.lod}
            # 6 cognition
            await _progress(ctx, 6)
            intents = await cognition.decide(tx, s, plan, affs, T, wave_at, reaction=wave_idx > 0, answered=ctx.answered,
                                             audits=ctx.judged)
            if wave_idx == 0:
                intents[s.pc_id] = cognition.urge_pc(tx, rng, s.pc_id, ctx.pc_intent, T, wave_at)
            asks = {a: cognition.asks_for(tx, a, T, ctx.answered) for a in sorted(intents)}
            # 7 barrier
            await _progress(ctx, 7)
            ordered = barrier(tx, [intents[a] for a in sorted(intents)])
            # 8 resolve
            await _progress(ctx, 8)
            first = _max_seq(tx)
            resolve_wave(tx, rng, ordered, wave_at, T, horizon_ms=ctx.horizon)
            answers = cognition.record_responses(tx, intents, affs, asks, T, wave_at, first)
            ctx.answered |= {(a, e) for a, e, _r in answers}
            responses.extend(answers)
            evs = _events_after(tx, first)
            # 9 propagate
            evs += propagate(tx, evs, wave_at, T)
            # 10 cascade
            evs += cascade.sweep(tx, evs, rules, wave_at, T)
            # 11 reactions: everyone perceives what happened, then who reacts
            await _progress(ctx, 11)
            nxt, holders = await _after_wave(ctx, tx, evs, wave_idx, max_waves, perceivers)
            if nxt is None or not holders:
                break
            wave_idx += 1
            wave_at = nxt
            reacting = holders
        for st in (3, 4, 5, 6, 7, 8, 9, 10, 11):
            _ledger(tx, T, st, "ok", {"waves": plans} if st == 4 else ({"responses": responses} if st == 8 else {}),
                    2 if ctx.strict else 1)
        # ---------------- 12 commit
        await _progress(ctx, 12)
        while True:   # a COST landing may complete after the horizon (G04); nothing due before the end may stay pending (S08)
            final = max(ctx.horizon, _last_at(tx, T))
            rows = clock.due_between(tx, -1, final)
            if not rows:
                break
            timers.fire_one(tx, rng, rows[0], T, final)
        ctx.final = final
        for a in [r[0] for r in tx.query("SELECT DISTINCT actor_id FROM tasks WHERE status='active' ORDER BY actor_id")]:
            tasks.advance(tx, a, final, T)
        for b in [r[0] for r in tx.query("SELECT body_id FROM bodies WHERE alive=1 ORDER BY body_id")]:
            bodies.progress(tx, b, final, T, rng)
        clock.advance_event(tx, final, "turn")
        perception.compile_scene(tx, s.pc_id, final, T)
        scenes(tx, s.pc_id, T, t0, final)
        for q, r in ctx.calls:        # kept in ctx.calls: a gate failure reuses them in the strict retry
            record_call(tx, q, r)
        gate = commit_gate.compute(tx, T)
        tx.bookkeep("audit", "commit_gate_log", WriteOp.INSERT, {}, {
            "turn_index": T, "session_bits": gate.session, "world_bits": gate.world, "entities_bits": gate.entities,
            "global_bits": gate.global_, "passed": int(gate.passed), "failures": gate.failures})
        if not gate.passed:
            raise GateFailed(gate.failures)
        _ledger(tx, T, 12, "ok", {"horizon": ctx.horizon, "final": final, "gate": "all 58"}, 2 if ctx.strict else 1)


async def _after_wave(ctx, tx, evs, wave_idx, max_waves, perceivers):
    """Perceive the wave's events, fire timers, decide the next wave. Returns (time | None, holders)."""
    from ..action import cascade, reactions
    from ..action.propagate import propagate
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    from ..kernel import clock
    from ..mind import perception
    from . import select, timers
    s = ctx.session
    T = ctx.T
    rules = tx.canon.all("cascade")
    everyone = sorted(set(select.candidates(tx, s.pc_id, T, ctx.horizon)) | {s.pc_id} | set(perceivers))

    def perceive(events):
        last = max([e.at for e in events] + [ctx.t0])
        for h in sorted(set(everyone) | set(select.reached(tx, events, T))):   # SEL-07 (B6, C08)
            perception.compile_aftermath(tx, h, events, last, T)
        for h, trig in reactions.material_holders(tx, events, T):
            if h == s.pc_id:
                ctx.horizon = select.pull(ctx.horizon, trig, _last_at(tx, T))

    perceive(evs)
    exclude = {s.pc_id}
    nxt, holders = _next(tx, s, evs, T, wave_idx + 1, ctx.horizon, exclude, max_waves)
    # timers between now and the next wave (or the horizon), one at a time: each may move the horizon
    while True:
        limit = nxt if nxt is not None else ctx.horizon
        rows = clock.due_between(tx, -1, limit)
        if not rows:
            break
        row = rows[0]
        fired = clock.fire(tx, row, T)
        first = tx.query_one("SELECT COALESCE(MAX(seq),0) FROM events")[0]
        timers.dispatch(tx, s.rng, row, fired, T, ctx.horizon)
        from ..action._impl_p5b import _events_since
        tev = _events_since(tx, first)
        tev += propagate(tx, tev, row["due_at"], T)
        tev += cascade.sweep(tx, tev, rules, row["due_at"], T)
        everyone = sorted(set(select.candidates(tx, s.pc_id, T, ctx.horizon)) | {s.pc_id} | set(perceivers))
        perceive(tev)
        t2, h2 = _next(tx, s, tev, T, wave_idx + 1, ctx.horizon, exclude, max_waves)
        if t2 is not None and (nxt is None or t2 <= nxt):
            holders = sorted(set(holders) | set(h2)) if nxt == t2 else h2
            nxt = t2
    if nxt is not None and nxt > ctx.horizon:
        nxt, holders = None, []
    return nxt, [h for h in holders if select.conscious(tx, h)]


def _next(tx, s, evs, T, wave_index, horizon, exclude, max_waves):
    from ..action import reactions
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    from ..kernel.clock import now
    t, hs = reactions.next_wave(tx, s.rng, evs, T, wave_index, horizon, exclude=exclude)
    if hs and (t is None or wave_index > max_waves):
        for h in hs:
            if tx.query_one("SELECT 1 FROM pending_reactions WHERE actor_id=? AND status='pending'", (h,)):
                continue
            rid = tx.mint("rct")
            tx.commit_event(Event(type=EventType.PENDING_REACTION, writer="turn.pipeline", at=max(e.at for e in evs), turn_index=T, actor_id=h,
                                  payload={"reaction_id": rid, "actor_id": h, "status": "pending"},
                                  writes=[WriteRecord(op=WriteOp.INSERT, table="pending_reactions",
                                                      values={"reaction_id": rid, "actor_id": h, "created_turn": T, "status": "pending",
                                                              "intent": {"deferred": True, "trigger_turn": T}})]))
        return None, []
    return t, hs


async def run_turn(session, submit, progress=None):
    from ..audit.log import repair as log_repair
    from ..contracts.common import Lane
    from ..kernel import clock
    from ..lanes.errors import ModelSwapped
    from .intake import Rejected
    from .pipeline import TurnOutcome
    if submit.mode == "ask":
        raise ValueError("Ask is not a turn: the service answers it with GUIDE (P8)")
    if session.busy:
        raise RuntimeError("busy")
    session.busy = True
    try:
        cur = clock.turn_index(session.store)
        health = await session.client.refresh_health()
        lanes_up = {l for l, ok in health.items() if ok}
        if not lanes_up:
            return TurnOutcome(ok=False, turn_index=cur, rejected_code="no_models", rejected_message=NO_MODELS)
        try:
            await session.client.check_models()
        except ModelSwapped as e:
            return TurnOutcome(ok=False, turn_index=cur, rejected_code="model_swapped", rejected_message=MODEL_SWAPPED)
        notices = []
        if Lane.B not in lanes_up:
            notices.append(LANE_B_DOWN)
        if Lane.A not in lanes_up:
            notices.append(LANE_A_DOWN)
        errors = []
        ctx = None
        reuse = {}
        inner = session.client.transport
        for attempt in (1, 2):
            ctx = Ctx(session=session, submit=submit, strict=attempt == 2, lanes_up=lanes_up, progress=progress)
            prev = session.client.on_call
            session.client.on_call = lambda q, r, _c=ctx: _c.calls.append((q, r))
            if attempt == 2:
                session.client.transport = ReuseTransport(inner, reuse)
            try:
                await simulate(ctx)
                break
            except Rejected as rj:
                if rj.code == "decision_held":          # HOLD-01: who and why outlive the rolled-back turn
                    with session.store.transaction() as tx:
                        log_repair(tx, "decision_held", 6, "HOLD-01", {"actor_id": rj.actor_id, "reason": rj.kind}, cur + 1,
                                   clock.now(tx))
                return TurnOutcome(ok=False, turn_index=cur, rejected_code=rj.code, rejected_message=rj.message, clarify=rj.clarify)
            except Exception as e:  # noqa: BLE001 — the rollback law
                errors.append(e)
                for q, r in ctx.calls:
                    if r.parse_status == "ok":
                        reuse.setdefault(request_hash(q), []).append(r.raw or r.text)
                if attempt == 2:
                    rule = e.failures[0] if isinstance(e, GateFailed) else getattr(e, "rule", None)
                    from ..audit.commit_gate import BIT_STAGE
                    stage = BIT_STAGE.get(rule) if isinstance(e, GateFailed) else None   # AUDIT-03
                    with session.store.transaction() as tx:
                        log_repair(tx, "rollback", stage, rule, {"error": f"{type(e).__name__}: {e}"[:500],
                                                               "first": f"{type(errors[0]).__name__}: {errors[0]}"[:500]}, cur + 1,
                                   clock.now(tx))
                    return TurnOutcome(ok=False, turn_index=cur, rejected_code="turn_failed", rejected_message=REJECT_FAILED)
            finally:
                session.client.on_call = prev
                session.client.transport = inner
        if ctx.info.get("addressee"):
            session.extras["last_addressee"] = ctx.info["addressee"]
        session.extras["remainder"] = ctx.info.get("remainder")
        try:
            outcome = await after_commit(ctx, notices)
        except Exception as e:  # noqa: BLE001 — stages 13-19 never undo the committed turn
            with session.store.transaction() as tx:
                log_repair(tx, "degraded", None, "GATE-13", {"error": f"{type(e).__name__}: {e}"[:500]}, ctx.T, clock.now(tx))
            row = session.store.query_one("SELECT text FROM narration WHERE turn_index=?", (ctx.T,))
            dead = session.store.query_one("SELECT alive FROM bodies WHERE body_id=?", (session.pc_id,))[0] == 0
            outcome = TurnOutcome(ok=True, turn_index=ctx.T, narration=row[0] if row else "", degraded=True, notices=notices,
                                  died=dead)
        return outcome
    finally:
        session.busy = False


async def after_commit(ctx, notices):
    """Stages 13-19, each in its own transaction. Failures never roll back the world."""
    from ..audit.log import repair as log_repair
    from ..contracts.calls import WritebackContext
    from ..contracts.common import CallClass
    from ..contracts.mind import WritebackOutput
    from ..kernel import clock
    from ..lanes.calllog import record as record_call
    from ..lanes.requests import build_request
    from ..lanes.schemas import writeback_schema
    from ..mind.memory import apply_writeback, build_aftermath, writeback_groups
    from ..narration.narrator import build_narrator_packet, narrate
    from ..service.session import append_story
    from .pipeline import TurnOutcome
    s = ctx.session
    store = s.store
    T = ctx.T
    calls = []
    prev = s.client.on_call
    s.client.on_call = lambda q, r: calls.append((q, r))
    degraded = False
    try:
        # 13 aftermath
        await _progress(ctx, 13)
        with store.transaction() as tx:
            at = clock.now(tx)
            holders = [r[0] for r in tx.query("SELECT DISTINCT p.holder_id FROM percept_log p JOIN bodies b ON b.body_id=p.holder_id "
                                              "WHERE p.turn_index=? AND b.alive=1 ORDER BY p.holder_id", (T,))]
            packets = {h: build_aftermath(tx, h, T, at) for h in holders}
            packets = {h: p for h, p in packets.items() if p.percepts or p.utterances}
            from ..mind.memory import queue_writeback
            keys = {h: queue_writeback(tx, h, T, at) for h in sorted(packets)}
            R_m = store.rules.memory
            retry = [dict(r) for r in tx.query("SELECT * FROM memory_jobs WHERE status='failed' AND attempts < ? AND turn_index < ? "
                                                "ORDER BY turn_index, holder_id LIMIT ?", (R_m.writeback_retries, T, R_m.max_retry_jobs))]
            retry_packets = {r["job_key"]: build_aftermath(tx, r["holder_id"], r["turn_index"], at) for r in retry}
            allp = {**packets, **retry_packets}
            _ledger(tx, T, 13, "ok", {"holders": sorted(packets)})
        # 16 PC compile
        await _progress(ctx, 16)
        with store.transaction() as tx:
            npk = build_narrator_packet(tx, s.pc_id, T, ctx.t0, s.settings)
            from ..narration.narrator import known_names
            names = known_names(tx)
            _ledger(tx, T, 16, "ok", {"lines": len(npk.lines)})
        # 17-18 narrate + lint (lane A) while 14 writeback runs (lane B)
        import asyncio
        style_rules = store.canon.find("style", "narration")

        async def do_narrate():
            await _progress(ctx, 17)
            return await narrate(s.client, npk, style_rules, store.rules.style, config=s.config,
                                 all_known_names=names, turn_index=T)

        async def do_writeback():
            from ..lanes.scheduler import Job, run_jobs
            groups = writeback_groups(packets) + [[k] for k in retry_packets]
            jobs = []
            for g in groups:
                a = allp[g[0]]
                ctxw = WritebackContext(aftermath=a)
                cue_ids = [c.id for c in _cues(store)]
                sch = writeback_schema([x.handle for x in a.percepts] + [u.handle for u in a.utterances] + [o.handle for o in a.self_experiences] or ["S1"],
                                       [e.handle for e in a.entities], [l.handle for l in a.open_loops])
                req = build_request(s.config, CallClass.WRITEBACK, turn_index=T, actor_id=a.holder_id, context=ctxw, json_schema=sch,
                                    a=a, cue_ids=cue_ids)
                jobs.append(Job(job_id=g[0], call_class=CallClass.WRITEBACK, request=req, output_model=WritebackOutput,
                                lane_pref=req.lane, est_s=store.rules.scheduler.estimated_call_s["writeback"]))
            from ..audit import portrayal
            from ..contracts.mind import PortrayalVerdict
            for i, (_j, q) in enumerate(retro):
                jobs.append(Job(job_id=f"portrayal:{i}", call_class=CallClass.PORTRAYAL_AUDIT, request=q,
                                output_model=PortrayalVerdict, lane_pref=q.lane,
                                est_s=store.rules.scheduler.estimated_call_s["portrayal_audit"]))
            res = await run_jobs(s.client, jobs) if jobs else {}
            return groups, res

        from ..audit import portrayal as _portrayal
        retro = _portrayal.jobs(s.config, ctx.judged, T)   # PORT-06: judged after the fact, on lane B
        (prose, findings, attempts, passed), (groups, wres) = await asyncio.gather(do_narrate(), do_writeback())
        # 14 writeback apply
        await _progress(ctx, 14)
        with store.transaction() as tx:
            at = clock.now(tx)
            cue_ids = [c.id for c in _cues(store)]
            from ..mind.memory import finish_writeback
            wb_failed = []
            for g in groups:
                r = wres[g[0]]
                pk = allp[g[0]]
                key = keys.get(g[0], g[0])
                if r.parse_status != "ok":
                    wb_failed.append(g[0])
                    log_repair(tx, {"timeout": "timeout", "lane_error": "lane_down"}.get(r.parse_status, r.parse_status
                                   if r.parse_status in ("grammar_fail", "schema_fail") else "degraded"), 14, "MEM-02",
                               {"holders": [pk.holder_id], "status": r.parse_status}, T, at)
                    finish_writeback(tx, key, False, at, T)
                    continue
                out = WritebackOutput.model_validate(r.parsed)
                apply_writeback(tx, pk.holder_id, out, pk, at, T, cue_ids=cue_ids)
                finish_writeback(tx, key, True, at, T)
            _ledger(tx, T, 14, "degraded" if wb_failed else "ok", {"groups": groups, "failed": wb_failed})
        # 15 audits: the leak scan (a query)
        await _progress(ctx, 15)
        with store.transaction() as tx:
            leaks = [dict(r) for r in tx.query(
                "SELECT h.holder_id, h.claim_id FROM claim_holdings h WHERE h.acquired_at >= ? AND h.provenance != 'inferred' AND NOT EXISTS "
                "(SELECT 1 FROM percept_log p WHERE p.holder_id=h.holder_id AND p.event_id=h.acquired_via)", (ctx.t0,))]
            from ..audit.log import record
            record(tx, "G15-leak", "mind.perception", "fail" if leaks else "pass", leaks, T)
            for i, (j, q) in enumerate(retro):
                _portrayal.record_retrospective(tx, j, q, wres[f"portrayal:{i}"], T)
            _ledger(tx, T, 15, "ok", {"leaks": len(leaks)})
        # 17/18 write narration + story
        with store.transaction() as tx:
            from ..narration import style as nstyle
            from ..narration.narrator import write_narration
            write_narration(tx, T, prose, npk, passed, attempts)
            nstyle.save(tx, nstyle.update_after_turn(nstyle.load(tx), prose, nstyle.scene_type(npk)), T)
            pin = tx.query_one("SELECT mode, raw_text FROM player_inputs WHERE turn_index=?", (T,))
            if pin is not None:
                append_story(tx, T, "player", pin[1], "say" if pin[0] == "say" else "do")
            for n in notices:
                append_story(tx, T, "notice", n)
            append_story(tx, T, "narration", prose)
            if not passed:
                log_repair(tx, "lint_fail", 18, "NARR-07", {"findings": [f.model_dump(mode="json") for f in findings]}, T, clock.now(tx))
            _ledger(tx, T, 17, "ok", {"attempts": attempts})
            _ledger(tx, T, 18, "ok" if passed else "degraded", {"findings": [f.rule for f in findings]})
            for q, r in calls:
                record_call(tx, q, r)
            calls.clear()
        # 19 autosave
        await _progress(ctx, 19)
        from ..service import runs
        saved = None
        if s.run_dir is not None:
            saved = runs.autosave(s)
        from ..kernel.hashing import full_state_hash
        with store.transaction() as tx:
            _ledger(tx, T, 19, "ok" if saved else "skipped", {"file": saved.name if saved else None,
                                                             "full_state_hash": full_state_hash(store)})
        died = store.query_one("SELECT alive FROM bodies WHERE body_id=?", (s.pc_id,))[0] == 0
        return TurnOutcome(ok=True, turn_index=T, narration=prose, degraded=(not passed) or bool(notices) or bool(wb_failed),
                           notices=notices, died=died)
    finally:
        s.client.on_call = prev


def _cues(store):
    out = []
    for p in store.canon.by_kind.get("cue", {}).values():
        out.append(p)
    return sorted(out, key=lambda c: c.id)


def request_hash(q):
    from ..lanes.calllog import request_hash as rh
    return rh(q)


class ReuseTransport:
    """Strict retry: an identical request (same hash) gets the first attempt's successful answer again."""

    def __init__(self, inner, cache):
        self.inner, self.cache = inner, cache

    async def send(self, lane, request):
        from ..contracts.lanes import LMResponse
        got = self.cache.get(request_hash(request))
        if got:
            return LMResponse(call_class=request.call_class, lane=request.lane, text=got.pop(0), model="reused")
        return await self.inner.send(lane, request)

    async def list_models(self, lane_id, lane):
        return await self.inner.list_models(lane_id, lane)

    async def health(self, lane_id, lane):
        return await self.inner.health(lane_id, lane)


def _pc_place(tx, pc):
    return tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (pc,))[0]


def scenes(tx, pc, T, t0, horizon):
    # SCENE-01 (P7 minimum): a scene is the PC's stay in one place.
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    act = tx.query_one("SELECT scene_id, place_id FROM scenes WHERE status='active' ORDER BY started_at DESC, scene_id DESC LIMIT 1")
    here = _pc_place(tx, pc)

    def start(at):
        sid = tx.mint("scn")
        who = sorted(r[0] for r in tx.query("SELECT p.body_id FROM positions p JOIN bodies b ON b.body_id=p.body_id "
                                            "WHERE p.place_id=? AND b.alive=1", (here,)))
        tx.commit_event(Event(type=EventType.SCENE_START, writer="turn.pipeline", at=at, turn_index=T, place_id=here,
                              payload={"scene_id": sid, "place_id": here, "problem": "arrival"},
                              writes=[WriteRecord(op=WriteOp.INSERT, table="scenes", values={
                                  "scene_id": sid, "problem": "arrival", "place_id": here, "participants": who, "started_at": at,
                                  "agency_level": "high", "chunk_count": 0, "chunk_estimate": 3, "chunk_max": 12, "status": "active"})]))
    if act is None:
        start(t0)
        return
    if act[1] != here:
        st = tx.query_one("SELECT turn_index FROM events WHERE type='SCENE_START' AND json_extract(payload,'$.scene_id')=?", (act[0],))[0]
        tx.commit_event(Event(type=EventType.SCENE_END, writer="turn.pipeline", at=horizon, turn_index=T, place_id=act[1],
                              payload={"scene_id": act[0], "reason": "left"},
                              writes=[WriteRecord(op=WriteOp.UPDATE, table="scenes", key={"scene_id": act[0]},
                                                  values={"status": "ended", "ended_at": horizon, "chunk_count": T - st + 1})]))
        start(horizon)
