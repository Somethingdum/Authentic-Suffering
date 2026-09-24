"""Implementation of service/background.py (P10)."""
from __future__ import annotations

import asyncio
import json
import logging

log = logging.getLogger("as_engine.service")

DAY = 86_400_000


def _B():
    from . import background
    return background


def _rows(s, sql, p=()):
    return [dict(r) for r in s.query(sql, p)]


def _row(s, sql, p=()):
    r = s.query_one(sql, p)
    return dict(r) if r is not None else None


def _turn(s):
    return s.query_one("SELECT turn_index FROM world_clock")[0]


def _eligible(s, actor_id):
    r = _row(s, "SELECT a.controller, b.alive FROM actors a JOIN bodies b ON b.body_id=a.actor_id WHERE a.actor_id=?",
             (actor_id,))
    return r is not None and r["controller"] != "human" and r["alive"] == 1


def _prev(s, actor_id, T):
    """(turn_index, at) of the actor's newest REFLECTION of a turn before T, or None."""
    r = s.query_one("SELECT turn_index, at FROM events WHERE type='REFLECTION' AND actor_id=? AND turn_index < ? "
                    "ORDER BY seq DESC LIMIT 1", (actor_id, T))
    return (r[0], r[1]) if r is not None else None


def new_episodes(s, actor_id, T):
    # BG-02 NEW episodes of ``actor_id`` at boundary T, by (at, episode_id); and prev.
    prev = _prev(s, actor_id, T)
    if prev is None:
        return _rows(s, "SELECT * FROM episodes WHERE holder_id=? ORDER BY at, episode_id", (actor_id,)), None
    return _rows(s, "SELECT * FROM episodes WHERE holder_id=? AND turn_index > ? ORDER BY at, episode_id",
                 (actor_id, prev[0])), prev


def eligibility_key(s, actor_id, T):
    # BG-02: 'm:<episode>' | 's:<last_sleep_ms>' | None, with the new episodes.
    R = s.rules.background
    eps, prev = new_episodes(s, actor_id, T)
    if not eps:
        return None, eps
    mat = [e for e in eps if e["salience"] >= R.material_salience or e["anchor"] == 1]
    if mat:
        return "m:" + mat[-1]["episode_id"], eps
    if len(eps) >= R.rest_min_episodes:
        r = s.query_one("SELECT last_sleep_ms FROM needs WHERE body_id=?", (actor_id,))
        if r is not None and r[0] > eps[0]["at"] and (prev is None or r[0] > prev[1]):
            return "s:" + str(r[0]), eps
    return None, eps


def _boundary_retold(s, rumour_id, T):
    out = set()
    for (pl,) in s.query("SELECT payload FROM events WHERE type='RUMOUR_DISTORTED' AND turn_index=?", (T,)):
        d = json.loads(pl)
        if d.get("rumour_id") == rumour_id:
            out.add(d.get("holder_id"))
    return out


def jobs(store, turn_index):
    from ..kernel.clock import now as clock_now
    from ..world.rumours import holders
    B = _B()
    T = turn_index
    R = store.rules.background
    refl = []
    for (a,) in store.query("SELECT DISTINCT holder_id FROM episodes ORDER BY holder_id"):
        if not _eligible(store, a):
            continue
        key, eps = eligibility_key(store, a, T)
        if key is None:
            continue
        refl.append((-eps[-1]["at"], a, key))
    refl.sort()
    out = [B.Job(kind="reflection", subject_id=a, rumour_id=None, request_key=f"reflection:{a}:{key}")
           for _na, a, key in refl[:R.max_reflections]]
    now = clock_now(store)
    quiet = store.rules.society.rumour_quiet_days * DAY
    ret = []
    for r in store.query("SELECT rumour_id, distortions, created_at FROM rumours ORDER BY rumour_id"):
        if r["created_at"] < now - quiet:
            continue
        done = {d.get("holder_id") for d in json.loads(r["distortions"] or "[]")}
        done -= _boundary_retold(store, r["rumour_id"], T)
        for h, conf in holders(store, r["rumour_id"]):
            if conf < 1 or h in done or not _eligible(store, h):
                continue
            ret.append(B.Job(kind="retelling", subject_id=h, rumour_id=r["rumour_id"],
                             request_key=f"retelling:{h}:{r['rumour_id']}"))
    return out + ret[:R.max_retellings]


