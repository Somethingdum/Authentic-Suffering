# 03 — Data Model

The data model is **code**: `as_engine/src/as_engine/kernel/schema.sql` (DDL),
`kernel/ownership.py` (owners), `contracts/*.py` (pydantic). This document explains how they fit.

## 1. One file per run

`as_runs/<run_id>/world.sqlite`, WAL mode, foreign keys ON. A save is a consistent copy of that file
(`sqlite3` backup API) plus a manifest with its sha256. Content is NOT copied into the run: the run
stores `meta.content_hash` and the dossier baselines it instantiated (dossiers are never trimmed —
DOS-01), so a run keeps working if packs change later; on load the UI warns when the content hash
differs (09 §Content changes after a run starts).

## 2. Two kinds of table

| Kind | Tables | How they change | Replay |
|---|---|---|---|
| **World tables** | everything not listed below | ONLY through `Tx.commit_event(Event)`; each `WriteRecord` names its table; the event's `writer` must own it | Event-apply replay reproduces them (`world_state_hash`) |
| **Bookkeeping** | `counters`, `blobs`, `rng_streams`, `prng_ledger`, `events`, `turn_ledger`, `lm_calls`, `audit_log`, `error_repair_log`, `commit_gate_log`, `story_log` | `Tx.bookkeep(owner, table, …)`, owner-checked | Re-simulation replay (recorded model outputs) reproduces the first five (`full_state_hash`) |

**Every material change is exactly one event** (plan §13.2.2 law). Prose, reputation, journals and
memory are views over events and mind tables, never extra copies of reality.

## 3. Events and write records

```python
Event(at, type, writer, actor_id, target_ids, place_id, cause_event_id, payload,
      writes: list[WriteRecord], rule_cited, turn_index, origin)
WriteRecord(op: insert|update|upsert|delete, table, key: {pk cols}, values: {cols})
```

- `EventType` has 103 values in 8 classes (`contracts/events.py`); an unknown type is rejected
  (STORE-05).
- `cause_event_id` links consequences to causes. `kernel.events.cause_chain` walks it; the death
  screen uses it to list the player's contributing choices.
- `rule_cited` is mandatory for cascade events (G10) and for anything a validator produced (L14).
- `origin`: `sim` (normal play), `worldgen`, `cheat` (quarantine + sandbox), `migration`, `system`
  (scenario setup, maintenance).
- Payloads over 64 KB go to `blobs` and the payload stores `{"blob": "<sha256>"}` (bit E14).

## 4. Ids

`kernel.ids.mint(tx, kind)` → `"<kind>_<6 digits>"`, per-kind counters, deterministic. An Actor's id
IS its body id (`act_…`). Content records are referenced by **content refs**
`"<pack>:<kind>/<slug>"` (e.g. `core:actor/mara_voss`) and never by runtime ids.

## 5. The knowledge core (the most important schema decision)

| Table | Holds | Who writes | Who reads |
|---|---|---|---|
| `claims` | **Truth**: what is actually so (subject, predicate, object, true_from/until, origin event) | `kernel.truth` (resolver, worldgen) | resolver, worldgen, perception compiler, audits, post-death reveal |
| `propositions` | Things said or inferred that are **not** truth-layer facts (statements heard, inferences, rumours, lies). `matches_claim` links to a claim when code can tell (the linked claim may say the proposition is false) | `mind.perception` | minds via holdings |
| `claim_holdings` | **Beliefs**: holder × (claim or proposition), `believed`, confidence 0–3, provenance, fidelity, acquired via event, superseded_by | `mind.perception.grant` ONLY | packet builder, retrieval, view |
| `percept_log` | **Every percept that ever reached a mind**, with channel, fidelity, rendered text, source (or NULL when the source could not be told) | `mind.perception.grant` ONLY (`granted_by` CHECK) | packet builder, aftermath, audits |

Two SQL views (schema.sql): `canonical_truth` (current facts) and `timer_bank` (every pending clock).
The packet builder imports modules that read `claim_holdings`/`percept_log` and **cannot import**
`kernel.truth`. That is the containment, expressed as a dependency, not a discipline (SKULL-02).

**Why one holdings table instead of twenty.** Beliefs, rumours, secrets, suspicions, perceived
relationship states, faction intelligence and misremembered events are all the same shape:
*somebody holds something about a subject, with a confidence and a source.*

**Three classes of information stay separate forever** (plan §9.1 LAW): truth (store), percept
(perception compiler), belief (mind). A spoken statement writes "X claims Y" (a proposition held
with provenance `told_by:X`), never Y.

## 6. People

