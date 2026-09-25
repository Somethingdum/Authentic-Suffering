"""Nothing in the game admits it exists (P12). Rule CHEAT-03 (CHEATS.md §2).

No prompt that a person in the world or the narrator reads, and no play screen, carries the word,
the persona's name or a command word. (The guide's own deflection and the persona's prompt are
the two places allowed to know.)
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.phase(12)

ROOT = Path(__file__).resolve().parents[4]
PROMPTS = ROOT / "as_engine" / "src" / "as_engine" / "prompts"
PLAY = ROOT / "talemate_frontend" / "src" / "play"
WORDS = ("2508", "cheater", "cheat", "god mode", "noclip", "/spawn", "/god", "/give", "sandbox")


def test_no_mind_and_no_narrator_is_told():
    seen = []
    for f in sorted(PROMPTS.glob("*.j2")):
        if f.name.startswith(("cheat_persona.", "guide.")):
            continue
        t = f.read_text(encoding="utf-8").lower()
        seen += [(f.name, w) for w in WORDS if w in t]
    assert seen == []


def test_no_play_screen_names_the_word_or_the_voice():
    seen = []
    for f in sorted(list(PLAY.glob("*.vue")) + list(PLAY.glob("words.js"))):
        t = f.read_text(encoding="utf-8").lower()
        seen += [(f.name, w) for w in ("2508", "mr. cheater", "cheater man", "cheat code") if w in t]
    assert seen == []


def test_the_canned_lines_are_the_document_s():
    """CHEAT-09: the machine copy of CHEATS.md §5's canned lines is CANNED_LINES; the two match."""
    import re

    from as_engine.cheats.commands import CANNED_LINES, DEACTIVATION_LINE
    doc = (ROOT / "docs" / "as" / "CHEATS.md").read_text(encoding="utf-8")
    table = {}
    for m in re.finditer(r"^\| `/(\w+)` \| (\".*\") \|$", doc, re.M):
        table[m.group(1)] = tuple(re.findall(r"\"([^\"]*)\"", m.group(2)))
    assert table.pop("off") == (DEACTIVATION_LINE,)
    assert table == {k: v for k, v in CANNED_LINES.items() if k != "off"}
