"""The worldgen pipeline and the run it makes (P10). Rules WG-10..37, WG-DET-01, RUN-01, RUN-09, RUN-11
(world/worldgen/pipeline.py, service/runs.py create_run).

A world is made in stages, each in its own transaction, each announced to the player; the model only
writes words, and when it cannot (lanes down, bad answers) code writes them, so a world is always
complete. A world that cannot hold is refused plainly, and nothing half-made is left behind.
"""

from __future__ import annotations

import asyncio
import json
import math
import shutil
from pathlib import Path

import pytest

from as_engine.contracts.common import CallClass, Lane
from as_engine.contracts.settings import EngineConfig, RulesConfig, RunSettings
from as_engine.contracts.worldgen import WorldgenCommit, WorldgenProgress
from as_engine.kernel.errors import SettingsError
from as_engine.kernel.hashing import table_digest
from as_engine.kernel.store import Store
from as_engine.service import runs
from as_engine.testing.fake_lm import FakeTransport
from as_engine.world.worldgen import atlas, region, tables
from as_engine.world.worldgen.pipeline import WorldgenAborted, WorldgenAssertion

from conftest import FIXTURE_PACKS, REPO_PACKS, WORLD_PC
from world_kit import DAY, H, all_rows, commit_json, now, one, params, rows

pytestmark = pytest.mark.phase(10)

SMALL = {"world_detail": "gotta_go_to_work_soon", "seed": 7, "era": "established"}


async def make(cfg, pc=WORLD_PC, fake=None, progress=None, **settings):
    return await runs.create_run(cfg, pc, RunSettings(**(SMALL | settings)), fake or FakeTransport(), progress=progress)


def leftovers(cfg) -> list[str]:
    """Everything in the runs folder (a failed or cancelled start must leave nothing)."""
    root = Path(cfg.runs_dir)
    if not root.exists():
        return []
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_dir() and p.name != "_worlds")


# --------------------------------------------------------------------------- the run it makes
def test_run_and_world_ids(made_world):
    """RUN-01 / RUN-11: run_id from the PC's name and the seed; world_id from the seed."""
    assert made_world.run_id == "owen_marsh_7"
    assert made_world.world_id == "w_7" and made_world.report.world_id == "w_7"


def test_stages_and_report(made_world, canon):
    r = made_world.report
    assert r.stages == list(atlas.STAGES)
    assert r.retries == [] and r.qc_result in ("pass", "patched")
    assert all(reason for _ref, reason in r.skipped_actors)
    want = [f"{canon.get(ref).identity.name} is not in this world: {reason}." for ref, reason in r.skipped_actors]
    assert made_world.notices == want


async def test_progress_is_announced_stage_by_stage(run_cfg):
    """Before each stage: its label, the share of the bar already done, and a time estimate."""
    seen = []

    async def progress(p):          # an async callback is awaited
        seen.append(p)
    s = await make(run_cfg, progress=progress)
    s.store.close()
    assert all(isinstance(p, WorldgenProgress) for p in seen)
    assert [p.stage for p in seen] == list(atlas.STAGES)
    est = tables.DETAIL_TIERS["gotta_go_to_work_soon"]["est_minutes"]
    done = 0
    for p in seen:
        assert p.label == atlas.STAGE_LABELS[p.stage]
        assert p.pct == done
        assert p.eta_s == pytest.approx((100 - done) * est * 60 / 100)
        done += atlas.STAGE_SHARE[p.stage]
    assert seen[-1].pct == 100


async def test_a_plain_callback_works_too(run_cfg):
    seen = []
    s = await make(run_cfg, progress=seen.append)
    s.store.close()
    assert len(seen) == len(atlas.STAGES)


def _stage_order(stages):
    """The stage names with consecutive repeats folded (a stage may commit several events)."""
    out = []
    for st in stages:
        if not out or out[-1] != st:
            out.append(st)
    return out


