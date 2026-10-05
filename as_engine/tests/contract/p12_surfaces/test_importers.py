"""Bringing things in (P12; D-209). content/importers.py import_file, extract_card_json, docx_text — IMP-01..04, the
D-116 voice examples; 09_CONTENT_PACKS §8.

A record file the game already reads comes in as canon when the validator passes, or waits in _drafts/ with a list
of what is wrong. A SillyTavern character card — a picture with the card hidden in it, or the card's JSON — becomes
a draft person: their name, what the card says about them, what they know, a first go at their three voice lines,
and every line of theirs in the card's example dialogue as an example of how they talk (what was said to them first,
and by whom: never naming the player's side). Its lorebook becomes lore drafts. Nothing from a card is canon until
someone fills the gaps and moves it out of _drafts/. A Word document is read as text for dossier intake.

The content folder is a temporary one holding the core pack (a link to the real one) and whatever a test brings in.
"""

from __future__ import annotations

import base64
import io
import json
import struct
import zipfile
import zlib

import pytest
import yaml

from as_engine.content.importers import docx_text, extract_card_json, import_file
from as_engine.content.pack import load_canon

pytestmark = pytest.mark.phase(12)

CARD = {
    "spec": "chara_card_v2", "spec_version": "2.0",
    "data": {
        "name": "Rosa Vance",
        "description": "{{char}} is a former paramedic, wiry and sun-browned, who never sits with her back to a door.",
        "personality": "Blunt, tired, kind when nobody is looking.",
        "scenario": "{{char}} runs the clinic tent at the river camp and has not slept properly in a week.",
        "first_mes": '*Rosa glances up from the cot.* "You\'re bleeding on my floor. Sit." *She snaps on a glove.*',
        "mes_example": ("<START>\n{{user}}: Can you look at this?\n{{char}}: \"Arm out. Don't flinch.\"\n"
                        "<START>\nMarco: We're out of gauze.\nRosa Vance: Then we use shirts. Go.\n"
                        "Rosa Vance: And boil them first.\n{{user}}: Thanks, {{char}}.\n"
                        "{{char}}: Don't thank me, {{user}}. Keep the arm clean."),
        "creator": "someone", "creator_notes": "Works best grumpy.", "tags": ["medic", "survival"],
        "character_book": {"entries": [
            {"keys": ["river camp"], "content": "The river camp sits on a gravel bar that floods every spring.", "enabled": True},
            {"keys": ["Marco"], "name": "Marco", "content": "Marco is Rosa's runner, fifteen and fast.", "enabled": True},
            {"keys": ["off"], "content": "Not used.", "enabled": False},
        ]},
    },
}


@pytest.fixture
def content(tmp_path, core_pack_dir):
    root = tmp_path / "content"
    root.mkdir()
    (root / "core").symlink_to(core_pack_dir, target_is_directory=True)
    return root


def png(chunks):
    def chunk(typ, data):
        return struct.pack(">I", len(data)) + typ + data + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    body = chunk(b"IHDR", ihdr)
    for typ, data in chunks:
        body += chunk(typ, data)
    return b"\x89PNG\r\n\x1a\n" + body + chunk(b"IEND", b"")


def b64(obj):
    return base64.b64encode(json.dumps(obj).encode("utf-8"))


