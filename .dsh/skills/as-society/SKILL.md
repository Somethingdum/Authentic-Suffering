---
name: as-society
description: P9 only - the settlement (society/*, world/rumours.py), its timers and cascade chains, and how to debug them.
whenToUse: Working on P9 (society/*, world/rumours.py, mind/mind group standing, the P9 parts of turn/timers.py, turn/select.py, turn/pipeline.py, action/cascade.py).
disable-model-invocation: false
---

# Society (P9)

- Read `docs/as/06_WORLD.md` §2 and §6 for the picture, then the module docstrings: they are the
  contract, number by number. Every number comes from `RulesConfig().society` (`SocietyRules`),
  never from a literal.
- Nothing in `society/` ticks by itself. A settlement lives on `event_queue` rows (SETTLEMENT_DAY,
  PRODUCTION_CYCLE, GROUP_DAY, ROUTINE_STEP) that `turn.timers.seed_society` starts once and
  `turn.timers.fire_one` dispatches, then sweeps the handler's events through `action.cascade`.
  Build `turn/timers.py` early (13 P9 step 4): the tests' `run(w, hours)` is `run_offscreen`.
- A consequence between two society events is **content** (`as_content/packs/core/cascade/
  economy.yaml`, `people.yaml`), not code. If a chain does not fire, find the rule (CAS-001 …
  CAS-018), then check in this order: the trigger's `where` against the event's payload, the
  preconditions (`cascade.evaluate_precondition`), the selector (`cascade.select` returning `[]`
  makes the effect a silent no-op, CAS-07), the dispatch line.
- Walk a chain backwards with `society_kit.cause_chain(w, event_id)` or
  `kernel.events.cause_chain`: every hop must name its cause, and every cascade event its rule
  (`rule_cited`). A scheduled effect (`~>` in 06 §2.4) arrives as a CASCADE_EFFECT timer and
  starts again at cascade depth 0.
- Order matters for determinism (DET-01, `test_det_01_*`): iterate members, pairs, households and
  queue rows in the sorted orders the docstrings give, and draw rng from stream `society` with the
  exact keys given (`friction:{x}:{y}`, `bond:{x}:{y}`, `home:{x}:{y}`).
- Code never acts for a human-controlled body: no routine, cover, drift pair, loyalty check or
  animosity roll for the PC (SEL-06). The PC is still counted and fed at the draw.
- Background rows (`kernel.clock.BACKGROUND_QUEUE_TYPES`) never end a condition-ended window
  (HOR-01); a P7 scenario (no settlement) must behave exactly as before — run `p07_slice` and the
  sim soak after touching `turn/`.
- `test_econ_chain.py` is the proof: one injury, nothing else scripted. If it fails while every
  other P9 test passes, the pieces disagree about a number or an order; read the failing hop's
  docstring again rather than special-casing the test.
