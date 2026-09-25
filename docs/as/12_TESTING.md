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
