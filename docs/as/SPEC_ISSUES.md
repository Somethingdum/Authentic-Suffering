# SPEC_ISSUES

Where the builder reports suspected problems in the spec or a protected test. The builder adds
entries; **the human resolves them** (and records contract changes in `CHANGELOG_AS.md`). Never
edit a protected file to make a problem go away.

## How to file

Copy the template, give it the next number, fill every line.

```
### SI-<nnn> — <one-line title>
- Status: open
- Phase / test: P<n> · tests/contract/<file>::<test>
- Rule id(s): <e.g. AUD-03>
- The spec says: <quote, with file and section>
- The test/contract does: <what it asserts or requires>
- The problem: <why they cannot both be right, or why it is impossible/ambiguous>
- Evidence: <a unit test you wrote, command output, numbers>
- Proposed resolution: <what you think should change>
- Meanwhile: <what you are doing in the same phase while this is open>
```

## Open

### SI-001 — The 64 inherited v4 regression tests are not in the project
- Status: open (human)
- Phase / test: all
- Rule id(s): —
- The spec says: Rebuild Plan §16.1 "All 64 carry forward"; DECISIONS D-08.
- The test/contract does: covers their families (STORE/DET/TIME/GEO/CONSERVE/LOD/DOS).
- The problem: the list itself is not available to the builder.
- Evidence: not present in any project document.
- Proposed resolution: add the v4 test list to `docs/as/reference/v4_tests.md`; the spec author maps each to a contract test.
- Meanwhile: families are covered.

### SI-002 — No sample `CODEX-4.0` save for MIG-01
- Status: open (human)
- Phase / test: P12 · tests/contract/p12_surfaces/test_migration.py
- Rule id(s): MIG-01
- The spec says: Rebuild Plan §15.2 P12 "a v4 CODEX-4.0 save imports with every backfilled field flagged"; DECISIONS D-09.
- The test/contract does: tests the migration framework on an AS schema bump only.
- The problem: without a sample save the legacy format cannot be specified.
- Proposed resolution: add one or two real v4 saves to `as_engine/tests/fixtures/legacy/`.
- Meanwhile: framework only.

### SI-003 — LURKER_DEEP conversion probability and incubation length are not pinned
- Status: open (human)
- Phase / test: P8 · tests/contract/p08_worldgen/ (infection pathway compile), content pack `core:pathway/lurker_deep`
- Rule id(s): CNT-01 (content must not invent authoritative numbers past what source material supports)
- The spec says: Lore_and_World_Building.pdf §4 and Codex Ultima Super (Lurker dossier) — a Lurker claw wound "carries a significant, but not certain, chance" of leading to Lurker-borne infection, and "no one in-world truly knows how" the transformation happens; timing is never given.
- The test/contract does: `InfectionPathwayDef` requires concrete `exposure` probabilities and `stages[].starts_at_h` for every pathway, including `lurker_deep`.
- The problem: no source document gives a number for the claw-wound conversion chance or the incubation window, so `as_content/packs/core/pathways/pathways.yaml`'s `lurker_deep` record (exposure 0.35, incubation stages at 0h/720h) is an authored placeholder, not a value pulled from canon.
- Evidence: `as_content/packs/core/pathways/pathways.yaml` — the `lurker_deep` record is marked `canon_status: proposed` for this reason.
- Proposed resolution: either the human pins a number (and canon_status flips to `canon`), or the pathway is left `proposed` permanently and the content linter is told to accept `proposed` pathways without hard-failing CNT-01.
- Meanwhile: the pathway compiles and is usable in worldgen/testing, just flagged non-canon; CMG §42.19's hard rule (baseline infected never attack a true Lurker Infected victim) is unaffected by this gap and is enforced regardless.

### SI-004 — The wet strain's shared-bottle numbers are not in the lore
- Status: open (human)
- Phase / test: P10 · tests/contract/p10_world/test_wet_strain.py; content `core:pathway/wet`
- Rule id(s): CNT-01 (no authoritative numbers past what the sources support)
- The spec says: CODEX lore v2 §3.2 — a living spreader's saliva infects from about day 3, and
  "everyone knows somebody who was killed by a shared bottle"; no chance or duration is given.
- The test/contract does: `pathways.yaml` wet `exposure.mouth_contact_item: 0.3` and
  `InfectedRules.saliva_hours = 12.0` (how long a bottle a spreader drank from stays infective),
  both marked `[SAND]`; `test_wet_strain.py` reads them from the rules and the pack, never as constants.
- The problem: both numbers are this spec's choices.
- Proposed resolution: the owner confirms or replaces them (the tests follow whatever the pack and
  the rules say).
- Meanwhile: the mechanic is complete and tested with these values.

### SI-005 — The Ghosts' named leadership is an open decision in Ghosts_6
- Status: open (human)
- Phase / test: P10 · tests/contract/p10_world/test_ghosts.py; content `core:faction/ghosts`
- Rule id(s): FAC-02, WG-27
- The spec says: Ghosts_6 lists the five Top-Hat seats and the Front Man but marks their names as
  undecided.
- The test/contract does: every world generates its own seat holders (occupation = the title; the
  Front Man about forty) — nothing canonical is named (DECISIONS D-59).
- The problem: if the owner fixes names later, they belong in the record as pack actors
  (`leaders[].actor`). Worldgen already lets a placed pack actor lead as the first leader and skips
  generating any other seat whose leader names a placed pack actor (WG-27); making that actor the
  seat's holder (`group_members.role` = the seat) needs a one-line WG-28 amendment.
- Proposed resolution: when names exist, add them as actor dossiers in a pack, point the seats'
  `actor` at them, and amend WG-28 so a placed pack actor takes its seat's role.
- Meanwhile: generated per world.

## Resolved

(none yet)
