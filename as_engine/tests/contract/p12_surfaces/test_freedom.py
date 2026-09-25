"""Freedom of the narrative (P12). Rules FREE-01..03; DECISIONS D-104; 02 §10.

The owner: "I expect the finished product to have total freedom of narrative, amongst every Actor
and myself included. No limitations." The prompts say so, and nothing in them holds the models back.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from as_engine.contracts.settings import RunSettings

pytestmark = pytest.mark.phase(12)

PROMPTS = Path(__file__).resolve().parents[3] / "src" / "as_engine" / "prompts"
SOFTENERS = ("tasteful", "family-friendly", "family friendly", "fade to black", "fades to black", "keep it clean",
             "pg-13", "as an ai", "content policy", "inappropriate", "avoid graphic", "avoid explicit", "tone it down",
             "tone down", "be respectful", "stay respectful", "wholesome")


def test_the_narrator_fades_nothing_out():
    """FREE-01, and CNT-11 said where the narrator reads it."""
    system = (PROMPTS / "narration.system.j2").read_text(encoding="utf-8")
    assert ("Nothing that was perceived is skipped, summarised away or faded out because it is ugly: violence, cruelty, "
            "degradation, drugs, and sex between adults are told as plainly as anything else.") in system
    assert "Nothing sexual ever involves a child." in system


def test_a_person_may_do_anything_that_follows_from_who_they_are():
    """FREE-02."""
    core = (PROMPTS / "_actor_core.j2").read_text(encoding="utf-8")
    assert ("Nothing is off limits because it is ugly: you may lie, steal, threaten, hurt, kill, betray or abandon "
            "someone when that follows from who you are and what you understand.") in core


def test_no_prompt_holds_the_models_back():
    """FREE-02: no softening or refusal phrase in any prompt."""
    seen = []
    for f in sorted(PROMPTS.glob("*.j2")):
        t = f.read_text(encoding="utf-8").lower()
        seen += [(f.name, w) for w in SOFTENERS if w in t]
    assert seen == []


def test_the_only_levers_are_the_owner_s():
    """FREE-03: Full unless the owner picks Softer."""
    assert RunSettings.model_fields["intensity"].default == "full"
