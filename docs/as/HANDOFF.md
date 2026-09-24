# HANDOFF — state of the kit at the end of the Claude sessions (read before continuing P10)

This file is for whoever continues writing the kit (a person or another model). It says exactly
what is finished, what is half-finished and what does not exist yet. It is not a build document for
the DSH builder; delete it when P12 ships.

## 0. One correction first

Earlier summaries said P0–P12 all had full contract docstrings. That was wrong. **P0–P9 are complete
and verified** (contracts, protected tests, reference proof, docs, full zip + patch). **P10 is half
done** (contracts written, reference mostly written, no tests). **P11 and P12 are still at stub /
design level**: the modules exist with short docstrings from the original plan, but they are not
contract-grade and have no tests.

## 1. How the kit is made (the method to keep using)

Per phase: design → contract docstrings in `as_engine/src/as_engine/**` (the docstring IS the spec;
function bodies stay `raise NotImplementedError("P<n>")`) → protected contract tests in
`as_engine/tests/contract/p<nn>_<name>/` → a scratch reference implementation that is NEVER shipped,
used only to prove the contracts and tests are buildable and consistent → docs (`docs/as/*`) →
`tools/as/gate.py --docstrings --write-rules --scan`, `tools/as/protect.py --write-manifest` →
full suite green on the reference → full-kit zip + patch zip vs the previous delivery.

Standing rules (from the owner, all still in force):
- Never change the version number of any document or system without explicit instruction
  (SCHEMA_VERSION was NOT bumped for the P10 schema columns — DECISIONS D-38).
- Check the work before delivering it. Do not produce documents nobody asked for.
- `.cmd` downloads fail for the owner; deliver `.zip` or `.txt`.
- Codex_Master_Guide may only be edited with the owner's permission (pending requests below).
- No sexual or romantic content involving minors anywhere (content check CNT-11 is protected).

Merge rule for patches (the builder has already filled P0–P9 bodies): insert new functions BEFORE
an existing `def` line, never directly after a body the builder wrote; do not change a signature on
the line next to a built body. Simulate the merge: take the previous delivery's repo, replace every
`raise NotImplementedError("P0".."P9")` with a dummy body, commit, `git apply --3way` the new patch.

## 2. Test command

```
cd as_engine
PYTHONPATH=<reference dir> python3 -m pytest tests/contract tests/sim -q -p no:randomly \
  -o addopts="-p no:cacheprovider --import-mode=importlib -m 'not live'"
```
With the P10 scratch reference (delivered separately as `AS_p10_scratch_reference.zip`, folder
`ref2/`) all **908 P0–P9 tests pass** after the P10 contract changes (two old tests were amended,
§4). Without a reference every body raises NotImplementedError, as intended.

The reference is kept in sync by `sync_ref.sh`: it copies the kit's source over `ref2/` except the
hand-written files listed in `ref_impl_files.txt`, then appends `from ._ref_x import …` lines that
rebind the stubs to the `_ref_*.py` implementations. The paths inside it are absolute to the old
scratch folder — change `S=` at the top before using it.

## 3. P10 — what is DONE

### 3.1 Contracts written (kit source)
- `contracts/settings.py`: WorldRules additions (start_hour, world_hour, mortality_mult, op_chance,
  op_party, op_leg_h, op_dwell_h, defect_after_days, weather_change_chance), `InfectedRules`,
  `RulesConfig.infected`, `ERA_DAYS_RANGE`.
- `contracts/events.py` (PLACE_CHANGE, INFECTED_STATE, WORLD_DAY, RUMOUR_DISTORTED),
  `contracts/view.py` (PCCardView.world_age_days / world_age_note), `kernel/clock.py` (queue types
  INFECTED_STEP, WORLD_DAY), `kernel/schema.sql` (infected_state.risen_from/since/degrade_at etc.),
  `kernel/errors.py`.
