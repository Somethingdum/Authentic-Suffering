# GLOSSARY

One spelling per concept. Code, docs, prompts, content and tests use the **Canonical** column.
The **Player sees** column is what the Play UI says (UI-CLARITY-01 bans engine words on play
screens). **Retired** spellings are tombstones: old documents stay readable, new work never uses
them (CNT-08 warns on them in content; "sotry" is an error).

## Engine terms

| Canonical | Meaning | Player sees | Retired spellings |
|---|---|---|---|
| Actor | any body processed with a mind (the PC included) | a person / their name | NPC, character (for minds), entity, agent |
| PC | the Actor whose intent comes from a human | "you" / the character's name | player character (in code: never branch on it) |
| body | the physical record of any creature | — | — |
| dossier | the full record of who a person is (never trimmed) | "character sheet" (Content screen only: "dossier", "affordance", "actor" allowed there, 10 §1) | profile, character card (for the record) |
| Skull Packet | everything one mind receives for one decision | — | actor packet, perception packet, context bundle |
| affordance | one thing a body could attempt now, computed by code | "option" / a suggestion | action menu item |
| intent | what a mind attempts (never an outcome) | "what you do" | action (as a record), move |
| percept | one thing that reached one mind, with fidelity | "you heard / saw / felt" | — |
| fidelity | exact / partial / tone only / visual only | "clearly", "partly", "only the tone" | — |
| claim | a truth-layer fact | — | canonical fact |
| proposition | something said or inferred that is not a truth fact | — | — |
| holding | a belief: holder × claim/proposition with confidence and provenance | "what you know / think" | — |
| provenance | where a belief came from (witnessed, told_by:X …) | "how you know" | source tag |
| event | one committed change with a cause | — | log entry, delta |
| event log | the append-only `events` table | — | EVENT_STREAM, EVENT_HISTORY, RECENT EVENTS |
| store | the run's SQLite database | "your save" | MEMORY_LOG, save file, world state, the logs |
| run | one life in one world | "a life" / run card | campaign (in code) |
| world | the generated place, its people and history | "world" | — |
| genesis | the saved state of a world before any PC was placed | "the world as it began" | BaselineWorldFile (the ruling's name) |
| turn-0 snapshot | a run's `turn0.sqlite`: the run as it stood before its first turn (PC placed), kept so the run can be re-simulated (DET-02) — not a genesis | — | — |
| active area | the places a turn simulates in full: the PC's place, 2 portal hops, and the neighbourhood of any loud noise this turn | — | — |
| guide | the model that answers Ask-mode questions from what the character knows plus plain rules text (`service/guide.py`); never a turn | "Guide" | hint system, helper |
| push | a protocol message the service sends without being asked (turn progress, the turn's result, the story) to every connected page | — | broadcast, event (for messages) |
| busy | a turn is running; the service refuses anything that would read or change the run, except the view and the story from before the turn | "Your last move is still being worked out." | locked |
| lane | one model on one machine (A = desktop, B = laptop) | "Storyteller brain", "Fast brain" | box, slot |
| call class | the kind of model call (intake, narration …) | — | stage call |
| LOD | reasoning tier: HOT (deep, thinking), WARM (fast), COLD (code continues the plan) | — | level of detail (as a competence level — never) |
| turn | one transaction from player input to committed world + prose | "a turn" | tick |
| horizon | the world time a turn simulates to | — | — |
| wave | one round of simultaneous decisions inside a turn | "reactions" | — |
| barrier | the point where all intents are validated before anything changes | — | — |
| commit gate | the 58 computed checks before commit | — | Turn-5 bitfields (the S/U name; bit names kept) |
| Resolve | nerve: gates options, never modifies a roll | "Resolve" / "nerve" | RES_STATE, rs |
| check | the one universal d10 roll | "roll" (dice receipt) | — |
| margin | target − draw | — | — |
| band | clean / cost / fail / break | "success", "success with a cost", "failure", "failure with a new problem" | — |
| trace | diegetic evidence the world leaves | what you notice ("blood on the step") | — |
| cascade rule | declarative secondary consequence with a CAS id | — | — |
| cohort | unnamed people counted by band | — | — |
| settlement | a place where a community lives and works | the settlement's name | — |
| group | a faction or a procedural local group | its name | — |
| faction | canonical, authored mega-group (kind 'faction') | its name | — |
| rumour | a proposition passing hop by hop | "what people say" | — |
| household | people who live together; `guardian_of` says who looks after whom | the people ("Hal's family") | — |
| routine | a person's derived day: work, sleep, free time (COLD people follow it) | — | schedule (for this) |
| workplace | a place that produces something in cycles, with required roles and shifts | its name ("the pump") | — |
| cover | a worker moved to stand in for a missed shift (`covering_for`) | "covering for Hal" | — |
| vacancy | a post nobody holds or covers | — | — |
| ration level | 0–4, the share of the daily need handed out (3 = normal) | "rations" | — |
| shortage | a store under 3 days of need, declared by content | "running out of water" | — |
| tension | directional friction 0–100 of an actor or group toward another | — | — |
| standing | what a group as a whole thinks of a person (−5..5) | "they think well / little of you" | reputation (as a number) |
| defection pressure | the plain sum of reasons to leave a group | — | loyalty score, betrayal threshold |
| background timer | a queue row of `BACKGROUND_QUEUE_TYPES`: fires in a window but never ends a wait | — | — |
| off-screen step | `turn.timers.run_offscreen`: time passing in 6-hour windows without a played turn | — | society tick |
| open loop | promise, debt, grudge, goal, desire, fear, question, plan, kept secret | Journal entries | objective (for all of these) |
| lesson | a belief about what works, from experience | "lessons" | — |
| episode | one memory in the holder's own voice | — | memory entry |
| anchor memory | an episode that never decays | — | — |
| persistence lock | a subject decay never removes | — | PERSISTENCE_LOCK |
| place | a node in the place graph (room, street …) | the place's name | LSDL location (as geometry) |
| anchor | a named point inside a place | "the counter", "by the window" | — |
| portal | the link between two places (door, window, wall …) | "ways out" | — |
| layout discovery | rooms generated on first observation, permanent after | — | PLMP |
| timer | a scheduled future event (`event_queue`) | — | TENCL, TIMER_BANK (the view keeps the name `timer_bank`) |
| operation | off-screen group activity | — | SOL, STRATEGIC_OVERWATCH_LOG |
| object state | the `items` / `conditions` tables | — | PWOSS, WOSS, WORLD_OBJECT_STATE_LOG |
| place overlay | per-place changes | — | LSDL, LOCATION_STATE_DELTA_LOG |
| sim trace | `logs/sim_trace.jsonl` | — | SIM_TRACE_LOG, SWP trace, Header Block |
| narrator packet | what the narrator receives: only the PC's percepts | — | — |
| echo ledger | n-grams the model must not repeat back | — | — |
| Sandbox | a run where a cheat changed or revealed something | "Sandbox" tag | — |
| quarantine | cheat-origin entities excluded from balance maths | — | — |
| story | — | — | **sotry** (error) |

## Player-facing words (the only words play screens use for these things)

| Engine | Words (10 §5 word tables) |
|---|---|
| item condition | pristine · good · worn · damaged · failing · broken |
| Resolve ratio | steady · shaken · fraying · breaking · broken |
| impairment | clear-headed · slowed · impaired · badly impaired · barely functioning |
| bleeding | none · oozing · bleeding · bleeding badly · pouring |
| wound severity | minor · serious · severe · critical |
| load | light · moderate · heavy · overloaded |
| noise | quiet · some noise · noisy · deafening |
| need stage | fine · noticeable · bad · severe · critical |
| turn progress | Checking the world… · Reading your move… · Everyone takes it in… · People decide… · The world moves… · Reactions… · Locking it in… · Memories settle… · Writing it down… · Saving… |

## Retired names registry (machine-readable, used by CNT-08 and commit bit W14)

```
sotry        -> story        (error)
PWOSS        -> object state
LSDL         -> place overlay
PLMP         -> layout discovery
TENCL        -> timer
MEMORY_LOG   -> store
SOL_ADD      -> operation
NPC          -> Actor        (warning in content; allowed in player-facing prose)
```
