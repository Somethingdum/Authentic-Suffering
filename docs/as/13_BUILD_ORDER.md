# 13 — Build Order

Thirteen phases, P0–P12. Each has: what to read, an ordered task list, the gate, and what you are
**forbidden** to build yet. The phase order differs from the Rebuild Plan's (deviation D-02 in
`DECISIONS.md`): core narration moves into P7 so the slice is playable, and the Play UI comes
right after the slice (P8) so the human can play and judge it early.

## 1. Rules for every phase (Rebuild Plan §15.1, carried as law)

1. **No phase is green without evidence**: commit hash, exact test command, passing gate name,
   artifact path and an updated `PROGRESS.md` row — all written by `tools/as/gate.py`. Until then the
   only legal wording is "observed implementation, not proven gate".
2. **Passing tests is necessary, not sufficient.** Hard-coding a fixture value, returning a canned
   answer for a test's inputs, no-opping a behaviour, or special-casing a test name fails the phase
   whatever the tests say. `tools/as/gate.py` scans for the common forms (`if "metal_fence" in`,
   literal fixture ids like `act_000003` inside `src/`, `pytest` imported inside `src/`).
3. Every `[SAND]` number a phase depends on is either replaced by a measured value or listed in
   `PROGRESS.md` under "SAND remaining" with the benchmark that will replace it (D-04: numbers that
   need your real hardware are measured by you with `tools/as/bench.py`).
4. **No phase may build a later phase's systems.** Stubs for later phases stay stubs.
5. A contradiction between this spec, the Rebuild Plan and the Codex Master Guide is **recorded** in
   `SPEC_ISSUES.md`, never silently resolved.
6. Protected files (contract tests, fixtures, `testing/fake_lm.py`, `testing/scenario.py`'s
   `ScenarioSpec`, `kernel/jsoncanon.py`, the rng core, `docs/as/*` except `PROGRESS.md`,
   `SPEC_ISSUES.md`, `CHANGELOG_AS.md`) are never edited. Contract changes you believe are needed go
   to `SPEC_ISSUES.md`; approved ones are recorded in `CHANGELOG_AS.md` by the human.
7. Keep every function inside the module that owns it; write tables only through the owner
   (STORE-02). If a behaviour has no owner in the module map, record it and ask.

## 2. Session protocol (every DSH session)

`AGENTS.md` §1 is the working copy of this list; the two say the same thing.

1. The SessionStart hook shows the current phase and Next task. Run `python tools/as/doctor.py` —
   fix anything red that belongs to a finished phase first.
2. Read `PROGRESS.md` (current phase, Next task) and this phase's section in §4.
3. `python tools/as/gate.py --phase N --quick` — where you are, first failures.
4. Work task by task (§4), one function at a time. After each task: that phase's tests; before the
   gate, all earlier phases' tests too.
5. When the phase's tests pass: `python tools/as/gate.py --phase N`. It runs everything required,
   checks protection and anti-cheating rules, and writes the evidence row.
6. Before stopping: set `PROGRESS.md` "Next task" to the exact next function. The Stop hook
   (`gate.py --stop-check`) asks you to fix an empty Next task or a changed protected file before the
   turn ends (twice at most, then it leaves the problem for the human).

## 3. Phase map

