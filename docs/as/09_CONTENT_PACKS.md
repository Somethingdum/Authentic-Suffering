# 09 — Content Packs: People, Factions, Lore, Items

Everything that makes a world is **content**: plain YAML and Markdown files in a folder you can
edit with any text editor. Code never hard-codes a person, a faction, an item or a law. The
contracts are `as_engine/src/as_engine/contracts/dossier.py` and `contracts/content.py`; the loader
is `content/pack.py` (P2); importers and dossier intake are `content/importers.py` (P12).

This document is for **you** (the author) as much as for the builder.

## 1. Where content lives

```
as_content/
  packs/
    core/                 ships with the game (canon infected, items, affordances, laws, the
                          Mafia Remnants, ten people, three playable characters)
    my_content/           yours — created on first import; the game never overwrites it
    <any other pack>/     e.g. ghosts/ once you dump your Ghost corpus in (§8)
  templates/              blank, commented records to copy (never loaded)
  _compiled/canon.sqlite  built by the compiler (git-ignored; rebuilt when packs change)
```

A pack is a folder with a `pack.yaml`. Packs load in dependency order (`depends_on`). A later pack
may **not** silently replace a record from an earlier one: it must list the ref under
`overrides:` in its manifest (CNT-03). Files and folders starting with `_` (for example `_drafts/`)
and `README.md` files are ignored, so drafts never leak into canon.

```yaml
# as_content/packs/my_content/pack.yaml
schema: as.pack.v1
id: my_content
name: My content
version: 1.0.0
description: People and places I wrote or imported.
depends_on: [core]
authors: [SomethingDum]
```

## 2. Folders and record kinds

