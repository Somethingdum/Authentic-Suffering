"""Content packs: load, validate, lint, compile (P2). Rules CNT-00..14, LORE-01.
docs/as/09_CONTENT_PACKS.md is the authoring guide; this docstring is the machine contract.

Folder layout (every folder optional except pack.yaml):
  <pack>/pack.yaml                 PackManifest
  <pack>/actors/*.yaml             ActorDossier          -> ref '<pack>:actor/<id>'
  <pack>/pcs/*.yaml                PCDossier             -> '<pack>:pc/<id>'
  <pack>/factions/*.yaml           FactionDossier        -> '<pack>:faction/<id>'
  <pack>/lore/*.md                 LoreEntry as YAML front matter + optional markdown body
                                   (the body becomes depth text; front matter carries truth/beliefs)
  <pack>/items/*.yaml              list[ItemDef]         -> '<pack>:item/<id>'
  <pack>/affordances/*.yaml        list[AffordanceDef]   -> '<pack>:affordance/<id>'
  <pack>/infected/*.yaml           InfectedTypeDef | InfectedStateDef | QuirkDef (by 'schema')
                                   -> '<pack>:infected/<ID>', '<pack>:infected_state/<id>',
                                      '<pack>:quirk/<ID>' (bare ids inside infected records)
  <pack>/pathways/*.yaml           InfectionPathwayDef   -> '<pack>:pathway/<id>'
  <pack>/cascade/*.yaml            list[CascadeRuleDef]  -> '<pack>:cascade/<CAS-nnn>'
  <pack>/laws/*.yaml               list[LawDef]          -> '<pack>:law/<id>'
  <pack>/buildings/*.yaml          BuildingArchetype     -> '<pack>:building/<id>'
  <pack>/loot/*.yaml               list[LootTable]       -> '<pack>:loot/<id>'
  <pack>/names/*.yaml              NameList              -> '<pack>:names/<id>'
  <pack>/style/*.yaml              StyleRules            -> '<pack>:style/<id>'
  <pack>/lore/*.md                 LoreEntry             -> '<pack>:lore/<id>'
  <pack>/cues.yaml                 CueRegistry           (cue ids are global and bare)
A YAML file may hold one record (mapping) or a list of records of the folder's type.
Files and folders whose name starts with '_' (e.g. _drafts/, _notes.md) and README.md files are
ignored by the loader (IMP-02: drafts never load). Any other unknown folder is a warning.
A dossier file may use the extension .md: YAML front matter between '---' lines is the record,
and the markdown body is stored as ``depth_reference``.

Record kinds (the ``kind`` part of a ref, and the key of Canon.by_kind):
  actor pc faction lore item affordance infected infected_state quirk pathway cascade law building
  loot names style cue.  Cues get refs '<pack>:cue/<id>' in by_kind['cue'] but are looked up by
  bare id (Canon.find('cue', id)); infected types, states, quirks and pathways are also referenced
  by bare id inside content (quirks:, applies_to:, rise_as:, inherits:, BodySpec.infected).
  Bare ids are unique per kind across all packs (CNT-03), so Canon.find(kind, bare_id) is exact.
Loading order: packs sorted so every depends_on comes first (a missing dependency or a cycle is a
  CNT-04 error on pack.yaml); within a pack, folders in the table order above, files sorted by
  name, records in file order.
Issues: ContentIssue.file is the path relative to the pack root in posix form
  ('actors/mara_voss.yaml'), ContentIssue.pack the pack id, ContentIssue.field a dotted path
  ('voice.would_never_say', 'social.relations[0].target'), and ContentIssue.message is one
  plain-language line that starts with the file path (09 §9 shows the form). A record that fails
  its contract is not loaded (it is simply absent from canon) and yields one issue per pydantic
  error (at most 5 per record).

Validation (CNT-*), each error names file + field in plain language:
  CNT-00 the file is not valid YAML / front matter, a mapping repeats a key (YAML would silently
         keep the last one — the loader refuses instead), or its 'schema' is not the folder's.
  CNT-01 tooling exhaust strings anywhere in text (case-insensitive substring of the raw file):
         'IGNORE_WHEN_COPYING', 'content_copy', 'Use code with caution', 'As an AI', '[INSERT',
         'TODO', 'lorem ipsum'.
  CNT-02 placeholder bodies, for the narrative kinds (actor, pc, faction, lore, quirk): two or more
         records of one kind in one pack whose TEXT (every string leaf except id/schema and
         content refs, joined with newlines in document order) is identical after replacing
         every run of digits with '#' -> every record after the first is an error
         ("boilerplate plus an index").
  CNT-03 ids unique per kind across all loaded packs (later packs may NOT silently override;
         overriding requires `overrides: [<earlier ref>]` in the later pack's manifest; the later
         record then REPLACES the earlier one under the EARLIER ref, so every reference to it
         keeps resolving, e.g. a 'house_rules' pack overriding core:item/glock_19 changes what
         core:item/glock_19 is; there is no 'house_rules:item/glock_19').
  CNT-04 every ContentRef resolves: any string leaf that matches the whole ref pattern
         '^[a-z0-9_]+:<kind>/[A-Za-z0-9_-]+$', plus the bare-id references (quirks, applies_to,
         rise_as, inherits, building to_room / entrance_room, starting_inventory container labels,
         depends_on). The message suggests the closest existing ref ("Did you mean ...?", difflib
         cutoff 0.8) when there is one.
  CNT-05 every cue referenced exists in some pack's cues.yaml: capability.trained_responses[].cue,
         knowledge.cues, lore beliefs[].cues, affordance requires.belief_cues and
         requires.skill_or_belief_cue, quirk trigger_cue, pathway stages[].signs (P10).
  CNT-06 affordance.effect is in action.effects.EFFECT_IDS, and its label / ui_label use only the
         placeholders {target} {destination} {item} {distance} {duration}.
  CNT-07 LORE-01: lore needs truth AND >= 1 belief; factions need truth_text AND belief_text
         (both also enforced by min_length; CNT-07 is the code those failures carry).
  CNT-08 names use one spelling: 'sotry' anywhere (case-insensitive) is an error; the other
         audit.commit_gate.RETIRED_NAMES (GLOSSARY tombstones) found in a text value are warnings.
  CNT-09 PC dossiers: plausibility_gate.pass_any[] and hard_fail_all parse with
         world/worldgen/conditions.parse; the same for faction presence.presence_conditions[].
  CNT-10 a record that does not match its contract (unknown field, wrong type, missing field) —
         for dossiers this includes the specificity minimums (contracts/dossier.py min_length).
  CNT-11 child safety: any actor or pc record whose identity.age < 18 with a term from
         content/safety.py::MINOR_UNSAFE_TERMS in ANY string value (unsafe_terms()) is a hard error
         naming the field and the term — this check cannot be disabled (negation is not
         understood; see that module). It runs on the raw YAML mapping, so a record that also
         fails its contract is still checked.
  CNT-12 items: kind firearm requires `firearm`, melee requires `melee`, container requires
         `container`, food `food`, water `water`, medical `medical`; a block that does not belong
         to the kind (e.g. `firearm` on a tool) is an error too.
  CNT-13 infected ids are stable: an InfectedTypeDef may list only quirks whose applies_to names
         it or a type it inherits from, and a quirk or type id redefined through `overrides:` must
         keep its applies_to / inherits unchanged.
  CNT-14 generation 'cheat' dossiers, and any dossier tagged 'standing_brief' (CHEAT-11), may only
         live in packs whose manifest id starts with 'cheat_'.
Severity: every code is 'error' except the CNT-08 retired-name case and the unknown-folder case
  (code CNT-00, 'warning'). load_canon's Canon contains only records that loaded; callers treat
  any error as fatal (the conftest canon fixture asserts there are none for core).

lint_text_records(pack) -> CNT-01/02/08/11 issues for one loaded pack (the text-only checks,
  also run by the Content screen on a single pack).

compile_packs(pack_dirs, out_path) -> CompileReport
  Loads packs in dependency order, validates, and writes canon.sqlite (one table per record kind:
  ref TEXT PRIMARY KEY, pack TEXT, json TEXT) plus a 'lore_fts' FTS5 table over lore truth+beliefs.
  json = canonical_json(record.model_dump(mode='json', by_alias=True)).
  content_hash = sha256 over canonical_json(sorted [ref, json] pairs) — identical content gives an
  identical hash on every machine; any record change changes it. ok = no error issues; when not
  ok, canon.sqlite is NOT written (a half-valid canon never reaches a run).
  counts = {kind: number of records}.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel


@dataclass
class ContentIssue:
    code: str  # CNT-xx
    file: str  # relative to the pack root, posix: 'actors/mara_voss.yaml'
    field: str  # dotted path: 'voice.would_never_say'
    message: str  # plain language, starts with the file: "actors/mara_voss.yaml: voice.would_never_say needs at least 3 lines (it has 1)."
    severity: str = "error"
    pack: str = ""


@dataclass
class LoadedPack:
    manifest: Any
    root: Path
    records: dict[str, dict[str, BaseModel]] = field(default_factory=dict)  # kind -> ref -> record


@dataclass
class CompileReport:
    ok: bool
    issues: list[ContentIssue] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    content_hash: str = ""


@dataclass
class Canon:
    """In-memory view of compiled content used by the engine (catalog, items, dossiers...)."""

    packs: list[LoadedPack] = field(default_factory=list)
    by_kind: dict[str, dict[str, BaseModel]] = field(default_factory=dict)
    content_hash: str = ""

    def get(self, ref: str) -> BaseModel:
        kind = ref.split(":", 1)[1].split("/", 1)[0]
        return self.by_kind[kind][ref]

    def all(self, kind: str) -> list[BaseModel]:
        return [self.by_kind.get(kind, {})[k] for k in sorted(self.by_kind.get(kind, {}))]

    def refs(self, kind: str) -> list[str]:
        return sorted(self.by_kind.get(kind, {}))

    def find(self, kind: str, bare_id: str) -> BaseModel:
        """The record of ``kind`` whose bare id is ``bare_id`` (implemented). KeyError if none."""
        for r, rec in self.by_kind.get(kind, {}).items():
            if r.rsplit("/", 1)[1] == bare_id:
                return rec
        raise KeyError(f"{kind}/{bare_id}")

    def has(self, ref: str) -> bool:
        try:
            self.get(ref)
            return True
        except (KeyError, IndexError):
            return False


def load_pack(root: str | Path) -> tuple[LoadedPack | None, list[ContentIssue]]:
    raise NotImplementedError("P2")


def load_canon(pack_dirs: list[str | Path]) -> tuple[Canon, list[ContentIssue]]:
    raise NotImplementedError("P2")


def lint_text_records(pack: LoadedPack) -> list[ContentIssue]:
    raise NotImplementedError("P2")


def compile_packs(pack_dirs: list[str | Path], out_path: str | Path) -> CompileReport:
    raise NotImplementedError("P2")


def ref(pack_id: str, kind: str, record_id: str) -> str:
    """'<pack>:<kind>/<id>' (implemented)."""
    return f"{pack_id}:{kind}/{record_id}"
