"""What stands still is not news (D-228). Rules SEL-03 pressing_need, dependent_present, open_loop_with_pc
(turn/select.py salience_flags; NEED_NEWS_TURNS).

D-190 made a person with nothing new to go on run COLD — but three flags were standing conditions, true every turn
they held, so the same people were sent to a model every quiet turn: a hungry woman asked again every half minute
about the same hunger, a father whose son sleeps beside him, anyone with an open loop about the player wherever the
player was. Now a need is news until they have decided knowing it (and again when it gets worse), a child of their
own beside them counts when there is danger, and unfinished business with the player counts when he is there.
'restless' still has every one of them take stock every few turns.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.mind.affordance import NEED_PRESSING
from as_engine.mind.mind import open_loop
from as_engine.physical import space
from as_engine.turn import select

pytestmark = pytest.mark.phase(7)

T = 5


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def flags(w, who, turn=T):
    with w.store.transaction() as tx:
        return select.salience_flags(tx, w.id(who), [w.id(who)], w.id("pc"), turn, now(w))


def decided(w, who, turn):
    """An answered model decision of ``who`` in ``turn`` (what the pipeline records for one)."""
    seq = (w.store.query_one("SELECT MAX(seq) FROM lm_calls WHERE turn_index = ?", (turn,))[0] or 0) + 1
    w.store.conn.execute("INSERT INTO lm_calls (turn_index, seq, call_class, lane, actor_id, status, latency_ms, request_hash, "
                         "response_text) VALUES (?, ?, 'actor_cognition', 'B', ?, 'ok', 1, 'h', '{}')", (turn, seq, w.id(who)))


def worse(w, who, turn, stage):
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.NEED_STAGE, writer="physical.bodies", at=now(w), turn_index=turn,
                              target_ids=[w.id(who)], payload={"body_id": w.id(who), "need": "fatigue", "stage": stage}))


def test_a_need_is_news_until_decided_on(scenario):
    w = scenario("metal_fence")
    w.store.conn.execute("UPDATE needs SET fatigue_stage = ? WHERE body_id = ?", (NEED_PRESSING, w.id("june")))
    assert flags(w, "june")["pressing_need"], "never asked about it"
    decided(w, "june", T - 2)
    assert not flags(w, "june")["pressing_need"], "she decided knowing it; the same tiredness is not news"
    worse(w, "june", T - 1, NEED_PRESSING + 1)
    assert flags(w, "june")["pressing_need"], "it got worse since"
    decided(w, "june", T - 1)
    assert flags(w, "june")["pressing_need"], "worse in the turn she last decided: it may have come after"
    decided(w, "june", T)
    assert not flags(w, "june")["pressing_need"]
    assert flags(w, "june", T + select.NEED_NEWS_TURNS + 1)["pressing_need"], "too long ago to count"


def test_her_son_beside_her_is_at_stake_when_there_is_danger(scenario):
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("mara"), w.id("office"), None, 2.0, 2.0, t, None, 0))
    assert not flags(w, "mara", 0)["dependent_present"], "Eli asleep beside her on a quiet night"
    with w.store.transaction() as tx:
        perception.grant(tx, w.id("mara"), event_id="scene:test_grabbed", channel="tactile", fidelity="exact",
                         text="Something grabs your arm.", source_id=None, at=t, turn_index=0)
    f = flags(w, "mara", 0)
    assert f["in_conflict"] and f["dependent_present"]


def test_business_with_the_player_when_he_is_there(scenario):
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        open_loop(tx, w.id("nita"), "question", "What does the man with the axe want?", [w.id("pc")], 2, None, t, 0)
        tx.commit_event(space.move_event(tx, w.id("nita"), w.id("back_lot"), None, 6.0, 2.0, t, None, 0))
    assert not flags(w, "nita", 0)["open_loop_with_pc"], "he is inside; she is out in the lot"
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("pc"), w.id("back_lot"), None, 5.0, 3.0, t, None, 0))
    assert flags(w, "nita", 0)["open_loop_with_pc"]
