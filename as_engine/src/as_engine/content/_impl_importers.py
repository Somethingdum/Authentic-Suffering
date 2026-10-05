"""Bodies of content/importers.py (D-209). The contract is that module's docstring."""

from __future__ import annotations

import base64
import json
import re
import shutil
import struct
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import yaml

from .importers import ImportResult

_SLUG = re.compile(r"^[a-z0-9_]+$")
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_LINE = re.compile(r"^([^:\n]{1,40}):\s*(.*)$")
_QUOTED = re.compile(r"[\"“]([^\"“”]+)[\"”]")
_ACTION = re.compile(r"\*[^*]*\*")
_MD_KINDS = ("actor", "pc", "faction", "lore")


# ---------------------------------------------------------------------------------------------- docx
def docx_text(docx_bytes: bytes) -> str:
    import io
    try:
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
            xml = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as e:
        raise ValueError("not a .docx with word/document.xml") from e
    root = ElementTree.fromstring(xml)
    paras = []
    for p in root.iter(f"{_W}p"):
        out = []
        for el in p.iter():
            if el.tag == f"{_W}t":
                out.append(el.text or "")
            elif el.tag == f"{_W}tab":
                out.append("\t")
            elif el.tag == f"{_W}br":
                out.append("\n")
        paras.append("".join(out))
    return "\n".join(paras)