| Folder | Record (contract) | Ref form | One file holds |
|---|---|---|---|
| `actors/` | `ActorDossier` | `<pack>:actor/<id>` | one person |
| `pcs/` | `PCDossier` (an ActorDossier + selection/worldgen fields) | `<pack>:pc/<id>` | one playable character |
| `factions/` | `FactionDossier` | `<pack>:faction/<id>` | one faction or group |
| `lore/` | `LoreEntry` (YAML front matter + Markdown body) | `<pack>:lore/<id>` | one entry |
| `items/` | `ItemDef` | `<pack>:item/<id>` | a list |
| `affordances/` | `AffordanceDef` | `<pack>:affordance/<id>` | a list |
| `infected/` | `InfectedTypeDef` / `InfectedStateDef` / `QuirkDef` (by `schema`) | type id | one or a list |
| `pathways/` | `InfectionPathwayDef` | pathway id | one |
| `cascade/` | `CascadeRuleDef` | `CAS-###` | a list |
| `laws/` | `LawDef` | `<pack>:law/<id>` | a list |
| `buildings/` | `BuildingArchetype` | `<pack>:building/<id>` | one |
| `loot/` | `LootTable` | `<pack>:loot/<id>` | a list |
| `names/` | `NameList` | `<pack>:names/<id>` | one |
| `style/` | `StyleRules` | `<pack>:style/<id>` | one |
| `ui/` | `QuipList` (P10: the loading bar's lines, §7.1) | `<pack>:quips/<id>` | one or a list |
| `cues.yaml` | `CueRegistry` | cue id | the pack's cue list |

Ids are lowercase `snake_case` (`^[a-z0-9][a-z0-9_]{1,63}$`), except infected type and quirk ids,
which keep their canon form (`ZOMBIE_ARCHETYPE_SHAMBLER01`) and never change once used (CNT-13).
Refs between records always use the `<pack>:<kind>/<id>` form, never runtime ids.

## 3. Writing a person (actor dossier)

A dossier must describe **a person, not a category**. The validator enforces the minimum
specificity that stops drift (CNT-10); these are the rules in words:

| Section | The minimum | Why |
|---|---|---|
| `identity` | name, age, sex, cohort, birthplace, before/now occupation, a one-line identity (10–140 chars) | cohort (pre-Fall adult, Fall child, post-Fall born) changes what they believe is normal |
| `appearance` | at least one distinguishing mark; how they move under stress; a habit or gesture; how they feel about how they look | the narrator can only describe what is recorded |
| `capability` | SPECIAL 1–10; skills with rank 1–3 **and evidence** ("three years as a ward nurse"); literacy and tech literacy 0–3 | skills gate which options exist for them — an untrained person is never offered a trained move |
| `motive` | motive, method, moral line (`will` / `wont`, plus machine tags in `wont_tags`), inner conflict, past wound, signature behaviour, risk threshold 1–10 with text, resource constraints | the moral line removes options before the model ever sees them |
| `persona` | public face vs private truth | lies and piercing need both |
| `traits` | at least two, each with manifests / triggers / causes / costs / example | a bare adjective is a category |
| `contradictions` | at least one belief A vs belief B, and when each wins | people are not consistent; this makes them consistent in *how* they are inconsistent |
| `decision_stack` | at least four layers, highest first, inversion conditions, a past example | what they do when priorities collide |
| `silence` | at least two situations when they go quiet, body when silent | silence is characterisation |
| `knowledge` | knows / does not know / knows but hides | seeds their beliefs at world start; *does not know* is for authoring checks and never reaches a prompt |
| `voice` | capsule (20–500 chars), ≥ 2 speech tendencies, **three example lines** — low stakes, under pressure, at the limit — **≥ 3 things they would never say**, profanity level | the single strongest defence against every character sounding the same |
| `social` | relations with history, dependents, guardians, memberships | dependents appear in their decisions as stakes |
| `life` | aspiration, current project, ≥ 1 fear, secrets with who knows and what exposure costs | goals and grudges grow from these |
| `disposition` | archetype prior, stance to strangers, default first-contact behaviour | first contact without a model call when they are far away |
| `days_since_fall_range` | optional `[min, max]` days since the Fall that this person's age and history fit | a nine-year-old who remembers the Fall cannot exist ten years later; worldgen skips people who do not fit (WG-34) |
| `writers_notes` | optional, **human only** | never shown to the model (IDN-02): guidance for whoever writes this person; what a note asks for belongs in the fields above. The model never writes this field |
| `depth_reference` | optional long Markdown | pulled only on demand, never by default |

Almost every field above becomes a line of the person's **identity card** (05 §2.1), in their
own words, every time they decide. Write them as tendencies and history, never as senses or
knowledge of the present: "keeps checking where everyone in the room is" is a habit, "knows where
everyone is without looking" would grant a sense nobody has. Where people are, what is in the gun and
who is lying come from what the person perceives, not from their dossier. Kept off the card:
`writers_notes`, `depth_reference`, *does not know*, who knows a secret, `disposition`, trained
responses (code's reflexes), `resource_constraints` (a count that goes stale) and the numbers.

Voice lines are the most important craft element. Rules that make them work:

- Write lines this person would actually say, in their dialect, at their education level.
- The three pressures must sound like the same person at three temperatures, not three people.
- `would_never_say` lists concrete phrasings, not categories: `"I'm sorry for your loss."` beats
  `"formal condolences"`.
- Never put a line in a dossier that quotes the player or another character — the echo guard
  (ECHO-01) will fight it every turn.

Starting state: `starting_inventory` (item grants with slots and nesting labels) and
`starting_loops` (goals, grudges, promises they begin with).

**Capability tags** give +2 on any check that lists them (07_RULES §1; one tag, never stacking).
The core pack's checks use: `parkour`, `climber` (climbing), `quiet_mover` (sneaking, hiding),
`locksmith` (picking), `breacher` (forcing doors), `calm_voice` (talking someone down),
`field_medic` (suturing), `marksman` (shooting), `heavy_hitter` (melee). A tag no check lists does
nothing — add it to an affordance's `check.tags` in your pack if you invent one.

**Belief cues** (`knowledge.cues`) are what a person *believes works* — `knows_headshot_rule`,
`knows_false_death`, `knows_noise_draws_dead` … (the list is `cues.yaml`). They gate options
(AFF-10): nobody tries to finish a downed infected unless they believe the dead get back up. Lore
beliefs can grant cues too, so a whole settlement can share a belief — right or wrong.

The core pack's ten people (`as_content/packs/core/actors/`) are complete, validated examples.
Start from `as_content/templates/actor_template.yaml`.

## 4. Writing a playable character (PC dossier)

A PC dossier is an actor dossier (the PC is processed exactly like everyone else, L12) plus:

```yaml
# excerpt of as_content/packs/core/pcs/addison_flores.yaml (CMG §61 Part XV carried)
card:
  display_name: Addison Flores               # must equal identity.name
  one_line_identity: Small, warm, physically competent runner-scavenger
  pc_card_survival: Gets to places others can't reach, trades what she finds
  pc_selection_note: Her trade economy requires someone to trade with. Extreme isolation breaks her.
primary_survival_method: mobility_scavenging_barter
faction_start_type: usually_adjacent        # always_in_faction | usually_adjacent | outsider_tied | outsider_solo
worldgen_bias: {climate_heat: 0.7, climate_moisture: 0.4, instability: -0.1, faction_density: 0.3, wildcard_level: 0.1}
plausibility_gate:
  method: mobility_scavenging_barter
  pass_any:
    - "faction_density >= 2"
    - "hostile_human <= 6"
    - "entity_type = faction and start_trust >= 4"
  hard_fail_all: "hostile_human >= 8 and faction_density <= 1 and social_order <= 1 and entity_type = none"
  patch_on_fail: Raise faction_density to 2; if entity_type is none, generate a procedural group at neutral.
start_constraints: {start_trust_range: [4, 7], start_relationship_default: neutral, faction_present_preferred: either}
locked_start_facts:
  - "Cannot drive (hard lock)."
  - "Glock 19, loaded, one magazine of 15 plus two spare magazines (30 rounds); treats every round as precious."
recap:
  origin_tag: "Started collapse at ~10, parkour kid. Has been moving ever since."
  provisional: [formative_incident_1, formative_incident_2, unresolved_complication, open_ambiguity]
```

`motive` and `persona` may be left out for a PC: you supply those by playing. `behavior_law`
(CMG §54 — approach, topic handling, risk/flight, plan carry, distortion, pressure, knowledge
boundary, performance) is optional but strongly recommended: it is what "Say it my way" uses to
turn your idea into the character's own words, and what colours the manner of everything they do.
There is no separate PC template: start from `as_content/templates/actor_template.yaml` and add
the fields above (`addison_flores.yaml` is the reference). The plausibility
gate's expressions use the grammar in `world/worldgen/conditions.py`
(`<parameter> <op> <number>` joined by `and`); a gate that does not parse is an error at load
(CNT-09), not a surprise at world generation.

The card appears in the New Life wizard exactly in the Codex Master Guide §61 format:
`NAME — identity / Survives by / Starts as / Note`.

## 5. Writing a faction

```yaml
schema: as.faction.v1
id: mafia_remnants
name: The Mafia Remnants
kind: faction              # 'faction' = canonical mega-entity; 'group' = local/procedural
one_line: ...
wants: ...                 # what they actually want, under the stated purpose
stated_purpose: ...
methods: ...
will_not_do: [...]
resources_have: [...]
resources_need: [...]
pressure: ...
leaders: [{title: Don, role: ..., actor: core:actor/...}]
how_leadership_is_contested: ...
fault_lines: [...]
relations: [{faction: <ref>, stance: wary, history: ...}]
doctrine:                  # how their armed people behave — by rule, not by mood
  challenge_procedure: ...
  escalation_ladder: [..., ...]
  treatment_of_unknowns: ...
  treatment_of_visibly_sick: ...
  prisoner_policy: ...
  intake_screening: [...]   # judged by the officer's traits, NEVER by a roll (L7)
laws: [core:law/...]
presence: {regional_reach: ..., population_baseline: 400, presence_conditions: [...]}
belief_text: what ordinary survivors say about them
truth_text: what is actually true (engine only)
```

Start from `as_content/templates/faction_template.yaml`; `mafia_remnants.yaml` (a canonical
faction) and `delgados_crew.yaml` (a local group) are the worked examples.

Every faction needs **both** `truth_text` and `belief_text` (CNT-07): the world runs on the
truth; people talk from the belief. Doctrine is copied into the faction's groups at world start and
drives how their guards challenge strangers.

**Seats and behaviour** (P10, `world/factions.py`). A leader may name a `seat` (a slug) and an `age`
range: worldgen then makes a person for that office in the faction's settlement (the first leader
always leads; each other seat gets its own generated holder, `group_members.role` = the seat), with
names each world makes up. A faction may carry a `behaviour` block — every part optional:

```yaml
behaviour:
  enclave:                 # the faction lives sealed: one settlement behind one locked gate
    population: [20000, 25000]
    zone_kinds: [industrial, highway, downtown]   # where it stands, in preference order
    name: The Depot
    gate: the steel gate in the depot yard
    description: ...
  council:                 # the seats that meet, and when
    seats: [black_top_hat, gray_top_hat, white_top_hat, red_top_hat, blue_top_hat]
    every_days: 7
    hour: 20
    hours: 2.0
  route_watch: true        # sees a Mega Horde coming and seals the enclave for its passage
  decon:                   # what happens to whoever kills one of theirs
    team: 5
    women_share: 0.35
    occupation: ...
    appearance: ...        # how a team member looks
    goal: "{target} killed one of ours. Deconstruct them and leave nothing that points home."
                           # {target} = how the team member describes the killer
    mark: ...              # the trace left on the body
```

`core/factions/ghosts.yaml` is the worked example (Ghosts_6). CNT-15 checks that the council's seats
are seats of the faction's leaders and that no two leaders share one.

## 6. Lore (two layers, always)

```markdown
---
schema: as.lore.v1
id: wet_strain
title: The wet strain
kind: infected
truth: Passed by bites and saliva. A living-spreader phase of about three weeks ...
beliefs:
  - {held_by: common, text: "A bite is a death sentence, full stop.", confidence: 3}
  - {held_by: "cohort:post_fall_born", text: "You can burn it out if you cut fast enough.", confidence: 2}
tags: [infection, canon_cmg_42]
---
Long-form notes for humans and for on-demand depth (never loaded into a prompt by default).
```

`truth` is what the engine simulates; each `beliefs` entry is what a group of people think
(`held_by`: `common`, a faction ref, `cohort:<cohort>` or `region:<tag>`), seeded into their
minds at world start with the stated confidence. A lore entry with no belief layer is an error
(LORE-01). Lore is **queried**, never dumped into prompts: a mind receives a lore belief only if it
holds it.

## 7. Items, affordances, laws, buildings, cascades

- **Items** carry mass (g), bulk (0–20), tags and exactly the property block their kind needs
  (`firearm`, `melee`, `container`, `food`, `water`, `medical`) — CNT-12.
- **Affordances** are the menu of things a body can attempt. Each names its verb, what it binds to,
  its range, its requirements (hands, held/carried tags, skill, belief cues, Resolve), moral tags,
  duration, noise, an optional check, and the **effect handler id** that resolves it (CNT-06, the
  list in `action/effects.py`). `label` is what an Actor reads; `ui_label` is what you see as a
  suggestion. Both are templates with `{target}`, `{destination}`, `{item}`, `{distance}`,
  `{duration}`. Say what an option is FOR: `requires.target_kinds` names the kinds of body it may
  bind (`[human]` for talking someone down, signalling, shielding — the dead are not people) and
  `requires.portal_kinds` the kinds of way (`[door, window, gate, …]` for closing, locking and
  barring — an `opening`, a gap in a fence or a ladder hole, has nothing to close). Without them an
  option binds any body or way in range, and the menu offers nonsense (P10, D-66).
- **Laws** put a price on options for the people who know them (per affordance tag, for
  members/visitors/all, with a `cost_note`) and carry a `belief_text` — how locals describe the
  law, and the note a person weighs when an effect has none of its own. A member of the
  settlement's group knows its laws; anyone else only the laws they were told. `forbid` and `cost`
  both add the note and neither removes the option (Actor v2, AFF-11): the world answers when a law
  is broken, the menu never pretends it cannot be.
- **Buildings** are room-by-room archetypes with anchors (cover/concealment 0–3), portals (doors,
  windows, walls — a wall is a portal with aperture 0 that only carries sound) and loot tables.
  Rooms are generated the first time anyone sees inside.
- **Cascade rules** are the declarative "and then" of the world: trigger event type + filters +
  preconditions → effects, each with a `CAS-###` id that every resulting event cites (G10). The
  canonical chain (injured worker → missed shift → cover → efficiency → shortage → rations →
  tension) is `core/cascade/economy.yaml`.
- **Infection pathways** list their stages in order. P10 adds two optional fields per stage: `felt`
  (one second-person sentence: what the host feels — never the stage's name; the narrator and the
  host's own packet use it) and `signs` (cue ids an observer who sees the host clearly and close
  gets). A pathway's `exposure` names the ways in with their chances (`mouth_contact_item` is the
  shared bottle).

