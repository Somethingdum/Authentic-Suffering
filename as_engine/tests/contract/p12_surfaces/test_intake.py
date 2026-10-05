"""A document becomes a record (P12; D-210). content/importers.py intake_sections, field_guide, intake_document —
IMP-05/06; GameService on_intake_start; 09_CONTENT_PACKS §8.1.

"Dump a big document in": the owner's lore and their people are written as long documents. The Writer reads one
section at a time with the list of fields the record has, fills only what the section supports, and the parts are
merged — later sections add to lists and never overwrite what an earlier one filled. What the model notices
contradicting itself, and everything still missing, is listed beside the draft. Nothing becomes canon by itself.
"""

from __future__ import annotations

import asyncio
import base64

import pytest
import yaml

from as_engine.content import importers
from as_engine.content.importers import field_guide, intake_document, intake_sections
from as_engine.contracts.common import CallClass
from as_engine.contracts.settings import EngineConfig
from as_engine.lanes.client import LaneClient

pytestmark = pytest.mark.phase(12)

DOC = """# Rosa Vance
Rosa ran the clinic tent at the river camp. She was a paramedic before the Fall.

# How she talks
"Arm out. Don't flinch," she says to anyone who comes in bleeding.

# The flood year
The camp moved twice that spring.
"""


@pytest.fixture
def content(tmp_path, core_pack_dir):
    root = tmp_path / "content"
    root.mkdir()
    (root / "core").symlink_to(core_pack_dir, target_is_directory=True)
    return root


def test_sections_follow_the_headings(monkeypatch):
    assert intake_sections("   \n") == []
    assert intake_sections(DOC) == [DOC.strip()], "a short document is one section"
    monkeypatch.setattr(importers, "INTAKE_SECTION_TOKENS", 40)
    assert intake_sections(DOC) == [
        "# Rosa Vance\nRosa ran the clinic tent at the river camp. She was a paramedic before the Fall.",
        "# How she talks\n\"Arm out. Don't flinch,\" she says to anyone who comes in bleeding.\n\n# The flood year\nThe camp moved twice that spring.",
    ]
    long = "# Long\n" + "\n\n".join(["word " * 20] * 3)
    parts = intake_sections(long)
    assert len(parts) == 3 and all(len(p) // 4 <= 40 for p in parts), "a block too big alone is cut between paragraphs"
    monkeypatch.setattr(importers, "INTAKE_SECTION_TOKENS", 5)
    assert [len(p) for p in intake_sections("x" * 45)] == [20, 20, 5], "a paragraph too big is cut hard"


def test_the_field_list_the_writer_is_given():
    g = field_guide("actor").splitlines()
    assert "identity.sex: one of female | male | other" in g
    assert "voice.examples[].they_say: text — What this person said, in their own words." in g
    assert not [x for x in g if x.split(":")[0] in ("schema", "id", "generation", "writers_notes")]
    assert "truth: text" in field_guide("lore").splitlines()


def client_with(fake):
    return LaneClient(EngineConfig(), fake)


def test_a_document_becomes_a_draft(content, fake, monkeypatch):
    monkeypatch.setattr(importers, "INTAKE_SECTION_TOKENS", 40)
    fake.script(CallClass.DOSSIER_INTAKE, {"identity": {"name": "Rosa Vance", "age": 41},
                                           "voice": {"speech_tendencies": ["short orders"]}, "_conflicts": ["41 or 43?"]})
    fake.script(CallClass.DOSSIER_INTAKE, {"identity": {"name": "Rosa V.", "sex": "female"},
                                           "voice": {"speech_tendencies": ["short orders", "never says please"]}})
    seen = []

    async def step(i, n):
        seen.append((i, n))
    res = asyncio.run(intake_document(client_with(fake), DOC, "actor", "my_content", content, name="rosa.md", on_section=step))
    assert seen == [(1, 2), (2, 2)]
    assert res.ok and res.ref is None and res.draft_path == "my_content/_drafts/rosa_vance.yaml"
    d = yaml.safe_load((content / res.draft_path).read_text(encoding="utf-8"))
    assert (d["schema"], d["id"], d["generation"]) == ("as.actor.v1", "rosa_vance", "imported")
    assert d["identity"] == {"name": "Rosa Vance", "age": 41, "sex": "female"}, "a filled field is never overwritten"
    assert d["voice"]["speech_tendencies"] == ["short orders", "never says please"], "lists grow"
    assert "_conflicts" not in d and "conflict: 41 or 43?" in res.gaps and "identity.cohort is missing." in res.gaps
    reqs = fake.calls(CallClass.DOSSIER_INTAKE)
    user = reqs[0].messages[-1].content
    assert "identity.sex: one of female | male | other" in user and "Rosa ran the clinic tent" in user
    assert "The camp moved twice" not in user and "The camp moved twice" in reqs[1].messages[-1].content


def test_a_section_the_model_fails_is_a_gap(content, fake):
    fake.fail(CallClass.DOSSIER_INTAKE, "lane_error")
    res = asyncio.run(intake_document(client_with(fake), "Ghosts come in vans.", "lore", "my_content", content, name="ghosts.txt"))
    assert res.ok and res.draft_path == "my_content/_drafts/ghosts.md"
    assert res.gaps[0] == "section 1 of 1: the model gave nothing usable."
    assert (content / res.draft_path).read_text(encoding="utf-8").startswith("---\nschema: as.lore.v1\nid: ghosts\n")


def test_nothing_to_read(content, fake):
    res = asyncio.run(intake_document(client_with(fake), "  ", "faction", "my_content", content, name="empty.txt"))
    assert res.errors == ["empty.txt: there is nothing in it to read."] and not fake.calls(CallClass.DOSSIER_INTAKE)


def test_on_the_content_screen(content, tmp_path, fake, monkeypatch):
    """GameService.on_intake_start: answered at once with the number of sections, then progress per section and the
    result — a draft, never canon."""
    from protocol_kit import only, send

    from as_engine.service import game_service
    monkeypatch.setattr(game_service, "_SERVICE", None)
    svc = game_service.GameService(EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(content)), fake,
                                   config_path=str(tmp_path / "as_config.yaml"))
    pushed = []

    async def collect(m):
        pushed.append(m)
    svc.subscribe(collect)
    fake.script(CallClass.DOSSIER_INTAKE, {"name": "The river camp"})
    data = base64.b64encode(DOC.encode("utf-8")).decode("ascii")

    async def go():
        first = await send(svc, "intake_start", filename="camp.md", data_b64=data, target_kind="faction")
        await svc.intake_task
        return first
    first = asyncio.run(go())
    assert only(first, "intake_progress") == {"name": "camp.md", "done": 0, "total": 1}
    assert [m["data"] for m in pushed if m["action"] == "intake_progress"] == [{"name": "camp.md", "done": 1, "total": 1}]
    result = [m["data"] for m in pushed if m["action"] == "intake_result"]
    assert len(result) == 1 and result[0]["ok"] and result[0]["draft_path"] == "my_content/_drafts/the_river_camp.yaml"
    assert result[0]["ref"] is None and not (content / "my_content" / "factions").exists()
