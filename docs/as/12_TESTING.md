# 12 — Testing

The tests are the executable form of this spec. When a doc and a contract test disagree, stop and
report it in `SPEC_ISSUES.md` (§9) — do not "fix" either side on your own.

## 1. Tiers

| Tier | Where | Who writes | Runs | Purpose |
|---|---|---|---|---|
| **Contract** | `as_engine/tests/contract/pNN_*/` | the spec (protected) | every gate, every session | the spec, executable |
| **Unit** | `as_engine/tests/unit/` | the builder | freely | your own finer-grained tests; add them generously |
| **Sim** | `as_engine/tests/sim/` | the spec (protected) | P7+ gates, `-m slow` | multi-turn soak runs with the fake model (50–200 turns) and their re-simulation (DET-02) |
| **UI** | `talemate_frontend/src/play/__tests__/` | the spec (protected) | P8+ gates | vitest + @vue/test-utils + jsdom: the store, the socket, the words and every P8 screen, fed protocol messages from `fixtures/*.json` (10 §7) |
| **Plugin** | `tests/test_as_game_plugin.py` (fork root) | the spec (protected) | P8 gate | the route is registered; replies and pushes reach the socket; `hello` round-trips through the real service |
| **Live** | `as_engine/tests/live/` | the spec | you, on your machines (`AS_LIVE=1`) | real models: probe, JSON compliance, latency, eval |

"Protected" means three things. (1) `tools/as/protected_manifest.json` holds a SHA-256 of every
protected file; `python tools/as/protect.py --verify` (run by every gate and by the doctor) fails on
any changed, missing or added file. (2) The harness PreToolUse hook (`protect.py --hook`, installed by
`tools/as/setup.py`) blocks tool calls that would write, move or delete a protected path. (3) The
kit's first commit is tagged `as-kit-baseline`, so `git diff as-kit-baseline` shows any drift.
Protected paths are listed in `tools/as/protect.py::PROTECTED`. Only the human changes a protected
file: after an approved `CHANGELOG_AS.md` entry, edit it, then run (in your own terminal, never
through the agent) `AS_MAINTAINER=1 python tools/as/protect.py --write-manifest`
(PowerShell: `$env:AS_MAINTAINER=1; python tools/as/protect.py --write-manifest`).

## 2. Commands (copy exactly)

```bash
# from the fork root, with the venv active
cd as_engine
python -m pytest tests/contract/p00_substrate -q          # one phase
python -m pytest tests/contract -q -m "phase(0) or phase(1)"   # (markers also work)
python -m pytest tests/unit -q                              # your tests
python -m pytest tests/sim -q -m slow                       # soak (P7+)
AS_LIVE=1 python -m pytest tests/live -q -m live            # live, on your machines only

cd ../talemate_frontend && corepack pnpm run test:play      # UI (P8+)
cd .. && python -m pytest tests/test_as_game_plugin.py -q -o addopts=""   # plugin (P8+; Talemate env)

python tools/as/gate.py --phase 3                           # the official gate for a phase
python tools/as/doctor.py                                   # environment + invariant self-check
```

A phase is only "green" when `tools/as/gate.py --phase N` prints `GATE P<N>: GREEN` and writes the
evidence row into `docs/as/PROGRESS.md` (13 §1).

## 3. Markers and conventions

- Every contract test module sets `pytestmark = pytest.mark.phase(N)`.
- Every contract test MODULE docstring names the rule ids it proves (`"""... Rules SKULL-01..06
  ..."""`); a test function names a rule in its own docstring when it proves that one rule
  specifically. `RULES.md` is generated from the kit (`gate.py --write-rules`, maintainer only) and
  lists, per id, its statement, the modules that name it and the contract tests that name it;
  `tools/as/gate.py --rules` reports any id a docstring or test names that the registry does not know.
- Async tests are plain `async def` (pytest-asyncio auto mode).
- Tests never sleep on wall-clock time and never touch the network (except `live/`).
- Tests read tunable numbers from `RulesConfig()` defaults, not literals — unless the test's purpose
  is to pin a default (those say so: `"""pins the default ..."""`).
- A test that needs a phase not yet built fails with `NotImplementedError("P<n>")` from the stub.
  That is expected before the phase and is how you know where you are.
- **Never** mark a protected test `skip`/`xfail`, never edit it, never weaken an assertion. If you
  believe it is wrong, §9.

### 3.1 The protocol tests (P8)

