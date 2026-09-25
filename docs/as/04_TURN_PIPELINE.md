# 04 — The Turn Pipeline

A turn is a **transaction**, not a unit of time (plan §10.1). The player submits one input; the
engine simulates the world from `t0` (now) to a **horizon**, commits atomically, then remembers,
narrates, lints and saves. Implementation: `turn/pipeline.py::run_turn`. Stage labels shown to the
player are in `STAGE_LABELS` (never engine words).

## 1. The stages

| # | Stage | Owner | Output | Gate (fails → see §4) |
|---|---|---|---|---|
| 0 | wake | CODE | turn number begins (`clock.begin_turn`), a settlement's clocks started once (`turn.timers.seed_society`, P9), a generated world's clocks started once — its day and the faction councils (`turn.timers.seed_world`, P10; nothing in a hand-made scenario), due timers fired and cascade-swept (`turn.timers.fire_due`), pending reactions loaded, lanes probed, model-swap guard | **G0** state loads; `check_models` passes; at least one lane up |
| 1 | intake | LM(B) or CODE | the PC's `Intent` (see §2; `turn/intake.py`) | **G1** choice is a PC affordance; referents in the PC's believed set; no outcome fields |
| 2 | t0 freeze | CODE | `full_state_hash` recorded in `turn_ledger.detail` | **G2** hash recorded |
| 3 | perceive | CODE | `perception.compile_scene` for every candidate actor | **G3** every percept row granted by `perception.grant` |
| 4 | select | CODE | salience, mandatory set (`turn/select.py`), LOD plan (`lanes.scheduler.plan_cognition`) | **G4** mandatory set ⊆ HOT∪WARM |
| 5 | afford | CODE | `AffordanceSet` per HOT/WARM/COLD actor | **G5** every option passes the physical gate for that body |
| 6 | cognition | LM(A+B) | `ActorReplyV2` per HOT/WARM actor (a decision, or one consultation then a decision); plan continuation for COLD (`turn/cognition.py`) | **G6** schema-valid; choice ∈ offered handles; echo check on speech; targeted portrayal pre-check (§3.3, P11) |
| 7 | barrier | CODE | validated `Intent` list; nothing mutated yet | **G7** every referent resolves at T0 or is marked for ACTION_BLOCKED |
| 8 | resolve | CODE | outcome events (checks, conflicts, effects); how each mind answered what it was asked (refusals recorded, `turn/cognition.record_responses`) | **G8** each intent resolved exactly once; every draw in `prng_ledger` |
| 9 | propagate | CODE | sound, sight, evidence, harm follow-ons | **G9** conservation holds (items, bodies, cohorts) |
| 10 | cascade | CODE (+LM(B) advisory, never committed) | secondary consequences from the cascade table | **G10** every cascade event cites its rule id |
| 11 | reactions | CODE | next wave or stop (§3.2) | **G11** wave legality (time-bounded), cap 3, overflow → `pending_reactions` |
| 12 | commit | CODE | remaining due timers fired (`turn.timers.fire_one`, each swept); clock advanced to the end of the window; bodies/tasks progressed; the PC's closing view; scenes; 58-bit gate; COMMIT | **G12** all 58 bits = 1 |
| 13 | aftermath | CODE | `AftermathPacket` per mind that perceived anything | **G13** packet ⊆ that holder's percepts |
| 14 | writeback | LM(B) | memories, beliefs, feelings, loops, lessons (per holder or identical group) | **G14** no item cites an unperceived fact (dropped + logged) |
| 15 | audits | LM(B)+CODE | retrospective portrayal audit, leak scan | **G15** producer ≠ judge; leak scan is a query |
| 16 | PC compile | CODE | `NarratorPacket` | **G16** only PC-perceivable facts |
| 17 | narrate | LM(A) | prose | **G17** non-empty |
| 18 | lint | CODE+LM(B) | `LintReport` (+ up to 2 regenerations) | **G18** metrics, disclosure, echo pass (or best draft kept, §4) |
| 19 | autosave | CODE | ring save + manifest | **G19** manifest checksum verifies |

