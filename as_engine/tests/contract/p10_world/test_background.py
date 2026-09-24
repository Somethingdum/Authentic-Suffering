"""The quiet hours (P10): reflection and retelling between turns. Rules BG-01..07, INFO-06
(service/background.py; the hooks in service/game_service.py, cli.py and service/replay.py).

People think between moments, and the world decides who does: someone who lived through something
that mattered, or who slept on an ordinary day. The player's reading speed decides nothing: every
thought a turn boundary owes is finished before the next move, and nothing is thought twice.
"""

from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path

import pytest

from as_engine.contracts.common import CallClass, OpenLoopKind
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.contracts.mind import (
    LessonWrite,
    LoopClose,
    LoopWrite,
    ReflectionOutput,
    RumourDistortion,
)
from as_engine.contracts.settings import RulesConfig
from as_engine.kernel import clock
from as_engine.kernel.hashing import full_state_hash
from as_engine.mind import mind
from as_engine.physical import bodies
from as_engine.service import background as bg
from as_engine.world import rumours

pytestmark = pytest.mark.phase(10)

H = 3_600_000
DAY = 24 * H
TESTS = Path(__file__).resolve().parents[2]
SCENARIO = TESTS / "fixtures" / "scenarios" / "metal_fence.yaml"
PACKS = TESTS.parent.parent / "as_content" / "packs"

REFLECTED = {"goals_add": [], "loops_close": [], "lesson": None,
             "plan_goal": "Keep the back door barred at night", "plan_steps": ["Find a bar for the door"]}


# --------------------------------------------------------------------------- helpers
def now(w) -> int:
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def turn(w) -> int:
    return w.store.query_one("SELECT turn_index FROM world_clock")[0]


def next_turn(w, hours: float = 1.0) -> int:
    """Stands in for a played turn: time moves on and the turn number goes up (kernel.clock)."""
    with w.store.transaction() as tx:
        clock.advance_event(tx, now(w) + int(hours * H), "test")
        clock.begin_turn(tx, turn(w) + 1)
    return turn(w)


def episode(w, who: str, *, salience: int = 20, anchor: int = 0, at: int | None = None,
            summary: str | None = None) -> str:
    """One memory for ``who`` in the current turn, as mind.memory writes it after a turn."""
    at = now(w) if at is None else at
    t = turn(w)
    with w.store.transaction() as tx:
        eid = tx.mint("epi")
        values = {"episode_id": eid, "holder_id": w.id(who), "at": at, "turn_index": t, "place_id": None,
                  "summary": summary or f"Something {who} saw at {at}.", "salience": salience,
                  "percept_ids": [], "subject_ids": [], "anchor": anchor, "decayed": 0}
        tx.commit_event(Event(type=EventType.EPISODE_WRITTEN, writer="mind.memory", at=at, turn_index=t,
                              actor_id=w.id(who), payload={"episode_id": eid, "holder_id": w.id(who),
                                                           "salience": salience, "anchor": anchor},
                              writes=[WriteRecord(op=WriteOp.INSERT, table="episodes", key={"episode_id": eid},
                                                  values=values)]))
    return eid


def slept(w, who: str, woke_at: int) -> None:
    """A night's sleep ending at ``woke_at`` (the routine's waking refreshes fatigue)."""
    with w.store.transaction() as tx:
        bodies.refresh_need(tx, w.id(who), "fatigue", woke_at, None, turn(w))


def dies(w, who: str) -> None:
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.DEATH, writer="physical.bodies", at=now(w), turn_index=turn(w),
                              actor_id=w.id(who), payload={"body_id": w.id(who)},
                              writes=[WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": w.id(who)},
                                                  values={"alive": 0, "dead_at": now(w)})]))


def reflection(w, who: str, key: str) -> bg.Job:
    return bg.Job(kind="reflection", subject_id=w.id(who), rumour_id=None, request_key=f"reflection:{w.id(who)}:{key}")


def retelling(w, who: str, rumour_id: str) -> bg.Job:
    return bg.Job(kind="retelling", subject_id=w.id(who), rumour_id=rumour_id,
                  request_key=f"retelling:{w.id(who)}:{rumour_id}")


def events_of(w, type_: str) -> list[dict]:
    out = []
    for r in w.store.query("SELECT * FROM events WHERE type = ? ORDER BY seq", (type_,)):
        d = dict(r)
        d["payload"] = json.loads(d["payload"])
        out.append(d)
    return out


def run_and_commit(w, job: bg.Job) -> list:
    """BG-03 then BG-04, as the runner does it."""
    s = w.session()
    res = asyncio.run(bg.run_job(s, job))
    with w.store.transaction() as tx:
        return bg.commit(tx, job, res, clock.now(tx), turn(w))


