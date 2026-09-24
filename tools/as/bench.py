#!/usr/bin/env python3
"""Per-call-class latency bench (docs/as/08_LLM_CALLS.md §5, BENCH-01). Run on your machines.

  python tools/as/bench.py --n 5            N calls per class with realistic prompts; writes as_runs/reports/bench.json
  python tools/as/bench.py --n 5 --accept   also writes rules.scheduler.estimated_call_s into as_config.yaml

The prompts are the protected samples (as_engine/tests/fixtures/prompt_samples), so every run is
comparable. Uses the configured regimes (lane, thinking, max_tokens). Needs the engine's P1.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
from pathlib import Path

from _live import REPORTS, ROOT, load_config, need, save_config

sys.path.insert(0, str(ROOT / "as_engine" / "tests" / "fixtures" / "prompt_samples"))

CLASSES = {  # bench key -> (call class name, hot?)
    "intake": ("intake", False), "actor_cognition_hot": ("actor_cognition", True),
    "actor_cognition_warm": ("actor_cognition", False), "actor_reaction": ("actor_reaction", False),
    "writeback": ("writeback", False), "portrayal_audit": ("portrayal_audit", False),
    "narration": ("narration", False), "render_lint": ("render_lint", False),
}


async def main(n: int, accept: bool) -> int:
    from as_engine.contracts.common import CallClass
    from as_engine.contracts.lanes import LMRequest
    from as_engine.lanes.client import LaneClient
    from as_engine.lanes.transport import HttpTransport
    from as_engine.prompts.render import cache_key, render
    import samples

    cfg = load_config()
    kw = samples.render_kwargs()
    transport = HttpTransport()
    client = LaneClient(cfg, transport)
    out = {}
    try:
        for key, (cc_name, hot) in CLASSES.items():
            cc = CallClass(cc_name)
            regime = cfg.hot_cognition if hot else cfg.regimes[cc]
            msgs = render(cc, **kw[cc])
            times = []
            for _ in range(n):
                req = LMRequest(call_class=cc, lane=regime.lane, messages=msgs, temperature=regime.temperature,
                                top_p=regime.top_p, max_tokens=regime.max_tokens, thinking=regime.thinking,
                                deadline_s=regime.deadline_s, cache_key=cache_key(msgs))
                try:
                    resp = await client.call(req)
                except NotImplementedError:
                    need("P1", "lanes.client.LaneClient.call")
                times.append(resp.latency_ms / 1000)
                print(f"{key}: {resp.latency_ms} ms ({resp.parse_status})")
            out[key] = {"mean_s": round(statistics.mean(times), 2), "max_s": round(max(times), 2), "n": n,
                        "lane": regime.lane.value}
    finally:
        try:
            await transport.aclose()
        except Exception:  # noqa: BLE001
            pass
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "bench.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    if accept:
        est = dict(cfg.rules.scheduler.estimated_call_s)
        est.update({k: v["mean_s"] for k, v in out.items()})
        rules = cfg.rules.model_copy(update={"scheduler": cfg.rules.scheduler.model_copy(update={"estimated_call_s": est})})
        save_config(cfg.model_copy(update={"rules": rules}))
        print("as_config.yaml: rules.scheduler.estimated_call_s updated (BENCH-01); update the SAND table in PROGRESS.md")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    n = int(args[args.index("--n") + 1]) if "--n" in args else 5
    sys.exit(asyncio.run(main(n, "--accept" in args)))