# ---------------------------------------------------------------------------------------------- png
def extract_card_json(png_bytes: bytes) -> dict | None:
    if png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    found: dict[str, str] = {}
    i = 8
    while i + 8 <= len(png_bytes):
        n, typ = struct.unpack(">I4s", png_bytes[i:i + 8])
        data = png_bytes[i + 8:i + 8 + n]
        i += 12 + n
        if typ == b"tEXt" and b"\x00" in data:
            key, text = data.split(b"\x00", 1)
            found.setdefault(key.decode("latin-1"), text.decode("latin-1"))
        elif typ == b"iTXt" and b"\x00" in data:
            key, rest = data.split(b"\x00", 1)
            if len(rest) >= 2 and rest[0] == 0:
                parts = rest[2:].split(b"\x00", 2)
                if len(parts) == 3:
                    found.setdefault(key.decode("latin-1"), parts[2].decode("utf-8", "replace"))
        elif typ == b"IEND":
            break
    for key in ("ccv3", "chara"):
        raw = found.get(key)
        if raw is None:
            continue
        try:
            card = json.loads(base64.b64decode(raw).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(card, dict):
            return card
    return None


# ---------------------------------------------------------------------------------------------- import
def _pack_dir(content_dir: Path, pack_id: str) -> Path:
    d = content_dir / pack_id
    mf = d / "pack.yaml"
    if not mf.exists():
        d.mkdir(parents=True, exist_ok=True)
        name = pack_id.replace("_", " ")
        mf.write_text(yaml.safe_dump({"schema": "as.pack.v1", "id": pack_id, "name": name[:1].upper() + name[1:],
                                      "version": "1.0.0", "description": "What you brought in yourself.",
                                      "depends_on": ["core"]}, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return d


def _rel(content_dir: Path, f: Path) -> str:
    return f.relative_to(content_dir).as_posix()


def _issues_for(content_dir: Path, pack_id: str, rel_in_pack: str) -> tuple[list[str], set[str]]:
    from .pack import load_canon
    core = content_dir / "core"
    pack = content_dir / pack_id
    dirs = [core] if pack.resolve() == core.resolve() else [core, pack]
    canon, issues = load_canon(dirs)
    loaded = {r for recs in canon.by_kind.values() for r in recs}
    return [i.message for i in issues if i.pack == pack_id and i.file == rel_in_pack and i.severity == "error"], loaded


def _folder_of(schema: str) -> tuple[str, str] | None:
    from .pack import _FOLDERS, _INFECTED, _SCHEMA_OF
    if schema in _INFECTED:
        return "infected", _INFECTED[schema][0]
    for kind, sch in _SCHEMA_OF.items():
        if sch == schema:
            return next(f for f, k, _c in _FOLDERS if k == kind), kind
    return None


def _write_gaps(path: Path, lines: list[str]) -> None:
    path.write_text("".join(f"- {line}\n" for line in lines), encoding="utf-8")


def _native(src: Path, data, body_text: str | None, pack_id: str, content_dir: Path) -> ImportResult:
    recs = data if isinstance(data, list) else [data]
    if not recs or not all(isinstance(r, dict) and r.get("schema") for r in recs):
        return ImportResult(ok=False, errors=[f"{src.name}: every record needs a 'schema' line."])
    where = _folder_of(recs[0]["schema"])
    if where is None:
        return ImportResult(ok=False, errors=[f"{src.name}: the schema '{recs[0]['schema']}' is not one the game knows."])
    folder, kind = where
    ext = src.suffix.lower()
    if ext == ".md" and kind not in _MD_KINDS:
        return ImportResult(ok=False, errors=[f"{src.name}: only people, factions and lore can be written as .md."])
    if kind == "lore" and isinstance(data, list):
        return ImportResult(ok=False, errors=[f"{src.name}: lore comes one entry to a file."])
    pack = _pack_dir(content_dir, pack_id)
    out_ext = ".md" if ext == ".md" or kind == "lore" else ".yaml"
    target = pack / folder / f"{src.stem}{out_ext}"
    if target.exists():
        return ImportResult(ok=False, errors=[f"{src.name}: {_rel(content_dir, target)} is already there; rename the file "
                                              "to bring it in alongside."])
    target.parent.mkdir(parents=True, exist_ok=True)
    if ext == ".md" or (ext == ".yaml" and kind != "lore"):
        shutil.copyfile(src, target)
    elif kind == "lore":
        target.write_text("---\n" + yaml.safe_dump(data, sort_keys=False, allow_unicode=True) + "---\n", encoding="utf-8")
    else:
        target.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    rel_in_pack = target.relative_to(pack).as_posix()
    problems, loaded = _issues_for(content_dir, pack_id, rel_in_pack)
    from .pack import ref
    r = ref(pack_id, kind, str(recs[0].get("id")))
    if not problems and r not in loaded:
        problems = [f"{rel_in_pack}: the record did not load."]
    if not problems:
        return ImportResult(ok=True, ref=r)
    drafts = pack / "_drafts"
    drafts.mkdir(exist_ok=True)
    moved = drafts / target.name
    shutil.move(str(target), str(moved))
    _write_gaps(drafts / f"{target.stem}.gaps.md", problems)
    return ImportResult(ok=True, draft_path=_rel(content_dir, moved), gaps=problems)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")


def _cleaner(name: str):
    def clean(text) -> str:
        t = str(text or "")
        t = re.sub(r"\{\{char\}\}|<BOT>", name, t, flags=re.I)
        t = re.sub(r"\{\{user\}\}|<USER>", "you", t, flags=re.I)
        return t.strip()
    return clean


def _speech(message: str) -> str:
    quoted = [q.strip() for q in _QUOTED.findall(message) if q.strip()]
    text = " ".join(quoted) if quoted else _ACTION.sub("", message)
    return re.sub(r"\s+", " ", text).strip()[:300]


def _example_lines(mes_example: str, name: str):
    """(block index, speaker kind, speaker label, text) per line of the example dialogue, in order."""
    out = []
    for bi, block in enumerate(re.split(r"<START>", mes_example or "", flags=re.I)):
        cur = None
        for raw in block.splitlines():
            line = raw.strip()
            if not line:
                continue
            m = _LINE.match(line)
            if m:
                if cur:
                    out.append(cur)
                who = m.group(1).strip()
                low = who.lower()
                kind = "char" if low in ("{{char}}", "<bot>", name.lower()) else "user" if low in ("{{user}}", "<user>") else "other"
                cur = [bi, kind, who, m.group(2).strip()]
            elif cur:
                cur[3] = (cur[3] + " " + line).strip()
        if cur:
            out.append(cur)
    return [tuple(x) for x in out]


def _voice_examples(lines, clean) -> list[dict]:
    out = []
    for n, (bi, kind, who, text) in enumerate(lines):
        if kind != "char":
            continue
        prev = lines[n - 1] if n > 0 and lines[n - 1][0] == bi and lines[n - 1][1] != "char" else None
        out.append({"situation": "In conversation.",
                    "by": "" if prev is None or prev[1] == "user" else clean(prev[2]),
                    "said_to_them": clean(prev[3])[:400] if prev is not None else "",
                    "they_say": clean(text)[:800], "pressure": "easy"})
        if len(out) == 60:
            break
    return out


def _plain(errors) -> list[str]:
    from .pack import _loc
    out = []
    for er in errors:
        loc = _loc(er["loc"]) or "the record"
        out.append(f"{loc} is missing." if er["type"] == "missing" else f"{loc}: {er['msg']}.")
    return out


def _card(src: Path, card: dict, pack_id: str, content_dir: Path) -> ImportResult:
    from pydantic import ValidationError

    from ..contracts.dossier import ActorDossier
    data = card.get("data") if isinstance(card.get("data"), dict) else card
    name = str(data.get("name") or "").strip()
    if not name:
        return ImportResult(ok=False, errors=[f"{src.name}: the card has no name."])
    clean = _cleaner(name)
    rid = _slug(name) or "imported_character"
    lines = _example_lines(str(data.get("mes_example") or ""), name)
    cands = [_speech(clean(data.get("first_mes") or ""))] + [_speech(clean(t)) for _b, k, _w, t in lines if k == "char"]
    cands = [c for c in cands if len(c) >= 5][:3]
    voice: dict = {"exemplars": dict(zip(("low_stakes", "under_pressure", "at_the_limit"), cands))}
    examples = _voice_examples(lines, clean)
    if examples:
        voice["examples"] = examples
    draft: dict = {"schema": "as.actor.v1", "id": rid, "generation": "imported", "identity": {"name": name}}
    if clean(data.get("scenario")):
        draft["knowledge"] = {"knows": [clean(data.get("scenario"))]}
    draft["voice"] = voice
    depth = [f"## {title}\n\n{clean(data.get(key))}" for title, key in (("Description", "description"), ("Personality", "personality"))
             if clean(data.get(key))]
    if depth:
        draft["depth_reference"] = "\n\n".join(depth)
    notes = [f"Imported from {src.name}."]
    if data.get("creator"):
        notes.append(f"Card by {data['creator']}.")
    if data.get("creator_notes"):
        notes.append(str(data["creator_notes"]).strip())
    if data.get("tags"):
        notes.append("Card tags: " + ", ".join(str(t) for t in data["tags"]) + ".")
    draft["writers_notes"] = " ".join(notes)
    pack = _pack_dir(content_dir, pack_id)
    drafts = pack / "_drafts"
    drafts.mkdir(exist_ok=True)
    try:
        ActorDossier.model_validate(draft)
        gaps: list[str] = []
    except ValidationError as e:
        gaps = _plain(e.errors())
    book = data.get("character_book") if isinstance(data.get("character_book"), dict) else {}
    taken: set[str] = set()
    for n, entry in enumerate(book.get("entries") or [], start=1):
        if not isinstance(entry, dict) or entry.get("enabled") is False or not clean(entry.get("content")):
            continue
        keys = entry.get("keys") or []
        title = str(entry.get("name") or entry.get("comment") or (keys[0] if keys else "") or "").strip()
        eid = _slug(title) or f"{rid}_{n}"
        while eid in taken:
            eid = f"{eid}_{n}"
        taken.add(eid)
        text = clean(entry.get("content"))
        front = {"schema": "as.lore.v1", "id": eid, "title": title or eid, "kind": "rumour", "truth": text,
                 "beliefs": [{"held_by": "common", "text": text, "confidence": 2}], "tags": ["imported", "review"]}
        (drafts / f"lore_{eid}.md").write_text("---\n" + yaml.safe_dump(front, sort_keys=False, allow_unicode=True) + "---\n",
                                               encoding="utf-8")
        gaps.append(f"lore_{eid}.md: check what kind of lore it is and who believes it.")
    target = drafts / f"{rid}.yaml"
    target.write_text(yaml.safe_dump(draft, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")
    _write_gaps(drafts / f"{rid}.gaps.md", gaps)
    return ImportResult(ok=True, draft_path=_rel(content_dir, target), gaps=gaps)


def import_file(path: str | Path, pack_id: str, content_dir: str | Path) -> ImportResult:
    src = Path(path)
    content_dir = Path(content_dir)
    if not _SLUG.match(pack_id or ""):
        return ImportResult(ok=False, errors=[f"'{pack_id}' is not a pack name the game can use (lower-case letters, "
                                              "digits and '_')."])
    ext = src.suffix.lower()
    intake = [f"{src.name}: a document is turned into a record with dossier intake, not imported directly."]
    try:
        if ext == ".png":
            card = extract_card_json(src.read_bytes())
            if card is None:
                return ImportResult(ok=False, errors=[f"{src.name}: there is no character card in this picture."])
            return _card(src, card, pack_id, content_dir)
        if ext in (".txt", ".docx"):
            return ImportResult(ok=False, errors=intake)
        text = src.read_text(encoding="utf-8")
        if ext == ".md":
            m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
            if not m:
                return ImportResult(ok=False, errors=intake)
            data = yaml.safe_load(m.group(1))
            return _native(src, data, m.group(2), pack_id, content_dir)
        if ext == ".json":
            data = json.loads(text)
            if isinstance(data, dict) and data.get("spec") in ("chara_card_v2", "chara_card_v3"):
                return _card(src, data, pack_id, content_dir)
            return _native(src, data, None, pack_id, content_dir)
        if ext in (".yaml", ".yml"):
            return _native(src, yaml.safe_load(text), None, pack_id, content_dir)
    except (yaml.YAMLError, json.JSONDecodeError, UnicodeDecodeError) as e:
        return ImportResult(ok=False, errors=[f"{src.name}: could not be read ({str(e).splitlines()[0]})."])
    return ImportResult(ok=False, errors=[f"{src.name}: the game does not know what to do with a '{ext or 'no'}' file."])