### 7.1 The loading bar's lines (`ui/*.yaml`, P10)

```yaml
schema: as.quips.v1
id: core_quips
lines:
  turn:                    # the whole plan
    - Rolling.
  turn.minds:              # one of its phases
    - Minds at work.
  turn.minds.decide:       # a phase's sub-phase
    - Choosing between bad and worse.
```

The bar (10_UI §2.10) shows one line at a time under the step the job is on — the most specific key
first — a new one every 2.5 s, never one of the last three. Keys name a plan (`worldgen`, `turn`,
`quiet_hours`, `time_skip`), one of its phases or a phase's sub-phase exactly (CNT-16 lists the
valid ones from `service/progress.PLANS`). A later pack adds lines to a key; it never removes any.
**Write jokes about the step, never hints about the world**: a line is shown whatever is happening,
so it must not say who is near, what anyone thinks or how a roll went — and it should not just repeat
the step's own label, which is on screen beside it. Keep each line under 80 characters.

## 8. Importing

**Content screen → drop a file** (or `content_import`). What happens depends on the file:

| File | Result |
|---|---|
| `.yaml` / `.yml` / `.json` with a `schema:` line | validated and copied into `my_content` |
| `.md` with front matter | same; the Markdown body becomes `depth_reference` |
| SillyTavern / Chub character card: `.png` with a `chara` or `ccv3` text chunk, or `.json` with `spec: chara_card_v2/v3` | converted to a **draft** actor dossier (IMP-03): name → identity; description/personality → depth reference and trait/appearance seeds; scenario → knowledge; first message + example messages → up to three voice-line candidates (with `{{char}}`/`{{user}}` removed); lorebook entries → lore drafts |
| `.txt` / `.docx` / `.md` without front matter | not imported directly — use dossier intake (below) |

