#!/usr/bin/env python3
"""Evaluation (docs/as/08_LLM_CALLS.md §4 ablation duty, §7). Needs P7+ (ablation: P11, LANE-09).

  python tools/as/eval.py                      play each canonical scenario script; write as_runs/reports/eval.json
  python tools/as/eval.py --ablate writeback   play plain AND with that call class disabled; compare
  python tools/as/eval.py --scenario metal_fence --turns 6
  python tools/as/eval.py --fake ...           the same on the fake model (no LM Studio): a smoke run

Reports per scenario (MEASURES): turns played, turns that played, mean turn wall-clock, calls, the
calls an ablation cancelled, intent repairs, echo rejections, lint failures, leak findings,
portrayal misfits, memory jobs that failed, held or continued decisions, refusals, narration word
counts. With --ablate, the class (a contracts.common.CallClass value) is put in
session.client.ablated (LANE-09): its calls come back 'cancelled' and every caller takes its
fallback path. compare(plain, ablated) lists every measure (other than the wall-clock, the call
counts and ablated_calls) that differs; a class whose ablation changes none of them is a removal
candidate (plan §17.3) — the report says so. The exit code is 0 either way: this is evidence for
a person to weigh, not a gate.
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
UNCOMPARED = ("mean_turn_s", "calls", "ablated_calls", "scenario", "ablated")


async def play(name: str, turns: int, ablate: str | None, *, fake: bool = False) -> dict:
    from as_engine.contracts.common import CallClass
    from as_engine.contracts.protocol import InTurnSubmit
    from as_engine.testing.scenario import load_scenario
    from as_engine.turn.pipeline import run_turn

    if fake:
        from as_engine.testing.fake_lm import FakeTransport
        transport = FakeTransport()
    else:
        from as_engine.lanes.transport import HttpTransport
        load_config()
        transport = HttpTransport()
    world = load_scenario(ROOT / "as_engine" / "tests" / "fixtures" / "scenarios" / f"{name}.yaml",
                          packs_root=ROOT / "as_engine" / "tests" / "fixtures" / "packs",
                          core_pack_dir=ROOT / "as_content" / "packs" / "core", transport=transport)
    try:
        session = world.session()
    except NotImplementedError:
        need("P7", "testing.scenario.ScenarioWorld.session")
    if ablate:
        session.client.ablated = {CallClass(ablate)}
    walls, words, ok = [], [], 0
    try:
        for mode, text in SCRIPTS[name][:turns]:
            t = time.perf_counter()
            out = await run_turn(session, InTurnSubmit(mode=mode, text=text))
            walls.append(time.perf_counter() - t)
            ok += int(out.ok)
            words.append(len((out.narration or "").split()))
        st = world.store

        def count(sql, params=()):
            r = st.query_one(sql, params)
            return r[0] if r else 0
        return {
            "scenario": name, "ablated": ablate, "turns": len(walls), "ok_turns": ok,
            "mean_turn_s": round(statistics.mean(walls), 1) if walls else None,
            "calls": count("SELECT COUNT(*) FROM lm_calls"),
            "ablated_calls": count("SELECT COUNT(*) FROM lm_calls WHERE status = 'cancelled'"),
            "intent_repairs": count("SELECT COUNT(*) FROM lm_calls WHERE call_class = 'intent_repair'"),
            "echo_rejections": count("SELECT COUNT(*) FROM error_repair_log WHERE kind LIKE 'echo%'"),
            "lint_failures": count("SELECT COUNT(*) FROM error_repair_log WHERE kind = 'lint_fail'"),
            "leak_findings": count("SELECT COUNT(*) FROM audit_log WHERE gate = 'G15-leak' AND result = 'fail'"),
            "portrayal_misfits": count("SELECT COUNT(*) FROM audit_log WHERE gate LIKE '%portrayal' AND result = 'fail'"),
            "memory_jobs_failed": count("SELECT COUNT(*) FROM memory_jobs WHERE status = 'failed'"),
            "decisions_not_made": count("SELECT COUNT(*) FROM events WHERE type = 'DEGRADED_FALLBACK'"),
            "refusals": count("SELECT COUNT(*) FROM events WHERE type = 'REFUSAL'"),
            "narration_words_mean": round(statistics.mean(words), 1) if words else None,
        }
    finally:
        world.store.close()


def compare(plain: dict, ablated: dict) -> dict:
    """What an ablation changed: {measure: [plain, ablated]} and the verdict."""
    changed = {k: [plain[k], ablated.get(k)] for k in sorted(plain) if k not in UNCOMPARED and plain[k] != ablated.get(k)}
    return {"scenario": plain["scenario"], "ablated": ablated["ablated"], "changed": changed,
            "verdict": "degrades" if changed else "removal candidate: nothing measurable changed"}


async def main(args: list[str]) -> int:
    ablate = args[args.index("--ablate") + 1] if "--ablate" in args else None
    only = args[args.index("--scenario") + 1] if "--scenario" in args else None
    turns = int(args[args.index("--turns") + 1]) if "--turns" in args else 99
    fake = "--fake" in args
    names = [n for n in SCRIPTS if only in (None, n)]
    results = [await play(n, turns, None, fake=fake) for n in names]
    out: dict = {"plain": results}
    if ablate:
        ablated = [await play(n, turns, ablate, fake=fake) for n in names]
        out.update(ablated=ablated, comparison=[compare(p, a) for p, a in zip(results, ablated, strict=True)])
    REPORTS.mkdir(parents=True, exist_ok=True)
    fname = f"eval{'_ablate_' + ablate if ablate else ''}{'_fake' if fake else ''}.json"
    (REPORTS / fname).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
