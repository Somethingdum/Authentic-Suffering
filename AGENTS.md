# Authentic Suffering — builder rules

You are building **Authentic Suffering (AS)**: a survival RPG whose engine is the pure-Python
package `as_engine/` (a fork of Talemate 0.39.0 hosts the UI). You work inside **DeepSeek Harness
(DSH)** on local LM Studio models. This file is always loaded; keep your own notes out of it.

The specification is complete. Your job is to make it true, one function at a time, until each
phase's contract tests pass. You do not design; you implement what the docstrings and tests say.

## 1. Every session, in this order

1. `python tools/as/doctor.py` — fix red items that belong to a finished phase first.
2. Read `docs/as/PROGRESS.md`: the current phase and the **Next task** line.
3. Read that phase in `docs/as/13_BUILD_ORDER.md` §4 (only that phase).
4. `python tools/as/gate.py --phase N --quick` — runs this phase's contract tests and prints the
   first failures, each with its rule ids and the source file:line where it failed.
5. Pick ONE failing test. Read the docstring of the function it calls (the module docstring and
   the function docstring are the contract) and the test body. Implement that one function.
6. Re-run only that test file: `cd as_engine && python -m pytest tests/contract/<phase dir>/<file> -q`.
7. Repeat 5–6. When the phase directory is green, run `python tools/as/gate.py --phase N` (full:
   all earlier phases too, protection, anti-cheat scan) — it writes the evidence row.
8. Before you stop: set **Next task** in `docs/as/PROGRESS.md` to the exact next function.

## 2. Hard rules (breaking one fails the phase whatever the tests say)

1. **Protected files are never edited, moved, deleted, skipped or weakened**: the tests
   (`as_engine/tests/contract/`, `fixtures/`, `sim/`, `live/`, `conftest.py`, `helpers.py`, the UI
   specs in `talemate_frontend/src/play/__tests__/`, `tests/test_as_game_plugin.py`), `testing/fake_lm.py`,
   `kernel/jsoncanon.py`, the IMPLEMENTED rng core in `kernel/rng.py`, `content/safety.py`, `docs/as/*`
   (except `PROGRESS.md` and `SPEC_ISSUES.md`), `AGENTS.md`, `.dsh/`, and `tools/as/{protect,gate,doctor}.py`.
   `python tools/as/protect.py --list` prints them all; `--verify` checks their hashes. A hook blocks
   tool calls that would write them (the message starts `BLOCKED:`) — that is not an error to work
   around. No `skip`, no `xfail`, no deleting a test. Undo an accidental change with `git restore <path>`.
2. **If a test and a docstring disagree, or a test looks wrong**: do not "fix" either. Add an entry
   to `docs/as/SPEC_ISSUES.md` (skill `as-spec-issue`), leave that test red, move to the next task.
3. **No gaming the tests**: no fixture names or literal ids (`metal_fence`, `act_000003`) inside
   `src/`, no `import pytest` inside `src/`, no returning canned values for a test's inputs, no
   special cases that exist only for a test. `gate.py` scans for these.
4. **Determinism**: no `random`, `secrets`, `uuid`, `time`, `datetime.now`, `os.urandom` anywhere in
   `as_engine/src/` (lanes/ may time HTTP calls). All chance goes through `kernel/rng.Rng` with a
   stream and a purpose. Iterate in a defined order (sorted ids) whenever order can change a result.
5. **The store is the only writer**: world tables change only through `Tx.commit_event(Event)`
   whose `writer` owns every table it writes (`kernel/ownership.py`); bookkeeping tables through
   `tx.bookkeep`. Never write SQL `INSERT/UPDATE/DELETE` outside `kernel/store.py`.
6. **Skull Law**: modules listed in `tests/contract/p00_substrate/test_boundaries.py`
   (`TRUTH_FORBIDDEN`) never import `kernel.truth`. A mind knows only its own percepts.
7. **Later phases stay stubs**: a function whose docstring says `P7` keeps
   `raise NotImplementedError("P7")` until P7. Do not build ahead, do not "prepare".
8. **No network** from `as_engine` except the configured LM Studio lane URLs. Tests never touch the
   network (except `tests/live/`, which runs only with `AS_LIVE=1`).
