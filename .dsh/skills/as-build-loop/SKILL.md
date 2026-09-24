---
name: as-build-loop
description: The step-by-step loop for implementing one Authentic Suffering engine function against its contract test.
whenToUse: Starting or continuing any phase task in as_engine (P0-P12), or when unsure what to do next.
---

# The build loop (one function at a time)

1. **Find the task.** `docs/as/PROGRESS.md` → *Next task*, e.g. `P5 task 4 — action/effects.py::land`.
2. **Find the failing test that exercises it.**
   `python tools/as/gate.py --phase 5 --quick` lists each failure as the test id, then
   `rules: … · at <file:line>`, then the error. `at as_engine/...` is where it failed in `src`.
   Prefer the test whose error is `NotImplementedError: P5` at the function you are on; an error
   from an EARLIER phase (`NotImplementedError: P2`) means that phase is not finished.
3. **Read, in this order, and nothing else:**
   - the test function (and any helper it calls in `as_engine/tests/helpers.py`);
   - the docstring of the function under test;
   - the module docstring (rules, event shapes, wording) — search it for the names the test uses.
   Worked numbers in test comments ("3.20 m; 1 s + 1.0 s/m -> 4.2 s") show the arithmetic the
   docstring asks for. Reproduce the arithmetic; never paste the number.
4. **Write the smallest correct implementation.** Use the owner's API for every write
   (`space.move_event`, `objects.transfer`, `bodies.apply_harm`, …). Use implemented helpers
   (`with_article`, `thing_phrase`, `duration_words`, `land_ms`, `attr_mod`, …).
5. **Run the one file**: `cd as_engine && python -m pytest tests/contract/p05_many_actors/test_effects.py -q`.
   Then `-k <name>` for the single test while iterating.
6. **Green file → run the whole phase**, then every earlier phase: `python -m pytest tests/contract -q -x`.
   A red earlier phase is fixed before anything new.
7. **Record**: when a task is done, update *Next task* in `PROGRESS.md` (exact module::function).

## Habits that save hours

- Deterministic order: `ORDER BY` a stable key (id, then time) in every query whose order matters.
- Ids come from `tx.mint(kind)` only. Times are integer milliseconds (`land_ms` rounds up).
- JSON columns hold canonical JSON (`kernel/jsoncanon.canonical_json`); read them back with `json.loads`.
- An event you build but do not commit changes nothing (`move_event` builds; the caller commits).
- Payload keys are exactly those in the docstring — tests compare whole payload dicts.
- Words shown to minds or the player come from docstring templates; spell them exactly.
- If you need a value the docstring does not define, stop: that is a spec issue, not a guess.
