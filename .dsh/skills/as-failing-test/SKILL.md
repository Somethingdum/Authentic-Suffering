---
name: as-failing-test
description: How to triage a failing Authentic Suffering contract test without editing it.
whenToUse: A contract test fails and the reason is not obvious from the assertion message.
---

# Triage a failing contract test

Never edit, skip or weaken the test. Work through these in order and stop at the first hit.

1. **Read the assertion message.** Most asserts carry a sentence ("not with you", "a click is never a
   shot"). The sentence names the rule you broke.
2. **NotImplementedError("P<n>")** — a stub you have not written yet. If `n` is a later phase, the
   test is calling through a function you implemented in a way that reaches later code: re-read
   your function's docstring; it never needs a later phase.
3. **KeyError / missing payload key** — compare your event payload with the docstring's payload
   shape key by key. Tests compare the whole dict.
4. **Off-by-one in time** — durations round UP to the next ms (`land_ms`); events carry the time
   they happen (`at`), not the time you computed them.
5. **Order differs** — sort by the documented key (ids are zero-padded, so string order is id order).
6. **Wrong words** — copy the template from the docstring; articles come from `with_article`,
   places from `place_phrase`, anchors from `at_phrase` / `to_phrase` / `thing_phrase`.
7. **Earlier phase regression** — run `python -m pytest tests/contract -q -x`; fix the earliest red.
8. **Randomness** — every draw goes through `rng` with the documented stream and purpose string;
   an extra or missing draw shifts every later value. Check `prng_ledger` in the failing store.
9. **Still stuck after three attempts** — note it in `PROGRESS.md` under Notes (what you tried),
   move on. If you believe the test or spec is wrong, use skill `as-spec-issue`.

Useful inspection inside a test run: `w.store.query("SELECT type, payload FROM events ORDER BY seq")`
and `w.local(real_id)` to turn internal ids back into fixture names.
