"""The loading bar (P10, progress v2). Rules PROG-01..07 (service/progress.py), CNT-16, and the
GameService and worldgen amendments that feed it.

A long job announces its whole plan — phases and sub-phases, in order — then says where it is,
live; the quips are the content's, and nothing the bar says gives the world away.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest
from world_kit import REPO_PACKS, WORLD_PC

from as_engine.content.pack import load_canon
from as_engine.contracts.common import CallClass
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.contracts.protocol import OUT_MODELS
from as_engine.service import background as bg
from as_engine.service import game_service, progress
from as_engine.testing.fake_lm import FakeTransport
from as_engine.world.worldgen import atlas

pytestmark = pytest.mark.phase(10)

TESTS = Path(__file__).resolve().parents[2]
SCENARIO = TESTS / "fixtures" / "scenarios" / "metal_fence.yaml"
RUN = "owen_marsh_71a"
BAR = ("progress_plan", "progress", "progress_done")
SMALL = {"world_detail": "gotta_go_to_work_soon", "seed": 7, "era": "established"}


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def tracker(kind, *, dev=False):
    got, clock = [], Clock()

    def push(action, data):
        OUT_MODELS[action].model_validate(data)
        got.append((action, data))
    return progress.Tracker(kind, f"{kind}-1", push, dev=dev, clock=clock), got, clock


def run(coro):
    return asyncio.run(coro)


# =========================================================================== PROG-02 plans
def test_every_plan_is_whole_and_in_order():
    """PROG-02: weights sum to 100; a turn's stages map onto its sub-phases in the order the
    pipeline announces them; worldgen's phases are its stages."""
    for kind, phases in progress.PLANS.items():
        assert sum(p.weight for p in phases) == 100, kind
        assert kind in progress.TITLES
        assert len({p.id for p in phases}) == len(phases)
        for p in phases:
            assert len({s.id for s in p.subs}) == len(p.subs)
    turn = progress.PLANS["turn"]
    order = [(p.id, s.id) for p in turn for s in p.subs]
    announced = [0, 1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 16, 17, 14, 15, 19]
    assert [progress.TURN_STAGES[st] for st in announced] == order
    assert set(progress.TURN_STAGES) == set(announced)
    wg = progress.PLANS["worldgen"]
    assert [p.id for p in wg] == [s for s in atlas.STAGES if s != "COMMIT"]
    assert [p.label for p in wg] == [atlas.STAGE_LABELS[p.id] for p in wg]
    assert {p.id: [s.id for s in p.subs] for p in wg if p.subs} == {"WG2": ["history"], "WG6": ["dossiers"]}


def test_no_label_is_engine_talk():
    """UI-CLARITY-01: plain words only."""
    banned = ("packet", "affordance", "percept", "lod", "claim", "intent", "handle", "lane", "schema", "token",
              "stage", "event", "actor", "dossier")
    for phases in progress.PLANS.values():
        for p in phases:
            for label in [p.label] + [s.label for s in p.subs]:
                assert not any(b in label.lower().split() for b in banned), label


# =========================================================================== PROG-03/04 the tracker
def test_the_plan_comes_first_and_whole():
    tr, got, clock = tracker("turn")
    run(tr.plan({"turn": ["Rolling."]}))
    [(action, data)] = got
    assert action == "progress_plan"
    assert data["job_id"] == "turn-1" and data["kind"] == "turn" and data["title"] == progress.TITLES["turn"]
    assert [p["id"] for p in data["phases"]] == [p.id for p in progress.PLANS["turn"]]
    assert data["phases"][0]["subs"][0] == {"id": "check", "label": "Checking the world"}
    assert data["quips"] == {"turn": ["Rolling."]}


def test_where_the_bar_is():
    """PROG-04: pct = earlier weights + this phase's weight x (sub position, or done / total);
    elapsed from the plan; eta once past 5 %; never backwards."""
    tr, got, clock = tracker("worldgen")
    run(tr.plan({}))
    w = {p.id: p.weight for p in progress.PLANS["worldgen"]}
    clock.t += 10
    run(tr.step("WG2"))
    _a, d = got[-1]
    assert (d["phase"], d["phase_index"], d["sub"], d["pct"], d["elapsed_s"]) == ("WG2", 2, None, w["WG0"] + w["WG1"], 10.0)
    assert d["eta_s"] == round(10.0 * (100 - d["pct"]) / d["pct"])
    run(tr.step("WG2", "history", done=1, total=4))
    _a, d = got[-1]
    assert d["pct"] == round(w["WG0"] + w["WG1"] + w["WG2"] / 4, 1)
    assert (d["sub"], d["sub_label"], d["done"], d["total"]) == ("history", "Remembering what happened", 1, 4)
    run(tr.step("WG1"))
    assert got[-1][1]["pct"] == d["pct"], "never backwards"
    clock.t += 5
    run(tr.done(True))
    assert got[-1] == ("progress_done", {"job_id": "worldgen-1", "kind": "worldgen", "ok": True, "elapsed_s": 15.0})


