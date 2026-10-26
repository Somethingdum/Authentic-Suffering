# 14 — The three-day release (D-296)

The owner, 2026-10-26: *"Rework the plan to be able to be completed and working in 3 days of non-stop work. Pick
the very most important features. We can work out supplemental updates afterward."*

This file replaces 13_BUILD_ORDER §4.0 as the plan until the release below is done. 13's phase lists stay the map
of what each module does and which tests pin it; every rule of AGENTS.md §2 still holds (protected tests, no skip,
determinism, the store is the only writer, the seal, the Skull Law).

**Where it starts.** The engine is built: P0–P11 and most of P12 (the cheats, the death screen, Willis, the
Doom and the Voice, parkour, the importers, the seal). The suite passes **2681 of 2688**. A generated world can be
made and played today in a terminal on the fake model (`as-engine new-run …`, `as-engine play …`, checked
2026-10-26). What is missing is what makes it **a game you can sit down and play**:

* **no screen to play on.** The Play, Connect, Home and Settings screens are placeholders; the frontend has no
  test toolchain; the Talemate plugin is not written;
* **it has never met your models.** Every call has only ever been answered by the fake. Nobody knows yet whether
  your Writer and Clerk answer in the formats the game reads, how long a turn takes on your pair, or which calls
  are worth their thinking time;
* **seven tests are red** (the sessions browser and a world that names no run);
* **no one-click start** on your Windows desktop.

Three days fix exactly those four things, in that order of risk, and nothing else.

## 1. Done means this (the owner's acceptance run)

On your Windows desktop, with LM Studio running and LM Link on:

1. `install-game.bat` once. It finishes with "Installed." No Talemate install, no torch, no TTS.
2. `python tools\as\tune.py` once (overnight). It finds each model's thinking switch, measures your machines, plays
   the game's own calls on both models and writes the settings into `as_config.yaml`.
3. `play.bat`. A browser tab opens at `http://127.0.0.1:5050`. Connect shows both models by name, each **Test**
   passes.
4. **New life**: the wizard, then the world is built with the loading bar moving and the time left shown.
5. **Play 20 turns** with Act, Say and Cheat: the story is the Writer's prose; people answer what you say and do,
   in their own voices, and remember it (insult someone, then talk to them again); Stop ends a turn that runs
   long; Ask answers without passing time; the Where, Body, People, Pack and Journal tabs match the story.
6. Close the browser and `play.bat` again: **Your lives** lists the life; Continue picks it up at the same moment.
7. **Die** (walk into the dead): the Doom, the death screen, Willis's roast. Back to Home; start another life.
8. The whole time nothing in the game connected anywhere but LM Studio (the seal's refusal list in
   `as_runs/logs/seal.log` is empty or lists only what it blocked).
9. A turn takes about what `tune.py` said it would.

If 1–9 hold, the release is done. Everything else is a supplemental update (§3).

## 2. What ships

| # | Feature | State today | Work in the three days |
|---|---|---|---|
| 1 | **Sealed and private** | built (SEAL-01..05) | the new server installs the seal before it opens a port, listens on 127.0.0.1 only, and logs refusals |
| 2 | **Your two models** — Writer (A) and Clerk (B) through one LM Studio over LM Link | built (lanes, probe, limits bench) | `fit.py` (quality per call, critical path), `tune.py` (one command: probe → bench → fit → write settings) |
| 3 | **Connect** — pick the Main and Second model from LM Studio's one list, Test each | protocol built (P8 steps 1–3) | the screen |
| 4 | **New life** — wizard, worldgen, loading bar | built, screens built (P10) | wire into the real app; end-to-end test |
| 5 | **Play** — the story, Act / Say / Cheat, people who react and remember, Stop, Ask, turn progress, the side tabs | engine built; screen a placeholder | the Play screen and its panels, to the protected specs |
| 6 | **Your lives** — save, continue, delete | protocol mostly built; 5 tests red | finish RUN-12 / RUN-13 (the red tests); the screen |
| 7 | **Death** — the Doom, the death screen, Willis | built, screens built (P12) | wire in; end-to-end test |
| 8 | **Cheats** — the console, plain-words cheats, codes, Willis | built (engine, cheat assist) | the Cheat field inside the Play screen |
| 9 | **Settings** — what you can change mid-life: turn depth, how long, which person and tense the story is told in, your character's voice (exact or my way), intensity, the dice receipt, the Wild Card | protocol built | the dialog |
| 10 | **One-click start on Windows** | none | `install-game.bat`, `play.bat` (and `.sh` twins, tested here) |