def test_every_stage_ends_with_its_event(gw):
    """Stages in order; each closes with {stage}; the row-writing events carry their counts."""
    ev = rows(gw, "WORLDGEN_STAGE")
    assert _stage_order([e["payload"]["stage"] for e in ev]) == list(atlas.STAGES)
    assert all((e["writer"], e["origin"], e["turn_index"]) == ("world.worldgen", "worldgen", 0) for e in ev)
    last = {}
    for e in ev:
        last[e["payload"]["stage"]] = e["payload"]
    assert all(last[st] == {"stage": st} for st in atlas.STAGES if st != "COMMIT")
    assert last["COMMIT"] == {"stage": "COMMIT", "world_id": "w_7"}
    extra = [e["payload"] for e in ev if len(e["payload"]) > 1 and e["payload"]["stage"] != "COMMIT"]
    n_hist = one(gw, "SELECT COUNT(*) AS n FROM history_events WHERE kind != 'personal'")["n"]
    n_pers = one(gw, "SELECT COUNT(*) AS n FROM history_events WHERE kind = 'personal'")["n"]
    assert extra == [{"stage": "WG0", "patches": len(commit_json(gw)["qc_patches"]) - commit_json(gw)["qc_patches"].count(
                         "QC-4: opening written by code")},
                     {"stage": "WG2", "events": n_hist}, {"stage": "WG8", "personal": n_pers},
                     {"stage": "WG8", "commit": True}]


def test_the_clock_starts_on_the_world_s_day(gw):
    """WG0: the clock stands at days_since_fall days plus WorldRules.start_hour, turn 0."""
    p = params(gw)
    assert now(gw) == p["days_since_fall"] * DAY + RulesConfig().world.start_hour * H
    assert gw.store.query_one("SELECT turn_index FROM world_clock")[0] == 0
    assert one(gw, "SELECT COUNT(*) AS n FROM events WHERE turn_index != 0")["n"] == 0


def test_run_meta_and_manifest(gw, world_cfg, made_world):
    assert gw.store.meta("world_id") == "w_7"
    s = rows(gw, "SETTINGS_CHANGE")
    assert [e["payload"] for e in s if e["payload"].get("source") == "worldgen"] == [{"source": "worldgen", "world_id": "w_7"}]
    pcc = rows(gw, "PC_CONTROL_CHANGE")
    assert len(pcc) == 1 and pcc[0]["payload"]["pc_actor_id"] == gw.pc_id == gw.store.meta("pc_actor_id")
    man = json.loads((Path(world_cfg.runs_dir) / made_world.run_id / "manifest.json").read_text(encoding="utf-8"))
    assert (man["world_id"], man["pc_name"], man["turn_index"], man["alive"]) == ("w_7", "Owen Marsh", 0, True)
    assert json.loads(gw.store.meta("settings_json"))["seed"] == 7
    assert [x.run_id for x in runs.list_runs(world_cfg)] == [made_world.run_id]


def test_the_commit_record(gw):
    """WG8 step 8: world_params.commit_json is the WorldgenCommit."""
    c = WorldgenCommit.model_validate(commit_json(gw))
    assert (c.run_id, c.seed, c.pc_ref) == ("owen_marsh_7", 7, WORLD_PC)
    assert c.params.model_dump(mode="json") == params(gw)
    assert c.qc_result in ("pass", "patched")
    kinds = {r["zone_id"]: r["kind"] for r in all_rows(gw, "SELECT zone_id, kind FROM zones")}
    first_zone = min(kinds)
    assert c.start_zone_type == kinds[first_zone]


def test_genesis_is_the_world_before_the_player(made_world):
    """RUN-09: genesis.sqlite is the world after WG7 — people, laws, history — and no PC."""
    wd = made_world.root / "runs" / "_worlds" / "w_7"
    g = Store.open(wd / "genesis.sqlite")
    try:
        assert g.query_one("SELECT COUNT(*) FROM actors WHERE controller = 'human'")[0] == 0
        assert g.query_one("SELECT COUNT(*) FROM events WHERE type IN ('PC_CONTROL_CHANGE')")[0] == 0
        assert _stage_order([r[0] for r in g.query("SELECT json_extract(payload, '$.stage') FROM events "
                                                   "WHERE type = 'WORLDGEN_STAGE' ORDER BY seq")]) == list(atlas.STAGES[:8])
        for t in ("settlements", "groups", "history_events", "laws_active", "cohorts", "world_params"):
            assert g.query_one(f"SELECT COUNT(*) FROM {t}")[0] > 0, t
    finally:
        g.close()
    wj = json.loads((wd / "world.json").read_text(encoding="utf-8"))
    p = json.loads(Store.open(made_world.root / "runs" / made_world.run_id / "world.sqlite").query_one(
        "SELECT params_json FROM world_params")[0])
    cd = p["climate_descriptor"]
    assert set(wj) == {"world_id", "title", "difficulty", "era", "day_at_genesis", "climate_text", "factions", "created_real",
                       "source", "seed", "detail"}
    assert wj["title"] == f"{cd[:1].upper() + cd[1:]} — Established, day {p['days_since_fall']}"
    assert (wj["world_id"], wj["difficulty"], wj["era"], wj["source"], wj["seed"], wj["detail"]) == \
           ("w_7", "normal", "established", "generated", 7, "gotta_go_to_work_soon")
    assert (wj["day_at_genesis"], wj["climate_text"]) == (p["days_since_fall"], cd)