def test_early_on_there_is_no_guess():
    tr, got, clock = tracker("worldgen")
    run(tr.plan({}))
    run(tr.step("WG0"))
    assert got[-1][1]["pct"] == 0 and got[-1][1]["eta_s"] is None


def test_a_turn_says_where_not_how_many():
    """PROG-05: a turn's steps carry no counts; nobody's detail outside developer mode."""
    tr, got, _clock = tracker("turn")
    run(tr.plan({}))
    run(tr.step("minds", "decide", done=2, total=7, detail="Mara, June"))
    d = got[-1][1]
    assert (d["done"], d["total"], d["detail"]) == (None, None, None)
    tr, got, _clock = tracker("turn", dev=True)
    run(tr.plan({}))
    run(tr.step("minds", "decide", detail="Mara, June"))
    assert got[-1][1]["detail"] == "Mara, June"
    tr, got, _clock = tracker("quiet_hours")
    run(tr.plan({}))
    run(tr.step("quiet", "jobs", done=2, total=7, detail="Mara"))
    assert (got[-1][1]["done"], got[-1][1]["total"], got[-1][1]["detail"]) == (2, 7, None)


def test_a_plan_is_a_promise():
    tr, _got, _clock = tracker("turn")
    run(tr.plan({}))
    with pytest.raises(ValueError):
        run(tr.step("dancing"))
    with pytest.raises(ValueError):
        run(tr.step("minds", "dancing"))


# =========================================================================== PROG-06 quips
def test_the_core_quips_cover_every_step(canon):
    """Every plan and every phase has at least three lines (the UI never repeats one of the last
    three); keys only name plans, phases and sub-phases (CNT-16); and no core line just repeats the
    label of its step, which is always on screen beside it."""
    def bare(text):
        return text.rstrip(".…!?").strip().lower()
    for kind, phases in progress.PLANS.items():
        q = progress.quips_for(canon, kind)
        assert len(q.get(kind, [])) >= 3, kind
        for p in phases:
            assert len(q.get(f"{kind}.{p.id}", [])) >= 3, f"{kind}.{p.id}"
        assert all(k == kind or k.startswith(kind + ".") for k in q)
        assert all(0 < len(line) <= 80 for lines in q.values() for line in lines)
        labels = {kind: progress.TITLES[kind]}
        for p in phases:
            labels[f"{kind}.{p.id}"] = p.label
            labels |= {f"{kind}.{p.id}.{s.id}": s.label for s in p.subs}
        for key, lines in q.items():
            assert bare(labels[key]) not in {bare(line) for line in lines}, key


def test_packs_add_lines(tmp_path, core_pack_dir):
    """PROG-06: a later pack adds lines to a key, duplicates once."""
    extra = tmp_path / "extra"
    (extra / "ui").mkdir(parents=True)
    (extra / "pack.yaml").write_text("schema: as.pack.v1\nid: extra\nname: Extra lines\nversion: 1.0.0\n"
                                     "description: More lines for the bar.\ndepends_on: [core]\n", encoding="utf-8")
    (extra / "ui" / "more.yaml").write_text("schema: as.quips.v1\nid: more_quips\nlines:\n  turn:\n    - Rolling.\n"
                                            "    - The kettle is on.\n", encoding="utf-8")
    c, issues = load_canon([core_pack_dir, extra])
    assert not [i for i in issues if i.severity == "error"], issues
    lines = progress.quips_for(c, "turn")["turn"]
    assert lines.count("Rolling.") == 1 and lines[-1] == "The kettle is on."


def test_a_quip_key_must_name_a_step(tmp_path, core_pack_dir):
    pack = tmp_path / "core"
    shutil.copytree(core_pack_dir, pack)
    f = pack / "ui" / "quips.yaml"
    f.write_text(f.read_text(encoding="utf-8").replace("  turn.minds:\n", "  turn.feelings:\n"), encoding="utf-8")
    _c, issues = load_canon([pack])
    assert any(i.code == "CNT-16" and "turn.feelings" in i.message for i in issues if i.severity == "error")


