#!/usr/bin/env python3
"""The limits bench (docs/as/08_LLM_CALLS.md §7; BENCH-01, D-112). Run it on your machines; it needs no one.

  python tools/as/bench.py                 every stage on both lanes -> as_runs/reports/bench.json and bench.md
  python tools/as/bench.py --accept        ... then writes the measured settings into as_config.yaml
  python tools/as/bench.py --quick         a short pass: fewer rungs, one repeat, no halving
  python tools/as/bench.py --lane B        one lane (repeatable)
  python tools/as/bench.py --stages ladder,classes
  python tools/as/bench.py --resume        keep the stages already measured for the same models (after a Stop or a crash)
  python tools/as/bench.py --ctx-B 59136   a lane's context, when LM Studio does not report it
  python tools/as/bench.py --n 3           repeats per call class (default 2)
  python tools/as/bench.py --keep-budgets  --accept leaves the turn budgets alone
  python tools/as/bench.py --fake          the whole bench on two simulated lanes with known limits (no LM Studio)

It does not grade the models. It finds where each one's limits are, so the game can be set to them. It assumes
nothing about speed: consumer cards are slow (the owner's Writer writes about 5 tokens a second), so every stage
is sized to cost as little model time as finds the limit, and the report says how long each part took.

  identity     the model LM Studio serves and the context it was loaded with (its native API, when it says)
  probe        the thinking switch, JSON with thinking, prompt progress (tools/as/probe.py) — used by every
               later stage, so the rest of the bench thinks the way the game will
  ladder       prompts from 1K tokens up to the context limit, each a supply log with five facts hidden at five
               depths and one question about them: reading speed, the limit (a prompt the server refuses or
               silently cuts; found by halving the gap when LM Studio does not report it) and recall (how far in
               the model still finds the facts; the fade point found by halving) in ONE pass over long prompts
  cache        a repeated prompt prefix, and the same prefix after another prompt: what the KV cache saves
  decode       writing speed, thinking off and on, and how much of the output is thinking
  concurrency  1..4 requests at once: whether parallel slots add throughput
  classes      every call class the game makes, at its own regime, ``--n`` times in round robin (so no call
               rides its twin's cache): time, prompt size, thinking, whether ``max_tokens`` cut it short, whether
               the answer parsed; and the HOT decision on the OTHER lane too, so the report can compare

Then, from all of it: the longest silence while a model was writing (the stall window), the turn time each depth
costs with the HOT minds on either lane, and the settings. ``--accept`` writes: each lane's thinking switch,
JSON-with-thinking and prompt progress; ``max_concurrency``; ``stall_window_s`` (only ever raised); every regime's
``max_tokens`` that cut a call short (raised) and ``deadline_s`` (the expected seconds);
``rules.scheduler.estimated_call_s``; and, unless ``--keep-budgets``, ``reserve_narration_s`` and
``turn_budget_s`` set so each turn depth still admits at least the minds it was designed for (rules apply to new
runs, SET-03). It never moves a call to another lane: which model does what is the owner's choice (D-111).

No call is cut off for taking long (LANE-10). The one bound: when a server does not report prompt progress, a
prompt read that stays silent four times longer than the measured reading speed predicts (plus 10 minutes) is
reported as the limit, so an unattended run cannot hang on a dead server.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from _live import REPORTS, ROOT, load_config, save_config

VERSION = 3
STAGES = ("identity", "probe", "ladder", "cache", "decode", "concurrency", "classes")
LADDER = (1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072, 262144)
QUICK_LADDER = (1024, 4096, 16384)
ANSWER_ROOM = 512            # tokens left free for the answer at the top rung
NEAR_TOP = 0.85              # a rung within 15% of the top is skipped: the top rung measures it
HALVINGS = 3                 # each halving costs one long prompt; three put a limit within 1/8 of its gap
DEPTHS = (0.05, 0.25, 0.5, 0.75, 0.95)
COLORS = ("red", "blue", "green", "yellow", "white")
CODE_WORDS = ("MARIGOLD", "HARBOR", "CINDER", "LANTERN", "THISTLE", "BRAMBLE", "COPPER", "RAVEN")
RECALL_FLOOR = 0.8           # four facts in five
SCHED_KEYS = ("intake", "actor_cognition_hot", "actor_cognition_warm", "actor_reaction", "writeback",
              "portrayal_audit", "narration", "render_lint")       # SchedulerRules.estimated_call_s
CAPACITY_CANDIDATES = 80

_NAMES = ("Mara", "June", "Eli", "Nita", "Owen", "Carl", "Reggie", "Alice")
_ACTS = ("counted", "carried", "hid", "mended", "traded", "found", "cleaned", "checked")
_THINGS = ("a bent bicycle", "a jar of nails", "a torn map", "a box of candles", "a dead radio", "a coil of rope",
           "a dented kettle", "a pair of boots")
_PLACES = ("the pharmacy", "the bus depot", "the water tower", "the laundromat", "the school gym", "the boat ramp",
           "the feed store", "the church hall")
_TIMES = ("at dawn", "before noon", "after the rain", "at dusk", "late at night", "in the cold", "after supper",
          "on the second day")


# ============================================================================ prompts


def log_text(words: int, tag: str, needles: tuple = ()) -> str:
    """At least ``words`` words of an ordinary supply log (one line over at most), unique to ``tag`` from its first
    line — so no two prompts share a cached prefix unless the bench means them to — with each needle line placed
    at its depth."""
    lines, count, i = [], 0, 0
    while count < words:
        line = (f"{_NAMES[i % 8]} {_ACTS[(i // 8) % 8]} {_THINGS[(i // 64) % 8]} near {_PLACES[(i * 3 + 1) % 8]} "
                f"{_TIMES[(i * 5 + 2) % 8]}, entry {i}.")
        lines.append(line)
        count += len(line.split())
        i += 1
    for depth, line in sorted(needles, reverse=True):
        lines.insert(int(depth * len(lines)), line)
    return f"Supply log {tag}.\n" + " ".join(lines)


def code_words(length: int) -> list[str]:
    return [f"{CODE_WORDS[(i + length // 1024) % len(CODE_WORDS)]}-{(length // 7 + i * 131) % 900 + 100}"
            for i in range(len(COLORS))]


def recall_question() -> str:
    shape = ", ".join(f'"{c}": "..."' for c in COLORS)
    return ("Five lines in the log above say which code word opens a door. Give the code word for each door as "
            "JSON: {" + shape + "}. Answer with the JSON only.")


def score_recall(text: str, words: list[str]) -> tuple[list[bool], bool]:
    """(found per depth, the answer was the JSON asked for)."""
    from as_engine.lanes.parse import extract_json
    got = extract_json(text) if text else None
    hits = []
    for c, w in zip(COLORS, words):
        said = str(got.get(c, "")) if isinstance(got, dict) else text
        hits.append(w.lower() in said.lower())
    return hits, isinstance(got, dict) and set(COLORS) <= set(got)


# ============================================================================ pure analysis


def pct(values: list[float], q: float) -> float:
    v = sorted(values)
    if not v:
        return 0.0
    k = (len(v) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def round_up(x: float, step: float) -> float:
    return math.ceil(x / step) * step


def truncated(completion_tokens: int, max_tokens: int, status: str, reasoning_chars: int) -> bool:
    """A call cut short by ``max_tokens``: it used (nearly) all of them, or it thought and never answered."""
    return completion_tokens >= max_tokens - 4 or (status == "empty" and reasoning_chars > 0)


def recommend_concurrency(rows: list[dict]) -> int:
    """The most parallel requests that still pay: each step up must add at least 20% throughput over the
    current pick without more than doubling a request's own time against one alone."""
    ok = [r for r in sorted(rows, key=lambda r: r["k"]) if r.get("ok")]
    if not ok:
        return 1
    pick, one = ok[0], ok[0]
    for r in ok[1:]:
        if r["tok_s"] >= 1.2 * pick["tok_s"] and r["mean_latency_s"] <= 2.0 * one["mean_latency_s"]:
            pick = r
    return pick["k"]


