# PROGRESS

Written by `tools/as/gate.py` (the Evidence columns) and by the builder (Next task, Notes).
Status words: **not started** · **in progress** · **observed implementation, not proven gate** ·
**green**. Only `gate.py` may write **green** (13 §1).

## Current

- Current phase: record the gates P0–P7 (the engine is built), then P8 steps 4–6
- Next task: `python tools/as/gate.py --phase 0`, then `--phase 1` … `--phase 7`, one at a time (13_BUILD_ORDER §4.0 step 1). Then P8 step 4 — `src/talemate/server/as_game_plugin.py` (02 §6).
- Blocked by: nothing
- Kit status: the engine is built — P0–P11, the sim soak, Actor v2 B1–B6 and the owner's F1a, F1b, H1, I1, W1 and F1c (13_BUILD_ORDER §4.0; the bodies are in `_impl_*.py` files or built in place, AGENTS.md §4). The engine suite: 2064 passed (2071 collected; D-110 added the stall watchdog, D-111 the Writer / Clerk lane split, D-112 the limits bench, D-114 the models at work under the bar, D-115 the Cheat field's command words and dictionary, D-116 character examples, D-117 what was said here, D-118 work picked up again, D-119 a killing seen, D-120 seen before swept, D-121 the second look, D-122 sleep rests you, D-123 what wears the will down, D-124 a bite seen, D-125 promises answered, D-126 being hurt leaves a mark, D-127 nobody is a template, and their tests); the 7 that fail are yours to build: the owner's sessions browser and hard delete (RUN-12/13, D-76: `wipe_tree`, the one-step delete, `list_runs`' `final`, `on_run_delete`) and a P10 genesis that names no run (`Store.backup_to(..., as_world=)`). Also not built: P8's Talemate plugin and upstream patches, the frontend toolchain and the P8 Play UI screens (the P10 screens are built) — 13_BUILD_ORDER §4.0 has the order. After the P10 gate, record the P11 gate (built: it only writes the evidence), then stop and write "waiting for the kit update (P12)" here.

## Phases

| Phase | Status | Commit | Command | Gate | Artifact | Date |
|---|---|---|---|---|---|---|
| P0 Substrate | observed implementation, not proven gate | | | | | |
| P1 Lane harness | observed implementation, not proven gate | | | | | |
| P2 Bodies, space, objects, content | observed implementation, not proven gate | | | | | |
| P3 Perception | observed implementation, not proven gate | | | | | |
| P4 One Actor | observed implementation, not proven gate | | | | | |
| P5 Many Actors | observed implementation, not proven gate | | | | | |
| P6 Memory | observed implementation, not proven gate | | | | | |
| P7 The Slice | observed implementation, not proven gate | | | | | |
| P8 Play UI | in progress (steps 1–3 built; plugin, toolchain and UI screens to build) | | | | | |
| P9 Society | observed implementation, not proven gate | | | | | |
| P10 Wide world | observed implementation, not proven gate | | | | | |
| P11 Audits | built by the kit (D-95..D-99); gate not yet recorded | | | | | |
| P12 Surfaces | not started | | | | | |

## SAND remaining

