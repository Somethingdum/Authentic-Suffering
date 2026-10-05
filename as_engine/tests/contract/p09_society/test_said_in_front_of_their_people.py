"""Said in front of their people (D-267). action/cascade.py groups_that_heard_threat; core CAS-118.

Hurting one of a group's own in front of any of them costs a point of the group's standing (CAS-110, D-220);
threatening one of them, to their face and in the others' hearing, cost nothing with the group however often it was
done. Now it costs a point, once a day — an evening of threats is one wrong.
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import space

pytestmark = pytest.mark.phase(9)

RULES = ("CAS-118",)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def crew(w):
    return w.store.query_one("SELECT group_id FROM group_members WHERE actor_id=? AND status='member'", (w.id("mara"),))[0]


def standing(w, toward="pc"):
    r = w.store.query_one("SELECT standing FROM group_standing WHERE group_id=? AND actor_id=?", (crew(w), w.id(toward)))
    return r[0] if r else 0


def room(scenario, *, alone=False):
    """June out of the storeroom, by Owen on the sales floor; Mara and Alice of the crew hear it — unless ``alone``:
    then Owen is in the storeroom with June, every way into it shut."""
    w = scenario("metal_fence")
    pc = w.store.query_one("SELECT place_id, x_m, y_m FROM positions WHERE body_id=?", (w.id("june" if alone else "pc"),))
    who = "pc" if alone else "june"
    w.store.conn.execute("UPDATE positions SET place_id=?, anchor_id=NULL, x_m=?, y_m=? WHERE body_id=?",
                         (pc[0], (pc[1] or 0) + 1.0, pc[2] or 0, w.id(who)))
    if alone:
        w.store.conn.execute("UPDATE portals SET is_open=0 WHERE place_a=? OR place_b=?", (pc[0], pc[0]))
    w.store.conn.commit()
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", now(w), None, 0)
    return w


def say(w, who, to, words, at):
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id(who), at=at, turn_index=0,
                                   payload={"words": words, "volume": "normal", "to": [w.id(to)], "source_db": 60,
                                            "armed": False}))
        for x in ("june", "mara", "alice", "pc"):
            perception.compile_aftermath(tx, w.id(x), [ev], at + 500, 0)
    return ev


def chosen(w, ev):
    with w.store.transaction() as tx:
        return cascade.select(tx, "groups_that_heard_threat(trigger.event_id)", ev)


def sweep(w, ev, at):
    with w.store.transaction() as tx:
        return cascade.sweep(tx, [ev], [r for r in w.canon.all("cascade") if r.id in RULES], at, 0)


def test_one_of_theirs_threatened_in_their_hearing(scenario):
    w = room(scenario)
    t = now(w)
    before = standing(w)
    ev = say(w, "pc", "june", "June, I'll break your arm.", t)
    assert chosen(w, ev) == [crew(w)]
    assert [e.rule_cited for e in sweep(w, ev, t + 1000)] == ["CAS-118"]
    assert standing(w) == before - 1
    again = say(w, "pc", "june", "You heard me. I'll break it.", t + 600_000)
    assert chosen(w, again) == [], "an evening of threats is one wrong"
    tomorrow = say(w, "pc", "june", "I'll break your arm, I swear it.", t + 86_400_000 + 1000)
    assert chosen(w, tomorrow) == [crew(w)]


def test_with_nobody_of_theirs_there(scenario):
    """Owen threatens June in the storeroom with nobody else to hear: her story to tell (D-253), not the crew's wrong."""
    w = room(scenario, alone=True)
    ev = say(w, "pc", "june", "June, I'll break your arm.", now(w))
    assert chosen(w, ev) == []


def test_words_that_are_not_a_threat(scenario):
    w = room(scenario)
    ev = say(w, "pc", "june", "June, I'll never hurt you.", now(w))
    assert chosen(w, ev) == []
