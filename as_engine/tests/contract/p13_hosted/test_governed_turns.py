"""The host's budget decides what a hosted turn spends (P13, D-299). Rules HOST-06..HOST-09, HOST-14,
HOST-17, HOST-18 (host/governor.py, host/service.py, turn/pipeline.py stage 4).

The engine declares every step a turn could take, the required ones and the optional ones in the
order they go first, and asks before each optional one. The people a turn is about always decide;
who else thinks with a model, and how fully, is the host's to say. Every answer is written into the
turn's ledger so the turn can be played again exactly.
"""

from __future__ import annotations

import json

import pytest
from host_kit import actions, call, only

from as_engine.contracts.common import LOD
from as_engine.host.governor import TIERS, Governor, RecordedGovernor
from as_engine.host.protocol import b64

pytestmark = pytest.mark.phase(13)


class Scripted(Governor):
    def __init__(self, tier=3, focus=None, refuse=()):
        super().__init__(tier, focus)
        self.refuse, self.declared, self.asked = set(refuse), [], []

    async def declare(self, steps):
        self.declared.extend(steps)

    async def _ask(self, step):
        self.asked.append(step)
        return step not in self.refuse


CANDS = [("act_a", 5.0, True), ("act_b", 4.0, False), ("act_c", 3.0, False), ("act_d", 2.0, False), ("act_e", 0.0, False)]


async def test_the_ranks_are_an_upper_set(config):
    g = Scripted(tier=4)
    await g.start_turn(config)
    await g.plan_cognition(CANDS, config, 0, {"A", "B"})
    opt = [s for s in g.declared if not s.get("required")]
    ranks = [s["drop"] for s in opt]
    assert len(ranks) == len(set(ranks)), "every rank unique within the turn"
    by = {s["id"]: s["drop"] for s in opt}
    assert (by["audit:portrayal"] < by["ambient"] < by["waves:2+"] < by["mind:0:act_d"] < by["mind:0:act_c"]
            < by["mind:0:act_b"] < by["focus:0:act_c"] < by["focus:0:act_b"] < by["judge"])
    assert "mind:0:act_e" not in by, "D-190: nothing new, nothing to ask about"
    assert all("act_" not in s["label"] for s in g.declared), "a label never names anyone"
    req = {s["id"] for s in g.declared if s.get("required")}
    assert {"intake", "write", "mind:0:act_a"} <= req


async def test_everything_granted(config):
    g = Scripted(tier=4)
    plan = await g.plan_cognition(CANDS, config, 0, {"A", "B"})
    assert plan.lod["act_a"] == LOD.HOT and plan.lod["act_b"] == LOD.HOT and plan.lod["act_c"] == LOD.HOT
    assert plan.lod["act_d"] == LOD.WARM
    assert plan.lod["act_e"] == LOD.COLD, "D-190: nothing new, nothing to decide"
    assert plan.order == ["act_a", "act_b", "act_c", "act_d", "act_e"]


async def test_the_people_it_is_about_always_decide(config):
    g = Scripted(tier=3, refuse={"focus:0:act_a", "focus:0:act_b", "mind:0:act_b"})
    plan = await g.plan_cognition(CANDS, config, 0, {"A", "B"})
    assert plan.lod["act_a"] == LOD.WARM, "a mandatory mind refused full voice still decides"
    assert [plan.lod[a] for a in ("act_b", "act_c", "act_d")] == [LOD.COLD] * 3
    assert "mind:0:act_c" not in g.asked, "after one background mind is refused, nobody after it is asked"
    g = Scripted(tier=3, refuse={"focus:0:act_b"})
    plan = await g.plan_cognition(CANDS, config, 0, {"A", "B"})
    assert plan.lod["act_b"] == LOD.WARM, "refused full voice, a person still decides for themselves"


async def test_a_refused_focus_ends_the_focus(config):
    g = Scripted(tier=5, refuse={"focus:0:act_b"})
    plan = await g.plan_cognition(CANDS, config, 0, {"A", "B"})
    assert plan.lod["act_a"] == LOD.HOT and plan.lod["act_b"] == LOD.WARM and plan.lod["act_c"] == LOD.WARM
    assert "focus:0:act_c" not in g.asked


