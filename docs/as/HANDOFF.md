# HANDOFF — state of the kit (read before continuing: the Actor v2 amendments, P11, P12)

This file is for whoever continues writing the kit (a person or another model). It says exactly
what is finished, what is half-finished and what does not exist yet. It is not a build document for
the DSH builder; delete it when P12 ships.

## 0. Where the kit stands

**The engine is built through P10 and committed**, and so is everything specified since (owner,
2026-09-24: "Commit all of your working code"; 2026-09-25: "If you're making implementations,
throw them into the final system, don't waste compute."). The bodies are the `_impl_*.py` files
bound at the end of each contract module (AGENTS.md §4), plus the modules built in place. Built:
P0–P10, the sim soak, Actor v2 B1–B6 (D-87..D-93) and the owner's F1a, F1b, H1, I1, W1 and F1c
(D-77, D-80, D-82..D-86, D-94: F1a-2 too). Every engine contract test passes except the seven D-76 items (the
sessions browser and a world that names no run), which the DSH builder builds. The P10 screens of
the Play UI are in `talemate_frontend/src/play/`; the P8 screens, the Talemate plugin and the
frontend toolchain are not built — the DSH builder builds them (13_BUILD_ORDER §4.0).

**From here on the kit-maker writes contracts, tests, docs — and, where it implements to prove
them, the implementation itself, committed with them** (the owner's 2026-09-25 instruction
replaces "the rest will remain uncoded"). What is left:
1. **Actor v2** — B6 is BUILT (D-93; tests 12 §3.15: work output gated by machinery and inputs,
   a boiling-over feud becomes a grudge the person decides about, far sounds are heard, the
   witnessed-theft rumour fires). Left: Actor Spec §12's plans with stable keys and delegation (a
   leader's orders the recipient decides on) and §11's conversations.
2. **P11** — the audits (§5).
3. **P12** — the surfaces (§5), with the **full cheat system** the owner described: overwriting an
   Actor's will, wiping a memory, giving one Top-Hat the wet strain remotely in the middle of a
   council meeting (`factions.in_session`), horde and Mega Horde cheats, census inspection — all
   inside the simulation (every cheat is an event with a cause; a cheated run is Sandbox forever).
4. **The sessions browser and the hard delete** — SPECIFIED (D-76, RUN-12, RUN-13): the Your lives
   screen (P8), `service/runs.wipe_tree`, the one-step delete, a world that names no run (P10), logs
   that name no session; tests in p08 `test_sessions.py`, p10 `test_world_names_no_run.py`, vitest
   `sessions.spec.js`.
5. **The final pass** — docs coherence, RULES regenerated, the manifest, the handoff.
Owner requirements queued (2026-09-24, in the owner's words where it matters; specify in this order):
- **Appearance, smell, condition, clothing** (new senses work, amends P2 bodies/items, P3 perception, P4 packet
  and cues, P10 infected): everyone and everything has a visual identity in high detail (hair, faces, marks,
  clothes in layers and slots with state, insignia; concealment under layers) that people read to judge each
  other — "never judge a book by its cover is a bold-faced lie". Smell is a real sense (sources, distance,
  wind, rooms; you get used to your own). Grime / blood / gore on body and clothes; washing and changing.
  Gore camouflage works on ordinary infected (CODEX: not on Lurkers, by heat) at an infection-exposure cost,
  and people avoid you until you wash. Nakedness: exposure and no protection, and a shock to most people —
  strictly non-sexual.
  **F1a is BUILT** (D-82, LOOK-01..06, CNT-17; tests
  12 §3.5): looks, clothing items and the outfit, condition columns and `soil`, what a look shows at each
  distance and light, the glance cues, the packet line, the PC dressed at the opening; the thirteen core
  people and Fredrick have looks. **F1b is BUILT** (D-83, SMELL-01..06, INF-14): smell as a people's sense
  (the dead, death, blood, sweat and dirt; range by strength, halved in the open air, never your own; with the
  look for someone seen, one smell per kind unseen; smell cues) and gore camouflage against the common dead (the
  lore's "they smell you" stays false). **F1c is BUILT** (D-86, LOOK-07..09, TEMPER-09; 07 §4.2; 13
  §4.0 step 1; tests 12 §3.9): wounds, blows, treating and butchering bloody people; days unwashed make
  them grimy; rain soaks them and rinses the gore off; a wash takes water, a wipe less; smearing on the
  dead carries the strain; clothes come off, go on and off people who cannot stop you, never a child's;
  clothes keep people warm and the cold can kill; the reek of the dead and a naked adult in sight wear on
  people; settlements have a decency law. **F1a-2 is BUILT** (D-94; tests 12 §3.16): generated people get looks
  and clothes for their climate, and the narrator and the Play UI's people chips show how people
  look and smell.
- **Human people** (the owner: smart, but human smart; everybody has a breaking point; bickering,
  brawls, betrayal). **H1 is BUILT** (D-84, TEMPER-01..08, LOOP-07, STL-15; 05 §7.1; 13 §4.0 step
  1; tests 12 §3.6): stress that deaths, hunger and blows build and sleep eases; a temper per person on
  their card; heat toward whoever provoked them, fading, kept warm by grudges; the packet says how close
  they are and how they feel about each person; the snap by outlet (a punch past their own nerve, having
  it out out loud, walking out, breaking down) with a grudge after; rows and fights in settlements
  off-screen; shoving someone to the dead and the leg shot, with the trust, the talk and the grudge they
  cost; all fourteen people have tempers, generated people get varied ones, and every settlement
  has its feud.
- **The dead feed** (the owner: eaten alive, anything that moves, tainted meat and water, graphic).
  **I1 is BUILT** (D-85, INF-15..19; 06 §5.2; 13 §4.0 step 1; tests 12 §3.7): once they have you
  they never let go, never the head or neck, the scream brings the rest, they stay on the dead, the
  devoured never rise, nothing draws a feeder off; six animals as prey (never infected); lasting
  taint in water near a feeding and in meat from what they fed on; butchering; witness stress; the
  narrator writes it without looking away, and never a child's body.
- **The wet strain as the owner told it. W1 is BUILT** (D-77, D-80; 06 §5.4; tests 12 §3.8): every
  fluid from day three, and the dead's; blood on the hands that treat, blood in the eyes from a blow;
  the urge to contaminate (a sleeper's mouth, the bottle handed over, water and food spat into) that
  grows ever more often and sickens the host; the player's hand taken now and then from week three,
  and the story says so; week-three hosts seen by the dead at half range.
- **Group dynamics with weight** (step 6 expanded): witnessed grave harm (scaled by what was seen: unarmed,
  captive, surrendering, a child, their own member) becomes rumour, group standing, tension, loyalty checks,
  a settlement's law response, reputation that travels; the player's character pays for crossing their own
  values (nerve, intrusive memories, sleep). The owner intends to push atrocity edge cases: the world must
  answer with Authentic Suffering, never a lecture.
- **Conversations** (steps 4-5, Actor Spec §11): per-person threads, topics, initiative, interruptions,
  group talk, distinct voices.
- **Willis / the cheat cure** (D-78, D-79) — with P12's cheat system.


## 1. How the kit is made (the method to keep using)

Per slice: design → contract docstrings in `as_engine/src/as_engine/**` (the docstring IS the
spec) → protected contract tests in `as_engine/tests/contract/p<nn>_<name>/` → the implementation,
in the repo (the `_impl_*.py` beside the module, or in place; owner 2026-09-25: never throw a
working implementation away) → docs (`docs/as/*`) → `tools/as/gate.py --docstrings --write-rules
--scan`, `tools/as/protect.py --write-manifest` → the full suite green once before the commit.
Work that is only specified (a function still raising `NotImplementedError`) is named in
13_BUILD_ORDER §4.0 for the builder. Then **play it**: a generated world played through the
service found faults no contract test had (§3.2).

Standing rules (from the owner, all still in force):
- Never change the version number of any document or system without explicit instruction
  (SCHEMA_VERSION was NOT bumped for the P9 or P10 schema columns — DECISIONS D-38, D-50).
- Check the work before delivering it. Do not produce documents nobody asked for.
- `.cmd` downloads fail for the owner; deliver `.zip` or `.txt`.
- Codex_Master_Guide may only be edited with the owner's permission (pending requests below).
- No sexual or romantic content involving minors anywhere (content check CNT-11 is protected).
- The kit-maker writes no more implementation (the owner, 2026-09-24): contracts, tests, docs only.

Merge rule for patches (the owner's builder has already filled P0–P9 bodies): insert new functions
BEFORE an existing `def` line, never directly after a body the builder wrote; do not change a
signature on the line next to a built body. Simulate the merge: take the previous delivery's repo,
replace every `raise NotImplementedError("P0".."P9")` with a dummy body, commit, `git apply --3way`
the new patch.

## 2. Test command

```
cd as_engine
PYTHONPATH=src python3 -m pytest tests -q -p no:randomly \
  -o addopts="-p no:cacheprovider --import-mode=importlib -m 'not live'"
```
Every engine test passes on the committed engine (the count is in README_FIRST §1); a new contract
test for an unbuilt function fails with NotImplementedError until the builder writes it. The UI
specs run with vitest once the builder has installed the toolchain (P8 step 5); the P10 specs pass
on the committed P10 screens.

## 3. P10 — how it was verified

### 3.1 Tests and sweeps
- `p10_world`: 231 test functions (268 tests) over a session world generated on the fake model,
  plus the hand-made scenarios; every new test was mutation-checked against the reference (a
  deliberate fault in the code it pins makes it fail).
- Every seed 1–40 builds a world at the smallest tier; openings swept over seeds 1–12.
- Earlier protected tests changed in P10: `p02 test_bodies.py` (DEATH `rise_pending`),
  `p08 protocol_kit.py` (the bar's messages), and the play-through tests below.

### 3.2 The play-through (DECISIONS D-63..D-69)
Playing moves in generated worlds through `GameService` found what the contract tests had not:
- a turn failed ("Something went wrong") because a reaction was shown a percept 0.7 s in its
  future — SKULL-10: a mind decides on what it had perceived by its own moment;
- every building met its street at one point, so the opening's dead reached the player in ten
  seconds — WG1 street frontages;
- a watch lasted eight hours with the dead standing beside the player — REACT-01 counts the dead
  coming within 20 m; standing still to watch, wait, guard, hide or talk is not movement to a
  Shambler (INF-02 `STILL_VERBS`);
- the menu offered "Talk a shambling figure down" and "Close the way to the Trujillo house", three
  identical axe chips, "the the Trujillo house", "moves away" for the dead coming, and a dice
  receipt that crashed the view on a defence — `requires.target_kinds` / `portal_kinds`, the
  speech and wound bindings, `place_phrase`, the MOVE wording, the receipt's "Resisting grab", no
  two suggestions alike;
- the Mega Horde next to a living player only ever grew in bodies (2,880 in its first hour, 6,720
  in its second) and a day of it ran for over ten minutes — HRD-18 `fold` (fidelity F04 demotion:
  an anonymous, unhurt body out of contact goes back into its count), SEL-01's 10-minute memory for
  loud noises, and a milling crowd's bodies stand where they are shown (D-67, D-68): now 640 bodies
  and about 3 s for the day;
- the dead drawn to one road walked down another and back first, because a hub's roads all meet at
  its centre and the tie went to the lowest portal id — a route enters each place at most once
  (`physical.space.path`, D-69).
`test_new_life.py::test_a_generated_world_plays` now plays such moves in the session world through
the 58-bit gate. Keep doing this for every phase: build a world, play it, read what the screen says.

### 3.3 Delivery (R9)
- Full kit: `AS_build_kit_p10.zip` (folder `as-kit/`), made from the committed kit files only. The
  zip also carries the kit's `.claude/settings.json` (the hooks for the per-workspace bridge,
  README_FIRST §4); it is added from the kit copy when zipping and never committed here (its hooks
  would block the maintainer's own session). Checked unzipped: `protect.py --verify`, `gate.py
  --docstrings` and `--scan` pass, and the tests pass against the unzipped reference.
- Reference: `AS_p10_scratch_reference.zip` (`ref2/`, `sync_ref.sh`, `ref_impl_files.txt`,
  `promises.md`, `ui/`) — for the owner and whoever writes the kit, never for the builder.
- **Update patch vs the P9 delivery: needs the P9 delivery zip**, which is not in this environment.
  With it: diff the P9 kit against this one, simulate the merge (§1), unzip-test. Ask the owner.

## 4. Open ends carried forward

- Identical descriptions in an Actor's packet: three of the dead read "a shambling figure" and the
  model tells them apart only by order (nearest first). The suggestions dedupe covers the player's
  chips; the Actor v2 identity work (AC01–AC16) is the place to give bodies distinguishing words.
- A shambler that arrives where a still player stands does not notice them (motion sight) and waits
  there until something draws it. That is the rule as written (INF-02, D-65); the owner may want a
  touch or smell sense at arm's length — a content/rules question, not a bug.
- Hostile-human openings do nothing with the fake model (it keeps everyone waiting); with real
  models the raiders decide. The live suite should play one.

## 5. P11 and P12 — NOT STARTED at contract level

**P11 Audits** (13_BUILD_ORDER §4): every commit-gate bit exactly as described with BIT_STAGE per
bit; `audit/portrayal.py` (targeted pre-check + retrospective); `audit/abuse.py`;
`narration/style.py`; `tools/as/eval.py --ablate`. Test `p11_audits/test_commit_gate_bits.py`
(AUDIT-02: each of the 58 injected faults drops exactly its bit) is the key test. Also carried here
from P10: the release audit re-runs `checks.assert_world` on the genesis snapshot (D-45), checks the
census conservation (HRD-15: the dead change only by rising and destruction), and fails a build that
still records `timer_unbuilt` / `cascade_unbuilt`. (No trace ratio: C11 retired the quota, D-52.)

**P12 Surfaces**: `cheats/commands.py` + GameService routing + the `cheat_admin` pack (CHEATS.md —
the owner's "bonus dev-cheats" document, extended with the owner's session-8 asks in §0);
`content/importers.py` (files, character cards, docx, dossier intake); `service/death.py` (death
screen, new life here); worlds (list / export / import, `create_run(world_id=…)` from
`_worlds/<id>/genesis.sqlite`); the sessions browser and hard delete; the migration framework
(`kernel/migrations/`, consent flow); read-aloud via Talemate TTS; the time-skip bar (PLANS
'time_skip' exists); final CNT-11 check across all content; the play-UI smoke checklist §8.

## 5A. "Ready to build" — the definition

A phase is READY TO BUILD when the DSH builder, given only the kit, can implement it and prove it
without asking anyone. For every phase that means nine things exist and agree with each other:

| # | Artifact | Where |
|---|---|---|
| R1 | Contract docstrings for every function the phase builds: inputs, outputs, every rule, every error, exact event types and payloads, rng streams and purposes, row shapes. Bodies stay `raise NotImplementedError("P<n>")` | `as_engine/src/as_engine/**` |
| R2 | Protected contract tests that fail on the stubs and pass on a correct build | `as_engine/tests/contract/p<nn>_*/` |
| R3 | Fixtures the tests need (scenarios, packs, fake-model scripts, vectors) | `as_engine/tests/fixtures/`, `testing/fake_lm.py` |
| R4 | Proof: until P10 a scratch reference passed R2 and every earlier phase's tests. From now on no implementation is written: each test is reviewed line by line against its docstring, every earlier test still passes on the committed engine (a new test of a built function must pass on it), and the builder files SPEC_ISSUES for anything inconsistent | the review; the suite |
| R5 | Design docs rewritten to match R1 (the docs explain; the docstrings rule) | `docs/as/0x_*.md` |
| R6 | The phase's task list, gate and forbidden list in `13_BUILD_ORDER.md` §4, in build order | docs |
| R7 | Records: DECISIONS rows, CHANGELOG row, GLOSSARY terms, RULES.md regenerated, PROGRESS row, SPEC_ISSUES for anything left open | docs |
| R8 | Tooling passes: `gate.py --docstrings --scan --write-rules`, `protect.py --write-manifest` then `--verify`, lines <= 100 | `tools/as/` |
| R9 | Delivery: full-kit zip + patch zip vs the previous delivery, merge-simulated against a built previous phase, fresh-unzip test run | outputs |

### P11 — Audits (nothing below exists yet)
R1 contracts to write:
- `audit/commit_gate.py`: every one of the 58 bits already has a one-line check; each needs the
  exact query, what "this turn" means for it, its BIT_STAGE (the stage to rerun), and its fault
  (the single DB edit that must drop exactly that bit). Genesis rules for generated worlds (P10).
- `audit/portrayal.py`: `precheck(...)` (before commit, which actors, prompt context, verdict model,
  regenerate-once flow) and `retrospective(...)`; the PortrayalAudit context and answer models; the
  judge-call-id ≠ producer-call-id rule; what is logged.
- `audit/abuse.py`: one function per ABUSE-01..08 with inputs, pass condition and plain failure text.
- `narration/style.py`: load / save / update_after_turn (noun-phrase extraction exact enough to
  test); wire into narrator packet (images not to reuse) — the anti-repetition the owner asked for.
- Release audit (new module, e.g. `audit/release.py`): re-run `checks.assert_world` on genesis,
  census conservation over a long off-screen run (HRD-15), no `timer_unbuilt` / `cascade_unbuilt`
  rows, CNT-11 over all content, soak statistics. (No trace-ratio check: D-52.)
- `tools/as/eval.py --ablate`: which call classes, what is measured, pass thresholds.
R2 tests: `p11_audits/test_commit_gate_bits.py` (58 parametrised faults, each drops exactly one
bit — AUDIT-02, the most important test in the suite), portrayal flow with scripted verdicts,
abuse battery on clean + deliberately broken worlds, style persistence across save/load, release
audit on a generated world, eval ablation smoke run.
R3–R9 as above; docs 04 §3.3/§5, 07, 12, CHANGELOG, DECISIONS.

### P12 — Surfaces (stubs exist; contracts not finished)
R1 contracts to write or finish:
- `cheats/commands.py` (a draft exists): every command's exact effects, events, refusals and persona
  lines; GameService routing (turn_submit with the 2508 token, /commands); the `cheat_admin` pack
  (dossiers such as 'fredrick'); sandbox save rules (CHEAT-02); CHEAT-03 (no cheat words in any
  narrator/actor prompt). The owner's additions (§0 item 3): a will overwrite (what the Actor then
  wants, how it is recorded, what others notice), a memory wipe (which episodes, beliefs, loops go;
  what a reflection makes of the gap), a remote infection of a named person wherever they are (a
  council in session included), horde / Mega Horde commands, census inspection. `docs/as/CHEATS.md`
  is the owner's bonus document — keep it and the contract identical.
- `content/importers.py` (draft exists): import_file per format, character-card mapping, docx
  extraction, intake_document chunk/merge/validate, ImportResult / IntakeJob, progress pushes.
- `service/death.py` (sketch): DeathView model, cause-chain rendering, last turns, contributing
  choices, truth_reveal after explicit click (DEATH-10), new-life-here flow.
- Worlds: `service/runs.py` list_worlds / export / import / `create_run(world_id=…)` from
  `_worlds/<id>/genesis.sqlite` (RUN-09); the world.json format is fixed by P10.
- Sessions: a list of every session ever played and an unrecoverable delete (RUN-06 amended: the
  run folder and every file in it, the world's genesis when no other run or saved world uses it,
  per-run logs only ever written inside the run folder, `secure_delete` on the run's databases,
  the UI's cached story cleared; one plain confirmation).
- Migrations: new `kernel/migrations/` package — registry, per-version step, consent flow, backup
  before migrating (version numbers change only on the owner's instruction).
- Read-aloud via Talemate TTS: which text, when, settings switch.
- GameService P12 handlers (content_import, intake_start, quickmake_pc, death_reveal,
  new_life_here, worlds_list, world_export, world_import, on_death, the sessions browser) and
  their protocol models.
R2 tests: `p12_surfaces/` for each item; UI vitest for death, imports, cheats, worlds and sessions.
R3: sample character card (png + json), sample docx, cheat pack, a world export file.
R4–R9 as above, plus the final whole-kit verification: full suite, CNT-11 over every pack, the
play-UI smoke checklist §8, and the last full zip.

## 6. Requests still waiting for the owner

- The **P9 delivery zip** (the one the builder unpacked for P9), to build and merge-test the P10
  update patch (§3.3).
- Permission to note goals/issues in `Codex_Master_Guide` (asked earlier; not edited).
- Review `SPEC_ISSUES.md`.
