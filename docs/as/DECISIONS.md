# DECISIONS

What this spec decided, what it changed from its sources, and why. Nothing is silently changed:
if it differs from the Rebuild Plan or the Codex Master Guide, it is here. The builder does not
add to this file; the human does (via `SPEC_ISSUES.md` → resolution).

Status words: **Answered** (you said so), **Decided** (the spec chose — confirm or change it),
**Carried** (an earlier ruling of yours, applied here).

## 1. The Rebuild Plan's open decisions (§19)

| # | Question | Status | Resolution |
|---|---|---|---|
| O1 | Model per lane | **Answered** | Lane A = Nemotron Cascade 2 30B-A3B (desktop), Lane B = Nemotron 3.5 Lightning 30B-A3B (laptop), fixed per session (LANE-05). Qwen-27B is not used. |
| O2 | Turn budget | **Decided** | Player setting "Turn depth": Quick 40 s / Balanced 75 s (default) / Deep 150 s, with a visible progress bar and honest stage labels. Mandatory people always think, even past budget. Deep = 3 deep thinkers, matching your earlier "5 NPCs per turn, 3 with thinking" design. |
| O3 | Is Addison the PC? | **Decided** (your new request supersedes "only one PC") | Addison ships as a playable character, one of three. You choose (or import, or quick-make) a character every run. When she is not the PC she is not placed in the world (her dossier is a PC dossier); copy her into `actors/` if you want her as an Actor. |
| O4 | Ghosts and the existing lore corpus | **Carried** ("I want the satisfaction of dumping the Ghost doc in") | The core pack ships the canon infected, contamination culture, the Mafia Remnants and a faction template — **no Ghost faction**. The dossier-intake mechanism is built to completion so you can feed the Ghost corpus in yourself. Worlds are generated fresh per run from whatever packs are loaded. |
| O5 | Resolve formula | **Decided** | `3 + floor((E+C)/4) + trait_mod`, drains/recoveries as in 05 §5, all in `RulesConfig.resolve`, tagged `[SAND]` and calibrated by `tools/as/eval.py` (BENCH-03). |
| O6 | ASL save a strict subset of AS | **Decided: yes** | Names, units, id formats and event type names are shared; nothing may be renamed without an entry here. The ASL importer itself is not in v1's build order (D-10). |
| O7 | 2508 in two systems | **Decided** | AS has no author-instruction channel (the Workshop UI is the author channel), so `2508` is only the cheat token. |
| O8 | Dev/debug surface | **Decided: yes** | Developer mode setting → Developer panel (stage timeline, options and choices, events, gate bits, raw model traffic). Logs are also always written to `as_runs/<run>/logs/`. |

## 2. Deviations from the Rebuild Plan

