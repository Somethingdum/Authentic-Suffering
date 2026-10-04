"""The player's words reach everything the PC could do (D-121). Rule INTAKE-07 (turn/intake.py), with
AFF-07's short first menu (mind/affordance.py) and CONSULT's appended options (mind/packet.py).

The PC's menu is a short first list ranked for a mind deciding in the moment — at the Night at
Delgado's, with a crash out back, it is moves, cover, the door and the guns. "I lie down and sleep"
found nothing there, and the player was told it wasn't clear what they wanted. Now a 'NONE' gets one
second look over everything else the PC could do, the first handles keeping their meaning.
"""

from __future__ import annotations

import pytest
from slice_kit import pick, play

from as_engine.contracts.common import CallClass
from as_engine.turn.intake import NONE_MESSAGES

pytestmark = pytest.mark.phase(7)


def options(w, r):
    p = r.context.packet
    return [(a.handle, p.handles[a.handle].split(":")[0]) for a in p.affordances]


def test_sleep_is_found_on_the_second_look(scenario, fake):
    w = scenario("metal_fence")
    s = w.session()
    looks = []

    def answer(r):
        looks.append(options(w, r))
        if not any(d == "sleep" for _h, d in looks[-1]):
            return {"choice": "NONE", "none_reason": "impossible", "manner": "", "remainder": None, "clarify": None}
        return {"choice": pick(w, r, "sleep"), "none_reason": None, "manner": "", "remainder": None, "clarify": None}
    fake.script(CallClass.INTAKE, answer, times=2)
    out = play(s, "do", "I lie down and sleep.")
    assert out.ok, out.rejected_message
    first, second = looks
    assert not any(d == "sleep" for _h, d in first), "the first menu had no room for it"
    assert second[:len(first)] == first, "the first handles keep their meaning"
    assert len(second) > len(first) and any(d == "sleep" for _h, d in second[len(first):])
    assert w.store.query_one("SELECT posture FROM bodies WHERE body_id = ?", (s.pc_id,))[0] == "lying"


def test_still_nothing_is_the_answer(scenario, fake):
    w = scenario("metal_fence")
    s = w.session()
    fake.script(CallClass.INTAKE, {"choice": "NONE", "none_reason": "impossible", "manner": "", "remainder": None,
                                   "clarify": "Climb the fence?"}, times=2)
    out = play(s, "do", "I fly over the fence.")
    assert not out.ok and out.rejected_code == "impossible" and out.rejected_message == NONE_MESSAGES["impossible"]
    assert len(fake.calls(CallClass.INTAKE)) == 2


def test_no_second_look_for_what_is_not_an_action(scenario, fake):
    w = scenario("metal_fence")
    s = w.session()
    fake.script(CallClass.INTAKE, {"choice": "NONE", "none_reason": "not_an_action", "manner": "", "remainder": None,
                                   "clarify": None})
    out = play(s, "do", "What year is it?")
    assert out.rejected_code == "not_an_action" and len(fake.calls(CallClass.INTAKE)) == 1