| Phase | Name | Main modules | Contract tests | Gate adds |
|---|---|---|---|---|
| P0 | Substrate | `kernel/*`, `audit/commit_gate.py` (framework) | `p00_substrate` | DET-01 on a 500-event synthetic trace; boundary scan |
| P1 | Lane harness | `lanes/*`, `config_loader.py`, `prompts` checks | `p01_lanes` | prompt render of every sample |
| P2 | Bodies, space, objects, content | `physical/*`, `content/pack.py`, `testing/scenario.load_scenario`, `worldgen/conditions.parse` | `p02_space_bodies` | core pack compiles clean |
| P3 | Perception | `kernel/truth.py`, `sense/*`, `mind/perception.py`, `space.line_of_sight` | `p03_perception` | — |
| P4 | One Actor | `mind/actor.py`, `mind/resolve.py`, `mind/affordance.py`, `mind/firewall.py` (classification), `mind/packet.py`, `action/intent.to_intent` | `p04_one_actor` | — |
| P5 | Many Actors | `action/*`, `lanes/scheduler.plan_cognition`, `action/intent.barrier/plan_continuation` | `p05_many_actors` | — |
| P6 | Memory | `mind/memory.py`, `mind/retrieval.py`, `mind/mind.py`, `mind/firewall.py` (refusals) | `p06_memory` | — |
| **P7** | **The Slice** | `turn/*`, `lanes/requests.py`, `narration/*` (not style), `service/session.py`, `service/runs.py` (scenario path), `service/view.py`, `service/replay.py`, `cli.py` | `p07_slice` + `sim` | the pivot list (§5.7) |
| P8 | Play UI | `service/game_service.py`, `service/guide.py`, Talemate plugin + patches, `talemate_frontend/src/play/*` | `p08_ui_protocol` + vitest + plugin test | the human smoke checklist (P8 part) |
| P9 | Society | `society/*`, `world/rumours.py`, `mind/mind` group standing, the P9 parts of `turn/timers.py`, `turn/select.py`, `turn/pipeline.py`, `action/cascade.py` | `p09_society` | — (P7 fixtures must run exactly as before) |
| P10 | Wide world | `world/worldgen/*`, `world/infected.py`, `world/worldmove.py`, `world/traces.py`, `world/decay.py`, `service/runs.create_run` | `p10_world` | a full worldgen run with the fake model |
| P11 | Audits | `audit/*`, `narration/style.py`, ablation in `tools/as/eval.py` | `p11_audits` | all 58 bits drop under their faults |
| P12 | Surfaces | `cheats/*`, `content/importers.py`, `service/death.py`, worlds (`service/runs`), migrations, read-aloud | `p12_surfaces` | — |

## 4. Tasks per phase

### P0 — Substrate
Read: 02, 03, `kernel/*` docstrings, `audit/commit_gate.py`.
1. `kernel/ids.py::mint` (counters as bookkeeping writes via `Tx.bookkeep`).
2. `kernel/store.py`: `create/open/memory/close/transaction/query/query_one/meta/backup_to`, `Tx.commit_event`, `Tx.bookkeep`, `Tx.mint`. Apply `schema.sql` with `executescript`. Enforce STORE-01..10 exactly as the docstring says. The `events` append-only rule (STORE-08) is enforced in code (reject any WriteRecord or bookkeep call targeting `events` with UPDATE/DELETE) **and** with two SQLite triggers you add at creation time (`BEFORE UPDATE ON events` / `BEFORE DELETE ON events` → `RAISE(ABORT, 'events is append-only')`); triggers are created by `Store.create/memory`, not in `schema.sql`.
3. `kernel/rng.py::Rng` methods (the core is done; vectors in `tests/fixtures/vectors/rng.json`).
4. `kernel/clock.py`: `now`, `turn_index`, `advance_event`, `schedule`, `due_between`, `next_due`.
5. `kernel/events.py`: `get`, `since`, `children`, `cause_chain`, `replay_world`.
6. `kernel/hashing.py`: `world_state_hash`, `full_state_hash`, `table_digest`.
7. `audit/commit_gate.py::compute` **framework**: evaluate every bit whose tables exist (they all exist from P0); bits return 1 on an empty world. The fault-injection proof is P11; here only `test_gate_framework.py` must pass.
8. `tests/contract/p00_substrate/test_boundaries.py` must pass from now on for every later phase.
Gate: `p00_substrate` green; `gate.py` runs DET-01 on a generated 500-event trace twice and across a process restart.
**Forbidden:** bodies, places, minds, content — any game logic.

### P1 — Lane harness
Read: 08, `lanes/*` docstrings, `contracts/lanes.py`, `contracts/calls.py`, `prompts/render.py`.
1. `lanes/parse.py` (all five functions — pure).
2. `lanes/schemas.py` (`to_lm_schema`, dynamic enums).
3. `lanes/transport.py::HttpTransport` with `httpx.AsyncClient`; the tests use `httpx.MockTransport`.
4. `lanes/client.py::LaneClient`.
5. `lanes/repair.py::call_with_repair`.
6. `lanes/scheduler.py::run_jobs` (not `plan_cognition` — that is P5).
7. `lanes/calllog.py::record`, `ReplayTransport`.
8. `config_loader.py`.
9. `tools/as/probe.py` and `tools/as/bench.py` run end-to-end against `FakeTransport` with `--fake` (their live paths are for the human).
Gate: `p01_lanes` green; every prompt template renders with its sample context.
**Forbidden:** any Actor logic. This phase talks to models about nothing in particular.