def effective_context(rows: list[dict], floor: float = RECALL_FLOOR) -> int:
    """The longest prompt up to which every length found at least ``floor`` of the facts."""
    best = 0
    for r in sorted(rows, key=lambda r: r["tokens"]):
        if r["score"] < floor:
            break
        best = r["tokens"]
    return best


def capacity(depth: str) -> tuple[int, int]:
    """How many HOT and WARM minds a turn of this depth admits by DESIGN (the planner on the default numbers)."""
    from as_engine.contracts.common import LOD, Lane
    from as_engine.contracts.settings import EngineConfig
    from as_engine.lanes.scheduler import plan_cognition
    p = plan_cognition([(f"c{i:02d}", 1.0, False) for i in range(CAPACITY_CANDIDATES)], EngineConfig(), depth,
                       {Lane.A, Lane.B})
    lods = list(p.lod.values())
    return lods.count(LOD.HOT), lods.count(LOD.WARM)


def wave_wall(cfg, hot_n: int, warm_n: int) -> float:
    """The planner's wave estimate for ``hot_n`` HOT and ``warm_n`` WARM minds on ``cfg`` (its lanes, numbers)."""
    from as_engine.contracts.common import CallClass, Lane
    S = cfg.rules.scheduler
    tot = {Lane.A: 0.0, Lane.B: 0.0}
    tot[cfg.hot_cognition.lane] += hot_n * S.estimated_call_s["actor_cognition_hot"]
    tot[cfg.regimes[CallClass.ACTOR_COGNITION].lane] += warm_n * S.estimated_call_s["actor_cognition_warm"]
    return max(tot[Lane.A] / cfg.lanes[Lane.A].max_concurrency, tot[Lane.B] / cfg.lanes[Lane.B].max_concurrency)


def design_budgets(cfg) -> tuple[float, dict]:
    """(reserve_narration_s, turn_budget_s) on ``cfg``'s numbers so each depth admits at least the HOT and WARM
    minds it admits by design: the reserve is one narration and its lint, each budget that plus the wave."""
    E = cfg.rules.scheduler.estimated_call_s
    reserve = float(round_up(E["narration"] + E["render_lint"], 5))
    budgets = {}
    for depth in ("quick", "balanced", "deep"):
        hot_n, warm_n = capacity(depth)
        budgets[depth] = float(round_up(reserve + wave_wall(cfg, hot_n, warm_n) + 0.5, 5))
    return reserve, budgets


def with_scheduler(cfg, **upd):
    return cfg.model_copy(update={"rules": cfg.rules.model_copy(update={
        "scheduler": cfg.rules.scheduler.model_copy(update=upd)})})


def project_turns(cfg) -> dict:
    """A medium scene at each depth, on ``cfg``'s numbers: five people the planner sorts into HOT / WARM / COLD
    by the depth's budget (lanes.scheduler.plan_cognition), one reaction wave of two, five memory jobs; then
    the narration and its lint beside the writeback. {depth: {"s": seconds, "hot": n, "warm": n, "cold": n}}."""
    from as_engine.contracts.common import LOD, CallClass, Lane
    from as_engine.lanes.scheduler import plan_cognition
    E = cfg.rules.scheduler.estimated_call_s
    concb = cfg.lanes[cfg.regimes[CallClass.ACTOR_REACTION].lane].max_concurrency
    concw = cfg.lanes[cfg.regimes[CallClass.WRITEBACK].lane].max_concurrency
    out = {}
    for depth in ("quick", "balanced", "deep"):
        plan = plan_cognition([(f"p{i}", 5.0 - i, False) for i in range(5)], cfg, depth, {Lane.A, Lane.B})
        lods = list(plan.lod.values())
        tail = max(E["narration"] + E["render_lint"], 5 * E["writeback"] / concw)
        out[depth] = {"s": round(E["intake"] + plan.est_wall_s + 2 * E["actor_reaction"] / concb + tail, 1),
                      "hot": lods.count(LOD.HOT), "warm": lods.count(LOD.WARM), "cold": lods.count(LOD.COLD)}
    return out


