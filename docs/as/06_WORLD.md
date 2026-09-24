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
the trouble… · Checking it all holds together…*

| Stage | Builds | Key rules |
|---|---|---|
| WG0 | parameters, plausibility gate + hard-fail protocol | CMG §61 QC-1..3, Part XII; enforced Bitch→Realism only |
| WG1 | zones (count by detail tier), routes with danger, building archetypes per zone kind | every zone reachable; ≥ 2 mutually exclusive routes between the start zone and one other |
| WG2 | causal history: code builds an event skeleton (kind, day, subjects, cause) from params; WORLDGEN_HISTORY (lane A, thinking) writes truth + belief text per event; structure fate: buildings that were defended, sealed or lucky get `places.held = 1` | WORLD-01: every settlement, faction posture and shortage cites ≥ 1 history event; history is causal, not decorative; the history horizon equals days-since-the-Fall, never a constant (WG-31); held buildings skip the interior Fall-damage pass at discovery (WG-32) |
| WG3 | canonical factions (presence rules, Part X) + procedural groups (`[dynamic] + [location type] + [rule or resource]`, ≤ 60 chars) | faction presence coherence (dominant needs density ≥ 6, active ≥ 3, peripheral ≥ 1) |
| WG4 | settlements, workplaces (water pump, kitchen, garden, workshop, clinic, watch, laundry, school), stores, laws | population baseline modulated by history (Batch-3 ruling #5) |
| WG5 | cohorts from a survivor pyramid; households | DEMO-01 bounds (§2.1); children are inhabitants (DEMO-02) |
| WG6 | Actors: pack actors first (protected), then generated detailed actors (WORLDGEN_ACTOR on both lanes in parallel, schema + validator + one targeted repair per failing section); relationship matrix 20 % positive / 60 % strangers / 20 % rivals (SOC-01); knowledge seeds → beliefs | hand-written characters cannot die in worldgen; if history would kill one, recalculate to explain survival (Batch-3 ruling #6) |
| WG7 | local laws per settlement (faction laws + params: curfew when hostile_human ≥ 6; weapons policy by social order; contamination/intake laws where factions have intake doctrine) | laws change the available options and their costs |
| — | **genesis snapshot** of the finished world, before any PC exists (`_worlds/<world_id>/genesis.sqlite`) | a world can be reused for a new run or shared as a file (RUN-09) |
| WG8 | PC placement (Part X), immediate contacts, opening pressure made of **real placed entities**, first objective; WORLDGEN_OPENING writes the text with citations; **PC survival history**: 3–5 history events with the PC as subject, each an anchor memory for the PC | QC-4: specific, non-trivial, reflects ≥ 1 A/B param, cites ≥ 1 placed entity; budgets 150/150/200/150 chars; WG-33: the PC starts with real memories and a reason for being alive |
| WG9 | invariants: ≥ 3 exploration magnets with breadcrumb chains (lead → risk → reward, with timers); ≥ 1 supply bottleneck with a credible lead; ≥ 1 lethal threat with ETA ≤ 2 hops; a death path ≤ 3 decisions, telegraphed; ≥ 2 mutually exclusive routes; no-repeat locks initialised; the 58-bit gate on genesis | continuous invariants re-asserted every in-game day by `world.worldmove` |

**Worldgen does not pre-script outcomes** (WG-30): it decides who people are, what happened and
what they face — never who betrays, dies, befriends the PC or becomes the villain.

**Detail tiers** (`tables.DETAIL_TIERS`): zones 3→8, places per zone 4→12, detailed actors 8→40,
LM-written dossiers 3→40, history events 6→30; estimated 3→60 minutes (shown before starting;
replaced by measured values after `bench`).

**Rooms are generated on first observation** (PLMP discovery, GEO-03) from building archetypes,
seeded by `layout:<place_id>`, and are permanent afterwards.
Buildings that did not hold through the Fall get the Fall-damage pass at discovery (damaged or open
exterior doors, picked-over loot, an "old damage" trace); held buildings keep their interiors (GEO-04).

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
condition_factor = 1.0 when machinery_condition >= 50, else 0.5 + machinery_condition / 100
spite            = the animosity result for this crew (2.5), 1.0 when nobody resents anybody
output[res]      = floor(base_output[res] × efficiency × staffed × condition_factor × spite)
```
Output goes into the settlement's stores (`STORES_CHANGE`); an unstaffed workplace records the
stall reason `unstaffed`. **Cover**: a missed shift pulls the least-worked qualified, able,
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
  group, its leader. Tension untouched for a day decays by 5.
- **Animosity at work**: for each crew pair where one resents the other at ≥ 2, the one who
  resents rolls an I check against resistance = resentment, situation from their current Resolve.
  `fail` → the cycle's output ×0.9 and +10 tension; `break` → ×0.75 and +20 tension. The PC never
  rolls for this.
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
  of engagement for organised force) ride on the same tension and pressure numbers and arrive with
  world motion (P10).

### 2.6 The coupling matrix is the P9 test plan

| Rule | Statement |
|---|---|
| ECON-01 | One injured worker reaches the settlement's rations, its households' tension and its morale with nothing scripted but the injury: every hop is a cascade rule or a settlement clock, cites its rule and names its cause (the chain in §2.4). |
| SOC-01 | Worldgen seeds each settlement's relationship matrix about 20 % positive, 60 % strangers and 20 % rivals (P10, WG6). |
| SOC-02 | Relationships between non-player people change while the PC is nowhere near: daily drift along households, crews and friendships, grudges souring, strain under short rations (§2.5). |
| SOC-03 | A rumour reaches trade: what a settlement's trader has heard and believes about a buyer changes the price or ends the deal (`trade_terms`, §2.4, §6). |

A body's condition → shifts → stores → rations → morale → loyalty; a death → household, grief,
vacancy (CAS-007); a law → options and standing for everyone under it; a rumour → trust,
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

## 3. Off-screen motion (P10) — "the world moves without you"

Producers with `next_due_at`: faction operations, settlement projects, trade runs, patrols, raids,
diplomacy, migration, scavenging trips, depletion, construction, leadership change, infrastructure
failure, recruitment, defection, epidemic. Places outside the active area tick every
`WorldRules.offscreen_tick_h` (6 h) at COLD fidelity (code only).

**Everybody dies (off-screen mortality).** Each COLD human draws a daily death risk
`base_daily_mortality[difficulty] × activity multiplier` (scavenging ×3, patrol ×2, sick/wounded
×5, child ×1.5, elder ×2); an `OFFSCREEN_DEATH` creates a corpse trace and a rumour seeded to the
people who would hear. Named characters are not exempt during play.

**Diegetic traces** (WORLD-03): the engine never says the world progressed — the world shows it.
Every off-screen event that could leave evidence registers a trace with a decay clock (tracks 2 d,
blood 7 d, corpse 30 d, graffiti 1 y, missing stock 14 d, damage 180 d). ≥ 70 % of off-screen
events leave a discoverable trace, and the narrator never writes "while you were gone" (lint).

## 4. Memory Fade (log decay, P10) — carried verbatim in shape

`SS = w1·narrative_weight + w2·location_importance + w3·player_recency + w4·object_type`
(weights 0.4/0.2/0.3/0.1). Tier 1 *graceful forgetting* (SS < 20: delete a trivial entry) · Tier 2
*environmental reclaim* (SS < 35, unsecured item in a public or dangerous place: delete + "another
survivor took it" event + trace) · Tier 3 *location overhaul* (unvisited 30 days, nothing active:
purge the place's deltas + a major world event: collapse, fire, occupation). **Persistence locks**:
a dead companion's weapon where they fell, quest-critical placements, everything inside a player
base, the stain where someone died, the hole in the wall from the argument. Every decay emits an
event — decay is replayable and is itself one of the world's strongest "it moved on" signals.

## 5. The infected (P10; canon: Lore v1.0 + CMG §42)

- Types (stable ids): `ZOMBIE_ARCHETYPE_SHAMBLER01`, `ZOMBIE_ARCHETYPE_CRAWLER01`,
  `ZOMBIE_VARIANT_ID_RUNNER01`, `ZOMBIE_VARIANT_ID_LURKER01`. States (dormant, starved, overfed,
  injured) apply across types.
- Perception: Shamblers hear (threshold per type) and see only motion contrast ≤ 3 m; Runners see
  shapes to ~15 m; Lurkers use thermal contrast in the dark.
- Energy: activity drains; 0 → dormant ("statue"), can reboot on stimulus.
- **"Dead" is a claim**: false death on catastrophic non-core trauma, reanimation after 6–14 h
  (Runners 8–16 h) if the brainstem/upper-spine junction is intact; true kill = destroy that
  junction or fully denature core tissue. Lurkers are alive and do not reanimate.
- Infected do not attack infected (except the rare Shambler bullying quirk); **baseline infected
  never attack a true Lurker-infected victim** (CMG §42 hard rule).
- Lifecycle: Runner → Shambler/Crawler allowed; never upward (CMG §42.17).
- **Infection pathways** (content `pathways/*.yaml`): air (everyone; behavioural), wet (bite/saliva:
  living-spreader phase weeks 1–3 with saliva infectivity from ~day 3 and growing compulsion,
  kill phase in week 4, death, rise after ~12 h), cold-start (unbitten dead with usable neural
  structures rise in ~3 days, only as Shambler/Crawler/dormant), lurker-deep (slash-and-leave;
  timeline marked `proposed` in the pack until you confirm it). **No cure.** Wounds from the wet
  strain may close deceptively well.
- Noise steering: any sound above an infected body's hearing threshold at its point sets its target
  toward the source (`INFECTED_DRIFT`); gunfire is remembered by the dead.
- Quirks are seeded per body (rng stream `quirks`): the same seed reproduces the same weird
  behaviour. The pack ships **authored** quirk variants only; the ~95 boilerplate tags from the old
  lore are not carried (CNT-02).
- Lurkers: Actors with generated dossiers, clans (ranks: scouts, hunters, butchers, sentinels,
  elders, rowdies), territory doctrine, learning ("every breach attempt becomes a lesson"),
  mimicry only from concealment and degrading under close pressure, two attack branches
  (infective slash-and-leave; paralytic capture only after winning the struggle).

## 6. Information spread (P9 rumours; the other channels as noted)

Channels: exact witness · partial witness · overhearing · failed overhearing (P3–P5 perception) ·
visual suspicion · rumour (P9) · second-hand report · lie (P6 firewall) · conflicting accounts ·
secret · faction intelligence · radio · public knowledge (P10). INFO-01: information is neither
universally known nor confined to the conversation partner.

**Rumours** (`world/rumours.py`, INFO-01..07). A rumour is a proposition passed from mind to mind —
"X claims Y", never a truth (INFO-03). It starts with a *seed*: someone who saw or overheard it
(provenance `overheard`, confidence 3 by default; core CAS-012 seeds one from a witnessed theft,
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

**Distortion** (INFO-06): one optional `RUMOUR_DISTORT` call per hop may drop a detail, shift an
attribution, sharpen an emotion or add an inference — never invent an entity. It needs background
cognition and arrives in P10; in P9 the words pass on exactly and `rumours.distortions` stays `[]`.
