# 06 — The World: Generation, Society, Motion, Decay

## 1. World generation (P10)

### 1.1 Inputs (New Life wizard → `RunSettings`)
difficulty (6 tiers) · era (Early / Established / Mature, default Mature) · days since the Fall
(optional; else drawn inside the era range) · world detail (5 tiers) · seed (optional) · the PC
dossier (its `worldgen_bias`, `plausibility_gate`, `faction_start_type`, `start_constraints`,
`locked_start_facts`, `recap`, `days_since_fall_range`) · content packs.

**A character fixes the world's age (WG-34).** A dossier's recorded age, cohort and history only
fit some world ages — Addison is twenty and was about ten when the Fall came, so her world is
9–11 years old. `days_since_fall_range` records that. The wizard only offers eras that overlap it
(the others show "Addison's story needs a world 9–11 years after the Fall"), draws the world age
inside the overlap, and "Start a new life in this world" lists only characters whose range holds
that world's age. Authored Actors whose range excludes the world's age are simply not placed
(listed in the worldgen report). A dossier without the field fits any world.

### 1.2 Parameters (WG0) — Codex Master Guide §61 carried verbatim
Blocks A (world feel), B (human landscape), C (what hunts you — difficulty-owned), D (what still
exists — shortages and tech difficulty-owned), E (flavour), simulation mechanics (snowball rate,
warning slack, recovery slack — fixed by tier). Tables live in `world/worldgen/tables.py`; the merge
protocol, rounding, draw order and contradiction handling are specified in
`world/worldgen/params.py`. Priority chain: difficulty bands → era constraints → PC bias → random
variation.

**Climate descriptor** (≤ 35 chars) from heat (1–10) × moisture (1–10):

| heat \ moisture | 1–3 dry | 4–7 moderate | 8–10 wet |
|---|---|---|---|
| 1–3 cold | "frozen, dry, wind-scoured" | "cold grey damp" | "sleet and slush, always wet" |
| 4–7 mild | "dry temperate scrub" | "temperate, rain some days" | "mild and waterlogged" |
| 8–10 hot | "arid heat, dust and glare" | "hot, humid, overgrown ruin" | "subtropical ruin, heavy rain" |

(Addison's bias heat +0.7 / moisture +0.4 resolves toward "hot, humid, overgrown ruin" — CMG §61
Part XV climate resolution.)

**What the simulation mechanics do** (symmetric for every body — no player advantage):
- warning slack `w`: ambient masking is lowered by (w − 5) dB for every listener (07 §Audibility);
- recovery slack `r`: healing time multiplier `1 + (5 − r) × 0.1`;
- snowball rate `s`: on a BREAK outcome, an extra complication fires with probability
  `max(0, s − 5) / 5` (rng stream `resolve`).

### 1.3 Pipeline (WG0–WG9, `world/worldgen/pipeline.py`)
Every stage commits `WORLDGEN_STAGE` + its content events (origin `worldgen`) and asserts its
invariant; a failing assertion reruns the stage once on a fresh sub-stream, then aborts with a plain
report (never a half-built world). Progress goes to the UI as `worldgen_progress` with friendly
labels: *Rolling the world… · Carving the land… · Writing what happened… · Drawing the lines of
power… · Building settlements… · Filling homes… · Waking the people… · Setting the laws… · Placing
the trouble… · Checking it all holds together…* — and to the loading bar (`service/progress.py`,
10_UI §2.10): the whole plan first, then each stage, with WG2 and WG6 counting their model answers
("Writing the people down — 2 of 12") and a line about the step under it.

