"""A question with an axe in hand (D-269). mind/firewall.py armed_threat; mind/cues.py weapon_pointed; mind/affordance.py
threats; turn/select.py (weapon_pointed is mandatory).

Owen walks about with his fire axe in his hand, and everything he said to anyone was said at weapon point: "Is the
water safe to drink?" put a weapon on the woman he asked — she was made to decide at once, as someone in a fight, and
the first things she was offered were to put her hands up, run, or drop flat. A weapon in hand makes an order a
threat (WILL-10); a question or a remark from the same man stays what it is.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.events import Event, EventType
from as_engine.mind import firewall, perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.cues import cues_of
from as_engine.physical import space

pytestmark = pytest.mark.phase(5)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def asked(w, words):
    """Owen, the Glock in his hand, says ``words`` to Mara on the lit sales floor; what she makes of it."""
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        perception.compile_scene(tx, w.id("mara"), t, 0)
        ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("pc"), at=t, turn_index=0,
                                   payload={"words": words, "volume": "normal", "to": [w.id("mara")], "source_db": 60,
                                            "armed": True}))
        perception.compile_aftermath(tx, w.id("mara"), [ev], t + 500, 0)
        d = tx.query_one("SELECT json_extract(detail,'$.armed_at_me') FROM percept_log WHERE event_id=? AND holder_id=?",
                         (ev.event_id, w.id("mara")))
        assert d is not None and d[0], "she sees the gun in his hand"
        cues = cues_of(tx, w.id("mara"), 0, t + 1000)
        a = enumerate_affordances(tx, w.id("mara"), w.canon.all("affordance"), t + 1000, 0)
    return cues, a


@pytest.mark.parametrize("words", ["Is the water safe to drink?", "Cold one tonight.", "Thanks for the coffee."])
def test_a_question_or_a_remark(scenario, words):
    cues, a = asked(scenario("metal_fence"), words)
    assert "weapon_pointed" not in cues
    assert not a.threats


@pytest.mark.parametrize("words", ["Open the door.", "Hands where I can see them.", "Give me the keys or I'll shoot."])
def test_an_order_at_gunpoint(scenario, words):
    w = scenario("metal_fence")
    cues, a = asked(w, words)
    assert "weapon_pointed" in cues and w.id("pc") in a.threats


def test_words_lost_under_a_gun_still_threaten():
    assert firewall.armed_threat("") and not firewall.armed_threat("Who are you?") and firewall.armed_threat("Drop it.")
