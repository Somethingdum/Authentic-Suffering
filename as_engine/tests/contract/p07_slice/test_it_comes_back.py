"""It comes back (D-145). Rule NARR-11 (narration/narrator.py pc_state_lines).

The player's character could watch someone killed and be told nothing of it again: the story never let the worst
things they had seen come back. Now, under strain, the worst thing they saw lately comes back unasked — oftener
the worse the strain. A memory, not a feeling: what Owen makes of it is the player's.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.kernel import clock
from as_engine.mind import perception
from as_engine.narration.narrator import INTRUSION_LINE, build_narrator_packet
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec

pytestmark = pytest.mark.phase(7)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def owen_sees_june_killed(w):
    """Turn 1: Alice cuts June's throat in front of Owen."""
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 1)
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("sales_floor"), None, 4.0, 4.0, t, None, 1))
        st = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=t + 500, turn_index=1, actor_id=w.id("alice"),
                                   payload={"actor_id": w.id("alice"), "def_id": "strike_melee", "verb": "attack",
                                            "target_id": w.id("june")}))
        hurt = bodies.apply_harm(tx, w.id("june"), WoundSpec(Anatomy.NECK, WoundType.CUT, WoundSeverity.CATASTROPHIC), t + 800,
                                 st.event_id, 1, w.rng)
        if not any(e.type == EventType.DEATH for e in hurt):
            harm = next(e for e in hurt if e.type == EventType.HARM)
            hurt.append(bodies.kill(tx, w.id("june"), "blood_loss", t + 900, 1, w.rng, cause_event_id=harm.event_id))
        perception.compile_aftermath(tx, w.id("pc"), [st] + hurt, t + 1500, 1)
        death = next(e for e in hurt if e.type == EventType.DEATH)
        seen = tx.query_one("SELECT text FROM percept_log WHERE holder_id = ? AND event_id = ?", (w.id("pc"), death.event_id))[0]
    return seen, t + 60_000


def lines(w, turn, at):
    with w.store.transaction() as tx:
        return build_narrator_packet(tx, w.id("pc"), turn, at, w.session().settings).pc_state_lines


def stress(w, n):
    w.store.conn.execute("UPDATE actors SET stress = ? WHERE actor_id = ?", (n, w.id("pc")))


def test_under_strain_it_comes_back(scenario):
    w = scenario("metal_fence")
    seen, at = owen_sees_june_killed(w)
    line = INTRUSION_LINE.format(text=seen)
    stress(w, 9)                                   # every 2nd turn
    assert line in lines(w, 2, at) and line not in lines(w, 3, at) and line in lines(w, 4, at)
    stress(w, 10)                                  # every turn
    assert line in lines(w, 3, at)
    with w.store.transaction() as tx:
        assert "June" in build_narrator_packet(tx, w.id("pc"), 3, at, w.session().settings).allowed_names, "the prose may name her"


def test_steady_nerves_and_old_memories(scenario):
    w = scenario("metal_fence")
    seen, at = owen_sees_june_killed(w)
    line = INTRUSION_LINE.format(text=seen)
    stress(w, 6)
    assert line not in lines(w, 5, at), "not under strain"
    stress(w, 10)
    assert line not in lines(w, 1, at), "not in the turn it happened: it is still happening"
    with w.store.transaction() as tx:
        clock.advance_event(tx, at + 4 * 24 * 3600 * 1000, "test")
    assert line not in lines(w, 2, now(w)), "days later it has let go"
