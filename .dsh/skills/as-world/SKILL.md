---
name: as-world
description: P10 only - the wide world (worldgen, the dead and the hordes, the world's day, the Ghosts, the quiet hours, the loading bar) and how to debug it.
whenToUse: Working on P10 (world/*, world/worldgen/*, service/background.py, service/progress.py, service/runs.create_run, the P10 GameService handlers and cli new-run, and the P10 lines of earlier modules).
disable-model-invocation: false
---

# The wide world (P10)

- Read `docs/as/06_WORLD.md` for the picture, then the module docstrings: they are the contract,
  number by number. Numbers come from `RulesConfig()` (`world`, `infected`, `hordes`,
  `background`, `decay`), never from a literal. Follow 13_BUILD_ORDER §4 P10 steps 0-13 in order.
- Most P10 tests use one generated world: `p10_world/conftest.py` builds it once per session
  through `service.runs.create_run`. Until the whole worldgen chain works (13 P10 step 6), every
  test that takes `gw` errors in setup. That is expected: work through the tests that do not
  need it first (params, placement, region, traces, and the infected and door tests on the
  `metal_fence` scenario).
- Worldgen is code; the model only writes words. Every model call has a code fallback, so the
  fake model's default answers must still give a whole world (`test_with_the_models_down_...`).
  Call every stage function through its module (`region.build_region`, not a name imported into
  `pipeline.py`): the tests replace one to make a stage fail.
- Determinism (WG-DET-01): draw from the named stream with the exact purpose string the
  docstring gives (`kind:{i}`, `kind:{i}:again`, `rise:{cause}:{zone}`, ...) and iterate in the
  sorted orders it gives. `vectors/params.json` and `region.json` name the first wrong draw; read
  that draw's line in the docstring rather than adjusting the order until it matches.
- The dead are counted (LOD, HRD-15): a body you meet was taken from a district's pool
  (`hordes.change`) and goes back to one; a crowd on the road is the same dead walking. The
  census total changes only when the dead rise or a body is destroyed. Never make an infected
  body from nothing, never drop one without giving it back to a count. Named people come from a
  cohort the same way (`population.take_from_cohort`, CONSERVE-04).
- Detail follows the player: a crowd shows as bodies only where the player is (HRD-07 `promote`),
  and a body walking with its crowd out of contact folds back into it at its next step (HRD-18
  `fold`, which `world.infected.step` calls first; D-67). A body with somewhere of its own to be
  (hunting, drawn by a noise) never folds: it has to arrive. A loud noise holds its neighbourhood in the active
  area for 10 minutes of world time, not for the rest of the turn (SEL-01 `LOUD_MEMORY_MS`,
  D-68). If a long off-screen run gets slow, count the events per hour (MATERIALIZE, MOVE,
  TIMER_FIRED) before guessing: a count that keeps growing means bodies are being made and never
  folded.
- Speed: `world.infected.sees` runs for every body at every step, and `turn.select.active_area`
  for every horde and body step. Read their time windows with one range query on the `ev_at`
  index (`at > ? AND at <= ?`; in SQLite add `INDEXED BY ev_at` when the planner would rather use
  `ev_type` or `ev_turn`, which grow with the whole log), never by scanning the log. The slowest
  P10 tests (the Depot gate, the Mega Horde passing) take 20-40 s on the reference; the limit is
  120 s a test (pytest-timeout).
- Nothing ticks by itself. A generated world lives on `event_queue` rows (WORLD_DAY,
  OPERATION_STEP, INFECTED_STEP, REANIMATION, HORDE_STEP, POOL_RISE, COUNCIL) that
  `turn.timers.seed_world` starts once and `fire_one` dispatches. They are background rows: they
  never end a watch (HOR-01); what they cause reaches the player only through what the PC
  perceives. The tests' `world_kit.run(s, hours)` is `run_offscreen`.
- A run without a `world_params` row (every hand-made scenario) must run exactly as before: run
  `p07_slice`, `p09_society` and the sim soak after touching `turn/`, `action/`, `physical/`.
- Fidelity rules the tests pin: nobody dies of a roll (C01: deaths come from wounds, thirst, what
  an outing meets, raids, the infected); nothing is deleted for being unimportant (C02: things
  wear, minds forget by retrieval); every mark comes from something that happened (C11). Code
  never acts for the PC: no outing, no routine, no compulsion (the PC feels the wet strain's
  pull; the player decides).
- The quiet hours (`service/background.py`): the job list is a pure read of the world as the
  turn left it (BG-02); each job commits in its own transaction between turns; the next turn
  awaits `catch_up` first (BG-07). Replay re-commits the recorded answers without a model call
  (BG-05).
- The loading bar (`service/progress.py`): no `time` import (DET-11): with `clock=None` read the
  running asyncio loop's `time()`. The percentage never drops; a turn never sends counts; the
  detail only in developer mode. Which quip shows is the UI's (`quips.js`), never the engine's.
- The P10 UI work follows `as-play-ui` (test ids in 10 §2.3, §2.4, §2.10; words from `words.js`).
