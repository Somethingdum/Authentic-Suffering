"""His own words, quoted (D-274). narration/narrator.py (the echo block in the prompt); prompts/narration.user.j2.

The player typed "Who runs this place?" for Owen to say; the narration prompt told the Writer to quote everyone's
exact words — and, a few lines on, to "never repeat these word runs from the player: … who runs this place". A small
model obeyed the second and paraphrased him. The lint never counted quoted words (ECHO-01); now the prompt says so.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import CallClass
from as_engine.contracts.narration import NarratorLine, NarratorPacket
from as_engine.prompts.render import render

pytestmark = pytest.mark.phase(7)


def test_the_echo_block_spares_his_quoted_words():
    k = NarratorPacket(turn_index=2, world_time_text="08:00, day 621 since the Fall (morning)", place_text="The Salazar house",
                       pc_name="Owen", allowed_names=["Owen"], length="short",
                       lines=[NarratorLine(seconds=0.0, kind="speech", text='Owen says, "Who runs this place?"', speaker="Owen",
                                           words="Who runs this place?")],
                       player_input_echo_block=["who runs this place"])
    system, user = (m.content for m in render(CallClass.NARRATION, k=k, words=(160, 350), fix=None))
    assert "use their exact words from the list, in quotation marks" in system
    line = [x for x in user.splitlines() if x.startswith("Never repeat these word runs from the player")][0]
    assert "outside quotation marks" in line and "Owen says aloud is quoted as said" in line and line.endswith("who runs this place")
