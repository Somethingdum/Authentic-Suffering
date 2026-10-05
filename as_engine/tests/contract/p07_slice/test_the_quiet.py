"""The quiet (D-150). Rules AMB-01 (mind/packet.py ambient_packet idle) and AMB-04 (turn/cognition.py decide).

D-128 let the people past the model budget say a line about what had just reached them — and a quiet moment
reached nobody, so a room of people sat in silence for as long as nothing happened. Now, when nobody has said
anything in the player's place this turn, one of them may say something idle — at most one line a moment, and
who says it goes round. Their act stays code's; only the words are asked for.
"""

from __future__ import annotations

import asyncio

import pytest

from as_engine.contracts.common import LOD, CallClass
from as_engine.contracts.events import Event, EventType
from as_engine.lanes.scheduler import CognitionPlan
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import ambient_packet
from as_engine.physical import space
from as_engine.turn.cognition import decide

pytestmark = pytest.mark.phase(7)

COLD = ("mara", "alice")


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def calm_floor(w, turn=0):
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, turn)
        for x in COLD:
            perception.compile_scene(tx, w.id(x), t + 100, turn)
    return t + 500


def moment(w, at, turn=0, *, reaction=False):
    s = w.session()
    ids = [w.id(a) for a in COLD]
    with s.store.transaction() as tx:
        affs = {a: enumerate_affordances(tx, a, w.canon.all("affordance"), at, turn) for a in ids}
    plan = CognitionPlan(lod={a: LOD.COLD for a in ids}, order=ids)

    async def go():
        with s.store.transaction() as tx:
            return await decide(tx, s, plan, affs, turn, at, reaction=reaction)
    return asyncio.run(go())


def lines(w, out):
    return {w.local(a): (i.speech.text if i is not None and i.speech is not None else None) for a, i in out.items()}


def says(line):
    return lambda r: {"line": line, "to": None, "volume": "low"}


def test_a_quiet_moment_has_one_line(scenario, fake):
    w = scenario("metal_fence")
    at = calm_floor(w)
    with w.store.transaction() as tx:
        assert ambient_packet(tx, w.id("mara"), 0, at) is None, "nothing reached her"
        pk = ambient_packet(tx, w.id("mara"), 0, at, idle=True)
    assert pk is not None and pk.reached == [] and pk.people
    fake.script(CallClass.AMBIENT_LINE, says("Generator's going to need fuel by Thursday."), actor_id=w.id("mara"))
    assert lines(w, moment(w, at)) == {"mara": "Generator's going to need fuel by Thursday.", "alice": None}
    req = fake.calls(CallClass.AMBIENT_LINE)[0]
    assert "a quiet moment" in req.messages[-1].content


def test_who_says_it_goes_round(scenario, fake):
    w = scenario("metal_fence")
    at = calm_floor(w, turn=1)
    fake.script(CallClass.AMBIENT_LINE, says("Anybody else hear that hum?"), actor_id=w.id("alice"))
    assert lines(w, moment(w, at, turn=1)) == {"mara": None, "alice": "Anybody else hear that hum?"}


def test_not_when_someone_has_spoken_or_in_a_reaction(scenario, fake):
    w = scenario("metal_fence")
    at = calm_floor(w)
    assert lines(w, moment(w, at, reaction=True)) == {"mara": None, "alice": None}
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("sales_floor"), None, 4.0, 4.0, at, None, 0))
        tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("june"), at=at + 50, turn_index=0,
                              payload={"words": "Forty-one.", "volume": "low", "to": ["everyone"], "source_db": 40,
                                       "armed": False}))
    assert lines(w, moment(w, at + 100)) == {"mara": None, "alice": None}
    assert fake.calls(CallClass.AMBIENT_LINE) == []


def test_nobody_talks_to_an_empty_street(scenario):
    """Mara steps out alone into the street: whoever she saw this turn, nobody is there to hear her."""
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("mara"), w.id("street"), None, 5.0, 5.0, t, None, 0))
        perception.compile_scene(tx, w.id("mara"), t + 100, 0)
        assert not tx.query("SELECT 1 FROM positions WHERE place_id = ? AND body_id != ?", (w.id("street"), w.id("mara")))
        assert ambient_packet(tx, w.id("mara"), 0, t + 500, idle=True) is None
