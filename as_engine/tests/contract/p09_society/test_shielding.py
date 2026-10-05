"""Shielding (D-139). action/cascade.py selector protecting_today; core CAS-058; mind/resolve.py's
protected_dependent recovery (05 §5).

05 §5 promised that protecting a dependent gives a little Resolve back, and nothing ever gave it: without a
limit, shielding someone would pump a person's nerve back up turn after turn. Now putting yourself between
someone you look after and the danger gives back one point, once a day however often you do it.
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.action.effects import SEEN
from as_engine.contracts.events import Event, EventType

pytestmark = pytest.mark.phase(9)

DAY = 86_400_000


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def resolve(w, who):
    return w.store.query_one("SELECT resolve_cur FROM actors WHERE actor_id = ?", (w.id(who),))[0]


def shield(w, who, whom, at):
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0, actor_id=w.id(who),
                                   payload={"actor_id": w.id(who), "def_id": "shield_dependent", "verb": "guard", "visible": True,
                                            "seen": SEEN.get("shield_dependent"), "target_id": w.id(whom)}))
        cascade.sweep(tx, [ev], [r for r in w.canon.all("cascade") if r.id == "CAS-058"], at, 0)
    return ev


def test_once_a_day(scenario):
    """Mara puts herself between Eli and the danger: one point back. Again an hour later: nothing. The next day:
    one more."""
    w = scenario("metal_fence")
    t = now(w)
    w.store.conn.execute("UPDATE actors SET resolve_cur = 1 WHERE actor_id = ?", (w.id("mara"),))
    shield(w, "mara", "eli", t + 1000)
    assert resolve(w, "mara") == 2
    shield(w, "mara", "eli", t + 3_600_000)
    assert resolve(w, "mara") == 2, "not a way to fill yourself back up"
    shield(w, "mara", "eli", t + 1000 + DAY + 1)
    assert resolve(w, "mara") == 3


def test_nothing_but_shielding_counts(scenario):
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=t + 1000, turn_index=0,
                                   actor_id=w.id("mara"), payload={"actor_id": w.id("mara"), "def_id": "wait_here", "verb": "wait"}))
        assert cascade.select(tx, "protecting_today(trigger.event_id)", ev) == []