| Id | Plan says | This spec does | Why |
|---|---|---|---|
| D-01 | Engine-agnostic module map; agent division Claude Code (Opus 5) + GPT 6 Astra with two-agent review on load-bearing surfaces | Built as a fork of **Talemate 0.39.0** (host: install, server, frontend, TTS) with the game in a separate pure-Python package `as_engine`; built by a coding agent in **DeepSeek Harness (DSH)** on your local LM Studio models (changed from OpenHands on 2026-09-22 at your instruction). Two-agent review becomes: protected contract tests + the gate script + your review of `SPEC_ISSUES.md` | Your instruction; Talemate's shared scene history breaks Skull Law, so its story loop is replaced, not reused (02 §1) |
| D-02 | P8 Society, P9 Wide world, P10 Narration, P11 Audits, P12 Surfaces | P7 includes core narration (the slice must be playable, which needs prose); **P8 = Play UI**; P9 Society; P10 Wide world; P11 Audits + narrator continuity; P12 Surfaces | You can play and judge the slice right after P7/P8 instead of after P12 |
| D-03 | GBNF compiled from schemas | LM Studio `response_format: json_schema` (LM Studio compiles it to a grammar internally) with dynamic enums; when a lane cannot combine a schema with thinking, extract JSON from text and allow one repair call with the schema | Same constraint (a model can only choose offered handles), no custom grammar compiler to maintain |
| D-04 | P1 gate: every `[SAND]` latency number replaced by measurement | The builder's sandbox cannot reach your machines. `tools/as/bench.py` is built and tested against the fake; **you** run it on the desktop+laptop and accept the numbers; phases stay green with "SAND remaining" listed | Honest about where measurements can happen |
| D-05 | IRONCLAD "concrete noun + verb share ≥ 0.6" | Replaced by an abstract-word ratio ≤ 3 % from a content word list | The original needs a part-of-speech tagger; the engine stays dependency-free |
| D-06 | `grant()` single writer enforced by a DB trigger | Enforced by a `CHECK (granted_by = 'perception.grant')` column rule + ownership (only `mind.perception` may write `percept_log`/`claim_holdings`) + the import-boundary test; the event log gets append-only triggers | Same guarantee, simpler to test |
| D-07 | Portrayal audit before commit; failure regenerates the intent | **Targeted** pre-check before the barrier only for high-stakes choices (moral-tagged options, attacks, responses to valid orders); all other audits run after commit and feed a portrayal note into that person's next packet | An audit per person per turn on the critical path would add ~2.6 s each on the laptop lane |
| D-08 | "v4 ships 64 regression tests; all 64 carry forward" | The 64-test list is not in this project's files. Their families (transaction integrity, time, space/portals, finite populations, LOD, profiles) are covered by STORE/DET/TIME/GEO/CONSERVE/LOD/DOS contract tests | Request: drop the v4 test list into `docs/as/reference/` if you want a verbatim one-to-one carry (SPEC_ISSUES SI-001) |
| D-09 | MIG-01: a v4 `CODEX-4.0` save imports with backfill flags | The migration framework (diagnose → report → consent → backfill events) is built in P12 for AS schema changes; importing `CODEX-4.0` saves waits for a sample save | No sample save exists in the project (SI-002) |
| D-10 | ASL ↔ AS import (§20.3) | Naming discipline kept; the importer is deferred | ASL has not been built yet |
| D-11 | One condition model incl. vehicles | The `conditions` table supports vehicles/structures; driving and vehicle travel are not in v1 | Scope; Addison cannot drive anyway (locked fact) |
| D-12 | — | Ironman death ends that run (no load, no new life in it); free mode keeps load and "new life here" | Carries your Codex Ultima ruling "death is permadeath" as the Ironman rule, while honouring per-run settings |
| D-13 | Seeded, reproducible worlds | Worlds are **files**: every generated world keeps a genesis snapshot; export/import `.asworld` | Carries your BaselineWorldFile ruling: model-written worldgen text is not reproducible from a seed |
| D-14 | "Without the document there is nothing to type that parses" | Nothing in the **game** reveals the token, grammar or persona; the source code necessarily contains the parser. Before activation, `/commands` are ordinary input | An app must contain its own parser; secrecy is a property of the play surface (CHEAT-03) |
| D-15 | Cheat table: Codex gives the tell; CMG §40/§44 sovereign authority, 100-day horizon | UI shimmer gives the tell; no narrator-god, no death timer, no fiat kill | The AS narrator is the PC's skull (L9); your Harness rulings retired the 100-day clock and sovereign termination |
| D-16 | Portrayal "atomic out-of-character scoring thresholds" (CMG §37 open policy) | Three-level verdict (fits / doubtful / out of character); only "out of character" regenerates | Simple, testable; tune with eval data |
| D-17 | Scenes paced by beats with pivot decisions (CMG §40) | Scenes open/close by code conditions (arrival, first contact, threat, resolution, chunk max); no beat graph or pivot authoring | A beat graph is authored story; AS forbids pre-scripting outcomes (WG-30, NARR-04) |
| D-18 | Era is a free choice for any PC (CMG §61 Part III) | A dossier may carry `days_since_fall_range`; the wizard only offers eras and world ages the character's age and history fit, and worldgen skips authored Actors who do not fit (WG-34). Addison: 9–11 years (Mature only) | Her locked facts (age 20, parkour since about ten, "started collapse at ~10") make an Early-era Addison a contradiction the engine would otherwise create silently |
| D-19 | Active area = the PC's place + places within 2 portal hops (§10.3) | The same, plus — for every noise of 80 dB or more this turn — its place and the places one hop from it (`turn/select.active_area`) | A crash at the edge of the area would otherwise leave the man standing beside it deaf to it (the stranger behind the fence in the anchor scene) |
| D-20 | "Keep watching" ends at a material percept (condition-ended actions only) | Every PC action: when the PC perceives something material, the window closes 3 s later — never before an event already committed; a longer action of the PC stays under way and continues if chosen again (`turn/select.pull`) | The player answers what matters to the PC; nothing that already happened is undone |
| D-21 | Replay returns recorded calls in call order | A recorded call is found by its request hash (the first unused row of that turn with that hash); a recorded timeout or lane error replays as the same failure (DET-03, P1 docstring amended in the P7 kit) | Concurrent calls on two lanes finish in any order, so position is not stable; the question asked is |
| D-22 | Scenes open/close on arrival, contact, threat, resolution, chunk max | P7: a scene is the PC's stay in one place (arrival opens, leaving closes); contact/threat/resolution/chunk max, passive-scene failsafe and scene summaries arrive with P11 | The slice needs scene boundaries for the refusal pivot; the rest needs the audit phase |
| D-23 | — | After each wave, code reads how every mind — the PC too — answered the asks it had heard before deciding: refusals and false compliance are recorded by the firewall; the model is never told it "refused" (`turn/cognition.record_responses`) | L6/L7 applied symmetrically (L12): the world remembers a player's refusal as it remembers an Actor's |
| D-24 | The plugin awaits `GameService.handle` for every message | A turn runs as a background task; `turn_submit` answers "busy" at once and progress, the result and the story are pushed to every subscribed connection; view and story asked for mid-turn answer with the moment before the turn (PROTO-04, PROTO-05) | Talemate reads a connection's messages one at a time and awaits each handler, so an awaited turn would block Stop and every other message for minutes |
| D-25 | The UI protocol lists every action from P8 | Actions of later phases (run_new, worldgen_cancel, pcs_list: P10; imports, intake, quick-make, death, new life here, worlds: P12) answer `not_built_yet` until their phase; the Play UI shows a "later" screen for the wizard, worldgen, death and worlds; in P8 a run is made with `as-engine new-scenario` (PROTO-09) | The UI shows what the engine already does (13 P8), and the human can play the slice from P8 |
| D-26 | Settings → Models edits "lanes/regimes" | `config_set` takes only the lanes (name, address, model, concurrency, timeout) and background thinking; regimes stay in the file (PROTO-10) | A regime changes every later request's hash, and replay finds recorded answers by that hash (D-21) |
| D-27 | Mid-run settings changes had no protocol action | `settings_get` / `settings_set`: one `SETTINGS_CHANGE {field, old, new}` per changed field (`service/session.change_settings`); re-simulation re-applies them between the same turns (SET-01) | 11 §1.2 lets a running game change them, and "replay reproduces it" needed an owner |
| D-28 | Ask answered by GUIDE with the PC's knowledge | `service/guide.py` builds the guide's context only from the play view already on screen plus plain rules summaries chosen by the question's words; the answer and the question join the story; nothing in the world changes (PROTO-07, GUIDE-01..03) | UI-SKULL-01 by construction: the guide cannot say what the screen could not |
| D-29 | UI-CLARITY-01 exempted only the Developer panel (and "dossier" on the Content screen) | The Content screen may also say "affordance" and "actor": it shows pack authors' own words and the pack folders are named so | The core pack's own description says "the affordance catalog"; an authoring screen is where those names belong |
| D-30 | Menus, dialogs and selects in the Play UI | Nothing the tests click or read is teleported: explicit top-bar buttons instead of a menu, inline item actions, choices as buttons, the settings dialog an inline card | jsdom tests cannot reach Vuetify overlays reliably; plain markup also reads better with a screen reader |
| D-31 | A society tick wired into the off-screen step | Nothing in `society/` ticks by itself: a settlement's clocks are `event_queue` rows (SETTLEMENT_DAY 07:00, PRODUCTION_CYCLE per workplace, GROUP_DAY 20:00, ROUTINE_STEP per person) started once by `turn.timers.seed_society` at stage 0 and fired like every other timer, each followed by a cascade sweep; consequences between them are cascade content. `turn.timers.run_offscreen` is the off-screen step (6-hour windows) | One scheduler, one replay path, and every hop citable; a world without settlements (every P7 scenario) runs exactly as before |
| D-32 | "Keep watching" ends at the next pending queue row | Rows of `kernel.clock.BACKGROUND_QUEUE_TYPES` (routines, production, draws, group days, loyalty checks, delayed consequences, trace decay) do not end a condition-ended window; they fire inside it, and what they make the PC perceive still pulls the horizon (HOR-01 amendment) | Otherwise a settlement would end every wait within the hour and "I wait and watch the yard" would never last |
| D-33 | `condition_factor = 0.5 + machinery_condition / 200` | 1.0 when machinery_condition ≥ 50, else 0.5 + condition / 100 (the same 0.5 at 0, continuous at 50) | Under the old formula no machine short of perfect ever ran at full output, so a balanced settlement was permanently short; now neglect shows and ordinary wear does not |
| D-34 | Animosity: an I + Resolve check at DC 4 + resentment; failure → refusal or sabotage | The one check system (07 §1): an I check against resistance = resentment, situation from current Resolve; `fail` → the cycle's output ×0.9 and +10 tension, `break` → ×0.75 and +20. No refusal in P9 | No second DC scale; the cost is measured in output; a refusal needs the person's own cognition (a HOT/WARM mind), which a COLD crew does not have |
| D-35 | Ration +1 "after 3 days above 7 days of stock"; households with dependents +10 tension **per day** at ration ≤ 2 | +1 after 3 draws in a row with every rationed store at ≥ 7 days (up to level 3); +10 tension once at the cut (core CAS-006, with a loyalty check for the worst-hit head), then +5 a day along every tie that holds resentment while rations stay ≤ 2 (GRP-05); tension decays 5 a day when nothing renews it | +10 a day would boil every such household over within a week of any shortage and had no cause event to cite; the cut does, and the daily strain follows existing grudges |
| D-36 | — | Code never acts for a human-controlled body in the society either (SEL-06): no routine, no cover assignment, no drift pair, no loyalty check, no animosity roll for the PC. The PC is still counted, drawn for and fed like anyone (L12), and what others feel toward the PC changes through play | The player decides for the PC; the settlement treats the PC as one more mouth |
| D-37 | P9 includes Lots, rumour distortion, leadership challenges, splintering, coalitions, faction doctrine and weather couplings | These arrive with world motion in P10: Lots with trade; the RUMOUR_DISTORT call with background cognition (P9 hops pass the words on exactly); challenges, splits and doctrine on P9's tension and pressure numbers; weather with weather. P9 proves the three couplings of 06 §2.6 | The P9 proofs must be deterministic with the fake model and must not wait on worldgen |
| D-38 | — | `work_assignments` is keyed `(workplace_id, actor_id, role, shift_start_hh)` (was without `shift_start_hh`) so a person can cover a second shift of their own role. `SCHEMA_VERSION` was **not** changed (your rule: no version change without instruction); no run made by an earlier build exists yet, so nothing needs migrating | Recorded so the schema history stays honest; say if you want the version raised |

