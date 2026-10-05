# 12 — Testing

The tests are the executable form of this spec. When a doc and a contract test disagree, stop and
report it in `SPEC_ISSUES.md` (§9) — do not "fix" either side on your own.

## 1. Tiers

| Tier | Where | Who writes | Runs | Purpose |
|---|---|---|---|---|
| **Contract** | `as_engine/tests/contract/pNN_*/` | the spec (protected) | every gate, every session | the spec, executable |
| **Unit** | `as_engine/tests/unit/` | the builder | freely | your own finer-grained tests; add them generously |
| **Sim** | `as_engine/tests/sim/` | the spec (protected) | P7+ gates, `-m slow` | multi-turn soak runs with the fake model (50–200 turns) and their re-simulation (DET-02) |
| **UI** | `talemate_frontend/src/play/__tests__/` | the spec (protected) | P8+ gates | vitest + @vue/test-utils + jsdom: the store, the socket, the words, every P8 screen and (P10) the New Life wizard, the Worldgen screen and the loading bar, fed protocol messages from `fixtures/*.json` (10 §7) |
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
validates the vitest fixtures against `OUT_MODELS`. `test_sessions.py` (the owner's sessions
browser, RUN-12/13) sees the hard delete through hard links: a second name for a file shows its
bytes after the first name is gone, so the overwrite with zeros is visible; the vitest
`sessions.spec.js` pins the Your lives screen.

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

### 3.3 The world tests (P10)

`p10_world` has two kinds of world. Most tests use a **generated** one: `conftest.py` runs
`service.runs.create_run` once per test session (Owen Marsh, Established, Normal, the smallest
detail tier, seed 7, the fake model) and gives every test a private copy — `gw` is that run loaded
(`runs.load_run`) as a `Session` with a fresh `FakeTransport` in `gw.extras['fake']`; `made_world`
has the run and world ids and the `WorldgenReport`; `run_cfg` is an empty runs folder for tests
that make their own runs. No test depends on WHICH world seed 7 makes, only on what every
generated world must be. Where a test needs a small, exactly known place — the dead up close,
a crowd on a door, the quiet hours' people and their memories, marks and the wet strain's signs —
it uses the hand-made `metal_fence` scenario instead (the shared `scenario` fixture).

`world_kit.py` (protected) holds the read helpers: `now`, `turn`, `one`, `all_rows`, `rows(s, type)`
(committed events as dicts), `params`, `commit_json`, `place_of`, `place`, `settlement`, `holds`,
`pc`, `area` (the PC's active area as `turn.select` sees it), `cause(tx, at)` (an OVERRIDE event to
stand as a cause), `run(s, hours)` (the off-screen step, `turn.timers.run_offscreen`) and
`tune(s, group={...})` (the run's rules with some numbers changed — e.g. a drift chance of 1.0 so a
horde leaves today). Nothing in it scripts an outcome: a test sets up a cause (a noise, a death, a
day passing) and reads what the world did.

| File | What it proves |
|---|---|
| `test_params.py`, `test_placement.py`, `test_region.py` | WG0 draw for draw against `vectors/params.json`; faction placement, QC-2/3 and the hard-fail protocol; WG1 zones, roads and reachability against `vectors/region.json` |
| `test_worldgen_pipeline.py` | the stages and their transactions, retries, fallbacks with both lanes down, the WG9 invariants, same seed → same world hash, cancel and refusal leave no folders, the run `create_run` makes; the fixture pack `packs/p10_hopeless` is a start no world can save |
| `test_world_names_no_run.py` | a world's genesis names no run and keeps no model traffic (`Store.backup_to(..., as_world=)`), the live store is untouched, and deleting the run leaves the world (RUN-09, RUN-12) |
| `test_new_life.py` | `pcs_list`, `run_new` → the Worldgen screen → `run_loaded`, `worldgen_cancel`, the refusals, `as-engine new-run` (CLI-05), and moves played in the generated world through the 58-bit gate while the dead walk up the street |
| `test_progress.py` | the loading bar: fixed plans, percent that never drops, estimates, no counts for a turn, developer detail only in developer mode, the quips (CNT-16) and the bars the service sends |
| `test_discovery.py`, `test_traces.py`, `test_materialise.py` | a building's rooms laid out once when someone first arrives; marks and who can see them; a person taken from a cohort, never made from nothing (CONSERVE-04) |
| `test_infected.py` | the dead up close: sight and hearing by kind, energy by time, feeding, a Runner's decline, rising (a NEW body, "what was left of"), one step at a time on screen and off |
| `test_hordes.py` | the census and its conservation (HRD-15), pools, drifts, noise draws, bodies in sight and folding back out of it (HRD-07, HRD-18), a crowd on a door, breaches, the exterior pools and the Mega Horde from its first sign to its leaving |
| `test_world_day.py`, `test_operations.py` | the world's day with nobody deciding: deaths from causes and noticed once, wear, marks fading; outings — who goes, where, what they bring back, what a raid leaves |
| `test_wet_strain.py`, `test_ghosts.py` | the wet strain's living spreaders (saliva, signs, the week-3 compulsion, never for the PC); the Ghosts' enclave, council, route watch, lockdown and DECON |
| `test_background.py` | the quiet hours: who reflects and why, retelling, every job of a boundary done before the next move whatever the player's reading speed, nothing thought twice, replay re-commits them (BG-01..07) |

Earlier protected files changed in P10: `p02_space_bodies/test_bodies.py` (a DEATH now carries
`rise_pending` and schedules the rising), `p02_space_bodies/test_space.py` (a route never enters a
place twice, D-69), `p08_ui_protocol/protocol_kit.py` (`pushed_after` leaves
the loading bar's messages out; `bar_after` reads them), and — from playing generated worlds
(DECISIONS D-63..D-66) — new tests in `p03_perception/test_perception.py` (how a move reads from
where you are), `p04_one_actor/test_packet.py` (SKULL-10), `p04_one_actor/test_affordances.py` (a gap
has nothing to close; the dead are not people; SKULL-10) and `p07_slice/test_location_view.py` (the
receipt names a defence). Each pins a P10 line of an earlier module: a fresh build meets it at its
own phase (13 §1 rule 4); a builder updating from the P9 kit meets it as a failing test of a
finished phase and amends that function in P10.

### 3.4 The Actor v2 amendments (the Actor Specification, AC01–AC16)

They change finished phases in place, so their tests live in those phases' folders:

| File | What it proves |
|---|---|
| `p04_one_actor/test_identity.py` | a person's own prompt (AC01: the spec's text, no story or author words, a reaction adds one paragraph, the message opens *Who you are*); the identity card is the whole person in the dossier's words, every line traceable to its fields (IDN-01, -03, -04); what it keeps out never reaches a prompt (IDN-02); a reaction's minimum card (IDN-05); an accepted development changes exactly its line |
| `p04_one_actor/test_knowledge_menus.py` | a menu built from what the person knows (AFF-11, AC06): paired worlds that differ only in a lock, an owner on record, a law nobody told them, a knife in someone's pack or an infection that shows nothing give the same options in the same words and the same prompt; in the dark or a poor light a weapon in a hand is not known, in good light it is (VIS-03); a law they know is a cost, never a wall (C05, AC07: `forbid` adds its note; members know the laws of home, a member who left does not); every cost is said, the post's then the laws' then the nerve's, a law with no note in the locals' words (fixture pack `knowing_laws`); 'owned' is what they believe; only their own line takes an option away; a tie never seen is *not seen*, a figure that knocks something over is *heard, not seen* (AC14). A small market yard and a cellar built as dict scenarios |
| `p04_one_actor/test_packet.py` (amended) | the hour only with a timepiece on them, even in a box in the pack (Actor Spec §5); *here*, *heard, not seen* and *last seen in … ago* (AC14); a flood of words cut where a word ends, read whole for its form; what the budget cut, in order, in `omitted` — the uncertainty lines last, the last first |
| `p06_memory/test_retrieval.py`, `test_memory.py` (amended) | a standing refusal of the one asking now survives any budget, an old refusal of someone only named goes, and every cut line is on record, never in the prompt (AC16); the aftermath cuts a flood of words as the packet does |
| `p01_lanes/test_schemas.py`, `p04_one_actor/test_affordances.py`, `test_intent.py` (amended) | the answer schema is `ActorReplyV2`: a decision or — only when offered — one consultation, handles and families as enums, fields no packet can use yet null-only (SCHEMA-04); the first menu is 24 options (Actor Spec §8) |
| `p04_one_actor/test_consult.py` | what a packet offers: recall, and more of a kind when the menu hides that family; nothing in a reaction or once a lookup was answered; why a consultation cannot be answered; more of one kind in pool order, and about one thing; a packet rebuilt with a lookup's answer keeps every handle and adds after them (CONSULT-01..04, 06) |
| `p04_one_actor/test_intent_v2.py` | pace only where the attempt allows it, changing time and noise; the player's pace words read as normal where it does not; a model's speech at most 100 words (12 in a reaction), the player's never limited; delivery and timing kept; a gesture, a look or a note only when offered, a quotation word for word (INTENT-07..09) |
| `p06_memory/test_recall.py` | recall brings back the holder's own episodes and beliefs the packet did not show — by their words or by whom they are about — saying how they know and when; memories first, at most three; nothing found is only that; never anyone else's records (CONSULT-05) |
| `p07_slice/test_decision_v2.py` | a V1 and a V2 answer both read; a lookup, then the decision on the same snapshot; more of one kind added after the menu and chosen; a consultation where none is offered repaired into a decision; a failed answer goes on with what they took on, or no attempt at all; a timeout gets no repair; an unanswered ask holds the decision, and in a whole turn nothing happens and the player is told (REPLY-01..02, HOLD-01..02) |

### 3.5 The owner's appearance and smell work (F1a, F1b; D-82, D-83)

Each part lives in the phase that owns the function it pins; every world is a small dict scenario
(bodies with `dress: true` and, for a stub, its own `looks`).

