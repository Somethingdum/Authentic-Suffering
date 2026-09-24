---
name: as-spec-issue
description: How to report a suspected contradiction or error in the Authentic Suffering spec or a protected test.
whenToUse: A test and a docstring disagree, a required value is undefined, or a test seems impossible to satisfy honestly.
---

# Report a spec issue

1. Open `docs/as/SPEC_ISSUES.md`, copy the template under "How to file", take the next SI number.
2. Fill every line. Quote the spec with file and section. Quote the assertion with test path.
   Add evidence you can reproduce (command + output, or a tiny unit test under `as_engine/tests/unit/`).
3. Propose the smallest change that would make both agree. Do not apply it.
4. Under "Meanwhile" say which other task you are doing instead.
5. Leave the test red. Do not work around it in `src/` (no special case, no guessed constant).
6. Take the next task in the phase.

The human answers in `SPEC_ISSUES.md` and records approved contract changes in `CHANGELOG_AS.md`.
Apply exactly what `CHANGELOG_AS.md` says, nothing more.
