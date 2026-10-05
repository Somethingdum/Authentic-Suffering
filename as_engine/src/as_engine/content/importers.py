"""Importers (P12). Rules IMP-01..06. Nothing imported enters canon until the validator passes;
drafts are written to <content_dir>/<pack>/_drafts/ with a sibling .gaps.md listing missing fields
in plain language.

import_file(path, pack_id, content_dir) -> ImportResult
  .yaml/.yml/.json with 'schema' -> native record, validated, copied into the pack folder.
  .md with front matter -> native record (body -> depth_reference).
  .png with a 'ccv3' or 'chara' tEXt chunk (base64 JSON) or .json with spec 'chara_card_v2'/'chara_card_v3'
    -> character card conversion (IMP-03):
       name -> identity.name; description/personality -> depth_reference + seeds for
       appearance/traits; scenario -> knowledge.knows; first_mes + mes_example -> voice exemplar
       candidates (up to 3 lines of the character's own speech, cleaned of {{char}}/{{user}});
       (D-116) mes_example -> voice.examples, one per line of the character's in it, in order (at
       most 60): split on '<START>'; a line opening '{{char}}:' or '<the card's name>:' is the
       character's, any other 'X:' line someone else's. Each character line is an example
       {situation 'In conversation.', by '' after a '{{user}}:' line (the player's side is never
       named) else that X, said_to_them the other line just before it in the same block or '',
       they_say the line without its prefix, '{{char}}' and '{{user}}' made the card's name and
       'you', cut to 800 characters (said_to_them to 400), pressure 'easy'} — a card's example
       dialogue is exactly the history D-116 shows a model;
       character_book entries -> LoreEntry drafts (truth = entry content; belief = same text with
       confidence 2; flagged for review). Everything the card lacks goes to .gaps.md.
  .txt/.docx/.md without front matter -> not auto-imported; use dossier intake (below).
  .docx text extraction: unzip word/document.xml and join <w:t> runs per <w:p> (no python-docx).

D-209 — the details (P12, IMP-01..04):
ImportResult: ok = something came in — as canon (ref = the first record's ref '<pack>:<kind>/<id>') or as
  a draft (draft_path = the draft file, posix, relative to content_dir; gaps = plain-language lines,
  one per thing missing or wrong). ok False -> errors says why nothing came in (one line each).
  The pack: pack_id must match the slug pattern (errors otherwise); a missing <content_dir>/<pack_id>/
  pack.yaml is created (schema as.pack.v1, id = pack_id, name = pack_id with '_' as spaces and the
  first letter capitalised, version '1.0.0', description 'What you brought in yourself.',
  depends_on ['core']). Nothing outside <content_dir>/<pack_id>/ is ever written.
  Validation is the loader's: content.pack.load_canon([<content_dir>/core, the pack]) (the core pack
  alone when pack_id is 'core'); the file's issues are those of that pack whose ``file`` is the new
  file's path in it, severity 'error'.
Native files (a mapping with 'schema', or a list of them): the folder is the one content.pack lays
  out for the schema (as.infected.v1 / as.infected_state.v1 / as.quirk.v1 -> infected/); an unknown
  schema -> errors. A .md keeps its front matter and body when its kind is actor, pc, faction or
  lore (the loader reads those as .md; lore only as .md) — any other kind as .md -> errors; a .json
  or a .yml becomes '<stem>.yaml' (yaml.safe_dump, keys in file order, unicode kept); a .yaml is
  copied as written; lore from a .yaml / .yml / .json becomes '<stem>.md' with the mapping as its
  front matter (one entry to a file: a list of lore -> errors). The target is <pack>/<folder>/<stem>.<ext>; a file already there -> errors
  (nothing is overwritten). Written, then validated: no error issue and the record in the loaded
  canon -> canon (ok, ref); else ('<file in pack>: the record did not load.' when it has no issue
  but is not there) the
  file moves to <pack>/_drafts/<same name> with <stem>.gaps.md beside it (the issues' messages,
  one per line, each after '- ') and ok with draft_path and gaps = those messages.
Cards: card = extract_card_json(png) or the .json mapping; data = card['data'] when it is a mapping
  there (v2 / v3), else the card itself (a v1 card in a picture). No non-empty data.name ->
  errors. clean(text) = text with '{{char}}' / '<BOT>' made the card's name and '{{user}}' /
  '<USER>' made 'you' (case-insensitive), stripped. id = the name lower-cased, every run of
  characters other than a-z and 0-9 made one '_', '_' trimmed (empty -> 'imported_character').
  The draft (an ActorDossier mapping, written as YAML to <pack>/_drafts/<id>.yaml, never canon):
    schema 'as.actor.v1', id, generation 'imported', identity {name}, knowledge {knows: [clean(
    scenario)] when there is one}, voice {exemplars: the candidates as low_stakes, under_pressure,
    at_the_limit in that order (those there are), examples (D-116, below)}, depth_reference =
    '## Description' and '## Personality' sections of clean(description) / clean(personality)
    (those not empty; none -> no depth_reference), writers_notes = 'Imported from <file name>' +
    the card's creator, its creator_notes and its tags when present (human-only).
  Speech of a message: the runs between double quotes (straight or curly) joined with ' ', or —
    with no quotes — the message with every *…* action removed; stripped, cut to 300 characters.
  Candidates: the speech of clean(first_mes), then of each character line of mes_example (below),
    the non-empty ones of at least 5 characters, the first three.
  Example lines (D-116): mes_example split on '<START>' (case-insensitive); in each block, a line
    matching '^([^:\\n]{1,40}):\\s*(.*)$' starts a line of that speaker; any other non-empty line
    joins the line before it (' '); a speaker '{{char}}' or the card's name (any case) is the
    character's, '{{user}}' / '<USER>' the player's, anyone else someone else's.
  Lore: each character_book entry (data.character_book.entries, enabled not false, content not
    empty) -> a LoreEntry draft <pack>/_drafts/lore_<eid>.md, eid = the id rule over its name or
    comment or first key (none -> f"{id}_{n}", n from 1), title = that text, kind 'rumour', truth =
    clean(content), beliefs [{held_by 'common', text: the same, confidence 2}], tags ['imported',
    'review'] — front matter only.
  gaps: every error of ActorDossier.model_validate(draft), in pydantic's order, as '<field> is
    missing.' (type 'missing'), '<field>: <msg>.' otherwise (field = the dotted path); then one
    line per lore draft ('lore_<eid>.md: check what kind of lore it is and who believes it.').
    Written to <pack>/_drafts/<id>.gaps.md as '- <line>' lines. ok, draft_path = the actor draft.
  A draft already there under that name is replaced (an import of the same card again).
.txt / .docx / a .md without front matter -> errors ['<file>: a document is turned into a record with
  dossier intake, not imported directly.']; any other extension -> errors (unknown file type).
extract_card_json(png_bytes) -> dict | None: not a PNG (signature) -> None. Walk the chunks; a tEXt
  chunk (keyword, NUL, latin-1 text) or an uncompressed iTXt chunk (keyword, NUL, flag 0, method,
  language NUL, translated NUL, utf-8 text) with keyword 'ccv3' or 'chara': base64-decode, utf-8,
  JSON; a mapping -> it. 'ccv3' wins over 'chara' when both are there. Nothing usable -> None.
docx_text(docx_bytes) -> str: word/document.xml from the zip; per <w:p> in document order the text of
  its <w:t> runs joined as written, a <w:tab/> as '\\t', a <w:br/> as '\\n'; paragraphs joined with
  '\\n'. Not a zip, or no word/document.xml -> ValueError.

Dossier intake (IMP-05, the 'dump a big document in' path — e.g. the Ghost faction corpus):
  intake_document(text, target_kind, pack_id) -> IntakeJob
  1. chunk the text into <= 12,000-token sections on heading boundaries;
  2. lane A (the Writer: the long context) DOSSIER_INTAKE call per section with the target schema field list
     -> partial JSON; 3. merge partials field by field (later sections append to lists, never
     overwrite a non-empty string); 4. validate; 5. write draft + gaps; 6. report progress
     (intake_progress) after each section. The user reviews and moves the draft into the pack.
  The engine never auto-publishes an intake draft into canon (IMP-06).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ImportResult:
    ok: bool
    draft_path: str | None = None
    gaps: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    ref: str | None = None


def import_file(path: str | Path, pack_id: str, content_dir: str | Path) -> ImportResult:
    raise NotImplementedError("P12")


def extract_card_json(png_bytes: bytes) -> dict | None:
    raise NotImplementedError("P12")


def docx_text(docx_bytes: bytes) -> str:
    raise NotImplementedError("P12")
from ._impl_importers import docx_text, extract_card_json, import_file  # noqa: E402,F811