`p08_ui_protocol` tests `GameService` with no websocket: `svc.handle(message)` returns the replies,
and a subscriber collects the pushes (`svc.pushed`). Its `conftest.py` gives `GatedTransport`, the
fake model with a gate: a call of a class in `transport.hold` waits until `transport.release` is set,
so a test can act in the middle of a turn (Stop before stage 12, `too_late` after it, a reloaded page
reaching the running turn, busy answers). `protocol_kit.check` asserts every envelope (PROTO-01) and
every error message (PROTO-08); `svc.idle()` waits for the turn to finish. `test_ui_fixtures.py`
validates the vitest fixtures against `OUT_MODELS`.

### 3.2 The society tests (P9)

`p09_society` runs `pump_settlement` (day 1100, 05:00, everyone asleep, stores for 3.1 days — the
pump makes exactly what 24 people drink). Its `conftest.py` gives the `settle` fixture;
`society_kit.py` (protected) gives the helpers: `run(w, hours)` is the off-screen step
(`turn.timers.run_offscreen`), `injure(w, local, anatomy=, severity=, stitched_by=)` cuts an arm (a
HARM plus the suture that stops the bleeding, then the cascade sweep), `heal`, `rows(w, type)`
(committed events as dicts), `settlement`, `workplace`, `rel`, `cause_chain`, `now`, `hhmm`, `H`,
`DAY`. Most P9 tests need the off-screen step, so `turn/timers.py` comes early (13 §4 P9 step 4).
`test_econ_chain.py` is the proof that the pieces add up (ECON-01): it scripts nothing but the
injury. `test_timers_society.py::test_det_01_*` runs the same settlement twice and compares
every event and the world hash, so drift and animosity draws must come from the `society` rng
stream in the documented order.

## 4. Shared fixtures (`as_engine/tests/conftest.py`, protected)

| Fixture | Gives you |
|---|---|
| `rules` | `RulesConfig()` |
| `config` | `EngineConfig()` with default lanes |
| `store` | `Store.memory(run_id="t", seed=1, start_ms=0)` (closed after the test) |
| `rng` | `Rng(1)` |
| `fake` | a fresh `FakeTransport()` |
| `client` | `LaneClient(config, fake)` |
| `core_pack_dir` | `<repo>/as_content/packs/core` |
| `fixture_packs` | `as_engine/tests/fixtures/packs` |
| `canon` | `load_canon([core_pack_dir])` (P2+) — session-scoped |
| `scenario` | factory: `scenario("metal_fence")` → `ScenarioWorld` loaded from `tests/fixtures/scenarios/metal_fence.yaml` with `fake` as transport |
| `spec_of` | factory: `spec_of("metal_fence")` → validated `ScenarioSpec` (works before P2) |
| `vectors` | factory: `vectors("rng")` → parsed JSON from `tests/fixtures/vectors/rng.json` |
| `make_event` | helper building a minimal valid `Event` for kernel tests |

Helpers (`as_engine/tests/helpers.py`, protected; `import helpers`): `handle_for(packet, def_id,
target_local, world)` (the A-handle of an offered option), `option_defs(packet)`,
`percepts_of(store, holder, turn)`, `holdings_of(store, holder)`, `events_of(store, type, turn)`,
`ledger_draws(store, turn)`, `text_of_percepts(rows)`, `make_intent(world, actor, def_id, target,
destination, item, *, est_s, speech, manner)` (an Intent straight from a core def — P5+ tests drive
the resolver without the menu) and `ScriptedRng(*values)` (a stand-in rng returning scripted
values, for tests where a band must be fixed).

## 5. Scenario format

A scenario is one YAML file describing a small world exactly: places, portals, bodies, items,
relationships, beliefs, timers. The machine contract is `testing/scenario.py::ScenarioSpec`
(implemented — `parse_scenario(path)` validates a file today); the loader that writes it into a
store is P2 work (`load_scenario`, contract in the same module).