Every import that is not already complete lands in `my_content/_drafts/` with a sibling
`<name>.gaps.md` that lists, in plain language, exactly what is missing ("voice needs three lines:
low stakes, under pressure, at the limit"). Drafts never load (IMP-02). Move a finished draft out of
`_drafts/` to make it canon.

### 8.1 Dossier intake: "dump a big document in"

**Content screen → Turn a document into a record** (`intake_start`). Choose what it is (person,
playable character, faction, lore) and drop a `.md`, `.txt` or `.docx`.

1. The text is split into sections of at most ~12,000 tokens on heading boundaries.
2. Cascade (Lane A, long context) reads each section with the record's field list and fills what
   that section supports. It never invents: fields a section does not support stay empty.
3. Partial results merge field by field (later sections append to lists; they never overwrite a
   filled text field).
4. The merged draft is validated; problems go to the `.gaps.md` file.
5. Progress shows per section. **Nothing becomes canon until you move the draft into the pack**
   (IMP-06).

This is the mechanism for your Ghost faction corpus. The core pack deliberately ships **no** Ghost
faction — the first time the Ghosts enter a world should be when you feed them in yourself.

## 9. The validator (plain-language reports)

`as-engine content-check` or **Content screen → Check** runs every rule and names the file and the
field. The rules:

| Rule | Meaning |
|---|---|
| CNT-00 | the file is not valid YAML (or front matter), or its `schema` is not the folder's; an unknown folder is a warning with this code |
| CNT-01 | tooling exhaust or placeholders anywhere (`IGNORE_WHEN_COPYING`, `content_copy`, `Use code with caution`, `As an AI`, `[INSERT`, `TODO`, `lorem ipsum`) |
| CNT-02 | placeholder bodies: two people, factions, lore entries or quirks in one pack that become identical once digits are masked ("boilerplate plus an index") |
| CNT-03 | duplicate ids across packs without an explicit `overrides:` |
| CNT-04 | a ref that points at nothing (with a "Did you mean …?" when one is close) |
| CNT-05 | a cue (trained response, knowledge cue, lore belief cue, affordance belief cue, quirk trigger) missing from every cue registry |
| CNT-06 | an affordance whose effect id the engine does not have |
| CNT-07 | lore without truth and belief; a faction without truth_text and belief_text |
| CNT-08 | "sotry" anywhere (error); retired names from the GLOSSARY tombstones (warning) |
| CNT-09 | a plausibility expression that does not parse |
| CNT-10 | a record that does not match its contract — for people this includes the specificity minimums in §3 |
| CNT-11 | **the one hard line**: any person record whose age is under 18 and that contains a word from the minor-safety list is an error. It cannot be disabled by any setting, pack or cheat. The word list is `as_engine/content/safety.py`; the check does not read negation, so a child's record must not contain those words even to forbid them — the engine already enforces the line for you. |
| CNT-12 | an item missing the property block its kind requires, or carrying one that belongs to another kind |
| CNT-13 | an infected type listing a quirk that is not written for it, or an override that changes which creature a type or quirk id means |
| CNT-14 | a `generation: cheat` dossier outside a pack whose id starts with `cheat_` |
| CNT-15 | a faction's `behaviour.council.seats` naming a seat none of its leaders holds, or two leaders sharing one seat |
| CNT-16 | a quip key that names no plan, phase or sub-phase of the loading bar; a quip line that is empty or longer than 80 characters |

Example report lines:

```
actors/mara_voss.yaml: voice.would_never_say needs at least 3 lines (it has 1).
actors/june_okafor.yaml: social.relations[0].target 'core:actor/eli_vos' does not exist. Did you mean 'core:actor/eli_voss'?
affordances/combat.yaml: 'shoot_head' uses effect 'headshot', which the engine does not have.
```

## 10. Content changes after a run starts

A run stores the full dossier of every person in it (never trimmed, DOS-01), so editing
`mara_voss.yaml` after a run started does not change the Mara who already exists in that world —
she has lived since. New and changed items, affordances, laws and lore apply on the next load. If a
run uses something that no longer exists in any pack, loading refuses with the list of missing refs
(RUN-10) instead of guessing.

## 11. Canon and citations

Canon carried from the Codex Master Guide cites its section in the record's `tags`
(`canon_cmg_42`, `canon_cmg_61`) or in `cites:` on cascade rules. The Lore v1.0 infected taxonomy is
carried into `core/infected/` with its stable ids; the ~95 boilerplate quirk tags from the old lore
are **not** carried (they fail CNT-02 by construction); the core pack ships authored quirks only.
