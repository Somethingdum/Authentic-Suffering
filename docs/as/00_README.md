# Authentic Suffering — Build Spec v1 (Talemate edition)

**What this folder is.** The complete game design and build specification for *Authentic Suffering*
(AS): a local-model, AI-narrated survival RPG built as a fork of Talemate 0.39.0, driven by two
LM Studio models — **Nemotron Cascade 2 30B-A3B** (desktop, "Lane A") and **Nemotron 3.5 Lightning
30B-A3B** (laptop, "Lane B"). It is written for a coding agent working in **DeepSeek Harness (DSH)** on local LM Studio models,
which must be able to build the game from these files alone.

**Status:** Specified. Not built. The only legal status words until a phase gate passes are
"specified" and "not started" (plan §0.2 carried).

## Reading order for the builder

| # | File | Read when |
|---|---|---|
| 1 | `../../AGENTS.md` | Always loaded. The working rules. |
| 2 | `13_BUILD_ORDER.md` | Start of every session: find your phase and its task list. |
| 3 | `PROGRESS.md` | Start of every session: what is done, what is next. |
| 4 | `02_ARCHITECTURE.md` | Before your first line of code. |
| 5 | The doc for your phase (table in 13) | Before starting the phase. |
| 6 | The module docstrings under `as_engine/src/as_engine/` | Before implementing that module. They are the function-level contract. A snapshot lives in `reference/docstrings_v1.json`; `tools/as/gate.py --docstrings` shows any drift. |
| 7 | The contract tests for your phase | They are the executable form of this spec. |
| 8 | `RULES.md` | When a test or validator names a rule id. |

## Reading order for the human (you)

`01_GAME_DESIGN.md` → `10_UI.md` → `11_SETTINGS.md` → `CHEATS.md` → `09_CONTENT_PACKS.md` →
`DECISIONS.md`.

## Sources of law, in priority order

1. **This build spec** owns *how it is built* (module layout, build order, tests).
2. **The Authentic Suffering Rebuild Plan** (project doc `claude/Authentic_Suffering_Rebuild_Plan.md`)
   owns *what the game must be* (laws L1–L15, the four failures F1–F4, the salvage ledger).
   Every deviation is recorded in `DECISIONS.md` §Deviations. Nothing is silently changed.
3. **Codex Master Guide v4.2** owns canon (infection truth §42, factions §43, cheats §44, worldgen
   §61, dossier wants §14–15). Canon carried into content packs cites its section.
4. **Lore and World Building v1.0** owns the infected taxonomy (carried into `as_content/packs/core`).

Where two sources disagree, the disagreement is recorded in `DECISIONS.md` and the builder asks
the human (via `SPEC_ISSUES.md`) instead of choosing.

## Folder map

```
docs/as/
  00_README.md            this file
  01_GAME_DESIGN.md       what the player experiences
  02_ARCHITECTURE.md      Talemate host + as_engine; process, files, module map
  03_DATA_MODEL.md        run database, events, ids, knowledge core, hashing
  04_TURN_PIPELINE.md     the 20-stage turn transaction, worked trace, rollback, degradation
  05_ACTORS.md            dossiers, skull packets, affordances, Resolve, firewall, memory
  06_WORLD.md             worldgen, society, off-screen motion, infected ecology, decay, rumours
  07_RULES.md             checks, harm, needs, time, space, sound, sight, weapons, effect handlers
  08_LLM_CALLS.md         lanes, LM Studio, call table, schemas, thinking, repair, probes, bench
  09_CONTENT_PACKS.md     authoring dossiers/factions/lore/items; importing; dossier intake
  10_UI.md                the Play UI: screens, components, test ids, copy, protocol
  11_SETTINGS.md          per-run settings and install config
  12_TESTING.md           test tiers, scenario format, fake LM, gates, doctor
  13_BUILD_ORDER.md       phases P0–P12: tasks, gates, forbidden work
  CHEATS.md               the bonus document (cheat activation and command surface)
  DECISIONS.md            resolved open questions, deviations from the Rebuild Plan
  RULES.md                every rule id: statement, where enforced, which tests (generated)
  GLOSSARY.md             one spelling per concept + retired names
  PROGRESS.md             phase tracker (builder updates it through tools/as/gate.py)
  SPEC_ISSUES.md          where the builder reports suspected spec/test bugs
  CHANGELOG_AS.md         contract changes made during the build
  reference/docstrings_v1.json  snapshot of every contract docstring and documented signature
```