9. **Talemate upstream**: change only the files listed in `docs/as/02_ARCHITECTURE.md` §4.1.
10. Keep every function in the module that owns it — or in that module's own `_impl_*.py` file, which
    it binds at its end (§4). If a behaviour has no owner, file a spec issue.

## 3. Commands

```
python tools/as/setup.py                      # once: venv packages, editable install, config copy
python tools/as/doctor.py                     # environment + protection + progress check
python tools/as/gate.py --phase 5 --quick     # this phase's tests, first failures
python tools/as/gate.py --phase 5             # the full gate (writes evidence to PROGRESS.md)
cd as_engine && python -m pytest tests/contract/p05_many_actors/test_effects.py -q
cd as_engine && python -m pytest tests/contract/p05_many_actors -q -k climbing
cd as_engine && python -m pytest tests/contract -q -x   # everything so far, stop at first failure
```
On Windows use the venv's `python` the same way; paths use `/` in these files.
Hooks you will see: at session start a brief (phase, Next task); before each tool call a protection
check; when you stop, a check that **Next task** is filled and protected files are intact.

## 4. Where things are

- `docs/as/13_BUILD_ORDER.md` — phases, task order, gates, forbidden work.
- `as_engine/src/as_engine/<package>/<module>.py` — each docstring is the contract for that module.
- `as_engine/src/as_engine/**/_impl_*.py` — the bodies of functions that are already built (P0–P10
  and everything added since; 13_BUILD_ORDER §4.0 says what is still yours).
  A module whose functions are built ends with lines like `from ._impl_packet import build_packet  # noqa`:
  those names are bound to the bodies in that `_impl_` file, and a fix to one goes there (the contract
  module's docstrings and signatures stay as they are). Import the owning module, never an `_impl_`
  file. Some modules are built in place (their functions simply have bodies). A function that still
  raises `NotImplementedError("P<n>")` and is not bound at the end is yours to write, in the owning
  module. 13_BUILD_ORDER §4.0 says where this copy starts.
  Never change a docstring or a documented signature: `python tools/as/gate.py --docstrings` compares
  them with the kit's snapshot (`docs/as/reference/docstrings_v1.json`) and the full gate fails on drift.
- `as_engine/tests/contract/pNN_*/` — the executable spec for phase NN.
- `as_engine/tests/helpers.py` — test helpers (read it to understand a test; never edit it).
- `as_engine/tests/fixtures/scenarios/*.yaml` — the worlds tests load (`metal_fence` is the main one).
- `as_content/packs/core/` — game content (items, affordances, actors, cues, cascade rules).
- `docs/as/RULES.md` — every rule id and where it is enforced and tested.
- `docs/as/GLOSSARY.md` — one spelling per concept. Use these names in code.

## 5. Working well with a small context

- Read the smallest thing that answers your question: the failing test, then the function's
  docstring, then the module docstring. Do not read whole documents "for background".
- One function per edit; run its test file after every edit.
- When a test fails, read the assertion message first — most say what was expected and why.
- Three honest attempts at one test with no progress: write down what you tried in
  `docs/as/SPEC_ISSUES.md` only if you believe the spec is wrong; otherwise note it under
  "Stuck" in `PROGRESS.md` and take the next task. Never loop on one test for a whole session.
- Implemented helpers exist (`with_article`, `at_phrase`, `duration_words`, `land_ms`,
  `range_band`, `effective_form`, `attr_mod`, `format_clock`, …). Use them; do not re-write them.

## 6. Skills (load on demand from `.dsh/skills/`)

`as-build-loop` (the task loop in detail) · `as-failing-test` (triage) · `as-spec-issue` (how to
report) · `as-store-events` (events, ownership, replay) · `as-content` (content packs and CNT
codes) · `as-phase-gate` (gate report, evidence, PROGRESS.md) · `as-play-ui` (P8 only) ·
`as-society` (P9 only) · `as-world` (P10 only).

## 7. The human

The human reads `docs/as/SPEC_ISSUES.md` and `docs/as/PROGRESS.md`. Approved contract changes are
written by the human into `docs/as/CHANGELOG_AS.md`; you then apply exactly those changes.
