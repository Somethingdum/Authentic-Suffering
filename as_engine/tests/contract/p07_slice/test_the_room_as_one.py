"""The room as one (D-265). narration/narrator.py build_narrator_packet lines.

Eleven people in a room; the player looks around, and the narration was handed nine lines that said the same thing
nine ways — "A heavyset woman stops and watches. A man stops and watches. Marcus Castillo stops and watches. …" — and
the Writer, retelling them, opened sentence after sentence the same way until the lint sent it back. Nine people
stopping to watch are two people and seven others.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.narration.narrator import build_narrator_packet

pytestmark = pytest.mark.phase(7)

T = 2


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def owen_sees(w, who, def_id="observe_area", text="{} stops and watches.", target=None):
    t = now(w)
    with w.store.transaction() as tx:
        for i, x in enumerate(who):
            ev = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", actor_id=w.id(x), at=t, turn_index=T,
                                       payload={"actor_id": w.id(x), "def_id": def_id, "verb": "observe",
                                                "target_id": target}))
            perception.grant(tx, w.id("pc"), event_id=ev.event_id, channel="visual", fidelity="exact",
                             text=text.format(x.capitalize()), source_id=w.id(x), at=t + 100, turn_index=T,
                             detail={"level": "clear"})
        return [ln.text for ln in build_narrator_packet(tx, w.id("pc"), T, t, w.session().settings).lines]


def test_two_and_the_others(scenario):
    w = scenario("metal_fence")
    got = owen_sees(w, ["mara", "alice", "june", "nita", "eli"])
    watch = [x for x in got if "stops and watches" in x or "do the same" in x]
    assert len(watch) == 3 and watch[2] == "Three others do the same.", got
    assert got.index(watch[2]) == got.index(watch[1]) + 1


def test_three_are_three(scenario):
    w = scenario("metal_fence")
    got = owen_sees(w, ["mara", "alice", "june"])
    assert len([x for x in got if "stops and watches" in x]) == 3 and not [x for x in got if "do the same" in x]


def test_what_is_not_holding_still_is_told(scenario):
    """Four people heading for the back door are four lines: only holding still is gathered."""
    w = scenario("metal_fence")
    got = owen_sees(w, ["mara", "alice", "june", "nita"], def_id="go_look", text="{} heads for the back door.")
    assert len([x for x in got if "heads for the back door" in x]) == 4 and not [x for x in got if "do the same" in x]
