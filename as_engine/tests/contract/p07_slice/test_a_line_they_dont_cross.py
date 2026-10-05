"""A line they don't cross (D-147). Rules INTAKE-05/07 (turn/intake.py), IntakeOutput's none_reason 'wont'
(contracts/mind.py), IntakeContext.wont (contracts/calls.py).

The player's character keeps its own card's lines (L12): an option that crosses one is never on its menu. When the
player asked for one anyway, the intake could only call it 'impossible', and the player read "That can't be done
from where you are." about something Owen could do perfectly well and would not. Now the intake knows what the
character will never do and says so.
"""

from __future__ import annotations

import pytest
from slice_kit import play

from as_engine.contracts.common import CallClass
from as_engine.turn.intake import NONE_MESSAGES

pytestmark = pytest.mark.phase(7)


def test_owen_will_not(scenario, fake):
    w = scenario("metal_fence")
    s = w.session()
    seen = {}

    def answer(r):
        seen["wont"], seen["prompt"] = r.context.wont, r.messages[-1].content
        return {"choice": "NONE", "none_reason": "wont", "manner": "", "remainder": None, "clarify": None}
    fake.script(CallClass.INTAKE, answer, times=2)
    out = play(s, "do", "I drag the kid out back and hurt him.")
    assert not out.ok and out.rejected_code == "wont" and out.rejected_message == NONE_MESSAGES["wont"]
    assert len(fake.calls(CallClass.INTAKE)) == 1, "a line is on no list: no second look"
    row = w.store.query_one("SELECT baseline_json FROM dossiers d JOIN actors a USING (dossier_id) WHERE a.actor_id = ?", (s.pc_id,))
    import json
    wont = json.loads(row[0])["motive"]["moral_line"]["wont"]
    assert seen["wont"] == wont and "Hurt a kid" in wont
    assert "will never do:" in seen["prompt"] and "- Hurt a kid" in seen["prompt"]
