"""The limits bench finds limits (tools/as/bench.py, D-112; 08 §7, BENCH-01).

The bench runs end to end on two simulated lanes whose limits are written down (tools/as/benchsim.py SMALL:
the owner's speeds — a Writer that writes 5 tokens a second, a Clerk that writes 19 and reads 200 — in small
contexts): the Writer reports its context and prompt progress and serves one request at a time; the Clerk
reports neither and serves two at once. The bench must find what is there — the context, the reading and
writing speeds, the cache, the parallel slots, how far in a fact is still found, the thinking switch — and turn
it into settings that keep the game's design: never a lower stall window, a raised ``max_tokens`` only where a
call was cut short, turn budgets that still admit the minds each depth was designed for, and no call moved to
another lane. It never writes as_config.yaml for simulated lanes.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from as_engine.contracts.common import LOD, CallClass, Lane
from as_engine.contracts.settings import EngineConfig

pytestmark = pytest.mark.phase(1)

ROOT = Path(__file__).resolve().parents[4]
TOOLS = ROOT / "tools" / "as"


def _load(name: str, file: str):
    sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location(name, TOOLS / file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod                      # dataclasses look their module up by name
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def bench():
    return _load("as_bench_tool", "bench.py")


@pytest.fixture(scope="module")
def sim():
    return _load("benchsim", "benchsim.py")


@pytest.fixture(scope="module")
def fake_report(bench, sim, tmp_path_factory):
    import asyncio
    out = tmp_path_factory.mktemp("bench")
    cfg_file = ROOT / "as_config.yaml"
    before = cfg_file.read_bytes() if cfg_file.exists() else None
    asyncio.run(bench.main(["--fake", "--accept", "--out", str(out)], sim_models=sim.SMALL, sim_scale=0.003))
    after = cfg_file.read_bytes() if cfg_file.exists() else None
    assert before == after, "simulated lanes never change as_config.yaml"
    assert (out / "bench.fake.md").exists()
    return json.loads((out / "bench.fake.json").read_text())


# ------------------------------------------------------------------------- it finds what is there


def test_it_finds_each_lane_s_context(fake_report, sim):
    A, B = sim.SMALL["A"], sim.SMALL["B"]
    a, b = fake_report["lanes"]["A"], fake_report["lanes"]["B"]
    assert a["identity"]["context"] == A.ctx and a["identity"]["context_source"] == "LM Studio"
    assert a["ladder"]["max_read_tokens"] >= 0.9 * A.ctx, "the top rung reads right up to the loaded context"
    assert b["identity"]["context"] is None, "the Clerk's LM Studio does not say: the ladder must find it"
    pf = b["ladder"]
    assert pf["limit_source"] == "found" and 0.9 * B.ctx <= pf["max_read_tokens"] <= B.ctx < pf["failure"]["target"] * 1.05
    assert pf["failure"]["target"] <= 1.15 * B.ctx, "halving the gap pins the limit, not just the next power of two"


def test_it_measures_reading_and_writing_speed(fake_report, sim):
    for key in ("A", "B"):
        m, L = sim.SMALL[key], fake_report["lanes"][key]
        top = max(L["ladder"]["rungs"], key=lambda r: r["prompt_tokens"])
        assert abs(top["rate_tok_s"] - m.prefill_tps) <= 0.15 * m.prefill_tps
        off = next(r for r in L["decode"]["runs"] if not r["thinking"])
        assert abs(off["tok_s"] - m.decode_tps) <= 0.2 * m.decode_tps


def test_it_finds_the_thinking_switch_and_the_prompt_progress(fake_report):
    a, b = fake_report["lanes"]["A"]["probe"], fake_report["lanes"]["B"]["probe"]
    assert a["thinking_mode"] in ("system_think_token", "chat_template_kwargs") and a["thinking_on_works"]
    assert b["thinking_mode"] in ("system_no_think", "chat_template_kwargs", "prefill_empty_think") and b["thinking_on_works"]
    assert (a["prefill_progress"], b["prefill_progress"]) == ("supported", "unsupported")
    on = next(r for r in fake_report["lanes"]["A"]["decode"]["runs"] if r["thinking"])
    assert on["thought"], "the later stages use the switch the probe found"


def test_it_sees_the_cache_the_slots_and_the_recall(fake_report, sim):
    for key in ("A", "B"):
        m, L = sim.SMALL[key], fake_report["lanes"][key]
        assert L["cache"]["repeat_share"] < 0.2 and L["cache"]["after_other_share"] > 0.8, "one cached prompt"
        assert L["concurrency"]["recommended"] == m.slots
        assert 0.75 * m.recall_tokens <= L["ladder"]["recall_tokens"] <= m.recall_tokens
        assert L["ladder"]["format_ok"] == L["ladder"]["rung_count"], "every rung answered in the JSON asked for"


def test_every_call_class_runs_on_its_own_lane_at_its_own_regime(fake_report, bench):
    cfg = EngineConfig()
    rows = fake_report["classes"]
    assert rows["actor_cognition_hot"]["lane"] == cfg.hot_cognition.lane.value and rows["actor_cognition_hot"]["thinking"]
    for cc in CallClass:
        if cc in (CallClass.PROBE, CallClass.ACTOR_COGNITION):
            continue
        r = rows[cc.value]
        reg = cfg.regimes[cc]
        assert (r["lane"], r["thinking"], r["max_tokens"]) == (reg.lane.value, reg.thinking, reg.max_tokens), cc.value
    assert rows["actor_cognition_warm"]["lane"] == cfg.regimes[CallClass.ACTOR_COGNITION].lane.value
    other = "B" if cfg.hot_cognition.lane == Lane.A else "A"
    assert rows[f"actor_cognition_hot@{other}"]["lane"] == other, "the HOT decision is timed on the other lane too"
    for k in bench.NO_THINK:
        quiet = rows[f"{k}@nothink"]
        assert rows[k]["thinking"] and not quiet["thinking"] and quiet["lane"] == rows[k]["lane"], \
            f"{k}: the thinking calls on every move's path are timed without thinking too"
        assert quiet["parsed"] == quiet["n"] and quiet["mean_s"] < rows[k]["mean_s"], k
    for k in ("intake", "actor_cognition_hot", "actor_cognition_warm", "writeback", "narration", "render_lint"):
        assert rows[k]["parsed"] == rows[k]["n"] and not rows[k]["truncated"], k
    lint = rows["narration"]["lint"]
    assert lint["drafts"] == rows["narration"]["n"] and 0 <= lint["passed"] <= lint["drafts"], \
        "every narration draft is put through the game's own code lint"
    assert lint["max_attempts"] == cfg.rules.style.max_narration_attempts


# ------------------------------------------------------------------------- the settings that follow


def test_the_settings_keep_the_design(fake_report, bench):
    from as_engine.lanes.scheduler import plan_cognition
    base = EngineConfig()
    new, changes = bench.recommend(fake_report, base)
    assert "lanes.B.max_concurrency: 1 -> 2" in changes and new.lanes[Lane.B].max_concurrency == 2
    assert all(new.lanes[l].stall_window_s >= base.lanes[l].stall_window_s for l in Lane)
    S = new.rules.scheduler
    assert S.estimated_call_s["actor_cognition_warm"] == round(fake_report["classes"]["actor_cognition_warm"]["mean_s"], 1)
    for depth in ("quick", "balanced", "deep"):
        hot_n, warm_n = bench.capacity(depth)
        p = plan_cognition([(f"c{i:02d}", 1.0, False) for i in range(bench.CAPACITY_CANDIDATES)], new, depth, {Lane.A, Lane.B})
        lods = list(p.lod.values())
        assert lods.count(LOD.HOT) == hot_n and lods.count(LOD.WARM) >= warm_n, depth
    assert new.hot_cognition.lane == base.hot_cognition.lane and all(
        new.regimes[cc].lane == base.regimes[cc].lane for cc in CallClass), "the bench never moves a call"
    assert new.hot_cognition.thinking == base.hot_cognition.thinking and all(
        new.regimes[cc].thinking == base.regimes[cc].thinking for cc in CallClass), "nor turns thinking off: the owner's call"
    pj = fake_report["projection"]
    assert pj["other_hot_lane"] and set(pj["after"]) == {"quick", "balanced", "deep"}
    assert all(pj["no_thinking"][d]["s"] < pj["after"][d]["s"] for d in pj["after"])
    assert pj["no_thinking_settings"] == ["hot_cognition.thinking: false", "regimes.narration.thinking: false",
                                          "regimes.render_lint.thinking: false"]
    md = bench.markdown(fake_report)
    assert "without thinking*" in md and "`regimes.render_lint.thinking: false`" in md
    kept, kept_changes = bench.recommend(fake_report, base, keep_budgets=True)
    assert kept.rules.scheduler.turn_budget_s == base.rules.scheduler.turn_budget_s
    assert not any("turn_budget_s" in c or "reserve_narration_s" in c for c in kept_changes)
    EngineConfig.model_validate(new.model_dump(mode="json"))


def test_a_call_cut_short_gets_room_and_a_long_silence_widens_the_window(bench):
    base = EngineConfig()
    report = {"lanes": {"A": {"ladder": {"limit": 20000}, "stall": {"max_gap_s": 140.0}}, "B": {"stall": {"max_gap_s": 2.0}}},
              "classes": {"narration": {"call_class": "narration", "lane": "A", "truncated": 2, "completion_max": 8192,
                                        "prompt_tokens": 6000, "ok": True, "p90_s": 200.0, "mean_s": 150.0},
                          "intake": {"call_class": "intake", "lane": "B", "truncated": 0, "completion_max": 30,
                                     "prompt_tokens": 500, "ok": True, "p90_s": 4.0, "mean_s": 3.0}}}
    new, changes = bench.recommend(report, base, keep_budgets=True)
    assert new.regimes[CallClass.NARRATION].max_tokens == 13744, "doubled, capped by the context left after the prompt"
    assert new.regimes[CallClass.INTAKE].max_tokens == base.regimes[CallClass.INTAKE].max_tokens, "never lowered"
    assert new.lanes[Lane.A].stall_window_s == 420.0 and new.lanes[Lane.B].stall_window_s == 300.0
    assert new.regimes[CallClass.NARRATION].deadline_s == 200.0 and new.regimes[CallClass.INTAKE].deadline_s == 5.0


# ------------------------------------------------------------------------- the pieces


def test_parallel_slots_must_pay_for_themselves(bench):
    serial = [{"k": 1, "tok_s": 30, "mean_latency_s": 5, "ok": True}, {"k": 2, "tok_s": 31, "mean_latency_s": 10, "ok": True}]
    two = [{"k": 1, "tok_s": 30, "mean_latency_s": 5, "ok": True}, {"k": 2, "tok_s": 58, "mean_latency_s": 5.2, "ok": True},
           {"k": 3, "tok_s": 60, "mean_latency_s": 7, "ok": True}]
    slow = [{"k": 1, "tok_s": 30, "mean_latency_s": 5, "ok": True}, {"k": 2, "tok_s": 50, "mean_latency_s": 11, "ok": True}]
    assert (bench.recommend_concurrency(serial), bench.recommend_concurrency(two), bench.recommend_concurrency(slow)) == (1, 2, 1)


def test_recall_is_reliable_only_up_to_the_first_length_that_fades(bench):
    rows = [{"tokens": 2000, "score": 1.0}, {"tokens": 8000, "score": 0.8}, {"tokens": 16000, "score": 0.4},
            {"tokens": 32000, "score": 1.0}]
    assert bench.effective_context(rows) == 8000 and bench.effective_context([]) == 0


def test_cut_short_means_the_cap_was_reached_or_thinking_never_ended(bench):
    assert bench.truncated(1024, 1024, "ok", 0) and bench.truncated(300, 1024, "empty", 900)
    assert not bench.truncated(400, 1024, "ok", 900)


def test_the_filler_has_the_words_asked_for_and_the_facts_where_asked(bench):
    text = bench.log_text(2000, "t", ((0.5, "NEEDLE-MID"), (0.05, "NEEDLE-EARLY")))
    words = text.split()
    assert 2000 <= len(words) <= 2030 and text.startswith("Supply log t.")
    assert text.index("NEEDLE-EARLY") < text.index("NEEDLE-MID") and 0.4 < text.index("NEEDLE-MID") / len(text) < 0.6
    assert bench.log_text(500, "a") != bench.log_text(500, "b"), "two tags never share a cached prefix"


async def test_a_resumed_run_keeps_what_it_measured(bench, sim):
    t1 = sim.SimTransport(sim.SMALL, scale=0.001)
    b1 = bench.Bench(EngineConfig(), t1, clock=t1.clock, log=lambda *_: None, quick=True)
    r1 = await b1.run([Lane.B], ["identity", "ladder"])
    said = []
    t2 = sim.SimTransport(sim.SMALL, scale=0.001)
    b2 = bench.Bench(EngineConfig(), t2, clock=t2.clock, log=said.append, quick=True)
    r2 = await b2.run([Lane.B], ["identity", "ladder", "cache"], resume=json.loads(json.dumps(r1)))
    assert r2["lanes"]["B"]["ladder"] == r1["lanes"]["B"]["ladder"] and "cache" in r2["lanes"]["B"]
    assert any("ladder] kept from the last run" in s for s in said)


def test_an_unknown_stage_is_refused(bench, tmp_path):
    import asyncio
    assert asyncio.run(bench.main(["--fake", "--stages", "prefill", "--out", str(tmp_path)])) == 2
