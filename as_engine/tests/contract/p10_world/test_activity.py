"""The models at work, live, under the bar (D-114). PROG-08 (service/progress.py), LANE-11 routing
(lanes/client.py), LANE-10 read from a snapshot (lanes/progress.py stall_window).

A Writer that writes five tokens a second makes a move minutes long; the bar must show the wait is
work — waiting, reading, thinking, writing, for how long, how long quiet — and never who is thinking,
on which model, or how many (PROG-05).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from world_kit import REPO_PACKS

from as_engine.contracts.common import CallClass, Lane
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.contracts.lanes import ChatMessage, LMRequest
from as_engine.contracts.protocol import OUT_MODELS
from as_engine.contracts.settings import EngineConfig, LaneConfig
from as_engine.lanes.client import LaneClient
from as_engine.lanes.progress import CallProgress, stall_window
from as_engine.lanes.transport import HttpTransport
from as_engine.service import background as bg
from as_engine.service import game_service, progress
from as_engine.testing.fake_lm import FakeTransport

pytestmark = pytest.mark.phase(10)

TESTS = Path(__file__).resolve().parents[2]
SCENARIO = TESTS / "fixtures" / "scenarios" / "metal_fence.yaml"
RUN = "owen_marsh_71a"
KEYS = {"job_id", "kind", "phase", "call_s", "quiet_s", "slow", "reading_pct", "stall_in_s"}


class Reporting(FakeTransport):
    """The fake model, reporting progress as a streaming server does: waiting, thinking, writing."""
    sink = None

    async def send(self, lane, request):
        prog = CallProgress(request.call_class, request.lane, expected_s=request.deadline_s)
        if self.sink:
            self.sink(request, prog)
            prog.note_reasoning(3)
            self.sink(request, prog)
            prog.note_text(5)
            self.sink(request, prog)
        return await super().send(lane, request)


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def snap(phase="waiting", lane="A", elapsed=1.0, quiet=0.5, slow=False, processed=0, total=0, progressed=None):
    return {"call_class": "narration", "lane": lane, "phase": phase, "elapsed_s": elapsed, "quiet_s": quiet, "slow": slow,
            "prompt_processed": processed, "prompt_total": total,
            "progressed": phase in ("thinking", "writing") if progressed is None else progressed}


LANES = {Lane.A: LaneConfig(name="a", stall_window_s=300), Lane.B: LaneConfig(name="b", stall_window_s=200)}


# ------------------------------------------------------------------------- PROG-08 activity()


def test_activity_says_what_is_happening_and_nothing_about_who():
    assert progress.activity([]) is None
    a = progress.activity([(snap("waiting", "A", elapsed=40, quiet=40), LANES[Lane.A]),
                           (snap("thinking", "B", elapsed=12, quiet=1.25), LANES[Lane.B])])
    assert a == {"phase": "thinking", "call_s": 40.0, "quiet_s": 1.2, "slow": False, "reading_pct": None,
                 "stall_in_s": 198.8}, "the furthest phase, the longest call, the newest sign of life"
    assert set(a) == KEYS - {"job_id", "kind"}, "never a lane, a call class, a name or a count"
    r = progress.activity([(snap("prefill", "A", processed=300, total=1000, quiet=2), LANES[Lane.A]),
                           (snap("prefill", "A", processed=50, total=100, quiet=9), LANES[Lane.A])])
    assert (r["phase"], r["reading_pct"], r["stall_in_s"]) == ("reading", 50.0, 291.0)
    silent = progress.activity([(snap("waiting", "A", quiet=500, progressed=False), LANES[Lane.A])])
    assert silent["stall_in_s"] is None, "a silent prompt read has no limit unless the owner sets one (LANE-10)"
    assert progress.activity([(snap("writing", slow=True), LANES[Lane.A])])["slow"] is True


def test_the_window_read_from_a_snapshot_is_the_transport_s_own():
    for kw in ({}, {"prefill_progress": "supported"}, {"silent_prefill_window_s": 90.0}):
        lane = LaneConfig(name="a", stall_window_s=200, **kw)
        for move in (lambda p: None, lambda p: p.note_prefill(10, 100), lambda p: p.note_text(3),
                     lambda p: p.note_reasoning(4)):
            p = CallProgress(CallClass.NARRATION, Lane.A)
            move(p)
            assert stall_window(lane, p.snapshot()) == HttpTransport.window(lane, p), kw


def test_the_feed_pushes_on_a_change_and_otherwise_every_two_seconds():
    got, clock = [], Clock()
    feed = progress.ActivityFeed("turn-3", "turn", lambda action, data: got.append((action, data)), LANES, clock=clock)
    one, two = object(), object()
    feed.seen(one, snap("waiting", "A"))
    feed.seen(one, snap("waiting", "A"))                 # same phase, too soon
    clock.t += 2.5
    feed.seen(one, snap("waiting", "A"))                 # the heartbeat
    feed.seen(two, snap("thinking", "B"))                # a change
    feed.seen(one, None)                                 # one ends; still thinking, too soon
    feed.seen(two, None)                                 # nothing in flight: idle
    feed.seen(object(), None)                            # a call it never saw
    assert [(a, d["phase"]) for a, d in got] == [("activity", "waiting"), ("activity", "waiting"),
                                                 ("activity", "thinking"), ("activity", "idle")]
    for _a, d in got:
        OUT_MODELS["activity"].model_validate(d)
        assert set(d) == KEYS and (d["job_id"], d["kind"]) == ("turn-3", "turn")
    assert got[-1][1] == {"job_id": "turn-3", "kind": "turn", "phase": "idle", "call_s": 0.0, "quiet_s": 0.0,
                          "slow": False, "reading_pct": None, "stall_in_s": None}


# ------------------------------------------------------------------------- LANE-11: every client its own calls


async def test_two_clients_on_one_transport_each_see_only_their_own_calls():
    t = Reporting()
    a, b = LaneClient(EngineConfig(), t), LaneClient(EngineConfig(), t)
    seen_a, seen_b = [], []
    a.on_progress = lambda q, s: seen_a.append((q.call_class, s))
    b.on_progress = lambda q, s: seen_b.append((q.call_class, s))
    msgs = [ChatMessage(role="user", content="x")]
    await asyncio.gather(a.call(LMRequest(call_class=CallClass.NARRATION, lane=Lane.A, messages=msgs)),
                         b.call(LMRequest(call_class=CallClass.GUIDE, lane=Lane.B, messages=msgs)))
    assert {c for c, _s in seen_a} == {CallClass.NARRATION} and {c for c, _s in seen_b} == {CallClass.GUIDE}
    assert [s["phase"] for _c, s in seen_a[:-1]] == ["waiting", "thinking", "writing"]
    assert seen_a[-1][1] is None and seen_b[-1][1] is None, "the end of a call is reported as None"
    assert a.live == {} and b.live == {} and t.sink is LaneClient.dispatch


# ------------------------------------------------------------------------- through the service


def scenario_run(tmp_path, *, owed=False):
    from as_engine.cli import main
    from as_engine.config_loader import load_engine_config
    from as_engine.service.runs import load_run

    conf = tmp_path / "as_config.yaml"
    conf.write_text(f"schema: as.config.v1\nruns_dir: {(tmp_path / 'runs').as_posix()}\n"
                    f"content_dir: {REPO_PACKS.as_posix()}\n", encoding="utf-8")
    assert main(["--config", str(conf), "new-scenario", str(SCENARIO), "--fake"]) == 0
    cfg = load_engine_config(str(conf))
    if owed:
        s = load_run(cfg, RUN, FakeTransport())
        try:
            june = s.store.query_one("SELECT actor_id FROM actors WHERE display_name = 'June Okafor'")[0]
            at = s.store.query_one("SELECT now_ms FROM world_clock")[0]
            with s.store.transaction() as tx:
                eid = tx.mint("epi")
                values = {"episode_id": eid, "holder_id": june, "at": at, "turn_index": 0, "place_id": None,
                          "summary": "The crash at the fence.", "salience": 80, "percept_ids": [],
                          "subject_ids": [], "anchor": 0, "decayed": 0}
                tx.commit_event(Event(type=EventType.EPISODE_WRITTEN, writer="mind.memory", at=at, turn_index=0,
                                      actor_id=june, payload={"episode_id": eid, "holder_id": june,
                                                              "salience": 80, "anchor": 0},
                                      writes=[WriteRecord(op=WriteOp.INSERT, table="episodes",
                                                          key={"episode_id": eid}, values=values)]))
        finally:
            s.store.close()
    return cfg


def play_one(cfg, tmp_path):
    svc = game_service.GameService(cfg, Reporting(), config_path=str(tmp_path / "as_config.yaml"))
    pushed = []

    async def collect(m):
        pushed.append(m)
    svc.subscribe(collect)

    async def go():
        await svc.handle({"type": "as_game", "action": "run_load", "run_id": RUN})
        owed = len(bg.pending(svc.session.store, 0))
        start = len(pushed)
        await svc.handle({"type": "as_game", "action": "turn_submit", "mode": "do", "text": "I watch the front door."})
        await svc.idle()
        return owed, pushed[start:]
    try:
        return asyncio.run(go())
    finally:
        svc.session.store.close()


def test_a_turn_shows_its_models_at_work_and_ends_idle_before_its_bar_closes(tmp_path):
    owed, msgs = play_one(scenario_run(tmp_path), tmp_path)
    acts = [m["action"] for m in msgs]
    act = [(i, m["data"]) for i, m in enumerate(msgs) if m["action"] == "activity"]
    assert act, "the models' work is shown"
    for _i, d in act:
        OUT_MODELS["activity"].model_validate(d)
        assert set(d) == KEYS and (d["job_id"], d["kind"]) == ("turn-1", "turn")
    assert {"thinking", "writing"} <= {d["phase"] for _i, d in act}
    done = acts.index("progress_done")
    assert all(i < done for i, _d in act) and act[-1][1]["phase"] == "idle", "it ends idle, before the bar closes"
    assert acts.index("progress_plan") < act[0][0]


def test_the_quiet_hours_show_their_work_under_their_own_bar(tmp_path):
    owed, msgs = play_one(scenario_run(tmp_path, owed=True), tmp_path)
    assert owed == 1
    quiet = [(i, m["data"]) for i, m in enumerate(msgs) if m["action"] == "activity" and m["data"]["kind"] == "quiet_hours"]
    assert quiet and all(d["job_id"] == "quiet_hours-1" for _i, d in quiet)
    ends = [i for i, m in enumerate(msgs) if m["action"] == "progress_done" and m["data"]["kind"] == "quiet_hours"]
    assert ends and all(i < ends[0] for i, _d in quiet), "the job's own client passes its progress on (BG-03)"