| Number | Where | Replaced by |
|---|---|---|
| per-call latency estimates, the narration reserve and the turn budgets (placeholders sized for 20-second calls; the owner's pair writes about 5 and 19 tokens a second) | `SchedulerRules.estimated_call_s`, `reserve_narration_s`, `turn_budget_s` | `tools/as/bench.py --accept` on your machines (BENCH-01, D-112) |
| acoustic fidelity margins 12/5/0 dB | `AcousticRules` | `tools/as/eval.py` belief-accuracy runs (BENCH-07) |
| Resolve drains/recoveries | `ResolveRules` | eval refusal/compliance rates (BENCH-03) |
| packet token budgets 6000/4000/3000 (Actor Spec §5; were 3500/2200/1400) | `PacketRules.token_budget` | the bench's ladder (D-112): reading speed and recall by prompt length, and each cognition call's real time (BENCH-04) |
| room for a person's voice examples (600 tokens) and how many a split second gets (2) | `PacketRules.voice_example_tokens`, `voice_examples_reaction` | the bench's reading speed (D-112): what 600 tokens cost the Writer per call, and a play session's sense of whether people sound like themselves (D-116) |
| how far back what was said here reaches (30 minutes) and how much of it (8 lines) | `PacketRules.thread_window_min`, `max_thread_lines` | a play session: people should follow a conversation across moves without the prompt filling with old talk (D-117) |
| heard words cut at 800 characters (Actor Spec §5) | `PacketRules.max_heard_chars` | a play session's longest speeches: nobody's own context crowded out, no ordinary speech cut |
| outings: daily chance per kind | `WorldRules.op_chance` | 100-day fake-model soak per difficulty (BENCH-06): how many go out, how many come back |
| how long marks last under a roof | `WorldRules.sheltered_trace_mult` | play-tuning |
| the dead past each map edge; drift chance; the Mega Horde's daily chance | `HordeRules.exterior_pool`, `drift_chance`, `mega_daily_chance` | 100-day soak per difficulty: how often a Mega Horde comes, how full the streets get |
| how many of one crowd show in a place; how long a loud noise holds its neighbourhood in the moment | `HordeRules.local_cap` (40), `turn.select.LOUD_MEMORY_MS` (10 min) | a day of the Mega Horde next to the player: bodies shown per hour and seconds per simulated day (D-67, D-68) |
| how long a door holds under a crowd | `InfectedRules.portal_holds_min` | play-tuning |
| how long a spreader's bottle stays infective | `InfectedRules.saliva_hours` | the lore owner's word, then play-tuning |
| wear by wet days | `DecayRules.rust_per_wet_day`, `pulp_per_wet_day`, `rot_per_wet_day` | play-tuning |
| relationship drift chances 0.25 / 0.2 / 0.3 | `SocietyRules.drift_bond` / `drift_household` / `drift_friction` | play-tuning (how fast a settlement's feelings move) |
| thirst stage interval | `NeedsRules.thirst_stage_every_h` | play-tuning |
| how far a smell carries (1/2/5/10/20 m, half outdoors); when a corpse starts to smell (6/24/72 h) | `OlfactionRules.range_m`, `outdoor_mult`, `death_hours` | play-tuning (F1b) |
| gore camouflage: how much gore masks you, how loud gives you away, for how long (4, 55 dB, 30 s) | `InfectedRules.gore_mask_min`, `mask_break_db`, `mask_window_s` | play-tuning (F1b) |
| how much each provocation angers (struck 4 … ordered about 1), how fast anger fades (1 an hour), the chance to swallow it (0.1 per Resolve, at most 0.8), what stresses (H1) | `TemperRules.provocation_heat`, `heat_decay_min`, `hold_per_resolve`, `hold_max`, `stress_from` | play-tuning: how often a room of strangers comes to blows, and how often a group bickers (H1) |
| how often a settlement's sore pairs have a row (0.05 + 0.05 per point of stress) and a brawler's row comes to blows (0.3; a quarter for others) | `SocietyRules.quarrel_base`, `quarrel_per_stress`, `brawl_chance` | 100-day soak: a settlement should bicker weekly and brawl now and then, not daily (H1) |
| what wears a person down (a death seen 2 + bond, hunger past stage 2 +1, sleep -2) | core `cascade/stress.yaml` CAS-019..021 | play-tuning (H1) |
| how long the dead stay on a corpse (20 min), how many bites leave too little to rise (8), how far a scream pulls the rest of them in (30 m) | `InfectedRules.feed_on_dead_min`, `devoured_bites`, `scream_draw_m` | play-tuning (I1) |
| the chance tainted meat / fouled water gives the strain (0.5 / 0.4) | core `pathways.yaml` wet `tainted_food`, `tainted_water` | the lore owner's word, then play-tuning (I1) |
| a host's blood on the hands / in the eyes / a sleeper's mouth (0.15 / 0.05 / 0.6) | core `pathways.yaml` wet `fluid_contact`, `fluid_splash`, `mouth_contact_direct` | the lore owner's word, then play-tuning (W1) |
| how often the urge comes (10 min x 336 / hours, never under 2) and takes the player's hand (0.2 week three, 0.4 week four) | `InfectedRules.compulsion_cooldown_min`, `compulsion_min_gap_min`, `pc_urge_share` | play-tuning: the player should feel it coming, not lose the game to dice (W1) |
| a wound's blood (0/1/2/3 by severity); grime a day to 3; rain 20-minute steps | `ConditionRules.blood_from_wound`, `grime_every_h`, `grime_unwashed_max`, `weather_step_min` | play-tuning: people should look like what happened to them (F1c) |
| how cold it is (mild 1 / cold 3 / hot 0 by day, +1 night, -2 indoors, +1 soaked) and how fast it bites (4 chill a stage, -4 an hour warm) | `ConditionRules.cold_need`, `shelter`, `chill_per_stage`, `warm_per_step` | play-tuning: naked on a mild night about twelve hours to death; a wet night in a cold country a few (F1c) |
| smearing the dead on (0.05) and into an open wound (0.5) | core `pathways.yaml` wet `gore_smear`, `gore_in_wound` | the lore owner's word, then play-tuning (F1c) |
| the reek grates every 10 minutes (heat 1); a naked adult every 30 (heat 2, strain 1) | `ConditionRules.reek_every_min`, `bared_every_min`; `TemperRules` | play-tuning: nobody stands next to the reek for an hour (F1c) |

## Human checklist items

| Item | Phase | Done |
|---|---|---|
| LM Studio set up on both machines, LM Link on (08 §2) | before P7 live play | |
| `tools/as/bench.py --accept` run overnight (D-112; it runs the probe too) and `reports/bench.md` read | P1+, and after any model change | |
| Play UI smoke checklist, P8 part (`talemate_frontend/src/play/README.md` §0–§6) | P8 | |
| Play UI smoke checklist, later parts (§7 New life and worlds: P10; §8 death, imports, cheats: P12) | P10 / P12 | |
| Review `SPEC_ISSUES.md` | every phase | |

## Waiting on the owner

Things only you can do or decide, collected while you were away (newest last). Each says what happens if you
do nothing.

1. **Run the limits bench overnight**: `python tools\as\bench.py --accept` (about three hours on your pair;
   `--resume` if it stops; add `--ctx-B 59136` if LM Studio does not report the laptop's context through LM
   Link). Then read `as_runs\reports\bench.md`. Until then the planner's call times are placeholders many
   times too optimistic for these machines, so turns admit more minds than the time they take. (D-112)
2. **Boulesis's top_k**: set it to 64 in LM Studio (Google's recommendation for Gemma 4). The game sends
   temperature and top_p with every call; top_k only LM Studio sets. Nothing breaks without it.
3. **Who speaks through which model**: the people who matter most (HOT) think on lane A; the rest (WARM) on
   lane B, and their spoken lines come from B too. For every spoken line from A, set
   `regimes.actor_cognition.lane: A` and `regimes.actor_reaction.lane: A` — minutes per person at 5 tokens a
   second. Left alone: B voices the lesser people.
4. ~~The UI shows no live model progress~~ — done while you were away (D-114): the loading bar now says what
   the models are doing ("Thinking · 2 min") and speaks up when one goes quiet. Nothing for you to do; look at
   it on your first long move and say if the words are wrong.
5. **The Play UI specs**: run on a scratch vitest setup after D-111 / D-112 / D-114 / D-115 — 76 pass (15 new)
   and 103 fail. Every failure is a P8 part the builder has not built yet (words, play, connect / home,
   store, socket); two of them are new: the Cheat field's suggestion list and dictionary panel, and the store
   opening the field the moment the word is typed. The repo itself
   has no vitest toolchain yet (13_BUILD_ORDER P8).

6. **How picky the narration lint should be** (your call): every narration draft goes through a code lint;
   one error throws the draft away and asks the Writer again, up to `rules.style.max_narration_attempts` (3),
   keeping the best. The fidelity checks (a name the character cannot know, invented dialogue, knowledge the
   viewpoint cannot have, your own words echoed back) protect the game. The style checks (passive voice, -ly
   adverbs over 8%, more than one comparison per 200 words, abstract words, repeated sentence openers,
   length over 125%) are taste, written when the main model was weaker — and at 5 tokens a second each
   redraft costs minutes. The bench now lints the Writer's real drafts and lists which rules fail them
   (`bench.md`, "Narration and the code lint"). If the style rules throw away prose you like: set
   `rules.style.max_narration_attempts: 1` (new runs), loosen the numbers under `rules.style`, or tell me to
   make the style rules advisory and keep only the fidelity checks forcing a redraft.

7. ~~Cheat autocomplete and "Spawn Fredrick"~~ — done while you were away (D-115): a line in the Cheat field
   that starts with a command word is that command, at once, with no plain-words reading ("Spawn Fredrick",
   "give bandage 3 to Mara", "census"); a sentence that only starts like one ("kill the lights") still goes
   to plain words. The server now serves a dictionary of every command, what it does, an example, and what
   each blank can take (the people your character knows, places, items, groups, the packs' people, the dead
   by type, stats, weather, strains); the UI's autocomplete logic is built and tested. The list and the
   dictionary panel themselves sit in the Play screen's input box, which is still the builder's (P8). Try it
   once the Play screen exists and say if anything reads wrong.
8. **A private repository for the lore** (needed from you): this repository is public (a fork), so none of
   the ASCL lore may go in it. These wait for a private repository you create and add to the session: the
   Lurker venom and feeding ("it should be in there, if not there's issues"), the Lurker stalk and the
   settlement hunt, Codex as the inner monologue, and your Willis card updates (2026-09-26). Left alone:
   the game keeps the lore it has now (CHEATS §6b, the core pack), and none of these are built.
9. **Your character examples** (D-116, done while you were away; the examples themselves are yours): every
   character can now carry `voice.examples` — moments in their own words (what was going on, who spoke to
   them and what they said, what the character said back, how hard it pressed them). The game shows a
   person's examples to the model as things they already said, never as lines to repeat: in their
   decisions, in say-my-way when you opt in, and Willis's in his frozen-moment roast. Send me the Willis
   and Addison examples you have (as text, or a story or chat log: each moment where they speak becomes
   one), and say whether they may go in this public repository or belong in a private pack. Left alone:
   nobody has examples; everything works as before (the three exemplar lines on each card).
10. **How long a move takes, and thinking** (your call, after the bench): every move's own path has three
   calls that think first — each HOT person's decision and the narration on the Writer, and the narration's
   judge on the Clerk. Guessing from your speeds (the Writer thinking about 800 tokens at 5 a second is nearly
   three minutes a call), a move with one HOT person takes roughly 9 minutes and a deep one with three about
   15; with those three calls not thinking, roughly 3 to 4. The bench now times each of them both ways and
   shows the whole move both ways ("without thinking" in `bench.md`), with the exact as_config.yaml lines
   (`hot_cognition.thinking: false`, `regimes.narration.thinking: false`, `regimes.render_lint.thinking:
   false`); `--accept` never changes thinking. Left alone: everything thinks, as you asked for quality.
11. ~~Conversations, part one~~ — done while you were away (D-117, your "conversations ... buffed"): every
   person deciding now sees what was said where they are before this moment — the last eight lines since
   they arrived, as they heard them, their own among them — and knows when a question put to them is still
   hanging (and is given a moment to answer it). Building it found a bug: nothing ever saved what people said, so nobody saw their own last
   words; fixed. Still to come: people starting topics themselves, interrupting, changing the subject.
12. **A killing seen** — built while you were away (D-119, your "kill one of my squad mates for the hell of
   it, in front of everybody"): whoever saw it — saw who fell and who did it — stops trusting the killer,
   is afraid of them and tells it; whoever believes the telling trusts them less; the crew that saw thinks
   less of them, even one of its own; the killer carries it whether anyone saw or not. In the dark nobody
   can say who; self-defence and stopping someone hurting another cost nothing more; your own character
   is never told how to feel about one. **Your call**: should settlements have a law against killing (a
   cost on the option for whoever knows the law, and the settlement's answer)? That changes what worldgen
   writes, so it waits for your word. Checking it through whole turns found an older fault: in a real
   turn the world never answered what people had just seen — a theft, a death, someone shoved to the
   dead — because it answered before they had seen it, and a death at the end of a moment or off-screen
   was never answered at all. Fixed (D-120); one moment now moves anyone's trust by 2 at most (the
   game's own check refused more, which would have undone the whole move).
13. **Things you would have hit in your first hour** — fixed while you were away. Typing "I lie down and
   sleep" said it wasn't clear what you meant whenever the short menu had no room for sleep; now the game
   takes a second look at everything you could do (D-121). Sleeping never rested you, and once asleep
   everything you typed was refused until some noise woke you; now a night's sleep pays off a day, a nap
   a little, and whatever you do wakes you (D-122). Nothing ever gave anyone's Resolve back; now an
   unbroken night and a kept promise do (D-122). And ten of the sixteen ways the spec says a person's will
   wears down had nothing that caused them; now grief seen or heard (a dependent's the worst), a first
   kill, killing a child, severe pain, hunger and going without sleep all cost Resolve (D-123).
14. **People don't all sound the same** (your "If they all talk the same ... I'll crash out"). Most of a
   world's people are never written by a model, and they all shared one inner life and four voices; a
   five-year-old talked like a pump mechanic. Now each has their own voice, lines, motive, wound, fears and
   the things they would never say, by age, when they were born and their work (D-127). Next: the people you
   actually get to know get their own words written by the Writer in the quiet hours (HANDOFF).
15. **Treat them badly and they remember** (your "I do expect reactions, and proper ones"). Hit someone who
   was not fighting you and they stop trusting you, are afraid of you and hold it against you; whoever saw
   it trusts you less and tells it; threaten someone with a gun in your hand and they stay afraid of you
   (D-126). With D-119 (a killing seen) and D-123 (a first kill, a child) the worst things now cost what
   they should. Anger still flares and fades by the hour on top of that, and people can still snap.

## Notes (builder)

(append dated notes here: what was tricky, what you tried, anything the next session must know)

- 2026-09-24 (kit maintainer): the engine through P10 was built outside DSH and committed on the owner's
  instruction. Its bodies are in `_impl_*.py` files; see AGENTS.md §4 before changing one. Start at
  13_BUILD_ORDER §4.0, not at P0 task 1.
