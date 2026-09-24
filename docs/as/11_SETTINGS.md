# 11 — Settings

Two kinds of settings exist and they never mix:

| Kind | Stored in | Chosen | Contract |
|---|---|---|---|
| **Run settings** — how this life and this world work | the run's `meta.settings_json` | New Life wizard; some can change during play | `contracts/settings.py::RunSettings` |
| **Install config** — your machines, models and tuning | `as_config.yaml` next to the game | Connect screen / Settings → Models; editing the file | `contracts/settings.py::EngineConfig` |

Every mid-run change is a `SETTINGS_CHANGE` event (so replay reproduces it) and takes effect from
the next turn (SET-01). The rules numbers a run uses are frozen into `meta.rules_json` when the run
is created: editing `rules:` in `as_config.yaml` later changes **new** runs only (SET-03).

## 1. Run settings

### 1.1 Chosen once, at the start (locked for the run)

| Setting (UI label) | Field | Values (default **bold**) | What it does |
|---|---|---|---|
| **Difficulty** | `difficulty` | Bitch Mode · Easy · **Normal** · Realism · Actually Hell · Fuck You | Sets the "what hunts you" and "what still exists" bands, the simulation mechanics (snowball, warning slack, recovery slack), how many dead wait past the map's edges, and how likely and how big a Mega Horde is (`HordeRules`, 06 §5). Nobody dies by lottery: off-screen deaths come from what happens to people (D-52). Plausibility protection for your character applies from Bitch Mode through Realism only (CMG §61 QC-2). |
| **Era** | `era` | Early (weeks – ~1 year) · Established (1–4 years) · **Mature** (5+ years) | Constrains factions and social order; decides who exists (post-Fall-born people only in Mature) and what still works. |
| **Days since the Fall** | `days_since_fall` | blank = drawn inside the era's range; or a number | Exact world age. The history horizon equals this number (WG-31). It must fit your character's `days_since_fall_range` (WG-34); eras and values that cannot are not offered. |
| **World detail** | `world_detail` | Gotta go to work soon (~3 min) · Quick look (~7) · **Standard** (~15) · Settle in (~30) · I don't intend to use my laptop much today (~60) | Zones, places, detailed people, model-written dossiers and history events (`tables.DETAIL_TIERS`). The minutes are fixed estimates (`est_minutes`); the real time depends on your machines, and the loading bar shows the time left while the world is built (10 §2.4). |
| **Seed** | `seed` | blank = random | Fixes every code-side draw. It does **not** reproduce model-written text, so it cannot rebuild a world — use a world file for that (RUN-09). |
| **Save mode** | `save_mode` | **Free** · Ironman | Free: named saves, load, "new life here" after death. Ironman: only autosave and Continue; death ends the run (RUN-08). |
| **Packs** | `pack_ids` | **[core]** + any you add | Which content packs this world is built from. |

Difficulty descriptions (CMG §61 Part II, shown verbatim in the wizard):

| Tier | Description |
|---|---|
| Bitch Mode | The world is almost livable. Threats exist but rarely compound. For learning the system or narrative-first play. |
| Easy | Real danger, real consequences. Mistakes cost something. You have breathing room. |
| Normal | Survivable with consistent good decisions. Comfort is earned. Setbacks require active recovery. |
| Realism | The world will not forgive much. Every decision carries weight. Intended experience. Losses cascade. |
| Actually Hell | No mercy. Losses compound fast. You will die from things Normal makes manageable. |
| Fuck You | Slaughter mode. Not balanced. Not fair. Not intended for narrative play. |

### 1.2 Changeable during play (Settings → Gameplay)