def pending(store, turn_index):
    T = turn_index
    keys = {json.loads(pl).get("request_key")
            for (pl,) in store.query("SELECT payload FROM events WHERE type='REFLECTION' AND turn_index=?", (T,))}
    retold = set()
    for (pl,) in store.query("SELECT payload FROM events WHERE type='RUMOUR_DISTORTED' AND turn_index=?", (T,)):
        d = json.loads(pl)
        retold.add((d.get("rumour_id"), d.get("holder_id")))
    return [j for j in jobs(store, T)
            if not (j.kind == "reflection" and j.request_key in keys)
            and not (j.kind == "retelling" and (j.rumour_id, j.subject_id) in retold)]


def _reflection_request(session, packet, recent, turn_index):
    from ..contracts.calls import ReflectionContext
    from ..contracts.common import CallClass
    from ..contracts.mind import ReflectionOutput
    from ..lanes.requests import build_request
    from ..lanes.schemas import to_lm_schema
    ctx = ReflectionContext(packet=packet, recent_episodes=recent)
    schema = to_lm_schema(ReflectionOutput)
    return build_request(session.config, CallClass.REFLECTION, turn_index=turn_index, actor_id=packet.actor_id,
                         context=ctx, json_schema=schema, ctx=ctx), schema


async def run_job(session, job):
    from ..contracts.common import LOD, CallClass
    from ..contracts.mind import ReflectionOutput, RumourDistortion
    from ..kernel.clock import now
    from ..lanes.repair import call_with_repair
    from ..lanes.requests import build_request, repair_request
    from ..lanes.schemas import to_lm_schema
    from ..mind.affordance import enumerate_affordances
    from ..mind.packet import build_packet
    from ..mind.perception import word_for
    from ..world.rumours import claim_sentence, holders
    from ..lanes.client import LaneClient
    B = _B()
    store = session.store
    T = _turn(store)
    calls = []
    client = LaneClient(session.config, session.client.transport, on_call=lambda q, r: calls.append((q, r)))
    if job.kind == "reflection":
        with store.transaction() as tx:
            at = now(tx)
            affs = enumerate_affordances(tx, job.subject_id, tx.canon.all("affordance"), at, T)
            packet = build_packet(tx, job.subject_id, LOD.WARM, affs, T, at)
            eps = new_episodes(tx, job.subject_id, T)[0][-tx.rules.background.max_episodes:]
        req, schema = _reflection_request(session, packet, [e["summary"] for e in eps], T)

        def rebuild(rq, resp):
            return repair_request(session.config, rq, {"raw": resp.text or "", "error": resp.error or resp.parse_status},
                                  packet, schema)
        resp, _repaired = await call_with_repair(client, req, ReflectionOutput, repair_builder=rebuild)
        if resp.parse_status != "ok":
            return B.JobResult(job=job, failed=True, calls=tuple(calls))
        return B.JobResult(job=job, answer={"output": ReflectionOutput.model_validate(resp.parsed),
                                            "handles": dict(packet.handles)}, calls=tuple(calls))
    # retelling
    from ..contracts.calls import RumourContext
    with store.transaction() as tx:
        p = _row(tx, "SELECT p.* FROM rumours r JOIN propositions p ON p.prop_id=r.prop_id WHERE r.rumour_id=?", (job.rumour_id,))
        conf = dict(holders(tx, job.rumour_id)).get(job.subject_id, 0)
        name = tx.query_one("SELECT display_name FROM actors WHERE actor_id=?", (job.subject_id,))[0]
        text = claim_sentence(p["predicate"], word_for(tx, job.subject_id, p["subject_id"]))
    ctx = RumourContext(teller_identity=name, claim_text=text, teller_confidence=conf)
    req = build_request(session.config, CallClass.RUMOUR_DISTORT, turn_index=T, actor_id=job.subject_id, context=ctx,
                        json_schema=to_lm_schema(RumourDistortion), ctx=ctx)
    resp = await client.call(req, RumourDistortion)
    if resp.parse_status != "ok":
        return B.JobResult(job=job, failed=True, calls=tuple(calls))
    return B.JobResult(job=job, answer=RumourDistortion.model_validate(resp.parsed), calls=tuple(calls))