def write(path, data):
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- docx / png
def test_a_word_document_read_as_text():
    xml = ('<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
           '<w:p><w:r><w:t>The Ghosts</w:t></w:r><w:r><w:t xml:space="preserve"> came at dawn.</w:t></w:r></w:p>'
           '<w:p><w:r><w:t>Five</w:t><w:tab/><w:t>to a van.</w:t><w:br/><w:t>Masked.</w:t></w:r></w:p>'
           '</w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    assert docx_text(buf.getvalue()) == "The Ghosts came at dawn.\nFive\tto a van.\nMasked."
    with pytest.raises(ValueError):
        docx_text(b"not a zip")


def test_the_card_hidden_in_a_picture():
    v2 = {"spec": "chara_card_v2", "data": {"name": "A"}}
    v3 = {"spec": "chara_card_v3", "data": {"name": "B"}}
    assert extract_card_json(png([(b"tEXt", b"chara\x00" + b64(v2))])) == v2
    assert extract_card_json(png([(b"tEXt", b"chara\x00" + b64(v2)), (b"tEXt", b"ccv3\x00" + b64(v3))])) == v3, "ccv3 wins"
    assert extract_card_json(png([(b"iTXt", b"chara\x00\x00\x00\x00\x00" + b64(v2))])) == v2
    assert extract_card_json(png([(b"tEXt", b"Comment\x00hello")])) is None
    assert extract_card_json(b"GIF89a") is None


# --------------------------------------------------------------------------- cards
def test_a_card_becomes_a_draft_person(content, tmp_path):
    res = import_file(write(tmp_path / "rosa.json", CARD), "my_content", content)
    assert res.ok and res.ref is None and res.draft_path == "my_content/_drafts/rosa_vance.yaml"
    d = yaml.safe_load((content / res.draft_path).read_text(encoding="utf-8"))
    assert (d["schema"], d["id"], d["generation"], d["identity"]) == ("as.actor.v1", "rosa_vance", "imported", {"name": "Rosa Vance"})
    assert d["knowledge"] == {"knows": ["Rosa Vance runs the clinic tent at the river camp and has not slept properly in a week."]}
    assert d["depth_reference"].startswith("## Description\n\nRosa Vance is a former paramedic")
    assert "## Personality\n\nBlunt, tired" in d["depth_reference"]
    assert d["voice"]["exemplars"] == {"low_stakes": "You're bleeding on my floor. Sit.", "under_pressure": "Arm out. Don't flinch.",
                                       "at_the_limit": "Then we use shirts. Go."}
    assert d["voice"]["examples"] == [
        {"situation": "In conversation.", "by": "", "said_to_them": "Can you look at this?", "they_say": '"Arm out. Don\'t flinch."',
         "pressure": "easy"},
        {"situation": "In conversation.", "by": "Marco", "said_to_them": "We're out of gauze.", "they_say": "Then we use shirts. Go.",
         "pressure": "easy"},
        {"situation": "In conversation.", "by": "", "said_to_them": "", "they_say": "And boil them first.", "pressure": "easy"},
        {"situation": "In conversation.", "by": "", "said_to_them": "Thanks, Rosa Vance.",
         "they_say": "Don't thank me, you. Keep the arm clean.", "pressure": "easy"},
    ], "the player's side is never named; a line after her own has nobody speaking to her"
    assert "Works best grumpy." in d["writers_notes"] and "medic" in d["writers_notes"]


def test_what_a_card_lacks_is_listed(content, tmp_path):
    res = import_file(write(tmp_path / "rosa.json", CARD), "my_content", content)
    assert "identity.age is missing." in res.gaps and "voice.capsule is missing." in res.gaps
    assert res.gaps[-2:] == ["lore_river_camp.md: check what kind of lore it is and who believes it.",
                             "lore_marco.md: check what kind of lore it is and who believes it."]
    gaps = (content / "my_content/_drafts/rosa_vance.gaps.md").read_text(encoding="utf-8").splitlines()
    assert gaps == [f"- {g}" for g in res.gaps]
    lore = (content / "my_content/_drafts/lore_marco.md").read_text(encoding="utf-8")
    front = yaml.safe_load(lore.split("---")[1])
    assert front == {"schema": "as.lore.v1", "id": "marco", "title": "Marco", "kind": "rumour",
                     "truth": "Marco is Rosa's runner, fifteen and fast.",
                     "beliefs": [{"held_by": "common", "text": "Marco is Rosa's runner, fifteen and fast.", "confidence": 2}],
                     "tags": ["imported", "review"]}
    assert not (content / "my_content/_drafts/lore_off.md").exists(), "a disabled entry is left out"


def test_drafts_never_load(content, tmp_path):
    import_file(write(tmp_path / "rosa.json", CARD), "my_content", content)
    canon, issues = load_canon([content / "core", content / "my_content"])
    assert not [r for recs in canon.by_kind.values() for r in recs if r.startswith("my_content:")]
    assert not [i for i in issues if i.severity == "error"]
    man = yaml.safe_load((content / "my_content/pack.yaml").read_text(encoding="utf-8"))
    assert man == {"schema": "as.pack.v1", "id": "my_content", "name": "My content", "version": "1.0.0",
                   "description": "What you brought in yourself.", "depends_on": ["core"]}


def test_the_card_in_a_picture(content, tmp_path):
    p = tmp_path / "rosa.png"
    p.write_bytes(png([(b"tEXt", b"chara\x00" + b64(CARD))]))
    res = import_file(p, "my_content", content)
    assert res.ok and res.draft_path == "my_content/_drafts/rosa_vance.yaml"
    p.write_bytes(png([]))
    assert import_file(p, "my_content", content).errors == ["rosa.png: there is no character card in this picture."]


# --------------------------------------------------------------------------- native records
ITEM = {"schema": "as.item.v1", "id": "silk_rope", "name": "silk rope", "plural": "silk ropes", "kind": "tool", "mass_g": 400,
        "bulk": 1, "tags": ["tool", "rope", "binding"], "barter_value": 12, "description": "Climbing silk, light and strong."}


def test_a_record_the_game_reads_comes_in_as_canon(content, tmp_path):
    res = import_file(write(tmp_path / "silk.json", ITEM), "my_content", content)
    assert (res.ok, res.ref, res.draft_path, res.gaps) == (True, "my_content:item/silk_rope", None, [])
    assert (content / "my_content/items/silk.yaml").exists()
    canon, _ = load_canon([content / "core", content / "my_content"])
    assert canon.get("my_content:item/silk_rope").name == "silk rope"
    again = import_file(write(tmp_path / "silk.json", ITEM), "my_content", content)
    assert not again.ok and "my_content/items/silk.yaml is already there" in again.errors[0], "nothing is overwritten"


def test_a_record_that_fails_waits_in_drafts(content, tmp_path):
    bad = {k: v for k, v in ITEM.items() if k != "kind"}
    res = import_file(write(tmp_path / "broken.yaml", yaml.safe_dump(bad)), "my_content", content)
    assert res.ok and res.ref is None and res.draft_path == "my_content/_drafts/broken.yaml"
    assert res.gaps and all(g.startswith("items/broken.yaml: ") for g in res.gaps) and any("kind" in g for g in res.gaps)
    assert not (content / "my_content/items/broken.yaml").exists()
    assert (content / "my_content/_drafts/broken.gaps.md").read_text(encoding="utf-8").startswith("- items/broken.yaml: ")


def test_lore_as_json_is_written_as_lore(content, tmp_path):
    lore = {"schema": "as.lore.v1", "id": "gravel_bar", "title": "The gravel bar", "kind": "place",
            "truth": "The gravel bar floods every spring and nobody camps there after March.",
            "beliefs": [{"held_by": "common", "text": "Don't sleep on the bar after March.", "confidence": 2}]}
    res = import_file(write(tmp_path / "bar.json", lore), "my_content", content)
    assert (res.ok, res.ref) == (True, "my_content:lore/gravel_bar")
    assert (content / "my_content/lore/bar.md").read_text(encoding="utf-8").startswith("---\n")


def test_documents_go_to_intake(content, tmp_path):
    for name, text in (("notes.txt", "Rosa runs the clinic."), ("notes.md", "# Rosa\nShe runs the clinic.")):
        res = import_file(write(tmp_path / name, text), "my_content", content)
        assert res.errors == [f"{name}: a document is turned into a record with dossier intake, not imported directly."]
    assert not import_file(write(tmp_path / "x.csv", "a,b"), "my_content", content).ok
    assert not import_file(write(tmp_path / "silk.json", ITEM), "My Content", content).ok, "not a pack name"


# --------------------------------------------------------------------------- the Content screen
def test_dropped_on_the_content_screen(content, tmp_path, fake, monkeypatch):
    """GameService.on_content_import (D-209): the dropped bytes pass through <pack>/_incoming/ and are gone after;
    only the file's own name is used; a pack name that is not one writes nothing."""
    import asyncio

    from protocol_kit import only, send

    from as_engine.contracts.settings import EngineConfig
    from as_engine.service import game_service
    monkeypatch.setattr(game_service, "_SERVICE", None)
    svc = game_service.GameService(EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(content)), fake,
                                   config_path=str(tmp_path / "as_config.yaml"))
    data = base64.b64encode(json.dumps(CARD).encode("utf-8")).decode("ascii")
    got = only(asyncio.run(send(svc, "content_import", filename="C:\\cards\\rosa.json", data_b64=data)), "import_result")
    assert got["ok"] and got["draft_path"] == "my_content/_drafts/rosa_vance.yaml" and got["errors"] == []
    assert not (content / "my_content/_incoming").exists()
    assert only(asyncio.run(send(svc, "content_import", filename="x.json", data_b64="not base64!")), "error")["code"] == "bad_request"
    bad = only(asyncio.run(send(svc, "content_import", filename="x.json", data_b64=data, pack_id="../evil")), "import_result")
    assert bad["ok"] is False and not (tmp_path / "evil").exists() and not (content.parent / "evil").exists()