| File | What it proves |
|---|---|
| `p02_space_bodies/test_looks.py` | the thirteen core people all have looks and an outfit that covers them, and list no worn clothing twice; every clothing item's block (CNT-12); CNT-17 — no looks is a warning, an outfit that leaves the torso or groin bare, a piece that is not clothing and a worn clothing grant are errors; `bodies.looks` is the looks without the outfit, NULL when never recorded; the dead start filthy and caked in gore, however they came to be; `soil` clamps, says what changed and writes nothing when nothing does; the loader dresses after every fixture item so no fixture id moves; `worn` reads outside in; a body already in clothes is not dressed again; `visible_gear` — hands, then belt gear, a handgun hidden under a long parka until it comes off (LOOK-01, -02, -04) |
| `p03_perception/test_appearance.py` | what the looker sees at each distance (hair and clothes across the room, skin and near marks within 5 m, eyes within 1.5 m, the boundaries exactly), in poor light (the outline of the coat) and not at all; a beard across a room, stubble only close; naked and bare to the waist in plain words; only the outer layer and a badge only when it shows; a coat taken off shows what it hid; no looks on record, no claim about clothes; the dead; every step of blood, gore, grime and rain; the cues a glance gives, clear and partial (LOOK-03, LOOK-05) |
| `p04_one_actor/test_appearance_in_packet.py` | a person present comes with what the holder sees of them, on its own line under theirs; someone out of sight, nothing (LOOK-06) |
| `p05_many_actors/test_appearance_cues.py` | `cues_of` adds a glance's cues only for someone seen this turn: a gun on a hip in view, not in a pocket; blood behind a closed door is no cue; your own look is none (LOOK-05) |
| `p10_world/test_dressed.py` | the player starts in their own clothes: their looks on record, their outfit worn, their gear on top (worldgen opening, LOOK-01, -02) |
| `p03_perception/test_smell.py` | F1b: what is on someone is what they smell of, the strongest winning, ties in order; a corpse smells of death after 6 / 24 / 72 hours; the open air halves how far a smell carries; clearly within half the range, faintly to its edge, never your own, never asleep, never through a wall; the dead in the dark smelled before they are seen — one smell per kind, naming nobody, the nearest setting how strongly; someone seen is smelled with how they look (SMELL-01..05) |
| `p10_world/test_gore_mask.py` | F1b: caked in gore a living body moves among the dead unpicked — a smear is not a mask; a whisper or a low voice keeps it, a normal voice, a shout, a run or a hand on one of them gives it away, for 30 s; touching a living person does not; masked, a body looking round the room finds nobody, and what already has you keeps on (INF-14) |

`test_appearance_in_packet.py` and `test_appearance_cues.py` also pin the smell on the packet line
(SMELL-04) and the smell cues, seen and unseen (SMELL-06).

### 3.6 The owner's human people (H1; D-84)

Dict scenarios again: a bar room at day 3100 (Reggie, Irene, Tess, a stranger), a back lot and a
street at noon with one of the dead close, Pumpwell for the rows.

| File | What it proves |
|---|---|
| `p04_one_actor/test_identity.py` | the card gains "What sets you off" between habits and voice — the fuse, the outlet and the grudge in words, the pet peeves, what settles them — and keeps all of it in a reaction (IDN-01, IDN-05) |
| `p05_many_actors/test_temper.py` | a temper comes from the dossier (the middle of the road without one); strain shortens the fuse; heat fades by the hour and a grudge keeps it warm; what is said to you (an insult, being ordered about, a threat — never words meant for someone else) and done to you and yours (shoved, struck — the blow is felt and who threw it seen —, your people hurt by someone you saw) provokes, each thing once; past his breaking point a man with no nerve left swings, lets some of it out, and holds a grudge and resentment; swallowing it costs Resolve; an old grudge makes it quicker and deepens; the player's anger is on record and never takes their hand (TEMPER-01..05, -07, LOOP-07) |
| `p05_many_actors/test_temper_in_packet.py` | how close to breaking, and how they feel about each person, in the packet and the prompt; a snap is said first and belongs to its moment; the actor core's humanity paragraph; shoving someone to the dead offered only with the dead right there — and shown, not buried — and taken away by a person's own line; a gun can be aimed at a leg (TEMPER-08, AFF-07) |
| `p05_many_actors/test_betrayal.py` | shoved into the dead: pushed at most 2 m, never through it, toward the one nearest him, on his back, and it turns on him by sight; keeping your feet; with no dead near it is a shove; shot in the leg you go down and cannot run, a graze in the leg still hobbles, the body shot is unchanged; a hurt leg or foot stops running, never walking, and running leaves the menu; everyone who saw the shove stops trusting him and word travels; the one shoved never forgets; seeing someone die wears you down more if you loved them; hunger past the first pangs; a night's sleep (CAS-019..023) |
| `p07_slice/test_breaking_point.py` | a snap makes the person think this wave; someone you can hardly stand in the room raises salience; fists become a punch whatever was decided and whatever nerve is left — never at a child, and words when out of reach; a snap in words must be said out loud, one repair, then they walk out; cold walks out, or to the far end with the door shut; tears sit down; in a whole turn, insult him twice and he swings (TEMPER-06, SEL-02, SEL-03, S3b) |
| `p10_world/test_materialise.py` (H1 tests) | generated people break in different ways — every outlet, fuse and grudge across a hundred of them, on their card; every settlement has its feud, the first rival pair of its generated people, and only that one (WG-29) |
| `p09_society/test_quarrels.py` | nobody sore, no rows; a row between two who resent each other, more likely the more strained, started by the more strained, heard about by the settlement; blows (bruises, standing lost); a grudge is enough; never the player; the settlement day has its rows (STL-15, STL-03 step 8b) |

### 3.7 The dead feed (I1; D-85)

| File | What it proves |
|---|---|
| `p02_space_bodies/test_animals.py` | the six core animals and raw meat; an animal in a scenario is a body of kind 'animal' with its def's size — no dossier, no actor; a body is exactly one thing |
| `p03_perception/test_animals_seen.py` | a dog reads as a dog; a bite reads as someone — or something — being eaten alive, and the dead as being eaten |
| `p05_many_actors/test_tainted.py` | a lasting mark never dries and a passing one never washes it out; tainted meat and fouled water are exposures, clean meat is supper, a mouth on a can is not taint; only a dead animal is offered for butchering; butchering makes the def's meat and leaves a carcass, once; meat from what the dead fed on is tainted for good |
| `p07_slice/test_narration_horror.py` | the narrator does not look away from the dead feeding, never describes a child's body, and the perceived-only rules still come first |
| `p10_world/test_feeding.py` | once it has you it does not let go, overfed or not; never the head or the neck, first deep then torn; he screams and the rest of them come; busy eating it is not drawn off; they stay on what they killed, then leave it; the devoured do not rise; a dog is prey, never infected, never risen; expose takes only people; what comes out of them fouls the water near it for good, a passing mark still dries; every bite seen wears you down (INF-15..19, CAS-024) |

### 3.8 The wet strain as the owner told it (W1; D-77, D-80)

| File | What it proves |
|---|---|
| `p10_world/test_wet_fluids.py` | from day three everything that comes out of a host carries it, and the dead's fluids too; blood on the hands that stop it; their blood in your eyes from a blow that opens them (a nick splashes nothing), a clean man's blood nothing; the sleeper first, and what it does to a sleeper (never to someone awake); nothing else at hand, the food on the table; the urge comes ever more often; the host is sickened by it; what the player types mostly happens, now and then the urge instead, and the story says so; week two the player only feels it; the urge is never on a menu |
| `p10_world/test_wet_strain.py` (amended) | week two only wants to — an urge on record and Resolve spent holding back; alone with a bottle, a host fouls its own water |
| `p10_world/test_infected.py` (amended) | INF-07: a week-three host is seen within half the range, not beyond |

### 3.9 Washing, clothes and the cold (F1c; D-86)