def seed(w, holder: str, about: str, claim: str = "lied") -> str:
    with w.store.transaction() as tx:
        return rumours.seed(tx, w.id(holder), w.id(about), claim, now(w), turn(w), None)


def lm_calls(w) -> int:
    return w.store.query_one("SELECT COUNT(*) FROM lm_calls")[0]


# =========================================================================== BG-02 who reflects
def test_a_material_experience_is_reflected_on(scenario):
    """BG-02 (AC12): a new episode at or above R.material_salience makes a reflection; the key
    names the newest such episode."""
    w = scenario("metal_fence")
    T = next_turn(w)
    t = now(w)
    episode(w, "june", salience=20, at=t)
    episode(w, "june", salience=60, at=t + 1000)
    e = episode(w, "june", salience=75, at=t + 2000)
    episode(w, "june", salience=10, at=t + 3000)
    assert bg.jobs(w.store, T) == [reflection(w, "june", f"m:{e}")]


def test_an_anchor_memory_is_material_whatever_its_salience(scenario):
    """BG-02: anchor 1 (a bonded one dead, MEM-06) counts as material at any salience."""
    w = scenario("metal_fence")
    T = next_turn(w)
    e = episode(w, "mara", salience=5, anchor=1)
    assert bg.jobs(w.store, T) == [reflection(w, "mara", f"m:{e}")]


