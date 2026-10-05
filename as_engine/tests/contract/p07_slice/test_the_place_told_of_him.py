"""The place told of him (D-178). narration/narrator.py (the MOVE line, place_details and people_present told of the
PC); mind/perception.py retell (contractions, TEXT-01).

D-170 told what the player's character perceived of him, not as "you" — but the place he walked into still reached
the Writer as "You're alone." and "The far side of the car would hide you.", and retell made "He'res alone." of the
first. And leaving the garage by its side door was told "Owen moves to the side door.": the anchor he arrived at, not
that he had gone out into the yard.
"""

from __future__ import annotations

import pytest
from slice_kit import pick, play

from as_engine.contracts.common import CallClass
from as_engine.mind.perception import retell

pytestmark = pytest.mark.phase(7)


def test_contractions():
    assert [retell("You're alone.", "third", x) for x in ("male", "female", None)] == \
        ["He's alone.", "She's alone.", "They're alone."]
    assert retell("You're alone.", "first") == "I'm alone."
    assert retell("You've been bitten.", "third", "male") == "He's been bitten."
    assert retell("You'll need both hands.", "third", "female") == "She'll need both hands."
    assert retell("You'd better run.", "first") == "I'd better run."


def test_out_the_side_door(scenario, fake):
    w = scenario("two_skills")
    s = w.session()
    w.store.conn.execute("DELETE FROM event_queue WHERE subject_id = ?", (w.id("shambler"),))   # the walker stays put
    def out(r):
        try:
            return {"choice": pick(w, r, "move_through_portal", dest="yard"), "none_reason": None, "manner": "",
                    "remainder": None, "clarify": None}
        except KeyError:                                                # not on the short first list (INTAKE-07)
            return {"choice": "NONE", "none_reason": "impossible", "manner": "", "remainder": None, "clarify": None}
    fake.script(CallClass.INTAKE, out, times=2)
    assert play(s, "do", "I go out the side door into the yard.").ok
    assert w.store.query_one("SELECT place_id FROM positions WHERE body_id = ?", (s.pc_id,))[0] == w.id("yard")
    k = fake.calls(CallClass.NARRATION)[-1].context
    assert "Owen goes into the yard." in [ln.text for ln in k.lines], [ln.text for ln in k.lines]
    assert k.establish_place and "He's alone." in k.place_details, k.place_details
    assert not any("you" in x.lower().split() or "you're" in x.lower() for x in k.place_details + k.people_present)
