"""How the narrator writes the dead feeding (P7, the owner's I1). prompts/narration.system.j2.

The owner: "be highly graphic with infected. It's a big part of the horror aspect. They don't just
bite you and waddle off ... They eat you alive. Feast on you while you watch." The narrator writes
only what the person perceived (a bite reads "... is being eaten alive"); the prompt tells it not
to look away — and, when the one being eaten is a child, to stay with the sound and the faces of
those watching instead of the child's body.
"""

from __future__ import annotations

import pytest

from as_engine.prompts.render import PROMPT_DIR

pytestmark = pytest.mark.phase(7)


def test_the_narrator_does_not_look_away():
    system = (PROMPT_DIR / "narration.system.j2").read_text(encoding="utf-8")
    assert "The dead do not kill cleanly. They hold on and eat a living person, and the person is aware of it." in system
    assert "the grip, the teeth, flesh torn away, blood, the screaming" in system
    assert "without relish and without softening it" in system


def test_a_child_is_never_described():
    system = (PROMPT_DIR / "narration.system.j2").read_text(encoding="utf-8")
    assert ("When the one being eaten is a child, do not describe the child's body or wounds. Stay with the sound, "
            "with where the person you follow is, and with the faces of the people watching.") in system


def test_the_rules_still_come_first():
    """The horror is written only from what was perceived: the hard rules stand above the style."""
    system = (PROMPT_DIR / "narration.system.j2").read_text(encoding="utf-8")
    assert system.index("Write ONLY what appears in the list of things they perceived.") < system.index("The dead do not kill cleanly.")
