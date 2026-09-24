#!/usr/bin/env python3
"""Live evaluation with real models (docs/as/08_LLM_CALLS.md §4 ablation duty, §7). Needs P7+.

  python tools/as/eval.py                      play each canonical scenario script; write as_runs/reports/eval.json
  python tools/as/eval.py --ablate writeback   the same with that call class disabled (fallback path)
  python tools/as/eval.py --scenario metal_fence --turns 6

Reports per scenario: turns played, mean turn wall-clock, intent repair rate, echo rejections,
lint failures per 10 turns, leak findings, refusal/compliance counts on the WILL scenarios, and the
narration word counts. Compare an --ablate run with a plain run: a call whose ablation changes
nothing measurable is a removal candidate (plan §17.3).
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time

from _live import REPORTS, ROOT, load_config, need

SCRIPTS = {  # canonical player inputs per scenario (mode, text)
    "metal_fence": [("do", "Look toward the back of the store."), ("say", "Mara, did you hear that?"),
                    ("do", "Go to the storeroom doorway, gun low."), ("do", "Wait and listen."),
                    ("say", "Nita, you out there?"), ("do", "Keep watching the back door.")],
    "request_firewall": [("say", "Put the hammer down."), ("say", "Please, put it down. I'm not here to hurt anyone."),
                         ("say", "I said put it down."), ("do", "Wait.")],
    "empty_gun": [("say", "Reggie, put it away. Carl can pay you tomorrow."), ("do", "Step between them.")],
    "crowd_accusation": [("say", "Who says it was me?"), ("do", "Look at the crowd.")],
}


async def play(name: str, turns: int, ablate: str | None) -> dict:
    from as_engine.contracts.protocol import InTurnSubmit
    from as_engine.lanes.transport import HttpTransport
    from as_engine.testing.scenario import load_scenario
    from as_engine.turn.pipeline import run_turn

    cfg = load_config()
    world = load_scenario(ROOT / "as_engine" / "tests" / "fixtures" / "scenarios" / f"{name}.yaml",
                          packs_root=ROOT / "as_engine" / "tests" / "fixtures" / "packs",
                          core_pack_dir=ROOT / "as_content" / "packs" / "core", transport=HttpTransport())
    try:
        session = world.session()
    except NotImplementedError:
        need("P7", "testing.scenario.ScenarioWorld.session")
    if ablate:
        session.extras["ablate"] = {ablate}
    walls, words, ok = [], [], 0
    for mode, text in SCRIPTS[name][:turns]:
        t = time.perf_counter()
        out = await run_turn(session, InTurnSubmit(mode=mode, text=text))
        walls.append(time.perf_counter() - t)
        ok += int(out.ok)
        words.append(len(out.narration.split()))
    st = world.store

    def count(sql, params=()):
        r = st.query_one(sql, params)
        return r[0] if r else 0
    calls = count("SELECT COUNT(*) FROM lm_calls")
    return {
        "scenario": name, "turns": len(walls), "ok_turns": ok, "mean_turn_s": round(statistics.mean(walls), 1) if walls else None,
        "calls": calls,
        "intent_repairs": count("SELECT COUNT(*) FROM lm_calls WHERE call_class = 'intent_repair'"),
        "echo_rejections": count("SELECT COUNT(*) FROM error_repair_log WHERE kind LIKE 'echo%'"),
        "lint_failures": count("SELECT COUNT(*) FROM audit_log WHERE gate LIKE 'G18%' AND result = 'fail'"),
        "leak_findings": count("SELECT COUNT(*) FROM audit_log WHERE gate LIKE 'G15%' AND result = 'fail'"),
        "refusals": count("SELECT COUNT(*) FROM events WHERE type = 'REFUSAL'"),
        "narration_words_mean": round(statistics.mean(words), 1) if words else None,
    }


async def main(args: list[str]) -> int:
    ablate = args[args.index("--ablate") + 1] if "--ablate" in args else None
    only = args[args.index("--scenario") + 1] if "--scenario" in args else None
    turns = int(args[args.index("--turns") + 1]) if "--turns" in args else 99
    results = [await play(n, turns, ablate) for n in SCRIPTS if only in (None, n)]
    REPORTS.mkdir(parents=True, exist_ok=True)
    fname = f"eval{'_ablate_' + ablate if ablate else ''}.json"
    (REPORTS / fname).write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
