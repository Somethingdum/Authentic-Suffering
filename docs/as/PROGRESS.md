# PROGRESS

Written by `tools/as/gate.py` (the Evidence columns) and by the builder (Next task, Notes).
Status words: **not started** · **in progress** · **observed implementation, not proven gate** ·
**green**. Only `gate.py` may write **green** (13 §1).

## Current

- Current phase: record the gates P0–P7 (the engine is built), then P8 steps 4–6
- Next task: `python tools/as/gate.py --phase 0`, then `--phase 1` … `--phase 7`, one at a time (13_BUILD_ORDER §4.0 step 1). Then P8 step 4 — `src/talemate/server/as_game_plugin.py` (02 §6).
- Blocked by: nothing
- Kit status: the engine is built — P0–P11, the sim soak, Actor v2 B1–B6 and the owner's F1a, F1b, H1, I1, W1 and F1c (13_BUILD_ORDER §4.0; the bodies are in `_impl_*.py` files or built in place, AGENTS.md §4). The engine suite: 2283 passed (2290 collected; D-110 added the stall watchdog, D-111 the Writer / Clerk lane split, D-112 the limits bench, D-114 the models at work under the bar, D-115 the Cheat field's command words and dictionary, D-116 character examples, D-117 what was said here, D-118 work picked up again, D-119 a killing seen, D-120 seen before swept, D-121 the second look, D-122 sleep rests you, D-123 what wears the will down, D-124 a bite seen, D-125 promises answered, D-126 being hurt leaves a mark, D-127 nobody is a template, D-128 the room talks, D-129 what is done to you and yours lasts, D-130 everyone knows, D-131 the Writer sees what it is asked to write, D-132 putting down the dead is not hurting anyone, D-133 eating the dead, D-134 captives, D-135 hands up, D-136 the player's hands, D-137 what makes you look up, D-138 your own, D-139 shielding, D-140 the guide knows what the character grew up hearing, D-141 seen going, D-142 left behind, D-143 a person's lines sound like the person, D-144 one of our own, D-145 it comes back, D-146 broken nights, D-147 a line they don't cross, D-148 a child, D-149 people you get to know, D-150 the quiet, D-151 words only, D-152 in the right person, D-153 people you know of, D-154 what the lint wants said first, D-155 nobody to calm, D-157 the words are lost, D-158 seen not caught, D-159 when it is, D-160 what they call them, D-161 it missed, D-162 you saw it, D-163 the door shut on them, D-164 my way words only, D-165 how much, D-166 how they spoke, D-167 asked then said why, D-168 who they are to you, D-169 the world's words, D-170 of him, D-171 waking up, D-172 the night passed, D-173 out cold, D-174 a wait is minutes, D-175 the Writer for what matters, D-176 news is new, D-177 what happens first, D-178 the place told of him, D-179 who it was, D-180 someone you love nearly killed, D-181 the way out, D-182 what the body wants, D-183 rested they wake, D-184 the bench simulator on virtual time, D-185 faster with the same results, D-186 seen spreading it, D-187 the act is the sign, D-188 a law kept, D-189 nothing to remember, D-190 nothing new nothing to decide, D-191 what they now want, D-192 names called, D-193 the mouth rules, and their tests); the 7 that fail are yours to build: the owner's sessions browser and hard delete (RUN-12/13, D-76: `wipe_tree`, the one-step delete, `list_runs`' `final`, `on_run_delete`) and a P10 genesis that names no run (`Store.backup_to(..., as_world=)`). Also not built: P8's Talemate plugin and upstream patches, the frontend toolchain and the P8 Play UI screens (the P10 screens are built) — 13_BUILD_ORDER §4.0 has the order. After the P10 gate, record the P11 gate (built: it only writes the evidence), then stop and write "waiting for the kit update (P12)" here.

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
| packet token budgets 6000/6000/3000 (Actor Spec §5; were 3500/2200/1400, WARM 4000 until D-175) | `PacketRules.token_budget` | the bench's ladder (D-112): reading speed and recall by prompt length, and each cognition call's real time (BENCH-04) |
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
   they should. Anger still flares and fades by the hour on top of that, and people can still snap. Now
   also (D-129): take what is someone's in front of them and they hold it against you; hurt someone they
   love and it is not forgiven, kill them and it never is; shame them in front of others and it wears them
   down; hold them and make them watch and it breaks something; make them do it at gunpoint and they
   resent you for it. And (D-133) the dead can be eaten — anyone with a blade and the hunger, whose card
   does not say never — and whoever sees it is shaken, trusts them less, fears them and tells it; whoever
   loved the dead never forgives it; the one who does it carries it. Putting the dead down, as everyone
   must, is not counted as hurting anyone (D-132).
16. **The room talks** (your "We have a very very fast model ... insignificant NPC dialogue"). Past the model
   budget people were moved by code and never said a word, so in a full room two or three people talked and
   the rest were furniture. Now the most salient of them in your place, when something reached them, get one
   short line each on the fast lane in their own voice — or say nothing, as most people would (D-128). A
   line costs a second or two on lane B, at most 1 / 2 / 3 a wave by depth; a failed one is silence. The
   limits bench measures it (`ambient_line`).
