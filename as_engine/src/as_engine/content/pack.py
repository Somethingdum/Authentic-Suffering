"""Content packs: load, validate, lint, compile (P2). Rules CNT-00..17, LORE-01.
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
  <pack>/animals/*.yaml            list[AnimalDef]       -> '<pack>:animal/<id>'   (I1: prey and meat;
                                   the folder comes right after pathways in the load order and
                                   'animal' is a record kind of refs, REF_RE)
  <pack>/cascade/*.yaml            list[CascadeRuleDef]  -> '<pack>:cascade/<CAS-nnn>'
  <pack>/laws/*.yaml               list[LawDef]          -> '<pack>:law/<id>'
  <pack>/buildings/*.yaml          BuildingArchetype     -> '<pack>:building/<id>'
  <pack>/loot/*.yaml               list[LootTable]       -> '<pack>:loot/<id>'
  <pack>/names/*.yaml              NameList              -> '<pack>:names/<id>'
  <pack>/style/*.yaml              StyleRules            -> '<pack>:style/<id>'
  <pack>/ui/*.yaml                 QuipList              -> '<pack>:quips/<id>'   (P10: the loading bar's lines)
  <pack>/lore/*.md                 LoreEntry             -> '<pack>:lore/<id>'
  <pack>/cues.yaml                 CueRegistry           (cue ids are global and bare)
A YAML file may hold one record (mapping) or a list of records of the folder's type.
Files and folders whose name starts with '_' (e.g. _drafts/, _notes.md) and README.md files are
ignored by the loader (IMP-02: drafts never load). Any other unknown folder is a warning.
A dossier file may use the extension .md: YAML front matter between '---' lines is the record,
and the markdown body is stored as ``depth_reference``.

Record kinds (the ``kind`` part of a ref, and the key of Canon.by_kind):
  actor pc faction lore item affordance infected infected_state quirk pathway cascade law building
  loot names style quips cue.  Cues get refs '<pack>:cue/<id>' in by_kind['cue'] but are looked up by
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
         `container`, food `food`, water `water`, medical `medical`, clothing `clothing` (F1a);
         a block that does not belong to the kind (e.g. `firearm` on a tool) is an error too.
  CNT-13 infected ids are stable: an InfectedTypeDef may list only quirks whose applies_to names
         it or a type it inherits from, and a quirk or type id redefined through `overrides:` must
         keep its applies_to / inherits unchanged.
  CNT-14 generation 'cheat' dossiers, and any dossier tagged 'standing_brief' (CHEAT-11), may only
         live in packs whose manifest id starts with 'cheat_'.
  CNT-15 (P10) a faction's behaviour.council.seats each name the ``seat`` of one of its leaders, and
         no two leaders share a seat.
  CNT-16 (P10) a QuipList's keys each name a progress plan (service.progress.PLANS: kind), one of
         its phases (f"{kind}.{phase}") or a sub-phase of that phase (f"{kind}.{phase}.{sub}"); no
         line is empty or longer than 80 characters.
  CNT-17 (F1a) looks: an actor or pc dossier without appearance.looks is a warning (others will
         see its height and build only). With looks, each an error on field
         'appearance.looks.outfit[i]' / 'appearance.looks.outfit' / 'starting_inventory[i]':
         an outfit item that resolves (CNT-04 reports one that does not) but has no clothing
         block; an outfit whose clothing does not cover both 'torso' and 'groin' (the message
         names what is uncovered: a person is never created naked by accident); a
         starting_inventory grant in slot 'worn' whose item has a clothing block (the outfit is
         what they wear — one list; clothing carried in a pack is fine).
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



import difflib as _difflib
import hashlib as _hashlib
import re as _re

import yaml as _yaml

_FOLDERS = [  # folder, kind, contract name, one-or-list
    ("actors", "actor", "ActorDossier"), ("pcs", "pc", "PCDossier"), ("factions", "faction", "FactionDossier"),
    ("lore", "lore", "LoreEntry"), ("items", "item", "ItemDef"), ("affordances", "affordance", "AffordanceDef"),
    ("infected", None, None), ("pathways", "pathway", "InfectionPathwayDef"), ("animals", "animal", "AnimalDef"), ("cascade", "cascade", "CascadeRuleDef"),
    ("laws", "law", "LawDef"), ("buildings", "building", "BuildingArchetype"), ("loot", "loot", "LootTable"),
    ("names", "names", "NameList"), ("style", "style", "StyleRules"), ("ui", "quips", "QuipList"),
]
_INFECTED = {"as.infected.v1": ("infected", "InfectedTypeDef"), "as.infected_state.v1": ("infected_state", "InfectedStateDef"),
             "as.quirk.v1": ("quirk", "QuirkDef")}
_SCHEMA_OF = {"actor": "as.actor.v1", "pc": "as.pc.v1", "faction": "as.faction.v1", "lore": "as.lore.v1",
              "item": "as.item.v1", "affordance": "as.affordance.v1", "pathway": "as.pathway.v1",
              "cascade": "as.cascade.v1", "law": "as.law.v1", "building": "as.building.v1", "loot": "as.loot.v1",
              "names": "as.names.v1", "style": "as.style.v1", "quips": "as.quips.v1", "animal": "as.animal.v1"}
KINDS = ("actor", "pc", "faction", "lore", "item", "affordance", "infected", "infected_state", "quirk", "pathway",
         "cascade", "law", "building", "loot", "names", "style", "quips", "cue", "animal")
EXHAUST = ('IGNORE_WHEN_COPYING', 'content_copy', 'Use code with caution', 'As an AI', '[INSERT', 'TODO', 'lorem ipsum')
REF_RE = _re.compile(r"^[a-z0-9_]+:(" + "|".join(KINDS) + r")/[A-Za-z0-9_-]+$")


def _model(name):
    from ..contracts import content as c, dossier as d
    return getattr(c, name, None) or getattr(d, name)


def _loc(loc):
    out = ""
    for x in loc:
        if isinstance(x, int):
            out += f"[{x}]"
        else:
            out += ("." if out else "") + str(x)
    return out


def _issue(pack_id, rel, code, field, text, severity="error"):
    return ContentIssue(code=code, file=rel, field=field, message=f"{rel}: {text}", severity=severity, pack=pack_id)


def _ignored(path, root):
    parts = path.relative_to(root).parts
    return any(x.startswith("_") for x in parts) or path.name == "README.md"


class _UniqueLoader(_yaml.SafeLoader):
    pass


def _unique_mapping(loader, node, deep=False):
    seen = set()
    for k, _v in node.value:
        key = loader.construct_object(k, deep=deep)
        if key in seen:
            raise _yaml.YAMLError(f"duplicate key '{key}' on line {k.start_mark.line + 1}")
        seen.add(key)
    return _yaml.SafeLoader.construct_mapping(loader, node, deep)


_UniqueLoader.add_constructor(_yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def _load_yaml(text):
    return _yaml.load(text, Loader=_UniqueLoader)


def _read_records(f, rel, pack_id, issues):
    text = f.read_text(encoding="utf-8")
    try:
        if f.suffix == ".md":
            m = _re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, _re.S)
            if not m:
                issues.append(_issue(pack_id, rel, "CNT-00", "", "has no YAML front matter between '---' lines."))
                return text, []
            data = _load_yaml(m.group(1))
            body = m.group(2).strip() or None
            recs = [data] if isinstance(data, dict) else []
            return text, [(r, body) for r in recs]
        data = _load_yaml(text)
    except _yaml.YAMLError as e:
        issues.append(_issue(pack_id, rel, "CNT-00", "", f"is not valid YAML ({str(e).splitlines()[0]})."))
        return text, []
    if data is None:
        return text, []
    recs = data if isinstance(data, list) else [data]
    return text, [(r, None) for r in recs if isinstance(r, dict)]


def _strings(o, path=""):
    if isinstance(o, str):
        yield path, o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield from _strings(v, f"{path}.{k}" if path else str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _strings(v, f"{path}[{i}]")


def _minor_issues(pack_id, rel, raw):
    from .safety import unsafe_terms
    out = []
    try:
        age = int(raw.get("identity", {}).get("age"))
    except (TypeError, ValueError):
        return out
    if age >= 18:
        return out
    for path, s in _strings(raw):
        for t in unsafe_terms(s):
            out.append(_issue(pack_id, rel, "CNT-11", path,
                              f"{path}: a record for someone under 18 contains the word '{t}'. This is never allowed (CNT-11)."))
    return out


def load_pack(root: str | Path) -> tuple[LoadedPack | None, list[ContentIssue]]:
    from ..contracts.content import CueRegistry, PackManifest
    from pydantic import ValidationError
    root = Path(root)
    issues: list[ContentIssue] = []
    mf = root / "pack.yaml"
    if not mf.exists():
        return None, [ContentIssue("CNT-00", "pack.yaml", "", f"{root.name}: pack.yaml is missing.")]
    try:
        manifest = PackManifest.model_validate(_yaml.safe_load(mf.read_text(encoding="utf-8")))
    except (ValidationError, _yaml.YAMLError) as e:
        return None, [ContentIssue("CNT-10", "pack.yaml", "", f"pack.yaml: {str(e).splitlines()[0]}")]
    pid = manifest.id
    pack = LoadedPack(manifest=manifest, root=root)
    pack.raw = {}  # ref -> (rel, raw dict)
    pack.texts = {}  # rel -> raw text
    known = {f for f, _, _ in _FOLDERS} | {"pack.yaml", "cues.yaml"}
    for child in sorted(root.iterdir()):
        if child.name.startswith("_") or child.name == "README.md" or child.name in known:
            continue
        issues.append(_issue(pid, child.name, "CNT-00", "", f"is not a content folder the engine knows; it was skipped.", "warning"))
    for folder, kind, cname in _FOLDERS:
        d = root / folder
        if not d.is_dir():
            continue
        pattern = "*.md" if folder == "lore" else "*"
        for f in sorted(d.rglob(pattern)):
            if not f.is_file() or _ignored(f, root) or f.suffix not in (".yaml", ".yml", ".md"):
                continue
            rel = f.relative_to(root).as_posix()
            text, recs = _read_records(f, rel, pid, issues)
            pack.texts[rel] = text
            for raw, body in recs:
                if folder == "infected":
                    k, cn = _INFECTED.get(raw.get("schema"), (None, None))
                    if k is None:
                        issues.append(_issue(pid, rel, "CNT-00", "schema", f"schema '{raw.get('schema')}' is not an infected, infected_state or quirk schema."))
                        continue
                else:
                    k, cn = kind, cname
                    if raw.get("schema") not in (None, _SCHEMA_OF[k]):
                        issues.append(_issue(pid, rel, "CNT-00", "schema", f"schema '{raw.get('schema')}' does not belong in {folder}/ (expected {_SCHEMA_OF[k]})."))
                        continue
                if k in ("actor", "pc"):
                    issues.extend(_minor_issues(pid, rel, raw))
                if body is not None:
                    if k == "lore":
                        raw = {**raw, "body": body}
                    elif k in ("actor", "pc"):
                        raw = {**raw, "depth_reference": body}
                try:
                    rec = _model(cn).model_validate(raw)
                except ValidationError as e:
                    code = "CNT-07" if k in ("lore", "faction") and any(
                        str(er["loc"][0]) in ("truth", "beliefs", "truth_text", "belief_text") for er in e.errors()) else "CNT-10"
                    for er in e.errors()[:5]:
                        loc = _loc(er["loc"])
                        issues.append(_issue(pid, rel, code, loc, f"{raw.get('id', '?')}: {loc}: {er['msg']}."))
                    continue
                r = ref(pid, k, rec.id)
                if r in pack.records.get(k, {}):
                    issues.append(_issue(pid, rel, "CNT-03", "id", f"id '{rec.id}' is defined twice in pack {pid}."))
                    continue
                pack.records.setdefault(k, {})[r] = rec
                pack.raw[r] = (rel, raw)
    cf = root / "cues.yaml"
    if cf.exists():
        rel = "cues.yaml"
        try:
            reg = CueRegistry.model_validate(_yaml.safe_load(cf.read_text(encoding="utf-8")))
            for c in reg.cues:
                r = ref(pid, "cue", c.id)
                pack.records.setdefault("cue", {})[r] = c
                pack.raw[r] = (rel, c.model_dump())
            pack.texts[rel] = cf.read_text(encoding="utf-8")
        except (ValidationError, _yaml.YAMLError) as e:
            issues.append(_issue(pid, rel, "CNT-10", "cues", f"{str(e).splitlines()[0]}"))
    issues.extend(lint_text_records(pack))
    return pack, issues


def _text_of(raw):
    out = []
    for path, s in _strings(raw):
        last = path.split(".")[-1].split("[")[0]
        if last in ("id", "schema") or REF_RE.match(s):
            continue
        out.append(s)
    return "\n".join(out)


def lint_text_records(pack: LoadedPack) -> list[ContentIssue]:
    from ..audit.commit_gate import RETIRED_NAMES
    pid = pack.manifest.id
    issues = []
    for rel, text in sorted(getattr(pack, "texts", {}).items()):
        low = text.lower()
        for b in EXHAUST:
            if b.lower() in low:
                issues.append(_issue(pid, rel, "CNT-01", "", f"contains tooling exhaust or a placeholder ('{b}')."))
        if "sotry" in low:
            issues.append(_issue(pid, rel, "CNT-08", "", "uses the misspelling 'sotry'; the word is 'story'."))
    for r, (rel, raw) in sorted(getattr(pack, "raw", {}).items()):
        for path, s in _strings(raw):
            for name in RETIRED_NAMES:
                if name == "sotry":
                    continue
                if _re.search(r"\b" + _re.escape(name) + r"\b", s):
                    issues.append(_issue(pid, rel, "CNT-08", path, f"{path}: '{name}' is a retired name (see GLOSSARY).", "warning"))
    for kind in ("actor", "pc", "faction", "lore", "quirk"):
        seen = {}
        for r in pack.records.get(kind, {}):
            rel, raw = pack.raw[r]
            key = _re.sub(r"\d+", "#", _text_of(raw))
            if key in seen:
                issues.append(_issue(pid, rel, "CNT-02", "", f"'{r}' is the same text as '{seen[key]}' with only numbers changed (boilerplate plus an index)."))
            else:
                seen[key] = r
    return issues


def _toposort(packs, issues):
    by_id = {p.manifest.id: p for p in packs}
    order, state = [], {}

    def visit(pid, chain):
        if state.get(pid) == 2:
            return
        if state.get(pid) == 1:
            issues.append(ContentIssue("CNT-04", "pack.yaml", "depends_on", f"pack.yaml: dependency cycle {' -> '.join(chain + [pid])}.", pack=pid))
            return
        state[pid] = 1
        for dep in by_id[pid].manifest.depends_on:
            if dep not in by_id:
                issues.append(ContentIssue("CNT-04", "pack.yaml", "depends_on", f"pack.yaml: depends on pack '{dep}', which is not loaded.", pack=pid))
                continue
            visit(dep, chain + [pid])
        state[pid] = 2
        order.append(by_id[pid])

    for p in sorted(packs, key=lambda p: p.manifest.id):
        visit(p.manifest.id, [])
    return order


def load_canon(pack_dirs: list[str | Path]) -> tuple[Canon, list[ContentIssue]]:
    from ..action.effects import EFFECT_IDS
    from ..world.worldgen.conditions import ConditionSyntaxError, parse
    issues: list[ContentIssue] = []
    packs = []
    for d in pack_dirs:
        p, iss = load_pack(d)
        issues.extend(iss)
        if p is not None:
            packs.append(p)
    packs = _toposort(packs, issues)
    canon = Canon(packs=packs)
    raw_of = {}
    bare = {}  # (kind, bare id) -> ref
    for p in packs:
        pid = p.manifest.id
        for kind, recs in p.records.items():
            for r, rec in recs.items():
                b = r.rsplit("/", 1)[1]
                prior = bare.get((kind, b))
                rel = p.raw[r][0]
                if prior is not None:
                    if prior not in p.manifest.overrides:
                        issues.append(_issue(pid, rel, "CNT-03", "id", f"{kind} id '{b}' already exists as '{prior}'; list it under overrides: in pack.yaml to replace it."))
                        continue
                    old = canon.by_kind[kind][prior]
                    if kind in ("quirk", "infected"):
                        f = "applies_to" if kind == "quirk" else "inherits"
                        if getattr(old, f) != getattr(rec, f):
                            issues.append(_issue(pid, rel, "CNT-13", f, f"{f}: '{b}' is a stable id; an override may not change which creature it means."))
                    canon.by_kind[kind][prior] = rec
                    raw_of[prior] = (p, rel, p.raw[r][1])
                    continue
                canon.by_kind.setdefault(kind, {})[r] = rec
                bare[(kind, b)] = r
                raw_of[r] = (p, rel, p.raw[r][1])
    all_refs = {r for k in canon.by_kind for r in canon.by_kind[k]}
    cues = {r.rsplit("/", 1)[1] for r in canon.by_kind.get("cue", {})}
    types = {r.rsplit("/", 1)[1] for r in canon.by_kind.get("infected", {})}
    quirks = {r.rsplit("/", 1)[1]: q for r, q in canon.by_kind.get("quirk", {}).items()}

    def err(p, rel, code, field, text):
        issues.append(_issue(p.manifest.id, rel, code, field, text))

    for r, (p, rel, raw) in sorted(raw_of.items()):
        kind = r.split(":", 1)[1].split("/", 1)[0]
        rec = canon.by_kind[kind].get(r)
        if rec is None:
            continue
        # CNT-04 full refs
        for path, s in _strings(raw):
            if REF_RE.match(s) and s not in all_refs:
                close = _difflib.get_close_matches(s, sorted(all_refs), n=1, cutoff=0.8)
                hint = f" Did you mean '{close[0]}'?" if close else ""
                err(p, rel, "CNT-04", path, f"{path} '{s}' does not exist.{hint}")
        # bare refs
        if kind == "infected":
            if rec.inherits and rec.inherits not in types:
                err(p, rel, "CNT-04", "inherits", f"inherits '{rec.inherits}' does not exist.")
            lineage = {rec.id}
            cur = rec
            while cur.inherits and cur.inherits in types and cur.inherits not in lineage:
                lineage.add(cur.inherits)
                cur = canon.find("infected", cur.inherits)
            for i, q in enumerate(rec.quirks):
                if q not in quirks:
                    err(p, rel, "CNT-04", f"quirks[{i}]", f"quirks[{i}] '{q}' does not exist.")
                elif not (set(quirks[q].applies_to) & lineage):
                    err(p, rel, "CNT-13", f"quirks[{i}]", f"quirks[{i}] '{q}' is written for {quirks[q].applies_to}, not for {rec.id}.")
        if kind == "quirk":
            for i, t in enumerate(rec.applies_to):
                if t not in types:
                    err(p, rel, "CNT-04", f"applies_to[{i}]", f"applies_to[{i}] '{t}' does not exist.")
            if rec.trigger_cue and rec.trigger_cue not in cues:
                err(p, rel, "CNT-05", "trigger_cue", f"trigger_cue '{rec.trigger_cue}' is not in any cues.yaml.")
        if kind == "quips":
            from ..service.progress import PLANS
            ok_keys = set()
            for knd, phases in PLANS.items():
                ok_keys.add(knd)
                for ph in phases:
                    ok_keys.add(f"{knd}.{ph.id}")
                    ok_keys |= {f"{knd}.{ph.id}.{s.id}" for s in ph.subs}
            for key, lines in rec.lines.items():
                if key not in ok_keys:
                    err(p, rel, "CNT-16", f"lines.{key}", f"'{key}' is not a progress plan, phase or sub-phase.")
                for i, line in enumerate(lines):
                    if not line.strip() or len(line) > 80:
                        err(p, rel, "CNT-16", f"lines.{key}[{i}]", "a quip must be 1 to 80 characters.")
        if kind == "pathway":
            for i, t in enumerate(rec.rise_as):
                if t not in types:
                    err(p, rel, "CNT-04", f"rise_as[{i}]", f"rise_as[{i}] '{t}' does not exist.")
            for i, st in enumerate(rec.stages):
                for j, c in enumerate(st.signs):
                    if c not in cues:
                        err(p, rel, "CNT-05", f"stages[{i}].signs[{j}]", f"cue '{c}' is not in any cues.yaml.")
        if kind == "building":
            ids = {x.id for x in rec.rooms}
            if rec.entrance_room not in ids:
                err(p, rel, "CNT-04", "entrance_room", f"entrance_room '{rec.entrance_room}' is not one of its rooms.")
            for i, room in enumerate(rec.rooms):
                for j, pt in enumerate(room.portals):
                    if pt.to_room not in ids:
                        err(p, rel, "CNT-04", f"rooms[{i}].portals[{j}].to_room", f"portal to_room '{pt.to_room}' is not one of its rooms.")
            for j, pt in enumerate(rec.exterior_portals):
                if pt.to_room not in ids:
                    err(p, rel, "CNT-04", f"exterior_portals[{j}].to_room", f"to_room '{pt.to_room}' is not one of its rooms.")
        if kind in ("actor", "pc"):
            lk = rec.appearance.looks
            if lk is None:
                issues.append(_issue(p.manifest.id, rel, "CNT-17", "appearance.looks", "has no appearance.looks; others will see only height and build.", "warning"))
            else:
                cov = set()
                for i, pc in enumerate(lk.outfit):
                    if pc.item not in all_refs:
                        continue
                    d = canon.get(pc.item)
                    if d.clothing is None:
                        err(p, rel, "CNT-17", f"appearance.looks.outfit[{i}]", f"outfit[{i}] '{pc.item}' is not clothing (it has no clothing: block).")
                    else:
                        cov |= set(d.clothing.covers)
                miss = [x for x in ("torso", "groin") if x not in cov]
                if miss:
                    err(p, rel, "CNT-17", "appearance.looks.outfit", f"the outfit leaves the {' and the '.join(miss)} uncovered.")
                for i, g in enumerate(rec.starting_inventory):
                    if g.slot == "worn" and not g.container and g.item in all_refs and canon.get(g.item).clothing is not None:
                        err(p, rel, "CNT-17", f"starting_inventory[{i}]", f"starting_inventory[{i}] '{g.item}' is clothing worn; put it in appearance.looks.outfit instead.")
            labels = {g.label for g in rec.starting_inventory if g.label}
            for i, g in enumerate(rec.starting_inventory):
                if g.container and g.container not in labels:
                    err(p, rel, "CNT-04", f"starting_inventory[{i}].container", f"container label '{g.container}' is not the label of another item.")
            for i, t in enumerate(rec.capability.trained_responses):
                if t.cue not in cues:
                    err(p, rel, "CNT-05", f"capability.trained_responses[{i}].cue", f"cue '{t.cue}' is not in any cues.yaml.")
            for i, c in enumerate(rec.knowledge.cues):
                if c not in cues:
                    err(p, rel, "CNT-05", f"knowledge.cues[{i}]", f"cue '{c}' is not in any cues.yaml.")
            if rec.generation == "cheat" or "standing_brief" in rec.tags:
                if not p.manifest.id.startswith("cheat_"):
                    err(p, rel, "CNT-14", "generation", "a cheat dossier (generation cheat or tag standing_brief) may only live in a pack whose id starts with 'cheat_'.")
        if kind == "pc":
            g = rec.plausibility_gate
            for i, e in enumerate(list(g.pass_any) + ([g.hard_fail_all] if g.hard_fail_all else [])):
                try:
                    parse(e)
                except ConditionSyntaxError as ex:
                    err(p, rel, "CNT-09", "plausibility_gate", f"plausibility_gate expression {e!r} does not parse ({ex}).")
        if kind == "faction":
            for i, e in enumerate(rec.presence.presence_conditions):
                try:
                    parse(e)
                except ConditionSyntaxError as ex:
                    err(p, rel, "CNT-09", f"presence.presence_conditions[{i}]", f"presence condition {e!r} does not parse ({ex}).")
            seats = [ld.seat for ld in rec.leaders if ld.seat]
            if len(seats) != len(set(seats)):
                err(p, rel, "CNT-15", "leaders", "two leaders share a seat.")
            if rec.behaviour.council is not None:
                for i, s in enumerate(rec.behaviour.council.seats):
                    if s not in seats:
                        err(p, rel, "CNT-15", f"behaviour.council.seats[{i}]", f"council seat '{s}' is no leader's seat.")
        if kind == "lore":
            for i, b in enumerate(rec.beliefs):
                for j, c in enumerate(b.cues):
                    if c not in cues:
                        err(p, rel, "CNT-05", f"beliefs[{i}].cues[{j}]", f"cue '{c}' is not in any cues.yaml.")
        if kind == "affordance":
            if rec.effect not in EFFECT_IDS:
                err(p, rel, "CNT-06", "effect", f"'{rec.id}' uses effect '{rec.effect}', which the engine does not have.")
            for fld in ("label", "ui_label"):
                for ph in _re.findall(r"\{([^}]*)\}", getattr(rec, fld)):
                    if ph not in ("target", "destination", "item", "distance", "duration"):
                        err(p, rel, "CNT-06", fld, f"'{rec.id}' {fld} uses the placeholder {{{ph}}}, which the engine does not fill.")
            req = rec.requires
            if req is not None:
                for j, c in enumerate(req.belief_cues):
                    if c not in cues:
                        err(p, rel, "CNT-05", f"requires.belief_cues[{j}]", f"cue '{c}' is not in any cues.yaml.")
                if req.skill_or_belief_cue and req.skill_or_belief_cue not in cues:
                    err(p, rel, "CNT-05", "requires.skill_or_belief_cue", f"cue '{req.skill_or_belief_cue}' is not in any cues.yaml.")
        if kind == "item":
            need = {"firearm": "firearm", "melee": "melee", "container": "container", "food": "food", "water": "water", "medical": "medical", "clothing": "clothing"}
            for block in need.values():
                present = getattr(rec, block) is not None
                if rec.kind == block and not present:
                    err(p, rel, "CNT-12", block, f"'{rec.id}' is a {rec.kind} but has no {block}: block.")
                if present and rec.kind != block:
                    err(p, rel, "CNT-12", block, f"'{rec.id}' is a {rec.kind} but carries a {block}: block.")
    h = _hashlib.sha256()
    from ..kernel.jsoncanon import canonical_json
    pairs = sorted((r, canonical_json(rec.model_dump(mode="json", by_alias=True))) for k in canon.by_kind for r, rec in canon.by_kind[k].items())
    canon.content_hash = _hashlib.sha256(canonical_json([list(x) for x in pairs]).encode()).hexdigest()
    canon._pairs = pairs
    return canon, issues


def compile_packs(pack_dirs: list[str | Path], out_path: str | Path) -> CompileReport:
    import sqlite3
    canon, issues = load_canon(pack_dirs)
    ok = not any(i.severity == "error" for i in issues)
    counts = {k: len(v) for k, v in sorted(canon.by_kind.items())}
    rep = CompileReport(ok=ok, issues=issues, counts=counts, content_hash=canon.content_hash)
    if not ok:
        return rep
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = sqlite3.connect(out)
    pack_of = {}
    for p in canon.packs:
        for k in p.records:
            for r in p.records[k]:
                pack_of[r] = p.manifest.id
                b = r.rsplit("/", 1)[1]
                for o in p.manifest.overrides:
                    if o.split(":", 1)[1] == f"{k}/{b}":
                        pack_of[o] = p.manifest.id
    for k in KINDS:
        con.execute(f"CREATE TABLE {k} (ref TEXT PRIMARY KEY, pack TEXT, json TEXT)")
    for r, j in canon._pairs:
        k = r.split(":", 1)[1].split("/", 1)[0]
        con.execute(f"INSERT INTO {k} VALUES (?,?,?)", (r, pack_of.get(r, ""), j))
    con.execute("CREATE VIRTUAL TABLE lore_fts USING fts5(ref, text)")
    for r, rec in canon.by_kind.get("lore", {}).items():
        con.execute("INSERT INTO lore_fts VALUES (?,?)", (r, rec.truth + "\n" + "\n".join(b.text for b in rec.beliefs)))
    con.commit()
    con.close()
    return rep


def ref(pack_id: str, kind: str, record_id: str) -> str:
    """'<pack>:<kind>/<id>' (implemented)."""
    return f"{pack_id}:{kind}/{record_id}"