# =========================================================================== through the service
def scenario_run(tmp_path, *, owed=False):
    """The metal_fence run on disk, as the terminal makes it. owed=True leaves June a material
    memory at boundary 0, so the quiet hours have one reflection to finish before turn 1."""
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


def service(cfg, tmp_path, fake=None):
    svc = game_service.GameService(cfg, fake or FakeTransport(), config_path=str(tmp_path / "as_config.yaml"))
    pushed = []

    async def collect(msg):
        if msg["action"] in BAR:
            OUT_MODELS[msg["action"]].model_validate(msg["data"])
        pushed.append(msg)
    svc.subscribe(collect)
    return svc, pushed


def msg(action, **fields):
    return {"type": "as_game", "action": action, **fields}


def play_one(cfg, tmp_path, text="I watch the front door.", fake=None):
    """Load the run, note what the quiet hours owe, play one move; the pushes of the move."""
    svc, pushed = service(cfg, tmp_path, fake)

    async def go():
        await svc.handle(msg("run_load", run_id=RUN))
        owed = len(bg.pending(svc.session.store, 0))
        start = len(pushed)
        await svc.handle(msg("turn_submit", mode="do", text=text))
        await svc.idle()
        return owed, pushed[start:]
    try:
        owed, msgs = asyncio.run(go())
        canon = svc.session.store.canon
    finally:
        svc.session.store.close()
    return owed, msgs, canon


def acts(msgs):
    return [m["action"] for m in msgs]


def test_a_turn_shows_its_plan_then_follows_the_pipeline(tmp_path):
    """PROG-01/03/05 through the service: the turn's plan is pushed before its first step, the steps
    are the pipeline's own stages in the order they ran, and the bar closes before the result."""
    owed, msgs, canon = play_one(scenario_run(tmp_path), tmp_path)
    assert owed == 0, "nothing is owed at the start of this run: no quiet-hours bar"
    bar = [m["data"] for m in msgs if m["action"] in BAR]
    a = acts(msgs)
    assert a.count("progress_plan") == 1 and a.index("progress_plan") < a.index("turn_progress")
    plan, steps, fin = bar[0], bar[1:-1], bar[-1]
    assert (plan["job_id"], plan["kind"], plan["title"]) == ("turn-1", "turn", progress.TITLES["turn"])
    assert plan["quips"] == progress.quips_for(canon, "turn")
    stages = [m["data"]["stage"] for m in msgs if m["action"] == "turn_progress"]
    assert [(d["phase"], d["sub"]) for d in steps] == [progress.TURN_STAGES[st] for st in stages
                                                       if st in progress.TURN_STAGES]
    ids = [p.id for p in progress.PLANS["turn"]]
    assert all(d["phase_index"] == ids.index(d["phase"]) and d["job_id"] == "turn-1" for d in steps)
    assert all((d["done"], d["total"], d["detail"]) == (None, None, None) for d in steps)
    pcts = [d["pct"] for d in steps]
    assert pcts == sorted(pcts) and pcts[-1] >= 98
    assert fin == {"job_id": "turn-1", "kind": "turn", "ok": True, "elapsed_s": fin["elapsed_s"]}
    assert a.index("progress_done") < a.index("turn_result")


def test_a_rejected_move_closes_its_bar_unfinished(tmp_path):
    """done(outcome.ok): the move could not be read, so the bar ends not ok, before the answer."""
    fake = FakeTransport().script(CallClass.INTAKE, {"choice": "NONE", "none_reason": "impossible", "manner": "",
                                                     "remainder": None, "clarify": None})
    _owed, msgs, _canon = play_one(scenario_run(tmp_path), tmp_path, "I fly over the fence.", fake)
    a = acts(msgs)
    fin = [m["data"] for m in msgs if m["action"] == "progress_done"]
    assert [(d["kind"], d["ok"]) for d in fin] == [("turn", False)]
    assert a.index("progress_done") < a.index("turn_rejected")


