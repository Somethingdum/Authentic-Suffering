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
       character_book entries -> LoreEntry drafts (truth = entry content; belief = same text with
       confidence 2; flagged for review). Everything the card lacks goes to .gaps.md.
  .txt/.docx/.md without front matter -> not auto-imported; use dossier intake (below).
  .docx text extraction: unzip word/document.xml and join <w:t> runs per <w:p> (no python-docx).

Dossier intake (IMP-05, the 'dump a big document in' path — e.g. the Ghost faction corpus):
  intake_document(text, target_kind, pack_id) -> IntakeJob
  1. chunk the text into <= 12,000-token sections on heading boundaries;
  2. lane A (Cascade, 1M context) DOSSIER_INTAKE call per section with the target schema field list
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