def flipped_hot(cfg, report: dict):
    """``cfg`` with the HOT minds on the other lane, timed by the HOT call the bench measured there; None when it
    was not measured. Budgets are re-derived for it the same way, so the two placements compare fairly."""
    from as_engine.contracts.common import Lane
    other = Lane.B if cfg.hot_cognition.lane == Lane.A else Lane.A
    row = (report.get("classes") or {}).get(f"actor_cognition_hot@{other.value}")
    if not row or not row.get("ok"):
        return None
    est = dict(cfg.rules.scheduler.estimated_call_s, actor_cognition_hot=round(row["mean_s"], 1))
    alt = with_scheduler(cfg, estimated_call_s=est).model_copy(update={
        "hot_cognition": cfg.hot_cognition.model_copy(update={"lane": other})})
    reserve, budgets = design_budgets(alt)
    return with_scheduler(alt, reserve_narration_s=reserve, turn_budget_s=budgets)


def recommend(report: dict, cfg, *, keep_budgets: bool = False):
    """(new config, [what changed]) from a bench report. Pure: writes nothing. Never moves a call to another lane."""
    from as_engine.contracts.common import CallClass, Lane
    new = cfg.model_copy(deep=True)
    changes: list[str] = []

    def lane_set(lane: Lane, field: str, value) -> None:
        old = getattr(new.lanes[lane], field)
        if value is not None and value != old:
            new.lanes[lane] = new.lanes[lane].model_copy(update={field: value})
            changes.append(f"lanes.{lane.value}.{field}: {old} -> {value}")

    for key, L in report.get("lanes", {}).items():
        lane = Lane(key)
        pr = L.get("probe") or {}
        lane_set(lane, "thinking_mode", pr.get("thinking_mode"))
        for f in ("structured_with_thinking", "prefill_progress"):
            if pr.get(f) in ("supported", "unsupported"):
                lane_set(lane, f, pr[f])
        if (L.get("concurrency") or {}).get("recommended"):
            lane_set(lane, "max_concurrency", L["concurrency"]["recommended"])
        gap = (L.get("stall") or {}).get("max_gap_s") or 0.0
        want = round_up(3 * gap, 30)
        if want > new.lanes[lane].stall_window_s:
            lane_set(lane, "stall_window_s", float(want))

    rows = report.get("classes", {})
    for key, row in sorted(rows.items()):
        if key == "actor_cognition_hot":
            reg, where = new.hot_cognition, "hot_cognition"
        else:
            cc = CallClass(row["call_class"])
            if key not in (cc.value, "actor_cognition_warm"):
                continue                         # e.g. the HOT call measured on the other lane: a comparison only
            reg, where = new.regimes[cc], f"regimes.{cc.value}"
        upd = {}
        if row.get("truncated"):
            want = int(round_up(max(2 * reg.max_tokens, 1.5 * row.get("completion_max", 0)), 256))
            ctx = ((report["lanes"].get(row["lane"]) or {}).get("ladder") or {}).get("limit")
            if ctx:
                want = min(want, int(ctx) - int(row.get("prompt_tokens", 0)) - 256)
            if want > reg.max_tokens:
                upd["max_tokens"] = want
        if row.get("ok"):
            expect = float(round_up(max(row["p90_s"], 1.0), 5))
            if expect != reg.deadline_s:
                upd["deadline_s"] = expect
        if upd:
            changes += [f"{where}.{k}: {getattr(reg, k)} -> {v}" for k, v in upd.items()]
            reg2 = reg.model_copy(update=upd)
            if key == "actor_cognition_hot":
                new.hot_cognition = reg2
            else:
                new.regimes[CallClass(row["call_class"])] = reg2

    S = new.rules.scheduler
    est = dict(S.estimated_call_s)
    for k in SCHED_KEYS:
        if k in rows and rows[k].get("ok"):
            est[k] = round(rows[k]["mean_s"], 1)
    changes += [f"rules.scheduler.estimated_call_s.{k}: {S.estimated_call_s.get(k)} -> {v}"
                for k, v in est.items() if S.estimated_call_s.get(k) != v]
    new = with_scheduler(new, estimated_call_s=est)
    measured = all(k in rows and rows[k].get("ok") for k in ("narration", "render_lint", "actor_cognition_hot",
                                                             "actor_cognition_warm"))
    if not keep_budgets and measured:
        reserve, budgets = design_budgets(new)
        if reserve != S.reserve_narration_s:
            changes.append(f"rules.scheduler.reserve_narration_s: {S.reserve_narration_s} -> {reserve}")
        changes += [f"rules.scheduler.turn_budget_s.{d}: {S.turn_budget_s.get(d)} -> {v}"
                    for d, v in budgets.items() if v != S.turn_budget_s.get(d)]
        new = with_scheduler(new, reserve_narration_s=reserve, turn_budget_s=budgets)
    return new, changes


# ============================================================================ measuring


@dataclass
class Shot:
    status: str
    error: str | None
    prompt_tokens: int
    completion_tokens: int
    ttft_s: float | None          # until the first token (thinking or text)
    total_s: float
    max_gap_s: float              # the longest stretch without progress after the first token
    prefill_reported: bool
    reasoning_chars: int
    text: str
    parsed: dict | None

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    @property
    def read_s(self) -> float:
        return self.ttft_s if self.ttft_s is not None else self.total_s

    @property
    def decode_s(self) -> float:
        return max(self.total_s - self.read_s, 1e-6)


