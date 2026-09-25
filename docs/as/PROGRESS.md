# PROGRESS

Written by `tools/as/gate.py` (the Evidence columns) and by the builder (Next task, Notes).
Status words: **not started** · **in progress** · **observed implementation, not proven gate** ·
**green**. Only `gate.py` may write **green** (13 §1).

## Current

- Current phase: record the gates P0–P7 (the engine is built), then P8 steps 4–6
- Next task: `python tools/as/gate.py --phase 0`, then `--phase 1` … `--phase 7`, one at a time (13_BUILD_ORDER §4.0 step 1). Then P8 step 4 — `src/talemate/server/as_game_plugin.py` (02 §6).
- Blocked by: nothing
- Kit status: the engine side of P0–P10 is built and every contract test of P0–P10 and the sim soak passes (1299 tests; the bodies are in `_impl_*.py` files, AGENTS.md §4), Actor v2 steps 1–3 included. Not built: the owner's appearance and smell work (F1a, F1b — D-82, D-83: looks, clothing, condition, what a look shows, the glance cues, smell, gore camouflage — their parts sit in P2, P3, P4, P5 and P10; 13 §4.0 step 1 lists them), the owner's human people (H1 — D-84: tempers, breaking points, grudges, rows, betrayal — parts in P4, P5, P7, P9 and P10, same list), the owner's feeding dead (I1 — D-85: eaten alive, animals, tainted meat and water — parts in P2, P3, P5 and P10, same list), the wet strain as the owner told it (W1 — D-77, D-80: every fluid, the urge to contaminate, the player's hand — parts in P4, P5 and P10, same list), Actor v2 step 4 (B4 — D-87: speech in segments, gestures, attention — parts in P1, P4, P5 and P7, same list), the owner's washing, clothes and cold (F1c — D-86: who gets bloodied, grime, rain, washing, smearing, changing and stripping, the cold, the reek and nakedness wearing on people — parts in P2, P4, P5, P7 and P10, same list), the owner's sessions browser and hard delete (RUN-12/13, D-76: `wipe_tree`, the one-step delete, the Your lives screen; a P10 genesis that names no run), P8's Talemate plugin and upstream patches, the frontend toolchain and the P8 Play UI screens (the P10 screens are built) — 13_BUILD_ORDER §4.0 has the order. After the P10 gate, stop and write "waiting for the kit update (Actor v2 steps 4–6, P11, P12)" here.

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
| how far a smell carries (1/2/5/10/20 m, half outdoors); when a corpse starts to smell (6/24/72 h) | `OlfactionRules.range_m`, `outdoor_mult`, `death_hours` | play-tuning (F1b) |
| gore camouflage: how much gore masks you, how loud gives you away, for how long (4, 55 dB, 30 s) | `InfectedRules.gore_mask_min`, `mask_break_db`, `mask_window_s` | play-tuning (F1b) |
| how much each provocation angers (struck 4 … ordered about 1), how fast anger fades (1 an hour), the chance to swallow it (0.1 per Resolve, at most 0.8), what stresses (H1) | `TemperRules.provocation_heat`, `heat_decay_min`, `hold_per_resolve`, `hold_max`, `stress_from` | play-tuning: how often a room of strangers comes to blows, and how often a group bickers (H1) |
| how often a settlement's sore pairs have a row (0.05 + 0.05 per point of stress) and a brawler's row comes to blows (0.3; a quarter for others) | `SocietyRules.quarrel_base`, `quarrel_per_stress`, `brawl_chance` | 100-day soak: a settlement should bicker weekly and brawl now and then, not daily (H1) |
| what wears a person down (a death seen 2 + bond, hunger past stage 2 +1, sleep -2) | core `cascade/stress.yaml` CAS-019..021 | play-tuning (H1) |
| how long the dead stay on a corpse (20 min), how many bites leave too little to rise (8), how far a scream pulls the rest of them in (30 m) | `InfectedRules.feed_on_dead_min`, `devoured_bites`, `scream_draw_m` | play-tuning (I1) |
| the chance tainted meat / fouled water gives the strain (0.5 / 0.4) | core `pathways.yaml` wet `tainted_food`, `tainted_water` | the lore owner's word, then play-tuning (I1) |
| a host's blood on the hands / in the eyes / a sleeper's mouth (0.15 / 0.05 / 0.6) | core `pathways.yaml` wet `fluid_contact`, `fluid_splash`, `mouth_contact_direct` | the lore owner's word, then play-tuning (W1) |
| how often the urge comes (10 min x 336 / hours, never under 2) and takes the player's hand (0.2 week three, 0.4 week four) | `InfectedRules.compulsion_cooldown_min`, `compulsion_min_gap_min`, `pc_urge_share` | play-tuning: the player should feel it coming, not lose the game to dice (W1) |
| a wound's blood (0/1/2/3 by severity); grime a day to 3; rain 20-minute steps | `ConditionRules.blood_from_wound`, `grime_every_h`, `grime_unwashed_max`, `weather_step_min` | play-tuning: people should look like what happened to them (F1c) |
| how cold it is (mild 1 / cold 3 / hot 0 by day, +1 night, -2 indoors, +1 soaked) and how fast it bites (4 chill a stage, -4 an hour warm) | `ConditionRules.cold_need`, `shelter`, `chill_per_stage`, `warm_per_step` | play-tuning: naked on a mild night about twelve hours to death; a wet night in a cold country a few (F1c) |
| smearing the dead on (0.05) and into an open wound (0.5) | core `pathways.yaml` wet `gore_smear`, `gore_in_wound` | the lore owner's word, then play-tuning (F1c) |
| the reek grates every 10 minutes (heat 1); a naked adult every 30 (heat 2, strain 1) | `ConditionRules.reek_every_min`, `bared_every_min`; `TemperRules` | play-tuning: nobody stands next to the reek for an hour (F1c) |

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
