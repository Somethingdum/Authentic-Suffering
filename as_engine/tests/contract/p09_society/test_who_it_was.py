"""Who it was (D-179). Rule INFO-08 (world/rumours.py CLAIM_WHOM, claim_sentence, seed whom_id); action/cascade.py
create_rumour p.whom and the path trigger.missed_target; core CAS-022/025/037/045/049/050/052/053/063/068.

June watched Owen fire at Mara, her friend, from across the room. What she came away believing was "Owen tried to kill
someone who was not fighting." — as if she had heard it third-hand. The one who saw it knows who it was done to; the
one who is told it later hears "someone".
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import space
from as_engine.world import rumours

pytestmark = pytest.mark.phase(9)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def test_the_sentence():
    assert rumours.claim_sentence("tried_to_kill_someone", "Owen", "Mara") == "Owen tried to kill Mara, who was not fighting."
    assert rumours.claim_sentence("tried_to_kill_someone", "Owen") == "Owen tried to kill someone who was not fighting."
    assert rumours.claim_sentence("killed_someone", "a tall man", "you") == "A tall man killed you, who was not fighting back."
    assert rumours.claim_sentence("dead", "Eli", "Mara") == "Eli is dead.", "a claim with no one it was done to"
    assert set(rumours.CLAIM_WHOM) <= set(rumours.CLAIM_TEXT)


def test_june_saw_it_was_mara(scenario):
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("sales_floor"), None, 7.0, 4.0, t, None, 0))
    at = t + 1000
    with w.store.transaction() as tx:
        st = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0, actor_id=w.id("pc"),
                                   payload={"actor_id": w.id("pc"), "def_id": "shoot_center_mass", "verb": "attack",
                                            "target_id": w.id("mara"), "visible": True, "seen": "goes for {target}"}))
        done = tx.commit_event(Event(type=EventType.ACTION_COMPLETE, writer="action.resolve", at=at + 300, turn_index=0,
                                     actor_id=w.id("pc"), cause_event_id=st.event_id,
                                     payload={"actor_id": w.id("pc"), "def_id": "shoot_center_mass", "band": "fail",
                                              "result": "miss", "visible": False}))
        for x in ("mara", "june"):
            perception.compile_aftermath(tx, w.id(x), [st, done], at + 500, 0)
        assert cascade.select(tx, "attack_onlookers_of(trigger.event_id)", done) == [w.id("june")]
        cascade.sweep(tx, [st, done], [r for r in w.canon.all("cascade") if r.id == "CAS-068"], at + 1000, 0)
    (text,) = [r[0] for r in w.store.query("SELECT p.text FROM rumours r JOIN percept_log p ON p.event_id = 'rumour:' || r.rumour_id "
                                           "WHERE r.origin_holder = ?", (w.id("june"),))]
    assert text == "Owen tried to kill Mara, who was not fighting."
    (rid,) = [r[0] for r in w.store.query("SELECT rumour_id FROM rumours WHERE origin_holder = ?", (w.id("june"),))]
    with w.store.transaction() as tx:
        rumours.spread_one(tx, rid, w.id("june"), w.id("alice"), at + 60_000, 0, None)
    told = w.store.query_one("SELECT text FROM percept_log WHERE holder_id = ? ORDER BY rowid DESC LIMIT 1", (w.id("alice"),))[0]
    assert told.endswith("tried to kill someone who was not fighting."), "talk passed on says someone"