def test_turn0_is_the_run_before_the_first_turn(made_world, gw):
    """RUN-01: turn0.sqlite is the finished world with the PC in it, before any turn."""
    t0 = Store.open(made_world.root / "runs" / made_world.run_id / "turn0.sqlite")
    try:
        tables_ = [r[0] for r in t0.query("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
                                          "AND name NOT LIKE 'episodes_fts%'")]
        for t in tables_:
            assert table_digest(t0, t) == table_digest(gw.store, t), t
    finally:
        t0.close()


async def test_wg_det_01_the_same_seed_makes_the_same_world(tmp_path):
    """WG-DET-01: table for table the same; meta differs only in the wall-clock creation time."""
    stores = []
    for k in range(2):
        cfg = EngineConfig(runs_dir=str(tmp_path / f"r{k}" / "runs"), content_dir=str(REPO_PACKS))
        stores.append((await make(cfg)).store)
    a, b = stores
    try:
        names = [r[0] for r in a.query("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
                                       "AND name NOT LIKE 'episodes_fts%'")]
        assert [t for t in names if t != "meta" and table_digest(a, t) != table_digest(b, t)] == []
        ma, mb = (dict(s.query("SELECT key, value FROM meta").fetchall() if hasattr(s.query("SELECT 1"), "fetchall")
                       else [tuple(r) for r in s.query("SELECT key, value FROM meta")]) for s in (a, b))
        assert {k for k in ma if ma[k] != mb.get(k)} <= {"created_at_real"}
    finally:
        a.close()
        b.close()


async def test_another_seed_makes_another_world(run_cfg, tmp_path):
    a = await make(run_cfg)
    b = await make(EngineConfig(runs_dir=str(tmp_path / "other"), content_dir=str(REPO_PACKS)), seed=8)
    try:
        assert table_digest(a.store, "places") != table_digest(b.store, "places")
    finally:
        a.store.close()
        b.store.close()


async def test_names_are_never_reused(run_cfg):
    """RUN-01 / RUN-11: a second run of the same seed gets '_2' — and a world of its own."""
    a = await make(run_cfg)
    b = await make(run_cfg)
    try:
        assert (a.run_id, b.run_id) == ("owen_marsh_7", "owen_marsh_7_2")
        assert (a.store.meta("world_id"), b.store.meta("world_id")) == ("w_7", "w_7_2")
        assert (Path(run_cfg.runs_dir) / "_worlds" / "w_7_2" / "genesis.sqlite").exists()
    finally:
        a.store.close()
        b.store.close()


async def test_a_seed_comes_from_outside_when_none_is_given(run_cfg):
    s = await runs.create_run(run_cfg, WORLD_PC, RunSettings(world_detail="gotta_go_to_work_soon", era="established"),
                              FakeTransport())
    try:
        seed = json.loads(s.store.meta("settings_json"))["seed"]
        assert isinstance(seed, int) and 0 <= seed < 16 ** 15
        assert int(s.store.meta("seed")) == seed and s.run_id == f"owen_marsh_{seed:x}"
    finally:
        s.store.close()


# --------------------------------------------------------------------------- the model's part
def test_every_worldgen_call_is_logged(gw, made_world):
    """Call log: every model call worldgen made is an lm_calls row of turn 0."""
    calls = all_rows(gw, "SELECT call_class, status FROM lm_calls WHERE turn_index = 0 ORDER BY seq")
    assert len(calls) == made_world.report.model_calls > 0
    classes = [c["call_class"] for c in calls]
    n_events = one(gw, "SELECT COUNT(*) AS n FROM history_events WHERE kind != 'personal'")["n"]
    assert classes.count("worldgen_history") == math.ceil(n_events / 8)
    assert classes.count("worldgen_opening") == 1
    tier = tables.DETAIL_TIERS["gotta_go_to_work_soon"]
    generated = one(gw, "SELECT COUNT(*) AS n FROM dossiers WHERE source = 'generated'")["n"]
    assert classes.count("worldgen_actor") == min(tier["llm_dossiers"], generated)