class Bench:
    def __init__(self, cfg, transport, *, clock=time.perf_counter, quick: bool = False, n: int = 2,
                 ctx_override: dict | None = None, log=print, fake: bool = False):
        from as_engine.lanes.client import LaneClient
        self.base = cfg
        self.cfg = cfg.model_copy(deep=True)
        self.transport = transport
        self.client = LaneClient(self.cfg, transport)
        self.client.on_progress = self._progress
        self.clock, self.quick, self.n, self.log = clock, quick, n, log
        self.ctx_override = {k: v for k, v in (ctx_override or {}).items() if v}
        self.report: dict = {"version": VERSION, "fake": fake, "quick": quick, "lanes": {}, "classes": {}}
        self.watch: dict[int, dict] = {}
        self.gaps: dict[str, list[float]] = {}
        self.seq = 0

    # -- one call ---------------------------------------------------------------------------------------

    def _progress(self, request, snap: dict | None) -> None:
        w = self.watch.get(id(request))
        if w is None or snap is None:            # None: the call has ended (LANE-11)
            return
        t = self.clock()
        if snap.get("prompt_total"):
            w["prefill"] = True
        mark = (snap.get("text_chars"), snap.get("reasoning_chars"))
        if w["first"] is None:
            if snap.get("phase") in ("thinking", "writing"):
                w["first"] = w["last"] = t
                w["mark"] = mark
            return
        w["gap"] = max(w["gap"], t - w["last"])
        if mark != w["mark"]:
            w["mark"], w["last"] = mark, t

    async def shot(self, request, output_model=None, *, silent_bound: float | None = None) -> Shot:
        lane = request.lane
        saved = self.cfg.lanes[lane]
        if silent_bound and saved.prefill_progress != "supported":
            self.cfg.lanes[lane] = saved.model_copy(update={"silent_prefill_window_s": silent_bound})
        w = {"first": None, "last": None, "mark": None, "gap": 0.0, "prefill": False}
        self.watch[id(request)] = w
        t0 = self.clock()
        try:
            r = await self.client.call(request, output_model)
        finally:
            self.watch.pop(id(request), None)
            if silent_bound:
                self.cfg.lanes[lane] = saved
        t1 = self.clock()
        if r.parse_status == "lane_error":
            self.client.mark_down(lane, False)          # a refused prompt is a finding, not a dead lane
        s = Shot(status=r.parse_status, error=r.error, prompt_tokens=r.prompt_tokens,
                 completion_tokens=r.completion_tokens, ttft_s=None if w["first"] is None else w["first"] - t0,
                 total_s=t1 - t0, max_gap_s=w["gap"], prefill_reported=w["prefill"],
                 reasoning_chars=len(r.reasoning or ""), text=r.text or "", parsed=r.parsed)
        self.gaps.setdefault(lane.value, []).append(s.max_gap_s)
        return s

    def request(self, lane, user: str, *, system: str = "You read carefully and follow the last instruction exactly.",
                thinking: bool = False, max_tokens: int = 16, temperature: float = 0.0, expected: float = 60.0):
        from as_engine.contracts.common import CallClass
        from as_engine.contracts.lanes import ChatMessage, LMRequest
        return LMRequest(call_class=CallClass.PROBE, lane=lane, temperature=temperature, max_tokens=max_tokens,
                         thinking=thinking, deadline_s=max(expected, 1.0),
                         messages=[ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)])

    def tag(self, what: str) -> str:
        self.seq += 1
        return f"{what} #{self.seq}"

    def lanes(self, lane) -> dict:
        return self.report["lanes"].setdefault(lane.value, {})

    def tpw(self, lane) -> float:
        return self.lanes(lane).get("tokens_per_word") or 1.4

    async def read(self, lane, target: int, *, tail: str = "ready", prefix: str | None = None) -> Shot:
        """A prompt of about ``target`` tokens (or ``prefix``) that asks for one word."""
        text = prefix if prefix is not None else log_text(max(20, int((target - 40) / self.tpw(lane))), self.tag("read"))
        return await self.shot(self.request(lane, text + f"\n\nReply with the single word: {tail}"), silent_bound=600.0)

    async def rung(self, lane, target: int, rate: float | None, what: str) -> dict:
        """One rung of the ladder: a supply log of about ``target`` tokens with the five facts, and the question.
        Measures the read (time to the first token), whether the server took the whole prompt, and recall."""
        words = code_words(target)
        needles = tuple((d, f"Remember this: the {c} door's code word is {w}.") for d, c, w in zip(DEPTHS, COLORS, words))
        text = log_text(max(20, int((target - 120) / self.tpw(lane))), self.tag(f"{what} {target}"), needles)
        expected = target / rate if rate else 60.0
        req = self.request(lane, text + "\n\n" + recall_question(), system="You read long documents and answer exactly.",
                           max_tokens=300, expected=expected)
        s = await self.shot(req, silent_bound=600.0 + 4 * expected)
        cut = s.ok and s.prompt_tokens and s.prompt_tokens < 0.85 * target
        ok = s.ok and not cut and s.prompt_tokens > 0
        hits, fmt = score_recall(s.text, words) if ok else ([False] * len(COLORS), False)
        row = {"target": target, "prompt_tokens": s.prompt_tokens, "read_s": round(s.read_s, 2),
               "rate_tok_s": round(s.prompt_tokens / s.read_s, 1) if ok and s.read_s > 0 else None,
               "silent": not s.prefill_reported, "ok": bool(ok), "status": s.status,
               "error": ("the server cut the prompt to %d tokens" % s.prompt_tokens) if cut else s.error,
               "hits": hits, "score": round(sum(hits) / len(hits), 2), "format_ok": fmt,
               "words": len(text.split())}
        if ok:
            self.log(f"[{lane.value} {what} {target:>6}] {row['prompt_tokens']:,} tokens read in {_dur(row['read_s'])} "
                     f"({row['rate_tok_s']:,.0f} tok/s); recall {sum(hits)}/5 "
                     + " ".join(f"{int(d * 100)}%:{'y' if h else 'n'}" for d, h in zip(DEPTHS, hits)))
        else:
            self.log(f"[{lane.value} {what} {target:>6}] refused or cut: {row['error'] or row['status']}")
        return row

    # -- stages -----------------------------------------------------------------------------------------

    async def stage_identity(self, lane) -> dict:
        lc = self.cfg.lanes[lane]
        out = {"model": lc.model, "base_url": lc.base_url}
        try:
            out["listed"] = lc.model in await self.transport.list_models(lane, lc)
        except Exception as e:  # noqa: BLE001
            out.update(reachable=False, error=str(e)[:200])
            return out
        out["reachable"] = True
        info = await native_info(self.transport, lc)
        out.update({k: info[k] for k in ("max_context_length", "loaded_context_length", "quantization", "arch", "state")
                    if k in info})
        if self.ctx_override.get(lane.value):
            out["context"], out["context_source"] = int(self.ctx_override[lane.value]), "--ctx"
        elif info.get("loaded_context_length"):
            out["context"], out["context_source"] = int(info["loaded_context_length"]), "LM Studio"
        else:
            out["context"], out["context_source"] = None, "unknown: the ladder finds it"
        return out

    async def stage_probe(self, lane) -> dict:
        import probe as probe_tool
        r = await probe_tool.probe_lane(lane, self.cfg, self.transport)
        out = {k: r.get(k) for k in ("thinking_mode", "thinking_on_works", "json_schema", "structured_with_thinking",
                                     "prefill_progress", "time_to_first_token_s", "prompt_tokens_per_s")}
        self.apply_probe(lane, out)
        return out

    def apply_probe(self, lane, out: dict) -> None:
        upd = {}
        if out.get("thinking_mode"):
            upd["thinking_mode"] = out["thinking_mode"]
        for f in ("structured_with_thinking", "prefill_progress"):
            if out.get(f) in ("supported", "unsupported"):
                upd[f] = out[f]
        self.cfg.lanes[lane] = self.cfg.lanes[lane].model_copy(update=upd)

    async def stage_ladder(self, lane) -> dict:
        ctx = (self.lanes(lane).get("identity") or {}).get("context")
        cal = await self.rung(lane, 1500, None, "calibrate")
        tpw = round(cal["prompt_tokens"] / cal["words"], 3) if cal["ok"] and cal["words"] else 1.4
        self.lanes(lane)["tokens_per_word"] = tpw
        top = ctx - ANSWER_ROOM if ctx else None
        rungs = [r for r in (QUICK_LADDER if self.quick else LADDER) if top is None or r < top * NEAR_TOP]
        if top and not self.quick:
            rungs.append(top)
        rows, fail, rate = [], None, None
        for target in rungs:
            row = await self.rung(lane, target, rate, "rung")
            if not row["ok"]:
                fail = row
                break
            rows.append(row)
            rate = row["rate_tok_s"] or rate
        found = max((r["prompt_tokens"] for r in rows), default=0)
        if ctx is None and fail is not None and rows and not self.quick:
            lo, hi = found, fail["target"]
            for _ in range(HALVINGS):
                mid = (lo + hi) // 2
                row = await self.rung(lane, mid, rate, "limit")
                if row["ok"]:
                    rows.append(row)
                    lo = max(lo, row["prompt_tokens"])
                else:
                    hi, fail = mid, row
            found = lo
        good = sorted(rows, key=lambda r: r["prompt_tokens"])
        fade = next((r for r in good if r["score"] < RECALL_FLOOR), None)
        if fade is not None and not self.quick:                        # where between two rungs does recall fade?
            lo = max((r["target"] for r in good if r["score"] >= RECALL_FLOOR and r["target"] < fade["target"]), default=0)
            hi = fade["target"]
            for _ in range(HALVINGS):
                if not lo or hi - lo < 1024:
                    break
                mid = (lo + hi) // 2
                row = await self.rung(lane, mid, rate, "recall")
                if not row["ok"]:
                    break
                rows.append(row)
                if row["score"] >= RECALL_FLOOR:
                    lo = mid
                else:
                    hi = mid
            good = sorted(rows, key=lambda r: r["prompt_tokens"])
        limit = ctx if ctx else (found if fail is not None else None)
        return {"tokens_per_word": tpw, "rungs": good, "failure": fail, "max_read_tokens": found, "limit": limit,
                "limit_source": "context" if ctx else ("found" if fail is not None else "not reached"),
                "recall_tokens": effective_context([{"tokens": r["prompt_tokens"], "score": r["score"]} for r in good]),
                "format_ok": sum(r["format_ok"] for r in good), "rung_count": len(good)}

    async def stage_cache(self, lane) -> dict:
        lad = self.lanes(lane).get("ladder") or {}
        size = int(min(4096, max(1024, (lad.get("max_read_tokens") or 4096) * 0.5)))
        P = log_text(int(size / self.tpw(lane)), self.tag("cache P"))
        Q = log_text(int(size / self.tpw(lane)), self.tag("cache Q"))
        cold = await self.read(lane, size, prefix=P, tail="ready")
        again = await self.read(lane, size, prefix=P, tail="done")
        await self.read(lane, size, prefix=Q, tail="ready")
        after = await self.read(lane, size, prefix=P, tail="yes")
        base = max(cold.read_s, 1e-6)
        out = {"tokens": cold.prompt_tokens, "cold_s": round(cold.read_s, 2), "repeat_s": round(again.read_s, 2),
               "after_other_s": round(after.read_s, 2), "repeat_share": round(again.read_s / base, 3),
               "after_other_share": round(after.read_s / base, 3), "ok": cold.ok and again.ok and after.ok}
        self.log(f"[{lane.value} cache] a repeated prefix costs {out['repeat_share']:.0%} of a cold read; "
                 f"after another prompt, {out['after_other_share']:.0%}")
        return out

    async def stage_decode(self, lane) -> dict:
        rows = []
        for thinking in (False, True):
            req = self.request(lane, "Write a story of about 200 words about a lighthouse keeper who finds a stranger "
                                     "on the rocks. Plain prose, no headings.", system="You are a writer.",
                               thinking=thinking, max_tokens=2048 if thinking else 600, temperature=0.8, expected=120)
            s = await self.shot(req)
            tc = len(s.text)
            row = {"thinking": thinking, "ok": s.ok, "completion_tokens": s.completion_tokens,
                   "write_s": round(s.decode_s, 2), "tok_s": round(s.completion_tokens / s.decode_s, 1) if s.ok else None,
                   "thought": s.reasoning_chars > 0, "think_share": round(s.reasoning_chars / max(s.reasoning_chars + tc, 1), 2),
                   "status": s.status, "cut_short": truncated(s.completion_tokens, req.max_tokens, s.status, s.reasoning_chars)}
            self.log(f"[{lane.value} decode thinking={'on' if thinking else 'off'}] "
                     f"{row['completion_tokens']} tokens in {_dur(row['write_s'])} ({row['tok_s']} tok/s), "
                     f"thought: {row['thought']} ({row['think_share']:.0%} of the output)")
            rows.append(row)
        return {"runs": rows}

    async def stage_concurrency(self, lane) -> dict:
        rows = []
        for k in range(1, (2 if self.quick else 4) + 1):
            reqs = [self.request(lane, log_text(int(600 / self.tpw(lane)), self.tag(f"parallel {k}")) +
                                 "\n\nWrite about 80 words about what the log above shows.",
                                 max_tokens=200, temperature=0.7, expected=60) for _ in range(k)]
            t0 = self.clock()
            shots = await asyncio.gather(*(self.shot(r) for r in reqs))
            wall = max(self.clock() - t0, 1e-6)
            row = {"k": k, "wall_s": round(wall, 2), "tok_s": round(sum(s.completion_tokens for s in shots) / wall, 2),
                   "mean_latency_s": round(statistics.mean(s.total_s for s in shots), 2), "ok": all(s.ok for s in shots)}
            self.log(f"[{lane.value} parallel {k}] {row['tok_s']} tok/s together, {_dur(row['mean_latency_s'])} each")
            rows.append(row)
        return {"runs": rows, "recommended": recommend_concurrency(rows)}

    async def stage_classes(self, lane) -> dict:
        from as_engine.lanes.schemas import OUTPUT_MODELS
        out = {}
        plan = [(key, cc, req) for key, cc, req in class_requests(self.cfg) if req.lane == lane]
        got: dict[str, list[Shot]] = {key: [] for key, _cc, _r in plan}
        for _ in range(self.n):              # round robin: no call follows its own twin, so none rides its cache
            for key, cc, req in plan:
                got[key].append(await self.shot(req.model_copy(), OUTPUT_MODELS.get(cc)))
        for key, cc, req in plan:
            shots = got[key]
            lat = [s.total_s for s in shots]
            row = {"call_class": cc.value, "lane": lane.value, "thinking": req.thinking, "max_tokens": req.max_tokens,
                   "schema": req.json_schema is not None, "n": len(shots),
                   "mean_s": round(statistics.mean(lat), 2), "p90_s": round(pct(lat, 0.9), 2),
                   "ttft_s": round(statistics.mean(s.read_s for s in shots), 2),
                   "prompt_tokens": max(s.prompt_tokens for s in shots),
                   "completion_max": max(s.completion_tokens for s in shots),
                   "reasoning_chars": int(statistics.mean(s.reasoning_chars for s in shots)),
                   "parsed": sum(s.ok for s in shots), "statuses": sorted({s.status for s in shots}),
                   "truncated": sum(truncated(s.completion_tokens, req.max_tokens, s.status, s.reasoning_chars)
                                    for s in shots)}
            row["ok"] = row["parsed"] > 0
            self.log(f"[{lane.value} {key}] {_dur(row['mean_s'])} (p90 {_dur(row['p90_s'])}), {row['prompt_tokens']} in, "
                     f"{row['completion_max']} out of {row['max_tokens']}, parsed {row['parsed']}/{row['n']}"
                     + (f", CUT SHORT {row['truncated']}x" if row["truncated"] else ""))
            out[key] = row
        self.report["classes"].update(out)
        return {"measured": sorted(out)}

    # -- the whole run ----------------------------------------------------------------------------------

    async def run(self, lanes, stages, *, resume: dict | None = None, save=None, keep_budgets: bool = False) -> dict:
        if resume:
            self.adopt(resume)
        for lane in lanes:
            L = self.lanes(lane)
            for stage in stages:
                if stage == "identity" and (L.get("identity") or {}).get("reachable"):
                    continue
                if stage in L and stage != "identity":
                    self.log(f"[{lane.value} {stage}] kept from the last run")
                    if stage == "probe":
                        self.apply_probe(lane, L["probe"])
                    continue
                self.log(f"[{lane.value}] {stage} ...")
                t0 = self.clock()
                L[stage] = await getattr(self, f"stage_{stage}")(lane)
                L.setdefault("took_s", {})[stage] = round(self.clock() - t0, 1)
                if save:
                    save(self.report)
                if stage == "identity" and not L[stage].get("reachable"):
                    self.log(f"[{lane.value}] not reachable: {L[stage].get('error')} — skipping this lane")
                    break
        for key, L in self.report["lanes"].items():
            gaps = self.gaps.get(key, [])
            L["stall"] = {"max_gap_s": round(max(gaps + [(L.get("stall") or {}).get("max_gap_s", 0.0)]), 2)}
        new, changes = recommend(self.report, self.base, keep_budgets=keep_budgets)
        measured_only = with_scheduler(self.base, estimated_call_s=new.rules.scheduler.estimated_call_s)
        flip = flipped_hot(new, self.report)
        self.report["projection"] = {"now": project_turns(measured_only), "after": project_turns(new),
                                     "hot_lane": new.hot_cognition.lane.value,
                                     "other_hot_lane": project_turns(flip) if flip is not None else None}
        self.report["changes"] = changes
        self.report["complete"] = True
        return self.report

    def adopt(self, old: dict) -> None:
        """Keep an earlier run's stages for lanes whose model is the same."""
        from as_engine.contracts.common import Lane
        for key, L in (old.get("lanes") or {}).items():
            lc = self.cfg.lanes.get(Lane(key))
            if lc is not None and (L.get("identity") or {}).get("model") == lc.model:
                self.report["lanes"][key] = L
        for k, row in (old.get("classes") or {}).items():
            if row.get("lane") in self.report["lanes"]:
                self.report["classes"][k] = row