Stages 0–12 run inside ONE store transaction. Stages 13–19 run after COMMIT, each in its own
transaction; **the writeback calls (14) run concurrently with narration and its lint (17–18)**
(independent given committed state — free width across the two lanes, plan §4.5). Their results
are applied in a fixed order (14, 15, then the narration row), so the order the answers arrive in
never changes the world. The whole contract is the `turn/pipeline.py` docstring.

### 1.1 What the player sees while a move runs (P10, the loading bar)

The pipeline reports each stage as it begins (`progress(stage, STAGE_LABELS[stage], stage / 19)`:
0, 1, 2; per wave 3, 4, 5, 6, 7, 8, 11; then 12, 13, 16, 17, 14, 15, 19 — 9, 10 and 18 are
instant and never announced). P8 turns each call into `turn_progress` (the line under the input
box). P10 adds the loading bar (`service/progress.py`, PROG-01..07; 10 §2.10): just before
`run_turn` the service sends the turn's whole **plan**, and each announced stage lights its
sub-phase through `TURN_STAGES`:

| Phase (weight) | Sub-phases, in order (the stage that lights each) |
|---|---|
| Reading your move (8) | Checking the world (0) · Reading your move (1) · Weighing your words (2) |
| Everyone takes it in (12) | Eyes and ears (3) · Who noticed what (4) · What it means to them (5) |
| People decide (30) | People decide (6) |
| The world moves (15) | Everyone acts (7) · It lands (8) · Reactions (11) |
| Locking it in (3) | Locking it in (12) |
| Writing it down (30) | What they will remember (13) · Writing it down (16) · Choosing the words (17) · What it changes between them (14) · Loose ends (15) |
| Saving (2) | Saving (19) |

A reaction wave or a strict retry announces its stages again; the bar holds rather than going back
(PROG-04: the percentage never drops). A turn's bar never counts anything and never names who is
thinking (PROG-05). Before that bar, when the last boundary's quiet-hours jobs are not all done, a
second bar, *Everyone else catches up*, counts the jobs still to run ("1 of 3") while
`background.catch_up` finishes them (§5); its calls to the P8 callback are stage 0 and light
nothing on the turn's bar. Under each bar, one rotating line about the step (content
`ui/quips.yaml`, CNT-16; which line and when is the UI's, PROG-07).

## 2. How the player's input becomes an intent (stage 1)

