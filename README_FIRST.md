# Authentic Suffering — build kit: read this first

This kit is the complete specification of **Authentic Suffering (AS)** plus everything a coding
agent needs to build it: the design docs, an engine skeleton whose docstrings are the contracts,
executable contract tests, the core content pack, and the tools that gate each phase. It is laid
over a clone of **Talemate 0.39.0**; the game engine is the separate pure-Python package
`as_engine/`, and the agent that builds it works in **DeepSeek Harness (DSH)** on your local
LM Studio models.

## 1. Status of this copy (interim)

| Part | State |
|---|---|
| Design and rules (`docs/as/`, 14 docs + CHEATS, GLOSSARY, DECISIONS, RULES) | Specified for all phases P0–P12 |
| Engine (`as_engine/src/`) | Every module, function and contract docstring for P0–P12. **P0–P10 are built** (committed on your instruction, 2026-09-24): the bodies are in `_impl_*.py` files bound at the end of each contract module, Actor v2 steps 1–3 included. P11–P12 bodies are stubs that raise `NotImplementedError("P<n>")` |
| Contract tests P0–P6 (substrate, lanes, space/bodies/content, perception, one Actor, many Actors, memory) | **699 tests** (693, plus six that pin P10 lines of those phases) |
| Contract tests P7 (the slice: whole turns of the fence scene, intake, narration and its lint, the *Where you are* panel, saves, replay, the command line) and the 50-turn sim soak | **41 tests + 1 soak** |
| Contract tests P8 (the Play UI protocol: connect, runs, turns in the background, Stop, reconnect, Ask, settings, the developer panel, packs) | **98 tests** (83, plus one check per fixture message P10 added; the service side is built — the Talemate plugin, the frontend toolchain and the P8 screens are the builder's) |
| Play UI specs (`talemate_frontend/src/play/__tests__/`, vitest) | **161 tests in 14 files**, with 41 fixture messages. The P8 specs (124 tests) pass against a reference front end built on a real Talemate 0.39.0 frontend with the 02 §4.1 changes; the P10 specs (37 tests: the New Life wizard, the Worldgen screen, the loading bar and its lines) and the amended app spec pass against a reference of the P10 screens (the P10 screens are now in `talemate_frontend/src/play/`; the P8 screens are placeholders the builder writes) |
| Talemate plugin test (`tests/test_as_game_plugin.py`) and the Play UI smoke checklist | In. The plugin test passes (7/7) against the reference service; checked against the real Talemate 0.39.0 source (plugin base, route table, one-connection rule, the sequential message loop, pnpm, uv) |
| Contract tests P9 (society: households, routines, work and cover, the settlement's stores and rations, tension, drift, loyalty, standing, rumours, the off-screen step; the one-injury-reaches-morale chain) | **91 tests** |
| Contract tests P10 (the wide world: worldgen from the wizard's choices to a playable run; buildings found, not pre-built; marks; the dead up close and counted by district; hordes, the exterior and the Mega Horde; the world's day with nobody deciding; outings and raids; the wet strain's living spreaders; the Ghosts; the quiet hours between turns; the loading bar) | **268 tests** (231 test functions). All 1198 engine tests (P0–P10 and the soak) pass against the reference implementation |
| Actor v2 steps 1–3 (the Actor Specification: a person's own prompt and identity card; a menu from what they know, laws as costs, who is where; the answer format, one consultation, the hold when an answer fails) | Contracts, tests and bodies in. **All 1299 engine tests pass** on the committed engine |
| Contract tests P11–P12, live tests | **Not in this copy yet.** The builder stops after the P10 gate; a kit update adds them |
| Core content pack (`as_content/packs/core/`) | 289 records, all validate |
| DSH builder kit (`AGENTS.md`, `.dsh/skills/`, hooks, `tools/as/`) | In. The hook scripts are tested (59 tool-call cases); the DSH bridge-plugin wiring comes from the DSH hooks docs and has **not** been run on a real DSH install — §4 tells you how to check it in two minutes |

## 2. What is where

```
README_FIRST.md            this file
AGENTS.md                  the builder's rules (DSH loads it into every session)
.dsh/skills/               9 on-demand builder skills        .dsh/hooks.json   harness hooks
as_engine/                 the game engine (package as-engine) + tests/
as_content/packs/core/     the core content pack
as_config.example.yaml     install config template (setup copies it to as_config.yaml)
docs/as/                   the spec — start with 00_README.md
tests/test_as_game_plugin.py            Talemate-side plugin test (P8)
talemate_frontend/src/play/README.md    your smoke checklist (P8 part §0–§6; §7 after P10, §8 after P12)
talemate_frontend/src/play/__tests__/   the Play UI specs and their fixtures (P8, P10)
tools/as/                  setup, doctor, gate, protect (+ manifest), probe, bench, eval
```

The kit adds files only; it replaces none of Talemate's.

## 3. Install (Windows desktop)

1. Clone Talemate at 0.39.0 into a new folder and make a branch:
   ```
   git clone https://github.com/vegu-ai/talemate.git AuthenticSuffering
   cd AuthenticSuffering
   git checkout -b authentic-suffering 0.39.0
   ```
2. Run Talemate's own `install.bat` once (it creates `.venv`, the embedded Python and Node, and
   builds the frontend).
3. Unzip this kit into that folder (merge).
4. In a terminal in that folder:
   ```
   .venv\Scripts\activate
   python tools\as\setup.py
   ```
   This installs `as_engine` with its test tools into Talemate's `.venv` (with uv, because that venv
   has no pip), copies `as_config.example.yaml` to `as_config.yaml`, writes the hook files with this
   machine's Python path, prints the DSH hook snippet (next section) and runs the doctor. Expected
   doctor result on a fresh kit: no red; warnings for git and node are fine until later phases.
5. Commit the baseline and tag it:
   ```
   git add -A
   git commit -m "Authentic Suffering kit baseline"
   git tag as-kit-baseline
   ```

## 4. Wire the hooks into DeepSeek Harness

The hooks keep the builder honest: at session start it is told the current phase and next task;
before every tool call a guard blocks writes to protected files (tests, fixtures, docs, the gate
tools); when it stops, it must have filled in *Next task*. They are ordinary Claude-Code-format
command hooks, which DSH runs through one of its two bridge plugins. Enable **one**:

**(a) Official bridge** `@deepseek-ai/dsh-hooks-claude-code` — add to the `cordis.patch.yml` of the
profile you build with (`setup.py` prints this block with your real paths):
```yaml
- id: hooks-claude-code
  name: '@deepseek-ai/dsh-hooks-claude-code'
  config:
    configPath: C:/path/to/AuthenticSuffering/.dsh/hooks.json
    projectDir: C:/path/to/AuthenticSuffering
```

**(b) Per-workspace bridge** — `dsh plugin --profile <profile> add dsh-hooks-claude-code-per-workspace`,
then restart the profile. It reads `.claude/settings.json` (same hooks) from the folder you open.

Two-minute check:
- Start a DSH session with the repo folder as the workspace. Its first context must include
  **"Authentic Suffering build — session brief"**. If not, the hooks are not running.
- Ask the agent: *"Add a comment line to as_engine/tests/helpers.py."* It must get a message
  starting **BLOCKED:** and not change the file. Then run `python tools\as\protect.py --verify`
  yourself: `protection: OK`.

Even without hooks the kit is protected: every gate compares the hashes of all protected files and
fails on any change. The hooks just stop mistakes earlier.

## 5. Start the builder

Open DSH on the repo folder with the model you want as the builder and send:

> Start the build. Follow AGENTS.md §1.

It reads `docs/as/PROGRESS.md`. The engine is built through P10, so it first records the gates P0–P7
(`python tools/as/gate.py --phase N`, which writes each evidence row), then builds P8's plugin,
frontend toolchain and screens, then gates P8, P9 and P10 (13_BUILD_ORDER §4.0). With this copy it
should stop after the P10 gate.

## 6. Your part

| When | What |
|---|---|
| Any time | Read `docs/as/SPEC_ISSUES.md`. The builder files there instead of changing a test or doc |
| Approving a change | Edit the protected file(s), add a row to `docs/as/CHANGELOG_AS.md`, then in **your own** terminal set `AS_MAINTAINER=1` (cmd: `set AS_MAINTAINER=1`; PowerShell: `$env:AS_MAINTAINER=1`) and run `python tools\as\protect.py --write-manifest` — after a docstring change run `python tools\as\gate.py --write-reference` first |
| P1 | On your machines: `python tools\as\probe.py --write` (finds each model's thinking switch and structured-output support), then `python tools\as\bench.py --n 5 --accept` |
| P8 | The smoke checklist in `talemate_frontend/src/play/README.md` |
| P10 | Its §7: a new life through the wizard, a world built under the loading bar, the bar during a move, and an Ironman run |

The builder never runs the maintainer commands; the guard blocks them.

## 7. The game (what the spec builds)

- **AI as Dungeon Master, engine as rulebook**: two local models (Nemotron Cascade 2 on the desktop,
  Nemotron 3.5 Lightning on the laptop) play everyone else and narrate; the engine owns rules,
  dice, bodies, clocks, inventory, location and memory. One machine off → slower, thinner, still
  playable, and it tells you.
- **Actors, not NPCs**: each person thinks in their own model call with only what reached them
  (Skull Law); code offers each body only what it can attempt; requests arrive as speech, never
  orders; refusals are remembered; everyone keeps their own version of events, grows goals and
  grudges, and lives and dies off-screen. Everybody dies.
- **You only know what your body knows**: sound and sight computed per listener, fragments through
  walls; the narrator sees only your character's perception; a code-rendered *Where you are* panel,
  hard-coded inventory and body panels.
- **DnD-style rules without clutter**: one universal d10 check with four outcomes, a six-step
  stealth ladder, wounds with anatomy and bleeding clocks instead of hit points, impairment that
  removes options, one death test for every body.
- **Continuous time**: a turn is a decision, not a tick; talking takes real seconds.
- **Persistent memory and strict logging**: every change is one event with a cause; replay
  reproduces the world hash; per-run logs of every model call; beliefs, lessons, rumours, traces
  and promises persist and decay by rule; a journal of promises, goals, rumours, lessons and the dead.
- **Dialogue that doesn't cringe**: stable voices (three example lines, a "would never say" list,
  recent real lines), an echo ledger that rejects quoting your words back, narration lint.
- **Choose or bring your character each run**: pack characters as cards, import YAML/Markdown or
  SillyTavern/Chub cards, quick-make, or run a long document through dossier intake.
- **Worldgen**: six difficulties (Bitch Mode → Fuck You), three eras, detail from ~3 minutes to
  ~an hour; causal history, factions, settlements, households, law, an opening built from real
  threats; every world saved, reusable and exportable.
- **Per-run settings**: difficulty, era, save mode (Free or Ironman), narration length/person/tense,
  turn depth, "say it my way", show dice, developer mode.
- **Content packs**: people, PCs, factions, lore with truth and belief layers, items, laws,
  buildings, infected variants, cascade rules — plain YAML/Markdown with a plain-language validator.
- **Death that teaches**: cause, last turns and contributing choices from your record, then
  "show me everything" — the truth you never perceived; new life in the same world.
- **The bonus document — cheats** (`docs/as/CHEATS.md`): a hidden developer mode nothing admits
  exists until activated; commands for items, healing, god mode, teleport, stat edits, time skips,
  weather, reputation, spawning, kill/revive, and reading the hidden truth or a person's mind;
  Mr. Cheater Man and Fredrick the admin companion; a cheated run is marked Sandbox forever and
  cheat-made things are quarantined from balance. One line no setting or cheat can cross: no
  sexual or romantic content involving minors (content rule CNT-11, protected).

## 8. Updating from an earlier copy

**The engine is in the repo from this copy on.** If your builder already wrote bodies in an earlier
copy, taking this one replaces them (or conflicts with them in git): keep one or the other. The
committed engine passes every P0–P10 test; the builder's copy has its own gate evidence.

**Haven't started the builder yet?** Unzip this kit over the folder and commit. **Already
building?** Don't unzip over it (that would put stubs back over finished functions) — apply the
patch instead, from the repo root. From the P9 copy:
```
git apply --3way as_kit_update_p10.patch
git add -A && git commit -m "Kit update: P10"
```
From an older copy, apply the earlier patches first, in order (`as_kit_update_p6.patch`,
`as_kit_update_p7.patch`, `as_kit_update_p8.patch`, `as_kit_update_p9.patch`), then the P10 one.
Then run `python tools\as\protect.py --verify` (expect `protection: OK`) and tell the builder:
*"The kit update is in. Continue with P10 (AGENTS.md §1)."* It sets its own Next task in
`PROGRESS.md`.

What the P10 update changes for the builder (13_BUILD_ORDER §4 P10 has the order, step by step):
- **P10 (new)** — full contracts and 268 tests (`tests/contract/p10_world/`): worldgen from the
  wizard's choices to a playable run (`world/worldgen/*`, `service/runs.create_run`); buildings
  laid out the first time anyone walks in; marks and wear (`world/traces.py`, `world/decay.py`);
  the dead up close (`world/infected.py`) and counted by district, the hordes on the roads, the
  dead past the map's edges and the Mega Horde (`world/hordes.py`); the world's day with nobody
  deciding, outings and raids (`world/worldmove.py`); the Ghosts' council, route watch, lockdown
  and DECON (`world/factions.py`); the quiet hours between turns (`service/background.py`); the
  loading bar (`service/progress.py`); the GameService handlers for the New Life wizard and
  worldgen; `as-engine new-run`. Play UI: the wizard, the Worldgen screen and the loading bar
  (37 new vitest tests with their fixtures). New builder skill `as-world`.
- **Earlier modules** (each marks its P10 lines "P10"): `physical/objects`, `physical/space`
  (`remove_body`; a route enters each place at most once — the new P2 test
  `test_space.py::test_a_route_never_enters_a_place_twice`, so rebuild `path`), `physical/bodies`
  (a DEATH now carries `rise_pending` and schedules the rising — the P2 test
  `test_bodies.py::test_bleeding_out_unconscious_then_dead` changed, so rebuild `die`),
  `mind/actor.create`, `mind/perception` (marks as percepts; "what was left of"; a move reads
  "arrives" or "moves into <place>" for someone coming), `mind/packet`, `mind/affordance`,
  `mind/retrieval`, `mind/memory` and `turn/select` (SKULL-10: a mind decides on what it had
  perceived by its own moment; options name the kinds of body and way they fit; nobody speaks to
  or dresses the wounds of the dead; a loud noise holds the active area for 10 minutes of world
  time), `mind/cues`, `society/population` (`take_from_cohort`,
  `materialise`), `society/routine` ('away'), `society/settlement` (lockdown), `action/reactions`
  (one of the dead seen coming within 20 m is news), `action/propagate`, `action/effects`,
  `action/cascade`, `turn/cognition` (the wet strain's week-3 pull, never the PC's), `turn/timers`
  (`seed_world`, the new dispatch lines; the off-screen step skips a body folded back into a
  count), `turn/pipeline` (stage 0 starts a generated world's
  clocks), `narration/*`, `world/rumours` (`retell`), `service/view` (the dice receipt names a
  defence; no two suggestions alike), `service/replay` (BG-05), `audit/commit_gate` (W12). New
  tests in finished phases pin the lines you must amend: p02 `test_space.py` (a route never
  enters a place twice), p03 `test_perception.py` (how a move reads), p04 `test_packet.py` and `test_affordances.py` (SKULL-10, a gap has nothing to close, the
  dead are not people), p07 `test_location_view.py` (the receipt's defence line). A run without a
  `world_params` row — every hand-made scenario — must otherwise run exactly as before.
- **Actor v2** (the Actor Specification, in place in finished phases): a person's own prompt and
  the identity card — `mind/identity.py` is new and implemented (do not rewrite it); rebuild
  `mind/packet.build_packet` (the card replaces the identity lines; whereabouts, the hour only
  with a timepiece, cut floods of words, the budget's pins and `omitted`) and
  `mind/memory.build_aftermath` (the aftermath carries the card and cuts words the same way); the
  actor templates are the kit's. Rebuild `mind/affordance.enumerate_affordances` for AFF-11: a
  menu from what the person knows — the duty gate never rejects, known laws are costs, 'owned' is
  a belief, a weapon in a hand counts only when seen clearly; `turn/cognition.record_responses` blocks on
  the moral gate only. Tests: p04 `test_identity.py`, `test_knowledge_menus.py` (new), the amended
  `test_packet.py`, p06 `test_memory.py` and `test_retrieval.py`.
- **P0 data** — new event and queue types, `BACKGROUND_QUEUE_TYPES` grows, new schema columns (the
  schema version is unchanged — DECISIONS D-50), the P10 rule groups in `contracts/settings.py`
  (11 §2.1), the loading bar's protocol messages. `p08_ui_protocol/protocol_kit.py` leaves the
  bar's messages out of `pushed_after` (the P8 tests themselves did not change).
- **Content** — the Ghosts (`factions/ghosts.yaml`, `lore/ghosts.md`), infected states and quirks,
  pathways with their felt lines and signs, buildings and loot tables, name lists, the loading
  bar's lines (`ui/quips.yaml`); CAS-013 now names the body; the door-handling options name the
  kinds of way they fit and the calming, signalling and shielding options are for people
  (`affordances/portals.yaml`, `social_body_attention.yaml`).
- **Docs** — 06 rewritten (worldgen, the Ghosts, the world's day, wear, the dead, hordes and the
  Mega Horde, the quiet hours), 03, 04, 05, 09, 10, 11, 12, 13 (the P10 task list), DECISIONS
  D-39–D-69, GLOSSARY, SPEC_ISSUES SI-004–SI-005, RULES regenerated.

What the P9 update changed (for anyone still on the P8 copy):
- **P9 (new)** — full contracts and 91 tests: population and households (`society/population.py`,
  `household.py`), routines (`routine.py`), work, cover and production (`work.py`), the
  settlement's stores, daily draw, rations, laws and trade terms (`settlement.py`), tension,
  drift, animosity and loyalty (`group.py`), group standing (`mind/mind.py`), rumours
  (`world/rumours.py`), and the off-screen step (`turn/timers.run_offscreen`). The proof is
  `test_econ_chain.py`: one cut arm reaches rations, tension and morale with nothing else
  scripted. New builder skill `as-society`.
- **P0** — new event types, two new timer types and `BACKGROUND_QUEUE_TYPES` (`kernel/clock.py`,
  data only), `SocietyRules` in the settings, and the `work_assignments` key gains
  `shift_start_hh` (`schema.sql`; the schema version is unchanged — DECISIONS D-38).
- **P2** — `physical/bodies.progress` clamps a need stage at 0 (a meal can be later than a step's
  end). **P3** — `mind/perception.grant(..., confidence=)`. **P5** — `action/cascade.py` gains the
  society selectors, precondition paths and dispatch lines, and scheduled effects (CAS-06,
  `fire_scheduled`); `action/intent.plan_continuation` step 5 follows routines. **P7** —
  `turn/timers.py` (`fire_one`, `fire_due`, `seed_society`, `run_offscreen`), the horizon ignores
  background timers (HOR-01), pipeline stages 0 and 12 use them, the journal lists rumours. These
  are P9 tasks: no earlier test changes, and the P7 scenarios (no settlements) must run exactly as
  before.
- **Content** — three cascade rules fixed (CAS-001 hurt the attacker's shifts, CAS-002 lost the
  shift's hours, CAS-007 never fired) and three added (CAS-016, CAS-017 food shortages; CAS-018 a
  theft rumour costs trust). `pump_settlement.yaml` gains six households.
- **Docs** — 06 §2 and §6 rewritten to match the contracts, 03, 04, 11, 12, 13 (the P9 task
  list), DECISIONS D-31–D-38, GLOSSARY, RULES regenerated.

What the P8 update changed (for anyone still on the P7 copy):
- **P8 (new)** — full contracts and 83 tests: the whole Play UI protocol (`service/game_service.py`:
  connect, models, runs, settings, the developer panel, packs; a turn runs as a background task
  whose progress and result are pushed; Stop before "Locking it in…"; a reloaded page finds the
  running turn), Ask (`service/guide.py`), new protocol models (`contracts/protocol.py`), and the
  Play UI specs (`talemate_frontend/src/play/__tests__/`, 124 vitest tests with their fixtures).
  Actions of later phases answer "not built yet"; in P8 you make a run with `as-engine new-scenario`
  and play it in the browser.
- **P0** — `Store.transaction` must roll back on any `BaseException` (Stop cancels a running turn):
  one new test, `test_store.py::test_a_cancelled_task_rolls_back_too`. If your `transaction`
  catches `Exception` only, change it to `BaseException`.
- **P7** — `service/session.change_settings` and `service/replay.resimulate` re-applying mid-run
  settings changes are P8 tasks (the P7 tests do not change); the pipeline docstring now says how a
  cancelled turn behaves (nothing to build: a `finally` already restores it).
- **Docs** — 10 (§1–§4 rewritten: every P8 screen, the socket and the store, which phase builds
  which screen; §7 the specs), 02 (the background turn; the vitest `setupFiles`), 04, 11, 12, 13
  (the P8 task list), DECISIONS D-24–D-30, GLOSSARY, RULES regenerated; the smoke checklist split by
  phase.

What the P7 update changed (for anyone still on the P6 copy):
- **P7 (new)** — full contracts and 40 tests + the sim soak: who takes part and how long a turn
  runs (`turn/select.py`), the player's input (`turn/intake.py`), Actor decisions and how asks
  were answered (`turn/cognition.py`), due timers (`turn/timers.py`), request building
  (`lanes/requests.py`), the 20-stage turn (`turn/pipeline.py`), narration and its lint
  (`narration/`), the play view, saves and runs (`service/`), re-simulation (`service/replay.py`)
  and the command line (`cli.py`). New fixture `fence_climb.yaml`.
- **P0** — `kernel/clock.begin_turn` (a P7 stub in a P0 module); `Store.rebuild_fts` and
  `kernel/store.wall_clock_iso` are implemented for you, and `Store.create`'s `created_at_real`
  now comes from `wall_clock_iso` (the gate's scan forbids importing `datetime` outside `lanes/`;
  if you already wrote `Store.create`, switch it to the helper); bit G08 checks
  `ownership.EVENT_WRITERS` (the resolver and propagation write events but own no table); events
  `NARRATION`, `ECHO_RECORD`, `PENDING_REACTION`.
- **P1** — `lanes/calllog.request_hash` is implemented; `ReplayTransport` now finds a recorded
  call by its request hash instead of its position (concurrent calls finish in any order) and
  replays recorded timeouts and lane errors. One new test
  (`test_calllog.py::test_replay_matches_by_request_not_by_position`).
- **P2** — no code change, but the fixture test runs once more: every scenario fixture must load
  and pass the gate at turn 0, and `fence_climb.yaml` is a new fixture.
- **P5** — `action/reactions.next_wave(..., exclude=)` (the PC never reacts on its own).
- **Testing helper** — `ScenarioWorld.session(run_dir=None)` (a P7 stub).
- **Docs** — 04 (stages, waves, horizon, rollback, scenes, the trace), 13 (the P7 task list),
  12 (the sim tier), 10 (the location templates), DECISIONS D-19–D-23, RULES regenerated.

What the P6 update changed (for anyone still on the first copy):
- **P0** — new rule STORE-11: a write value `"$event_id"` (`kernel.store.EVENT_SELF`) becomes the
  committing event's own id; `kernel.store` mints the event id before applying writes. One new
  test (`test_store.py::test_a_write_can_name_its_own_event`). New implemented helper
  `kernel.events.committed_or_none`.
- **P5** — ACTION_START's payload gains `label` and `goal` (`test_effects.py` updated);
  `action.effects.situation` gains the re-ask penalty for 'negotiable' defs; the cascade dispatch
  table spells out `relate` / `open_loop` arguments; `mind.cues` gains the `promise_broken` cue
  (P6). `tests/helpers.make_intent` gains optional `label=` / `goal=`.
- **P6** — full contracts and 75 tests: relationships, loops, lessons (`mind/mind.py`), refusals
  and lies (`mind/firewall.py`), `perception.infer`, aftermath and writeback (`mind/memory.py`),
  retrieval and its wiring into the packet (`mind/retrieval.py`, `SkullPacket.lessons`).
- **Content** — core cascade rule CAS-011 opened a loop of kind `grievance`, which does not exist;
  it now opens a `grudge` worded in the promisee's own words.
- **Design fix** — closing a promise as broken used to lower trust in *other* minds straight from
  the promiser's private verdict (a Skull Law breach). Now only the person who was owed decides a
  promise was broken, and what that costs comes from cascade content, applied to them alone.

## 9. Known gaps in this copy

- Actor v2 steps 4–6, P11–P12 contract tests and the live suites are still to be written (next kit
  updates). The
  death screen, saved worlds and the sessions browser come with P12 (their specs too).
- Lots for settlement goods, leadership challenges, splintering, coalitions and faction doctrine in
  play are backlog, not v1 (DECISIONS D-49). P10 brings the rest of what P9 left for world motion:
  materialising unnamed people, leaving a group, trade runs and raids, rumour retelling, weather.
- `docs/as/RULES.md` lists every rule id; the P6–P10 families (REL, LOOP, LESSON, MEM,
  WILL-05..11, SEL, HOR, INTAKE, CLI, PROTO, GUIDE, UI-CLARITY, DEMO, HH, ROUT, WORK, STL, GRP,
  STAND, INFO, ECON, SOC, INF, HRD, FAC, OPS, WEAR, BG, PROG and most of WG, WORLD and TRACE) and
  the content rules (a cascade rule's own description) have their own statements. Across the kit
  248 of 580 ids are still named only inside a range or a sentence
  (their behaviour is specified by the module docstring or doc section the registry points to, and
  pinned by tests). Writing individual statements for them is open.
- The sim soak plays 50 turns against the fake model; it proves the pipeline holds together and
  replays, not that the story reads well. That is the live suite's job.
- The Play UI specs run in jsdom: layout, colours and real-browser behaviour are the smoke
  checklist's job. The vitest toolchain was installed and run on Linux; on Windows `corepack pnpm
  install` then `corepack pnpm run test:play` should behave the same, but it has not been run there.
- Voice pinning in the People panel (DOS-05, "Pin a line") has no protocol action yet; it is left
  out of P8.
- Deleting a life (Your lives) overwrites every file the game wrote for it with zeros and removes it
  (RUN-12, D-76). Two things no program can reach: an SSD's own spare blocks, and backups your
  operating system or a sync service made of the `as_runs` folder. For those, full-disk encryption
  and leaving `as_runs` out of backups are the answer.
- The DSH bridge configuration in §4 is from DSH's documentation, not from a run on your DSH.
- Timing and tuning numbers marked `[SAND]` are placeholders until you run `bench.py`/`eval.py` on
  your machines (listed under "SAND remaining" in `PROGRESS.md`).
