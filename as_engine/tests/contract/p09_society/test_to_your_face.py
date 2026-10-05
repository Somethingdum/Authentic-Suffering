"""To your face (D-219). action/cascade.py insulted_to_their_face; core CAS-107, CAS-108.

The owner: "If I treat them like shit … I do expect reactions, and proper ones." Called a useless idiot or given the
finger with nobody else there, June was angry for an hour (TEMPER-03) and then it was as if it had never been said;
only an audience (CAS-042, CAS-079) made it last. Now being treated like dirt to your face is held against the one
who did it — once an hour, however often — and with an audience it stays the humiliation it was.
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import space

pytestmark = pytest.mark.phase(9)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def resentment(w, a, b):
    r = w.store.query_one("SELECT resentment FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def alone(w):
    """Owen and June on the lit sales floor; Mara in the office."""
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        for who, x in (("pc", 5.0), ("june", 6.5)):
            tx.commit_event(space.move_event(tx, w.id(who), w.id("sales_floor"), None, x, 4.0, t, None, 0))
        tx.commit_event(space.move_event(tx, w.id("mara"), w.id("office"), None, 2.0, 2.0, t, None, 0))
    return t + 100


def say(w, who, to, words, at, hearers):
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id(who), at=at, turn_index=0,
                                   payload={"words": words, "volume": "normal", "to": [w.id(to)], "source_db": 60}))
        for x in hearers:
            perception.compile_aftermath(tx, w.id(x), [ev], at + 200, 0)
    return ev


def gesture(w, who, to, what, at, seers):
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.GESTURE, writer="action.propagate", at=at, turn_index=0, actor_id=w.id(who),
                                   payload={"actor_id": w.id(who), "gesture": what, "target_id": w.id(to)}))
        for x in seers:
            perception.compile_aftermath(tx, w.id(x), [ev], at + 200, 0)
    return ev


def face(w, ev):
    with w.store.transaction() as tx:
        return cascade.select(tx, "insulted_to_their_face(trigger.event_id)", ev)


def sweep(w, ev, at, rule):
    with w.store.transaction() as tx:
        return cascade.sweep(tx, [ev], [r for r in w.canon.all("cascade") if r.id == rule], at, 0)


def test_called_a_useless_idiot_with_nobody_there(scenario):
    w = scenario("metal_fence")
    t = alone(w)
    before = resentment(w, "june", "pc")
    ev = say(w, "pc", "june", "You useless idiot.", t, ("june",))
    assert face(w, ev) == [w.id("june")]
    sweep(w, ev, t + 500, "CAS-107")
    assert resentment(w, "june", "pc") == min(3, before + 1)
    again = say(w, "pc", "june", "Shut up.", t + 30_000, ("june",))
    assert face(w, again) == [], "once an hour, however often"
    later = say(w, "pc", "june", "Coward.", t + 3_700_000, ("june",))
    assert face(w, later) == [w.id("june")]


def test_ordinary_words_are_nothing(scenario):
    w = scenario("metal_fence")
    t = alone(w)
    assert face(w, say(w, "pc", "june", "Hand me the tape.", t, ("june",))) == []


def test_with_an_audience_it_is_the_humiliation(scenario):
    """Mara on the floor with them hears it: that is CAS-042's."""
    w = scenario("metal_fence")
    t = alone(w)
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("mara"), w.id("sales_floor"), None, 8.0, 4.0, t, None, 0))
    ev = say(w, "pc", "june", "You useless idiot.", t + 100, ("june", "mara"))
    assert face(w, ev) == []
    with w.store.transaction() as tx:
        assert cascade.select(tx, "humiliated_by(trigger.event_id)", ev) == [w.id("june")]


@pytest.mark.parametrize("what, counts", [("the_finger", True), ("spit_at", True), ("point_at", False)])
def test_given_the_finger_alone(scenario, what, counts):
    w = scenario("metal_fence")
    t = alone(w)
    before = resentment(w, "june", "pc")
    ev = gesture(w, "pc", "june", what, t, ("june",))
    assert face(w, ev) == ([w.id("june")] if counts else [])
    sweep(w, ev, t + 500, "CAS-108")
    assert resentment(w, "june", "pc") == (min(3, before + 1) if counts else before)


def test_never_the_player_character(scenario):
    w = scenario("metal_fence")
    t = alone(w)
    assert face(w, say(w, "june", "pc", "You useless idiot.", t, ("pc",))) == []