```yaml
schema: as.scenario.v1
name: metal_fence                    # file name without .yaml
description: Night at Delgado's — the P7 anchor scene (plan §5.4)
seed: 1818
start: {day: 18, time: "23:14:03"}  # world time; day 0 = the day of the Fall
weather: {kind: wind, wind_level: 2}
settings: {turn_depth: balanced}    # RunSettings fields (optional)
rules: {}                           # RulesConfig overrides, deep-merged (optional)
places:
  - id: sales_floor                 # fixture-local id (real ids are minted: plc_000001 ...)
    name: Sales floor
    kind: room
    width_m: 14
    depth_m: 9
    material: brick
    light: 1
    anchors:
      - {id: counter, name: counter, kind: cover, x: 6, y: 4, cover: 2, concealment: 2}
portals:
  - {id: storeroom_door, a: sales_floor, b: storeroom, kind: door, name: storeroom door,
     open: true, w: 90, h: 205, seal_db: 25}
  - {id: back_wall, a: storeroom, b: alley, kind: wall, name: back wall, w: 0, h: 0, seal_db: 45}
bodies:
  - id: pc
    dossier: core:pc/owen_marsh     # a pre-Fall adult, so day 18 fits him (WG-34)
    controller: human               # exactly one human
    place: sales_floor
    anchor: counter
    inventory:
      - {item: core:item/glock_19, slot: hand_r, label: glock, props: {chambered: true}}
      - {item: core:item/magazine_9mm_15, container: glock, props: {rounds: 14}}
  - id: june
    dossier: core:actor/june_okafor
    place: storeroom
    anchor: shelves
    task: {kind: count_stock, label: counting cans, steps_total: 60, steps_done: 41, step_s: 10,
           interrupt_on: [loud_noise, addressed_by_name]}
relationships:
  - {from: june, to: mara, kind: friend, trust: 2, affection: 1}
knows:                                # who knows whom by name (acquaintance rows)
  - {holder: pc, subject: mara, name: Mara}
beliefs:                              # seeded holdings, with provenance
  - {holder: nita, subject_type: place, subject: alley, predicate: status,
     text: "The alley was clear at eleven.", confidence: 2, provenance: witnessed}
households:
  - {id: voss, members: [{actor: mara, role: head, guardian_of: [eli]}, {actor: eli, role: child}]}
groups:
  - {id: crew, name: "Delgado's crew", members: [{actor: mara, role: guard}]}
events_due:                           # event_queue rows (types: kernel.clock.QUEUE_TYPES)
  - {at: "23:14:03", type: NOISE, place: alley, anchor: fence_sheet,
     payload: {source_db: 98, kind: metal_crash, text: "a loud metal crash"}}
```

Validation (already enforced by `ScenarioSpec`): duplicate ids, unknown references, exactly one
human body, walls/fences with aperture 0 and never open, loose items with exactly one location,
bodies with exactly one of `dossier`/`infected`, infected bodies controlled by `policy`.

Shipped scenarios (`tests/fixtures/scenarios/`):

| File | Used by | What it sets up |
|---|---|---|
| `metal_fence.yaml` | P3–P7, P11, sim | the anchor scene: store, storeroom, office, alley, street; PC, Mara, Alice, June, Eli, Nita, the stranger; the gust timer |
| `fence_climb.yaml` | P7 ("Actions fail") | a yard, a 250 cm fence (obstacle class 5), Owen at its foot, a neighbour (stub) watching from the porch; the seed fails the first check |
| `three_rooms_gunshot.yaml` | SKULL-01/04 | Room 1 (A with a pistol), Room 2 behind brick (B), Room 3 two walls away (C asleep) |
| `crowd_accusation.yaml` | CROWD-01..05 | one open hall, PC + 8 listeners at varied distances, one observer 25 m away |
| `request_firewall.yaml` | WILL-01..09, P7 refusal slice | Mara mid-task with Eli asleep nearby; a stranger; Mara's commander; a porch outside the open front door |
| `empty_gun.yaml` | INTENT-03, HALLUC-01 | Reggie with an unloaded pistol facing Carl (a stub debtor); a believed-but-gone crowbar |
| `pump_settlement.yaml` | P9 ECON-01, SOC-02, SOC-03 | a 24-person settlement (Pumpwell) with a water pump on two 12-hour shifts, a kitchen, a watch rota, twelve households with children and elders, laws, a quartermaster, and a feud (Jude and Amos) |
| `two_skills.yaml` | WILL-03 | two identical Actors differing only in skills and Resolve, same room, same items |

## 6. The fake model (`testing/fake_lm.py`, implemented, protected)

