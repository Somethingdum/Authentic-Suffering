"""Watching is no news (D-293). mind/packet.py AMB-01 ambient_packet (reached, people); turn/cognition.py AMB-02.

In a room where everyone settles in, the line each COLD person was given to remark on read "Ernesto Medina stops and
watches. Darnell Walsh stops and watches. Andre Vargas stops and watches. …" — a call to say something about
nothing, naming people the list of who they could see did not hold. A voice too muffled to make out read
'Someone said: ""'. A man lying down to sleep was told "What you are doing: Lie down and sleep". Now someone else's
quiet hold reaches nobody as news, who reached them comes first among the people they see, words not caught are
said to be so, and what they are doing is told as their choice.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import CallClass
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.mind.packet import ambient_packet
from as_engine.physical import space
from as_engine.prompts.render import render

pytestmark = pytest.mark.phase(7)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def lit(w, at):
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", at, None, 0)
        perception.compile_scene(tx, w.id("mara"), at, 0)


def watches(w, who, at):
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0, actor_id=w.id(who),
                                   payload={"actor_id": w.id(who), "def_id": "observe_area", "verb": "observe",
                                            "label": "Stay put and watch", "visible": True, "seen": "stops and watches"}))
        perception.compile_aftermath(tx, w.id("mara"), [ev], at + 100, 0)


def says(w, who, words, at, volume="normal"):
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id(who), at=at, turn_index=0,
                                   payload={"words": words, "volume": volume, "to": ["everyone"], "source_db": 60, "armed": False}))
        perception.compile_aftermath(tx, w.id("mara"), [ev], at + 100, 0)


def packet(w, at, **kw):
    with w.store.transaction() as tx:
        return ambient_packet(tx, w.id("mara"), 0, at, **kw)


def test_someone_watching_is_nothing_to_remark_on(scenario):
    w = scenario("metal_fence")
    t = now(w)
    lit(w, t)
    for i, who in enumerate(("june", "alice", "nita")):
        watches(w, who, t + 100 * (i + 1))
    assert packet(w, t + 1000) is None, "nothing reached her"


def test_who_spoke_comes_first(scenario):
    w = scenario("metal_fence")
    t = now(w)
    lit(w, t)
    watches(w, "june", t + 100)
    says(w, "alice", "Anyone got a light?", t + 200)
    pk = packet(w, t + 1000, doing="Stay put and watch everything you can see and hear")
    assert [x for x in pk.reached if "watches" in x] == [] and len(pk.reached) == 1, pk.reached
    assert pk.handles[pk.people[0].handle] == w.id("alice"), "whoever a line speaks of comes first"
    text = render(CallClass.AMBIENT_LINE, ctx=pk)[1].content
    assert "\nYou chose to stay put and watch everything you can see and hear.\n" in text, text


def test_a_voice_she_could_not_make_out(scenario):
    w = scenario("metal_fence")
    t = now(w)
    lit(w, t)
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("eli"), at=t + 200,
                                   turn_index=0, payload={"words": "where's mom", "volume": "whisper", "to": ["everyone"],
                                                          "source_db": 20, "armed": False}))
        perception.grant(tx, w.id("mara"), event_id=ev.event_id, channel="speech", fidelity="tone_only",
                         text="Someone says something too low to make out.", source_id=None, at=t + 200, turn_index=0,
                         detail={"words": "", "volume": "whisper", "addressed_to_me": False})
    pk = packet(w, t + 1000)
    assert pk.reached == ["Someone said something you could not make out"], pk.reached