## 3. What waits (supplemental updates, in this order)

1. Anything the owner's acceptance run turns up that is not a blocker.
2. The full model benchmark: `fit.py` over every call class (the release measures the turn's own path only).
3. The owner's lore, ready when you are: the Willis card update, the Lurkers, Addison's canon story, the Codex.
4. The gaps found in play-testing on the fake model: an insult is shown to the hearer as "a statement"; people
   who love someone kissed against their will have no rule for it; generated worlds have no barricades. (The
   first goes in on Day 3 if there is time: §5, block 3.7.)
5. The Talemate plugin and patches (02 §4.1, §6), so the Workshop can sit beside the game; Read aloud (local TTS).
6. Worlds: list, export, import, a new life in the same world after a death (RUN-07, P12 step 4).
7. Migrations (P12 step 5).
8. The Content screen's imports (character cards, documents, dossier intake) and the developer panel beyond what
   its spec pins.

## 4. The one change of course: the game serves itself

02 §1 hosts the game inside Talemate's backend. For this release the game gets its **own small server**
(`as_engine/service/serve.py`, `as-engine serve`), and the Talemate route waits (§3 item 5). Why:

* **Install.** Talemate's backend pulls torch, ChromaDB, four TTS stacks and seven cloud SDKs (gigabytes, CUDA
  wheels). The game needs none of them. Its own server needs one small library (`websockets`) on top of the
  engine's four.
* **Privacy.** Seven cloud clients that are never used are seven things the seal has to stop. A process that
  never imports them has nothing to stop.
* **Risk.** One process, one port, one protocol the engine already speaks and tests. Talemate's frontend
  server, its one-tab rule and its startup are no longer on the critical path.

What stays the same: the Play UI is built in `talemate_frontend/src/play/` against its protected specs; the wire
protocol is exactly 10 §3's (`{type: "as_game", action, …}` over `ws://…:5050/ws`, one tab at a time), so the
Talemate plugin of 02 §6 still drops in later unchanged. The browser loads the Play UI as static files the server
serves from `as_engine/src/as_engine/service/ui/`, built by `tools/as/build_ui.py` from a play-only Vite entry and
committed, so your machine needs no Node. A test fails when the committed build is older than its sources.

## 5. The plan, block by block

Each block ends with its **exit check**; a block is not done until its check passes. Hours are working hours of
non-stop work; about a quarter of each day is kept as slack and is spent on whatever the checks turn up.

### Day 1 — green, measured, served (hours 0–24)