### P2 — Bodies, space, objects, content
Read: 07 §2, §5, §6, §7; 09; `physical/*`, `content/pack.py`, `testing/scenario.py` docstrings.
1. `content/pack.py`: `load_pack`, `load_canon`, `lint_text_records`, `compile_packs` with every CNT rule. Then make the **core pack compile with zero errors** (if the core pack itself is wrong, that is a SPEC_ISSUE, not an edit).
2. `world/worldgen/conditions.py::parse` (grammar only; `evaluate` is P10).
3. `physical/space.py`: everything except `line_of_sight` (P3) and `discover_layout` (P10).
4. `physical/objects.py`: all.
5. `physical/bodies.py`: all (the death test included; infected false death reads the type from `infected_state` and keeps its timers on `bodies`).
6. `mind/actor.py::resolve_max` (a formula; the loader needs it — the rest of mind.actor is P4).
7. `testing/scenario.py::load_scenario` — its docstring's "Row details" are the contract; every fixture must load and pass the 58-bit gate at turn 0.
Gate: `p02_space_bodies` green (its `test_core_pack_is_clean` is the content check; the `as-engine content-check` command itself arrives with the CLI in P7).
**Forbidden:** perception. Bodies exist and move; nobody notices yet.

### P3 — Perception
Read: 05 §3, 07 §3–4, `sense/*`, `mind/perception.py`, `kernel/truth.py`.
1. `sense/acoustics.py` (pure parts first: `fidelity_for_margin`, `partial_words`; then `received_db`, `receptions`).
2. `sense/optics.py` (`visibility_score`, `band`, `visibility`) + `physical/space.line_of_sight`.
3. `kernel/truth.py::current_facts`.
4. `mind/perception.py`: `grant` (the single writer), `render_visual`, `compile_scene`, `compile_aftermath`.
Gate: `p03_perception` green.
**Forbidden:** decisions. Minds receive; they do not yet choose.

### P4 — One Actor
Read: 05 §2–8, `mind/actor.py`, `mind/resolve.py`, `mind/affordance.py`, `mind/firewall.py`, `mind/packet.py`, `action/intent.py`, the core affordance catalog.
1. `mind/actor.py` (fusion, resolve_max, display_name, recent_lines, controller).
2. `mind/resolve.py`.
3. `mind/firewall.py`: `classify_form`, `classify_standing`, `request_signature`, `classify_response`.
4. `mind/affordance.py::enumerate_affordances` (all seven gates in order; selection rules).
5. `mind/packet.py::build_packet` (render budget via `prompts/actor_cognition` templates).
6. `action/intent.py::to_intent`.
Gate: `p04_one_actor` green.
**Forbidden:** multiple actors resolving together. One mind, done properly, before five.

### P5 — Many Actors
Read: 04 §3, 07 §1, §8, §9, `action/*`, `mind/cues.py`, `lanes/scheduler.py`.
0. The P5 helpers in lower layers (each docstring says "P5"): `kernel/store.Tx.citing`,
   `kernel/clock.fire` / `cancel` / `pending_for`, `physical/space.distance_to_point`,
   `physical/bodies.posture_event` / `grip_event` / `release_event` / `grips_on` / `refresh_need`,
   `physical/objects.chamber` / `load_rounds` + `destroy(qty=)` + `transfer(props_update=)`,
   `sense/optics.light_at`, `mind/actor.adjust_stress`. (`audit/log.record` is implemented.)
1. `action/checks.py`. 2. `action/tasks.py`. 3. `mind/cues.py`. 4. `action/effects.py`: `land`,
   `situation`, `resistance`, then one registered handler per id in `EFFECT_IDS` (start with move /
   portal / item / speak / observe / wait; then shoot, strike, holds). 5. `action/conflict.py`.
   6. `action/resolve.py` (`resolve_wave`, `land_pending`). 7. `action/intent.py` (`barrier`,
   `plan_continuation`, `intent_to_dict` / `intent_from_dict`). 8. `action/reactions.py`.
   9. `action/propagate.py` (P5 returns []). 10. `action/cascade.py` (P5 selectors + dispatch;
   the rest records `cascade_unbuilt`). 11. `lanes/scheduler.py::plan_cognition`.
