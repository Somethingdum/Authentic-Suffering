# PROGRESS

Written by `tools/as/gate.py` (the Evidence columns) and by the builder (Next task, Notes).
Status words: **not started** · **in progress** · **observed implementation, not proven gate** ·
**green**. Only `gate.py` may write **green** (13 §1).

## Current

- Current phase: P0
- Next task: P0 task 1 — `kernel/ids.py::mint`
- Blocked by: nothing
- Kit status: contract tests exist for P0–P9 (P7 = the slice + the sim soak; P8 = the protocol, the Play UI specs and the plugin test; P9 = the society). After the P9 gate, stop and write "waiting for the kit update (P10+ tests)" here.

## Phases

| Phase | Status | Commit | Command | Gate | Artifact | Date |
|---|---|---|---|---|---|---|
| P0 Substrate | not started | | | | | |
| P1 Lane harness | not started | | | | | |
| P2 Bodies, space, objects, content | not started | | | | | |
| P3 Perception | not started | | | | | |
| P4 One Actor | not started | | | | | |
| P5 Many Actors | not started | | | | | |
| P6 Memory | not started | | | | | |
| P7 The Slice | not started | | | | | |
| P8 Play UI | not started | | | | | |
| P9 Society | not started | | | | | |
| P10 Wide world | in progress — contracts + most reference done, tests/UI/docs missing (see HANDOFF.md) | | | | | |
| P11 Audits | not started | | | | | |
| P12 Surfaces | not started | | | | | |

## SAND remaining

| Number | Where | Replaced by |
|---|---|---|
| per-call latency estimates | `SchedulerRules.estimated_call_s` | `tools/as/bench.py` on your machines (BENCH-01) |
| acoustic fidelity margins 12/5/0 dB | `AcousticRules` | `tools/as/eval.py` belief-accuracy runs (BENCH-07) |
| Resolve drains/recoveries | `ResolveRules` | eval refusal/compliance rates (BENCH-03) |
| packet token budgets 3500/2200/1400 | `PacketRules.token_budget` | bench prefill times (BENCH-04) |
| off-screen daily mortality | `WorldRules.base_daily_mortality` | 100-day fake-model soak per difficulty (BENCH-06) |
| relationship drift chances 0.25 / 0.2 / 0.3 | `SocietyRules.drift_bond` / `drift_household` / `drift_friction` | play-tuning (how fast a settlement's feelings move) |
| thirst stage interval | `NeedsRules.thirst_stage_every_h` | play-tuning |

## Human checklist items

| Item | Phase | Done |
|---|---|---|
| LM Studio set up on both machines, LM Link on (08 §2) | before P7 live play | |
| `tools/as/probe.py` run; thinking mode + structured-with-thinking written to `as_config.yaml` | P1 | |
| `tools/as/bench.py --n 5` run and accepted | P1+ | |
| Play UI smoke checklist, P8 part (`talemate_frontend/src/play/README.md` §0–§6) | P8 | |
| Play UI smoke checklist, later parts (§7 New life and worlds: P10; §8 death, imports, cheats: P12) | P10 / P12 | |
| Review `SPEC_ISSUES.md` | every phase | |

## Notes (builder)

(append dated notes here: what was tricky, what you tried, anything the next session must know)