## 3. Your earlier rulings carried into this spec

| Ruling (source) | Where it lands |
|---|---|
| Structures that held through the Fall are flagged HELD and skip the interior Fall pass (Batch 2 #4) | `places.held`, WG-32, GEO-04 |
| Worldgen cannot be byte-perfect → BaselineWorldFiles (Batch 2 #6) | RUN-09, Worlds screen (D-13) |
| Only three infection vectors; no gaseous corpse transmission (Batch 2 #5) | `core/pathways/`: air, wet, cold-start (+ lurker-deep marked proposed); no other exposure kinds exist |
| Death is permadeath (Batch 2 #2) | Ironman rule (D-12) |
| Fall-sim horizon must equal the days-since-Fall value (Batch 3 #1) | WG-31 |
| Worldgen detail tiers "Gotta go to work soon" → "I don't intend to use my laptop much today" (Batch 3 #4) | `WorldDetail`, 11 §1.1 |
| Faction population baselines modulated by history (Batch 3 #5) | WG4 |
| Hand-written characters cannot die in worldgen; explain their survival; the PC gets a real survival history (Batch 3 #6) | WG6, WG-33 |
| Campaigns "Normal" and "Ghost" (Batch 3 #7) | Normal is the default game. A Ghost campaign becomes possible the day you import the Ghost corpus: a PC with `faction_start_type: always_in_faction` and a Ghost membership starts inside it |
| A good DM just runs the scene; never ask the player to approve story seeds (FREEPLAY issue) | Suggestions are derived from the PC's own options, never story prompts (UI-SUG-02) |
| No pseudo-code in anything a model reads (design principles) | PROMPT-02 |
| Thin dossiers cause drift; full dossiers never trimmed; recent real lines; human-only writer's notes (design principles) | DOS-01, DOS-05, `writers_notes` |
| One fresh model call per job, stable→volatile prompt order, intent before narration, no vector search, model never decides what it receives (Codex Desk) | L-laws, PROMPT-01, 05 §9.3 |
| Logs go to files, not chat (Authentic Suffering notes) | `as_runs/<run>/logs/*.jsonl`; Dev panel only in Developer mode |
| Admin NPC "Fredrick" spawnable by cheat (Batch 2 idea): OP stats, infinite loyalty, engine-level awareness, fully mortal | `cheat_admin` pack; CHEATS.md §6; awareness = automatic standing brief through the perception door every turn he thinks (CHEAT-11), so Skull Law's single writer still holds |

## 4. Not carried (and where they could come back)

- The Harness narrator-god "It" (Title Zero content): AS's narrator is the PC's own perception.
  It could return later as lore content, never as a narrator with authority.
- The CMG §40–41 scene package / beat graph / pivot contract (D-17).
- The Ethan summon: bring him back as a dossier in a `cheat_` pack if you want him.
- Codex Ultima retired names (Aethelburg Necropolis, GearGhoul): appear only as quoted history in
  CHEATS.md.

## 5. Requests for the Codex Master Guide (not edits — for your approval)

Per the project's standing instruction these are requests. The guide has not been touched and no
version number has been changed.

**Goals to add**
- G-AS-7: The AS engine is host-independent; the host (currently a Talemate fork) only installs,
  serves and relays.
- G-AS-8: Every rule id is enforced by a named test in the build spec; a rule without a test is a
  wish.
- G-AS-9: Worlds are shared as files, never as seeds.

**Issues to note**
- I-AS-9: CMG §40.6 (100-day horizon) and §44 (sovereign termination, Codex authority over
  cheats) are still marked active, but the Harness rulings retired them.
- I-AS-10: The PC card text differs between Part II §2.3 ("Getting to places…") and Part XV
  ("Gets to places…"). The spec uses Part XV.
- I-AS-11: The document is titled "Master Guide v4.1" inside while its file and footer say v4.2.
  (Not changed — recorded only.)
- I-AS-12: CMG §43.B's Addison Containment Rule assumes Addison is always the PC; with selectable
  PCs it needs a rule for runs where she is not.
- I-AS-13: CMG §42.1 names Codex as responsible for the escape; AS has no narrator-god, so the
  escape's author is unassigned in AS canon.
- I-AS-14: CMG §61 Part XV locks Addison at age 20 with "started collapse at ~10", which pins her
  world to about ten years after the Fall, while Parts II–III let the player pick any era with
  her. AS resolves it with WG-34 (D-18); the guide could state the same.
- I-AS-15: CMG §43.C's No-Release Quarantine names "execution" and "black-site observation" as
  valid outcomes but no section says who decides between them; AS leaves it to each faction's
  doctrine (`treatment_of_visibly_sick`).
