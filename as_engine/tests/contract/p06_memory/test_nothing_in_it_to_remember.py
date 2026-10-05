"""Nothing in it to remember (D-254). mind/memory.py worth_writing (MEM-20).

Talking with one person in a house, the player set ten people writing memories every turn: on the first turn of the
run, eight people in the next building were each sent to write down that they could see the others they had been
standing with all along ("Keisha Garza stands at the front."); on the next, that the others had stopped to watch
("Keisha Garza stops and watches."). Someone else holding still is not something to remember, and neither is the place
and the people a person was already among when the run began.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.events import Event, EventType
from as_engine.mind import memory, perception

pytestmark = pytest.mark.phase(6)

T = 3


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def saw(w, def_id, text, turn=T, *, before=True):
    """June sees Mara start something, at ``turn``, and nothing else happens to her; is it worth a memory?"""
    t = now(w)
    with w.store.transaction() as tx:
        if before:
            perception.grant(tx, w.id("june"), event_id="scene:" + w.id("mara"), channel="visual", fidelity="exact",
                             text="Mara stands by the counter.", source_id=w.id("mara"), at=t - 5000, turn_index=turn - 1,
                             detail={"level": "clear"})
        ev = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", actor_id=w.id("mara"), at=t,
                                   turn_index=turn, payload={"actor_id": w.id("mara"), "def_id": def_id, "verb": "x"}))
        perception.grant(tx, w.id("june"), event_id=ev.event_id, channel="visual", fidelity="exact", text=text,
                         source_id=w.id("mara"), at=t + 100, turn_index=turn, detail={"level": "clear"})
        a = memory.build_aftermath(tx, w.id("june"), turn, t + 1000)
        assert [p.text for p in a.percepts] == [text]
        return memory.worth_writing(tx, w.id("june"), a, turn)


@pytest.mark.parametrize("def_id, text", [("observe_area", "Mara stops and watches."), ("wait_here", "Mara stops and waits.")])
def test_someone_else_holding_still(scenario, def_id, text):
    assert not saw(scenario("metal_fence"), def_id, text)


@pytest.mark.parametrize("def_id, text", [("go_look", "Mara heads for the back door."), ("take_cover", "Mara ducks behind the counter.")])
def test_someone_doing_something(scenario, def_id, text):
    assert saw(scenario("metal_fence"), def_id, text)


def test_where_she_already_was(scenario):
    """The run's first turn: no one perceived anything before it; what June sees standing around her is where she
    already was. Mara starting off somewhere is still news."""
    w = scenario("metal_fence")
    t = now(w)
    assert not w.store.query_one("SELECT 1 FROM percept_log WHERE turn_index = 0")
    with w.store.transaction() as tx:
        perception.grant(tx, w.id("june"), event_id="scene:" + w.id("mara"), channel="visual", fidelity="exact",
                         text="Mara stands by the counter.", source_id=w.id("mara"), at=t, turn_index=1, detail={"level": "clear"})
        a = memory.build_aftermath(tx, w.id("june"), 1, t + 1000)
        assert [p.text for p in a.percepts] == ["Mara stands by the counter."]
        assert not memory.worth_writing(tx, w.id("june"), a, 1)
        ev = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", actor_id=w.id("mara"), at=t + 200,
                                   turn_index=1, payload={"actor_id": w.id("mara"), "def_id": "go_look", "verb": "move"}))
        perception.grant(tx, w.id("june"), event_id=ev.event_id, channel="visual", fidelity="exact",
                         text="Mara heads for the back door.", source_id=w.id("mara"), at=t + 300, turn_index=1,
                         detail={"level": "clear"})
        assert memory.worth_writing(tx, w.id("june"), memory.build_aftermath(tx, w.id("june"), 1, t + 1000), 1)