| Block | Hours | Work | Exit check |
|---|---|---|---|
| 1.1 | 0–1 | Fresh environment (engine venv, frontend `pnpm install`); the full suite as a baseline | 2681 / 2688 as recorded |
| 1.2 | 1–4 | **The seven red tests.** RUN-12 / RUN-13 in `_impl_runs.py` (`wipe_tree`, `delete_run`, `list_runs`' `final`) and `on_run_delete`; `Store.backup_to(…, as_world=)` and worldgen's GENESIS step (D-76) | the suite: 2688 / 2688 |
| 1.3 | 4–11 | **`tools/as/fit.py`, the turn's own path.** Plays the game's real calls (captured from scripted scenes on the fake: an insult, a question, a kiss unwanted and welcome, a shove, a shooting seen, the room after a crash) on your models: intake, WARM and HOT decisions, reactions (HOT and WARM), narration, the lint judge. Each as set, with thinking flipped, and the HOT calls on the other lane too. Graded by code: parsed; the intake picked the right option (gold answers); a person spoken to answers; no name they cannot know; no refusal or out-of-story talk; the narration passes the game's own lint. Then a **turn-time table** for three profiles — Quality (as set), Balanced, Fast — and `--accept quality|balanced|fast` writes the profile you pick. `--fake`, `--quick`, `--resume`; reports under `as_runs/reports/fit.md` | a contract test on the fake: the cases build, the grading separates a good answer from a bad one, a profile writes the settings it lists, nothing outside the configured lane URLs is touched |
| 1.4 | 11–12 | **`tools/as/tune.py`**: probe `--write`, then `bench.py --quick --accept`, then `fit.py --quick`, printing the profile table and the command that accepts one | runs end to end on `--fake` |
| 1.5 | 12–17 | **`as-engine serve`.** `websockets` server on 127.0.0.1:5050: `/ws` speaks 10 §3's protocol to `GameService` (one tab at a time, pushes to the open tab, a reload reconnects to the running game), every other path serves the built Play UI; the seal installed before the port opens, refusals logged; `--fake` for tests | contract tests through the server's handler with an in-memory connection (no sockets): hello round-trips, a second tab gets the other-tab message, a turn's pushes arrive, the seal is on |
| 1.6 | 17–19 | **Owner checkpoint 1 package**: `install-game.sh` / `.bat`, `play.sh` / `.bat` (`play` opens the browser), README_FIRST's "Play it" section rewritten for this path | the `.sh` pair, run in a clean folder here, ends with the server answering on 5050 |
| 1.7 | 19–24 | Slack; then the records (DECISIONS, CHANGELOG, 12_TESTING, PROGRESS, the references and the manifest); push | gate `--docstrings` OK, the source scan clean, pushed |

**Owner checkpoint 1** (end of Day 1, §6): pull, `install-game.bat`, `python tools\as\tune.py` overnight, and three
turns in the terminal (`as-engine play`).

### Day 2 — the Play UI (hours 24–48)

All screens are built to the protected vitest specs and 10_UI; the order is the order a player meets them, so an
early stop still leaves a playable game.

| Block | Hours | Work | Exit check |
|---|---|---|---|
| 2.1 | 24–26 | Toolchain (02 §4.1): vitest, @vue/test-utils, jsdom, `test:play`, the vite `test` block, the lockfile; `App.vue`; the play-only Vite entry and `tools/as/build_ui.py` | the P10 / P12 specs that pass today still pass under the new toolchain |
| 2.2 | 26–29 | `words.js`, `socket.js`, `store.js` | `words`, `socket`, `store` specs |
| 2.3 | 29–32 | `PlayApp.vue`, Connect, Home, **Your lives** | `app`, `connect_home`, `sessions` specs |
| 2.4 | 32–39 | **The Play screen**: the top bar, Where, the story, a turn in progress and Stop, the rejection banner, the input box (Act / Say with person chips / Cheat with suggestions and dictionary / Ask), the suggestion chips, a dead character's input; the tabs: Pack, Body, People, Journal, Map | `play`, `panels`, `cheat_assist` specs |
| 2.5 | 39–41 | Settings dialog; the developer panel only as far as its spec; `ContentScreen` only as far as its spec (the validator) | `settings_dev`, `clarity`, `workshop` specs; **every** Play UI spec green |
| 2.6 | 41–46 | **End to end in a real browser** (Chromium, here): `as-engine serve --fake`, then a script: Connect → New life → worldgen → 10 turns with Act, Say, Cheat, Stop and Ask → reload mid-life → Continue → die → the death screen → Home. Fix what breaks | the script passes twice in a row from a clean `as_runs/` |
| 2.7 | 46–48 | Build and commit `service/ui/`; records; push | the freshness test green; pushed |

**Owner checkpoint 2** (end of Day 2): pull, `play.bat`, a life on your models for as long as you like; send what
went wrong (§6).

### Day 3 — your models, hardened (hours 48–72)

| Block | Hours | Work | Exit check |
|---|---|---|---|
| 3.1 | 48–54 | **What checkpoints 1 and 2 found.** Every call that failed to parse, every prompt your models misread, every stall, every slow call: a fix with a test that fails without it | the fake-model test for each, and `fit.py --fake` on the changed prompts |
| 3.2 | 54–57 | The defaults in `as_config.example.yaml` and `contracts/settings.default_regimes` set from your measurements, so a fresh install starts where `tune.py` would put it | the settings tests; `tune.py --fake` shows nothing left to change |
| 3.3 | 57–61 | **The long run**: 100 turns through the server on the fake, with a reconnect every 10 turns, Stop mid-turn, save and load mid-life, the quiet hours, a death; then the 100-day world soak per difficulty (BENCH-06) | no crash, no lost turn, replay says "all the same" |
| 3.4 | 61–64 | Gates: `gate.py --phase 0` … `--phase 11` recorded one by one (P8's row says the plugin test waits for §3 item 5) | each row written by the gate |
| 3.5 | 64–66 | The Windows scripts read line by line against the tested `.sh` pair; README_FIRST and the Play UI smoke checklist rewritten for the release path | — |
| 3.6 | 66–68 | Records, references, manifest; push | pushed, clean |
| 3.7 | 68–72 | Slack. If unused: an insult reaches the hearer as an insult, not "a statement" (§3 item 4), with its test | — |

## 6. Owner checkpoints

Your machines are the only place the real models are, so three things only you can do. The plan does not wait on
them: if a checkpoint does not happen, the next day's work goes ahead on the fake, and what your models would have
shown becomes the first supplemental update.

**Checkpoint 1 (end of Day 1, takes you 10 minutes plus a night):**
```
git pull
install-game.bat
python tools\as\tune.py            (leave it overnight; it prints a table at the end)
as-engine new-run core:pc/owen_marsh --detail gotta_go_to_work_soon
as-engine play <the run id it printed>      (three moves, then quit)
```
Send back: `as_runs\reports\fit.md`, `bench.md`, `probe.json`, and anything the terminal printed that looked
wrong. These hold game text and your model names, nothing else; they are yours to send or not.

**Checkpoint 2 (end of Day 2):** `git pull`, `play.bat`, play. Send: what broke, what was slow, what read wrong,
and `as_runs\logs\` if a turn failed.

**Checkpoint 3 (after Day 3):** the acceptance run of §1.

## 7. Risks

| Risk | What happens | Fallback |
|---|---|---|
| A model does not answer in the shapes the game reads | its calls fail; people hold still; the story is told plainly | the fallbacks are built (repair, hold, plain narration), so the game still plays; `fit.md` shows which calls, and Day 3 fixes them |
| Turns are too slow on your pair | minutes per move | `tune.py` measures it and offers Balanced and Fast; turn depth Quick in Settings; Stop always works |
| No working thinking switch for a model | it always or never thinks | the probe reports it; the profile accounts for it |
| The Windows scripts fail on your machine | no one-click start | `as-engine serve` and `as-engine play` from a prompt do the same thing; checkpoint 1 finds it on Day 1, not Day 3 |
| The Play UI is not finished by hour 48 | fewer screens | the order of Day 2 leaves Connect, Home, Play and Your lives first; the terminal plays the same game |
| A protected test turns out wrong | it stays red | an entry in SPEC_ISSUES.md (AGENTS.md §2.2); it does not block the release unless it is a real fault |
| No checkpoint report | real-model faults stay unknown | Day 3 hardens on the fake and `fit.py --fake`; your first report becomes supplemental update 1 |

## 8. How the release is checked

* The engine suite: every test green (2688 and the new ones).
* The Play UI: every vitest spec green.
* `gate.py --phase 0..11` rows recorded; `gate.py --docstrings` OK; the source scan clean; `protect.py --verify`
  clean (its one expected problem aside: `.claude/settings.json` is never committed).
* The browser script of block 2.6 and the long run of block 3.3 pass.
* The acceptance run of §1, by you.
