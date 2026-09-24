# PROGRESS

Written by `tools/as/gate.py` (the Evidence columns) and by the builder (Next task, Notes).
Status words: **not started** · **in progress** · **observed implementation, not proven gate** ·
**green**. Only `gate.py` may write **green** (13 §1).

## Current

- Current phase: record the gates P0–P7 (the engine is built), then P8 steps 4–6
- Next task: `python tools/as/gate.py --phase 0`, then `--phase 1` … `--phase 7`, one at a time (13_BUILD_ORDER §4.0 step 1). Then P8 step 4 — `src/talemate/server/as_game_plugin.py` (02 §6).
- Blocked by: nothing
- Kit status: the engine side of P0–P10 is built and every contract test of P0–P10 and the sim soak passes (1299 tests; the bodies are in `_impl_*.py` files, AGENTS.md §4), Actor v2 steps 1–3 included. Not built: the owner's sessions browser and hard delete (RUN-12/13, D-76: `wipe_tree`, the one-step delete, the Your lives screen; a P10 genesis that names no run), P8's Talemate plugin and upstream patches, the frontend toolchain and the P8 Play UI screens (the P10 screens are built) — 13_BUILD_ORDER §4.0 has the order. After the P10 gate, stop and write "waiting for the kit update (Actor v2 steps 4–6, P11, P12)" here.

## Phases

| Phase | Status | Commit | Command | Gate | Artifact | Date |
|---|---|---|---|---|---|---|
| P0 Substrate | observed implementation, not proven gate | | | | | |
| P1 Lane harness | observed implementation, not proven gate | | | | | |
| P2 Bodies, space, objects, content | observed implementation, not proven gate | | | | | |
| P3 Perception | observed implementation, not proven gate | | | | | |
| P4 One Actor | observed implementation, not proven gate | | | | | |
| P5 Many Actors | observed implementation, not proven gate | | | | | |
| P6 Memory | observed implementation, not proven gate | | | | | |
| P7 The Slice | observed implementation, not proven gate | | | | | |
| P8 Play UI | in progress (steps 1–3 built; plugin, toolchain and UI screens to build) | | | | | |
| P9 Society | observed implementation, not proven gate | | | | | |
| P10 Wide world | observed implementation, not proven gate | | | | | |
| P11 Audits | not started | | | | | |
| P12 Surfaces | not started | | | | | |

## SAND remaining

| Number | Where | Replaced by |
|---|---|---|
| per-call latency estimates | `SchedulerRules.estimated_call_s` | `tools/as/bench.py` on your machines (BENCH-01) |
| acoustic fidelity margins 12/5/0 dB | `AcousticRules` | `tools/as/eval.py` belief-accuracy runs (BENCH-07) |
| Resolve drains/recoveries | `ResolveRules` | eval refusal/compliance rates (BENCH-03) |
| packet token budgets 6000/4000/3000 (Actor Spec §5; were 3500/2200/1400) | `PacketRules.token_budget` | bench prefill times (BENCH-04) with the identity card in every call |
| heard words cut at 800 characters (Actor Spec §5) | `PacketRules.max_heard_chars` | a play session's longest speeches: nobody's own context crowded out, no ordinary speech cut |
| outings: daily chance per kind | `WorldRules.op_chance` | 100-day fake-model soak per difficulty (BENCH-06): how many go out, how many come back |
| how long marks last under a roof | `WorldRules.sheltered_trace_mult` | play-tuning |
| the dead past each map edge; drift chance; the Mega Horde's daily chance | `HordeRules.exterior_pool`, `drift_chance`, `mega_daily_chance` | 100-day soak per difficulty: how often a Mega Horde comes, how full the streets get |
| how many of one crowd show in a place; how long a loud noise holds its neighbourhood in the moment | `HordeRules.local_cap` (40), `turn.select.LOUD_MEMORY_MS` (10 min) | a day of the Mega Horde next to the player: bodies shown per hour and seconds per simulated day (D-67, D-68) |
| how long a door holds under a crowd | `InfectedRules.portal_holds_min` | play-tuning |
| how long a spreader's bottle stays infective | `InfectedRules.saliva_hours` | the lore owner's word, then play-tuning |
| wear by wet days | `DecayRules.rust_per_wet_day`, `pulp_per_wet_day`, `rot_per_wet_day` | play-tuning |
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

- 2026-09-24 (kit maintainer): the engine through P10 was built outside DSH and committed on the owner's
  instruction. Its bodies are in `_impl_*.py` files; see AGENTS.md §4 before changing one. Start at
  13_BUILD_ORDER §4.0, not at P0 task 1.