17. **Everyone knows what their world says** (your "The lore needs merged into ever crevice of this"). The
   core pack's lore — what everyone says ("If it's not the head, it's not dead."), what each generation
   says (a child born after the Fall: "Walkers are sleepwalking people."), what the Remnants say among
   themselves — was written but nobody ever held any of it, and people made by worldgen never even got
   what their own card says they know. Now everyone holds what their world, their generation and their
   people say, and it comes to mind when it bears on the moment: said aloud (someone asks about a cure),
   seen (a Ghost in the yard) or felt (a scream) — a few lines at most, never a list (D-130). Your lore's
   records can say what brings each one to mind (`about`: words; `when`: moments — LORE_STRUCTURE §2.5).
   **Your call** (SPEC_ISSUES SI-006): the lore says everyone knows to aim for the head; the combat
   menus were built on the untrained not knowing it. Should everyone know?
18. **The Writer was writing your world blind** (found while doing 17). Every worldgen call kept what the
   Writer needed beside its prompt instead of in it: the region's history was asked for by ids it never
   saw (so every event stayed a one-line stub), the opening was asked to cite people and places it was
   never shown (so every opening was written by code), and the people were written from a name, an age
   and a job. The test model read the hidden parts directly, so nothing ever failed. Now each prompt
   carries what it needs — for a person: how long since the Fall, what their generation remembers, the
   sketch that makes them different, what happened here, and what everyone around them says (D-131).

19. **The evil you do is answered** (your "If I treat them like shit, or do something just absolutely evil")
   — built while you were away: eating the dead (D-133); torture and executing a prisoner — someone held, or
   someone who put their hands up (D-134, D-135); a gun held on someone's child, stripping someone's dead
   (D-138); walking out on someone who loves you while they bleed (D-142); killing one of your own crew,
   which sets the crew weighing whether to stay (D-144). People now react inside the moment to a knife
   drawn, a hand on their things, a gesture, a surrender (D-137), and see people leave a room (D-141 — before,
   nobody ever saw anyone go). Your character can nod, shrug and put their hands up (D-136); under strain
   the worst thing they saw comes back unasked (D-145) and their nights break after three hours (D-146).
   Generated people's lines now sound like their voice (D-143). Since then: a shot that misses is still
   trying to kill someone — they know it, and so does whoever saw it (D-161) — and a door shut on someone with
   the dead outside is remembered by them and by whoever loves them (D-163); whoever saw a thing done holds it
   as seen, not as talk (D-162). Nothing for you to do.
20. **Your character's own lines** (your call). Each player character's card has things they will never do
   (Owen: leave someone wounded, hurt a kid; Addison: hit someone unarmed; Ruth: leave a wounded person,
   execute a prisoner, feed anyone to the dead), and the spec (L12) takes those options off the player's
   menu exactly as it does for everyone else. Since D-134/D-135 that includes killing someone held or
   someone with their hands up, and Owen's "leave someone wounded" keeps him in a room while someone he
   loves bleeds. Until now the player was told "That can't be done from where you are."; now they are told
   "Your character won't do that. It's a line they don't cross." (D-147). Left alone: the lines stay
   absolute. Your options: keep them; make them a cost instead (the act is allowed and the character pays
   — nerve, stress, what comes back at night); or let the player choose per run.

21. **Who writes the voices of the people you get to know** (your call). Generated people you have talked
   with (three exchanges) now get their voice written once, between moves, from what they actually said
   (D-149). It runs on the Clerk (lane B: a few seconds each). For the Writer instead — slower (about a
   minute each at 5 tokens a second, while you read) and in the story's own voice — set
   `regimes.person_voice.lane: A` in as_config.yaml. Left alone: the Clerk writes them.

23. **Putting down the bitten** (your call). Your lore says "A bite is a death sentence, full stop." Today,
   when someone shoots a bitten person who is not fighting, everyone who sees it takes it as a murder: they
   trust the shooter less and fear them, tell it as "killed someone who was not fighting back", and the dead
   one's group thinks less of the shooter. The lore does not say how survivors judge it. (a) Leave it: a
   killing is a killing. (b) Whoever saw the bite, or holds the quarantine law for that person (D-188), takes
   it as a hard necessity — no trust lost, no murder told — while those who loved them still grieve and may
   never forgive it. (c) It depends on the place: some settlements or factions have a law that the bitten are
   put down, and only there is it no crime. Left alone: (a).