| Stage | Builds | Key rules |
|---|---|---|
| WG0 | parameters, plausibility gate + hard-fail protocol | CMG §61 QC-1..3, Part XII; enforced Bitch→Realism only |
| WG1 | zones (count by detail tier; at most one 'wilds' zone, which has no buildings), each a hub street with its building sites (grounds only) or outdoor places — each meeting the street at its own frontage along one side or the other, so the next building is a walk down the street (D-64) —, roads between hubs (a ring plus chords), the four ways out — the exterior zones past each edge — and every district's counted dead (§5.1) | every place reachable; the start zone has two edge-disjoint ways to another zone (WG-15..17) |
| WG2 | causal history: code builds an event skeleton (kind, day, subjects, cause) from params; WORLDGEN_HISTORY (lane A, thinking) writes truth + belief text per event; structure fate: buildings that were defended, sealed or lucky get `places.held = 1` | WORLD-01: every settlement, faction posture and shortage cites ≥ 1 history event; history is causal, not decorative; the history horizon equals days-since-the-Fall, never a constant (WG-31); held buildings skip the interior Fall-damage pass at discovery (WG-32) |
| WG3 | canonical factions (presence rules, Part X) + procedural groups (`[dynamic] + [location type] + [rule or resource]`, ≤ 60 chars); an enclave faction (the Ghosts) is planned on top, never as the placement faction, with its sealed site (§2.8) | faction presence coherence (dominant needs density ≥ 6, active ≥ 3, peripheral ≥ 1) |
| WG4 | settlements, workplaces (water pump, kitchen, garden, workshop, clinic, watch, laundry, school), stores, laws | population baseline modulated by history (Batch-3 ruling #5) |
| WG5 | cohorts from a survivor pyramid; households | DEMO-01 bounds (§2.1); children are inhabitants (DEMO-02) |
| WG6 | Actors: pack actors first (protected), then generated detailed actors (WORLDGEN_ACTOR on both lanes in parallel, schema + validator + one targeted repair per failing section) — posts, leaders, a faction's other seat holders (the Top Hats, the Front Man), residents — each named out of the counted cohorts; relationship matrix 20 % positive / 60 % strangers / 20 % rivals (SOC-01); knowledge seeds → beliefs | hand-written characters cannot die in worldgen; if history would kill one, recalculate to explain survival (Batch-3 ruling #6) |
| WG7 | local laws per settlement (faction laws + params: curfew when hostile_human ≥ 6; weapons policy by social order; contamination/intake laws where factions have intake doctrine) | laws are costs on the options of the people who know them (members; anyone told) — never a missing option (05 §4, AFF-11) |
| — | **genesis snapshot** of the finished world, before any PC exists (`_worlds/<world_id>/genesis.sqlite`) | a world can be reused for a new run or shared as a file (RUN-09) |
| WG8 | PC placement (Part X), immediate contacts, opening pressure made of **real placed entities**, first objective; WORLDGEN_OPENING writes the text with citations; **PC survival history**: 3–5 history events with the PC as subject, each an anchor memory for the PC | QC-4: specific, non-trivial, reflects ≥ 1 A/B param, cites ≥ 1 placed entity; budgets 150/150/200/150 chars; WG-33: the PC starts with real memories and a reason for being alive |
| WG9 | the world's checks (WG-35): three places worth the risk that the PC has leads on; a settlement short of food or water that the PC knows about; a lethal threat within two places of the start, and a mark that warns of it; two ways out of the start zone; history for every settlement and group (WORLD-01); every settlement's demographics sound (DEMO-01); the 58-bit gate | a failure means a stage was built wrong: worldgen stops with every failure named in one sentence. Not re-asserted daily in v1 (WG-37, D-45): the P11 release audit re-runs the checks on the run's turn-0 snapshot (genesis has no PC yet; D-95), from the skeleton WG8 keeps in the worldgen commit |

**Worldgen does not pre-script outcomes** (WG-30): it decides who people are, what happened and
what they face — never who betrays, dies, befriends the PC or becomes the villain.

**Detail tiers** (`tables.DETAIL_TIERS`): zones 3→8, places per zone 4→12, detailed actors 8→40,
LM-written dossiers 3→40, history events 6→30; estimated 3→60 minutes (shown before starting;
replaced by measured values after `bench`).

**Rooms are generated on first observation** (PLMP discovery, GEO-03) from building archetypes,
seeded by `layout:<place_id>`, and are permanent afterwards.
Buildings that did not hold through the Fall get the Fall-damage pass at discovery (damaged or open
exterior doors, picked-over loot, an "old damage" trace); held buildings keep their interiors (GEO-04).
A building whose archetype has a roof gets it at discovery too (D-108, PARKOUR-08): open air at its
height, a hatch from inside, a drainpipe or a fire escape outside, an edge down; the roofs of
neighbouring buildings in a zone get a gap between them more often than not (70–300 cm) — the
lines a runner-scavenger like Addison Flores lives on, above the dead.

### 1.4 Worlds are files, not seeds (RUN-09)
The seed fixes every code-side draw, but model-written history and people differ between runs, so a
seed does not reproduce a world. Every generated world therefore keeps its **genesis snapshot**.
Home → **Worlds** lists them; "Start a new life in this world" places a new character into a fresh
copy (WG8–WG9 only); **Export** writes `<world_id>.asworld` (a zip of the snapshot + a summary) and
**Import** reads one. The PC's worldgen bias cannot reshape a world that already exists; its
plausibility gate is still checked and refuses a hopeless start at Bitch Mode–Realism.

## 2. Society (P9) — the answer to "stories aren't rich enough" (F1) and "the world doesn't move" (F3)

The contracts are the module docstrings of `society/*.py`, `world/rumours.py` and the P9 parts of
`mind/mind.py`, `turn/timers.py` and `action/cascade.py`; every number below lives in
`SocietyRules` (`RulesConfig.society`, 11_SETTINGS). This section is the overview.

### 2.1 Demographics (DEMO-01..04, `society/population.py`)
A settlement's people are its **named** members (living bodies with an `actors` row and a
`member`/`probation` row in the settlement's governing group — the PC counts like anyone) plus its
**unnamed** people (`cohorts` rows: counts by age band, not bodies). `census()` counts both.
Survivor pyramid bounds for any settlement above 15 people (DEMO-01): infants+children 10–30 %,
preteens+teens 8–20 %, adults 40–70 %, elders 3–15 %; `demographic_issues()` returns one plain
sentence per band group outside its bounds. Children are inhabitants with routines like everyone
(DEMO-02). A settlement of only military-age adults must cite a reason, recorded by worldgen as a
history event (DEMO-03, P10). Changing a cohort is a `POPULATION_CHANGE` that can never go below
zero; materialising a person from a cohort decrements it in the same transaction (L11,
CONSERVE-04 — the materialise step itself is P10).

### 2.2 Households (HH-01..07, `society/household.py`)
`households` + `household_members` (role, `guardian_of`, protection priority), shared stores, grief
state. A parent's decisions can account for their child because the engine knows who their child
is: `dependents_of()` reads `guardian_of`; a household "has dependents" when a living member is a
child or dependent by role or by age band (infant, child, preteen). The head is the `head`, else a
`partner`, else the oldest member aged 15+. The **worst-hit household** in a shortage is the one
with the most dependents per able provider (ties: the smaller shared stores). Deaths, joins and
departures are `HOUSEHOLD_CHANGE` events; grief (0–3) rises with a death (core CAS-007) and eases
by one after 7 quiet days (checked at the daily draw).

### 2.3 Routines and work (ROUT-01..07, WORK-01..12, `society/routine.py`, `society/work.py`)
**Routines** are derived, never stored as truth: a non-human named member's day is filled from
their work assignments first, then sleep (children 19:00–07:00, adults 22:00–06:00, night workers
8 h from the end of their shift, dropped if fewer than 4 free hours), then `play` (children) or
`free`. A `ROUTINE_STEP` timer fires at each step boundary and wakes, moves (to the place's
centre, only when the body is mobile), beds down or starts the shift. A routine yields to what
someone is doing (an active task or a pending action → `skipped`); an unconscious or restrained
body skips; a worker who is not able for the role spends the shift as free time at the
settlement's place instead of standing at the post. **Code never gives the PC a routine** (SEL-06).

**Work.** A worker is *qualified* for a role by skill rank (`SocietyRules.role_skill`: pump
operator and mechanic need mechanics 1, cook cooking 1, medic medicine 1, …; unlisted roles need
nothing) and *able* unless dead, unconscious, restrained, or — for a manual role — carrying an
unhealed arm or hand wound with function loss ≥ 1. Asleep is able: people wake for their shift.

Workplaces run `PRODUCTION_CYCLE` timers every `cycle_h`. An assignment works a cycle when its
daily shift shares any time with the cycle window. Per cycle:
```
staffed          = filled required roles / required roles  (able + qualified crew only)
input_factor     = the scarcest input's share on hand: min over inputs of min(1, stores / per cycle)
condition_factor = min(1, machinery_condition / 50) — 0 at condition 0: broken machinery makes nothing
spite            = the animosity result for this crew (2.5), 1.0 when nobody resents anybody
output[res]      = floor(base_output[res] × efficiency × staffed × input_factor × condition_factor × spite)
```
(Actor v2 B6, fidelity C04.) What running took (inputs × staffed × input_factor; nothing when the
machinery is broken) comes out of the settlement's stores once, as a `STORES_CHANGE` like every
other draw — one ledger for what is made, used and eaten; rationing is who gets what, never a
second draw. Output goes into the stores (`STORES_CHANGE`); the stall reasons say why a workplace
stood: `unstaffed`, `broken`, `no_<input>`. **Cover**: a missed shift pulls the least-worked qualified, able,
non-human teen or adult whose own shifts do not overlap (`pick_cover`); the cover's own post loses
0.25 efficiency (core CAS-003) and regains 0.25 per cycle once nobody of that post is covering
elsewhere; the cover is released (`ROLE_RELEASED`) when the covered worker is able again. A dead
worker's post is deleted and becomes a **vacancy** on the settlement; nobody to cover also makes
a vacancy. Goods carry **Lot ids** (production site, cycle, quality, adulteration, chain) once
trade arrives (P10); P9 stores are counted units.

### 2.4 Settlement economy (STL-01..12, ECON-01, `society/settlement.py`)
Daily need per person at the normal ration (level 3): water 3 units and food 2 units (infants
1 / 0.5, children 1 / 1). Ration levels 0–4 multiply the need by 0.25 / 0.5 / 0.75 / 1.0 / 1.25.

**The daily draw** (`SETTLEMENT_DAY`, 07:00): named people drink and eat in priority order —
infants, children, preteens, teens, elders, then adults, by id — each either getting their full
share or going on the `short` list; the unnamed take what is left. The fed have thirst (level ≥ 1)
and hunger (level ≥ 2) refreshed — at level 1 people drink but go hungry, at level 0 neither.
While the ration is ≤ 2 morale falls by 1 a day; with no shortage and morale under the baseline 5
it recovers by 1 a day. A shortage ends at the draw that leaves ≥ 3 days of that store; the ration
rises by one (up to 3) after 3 draws in a row with every rationed store at ≥ 7 days.

**Shortages and cuts are content**, not code: a pump or kitchen cycle that leaves under 3 days
declares a `SHORTAGE` (CAS-004 water, CAS-016 food), and a shortage cuts the ration by one
(CAS-005, CAS-017). A cut to ≤ 2 raises every dependent-holding household head's tension toward
the leadership by 10 and schedules a loyalty check for the head of the worst-hit household an
hour later (CAS-006). Laws are the content law defs active in the settlement; applying a punishing
law (curfew, weapons, ration, trade, theft, noise, visitors) costs the subject 1 group standing;
protective laws (contamination, intake, quarantine) cost nothing.

**The canonical cascade (ECON-01)** fires end-to-end from one injury, every hop citing its rule
(core pack `cascade/economy.yaml`; `~>` = scheduled, fires later at depth 0 — CAS-06):
```
worker injured (arm function loss >= 1)   CAS-001 ~> SHIFT_MISSED at the next shift start
shift missed                              CAS-002 -> ROLE_ASSIGNED cover (covering_for)
cover leaves their own post               CAS-003 -> that workplace efficiency -0.25
pump cycle leaves < 3 days of water       CAS-004 -> SHORTAGE water
shortage                                  CAS-005 -> RATION_CHANGE -1
ration cut to <= 2                        CAS-006 -> TENSION_CHANGE +10 (heads of households with
                                                     dependents -> the leadership)
                                                  ~> LOYALTY_CHECK for the worst-hit head (+1 h)
next daily draw at ration <= 2            STL-03  -> SETTLEMENT_CHANGE morale -1
```
Worked timeline (fixture `pump_settlement`, Hal's arm cut at 05:00): 06:00 Hal misses the day
shift, Ben comes off the night shift to cover, and his own post — the pump — drops to 0.75, so the
06:00 cycle makes 23 water instead of 31; 07:00 the draw takes 62 (153 left); 18:00 the day cycle
makes 23 → 176 water (2.84 days) → shortage → ration 3 → 2 → tension for six heads → 19:00 Iris's
loyalty check; day 2 07:00 morale 5 → 4. The same world without the injury ends the day at 192
water (3.1 days) and nothing happens.

**Trade terms** (SOC-03): a settlement's trader is its non-human member with the best trade
skill. `trade_terms()` reads the group's standing toward the buyer (≤ −3 unwilling; −2 ×1.5;
−1 ×1.25; ≥ 2 ×0.9), the trader's own feelings (resentment ≥ 2 unwilling; trust ≤ −2 ×1.25) and
what the trader *believes* about the buyer (a believed theft claim at confidence ≥ 2 unwilling,
at 1 ×1.5), and returns the reasons as plain sentences.

### 2.5 Group dynamics (GRP-01..12, STAND-01..02, `society/group.py`, `mind/mind.py`)
- **Tension** is directional, per actor or group toward an actor or group (0–100, boiling point
  70). Crossing the boiling point upward is an `ESCALATION` (form `verbal` in P9; physical forms
  from dossiers arrive with doctrine, P10) and adds 1 resentment toward the other side — for a
  group, its leader — and (B6, fidelity C06) a grudge the person now carries, "Things between them
  and me are about to boil over": what they do about it is their own decision, made like any
  other (never for the player, whose feelings are the player's). Tension untouched for a day
  decays by 5.
- **Animosity at work**: for each crew pair where one resents the other at ≥ 2, the one who
  resents rolls an I check against resistance = resentment, situation from their current Resolve.
  `fail` → the cycle's output ×0.9 and +10 tension; `break` → ×0.75 and +20 tension. The PC never
  rolls for this. The roll costs composure and execution only: no die ever chooses a refusal,
  sabotage, a betrayal or a change of values (C06).
- **Drift without the PC** (SOC-02): once a day, every pair of non-human members who share a
  household, a workplace or a friendship drifts, one axis step at a time — a sour tie (resentment
  ≥ 1 or trust ≤ −1) may sour further (30 %), a healthy tie may gain trust (25 %) and housemates
  affection (20 %), never past +2. Short rations (≤ 2) add 5 tension along every tie that holds resentment, each day.
- **Loyalty vs survival**: `defection_pressure` is the sum of plain terms — grievance (tension
  toward the group ÷ 20), deprivation (ration ≤ 2: 1, ≤ 1: 2), dependents going short, endangered
  dependents (thirst or hunger stage ≥ 3), viability (morale ≤ 3: 1, ≤ 1: 2), resentment of the
  leader, low standing — capped at 10. A loyalty check compares it with the dossier's risk
  threshold: `stays`, `wavering` (one below) or `plans_to_leave`, which opens a *plan* the actor
  holds. Crossing the threshold starts planning, never an instant betrayal; leaving is P10. The
  group day re-checks anyone within one of their threshold, at most every 3 days.
- **Standing** — the group's memory of a person (−5..+5) — lives in `group_standing`; laws and,
  from P10, deeds move it; it feeds trade and pressure.
- Leadership challenges, splintering, coalitions, reconciliation and **faction doctrine** (rules
  of engagement for organised force) would ride on the same tension and pressure numbers; they are
  backlog, not v1 (DECISIONS D-49). P10 brings leaving a group (§3: people who meant to leave go).

### 2.6 The coupling matrix is the P9 test plan

| Rule | Statement |
|---|---|
| ECON-01 | One injured worker reaches the settlement's rations, its households' tension and its morale with nothing scripted but the injury: every hop is a cascade rule or a settlement clock, cites its rule and names its cause (the chain in §2.4). |
| SOC-01 | Worldgen seeds each settlement's relationship matrix about 20 % positive, 60 % strangers and 20 % rivals (P10, WG6). |
| SOC-02 | Relationships between non-player people change while the PC is nowhere near: daily drift along households, crews and friendships, grudges souring, strain under short rations (§2.5). |
| SOC-03 | A rumour reaches trade: what a settlement's trader has heard and believes about a buyer changes the price or ends the deal (`trade_terms`, §2.4, §6). |

A body's condition → shifts → stores → rations → morale → loyalty; a death → household, grief,
vacancy (CAS-007); a law → costs on the options of whoever knows it, and standing for everyone under it; a rumour → trust,
trade willingness, who is believed later (CAS-018, SOC-03). Weather's couplings (travel time,
noise floor, visibility, work stalls, infected activity) arrive with weather in P10. **P9 is done
when one injured worker demonstrably reaches morale (`test_econ_chain.py`), relationships drift
with the PC absent (`test_group.py`), and one rumour demonstrably reaches trade
(`test_rumours.py`).**

### 2.7 How the society runs
Nothing in `society/` ticks by itself. A settlement's clocks are ordinary `event_queue` rows —
`SETTLEMENT_DAY` (07:00), `PRODUCTION_CYCLE` (per workplace), `GROUP_DAY` (20:00),
`ROUTINE_STEP` (per person) — started once by `turn.timers.seed_society` at stage 0 of every turn
and fired by `turn.timers` like every other timer, each followed by a cascade sweep over what the
handler committed. These are **background** queue types (`kernel.clock.BACKGROUND_QUEUE_TYPES`):
they fire inside the PC's windows but never cut a condition-ended window short (HOR-01), so
"I wait and watch the yard" still lasts its 8 hours. `turn.timers.run_offscreen` is the off-screen
step — 6-hour windows (`WorldRules.offscreen_tick_h`) of seed → fire due timers → progress every
living body's needs → advance the clock — used by tests and, from P10, by travel and long waits.
A world with no settlements (every P7 scenario) runs exactly as it did before P9.
People away on an outing skip their timetable (ROUT-06 'away', P10) — otherwise the routine
would walk them home in the middle of it.

### 2.8 Factions that do more than hold ground (P10) — the Ghosts (`world/factions.py`, FAC-01..06)
A faction record may carry a `behaviour` block (09_CONTENT_PACKS §3): an enclave, a council, a route
watch, a DECON doctrine. The core pack's Ghosts (Ghosts_6) have all four; any pack can give another
faction any of them.
- **The enclave** (FAC-01): the faction lives sealed underground — the Depot, one settlement of many
  thousands behind a single locked gate (worldgen places it in an industrial district when there is
  one). It is never the home settlement and never a placement faction; the crowd presses its gate and
  nothing more (a breach never happens, and the gate never gives way to a crowd, INF-13). In
  lockdown nobody leaves on an outing.
- **The council** (FAC-02): the seats — five Top Hats (Black, Gray, White, Red, Blue); the Black Top
  Hat leads — meet every seven days at 20:00 for two hours in the council room. Seat holders are real
  generated people; their names are each world's own (Ghosts_6 leaves them open). The Front Man
  (about forty) is the face outsiders deal with and is not a seat of the council. A council does not
  go scavenging. `in_session` says whether a meeting is under way — "in the middle of a meeting".
- **The route watch** (FAC-03): the moment a Mega Horde forms, the watch reports it (days before the
  first birds) and every seat holder learns it is coming; when it begins its passage through the
  region the enclave seals (lockdown), and opens again when it is gone.
- **DECON** (FAC-04/05): a Ghost killed by a human hand is taken to the next meeting. The council
  sends a team (five operators, materialised from the enclave's own counted people, FAC-06) to the
  killer. Off screen the killer dies and the body is left with the smile mark; on screen, the team
  walks in and hunts — the player sees them coming, and every Ghost they kill is taken to the next
  meeting too. A death by the infected orders nothing.

## 3. The world's day (P10) — "the world moves without you"

The contracts are `world/worldmove.py` (WORLD-02..06, OPS-01..08), `world/traces.py`
(TRACE-01..06), `world/decay.py` (WEAR-01..04) and `world/factions.py`; the numbers are
`WorldRules`. Nothing here ticks by itself (WORLD-02): the world's clock is one `WORLD_DAY` queue row
a day at `world_hour` (04:00), started by `turn.timers.seed_world` and fired in a turn's window or
by the off-screen step (`turn.timers.run_offscreen`) alike. A hand-made scenario without a
`world_params` row gets none of it. The day, in order: the weather (and rain washing marks out in
the open) → the deaths nobody on screen saw are noticed → operations are planned → people who meant
to leave go → things wear → the infected's day → the hordes' day → the next WORLD_DAY.

**The active area is the turn's** (WORLD-04): off-screen code never kills, moves or sends away a
body that stands where the player could see it happen — the turn simulates that. (Infected bodies
are the exception: their steps are the same physics on screen and off, §5.)

**Nobody dies of a lottery** (fidelity C01; WORLD-05). There is no daily death roll. People die of
what happens to them: wounds and illness running their course, thirst and hunger when the water is
gone (`physical.bodies.progress`, every turn and every off-screen step), what meets them on an
outing, raids, the infected — and, for the unnamed, privation in a settlement that has run dry. A
death nobody on screen saw is noticed once, at the next world day (`OFFSCREEN_DEATH`): a stain where
it happened, grief among those who knew, talk among those who would hear. Named characters are not
protected during play; worldgen's plausibility protection is a worldgen-only rule.

**Outings** (OPS-01..08). Each day, each settlement off screen may send one party out — scavenging
(twice as likely when it is short of something), a patrol along one of its roads, or a trade run to
another settlement — crewed by free, able, living members (never the player, never a council's seat
holders, never anyone already out, never from a settlement in lockdown). A hostile band with two or
more free members may raid a settlement. The party walks to its district's hub, out along the road
(`op_leg_h` hours), stays (`op_dwell_h`), and comes home:
- the dead where they go hurt them in proportion to how thick they are there (a cleared district is
  safe); a bleeding wound is packed on the spot and the party turns for home; at home a significant
  wound is sutured while the settlement has medicine (OPS-07);
- a scavenging party lays out a building nobody has entered yet (GEO-03), carries off up to three
  loose things, leaves boot prints (and a gap on the shelf where it took something), and with luck
  brings home 2–8 food and water each; a patrol leaves a loose line of boot prints; a trade run swaps
  a tenth of what its settlement has most of for as much of the other; a raid that gets in takes a
  tenth to a quarter of the target's food and water, leaves a forced door and blood, costs morale
  and leaves the target's people a grudge — one that fails leaves a raider shot.
Every mark comes from something that happened (C11): there is no quota of traces, and no clue is
guaranteed to last.

**Traces** (TRACE-01..06). A trace is what someone can perceive of something that happened while
they were not there. Each has a lifetime by kind in the open (tracks 2 days, blood 7, corpse 30,
missing stock 14, damage 180, graffiti a year), four times as long under a roof; rain, a storm or
snow erase exposed tracks, blood and smoke at once; a carved name or a grave is locked and never
fades. People see the marks where they stand when there is light enough — as their own percepts,
never by reading the table (TRACE-05) — and the narrator never writes "while you were gone"
(WORLD-06).

## 4. Wear, not forgetting (P10; fidelity C02 — replaces the salvaged Memory Fade)

The world does not forget; minds do (`mind.retrieval`). Nothing is deleted because the player was
away or because it seemed unimportant — there are no scores, tiers or location overhauls. Things
change because something happened to them (WEAR-01..04, `DecayRules`): a gun left in the street
rusts on every wet day, paper turns to pulp and falls apart, cloth and leather rot, food goes off
after its spoil days wherever it is — in a pack or on a shelf. A mark fades on its own clock (§3).
What a scavenger takes, a scavenger who exists took. Every change is an event, so the whole history
of the world stays readable and replayable.

## 5. The infected (P10; canon: Lore v1.0 + CMG §42, Lore v2 for the wet strain)

The contracts are `world/infected.py` (INF-01..13), `world/hordes.py` (HRD-01..18) and the P10
parts of `physical/bodies.py`; the numbers are `InfectedRules` and `HordeRules`.

### 5.1 Levels of detail — the dead are counted, and they are finite (fidelity §5, E01–E03, W04)
The dead exist in four forms and pass between them; none is made or lost on the way:
- **Bodies** where the player is: infected bodies simulated step by step (`INFECTED_STEP` timers,
  the same rules on screen and off, INF-12).
- **Pools**: per district and type, how many dead are active and how many stand dormant — a
  district's dead nobody has met yet. Worldgen fills them from the district's kind and the world's
  parameters (a downtown holds thousands, the wilds a few dozen).
- **Hordes**: counted crowds walking hub to hub along the roads.
- **The exterior**: four zones past the region's edge (north, east, south, west), each one huge pool
  — the rest of the country's dead, large but finite (W04).
The first time someone arrives in a place, some of its district's dead become bodies there
(INF-11, `populate`: a place's share, most of them still dormant in a mature world) — taken from the
pool. A pool grows only from real sources: stragglers, a crowd that breaks up or passes through,
bodies folding back, the district's own dead rising. A cleared district stays clear until dead that
exist walk in. The **census** (`hordes.census`) adds it all up; the total changes only by the dead
rising and by bodies destroyed (HRD-15) — the P11 release audit checks exactly that.

**Back into the count** (HRD-18, fidelity F04 demotion; D-67). When the contact is over, a body
that is nobody in particular folds back into its crowd's count — or its district's, when the crowd
is gone: one taken from a count, unhurt, going nowhere of its own (walking with its crowd, or with
no target at all), holding and held by nobody, where nobody alive stands and outside the active
area. A hurt one keeps its wounds and stays a body; so do a corpse that got up, a scenario's body
and a cheat's; and one hunting someone or drawn by a noise keeps walking until it gets there — the
dead drawn by a shot three streets away still arrive. The body's record stays (its history is
whole); only its place in the world goes (`DEMATERIALIZE`), and a later contact takes a new body
from the count. A loud noise holds its neighbourhood in the moment for ten minutes of world time
(SEL-01, D-68), not for the rest of a turn that may run off screen for days. This is what keeps a
Mega Horde next to a living player finite in bodies: the street stays full while the player can see
it, and the dead who walk on out of sight go back into the crowd.

### 5.2 Bodies up close
- Types (stable ids): Shambler, Crawler, Runner (driven by code, no mind) and the Lurker (alive,
  with a dossier: an Actor, not driven here). States — dormant, starved, overfed, injured — apply
  across types (INF-01).
- **Senses** (INF-02): hearing threshold by type plus each state's shift. Shamblers and Crawlers see
  only motion within 4 m (something that moved, or started an action that moves the body, in the
  last 10 s — starting to watch, wait, keep guard, hide or talk is standing still, `STILL_VERBS`:
  the one way past a Shambler at arm's length); Runners see any shape within 12 m. Nobody is seen
  through a wall; a sleeper lies in plain view; the dead and the unconscious are not prey.
- **Seen coming** (REACT-01, P10): anyone who sees one of the dead move to within 20 m reacts, and
  the player's watch ends there — the dead walking up are always news (D-65).
- **What draws them** (INF-09): a sound above its threshold sets it walking toward the place of the
  sound; prey in reach beats a noise elsewhere; drawn to where it already stands, it looks around.
- **Energy by time** (INF-03): being active costs one energy per minute for a Shambler (two minutes
  for a Crawler, 20 s for a Runner) — an hour banging on a door tires it as much as an hour walking;
  standing still costs nothing. At 0 it goes dormant ("a statue") and forgets its target; a
  stimulus reboots it; a bite that lands feeds it. Starved bodies slow down and listen harder;
  overfed ones mostly let go and walk off.
- **Doors** (INF-13): a lone body bangs on a closed door and never breaks in. Three or more leaning
  on it count its strain a minute at a time; a plain door holds 30 minutes (a window 10, a gate 45),
  each barricade level another 30, each point of lock quality another 15. Damage 1–3 shows how near it
  is to giving way; then it gives, loudly. Quiet survivors behind a strong door outlast a small
  crowd; noise inside wakes it.
- **The dead rise** (INF-04): a person who dies with the brain and upper spine intact gets up again
  as a NEW body where the corpse lay, holding what it held — the plain dead through the cold start
  (66–78 h later, as a Shambler or a Crawler), a wet host dead of the strain after 10–14 h as a
  Runner. A destroyed head stays down. A Runner slows into a Shambler or a Crawler after 20–40 days,
  never the reverse (INF-10). Everyone who knew the dead person sees "what was left of <name>".
- Infected never hunt infected (INF-05); a Lurker-to-be past its first stage is never a target
  (INF-06, CMG §42 hard rule); a wet host three weeks in is not hunted by sight (INF-07). Quirks are
  seeded per body (INF-08): the same world makes the same body with the same quirks.
- **Gore camouflage** (INF-14, the owner's F1b): a living body caked in the gore of the dead
  (`bodies.gore` 4 or more) moves among them as one of them — the common dead do not pick it out,
  until it gives itself away within the last 30 s: a sound of its own of 55 dB or more (a run, a
  strike, a shot, a normal voice; a whisper or a low voice is not) or a hand on one of them. Sound
  still draws them to where it is, and one already hunting it keeps on. A Lurker reads heat
  straight through it (CODEX). The dead do not track by smell (their lore's false belief); people
  do — whoever wears the dead reeks of them (sense.olfaction), and the fluids carry the wet strain
  (D-77): smearing yourself with them is an exposure (F1c, action.effects smear), and the rain takes
  the gore off you in the open (physical.bodies LOOK-08).
- **They eat people alive** (INF-15..19, the owner's I1, D-85). The dead do not bite and wander
  off, and they do not go for the kill: once one has hold of someone it does not let go (the
  overfed only fumble before they have you), and it bites every step — never the head or the
  neck, the first bite deep, every one after tearing flesh away — until the person dies of it,
  slowly, conscious for most of it. Every bite on a conscious person makes them scream (90 dB);
  the scream pulls every other one of the dead in the place (within 30 m) onto them, and carries
  beyond like any sound. Any number can hold and eat one body. When the prey dies they stay on it
  and keep eating for 20 minutes, then drop what is left; a body bitten eight times or more never
  gets up. While one is eating, nothing else draws it off — whoever is left to them buys the rest
  a little time. They eat anything that moves the same way — a dog, a horse — but only people take
  the strain: an animal is never infected and never rises. What comes out of them fouls water: a
  bottle or canteen lying within a metre of a feeding, or of one of them when it goes down, carries
  the strain for good; meat butchered from something they fed on carries it too (a lasting mark;
  eating or drinking it is an exposure, `tainted_food` / `tainted_water`). Everyone who sees a bite
  is worn down by it (CAS-024), and the narrator does not look away — except from a child's body.

### 5.3 Crowds, and the Mega Horde (HRD-03..17)
- **Drift**: a district with enough active dead sometimes sends a crowd off to a neighbouring hub
  (more often when the world's horde pressure is high); it mills there for hours, then scatters into
  that district's pool.
- **Drawn**: a sound of 130 dB or more (an explosion, an alarm) draws a share of its district's dead
  to it, arriving after half an hour.
- **Pressing**: where a crowd stops at a settlement, it presses on it; a crowd big enough for the
  settlement's defences breaks in — unnamed people die, named people there may be bitten. An
  enclave's gate is never breached (§2.8).
- **Rallying**: at every hub a moving crowd leaves stragglers behind and picks up a share of the
  district's active dead.
- **In sight** (HRD-07): where the player is, a crowd shows as bodies — up to 40 of one crowd in a
  place. A walking crowd's bodies follow it down the road; a milling crowd's stand where they are
  and fill the street, and it fills the place up again every 5 minutes while it is in sight (D-68).
- **The Mega Horde** — the end-game event. Rarely, and more likely the longer the run goes (the
  chance ramps up over the first 60 days, scaled by difficulty and horde pressure), the country's
  dead rally in one of the exterior zones: tens of thousands, up to hundreds of thousands at the
  hardest difficulties. It is seen coming for days (3–10): a week out, whole flocks of birds go over
  heading away; five days out, talk of it reaches the settlements nearest its road; two days out, a
  low roar far off never stops — and a faction with a route watch reports it before any of that
  (§2.8). When it arrives it walks through the region district by district; each district it
  is in never goes quiet (ambient 85 dB) and every street is full — going outside is not survivable
  while it passes. It takes days to pass (20 000 a day through one district); doors are pressed and
  the weakest give. Then it leaves by another road, leaving stragglers and the dead it made. It
  obeys every rule above: it is counted, finite, and made of dead that already existed.

### 5.4 The wet strain's living spreaders (Lore v2; pathways content)
A bitten host lives for about four weeks. From about the third day their saliva infects: a bottle
they drank from carries it for 12 hours (`mouth_contact_item` exposure; everyone knows somebody who
was killed by a shared bottle). From the second week the spreader's tells show to anyone who looks
closely (within 3 m, a clear look), and in the fourth the fever too. In the third week the urge to pass it
on becomes a compulsion: code — not the host's own reasoning — makes them offer food or drink from
their mouth now and then (an involuntary act, at most every 10 minutes; never the player's
character, whose hands stay the player's). The fourth week kills; the host rises as a Runner.
Pathways: air (everyone; behavioural), wet (bite, saliva), cold start (the unbitten dead), lurker
deep (slash and leave; timeline `proposed` until the owner confirms it). **No cure.**

**As the owner told it (W1, D-77, D-80).** From day three EVERY fluid of a host carries the strain —
blood, saliva, mucus — and the dead's fluids too (`physical.bodies.contagious`): whoever treats a
host's wound has their blood on the hands (`fluid_contact`), a blow that opens one up splashes it
into the attacker's eyes and mouth (`fluid_splash`), food a host ate from carries it like a bottle.
The urge is not to share but to **contaminate**: to spit into water and food, and into the mouths of
people asleep (`mouth_contact_direct`) — sleeper first, then handing over what their mouth touched,
then spitting into water or food at hand. In the second week it only wants to (an 'urge' on record;
holding back drains Resolve); from the third it happens, code-owned, and the host is sickened by
what it did (stress, `self_disgust`); and it comes ever more often — the gap shrinks with the hours
(10 minutes at two weeks, 5 at four, never under 2). The player's character is not exempt any more:
what you type mostly happens, but from the third week a share of your actions (1 in 5, then 2 in
5) comes out as the urge instead, and the story says it was not your choice. The dead pay a
week-three host less mind, not none: they see it only within half their range (INF-07).

## 6. Information spread (P9 rumours; the other channels as noted)

Channels: exact witness · partial witness · overhearing · failed overhearing (P3–P5 perception) ·
visual suspicion · rumour (P9) · second-hand report · lie (P6 firewall) · conflicting accounts ·
secret · faction intelligence · radio · public knowledge (P10). INFO-01: information is neither
universally known nor confined to the conversation partner.

**Rumours** (`world/rumours.py`, INFO-01..07). A rumour is a proposition passed from mind to mind —
"X claims Y", never a truth (INFO-03). It starts with a *seed*: someone who saw or overheard it
(provenance `overheard`, confidence 3 by default; core CAS-012 seeds one in whoever saw someone take
what they know belongs to another — B6, the `theft_witnesses_of` selector —,
CAS-013 from an off-screen death). Every hop after that is **told**, through the single knowledge
writer (`mind.perception.grant`): the listener gets a speech percept and a claim holding with
provenance `told_by:<teller>` and confidence one lower than the teller's (INFO-02; SKULL-05 — C
heard it from B, not from A). The words use the listener's own word for everyone ("A man took what
was not theirs." until they learn his name). The listener believes it unless they distrust the
teller (trust ≤ −2). Confidence 0 is held but never passed on.

At the group day each non-human holder tells at most 2 of their contacts a day — household,
work crew, friends — the closest first, never the subject and never someone who already holds it;
a rumour older than 14 days is no longer passed on (INFO-05). Hearing from someone you believe that
a person steals costs that person 1 trust (CAS-018), and a trader who has heard it charges more or
will not deal (SOC-03). The PC hears gossip like anyone, and it appears in the journal.

**Distortion** (INFO-06): when a holder retells a fresh rumour in the quiet hours (§7), one
`RUMOUR_DISTORT` call may drop a detail, shift an attribution, sharpen an emotion or add an
inference — never invent who is in it (a retelling that names a person or place the holder does not
know is refused, and the holder passes the words on as they heard them). In P9 the words pass on exactly and `rumours.distortions` stays `[]`.
**Horde talk** (P10): a rumour may be about a place — 'horde_coming' — seeded by the Mega Horde's
signs and by a route watch's report (§5.3, §2.8), and passed on like any other.

## 7. The quiet hours (P10; `service/background.py`, BG-01..07; Actor Spec AC12, fidelity C07)

People think between moments. After a turn's result is on screen, while the player reads, the
engine runs the jobs the turn boundary owes: **reflection** (someone who lived through something
that mattered — a salient memory or an anchor — or who slept on an ordinary day draws a lesson,
changes a plan, forms a goal or a grudge; at most two a boundary) and **retelling** (a fresh rumour's
holders put it in their own words; at most four). Which jobs a boundary has is a function of the
world as the turn left it, never of the player's reading speed (BG-07): before the next move the turn
first finishes everything still owed ("Everyone else catches up…", with its own loading bar), so a
player who answers at once and one who waits an hour get the same people thinking about the same
things. A job cancelled mid-call (Load, Close, New life) leaves nothing behind and runs at the next
catch-up; a failed one is not asked twice at one boundary. The results are ordinary recorded events
and replay re-commits them from their payloads (BG-05), without a model call.