async def native_info(transport, lane) -> dict:
    """LM Studio's own model record (GET /api/v0/models/{id}): the loaded context, quantisation, state. {} when
    the server has no such API. Same host as the lane (the seal, SEAL-01); the client never reads proxies."""
    if hasattr(transport, "native_info"):
        return await transport.native_info(lane)
    client = getattr(transport, "_c", None)
    if client is None:
        return {}
    root = lane.base_url.rstrip("/")
    root = root[:-3] if root.endswith("/v1") else root
    try:
        r = await client.get(f"{root}/api/v0/models/{lane.model}", headers={"Authorization": f"Bearer {lane.api_key}"},
                             timeout=10)
        data = r.json() if r.status_code < 400 else {}
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 — not LM Studio, or an older one
        return {}


def class_requests(cfg) -> list:
    """(bench key, call class, the game's own request) for every call class, from the protected prompt samples; and
    the HOT decision on the other lane as ``actor_cognition_hot@<lane>`` (a comparison: it changes no setting)."""
    sys.path.insert(0, str(ROOT / "as_engine" / "tests" / "fixtures" / "prompt_samples"))
    import samples
    from as_engine.contracts.calls import WritebackContext
    from as_engine.contracts.common import LOD, CallClass, Lane
    from as_engine.lanes.requests import build_request
    from as_engine.lanes.schemas import OUTPUT_MODELS, to_lm_schema
    from as_engine.turn.cognition import cognition_request

    kw = samples.render_kwargs()
    p = kw[CallClass.ACTOR_COGNITION]["p"]
    other = Lane.B if cfg.hot_cognition.lane == Lane.A else Lane.A
    out = [("actor_cognition_hot", CallClass.ACTOR_COGNITION,
            cognition_request(cfg, p, LOD.HOT, cfg.hot_cognition.lane, reaction=False, turn_index=1)),
           (f"actor_cognition_hot@{other.value}", CallClass.ACTOR_COGNITION,
            cognition_request(cfg, p, LOD.HOT, other, reaction=False, turn_index=1)),
           ("actor_cognition_warm", CallClass.ACTOR_COGNITION,
            cognition_request(cfg, p, LOD.WARM, cfg.regimes[CallClass.ACTOR_COGNITION].lane, reaction=False, turn_index=1)),
           ("actor_reaction", CallClass.ACTOR_REACTION,
            cognition_request(cfg, p, LOD.WARM, cfg.regimes[CallClass.ACTOR_REACTION].lane, reaction=True, turn_index=1))]
    for cc, kws in kw.items():
        if cc in (CallClass.ACTOR_COGNITION, CallClass.ACTOR_REACTION, CallClass.PROBE):
            continue
        model = OUTPUT_MODELS.get(cc)
        context = WritebackContext(aftermath=kws["a"]) if "a" in kws else kws.get("ctx", kws.get("k", kws.get("p")))
        req = build_request(cfg, cc, turn_index=1, context=context,
                            json_schema=to_lm_schema(model) if model else None, **kws)
        out.append((cc.value, cc, req))
    return out


