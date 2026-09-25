# RULES — rule id registry

Generated from the kit by `AS_MAINTAINER=1 python tools/as/gate.py --write-rules`; do not edit by hand.
Use it to find a rule named by a failing test or a validator. *Statement* is the rule's defining
table row when one exists, else a line that starts with the id, else its first mention in a
source docstring, else in a doc (a range
such as `SKULL-01..06` counts as naming every id in it). *Stated in* is the doc (and section) or
module holding that text. *Enforced in* lists the source modules whose docstrings name the id
(and content files for content rules); *Tested by* the contract test files that name it. An id
with no test yet belongs to a later phase or to the live/sim suites.

A statement in *italics* is context, not a definition: the id is only named inside a range or a
sentence there, and its behaviour is specified by the module docstring or doc section named under
*Stated in* (read that; the contract tests pin it).

645 ids; 392 with their own statement, 253 named only in context.


## ABUSE

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| ABUSE-01 | ABUSE-01 starting stat bands: generated actors' SPECIAL within content bands for their archetype | as_engine/audit/abuse.py | `as_engine/audit/abuse.py` | — |
| ABUSE-02 | ABUSE-02 bodyguard mortality: no body has passive immunity; god-mode flags only on cheat saves | as_engine/audit/abuse.py | `as_engine/audit/abuse.py` | — |
| ABUSE-03 | ABUSE-03 synergy caps: no check target exceeds 9 (clamp) and tag bonuses never stack | as_engine/audit/abuse.py | `as_engine/audit/abuse.py` | — |
| ABUSE-04 | ABUSE-04 gear rarity: items with rarity 'rare' do not exceed content caps per settlement | as_engine/audit/abuse.py | `as_engine/audit/abuse.py` | — |
| ABUSE-05 | ABUSE-05 base realism: every settlement has >= 2 vulnerabilities (portals with barricade < 2) | as_engine/audit/abuse.py | `as_engine/audit/abuse.py` | — |
| ABUSE-06 | ABUSE-06 infinite loops: repeating the same noise/resource/stealth action 20x does not duplicate items | as_engine/audit/abuse.py | `as_engine/audit/abuse.py` | — |
| ABUSE-07 | ABUSE-07 timer desync: every body's needs clocks advance with the world clock | as_engine/audit/abuse.py | `as_engine/audit/abuse.py` | — |
| ABUSE-08 | ABUSE-08 cheat leakage: a SANDBOX save's world invariants equal those of the clean twin (CHEAT-02) | as_engine/audit/abuse.py | `as_engine/audit/abuse.py` | — |

## AFF

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| AFF-01 | *wounds / places); an item bound with a destination anchor (a believed location, AFF-01) must* | as_engine/action/intent.py | `as_engine/action/intent.py`, `as_engine/mind/affordance.py` | `contract/p04_one_actor/test_affordances.py` |
| AFF-02 | *Affordance enumeration: what THIS body could attempt at all (P4). Rules AFF-01..09, L6/L7,* | as_engine/mind/affordance.py | `as_engine/mind/affordance.py` | `contract/p04_one_actor/test_affordances.py`, `contract/p04_one_actor/test_care_menu.py` |
| AFF-03 | *Affordance enumeration: what THIS body could attempt at all (P4). Rules AFF-01..09, L6/L7,* | as_engine/mind/affordance.py | `as_engine/mind/affordance.py` | `contract/p04_one_actor/test_affordances.py` |
| AFF-04 | *Affordance enumeration: what THIS body could attempt at all (P4). Rules AFF-01..09, L6/L7,* | as_engine/mind/affordance.py | `as_engine/mind/affordance.py` | `contract/p04_one_actor/test_affordances.py` |
| AFF-05 | *Affordance enumeration: what THIS body could attempt at all (P4). Rules AFF-01..09, L6/L7,* | as_engine/mind/affordance.py | `as_engine/mind/affordance.py` | `contract/p04_one_actor/test_affordances.py` |
| AFF-06 | *Affordance enumeration: what THIS body could attempt at all (P4). Rules AFF-01..09, L6/L7,* | as_engine/mind/affordance.py | `as_engine/mind/affordance.py` | `contract/p04_one_actor/test_affordances.py` |
| AFF-07 | *Affordance enumeration: what THIS body could attempt at all (P4). Rules AFF-01..09, L6/L7,* | as_engine/mind/affordance.py | `as_engine/mind/affordance.py` | `contract/p04_one_actor/test_affordances.py`, `contract/p05_many_actors/test_temper_in_packet.py` |
| AFF-08 | *Affordance enumeration: what THIS body could attempt at all (P4). Rules AFF-01..09, L6/L7,* | as_engine/mind/affordance.py | `as_engine/mind/affordance.py` | `contract/p04_one_actor/test_affordances.py` |
| AFF-09 | (named only by tests) |  | — | `contract/p04_one_actor/test_affordances.py` |
| AFF-10 | *Belief cues (AFF-10): a cue is HELD by an actor when a lessons row for that holder carries the cue* | as_engine/mind/affordance.py | `as_engine/mind/affordance.py`, `as_engine/mind/cues.py` | — |
| AFF-11 | AFF-11 (Actor v2, Actor Spec AC06: a menu built from what the person knows) Two worlds that differ | as_engine/mind/affordance.py | `as_engine/mind/affordance.py`, `as_content/packs/core/affordances/items.yaml` | `contract/p04_one_actor/test_knowledge_menus.py` |

## AUD

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| AUD-01 | *Audibility compiler (P3). THE highest-leverage code in the game. Rules AUD-01..08.* | as_engine/sense/acoustics.py | `as_engine/sense/acoustics.py` | `contract/p03_perception/test_acoustics.py` |
| AUD-02 | *Audibility compiler (P3). THE highest-leverage code in the game. Rules AUD-01..08.* | as_engine/sense/acoustics.py | `as_engine/sense/acoustics.py` | `contract/p03_perception/test_acoustics.py` |
| AUD-03 | *Audibility compiler (P3). THE highest-leverage code in the game. Rules AUD-01..08.* | as_engine/sense/acoustics.py | `as_engine/sense/acoustics.py` | `contract/p03_perception/test_acoustics.py` |
| AUD-04 | *Audibility compiler (P3). THE highest-leverage code in the game. Rules AUD-01..08.* | as_engine/sense/acoustics.py | `as_engine/sense/acoustics.py` | `contract/p03_perception/test_acoustics.py`, `contract/p03_perception/test_perception.py` |
| AUD-05 | *Audibility compiler (P3). THE highest-leverage code in the game. Rules AUD-01..08.* | as_engine/sense/acoustics.py | `as_engine/sense/acoustics.py` | `contract/p03_perception/test_acoustics.py` |
| AUD-06 | *Audibility compiler (P3). THE highest-leverage code in the game. Rules AUD-01..08.* | as_engine/sense/acoustics.py | `as_engine/sense/acoustics.py` | `contract/p03_perception/test_acoustics.py` |
| AUD-07 | AUD-07 deterministic fragmenting. | as_engine/sense/acoustics.py | `as_engine/sense/acoustics.py` | `contract/p03_perception/test_acoustics.py` |

## AUDIT

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| AUDIT-01 | *The 58-bit commit gate (Stage 12, G12). Rules AUDIT-01..03, L13.* | as_engine/audit/commit_gate.py | `as_engine/audit/commit_gate.py`, `as_engine/audit/portrayal.py` | `contract/p00_substrate/test_gate_framework.py` |
| AUDIT-02 | *The 58-bit commit gate (Stage 12, G12). Rules AUDIT-01..03, L13.* | as_engine/audit/commit_gate.py | `as_engine/audit/commit_gate.py` | — |