22. **A turn, played and read line by line** (your "fully flesh out the per turn pipeline" and "every aspect of
   LLM usage"). I played whole turns with the test model and read every prompt the real models get. Fixed: a
   person's stage directions ("*sighs*") were spoken aloud as words (D-151); the story's record of your
   choices read "Owen chose to take your revolver", and people's memories "I chose to ... your ..." (D-152);
   your character knew nobody out of sight, so "I walk over to June and shove her" meant nothing — now he keeps
   his crew in mind, the first step is going to her, and "June, get in here!" through a door is for June
   (D-153); the Writer is told up front what the code would throw a draft away for, and the names your
   character knows, so fewer drafts are rewritten at a minute each (D-154); "talk them down" no longer fills
   menus with calm people (D-155); a line heard only as a murmur was handed to the Writer as the word "None"
   (D-157); sights were worded like speech ("some words lost") (D-158); the fast model was told the story was
   "years after the Fall" on day 18 (D-159); and everyone now calls the dead what their world calls them — a
   walker, a runner, a crawler — and seeing one brings to mind what people say about it (D-160). Your lore can
   say what each kind of dead is called (LORE_STRUCTURE §2.1, "Called"). Since then: "say it my way" (off unless
   you turn it on) no longer speaks stage directions aloud (D-164); feelings are worded by how strong they are —
   "you are wary of them" is not "you do not trust them at all" (D-165); the prompts no longer read "spoke shout"
   or "(peer)" (D-166, D-168); "You got any rounds? I'm down to six." is a question someone owes an answer to
   (D-167); the story is free to name the back door the way the world does even when you typed the same words
   (D-169 — three of twelve played turns had been thrown away for it); and what your character feels happen to
   him is told of him, not as "you", in a third-person story (D-170). And sleep: after a quiet night anything
   you typed failed the whole turn — the menu was built for a sleeper, who can do nothing — so only a noise
   could ever wake him; now what you type wakes him and he does it (D-171), and the story is told that he fell
   asleep, that the night went by, and that he woke after about eight hours (D-172). And out cold: nobody who
   lost a third of their blood ever came to, and when it was your character every turn after failed — the game
   was over with him alive. Now blood comes back slowly once the bleeding has stopped, people come to, and while
   your character is out your turns let the time pass around him ("Let the time pass") (D-173). Counting the
   model calls of quiet turns: each "I wait." passed eight hours in a quiet place (three were a whole day) —
   a wait is five minutes now, watching still runs until something happens (D-174); and every turn the main
   model spent ~40 s deciding for two people nothing was happening to — now it thinks only for the people
   something is at stake for, the fast model for everyone else, and a person on the fast model keeps
   everything they know (D-175); and someone watching the same man for an hour is not news every five
   minutes (D-176). And a real one: "I search the alley" — a two-minute search — had its end written
   before the world moved, so when a walker grabbed your character two seconds in, the turn could not stop
   for you to answer; he searched on while he was eaten and died without a say. Now what happens first
   happens first, the turn stops when something reaches him, and the search is still going (D-177). The
   place your character walks into is told of him too, not "You're alone." (D-178); and people who watch
   something done know who it was done to — June, who saw your character fire at Mara, believes "Owen
   tried to kill Mara", and her grudge names her; talk passed on still says "someone" (D-179); and since
   she loves Mara, that is not forgiven (D-180). Going through a door into the next room is on everyone's
   first list now, not crowded out by four ways to cross the room (D-181); and a tired person sees sleep, a
   starving one the food in their pocket, first (D-182) — and someone without a timetable who lies down
   to sleep wakes when rested, not only when a noise wakes them (D-183). And speed: the body clock no
   longer stops every twenty minutes for the weather, content look-ups are indexed, and the content packs
   are compiled once while they are unchanged — the same results, and the whole engine suite runs in four
   minutes instead of ten (D-185; the bench's own simulation now runs on virtual time and cannot be
   thrown off by a busy machine, D-184). And whoever sees a host of the wet strain spit into a sleeper's
   mouth or into the water now answers it, tells it, and — if they love the sleeper — never forgives it
   (D-186) — and thinks of what everyone says about the bitten, from across the room (D-187). And a
   settlement's law is kept by its people now: whoever saw a bite in the yard means to see the bitten
   quarantined, in the law's own words, and the bitten know what is coming; a host seen spitting into a
   sleeper's mouth comes under it too (D-188). And the models are spent on what matters: someone with
   nothing new is not asked to remember it (D-189), and decides with a model when something is happening
   to them, when there was talk, when they have just come to want something (D-191), or every third
   turn to take stock (D-190) — over ten ordinary turns,
   about half the Clerk's calls are gone. And the names people are called now wound: "whore", "go to
   hell", "waste of space" and the rest heat a temper and shame someone in front of others (D-192). A bite
   seen beside you brings the mouth rules to mind too ("Your bottle, your spoon, your smoke.") (D-193).
   Nothing for you to do.

## Notes (builder)

(append dated notes here: what was tricky, what you tried, anything the next session must know)

- 2026-09-24 (kit maintainer): the engine through P10 was built outside DSH and committed on the owner's
  instruction. Its bodies are in `_impl_*.py` files; see AGENTS.md §4 before changing one. Start at
  13_BUILD_ORDER §4.0, not at P0 task 1.