def commit(tx, job, result, at, turn_index):
    from ..audit.log import repair
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    from ..mind.mind import close_loop, learn, open_loop
    from ..world.rumours import retell
    from ..lanes.calllog import record
    for q, r in result.calls:
        record(tx, q, r)
    if result.failed or result.answer is None:
        return []
    first = tx.query_one("SELECT COALESCE(MAX(seq),0) FROM events")[0]
    if job.kind == "retelling":
        retell(tx, job.rumour_id, job.subject_id, result.answer, at, turn_index)
        from ..action._impl_p5b import _events_since
        return _events_since(tx, first)
    out, H = result.answer["output"], result.answer["handles"]
    actor = job.subject_id
    ref = tx.commit_event(Event(type=EventType.REFLECTION, writer="mind.mind", at=at, turn_index=turn_index, actor_id=actor,
                                origin="sim", payload={"actor_id": actor, "request_key": job.request_key,
                                                       "output": out.model_dump(mode="json"), "handles": H}))
    cause = ref.event_id

    def drop(item, index, bad):
        repair(tx, "hallucinated_ref", None, "BG-04", {"actor_id": actor, "item": item, "index": index, "ref": bad}, turn_index, at)

    for i, g in enumerate(out.goals_add):
        if g.kind in ("promise_made", "promise_owed"):
            continue
        if g.subject is None:
            subj = []
        elif g.subject.startswith("P") and g.subject in H:
            subj = [H[g.subject]]
        else:
            drop("goal", i, g.subject)
            continue
        open_loop(tx, actor, g.kind, g.text, subj, g.strength, cause, at, turn_index)
    for i, c in enumerate(out.loops_close):
        lid = H.get(c.loop) if c.loop.startswith("L") else None
        st = tx.query_one("SELECT status FROM open_loops WHERE loop_id=?", (lid,)) if lid else None
        if st is None or st[0] != "open":
            drop("loop_close", i, c.loop)
            continue
        close_loop(tx, lid, c.status, cause, at, turn_index)
    if out.lesson is not None:
        reg = {c.id for c in tx.canon.by_kind.get("cue", {}).values()}
        kept = [t for t in out.lesson.cue_tags if t in reg]
        if not kept:
            drop("lesson", 0, out.lesson.cue_tags[0])
        else:
            learn(tx, actor, kept, out.lesson.text, "", "", cause, at, turn_index)
    if out.plan_goal:
        old = tx.query_one("SELECT standing_orders FROM plans WHERE actor_id=?", (actor,))
        orders = json.loads(old[0]) if old else []
        steps = list(out.plan_steps)
        tx.commit_event(Event(type=EventType.PLAN_CHANGE, writer="mind.actor", at=at, turn_index=turn_index, actor_id=actor,
                              cause_event_id=cause, origin="sim",
                              payload={"actor_id": actor, "goal_text": out.plan_goal, "steps": steps},
                              writes=[WriteRecord(op=WriteOp.UPSERT, table="plans", key={"actor_id": actor},
                                                  values={"actor_id": actor, "goal_text": out.plan_goal, "steps": steps,
                                                          "standing_orders": orders, "updated_at": at}),
                                      WriteRecord(op=WriteOp.UPDATE, table="actors", key={"actor_id": actor},
                                                  values={"goal_text": out.plan_goal})]))
    from ..action._impl_p5b import _events_since
    return _events_since(tx, first)


class BackgroundRunner:
    def __init__(self):
        self._task = None
        self._tried = set()
        self._tried_T = None

    @property
    def running(self):
        return self._task is not None and not self._task.done()

    def _untried(self, store, T):
        if self._tried_T != T:
            self._tried, self._tried_T = set(), T
        return [j for j in _B().pending(store, T) if j.request_key not in self._tried]

    async def _one(self, session, job, T):
        from ..kernel.clock import now
        try:
            res = await _B().run_job(session, job)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001  a failed job is committed as nothing
            log.warning("background job %s failed", job.request_key, exc_info=True)
            self._tried.add(job.request_key)
            return
        self._tried.add(job.request_key)
        with session.store.transaction() as tx:
            _B().commit(tx, job, res, now(tx), T)

    def start(self, session):
        if self.running:
            return
        self._task = asyncio.create_task(self._loop(session))

    async def _loop(self, session):
        T = _turn(session.store)
        for job in self._untried(session.store, T):
            await self._one(session, job, T)

    async def catch_up(self, session, progress=None):
        t = self._task
        if t is not None:
            try:
                await t
            except asyncio.CancelledError:
                if asyncio.current_task().cancelling():
                    raise
            except Exception:  # noqa: BLE001
                log.warning("background task failed", exc_info=True)
            self._task = None
        T = _turn(session.store)
        todo = self._untried(session.store, T)
        for i, job in enumerate(todo):
            if progress is not None:
                r = progress(i, len(todo))
                if hasattr(r, "__await__"):
                    await r
            await self._one(session, job, T)

    async def cancel(self):
        t = self._task
        self._task = None
        if t is not None and not t.done():
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
            except Exception:  # noqa: BLE001
                log.warning("background task failed", exc_info=True)
        self._tried, self._tried_T = set(), None