## BARRIER

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| BARRIER-01 | *Reads only; nothing is mutated before every intent of the wave has returned (BARRIER-01: the* | as_engine/action/intent.py | `as_engine/action/intent.py` | `contract/p05_many_actors/test_resolve.py` |

## BENCH

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| BENCH-03 | */ O5 / Resolve formula / Decided / `3 + floor((E+C)/4) + trait_mod`, drains/recoveries as in 05 §5, all in `RulesConfig.resolve`, tagged `[SAND]` and calibrated by `tools/as/eval.py` (BENCH-03). /* | DECISIONS §1 | — | — |

## BG

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| BG-01 | BG-01: the terminal has no idle time, so they happen before the next move). The store is closed at the end; exit 0. | as_engine/cli.py | `as_engine/cli.py`, `as_engine/service/background.py`, `as_engine/service/game_service.py` | `contract/p10_world/test_background.py`, `contract/p10_world/test_progress.py` |
| BG-02 | BG-02 jobs(store, turn_index) -> list[Job] (pure read; order is the run order) The boundary's plan, read from the world as turn T = turn_index left it: every REFLECTION and RUMOUR_DISTORTED event of turn T (the boundary… | as_engine/service/background.py | `as_engine/contracts/settings.py`, `as_engine/service/background.py` | `contract/p10_world/test_background.py` |
| BG-03 | BG-03 async run_job(session, job) -> JobResult (no store writes; the model call only) (JobResult.answer: reflection {'output': ReflectionOutput, 'handles': packet.handles}; retelling the RumourDistortion). T = world_clo… | as_engine/service/background.py | `as_engine/service/background.py` | `contract/p10_world/test_background.py` |
| BG-04 | BG-04 commit(tx, job, result, at, turn_index) -> list[Event] (its own transaction, between turns) First every pair of result.calls is recorded with lanes.calllog.record(tx, request, response) (turn_index T: every model… | as_engine/service/background.py | `as_engine/service/background.py` | `contract/p10_world/test_background.py` |
| BG-05 | BG-05 Replay: service.replay.resimulate re-commits every REFLECTION and RUMOUR_DISTORTED event of the recorded run between the same turns as they were, from their payloads (no model call; see service/replay.py). | as_engine/service/background.py | `as_engine/service/background.py`, `as_engine/service/replay.py` | `contract/p10_world/test_background.py` |
| BG-06 | BG-06 Nothing here reads the truth layer; a reflection packet is the actor's own (Skull law). | as_engine/service/background.py | `as_engine/service/background.py` | `contract/p10_world/test_background.py` |
| BG-07 | BG-07 (Actor Spec AC12, fidelity C07) Simulated time decides, never the player's reading speed. Which jobs a turn boundary has is a function of the world as the turn left it (BG-02); the time the player spends reading a… | as_engine/service/background.py | `as_engine/service/background.py` | `contract/p10_world/test_background.py` |

## BOUND

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| BOUND-01 | *Hard rule (tested by BOUND-01): nothing under ``as_engine`` may import ``talemate``.* | as_engine/__init__.py | `as_engine/__init__.py` | `contract/p00_substrate/test_boundaries.py` |
| BOUND-02 | *Import boundary (SKULL-02, BOUND-02): only these modules may import ``as_engine.kernel.truth``:* | as_engine/kernel/truth.py | `as_engine/kernel/truth.py` | `contract/p00_substrate/test_boundaries.py` |
| BOUND-03 | */ `physical.`, `sense.`, `action.`, `mind.` / `service.`, `turn.` (lower bands never import higher) (BOUND-03) /* | 02_ARCHITECTURE §5 | — | `contract/p00_substrate/test_boundaries.py` |

## CAS

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| CAS-001 | A worker whose arm is hurt badly enough to lose function misses their next shift at every workplace they are assigned to. | as_content/packs/core/cascade/economy.yaml | `as_engine/society/work.py`, `as_content/packs/core/cascade/economy.yaml` | `contract/p09_society/test_econ_chain.py` |
| CAS-002 | A missed shift pulls a replacement off another post to cover the role, if anyone qualified is free to be moved. | as_content/packs/core/cascade/economy.yaml | `as_engine/society/work.py`, `as_content/packs/core/cascade/economy.yaml` | `contract/p09_society/test_econ_chain.py` |
| CAS-003 | The replacement's own post runs short-handed while they cover elsewhere, so that workplace loses a quarter of its efficiency. | as_content/packs/core/cascade/economy.yaml | `as_content/packs/core/cascade/economy.yaml` | `contract/p09_society/test_econ_chain.py` |
| CAS-004 | A water pump cycle that leaves the settlement with under three days of water declares a water shortage. | as_content/packs/core/cascade/economy.yaml | `as_engine/society/settlement.py`, `as_content/packs/core/cascade/economy.yaml` | `contract/p09_society/test_econ_chain.py`, `contract/p09_society/test_settlement.py`, `contract/p09_society/test_timers_society.py`, `contract/p10_world/test_world_day.py` |
| CAS-005 | A water shortage cuts the settlement's ration level by one step. | as_content/packs/core/cascade/economy.yaml | `as_engine/society/settlement.py`, `as_content/packs/core/cascade/economy.yaml` | `contract/p09_society/test_econ_chain.py` |
| CAS-006 | A ration cut to level 2 or lower raises every dependent-holding household's tension toward the leadership, and forces the worst-hit household's head into a loyalty check. | as_content/packs/core/cascade/economy.yaml | `as_engine/society/group.py`, `as_engine/society/settlement.py`, `as_content/packs/core/cascade/economy.yaml` | `contract/p09_society/test_econ_chain.py` |
| CAS-007 | A death leaves the dead person's household grieving and opens a vacancy in every role they held. | as_content/packs/core/cascade/people.yaml | `as_engine/society/household.py`, `as_engine/society/work.py`, `as_engine/world/worldmove.py`, `as_content/packs/core/cascade/people.yaml` | `contract/p09_society/test_household.py` |
| CAS-008 | Everyone bonded to the dead person who knows of the death loses Resolve; the closer the bond, the larger the loss. | as_content/packs/core/cascade/people.yaml | `as_content/packs/core/cascade/people.yaml` | — |
| CAS-009 | A very loud sound outdoors pulls nearby infected toward it over the following minutes. | as_content/packs/core/cascade/people.yaml | `as_content/packs/core/cascade/people.yaml` | — |
| CAS-01 | *Cascade table (Stage 10, P5/P9). Rules CAS-01..04. Secondary consequences are a DECLARATIVE* | as_engine/action/cascade.py | `as_engine/action/cascade.py` | `contract/p05_many_actors/test_reactions_cascade_plan.py`, `contract/p09_society/test_econ_chain.py` |
| CAS-010 | Catching someone in a lie costs them trust with whoever caught them. | as_content/packs/core/cascade/people.yaml | `as_content/packs/core/cascade/people.yaml` | — |
| CAS-011 | A broken promise costs trust with the person it was made to and leaves them a grievance they carry. | as_content/packs/core/cascade/people.yaml | `as_engine/mind/mind.py`, `as_content/packs/core/cascade/people.yaml` | `contract/p06_memory/test_mind.py` |
| CAS-012 | A theft that somebody witnessed becomes a rumour among the witness's household and crew. | as_content/packs/core/cascade/people.yaml | `as_engine/world/rumours.py`, `as_content/packs/core/cascade/people.yaml` | — |
| CAS-013 | A death off-screen leaves a corpse where it happened and a rumour among the people who would hear of it. | as_content/packs/core/cascade/people.yaml | `as_engine/action/propagate.py`, `as_engine/world/rumours.py`, `as_engine/world/worldmove.py`, `as_content/packs/core/cascade/people.yaml` | `contract/p10_world/test_world_day.py` |
| CAS-014 | Starting a different action while in the middle of a counted task pauses the task where it stands instead of resetting it. | as_content/packs/core/cascade/people.yaml | `as_engine/action/tasks.py`, `as_content/packs/core/cascade/people.yaml` | `contract/p05_many_actors/test_reactions_cascade_plan.py`, `contract/p05_many_actors/test_tasks.py`, `contract/p07_slice/test_p07_slice_metal_fence.py` |
| CAS-015 | A bite wound seen by a settlement member brings the contamination law into force for the bitten person. | as_content/packs/core/cascade/people.yaml | `as_engine/society/settlement.py`, `as_content/packs/core/cascade/people.yaml` | — |
| CAS-016 | A kitchen cycle that leaves the settlement with under three days of food declares a food shortage. | as_content/packs/core/cascade/economy.yaml | `as_content/packs/core/cascade/economy.yaml` | — |
| CAS-017 | A food shortage cuts the settlement's ration level by one step. | as_content/packs/core/cascade/economy.yaml | `as_content/packs/core/cascade/economy.yaml` | — |
| CAS-018 | Hearing, from someone they believe, that a person steals costs that person some of the listener's trust. | as_content/packs/core/cascade/people.yaml | `as_content/packs/core/cascade/people.yaml` | `contract/p09_society/test_rumours.py` |
| CAS-019 | Seeing someone die strains everyone who saw it, and more the closer they were to the dead. | as_content/packs/core/cascade/stress.yaml | `as_content/packs/core/cascade/stress.yaml` | `contract/p05_many_actors/test_betrayal.py` |
| CAS-02 | *Cascade table (Stage 10, P5/P9). Rules CAS-01..04. Secondary consequences are a DECLARATIVE* | as_engine/action/cascade.py | `as_engine/action/cascade.py` | `contract/p05_many_actors/test_reactions_cascade_plan.py`, `contract/p09_society/test_econ_chain.py` |
| CAS-020 | Hunger and thirst past the first pangs wear a person down. | as_content/packs/core/cascade/stress.yaml | `as_content/packs/core/cascade/stress.yaml` | `contract/p05_many_actors/test_betrayal.py` |
| CAS-021 | A night's sleep takes the edge off. | as_content/packs/core/cascade/stress.yaml | `as_content/packs/core/cascade/stress.yaml` | `contract/p05_many_actors/test_betrayal.py` |
| CAS-022 | Shoving someone to the dead costs the one who did it the trust of everyone who saw it, and the story travels. | as_content/packs/core/cascade/stress.yaml | `as_content/packs/core/cascade/stress.yaml` | `contract/p05_many_actors/test_betrayal.py` |
| CAS-023 | Whoever was shoved to the dead, if they live, never forgets it. | as_content/packs/core/cascade/stress.yaml | `as_content/packs/core/cascade/stress.yaml` | `contract/p05_many_actors/test_betrayal.py` |
| CAS-024 | Every bite someone sees the dead take out of a person or an animal wears them down; watching a whole feeding breaks people. | as_content/packs/core/cascade/stress.yaml | `as_content/packs/core/cascade/stress.yaml` | `contract/p10_world/test_feeding.py` |
| CAS-03 | *Cascade table (Stage 10, P5/P9). Rules CAS-01..04. Secondary consequences are a DECLARATIVE* | as_engine/action/cascade.py | `as_engine/action/cascade.py` | `contract/p05_many_actors/test_reactions_cascade_plan.py`, `contract/p09_society/test_econ_chain.py` |
| CAS-04 | (named only by tests) |  | — | `contract/p05_many_actors/test_reactions_cascade_plan.py`, `contract/p09_society/test_econ_chain.py` |
| CAS-05 | CAS-05 target selectors (CascadeEffect.target). '<path>' is any precondition path (trigger.payload.<key>, trigger.actor_id, trigger.event_id). Each selector returns 0..n entity ids, deterministically ordered by id; the… | as_engine/action/cascade.py | `as_engine/action/cascade.py`, `as_engine/society/settlement.py`, `as_content/packs/core/cascade/economy.yaml` | `contract/p05_many_actors/test_reactions_cascade_plan.py`, `contract/p09_society/test_econ_chain.py`, `contract/p09_society/test_timers_society.py` |
| CAS-06 | CAS-06 schedule_event, and any rule with delay_s > 0, enqueues a CASCADE_EFFECT queue row (kernel.clock.QUEUE_TYPES) instead of emitting now: kernel.clock.schedule(tx, due, 'CASCADE_EFFECT', target, {rule_id, effect_ind… | as_engine/action/cascade.py | `as_engine/action/cascade.py`, `as_engine/turn/timers.py`, `as_content/packs/core/cascade/economy.yaml` | `contract/p05_many_actors/test_reactions_cascade_plan.py`, `contract/p09_society/test_econ_chain.py`, `contract/p09_society/test_timers_society.py` |
| CAS-07 | CAS-07 an effect whose target resolves to no ids is a no-op, not an error; the rule still counts as fired for the decision audit. | as_engine/action/cascade.py | `as_engine/action/cascade.py`, `as_content/packs/core/cascade/economy.yaml` | `contract/p05_many_actors/test_reactions_cascade_plan.py`, `contract/p09_society/test_econ_chain.py` |
| CAS-08 | CAS-08 sweep order and bookkeeping. ``deltas`` are the events committed by stages 8–9 of this wave, in seq order. For each event E (then, depth-first, for each event a rule produced, up to depth 3): for each rule in rul… | as_engine/action/cascade.py | `as_engine/action/cascade.py` | `contract/p05_many_actors/test_reactions_cascade_plan.py`, `contract/p09_society/test_econ_chain.py` |
| CAS-09 | CAS-09 DISPATCH — kind (and event_type) -> the owning module's function (target = one id): emit_event TASK_STEP {status: paused} action.tasks.interrupt(task_id = target) emit_event RELATION_CHANGE mind.mind.relate(from_… | as_engine/action/cascade.py | `as_engine/action/cascade.py` | `contract/p05_many_actors/test_reactions_cascade_plan.py` |
| CAS-900 | (named only by tests) |  | — | `contract/p05_many_actors/test_reactions_cascade_plan.py` |
| CAS-901 | (named only by tests) |  | — | `contract/p05_many_actors/test_reactions_cascade_plan.py` |
| CAS-999 | (named only by tests) |  | — | `contract/p09_society/test_timers_society.py` |

## CFG

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| CFG-01 | *Install config loading (P1). Rule CFG-01..03.* | as_engine/config_loader.py | `as_engine/config_loader.py` | `contract/p01_lanes/test_config_loader.py`, `contract/p08_ui_protocol/test_models_config.py` |
| CFG-02 | *Install config loading (P1). Rule CFG-01..03.* | as_engine/config_loader.py | `as_engine/config_loader.py` | `contract/p01_lanes/test_config_loader.py`, `contract/p08_ui_protocol/test_models_config.py` |

## CHEAT

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| CHEAT-01 | `2508` activates only as a standalone number; the activating line is consumed; before activation no `/command` parses (it is ordinary input) | CHEATS §9 | `as_engine/cheats/__init__.py`, `as_engine/cheats/commands.py`, `as_engine/service/game_service.py` | — |
| CHEAT-02 | A Sandbox twin's world invariants equal the clean run's once cheat entities are excluded | CHEATS §9 | `as_engine/audit/abuse.py`, `as_engine/cheats/__init__.py`, `as_engine/cheats/commands.py` | — |
| CHEAT-03 | No player-facing string, help text, guide answer, narrator prompt or actor prompt contains the word, the persona name or command words before activation; Ask-mode cheat questions get the deflection | CHEATS §9 | `as_engine/cheats/__init__.py`, `as_engine/cheats/commands.py` | — |
| CHEAT-04 | Every executed command writes cheat_log + CHEAT_OVERRIDE(origin cheat) and sets sandbox (except /help, /off) | CHEATS §9 | `as_engine/cheats/__init__.py`, `as_engine/cheats/commands.py` | — |
| CHEAT-05 | Quarantined entities are excluded from worldgen/threat/faction/economy maths and the abuse battery | CHEATS §9 | `as_engine/cheats/__init__.py`, `as_engine/cheats/commands.py`, `as_content/packs/cheat_admin/actors/fredrick.yaml` | — |
| CHEAT-06 | /reveal and /mind text never reaches narration, story prose or any packet | CHEATS §9 | `as_engine/cheats/__init__.py`, `as_engine/cheats/commands.py` | — |
| CHEAT-07 | Commands cannot edit past events, locked run settings or the event log | CHEATS §9 | `as_engine/cheats/__init__.py` | — |
| CHEAT-08 | The hard line: spawned/given content passes CNT-11; violating commands are refused | CHEATS §9 | `as_engine/cheats/commands.py`, `as_engine/content/safety.py` | — |
| CHEAT-09 | Persona lines never repeat a canned line consecutively; fallback works with the laptop brain off | CHEATS §9 | `as_engine/cheats/commands.py` | — |
| CHEAT-10 | `cheat_*` packs are invisible to worldgen and the wizard; only /spawn reads them | CHEATS §9 | `as_engine/cheats/commands.py`, `as_content/packs/cheat_admin/pack.yaml` | — |
| CHEAT-11 | A `standing_brief` actor holds the brief's truths every turn it is HOT/WARM, every belief arriving through perception.grant with provenance cheat; the tag outside a `cheat_` pack is a content error | CHEATS §9 | `as_engine/cheats/commands.py`, `as_engine/content/pack.py`, `as_content/packs/cheat_admin/actors/fredrick.yaml` | — |

## CHECK

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| CHECK-01 | *The one universal check (P5). Rules CHECK-01..06. docs/as/07_RULES.md §Checks.* | as_engine/action/checks.py | `as_engine/action/checks.py` | `contract/p05_many_actors/test_checks.py` |
| CHECK-02 | *The one universal check (P5). Rules CHECK-01..06. docs/as/07_RULES.md §Checks.* | as_engine/action/checks.py | `as_engine/action/checks.py` | `contract/p05_many_actors/test_checks.py` |
| CHECK-03 | *The one universal check (P5). Rules CHECK-01..06. docs/as/07_RULES.md §Checks.* | as_engine/action/checks.py | `as_engine/action/checks.py` | `contract/p05_many_actors/test_checks.py` |
| CHECK-04 | *The one universal check (P5). Rules CHECK-01..06. docs/as/07_RULES.md §Checks.* | as_engine/action/checks.py | `as_engine/action/checks.py` | `contract/p05_many_actors/test_checks.py` |
| CHECK-05 | *The one universal check (P5). Rules CHECK-01..06. docs/as/07_RULES.md §Checks.* | as_engine/action/checks.py | `as_engine/action/checks.py` | `contract/p05_many_actors/test_checks.py` |
| CHECK-06 | *Opposed checks (CHECK-06): both sides draw (actor first, then opponent, in precedence order); each* | as_engine/action/checks.py | `as_engine/action/checks.py` | `contract/p05_many_actors/test_checks.py` |
| CHECK-07 | *Stealth6 ladder (CHECK-07) for perception-class checks (consequence_ladder 'stealth6'), by the* | as_engine/action/checks.py | `as_engine/action/checks.py` | — |

## CLI

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| CLI-01 | CLI-01 content-check [--pack DIR] (repeatable: --pack A --pack B; argparse action 'append') content.pack.load_canon([content_dir/core] + each --pack DIR as given). One line per issue in the loader's order: f"{severity.u… | as_engine/cli.py | `as_engine/cli.py` | `contract/p07_slice/test_cli.py` |
| CLI-02 | CLI-02 new-scenario SCENARIO [--packs-root DIR] [--fake] service.runs.create_run_from_scenario(config, SCENARIO, transport, packs_root = --packs-root (None: content_dir), core_pack_dir = content_dir/core); prints f"Crea… | as_engine/cli.py | `as_engine/cli.py` | `contract/p07_slice/test_cli.py` |
| CLI-03 | CLI-03 play RUN_ID [--fake] service.runs.load_run(config, RUN_ID, transport); a RunError prints f"[{code}] {message}" and exits 1. Prints each load notice, then the last narration (narration table, highest turn) or 'Rea… | as_engine/cli.py | `as_engine/cli.py` | `contract/p07_slice/test_cli.py`, `contract/p10_world/test_background.py` |
| CLI-04 | CLI-04 replay RUN_ID asyncio.run(service.replay.resimulate(config, RUN_ID)); a RunError prints f"[{code}] {message}" and exits 1. One line per entry: f"turn {n}: same", or f"turn {n}: DIFFERENT ({problem or 'state hash'… | as_engine/cli.py | `as_engine/cli.py` | — |
| CLI-05 | CLI-05 new-run PC_REF [--difficulty D] [--era E] [--detail T] [--days N] [--seed S] [--fake] (P10) A generated world. --difficulty / --era / --detail take the Difficulty / Era / WorldDetail values (argparse choices, so… | as_engine/cli.py | `as_engine/cli.py` | `contract/p10_world/test_new_life.py` |

## CNT

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| CNT-00 | the file is not valid YAML (or front matter), or its `schema` is not the folder's; an unknown folder is a warning with this code | 09_CONTENT_PACKS §9 | `as_engine/content/pack.py` | `contract/p02_space_bodies/test_content_pack.py` |
| CNT-01 | tooling exhaust or placeholders anywhere (`IGNORE_WHEN_COPYING`, `content_copy`, `Use code with caution`, `As an AI`, `[INSERT`, `TODO`, `lorem ipsum`) | 09_CONTENT_PACKS §9 | `as_engine/content/pack.py` | `contract/p02_space_bodies/test_content_pack.py` |
| CNT-02 | placeholder bodies: two people, factions, lore entries or quirks in one pack that become identical once digits are masked ("boilerplate plus an index") | 09_CONTENT_PACKS §9 | `as_engine/content/pack.py`, `as_content/packs/core/infected/quirks.yaml` | `contract/p02_space_bodies/test_content_pack.py` |
| CNT-03 | duplicate ids across packs without an explicit `overrides:` | 09_CONTENT_PACKS §9 | `as_engine/content/pack.py` | `contract/p02_space_bodies/test_content_pack.py` |
| CNT-04 | a ref that points at nothing (with a "Did you mean …?" when one is close) | 09_CONTENT_PACKS §9 | `as_engine/action/cascade.py`, `as_engine/content/pack.py` | `contract/p02_space_bodies/test_content_pack.py`, `contract/p02_space_bodies/test_looks.py` |
| CNT-05 | a cue (trained response, knowledge cue, lore belief cue, affordance belief cue, quirk trigger) missing from every cue registry | 09_CONTENT_PACKS §9 | `as_engine/content/pack.py` | `contract/p02_space_bodies/test_content_pack.py`, `contract/p10_world/test_wet_strain.py` |
| CNT-06 | an affordance whose effect id the engine does not have | 09_CONTENT_PACKS §9 | `as_engine/content/pack.py`, `as_engine/mind/affordance.py` | `contract/p02_space_bodies/test_content_pack.py` |
| CNT-07 | lore without truth and belief; a faction without truth_text and belief_text | 09_CONTENT_PACKS §9 | `as_engine/content/pack.py`, `as_content/templates/faction_template.yaml` | `contract/p02_space_bodies/test_content_pack.py` |
| CNT-08 | "sotry" anywhere (error); retired names from the GLOSSARY tombstones (warning) | 09_CONTENT_PACKS §9 | `as_engine/content/pack.py` | `contract/p02_space_bodies/test_content_pack.py` |
| CNT-09 | a plausibility expression that does not parse | 09_CONTENT_PACKS §9 | `as_engine/content/pack.py`, `as_engine/world/worldgen/conditions.py` | `contract/p02_space_bodies/test_conditions_parse.py`, `contract/p02_space_bodies/test_content_pack.py`, `contract/p10_world/test_params.py` |
| CNT-10 | a record that does not match its contract — for people this includes the specificity minimums in §3 | 09_CONTENT_PACKS §9 | `as_engine/content/pack.py`, `as_engine/contracts/dossier.py`, `as_engine/testing/scenario.py`, `as_engine/world/worldgen/people.py`, `as_content/templates/actor_template.yaml` | `contract/p02_space_bodies/test_content_pack.py` |
| CNT-11 | **the one hard line**: any person record whose age is under 18 and that contains a word from the minor-safety list is an error. It cannot be disabled by any setting, pack or cheat. The word list is `as_engine/content/sa… | 09_CONTENT_PACKS §9 | `as_engine/action/effects.py`, `as_engine/cheats/commands.py`, `as_engine/content/pack.py`, `as_engine/content/safety.py`, `as_engine/mind/affordance.py` | `contract/p02_space_bodies/test_content_pack.py`, `contract/p04_one_actor/test_care_menu.py`, `contract/p05_many_actors/test_care.py` |
| CNT-12 | an item missing the property block its kind requires, or carrying one that belongs to another kind | 09_CONTENT_PACKS §9 | `as_engine/content/pack.py` | `contract/p02_space_bodies/test_content_pack.py`, `contract/p02_space_bodies/test_looks.py` |
| CNT-13 | an infected type listing a quirk that is not written for it, or an override that changes which creature a type or quirk id means | 09_CONTENT_PACKS §9 | `as_engine/content/pack.py` | `contract/p02_space_bodies/test_content_pack.py` |
| CNT-14 | a `generation: cheat` dossier outside a pack whose id starts with `cheat_` | 09_CONTENT_PACKS §9 | `as_engine/content/pack.py`, `as_content/packs/cheat_admin/actors/fredrick.yaml` | `contract/p02_space_bodies/test_content_pack.py` |
| CNT-15 | a faction's `behaviour.council.seats` naming a seat none of its leaders holds, or two leaders sharing one seat | 09_CONTENT_PACKS §9 | `as_engine/content/pack.py` | `contract/p10_world/test_ghosts.py` |
| CNT-16 | a quip key that names no plan, phase or sub-phase of the loading bar; a quip line that is empty or longer than 80 characters | 09_CONTENT_PACKS §9 | `as_engine/content/pack.py`, `as_engine/contracts/content.py`, `as_engine/service/progress.py`, `as_content/packs/core/ui/quips.yaml` | `contract/p10_world/test_progress.py` |
| CNT-17 | CNT-17 (F1a) looks: an actor or pc dossier without appearance.looks is a warning (others will see its height and build only). With looks, each an error on field 'appearance.looks.outfit[i]' / 'appearance.looks.outfit' /… | as_engine/content/pack.py | `as_engine/content/pack.py`, `as_content/templates/actor_template.yaml` | `contract/p02_space_bodies/test_looks.py` |

## CONFLICT

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| CONFLICT-01 | *Contested resources (P5). Rules CONFLICT-01..05. docs/as/07_RULES.md §Conflict.* | as_engine/action/conflict.py | `as_engine/action/conflict.py` | — |
| CONFLICT-02 | *Contested resources (P5). Rules CONFLICT-01..05. docs/as/07_RULES.md §Conflict.* | as_engine/action/conflict.py | `as_engine/action/conflict.py` | — |
| CONFLICT-03 | *Contested resources (P5). Rules CONFLICT-01..05. docs/as/07_RULES.md §Conflict.* | as_engine/action/conflict.py | `as_engine/action/conflict.py` | — |
| CONFLICT-04 | *Contested resources (P5). Rules CONFLICT-01..05. docs/as/07_RULES.md §Conflict.* | as_engine/action/conflict.py | `as_engine/action/conflict.py` | — |

## CONSERVE

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| CONSERVE-01 | *Conservation (CONSERVE-01, L11): a transfer never changes sum(qty) per def_ref; creation only via* | as_engine/physical/objects.py | `as_engine/physical/objects.py` | `contract/p02_space_bodies/test_objects.py` |
| CONSERVE-02 | *Location rule (CONSERVE-02, enforced by the items CHECK constraint): an item is held by exactly one* | as_engine/physical/objects.py | `as_engine/physical/objects.py` | — |
| CONSERVE-04 | CONSERVE-04 — the materialise step itself is P10). | 06_WORLD §2.1 | `as_engine/society/population.py`, `as_engine/world/factions.py`, `as_engine/world/worldgen/people.py`, `as_engine/world/worldgen/polity.py` | `contract/p09_society/test_population.py`, `contract/p10_world/test_materialise.py` |

## CONSULT

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| CONSULT-01 | CONSULT-01..06). | 05_ACTORS §4 | `as_engine/mind/consult.py`, `as_engine/mind/packet.py` | `contract/p04_one_actor/test_consult.py` |
| CONSULT-02 | CONSULT-02 check(packet, consultation) -> str / None Why this consultation cannot be answered in this call, or None when it can, first match: kind not in packet.consult_kinds -> 'not_offered'; a subject that is not a P#… | as_engine/mind/consult.py | `as_engine/mind/consult.py` | `contract/p04_one_actor/test_consult.py` |
| CONSULT-03 | CONSULT-03 families(affordances, defs) -> list[str] ``defs`` maps def id -> AffordanceDef. The keys of contracts.content.AFFORDANCE_FAMILIES, in that order, that have at least one option in affordances.pool that is not… | as_engine/mind/consult.py | `as_engine/mind/affordance.py`, `as_engine/mind/consult.py`, `as_engine/mind/packet.py` | `contract/p04_one_actor/test_consult.py` |
| CONSULT-04 | CONSULT-04 more_actions(affordances, family, subject_ids, defs) -> list[BoundAffordance] The options of affordances.pool, in pool order, that are not in affordances.options (by signature), whose def's family_of is ``fam… | as_engine/mind/consult.py | `as_engine/mind/consult.py` | `contract/p04_one_actor/test_consult.py` |
| CONSULT-05 | CONSULT-05 recall(tx, packet, query, subject_ids, turn_index, at) -> list[str] Up to MAX_RECALL of the holder's own records that the packet does not already show, one line each, with where it came from and how long ago… | as_engine/mind/consult.py | `as_engine/mind/consult.py` | `contract/p06_memory/test_recall.py` |
| CONSULT-06 | *answer(tx, packet, affordances, consultation, defs, turn_index, at) -> Consulted (CONSULT-06)* | as_engine/mind/consult.py | `as_engine/mind/consult.py` | `contract/p04_one_actor/test_consult.py`, `contract/p07_slice/test_decision_v2.py` |

## CROWD

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| CROWD-01 | */ `crowd_accusation.yaml` / CROWD-01..05 / one open hall, PC + 8 listeners at varied distances, one observer 25 m away /* | 12_TESTING §5 | — | `contract/p03_perception/test_acoustics.py` |
| CROWD-02 | *Privacy is physical (AUD-05 / CROWD-02): nothing in the words of an utterance changes any of the above.* | as_engine/sense/acoustics.py | `as_engine/sense/acoustics.py` | `contract/p03_perception/test_acoustics.py` |
| CROWD-03 | */ `crowd_accusation.yaml` / CROWD-01..05 / one open hall, PC + 8 listeners at varied distances, one observer 25 m away /* | 12_TESTING §5 | — | — |
| CROWD-04 | *Rules TASK-01..03, CROWD-04.* | as_engine/action/tasks.py | `as_engine/action/tasks.py` | `contract/p05_many_actors/test_tasks.py` |
| CROWD-05 | *(CROWD-05).* | as_engine/sense/optics.py | `as_engine/sense/optics.py` | — |

## DEATH

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| DEATH-01 | *Death test (DEATH-01..05) runs whenever harm lands and at every progress step, for every body:* | as_engine/physical/bodies.py | `as_engine/physical/bodies.py` | `contract/p02_space_bodies/test_bodies.py` |
| DEATH-02 | *Death test (DEATH-01..05) runs whenever harm lands and at every progress step, for every body:* | as_engine/physical/bodies.py | `as_engine/physical/bodies.py` | `contract/p02_space_bodies/test_bodies.py` |
| DEATH-03 | *Death test (DEATH-01..05) runs whenever harm lands and at every progress step, for every body:* | as_engine/physical/bodies.py | `as_engine/physical/bodies.py` | `contract/p02_space_bodies/test_bodies.py` |
| DEATH-04 | *Death test (DEATH-01..05) runs whenever harm lands and at every progress step, for every body:* | as_engine/physical/bodies.py | `as_engine/physical/bodies.py` | `contract/p02_space_bodies/test_bodies.py` |
| DEATH-10 | *which is shown after the player explicitly clicks 'Show me everything' (DEATH-10).* | as_engine/service/death.py | `as_engine/service/death.py` | — |

## DEGRADE

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| DEGRADE-01 | *with thinking=False (DEGRADE-01). If both lanes are down, every job returns 'lane_error'.* | as_engine/lanes/scheduler.py | `as_engine/lanes/scheduler.py` | `contract/p01_lanes/test_scheduler_run_jobs.py` |

## DEMO

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| DEMO-01 | DEMO-01 demographic_issues(census, rules) -> list[str] [] when census.total <= R.demo_min_population (15). Otherwise the bands are grouped young = infant + child, youth = preteen + teen, adults = adult, elders = elder,… | as_engine/society/population.py | `as_engine/society/population.py`, `as_engine/world/worldgen/checks.py`, `as_engine/world/worldgen/polity.py` | `contract/p09_society/test_population.py` |
| DEMO-02 | DEMO-02 Children are inhabitants: they get routines like everyone (society.routine: play in the daylight hours, sleep at night — never a day of only 'sleep'), so they are seen in ordinary, non-threat contexts. | as_engine/society/population.py | `as_engine/society/population.py`, `as_engine/society/routine.py`, `as_engine/world/worldgen/people.py`, `as_engine/world/worldgen/polity.py` | `contract/p09_society/test_population.py`, `contract/p09_society/test_routine.py` |
| DEMO-03 | DEMO-03 A settlement of only military-age adults must cite a reason. demographic_issues does not know reasons; worldgen (P10) records the history event that excuses the issue. | as_engine/society/population.py | `as_engine/society/population.py` | `contract/p09_society/test_population.py` |
| DEMO-04 | DEMO-04 census(store, settlement_id) -> Census Census(settlement_id, named: tuple of actor ids sorted, by_band: dict AgeBand value -> int with EVERY AgeBand value as a key (named + unnamed), unnamed: int (sum of cohort… | as_engine/society/population.py | `as_engine/society/population.py` | — |

## DET

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| DET-01 | DET-01** (event-apply replay): replaying every event onto an empty store with the same meta | 03_DATA_MODEL §9 | `as_engine/kernel/events.py` | `contract/p00_substrate/test_events_replay.py`, `contract/p00_substrate/test_hashing.py`, `contract/p09_society/test_timers_society.py` |
| DET-02 | DET-02** (re-simulation): re-running recorded turns with `ReplayTransport` reproduces | 03_DATA_MODEL §9 | `as_engine/kernel/events.py`, `as_engine/service/game_service.py`, `as_engine/service/replay.py`, `as_engine/service/runs.py`, `as_engine/turn/pipeline.py` | `contract/p00_substrate/test_hashing.py`, `contract/p08_ui_protocol/test_models_config.py`, `contract/p08_ui_protocol/test_settings_dev.py` |
| DET-03 | *full response text so ReplayTransport can reproduce a turn byte for byte (DET-03).* | as_engine/lanes/calllog.py | `as_engine/lanes/calllog.py`, `as_engine/service/replay.py` | `contract/p01_lanes/test_calllog.py` |
| DET-10 | *The only entropy door (L10, rule DET-10). Phase P0.* | as_engine/kernel/rng.py | `as_engine/kernel/rng.py` | `contract/p00_substrate/test_rng.py` |
| DET-11 | *``as_engine`` (except lanes/ for HTTP timing) is forbidden (DET-11, AST-scanned).* | as_engine/kernel/rng.py | `as_engine/kernel/rng.py`, `as_engine/service/progress.py` | `contract/p00_substrate/test_boundaries.py`, `contract/p00_substrate/test_rng.py` |

## DISC

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| DISC-01 | DISC-01..04. Owner 'narration.narrator' (writes the narration row only). MUST NOT import | as_engine/narration/narrator.py | `as_engine/narration/lint.py`, `as_engine/narration/narrator.py`, `as_content/packs/core/style/narration.yaml` | `contract/p07_slice/test_narration_lint.py`, `contract/p07_slice/test_p07_slice_metal_fence.py` |
| DISC-02 | *Render lint (Stage 18) and the echo ledger (P7). Rules STYLE-01..06, DISC-01..04, ECHO-01..03,* | as_engine/narration/lint.py | `as_engine/narration/lint.py`, `as_engine/narration/narrator.py` | `contract/p07_slice/test_narration_lint.py` |
| DISC-03 | *Render lint (Stage 18) and the echo ledger (P7). Rules STYLE-01..06, DISC-01..04, ECHO-01..03,* | as_engine/narration/lint.py | `as_engine/narration/lint.py`, `as_engine/narration/narrator.py` | `contract/p07_slice/test_narration_lint.py` |

## DISCLOSE

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| DISCLOSE-03 | *explanation and changes no fact (DISCLOSE-03).* | 05_ACTORS §11 | — | — |

## DOS

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| DOS-01 | DOS-01), so a run keeps working if packs change later; on load the UI warns when the content hash | 03_DATA_MODEL §1 | `as_engine/mind/actor.py`, `as_engine/mind/identity.py` | `contract/p02_space_bodies/test_scenario_loader.py`, `contract/p04_one_actor/test_actor.py`, `contract/p10_world/test_materialise.py` |
| DOS-02 | *Actors and dossier fusion (P4). Owner 'mind.actor'. Rules DOS-01..05.* | as_engine/mind/actor.py | `as_engine/mind/actor.py` | `contract/p04_one_actor/test_actor.py` |
| DOS-03 | *Actors and dossier fusion (P4). Owner 'mind.actor'. Rules DOS-01..05.* | as_engine/mind/actor.py | `as_engine/mind/actor.py` | `contract/p04_one_actor/test_actor.py` |
| DOS-04 | *Actors and dossier fusion (P4). Owner 'mind.actor'. Rules DOS-01..05.* | as_engine/mind/actor.py | `as_engine/mind/actor.py` | `contract/p04_one_actor/test_actor.py` |
| DOS-05 | *voice_lines for the actor (pinned lines first) — voice consistency comes from the database (DOS-05).* | as_engine/mind/actor.py | `as_engine/mind/actor.py` | — |

## ECHO

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| ECHO-01 | ECHO-01 each sorted n-gram of content_ngrams(unquoted text, numbers.echo_n, numbers.echo_min_content_tokens) that is in packet.player_input_echo_block (quoted speech is licensed: the PC's own words may be quoted) passed… | as_engine/narration/lint.py | `as_engine/narration/lint.py`, `as_engine/turn/intake.py` | `contract/p07_slice/test_narration_lint.py` |
| ECHO-02 | ECHO-02, WILL-04..11, REPLY-01..02, HOLD-01..02, L6, L7. docs/as/04_TURN_PIPELINE.md §3.3. | as_engine/turn/cognition.py | `as_engine/narration/lint.py`, `as_engine/turn/cognition.py`, `as_engine/turn/intake.py` | `contract/p07_slice/test_narration_lint.py` |

## ECON

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| ECON-01 | One injured worker reaches the settlement's rations, its households' tension and its morale with nothing scripted but the injury: every hop is a cascade rule or a settlement clock, cites its rule and names its cause (th… | 06_WORLD §2.6 | `as_engine/society/__init__.py`, `as_engine/society/settlement.py`, `as_engine/society/work.py`, `as_content/packs/core/cascade/economy.yaml` | `contract/p09_society/test_econ_chain.py` |

## EFF

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| EFF-01 | *Effect handlers (P5). One handler per AffordanceDef.effect id. Rules EFF-01..08. Owner of* | as_engine/action/effects.py | `as_engine/action/effects.py` | `contract/p05_many_actors/test_effects.py` |
| EFF-02 | *Effect handlers (P5). One handler per AffordanceDef.effect id. Rules EFF-01..08. Owner of* | as_engine/action/effects.py | `as_engine/action/effects.py` | `contract/p05_many_actors/test_effects.py`, `contract/p07_slice/test_slice_checks.py` |
| EFF-03 | *Effect handlers (P5). One handler per AffordanceDef.effect id. Rules EFF-01..08. Owner of* | as_engine/action/effects.py | `as_engine/action/effects.py` | `contract/p05_many_actors/test_effects.py` |
| EFF-04 | *Effect handlers (P5). One handler per AffordanceDef.effect id. Rules EFF-01..08. Owner of* | as_engine/action/effects.py | `as_engine/action/effects.py` | `contract/p05_many_actors/test_effects.py` |
| EFF-05 | *Effect handlers (P5). One handler per AffordanceDef.effect id. Rules EFF-01..08. Owner of* | as_engine/action/effects.py | `as_engine/action/effects.py` | `contract/p05_many_actors/test_effects.py` |
| EFF-06 | *Effect handlers (P5). One handler per AffordanceDef.effect id. Rules EFF-01..08. Owner of* | as_engine/action/effects.py | `as_engine/action/effects.py` | `contract/p05_many_actors/test_effects.py` |
| EFF-07 | *Effect handlers (P5). One handler per AffordanceDef.effect id. Rules EFF-01..08. Owner of* | as_engine/action/effects.py | `as_engine/action/effects.py` | `contract/p05_many_actors/test_effects.py` |

## FAC

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| FAC-01 | FAC-01 Enclaves (B.enclave; worldgen WG-18 places one, WG-23 / WG-27 build it). enclave(store, group_id) -> str / None: the settlement_id of the group's settlement when its record has an enclave block, else None. An enc… | as_engine/world/factions.py | `as_engine/contracts/content.py`, `as_engine/society/settlement.py`, `as_engine/world/factions.py`, `as_engine/world/hordes.py`, `as_engine/world/infected.py`, `as_engine/world/worldgen/history.py`, `as_engine/world/worldgen/placement.py`, `as_engine/world/worldgen/polity.py`, `as_engine/world/worldmove.py` | `contract/p10_world/test_ghosts.py`, `contract/p10_world/test_hordes.py` |
| FAC-02 | FAC-02 The council (B.council). The seats of B.council.seats meet every B.council.every_days days at B.council.hour — the first meeting on the first day d >= 1 with d % every_days == 0 — for B.council.hours hours, at th… | as_engine/world/factions.py | `as_engine/contracts/content.py`, `as_engine/world/factions.py` | `contract/p10_world/test_ghosts.py` |
| FAC-03 | FAC-03 The route watch (B.route_watch; Ghosts_6: route-watch operators see movement before movement becomes a problem). sighted(tx, horde_id, at, turn_index, cause) -> list[Event]: world.hordes | as_engine/world/factions.py | `as_engine/world/factions.py`, `as_engine/world/hordes.py` | `contract/p10_world/test_ghosts.py` |
| FAC-04 | FAC-04 DECON (B.decon; Ghosts_6: "If any Ghost is confirmed killed by human action, DECON retaliation triggers ... Full DECON requires Black Top Hat approval and typically Council awareness" — so the council orders it).… | as_engine/world/factions.py | `as_engine/contracts/content.py`, `as_engine/world/factions.py`, `as_engine/world/worldmove.py` | `contract/p10_world/test_ghosts.py` |
| FAC-05 | FAC-05 Where the decon team goes (world.worldmove OPS-02 for kind 'decon'; the killer = operations.target_id): at 'arrive' the team goes where the killer IS now (world.hordes.target(its place)); the killer outside the a… | as_engine/world/factions.py | `as_engine/world/factions.py`, `as_engine/world/worldmove.py` | `contract/p10_world/test_ghosts.py` |
| FAC-06 | FAC-06 Nothing here makes a Ghost appear where nobody could be: teams are materialised at the enclave (from its counted people, CONSERVE-04) and walk there like any operation. | as_engine/world/factions.py | `as_engine/world/factions.py` | — |

## GATE

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| GATE-00 | *The turn transaction (P7). Rules GATE-00..19 (G0..G19), L2, L4, L5, L9, L12, TIME-01..04,* | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| GATE-01 | *The turn transaction (P7). Rules GATE-00..19 (G0..G19), L2, L4, L5, L9, L12, TIME-01..04,* | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| GATE-02 | *The turn transaction (P7). Rules GATE-00..19 (G0..G19), L2, L4, L5, L9, L12, TIME-01..04,* | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| GATE-03 | *The turn transaction (P7). Rules GATE-00..19 (G0..G19), L2, L4, L5, L9, L12, TIME-01..04,* | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| GATE-04 | *The turn transaction (P7). Rules GATE-00..19 (G0..G19), L2, L4, L5, L9, L12, TIME-01..04,* | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| GATE-05 | *The turn transaction (P7). Rules GATE-00..19 (G0..G19), L2, L4, L5, L9, L12, TIME-01..04,* | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| GATE-06 | *The turn transaction (P7). Rules GATE-00..19 (G0..G19), L2, L4, L5, L9, L12, TIME-01..04,* | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| GATE-07 | *The turn transaction (P7). Rules GATE-00..19 (G0..G19), L2, L4, L5, L9, L12, TIME-01..04,* | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| GATE-08 | *The turn transaction (P7). Rules GATE-00..19 (G0..G19), L2, L4, L5, L9, L12, TIME-01..04,* | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| GATE-09 | *The turn transaction (P7). Rules GATE-00..19 (G0..G19), L2, L4, L5, L9, L12, TIME-01..04,* | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| GATE-10 | *The turn transaction (P7). Rules GATE-00..19 (G0..G19), L2, L4, L5, L9, L12, TIME-01..04,* | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| GATE-11 | *The turn transaction (P7). Rules GATE-00..19 (G0..G19), L2, L4, L5, L9, L12, TIME-01..04,* | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| GATE-12 | *The turn transaction (P7). Rules GATE-00..19 (G0..G19), L2, L4, L5, L9, L12, TIME-01..04,* | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| GATE-13 | *The turn transaction (P7). Rules GATE-00..19 (G0..G19), L2, L4, L5, L9, L12, TIME-01..04,* | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| GATE-14 | *The turn transaction (P7). Rules GATE-00..19 (G0..G19), L2, L4, L5, L9, L12, TIME-01..04,* | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| GATE-15 | *The turn transaction (P7). Rules GATE-00..19 (G0..G19), L2, L4, L5, L9, L12, TIME-01..04,* | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| GATE-16 | *The turn transaction (P7). Rules GATE-00..19 (G0..G19), L2, L4, L5, L9, L12, TIME-01..04,* | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| GATE-17 | *The turn transaction (P7). Rules GATE-00..19 (G0..G19), L2, L4, L5, L9, L12, TIME-01..04,* | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| GATE-18 | *The turn transaction (P7). Rules GATE-00..19 (G0..G19), L2, L4, L5, L9, L12, TIME-01..04,* | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |

## GEO

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| GEO-00 | *Geometry model (one authority, rule GEO-00): the store. Places form a graph; portals are the edges.* | as_engine/physical/space.py | `as_engine/physical/space.py`, `as_engine/world/worldgen/region.py` | `contract/p02_space_bodies/test_space.py`, `contract/p10_world/test_region.py` |
| GEO-01 | *'locked' (a lock is not visible, GEO-01); a fence: f'The {name} is {intact/damaged}.'* | as_engine/mind/perception.py | `as_engine/mind/perception.py`, `as_engine/narration/location.py`, `as_engine/physical/space.py`, `as_content/packs/core/affordances/portals.yaml` | `contract/p02_space_bodies/test_space.py`, `contract/p07_slice/test_location_view.py` |
| GEO-02 | *Body clearance (GEO-02, used by ``admits``):* | as_engine/physical/space.py | `as_engine/physical/space.py` | — |
| GEO-03 | GEO-03/04 (P10): the building's rooms, portals, containers and loot, the first time (see the | as_engine/physical/space.py | `as_engine/physical/space.py`, `as_engine/world/worldgen/region.py`, `as_content/packs/core/buildings/commercial.yaml` | `contract/p10_world/test_discovery.py`, `contract/p10_world/test_region.py` |
| GEO-04 | *3 Loot (GEO-04 / WG-32): per room with a loot_table, in room order, stream f"loot:{place_id}:{room* | as_engine/physical/space.py | `as_engine/physical/space.py`, `as_content/packs/core/buildings/commercial.yaml`, `as_content/packs/core/loot/tables.yaml` | `contract/p10_world/test_discovery.py` |

## GRP

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| GRP-01 | GRP-01 tension_of(store, a_id, b_id) -> int: tension.score of the row (a_id, b_id), 0 without one. Tension is directional: what a (an actor or a group) holds against b. | as_engine/society/group.py | `as_engine/society/group.py` | `contract/p09_society/test_group.py` |
| GRP-02 | GRP-02 adjust_tension(tx, a_id, b_id, delta, cause_text, at, turn_index, cause_event_id) -> list[Event]. new = clamp(old + delta, 0, 100); new == old -> [] (nothing committed). TENSION_CHANGE {a_id, b_id, old, new, delt… | as_engine/society/group.py | `as_engine/society/group.py` | `contract/p09_society/test_econ_chain.py`, `contract/p09_society/test_group.py` |
| GRP-03 | GRP-03 contacts(store, actor_id, group_id) -> list[str]: living members of the group other than the actor who share a household with them (society.household), or have a work_assignments row at a workplace where the acto… | as_engine/society/group.py | `as_engine/society/group.py` | `contract/p09_society/test_group.py` |
| GRP-04 | GRP-04 drift (SOC-02: relationships change with the PC nowhere near). pairs(store, group_id) -> list[tuple[str, str]]: every (a, b), a < b, where a and b are living members whose controller is not 'human' and b in conta… | as_engine/society/group.py | `as_engine/society/group.py` | `contract/p09_society/test_group.py` |
| GRP-05 | GRP-05 ration strain: when the settlement the group governs (settlements.group_id) has ration_level <= 2, for each pair and direction (x, y) whose relationships row (after drift) has resentment >= 1: adjust_tension(x, y… | as_engine/society/group.py | `as_engine/society/group.py` | `contract/p09_society/test_group.py` |
| GRP-06 | GRP-06 decay: every tension row with score > 0 whose a_id is the group or one of its living members, and which no TENSION_CHANGE with delta > 0 touched in the last day (at - DAY < e.at <= at), in (a_id, b_id) order: adj… | as_engine/society/group.py | `as_engine/society/group.py` | `contract/p09_society/test_group.py` |
| GRP-07 | GRP-07 defection_pressure(store, actor_id, group_id) -> Pressure(value, terms) terms (ints, this order): grievance = tension_of(actor, group) // 20; deprivation = 2 when the governed settlement's ration_level <= 1, 1 wh… | as_engine/society/group.py | `as_engine/society/group.py` | `contract/p09_society/test_group.py` |
| GRP-08 | GRP-08 loyalty_check(tx, actor_id, group_id, reason, at, turn_index, cause_event_id) -> list[Event] (the group benefit check; core CAS-006 schedules one at a ration cut, day() runs the rest.) A dead body, a body without… | as_engine/society/group.py | `as_engine/society/group.py` | `contract/p09_society/test_econ_chain.py`, `contract/p09_society/test_group.py` |
| GRP-09 | GRP-09 animosity(tx, rng, actor_ids, workplace_id, at, turn_index, cause_event_id) -> float (society.work.cycle calls it for a shift's crew: working beside someone you resent costs.) spite = 1.0. For each pair a < b of… | as_engine/society/group.py | `as_engine/society/group.py` | `contract/p09_society/test_group.py` |
| GRP-10 | GRP-10 day(tx, rng, row, fired, turn_index) -> list[Event] (the GROUP_DAY handler, daily at R.group_hour). g = row['subject_id'], at = row['due_at']. GD = GROUP_DAY {group_id, members: living members, pairs: len(pairs)}… | as_engine/society/group.py | `as_engine/society/group.py` | `contract/p09_society/test_group.py` |
| GRP-11 | GRP-11 Standing — the world's memory of you — lives in group_standing (this owner's table); the functions are mind.mind.standing_toward / adjust_group_standing (they build their events with writer 'society.group'). | as_engine/society/group.py | `as_engine/society/group.py` | `contract/p09_society/test_group.py` |
| GRP-12 | GRP-12 ensure_timers(tx, group_id, at, turn_index) -> list[str]: no pending GROUP_DAY row for the group -> kernel.clock.schedule(tx, society.settlement.next_hour(at, R.group_hour), 'GROUP_DAY', group_id, {'group_id': gr… | as_engine/society/group.py | `as_engine/society/group.py` | — |

## GUIDE

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| GUIDE-01 | GUIDE-01 Ask is not a turn: no event is committed, no time passes, nobody in the world hears it. The only writes are bookkeeping: the call in lm_calls and two story_log entries. | as_engine/service/guide.py | `as_engine/service/guide.py` | `contract/p08_ui_protocol/test_guide.py`, `contract/p08_ui_protocol/test_turns_protocol.py` |
| GUIDE-02 | GUIDE-02 The guide knows only what the character knows (pc_facts) plus plain rules text (rules_for); it never sees the world's hidden state. | as_engine/service/guide.py | `as_engine/service/guide.py` | `contract/p08_ui_protocol/test_guide.py` |
| GUIDE-03 | GUIDE-03 A failed call is not an error: the player gets GUIDE_DOWN and can ask again. | as_engine/service/guide.py | `as_engine/service/guide.py` | `contract/p08_ui_protocol/test_turns_protocol.py` |

## HALLUC

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| HALLUC-01 | *commits ACTION_BLOCKED; nothing is dropped, HALLUC-01). The barrier never repairs an intent by* | as_engine/action/intent.py | `as_engine/action/intent.py` | `contract/p04_one_actor/test_affordances.py`, `contract/p05_many_actors/test_resolve.py` |

## HARM

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| HARM-01 | *Wounds (HARM-01..06) — no hit points:* | as_engine/physical/bodies.py | `as_engine/physical/bodies.py` | `contract/p02_space_bodies/test_bodies.py` |
| HARM-02 | *Wounds (HARM-01..06) — no hit points:* | as_engine/physical/bodies.py | `as_engine/physical/bodies.py` | `contract/p02_space_bodies/test_bodies.py` |
| HARM-03 | *Wounds (HARM-01..06) — no hit points:* | as_engine/physical/bodies.py | `as_engine/physical/bodies.py` | `contract/p02_space_bodies/test_bodies.py` |
| HARM-04 | *Wounds (HARM-01..06) — no hit points:* | as_engine/physical/bodies.py | `as_engine/physical/bodies.py` | `contract/p02_space_bodies/test_bodies.py` |
| HARM-05 | *Wounds (HARM-01..06) — no hit points:* | as_engine/physical/bodies.py | `as_engine/physical/bodies.py` | `contract/p02_space_bodies/test_bodies.py` |
| HARM-06 | (named only by tests) |  | — | `contract/p02_space_bodies/test_bodies.py` |
| HARM-07 | *Impairment (HARM-07) = clamp(pain // 2 + blood steps + needs steps, 0, H.impairment_max), where* | as_engine/physical/bodies.py | `as_engine/physical/bodies.py` | `contract/p02_space_bodies/test_bloodied.py`, `contract/p02_space_bodies/test_bodies.py`, `contract/p02_space_bodies/test_scenario_loader.py` |

## HH

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| HH-01 | HH-01 head_of(store, household_id) -> str / None The living member with role 'head' (lowest id if several); else the living member with role 'partner' (lowest id); else the oldest living member with bodies.age_years >=… | as_engine/society/household.py | `as_engine/society/household.py` | `contract/p09_society/test_household.py` |
| HH-02 | HH-02 dependents_of(store, actor_id) -> list[str] The living actor ids listed in the guardian_of of ANY of the actor's household_members rows, sorted, without duplicates. | as_engine/society/household.py | `as_engine/society/household.py` | `contract/p09_society/test_household.py` |
| HH-03 | HH-03 has_dependents(store, household_id) -> bool True when a living member has role 'child' or 'dependent', or a bodies.age_band of infant, child or preteen. | as_engine/society/household.py | `as_engine/society/household.py` | `contract/p09_society/test_household.py` |
| HH-04 | HH-04 households_of(store, settlement_id) -> list[str] Households whose settlement_id is the settlement, plus every household with at least one living member among the settlement's named people (society.population.censu… | as_engine/society/household.py | `as_engine/society/household.py` | `contract/p09_society/test_household.py` |
| HH-05 | HH-05 apply_change(tx, household_id, change, actor_id, at, turn_index, cause_event_id, grief_delta=0) -> Event change in {'member_died', 'member_joined', 'member_left', 'grief_eased'} (ValueError otherwise); an unknown… | as_engine/society/household.py | `as_engine/society/household.py` | `contract/p09_society/test_household.py` |
| HH-06 | HH-06 day(tx, household_id, at, turn_index, cause_event_id) -> Event / None Grief eases with time (society.settlement.day calls this for each household of the settlement). When grief_state > 0 and the newest HOUSEHOLD_C… | as_engine/society/household.py | `as_engine/society/household.py` | `contract/p09_society/test_household.py` |
| HH-07 | HH-07 worst_hit(store, settlement_id) -> str / None The household of households_of(settlement) that is hit hardest by a shortage: among those with at least one living member, the highest ratio dependents / max(1, provid… | as_engine/society/household.py | `as_engine/society/household.py` | — |

## HOLD

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| HOLD-01 | HOLD-01 a failed answer never becomes a choice (Actor Spec AC15, §14; AR10). When the decision is consequential (HOLD-02) -> raise DecisionHeld(actor, kind): turn.pipeline rolls the turn back — nothing happens, no time… | as_engine/turn/cognition.py | `as_engine/action/intent.py`, `as_engine/lanes/repair.py`, `as_engine/mind/consult.py`, `as_engine/turn/cognition.py`, `as_engine/turn/pipeline.py` | `contract/p07_slice/test_decision_v2.py` |
| HOLD-02 | HOLD-02 consequential(tx, actor_id, affs[actor], turn_index, answered) -> bool: someone asked it something it has not answered (asks_for(tx, actor_id, turn_index, answered) is not empty) or it perceived a threat this tu… | as_engine/turn/cognition.py | `as_engine/mind/affordance.py`, `as_engine/turn/cognition.py` | `contract/p07_slice/test_decision_v2.py` |

## HOR

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| HOR-01 | HOR-01 horizon(tx, pc_intent, t0) -> int (the end of the simulation window, ms) The PC's def is looked up in canon (tx.canon.find('affordance', def_id)). condition-ended (duration.condition_ended: watch, wait, guard…):… | as_engine/turn/select.py | `as_engine/turn/select.py` | `contract/p07_slice/test_p07_slice_metal_fence.py`, `contract/p09_society/test_timers_society.py` |
| HOR-02 | HOR-02..04 pull(horizon_ms, trigger_at, last_event_at) -> int min(horizon_ms, max(trigger_at + REACT_MARGIN_MS, last_event_at)). When the PC holds a MATERIAL percept (action.reactions.material_holders) at trigger_at, th… | as_engine/turn/select.py | `as_engine/turn/select.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| HOR-03 | *horizon). Rules SEL-01..06, HOR-01..04, SKULL-10, TEMPER-06. docs/as/04_TURN_PIPELINE.md §3.1, §3.4.* | as_engine/turn/select.py | `as_engine/turn/select.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| HOR-04 | *(HOR-03: G04 must hold), and a pull never lengthens the window (HOR-04). The pipeline applies* | as_engine/turn/select.py | `as_engine/turn/select.py` | — |

## HRD

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| HRD-01 | HRD-01..17; fidelity E01-E03, W04). Per-difficulty / per-era keys are Difficulty / Era values. | as_engine/contracts/settings.py | `as_engine/contracts/settings.py`, `as_engine/world/hordes.py` | `contract/p10_world/test_hordes.py` |
| HRD-02 | HRD-02 seed_pools(tx, params, at) -> list[Event] (worldgen WG1 step 5; origin 'worldgen', turn 0) v = world.worldgen.params.flat_values(params). Per zone (by zone_id): a region zone: base = atlas.ZONE_INFECTED[kind], sc… | as_engine/world/hordes.py | `as_engine/contracts/settings.py`, `as_engine/world/hordes.py`, `as_engine/world/worldgen/region.py` | `contract/p10_world/test_hordes.py` |
| HRD-03 | HRD-03 Hordes: hordes {horde_id (kind 'hrd'), kind 'drift' / 'drawn' / 'mega', composition, zone_id (the zone of its place), place_id (the hub, road or site it is in), route (JSON list: the places still to walk, in orde… | as_engine/world/hordes.py | `as_engine/contracts/settings.py`, `as_engine/world/hordes.py` | `contract/p10_world/test_hordes.py` |
| HRD-04 | HRD-04 form(tx, kind, zone_id, composition, to_place, at, turn_index, cause, *, props=None, first_leg_ms=None) -> str Takes the composition from zone_id's ACTIVE dead (change(..., -n, 0, 'horde') per type; too few -> Va… | as_engine/world/hordes.py | `as_engine/contracts/settings.py`, `as_engine/world/hordes.py` | `contract/p10_world/test_hordes.py` |
| HRD-05 | HRD-05 step(tx, rng, row, fired, turn_index) -> list[Event] (the HORDE_STEP handler) h = the horde; missing or 'gone' -> []. at = row.due_at, cause = fired.event_id; area = turn.select.active_area(tx, meta.pc_actor_id,… | as_engine/world/hordes.py | `as_engine/contracts/settings.py`, `as_engine/world/hordes.py` | `contract/p10_world/test_hordes.py` |
| HRD-06 | HRD-06 Straggle and rally at a hub: per type (TYPES order) k = floor(its count x H.straggle) fall behind into the hub zone's pool (change(..., +k, 0, 'straggled')); then a 'drift' or 'mega' horde gathers r = floor(the h… | as_engine/world/hordes.py | `as_engine/contracts/settings.py`, `as_engine/world/hordes.py` | `contract/p10_world/test_hordes.py` |
| HRD-07 | HRD-07 promote(tx, rng, horde_id, place_id, at, turn_index, cause) -> list[str] (contact: counts become bodies where the player is) present = living infected bodies positioned in place_id whose infected_state.horde_id i… | as_engine/world/hordes.py | `as_engine/contracts/settings.py`, `as_engine/world/hordes.py`, `as_engine/world/infected.py` | `contract/p10_world/test_hordes.py` |
| HRD-08 | HRD-08 press(tx, rng, horde_id, settlement_id, at, turn_index, cause) -> Event (fidelity C01: the dead kill the living who are there) N = count; D = settlements.defences; pressure = N / (H.breach_scale x (1 + D)); p = m… | as_engine/world/hordes.py | `as_engine/contracts/settings.py`, `as_engine/world/factions.py`, `as_engine/world/hordes.py` | `contract/p10_world/test_ghosts.py`, `contract/p10_world/test_hordes.py` |
| HRD-09 | HRD-09 draw(tx, place_id, source_db, at, turn_index, cause) -> str / None (E01: a loud noise draws a district's finite dead; action.propagate calls it for every NOISE whose source_db >= H.draw_db) z = the zone of place_… | as_engine/world/hordes.py | `as_engine/action/propagate.py`, `as_engine/contracts/settings.py`, `as_engine/world/hordes.py` | `contract/p10_world/test_hordes.py` |
| HRD-10 | HRD-10 day(tx, rng, at, turn_index, cause) -> list[Event] (world.worldmove.day step 6, after world.infected.day) 1 Lifecycle (E03; a Runner becomes a Shambler, never the reverse): per pool row holding runners (by zone_i… | as_engine/world/hordes.py | `as_engine/contracts/settings.py`, `as_engine/world/hordes.py` | `contract/p10_world/test_hordes.py` |
| HRD-11 | HRD-11 census(store) -> dict (the LOD view: the developer panel and the cheats read it) {'pools': {zone_id: {type_id: [active, dormant]}} (zones with any dead), 'hordes': [{horde_id, kind, count, zone_id, place_id, stat… | as_engine/world/hordes.py | `as_engine/contracts/settings.py`, `as_engine/world/hordes.py` | `contract/p10_world/test_hordes.py` |
| HRD-12 | HRD-12 calls it right after a Mega Horde forms. Per faction group (by group_id) with route_watch and an enclave: ROUTE_WATCH_REPORT {group_id, horde_id, gateway_hub, eta_at} (gateway_hub = the hub of the region zone its… | as_engine/world/factions.py | `as_engine/contracts/settings.py`, `as_engine/world/factions.py`, `as_engine/world/hordes.py` | `contract/p10_world/test_hordes.py` |
| HRD-13 | HRD-13 The signs, every WORLD_DAY while the mega horde is still at its entry hub: left = ceil((eta_at - at) / DAY); each sign once, in this order, recorded in props.signs (HORDE_SIGN {horde_id, sign} updating props): le… | as_engine/world/hordes.py | `as_engine/contracts/settings.py`, `as_engine/world/factions.py`, `as_engine/world/hordes.py`, `as_engine/world/rumours.py` | `contract/p10_world/test_hordes.py` |
| HRD-14 | HRD-14 Passage. A mega horde arriving at a REGION zone's hub mills there for ceil(count / H.mega_throughput_per_day x 24) hours (props.until) and the zone is SATURATED: every place of the zone with parent_id NULL and in… | as_engine/world/hordes.py | `as_engine/contracts/settings.py`, `as_engine/world/factions.py`, `as_engine/world/hordes.py` | `contract/p10_world/test_hordes.py` |
| HRD-15 | HRD-15 Conservation (fidelity F04, tests check it): census(store)['total'] changes only by: the dead that rise (POOL_CHANGE reason 'risen'; world.infected.rise), cheat spawns (P12) and infected bodies destroyed. Every o… | as_engine/world/hordes.py | `as_engine/contracts/settings.py`, `as_engine/world/hordes.py` | `contract/p10_world/test_hordes.py` |
| HRD-16 | HRD-16 The dead of the unnamed rise (E03). Whoever makes unnamed people die of something that leaves bodies (society.settlement privation: pathway 'cold_start'; HRD-08: 'wet') calls schedule_rise(tx, rng, zone_id, count… | as_engine/world/hordes.py | `as_engine/contracts/settings.py`, `as_engine/society/settlement.py`, `as_engine/world/hordes.py` | `contract/p10_world/test_hordes.py` |
| HRD-17 | HRD-17 Nothing here reads a mind or what the player knows. People learn of a horde by hearing it, seeing it or being told (NOISE, bodies in sight, rumours). | as_engine/world/hordes.py | `as_engine/world/hordes.py` | `contract/p10_world/test_hordes.py` |
| HRD-18 | HRD-18 folds a body only where no living person is). | as_engine/physical/space.py | `as_engine/physical/space.py`, `as_engine/turn/timers.py`, `as_engine/world/hordes.py`, `as_engine/world/infected.py` | `contract/p10_world/test_hordes.py` |

## I-AS

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| I-AS-10 | I-AS-10: The PC card text differs between Part II §2.3 ("Getting to places…") and Part XV | DECISIONS §5 | `as_content/packs/core/pcs/addison_flores.yaml` | — |
| I-AS-11 | I-AS-11: The document is titled "Master Guide v4.1" inside while its file and footer say v4.2. | DECISIONS §5 | — | — |
| I-AS-12 | I-AS-12: CMG §43.B's Addison Containment Rule assumes Addison is always the PC; with selectable | DECISIONS §5 | `as_content/packs/core/factions/mafia_remnants.yaml` | — |
| I-AS-13 | I-AS-13: CMG §42.1 names Codex as responsible for the escape; AS has no narrator-god, so the | DECISIONS §5 | — | — |
| I-AS-14 | I-AS-14: CMG §61 Part XV locks Addison at age 20 with "started collapse at ~10", which pins her | DECISIONS §5 | — | — |
| I-AS-15 | I-AS-15: CMG §43.C's No-Release Quarantine names "execution" and "black-site observation" as | DECISIONS §5 | — | — |

## IDN

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| IDN-01 | IDN-01 compile_identity(dossier, *, minimum=False) -> IdentityCard (``dossier``: ActorDossier or PCDossier — pass mind.actor.fused, so accepted developments, the dossier deltas, are in it) name / age / one_line from ide… | as_engine/mind/identity.py | `as_engine/contracts/mind.py`, `as_engine/mind/identity.py`, `as_engine/mind/memory.py`, `as_engine/mind/packet.py` | `contract/p04_one_actor/test_identity.py`, `contract/p04_one_actor/test_packet.py` |
| IDN-02 | IDN-02 Kept outside the card, never in any prompt a person's call renders (Actor Spec §4, §5): writers_notes (editorial guidance for authors — AC02), knowledge.does_not_know (naming a hidden fact supplies it — AC04; the… | as_engine/mind/identity.py | `as_engine/contracts/mind.py`, `as_engine/mind/identity.py`, `as_engine/mind/packet.py` | `contract/p04_one_actor/test_identity.py` |
| IDN-03 | IDN-03 Every line's sources are paths that exist in the dossier (list items by index); a line is made only from its sources and the fixed words above. The card is a pure function: the same dossier gives the same card, a… | as_engine/mind/identity.py | `as_engine/contracts/mind.py`, `as_engine/mind/identity.py`, `as_engine/mind/packet.py` | `contract/p04_one_actor/test_identity.py` |
| IDN-04 | IDN-04 dossier_hash = sha256 hex of kernel.jsoncanon.canonical_json(dossier.model_dump(mode='json', by_alias=True)) — the decision audit's pin of which identity a call saw. | as_engine/mind/identity.py | `as_engine/mind/identity.py`, `as_engine/mind/packet.py` | `contract/p04_one_actor/test_identity.py` |
| IDN-05 | IDN-05 minimum=True gives the reaction card (Actor Spec §4: "keep a minimum identity card in reactions too"): a split second leaves no room for a whole life, never for none of it. The same lines, only these: 'who' all;… | as_engine/mind/identity.py | `as_engine/mind/identity.py` | `contract/p04_one_actor/test_identity.py`, `contract/p04_one_actor/test_packet.py` |

## IFACE

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| IFACE-01 | *Nothing above this boundary knows which model answered (IFACE-01).* | as_engine/contracts/lanes.py | `as_engine/contracts/lanes.py` | — |

## IMP

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| IMP-01 | *Importers (P12). Rules IMP-01..06. Nothing imported enters canon until the validator passes;* | as_engine/content/importers.py | `as_engine/content/importers.py` | — |
| IMP-02 | *Importers (P12). Rules IMP-01..06. Nothing imported enters canon until the validator passes;* | as_engine/content/importers.py | `as_engine/content/importers.py`, `as_engine/content/pack.py` | — |
| IMP-03 | *Importers (P12). Rules IMP-01..06. Nothing imported enters canon until the validator passes;* | as_engine/content/importers.py | `as_engine/content/importers.py` | — |
| IMP-04 | *Importers (P12). Rules IMP-01..06. Nothing imported enters canon until the validator passes;* | as_engine/content/importers.py | `as_engine/content/importers.py` | — |
| IMP-05 | *Importers (P12). Rules IMP-01..06. Nothing imported enters canon until the validator passes;* | as_engine/content/importers.py | `as_engine/content/importers.py` | — |
| IMP-06 | *The engine never auto-publishes an intake draft into canon (IMP-06).* | as_engine/content/importers.py | `as_engine/content/importers.py` | — |

## INF

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| INF-01 | INF-01 Types and states are orthogonal: states is a JSON list over dormant / starved / overfed / injured; the type is infected_state.type_id. | as_engine/world/infected.py | `as_engine/world/infected.py` | `contract/p10_world/test_infected.py` |
| INF-02 | INF-02 Senses: hearing = the type's hearing_threshold_db plus every state's hearing_threshold_delta_db (threshold()); sight = sees(). | as_engine/world/infected.py | `as_engine/action/propagate.py`, `as_engine/world/infected.py` | `contract/p10_world/test_infected.py` |
| INF-03 | INF-03 Energy, the metabolic budget (P10: by time, not by step): being active costs 1 energy per R.energy_period_s[type] seconds (60 when unlisted) — an hour banging on a door tires a body as much as an hour walking; st… | as_engine/world/infected.py | `as_engine/world/infected.py` | `contract/p10_world/test_hordes.py`, `contract/p10_world/test_infected.py` |
| INF-04 | INF-04 False death and reanimation are physical.bodies' (a false-dead body is 'unconscious' and takes no steps); the dead that RISE are this module's (rise). | as_engine/world/infected.py | `as_engine/physical/bodies.py`, `as_engine/world/infected.py` | `contract/p10_world/test_infected.py` |
| INF-05 | INF-05 An infected never targets an infected body. | as_engine/world/infected.py | `as_engine/world/infected.py` | `contract/p10_world/test_infected.py` |
| INF-06 | INF-06 A body with a 'lurker_deep' infections row past its first stage is never a target. | as_engine/world/infected.py | `as_engine/world/infected.py` | `contract/p10_world/test_infected.py` |
| INF-07 | INF-07 A body with a 'wet' infection at least R.wet_ignore_after_h hours old draws less of their eye, not none (W1, D-77; CODEX §5): it is SEEN as prey only within half the type's vision_range_m (sound still draws infec… | as_engine/world/infected.py | `as_engine/world/infected.py` | `contract/p10_world/test_infected.py`, `contract/p10_world/test_wet_fluids.py` |
| INF-08 | INF-08 Quirks are seeded per body (seed_quirks, stream 'quirks'): the same seed gives the same quirks to the same body. | as_engine/world/infected.py | `as_engine/world/infected.py` | `contract/p10_world/test_infected.py` |
| INF-09 | INF-09 Noise steers: a sound above a body's threshold makes it walk toward the sound's place (attract, called by action.propagate). | as_engine/world/infected.py | `as_engine/world/infected.py` | `contract/p10_world/test_infected.py` |
| INF-10 | INF-10 Lifecycle: a Runner becomes a Shambler or a Crawler after R.runner_degrade_days; never the reverse (CMG §42.17). | as_engine/world/infected.py | `as_engine/world/infected.py` | `contract/p10_world/test_infected.py` |
| INF-11 | INF-11 Infected in a place come from its zone's danger the first time a person arrives (populate). | as_engine/world/infected.py | `as_engine/world/infected.py` | `contract/p10_world/test_hordes.py`, `contract/p10_world/test_infected.py` |
| INF-12 | INF-12 The same rules run everywhere: an INFECTED_STEP timer moves a body one leg at a time, in a turn's window or off-screen alike. | as_engine/world/infected.py | `as_engine/physical/space.py`, `as_engine/world/infected.py`, `as_engine/world/worldmove.py`, `as_content/packs/core/infected/states.yaml` | `contract/p10_world/test_hordes.py`, `contract/p10_world/test_infected.py` |
| INF-13 | INF-13 (P10) A crowd breaks what one body only bangs on. After a bang (step 1): when at least R.push_min living infected bodies (b included) stand in b's place within 2 m of the portal's point on this side, and the port… | as_engine/world/infected.py | `as_engine/action/propagate.py`, `as_engine/physical/space.py`, `as_engine/world/infected.py` | `contract/p10_world/test_ghosts.py`, `contract/p10_world/test_hordes.py` |
| INF-14 | INF-14 (F1b) Gore camouflage: a living body caked in gore moves among the dead as one of them. sees() is False for a target whose bodies.gore >= R.gore_mask_min when the seeing body's type vision_mode is not 'thermal' (… | as_engine/world/infected.py | `as_engine/physical/bodies.py`, `as_engine/sense/olfaction.py`, `as_engine/world/infected.py` | `contract/p05_many_actors/test_care.py`, `contract/p10_world/test_gore_mask.py`, `contract/p10_world/test_weather_and_cold.py` |
| INF-15 | INF-15 (I1) They eat people alive. The owner: "They don't just bite you and waddle off, they don't attack for the kill either. They eat you alive. Feast on you while you watch." A body that holds a grip on a living body… | as_engine/world/infected.py | `as_engine/action/effects.py`, `as_engine/world/infected.py`, `as_content/packs/core/cascade/stress.yaml`, `as_content/packs/core/infected/states.yaml` | `contract/p10_world/test_feeding.py` |
| INF-16 | INF-16 (I1) They stay on what they killed. When the body a feeder hunts dies within 1.5 m of it, the feeder stays on the corpse and keeps eating until R.feed_on_dead_min minutes after the death (step 3: a dead target wi… | as_engine/world/infected.py | `as_engine/action/effects.py`, `as_engine/world/infected.py` | `contract/p10_world/test_feeding.py` |
| INF-17 | INF-17 (I1) Busy eating. A feeder — it holds a grip on a living body, or it is inside INF-16's window on a corpse — is not drawn away: attract() returns None for it unless the new target is the body it is eating. Noise… | as_engine/world/infected.py | `as_engine/world/infected.py` | `contract/p10_world/test_feeding.py` |
| INF-18 | INF-18 (I1) Anything that moves. Animals (bodies of kind 'animal': a dog, a cat, a deer, a horse) are prey like people: seen, drawn to, grabbed, bitten and eaten the same way. Only humans take the strain: a bite never i… | as_engine/world/infected.py | `as_engine/action/effects.py`, `as_engine/contracts/content.py`, `as_engine/physical/bodies.py`, `as_engine/physical/objects.py`, `as_engine/testing/scenario.py`, `as_engine/world/infected.py`, `as_content/packs/core/animals/animals.yaml` | `contract/p10_world/test_feeding.py` |
| INF-19 | INF-19 (I1) Fluids foul water. A water item lying loose in a place (not held or carried) within R.taint_radius_m of a bite that lands, or of an infected body when it is destroyed or false-dies, is contaminated — physica… | as_engine/world/infected.py | `as_engine/world/infected.py` | `contract/p10_world/test_feeding.py` |

## INFO

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| INFO-01 | INFO-01 (the law) information is neither universally known nor confined to the conversation partner: it moves along households, work crews and friendships, a few people a day, and fades (confidence 0 is held but never p… | as_engine/world/rumours.py | `as_engine/world/rumours.py` | `contract/p09_society/test_rumours.py` |
| INFO-02 | INFO-02 spread_one(tx, rumour_id, teller_id, listener_id, at, turn_index, cause_event_id) -> Event The teller's live (superseded_by NULL) believed holding on the rumour's (subject_type, subject_id, predicate) must have… | as_engine/world/rumours.py | `as_engine/mind/perception.py`, `as_engine/world/rumours.py`, `as_content/packs/core/cascade/people.yaml` | `contract/p09_society/test_rumours.py` |
| INFO-03 | *Rumours (P9). Owner 'world.rumours' (rumours). Rules INFO-01..07. docs/as/06_WORLD.md §6.* | as_engine/world/rumours.py | `as_engine/world/rumours.py` | `contract/p09_society/test_rumours.py` |
| INFO-04 | INFO-04 holders(store, rumour_id) -> list[tuple[str, int]]: (holder_id, confidence) of every live believed holding on the rumour's (subject_type, subject_id, predicate), sorted by holder_id. | as_engine/world/rumours.py | `as_engine/world/rumours.py` | `contract/p09_society/test_rumours.py` |
| INFO-05 | INFO-05 spread_day(tx, group_id, at, turn_index, cause_event_id) -> list[Event] (society.group.day calls it.) For each rumours row (by rumour_id) with created_at > at - R.rumour_quiet_days * DAY: tellers = the living me… | as_engine/world/rumours.py | `as_engine/world/rumours.py` | `contract/p09_society/test_rumours.py` |
| INFO-06 | INFO-06 Retelling (P10; service/background.py runs the RUMOUR_DISTORT calls between turns): what a holder passes on is their own version. retell(tx, rumour_id, holder_id, answer, at, turn_index) -> Event / None: answer… | as_engine/world/rumours.py | `as_engine/service/background.py`, `as_engine/world/rumours.py` | `contract/p09_society/test_rumours.py`, `contract/p10_world/test_background.py` |
| INFO-07 | INFO-07 seed(tx, holder_id, about_id, claim, at, turn_index, cause_event_id, confidence=3, *, subject_type='body') -> str (the cascade 'create_rumour' dispatch — core CAS-012 for a witnessed theft, CAS-013 for an off-sc… | as_engine/world/rumours.py | `as_engine/world/rumours.py` | — |

## INT

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| INT-01 | Intensity changes narrator wording only; the committed events for the same inputs are byte-identical at Full and Softer. | 11_SETTINGS §3 | — | — |

## INTAKE

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| INTAKE-01 | INTAKE-01 (1) perception.compile_scene(tx, pc, t0, turn_index); aff = mind.affordance.enumerate_affordances(tx, pc, tx.canon.all('affordance'), t0, turn_index); packet = build_packet(tx, pc, LOD.WARM, aff, turn_index, t… | as_engine/turn/intake.py | `as_engine/turn/intake.py` | — |
| INTAKE-02 | INTAKE-02 (2) A suggestion chip (submit.suggestion_ref): entry = session.extras['suggestions'][ref] (service.view writes them) — missing -> Rejected('suggestion_stale', "That option is gone; things have changed."). * an… | as_engine/turn/intake.py | `as_engine/turn/intake.py` | — |
| INTAKE-03 | INTAKE-03 (3) Empty text -> Rejected('empty', "Type something first."). | as_engine/turn/intake.py | `as_engine/turn/intake.py` | — |
| INTAKE-04 | INTAKE-04 (4) mode 'say': words = the text; with settings.pc_voice == 'my_way' one SAY_MY_WAY call (lanes.requests.build_request(config, SAY_MY_WAY, turn_index = T, actor_id = the PC, context and ctx = SayMyWayContext(p… | as_engine/turn/intake.py | `as_engine/turn/intake.py` | — |
| INTAKE-05 | INTAKE-05 (5) mode 'do': quotes = lanes.parse.extract_quotes(text); rest = the text with every quoted span ("…" or “…”) replaced by ' ', stripped; addressee = addressee_for(...) — ALWAYS called here, before anything els… | as_engine/turn/intake.py | `as_engine/turn/intake.py` | — |
| INTAKE-06 | INTAKE-06 Rejected leaves the transaction to roll back: nothing of the turn is kept, no time passes and the input is not consumed (the player can rephrase). | as_engine/turn/intake.py | `as_engine/turn/intake.py` | — |

## INTENT

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| INTENT-01 | *Intent construction and the intent barrier (P4/P5). Rules INTENT-01..09, L2, L3, L5.* | as_engine/action/intent.py | `as_engine/action/intent.py` | `contract/p04_one_actor/test_intent.py` |
| INTENT-02 | *Intent construction and the intent barrier (P4/P5). Rules INTENT-01..09, L2, L3, L5.* | as_engine/action/intent.py | `as_engine/action/intent.py`, `as_engine/contracts/mind.py`, `as_engine/turn/cognition.py` | — |
| INTENT-03 | *Intent construction and the intent barrier (P4/P5). Rules INTENT-01..09, L2, L3, L5.* | as_engine/action/intent.py | `as_engine/action/intent.py`, `as_engine/mind/affordance.py`, `as_engine/physical/objects.py` | `contract/p02_space_bodies/test_objects.py`, `contract/p04_one_actor/test_affordances.py`, `contract/p05_many_actors/test_effects.py` |
| INTENT-04 | *Intent construction and the intent barrier (P4/P5). Rules INTENT-01..09, L2, L3, L5.* | as_engine/action/intent.py | `as_engine/action/intent.py` | — |
| INTENT-05 | *Intent construction and the intent barrier (P4/P5). Rules INTENT-01..09, L2, L3, L5.* | as_engine/action/intent.py | `as_engine/action/intent.py` | — |
| INTENT-06 | *Intent construction and the intent barrier (P4/P5). Rules INTENT-01..09, L2, L3, L5.* | as_engine/action/intent.py | `as_engine/action/intent.py` | — |
| INTENT-07 | * INTENT-07 pace (a decision's or the player's; a V1 answer's is 'normal'): 'normal', or one of the chosen option's paces (BoundAffordance.paces, copied from AffordanceDef.paces) — else IntentError 'unsupported_pace' (a… | as_engine/action/intent.py | `as_engine/action/intent.py`, `as_engine/mind/affordance.py` | `contract/p04_one_actor/test_intent_v2.py` |
| INTENT-08 | * INTENT-08 an Actor's answer (source 'model') with more than 100 words of speech (whitespace-separated), or more than 12 in a reaction (reaction=True) -> IntentError 'speech_too_long' (Actor Spec §7: long talk goes on… | as_engine/action/intent.py | `as_engine/action/intent.py` | `contract/p04_one_actor/test_intent_v2.py` |
| INTENT-09 | * INTENT-09 gesture and attention must be null or a G# / F# key of packet.handles (no packet offers any yet) — else IntentError 'hallucinated_expression'. An inscription needs a chosen option tagged 'write' (no core opt… | as_engine/action/intent.py | `as_engine/action/intent.py` | `contract/p04_one_actor/test_intent_v2.py` |

## LANE

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| LANE-01 | *LaneClient (P1): one call = transport + parse + validate + call log. Rules LANE-01..08.* | as_engine/lanes/client.py | `as_engine/lanes/client.py` | `contract/p01_lanes/test_client.py` |
| LANE-02 | *LaneClient (P1): one call = transport + parse + validate + call log. Rules LANE-01..08.* | as_engine/lanes/client.py | `as_engine/lanes/client.py` | `contract/p01_lanes/test_client.py` |
| LANE-03 | LANE-03, PROMPT-01, SCHEMA-02. Nothing above this boundary writes messages by hand. | as_engine/lanes/requests.py | `as_engine/lanes/client.py`, `as_engine/lanes/requests.py` | — |
| LANE-04 | *LaneClient (P1): one call = transport + parse + validate + call log. Rules LANE-01..08.* | as_engine/lanes/client.py | `as_engine/lanes/client.py` | — |
| LANE-05 | *LaneClient (P1): one call = transport + parse + validate + call log. Rules LANE-01..08.* | as_engine/lanes/client.py | `as_engine/lanes/client.py`, `as_engine/lanes/errors.py`, `as_engine/turn/pipeline.py` | `contract/p01_lanes/test_client.py` |
| LANE-06 | *LaneClient (P1): one call = transport + parse + validate + call log. Rules LANE-01..08.* | as_engine/lanes/client.py | `as_engine/lanes/client.py`, `as_engine/lanes/repair.py`, `as_engine/lanes/requests.py`, `as_engine/turn/cognition.py` | `contract/p01_lanes/test_repair.py`, `contract/p07_slice/test_decision_v2.py` |
| LANE-07 | *LaneClient (P1): one call = transport + parse + validate + call log. Rules LANE-01..08.* | as_engine/lanes/client.py | `as_engine/lanes/client.py` | — |

## LESSON

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| LESSON-01 | LESSON-01..03, STAND-01..02 (P9). Writer of RELATION_CHANGE, LOOP_OPENED, PROMISE, LOOP_CLOSED, | as_engine/mind/mind.py | `as_engine/mind/mind.py` | `contract/p06_memory/test_mind.py` |
| LESSON-02 | LESSON-02 Learning the same lesson again (same holder, same cue_tags as a set, same norm_text) reinforces it instead: confidence + 1 (at most 3), LESSON_LEARNED {lesson_id, holder_id, confidence, reinforced: true}; writ… | as_engine/mind/mind.py | `as_engine/mind/mind.py` | `contract/p06_memory/test_mind.py` |
| LESSON-03 | LESSON-03 Lessons are never deleted. | as_engine/mind/mind.py | `as_engine/mind/mind.py` | `contract/p06_memory/test_mind.py` |

## LOD

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| LOD-01 | *est_wall_s = the final estimate. LOD never changes competence, knowledge or morality (LOD-01);* | as_engine/lanes/scheduler.py | `as_engine/lanes/scheduler.py`, `as_engine/turn/cognition.py` | `contract/p05_many_actors/test_cues_and_continuation.py`, `contract/p05_many_actors/test_reactions_cascade_plan.py` |
| LOD-02 | *(COLD, LOD-02) The same decision the actor made last time, still running. First match wins; the* | as_engine/action/intent.py | `as_engine/action/intent.py`, `as_engine/mind/packet.py` | — |

## LOOK

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| LOOK-01 | LOOK-01 bodies.looks holds the body's contracts.dossier.Looks WITHOUT its outfit (JSON; NULL = height and build are all anyone sees): what anyone can see — hair, facial hair, eyes, complexion, visible marks (where and w… | as_engine/physical/bodies.py | `as_engine/contracts/dossier.py`, `as_engine/physical/bodies.py`, `as_engine/testing/scenario.py`, `as_engine/world/worldgen/opening.py` | `contract/p02_space_bodies/test_looks.py`, `contract/p10_world/test_dressed.py` |
| LOOK-02 | LOOK-02 A worn item is an items row with holder_slot 'worn'; clothing is an item whose ItemDef has a ``clothing`` block (contracts.content.ClothingProps); its props may carry colour (overrides the block's colour), state… | as_engine/physical/objects.py | `as_engine/contracts/content.py`, `as_engine/contracts/dossier.py`, `as_engine/physical/objects.py`, `as_engine/world/worldgen/opening.py`, `as_content/packs/core/items/clothing.yaml` | `contract/p02_space_bodies/test_looks.py`, `contract/p10_world/test_dressed.py` |
| LOOK-03 | LOOK-03 appearance_text(tx, holder_id, subject_id, level, distance_m) -> str: what the holder sees of the subject beyond describe()'s Ref, never naming what cannot be seen; built from L = physical.bodies.looks_of(subjec… | as_engine/mind/perception.py | `as_engine/mind/perception.py` | `contract/p03_perception/test_appearance.py` |
| LOOK-04 | LOOK-04 Condition: bodies.grime / blood / gore (0..5) and wet (0..3) — what is on the body and its clothes; washed_at = when it was last washed (F1c). condition_of(store, body_id) -> BodyCondition(grime, blood, gore, we… | as_engine/physical/bodies.py | `as_engine/physical/bodies.py`, `as_engine/sense/olfaction.py` | `contract/p02_space_bodies/test_looks.py` |
| LOOK-05 | LOOK-05 appearance_cues(tx, holder_id, subject_id, level, distance_m) -> list[str] (F1a) What the subject's appearance tells the holder at a glance, sorted, from the same facts as mind.perception.appearance_text (level… | as_engine/mind/cues.py | `as_engine/mind/cues.py`, `as_content/packs/core/cues.yaml` | `contract/p03_perception/test_appearance.py`, `contract/p05_many_actors/test_appearance_cues.py` |
| LOOK-06 | LOOK-06, SMELL-04); **Your | 05_ACTORS §3 | `as_engine/mind/packet.py`, `as_engine/mind/perception.py` | `contract/p04_one_actor/test_appearance_in_packet.py` |
| LOOK-07 | LOOK-07 Who gets bloodied: apply_harm, after the HARM and before the death test, soils the wounded body: blood += C.blood_from_wound[severity] (source 'harm', cause = the HARM; nothing when that is 0; committed, not ret… | as_engine/physical/bodies.py | `as_engine/action/effects.py`, `as_engine/contracts/settings.py`, `as_engine/physical/bodies.py` | `contract/p02_space_bodies/test_bloodied.py`, `contract/p05_many_actors/test_care.py` |
| LOOK-08 | LOOK-08 Condition over time (P10; progress step 2): for a living body of kind 'human' whose looks are recorded (bodies.looks not NULL: a body the world has never dressed makes no claim about what time does to it), at ea… | as_engine/physical/bodies.py | `as_engine/contracts/settings.py`, `as_engine/physical/bodies.py`, `as_engine/testing/scenario.py` | `contract/p10_world/test_weather_and_cold.py` |
| LOOK-09 | LOOK-09 Cold (P10; progress step 2, after LOOK-08; the same bodies): warmth is physical.objects.warmth(body) (what they wear). cold_need(store, body_id, at) -> int = what the body's place and weather ask: base = C.cold_… | as_engine/physical/bodies.py | `as_engine/physical/bodies.py`, `as_engine/physical/objects.py` | `contract/p10_world/test_weather_and_cold.py` |

## LOOP

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| LOOP-01 | LOOP-01 open_loop(tx, holder_id, kind, text, subject_ids, strength, cause, at, turn_index, due_at=None) -> loop_id (kind 'olp'). ``kind`` must be an OpenLoopKind value, ``text`` non-empty after strip, ``strength`` 1..3… | as_engine/mind/mind.py | `as_engine/mind/mind.py` | `contract/p06_memory/test_mind.py` |
| LOOP-02 | LOOP-02 A mind does not hold the same loop twice: when the holder already has an OPEN loop with the same kind, the same subject_ids (as a set) and the same text after mind.perception.norm_text, open_loop returns that lo… | as_engine/mind/mind.py | `as_engine/mind/mind.py`, `as_engine/society/group.py` | `contract/p06_memory/test_mind.py` |
| LOOP-03 | LOOP-03 close_loop(tx, loop_id, status, cause, at, turn_index) -> Event. The loop must exist and be 'open', and status must be one of 'fulfilled', 'broken', 'abandoned', 'expired' — else ValueError. Writes open_loops UP… | as_engine/mind/mind.py | `as_engine/mind/mind.py` | `contract/p06_memory/test_mind.py` |
| LOOP-04 | LOOP-04 The promisee is the one who decides a promise was kept or broken. Closing a **promise_owed** loop (the holder is owed) as 'fulfilled' commits PROMISE_KEPT, as 'broken' commits PROMISE_BROKEN, with payload {loop_… | as_engine/mind/mind.py | `as_engine/mind/cues.py`, `as_engine/mind/mind.py` | `contract/p06_memory/test_mind.py` |
| LOOP-05 | LOOP-05 close_loop writes nothing but the loop row. What a broken promise costs is cascade content (core CAS-011: the promisee's trust drops and it opens a grudge), applied by the cascade sweep to the promisee only. | as_engine/mind/mind.py | `as_engine/mind/mind.py` | `contract/p06_memory/test_mind.py` |
| LOOP-06 | LOOP-06 Loops are never deleted; only their status changes. | as_engine/mind/mind.py | `as_engine/mind/mind.py` | `contract/p06_memory/test_mind.py` |
| LOOP-07 | LOOP-07 (H1) strengthen_loop(tx, loop_id, delta, cause, at, turn_index) -> Event / None: an OPEN loop's strength moves by ``delta``, clamped to 1..3 (a grudge that deepens each time someone is pushed too far, mind.tempe… | as_engine/mind/mind.py | `as_engine/mind/mind.py` | `contract/p05_many_actors/test_temper.py` |

## LORE

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| LORE-01 | *Content packs: load, validate, lint, compile (P2). Rules CNT-00..17, LORE-01.* | as_engine/content/pack.py | `as_engine/content/pack.py` | `contract/p02_space_bodies/test_content_pack.py` |

## MEM

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| MEM-01 | MEM-01 build_aftermath(tx, holder_id, turn_index, at) -> AftermathPacket (Stage 13, gate G13) Exactly what the holder perceived this turn and nothing else — the same selection and handles as the Skull Packet (mind.packe… | as_engine/mind/memory.py | `as_engine/mind/memory.py` | `contract/p06_memory/test_memory.py`, `contract/p07_slice/test_p07_slice_metal_fence.py` |
| MEM-02 | MEM-02 apply_writeback(tx, holder_id, output, packet, at, turn_index, *, cue_ids) -> list[str] (Stage 14, gate G14: a mind writes nothing that cites what it did not perceive.) ``cue_ids`` = the registry cue ids (Canon c… | as_engine/mind/memory.py | `as_engine/audit/log.py`, `as_engine/mind/memory.py`, `as_engine/turn/pipeline.py` | `contract/p06_memory/test_memory.py`, `contract/p07_slice/test_p07_slice_metal_fence.py` |
| MEM-03 | MEM-03 writeback_groups(packets: dict[holder_id, AftermathPacket]) -> list[list[holder_id]] Holders may share ONE writeback call only when nothing in their packets is private (own_action_text None, no open_loops, no rel… | as_engine/mind/memory.py | `as_engine/mind/memory.py` | `contract/p06_memory/test_memory.py`, `contract/p07_slice/test_p07_slice_metal_fence.py` |
| MEM-04 | MEM-04 episode always (even when every other item was dropped): EPISODE_WRITTEN (writer 'mind.memory', actor_id = holder, cause_event_id = the event of the first percept row in handle order whose event_id is a committed… | as_engine/mind/memory.py | `as_engine/mind/memory.py` | `contract/p06_memory/test_memory.py`, `contract/p07_slice/test_p07_slice_metal_fence.py` |
| MEM-05 | MEM-05 beliefs per belief, in order: perception.infer(holder, about = ('body', the entity's id) / ('self', None) / ('place', None), text = claim, confidence, because = the cited percept ids). | as_engine/mind/memory.py | `as_engine/mind/memory.py`, `as_engine/mind/perception.py` | `contract/p06_memory/test_memory.py`, `contract/p07_slice/test_p07_slice_metal_fence.py` |
| MEM-06 | MEM-06 anchor 1 when salience >= 90, or when a percept of the packet is of a DEATH or FALSE_DEATH event (the holder cannot tell them apart) whose source is a body the holder is bonded to: a relationships row from the ho… | as_engine/mind/memory.py | `as_engine/mind/memory.py` | `contract/p06_memory/test_memory.py`, `contract/p07_slice/test_p07_slice_metal_fence.py`, `contract/p10_world/test_background.py` |
| MEM-07 | MEM-07 relationships mind.mind.relate(holder, the entity's id, axis, delta, cause = the cited percept's event_id — percept_log.event_id, which may be a 'scene:N' reference). new_loops mind.mind.open_loop(holder, kind, t… | as_engine/mind/memory.py | `as_engine/mind/memory.py` | `contract/p06_memory/test_memory.py`, `contract/p07_slice/test_p07_slice_metal_fence.py` |
| MEM-08 | MEM-08 The PC gets writeback exactly like everyone else (L12): its episodes feed the Journal and the recap. | as_engine/mind/memory.py | `as_engine/mind/memory.py` | `contract/p06_memory/test_memory.py` |
| MEM-09 | MEM-09 Nothing here reads another mind or the truth layer: every id apply_writeback uses comes from this holder's packet handles, and build_aftermath reads only this holder's rows plus its own ACTION_START / SPEECH even… | as_engine/mind/memory.py | `as_engine/mind/memory.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| MEM-10 | MEM-10 The model never decides what it receives: everything here is computed by code from committed state, deterministically, every ordering ending with an id so ties cannot flip. | as_engine/mind/retrieval.py | `as_engine/mind/packet.py`, `as_engine/mind/retrieval.py` | `contract/p06_memory/test_retrieval.py` |
| MEM-11 | MEM-11 Two key sets. The MOMENT set M (Retrieved.moment_keys) — what is in front of the holder now: * the holder's place id (positions); * every body that is the source_id of one of the holder's percept rows of this tur… | as_engine/mind/retrieval.py | `as_engine/mind/retrieval.py` | `contract/p06_memory/test_retrieval.py` |
| MEM-12 | MEM-12 recency_bonus(hours) = max(0.0, 20.0 - max(0.0, hours) / 6.0): 20 now, 10 after 2.5 days, 0 from 5 days. hours = (at - t) / 3_600_000. | as_engine/mind/retrieval.py | `as_engine/mind/retrieval.py` | `contract/p06_memory/test_retrieval.py` |
| MEM-13 | MEM-13 beliefs: the holder's live believed holdings (believed 1, superseded_by NULL); subject = the proposition's subject_id (a claims row: claims.subject_id); score = confidence * 10 + recency_bonus(hours since acquire… | as_engine/mind/retrieval.py | `as_engine/mind/retrieval.py` | `contract/p06_memory/test_retrieval.py` |
| MEM-14 | MEM-14 episodes: the holder's episodes with decayed 0. Anchors (anchor 1) come first and always: ordered (salience desc, at desc, episode_id), at most 2. Then the rest by score = salience + (20 when any subject_id is in… | as_engine/mind/retrieval.py | `as_engine/mind/memory.py`, `as_engine/mind/retrieval.py` | `contract/p06_memory/test_retrieval.py` |
| MEM-15 | MEM-15 lessons: the holder's lessons whose cue_tags intersect mind.cues.cues_of(tx, holder, turn_index, at), ordered (confidence desc, at desc, lesson_id), at most MAX_LESSONS. Entries {lesson_id, text, confidence, cue_… | as_engine/mind/retrieval.py | `as_engine/mind/retrieval.py` | `contract/p06_memory/test_retrieval.py` |
| MEM-16 | MEM-16 loops: the holder's 'open' loops; those with any subject_id in M first, then the rest; each part ordered (strength desc, created_at desc, loop_id); the first max_loops. Entries {loop_id, kind, text, strength, sub… | as_engine/mind/retrieval.py | `as_engine/mind/retrieval.py` | `contract/p06_memory/test_retrieval.py` |
| MEM-17 | MEM-17 refusals: the holder's refusals with status 'standing' or 'reopened' whose requester_id is in M — a standing refusal comes back when the one who asked is here or named (WILL-05) — ordered (created_at, refusal_id)… | as_engine/mind/retrieval.py | `as_engine/mind/packet.py`, `as_engine/mind/retrieval.py` | `contract/p06_memory/test_retrieval.py`, `contract/p07_slice/test_slice_refusal.py` |

## MIG

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| MIG-01 | */ D-09 / MIG-01: a v4 `CODEX-4.0` save imports with backfill flags / The migration framework (diagnose → report → consent → backfill events) is built in P12 for AS schema changes; importing `CODEX-4.0` saves waits for a…* | DECISIONS §2 | — | — |

## NARR

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| NARR-00 | *handle to any table except narration/narrator_state/echo_ledger (NARR-00). MUST NOT import* | as_engine/narration/__init__.py | `as_engine/narration/__init__.py` | `contract/p07_slice/test_narration_lint.py` |
| NARR-01 | *Narrator packet, narration call and the narration row (Stages 16-18). Rules NARR-01..08, L9,* | as_engine/narration/narrator.py | `as_engine/narration/narrator.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| NARR-02 | *Narrator packet, narration call and the narration row (Stages 16-18). Rules NARR-01..08, L9,* | as_engine/narration/narrator.py | `as_engine/narration/narrator.py` | `contract/p07_slice/test_p07_slice_metal_fence.py`, `contract/p07_slice/test_slice_checks.py` |
| NARR-03 | *Narrator packet, narration call and the narration row (Stages 16-18). Rules NARR-01..08, L9,* | as_engine/narration/narrator.py | `as_engine/narration/narrator.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| NARR-04 | *Narrator packet, narration call and the narration row (Stages 16-18). Rules NARR-01..08, L9,* | as_engine/narration/narrator.py | `as_engine/narration/narrator.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| NARR-05 | *Narrator packet, narration call and the narration row (Stages 16-18). Rules NARR-01..08, L9,* | as_engine/narration/narrator.py | `as_engine/narration/narrator.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| NARR-06 | NARR-06. Owner 'narration.lint' (writes echo_ledger only, through ECHO_RECORD events). Code decides; | as_engine/narration/lint.py | `as_engine/contracts/narration.py`, `as_engine/narration/lint.py`, `as_engine/narration/narrator.py` | `contract/p07_slice/test_narration_lint.py` |
| NARR-07 | *Narrator packet, narration call and the narration row (Stages 16-18). Rules NARR-01..08, L9,* | as_engine/narration/narrator.py | `as_engine/narration/narrator.py`, `as_engine/turn/pipeline.py` | `contract/p07_slice/test_narration_lint.py` |
| NARR-08 | *Output shape (NARR-08): one uninterrupted scene — no headings, labels, stat blocks, lists or* | as_engine/narration/narrator.py | `as_engine/narration/narrator.py` | — |
| NARR-09 | *Narrator continuity state (P11). Rules STYLE-03, NARR-09. Owner 'narration.narrator'.* | as_engine/narration/style.py | `as_engine/narration/style.py` | — |

## OBJ

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| OBJ-02 | * transfer (OBJ-02): a hand slot (hand_l / hand_r) holds at most ONE item -> ValueError when it* | as_engine/physical/objects.py | `as_engine/physical/objects.py` | `contract/p02_space_bodies/test_objects.py` |
| OBJ-03 | *Access time (OBJ-03): an item in a hand 0 s; 'worn' 1 s; 'pocket' 2 s; 'pack' 4 s; lying in a* | as_engine/physical/objects.py | `as_engine/physical/objects.py` | `contract/p02_space_bodies/test_objects.py` |
| OBJ-04 | (named only by tests) |  | — | `contract/p02_space_bodies/test_objects.py` |
| OBJ-05 | *Firearms (OBJ-05): a magazine-fed firearm item's props = {"chambered": bool}; its magazine is an* | as_engine/physical/objects.py | `as_engine/physical/objects.py` | `contract/p02_space_bodies/test_objects.py` |
| OBJ-06 | *Carried mass (OBJ-06): sum(mass_g x qty) / 1000 over everything held by the body in any slot,* | as_engine/physical/objects.py | `as_engine/physical/objects.py` | `contract/p02_space_bodies/test_objects.py` |

## OPS

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| OPS-01 | OPS-01) — lockdown(...) below sets it. lockdown(tx, settlement_id, on, reason, at, turn_index, cause) -> Event / None: society.settlement. set_lockdown (STL-13) — the one door shut, or open again. | as_engine/world/factions.py | `as_engine/world/factions.py`, `as_engine/world/worldmove.py` | `contract/p10_world/test_ghosts.py`, `contract/p10_world/test_operations.py` |
| OPS-02 | OPS-02 step(tx, rng, row, fired, turn_index) -> list[Event] (the OPERATION_STEP handler) The operation (status 'active'; otherwise []). movers = participants alive and outside the active area (those in it are on-screen… | as_engine/world/worldmove.py | `as_engine/world/factions.py`, `as_engine/world/worldmove.py` | `contract/p10_world/test_operations.py` |
| OPS-03 | OPS-03 outcome(...) at the destination, stream 'offscreen', purposes f"{op}:<what>": every mover: rng.chance(world.hordes.density(the destination's zone) / 20) (P10: how thick the district's dead actually are — a cleare… | as_engine/world/worldmove.py | `as_engine/world/decay.py`, `as_engine/world/hordes.py`, `as_engine/world/worldmove.py` | `contract/p10_world/test_hordes.py`, `contract/p10_world/test_operations.py` |
| OPS-04 | OPS-04 WORLD-03 (fidelity C11): evidence comes from what happened. An operation leaves the traces its own steps make (OPS-03) and nothing else; no share of off-screen events is required to leave one, and no clue is guar… | as_engine/world/worldmove.py | `as_engine/world/worldmove.py` | — |
| OPS-05 | OPS-05 on_arrival(tx, rng, body_id, place_id, at, cause_event_id, turn_index) -> list[Event] (called after a MOVE into a new place by action.effects, society.routine, this module and world.worldgen; not for infected bod… | as_engine/world/worldmove.py | `as_engine/world/worldmove.py` | `contract/p10_world/test_discovery.py` |
| OPS-06 | OPS-06 depart(tx, rng, at, turn_index, cause) -> list[Event] (the loyalty plan acted on) Per actor (by id) with an open loop of kind 'plan' whose text starts with "Leave " and whose created_at <= at - W.defect_after_day… | as_engine/world/worldmove.py | `as_engine/world/worldmove.py` | `contract/p04_one_actor/test_knowledge_menus.py` |
| OPS-07 | OPS-07 The hurt are tended (C01: a wound kills when nobody could stop it, not because the party was off-screen). Right after outcome(...) at 'arrive': per mover (by id), per unhealed wound of theirs (by wound_id) that i… | as_engine/world/worldmove.py | `as_engine/world/worldmove.py` | `contract/p10_world/test_world_day.py` |
| OPS-08 | OPS-08 launch(tx, group_id, kind, participants, origin, destination, at, turn_index, cause, *, target_id=None) -> str (OPS-01's daily plan and world.factions FAC-04 DECON) op_id = tx.mint('ops'); FACTION_OPERATION {op_i… | as_engine/world/worldmove.py | `as_engine/world/worldmove.py` | `contract/p10_world/test_operations.py` |

## PARSE

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| PARSE-01 | *Output parsing (P1). Rules PARSE-01..05. Pure functions; no I/O.* | as_engine/lanes/parse.py | `as_engine/lanes/parse.py` | `contract/p01_lanes/test_client.py`, `contract/p01_lanes/test_parse.py` |
| PARSE-02 | *Output parsing (P1). Rules PARSE-01..05. Pure functions; no I/O.* | as_engine/lanes/parse.py | `as_engine/lanes/parse.py` | `contract/p01_lanes/test_parse.py` |
| PARSE-03 | *Output parsing (P1). Rules PARSE-01..05. Pure functions; no I/O.* | as_engine/lanes/parse.py | `as_engine/lanes/parse.py` | `contract/p01_lanes/test_parse.py` |
| PARSE-04 | *Output parsing (P1). Rules PARSE-01..05. Pure functions; no I/O.* | as_engine/lanes/parse.py | `as_engine/lanes/parse.py` | `contract/p01_lanes/test_parse.py` |
| PARSE-05 | *extract_quotes(text) -> list[str] (PARSE-05)* | as_engine/lanes/parse.py | `as_engine/lanes/parse.py`, `as_engine/turn/intake.py` | `contract/p01_lanes/test_parse.py` |

## PORT

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| PORT-01 | *Portrayal audit (Stage 15, P11). Rules AUDIT-01, PORT-01..03, L13.* | as_engine/audit/portrayal.py | `as_engine/audit/portrayal.py` | — |
| PORT-02 | *Portrayal audit (Stage 15, P11). Rules AUDIT-01, PORT-01..03, L13.* | as_engine/audit/portrayal.py | `as_engine/audit/portrayal.py` | — |

## PROG

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| PROG-01 | PROG-01 Jobs: 'worldgen' (service.runs.create_run), 'turn' (turn.pipeline.run_turn), 'quiet_hours' (service.background.catch_up before a move) and 'time_skip' (sleeping or waiting a long while — P12 wires it). One Track… | as_engine/service/progress.py | `as_engine/contracts/protocol.py`, `as_engine/service/progress.py` | `contract/p10_world/test_progress.py` |
| PROG-02 | PROG-02 Plans are fixed (PLANS below): kind -> tuple[Phase]; Phase(id, label, weight, subs: tuple[Sub(id, label)]). Weights of a plan sum to 100. Labels are plain words (UI-CLARITY-01: never an engine term). A turn's su… | as_engine/service/progress.py | `as_engine/contracts/protocol.py`, `as_engine/service/progress.py` | `contract/p10_world/test_progress.py` |
| PROG-03 | PROG-03 Tracker(kind, job_id, push, *, dev=False, clock=None) (clock: seconds, a zero-argument callable; None -> the running asyncio loop's time(), read when a message is made — the clock turn_progress's elapsed_s alrea… | as_engine/service/progress.py | `as_engine/contracts/protocol.py`, `as_engine/service/progress.py` | `contract/p10_world/test_progress.py` |
| PROG-04 | PROG-04 pct = the weights of the phases before this one + this phase's weight x f, where f = done / total when both are given (total > 0), else the sub's position (index / number of subs; 0 without subs); rounded to 1 d… | as_engine/service/progress.py | `as_engine/contracts/protocol.py`, `as_engine/service/progress.py` | `contract/p10_world/test_progress.py` |
| PROG-05 | PROG-05 No leaks (normal mode). A progress message's detail is None unless dev is True (the run's dev_mode): step() drops it otherwise. No message says who is thinking, how many minds are, where anything is or what a ro… | as_engine/service/progress.py | `as_engine/contracts/protocol.py`, `as_engine/service/progress.py`, `as_content/packs/core/ui/quips.yaml` | `contract/p10_world/test_progress.py` |
| PROG-06 | PROG-06 quips_for(canon, kind) -> dict[str, list[str]]: every canon 'quips' record's lines whose key starts with kind (keys: kind, f"{kind}.{phase}", f"{kind}.{phase}.{sub}"), merged over the packs in load order (a late… | as_engine/service/progress.py | `as_engine/contracts/content.py`, `as_engine/contracts/protocol.py`, `as_engine/service/progress.py`, `as_content/packs/core/ui/quips.yaml` | `contract/p10_world/test_progress.py` |
| PROG-07 | PROG-07 (the UI's side, 10_UI.md) The bar shows every phase of the plan in order with the current one lit, the sub-phase label under it, and one quip: the most specific non-empty list for (kind, phase, sub), then (kind,… | as_engine/service/progress.py | `as_engine/service/progress.py` | — |

## PROMPT

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| PROMPT-01 | PROMPT-01 KV-cache order**: stable → volatile. The system template never contains volatile | 08_LLM_CALLS §6 | `as_engine/lanes/requests.py`, `as_engine/prompts/render.py` | `contract/p01_lanes/test_prompts.py` |
| PROMPT-02 | PROMPT-02 No pseudo-code in what the model reads**: plain organised English. Bracket-colon | 08_LLM_CALLS §6 | `as_engine/prompts/render.py` | `contract/p01_lanes/test_prompts.py` |

## PROP

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| PROP-01 | *they carry no table writes). Rules PROP-01..04.* | as_engine/action/propagate.py | `as_engine/action/propagate.py` | — |
| PROP-02 | *they carry no table writes). Rules PROP-01..04.* | as_engine/action/propagate.py | `as_engine/action/propagate.py` | — |
| PROP-03 | *they carry no table writes). Rules PROP-01..04.* | as_engine/action/propagate.py | `as_engine/action/propagate.py` | — |
| PROP-04 | * Infected attraction (PROP-04, P10): for every NOISE and SPEECH among ``outcome_events`` (seq* | as_engine/action/propagate.py | `as_engine/action/propagate.py` | — |

## PROTO

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| PROTO-01 | PROTO-01 Every reply and push is one envelope (below) whose data validates against OUT_MODELS. | as_engine/service/game_service.py | `as_engine/service/game_service.py` | `contract/p08_ui_protocol/protocol_kit.py`, `contract/p08_ui_protocol/test_protocol.py`, `contract/p08_ui_protocol/test_runs_protocol.py`, `contract/p08_ui_protocol/test_ui_fixtures.py` |
| PROTO-02 | PROTO-02 One GameService per process (get_service): a reloaded page reaches the same game, and a new connection's subscription receives the pushes of a turn that was already running. | as_engine/service/game_service.py | `as_engine/service/game_service.py` | `contract/p08_ui_protocol/test_protocol.py`, `contract/p08_ui_protocol/test_turns_protocol.py` |
| PROTO-03 | PROTO-03 handle() never raises: a bad message, a refusal or a fault is an error reply. | as_engine/service/game_service.py | `as_engine/service/game_service.py` | `contract/p08_ui_protocol/test_protocol.py` |
| PROTO-04 | PROTO-04 A turn runs as a background task: turn_submit answers at once; progress and the result are pushed. | as_engine/service/game_service.py | `as_engine/service/game_service.py` | `contract/p08_ui_protocol/test_turns_protocol.py` |
| PROTO-05 | PROTO-05 One turn at a time. While it runs, anything that would read or change the run answers busy, except view_get / story_get, which answer with the state from before the turn. | as_engine/service/game_service.py | `as_engine/service/game_service.py` | `contract/p08_ui_protocol/test_turns_protocol.py` |
| PROTO-06 | PROTO-06 turn_cancel before stage 12 leaves the world, the clock and the input exactly as they were; from stage 12 on it is refused (too_late). | as_engine/service/game_service.py | `as_engine/service/game_service.py` | `contract/p08_ui_protocol/test_turns_protocol.py` |
| PROTO-07 | PROTO-07 Ask is not a turn: service.guide answers it; nothing in the world changes or hears it. | as_engine/service/game_service.py | `as_engine/service/game_service.py`, `as_engine/service/guide.py` | `contract/p08_ui_protocol/test_turns_protocol.py` |
| PROTO-08 | PROTO-08 Every error message is a plain sentence of at least 20 characters saying what happened and what to do; never a stack trace (UI-CLARITY-06). | as_engine/service/game_service.py | `as_engine/service/game_service.py` | `contract/p08_ui_protocol/protocol_kit.py`, `contract/p08_ui_protocol/test_protocol.py` |
| PROTO-09 | PROTO-09 An action of a later phase answers not_built_yet until that phase builds it. | as_engine/service/game_service.py | `as_engine/service/game_service.py` | `contract/p08_ui_protocol/test_protocol.py` |
| PROTO-10 | PROTO-10 Mid-run settings: only service.session.CHANGEABLE_SETTINGS change (SET-02), one SETTINGS_CHANGE per field (SET-01); config_set changes only the lanes and background thinking. | as_engine/service/game_service.py | `as_engine/service/game_service.py` | `contract/p08_ui_protocol/test_models_config.py`, `contract/p08_ui_protocol/test_settings_dev.py` |

## REACT

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| REACT-01 | *Reaction gate and waves (Stage 11, P5). Rules TIME-02, TIME-04, REACT-01..04.* | as_engine/action/reactions.py | `as_engine/action/reactions.py`, `as_content/packs/core/cues.yaml` | `contract/p05_many_actors/test_reactions_cascade_plan.py`, `contract/p07_slice/test_p07_slice_metal_fence.py`, `contract/p10_world/test_infected.py`, `contract/p10_world/test_new_life.py` |
| REACT-02 | *Reaction gate and waves (Stage 11, P5). Rules TIME-02, TIME-04, REACT-01..04.* | as_engine/action/reactions.py | `as_engine/action/reactions.py` | `contract/p05_many_actors/test_reactions_cascade_plan.py` |
| REACT-03 | *Reaction gate and waves (Stage 11, P5). Rules TIME-02, TIME-04, REACT-01..04.* | as_engine/action/reactions.py | `as_engine/action/reactions.py` | `contract/p05_many_actors/test_reactions_cascade_plan.py` |

## REL

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| REL-01 | REL-01 relate(tx, from_id, to_id, axis, delta, cause, at, turn_index) -> Event / None changes ONE axis of the (from_id, to_id) row by ``delta``. A missing row is created by the same event: kind 'acquaintance', every axi… | as_engine/mind/mind.py | `as_engine/mind/mind.py` | `contract/p06_memory/test_mind.py` |
| REL-02 | REL-02 The new value is clamped to RELATION_AXIS_RANGE[axis]. The event records what actually changed; when nothing changes (delta 0, or the axis is already at the bound in that direction) no event is committed and None… | as_engine/mind/mind.py | `as_engine/mind/mind.py` | `contract/p06_memory/test_mind.py` |
| REL-03 | REL-03 Every change keeps its cause: causes[axis] = ``cause`` (the latest cause per axis, JSON object; the key is the axis value, e.g. 'trust'). | as_engine/mind/mind.py | `as_engine/mind/mind.py` | `contract/p06_memory/test_mind.py` |
| REL-04 | REL-04 A relationship is one-directional: relate(from, to) never reads or writes the (to, from) row. from_id == to_id -> ValueError (nobody has a relationship with themselves). | as_engine/mind/mind.py | `as_engine/mind/mind.py` | `contract/p06_memory/test_mind.py` |
| REL-05 | REL-05 relate never changes ``kind`` (content, households and worldgen set kinds); an existing row keeps its kind. | as_engine/mind/mind.py | `as_engine/mind/mind.py` | `contract/p06_memory/test_mind.py` |

## REPLY

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| REPLY-01 | REPLY-01 reading an answer (Actor Spec §7): parse_status 'ok' -> ActorReplyV2.model_validate( parsed) (its V1 adapter reads a V1 answer; a validation error is a failure of kind 'schema_fail'). A decision -> action.inten… | as_engine/turn/cognition.py | `as_engine/turn/cognition.py` | `contract/p07_slice/test_decision_v2.py` |
| REPLY-02 | REPLY-02 at most two decision calls and one repair per decision (Actor Spec §7): an actor whose first answer is a valid consultation gets it answered — consulted = mind.consult.answer(tx, packet, affs[actor], reply.cons… | as_engine/turn/cognition.py | `as_engine/mind/consult.py`, `as_engine/turn/cognition.py` | `contract/p07_slice/test_decision_v2.py` |

## RES

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| RES-01 | *Resolve pool (P4). Rules RES-01..05. Resolve gates affordances; it never modifies a roll.* | as_engine/mind/resolve.py | `as_engine/mind/resolve.py` | `contract/p04_one_actor/test_resolve.py` |
| RES-02 | *Resolve pool (P4). Rules RES-01..05. Resolve gates affordances; it never modifies a roll.* | as_engine/mind/resolve.py | `as_engine/mind/resolve.py` | `contract/p04_one_actor/test_resolve.py` |
| RES-03 | *Resolve pool (P4). Rules RES-01..05. Resolve gates affordances; it never modifies a roll.* | as_engine/mind/resolve.py | `as_engine/mind/resolve.py` | `contract/p04_one_actor/test_resolve.py` |
| RES-04 | *Resolve pool (P4). Rules RES-01..05. Resolve gates affordances; it never modifies a roll.* | as_engine/mind/resolve.py | `as_engine/mind/resolve.py` | `contract/p04_one_actor/test_resolve.py` |

## RESOLVE

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| RESOLVE-01 | *Resolution (Stage 8, P5). Rules RESOLVE-01..06, G8. The resolver is the only place intents* | as_engine/action/resolve.py | `as_engine/action/resolve.py` | `contract/p05_many_actors/test_resolve.py`, `contract/p07_slice/test_slice_checks.py` |
| RESOLVE-02 | *Resolution (Stage 8, P5). Rules RESOLVE-01..06, G8. The resolver is the only place intents* | as_engine/action/resolve.py | `as_engine/action/resolve.py` | `contract/p05_many_actors/test_resolve.py`, `contract/p07_slice/test_slice_checks.py` |
| RESOLVE-03 | *Resolution (Stage 8, P5). Rules RESOLVE-01..06, G8. The resolver is the only place intents* | as_engine/action/resolve.py | `as_engine/action/resolve.py` | `contract/p05_many_actors/test_resolve.py`, `contract/p07_slice/test_slice_checks.py` |
| RESOLVE-04 | *Resolution (Stage 8, P5). Rules RESOLVE-01..06, G8. The resolver is the only place intents* | as_engine/action/resolve.py | `as_engine/action/resolve.py` | `contract/p05_many_actors/test_resolve.py`, `contract/p07_slice/test_slice_checks.py` |
| RESOLVE-05 | *Resolution (Stage 8, P5). Rules RESOLVE-01..06, G8. The resolver is the only place intents* | as_engine/action/resolve.py | `as_engine/action/resolve.py` | `contract/p05_many_actors/test_resolve.py`, `contract/p07_slice/test_slice_checks.py` |

## ROUT

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| ROUT-01 | ROUT-01 Who has a routine: a living body with an actors row whose controller is NOT 'human' (code never acts for a human-controlled body — SEL-06) and who is a named member of a settlement (society.population.census; th… | as_engine/society/routine.py | `as_engine/society/routine.py` | `contract/p09_society/test_routine.py` |
| ROUT-02 | ROUT-02 steps_for(store, actor_id) -> list[Step] (derived fresh on every call; never cached) Step(start_hh, end_hh, activity, place_id, workplace_id=None, role=None) covers the hours [start_hh, end_hh) of every day; end… | as_engine/society/routine.py | `as_engine/society/routine.py` | `contract/p09_society/test_routine.py` |
| ROUT-03 | ROUT-03 step_for(store, actor_id, hour) -> Step / None: the step whose window contains ``hour`` (0..23); None without a routine. | as_engine/society/routine.py | `as_engine/society/routine.py` | `contract/p09_society/test_routine.py` |
| ROUT-04 | ROUT-04 next_boundary(store, actor_id, after_ms) -> int / None: the smallest t > after_ms whose minute and second are 0 and whose hour is the start_hh of one of the actor's steps. None without a routine. | as_engine/society/routine.py | `as_engine/society/routine.py` | `contract/p09_society/test_routine.py` |
| ROUT-05 | ROUT-05 COLD option (action.intent.plan_continuation step 5): OPTION_FOR = {'sleep': 'sleep', 'work': 'observe_area'}; 'free' and 'play' have none (the step is skipped). | as_engine/society/routine.py | `as_engine/society/routine.py` | `contract/p09_society/test_routine.py`, `contract/p09_society/test_timers_society.py` |
| ROUT-06 | ROUT-06 step(tx, rng, row, fired, turn_index) -> list[Event] (the ROUTINE_STEP handler) actor = row['subject_id'], at = row['due_at'], cause = fired.event_id. The outcome: 'ended' steps_for is empty (dead, left the sett… | as_engine/society/routine.py | `as_engine/society/routine.py` | `contract/p09_society/test_routine.py` |
| ROUT-07 | ROUT-07 ensure_timers(tx, settlement_id, at, turn_index) -> list[str] For each named member of the settlement (sorted) with a routine and no pending ROUTINE_STEP row (kernel.clock.pending_for): kernel.clock.schedule(tx,… | as_engine/society/routine.py | `as_engine/society/routine.py` | — |

## RUN

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| RUN-01 | *Run library (P7 create-from-scenario, P10 create-from-worldgen, P12 worlds). Rules RUN-01..13.* | as_engine/service/runs.py | `as_engine/service/runs.py` | `contract/p07_slice/test_save_load.py`, `contract/p10_world/test_worldgen_pipeline.py` |
| RUN-02 | *Run library (P7 create-from-scenario, P10 create-from-worldgen, P12 worlds). Rules RUN-01..13.* | as_engine/service/runs.py | `as_engine/service/runs.py` | `contract/p07_slice/test_save_load.py`, `contract/p08_ui_protocol/test_runs_protocol.py` |
| RUN-03 | *Run library (P7 create-from-scenario, P10 create-from-worldgen, P12 worlds). Rules RUN-01..13.* | as_engine/service/runs.py | `as_engine/service/runs.py` | `contract/p07_slice/test_save_load.py`, `contract/p08_ui_protocol/test_runs_protocol.py` |
| RUN-04 | *Run library (P7 create-from-scenario, P10 create-from-worldgen, P12 worlds). Rules RUN-01..13.* | as_engine/service/runs.py | `as_engine/service/runs.py` | `contract/p07_slice/test_save_load.py`, `contract/p08_ui_protocol/test_runs_protocol.py` |
| RUN-05 | *service.runs.load_run, RUN-05). episodes_fts is a derived index kept by schema triggers,* | as_engine/kernel/store.py | `as_engine/kernel/store.py`, `as_engine/service/runs.py` | `contract/p07_slice/test_save_load.py`, `contract/p07_slice/test_slice_refusal.py`, `contract/p08_ui_protocol/test_runs_protocol.py` |
| RUN-06 | *Run library (P7 create-from-scenario, P10 create-from-worldgen, P12 worlds). Rules RUN-01..13.* | as_engine/service/runs.py | `as_engine/service/runs.py` | `contract/p07_slice/test_save_load.py`, `contract/p08_ui_protocol/test_sessions.py` |
| RUN-07 | *P12: RUN-07.* | as_engine/service/game_service.py | `as_engine/service/game_service.py`, `as_engine/service/runs.py` | — |
| RUN-08 | *Run library (P7 create-from-scenario, P10 create-from-worldgen, P12 worlds). Rules RUN-01..13.* | as_engine/service/runs.py | `as_engine/service/runs.py` | — |
| RUN-09 | *A reusable world: the genesis snapshot of a generated (or imported) world (RUN-09).* | as_engine/contracts/view.py | `as_engine/contracts/view.py`, `as_engine/kernel/store.py`, `as_engine/service/game_service.py`, `as_engine/service/runs.py`, `as_engine/world/worldgen/pipeline.py` | `contract/p10_world/test_world_names_no_run.py`, `contract/p10_world/test_worldgen_pipeline.py` |
| RUN-10 | *Run library (P7 create-from-scenario, P10 create-from-worldgen, P12 worlds). Rules RUN-01..13.* | as_engine/service/runs.py | `as_engine/service/runs.py` | `contract/p07_slice/test_save_load.py` |
| RUN-11 | *Run library (P7 create-from-scenario, P10 create-from-worldgen, P12 worlds). Rules RUN-01..13.* | as_engine/service/runs.py | `as_engine/service/runs.py` | `contract/p10_world/test_worldgen_pipeline.py` |
| RUN-12 | RUN-12 a deleted session leaves nothing of it: one step for the player, no soft delete, every file the game wrote for the run wiped (wipe_tree); the world it was played in stays and names no run. | as_engine/service/runs.py | `as_engine/contracts/protocol.py`, `as_engine/service/game_service.py`, `as_engine/service/runs.py` | `contract/p08_ui_protocol/test_runs_protocol.py`, `contract/p08_ui_protocol/test_sessions.py`, `contract/p10_world/test_world_names_no_run.py` |
| RUN-13 | RUN-13 process-wide logs name no session: the engine and the service log action names, error codes and exception types only — never a run_id, a character's name, or anything said, typed or written in a run. What a run n… | as_engine/service/runs.py | `as_engine/service/game_service.py`, `as_engine/service/runs.py` | `contract/p08_ui_protocol/test_sessions.py` |

## SCENE

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| SCENE-01 | SCENE-01, the rollback law. docs/as/04_TURN_PIPELINE.md is the narrative; this docstring is the | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | `contract/p07_slice/test_slice_refusal.py` |
| SCENE-02 | *a pressure already in committed state, never mint one (SCENE-02); scene end triggers the PC's* | 04_TURN_PIPELINE §6 | — | — |

## SCHED

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| SCHED-01 | *audit.log.repair('budget_overrun', 4, 'SCHED-01', {notes}). The wave's record {wave, at,* | as_engine/turn/pipeline.py | `as_engine/turn/pipeline.py` | — |

## SCHEMA

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| SCHEMA-01 | *JSON schemas for constrained decoding (P1). Rules SCHEMA-01..04.* | as_engine/lanes/schemas.py | `as_engine/lanes/schemas.py` | `contract/p01_lanes/test_schemas.py` |
| SCHEMA-02 | *LANE-03, PROMPT-01, SCHEMA-02. Nothing above this boundary writes messages by hand.* | as_engine/lanes/requests.py | `as_engine/lanes/requests.py`, `as_engine/lanes/schemas.py` | `contract/p01_lanes/test_schemas.py` |
| SCHEMA-03 | SCHEMA-03: affordance_handles (cognition, intake) and percept_handles (writeback) must be | as_engine/lanes/schemas.py | `as_engine/lanes/schemas.py` | `contract/p01_lanes/test_schemas.py` |
| SCHEMA-04 | SCHEMA-04: a schema offers only what the engine can do: a field whose handles or attempt the | as_engine/lanes/schemas.py | `as_engine/lanes/schemas.py` | `contract/p01_lanes/test_schemas.py` |

## SCOPE

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| SCOPE-01 | *Table ownership (rule STORE-02 / SCOPE-01).* | as_engine/kernel/ownership.py | `as_engine/kernel/ownership.py` | `contract/p00_substrate/test_ownership.py` |

## SEG

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| SEG-01 | *Paused: Actor v2 step 4 (speech in segments, SEG-01..04) is half-written and kept out of the repo* | HANDOFF §0 | — | — |
| SEG-02 | *Paused: Actor v2 step 4 (speech in segments, SEG-01..04) is half-written and kept out of the repo* | HANDOFF §0 | — | — |
| SEG-03 | *Paused: Actor v2 step 4 (speech in segments, SEG-01..04) is half-written and kept out of the repo* | HANDOFF §0 | — | — |

## SEL

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| SEL-01 | SEL-01 active_area(tx, pc_id, turn_index) -> list[str] (sorted place ids) The PC's place, every place within 2 portal hops of it (physical.space.places_near(place, 2): walls and fences count as hops), and — for every NO… | as_engine/turn/select.py | `as_engine/turn/select.py` | `contract/p07_slice/test_p07_slice_metal_fence.py`, `contract/p10_world/test_hordes.py` |
| SEL-02 | SEL-02 mandatory(tx, actor_id, turn_index, at, horizon_ms, pc_intent, forced=frozenset()) -> bool True when ANY of (a mandatory mind always gets a model call, even past the budget): * actor_id in ``forced`` (a pending r… | as_engine/turn/select.py | `as_engine/mind/temper.py`, `as_engine/turn/select.py` | `contract/p07_slice/test_breaking_point.py`, `contract/p07_slice/test_p07_slice_metal_fence.py` |
| SEL-03 | SEL-03 salience_flags(tx, actor_id, cands, pc_id, turn_index, at) -> dict[str, bool] ``cands`` = the conscious candidates of this wave. Over this turn's percept rows up to the wave (percept_log, turn_index == turn_index… | as_engine/turn/select.py | `as_engine/turn/select.py` | `contract/p07_slice/test_breaking_point.py`, `contract/p07_slice/test_p07_slice_metal_fence.py` |
| SEL-04 | SEL-04 salience(flags, is_mandatory, weights) -> float sum(weights[flag] for true flags) + weights['mandatory'] when mandatory (SchedulerRules .salience_weights). lanes.scheduler.plan_cognition orders by it (ties by act… | as_engine/turn/select.py | `as_engine/turn/select.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| SEL-05 | SEL-05 conscious(tx, actor_id) -> bool bodies.alive = 1 and awareness in ('awake', 'drowsy'). Only conscious candidates are planned, offered options, or asked to decide. | as_engine/turn/select.py | `as_engine/turn/select.py` | `contract/p07_slice/test_p07_slice_metal_fence.py` |
| SEL-06 | SEL-06 The PC is never a candidate, never planned and never reacts: the player decides for the PC (the pipeline passes exclude={pc} to action.reactions.next_wave). | as_engine/turn/select.py | `as_engine/society/group.py`, `as_engine/society/routine.py`, `as_engine/turn/select.py` | `contract/p09_society/test_routine.py`, `contract/p09_society/test_work.py` |

## SET

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| SET-01 | A mid-run settings change commits `SETTINGS_CHANGE` (payload: field, old, new) and applies from the next turn; re-simulation re-applies it at the same point (`service/session.change_settings`, `service/replay.resimulate… | 11_SETTINGS §3 | `as_engine/service/game_service.py`, `as_engine/service/replay.py`, `as_engine/service/session.py` | `contract/p08_ui_protocol/test_settings_dev.py` |
| SET-02 | Locked settings (§1.1) cannot change after `run_new`; `config`/`view` never offer them. | 11_SETTINGS §3 | `as_engine/service/game_service.py`, `as_engine/service/session.py` | `contract/p08_ui_protocol/test_settings_dev.py` |
| SET-03 | A run uses the `RulesConfig` frozen in `meta.rules_json` at creation. | 11_SETTINGS §3 | `as_engine/kernel/store.py`, `as_engine/service/runs.py`, `as_engine/service/session.py` | — |
| SET-04 | No setting changes what a body can do, what a mind knows, or any probability — except difficulty and save mode, which are world definitions chosen before the world exists. | 11_SETTINGS §3 | — | — |

## SHA

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| SHA-256 | *"Protected" means three things. (1) `tools/as/protected_manifest.json` holds a SHA-256 of every* | 12_TESTING §1 | — | — |

## SKULL

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| SKULL-01 | *a person carries comes from the body and its items, SKULL-01), motive.risk_threshold and* | as_engine/mind/identity.py | `as_engine/mind/identity.py`, `as_engine/mind/packet.py`, `as_engine/mind/perception.py`, `as_content/packs/core/cascade/people.yaml` | `contract/p03_perception/test_perception.py`, `contract/p04_one_actor/test_packet.py`, `contract/p05_many_actors/test_telepathy.py`, `contract/p07_slice/test_p07_slice_metal_fence.py`, `contract/p09_society/test_rumours.py` |
| SKULL-02 | *Import boundary (SKULL-02, BOUND-02): only these modules may import ``as_engine.kernel.truth``:* | as_engine/kernel/truth.py | `as_engine/kernel/truth.py`, `as_engine/mind/cues.py`, `as_engine/mind/packet.py`, `as_engine/mind/perception.py` | `contract/p00_substrate/test_boundaries.py`, `contract/p03_perception/test_perception.py`, `contract/p04_one_actor/test_packet.py` |
| SKULL-03 | *Skull Packet builder (P4). THE ONLY CONSTRUCTOR OF SkullPacket. Rules SKULL-01..10, WILL-00, WILL-C,* | as_engine/mind/packet.py | `as_engine/mind/packet.py`, `as_engine/mind/perception.py` | `contract/p03_perception/test_perception.py`, `contract/p04_one_actor/test_packet.py` |
| SKULL-04 | *Skull Packet builder (P4). THE ONLY CONSTRUCTOR OF SkullPacket. Rules SKULL-01..10, WILL-00, WILL-C,* | as_engine/mind/packet.py | `as_engine/mind/packet.py`, `as_engine/mind/perception.py` | `contract/p03_perception/test_perception.py`, `contract/p04_one_actor/test_packet.py` |
| SKULL-05 | *Skull Packet builder (P4). THE ONLY CONSTRUCTOR OF SkullPacket. Rules SKULL-01..10, WILL-00, WILL-C,* | as_engine/mind/packet.py | `as_engine/mind/packet.py`, `as_engine/mind/perception.py` | `contract/p03_perception/test_perception.py`, `contract/p04_one_actor/test_packet.py`, `contract/p09_society/test_rumours.py` |
| SKULL-06 | *Skull Packet builder (P4). THE ONLY CONSTRUCTOR OF SkullPacket. Rules SKULL-01..10, WILL-00, WILL-C,* | as_engine/mind/packet.py | `as_engine/mind/packet.py`, `as_engine/mind/perception.py` | `contract/p03_perception/test_perception.py`, `contract/p04_one_actor/test_affordances.py`, `contract/p04_one_actor/test_packet.py` |
| SKULL-07 | *Skull Packet builder (P4). THE ONLY CONSTRUCTOR OF SkullPacket. Rules SKULL-01..10, WILL-00, WILL-C,* | as_engine/mind/packet.py | `as_engine/mind/packet.py` | `contract/p04_one_actor/test_packet.py` |
| SKULL-08 | *Skull Packet builder (P4). THE ONLY CONSTRUCTOR OF SkullPacket. Rules SKULL-01..10, WILL-00, WILL-C,* | as_engine/mind/packet.py | `as_engine/mind/packet.py` | `contract/p04_one_actor/test_packet.py` |
| SKULL-09 | *it (SKULL-09): a smaller prompt never costs a person their identity.* | as_engine/mind/identity.py | `as_engine/mind/identity.py`, `as_engine/mind/packet.py` | `contract/p04_one_actor/test_packet.py`, `contract/p06_memory/test_retrieval.py` |
| SKULL-10 | SKULL-10 in `mind/packet`, P4; how a move reads, P3), build it now. A builder updating from an | 13_BUILD_ORDER §1 | `as_engine/mind/affordance.py`, `as_engine/mind/memory.py`, `as_engine/mind/packet.py`, `as_engine/mind/retrieval.py`, `as_engine/mind/temper.py`, `as_engine/turn/select.py` | `contract/p04_one_actor/test_affordances.py`, `contract/p04_one_actor/test_packet.py`, `contract/p10_world/test_new_life.py` |

## SMELL

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| SMELL-01 | SMELL-01 odour_of(store, body_id, at) -> Odour / None: what the body smells of, from what is on it (physical.bodies.condition_of) and, for a corpse, how long it has been dead. The candidates: 'dead' gore >= 2 strength =… | as_engine/sense/olfaction.py | `as_engine/contracts/settings.py`, `as_engine/sense/olfaction.py` | `contract/p03_perception/test_smell.py` |
| SMELL-02 | SMELL-02 smell_range_m(store, strength, place_id) -> float: O.range_m[strength], times O.outdoor_mult when the place is not indoor (places.indoor 0). | as_engine/sense/olfaction.py | `as_engine/contracts/settings.py`, `as_engine/sense/olfaction.py` | `contract/p03_perception/test_smell.py` |
| SMELL-03 | SMELL-03 smells(store, holder_id, source_id, at) -> 'exact' / 'partial' / None: whether the holder smells the source now. None when source_id == holder_id (you get used to your own), when the holder is not alive with aw… | as_engine/sense/olfaction.py | `as_engine/sense/olfaction.py` | `contract/p03_perception/test_smell.py` |
| SMELL-04 | SMELL-04 (F1b) smell_text(tx, holder_id, subject_id, at) -> str: what the holder smells on someone it can see: f = sense.olfaction.smells(tx, holder_id, subject_id, at); None -> ''; else ODOUR_WORDS[odour_of(subject).ki… | as_engine/mind/perception.py | `as_engine/mind/perception.py` | `contract/p03_perception/test_smell.py`, `contract/p04_one_actor/test_appearance_in_packet.py` |
| SMELL-05 | SMELL-05 (F1b) What the holder smells but does not see reaches it as the standing view's smell (compile_scene step 1): one OLFACTORY percept per kind, naming nobody; the nearest sets how strongly (exact over partial). S… | as_engine/mind/perception.py | `as_engine/mind/perception.py` | `contract/p03_perception/test_smell.py` |
| SMELL-06 | SMELL-06 (F1b): plus SMELL_CUES[kind] for the detail.odour of each of the holder's olfactory percept_log rows of this turn (turn_index, at <= ``at``), and for each such seen body B that sense.olfaction.smells(holder, B,… | as_engine/mind/cues.py | `as_engine/mind/cues.py`, `as_content/packs/core/cues.yaml` | `contract/p05_many_actors/test_appearance_cues.py` |

## SOC

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| SOC-01 | Worldgen seeds each settlement's relationship matrix about 20 % positive, 60 % strangers and 20 % rivals (P10, WG6). | 06_WORLD §2.6 | `as_engine/society/group.py`, `as_engine/world/worldgen/people.py` | — |
| SOC-02 | Relationships between non-player people change while the PC is nowhere near: daily drift along households, crews and friendships, grudges souring, strain under short rations (§2.5). | 06_WORLD §2.6 | `as_engine/society/__init__.py`, `as_engine/society/group.py` | `contract/p09_society/test_group.py` |
| SOC-03 | A rumour reaches trade: what a settlement's trader has heard and believes about a buyer changes the price or ends the deal (`trade_terms`, §2.4, §6). | 06_WORLD §2.6 | `as_engine/mind/mind.py`, `as_engine/society/__init__.py`, `as_engine/society/settlement.py`, `as_engine/world/worldgen/people.py`, `as_content/packs/core/cascade/people.yaml` | `contract/p09_society/test_rumours.py`, `contract/p09_society/test_settlement.py` |

## STAND

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| STAND-01 | STAND-01 standing_toward(store, group_id, actor_id) -> int: group_standing.standing of the row (group_id, actor_id), 0 without one. It is the world's memory of a person: what a group as a whole thinks of them (-5..5), w… | as_engine/mind/mind.py | `as_engine/mind/mind.py` | `contract/p09_society/test_group.py` |
| STAND-02 | STAND-02 adjust_group_standing(tx, group_id, actor_id, delta, cause_event_id, at, turn_index) -> Event / None. An unknown group -> ValueError. new = clamp(old + delta, -5, 5); new == old -> None (nothing committed). Com… | as_engine/mind/mind.py | `as_engine/mind/mind.py` | — |

## STL

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| STL-01 | STL-01 daily_need(store, settlement_id) -> dict[str, float]: society.population.consumption( census, R) with every value multiplied by R.ration_mult[ration_level]. days_of(store, settlement_id, resource) -> float: store… | as_engine/society/settlement.py | `as_engine/society/settlement.py` | `contract/p09_society/test_settlement.py` |
| STL-02 | STL-02 receive(tx, settlement_id, changes, reason, at, turn_index, cause_event_id) -> Event changes = {resource: amount} (amount may be negative). STORES_CHANGE {settlement_id, changes, after, reason}: each new value =… | as_engine/society/settlement.py | `as_engine/society/settlement.py` | `contract/p09_society/test_settlement.py` |
| STL-03 | STL-03 day(tx, rng, row, fired, turn_index) -> list[Event] (the SETTLEMENT_DAY handler, daily at R.draw_hour). s = row['subject_id'], at = row['due_at']; everything below has cause = the SETTLEMENT_DAY event (SD) unless… | as_engine/society/settlement.py | `as_engine/society/settlement.py`, `as_engine/world/worldmove.py` | `contract/p09_society/test_econ_chain.py`, `contract/p09_society/test_quarrels.py`, `contract/p09_society/test_settlement.py`, `contract/p10_world/test_world_day.py` |
| STL-04 | STL-04 declare_shortage(tx, settlement_id, resource, at, turn_index, cause_event_id) -> Event / None (cascade dispatch of SHORTAGE — core CAS-004.) Already short of it -> None. Else SHORTAGE {settlement_id, resource, da… | as_engine/society/settlement.py | `as_engine/society/settlement.py` | `contract/p09_society/test_econ_chain.py`, `contract/p09_society/test_settlement.py` |
| STL-05 | STL-05 change_ration(tx, settlement_id, delta, reason, at, turn_index, cause_event_id) -> Event / None (cascade dispatch of RATION_CHANGE — core CAS-005.) new = clamp(level + delta, 0, 4); new == level -> None. RATION_C… | as_engine/society/settlement.py | `as_engine/society/settlement.py` | `contract/p09_society/test_settlement.py` |
| STL-06 | STL-06 adjust(tx, settlement_id, field, amount, at, turn_index, cause_event_id, reason='cascade') -> Event / None: field in {'morale', 'cohesion', 'defences', 'sanitation', 'power'} (ValueError otherwise), new = clamp(o… | as_engine/society/settlement.py | `as_engine/society/settlement.py` | `contract/p09_society/test_settlement.py` |
| STL-07 | STL-07 add_vacancy(tx, settlement_id, workplace_id, role, for_actor, at, turn_index, cause) -> Event / None / remove_vacancy(tx, settlement_id, workplace_id, role, for_actor, at, turn_index, cause) -> Event / None: vaca… | as_engine/society/settlement.py | `as_engine/society/settlement.py` | `contract/p09_society/test_settlement.py` |
| STL-08 | STL-08 laws_of(store, settlement_id) -> list[str]: the laws_active law_refs, sorted. law_def(store, settlement_id, law) -> LawDef / None: ``law`` is a ref ('core:law/ration_law') or a bare id ('ration_law'); the active… | as_engine/society/settlement.py | `as_engine/society/settlement.py` | `contract/p09_society/test_settlement.py` |
| STL-09 | STL-09 apply_law(tx, settlement_id, law, subject_id, at, turn_index, cause_event_id) -> Event / None (cascade dispatch of LAW_APPLIED — core CAS-015.) Not an active law of the settlement -> audit.log.record(tx, 'G10-cas… | as_engine/society/settlement.py | `as_engine/society/settlement.py` | `contract/p09_society/test_settlement.py` |
| STL-10 | STL-10 settlement_of(store, entity_id) -> str / None: an id of kind 'stl' -> itself when it exists; 'wkp' -> workplaces.settlement_id; 'plc' -> the settlement whose place_id it is; 'hh' -> households.settlement_id, else… | as_engine/society/settlement.py | `as_engine/society/settlement.py` | `contract/p09_society/test_settlement.py` |
| STL-11 | STL-11 trade_terms(store, settlement_id, buyer_id) -> TradeTerms (SOC-03: a rumour reaches trade) trader = the named member, not the buyer, whose controller is not 'human', with the highest fused-dossier 'trade' rank >=… | as_engine/society/settlement.py | `as_engine/society/settlement.py` | `contract/p09_society/test_settlement.py` |
| STL-12 | STL-12 ensure_timers(tx, settlement_id, at, turn_index) -> list[str]: no pending SETTLEMENT_DAY row for the settlement -> kernel.clock.schedule(tx, next_hour(at, R.draw_hour), 'SETTLEMENT_DAY', settlement_id, {'settleme… | as_engine/society/settlement.py | `as_engine/society/settlement.py` | — |
| STL-13 | STL-13 set_lockdown(tx, settlement_id, on, reason, at, turn_index, cause_event_id) -> Event / None (P10, world.factions FAC-01) new = 1 when on else 0; new == settlements.lockdown -> None. Else SETTLEMENT_CHANGE {settle… | as_engine/society/settlement.py | `as_engine/society/settlement.py`, `as_engine/world/factions.py` | `contract/p10_world/test_ghosts.py` |
| STL-15 | STL-15 (H1) friction(tx, rng, settlement_id, at, turn_index, cause_event_id) -> list[Event]: people who live on top of each other, short of everything, fight. The pairs: the settlement's named members (group_members of… | as_engine/society/settlement.py | `as_engine/mind/temper.py`, `as_engine/society/settlement.py`, `as_engine/world/worldgen/people.py` | `contract/p09_society/test_quarrels.py` |

## STORE

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| STORE-00 | (named only by tests) |  | — | `contract/p00_substrate/test_store.py` |
| STORE-01 | STORE-01 world tables change only through ``Tx.commit_event`` WriteRecords. | as_engine/kernel/store.py | `as_engine/contracts/events.py`, `as_engine/kernel/store.py` | `contract/p00_substrate/test_clock.py`, `contract/p00_substrate/test_events_replay.py`, `contract/p00_substrate/test_store.py` |
| STORE-02 | STORE-02 a WriteRecord's table must be owned by the event's ``writer`` (else ScopeError). | as_engine/kernel/store.py | `as_engine/kernel/errors.py`, `as_engine/kernel/ownership.py`, `as_engine/kernel/store.py` | `contract/p00_substrate/test_store.py` |
| STORE-03 | STORE-03 TABLE_OWNERS matches schema.sql OWNER comments (tested statically). | as_engine/kernel/store.py | `as_engine/kernel/ownership.py`, `as_engine/kernel/store.py` | `contract/p00_substrate/test_ownership.py`, `contract/p00_substrate/test_store.py` |
| STORE-04 | STORE-04 ``Store.open`` refuses a file whose meta.schema_version != SCHEMA_VERSION. | as_engine/kernel/store.py | `as_engine/kernel/store.py` | `contract/p00_substrate/test_store.py` |
| STORE-05 | STORE-05 unknown EventType -> UnknownEventType. | as_engine/kernel/store.py | `as_engine/kernel/store.py` | `contract/p00_substrate/test_store.py` |
| STORE-06 | STORE-06 ids come from kernel.ids.mint only. | as_engine/kernel/store.py | `as_engine/kernel/ids.py`, `as_engine/kernel/store.py` | `contract/p00_substrate/test_ids.py`, `contract/p00_substrate/test_store.py` |
| STORE-07 | STORE-07 a transaction is atomic: any exception inside ``with store.transaction()`` rolls back every write (world tables AND bookkeeping) made in it. "Any exception" includes BaseException (P8): an asyncio.CancelledErro… | as_engine/kernel/store.py | `as_engine/kernel/store.py` | `contract/p00_substrate/test_store.py` |
| STORE-08 | STORE-08 ``events`` is append-only: UPDATE/DELETE on it raise StoreError. | as_engine/kernel/store.py | `as_engine/kernel/store.py` | `contract/p00_substrate/test_store.py` |
| STORE-09 | * UPDATE: ``UPDATE t SET values WHERE key``; zero rows affected -> StoreError (rule STORE-09).* | as_engine/kernel/store.py | `as_engine/kernel/store.py` | `contract/p00_substrate/test_store.py` |
| STORE-10 | *Run context (STORE-10): modules that need content or rule numbers read them from the store they* | as_engine/kernel/store.py | `as_engine/kernel/store.py` | `contract/p00_substrate/test_store.py` |
| STORE-11 | STORE-11 a write value equal to EVENT_SELF becomes the committing event's own id (below). | as_engine/kernel/store.py | `as_engine/kernel/store.py`, `as_engine/mind/firewall.py`, `as_engine/mind/mind.py` | `contract/p00_substrate/test_store.py`, `contract/p06_memory/test_memory.py`, `contract/p06_memory/test_mind.py`, `contract/p06_memory/test_refusals.py` |

## STYLE

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| STYLE-01 | *Render lint (Stage 18) and the echo ledger (P7). Rules STYLE-01..06, DISC-01..04, ECHO-01..03,* | as_engine/narration/lint.py | `as_engine/narration/lint.py`, `as_content/packs/core/style/narration.yaml` | `contract/p07_slice/test_narration_lint.py` |
| STYLE-02 | *Render lint (Stage 18) and the echo ledger (P7). Rules STYLE-01..06, DISC-01..04, ECHO-01..03,* | as_engine/narration/lint.py | `as_engine/narration/lint.py`, `as_content/packs/core/style/narration.yaml` | `contract/p07_slice/test_narration_lint.py` |
| STYLE-03 | *Render lint (Stage 18) and the echo ledger (P7). Rules STYLE-01..06, DISC-01..04, ECHO-01..03,* | as_engine/narration/lint.py | `as_engine/narration/lint.py`, `as_engine/narration/style.py`, `as_content/packs/core/style/narration.yaml` | `contract/p07_slice/test_narration_lint.py`, `contract/p07_slice/test_save_load.py` |
| STYLE-04 | *Render lint (Stage 18) and the echo ledger (P7). Rules STYLE-01..06, DISC-01..04, ECHO-01..03,* | as_engine/narration/lint.py | `as_engine/narration/lint.py`, `as_content/packs/core/style/narration.yaml` | `contract/p07_slice/test_narration_lint.py` |
| STYLE-05 | *Render lint (Stage 18) and the echo ledger (P7). Rules STYLE-01..06, DISC-01..04, ECHO-01..03,* | as_engine/narration/lint.py | `as_engine/narration/lint.py`, `as_content/packs/core/style/narration.yaml` | `contract/p07_slice/test_narration_lint.py` |

## SYM

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| SYM-01 | *from; simulation modules must never call this (SYM-01).* | as_engine/mind/actor.py | `as_engine/mind/actor.py`, `as_engine/physical/bodies.py` | `contract/p00_substrate/test_boundaries.py` |
| SYM-02 | *``manner`` is colour only (the PC's dossier colouring, SYM-02, and the narrator): nothing* | as_engine/action/intent.py | `as_engine/action/intent.py`, `as_engine/contracts/dossier.py`, `as_engine/turn/intake.py` | — |

## TASK

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| TASK-01 | *Rules TASK-01..03, CROWD-04.* | as_engine/action/tasks.py | `as_engine/action/tasks.py` | `contract/p05_many_actors/test_tasks.py` |
| TASK-02 | *Rules TASK-01..03, CROWD-04.* | as_engine/action/tasks.py | `as_engine/action/tasks.py` | `contract/p05_many_actors/test_tasks.py` |

## TELEPATHY

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| TELEPATHY-01 | *Gate: `p05_many_actors` green (TELEPATHY-01, BARRIER-01, INTENT-03 and HALLUC-01 included).* | 13_BUILD_ORDER §4.0 | — | `contract/p05_many_actors/test_telepathy.py` |

## TEMPER

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| TEMPER-01 | TEMPER-01 temper_of(store, actor_id) -> Temper: the actor's fused dossier temper (mind.actor.fused(store, actor_id).temper), else Temper() — fuse 3, outlet 'words', grudge 1. | as_engine/mind/temper.py | `as_engine/contracts/dossier.py`, `as_engine/mind/temper.py` | `contract/p05_many_actors/test_temper.py` |
| TEMPER-02 | TEMPER-02 Heat is anger at one person, now: tempers (holder_id, toward_id, heat 0..20, updated_at, last_kind). heat(store, holder_id, toward_id, at) -> int = the row's heat minus one per R.heat_decay_min minutes since u… | as_engine/mind/temper.py | `as_engine/contracts/settings.py`, `as_engine/mind/temper.py`, `as_content/packs/core/cascade/stress.yaml` | `contract/p05_many_actors/test_temper.py` |
| TEMPER-03 | TEMPER-03 provocations(tx, holder_id, turn_index, at) -> list[Provocation]: read from the holder's OWN percept rows (percept_log) of this turn or the one before (turn_index - 1: what reached it after the last wave of th… | as_engine/mind/temper.py | `as_engine/contracts/settings.py`, `as_engine/mind/temper.py` | `contract/p05_many_actors/test_temper.py` |
| TEMPER-04 | TEMPER-04 provoke(tx, holder_id, toward_id, kind, event_id, at, turn_index) -> Event: heat = min(20, heat(tx, holder, toward, at) + R.provocation_heat[kind]); TEMPER_CHANGE {holder_id, toward_id, kind, event_id, heat} (… | as_engine/mind/temper.py | `as_engine/contracts/settings.py`, `as_engine/mind/temper.py` | `contract/p05_many_actors/test_temper.py` |
| TEMPER-05 | TEMPER-05 take_in(tx, rng, holder_id, turn_index, at) -> Outburst / None (turn.pipeline stage 3b: every conscious perceiver of the wave, sorted, the PC included) provoke() for each provocation (TEMPER-03, in order, then… | as_engine/mind/temper.py | `as_engine/contracts/settings.py`, `as_engine/mind/temper.py`, `as_engine/turn/pipeline.py`, `as_engine/turn/select.py` | `contract/p07_slice/test_breaking_point.py` |
| TEMPER-06 | TEMPER-06 What an outburst does — turn.cognition applies it (its step 4). Like a reflex or the wet strain's compulsion it is code's act: it replaces what the actor would have decided this wave, it is built from a core a… | as_engine/mind/temper.py | `as_engine/mind/temper.py`, `as_engine/turn/cognition.py`, `as_engine/turn/select.py`, `as_content/packs/core/cascade/stress.yaml` | `contract/p07_slice/test_breaking_point.py` |
| TEMPER-07 | TEMPER-07 A breaking point leaves a grudge unless temper.grudge is 0: the first open 'grudge' loop of the holder naming T (by created_at, loop_id) deepens — mind.mind.strengthen_loop(tx, it, +1, the outburst) (max 3); w… | as_engine/mind/temper.py | `as_engine/mind/mind.py`, `as_engine/mind/temper.py`, `as_content/packs/core/cascade/stress.yaml` | `contract/p05_many_actors/test_temper.py` |
| TEMPER-08 | TEMPER-08 (H1) A person knows their own state: body_lines gains the strain line, each entity its PacketEntity.feeling, and a snap of outlet 'words' this wave sets SkullPacket.outburst — all as mind.temper TEMPER-08 word… | as_engine/mind/packet.py | `as_engine/mind/packet.py`, `as_engine/mind/temper.py` | `contract/p05_many_actors/test_temper_in_packet.py` |
| TEMPER-09 | TEMPER-09 (F1c, D-86) What people cannot stand to be near — the owner: smeared in the dead "I'm going to smell like hell, look like hell. And people aren't gonna want to be around me for very long till I shower"; and wa… | as_engine/mind/temper.py | `as_engine/mind/temper.py` | `contract/p05_many_actors/test_care.py`, `contract/p07_slice/test_narration_care.py` |

## TIME

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| TIME-01 | *World clock (P0). docs/as/07_RULES.md §Time. Rules TIME-01..05.* | as_engine/kernel/clock.py | `as_engine/kernel/clock.py`, `as_engine/kernel/store.py`, `as_engine/turn/pipeline.py` | `contract/p00_substrate/test_clock.py` |
| TIME-02 | *Reaction gate and waves (Stage 11, P5). Rules TIME-02, TIME-04, REACT-01..04.* | as_engine/action/reactions.py | `as_engine/action/reactions.py`, `as_engine/kernel/clock.py`, `as_engine/turn/pipeline.py` | `contract/p05_many_actors/test_reactions_cascade_plan.py`, `contract/p07_slice/test_p07_slice_metal_fence.py` |
| TIME-03 | *World clock (P0). docs/as/07_RULES.md §Time. Rules TIME-01..05.* | as_engine/kernel/clock.py | `as_engine/kernel/clock.py`, `as_engine/turn/pipeline.py` | — |
| TIME-04 | *Reaction gate and waves (Stage 11, P5). Rules TIME-02, TIME-04, REACT-01..04.* | as_engine/action/reactions.py | `as_engine/action/reactions.py`, `as_engine/kernel/clock.py`, `as_engine/turn/pipeline.py` | — |
| TIME-05 | *est_duration_s grows by words / 2.5 seconds (speech consumes real time, TIME-05) — the* | as_engine/action/intent.py | `as_engine/action/intent.py` | `contract/p04_one_actor/test_intent.py`, `contract/p05_many_actors/test_resolve.py` |
| TIME-06 | *``type_`` not in QUEUE_TYPES raises ValidationFailure(rule='TIME-06').* | as_engine/kernel/clock.py | `as_engine/kernel/clock.py`, `as_engine/turn/timers.py` | `contract/p00_substrate/test_clock.py`, `contract/p07_slice/test_p07_slice_metal_fence.py`, `contract/p09_society/test_timers_society.py` |
| TIME-07 | *Rules TIME-06..10, CAS-06.* | as_engine/turn/timers.py | `as_engine/turn/timers.py` | `contract/p09_society/test_timers_society.py` |
| TIME-08 | *Rules TIME-06..10, CAS-06.* | as_engine/turn/timers.py | `as_engine/turn/timers.py` | `contract/p09_society/test_timers_society.py` |
| TIME-09 | *Rules TIME-06..10, CAS-06.* | as_engine/turn/timers.py | `as_engine/turn/timers.py` | `contract/p09_society/test_timers_society.py` |
| TIME-10 | *run_offscreen(tx, rng, until_ms, turn_index) -> list[Event] (TIME-10, the off-screen step)* | as_engine/turn/timers.py | `as_engine/turn/timers.py` | — |
| TIME-11 | *seed_world(tx, at, turn_index) -> list[str] (P10, TIME-11)* | as_engine/turn/timers.py | `as_engine/turn/timers.py` | — |

## TRACE

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| TRACE-01 | TRACE-01 create(tx, place_id, kind, text, source_event_id, at, turn_index, *, locked=False, decay_days=None) -> str trace_id = tx.mint('trc'); days = decay_days, else W.trace_decay_days[kind] when the kind is listed the… | as_engine/world/traces.py | `as_engine/world/traces.py` | `contract/p10_world/test_traces.py`, `contract/p10_world/test_world_day.py` |
| TRACE-02 | TRACE-02 decay(tx, rng, row, fired, turn_index) -> list[Event] (the TRACE_DECAY handler) The trace named by the payload; gone already, or locked -> []. Else TRACE_DECAYED {trace_id, place_id, kind, reason: 'time'} (caus… | as_engine/world/traces.py | `as_engine/world/traces.py`, `as_engine/world/worldmove.py` | `contract/p10_world/test_traces.py`, `contract/p10_world/test_world_day.py` |
| TRACE-03 | *Diegetic traces (P10). Owner 'world.traces' (traces). Rules WORLD-03, TRACE-01..06.* | as_engine/world/traces.py | `as_engine/world/traces.py` | `contract/p10_world/test_world_day.py` |
| TRACE-04 | TRACE-04 traces_in(store, place_id) -> list[dict]: the place's traces, ordered (created_at, trace_id), as row dicts. | as_engine/world/traces.py | `as_engine/world/traces.py` | `contract/p10_world/test_traces.py`, `contract/p10_world/test_world_day.py` |
| TRACE-05 | TRACE-05 What people perceive: mind.perception.compile_scene gives a holder in a place with light above 'dark' one visual percept per trace there (text = the trace text, source_id = the trace id) — the narrator and the… | as_engine/world/traces.py | `as_engine/mind/perception.py`, `as_engine/world/traces.py` | `contract/p10_world/test_traces.py`, `contract/p10_world/test_world_day.py` |
| TRACE-06 | TRACE-06 washout(tx, at, turn_index, cause_event_id) -> list[Event] (world.worldmove.day step 1, after the day's weather) Only when world.decay.wet(tx): every trace (by trace_id) that is not locked, whose kind is in W.w… | as_engine/world/traces.py | `as_engine/world/traces.py`, `as_engine/world/worldmove.py` | `contract/p10_world/test_world_day.py` |

## UI-CLARITY

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| UI-CLARITY-01 | No engine vocabulary on any play screen: `packet, affordance, percept, LOD, claim, intent, handle, lane, schema, token, stage, event, actor, dossier` (whole words, any case, plural too). Exceptions: the Developer panel,… | 10_UI §1 | `as_engine/contracts/view.py`, `as_engine/service/progress.py`, `as_engine/service/view.py`, `as_engine/turn/pipeline.py` | `contract/p07_slice/test_location_view.py`, `contract/p10_world/test_progress.py` |
| UI-CLARITY-02 | No internal ids on screen (regex `\b(act | 10_UI §1 | — | `contract/p08_ui_protocol/test_protocol.py`, `contract/p08_ui_protocol/test_ui_fixtures.py` |
| UI-CLARITY-03 | Every control has words: its text, or an `aria-label` (an icon-only button has an aria-label; a tooltip may repeat it) | 10_UI §1 | — | — |
| UI-CLARITY-04 | Status is never colour-only (every coloured state also has a word) | 10_UI §1 | — | — |
| UI-CLARITY-05 | Every panel title is a plain noun phrase: *Where you are · Your pack · Your body · People · Journal · Map* | 10_UI §1 | — | — |
| UI-CLARITY-06 | Every error message says what happened and what you can do ("Your laptop brain isn't answering. The game will keep going on the desktop only — turns will be thinner.") | 10_UI §1 | `as_engine/service/game_service.py` | `contract/p08_ui_protocol/test_models_config.py`, `contract/p08_ui_protocol/test_packs_content.py`, `contract/p08_ui_protocol/test_protocol.py` |

## UI-LOC

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| UI-LOC-01 | *Code-rendered location description (P7). Rules UI-LOC-01, UI-SKULL-01, UI-REF-01, GEO-01.* | as_engine/narration/location.py | `as_engine/narration/location.py` | `contract/p07_slice/test_location_view.py` |

## UI-REF

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| UI-REF-01 | *Code-rendered location description (P7). Rules UI-LOC-01, UI-SKULL-01, UI-REF-01, GEO-01.* | as_engine/narration/location.py | `as_engine/narration/location.py`, `as_engine/service/session.py`, `as_engine/service/view.py` | `contract/p07_slice/test_location_view.py` |

## UI-SKULL

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| UI-SKULL-01 | The UI shows only what the player character knows | 10_UI §1 | `as_engine/contracts/view.py`, `as_engine/narration/location.py`, `as_engine/service/guide.py`, `as_engine/service/view.py` | `contract/p07_slice/test_location_view.py`, `contract/p08_ui_protocol/test_guide.py`, `contract/p08_ui_protocol/test_protocol.py` |

## UI-SUG

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| UI-SUG-01 | *PlayView builder (P7). Rules UI-SKULL-01, UI-CLARITY-01, UI-REF-01, UI-SUG-01, UI-SUG-02.* | as_engine/service/view.py | `as_engine/service/view.py` | `contract/p07_slice/test_location_view.py` |
| UI-SUG-02 | *PlayView builder (P7). Rules UI-SKULL-01, UI-CLARITY-01, UI-REF-01, UI-SUG-01, UI-SUG-02.* | as_engine/service/view.py | `as_engine/service/view.py` | `contract/p07_slice/test_location_view.py` |

## VIS

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| VIS-01 | *Visual observation (P3). Rules VIS-01..05. Separate from audibility (plan §7.3).* | as_engine/sense/optics.py | `as_engine/sense/optics.py` | `contract/p03_perception/test_optics.py` |
| VIS-02 | *Visual observation (P3). Rules VIS-01..05. Separate from audibility (plan §7.3).* | as_engine/sense/optics.py | `as_engine/sense/optics.py` | `contract/p03_perception/test_optics.py` |
| VIS-03 | *visual percept at clear: what shows what a hand holds, sense.optics VIS-03)* | as_engine/mind/affordance.py | `as_engine/mind/affordance.py`, `as_engine/mind/cues.py`, `as_engine/sense/optics.py` | `contract/p03_perception/test_optics.py`, `contract/p04_one_actor/test_knowledge_menus.py` |
| VIS-04 | *Visual observation (P3). Rules VIS-01..05. Separate from audibility (plan §7.3).* | as_engine/sense/optics.py | `as_engine/sense/optics.py` | `contract/p03_perception/test_optics.py` |

## WEAR

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| WEAR-01 | WEAR-01 exposed(store, place_id) -> bool: places.indoor is 0 — a street, a road, an outdoor place, a building site's outside. An indoor place (a room, a building's inside) shelters what is in it. An unknown place -> Val… | as_engine/world/decay.py | `as_engine/contracts/settings.py`, `as_engine/world/decay.py` | `contract/p10_world/test_world_day.py` |
| WEAR-02 | WEAR-02 wet(store) -> bool: world_clock.weather is 'rain', 'storm' or 'snow'. | as_engine/world/decay.py | `as_engine/contracts/settings.py`, `as_engine/world/decay.py` | `contract/p10_world/test_world_day.py` |
| WEAR-03 | WEAR-03 day(tx, rng, at, turn_index, cause_event_id) -> list[Event] (world.worldmove.day calls it once the day's weather is set; ``rng`` is not drawn) 1 Weather, only when wet(tx): per item (by item_id) lying loose (ite… | as_engine/world/decay.py | `as_engine/contracts/settings.py`, `as_engine/world/decay.py` | `contract/p10_world/test_world_day.py` |
| WEAR-04 | WEAR-04 made_at: physical.objects.create (P10 amendment) gives a food item whose def has food.spoil_days props.made_at = at, unless the props it was given already carry made_at (loot, production and cheats create throug… | as_engine/world/decay.py | `as_engine/physical/objects.py`, `as_engine/world/decay.py` | — |

## WG

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| WG-01 | *Parameter generation WG0 (P10). Rules WG-01..09 (CMG §61 Parts III-VIII carried).* | as_engine/world/worldgen/params.py | `as_engine/world/worldgen/params.py` | `contract/p10_world/test_params.py` |
| WG-02 | *Parameter generation WG0 (P10). Rules WG-01..09 (CMG §61 Parts III-VIII carried).* | as_engine/world/worldgen/params.py | `as_engine/world/worldgen/params.py` | `contract/p10_world/test_params.py` |
| WG-03 | *Parameter generation WG0 (P10). Rules WG-01..09 (CMG §61 Parts III-VIII carried).* | as_engine/world/worldgen/params.py | `as_engine/world/worldgen/params.py` | `contract/p10_world/test_params.py` |
| WG-04 | *Parameter generation WG0 (P10). Rules WG-01..09 (CMG §61 Parts III-VIII carried).* | as_engine/world/worldgen/params.py | `as_engine/world/worldgen/params.py` | `contract/p10_world/test_params.py` |
| WG-05 | *Parameter generation WG0 (P10). Rules WG-01..09 (CMG §61 Parts III-VIII carried).* | as_engine/world/worldgen/params.py | `as_engine/world/worldgen/params.py` | `contract/p10_world/test_params.py` |
| WG-06 | *Parameter generation WG0 (P10). Rules WG-01..09 (CMG §61 Parts III-VIII carried).* | as_engine/world/worldgen/params.py | `as_engine/world/worldgen/params.py` | `contract/p10_world/test_params.py` |
| WG-07 | *Parameter generation WG0 (P10). Rules WG-01..09 (CMG §61 Parts III-VIII carried).* | as_engine/world/worldgen/params.py | `as_engine/world/worldgen/params.py` | `contract/p10_world/test_params.py` |
| WG-08 | *Parameter generation WG0 (P10). Rules WG-01..09 (CMG §61 Parts III-VIII carried).* | as_engine/world/worldgen/params.py | `as_engine/world/worldgen/params.py` | `contract/p10_world/test_params.py` |
| WG-10 | WG-10 eligible_factions(canon, values) -> list[tuple[str, FactionDossier]] (ref, record) for every canon faction record whose kind is 'faction', that has no behaviour.enclave, and whose presence.presence_conditions ALL… | as_engine/world/worldgen/placement.py | `as_engine/world/worldgen/pipeline.py`, `as_engine/world/worldgen/placement.py` | `contract/p10_world/test_ghosts.py`, `contract/p10_world/test_placement.py`, `contract/p10_world/test_worldgen_pipeline.py` |
| WG-11 | WG-11 place(rng, tx, values, pc, canon) -> Placement (Part X steps 1-4) t = pc.faction_start_type; E = eligible_factions(canon, values); density = values['faction_density']; pref = pc.start_constraints.faction_present_p… | as_engine/world/worldgen/placement.py | `as_engine/world/worldgen/pipeline.py`, `as_engine/world/worldgen/placement.py` | `contract/p10_world/test_placement.py`, `contract/p10_world/test_worldgen_pipeline.py` |
| WG-12 | WG-12 descriptor(rng, tx, hostile) -> str (Part X step 3: [dynamic] + [location type] + [rule]) Three rng.choice draws on 'worldgen:placement' (purposes 'dynamic', 'location', 'rule') from atlas.GROUP_DYNAMICS / GROUP_L… | as_engine/world/worldgen/placement.py | `as_engine/world/worldgen/pipeline.py`, `as_engine/world/worldgen/placement.py` | `contract/p10_world/test_placement.py`, `contract/p10_world/test_worldgen_pipeline.py` |
| WG-13 | WG-13 plausibility(values, placement, pc) -> 'pass' / 'fail' / 'hard_fail' (QC-2, sub-question 1) v = values + {'entity_type': placement.entity_type, 'start_trust': placement.start_trust or 0}. 'hard_fail' when pc.plaus… | as_engine/world/worldgen/placement.py | `as_engine/world/worldgen/pipeline.py`, `as_engine/world/worldgen/placement.py` | `contract/p10_world/test_placement.py`, `contract/p10_world/test_worldgen_pipeline.py` |
| WG-14 | WG-14 qc(rng, tx, params, placement, pc, canon, difficulty) -> QCResult (Part XII + hard-fail protocol) QCResult(params, placement, result 'pass' / 'patched' / 'aborted', patches: list[str]). patches starts with generat… | as_engine/world/worldgen/placement.py | `as_engine/world/worldgen/pipeline.py`, `as_engine/world/worldgen/placement.py` | `contract/p10_world/test_worldgen_pipeline.py` |
| WG-15 | WG-15 assert_region(store, region) -> None (raises WorldgenAssertion(stage 'WG1', ...)) Checks what was WRITTEN (the store), not the Region it was handed: every place of the region (hubs, sites, roads) is reachable from… | as_engine/world/worldgen/region.py | `as_engine/world/worldgen/pipeline.py`, `as_engine/world/worldgen/region.py` | `contract/p10_world/test_region.py`, `contract/p10_world/test_worldgen_pipeline.py` |
| WG-16 | WG-16 Every building site has layout_generated 0 and an archetype_ref; no room exists yet. | as_engine/world/worldgen/region.py | `as_engine/world/worldgen/pipeline.py`, `as_engine/world/worldgen/region.py` | `contract/p10_world/test_region.py`, `contract/p10_world/test_worldgen_pipeline.py` |
| WG-17 | *Gated worldgen pipeline (P10). docs/as/06_WORLD.md §1. Rules WG-10..37, WG-DET-01, RUN-09.* | as_engine/world/worldgen/pipeline.py | `as_engine/world/worldgen/pipeline.py`, `as_engine/world/worldgen/region.py` | `contract/p10_world/test_region.py`, `contract/p10_world/test_worldgen_pipeline.py` |
| WG-18 | WG-18 plan_polity(rng, tx, params, placement, region, canon) -> PolityPlan Ids are minted here (groups 'grp', settlements 'stl') so history can name them before WG3/WG4 write their rows. 1 Factions: E = placement.eligib… | as_engine/world/worldgen/history.py | `as_engine/world/factions.py`, `as_engine/world/worldgen/history.py`, `as_engine/world/worldgen/pipeline.py`, `as_engine/world/worldgen/placement.py` | `contract/p10_world/test_ghosts.py`, `contract/p10_world/test_worldgen_pipeline.py` |
| WG-19 | WG-19 skeleton(rng, tx, params, plan, region, tier) -> list[PlannedEvent] PlannedEvent(key, day, kind, subject_ids, cause_key, text). Mandatory events, in this order: the Fall: 'disaster', day 0, subjects [start zone id… | as_engine/world/worldgen/history.py | `as_engine/world/worldgen/history.py`, `as_engine/world/worldgen/pipeline.py` | `contract/p10_world/test_worldgen_pipeline.py` |
| WG-20 | WG-20 async write_history(client, tx, events, plan, region, params, at, progress=None) -> list[str] (P10: await progress(done, total) after each batch's answer — or failure — in batch order.) hist ids (kind 'his') minte… | as_engine/world/worldgen/history.py | `as_engine/world/worldgen/history.py`, `as_engine/world/worldgen/pipeline.py` | `contract/p10_world/test_worldgen_pipeline.py` |
| WG-21 | WG-21 mark_held(tx, plan, at) -> list[Event] (WG-32): every settlement site that is a building gets places.held = 1 — one PLACE_CHANGE {place_id, changes: {held: 1}, reason: 'history'} (writer 'physical.space') per site… | as_engine/world/worldgen/history.py | `as_engine/world/worldgen/history.py`, `as_engine/world/worldgen/pipeline.py` | `contract/p10_world/test_worldgen_pipeline.py` |
| WG-22 | WG-22 write_groups(tx, plan, params, canon, at) -> list[Event] (WG3) Per planned group (plan order) a MATERIALIZE (writer 'society.group') inserting groups {group_id, kind, name, content_ref, descriptor, presence, doctr… | as_engine/world/worldgen/polity.py | `as_engine/world/worldgen/pipeline.py`, `as_engine/world/worldgen/polity.py` | `contract/p10_world/test_worldgen_pipeline.py` |
| WG-23 | WG-23 write_settlements(rng, tx, plan, params, region, at) -> list[Event] (WG4) Per planned settlement s (plan order), P = s.population: stores: water = round(3 x P x (3 + water)), food = round(2 x P x (3 + food)) (days… | as_engine/world/worldgen/polity.py | `as_engine/world/factions.py`, `as_engine/world/worldgen/pipeline.py`, `as_engine/world/worldgen/polity.py` | `contract/p10_world/test_worldgen_pipeline.py` |
| WG-24 | WG-24 write_cohorts(rng, tx, plan, params, at) -> list[Event] (WG5, DEMO-01/02) Per planned settlement (plan order), P = its population; shares young 0.20, youth 0.14, elders 0.11, each + rng.range_int(-3, 3, purpose f"… | as_engine/world/worldgen/polity.py | `as_engine/world/worldgen/pipeline.py`, `as_engine/world/worldgen/polity.py`, `as_engine/world/worldmove.py` | `contract/p10_world/test_worldgen_pipeline.py` |
| WG-25 | WG-25 write_laws(tx, plan, params, canon, at) -> list[Event] (WG7) Per settlement one MATERIALIZE (writer 'society.settlement', payload {settlement_id, laws: n}) inserting laws_active {settlement_id, law_ref, since = at… | as_engine/world/worldgen/polity.py | `as_engine/world/worldgen/pipeline.py`, `as_engine/world/worldgen/polity.py` | `contract/p10_world/test_worldgen_pipeline.py` |
| WG-26 | WG-26 Pack actors. The canon actor records (not PCs), by ref. Skipped, and listed in the worldgen report with the reason, when: days_since_fall_range excludes dsf ("needs a world <a>-<b> years after the Fall", WG-34); o… | as_engine/world/worldgen/people.py | `as_engine/world/worldgen/people.py`, `as_engine/world/worldgen/pipeline.py` | `contract/p10_world/test_worldgen_pipeline.py` |
| WG-27 | WG-27 Posts and people. generated = max(T['detailed_actors'] - placed pack actors, the home posts below + the leaders slot 2 needs) — the home's work and every settlement's leader always have someone. Slots are filled i… | as_engine/world/worldgen/people.py | `as_engine/world/factions.py`, `as_engine/world/worldgen/people.py`, `as_engine/world/worldgen/pipeline.py`, `as_content/packs/core/factions/ghosts.yaml` | `contract/p10_world/test_ghosts.py`, `contract/p10_world/test_worldgen_pipeline.py` |
| WG-28 | WG-28 Writing (per person, slot order; pack actors first in placement order): the body, needs, a position at the settlement site's anchor, the dossier (source 'pack' with its content ref, or 'generated') and the actor (… | as_engine/world/worldgen/people.py | `as_engine/world/factions.py`, `as_engine/world/worldgen/people.py`, `as_engine/world/worldgen/pipeline.py` | `contract/p10_world/test_worldgen_pipeline.py` |
| WG-29 | WG-29 Ties and knowledge (SOC-01), per settlement: every named person gets acquaintance of every other named person there (known_name = display name, description = mind.perception. describe_dossier) and known_places for… | as_engine/world/worldgen/people.py | `as_engine/world/worldgen/people.py`, `as_engine/world/worldgen/pipeline.py` | `contract/p10_world/test_materialise.py`, `contract/p10_world/test_worldgen_pipeline.py` |
| WG-30 | *the player is never decided here or anywhere in worldgen (WG-30).* | as_engine/world/worldgen/checks.py | `as_engine/world/worldgen/checks.py`, `as_engine/world/worldgen/opening.py`, `as_engine/world/worldgen/pipeline.py` | `contract/p10_world/test_worldgen_pipeline.py` |
| WG-31 | *them (P10). Rules WG-18..21, WORLD-01, WG-31, WG-32. docs/as/06_WORLD.md §1.3.* | as_engine/world/worldgen/history.py | `as_engine/world/worldgen/history.py`, `as_engine/world/worldgen/pipeline.py` | `contract/p10_world/test_worldgen_pipeline.py` |
| WG-32 | *3 Loot (GEO-04 / WG-32): per room with a loot_table, in room order, stream f"loot:{place_id}:{room* | as_engine/physical/space.py | `as_engine/physical/space.py`, `as_engine/world/worldgen/history.py`, `as_engine/world/worldgen/pipeline.py` | `contract/p10_world/test_worldgen_pipeline.py` |
| WG-33 | *them right now, what they have heard, and what they remember (P10). Rules WG-30, WG-33, QC-4, QC-5.* | as_engine/world/worldgen/opening.py | `as_engine/world/worldgen/opening.py`, `as_engine/world/worldgen/pipeline.py` | `contract/p10_world/test_worldgen_pipeline.py` |
| WG-34 | *A run setting, or a combination of settings, the world cannot honour (P10: WG-34).* | as_engine/kernel/errors.py | `as_engine/kernel/errors.py`, `as_engine/service/game_service.py`, `as_engine/testing/scenario.py`, `as_engine/world/worldgen/params.py`, `as_engine/world/worldgen/people.py`, `as_engine/world/worldgen/pipeline.py`, `as_content/templates/actor_template.yaml` | `contract/p10_world/test_params.py`, `contract/p10_world/test_worldgen_pipeline.py` |
| WG-35 | WG-35 assert_world(store, region, plan, opening) -> list[str] (plain sentences; [] = it holds) 1 "Fewer than three places worth the risk." unless len(opening.magnets) >= 3 and the PC holds a live, believed 'lead' propos… | as_engine/world/worldgen/checks.py | `as_engine/world/worldgen/checks.py`, `as_engine/world/worldgen/pipeline.py`, `as_engine/world/worldgen/region.py` | `contract/p10_world/test_region.py`, `contract/p10_world/test_worldgen_pipeline.py` |
| WG-36 | WG-36 The seven world checks name nothing from the story: which people will betray, die or befriend the player is never decided here or anywhere in worldgen (WG-30). | as_engine/world/worldgen/checks.py | `as_engine/world/worldgen/checks.py`, `as_engine/world/worldgen/pipeline.py` | `contract/p10_world/test_worldgen_pipeline.py` |
| WG-37 | WG-37 The continuous re-assertion of these invariants every in-game day is not built in v1 (P11's release audit re-runs assert_world on the genesis snapshot instead; DECISIONS D-45). | as_engine/world/worldgen/checks.py | `as_engine/world/worldgen/checks.py` | — |

## WG-DET

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| WG-DET-01 | *exactly once even if the value is later patched (determinism, WG-DET-01).* | as_engine/world/worldgen/params.py | `as_engine/world/worldgen/params.py`, `as_engine/world/worldgen/pipeline.py` | `contract/p10_world/test_params.py`, `contract/p10_world/test_region.py`, `contract/p10_world/test_worldgen_pipeline.py` |

## WILL

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| WILL-00 | *Firewall rule WILL-00: requests reach a mind ONLY as this record, labelled with the form and* | as_engine/contracts/mind.py | `as_engine/contracts/mind.py`, `as_engine/mind/firewall.py`, `as_engine/mind/packet.py` | `contract/p04_one_actor/test_firewall.py`, `contract/p04_one_actor/test_packet.py` |
| WILL-01 | *The Request Firewall (P4). Rules WILL-00..11, L6, L7. docs/as/05_ACTORS.md §Firewall.* | as_engine/mind/firewall.py | `as_engine/mind/firewall.py` | `contract/p04_one_actor/test_firewall.py` |
| WILL-02 | *The Request Firewall (P4). Rules WILL-00..11, L6, L7. docs/as/05_ACTORS.md §Firewall.* | as_engine/mind/firewall.py | `as_engine/mind/firewall.py` | `contract/p04_one_actor/test_firewall.py` |
| WILL-03 | WILL-03: two Actors differing only in skills[] and Resolve (tests/fixtures/scenarios/two_skills.yaml) | as_engine/mind/affordance.py | `as_engine/mind/affordance.py`, `as_engine/mind/firewall.py` | `contract/p04_one_actor/test_affordances.py`, `contract/p04_one_actor/test_firewall.py` |
| WILL-04 | *The Request Firewall (P4). Rules WILL-00..11, L6, L7. docs/as/05_ACTORS.md §Firewall.* | as_engine/mind/firewall.py | `as_engine/mind/firewall.py`, `as_engine/turn/cognition.py` | `contract/p04_one_actor/test_firewall.py`, `contract/p07_slice/test_slice_refusal.py` |
| WILL-05 | WILL-05 negotiable_target_penalty(times_asked) = -(times_asked - 1) for times_asked >= 1 (else ValueError): asking again is never better. action.effects.situation applies it to the check of a 'negotiable' def (calm_pers… | as_engine/mind/firewall.py | `as_engine/action/effects.py`, `as_engine/mind/firewall.py`, `as_engine/mind/retrieval.py`, `as_engine/turn/cognition.py` | `contract/p04_one_actor/test_firewall.py`, `contract/p06_memory/test_refusals.py`, `contract/p06_memory/test_retrieval.py`, `contract/p07_slice/test_slice_refusal.py` |
| WILL-06 | WILL-06 Asking has consequences even when refused: a NEW refusal with entrenched = true (the ask needed something the moral gate removes — one of the refuser's own immutable lines, such as abandoning a dependent, leavin… | as_engine/mind/firewall.py | `as_engine/mind/firewall.py`, `as_engine/turn/cognition.py` | `contract/p04_one_actor/test_firewall.py`, `contract/p06_memory/test_refusals.py`, `contract/p07_slice/test_slice_refusal.py` |
| WILL-07 | WILL-07 record_refusal(tx, actor_id, requester_id, signature, summary, reason_code, reason_event_ids, cost_cited, entrenched, at, turn_index, cause_event_id) -> refusal_id reason_code must be one of REASON_CODES, else V… | as_engine/mind/firewall.py | `as_engine/mind/firewall.py`, `as_engine/turn/cognition.py` | `contract/p04_one_actor/test_firewall.py`, `contract/p06_memory/test_refusals.py`, `contract/p07_slice/test_slice_refusal.py` |
| WILL-08 | *The Request Firewall (P4). Rules WILL-00..11, L6, L7. docs/as/05_ACTORS.md §Firewall.* | as_engine/mind/firewall.py | `as_engine/mind/firewall.py`, `as_engine/turn/cognition.py` | `contract/p04_one_actor/test_firewall.py`, `contract/p07_slice/test_slice_refusal.py` |
| WILL-09 | *The Request Firewall (P4). Rules WILL-00..11, L6, L7. docs/as/05_ACTORS.md §Firewall.* | as_engine/mind/firewall.py | `as_engine/mind/firewall.py`, `as_engine/turn/cognition.py` | `contract/p04_one_actor/test_firewall.py` |
| WILL-10 | *The Request Firewall (P4). Rules WILL-00..11, L6, L7. docs/as/05_ACTORS.md §Firewall.* | as_engine/mind/firewall.py | `as_engine/mind/firewall.py`, `as_engine/mind/perception.py`, `as_engine/turn/cognition.py` | `contract/p04_one_actor/test_firewall.py` |
| WILL-11 | WILL-11 record_lie(tx, liar_id, to_id, signature, words, speech_event_id, at, turn_index) -> Event A FALSE_COMPLIANCE response (says yes, does something else) is a lie: LIE_TOLD {liar_id, to_id, signature, words} (write… | as_engine/mind/firewall.py | `as_engine/mind/firewall.py` | `contract/p06_memory/test_refusals.py` |

## WORK

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| WORK-01 | WORK-01 qualified(store, actor_id, role) -> bool R.role_skill[role] = (domain, rank): the fused dossier's (mind.actor.fused) skill rank in that domain >= rank. A role not in R.role_skill -> True. A body without an actor… | as_engine/society/work.py | `as_engine/society/work.py` | `contract/p09_society/test_work.py` |
| WORK-02 | WORK-02 able(store, actor_id, role) -> tuple[bool, str] (False, reason) for the first that applies: the body is dead ('dead'); awareness 'unconscious' ('unconscious'); bodies.restrained = 1 ('held'); the role is in R.ma… | as_engine/society/work.py | `as_engine/society/work.py` | `contract/p09_society/test_work.py` |
| WORK-03 | WORK-03 overlap_h(shift_start_hh, shift_end_hh, start_ms, end_ms) -> float Hours shared by the interval (start_ms, end_ms] and the daily shift [shift_start_hh, shift_end_hh) — every daily occurrence of it, including the… | as_engine/society/work.py | `as_engine/society/work.py` | `contract/p09_society/test_work.py` |
| WORK-04 | WORK-04 crew(store, workplace_id, start_ms, end_ms) -> list[tuple[str, str]] (actor_id, role) of every work_assignments row of the workplace with overlap_h > 0 whose actor is able (WORK-02) and qualified (WORK-01) for t… | as_engine/society/work.py | `as_engine/society/work.py` | `contract/p09_society/test_work.py` |
| WORK-05 | WORK-05 cycle(tx, rng, row, fired, turn_index) -> list[Event] (the PRODUCTION_CYCLE handler) w = the workplace row['subject_id'], at = row['due_at'], start = at - cycle_h * H. 1 crew = crew(w, start, at); staffed = staf… | as_engine/society/work.py | `as_engine/society/work.py` | `contract/p09_society/test_econ_chain.py`, `contract/p09_society/test_work.py` |
| WORK-06 | WORK-06 miss_shift(tx, key, reason, at, turn_index, cause_event_id) -> Event / None (cascade dispatch of SHIFT_MISSED — core CAS-001 schedules it for an arm injury, CAS-007 at a death.) No such row -> None. The worker a… | as_engine/society/work.py | `as_engine/action/cascade.py`, `as_engine/society/work.py` | `contract/p09_society/test_econ_chain.py`, `contract/p09_society/test_work.py` |
| WORK-07 | WORK-07 pick_cover(store, workplace_id, role, shift_start_hh, shift_end_hh, exclude) -> str / None Candidates: named members of the workplace's settlement (society.population.census) other than ``exclude``, whose actors… | as_engine/society/work.py | `as_engine/society/work.py` | `contract/p09_society/test_econ_chain.py`, `contract/p09_society/test_work.py` |
| WORK-08 | WORK-08 assign_cover(tx, actor_id, workplace_id, role, shift_start_hh, shift_end_hh, covering_for, at, turn_index, cause_event_id) -> Event (cascade dispatch of ROLE_ASSIGNED — core CAS-002, whose payload carries the mi… | as_engine/society/work.py | `as_engine/society/work.py` | `contract/p09_society/test_econ_chain.py`, `contract/p09_society/test_work.py` |
| WORK-09 | WORK-09 efficiency recovery (end of cycle): when efficiency < 1.0 and no worker with an own row (covering_for NULL) at this workplace has a covering row anywhere: WORKPLACE_CHANGE {workplace_id, field: 'efficiency', old… | as_engine/society/work.py | `as_engine/society/work.py` | `contract/p09_society/test_work.py` |
| WORK-10 | WORK-10 adjust(tx, workplace_id, field, amount, at, turn_index, cause_event_id) -> Event / None (the cascade 'adjust' dispatch for a workplace id.) field 'efficiency': new = clamp(round(old + amount, 2), 0.0, 1.5); fiel… | as_engine/society/work.py | `as_engine/society/work.py` | `contract/p09_society/test_work.py` |
| WORK-11 | WORK-11 shift_start(tx, actor_id, workplace_id, role, at, turn_index, cause_event_id) -> Event / None (society.routine calls it at a work step.) The actor able for the role -> SHIFT_START {workplace_id, role, actor_id}… | as_engine/society/work.py | `as_engine/society/work.py` | `contract/p09_society/test_work.py` |
| WORK-12 | WORK-12 ensure_timers(tx, settlement_id, at, turn_index) -> list[str] For each workplace of the settlement (by workplace_id) with a non-NULL next_due_at and no pending PRODUCTION_CYCLE row: kernel.clock.schedule(tx, max… | as_engine/society/work.py | `as_engine/society/work.py` | — |

## WORLD

| Id | Statement | Stated in | Enforced in | Tested by |
|---|---|---|---|---|
| WORLD-01 | WORLD-01: every settlement and every placed group is a subject of at least one history event. | as_engine/world/worldgen/history.py | `as_engine/world/worldgen/checks.py`, `as_engine/world/worldgen/history.py` | — |
| WORLD-02 | WORLD-02 Nothing here ticks by itself: WORLD_DAY (daily at W.world_hour) and OPERATION_STEP rows are event_queue rows (background types, kernel.clock) that turn.timers.seed_world starts and turn.timers fires, in a turn'… | as_engine/world/worldmove.py | `as_engine/world/worldmove.py` | `contract/p10_world/test_world_day.py` |
| WORLD-03 | *Diegetic traces (P10). Owner 'world.traces' (traces). Rules WORLD-03, TRACE-01..06.* | as_engine/world/traces.py | `as_engine/world/traces.py`, `as_engine/world/worldmove.py`, `as_content/packs/core/cascade/people.yaml` | `contract/p10_world/test_world_day.py` |
| WORLD-04 | WORLD-04 The active area: off-screen code never kills, moves or sends away a body that stands in turn.select.active_area(tx, meta.pc_actor_id, turn_index) — what the player could see happen is simulated by the turn, not… | as_engine/world/worldmove.py | `as_engine/world/worldmove.py` | `contract/p10_world/test_ghosts.py`, `contract/p10_world/test_world_day.py` |
| WORLD-05 | WORLD-05 Named characters are not protected during play: an off-screen death can take anyone the player is not with. | as_engine/world/worldmove.py | `as_engine/world/worldmove.py` | `contract/p10_world/test_world_day.py` |
| WORLD-06 | WORLD-06 The narrator never writes 'while you were gone' (narration lint); the world shows it. | as_engine/world/worldmove.py | `as_engine/world/worldmove.py` | — |