- Worldgen, all in `world/worldgen/`: `tables.py` (CMG canon), `atlas.py` (AS tables, stage labels,
  DIFFICULTY_LABELS / ERA_LABELS), `params.py` (WG0), `placement.py` (Part X + QC-2/3 + hard-fail),
  `region.py` (WG1), `history.py` (WG2 + `home_settlement`, implemented), `polity.py` (WG3/4/5/7),
  `people.py` (WG6, `skeleton_dossier` implemented), `opening.py` (WG8, `fallback_opening`
  implemented), `checks.py` (WG9), `pipeline.py` (orchestration, retries, genesis, call log).
- World: `world/traces.py`, `world/infected.py`, `world/worldmove.py`, `world/decay.py`,
  `world/rumours.py` (INFO-06 retell + spread_one amendment).
- Amendments: `physical/bodies.py` (create/expose/die/rise, DEATH rise_pending + REANIMATION
  schedule), `physical/space.py` (discover_layout, place_body, change_place), `physical/objects.py`
  (condition), `mind/actor.py` (create), `mind/perception.py` (trace percepts, word_for "what was
  left of"), `society/population.py` (take_from_cohort, materialise), `society/routine.py`
  (on_arrival), `action/propagate.py` (infected noise/sight, evidence traces), `action/effects.py`
  (bite → expose + feed; on_arrival after a MOVE), `action/cascade.py` (INFECTED_DRIFT,
  create_trace, `TRACE_TEXT` implemented), `narration/location.py` (traces line),
  `turn/timers.py` (P10 dispatch lines, seed_world, run_offscreen), `turn/pipeline.py` (S0 seeds the
  world), `audit/commit_gate.py` (W12 now allows a place target), `service/runs.py` (create_run),
  `service/game_service.py` (P10 handlers, `worldgen_task`, `background` property, busy),
  `service/background.py` (new: quiet-hours reflection and rumour retelling), `cli.py` (new-run),
  `testing/fake_lm.py` (worldgen defaults), content `cascade/people.yaml` (CAS-013 body_id).

### 3.2 Scratch reference written (in `ref2/`, proves the contracts)
- `world/worldgen/_ref_wg.py`: every worldgen function WG0–WG9 and `run_worldgen`. **A full world
  generates end to end with the fake model** (every PC × era × difficulty that WG-34 allows, tiers
  gotta_go_to_work_soon → not_using_my_laptop_today, ~0.2 s at the smallest tier); WG9 and the
  58-bit gate pass on it. Driver scripts: `p10/drive_wg.py`, `p10/sweep.py`, `p10/look.py`.
- `world/_ref_p10.py`: mind.actor.create, population.take_from_cohort / materialise, traces
  (create/decay/lock/traces_in), infected (all functions), propagate (P10), worldmove (all),
  decay (all), rumours.retell. **Written but only lightly exercised** — no test drives the infected
  step loop, world days, operations, decay or retelling yet.
- Patched reference files: `mind/perception.py`, `action/_ref_effects.py`, `action/_ref_p5b.py`
  (cascade dispatch), `narration/_ref_location.py`, `society/_ref_society.py` (routine arrival),
  `world/_ref_rumours.py`, `turn/_ref_timers.py`, `turn/_ref_pipeline.py`, `kernel/clock.py`,
  `audit/commit_gate.py`.

## 4. P10 — what is MISSING (do these in this order)

1. **Reference still to write**: `service/background.py` (jobs / run_job / commit /
   BackgroundRunner — contract is complete; REFLECTION payload carries `handles`),
   `service/runs.create_run`, the GameService P10 handlers (`on_pcs_list`, `on_run_new`,
   `on_worldgen_cancel`, background start after a turn and cancel before turn/load/close/new),
   `cli new-run`, and the replay amendment **BG-05** (the replay contract in `service/replay.py`
   does not mention it yet — add: after replaying turn T, re-commit the original REFLECTION and
   RUMOUR_DISTORTED events of turn T through `background.commit` from their payloads).
2. **Tests** `tests/contract/p10_world/` (none exist): conftest with a session-scoped generated
   world (gotta_go_to_work_soon, fake model) copied per test; tests for conditions, params vectors
   and contradictions, placement / QC / abort message, region reachability, full-worldgen
   invariants (WG9 list), determinism (same seed → same world_state_hash), stage retry, cancel
   cleanup (no folders left), WG-34 SettingsError, discovery + loot on arrival, traces + decay,
   infected (sees / attract / step / bang on a closed door / bite → infection → rise as a NEW body
   named "what was left of X"), world day (weather, mortality, operations leave traces — WORLD-03),
   materialise conserves headcount (CONSERVE-04), background jobs (reflection, retelling
   refusal of invented names), protocol (pcs_list, run_new → worldgen_progress → run_loaded,
   worldgen_cancel), replay with background events.
3. **UI**: vitest specs + fixtures for WizardScreen and WorldgenScreen; PlayApp routes the wizard
   and worldgen screens instead of LaterScreen.
4. **Docs**: 06_WORLD §1 and §3–5 rewritten to the contracts; 13_BUILD_ORDER P10 task list (the
   current one is the old plan); 03 (new columns/events), 04 (S0 seeding), 10 (wizard, worldgen
   screens), 11 (settings), 12 (p10 tests); DECISIONS D-39…D-50 (list in §6); CHANGELOG P10 row;
   GLOSSARY (materialise, trace, magnet, home settlement, quiet hours); README_FIRST; PROGRESS;
   regenerate RULES.md with `gate.py --write-rules`.
5. **Hygiene**: reflow docstring lines over 100 characters in the P10 files (routine.py 53,
   decay.py 59, infected.py 186–191, traces.py 41/50, worldmove.py 147, atlas.py 24, rumours.py
   111); `gate.py --docstrings --scan`; `protect.py --write-manifest` (the two amended protected
   tests below change the manifest).
6. **Package**: full suite on the reference, merge simulation vs the P9 delivery, full zip + patch
   zip, fresh-unzip verification.

Protected tests amended in P10 (already done, keep them):
- `p02_space_bodies/test_bodies.py::test_bleeding_out_unconscious_then_dead` — the DEATH payload
  now carries `rise_pending: true`.
- (P05 needed no change after `on_arrival` was made a no-op in runs without `world_params`.)

## 5. P11 and P12 — NOT STARTED at contract level

**P11 Audits** (13_BUILD_ORDER §4): every commit-gate bit exactly as described with BIT_STAGE per
bit; `audit/portrayal.py` (targeted pre-check + retrospective); `audit/abuse.py`;
`narration/style.py`; `tools/as/eval.py --ablate`. Test `p11_audits/test_commit_gate_bits.py`
(AUDIT-02: each of the 58 injected faults drops exactly its bit) is the key test. Also carried here
from P10: the release audit re-runs `checks.assert_world` on the genesis snapshot (D-45) and counts
the off-screen trace ratio (`WorldRules.min_offscreen_trace_ratio`, WORLD-03), and fails a build
that still records `timer_unbuilt` / `cascade_unbuilt`.

**P12 Surfaces**: `cheats/commands.py` + GameService routing + the `cheat_admin` pack (CHEATS.md —
the owner's "bonus dev-cheats" document); `content/importers.py` (files, character cards, docx,
dossier intake); `service/death.py` (death screen, new life here); worlds (list / export / import,
`create_run(world_id=…)` from `_worlds/<id>/genesis.sqlite`); migration framework
(`kernel/migrations/`, consent flow); read-aloud via Talemate TTS; final CNT-11 check across all
content; the play-UI smoke checklist §7–§8.

## 5A. "Ready to build" — the definition, and everything between here and there

A phase is READY TO BUILD when the DSH builder, given only the kit, can implement it and prove it
without asking anyone. For every phase that means nine things exist and agree with each other:

| # | Artifact | Where |
|---|---|---|
| R1 | Contract docstrings for every function the phase builds: inputs, outputs, every rule, every error, exact event types and payloads, rng streams and purposes, row shapes. Bodies stay `raise NotImplementedError("P<n>")` | `as_engine/src/as_engine/**` |
| R2 | Protected contract tests that fail on the stubs and pass on a correct build | `as_engine/tests/contract/p<nn>_*/` |
| R3 | Fixtures the tests need (scenarios, packs, fake-model scripts, vectors) | `as_engine/tests/fixtures/`, `testing/fake_lm.py` |
| R4 | Proof: a scratch reference passes R2 AND every earlier phase's tests (never shipped) | scratch `ref2/` |
| R5 | Design docs rewritten to match R1 (the docs explain; the docstrings rule) | `docs/as/0x_*.md` |
| R6 | The phase's task list, gate and forbidden list in `13_BUILD_ORDER.md` §4, in build order | docs |
| R7 | Records: DECISIONS rows, CHANGELOG row, GLOSSARY terms, RULES.md regenerated, PROGRESS row, SPEC_ISSUES for anything left open | docs |
| R8 | Tooling passes: `gate.py --docstrings --scan --write-rules`, `protect.py --write-manifest` then `--verify`, lines <= 100 | `tools/as/` |
| R9 | Delivery: full-kit zip + patch zip vs the previous delivery, merge-simulated against a built previous phase, fresh-unzip test run | outputs |

### P10 — status against R1–R9
- R1 done except: `service/replay.py` BG-05 line (add it), and a second read of `worldmove.py` /
  `infected.py` once the tests exist (they will expose gaps — fix the docstring, not only the ref).
- R2 missing entirely (§4 item 2 lists the tests). R3: a small hand-made scenario with world_params
  for the infected / world-day tests; fake-model scripts for WORLDGEN_* failure paths (bad QC-4 twice
  → code opening; history answer too short → skeleton kept); a UI fixture of worldgen_progress.
- R4 partial: worldgen proven; background / create_run / GameService P10 / cli / replay not
  written; world motion written but unproven.
- R5–R9 missing (§4 items 3–6). R6 matters most for the builder: the current P10 task list in
  13_BUILD_ORDER is the old 8-line plan and must become the real order: conditions → params →
  placement → region → traces → space.discover_layout/change_place/place_body → bodies P10 →
  mind.actor.create + population.materialise → history → polity → people → infected → opening →
  checks → pipeline → decay → worldmove → rumours.retell → propagate/effects/cascade/location/
  routine amendments → timers + turn S0 → runs.create_run → background → GameService → cli →
  replay → UI wizard + worldgen screens.

### P11 — Audits (nothing below exists yet)
R1 contracts to write:
- `audit/commit_gate.py`: every one of the 58 bits already has a one-line check; each needs the
  exact query, what "this turn" means for it, its BIT_STAGE (the stage to rerun), and its fault
  (the single DB edit that must drop exactly that bit). Genesis rules for generated worlds (P10).
- `audit/portrayal.py`: `precheck(...)` (before commit, which actors, prompt context, verdict model,
  regenerate-once flow) and `retrospective(...)`; the PortrayalAudit context and answer models; the
  judge-call-id ≠ producer-call-id rule; what is logged.
- `audit/abuse.py`: one function per ABUSE-01..08 with inputs, pass condition and plain failure text.
- `narration/style.py`: load / save / update_after_turn (noun-phrase extraction exact enough to
  test); wire into narrator packet (images not to reuse) — the anti-repetition the owner asked for.
- Release audit (new module, e.g. `audit/release.py`): re-run `checks.assert_world` on genesis,
  off-screen trace ratio >= `min_offscreen_trace_ratio`, no `timer_unbuilt` / `cascade_unbuilt`
  rows, CNT-11 over all content, soak statistics.
- `tools/as/eval.py --ablate`: which call classes, what is measured, pass thresholds.
R2 tests: `p11_audits/test_commit_gate_bits.py` (58 parametrised faults, each drops exactly one
bit — AUDIT-02, the most important test in the suite), portrayal flow with scripted verdicts,
abuse battery on clean + deliberately broken worlds, style persistence across save/load, release
audit on a generated world, eval ablation smoke run.
R3–R9 as above; docs 04 §3.3/§5, 07, 12, CHANGELOG, DECISIONS.

### P12 — Surfaces (stubs exist; contracts not finished)
R1 contracts to write or finish:
- `cheats/commands.py` (195-line draft exists): finish every command's exact effects, events,
  refusals and persona lines; GameService routing (turn_submit with the 2508 token, /commands);
  the `cheat_admin` pack (dossiers such as 'fredrick'); sandbox save rules (CHEAT-02); guarantee
  CHEAT-03 (no cheat words in any narrator/actor prompt). `docs/as/CHEATS.md` (254 lines) is the
  owner's bonus document — keep it and the contract identical.
- `content/importers.py` (draft exists): import_file per format, character-card mapping, docx
  extraction, intake_document chunk/merge/validate, ImportResult / IntakeJob, progress pushes.
- `service/death.py` (13-line sketch): DeathView model, cause-chain rendering, last turns,
  contributing choices, truth_reveal after explicit click (DEATH-10), new-life-here flow.
- Worlds: `service/runs.py` list_worlds / export / import / `create_run(world_id=…)` from
  `_worlds/<id>/genesis.sqlite` (RUN-09); the world.json format is already fixed by P10.
- Migrations: new `kernel/migrations/` package — registry, per-version step, consent flow, backup
  before migrating (and note: version numbers change only on the owner's instruction).
- Read-aloud via Talemate TTS: which text, when, settings switch.
- GameService P12 handlers (content_import, intake_start, quickmake_pc, death_reveal,
  new_life_here, worlds_list, world_export, world_import, on_death) and their protocol models.
R2 tests: `p12_surfaces/` for each item; UI vitest for death, imports, cheats, worlds screens.
R3: sample character card (png + json), sample docx, cheat pack, a world export file.
R4–R9 as above, plus the final whole-kit verification: full suite, CNT-11 over every pack, the
play-UI smoke checklist §7–§8 updated, and the last full zip.

### Rough size (for planning)
P10 remaining ≈ 35–45 % of P10 (tests are the big part). P11 ≈ one full phase (the 58-fault test is
the bulk). P12 ≈ one full phase, larger in surface area (five subsystems + UI).

## 6. P10 decisions to record in DECISIONS.md (D-39 … D-50)

D-39 code decides, the model only writes words, and every model call has a code fallback (a world
is always complete). D-40 WG2 plans the polity and a causal history first; WG3–WG7 build what it
says (WORLD-01). D-41 region = per zone a hub street + building sites (grounds) + roads; rooms are
made the first time anyone arrives. D-42 named labour only at the home settlement; other
workplaces run on unnamed people (required_roles []). D-43 infected are driven by INFECTED_STEP
timers, the same on-screen and off. D-44 the risen dead are NEW bodies (risen_from). D-45 WG9's
daily re-assertion is not in v1; P11 audits the genesis snapshot. D-46 quiet-hours background jobs
are recorded events and replay from their payloads. D-47 Part XII's automatic retries/era shifts
are player choices in the wizard. D-48 the PC's survival history comes from the recap by code.
D-49 backlog, not v1: Lots, leadership challenges, splinters, coalitions, doctrine-driven
behaviour, weather couplings, exploration-magnet timers, lurker attack branches. D-50 schema
columns added without a version bump (owner rule; D-38).

## 7. Requests still waiting for the owner

- Permission to note goals/issues in `Codex_Master_Guide` (asked earlier; not edited).
- Review `SPEC_ISSUES.md`.