@pytest.mark.parametrize("tier", [1, 2])
async def test_the_fast_tiers_keep_background_minds_out(config, tier):
    g = Scripted(tier=tier)
    plan = await g.plan_cognition(CANDS, config, 0, {"A", "B"})
    assert plan.lod["act_a"] == (LOD.HOT if tier == 2 else LOD.WARM)
    assert all(plan.lod[a] == LOD.COLD for a in ("act_b", "act_c", "act_d", "act_e"))
    assert TIERS[tier]["depth"] == "quick"


async def test_late_waves_wait_on_the_host(config):
    g = Scripted(tier=4, refuse={"waves:2+"})
    plan = await g.plan_cognition(CANDS, config, 2, {"A", "B"})
    assert plan.lod["act_a"] in (LOD.HOT, LOD.WARM), "the people it is about still decide"
    assert [plan.lod[a] for a in ("act_b", "act_c", "act_d", "act_e")] == [LOD.COLD] * 4, \
        "a refused late wave leaves nobody else thinking, in focus or not"
    assert g.asked[0] == "waves:2+"


async def test_an_answer_is_given_once_a_turn(config):
    g = Scripted(tier=4)
    await g.plan_cognition(CANDS, config, 0, {"A", "B"})
    n = len(g.asked)
    p2 = await g.plan_cognition(CANDS, config, 0, {"A", "B"})
    assert len(g.asked) == n, "the strict retry asks nothing again (HOST-08)"
    r = RecordedGovernor(dict(g.plan_steps), tier=4)
    p3 = await r.plan_cognition(CANDS, config, 0, {"A", "B"})
    assert p3.lod == p2.lod and p3.lane == p2.lane


async def test_a_hosted_turn_records_its_budget(world0, host, hosted):
    h = host(may=lambda step: not step.startswith("mind:0:"))
    svc = hosted(h)
    await call(svc, "open", world=b64(world0))
    got = await call(svc, "turn", mode="do", text="I look over the fence.", tier=4)
    assert "error" not in got, got
    assert actions(got).count("turn_result") == 1
    assert set(got["steps"]) == set(h.asked)
    row = svc.session.store.query_one("SELECT detail FROM turn_ledger WHERE turn_index=1 AND stage=4")
    w0 = json.loads(row[0])["waves"][0]
    assert w0["tier"] == 4 and w0["steps"] and all(got["steps"][k] == v for k, v in w0["steps"].items())
    ids = {s["id"] for s in h.declared}
    assert {"intake", "write", "judge", "ambient", "audit:portrayal", "waves:2+"} <= ids


async def test_the_tier_sets_the_turns_depth(world0, host, hosted):
    svc = hosted(host())
    await call(svc, "open", world=b64(world0))
    await call(svc, "turn", mode="do", text="I look over the fence.", tier=1)
    assert svc.session.settings.turn_depth == "quick"
    ev = [json.loads(r[0]) for r in svc.session.store.query("SELECT payload FROM events WHERE type='SETTINGS_CHANGE' ORDER BY seq")]
    assert {"field": "turn_depth", "old": "balanced", "new": "quick"} in ev


async def test_a_stingy_host_still_gets_a_turn(world0, host, hosted):
    h = host(may=lambda step: False)
    svc = hosted(h)
    await call(svc, "open", world=b64(world0))
    got = await call(svc, "turn", mode="do", text="I look over the fence.", tier=3)
    r = only(got, "turn_result")
    assert r["narration"]
    classes = [p["work"]["call_class"] for _k, p in h.calls]
    assert "ambient_line" not in classes and "render_lint" not in classes and "portrayal_audit" not in classes
    assert classes.count("narration") >= 1 and "intake" in classes
    skipped = svc.session.store.query("SELECT call_class FROM lm_calls WHERE status='cancelled'")
    assert {r[0] for r in skipped} <= {"ambient_line", "render_lint", "portrayal_audit", "cascade_advisory"}


async def test_the_quiet_hours_run_only_when_the_host_asks(world0, host, hosted):
    svc = hosted(host())
    await call(svc, "open", world=b64(world0))
    await call(svc, "turn", mode="do", text="I look over the fence.", tier=3)
    assert not svc.background.running, "nothing starts between turns on its own (HOST-18)"
    got = await call(svc, "quiet")
    assert got.get("done") is True and "error" not in got
    assert not svc.background.running