def test_an_ordinary_day_waits_for_a_nights_sleep(scenario):
    """BG-02 rest: at least R.rest_min_episodes new episodes AND a sleep that ended after the
    first of them. Time spent reading makes no one rested."""
    w = scenario("metal_fence")
    T = next_turn(w)
    t = now(w)
    for i in range(3):
        episode(w, "june", at=t + i * H)
    assert bg.jobs(w.store, T) == []
    slept(w, "june", t + H // 2)                 # a nap between the first and second: not after the first
    assert bg.jobs(w.store, T) == [reflection(w, "june", f"s:{t + H // 2}")]
    slept(w, "june", t + 10 * H)                 # the key is the newest sleep
    assert bg.jobs(w.store, T) == [reflection(w, "june", f"s:{t + 10 * H}")]


def test_a_sleep_before_the_day_began_does_not_count(scenario):
    """BG-02 rest: the sleep must end after the oldest new episode (strictly)."""
    w = scenario("metal_fence")
    T = next_turn(w)
    t = now(w)
    slept(w, "june", t)
    for i in range(3):
        episode(w, "june", at=t + i * H)
    assert bg.jobs(w.store, T) == []


def test_two_ordinary_memories_are_not_enough(scenario):
    w = scenario("metal_fence")
    T = next_turn(w)
    t = now(w)
    episode(w, "june", at=t)
    episode(w, "june", at=t + H)
    slept(w, "june", t + 10 * H)
    assert bg.jobs(w.store, T) == []


def test_the_player_and_the_dead_do_not_reflect(scenario):
    """BG-02: only living people whose controller is not 'human'."""
    w = scenario("metal_fence")
    T = next_turn(w)
    episode(w, "pc", salience=90)
    episode(w, "nita", salience=90)
    dies(w, "nita")
    assert bg.jobs(w.store, T) == []


def test_at_most_two_the_freshest_first(scenario):
    """BG-02: sorted by the newest new episode's at (descending), then actor id; at most
    R.max_reflections."""
    w = scenario("metal_fence")
    T = next_turn(w)
    t = now(w)
    ea = episode(w, "alice", salience=70, at=t + 1000)
    ej = episode(w, "june", salience=70, at=t + 3000)
    em = episode(w, "mara", salience=70, at=t + 3000)
    tie = sorted([(w.id("june"), reflection(w, "june", f"m:{ej}")), (w.id("mara"), reflection(w, "mara", f"m:{em}"))])
    assert bg.jobs(w.store, T) == [j for _i, j in tie]
    assert w.store.rules.background.max_reflections == 2
    assert reflection(w, "alice", f"m:{ea}") not in bg.jobs(w.store, T)


def test_the_numbers_are_the_runs_rules(scenario):
    """BG-02: R = RulesConfig.background of the run (frozen with it)."""
    rules = RulesConfig(background={"max_reflections": 3, "material_salience": 80})
    w = scenario("metal_fence", rules=rules)
    T = next_turn(w)
    t = now(w)
    episode(w, "alice", salience=80, at=t + 1000)
    episode(w, "june", salience=79, at=t + 2000)
    episode(w, "mara", salience=85, at=t + 3000)
    episode(w, "nita", salience=90, at=t + 4000)
    assert [j.subject_id for j in bg.jobs(w.store, T)] == [w.id("nita"), w.id("mara"), w.id("alice")]


# =========================================================================== BG-02 the plan holds
def test_the_plan_does_not_change_while_it_is_carried_out(scenario):
    """BG-02 / BG-07: the boundary's own commits are ignored, so committing the first job does not
    let a third person slide into the plan; pending() is the plan minus what is done."""
    w = scenario("metal_fence")
    T = next_turn(w)
    t = now(w)
    episode(w, "alice", salience=70, at=t + 1000)
    episode(w, "june", salience=70, at=t + 2000)
    episode(w, "mara", salience=70, at=t + 3000)
    plan = bg.jobs(w.store, T)
    assert [j.subject_id for j in plan] == [w.id("mara"), w.id("june")]
    assert bg.pending(w.store, T) == plan
    run_and_commit(w, plan[0])
    assert bg.jobs(w.store, T) == plan
    assert bg.pending(w.store, T) == plan[1:]
    run_and_commit(w, plan[1])
    assert bg.jobs(w.store, T) == plan and bg.pending(w.store, T) == []


def test_what_was_reflected_on_is_not_new_at_the_next_boundary(scenario):
    """BG-02: after a REFLECTION, only episodes of later turns are new; the one left out by the
    cap is still owed."""
    w = scenario("metal_fence")
    T = next_turn(w)
    t = now(w)
    ea = episode(w, "alice", salience=70, at=t + 1000)
    episode(w, "june", salience=70, at=t + 2000)
    episode(w, "mara", salience=70, at=t + 3000)
    for j in bg.jobs(w.store, T):
        run_and_commit(w, j)
    T2 = next_turn(w)
    assert bg.jobs(w.store, T2) == [reflection(w, "alice", f"m:{ea}")]
    e = episode(w, "june", salience=95)
    assert bg.jobs(w.store, T2) == [reflection(w, "june", f"m:{e}"), reflection(w, "alice", f"m:{ea}")]


def test_rest_counts_only_a_sleep_after_the_last_reflection_and_the_new_day(scenario):
    """BG-02 rest after a reflection: the sleep must end after the reflection AND after the oldest
    new episode."""
    w = scenario("metal_fence")
    T = next_turn(w)
    episode(w, "june", salience=70)
    run_and_commit(w, bg.jobs(w.store, T)[0])
    A = events_of(w, "REFLECTION")[-1]["at"]
    T2 = next_turn(w, hours=1)
    slept(w, "june", A + H // 2)                 # after the reflection, before the new day
    t = now(w)
    for i in range(3):
        episode(w, "june", at=t + i * H)
    assert bg.jobs(w.store, T2) == []
    slept(w, "june", t + 12 * H)
    assert bg.jobs(w.store, T2) == [reflection(w, "june", f"s:{t + 12 * H}")]


# =========================================================================== BG-02 retelling
def test_fresh_rumours_are_retold_once_by_each_holder(scenario):
    """BG-02 retelling: a holder with confidence >= 1 of a rumour younger than rumour_quiet_days
    retells it once; the plan holds after the retelling is committed."""
    w = scenario("metal_fence")
    T = next_turn(w)
    rid = seed(w, "mara", "stranger", "lied")
    assert bg.jobs(w.store, T) == [retelling(w, "mara", rid)]
    run_and_commit(w, retelling(w, "mara", rid))
    assert bg.jobs(w.store, T) == [retelling(w, "mara", rid)]
    assert bg.pending(w.store, T) == []
    T2 = next_turn(w)
    assert bg.jobs(w.store, T2) == []


def test_at_most_four_retellings_by_holder_id_and_old_talk_is_not_retold(scenario):
    """BG-02: holders by id, at most R.max_retellings; created_at older than rumour_quiet_days
    days is no longer passed on. Reflections come before retellings."""
    w = scenario("metal_fence")
    T = next_turn(w)
    rid = seed(w, "mara", "pc", "lied")
    with w.store.transaction() as tx:
        for x in ("june", "alice", "nita", "stranger"):
            rumours.spread_one(tx, rid, w.id("mara"), w.id(x), now(w), T, None)
    who = sorted(w.id(x) for x in ("mara", "june", "alice", "nita", "stranger"))[:4]
    assert [j.subject_id for j in bg.jobs(w.store, T)] == who
    e = episode(w, "june", salience=70)
    assert bg.jobs(w.store, T)[0] == reflection(w, "june", f"m:{e}")
    with w.store.transaction() as tx:
        clock.advance_event(tx, now(w) + 14 * DAY + 1, "test")
    assert bg.jobs(w.store, T) == [reflection(w, "june", f"m:{e}")]


# =========================================================================== BG-03 asking
def test_a_reflection_is_asked_with_the_actors_own_packet(scenario, fake):
    """BG-03: one REFLECTION call for the actor, turn T, with its WARM packet and the newest
    R.max_episodes new episodes (oldest first); nothing is written."""
    w = scenario("metal_fence")
    T = next_turn(w)
    t = now(w)
    names = [f"June remembers moment {i:02d}." for i in range(11)]
    for i, text in enumerate(names):
        episode(w, "june", salience=70 if i == 5 else 20, at=t + i * 1000, summary=text)
    fake.script(CallClass.REFLECTION, REFLECTED, actor_id=w.id("june"))
    before = w.store.query_one("SELECT COUNT(*) FROM events")[0]
    job = bg.jobs(w.store, T)[0]
    res = asyncio.run(bg.run_job(w.session(), job))
    assert w.store.query_one("SELECT COUNT(*) FROM events")[0] == before
    assert res.job == job and not res.failed
    out = res.answer["output"]
    assert isinstance(out, ReflectionOutput) and out.plan_goal == REFLECTED["plan_goal"]
    [req] = fake.calls(CallClass.REFLECTION)
    assert req.actor_id == w.id("june") and req.turn_index == T
    assert req.context.recent_episodes == names[-8:]
    assert req.context.packet.actor_id == w.id("june")
    assert res.answer["handles"] == dict(req.context.packet.handles)
    assert [(q.call_class, r.parse_status) for q, r in res.calls] == [(CallClass.REFLECTION, "ok")]


def test_a_broken_answer_gets_one_repair(scenario, fake):
    """BG-03: call_with_repair — one repair call; still broken -> failed, and both calls are in
    JobResult.calls."""
    w = scenario("metal_fence")
    T = next_turn(w)
    episode(w, "june", salience=70)
    job = bg.jobs(w.store, T)[0]
    fake.fail(CallClass.REFLECTION, "grammar_fail")
    fake.script(CallClass.INTENT_REPAIR, REFLECTED)
    res = asyncio.run(bg.run_job(w.session(), job))
    assert not res.failed and res.answer["output"].plan_goal == REFLECTED["plan_goal"]
    assert [r.parse_status for _q, r in res.calls] == ["grammar_fail", "ok"]
    fake.fail(CallClass.REFLECTION, "grammar_fail")
    fake.fail(CallClass.INTENT_REPAIR, "schema_fail")
    res = asyncio.run(bg.run_job(w.session(), job))
    assert res.failed and res.answer is None and len(res.calls) == 2


def test_a_retelling_is_asked_in_the_holders_own_words(scenario, fake):
    """BG-03 retelling: RumourContext(teller_identity = display_name, claim_text = the claim in the
    holder's words for the subject, teller_confidence); no repair."""
    w = scenario("metal_fence")
    T = next_turn(w)
    rid = seed(w, "nita", "stranger", "lied")
    fake.fail(CallClass.RUMOUR_DISTORT, "grammar_fail")
    res = asyncio.run(bg.run_job(w.session(), retelling(w, "nita", rid)))
    assert res.failed and len(res.calls) == 1
    [req] = fake.calls(CallClass.RUMOUR_DISTORT)
    assert req.actor_id == w.id("nita") and req.turn_index == T
    assert req.context.teller_identity == "Nita Reyes"
    assert req.context.claim_text == "The thin man who watches the back fence lied to people here."
    assert req.context.teller_confidence == 3


# =========================================================================== BG-04 committing
def test_a_reflection_lands_first_and_causes_the_rest(scenario):
    """BG-04: REFLECTION (writer mind.mind, origin sim, no writes) first; then goals, closed loops,
    the lesson and the plan, each caused by it; dropped items logged as hallucinated_ref."""
    w = scenario("metal_fence")
    T = next_turn(w)
    episode(w, "mara", salience=70)
    job = bg.jobs(w.store, T)[0]
    at = now(w)
    with w.store.transaction() as tx:
        l1 = mind.open_loop(tx, w.id("mara"), OpenLoopKind.FEAR, "The thin man at the fence", [w.id("stranger")], 2,
                            None, at, T)
        l2 = mind.open_loop(tx, w.id("mara"), OpenLoopKind.QUESTION, "Where Nita goes at night", [w.id("nita")], 1,
                            None, at, T)
        mind.close_loop(tx, l2, "fulfilled", None, at, T)
    out = ReflectionOutput(
        goals_add=[LoopWrite(kind="grudge", text="That man keeps watching us", subject="P1", strength=2, because="S1"),
                   LoopWrite(kind="promise_made", text="I will keep Eli inside", subject=None, strength=3, because="S1"),
                   LoopWrite(kind="question", text="Who sent him here", subject="P9", strength=1, because="S1")],
        loops_close=[LoopClose(loop="L1", status="abandoned", because="S1"),
                     LoopClose(loop="L2", status="broken", because="S1")],
        lesson=LessonWrite(cue_tags=["made_up_cue", "loud_noise"], text="Noise at night brings trouble", because="S1"),
        plan_goal="Watch the back as well as the front", plan_steps=["Ask Nita about the fence"])
    handles = {"P1": w.id("stranger"), "L1": l1, "L2": l2}
    res = bg.JobResult(job=job, answer={"output": out, "handles": handles})
    with w.store.transaction() as tx:
        evs = bg.commit(tx, job, res, at, T)
    types = [str(getattr(e.type, "value", e.type)) for e in evs]
    assert types == ["REFLECTION", "LOOP_OPENED", "LOOP_CLOSED", "LESSON_LEARNED", "PLAN_CHANGE"]
    [ref] = events_of(w, "REFLECTION")
    assert ref["writer"] == "mind.mind" and ref["origin"] == "sim" and ref["actor_id"] == w.id("mara")
    assert json.loads(ref["state_delta"]) == [] and ref["turn_index"] == T and ref["at"] == at
    assert ref["payload"] == {"actor_id": w.id("mara"), "request_key": job.request_key,
                              "output": out.model_dump(mode="json"), "handles": handles}
    assert all(e.cause_event_id == ref["event_id"] for e in evs[1:])
    grudge = w.store.query_one("SELECT subject_ids, text FROM open_loops WHERE holder_id = ? AND kind = 'grudge'",
                               (w.id("mara"),))
    assert json.loads(grudge[0]) == [w.id("stranger")]
    assert w.store.query_one("SELECT COUNT(*) FROM open_loops WHERE kind IN ('promise_made', 'question') "
                             "AND status = 'open' AND holder_id = ?", (w.id("mara"),))[0] == 0
    assert w.store.query_one("SELECT status FROM open_loops WHERE loop_id = ?", (l1,))[0] == "abandoned"
    assert w.store.query_one("SELECT status FROM open_loops WHERE loop_id = ?", (l2,))[0] == "fulfilled"
    lesson = evs[3].payload
    assert lesson["cue_tags"] == ["loud_noise"] and lesson["text"] == "Noise at night brings trouble"
    assert json.loads(w.store.query_one("SELECT cue_tags FROM lessons WHERE lesson_id = ?", (lesson["lesson_id"],))[0]) == ["loud_noise"]
    plan = w.store.query_one("SELECT goal_text, steps, standing_orders FROM plans WHERE actor_id = ?", (w.id("mara"),))
    assert plan[0] == "Watch the back as well as the front" and json.loads(plan[1]) == ["Ask Nita about the fence"]
    assert json.loads(plan[2]) == [{"response": "find the source and cover it", "trigger": "loud_noise"}]
    assert w.store.query_one("SELECT goal_text FROM actors WHERE actor_id = ?", (w.id("mara"),))[0] == plan[0]
    logged = [json.loads(r[0]) for r in w.store.query(
        "SELECT detail FROM error_repair_log WHERE kind = 'hallucinated_ref' AND rule_id = 'BG-04' ORDER BY entry_id")]
    assert logged == [{"actor_id": w.id("mara"), "item": "goal", "index": 2, "ref": "P9"},
                      {"actor_id": w.id("mara"), "item": "loop_close", "index": 1, "ref": "L2"}]


def test_nobody_in_particular_and_no_known_cue(scenario):
    """BG-04: a goal about nobody opens with subject_ids []; a lesson with no registry cue left is
    dropped (ref = its first tag); a plan for someone with none starts with no standing orders."""
    w = scenario("metal_fence")
    T = next_turn(w)
    episode(w, "june", salience=70)
    job = bg.jobs(w.store, T)[0]
    lessons = w.store.query_one("SELECT COUNT(*) FROM lessons WHERE holder_id = ?", (w.id("june"),))[0]
    out = ReflectionOutput(goals_add=[LoopWrite(kind="goal", text="Get more sleep", subject=None, strength=1, because="S1")],
                           lesson=LessonWrite(cue_tags=["not_a_cue"], text="Nothing ever changes here", because="S1"),
                           plan_goal="Count the cans again", plan_steps=[])
    with w.store.transaction() as tx:
        evs = bg.commit(tx, job, bg.JobResult(job=job, answer={"output": out, "handles": {}}), now(w), T)
    assert [str(getattr(e.type, "value", e.type)) for e in evs] == ["REFLECTION", "LOOP_OPENED", "PLAN_CHANGE"]
    assert json.loads(w.store.query_one("SELECT subject_ids FROM open_loops WHERE holder_id = ?", (w.id("june"),))[0]) == []
    assert w.store.query_one("SELECT COUNT(*) FROM lessons WHERE holder_id = ?", (w.id("june"),))[0] == lessons
    assert json.loads(w.store.query_one("SELECT standing_orders FROM plans WHERE actor_id = ?", (w.id("june"),))[0]) == []
    [d] = [json.loads(r[0]) for r in w.store.query("SELECT detail FROM error_repair_log WHERE rule_id = 'BG-04'")]
    assert d == {"actor_id": w.id("june"), "item": "lesson", "index": 0, "ref": "not_a_cue"}


def test_every_call_is_logged_even_a_failed_one(scenario, fake):
    """BG-04: the calls are recorded first (turn T); a failed job writes nothing else."""
    w = scenario("metal_fence")
    T = next_turn(w)
    episode(w, "june", salience=70)
    job = bg.jobs(w.store, T)[0]
    fake.fail(CallClass.REFLECTION, "grammar_fail")
    fake.fail(CallClass.INTENT_REPAIR, "schema_fail")
    res = asyncio.run(bg.run_job(w.session(), job))
    calls, events = lm_calls(w), w.store.query_one("SELECT COUNT(*) FROM events")[0]
    with w.store.transaction() as tx:
        assert bg.commit(tx, job, res, now(w), T) == []
    assert lm_calls(w) == calls + 2
    assert w.store.query_one("SELECT COUNT(*) FROM events")[0] == events
    assert {r[0] for r in w.store.query("SELECT DISTINCT turn_index FROM lm_calls WHERE call_class IN "
                                        "('reflection', 'intent_repair')")} == {T}
    assert bg.pending(w.store, T) == [job]


def test_a_retelling_may_twist_the_story_but_not_invent_who_is_in_it(scenario):
    """INFO-06: a retold claim naming a living person by a name the holder does not use is
    refused (kept as operation 'none', text null); the holder's own names pass."""
    w = scenario("metal_fence")
    T = next_turn(w)
    rid = seed(w, "nita", "pc", "lied")
    with w.store.transaction() as tx:
        rumours.spread_one(tx, rid, w.id("nita"), w.id("mara"), now(w), T, None)
    bad = RumourDistortion(operation="shift_attribution", retold_claim="Dale Pruitt says Owen lied to people here.")
    good = RumourDistortion(operation="sharpen_emotion", retold_claim="Owen lied to June's face, and he smiled.")
    with w.store.transaction() as tx:
        e1 = bg.commit(tx, retelling(w, "nita", rid), bg.JobResult(job=retelling(w, "nita", rid), answer=bad), now(w), T)
        e2 = bg.commit(tx, retelling(w, "mara", rid), bg.JobResult(job=retelling(w, "mara", rid), answer=good), now(w), T)
    assert len(e1) == 1 and len(e2) == 1
    dist = json.loads(w.store.query_one("SELECT distortions FROM rumours WHERE rumour_id = ?", (rid,))[0])
    assert dist == sorted([{"holder_id": w.id("nita"), "operation": "none", "text": None},
                           {"holder_id": w.id("mara"), "operation": "sharpen_emotion",
                            "text": "Owen lied to June's face, and he smiled."}], key=lambda d: d["holder_id"])
    assert [e["payload"] for e in events_of(w, "RUMOUR_DISTORTED")] == [
        {"rumour_id": rid, "holder_id": w.id("nita"), "operation": "none", "text": None},
        {"rumour_id": rid, "holder_id": w.id("mara"), "operation": "sharpen_emotion",
         "text": "Owen lied to June's face, and he smiled."}]


# =========================================================================== BG-01 / BG-07 the runner
def _two_owed(w):
    T = next_turn(w)
    t = now(w)
    episode(w, "june", salience=70, at=t + 1000)
    episode(w, "mara", salience=70, at=t + 2000)
    rid = seed(w, "nita", "stranger", "lied")
    return T, rid


def test_catch_up_finishes_the_boundary(scenario):
    """BG-01: catch_up runs and commits every pending job, in order, with progress(done, total)
    before each."""
    w = scenario("metal_fence")
    T, rid = _two_owed(w)
    plan = bg.pending(w.store, T)
    assert [j.kind for j in plan] == ["reflection", "reflection", "retelling"]
    seen = []
    runner = bg.BackgroundRunner()
    asyncio.run(runner.catch_up(w.session(), lambda done, total: seen.append((done, total))))
    assert seen == [(0, 3), (1, 3), (2, 3)]
    assert bg.pending(w.store, T) == []
    assert [e["payload"]["request_key"] for e in events_of(w, "REFLECTION")] == [j.request_key for j in plan[:2]]
    assert [e["payload"]["holder_id"] for e in events_of(w, "RUMOUR_DISTORTED")] == [w.id("nita")]
    assert not runner.running


def test_reading_speed_changes_nothing(scenario):
    """BG-07: a slow reader (the runner finishes while they read) and a fast one (catch_up does it
    all) end the boundary in the same state."""
    slow, fast = scenario("metal_fence"), scenario("metal_fence")
    for w in (slow, fast):
        _two_owed(w)

    async def reader_takes_their_time():
        r = bg.BackgroundRunner()
        r.start(slow.session())
        assert r.running
        while r.running:
            await asyncio.sleep(0.005)
        await r.catch_up(slow.session())

    asyncio.run(reader_takes_their_time())
    asyncio.run(bg.BackgroundRunner().catch_up(fast.session()))
    assert full_state_hash(slow.store) == full_state_hash(fast.store)
    assert lm_calls(slow) == lm_calls(fast) == 3


def test_a_cancelled_job_leaves_nothing_and_is_finished_later(scenario, fake):
    """BG-01: cancel() mid-call commits nothing of that job; the next catch_up runs it."""
    w = scenario("metal_fence")
    T, _rid = _two_owed(w)
    fake.latency_ms = 2000

    async def start_then_cancel():
        r = bg.BackgroundRunner()
        r.start(w.session())
        await asyncio.sleep(0.2)
        await r.cancel()
        assert not r.running
        return r

    r = asyncio.run(start_then_cancel())
    assert events_of(w, "REFLECTION") == [] and lm_calls(w) == 0
    fake.latency_ms = 1
    asyncio.run(r.catch_up(w.session()))
    assert bg.pending(w.store, T) == [] and len(events_of(w, "REFLECTION")) == 2


def test_a_failed_job_is_not_asked_twice_at_one_boundary(scenario, fake):
    """BG-01: a job whose run_job finished (here: failed) is tried; catch_up skips it. A new
    runner (after a load) may ask again."""
    w = scenario("metal_fence")
    T = next_turn(w)
    episode(w, "june", salience=70)
    fake.fail(CallClass.REFLECTION, "grammar_fail")
    fake.fail(CallClass.INTENT_REPAIR, "schema_fail")

    async def read_then_move_on(r):
        r.start(w.session())
        while r.running:
            await asyncio.sleep(0.005)
        await r.catch_up(w.session())

    r = bg.BackgroundRunner()
    asyncio.run(read_then_move_on(r))
    assert lm_calls(w) == 2 and events_of(w, "REFLECTION") == []
    assert bg.pending(w.store, T) != []
    asyncio.run(bg.BackgroundRunner().catch_up(w.session()))
    assert lm_calls(w) == 3 and len(events_of(w, "REFLECTION")) == 1


def test_a_job_that_raises_is_skipped(scenario, monkeypatch):
    """BG-01: an exception from run_job (other than cancellation) is logged and the job skipped;
    the others still run."""
    w = scenario("metal_fence")
    T, _rid = _two_owed(w)
    real = bg.run_job

    async def boom(session, job):
        if job.subject_id == w.id("mara"):
            raise RuntimeError("the model fell over")
        return await real(session, job)

    monkeypatch.setattr(bg, "run_job", boom)
    asyncio.run(bg.BackgroundRunner().catch_up(w.session()))
    assert [e["actor_id"] for e in events_of(w, "REFLECTION")] == [w.id("june")]
    assert len(events_of(w, "RUMOUR_DISTORTED")) == 1


# =========================================================================== the hooks
@pytest.fixture
def conf(tmp_path):
    p = tmp_path / "as_config.yaml"
    p.write_text(f"schema: as.config.v1\nruns_dir: {(tmp_path / 'runs').as_posix()}\ncontent_dir: {PACKS.as_posix()}\n",
                 encoding="utf-8")
    return p


def _owed_run(conf, tmp_path):
    """The metal_fence run on disk with a material memory owed at boundary 0: June's."""
    from as_engine.cli import main
    from as_engine.config_loader import load_engine_config
    from as_engine.service.runs import load_run
    from as_engine.testing.fake_lm import FakeTransport

    assert main(["--config", str(conf), "new-scenario", str(SCENARIO), "--fake"]) == 0
    cfg = load_engine_config(str(conf))
    s = load_run(cfg, "owen_marsh_71a", FakeTransport())
    try:
        june = s.store.query_one("SELECT actor_id FROM actors WHERE display_name = 'June Okafor'")[0]
        at = s.store.query_one("SELECT now_ms FROM world_clock")[0]
        with s.store.transaction() as tx:
            eid = tx.mint("epi")
            tx.commit_event(Event(type=EventType.EPISODE_WRITTEN, writer="mind.memory", at=at, turn_index=0, actor_id=june,
                                  payload={"episode_id": eid, "holder_id": june, "salience": 80, "anchor": 0},
                                  writes=[WriteRecord(op=WriteOp.INSERT, table="episodes", key={"episode_id": eid},
                                                      values={"episode_id": eid, "holder_id": june, "at": at, "turn_index": 0,
                                                              "place_id": None, "summary": "The crash at the fence.",
                                                              "salience": 80, "percept_ids": [], "subject_ids": [],
                                                              "anchor": 0, "decayed": 0})]))
        s.store.backup_to(Path(s.run_dir) / "turn0.sqlite")   # the run starts owing it
    finally:
        s.store.close()
    return cfg, june


def _first_seq(store, type_, **where):
    rows = [dict(r) for r in store.query("SELECT seq, turn_index, payload FROM events WHERE type = ? ORDER BY seq", (type_,))]
    for r in rows:
        pl = json.loads(r["payload"])
        if all(pl.get(k) == v for k, v in where.items()):
            return r
    return None


def test_the_terminal_catches_up_before_each_move_and_replay_agrees(conf, tmp_path, capsys, monkeypatch):
    """CLI-03 (P10) + BG-05: the quiet hours owed at the start run before turn 1 (REFLECTION of turn
    0 before turn 1 begins); re-simulating the run re-applies them and every turn matches."""
    from as_engine.cli import main
    from as_engine.kernel.store import Store

    cfg, june = _owed_run(conf, tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO("I watch the front door.\nquit\n"))
    assert main(["--config", str(conf), "play", "owen_marsh_71a", "--fake"]) == 0
    capsys.readouterr()
    st = Store.open(Path(cfg.runs_dir) / "owen_marsh_71a" / "world.sqlite")
    try:
        ref = _first_seq(st, "REFLECTION", actor_id=june)
        start = _first_seq(st, "CLOCK_ADVANCE", reason="turn_start")
        assert ref is not None and ref["turn_index"] == 0 and ref["seq"] < start["seq"]
    finally:
        st.close()
    assert main(["--config", str(conf), "replay", "owen_marsh_71a"]) == 0
    assert capsys.readouterr().out.strip().splitlines() == ["turn 1: same", "1 turns re-simulated: all the same."]


def test_the_next_move_waits_for_the_quiet_hours(conf, tmp_path, monkeypatch):
    """BG-01 through the protocol: turn_submit answers at once; the turn task first finishes what
    the boundary owes (turn_progress stage 0 with background.QUIET_HOURS), then plays the move."""
    from as_engine.service import game_service
    from as_engine.testing.fake_lm import FakeTransport

    cfg, june = _owed_run(conf, tmp_path)
    monkeypatch.setattr(game_service, "_SERVICE", None)
    svc = game_service.GameService(cfg, FakeTransport(), config_path=str(tmp_path / "as_config.yaml"))
    pushed = []

    async def collect(msg):
        pushed.append(msg)

    async def play():
        svc.subscribe(collect)
        await svc.handle({"type": "as_game", "action": "run_load", "run_id": "owen_marsh_71a"})
        replies = await svc.handle({"type": "as_game", "action": "turn_submit", "mode": "do",
                                    "text": "I watch the front door."})
        assert [m["action"] for m in replies] == ["state"]
        await svc.idle()

    try:
        asyncio.run(play())
        st = svc.session.store
        ref = _first_seq(st, "REFLECTION", actor_id=june)
        start = _first_seq(st, "CLOCK_ADVANCE", reason="turn_start")
        assert ref is not None and ref["turn_index"] == 0 and ref["seq"] < start["seq"]
        progress = [m["data"] for m in pushed if m["action"] == "turn_progress"]
        assert progress[0]["stage"] == 0 and progress[0]["label"] == bg.QUIET_HOURS
        assert [p["label"] for p in progress].count(bg.QUIET_HOURS) == 1
    finally:
        if svc.session is not None:
            svc.session.store.close()