`bodies` (physical: kind, size, SPECIAL, blood loss, pain, impairment, awareness, posture) ·
`positions` · `wounds` · `needs` · `infections` · `actors` (the mind wrapper: dossier, controller,
Resolve, stress, goal, duty post, accepted authority, quarantine) · `dossiers` (full baseline JSON)
· `dossier_deltas` · `voice_lines` · `plans` · `tasks` · `relationships` (6 axes, per-axis cause) ·
`refusals` · `open_loops` (promises, debts, grudges, goals, desires, fears, questions, plans, kept
secrets) · `lessons` · `episodes` (+ FTS) · `acquaintance` (what a holder calls another body) ·
`known_places`.

`actors.controller` is `human` for the player character, `model` for minds that get model calls,
`policy` for bodies driven by code only. **Only `turn.pipeline` reads it** (SYM-01).

## 7. Society and world

`groups` (factions and procedural groups) · `group_members` · `group_standing` (how a group regards
any actor — the world's memory of you) · `tension` · `households` · `household_members` ·
`routines` · `settlements` · `laws_active` · `workplaces` · `work_assignments` · `cohorts`
(unnamed people; materialising one decrements a count — L11) · `world_params` · `history_events`
(dual-layer) · `operations` (off-screen motion) · `traces` · `rumours` · `persistence_locks` ·
`infected_state` · `zones` · `places` · `anchors` · `portals` (orthogonal facts; walls are
acoustic-only portals) · `routes` · `items` (exactly one location, CHECK) · `lots`.

P9 notes. A `work_assignments` row is keyed `(workplace_id, actor_id, role, shift_start_hh)` —
one person may hold the same role at the same place on two shifts (their own and a cover);
`covering_for` names whom a cover stands in for. `settlements.stores` holds counted units
(`{"food": 160, "water": 192}`), `shortages` a list of resources, `vacancies` a sorted list of
`{workplace_id, role, for_actor, since}`, `ration_level` 0–4 and morale / cohesion / defences /
sanitation / power 0–10. `tension` is directional (`a_id` holds it against `b_id`; either side may
be an actor or a group). `rumours` records a rumour's origin and furthest hop; who holds it is
`claim_holdings` like any other belief. A settlement's clocks are `event_queue` rows, and the
`next_due_at` columns of `settlements`, `workplaces`, `groups` and `routines` mirror them.

## 8. Narration and UI state

`narration` (the committed prose per turn + lint result; written by a `NARRATION` event) ·
`narrator_state` (style continuity) · `echo_ledger` (the player's 4-word runs; `ECHO_RECORD`
events) · `story_log` (the chat history the UI shows, bookkeeping) · `player_inputs` (raw text +
hash as received — bit S03; `PLAYER_INPUT` events) · `pending_reactions` (reactions deferred past
the wave cap, resolved at the next turn's start; `PENDING_REACTION` events) · `scenes` (P7: the
PC's stay in one place; `SCENE_START` / `SCENE_END`).

## 9. Hashing

`kernel/hashing.py` defines the exact algorithm: sha256 over tables in name order, rows in primary
key order, canonical JSON per row. `world_state_hash` excludes bookkeeping; `full_state_hash`
additionally covers counters, rng streams, the prng ledger and the event log.

- **DET-01** (event-apply replay): replaying every event onto an empty store with the same meta
  reproduces `world_state_hash` exactly.
- **DET-02** (re-simulation): re-running recorded turns with `ReplayTransport` reproduces
  `full_state_hash` after every turn.

## 10. Saves, autosave, load, migration

- Autosave after every committed turn into a ring of `settings.autosave_ring` files (default 5).
- Named saves in free mode; Ironman keeps only the ring and "Continue".
- Load: open → schema version check → fuse dossiers → rebuild FTS → verify manifest hash → ready.
- Worlds: every generated world keeps `as_runs/_worlds/<world_id>/genesis.sqlite` (the world
  before any PC was placed) + `world.json`; new runs can start from it; `.asworld` files move it
  between machines (RUN-09).
- Ironman death ends the run (RUN-08); free mode allows load and "new life here" (RUN-07).
- Run context: the store carries the run's compiled content and rules (`store.canon`,
  `store.rules`, STORE-10) so modules never reach for globals.
- Schema version bumps ship a migration in `kernel/migrations/` with a diagnostic → itemised
  report → **explicit consent in the UI** → reconstruction; every backfilled row is written by a
  `MIGRATION_BACKFILL` event with `origin='migration'` (plan §13.9 carried; bit E16).

## 11. ASL compatibility (deferred, preserved)

Names, units and event type names are shared with the ASL plan so an ASL save can later be imported
as a strict subset (plan §20.3). Import is not in v1's build order; nothing in v1 may rename a table
or event type without recording it in `DECISIONS.md`.