| Setting (UI label) | Field | Values (default **bold**) | What it does |
|---|---|---|---|
| **Turn depth** | `turn_depth` | Quick (≈40 s, 1 deep thinker) · **Balanced** (≈75 s, 2) · Deep (≈150 s, 3) | Budget for how many people think with full reasoning each turn. People in immediate danger, spoken to, or fighting over something with you always think, even past the budget. Depth never changes what anyone can do or knows (LOD-01). |
| **Scene length** | `narration_length` | Short (80–180 words) · **Medium** (160–350) · Long (300–600) | Target prose length (lint band). |
| **Point of view** | `narration_person` | **Third person** ("Addison") · Second person ("you") | Narrator grammar only. |
| **Tense** | `narration_tense` | **Past** · Present | Narrator grammar only. |
| **Say it my way** | `pc_voice` | **Off** (your words are spoken exactly) · On (you give the idea; your character says it their way) | CMG §53 Dialogue Seed Protocol. The result is recorded as intact, softened, garbled or withheld. Never changes who you address or what you do. |
| **Intensity** | `intensity` | **Full** · Softer | Presentation only: Softer asks the narrator to describe gore and atrocity with less graphic detail. **Every fact still happens and is still remembered**; the simulation is identical (INT-01). The content charter's one hard line (no sexual content involving minors) is not a setting and applies at every intensity. |
| **Show dice** | `show_mechanics` | Off · **Summary** · Full | A small receipt under the scene ("Climb the fence: skilled +2, wet −1 → success with a cost"). Never inside the prose. Full adds every draw and modifier. |
| **Read aloud** | `read_aloud` | **Off** · On | Uses Talemate's text-to-speech agent for narration (P12). |
| **Developer mode** | `dev_mode` | **Off** · On | Shows the Developer panel (stage timings, every person's options and choice, events, gate bits, raw model traffic). It shows hidden information and changes nothing in the world. The Play UI puts this one under Settings → Advanced. |
| **Autosave slots** | `autosave_ring` | 1–50, **5** | Size of the autosave ring. |

### 1.3 Why these defaults

Normal + Mature + Standard is the tuned baseline: every `[SAND]` number is calibrated there first.
Third person past tense matches how the reference dossiers' voice lines are written. Summary dice
keep the rules legible without cluttering the story.

## 2. Install config (`as_config.yaml`)

Copy `as_config.example.yaml` to `as_config.yaml` (git-ignored). The Play UI's Models screen edits
the `lanes` section for you; everything else is for tuning.

```yaml
schema: as.config.v1
runs_dir: as_runs
content_dir: as_content/packs
compiled_dir: as_content/_compiled
lanes:
  A:
    name: Main model — Nemotron Cascade 2 30B-A3B
    base_url: http://localhost:1234/v1
    model: nemotron-cascade-2-30b-a3b
    max_concurrency: 1
    request_timeout_s: 240
    thinking_mode: native          # set by the probe: native | system_no_think | chat_template_kwargs | prefill_empty_think | none
    structured_mode: json_schema   # json_schema | prompt_only
    structured_with_thinking: unknown   # set by the probe
  B:
    name: Second model — Nemotron 3.5 Lightning 30B-A3B
    base_url: http://localhost:1234/v1   # via LM Link; or the laptop's own address
    model: nvidia-nemotron-3.5-lightning-30b-a3b
    max_concurrency: 1
background_cognition: true         # quiet-hours reflection between turns (05 §9.2)
# regimes:                         # per call class: lane, temperature, max_tokens, thinking, deadline_s
#   narration: {lane: A, temperature: 0.8, max_tokens: 1400, deadline_s: 90}
# hot_cognition: {lane: A, temperature: 0.7, max_tokens: 3000, thinking: true, deadline_s: 75}
# rules:                           # RulesConfig overrides — new runs only (SET-03)
#   scheduler: {turn_budget_s: {quick: 40, balanced: 75, deep: 150}}
#   society: {draw_hour: 7, group_hour: 20, shortage_days: 3, drift_friction: 0.3}   # P9 (06 §2)
#   world: {world_hour: 4, op_party: [2, 3], weather_change_chance: 0.35}            # P10 (06 §3)
#   infected: {bang_db: 70, push_min: 3, saliva_hours: 12}                           # P10 (06 §5)
#   hordes: {drift_chance: 0.15, draw_db: 130, mega_ramp_days: 60}                   # P10 (06 §5)
#   background: {max_reflections: 2, max_retellings: 4}                              # P10 (05 §9.2)
#   decay: {rust_per_wet_day: 1, rot_per_wet_day: 2}                                 # P10 (06 §4)
```

| Key | Meaning | Who changes it |
|---|---|---|
| `lanes.A/B.base_url`, `.model` | where each brain lives | Connect screen |
| `lanes.*.thinking_mode`, `structured_with_thinking` | how to switch thinking off, and whether JSON schemas work with thinking on | `tools/as/probe.py --write` (the Connect screen's Test button only checks that the model answers, how fast, and whether structured answers work) |
| `lanes.*.max_concurrency` | parallel requests per machine | you, after `bench` shows the machine copes |
| `regimes.<call_class>` | lane, sampling, token cap, deadline per call class (08 §4) | you (advanced; edit the file — the Play UI never changes regimes, because a regime change alters every later request and so breaks re-simulation, DET-02) |
| `hot_cognition` | the regime for deep-thinking people | you (advanced) |
| `rules` | every tunable number (`RulesConfig`; P9 adds `society`: daily needs by age band, ration multipliers, shortage and recovery days, draw and group hours, role skills, sleep windows, tension and drift numbers, rumour pace — `contracts/settings.py::SocietyRules`; P10 adds the table below). A group you name keeps its defaults for the numbers you leave out, but a table keyed by difficulty or era (for example `hordes.mega_daily_chance`) replaces the default table whole: give every key | you (advanced; new runs only) |
| `background_cognition` | allow reflection jobs while you read | Settings → Advanced (`config_set`) |

Unknown keys are errors with a plain message naming the key (CFG-02); a missing file means all
defaults (CFG-01).

### 2.1 The P10 rule groups (`contracts/settings.py`)

| Group | What it tunes | Read by |
|---|---|---|
| `world` (`WorldRules`) | the off-screen step's tick; how long marks last in the open and under a roof, and what rain washes out; the clock hour a generated world starts at and its daily tick (`world_hour`); the daily chance of each kind of outing, the crew's size, travel and dwell times; how long a plan to leave is carried before it is acted on; the daily chance the weather turns | `world.traces`, `world.worldmove`, `turn.timers` (06 §3–4) |
| `infected` (`InfectedRules`) | energy by time per type, feeding, starving and overfed thresholds, a dormant body's recovery; what counts as moving to their eyes; the step interval; banging on a door; a Runner's decline; when a week-3 wet host stops being hunted by sight; how many dead one place shows and how much each kind of place draws; quirks; a crowd pushing on a door (how many, how long each portal, barricade and lock hold); the wet strain's saliva window, how close its signs show, and the compulsion's cooldown | `world.infected` (06 §5) |
| `hordes` (`HordeRules`) | the dead past each map edge (per difficulty), the dormant, Runner and Crawler shares (per era), district density and how many a place shows; horde pace, milling, straggling and rallying; drift and noise-draw chances and sizes; breaches; the Mega Horde's chance (ramping over the run's first days), size, warning time, speed, throughput and noise | `world.hordes` (06 §5.3–5.4) |
| `background` (`BackgroundRules`) | what makes an experience material, how many ordinary ones a night's sleep needs, and how many reflections and retellings one turn boundary may hold | `service.background` (05 §9.2, 06 §7) |
| `decay` (`DecayRules`) | which kinds rust and rot, and how much condition a wet day in the open costs | `world.decay` (06 §4) |

Numbers marked `[SAND]` in the source are placeholders until play-testing or `bench`/`eval`
settles them (PROGRESS.md). Retired fields, read by nothing: `world.base_daily_mortality`,
`world.min_offscreen_trace_ratio` and `world.mortality_mult` (no death lottery and no trace quota,
D-52), and `decay.weights`, `decay.tier1_below`, `decay.tier2_below`, `decay.tier3_unvisited_days`
(no Memory Fade, D-53); they stay only so an older run's frozen rules still load.

## 3. Settings rules

| Rule | Statement |
|---|---|
| SET-01 | A mid-run settings change commits `SETTINGS_CHANGE` (payload: field, old, new) and applies from the next turn; re-simulation re-applies it at the same point (`service/session.change_settings`, `service/replay.resimulate`). Settings → Gameplay sends `settings_set`; the receipt and the Developer panel follow at once. |
| SET-02 | Locked settings (§1.1) cannot change after `run_new`; `config`/`view` never offer them. |
| SET-03 | A run uses the `RulesConfig` frozen in `meta.rules_json` at creation. |
| SET-04 | No setting changes what a body can do, what a mind knows, or any probability — except difficulty and save mode, which are world definitions chosen before the world exists. |
| INT-01 | Intensity changes narrator wording only; the committed events for the same inputs are byte-identical at Full and Softer. |
