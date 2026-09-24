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
| identity card | who a person is as their decision calls show it: the whole dossier's person in plain lines, each traceable to its fields; the minimum card in a reaction (`mind.identity`, IDN-01..05) | — | character summary, persona prompt |
| affordance | one thing a body could attempt now, computed by code | "option" / a suggestion | action menu item |
| whereabouts | where one mind can account for a person being: here (seen now), heard not seen, last seen somewhere, or not seen (`PacketEntity.whereabouts`, Actor Spec AC14) | — | location (for a person in a mind) |
| looks | what anyone can see of a person: hair, facial hair, eyes, complexion, visible marks, and the outfit they are first dressed in (`contracts.dossier.Looks`; `bodies.looks` without the outfit; LOOK-01). Visible facts only, never history | how someone looks | — |
| outfit | the clothing items a person is dressed in when placed in the world (`Looks.outfit`, `physical.objects.dress`); afterwards what they wear is items with slot `worn` | what they're wearing | — |
| clothing block | an item's `clothing` properties: slot, layer, covers, words, colour, style, warmth, protection, conceals (`ClothingProps`, LOOK-02) | — | — |
| SHOWN | the pieces of clothing someone looking can see: the outermost layer at each slot (a one-piece suit hides a shirt of its own layer), in slot order (`mind.perception.appearance_text`) | — | — |
| condition (of a body) | grime, blood, gore (0–5) and wet (0–3) on a body and its clothes (`bodies.grime / blood / gore / wet`, `physical.bodies.soil`, LOOK-04); the dead start at grime 5, blood 3, gore 5 | filthy, bloodied, caked in gore, soaked through | — |
| appearance (of a person, to a mind) | what one mind sees of someone at this moment, from their looks, clothes, visible gear and condition at that distance and light (`appearance_text`, `PacketEntity.appearance`, LOOK-03, LOOK-06) | — | — |
| odour | what a body smells of now: kind (the dead, death, blood, unwashed) and strength 1–5, from its condition or, for a corpse, the hours since death (`sense.olfaction.odour_of`, SMELL-01) | "reeks of the dead", "smells of blood" | — |
| gore camouflage | a living body caked in the dead's gore goes unpicked by the common dead until it gives itself away (`world.infected` INF-14) | — | — |
| known law | a law of the place a person knows: every law there for a member of the settlement's group, and the ones anyone else was told; a cost next to an option, never a missing option (AFF-11) | — | forbidden action |
| intent | what a mind attempts (never an outcome) | "what you do" | action (as a record), move |
| decision | an Actor's answer that attempts something: one offered option, its pace, speech, goal, private reason (`ActorReplyV2` kind decision) | what they do | — |
| consultation | one lookup in a person's own head before they decide: recall, or more options of one family (`mind/consult.py`) | — | — |
| affordance family | the kind of thing an option is (attention, movement, access …; `AFFORDANCE_FAMILIES`) | — | — |
| pace | normal, careful or rushed: the one manner that changes time, noise and the check (INTENT-07) | "carefully", "quickly" | — |
| held decision | a consequential decision whose answer could not be used: the turn is not played (`DecisionHeld`, HOLD-01) | "this turn was not played" | — |
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
| sessions browser | the Your lives screen: every run, ended ones too, with a one-step delete that wipes the run (RUN-12) | "Your lives" | Load list |
| world | the generated place, its people and history | "world" | — |
| genesis | the saved state of a world before any PC was placed | "the world as it began" | BaselineWorldFile (the ruling's name) |
| turn-0 snapshot | a run's `turn0.sqlite`: the run as it stood before its first turn (PC placed), kept so the run can be re-simulated (DET-02) — not a genesis | — | — |
| active area | the places a turn simulates in full: the PC's place, 2 portal hops, and the neighbourhood of any loud noise this turn in the last 10 minutes of world time (SEL-01) | — | — |
| guide | the model that answers Ask-mode questions from what the character knows plus plain rules text (`service/guide.py`); never a turn | "Guide" | hint system, helper |
| push | a protocol message the service sends without being asked (turn progress, the turn's result, the story) to every connected page | — | broadcast, event (for messages) |
| busy | a turn is running; the service refuses anything that would read or change the run, except the view and the story from before the turn | "Your last move is still being worked out." | locked |
| lane | one model the game uses (A = the main model, B = the second; both picked from one LM Studio list) | "Main model", "Second model" | box, slot, Storyteller brain, Fast brain |
| call class | the kind of model call (intake, narration …) | — | stage call |
| LOD | reasoning tier of a mind: HOT (deep, thinking), WARM (fast), COLD (code continues the plan). The world's levels of detail are something else: see "levels of detail (world)" | — | level of detail (as a competence level — never) |
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
| levels of detail (world) | the forms the dead take by distance from the player — bodies where the player is, pools per district, hordes on the roads, the exterior past the edges (fidelity §5; 06 §5.1). Nothing is made or lost passing between them | — | LOD (for this: LOD is a mind's reasoning tier) |
| pool | a district's counted dead by type, active or dormant (`infected_pools`) | — | encounter rating, spawn table |
| frontage | where a building site meets its street: an anchor of the hub along one side or the other ("the front of the Yazzie house"); the next building is a walk down the street (WG1, D-64) | "the front of the Yazzie house" | — |
| horde | a counted crowd walking hub to hub: drift (a district sends some off), drawn (a loud sound pulls them), mega | "a crowd of the dead" | — |
| Mega Horde | the end-game event: the country's dead, tens to hundreds of thousands, through the region for days (HRD-12..16; D-57) | what people call it ("the big one coming") | — |
| exterior | the four zones past the region's edges, each one huge finite pool (W04) | the roads out ("the North Road") | — |
| census | pools + hordes + bodies: every infected in the world, conserved but for rising and destruction (HRD-15) | — | — |
| fold | one of the dead going back into a count when the contact is over — anonymous, unhurt, going nowhere of its own (with its crowd, or no target), holding nobody, where nobody alive stands, outside the active area; its record stays, its position goes (HRD-18, D-67). The reverse of promotion, where a count's dead become bodies where the player is (HRD-07) | — | despawn, delete |
| density | how thick a district's active dead are, 0–10 (the heat map; outings are hurt by it) | — | encounter rating |
| saturated | a district the Mega Horde is passing through: never quiet (85 dB), every street full | — | — |
| strain | the minutes a crowd has leaned on a door (`portals.strain_min`); damage 0–3 shows how near it is to giving way | "the door is splintering" | — |
| energy | an infected body's budget, spent by time while active; 0 → dormant | — | — |
| dormant | an infected standing still until something wakes it ("a statue") | "standing still, like a statue" | — |
| risen | a new infected body that got up from a corpse (`risen_from`) | "what was left of <name>" | reanimated corpse (as the same body) |
| living spreader | a wet-strain host in weeks 1–3, infective from about day 3 | — (the signs show, the name never does) | — |
| spreader signs | what a close, clear look shows of a week-2+ host (a cue) | what you notice about them | — |
| compulsion | a week-3 host's involuntary offer of mouth-contact food or drink (never the PC) | — | — |
| enclave | a faction's sealed settlement: one gate, never breached (the Depot) | its name | bunker (in code) |
| lockdown | an enclave shut: nobody goes out (`settlements.lockdown`) | "they've sealed the Depot" | — |
| seat / seat holder | an office a faction's leader list names (Leader.seat); its holder is a real generated person | the title ("the Gray Top Hat") | — |
| council | the seats that meet on a schedule (FAC-02) | "the Top Hats are meeting" | — |
| route watch | a faction that sees a Mega Horde forming before any sign (FAC-03) | — | — |
| DECON | a faction's retaliation team sent after whoever killed one of theirs (FAC-04/05) | what people whisper | — |
| operator | a DECON team member, named out of the enclave's counted people | — | — |
| outing | an operation: scavenge, patrol, trade run, raid, decon (OPS-01..08) | what people say ("they went out for supplies") | — |
| world day | the world's daily clock (`WORLD_DAY`, 04:00): weather, the unseen dead, outings, wear, the infected, the hordes | — | world tick |
| wear | what weather and time do to things (rust, pulp, rot, spoiling); nothing is deleted (C02) | the item's condition word | Memory Fade, graceful forgetting, environmental reclaim, location overhaul |
| materialise | one unnamed person taken from a cohort becomes a named one (L11) | — | spawn (for people) |
| quiet hours | the jobs a turn boundary owes — reflection and retelling — run while the player reads and finished before the next move (BG-01..07) | "Everyone else catches up" | idle-time cognition |
| reflection | a person mulling what happened (goals, grudges, a lesson, a plan) | — | — |
| retelling | a holder putting a fresh rumour into their own words (INFO-06) | — | — |
| loading bar | the progress view of a long job: its whole plan, the step lit, a line about it (PROG-01..07) | the bar | — |
| plan / phase / sub-phase | a long job's steps, in order (`service/progress.PLANS`) | the step's plain label | stage (on screen: never) |
| quip | one line the bar shows about the step (`ui/*.yaml`, CNT-16) | the line under the bar | — |
| magnet | a place worth the risk that the PC has a lead on (WG8, WG-35) | "a lead" (Journal) | — |
| home settlement | the settlement the PC starts in or beside (WG2) | its name | — |
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
| loading bar (P10) | titles: Making your world · Your move · Everyone else catches up · Time passes; a turn's steps: Reading your move · Everyone takes it in · People decide · The world moves · Locking it in · Writing it down · Saving (`service/progress.PLANS`) |

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