| Input | Path | Model call? |
|---|---|---|
| Suggestion chip | the suggestion ref maps to a PC `BoundAffordance` built last turn; re-validated against the fresh AffordanceSet | No |
| **Do** text | quoted spans → speech (verbatim, PARSE-05); the rest → INTAKE (lane B, `intake_schema` with the PC's affordance handles) | Yes |
| **Say** text, mode "exact" | `speak` affordance to the chosen addressee (default: the person the PC last spoke with or is facing; the UI's "To:" chip overrides); words verbatim | No |
| **Say** text, mode "my way" | SAY_MY_WAY (lane B) turns the idea into the PC's line; `survived` recorded | Yes |
| **Ask** | GUIDE (lane B), answered by `service/guide.py` in P8 from the play view the player already sees plus plain rules text — **not a turn**: no event, no time passes; only the call log and two story entries are written (PROTO-07, GUIDE-01..03) | Yes |
| Contains `2508` / starts with `/` after activation | cheats (P12, routed by the service; see CHEATS.md) | Maybe |

INTAKE `choice = NONE` ends the request with `turn_rejected` (reason code + a plain message built
by code, e.g. `not_holding` → "You're not holding that.", plus the model's clarifying question when
it asked one) — **the input is not consumed and no time passes**. `remainder` becomes the first
suggestion next turn ("Continue: grab the can"). The exact messages and the recorded
`player_inputs` row are in the `turn/intake.py` docstring.
The PC's intent goes through the same barrier and resolver as everyone's (L12). Translation may
change manner; never the verb, the target or a refusal (SYM-02).

## 3. The simulation window (stages 3–11)

### 3.1 Horizon (`turn/select.py` HOR-01..04)

```
t0 = world_clock.now_ms
if PC intent is condition-ended (watch, wait, guard):
    horizon = min(t0 + 8 h, earliest pending queue due_at > t0, earliest actors.next_due_at > t0)
              and at least t0 + 3 s        # "keep watching" runs to the next scheduled thing;
                                           # a colleague's task step is not news
              # P9: queue rows of kernel.clock.BACKGROUND_QUEUE_TYPES (ROUTINE_STEP,
              # PRODUCTION_CYCLE, SETTLEMENT_DAY, GROUP_DAY, LOYALTY_CHECK, CASCADE_EFFECT,
              # TRACE_DECAY) do not end the window: a settlement's life is not news. P10 adds the
              # world's own clocks (WORLD_DAY, OPERATION_STEP, INFECTED_STEP, REANIMATION,
              # HORDE_STEP, POOL_RISE, COUNCIL): a horde matters when it is heard or seen. They
              # still fire inside the window, and anything they make the PC perceive pulls the
              # horizon.
else:
    horizon = max(t0 + 3 s, the PC action's landing time)
pull: whenever the PC holds a MATERIAL percept at m (a timer at stage 0, any wave, any timer inside
      the window), horizon = min(horizon, max(m + 3 s, the latest event already committed))
end of window (stage 12): final = max(horizon, the latest committed event)   # a COST landing may
      complete after the horizon; anything still due before final fires first
```

The pull applies to every PC action, not only waiting: when something the PC must answer happens,
the window closes three seconds later and the player decides. A longer action of the PC is then
still under way (its ACTION_LAND is queued); choosing it again next turn carries it on, choosing
something else interrupts it (P5 resolver rules).

### 3.2 Waves

```
active area = the PC's place + places within 2 portal hops (walls and fences count) + for every
              NOISE of this turn of 80 dB or more in the last 10 minutes of world time (P10), its
              place and the places 1 hop from it
wave 0 at t0: candidates = living actors in the active area except the PC + actors elsewhere whose
              next_due_at <= horizon; perceivers = candidates + the PC
for each wave w (0..cap; cap 3, 1 in the strict retry):
    S3 perceive  -> S4 select -> S5 afford -> S6 cognition (the PC's intent joins at wave 0)
    -> S7 barrier -> S8 resolve (+ how each mind answered what it was asked)
    -> S9 propagate -> S10 cascade
    S11: everyone in the area — and, B6 (SEL-07, fidelity C08), whoever the wave's sounds reach,
         wherever they are — perceives the wave's events (compile_aftermath); the PC's material
         percepts pull the horizon; holders with MATERIAL new percepts (reactions.material_holders,
         the PC excluded — the player answers next turn) react at trigger + 150–250 ms (+400 ms
         drowsy or focused); timers due before that (or before the horizon) fire first, one at a
         time, and their consequences may bring the next wave forward. Holders past the cap or
         past the window go to pending_reactions (TIME-04): they are mandatory at the start of the
         next transaction. Stop when no wave remains.
```

The reaction limit is **time-bounded, not count-bounded** (plan §10.4): every wave advances the
clock. The cap exists for cost only, and nothing is dropped.

A wave writes its landings when it resolves, and a timer's action lands with it, so the log can
hold a percept from a second after a reaction that comes before it. Every mind decides on what it
had perceived **by its own moment** — the packet, the options, recall and salience read only
percepts with `at <= at` (SKULL-10, D-63). What is material also covers the dead: one of them seen
moving to within 20 m is news to whoever sees it, and it ends the player's watch (REACT-01, D-65).

### 3.3 Cognition (stage 6)

- HOT: `EngineConfig.hot_cognition` (lane A, thinking on, 3000 max tokens including reasoning).
  Structured output with thinking depends on the probe result for the lane
  (`structured_with_thinking`): `supported` → json_schema on the call; otherwise the call is made
  without a schema, the JSON is extracted from the text, and a failure goes to one INTENT_REPAIR on
  lane B with the schema (LANE-06).
- WARM: `regimes[actor_cognition]` (lane B, thinking off, json_schema).
- COLD: `action.intent.plan_continuation` — the same decision still running. **LOD is a reasoning
  tier only**: it never changes competence, morality or knowledge (LOD-01).
- The scheduler fills both lanes breadth-first: a WARM call beside a HOT call costs no wall-clock
  (plan §4.4). Mandatory actors always get a call, even past budget (`BUDGET_OVERRUN` logged).
- Every generated speech line is checked against the echo ledger; an echo triggers one repair with
  the phrase forbidden; when that repair fails or still echoes, the original line stands and the
  echo is logged (ECHO-02, Actor Spec §11: a failed repair is no reason to silence a person).
- **The answer (Actor Spec §7; REPLY-01..02, D-74).** An `ActorReplyV2`: a decision (one offered
  attempt with its pace, speech with delivery and timing, goal, private reason) or — only when the
  packet offers one — one consultation first: *recall* (their own episodes and beliefs the packet
  did not show) or *more_actions* (more options of one family the menu hides). It is answered from
  the same snapshot and a second call decides. At most two decision calls and one repair per
  decision; a V1 answer is read through the adapter.
- **A failed answer never becomes a choice (HOLD-01..02, D-75).** Still unusable after its repair,
  or the lane timed out: when the moment is consequential (an unanswered ask, or a threat they
  perceived) the turn is not played (`DecisionHeld`: rolled back, input kept, a plain message);
  otherwise what they already took on goes on (`plan_continuation(accepted_only=True)`), or they
  make no attempt this wave. `DEGRADED_FALLBACK` records which.
- **Answers are read by code (stage 8):** what each mind had heard addressed to it before it
  decided is classified by the firewall (form, standing, signature); a refusal is recorded
  (`REFUSAL`, WILL-07), a "yes" with a different action is a recorded lie (WILL-11). The model is
  never told it "refused" — it chose, and code reads the choice (`turn/cognition.record_responses`).
- **Targeted portrayal pre-check (deviation D-07, P11):** when a HOT or WARM actor chooses an affordance
  with moral tags, an ATTACK, or a refusal/compliance to a request with standing VALID_ORDER, one
  PORTRAYAL_AUDIT call (lane B) judges it before the barrier. `out_of_character` → the intent is
  regenerated once with the reasons appended. All other audits are retrospective (stage 15) and
  feed a *portrayal note* into that actor's next packet instead of rewriting the past.

### 3.4 Mandatory set and salience (stage 4, `turn/select.py`)

Mandatory (always HOT or WARM, even past the budget): a pending reaction from the last transaction;
immediate danger to its body or freedom (cues weapon_pointed, infected_close, grabbed_from_behind,
dependent_in_danger; gripped; touched or hurt); addressed by name; one of its standing orders'
triggers is present (a guard told to answer a loud noise hears one); its task ends inside the
window; the PC's intent targets it.

Salience = Σ `SchedulerRules.salience_weights` over the true flags: `unique_info` (holds a
PARTIAL+ percept no other candidate holds), `loudest_percept`, `addressed`, `in_conflict`,
`interrupt_trigger` (a standing order's trigger crossed), `open_loop_with_pc`,
`dependent_present`, `visible_to_pc`. Ties break by actor id.

## 4. Failure, rollback and degradation

**Rollback law.** Any exception or `ValidationFailure` in stages 0–12 rolls back the whole
transaction. The pipeline retries ONCE in strict mode (reactions capped at 1), reusing the first
attempt's successful model answers whose request hash is unchanged. A second failure leaves the
world exactly as it was, logs `error_repair_log(kind='rollback', rule_id=…)`, and answers
`turn_rejected {code: 'turn_failed'}` — **the player's input is not consumed.**
Failures in 13–19 never roll back state: prose is a projection over committed state (plan §5).

**Stop (P8).** The Play UI's Stop button sends `turn_cancel`; `GameService` cancels the task running
the turn, but only while the last reported stage is below 12. The `asyncio.CancelledError` is not a
rollback-law failure: the store transaction rolls it back (a `BaseException` rolls back too,
`Store.transaction`), nothing is logged, and the world, the clock and the input are exactly as they
were (PROTO-06). From stage 12 on the answer is `too_late` and the result still arrives.

| Failure | Detection | Behaviour (never "guess and continue") |
|---|---|---|
| Lane B down at turn start | stage 0 probe | Single-lane mode: the scheduler places HOT and WARM calls on lane A within the budget (the rest run COLD); every other call moves to lane A; the turn's notice: "Your second model is offline; turns will be thinner until it is back." |
| Lane A down | stage 0 probe | No HOT; WARM, narration and the rest move to lane B (thinking off); notice: "Your main model is offline; the story runs on the second model until it is back." |
| Both down | stage 0 | Refuse the turn: `turn_rejected {code: 'no_models'}`; nothing changes |
| Lane dies mid-wave | timeout / reset | No repair; HOLD-01 for that actor (a consequential moment: the turn is not played; otherwise what they took on goes on, or no attempt); `DEGRADED_FALLBACK` event |
| Grammar/schema failure | parse_status | One repair call (INTENT_REPAIR, a decision only); then HOLD-01 + `DEGRADED_FALLBACK` + `error_repair_log` |
| Choice not in the offered set | intent validator | Same as above; never reaches `resolve` |
| An Actor line repeats the player's words | echo ledger | One repair with the phrases named; when it fails or still echoes, the original line stands; logged as `echo_reject` |
| Call over deadline | scheduler | Cancel; HOLD-01; record |
| Model swapped mid-session | `check_models` | Hard stop before T0 with a plain message (LANE-05) |
| Commit fails | exception | Full rollback; input not consumed |
| Save write fails | checksum | Keep previous save; keep new as `.partial`; refuse to advance |
| Narration lints 3× | lint | Keep the draft with the fewest errors; log findings; state untouched |
| A stage in 13–19 raises | exception | The committed turn stands; `error_repair_log(kind='degraded', rule_id='GATE-13')`; the turn is reported degraded with whatever narration was written |

A degraded turn is honest and recorded; a guessed turn is corruption (plan §5.3).

## 5. After commit (13–19)

- **Aftermath** (13): per holder, only its own percepts of this transaction's events; holders
  with nothing perceived get no packet.
- **Writeback** (14): every person gets their own call (MEM-03, Actor v2 B5b); the PC gets
  writeback too (its Journal and recap come from it). Each is a memory job (MEM-19): a failed call
  writes nothing, is logged, and is tried again at later turns, and until it is done the person's
  next packet carries what they did and saw raw.
- **Audits** (15): the leak scan is a SQL query — every `claim_holdings` row acquired this
  window (inferences aside) cites an event its holder has a percept of; `audit_log` rows with
  producer ≠ judge. The retrospective portrayal audit is P11.
- **PC compile / narrate / lint** (16–18): see 05 §Narration and 07 §Style metrics. Up to three
  drafts; the code lint first, then the RENDER_LINT judge (lane B) on a draft the code passed —
  the judge can only add faults. No draft at all: the code tells the moment plainly.
- **Autosave** (19): ring file + manifest (`service/runs.py`); in-memory test sessions skip it.
  The service stays `busy` until 19 finishes (a submit meanwhile gets
  `error {code:'busy', message:'Still settling the last moment…'}`).
- **The quiet hours** (P10, `service/background.py`, BG-01..07; 05 §9.2, 06 §7): after the result
  is pushed, people with something to think over reflect, and rumour holders choose the words they
  will pass a story on in — one model call at a time, each committed in its own transaction, while
  the player reads. Which jobs a boundary has is fixed by the world as the turn left it (BG-02);
  the next turn first awaits `background.catch_up`, which finishes every one of them, so the
  player's reading speed never changes who thinks about what (BG-07, AC12). Jobs never run inside
  a turn's transaction; loading, closing or starting a run cancels the runner, and the next
  `catch_up` finishes what is left. Replay re-commits the recorded answers (BG-05).
- **Re-simulation** (`service/replay.py`, `as-engine replay`): every run keeps `turn0.sqlite`
  (the run at turn 0); replaying its `player_inputs` with the recorded model answers (found by request hash)
  must reproduce `full_state_hash` after every turn (DET-02) — the sim soak proves it every gate.

## 6. Scenes

`scenes` rows are opened/closed by code (plan §10.5 carried). **P7 (SCENE-01)**: a scene is the
PC's stay in one place — the first turn opens one; leaving the place ends it (`SCENE_END` reason
'left') and opens the next. **P11** adds the rest: a first contact or a threat appearing starts a
scene; the problem resolving or its `chunk_max` ends one (PASSIVE scenes — unconscious,
restrained, carried — MUST end at max: the coma failsafe); **opportunity weaving may only surface
a pressure already in committed state**, never mint one (SCENE-02); scene end triggers the PC's
scene summary (lane B) for the Journal.

## 7. Worked trace — "Night at Delgado's" (P7 integration scenario)

Fixture: `as_engine/tests/fixtures/scenarios/metal_fence.yaml` (the plan §5.4 anchor scene).
Barricaded store, day 18, 23:14, wind rising. PC (Owen) at the counter; Mara at the front window
(guard, revolver, tired; standing order "loud_noise"); Alice behind the counter (sorting a run's
haul); June in the storeroom (counting cans, 41/60); Eli asleep in the office; Nita in the rear
alley by the dumpster, finishing her 23:00 perimeter walk — the back door is unbarred and ajar for
her return; an unknown man (Dale) in the lot right behind the chain-link fence. A loose metal
sheet is wired to the fence and a gust is queued for 23:14:03, the start time. The scripted model
answers are `tests/contract/p07_slice/slice_kit.py::script_night_at_delgados`; everything else is
computed with `RulesConfig()` defaults (reception arithmetic: `tests/fixtures/vectors/acoustics.json`).
Asserted by `test_p07_slice_metal_fence.py` unless noted.

| Stage | What happens |
|---|---|
| 0 | `CLOCK_ADVANCE` (turn 1 begins), `TIMER_FIRED`, then `NOISE` 98 dB at the fence sheet — before the player's input is recorded |
| 1 | "I watch the front window and keep quiet." → INTAKE → the PC's own `observe_area` (condition-ended); no movement invented; the input's 4-word runs go into the echo ledger |
| 2–3 | the crash is material to the PC at t0, so the window closes at t0 + 3 s. Receptions: PC, Mara, Alice, June EXACT ("A loud metal crash came from the rear alley."), Eli TONE_ONLY ≈60 dB through the boarded window — ≥ the 55 dB sleeper threshold, so he wakes; Nita EXACT from the sheet itself; the stranger EXACT "from the other side of the chain-link fence". The loud crash brings the lot into the active area, so the stranger is a candidate |
| 4 | Mara mandatory (her standing order's trigger) → HOT; Alice HOT (salience); June, Eli, Nita, the stranger WARM; the PC is never a candidate |
| 5 | June (no firearms, Resolve 3) is offered no shooting option |
| 6 | scripted: Mara "Quiet." + take cover at the rear shelving; June "What was that?" (raised) + go and look toward the back door; Alice watches the storeroom door; Nita hides at the dumpster; the stranger runs to the tall weeds (Eli waits: the fake's default) |
| 8 | the stranger's run lands at +0.9 s; Mara's, June's and Nita's moves land after the window (queued `ACTION_LAND`) |
| 9 | Mara's "Quiet." reaches June as a voice only (TONE_ONLY); June's call reaches Nita PARTIAL ("What … that?"), Mara PARTIAL, the stranger TONE_ONLY |
| 10 | June's and Alice's tasks pause (`CAS-014` cited) |
| 11 | Nita alone sees an unknown man run to the weeds within 20 m — material → wave 1 at the run + 150–250 ms: she keeps hiding (same choice, the hide carries on); no wave 2 |
| 12 | clock → t0 + 3 s; 58 bits all 1; commit |
| 13–14 | Nita alone writes "someone was watching the back and ran when June shouted", and infers "The thin man ran because June shouted." from a half-heard call — confidence 2, fidelity partial; nobody else can know it |
| 16–18 | the narrator is given the crash, the PC's choice, Mara's "Quiet.", June's "What was that?" — and nothing of Nita, the man, the weeds or the dumpster (DISC-01) |

What the player receives: the scene and nothing else. If they want to know about the stranger,
someone has to tell them — and Nita decides for herself whether to.