| File | What it proves |
|---|---|
| `p02_space_bodies/test_bloodied.py` | a wound bloodies the one who took it by its depth (a nick leaves nothing), up to soaked, and apply_harm still returns only the HARM; a new body starts clean, now; warmth is what they have on; the cold stage counts toward impairment |
| `p02_space_bodies/test_looks.py` (amended) | washed_at is the moment a body is made (the scenario's start), and soil never washes |
| `p04_one_actor/test_care_menu.py` | wash for what holds water, take_off for what is worn, change_into for clothes carried; the gore of the dead only once they are down; off someone out cold, the outermost piece at each slot; nothing ever offers to bare a child (CNT-11); the decency law prices undressing, not changing or washing; the packet says when you have nothing on or are bare to the waist, and how cold you are |
| `p05_many_actors/test_care.py` | a jug washes you clean and is gone, a bottle only wipes; fouled water is their fluids on you; smeared with the dead to walk among them, 'gore_smear' on whole skin and 'gore_in_wound' into an open one; one still standing is not smeared; clothes to a free hand then the pack; changing is one move; a child is never left bare; clothes off an adult out cold, never a child's, never someone awake; the splash, treating and butchering are bloody work; the reek of the dead grates every ten minutes and boils over; a naked adult in sight is a jolt and heat every half hour; bare to the waist is not naked; the player feels it and keeps their hand |
| `p07_slice/test_narration_care.py` | the story knows when the player has nothing on or is bare to the waist, and when they are freezing |
| `p10_world/test_weather_and_cold.py` | a day at a time to grimy and no further; a wash starts the count again; the rain soaks and rinses the gore off (the camouflage with it), never under a roof; out of it you dry; what the place, the night and a soaking ask; a night in the open by what each wears, and no claim for a body never dressed; the cold impairs; naked on a wet night in a cold country kills; warm again the chill goes |

### 3.10 Timing, gestures and attention (Actor v2 B4; D-87)

| File | What it proves |
|---|---|
| `p04_one_actor/test_speech_timing.py` | words alongside overlap the attempt, before or after they add; even one word takes time; nobody hides or sneaks while talking; the words that are the attempt; the menu never changes |
| `p04_one_actor/test_expressions.py` | the gestures free hands allow, toward each person here; hands full leaves only what needs none; where to keep your eyes (people here, the door you see); a reaction offers neither; the prompt lists them and the answer may name one of each; the Intent carries them through the round trip; a gesture needs the hands the attempt leaves |
| `p05_many_actors/test_speech_segments.py` | eight words at most, cut at a pause; a long warning arrives a segment at a time; what is not yet said waits on the clock; a dead speaker finishes nothing; new words cut the old; words after the attempt come when it is done; a listener hears only what was said |
| `p05_many_actors/test_gestures.py` | a gesture goes out with the attempt; she sees it pointed at her; nobody hears a gesture; eyes on one thing miss others, and the next attempt ends it; watching a door is watching whoever stands in it |
| `p01_lanes/test_schemas.py`, `p04_one_actor/test_intent.py`, `test_intent_v2.py`, `test_packet.py`, `p05_many_actors/test_effects.py`, `test_resolve.py` (amended) | the offered G / F handles are the schema's only values; words' time by SEG-02; an unoffered G99 / F99 is refused; G and F handles are handles like the rest; the start carries its attention; a SPEECH says which segment of which utterance it is |

### 3.11 Zero Resolve, answers and reconsidering (Actor v2 B5a; D-88)

| File | What it proves |
|---|---|
| `p04_one_actor/test_resolve.py` (amended) | at zero Resolve voice, silence, eyes, cover, hiding, protecting someone and surrender stay; what needs nerve goes; a low-exposure attempt stays |
| `p04_one_actor/test_firewall.py` (amended) | a yes is not a lie by itself: a question back, a yes with a condition or a delay, a yes and a step toward it, an unresolved yes; open the back door means the door, guard it means where you stand |
| `p06_memory/test_refusals.py` (amended) | a person can change their mind (the refusal revised and kept); a yes and something else is recorded, not judged |
| `p07_slice/test_answers.py` | Owen asks Mara to open the yard door: a promise she holds, preparing, a question back, a yes and something else recorded without blame, and a refusal she now reverses |

### 3.12 Self-experience, own readings, unknown names, memory jobs (Actor v2 B5b; D-89)

| File | What it proves |
|---|---|
| `p06_memory/test_memory_v2.py` | what June did and said is evidence (O handles), felt by how it went and never why; a promise can be caused by her own words and the memory keeps them; a name she could not know quarantines the memory (kept, never recalled, never looked up) and drops the belief; a name she knows is fine; a failed summary keeps its job, her raw experience is in her next packet, and a done job is never applied twice; short of room, older raw turns go first and the latest stays |
| `p07_slice/test_memory_jobs.py` | the night at Delgado's with June's writeback timing out: her job is kept failed, "Still raw from before" is in her next prompt, and the next turn asks again and writes the memory |
| `p06_memory/test_memory.py` (amended), `p10_world/test_background.py` (amended) | every named person reads the same crash as themselves; a held-back memory is never thought over |

### 3.13 Several causes (Actor v2 B5c; D-90)

| File | What it proves |
|---|---|
| `p00_substrate/test_event_links.py` | links are kept with the event in their order and read back; every cause, the parent first; what an event caused, whichever way it is named, each once; a link to nothing, to the parent, twice or of an unknown role writes nothing; replay keeps every link |
| `p02_space_bodies/test_bodies.py` (amended) | the attack that killed is the parent and every other wound that bled is a contributing cause; one wound is one cause |
| `p07_slice/test_answers.py` (amended) | a promise and an unmet yes link the ask they answer |

### 3.14 Promises as each person understands them (Actor v2 B5d; D-91)

| File | What it proves |
|---|---|
| `p06_memory/test_promises.py` | the words (categories, statuses, what an ask promises); each holds their own understanding, once; nobody holds what they never heard, words someone else said, or anything but words; an agreement only when both understandings agree, and then both stand accepted; different understandings make none; a status moves only forward; taking it back is withdrawn; kept against broken is disputed on both sides, with no liar and the promisee's own PROMISE_BROKEN; the packet line says how it stands; what Owen took from Mara's words is his own understanding, and a promise he never said is the loop alone |
| `p07_slice/test_answers.py` (amended) | a yes with a condition is her accepted promise about the door, on its condition; a yes and a step toward it is under way; a question back and an unresolved yes promise nothing |

### 3.15 Work output, feuds, far sounds, witnessed theft (Actor v2 B6; D-93)

| File | What it proves |
|---|---|
| `p09_society/test_work.py` (amended) | worn machinery makes its share of full output, never half for nothing; broken machinery makes nothing and burns nothing; a fuelled pump draws its fuel once, in the same ledger, makes what the fuel allows and stops when it is gone |
| `p09_society/test_group.py` (amended) | boiling over leaves a grudge the person carries; the player's feelings are the player's |
| `p07_slice/test_far_hearing.py` | the moment ends at the street but a shot reaches the shop, never the sealed cellar; the one in the shop perceives it in a played turn |
| `p09_society/test_theft_seen.py` | only who saw the taking and knows whose it is carries the rumour; talk spreads from them; taking one's own, or moving a thing, is no theft |

### 3.16 Generated people's looks and clothes; the story and the UI show them (F1a-2; D-94)

| File | What it proves |
|---|---|
| `p10_world/test_materialise.py` (amended) | generated people look like someone (hair by age, no beard on a woman or a boy, no tattoo on a child, the prose agrees) and not like each other; they dress for the climate (warm and coated where cold, no coat where hot, a medic's scrubs), one piece per slot and layer; nobody steps out of the count naked; a generated world is dressed |
| `p07_slice/test_narration_looks.py` | the prose is given how someone looks and smells as they come in, and only then, never the player; the scene's people chip carries it |

### 3.17 The audits (P11; D-95..D-99)

`p11_audits/conftest.py` puts the P7 helpers on the path and makes one generated world per session
(the P10 one: Owen Marsh, Established, Normal, the smallest tier, seed 7), copied for each test.

| File | What it proves |
|---|---|
| `test_commit_gate_bits.py` | AUDIT-02 (§8): the night as played passes all 58 bits; each bit's fault drops exactly that bit; every bit names the stage that writes what it checks (AUDIT-03) |
| `test_style.py` | the narrator's own pictures are remembered (never quoted speech, never a name, never a verb), the last 30 kept and a reused one moved to the end; the scene type; a played turn saves them and the next prompt names them; nothing new writes nothing |
| `test_abuse.py` | an honest night, an honest climb (a real check) and a generated world pass the battery; each of the eight exploits, planted on its own, is named by its rule alone in plain words; bands bind generated people only; god mode belongs to a sandbox; a cheat-made person is quarantined there |
| `test_release.py` | a generated world passes its release audit, which works on copies; the world as it began is checked again (a missing threat is caught; no skeleton, no check); a step that loses the dead is caught (HRD-15); rules nobody built are named once each; a child's record with the words is caught (CNT-11) |
| `test_portrayal.py` | a blow is judged before it lands by a call that did not make it; out of character, she decides once more with the reasons and what she then decides stands; a second misfit stands and is logged; no second asking once the repair is spent; the rest are judged after the fact and leave a note in her next prompt |
| `test_eval_ablation.py` | an ablated call never reaches the model; switching off writeback is measured (memory jobs fail, the world goes on); a call whose ablation changes nothing is named for removal |

### 3.18 The cheat console (P12a, P12b, P12c; D-100, D-101, D-102, D-103)

`p12_surfaces/conftest.py` makes both kits importable (P7 slice_kit, P8 protocol_kit) and gives a
GameService on the fake model, the metal_fence run on disk, and the night with a session whose
config reads the repository's packs (where `cheat_admin` lives).

| File | What it proves |
|---|---|
| `test_cheat_console.py` | the word is a standalone number; waking it consumes the line and marks nothing; every command is on the record and makes the run a Sandbox for good (/off is not logged); heal and god mode (per body); tp (not a MOVE), set, time, weather, rep; unknown names change nothing; spawn (infected and Fredrick, quarantined, an ally), the retired camper van, despawn only what the console made; kill and revive cure nothing; reveal and mind stay in the console, brief goes through perception; noise; canned persona lines never repeat; the hard line refuses and logs; cheat packs are not in a run |
| `test_cheat_protocol.py` | the word in any box, commands and parse errors through the GameService; before the word a '/' line is only words; a cheat question gets the world back, after the word nothing is hidden; a dead character can be revived; Fredrick is briefed the turn he thinks and nobody else learns anything; what the console says reaches no model call |
| `test_cheat_twin.py` | CHEAT-02: a Sandbox twin with Fredrick and a crate of ammunition, run a day beside the clean night, holds the same world once the cheat-made things are left out |
| `test_cheat_owner.py` | the owner's commands: a will overwritten (never the player's); a memory cut out (sealed, beliefs retired, the name gone, a gap left); the strain put in a council member mid-meeting, then cured; the cure kills what rose; a horde from its own district (the count holds), the Mega Horde sent early (only one at a time), the census in the console only |
| `test_cheat_secrecy.py` | CHEAT-03: no actor or narrator prompt and no play screen knows the word, the voice or a command; CHEAT-09: CANNED_LINES is CHEATS.md §5 |
| `test_willis.py` | CHEAT-12..15, TEMPER-10, REL-06, WORLD-07 (D-102): the code box answers only taken or not and opens the New Life list; his life is asked for with his pack only after the code; it starts with the console open, a Sandbox, and him in the reality exception, fickle, dressed, coffee in hand and among people who know him; no wound, need, strain, dirt, cold or grip touches him while the man beside him keeps every rule; the console cannot kill him; every fight is unwinnable (a lookalike corpse, and he is elsewhere); /wonder is his alone, happens as the next turn opens, is seen and told; the voice knows he thinks it a demon; Fredrick blends in beside him; only he is offered the wonders, and nothing stops them; the endless plate of samiches (no samich mountain); insults are nothing to him, worship is wrath, one stray wish is let pass with a correction, ingratitude for his gift is wrath that kills; the Wild Card walks a normal world away from you, friendly at best and never a friend, never where you left him |
| `test_plain_cheats.py` | CHEAT-16..19 (D-103): the scene is the Boss's side of the glass (handles; what the PC looks at is marked; people known by name); "Make that infected jig joyously" — the shambler in front jigs for the minutes asked and does nothing else, the PC sees it, it is logged in the Boss's words and the run is a Sandbox; an ambiguous line is asked back and writes nothing; a bad step runs nothing; an impossible step halfway undoes the ones before it; several steps in order (a teleport, a belief, a feeling, a made thing); a blast wounds by distance and makes a 180 dB bang; a show is seen by everyone there and told by the narrator; with no chip chosen, Say goes to a name the words (or an Act's quoted words) start with when that one is here, else to the last one spoken to, whom the view offers first; through the GameService, the Cheat field is empty until the word, takes the word and then slash lines, and an empty compose is refused |

### 3.19 The seal and the freedom of the narrative (P12; D-104)

| File | What it proves |
|---|---|
| `p12_surfaces/test_seal.py` | SEAL-01..05: sealed, this machine and the model machines answer and nothing else does — a public name is refused before any DNS question, a public address or a home address with no model on it is refused on plain sockets and on the event loop, and every refusal is logged; the libraries are switched offline and proxies removed, and lifting the seal puts them back; a model address outside the home never loads (LaneConfig, EngineConfig, the Connect screen's config_set) and a bad install changes nothing; the lane client reads no proxy; the Talemate server's first import is the seal and it never fetches punkt while sealed; every CLI command runs sealed; a changed model address re-seals; the launchers bind 127.0.0.1 and run uv offline, Docker publishes on 127.0.0.1, and the frontend loads no font or script from outside |
| `p12_surfaces/test_freedom.py` | FREE-01..03: the narrator fades nothing out (and CNT-11 is said where it reads it); a person may do anything that follows from who they are; no prompt carries a softening or refusal phrase; Intensity is Full unless the owner picks Softer |

### 3.20 The death screen and Willis (P12; D-105, D-106)

| File | What it proves |
|---|---|
| `p12_surfaces/test_death.py` | DEATH-10..14: the screen tells the dead person's own story (the cause as they felt it, the last three moments, their own choices) with Willis's lines from the frozen moment and the Voice's words, its last word still to come; one WILLIS_ROAST call with their own record (the words they typed, how long they lasted; not how they die), at most three lines, kept in the story at the doom's turn and never asked for twice; with the model down Willis still comes — to a stranger, "why am I here?", cut off; whatever the settings (the console used, Ironman: no loading back); nothing but their own record goes to him, and the reveal names who was where by their true names; he remembers meeting them and owns the killing when it was his; in his debt six lines, twice as hard; how long they lasted in words; through the GameService: the Doom before the turn's result, the screen at once, the Voice's last word a moment later (both its calls recorded), the story, screen 'dead', the truth only when asked and nothing to reveal while alive; Willis collects: the console closes |
| vitest `death.spec.js` | the Death screen: Willis's lines and the Voice's words at once, its last word when it comes; title, time, cause, last moments, choices; the truth only after a warning, sent as `death_reveal`; Ironman hides Load; the clarity rules |

### 3.21 The Doom and the Voice (P12; D-106)

| File | What it proves |
|---|---|
| `p12_surfaces/test_doom.py` | DOOM-01..08, VOICE-01..09: bleeding that the best care could no longer stop is a doom at once (a limb with a tourniquet, the torso packed), with the time left; the doomed scream — the room hears it, they feel it, a mind does nothing else — and nobody learns why; a killing blow is a doom in the instant, with no time to scream; the wet strain's last minutes are known ahead; a doom found while the world runs off-screen leaves nothing scheduled in the past; the untouchable are never doomed; nothing undoes a doom (the console refuses), and the overdue safety net logs a repair; the scene in order — freeze, three seconds, the dark, footsteps, Willis, the snatch a quarter of a second after his last word, nothing, the Voice, the dust — stored in the story before the narration; Willis to a stranger, in his debt (the loan: six lines), to someone he met; the Voice's facts from the record only (the clue they felt and could not place, what was near them, the upper hand, never how); the Voice without a model; how long they have in words; the doomed cannot tell (DOOM_GUARD, the phrase check when it is down; ordinary words still get out, no time passes); a doom made between turns plays with the next moment, once; a broken scene never costs the turn (a repair is logged); revived, the doom is spent (no safety net, no more screaming); no prompt, scene text or fallback names the Voice |
| vitest `doom.spec.js` | the Doom overlay: over any screen, the beats' pacing on a fake clock, the snatch, a click to go on and to let it go, a new run clears it, the clarity rules |

### 3.22 The Doom, deepened (P12; D-107)

| File | What it proves |
|---|---|
| `p12_surfaces/test_doom_deep.py` | DOOM-09..15, RES-06..07, RESOLVE-07: the screaming starts a short while before the end, not at the doom, and some never scream; everyone knows the scream and nothing more (lore, cue, no word of why); what the talk leaves — shattered, broken, held — and that it never comes back further; a shattered mind's first hours; a broken mind feels it and knows nothing (its packet); words come out in pieces, the player's too; the Voice dooms some at the bite (four weeks, the despair checks set) and not all; it tells the bitten "about 4 weeks"; the dust moves again on what is left; they can't take it (a check a day, the revolver she carries, a gunshot, DEATH 'suicide'); or they go through all of it (no means: nothing, a check every day); the player decides for themselves; ending it is on the menu only at the end of the rope, and only for what is in hand; the player can end it (the frozen moment even then; "You took your own life."); an empty gun only clicks; Willis cannot end himself |

### 3.23 Parkour (P12; D-108)

| File | What it proves |
|---|---|
| `p12_surfaces/test_parkour.py` (world `rooftops`) | PARKOUR-01..08, FALL-01, INF-20: the roofs have height (elevations, drops, rises) and nobody walks a climb, a gap or an edge; Addison sees the lines on her menu (the pipe, the gap, the edge) and nothing to open or walk through; the Where panel says how high, how far and which way; how hard each line is (climb, gap and drop classes, up and down); she makes the jump (CLEAN), balks at the edge (FAIL), falls short into the alley (BREAK: a leg and an arm, down, the noise of it); a roll takes the drop out, a bad one takes all of it, the worst lands head first; down the drainpipe is easier; how a fall hurts by height, and twenty metres kills; she moves before she knows why (fleeing means up); the dead below cannot follow — a shambler never, a runner by the drainpipe, anyone by the fire escape; the runner climbs and sometimes falls; roofs come with their buildings (hatch, drainpipe, edge) and the block's roofs get a gap |

### 3.24 Addison and canon events (P12; D-109)

| File | What it proves |
|---|---|
| `p12_surfaces/test_addison.py` (world `rooftops`) | D-109, WG-33b: she is from Boston and sounds it (no Mississippi, no Hattiesburg, no y'all); pale skin and the tight low bun; light parkour pants, not the skort; the bible's sample lines; hard to crash out (fuse 4, cold); she knows the mimicry (the cue); dressed from her card, the pants, bra and shoes cover her; the laundromat is canon, 1–365 days before the run; a canon event's range must be real (1 <= lo <= hi); `canon_memories` writes one personal history row and one anchor memory (salience 100) on a day 1–365 before; a card without canon events writes and draws nothing; the day is drawn on the opening stream, purpose canon:0 |

### 3.25 No deadlines: the stall watchdog (P1; D-110)

| File | What it proves |
|---|---|
| `p01_lanes/test_stall.py` | LANE-10: a call that keeps moving outlasts both the stall window and its expected time; reasoning alone is progress; keep-alives, empty deltas and a prefill counter that stops advancing are not; no progress for the window is `LaneStalled` (a `LaneTimeout`); the silent wait before the first token (a silent head or a silent body) has no limit unless `silent_prefill_window_s` is set; with `prefill_progress: supported` the window applies from the first second and `return_progress` is sent (and only then); cancelling a call closes the stream; an error event or a dropped connection is a lane error, not a stall; a server that ignores `stream` is read as one body. LANE-11: progress snapshots show the phases and the quiet time; the client reports what is live, never cuts a slow call off, and maps a stall to `timeout` without marking the lane down. Settings: stall window 300 s, silent prefill 0, a config that still has `request_timeout_s` loads. `p01_lanes/test_http_transport.py` (amended): the request asks for a stream |

### 3.26 The Writer and the Clerk (P1, P5, P7; D-111)

| File | What it proves |
|---|---|
| `p01_lanes/test_writer_clerk.py` | `system_think_token` puts `<|think|>` at the start of the system message only when thinking is on (and makes a system message when there is none); no other mode sends it; Gemma's thought channel (closed, cut off, empty) is reasoning, never story; the Writer's call classes are exactly the narrative and long-context ones (D-113: scene summaries and say-my-way included), and its narration, Voice, Willis, recap, scene summaries and say-my-way think; the HOT minds think on the Writer, the WARM minds and the judges on the Clerk, the judges thinking; every call that thinks has at least 2,000 tokens of room |
| `p05_many_actors/test_reactions_cascade_plan.py` (amended) | HOT goes to `hot_cognition.lane` (A by default; B when the owner sets it) and WARM to the actor-cognition lane; with the Clerk down WARM moves to the Writer (DEGRADE-01); WARM never spills onto the Writer to balance load |
| `p07_slice/test_hot_lane_schema.py` | a HOT call's JSON schema is sent with thinking on only when its OWN lane supports it |

### 3.27 The limits bench (tools; D-112)

| File | What it proves |
|---|---|
| `p01_lanes/test_bench_limits.py` | `tools/as/bench.py --fake` on two simulated lanes with known limits (`tools/as/benchsim.py` SMALL: the owner's speeds in small contexts) finds them: a reported context, and an unreported one pinned by halving; reading and writing speed within 15–20%; the thinking switch and prompt progress; one cached prompt; the parallel slots; how far in five facts are still found, every rung answered in the JSON asked for; every call class on its own lane and regime, and the HOT call timed on the other lane too; the HOT call, the narration and its judge timed without thinking too, each faster, and the turn projection without thinking faster at every depth, with the settings named in the report; every narration draft put through the code lint. The settings keep the design: concurrency from the slots, never a lower stall window, `max_tokens` raised only where a call was cut short (capped by the context left), expected seconds from p90, budgets that still admit each depth's designed minds, no call moved to another lane and no thinking turned off, `--keep-budgets` honoured; it never writes as_config.yaml for simulated lanes. The pieces: parallel slots must pay (20% throughput, at most double the latency), recall is reliable only up to the first fading length, cut short means the cap was reached or thinking never ended, the filler is the size asked with facts where asked and no shared prefix, a resumed run keeps what it measured, an unknown stage is refused |

### 3.28 The models at work under the bar (P10; D-114)

| File | What it proves |
|---|---|
| `p10_world/test_activity.py` | PROG-08: `activity()` takes the furthest phase, the longest call, the newest sign of life, the reading percentage and the time left before the stall watchdog, and says nothing of lanes, calls or counts; the window read from a snapshot is the transport's own (LANE-10); the feed pushes on a change and otherwise every two seconds, ending idle. LANE-11: two clients over one transport each see only their own calls, and the end of a call is reported as None. Through the service: a turn's activity is valid, its own, ends idle before its bar closes; the quiet hours' job clients pass theirs on (BG-03) |
| UI `loading_bar.spec.js` (amended) | the activity line and the quiet line (10_UI §2.10) |

### 3.29 The Cheat field's words and its dictionary (P12; D-115)

| File | What it proves |
|---|---|
| `p12_surfaces/test_cheat_dictionary.py` | CHEAT-20: a command word first is that command, its raw the line as typed ("Spawn Fredrick" is /spawn); a command that takes nothing only as the word alone; anything else is plain words; every command has a meaning, a usage and an example that parses; a plain command that cannot happen writes nothing at all (no story line, no log, no Sandbox) while a '/' line keeps its record; through the service "Spawn Fredrick" spawns him with no plain-words reading, and "kill the lights" goes on to plain words untouched. CHEAT-21: the dictionary lists every command in order (wonder only in the reality exception) with its usage, meaning, example and the options of each blank — 'me' and the people the PC knows by name, the places it knows, the items, the groups, the packs' people and the dead by type, the stats, the weather, the strains — sorted, without repeats; CHEAT-03: empty with no run and before the word |
| UI `cheat_assist.spec.js` | the autocomplete (`cheatAssist.js`): every command on an empty field, narrowed as the word is typed, a space after one that takes something; the blanks' options from what is typed (the longest run of words, an open quote), quoted when they have a space, the blank after to / about / with / at first; nothing for plain words; the dictionary rows, filter and the one being typed; plain words only; the store keeps the words while the console is open and drops them with the console or the run |

### 3.30 Character examples as history (P4; D-116)

| File | What it proves |
|---|---|
| `p04_one_actor/test_voice_examples.py` | EXAMPLE-01: an example is a situation, who spoke first and what they said, the person's words and a pressure; a voice without examples is still a voice. EXAMPLE-02: a deliberation takes them in order until the room (600 tokens) is gone, the first that does not fit ending the list; a reaction only the pressure and limit ones, at most two; over the packet budget the last example goes first and nothing else. EXAMPLE-03: the prompt shows them right after the card, before what matters now, as things already said, and a person with none shows no heading; say-my-way shows the PC's before the idea. EXAMPLE-04: Willis's own examples (the `wild_card` records of the cheat packs) open his roast; none, a missing folder or no folder: none |

### 3.31 What was said here (P4, P7; D-117)

| File | What it proves |
|---|---|
| `p04_one_actor/test_conversation_thread.py` | THREAD-01: a question put to her hangs until she answers, a demand does not; her own lines in order among what she heard; a speaker never hears herself; this turn's words are utterances, not the thread, and nothing later than the moment reaches it; the window (30 minutes, a rule) and the room (she left and came back: what was said before is gone; a step within the room is not an arrival); only the last few lines, the speaker as a handle, never an id. THREAD-02: the heading and lines in the prompt between where she is and what reaches her; over budget the oldest line goes first, after memories and lessons. SEL-03 `owed_answer`: a question left hanging keeps her in the moment until she answers; the one who asked owes nothing; a flag the weights do not name counts nothing |
| `p07_slice/test_what_was_said.py` | DOS-05 through whole turns: Mara's "Quiet." and June's "What was that?" become their voice lines, each naming its utterance, and Mara knows what she said; the silent have none. THREAD-01 the next turn: Alice has both lines in the order said, Mara her own first, June hers |

### 3.32 Work put down can be taken up again (P5; D-118)

| File | What it proves |
|---|---|
| `p05_many_actors/test_picking_up_work.py` | After CAS-014 pauses June's count, `put_down` names it, the menu offers "Keep going" for it by its label and her commitments say it is put down; keeping working resumes it from where it stood (never from zero) and counts on; finished work is never offered again |

### 3.33 A killing seen (P9; D-119)

| File | What it proves |
|---|---|
| `p09_society/test_a_killing_seen.py` | With the lights on, Owen kills Alice in front of Mara, all three of Delgado's crew: `trigger.killer` is Owen; the onlookers are Mara alone (never the killer, the dead or June in the back) and the crew is the group that saw; CAS-025 — Mara trusts him 2 less, fears him 2 more, holds a fear of him and carries the story; CAS-026 — he carries it (stress +2); CAS-027 — the crew's standing for him drops by 2. CAS-028: told by Mara, Eli (who trusts her) believes it and trusts Owen 2 less; Nita (who does not) changes nothing. In the dark Mara sees a figure go down: nobody is an onlooker, no group saw, nothing changes but his own stress. Self-defence and stopping her going for Mara: `killer_provoked`, nothing follows. Mara kills Alice in front of Owen: nothing is written into the player's character (C06). No killer — a death with no cause, or the cold after he hit her — is not a killing; the rumour's words |

### 3.34 Seen before swept (P7; D-120)

| File | What it proves |
|---|---|
| `p07_slice/test_seen_before_swept.py` | Through whole turns, not hand-granted percepts: Owen takes Dale's jerky from the stall and June, who saw it and knows whose it is, carries it out of the turn (CAS-012 found her in S10) — Nita, who saw it too, does not; Alice, cut by Owen before the moment, bleeds out as it ends (S12) in the light, Mara sees her go down, is strained by it (CAS-019), trusts Owen 2 less and carries the story (CAS-025). Off-screen (`run_offscreen`) her death is swept too: Owen carries it (CAS-026), and nobody is strained by seeing it, because nobody perceives off-screen |

### 3.35 The second look (P7; D-121)

| File | What it proves |
|---|---|
| `p07_slice/test_the_second_look.py` | INTAKE-07 at the Night at Delgado's: "I lie down and sleep" — the first menu has no room for sleep and the intake says NONE; the second look has the same first handles, then the rest of what Owen could do, sleep among them, and he lies down. Still nothing on the second look is the rejection (two calls); words that are not an action get no second look (one call) |

### 3.36 Sleep rests you (P7; D-122)

| File | What it proves |
|---|---|
| `p07_slice/test_sleep_rests_you.py` | SLEEP-01: 16 hours awake then 8 asleep — fatigue held while she sleeps, rested when she wakes, the waking saying how long she slept; a 2-hour nap pays 4 of the 16 hours owed. SLEEP-02 through a turn: Owen has slept seven hours and "I wait" wakes him first, rested, and the night takes the edge off and gives back a little Resolve (CAS-021 — swept although a sound at the scene compile was what woke him). Five hours is not a night. SLEEP-02 in the resolver: Owen asleep wakes before anything but sleep, sleeping on is not falling asleep again (all of it counts), and June asleep does not wake by deciding to. CAS-029: Mara kept her promise to June and is steadier for it |

### 3.37 What wears the will down (P9; D-123)

| File | What it proves |
|---|---|
| `p09_society/test_what_wears_the_will_down.py` | In a kitchen: Dale cuts eight-year-old Teo's throat in front of his mother — Rosa, his guardian, loses 3 (CAS-008, lost_dependent); the onlookers who saw who it was never include the dead; Dale's first kill and a child: 1 and 3 (CAS-031, CAS-032). Owen kills Rosa: Dale, who loves her, and Teo, her son, lose 2 each, Owen nothing; the same death is grieved once. Rosa in the yard sees nothing; Nita tells her, she believes it and loses 3 (CAS-030) — told twice, grieved once. A second kill is not a first. A scratch is not severe pain, a stab is (CAS-033); fed, nothing — hungry, 1 (CAS-034); sixteen hours awake, nothing — a day, 1 (CAS-035) |

### 3.38 A bite seen (P9; D-124)

| File | What it proves |
|---|---|
| `p09_society/test_a_bite_seen.py` | Hal is bitten in the yard in the light with Mae beside him: the settlement that saw is Pumpwell (Hal's own bite is no sighting; Owen belongs nowhere) and its quarantine law comes into force for Hal (CAS-015). With Mae in the shed nobody of the settlement saw it: nothing. A settlement without the law: nothing, and no warning — not having the law is not a fault |

### 3.39 Promises answered (P7; D-125)

| File | What it proves |
|---|---|
| `p07_slice/test_promises_answered.py` | Through a turn: June's writeback says Mara broke her promise — June trusts Mara 2 less and holds a grudge (CAS-011) in that same turn; says she kept it — Mara gets a little Resolve back (CAS-029). In the quiet hours: Mara's reflection decides Eli broke his — answered there too (BG-04) |

### 3.40 Nobody is a template (P10; D-127)

| File | What it proves |
|---|---|
| `p10_world/test_nobody_is_a_template.py` | GEN-01: twenty adults of one settlement and one trade have twenty different voices and inner lives, and each part of them varies on its own; a child's lines are a child's, with no swearing, dialect or secret; nobody born after the Fall lost family in its first week; a thousand people of every age are valid (CNT-10) and child-safe (CNT-11); the same seed is the same person |

### 3.41 Being hurt leaves a mark (P9; D-126)

| File | What it proves |
|---|---|
| `p09_society/test_being_hurt.py` | Owen hits Alice for nothing with Mara watching: Alice trusts him 2 less, fears him 1 more and holds it against him (CAS-036); Mara trusts him 1 less and tells it (CAS-037). A fight Alice started: nothing. Mara hits Owen: nothing is written into Owen (C06), and Alice, watching, judges Mara. Owen with his Glock: "Quiet." is no threat to remember; "Hand it over or I'll shoot you." leaves Alice afraid of him (CAS-038) |

### 3.42 The room talks (P7; D-128)

| File | What it proves |
|---|---|
| `p07_slice/test_the_room_talks.py` | AMB-01..03: Owen asks the floor for his lighter; Mara, past the budget, gets one line on lane B from a packet of her own voice and what reached her, and it is her COLD act's speech, to Owen; Alice, unscripted, keeps quiet. The line is said and goes into her voice lines. Quotes and asterisks are not words. A failed line is silence — no fallback event, no repair row. At quick depth one line, the most salient first. Nothing reached them, lane B down, or already spoken this turn: no call |

### 3.43 What is done to you and yours lasts (P9; D-129)

| File | What it proves |
|---|---|
| `p09_society/test_what_is_done_lasts.py` | Owen takes Alice's ledger from her hand: she trusts him 2 less, resents him and holds it (CAS-039); Mara, who knows whose it is, is a witness, not the one robbed; Alice taking Owen's Glock writes nothing into Owen. Owen hits June for nothing: Mara, who loves her, trusts him 2 less in all and holds it (CAS-040), Alice 1 less; Owen kills June: Mara's grudge is strength 3 (CAS-041). Called useless alone: an insult only; in front of Mara: Alice loses a point of Resolve and resents him (CAS-042), once an hour; Owen insulted: nothing. Held, Mara watches June beaten: Resolve -2, once an hour; Alice, held, does not love June: nothing (CAS-043). Alice hands over the ledger at gunpoint: Resolve -1 and resentment (record_responses) |

### 3.44 Everyone knows (P6; D-130)

| File | What it proves |
|---|---|
| `p06_memory/test_everyone_knows.py` | LORE-02: in a market yard Owen, Vito of the Remnants, a masked Ghost and a child of seven each hold exactly what everyone says, what their generation says and what their faction says — never as a belief, and with no event more than the load had. LORE-03: with nothing in the moment none of it comes to mind, and when it does it is what people say, never something they know; "Is there a cure for a bite?" brings "There's no cure…" and what the Remnants say about it to Vito's mind; seeing the Ghost brings the three things he has heard about them; the child's lines say where they come from and reach her ambient packet; a scream heard (the cue, no word said) brings what everyone says about the screaming, each thing once before any twice. A person made mid-game (mind.actor.create) holds the same, and their card's knowledge cues as lessons |

### 3.45 The Writer sees what it is asked to write (P10; D-131)

| File | What it proves |
|---|---|
| `p10_world/test_the_writer_sees_the_world.py` | Read from the prompts the Writer was sent, not the fields beside them: the history call lists every event it must answer for, by id; a person is written knowing the day since the Fall, what their generation remembers, the sketch that makes them who they are, what happened here and what everyone (and their generation) says — a child born after the Fall hears "Walkers are sleepwalking people", not what the old say; the opening call lists every entity it may cite by id and every condition by name |

### 3.46 Putting down the dead is not hurting anyone (P9; D-132)

| File | What it proves |
|---|---|
| `p09_society/test_putting_down_the_dead.py` | June is dead; a minute later Alice destroys her head, as everyone must: no attacker, no onlookers of an assault, no grudge for Mara who loved her, no rumour, no lost trust; no anger at Alice and no 'bonded_hurt' for Mara. The blow that kills still lands on someone alive |

### 3.47 Eating the dead (P9; D-133)

| File | What it proves |
|---|---|
| `p09_society/test_eating_the_dead.py` | Alice, a knife in hand by June's body, is offered to cut meat from it, and the body gives raw meat by its mass; Owen and Mara watch: Mara (never Owen) trusts Alice 2 less, fears her, is shaken and tells it, and — she loved June — holds a grudge of strength 3; Alice carries it (stress, Resolve). Shoving someone to the dead (CAS-022) is never written into Owen |

### 3.48 Captives (P9; D-134)

| File | What it proves |
|---|---|
| `p09_society/test_captives.py` | Alice holds Mara; Owen hits her: she was held when it landed, Alice and June saw it, June trusts Owen less, is shaken and tells it (CAS-049). Mara had swung at Owen, was taken, and Owen kills her: CAS-025 does not count it (she had been fighting), CAS-050/051 do — June is shaken, tells it, and trusts him 2 less. June's card says never 'torture': with Mara free she may hit her; with Mara held the blow is off her menu (gate 'moral') |

### 3.49 Hands up (P9; D-135)

| File | What it proves |
|---|---|
| `p09_society/test_hands_up.py` | Mara holds up empty hands; Owen hits her: she had given up, June trusts him less, is shaken and tells it — once (CAS-052; CAS-049 does not count it, she was not held). A surrender in the same instant as an attack is a feint, one followed by an attack is over, and one more than 10 minutes before is not this fight. Mara swung at Owen, then gave up (the surrender option), and Owen kills her: CAS-025 and the captive rules do not count it, CAS-053/054 do — June is shaken, tells it and trusts him 2 less. Mara's card says never 'execute_prisoner': knife in hand, she may cut Alice down until she sees Alice's hands go up, and again once Alice swings at her; hitting her stays offered throughout |

### 3.50 The player's hands (P7; D-136)

| File | What it proves |
|---|---|
| `p07_slice/test_the_players_hands.py` | "I nod.": the INTAKE schema's gesture enum and the prompt list the PC's gestures, the answer's nod goes with staying put, and a GESTURE 'nod' by the PC is committed. 'I hold up my empty hands. "Don't shoot."' (the Glock pocketed first): the PC stays put, says the words and shows empty hands. A gesture handle the PC was not offered is dropped and the turn still runs |

### 3.51 What makes you look up (P5; D-137)

| File | What it proves |
|---|---|
| `p05_many_actors/test_what_makes_you_look_up.py` | Material percepts (REACT-01): Mara takes a knife out of her pocket — news to June; glasses out of a pocket are not. June lies dead and Alice starts taking her clothes — news to Mara, who loved her, not to Owen. Owen takes the ledger out of Alice's hand — news to her. Mara beckons June — news to June; a shrug is news to nobody. June swung at Mara and Mara holds up empty hands — news to June alone; a minute and a half later it is no fight |

### 3.52 Your own (P9; D-138)

| File | What it proves |
|---|---|
| `p09_society/test_your_own.py` | Owen holds his Glock on June and threatens her: June fears him (CAS-038), Mara, who loves her, trusts him less and resents him (CAS-055), Alice is unmoved. Alice holds a knife on Owen: nothing is written into Owen, but June, who has come to love him, holds it against Alice. June lies dead and Alice strips her: Mara trusts Alice less and holds a grudge (CAS-056), CAS-057 does not fire (the dead are stripped every day). June out cold and stripped: Mara trusts Alice 2 less in all (CAS-056, CAS-057); Owen unchanged |

### 3.53 Shielding (P9; D-139)

| File | What it proves |
|---|---|
| `p09_society/test_shielding.py` | Mara puts herself between Eli and the danger: one point of Resolve back; again an hour later, nothing; the next day, one more (CAS-058, once a day). Waiting is not shielding: protecting_today selects no one |

### 3.54 What the character grew up hearing (P8; D-140)

| File | What it proves |
|---|---|
| `p08_ui_protocol/test_the_guide_knows.py` | GUIDE-04: asked about crawlers, the guide is given only the crawler lore Owen holds and what he has learned about them ('You know: …', the 'Knows: ' dropped); a question about bleeding touches none of it; asked whether the head matters he is told what he heard, the wrong saying too; lore and lessons he does not hold never come through |

### 3.55 Seen going (P5; D-141)

| File | What it proves |
|---|---|
| `p05_many_actors/test_seen_going.py` | VIS-06: Mara walks into the storeroom; where she went June cannot see her, but she sees her go at the doorway ('Mara moves away.', source Mara). Someone in another place, or asleep, sees nobody go |

### 3.56 Left behind (P9; D-142)

| File | What it proves |
|---|---|
| `p09_society/test_left_behind.py` | June, bleeding from a deep cut, watches Mara (whom she loves) walk out: she trusts her 2 less and holds a grudge (CAS-059); a minute later it is not counted again. Owen walks out on her the same way (she has come to love him): the same, nothing written into Owen. A scratch, someone she does not love, or June out cold: nobody is left behind |

### 3.57 A person's lines sound like the person (P10; D-143)

| File | What it proves |
|---|---|
| `p10_world/test_voices_hang_together.py` | For adults, children, teens and elders the three lines are always the set that belongs to the voice drawn; elders are not only their age (a dozen or more voices among a hundred); nobody born after the Fall remembers the world before it; whoever swears when nervous swears, whoever quotes scripture or apologises for everything never does; no line names another trade's work or a sex |

### 3.58 One of our own (P9; D-144)

| File | What it proves |
|---|---|
| `p09_society/test_one_of_our_own.py` | Owen kills Alice in front of June and Mara, all of Delgado's crew: the crew is the group they shared, June and Mara the crew who saw it; their grievance with the crew rises 20 (CAS-060) and an hour later each has a LOYALTY_CHECK for the crew, reason 'killed_one_of_us'. Mara kills the stranger: he was never one of theirs, nobody's loyalty is asked |

### 3.59 It comes back (P7; D-145)

| File | What it proves |
|---|---|
| `p07_slice/test_it_comes_back.py` | Owen watched Alice kill June: at stress 9 it comes back every second turn, at 10 every turn, in his own words for it ('It comes back unasked: June goes down and does not move.'), and the prose may name her; at stress 6 it does not, nor in the turn it happened, nor four days on |

### 3.60 Broken nights (P9; D-146)

| File | What it proves |
|---|---|
| `p09_society/test_broken_nights.py` | Mara lies down at stress 9: three hours in she is awake (CAS-061; slept 3 h) and nothing is given back. At stress 5 she sleeps through. A night already over is not broken (she woke at two hours and lay down again). Owen at stress 8 wakes the same way and the narrator's state lines say so that turn only |

### 3.61 A line they don't cross (P7; D-147)

| File | What it proves |
|---|---|
| `p07_slice/test_a_line_they_dont_cross.py` | The intake is shown what Owen will never do (his card's wont list, in the prompt); answered 'wont', the player is told "Your character won't do that. It's a line they don't cross." and no second look is made |

### 3.62 A child (P9; D-148)

| File | What it proves |
|---|---|
| `p09_society/test_a_child.py` | Owen hits Eli (9) in front of June: she trusts him less, is shaken and tells it (CAS-063). Blood has just been spilled on the floor and Mara runs into the storeroom leaving Eli there: Eli trusts her 2 less and holds it (CAS-064, strength 3); June, who saw it, trusts her less and tells it (CAS-065). A quiet room is no danger: nobody is left behind |

### 3.63 People you get to know (P10; D-149)

| File | What it proves |
|---|---|
| `p10_world/test_people_you_get_to_know.py` | June (made generated) and Owen exchange three lines: the boundary has a voicing job for her; it is asked with her card, the lines she actually said and her name; its answer becomes her voice (capsule, habits, example lines) and she is not voiced again, at this boundary or later. Unanswered (the fake model has nothing to say), her card stands and she is not asked again. An authored person, or someone who said one word to Owen, is never voiced |

### 3.64 The quiet (P7; D-150)

| File | What it proves |
|---|---|
| `p07_slice/test_the_quiet.py` | A calm lit floor: nothing reached Mara, but in a quiet moment with people around she gets a packet with nothing reached and someone to talk to, and says one line (the prompt says it is a quiet moment); Alice says nothing. The next turn it is Alice's line. Not in a reaction wave, not when someone has already spoken in the room this turn (no call at all), and never alone in an empty street |

### 3.65 Words only (P4; D-151)

| File | What it proves |
|---|---|
| `p04_one_actor/test_words_only.py` | A model's speech keeps only the words: '*sighs* Fine.' says 'Fine.', bracketed and parenthesised directions and double quotes go, spaces are collapsed; nothing but a direction is no speech (a speak choice is 'empty', any other choice goes ahead silent); the player's own '*waves* Hi.' is said as typed |

### 3.66 In the right person (P7; D-152)

| File | What it proves |
|---|---|
| `p07_slice/test_in_the_right_person.py` | `retell` tells a second-person menu label in the first person and of a man, a woman or someone else (possessives, reflexives, 'you' as subject or object, 'are'/'were'/-s agreement, modals and past tenses untouched; a label with no 'you' is unchanged); the narrator's line of the PC's own choice is told of him ('Owen chose to take his Glock 19 into his hand.', no 'your'); a person's own memory of a choice is in the first person ('Chose to take my .38 revolver into my hand.', 'I chose to …') |

### 3.67 People you know of (P7; D-153)

| File | What it proves |
|---|---|
| `p07_slice/test_people_you_know_of.py` | The player's character (no relationship rows, C06) keeps its crew in mind with where it last saw each ('June: last seen in the stockroom just now'); at most `max_known_elsewhere` of them, the most recently seen first, and never one it saw die; "I walk over to June and shove her." reaches an intake that lists June with where she was last seen and is told the first step is going there: the PC goes through the storeroom door and 'shove June' is the remainder |

### 3.68 What the lint wants, said first (P7; D-154)

| File | What it proves |
|---|---|
| `p07_slice/test_what_the_lint_wants.py` | The narration prompt states the lint's rules before any draft (no three sentences in a row starting with the same word, the active voice, no moods named) and lists the names the PC knows, the packet's allowed_names; no names, no list; (D-157) a line of which only the tone was heard shows what was heard, never a quoted "None", to the Writer and to the judge, and a speaker is capitalised |

### 3.69 Nobody to calm (P4; D-155)

| File | What it proves |
|---|---|
| `p04_one_actor/test_nobody_to_calm.py` | In a quiet room nobody is offered to calm (each is refused at the physical gate); someone heard shouting, then someone seen hurt, is |

### 3.70 Seen, not caught (P4; D-158)

| File | What it proves |
|---|---|
| `p04_one_actor/test_seen_not_caught.py` | A woman half seen behind the counter came through "only partly" (no "some words lost") and leaves "You could not make out all of S#." |

### 3.71 When it is (P7; D-159)

| File | What it proves |
|---|---|
| `p07_slice/test_when_it_is.py` | A room line on day 18 is told "When: Day 18 since the Fall (night)."; no fast-lane prompt says "years after the Fall" |

### 3.72 What they call them (P3; D-160)

| File | What it proves |
|---|---|
| `p03_perception/test_what_they_call_them.py` | One of the dead is known by its infected type (thing_ref); Owen, who holds what everyone says about walkers, sees "a walker" and what everyone says about them comes to mind; someone never told sees "a shambling figure" |

### 3.73 It missed; you saw it (P9; D-161, D-162)

| File | What it proves |
|---|---|
| `p09_society/test_it_missed.py` | Owen's shot at Mara misses: she trusts him 2 less, fears him 2 more and holds that he tried to kill her; Alice and June, who saw the gun raised, trust him less, fear him and tell it — as something they saw (provenance 'witnessed'); a shove that hurt nobody costs a little trust and some resentment, no grudge, no talk; a shot that landed is CAS-036's, one at someone who had gone for him first is nothing new; never into the player's character |

### 3.74 The door shut on them (P9; D-163)

| File | What it proves |
|---|---|
| `p09_society/test_the_door_shut.py` | June shuts the back door on Nita with one of the dead in the alley: Nita trusts her 2 less, resents her and holds it (strength 3); Mara, who loves Nita and saw it, trusts June less, resents it and tells it; Alice, who saw it but has no tie to Nita, nothing; locking the door after is the same act, not a second grudge; with no danger out there, shutting a door is nothing |

### 3.75 My way, words only (P7; D-164)

| File | What it proves |
|---|---|
| `p07_slice/test_my_way_words_only.py` | With "say it my way" on, a rewritten line keeps its words ("*shrugs* Fine. (looks away) Whatever." says "Fine. Whatever."); a line that is only a direction says what was typed; a line withheld is "Your character won't do that" and nothing is said |

### 3.76 How much (P4; D-165)

| File | What it proves |
|---|---|
| `p04_one_actor/test_how_much.py` | Feelings are worded by how far they went: "You do not trust them at all; you are terrified of them; you will not forgive them." against "You are wary of them; they make you uneasy; something they did still rankles."; contempt, hatred and debts likewise |

### 3.77 How they spoke (P4; D-166)

| File | What it proves |
|---|---|
| `p04_one_actor/test_how_they_spoke.py` | A heard line reads "spoke to you", "called out to you", "shouted to you" — never "spoke normal" or "spoke shout"; (D-168) the speaker is "(someone you know)", never "(peer)" |

### 3.78 Asked, then said why (P4; D-167)

| File | What it proves |
|---|---|
| `p04_one_actor/test_asked_then_said.py` | A question followed by a reason is a question ("you got any rounds to spare? I'm down to six."); a request or an order with a question in it stays a request or an order |

### 3.79 The world's words (P7; D-169)

| File | What it proves |
|---|---|
| `p07_slice/test_the_worlds_words.py` | The player typed "the back door into the alley"; the story's own line says "through the back door into the rear alley": those word runs are the narrator's to use, while the player's own "quick as a stray cat" stays blocked |

### 3.80 Of him (P7; D-170)

| File | What it proves |
|---|---|
| `p07_slice/test_of_him.py` | In a third-person story the PC's percepts reach the narrator told of him ("grabs at him", "his left arm"), quoted writing untouched; a second-person story keeps "you" |

### 3.81 Waking up (P7; D-171, D-172)

| File | What it proves |
|---|---|
| `p07_slice/test_waking_up.py` | After a quiet night "I get up" is a turn like any other: the menu is what he could do on waking, he wakes and stands, and the story is told "Owen woke after about 8 hours asleep." before "Owen chose to stand up."; lying down to sleep is told "Owen fell asleep.", from when the turn began to when it ended, with nobody seen and the story ending on him asleep; June asleep still decides nothing (her menu is not built waking) and out cold is never read as asleep |

### 3.82 Out cold (P7; D-173)

| File | What it proves |
|---|---|
| `p07_slice/test_out_cold.py` | June out cold at 32 % with the bleeding long stopped comes to at exactly the moment four hours of blood are back (comes_to_at, progress), where she lay, and the blood keeps coming back; not while a wound bleeds, and nothing comes back in the first hour after a wound; the player's character out cold: whatever is typed, no model is asked and he does nothing, the time passes until he comes to and the story says so; the view offers one chip, "Let the time pass", and pressing it plays the turn |

### 3.83 A wait is minutes; the Writer for what matters (P5, P7; D-174, D-175)

| File | What it proves |
|---|---|
| `p07_slice/test_a_wait_is_minutes.py` | "Wait" runs at most five minutes in a quiet place; watching still runs until something happens; an out-cold PC's window runs to `until`; three "I wait." turns are minutes each, not a day |
| `p05_many_actors/test_reactions_cascade_plan.py::test_plan_cognition_keeps_the_writer_for_what_matters` | Below the HOT threshold (and not mandatory) a mind is WARM on the fast lane; a mandatory mind is HOT whatever its salience |

### 3.84 News is new (P5; D-176)

| File | What it proves |
|---|---|
| `p05_many_actors/test_news_is_new.py` | Nita's first sight of the man in the lot is news; the same man the next turn is not; after she lost sight of him, seeing him again is |

### 3.85 What happens first, happens first (P7; D-177)

| File | What it proves |
|---|---|
| `p07_slice/test_what_happens_first.py` | A shout two seconds into a two-minute search closes the window seconds later; the search has not ended and waits in the queue for the player's next say; with nothing in the way, the search lands in the wave as before |

### 3.86 The place told of him (P7; D-178)

| File | What it proves |
|---|---|
| `p07_slice/test_the_place_told_of_him.py` | retell turns "You're alone." into "He's alone." / "I'm alone." / "They're alone.", "You've" into "He's", and keeps "You'll" / "You'd" as "He'll" / "I'd"; going out the garage's side door is told "Owen goes into the yard.", and the yard is described of him, with no "you" left in the place or the people |

### 3.87 Who it was (P9; D-179, D-180)

| File | What it proves |
|---|---|
| `p09_society/test_who_it_was.py` | The sentence names the one it was done to when there is a word for them ("Owen tried to kill Mara, who was not fighting."; "you" when it was the holder) and not otherwise; June, who saw Owen fire at Mara, believes it of Mara; Alice, told it by June, hears "someone"; (D-180) June, who loves Mara, trusts him two less and holds "Owen tried to kill Mara, someone you love." |

### 3.88 The way out is on the list; what the body wants (P4; D-181, D-182)

| File | What it proves |
|---|---|
| `p04_one_actor/test_the_way_out.py` | In the garage the side door to the yard is on the first menu, right after the nearest way out and before the ways to reach the car; creeping about the room is still offered |
| `p04_one_actor/test_what_the_body_wants.py` | (D-182) June exhausted sees sleep at the head of her waiting options; starving with jerky in her pocket, she is offered to eat it |

### 3.89 Rested, they wake (P7; D-183)

| File | What it proves |
|---|---|
| `p07_slice/test_rested_they_wake.py` | June, sixteen hours awake, sleeps eight and wakes rested at that moment (fatigue paid); a nap is at least an hour; the player's character is never woken this way (SLEEP-02) |

### 3.90 Seen spreading it (P9; D-186)

| File | What it proves |
|---|---|
| `p09_society/test_seen_spreading_it.py` | June watching Alice spit into sleeping Eli's mouth trusts her two less, fears her, and holds "Alice spat into the mouth of Eli while they slept."; Mara, his mother, holds a grudge that names him; the player's character holds nothing; spitting into the water is answered and told too |

### 3.91 The act is the sign (P9; D-187)

| File | What it proves |
|---|---|
| `p09_society/test_seen_spreading_it.py` | June, across the room, watching Alice spit into sleeping Eli's mouth has the `spreader_signs` cue and what she grew up hearing about the wet strain or the mouth rules comes to mind; Alice's own act is no sign to her; an ordinary act is no sign |

### 3.92 A law kept (P9; D-188)

| File | What it proves |
|---|---|
| `p09_society/test_a_law_kept.py` | Mae, who saw Hal bitten in Pumpwell's yard, holds the goal of the contamination quarantine in the law's own words; Otis in the shed holds nothing; Hal holds the fear of it; a second bite is the same law; with Owen bitten among his own, Mae means to see him quarantined and nothing is written into Owen; Hal seen spitting into sleeping Otis's mouth brings the law on both (Otis, asleep, does not know; Hal does), into the water on Hal alone |

### 3.93 Nothing new (P7; D-189, D-190, D-191, D-198, D-206)

| File | What it proves |
|---|---|
| `p07_slice/test_nothing_new.py` | After two quiet turns, whoever perceived nothing that was not there the turn before is not sent to be remembered, and everyone sent has something; a non-mandatory mind with salience 0 is COLD; a mind takes stock with a model every third turn; after Mara's "Quiet." and June's "What was that?", everyone who heard any of it — and June, who asked — takes it in the next turn; (D-191) a goal formed the turn before gives a decision this turn, and not once let go; (D-198) a pressing need gives salience; (D-206) spoken to, Mara does not decide before the words reach her, and a blow aimed at her still makes her decide at once |
| `p05_many_actors/test_reactions_cascade_plan.py` | (D-190) nothing at all for someone: no call |

### 3.94 Names called (P5; D-192, D-204, D-205)

| File | What it proves |
|---|---|
| `p05_many_actors/test_names_called.py` | "You're a whore, Mara.", "Go to hell, June.", "Eli, you're a waste of space." and the rest wound (TEMPER-03 'insulted'), "you’re" as a phone types it too; "Take the garbage out back.", "The water's filthy.", "Don't fool around." and other ordinary words do not; (D-204) spitting at June's feet or giving her the finger insults her and pointing does not, and she sees "Owen spits at your feet."; (D-205) given the finger with Mara watching she is worn down and resents him, alone she is not |

### 3.95 The mouth rules (P9; D-193, D-196, D-197, D-201)

| File | What it proves |
|---|---|
| `p09_society/test_mouth_rules.py` | Mara, beside June with a fresh bite in a lit room, has the bite_wound_seen cue, and both the wet strain's lore and the mouth rules come to mind; (D-196) her memory of it is written with that lore in its prompt, and read back raw from the store until it is; (D-197) Owen, beside her, has what he grew up hearing in the Writer's prompt the turn it first comes up, and not again the next turn; (D-201) a stranger who sees one of Delgado's crew recalls what survivors say about them, and the crew never think it of their own |

### 3.96 The same wrong again (P9; D-194)

| File | What it proves |
|---|---|
| `p09_society/test_the_same_wrong_again.py` | Alice, hit by Owen for nothing, resents him one more and holds "Owen hurt you, and you were not fighting them." at 2; hit again, she holds it at 3; the same blow swept twice deepens it once, and a third blow leaves it at 3 |

### 3.97 Kindness is remembered (P9; D-195, D-200)

| File | What it proves |
|---|---|
| `p09_society/test_kindness.py` | Owen's gift earns Mara's trust once a world day, and the next day's again; Mara's gift writes nothing into Owen; taking is not giving; June tending Alice's wound while she is awake earns one trust, one warmth and "June tended your wounds. You owe them.", the day's care counting once and the next day's deepening the debt; asleep she never knew who; tending yourself owes no one; (D-200) Alice, who saw June step in front of her, trusts her one more and feels one warmer, once a day; a turn spent shielding is worth remembering and a turn spent waiting is not |

### 3.98 No two voices alike in one place (P10; D-199, D-203)

| File | What it proves |
|---|---|
| `p10_world/test_no_two_voices_alike.py` | Thirty adults dealt voices in one place get thirty different voices; with every voice taken one is still drawn; the pools hold at least 40 adult voices and 10 for each other age, no two opening with the same line; nobody born after the Fall gets a voice that remembers before it; (D-203) a Ghost team made mid-game sounds like nobody in the Depot or among the Ghosts, and like none of each other |

### 3.99 A safety precaution (P9; D-202)

| File | What it proves |
|---|---|
| `p09_society/test_a_safety_precaution.py` | June, who saw Alice bitten, does not judge Owen for putting her down — trust kept, no story told — while Mara, who did not, sees a killing; June still grieves; seeing Alice spit into a sleeper's mouth is knowing too |

### 3.100 Pulled free (P9; D-207, D-211)

| File | What it proves |
|---|---|
| `p09_society/test_pulled_free.py` | One of the dead shot through the head lets go of Cal (the CONTROL_RELEASE caused by its DEATH); a holder asleep or out cold lets go; a holder who walks off lets go when the walk lands; letting go is an act; break_grip is offered only from a hand that is there and let_go only of someone held; a shove that knocks the holder down breaks its hold; one of the dead keeps hold of a corpse while it feeds and lets go when it is done; Cal, pulled out of the dead's hands by a stranger, trusts him two more, feels one warmer and owes him his life, and June, who loves Cal and saw it, trusts him one more; still in another hand is not saved; breaking free yourself owes nobody; out of a person's grip, the same debt; (D-211) June sees Cal "In the grip of a walker." as long as it holds him, Owen holding him sees "In your grip.", and once he is free nothing says grip |

### 3.101 Tied up (P9; D-208)

| File | What it proves |
|---|---|
| `p09_society/test_tied_up.py` | Mara awake and free cannot be tied (not offered; tried, she resists); held, asleep, or seen showing empty hands, she can; tied with the rope she has no free hands and cannot walk, the hand that held her lets go, June sees "hands and feet tied with a length of rope" (not "carrying" it) and Dale, at a distance, "tied up"; her first body line is "Your hands and feet are tied.", she can work at the knots and nothing that needs hands or legs, and Owen can untie her; someone held is told what has hold of them a turn later; untied by June she is free, the rope in June's hand, two trust, one warmth and a debt; untied by the man who tied her she owes nothing; working free takes seven three-minute tries in the room's seed and drops the rope at her feet; tied, she fears and resents Owen and holds it against him, and June, who saw her friend tied, trusts him one less; a tied corpse rises tied; the story's state lines open with what has hold of Owen, then that his hands and feet are tied |

### 3.102 Bringing things in (P12; D-209)

| File | What it proves |
|---|---|
| `p12_surfaces/test_importers.py` | A Word document's paragraphs, tabs and breaks come out as text; a card hidden in a PNG's tEXt or iTXt chunk is found, ccv3 over chara; a card becomes a draft person in `_drafts/` — name, what they know, depth from description and personality, three voice-line candidates from their own speech, every line of theirs in the example dialogue as an example with what was said first and by whom (the player's side never named; a line after her own has nobody speaking to her) — with what it lacks listed in plain language and its enabled lorebook entries as lore drafts; drafts never load and the `my_content` pack is made; the card in a picture the same; an item record comes in as canon, and the same file again overwrites nothing; a record that fails waits in `_drafts/` with the validator's lines; lore as JSON is written as `.md` and loads; documents go to intake; the Content screen's message passes the file through `_incoming/` and leaves nothing behind, refuses what is not base64, and writes nothing for a pack name that is not one |

### 3.103 A document becomes a record (P12; D-210)

| File | What it proves |
|---|---|
| `p12_surfaces/test_intake.py` | A short document is one section; headings start sections that join while they fit; a block too big is cut between paragraphs and a paragraph too big is cut hard; the Writer's field list names every field with its kind and description (never schema, id, generation, writers_notes); a two-section document makes one call per section, each seeing its own text and the field list, and merges into one draft — a filled field never overwritten, lists grown — with the model's conflicts and the missing fields listed and progress per section; a section the model fails is listed; lore comes out as a `.md` draft; an empty document calls nothing; the Content screen's message answers at once with the number of sections, then pushes progress and the result — a draft, never canon |

### 3.104 One search where many did (P3; D-212)

| File | What it proves |
|---|---|
| `p03_perception/test_one_search.py` | One sound-path search from a place gives, for every place, what a search for that place alone gives (every pair on metal_fence); the route search gives the same distance and the same portals as the search before D-212 (kept in the test) for every pair of bodies in different places on three scenarios; a request schema made once still gives every caller its own copy (enums set on one never reach another) |

### 3.105 Gone when you wake (P9; D-213)

| File | What it proves |
|---|---|
| `p09_society/test_gone_when_you_wake.py` | Mara, robbed in her sleep of the jerky in her pocket and the bottle in the pack on her back, wakes to "Your pack of jerky is gone." and "Your bottle of water is gone." and sets out to find out who — not knowing who; the same loss is found once; what she saw taken and what she moved herself are not gone; a slamming door that wakes her has her find it at once; the player's character finds it too, with nothing written into him |

### 3.106 Fed to the dead (P9; D-214)

| File | What it proves |
|---|---|
| `p09_society/test_fed_to_the_dead.py` | Ray shoves Cal to the dead in front of June, who loves him, and Nita, who does not: June loses three trust and holds a grudge for the shove itself, Nita two, the player's character nothing; the dead's first bite is Ray's — Cal, June and Nita answer it as an assault, though they saw the bite (they did not know he carried it when he was shoved), and the later bites are the dead's; Cal's death of it is Ray's killing — June's grudge for someone she loved, Nita's fear and her story, Ray's own burden; a bite three minutes on is nobody's |

### 3.107 Said to your face (P9; D-215)

| File | What it proves |
|---|---|
| `p09_society/test_said_to_your_face.py` | A promise of violence is a threat however it is put — sworn at, typed with a phone's apostrophe, "you're dead", "I'll break your arm" — and kind words, warnings and "I'll cut your hair" are not; Owen's bare-handed threat costs him a point of Alice's trust and a point of resentment, not her fear, once an hour however often he says it; after she saw him cut Mara it frightens her too; at gunpoint it is CAS-038's fear and CAS-089's trust, not CAS-090; a threat to the player's character changes nothing in him |

### 3.108 Word gets around (P9; D-216)

| File | What it proves |
|---|---|
| `p09_society/test_word_gets_around.py` | For every story of a wrong — hurt, tried to kill, shut out, pushed to the dead, a captive beaten or killed, one who gave up hit or killed, a child hurt or left, spit in a mouth or the food, a killing, eating the dead, a theft — Kit, told by Finn whom she believes, trusts Jude less by what the rule says (and fears him for spreading the sickness), while Finn, who saw it, is not changed by telling it; Amos, who does not believe Jude, is not changed; told to the player's character, nothing is written into him |

### 3.109 Word of a bite (P9; D-217)

| File | What it proves |
|---|---|
| `p09_society/test_word_of_a_bite.py` | June, who saw Alice bitten, carries the story — never Alice or Owen; Mara, told it by June, believes it and is afraid of Alice; Owen putting Alice down a minute later is a precaution to both of them; told only after he did it, Mara saw a killing |

### 3.110 Let them in (P9; D-218)

| File | What it proves |
|---|---|
| `p09_society/test_let_them_in.py` | June opens the back door with one of the dead in the alley and it walks in on Mara and Alice: both trust her two less, hold it against her and tell it — never June or Owen judging — and only the first of the dead through counts; Owen opening it is judged like anyone; opened for Nita, who comes in with the dead behind her, it is a rescue; six minutes on, or the living coming in, is nothing |

### 3.111 To your face (P9; D-219)

| File | What it proves |
|---|---|
| `p09_society/test_to_your_face.py` | Owen calls June a useless idiot with nobody else there: she resents him a point more, once an hour however often he says it, and again an hour on; ordinary words are nothing; with Mara on the floor it is the humiliation (CAS-042), not this; the finger or spitting at her alone counts, pointing does not; an insult to the player's character changes nothing in him |

### 3.112 Cast out (P9; D-220)

| File | What it proves |
|---|---|
| `p09_society/test_cast_out.py` | Finn cast out of Pumpwell: expelled from the settlers, out of his household, off the watch with his post left vacant, told he cannot stay, and everyone else set to keep him out — once; a standing that falls to -3 casts Jude out, and not before; the player's character can be cast out, with nothing written into him; hurting one of their own in front of them costs a point once a day; Jude cutting Finn's throat in front of Wade and Kit is the end of it; Tomas cast out leads no more |

### 3.113 A friend of yours (P9; D-221)

| File | What it proves |
|---|---|
| `p09_society/test_a_friend_of_yours.py` | June, a friend of Cal's (affection 1), holds "Ray shoved Cal, a friend of yours, to the dead."; loving him (affection 2), "Ray shoved Cal, someone you love, to the dead." |

### 3.114 Word of a death (P9; D-222)

| File | What it proves |
|---|---|
| `p09_society/test_word_of_a_death.py` | Mae, told by Finn that her husband Hal is dead, loses a point of Resolve (word_of_a_death); Kit, not close to him, nothing; told again by Kit, Mae grieves once; Hal told his daughter Pip is dead is broken (lost_dependent, CAS-030) and not drained twice; the player's character told it is not changed |

### 3.115 A hash that keeps up (P0; D-223)

| File | What it proves |
|---|---|
| `p00_substrate/test_hash_keeps_up.py` | After more events and an rng draw the carried-forward digest is used and both state hashes equal a cold reading; a turn rolled back after it was hashed, its rows then taken by other events, is not carried; different events still hash differently |

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
| `metal_fence.yaml` | P3–P7, P10, P11, sim | the anchor scene: store, storeroom, office, alley, street; PC, Mara, Alice, June, Eli, Nita, the stranger; the gust timer |
| `fence_climb.yaml` | P7 ("Actions fail") | a yard, a 250 cm fence (obstacle class 5), Owen at its foot, a neighbour (stub) watching from the porch; the seed fails the first check |
| `three_rooms_gunshot.yaml` | SKULL-01/04 | Room 1 (A with a pistol), Room 2 behind brick (B), Room 3 two walls away (C asleep) |
| `crowd_accusation.yaml` | CROWD-01..05 | one open hall, PC + 8 listeners at varied distances, one observer 25 m away |
| `request_firewall.yaml` | WILL-01..09, P7 refusal slice | Mara mid-task with Eli asleep nearby; a stranger; Mara's commander; a porch outside the open front door |
| `empty_gun.yaml` | INTENT-03, HALLUC-01 | Reggie with an unloaded pistol facing Carl (a stub debtor); a believed-but-gone crowbar |
| `pump_settlement.yaml` | P9 ECON-01, SOC-02, SOC-03 | a 24-person settlement (Pumpwell) with a water pump on two 12-hour shifts, a kitchen, a watch rota, twelve households with children and elders, laws, a quartermaster, and a feud (Jude and Amos) |
| `two_skills.yaml` | WILL-03 | two identical Actors differing only in skills and Resolve, same room, same items |

Fixture packs (`tests/fixtures/packs/`): `p10_hopeless` holds one character, Hal Brandt, whose
hard-fail condition every world meets, so wherever the plausibility check applies (Bitch Mode
through Realism) his start is refused plainly, and above it the world is made (WG-14, D-47).

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
- `tests/fixtures/vectors/acoustics.json`, `checks.json`, `optics.json`: hand-computed expected
  values for the pure formulas (each entry shows its arithmetic in a `why` field).
- `tests/fixtures/vectors/params.json`, `region.json` (P10): WG0 and WG1 draw for draw for fixed
  seeds, so a mismatch names the first wrong draw.
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

`tests/contract/p11_audits/test_commit_gate_bits.py` plays the night at Delgado's for two turns and
asserts all 58 bits are 1. Then, for each bit, on a fresh copy of that world, it applies exactly
one fault from `FAULTS[bit_id]` — written straight into the database with foreign keys off, the
way a bug would leave it (e.g. `W08`: a portal open and barricaded) — recomputes the gate and
asserts that **exactly that bit** dropped and no other. A bit whose fault does not drop it, or
drops a different bit, fails the test: a check that cannot fail is not a check. It also pins
`BIT_STAGE` (AUDIT-03): every bit names the pipeline stage that writes what it checks, never 12.

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
- `tools/as/bench.py`: the limits bench (08 §7, D-112) → `reports/bench.json` and `bench.md`; `--accept` writes the settings.
- `tools/as/eval.py --scenario metal_fence --turns 10 [--ablate <call_class>] [--fake]`: plays with
  real models (or the fake one) and reports the measures in its docstring. With --ablate it plays
  plain and with that call class switched off (LANE-09) and names what changed; a class whose
  ablation changes nothing measurable is a removal candidate — the plan's ablation duty (08 §4).
- `audit.release.release_audit(config, run_id, days=30)`: the release audit on a generated run
  (REL-01..06) — run it on a world the fake made and on one your models made, before a release.