async def test_with_the_models_down_the_world_is_still_whole(run_cfg):
    """Model calls never abort worldgen: skeleton history, skeleton people, the code opening."""
    fake = FakeTransport()
    fake.down(Lane.A)
    fake.down(Lane.B)
    s = await make(run_cfg, fake=fake)
    try:
        hist = all_rows(s, "SELECT * FROM history_events WHERE kind != 'personal' ORDER BY day, hist_id")
        assert hist
        for h in hist:
            assert h["truth_text"].startswith(f"Day {h['day']}: ")
            assert h["belief_text"] == "People say " + h["truth_text"].split(": ", 1)[1]
        c = commit_json(s)
        assert "QC-4: opening written by code" in c["qc_patches"]
        assert s.extras["worldgen_report"].stages == list(atlas.STAGES)
    finally:
        s.store.close()


async def test_a_history_answer_that_is_too_short_keeps_the_skeleton(run_cfg):
    """WG-20: an event missing from the answer, or with a truth outside 20..600, keeps its skeleton."""
    fake = FakeTransport()

    def answer(req):
        evs = req.context.fields["events"]
        return {"events": [{"id": evs[0]["id"], "truth": "Too short.", "belief": "Short too."}] +
                          [{"id": e["id"], "truth": f"The written truth of {e['id']}, long enough to keep.",
                            "belief": f"What people say of {e['id']}."} for e in evs[1:-1]]}
    for _ in range(10):
        fake.script(CallClass.WORLDGEN_HISTORY, response=answer)
    s = await make(run_cfg, fake=fake)
    try:
        hist = {h["hist_id"]: h for h in all_rows(s, "SELECT * FROM history_events WHERE kind != 'personal'")}
        req = fake.calls(CallClass.WORLDGEN_HISTORY)[0]
        evs = req.context.fields["events"]
        first, middle, last = evs[0], evs[1:-1], evs[-1]
        for e in (first, last):
            assert hist[e["id"]]["truth_text"] == e["skeleton"]
        for e in middle:
            assert hist[e["id"]]["truth_text"] == f"The written truth of {e['id']}, long enough to keep."
            assert hist[e["id"]]["belief_text"] == f"What people say of {e['id']}."
        assert len(evs) <= 8
    finally:
        s.store.close()


async def test_an_opening_that_fails_qc4_twice_is_written_by_code(run_cfg):
    """QC-4 / QC-5: one retry with the problem named; then fallback_opening."""
    fake = FakeTransport()
    bad = {"immediate_contacts": "Nobody.", "immediate_liabilities": "Nothing.", "opening_pressure": "Something.",
           "first_objective": "Survive.", "cites_entity_ids": ["act_999999"], "cites_params": ["ammo"]}
    fake.script(CallClass.WORLDGEN_OPENING, response=bad)
    fake.script(CallClass.WORLDGEN_OPENING, response=bad)
    s = await make(run_cfg, fake=fake)
    try:
        calls = fake.calls(CallClass.WORLDGEN_OPENING)
        assert len(calls) == 2
        assert "error" not in calls[0].context.fields and calls[1].context.fields.get("error")
        c = WorldgenCommit.model_validate(commit_json(s))
        assert "QC-4: opening written by code" in c.qc_patches and c.qc_result == "patched"
        assert c.opening.cites_entity_ids != ["act_999999"]
        assert c.opening.opening_pressure.endswith(("within the hour.", "…"))
    finally:
        s.store.close()


async def test_a_good_opening_is_used_as_written(run_cfg):
    fake = FakeTransport()
    s = await make(run_cfg, fake=fake)
    try:
        c = WorldgenCommit.model_validate(commit_json(s))
        (req,) = fake.calls(CallClass.WORLDGEN_OPENING)
        ids = {e["id"] for e in req.context.fields["entities"]}
        assert set(c.opening.cites_entity_ids) <= ids and c.opening.cites_entity_ids
        assert "QC-4: opening written by code" not in c.qc_patches
        assert set(req.context.fields["budgets"]) == set(tables.OPENING_BUDGETS)
    finally:
        s.store.close()


# --------------------------------------------------------------------------- when a stage fails
async def test_a_stage_that_fails_once_runs_again(run_cfg, monkeypatch):
    """WG-DET-01 retry: the failed transaction is rolled back; one 'retry' draw; the stage runs again."""
    real = region.assert_region
    calls = []

    def flaky(store, reg):
        calls.append(1)
        if len(calls) == 1:
            raise WorldgenAssertion("WG1", "a test broke the region")
        return real(store, reg)
    monkeypatch.setattr(region, "assert_region", flaky)
    s = await make(run_cfg)
    try:
        rep = s.extras["worldgen_report"]
        assert rep.retries == ["WG1"] and rep.stages == list(atlas.STAGES)
        retry = all_rows(s, "SELECT stream, n FROM prng_ledger WHERE purpose = 'retry'")
        assert retry == [{"stream": "worldgen:region", "n": 2}]
        assert one(s, "SELECT COUNT(*) AS n FROM zones")["n"] == tables.DETAIL_TIERS["gotta_go_to_work_soon"]["zones"], \
            "the failed attempt's rows are gone"
    finally:
        s.store.close()


