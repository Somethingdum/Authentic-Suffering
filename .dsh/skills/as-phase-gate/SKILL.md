---
name: as-phase-gate
description: Running tools/as/gate.py, reading its report, and recording phase evidence in PROGRESS.md.
whenToUse: A phase's contract tests look green, or before ending a session.
---

# The phase gate

`python tools/as/gate.py --phase N` does, in order:
1. `protect.py --verify` — every protected file matches `tools/as/protected_manifest.json`, and
   the hook files still call the hooks.
2. Contract tests for P0..PN (`as_engine/tests/contract/p00_*` … `pNN_*`), all must pass.
3. The anti-cheat scan over `as_engine/src/` (fixture names, literal fixture ids, `import pytest`,
   forbidden entropy and clock imports).
4. Contract docstrings: every documented function, class and module docstring (and documented
   signature) equals the kit's snapshot `docs/as/reference/docstrings_v1.json`
   (`gate.py --docstrings` shows the differences on their own).
5. From P7 the sim soak (`tests/sim -m slow`); from P8 the Talemate plugin test, the Play UI
   tests (`corepack pnpm run test:play`) and `--upstream-diff`.
6. On success it prints `GATE P<N>: GREEN`, writes the phase row in `docs/as/PROGRESS.md` (status
   **green**, commit hash if the folder is a git repo, the exact command, date, artifact path) and
   saves the full pytest output under `as_runs/gate/`.

A red gate prints `GATE P<N>: RED` and writes nothing. Each red step names what failed; fix those
in order (protection first — `git restore <path>` undoes an accidental change).

`--quick` runs only phase N's tests and prints the first failures; it writes nothing.
`--rules` lists rule ids a docstring or test names that `docs/as/RULES.md` does not know.
`--stop-check` (the Stop hook) checks protection and that *Next task* is filled.

Only `gate.py` may write **green**. Before the gate passes the only legal wording is
"observed implementation, not proven gate".