Gate: `p05_many_actors` green (TELEPATHY-01, BARRIER-01, INTENT-03 and HALLUC-01 included).
**Forbidden:** society tables (households, settlements, workplaces) beyond reading what fixtures put there. Five people in a room, not a settlement.

### P6 — Memory
Read: 05 §6, §9, `mind/mind.py`, `mind/memory.py`, `mind/retrieval.py`, the P6 parts of
`mind/firewall.py` and `mind/perception.py` (`infer`).
1. `mind/mind.py`: `relate`, `open_loop`, `close_loop`, `learn` (`test_mind.py`; the last test also
   needs the cascade dispatch lines for RELATION_CHANGE / LOOP_OPENED in `action/cascade.py` and the
   `promise_broken` cue in `mind/cues.py`).
2. `mind/firewall.py`: `record_refusal`, `negotiable_target_penalty`, `record_lie`; then the
   'negotiable' term in `action/effects.situation` (`test_refusals.py`).
3. `mind/perception.py::infer`.
4. `mind/memory.py`: `build_aftermath` (reuse the packet's percept selection, entities and
   wording), `writeback_groups`, `apply_writeback` (`test_memory.py`).
5. `mind/retrieval.py`: `recency_bonus`, `retrieve`; then wire it into `mind/packet.build_packet`
   (memories, lessons, beliefs, loops, refusals; the budget's new drop order) (`test_retrieval.py`).
   The P3–P5 tests must stay green after this step.
Gate: `p06_memory` green (with P0–P5).
**Forbidden:** narration. The minds are right before anything describes them.

### P7 — The Slice (the pivot)
Read: 04 (all), 05 §11, 07 §10, 10 §5–6, and the docstrings of every module below (they are the contract).
1. Small pieces first: `kernel/clock.begin_turn`, `kernel/store.Store.rebuild_fts` (implemented), `lanes/calllog.request_hash` (implemented) and the P7 change to `ReplayTransport` (find calls by request hash — `p01_lanes/test_calllog.py` gains a test), `action/reactions.next_wave(..., exclude=)`.
2. `narration/lint.py` (pure metrics first, then the echo ledger) — `test_narration_lint.py` up to the narrate tests.
3. `narration/location.py` — `test_location_view.py` (the describe tests).
4. `lanes/requests.py`, then `narration/narrator.py` (packet, narrate with the judge, code_render, write_narration).
5. `service/session.py` (`append_story`), `testing/scenario.ScenarioWorld.session`.
6. `turn/select.py`, `turn/timers.py`, `turn/intake.py`, `turn/cognition.py`.
7. `turn/pipeline.py::run_turn` — stages in order; get `test_p07_slice_metal_fence.py` green stage by stage (the ledger rows tell you how far a turn got), then `test_slice_checks.py`.
8. Rollback + strict retry + degradation paths (the pipeline docstring).
9. `service/runs.py` (scenario path, save/load/autosave/list/delete; not worldgen), `service/view.py`, `service/replay.py` — `test_save_load.py`, the view tests, `test_slice_refusal.py`.
10. `cli.py` (`content-check`, `new-scenario`, `play`, `replay`) — `test_cli.py`.
Gate: `p07_slice` green, the `sim` soak green (`tests/sim/test_soak_metal_fence.py`: 50 turns, every committed turn passes the 58 bits, no rollback, then DET-02 re-simulation of every turn), and every item of §5.7.
**Forbidden:** worldgen, society, UI. The slice runs on hand-authored scenarios.

### P8 — Play UI
Read: 10 (all), 02 §3, §4.1, §6, 11 §1.2, `contracts/protocol.py`, `service/game_service.py`, `service/guide.py`.
1. Small pieces first: `kernel/store.Store.transaction` must roll back on any `BaseException` (a cancelled turn) — `p00_substrate/test_store.py` gains `test_a_cancelled_task_rolls_back_too`; `service/session.change_settings`; `service/replay.resimulate` re-applies mid-run settings changes (SET-01).
2. `service/guide.py` (`rules_for`, `pc_facts`, `answer`) — `test_guide.py`.
3. `service/game_service.py`: `out`, `handle` (validation, errors, not_built_yet), `push`, `idle`, `get_service`, then the `on_<action>` handlers of the module docstring in the order of the test files: `test_protocol.py`, `test_models_config.py`, `test_runs_protocol.py`, `test_packs_content.py`, `test_settings_dev.py`, `test_turns_protocol.py` (the background turn task, busy, Stop, reconnect, Ask). Leave the P10 / P12 handlers as stubs.
4. `src/talemate/server/as_game_plugin.py` (02 §6 gives the whole file) + the upstream patch list (02 §4.1) — nothing else upstream changes. Then `python -m pytest tests/test_as_game_plugin.py -q -o addopts=""` from the fork root.
5. The frontend toolchain (02 §4.1): devDependencies, the `test:play` script, the `test` block of `vite.config.mjs`, `corepack pnpm install` (commit the lockfile), `App.vue`.
6. `talemate_frontend/src/play/`: `words.js` (`words.spec.js`), `socket.js` (`socket.spec.js`), `store.js` (`store.spec.js`), `PlayApp.vue` + `LaterScreen.vue` (`app.spec.js`), the Connect / Home / Content screens (`connect_home.spec.js`), the panels (`panels.spec.js`), `PlayScreen.vue` with the top bar, Where, story, progress and input (`play.spec.js`), settings and the developer panel (`settings_dev.spec.js`), then `clarity.spec.js` over all of it. The test ids are exactly those of 10 §2; `__tests__/helpers.js` shows how every spec mounts.
Gate: `p08_ui_protocol` green (with P0–P7 and the sim soak), vitest green, the plugin test green, `gate.py --upstream-diff` clean. The human then makes a run with `as-engine new-scenario` and goes through the smoke checklist in `talemate_frontend/src/play/README.md` (its P8 part) and ticks it in PROGRESS.
**Forbidden:** new engine features. The UI shows what the engine already does: the wizard, worldgen, death and worlds screens wait for P10 / P12 (PlayApp shows LaterScreen for them).

### P9 — Society
Read: 06 §2, §6; 04 §1 (stages 0 and 12) and §3.1 (HOR-01); 07 §9 (cascades); 11 (`SocietyRules`);
the docstrings of `society/*` and `world/rumours.py`, and the P9 parts of `mind/mind.py`,
`turn/timers.py`, `turn/select.py`, `turn/pipeline.py`, `action/cascade.py`, `action/intent.py`,
`service/view.py` (each marks its P9 lines). The fixture is `pump_settlement` (24 people, a pump
that makes exactly what they drink).
0. Small pieces first (lower layers amended for P9): `physical/bodies.progress` clamps a need stage
   at 0; `mind/perception.grant(confidence=)`; `mind/mind.standing_toward` /
   `adjust_group_standing` (`test_group.py::test_stand_01_02_standing`). `kernel/clock.QUEUE_TYPES`,
   `BACKGROUND_QUEUE_TYPES`, the new event types and `SocietyRules` are data and already written.
1. `society/population.py` (`test_population.py`), `society/household.py` (`test_household.py`).
2. The parts of `society/work.py`, `society/settlement.py` and `society/group.py` that are not timer
   handlers (`parse_key` … `pick_cover`, `assign_cover`, `miss_shift`, `adjust`, `shift_start`;
   `daily_need` … `trade_terms`; `tension_of` … `animosity`), then `world/rumours.py` `seed`,
   `spread_one`, `holders`.
3. `action/cascade.py`: the P9 selectors and precondition paths, the P9 dispatch lines, CAS-06
   scheduling and `fire_scheduled` (`test_timers_society.py::test_cas_05_*`, `test_cas_06_*`).
4. `turn/timers.py`: the P9 dispatch lines, `fire_one`, `fire_due`, `seed_society`,
   `run_offscreen` — the test helpers' `run(w, hours)` is `run_offscreen`, so most P9 tests need it.
5. The timer handlers and their `ensure_timers`: `work.cycle`, `settlement.day`, `routine.*`,
   `group.day`, `rumours.spread_day` (`test_work.py`, `test_settlement.py`, `test_routine.py`,
   `test_group.py`, `test_rumours.py`).
6. The turn amendments: `turn/select.horizon` (HOR-01 background rows), `turn/pipeline` stage 0
   (`seed_society`, `fire_due`) and stage 12 (`fire_one`), `action/intent.plan_continuation` step 5
   (routine options), `service/view` journal rumours (`test_timers_society.py`, the rest of
   `test_rumours.py`).
7. `test_econ_chain.py` last: it is the proof that the pieces add up, and it must pass without a
   single line written for it.
Gate: `p09_society` green with P0–P8, the sim soak and the P8 steps: the ECON-01 chain fires
unprompted from one injury; SOC-02 relationships drift with the PC absent; a rumour reaches trade;
the P7 scenarios (no settlements) run exactly as before.
**Forbidden:** worldgen and world motion (P10: materialising people, leaving a group, trade runs,
off-screen deaths, rumour distortion). Code never acts for a human-controlled body — no routine,
cover, drift, loyalty check or animosity roll for the PC. Build against the hand-authored
`pump_settlement` scenario.

### P10 — Wide world
Read: 06 §1, §3–5, `world/worldgen/*`, `world/*`, CMG §61 (carried in tables.py).
1. `worldgen/conditions.evaluate`. 2. `worldgen/params.py`. 3. `world/traces.py` (then `physical/space.discover_layout`, which creates the Fall-damage trace through it). 4. `world/decay.py`. 5. `world/infected.py`. 6. `world/worldmove.py`. 7. `worldgen/pipeline.py` WG0–WG9 + genesis snapshot. 8. `service/runs.create_run` (worldgen path).
Gate: `p10_world` green; `gate.py` runs a full worldgen at `gotta_go_to_work_soon` with the fake model and asserts WG9's invariants and the 58-bit gate on genesis.
**Forbidden:** rendering changes. The world can be wrong in the store, where it is cheap to see.

### P11 — Audits
Read: 04 §3.3, §5, `audit/*`, `narration/style.py`.
1. Every commit-gate bit exactly as described; `BIT_STAGE` refined per bit. 2. `audit/portrayal.py` (targeted pre-check + retrospective). 3. `audit/abuse.py`. 4. `narration/style.py`. 5. `tools/as/eval.py --ablate` against the fake model.
Gate: `p11_audits` green — AUDIT-02 (each of 58 faults drops exactly its bit) is the most important test in the suite.
**Forbidden:** nothing. This phase may reach anywhere, because its job is to be adversarial.

### P12 — Surfaces
Read: CHEATS.md, 09 §8, 10 §2.6, `cheats/*`, `content/importers.py`, `service/death.py`, `service/runs.py` (worlds).
1. `cheats/commands.py` parse/execute + GameService routing + the `cheat_admin` pack. 2. `content/importers.py` (files, character cards, docx, dossier intake). 3. `service/death.py`. 4. Worlds (list/export/import, `create_run(world_id=…)`). 5. Migration framework (`kernel/migrations/`, consent flow). 6. Read aloud via Talemate TTS.
Gate: `p12_surfaces` green.

## 5. Phase acceptance details

### 5.7 The P7 pivot list (Rebuild Plan §15.3 — every line has a test)
| Must hold, repeatably, in play | Test |
|---|---|
| Actors do not know hidden facts | `p07_slice/test_p07_slice_metal_fence.py::test_packets_contain_only_own_percepts` |
| Actors disagree without being told to | `::test_divergent_intents_from_divergent_percepts` |
| Call order does not create telepathy | `p05_many_actors/test_telepathy.py::test_order_permutation_identical_contexts` (re-run by every P7 gate) |
| Actions fail | `p07_slice/test_slice_checks.py::test_a_failed_climb_is_committed_and_narrated` |
| Sound produces believably wrong beliefs | `::test_partial_overhear_makes_partial_belief` |
| Each Actor remembers only its own experience | `::test_four_memories_one_absent` |
| The player receives nothing their body could not have | `::test_narration_withholds_alley` + `test_location_view.py::test_the_play_view_after_the_anchor_turn` |
| Save/reload preserves subjective history incl. wrong beliefs | `test_save_load.py::test_false_belief_survives_reload` |
| The narrator cannot rewrite reality | `test_narration_lint.py::test_invented_dialogue_rejected` + `::test_narrator_has_no_write_handle` |
| A refusal persists into the next scene | `test_slice_refusal.py::test_refusal_reloads_after_scene_change` |
| The same inputs reach the same world | `sim/test_soak_metal_fence.py::test_fifty_turns_hold_then_replay` (DET-02) |

If P7 does not hold, go back to P3–P6. Do not build outward.