async def test_a_stage_that_fails_twice_ends_worldgen(run_cfg, monkeypatch):
    def broken(store, reg):
        raise WorldgenAssertion("WG1", "a test broke the region")
    monkeypatch.setattr(region, "assert_region", broken)
    with pytest.raises(WorldgenAborted) as e:
        await make(run_cfg)
    assert e.value.code == "stage_failed"
    assert str(e.value) == "Carving the land… failed twice: a test broke the region"
    assert leftovers(run_cfg) == [] and runs.list_runs(run_cfg) == []


async def test_cancel_leaves_nothing_behind(run_cfg):
    """create_run cancelled mid-worldgen: the partial run and world folders are removed."""
    class Held(FakeTransport):
        def __init__(self):
            super().__init__()
            self.reached = asyncio.Event()

        async def send(self, lane, request):
            if request.call_class == CallClass.WORLDGEN_HISTORY:
                self.reached.set()
                await asyncio.Event().wait()          # never answers
            return await super().send(lane, request)
    fake = Held()
    task = asyncio.create_task(make(run_cfg, fake=fake))
    await asyncio.wait_for(fake.reached.wait(), 30)
    assert (Path(run_cfg.runs_dir) / "owen_marsh_7").exists()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert leftovers(run_cfg) == [] and runs.list_runs(run_cfg) == []
    assert not (Path(run_cfg.runs_dir) / "_worlds" / "w_7").exists()


@pytest.fixture
def hopeless_cfg(tmp_path):
    """A content folder with the core pack and the p10_hopeless fixture pack (Hal Brandt)."""
    content = tmp_path / "content"
    shutil.copytree(REPO_PACKS / "core", content / "core")
    shutil.copytree(FIXTURE_PACKS / "p10_hopeless", content / "p10_hopeless")
    return EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(content))


async def test_a_hopeless_start_is_refused_plainly(hopeless_cfg):
    """WG-14 / Part XII: at Bitch Mode .. Realism a start nobody could survive is not faked."""
    with pytest.raises(WorldgenAborted) as e:
        await make(hopeless_cfg, pc="p10_hopeless:pc/hopeless_hal", difficulty="normal", pack_ids=["core", "p10_hopeless"])
    assert e.value.code == "hopeless_start"
    assert str(e.value) == ("Hal Brandt cannot survive the start this world gives them at Normal. Try one difficulty "
                            "lower, another character, or another era.")
    assert e.value.options == ["difficulty_lower", "change_character", "change_era"]
    assert leftovers(hopeless_cfg) == []


async def test_the_same_start_at_fuck_you_is_allowed(hopeless_cfg):
    s = await make(hopeless_cfg, pc="p10_hopeless:pc/hopeless_hal", difficulty="fuck_you", pack_ids=["core", "p10_hopeless"])
    try:
        assert s.store.query_one("SELECT display_name FROM actors WHERE controller = 'human'")[0] == "Hal Brandt"
    finally:
        s.store.close()


async def test_a_world_the_character_cannot_live_in_is_refused(run_cfg):
    """WG-34: Ruth's history needs 1-10 years after the Fall; an Early world cannot hold her."""
    with pytest.raises(SettingsError) as e:
        await make(run_cfg, pc="core:pc/ruth_castillo", era="early")
    assert str(e.value) == "Ruth Castillo's age and history need a world 1-10 years after the Fall."
    assert leftovers(run_cfg) == []


async def test_an_unknown_character(run_cfg):
    for ref in ("core:pc/nobody", "core:actor/eli_voss"):
        with pytest.raises(runs.RunError) as e:
            await make(run_cfg, pc=ref)
        assert (e.value.code, e.value.message) == ("not_found", f"There is no character called {ref}.")
    assert leftovers(run_cfg) == []


async def test_worlds_are_reused_in_p12(run_cfg):
    """RUN-09: starting in an existing world arrives with P12 (the P10 build answers 'P12')."""
    with pytest.raises(NotImplementedError, match="P12"):
        await runs.create_run(run_cfg, WORLD_PC, RunSettings(**SMALL), FakeTransport(), world_id="w_7")
    assert leftovers(run_cfg) == []
