"""The room's lines (D-232). action/resolve.py SPEECH 'ambient'; turn/select.py talk_last_turn; mind/memory.py
worth_writing (MEM-20).

The people code moves say their few words on the fast lane (D-128, AMB-02) so a room is not silent. But one of them
saying "Cold again tonight." to nobody set everyone who heard it thinking the next turn (talk_last_turn) and writing
it down as a memory: a room of twelve rethought every other turn and remembered every turn it talked. A line of the
room still reaches everyone; said to someone, it is theirs to answer; it is not a conversation for the whole room.
"""

from __future__ import annotations

import helpers
import pytest

from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.contracts.events import Event, EventType
from as_engine.mind import memory, perception
from as_engine.turn import select

pytestmark = pytest.mark.phase(7)

T = 3


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def mara_says(w, *, ambient, to=("everyone",)):
    """Mara says a line at turn T - 1 and June hears it clearly."""
    t = now(w)
    pl = {"words": "Cold again tonight.", "volume": "normal", "to": [w.id(x) if x != "everyone" else x for x in to],
          "source_db": 60, "armed": False}
    if ambient:
        pl["ambient"] = True
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("mara"), at=t,
                                   turn_index=T - 1, payload=pl))
        perception.grant(tx, w.id("june"), event_id=ev.event_id, channel="speech", fidelity="exact",
                         text='Mara says, "Cold again tonight."', source_id=w.id("mara"), at=t + 300, turn_index=T - 1,
                         detail={"words": "Cold again tonight.", "volume": "normal", "addressed_to_me": "june" in to})
        return ev


def talk(w, who):
    with w.store.transaction() as tx:
        return select.salience_flags(tx, w.id(who), [w.id(who)], w.id("pc"), T, now(w))["talk_last_turn"]


def worth(w, who):
    with w.store.transaction() as tx:
        a = memory.build_aftermath(tx, w.id(who), T - 1, now(w) + 1000)
        return memory.worth_writing(tx, w.id(who), a, T - 1)


def test_a_remark_to_nobody(scenario):
    w = scenario("metal_fence")
    mara_says(w, ambient=True)
    assert not talk(w, "june") and not talk(w, "mara"), "nobody is set thinking by it"
    assert not worth(w, "june") and not worth(w, "mara"), "nor writes it down for itself"


def test_said_to_her(scenario):
    w = scenario("metal_fence")
    mara_says(w, ambient=True, to=("june",))
    assert talk(w, "june") and worth(w, "june")


def test_talk_is_still_talk(scenario):
    w = scenario("metal_fence")
    mara_says(w, ambient=False)
    assert talk(w, "june") and talk(w, "mara") and worth(w, "june")


def test_the_resolver_marks_the_rooms_lines(scenario):
    w = scenario("metal_fence")
    t = now(w)
    lines = {}
    for source in ("ambient", "model"):
        i = helpers.make_intent(w, "june", "wait_here", speech=("Cold again tonight.", ["everyone"], "normal"), source=source)
        with w.store.transaction() as tx:
            evs = resolve_wave(tx, w.rng, barrier(tx, [i]), t, 0, horizon_ms=t + 30_000)
        lines[source] = next(e.payload for e in evs if e.type == "SPEECH")
        t += 60_000
    assert lines["ambient"].get("ambient") is True and "ambient" not in lines["model"]