# ============================================================================ the report


def markdown(report: dict) -> str:
    lines = ["# The limits bench", "",
             f"{'Simulated lanes (--fake). ' if report.get('fake') else ''}"
             f"{'A quick pass. ' if report.get('quick') else ''}What each model can do on these machines, "
             "and the settings that follow from it. Nothing here grades a model: it says where the limits are.", ""]
    roles = {"A": "the Writer", "B": "the Clerk"}
    for key, L in sorted(report.get("lanes", {}).items()):
        idn = L.get("identity") or {}
        lines += [f"## Lane {key} — {idn.get('model', '?')} ({roles.get(key, '')})", ""]
        if not idn.get("reachable", True):
            lines += [f"Not reachable: {idn.get('error')}", ""]
            continue
        pr, ld = L.get("probe") or {}, L.get("ladder") or {}
        if idn.get("context"):
            lines.append(f"- **Context**: {idn['context']:,} tokens (from {idn.get('context_source')})")
        elif ld.get("limit"):
            lines.append(f"- **Context**: found by the ladder: reads {ld['limit']:,} tokens, refuses "
                         f"{(ld.get('failure') or {}).get('target', 0):,}")
        elif ld:
            lines.append("- **Context**: no limit reached by the ladder")
        if pr:
            lines.append(f"- **Thinking switch**: {pr.get('thinking_mode')} (turns thinking on: "
                         f"{pr.get('thinking_on_works')}); JSON while thinking: {pr.get('structured_with_thinking')}; "
                         f"prompt progress: {pr.get('prefill_progress')}")
        if ld.get("rungs"):
            lines.append("- **Reading speed**: " + " · ".join(
                f"{_k(r['prompt_tokens'])} {r['rate_tok_s']:,.0f} tok/s" for r in ld["rungs"] if r.get("rate_tok_s")))
            big = max(ld["rungs"], key=lambda r: r["prompt_tokens"])
            lines.append(f"- **Largest prompt read**: {big['prompt_tokens']:,} tokens in {_dur(big['read_s'])}"
                         + (f"; refused or cut at {ld['failure']['target']:,}" if ld.get("failure") else ""))
            lines.append("- **Recall** (5 facts at 5%/25%/50%/75%/95% of the prompt): " + " · ".join(
                f"{_k(r['prompt_tokens'])} {int(round(r['score'] * 5))}/5" for r in ld["rungs"])
                + f" → reliable to about {ld['recall_tokens']:,} tokens; answered in the JSON asked for "
                  f"{ld['format_ok']}/{ld['rung_count']}")
        c = L.get("cache") or {}
        if c:
            lines.append(f"- **Prompt cache**: repeating a {c['tokens']:,}-token prefix costs {c['repeat_share']:.0%} "
                         f"of a cold read; after another prompt in between, {c['after_other_share']:.0%}")
        d = (L.get("decode") or {}).get("runs") or []
        if d:
            lines.append("- **Writing speed**: " + " · ".join(
                f"thinking {'on' if r['thinking'] else 'off'} {r['tok_s']} tok/s"
                + (f" ({r['think_share']:.0%} of it thinking)" if r["thinking"] else "") for r in d))
        cc = L.get("concurrency") or {}
        if cc.get("runs"):
            lines.append("- **Parallel requests**: " + " · ".join(
                f"{r['k']} → {r['tok_s']} tok/s, {_dur(r['mean_latency_s'])} each" for r in cc["runs"])
                + f" → use {cc['recommended']}")
        st = L.get("stall") or {}
        if st:
            lines.append(f"- **Longest silence while writing**: {_dur(st['max_gap_s'])}")
        if L.get("took_s"):
            lines.append("- **Bench time**: " + " · ".join(f"{k} {_dur(v)}" for k, v in L["took_s"].items()))
        lines.append("")
    rows = report.get("classes") or {}
    if rows:
        lines += ["## The game's calls", "",
                  "| Call | Lane | Thinks | Mean | p90 | Prompt | Thinking (chars) | Out (max) / cap | Parsed | Cut short |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for k, r in sorted(rows.items(), key=lambda kv: (kv[1]["lane"], kv[0])):
            lines.append(f"| {k} | {r['lane']} | {'yes' if r['thinking'] else 'no'} | {_dur(r['mean_s'])} | "
                         f"{_dur(r['p90_s'])} | {r['prompt_tokens']:,} | {r['reasoning_chars']:,} | "
                         f"{r['completion_max']:,} / {r['max_tokens']:,} | {r['parsed']}/{r['n']} | {r['truncated'] or ''} |")
        lines.append("")
    pj = report.get("projection") or {}
    if pj:
        hot = pj.get("hot_lane", "A")
        other = "B" if hot == "A" else "A"
        flip = pj.get("other_hot_lane")
        head = (f"| Depth | Today's lane settings | After --accept (HOT on {hot}) | After --accept, HOT on {other} instead |"
                if flip else "| Depth | Today's lane settings | After --accept |")
        lines += ["## A medium scene, per turn depth (an estimate from the measured call times)", "",
                  "Five people, sorted by the planner into HOT, WARM and no call by the depth's budget; one reaction wave "
                  "of two; five memory jobs; the narration and its lint beside the writeback.", "",
                  head, "|---|---|---|" + ("---|" if flip else "")]
        for dpt in ("quick", "balanced", "deep"):
            cells = [_scene(pj["now"][dpt]), _scene(pj["after"][dpt])] + ([_scene(flip[dpt])] if flip else [])
            lines.append(f"| {dpt} | " + " | ".join(cells) + " |")
        lines.append("")
    lines += ["## What --accept changes", ""]
    lines += [f"- `{c}`" for c in report.get("changes") or []] or ["- nothing"]
    return "\n".join(lines) + "\n"


def _k(tokens: int) -> str:
    return f"{tokens / 1000:.1f}K" if tokens < 10000 else f"{tokens / 1000:.0f}K"


def _scene(p: dict) -> str:
    return f"{_dur(p['s'])} ({p['hot']} HOT, {p['warm']} WARM, {p['cold']} without a model call)"


def _dur(s: float) -> str:
    s = float(s)
    if s < 90:
        return f"{s:.1f} s"
    if s < 5400:
        return f"{int(s // 60)} min {int(s % 60)} s"
    return f"{int(s // 3600)} h {int(s % 3600 // 60)} min"


# ============================================================================ main


def parse(argv):
    a = argparse.ArgumentParser(description="The limits bench (docs/as/08_LLM_CALLS.md §7)")
    a.add_argument("--accept", action="store_true")
    a.add_argument("--quick", action="store_true")
    a.add_argument("--fake", action="store_true")
    a.add_argument("--resume", action="store_true")
    a.add_argument("--keep-budgets", action="store_true")
    a.add_argument("--lane", action="append", choices=("A", "B"))
    a.add_argument("--stages", default=",".join(STAGES))
    a.add_argument("--n", type=int, default=None)
    a.add_argument("--ctx-A", type=int, default=None)
    a.add_argument("--ctx-B", type=int, default=None)
    a.add_argument("--out", default=None, help="report directory (default as_runs/reports)")
    return a.parse_args(argv)


async def main(argv=None, *, sim_models=None, sim_scale: float = 0.002) -> int:
    from as_engine.contracts.common import Lane
    args = parse(argv if argv is not None else sys.argv[1:])
    unknown = [s for s in args.stages.split(",") if s and s not in STAGES]
    if unknown:
        print(f"unknown stage(s): {', '.join(unknown)} (stages: {', '.join(STAGES)})", file=sys.stderr)
        return 2
    stages = [s for s in STAGES if s in args.stages.split(",")]
    if "identity" not in stages:
        stages.insert(0, "identity")
    out_dir = Path(args.out) if args.out else REPORTS
    name = "bench.fake" if args.fake else "bench"
    if args.fake:
        from as_engine.contracts.settings import EngineConfig
        from benchsim import SimTransport
        cfg, transport = EngineConfig(), SimTransport(sim_models, scale=sim_scale)
        clock = transport.clock
    else:
        from as_engine.lanes.transport import HttpTransport
        cfg, transport, clock = load_config(), HttpTransport(), time.perf_counter
    n = args.n if args.n is not None else (1 if args.quick else 2)
    bench = Bench(cfg, transport, clock=clock, quick=args.quick, n=n, fake=args.fake,
                  ctx_override={"A": args.ctx_A, "B": args.ctx_B})
    out_dir.mkdir(parents=True, exist_ok=True)
    jpath, mpath = out_dir / f"{name}.json", out_dir / f"{name}.md"
    old = json.loads(jpath.read_text(encoding="utf-8")) if args.resume and jpath.exists() else None

    def save(rep):
        jpath.write_text(json.dumps(rep, indent=1), encoding="utf-8")

    try:
        report = await bench.run([Lane(x) for x in (args.lane or ["A", "B"])], stages, resume=old, save=save,
                                 keep_budgets=args.keep_budgets)
    finally:
        save(bench.report)
        try:
            await transport.aclose()
        except Exception:  # noqa: BLE001
            pass
    mpath.write_text(markdown(report), encoding="utf-8")
    print(f"\nwrote {jpath} and {mpath}")
    if args.accept:
        if args.fake:
            print("--fake: nothing is written to as_config.yaml (the lanes were simulated)")
        else:
            new, changes = recommend(report, cfg, keep_budgets=args.keep_budgets)
            save_config(new)
            print("as_config.yaml updated:" + "".join(f"\n  {c}" for c in changes) if changes else "nothing to change")
    elif report.get("changes"):
        print("run again with --accept --resume to write these settings:" + "".join(f"\n  {c}" for c in report["changes"]))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
