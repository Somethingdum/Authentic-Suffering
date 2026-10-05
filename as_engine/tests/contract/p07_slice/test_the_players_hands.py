"""The player's hands (D-136). Rule INTAKE-08 (turn/intake.py), with INTENT-09 (action/intent.py), the
IntakeOutput's gesture (contracts/mind.py) and lanes/schemas.py intake_schema's gesture enum.

An Actor could nod, shrug, point, hush or hold up empty hands; the player could not — "I nod" found no
option and was refused. Now the words reach the PC's gestures as an Actor's answer does: the gesture goes
with the option the words choose (staying put, when it is the gesture alone), and everyone who sees the PC
sees it. One that cannot be made is dropped: the player's words are not a protocol.
"""

from __future__ import annotations

import pytest
from slice_kit import events, pick, play

from as_engine.contracts.common import CallClass
from as_engine.physical import objects
from as_engine.physical.objects import Holder

pytestmark = pytest.mark.phase(7)


def gesture_handle(r, gid):
    p = r.context.packet
    return next(g.handle for g in p.gestures if p.handles[g.handle].split(":")[0] == gid)


def test_a_nod_goes_with_staying_put(scenario, fake):
    w = scenario("metal_fence")
    s = w.session()
    seen = {}

    def answer(r):
        seen["schema"] = r.json_schema["properties"]["gesture"]
        seen["prompt"] = r.messages[-1].content
        seen["nod"] = gesture_handle(r, "nod")
        return {"choice": pick(w, r, "wait_here"), "none_reason": None, "manner": "", "gesture": seen["nod"],
                "remainder": None, "clarify": None}
    fake.script(CallClass.INTAKE, answer)
    out = play(s, "do", "I nod.")
    assert out.ok, out.rejected_message
    assert seen["nod"] in seen["schema"]["anyOf"][0]["enum"]
    assert "Gestures (only alongside an option):" in seen["prompt"] and f"- {seen['nod']}: nod" in seen["prompt"]
    g = [e for e in events(w, "GESTURE") if e["actor_id"] == s.pc_id]
    assert [e["payload"]["gesture"] for e in g] == ["nod"]


def test_hands_up_with_words(scenario, fake):
    """'I hold up my empty hands. "Don't shoot."' — the words are said and the hands are seen. (Owen's Glock goes
    in his pocket first: showing both empty hands needs both free.)"""
    w = scenario("metal_fence")
    s = w.session()
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        objects.transfer(tx, w.id("glock"), Holder("body", s.pc_id, "pocket"), None, t, s.pc_id, None, 0)
    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "wait_here"), "none_reason": None, "manner": "",
                                            "gesture": gesture_handle(r, "empty_hands"), "remainder": None, "clarify": None})
    out = play(s, "do", 'I hold up my empty hands. "Don\'t shoot."')
    assert out.ok, out.rejected_message
    assert [e["payload"]["gesture"] for e in events(w, "GESTURE") if e["actor_id"] == s.pc_id] == ["empty_hands"]
    assert [e["payload"]["def_id"] for e in events(w, "ACTION_START") if e["actor_id"] == s.pc_id] == ["wait_here"]
    assert [e["payload"]["words"] for e in events(w, "SPEECH") if e["actor_id"] == s.pc_id] == ["Don't shoot."]


def test_a_gesture_that_cannot_be_made_is_dropped(scenario, fake):
    w = scenario("metal_fence")
    s = w.session()
    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "wait_here"), "none_reason": None, "manner": "",
                                            "gesture": "G99", "remainder": None, "clarify": None})
    out = play(s, "do", "I wave my third hand.")
    assert out.ok, out.rejected_message
    assert [e["payload"]["def_id"] for e in events(w, "ACTION_START") if e["actor_id"] == s.pc_id] == ["wait_here"]
    assert not [e for e in events(w, "GESTURE") if e["actor_id"] == s.pc_id]
