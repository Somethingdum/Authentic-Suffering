"""Over there (D-279). turn/intake.py INTAKE-05 (the INTAKE prompt: what the PC perceives, the going-there rule).

Owen in the stockroom, his axe in his hand, one of the dead two metres past the open back door in the alley. "I put
my axe through its head." No blow is offered across a doorway (D-278), and the intake read "A walker stands in the
rear alley." and "P2: a walker" — listed as here, with nothing to say they were the same, and its going-there rule
spoke only of people last seen elsewhere: the answer was "not here" for a thing he was looking at. Now the line says
whose it is, and the rule covers someone seen in another place: the first step is going there.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import CallClass
from as_engine.contracts.events import Event, EventType
from as_engine.physical import space
from as_engine.world import infected

from slice_kit import pick, play

pytestmark = pytest.mark.phase(7)


def test_the_walker_past_the_door(scenario, fake):
    w = scenario("metal_fence")
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        for p in ("storeroom", "alley"):
            space.change_place(tx, w.id(p), {"light_level": 4}, "test", t, None, 0)
        tx.commit_event(space.move_event(tx, w.id("pc"), w.id("storeroom"), None, 5.5, 2.0, t, None, 0))
        why = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=0, payload={"what": "test"}))
        dead = infected.spawn(tx, w.rng, w.id("alley"), "ZOMBIE_ARCHETYPE_SHAMBLER01", t, 0, why.event_id, x_m=6.0, y_m=2.5)
    seen = {}

    def answer(r):
        seen["system"], seen["user"], seen["handles"] = r.messages[0].content, r.messages[-1].content, r.context.packet.handles
        return {"choice": pick(w, r, "move_through_portal", target="back_door"), "none_reason": None, "manner": "",
                "remainder": "put my axe through its head", "clarify": None}
    fake.script(CallClass.INTAKE, answer)
    assert play(w.session(), "do", "I put my axe through its head.").ok
    (h,) = [k for k, v in seen["handles"].items() if v == dead and k.startswith("P")]
    lines = seen["user"].split("What they can perceive:\n", 1)[1].split("\nPeople they know of", 1)[0].splitlines()
    assert any("rear alley" in ln and ln.endswith(f" ({h})") for ln in lines), lines
    assert "seen in another place" in seen["system"] and "the first step is going there" in seen["system"]