`FakeTransport` stands in for LM Studio. It never parses prompts: it reads the structured context
object on each request (`LMRequest.context`, `contracts/calls.py`). Default answers are
deterministic (keep doing your task / wait / observe; narration = the packet's lines joined).
Script exactly what a test needs:

```python
fake.script(CallClass.ACTOR_COGNITION, actor_id=w.id("mara"),
            response=lambda req: {"choice": handle_for(req.context, "move_to_anchor", "rear_cover"),
                                  "speech": {"text": "Quiet.", "to": ["everyone"], "volume": "normal"},
                                  "goal": "cover the back", "private_reason": "That was the fence."})
fake.fail(CallClass.WRITEBACK, "schema_fail", times=1)    # grammar_fail | schema_fail | empty | timeout | lane_error
fake.down(Lane.B)                                          # the laptop is off
assert len(fake.calls(CallClass.NARRATION)) == 1
```

`tests/helpers.py` (protected) provides `handle_for(packet, def_id, target_local=None, world=None)`
to find the A-handle of an option in a packet, `percepts_of(store, holder_id, turn)`,
`holdings_of(store, holder_id)`, `events_of(store, type, turn=None)` and `ledger_draws(store, turn)`.

## 7. Determinism and golden vectors

- `tests/fixtures/vectors/rng.json`: seeds, streams and the first draws of `Rng` (the core
  generator is implemented; the vectors were produced from it and checked against the reference
  xoshiro256** algorithm).
- `tests/fixtures/vectors/jsoncanon.json`: inputs and exact canonical strings.
- `tests/fixtures/vectors/acoustics.json`, `checks.json`, `optics.json`, `params.json`: hand-computed
  expected values for the pure formulas (each entry shows its arithmetic in a `why` field).
- **DET-01** event-apply replay and **DET-02** re-simulation replay are contract tests in P0 and P7.
  DET-02 is `tests/sim/test_soak_metal_fence.py`: fifty turns, then `service.replay.resimulate`
  plays every recorded input again from the run's `turn0.sqlite` with the recorded model answers
  (`lanes.calllog.ReplayTransport`, found by request hash) and compares `full_state_hash` per turn.
- P7 whole-turn tests use `tests/contract/p07_slice/slice_kit.py` (protected): `play(session, mode,
  text, **kw)` runs one turn synchronously; `pick(w, request, def_id, target=, dest=)` finds an
  option in the packet the fake was given (a script can only choose what that mind was offered);
  `script_night_at_delgados(w, fake)` is the anchor turn's answers; the `metal_turn` fixture
  (`p07_slice/conftest.py`) plays it.

## 8. The 58-bit fault-injection test (AUDIT-02, P11)

`tests/contract/p11_audits/test_commit_gate_bits.py` builds the metal-fence world after one clean
committed turn, asserts all 58 bits are 1, then for each bit applies exactly one fault from
`FAULTS[bit_id]` (a function that corrupts the store the way that bit's description says — e.g.
`W08`: set a portal to open and barricaded) inside a savepoint, recomputes the gate and asserts that
**exactly that bit** dropped and no other, then rolls the fault back. A bit whose fault does not
drop it, or drops a different bit, fails the test. A check that cannot fail is not a check.

## 9. When you think a test or the spec is wrong

1. Re-read the relevant doc section, the module docstring and `DECISIONS.md`.
2. Write a failing **unit** test of your own that shows the problem.
3. Add an entry to `docs/as/SPEC_ISSUES.md` (template inside) with the test id, the rule id, what
   the spec says, what you believe is right, and the evidence.
4. Continue with other work in the same phase. The human resolves spec issues; you never edit a
   protected file, and you never mark a contract test skipped.

## 10. Doctor (`tools/as/doctor.py`)

Runs anywhere, no models needed, and prints one plain line per check:

| Check | Pass condition |
|---|---|
| Python | 3.11–3.13 (Talemate 0.39.0 requires `>=3.11,<3.14`) |
| Packages | `as_engine` imports; pydantic ≥ 2.11; jinja2; httpx; pyyaml |
| Schema | `schema.sql` applies to a fresh memory DB; every table has an OWNER comment matching `TABLE_OWNERS` |
| Content | `core` pack compiles with zero errors |
| Prompts | every template renders with the sample contexts in `tests/fixtures/prompt_samples/` |
| Boundaries | the import-boundary scan passes (BOUND-*, SYM-01, DET-11) |
| Protected files | match `tools/as/protected_manifest.json` (`protect.py --verify`) |
| Hooks | `.dsh/hooks.json` and `.claude/settings.json` exist, call the three hooks, and use an absolute Python path; the protection hook blocks a protected write |
| Config | `as_config.yaml` parses (or is absent) |
| Runs | every run folder's manifest parses; checksums verify |
| Live (only with `--live`) | both lanes answer `/v1/models`; the configured model ids are present |

## 11. Live tests and evaluation (your machines)

- `tests/live/test_probe_live.py`: each lane answers; JSON-schema output validates; thinking can be
  switched off (and how).
- `tests/live/test_json_compliance_live.py`: 20 cognition calls per lane against real packets from
  the metal-fence scenario; ≥ 95 % parse and validate without repair.
- `tools/as/bench.py --n 5`: per call class latency on each lane → `reports/bench.json`.
- `tools/as/eval.py --scenario metal_fence --turns 10 [--ablate <call_class>]`: plays with real models
  and reports refusal rates, echo rejections, lint failures per 10 turns, leak findings, prose
  metrics, repair rate, turn wall-clock. The ablation mode is the plan's ablation duty (08 §4).