def test_the_quiet_hours_get_their_own_bar_first(tmp_path):
    """BG-01 + PROG-01: what the boundary owes is finished under its own bar — its plan, a step per
    job with how many are done (quiet hours may count), its end — and only then the turn's."""
    owed, msgs, canon = play_one(scenario_run(tmp_path, owed=True), tmp_path)
    assert owed == 1
    bar = [(m["action"], m["data"]) for m in msgs if m["action"] in BAR]
    kinds = [(action, d["kind"]) for action, d in bar]
    assert kinds[0] == ("progress_plan", "quiet_hours") and bar[0][1]["job_id"] == "quiet_hours-1"
    assert bar[0][1]["quips"] == progress.quips_for(canon, "quiet_hours")
    quiet = [d for action, d in bar if action == "progress" and d["kind"] == "quiet_hours"]
    assert [(d["phase"], d["sub"], d["done"], d["total"], d["detail"]) for d in quiet] == [("quiet", "jobs", 0, 1, None)]
    end = kinds.index(("progress_done", "quiet_hours"))
    assert bar[end][1]["ok"] is True
    assert kinds[end + 1] == ("progress_plan", "turn") and {k for _a, k in kinds[end + 1:]} == {"turn"}


def run_new(cfg, tmp_path, *, cancel=False):
    """A New Life through the protocol; the pushes until the worldgen job has ended."""
    svc, pushed = service(cfg, tmp_path)

    async def go():
        r = await svc.handle(msg("run_new", pc_ref=WORLD_PC, settings=SMALL))
        assert acts(r) == ["state"]
        task = svc.worldgen_task
        if cancel:
            async def first_step():
                while not any(m["action"] == "progress" for m in pushed):
                    await asyncio.sleep(0)
            await asyncio.wait_for(first_step(), 60)
            assert acts(await svc.handle(msg("worldgen_cancel"))) == ["state"]
        await asyncio.wait({task})
        return list(pushed)
    try:
        return asyncio.run(go())
    finally:
        if svc.session is not None:
            svc.session.store.close()


def test_worldgen_shows_every_stage_and_counts_the_long_ones(run_cfg, tmp_path):
    """PROG-01..04 for a New Life: the plan (every stage but COMMIT), then each stage in order —
    WG2 and WG6 counting their model answers one by one — never backwards, then the end, before the
    run opens. The old worldgen_progress messages still come, one per call."""
    msgs = run_new(run_cfg, tmp_path)
    bar = [(m["action"], m["data"]) for m in msgs if m["action"] in BAR]
    (a0, plan), (az, fin) = bar[0], bar[-1]
    assert (a0, plan["job_id"], plan["kind"]) == ("progress_plan", "worldgen-1", "worldgen")
    assert [p["id"] for p in plan["phases"]] == [s for s in atlas.STAGES if s != "COMMIT"]
    canon, _issues = load_canon([REPO_PACKS / "core"])
    assert plan["quips"] == progress.quips_for(canon, "worldgen")
    assert (az, fin["job_id"], fin["ok"]) == ("progress_done", "worldgen-1", True)
    assert {action for action, _d in bar[1:-1]} == {"progress"}
    steps = [d for _a, d in bar[1:-1]]
    order = []
    for d in steps:
        if not order or order[-1] != d["phase"]:
            order.append(d["phase"])
    assert order == [p["id"] for p in plan["phases"]], "each stage once, in order"
    for stage, sub in (("WG2", "history"), ("WG6", "dossiers")):
        mine = [d for d in steps if d["phase"] == stage]
        assert mine[0]["sub"] is None and all(d["sub"] == sub for d in mine[1:])
        total = mine[1]["total"]
        assert [(d["done"], d["total"]) for d in mine[1:]] == [(k, total) for k in range(1, total + 1)]
    assert all(d["sub"] is None and d["done"] is None for d in steps if d["phase"] not in ("WG2", "WG6"))
    pcts = [d["pct"] for d in steps]
    assert pcts == sorted(pcts)
    assert all(d["eta_s"] is None for d in steps if d["pct"] < 5)
    assert all(d["eta_s"] is not None for d in steps if d["pct"] >= 5)
    a = acts(msgs)
    assert a.count("worldgen_progress") == len(steps) + 1, "and one for COMMIT"
    assert a.index("progress_done") < a.index("run_loaded")


def test_a_cancelled_world_closes_its_bar(run_cfg, tmp_path):
    """on_worldgen_cancel: the job ends, and so does its bar — not ok — and nothing opens."""
    msgs = run_new(run_cfg, tmp_path, cancel=True)
    bar = [(m["action"], m["data"]) for m in msgs if m["action"] in BAR]
    assert bar[-1][0] == "progress_done" and bar[-1][1]["ok"] is False
    assert "run_loaded" not in acts(msgs)
