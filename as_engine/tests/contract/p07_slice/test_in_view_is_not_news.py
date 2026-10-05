"""In view is not news (D-229). Rule SEL-03 visible_to_pc (turn/select.py salience_flags).

With the player in a room of twelve, every one of them was sent to a model every quiet turn because the player could
see them — seventy-two decisions in six turns where nothing happened, about 44 000 tokens of prompt a turn. Now being
in his view gives salience when he has just come upon them; after that they take stock when 'restless', when
anything else gives them salience, and the room's lines still reach them (AMB-02).
"""

from __future__ import annotations

import pytest

from as_engine.mind import perception
from as_engine.turn import select

pytestmark = pytest.mark.phase(7)

T = 4


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def seen_by_owen(w, who, turn):
    with w.store.transaction() as tx:
        perception.grant(tx, w.id("pc"), event_id=f"scene:test_{who}_{turn}", channel="visual", fidelity="exact",
                         text=f"{who} stands there.", source_id=w.id(who), at=now(w), turn_index=turn)


def visible(w, who):
    with w.store.transaction() as tx:
        return select.salience_flags(tx, w.id(who), [w.id(who)], w.id("pc"), T, now(w))["visible_to_pc"]


def test_just_come_upon(scenario):
    w = scenario("metal_fence")
    seen_by_owen(w, "june", T)
    assert visible(w, "june"), "he has just come upon her"


def test_looked_at_all_along(scenario):
    w = scenario("metal_fence")
    seen_by_owen(w, "june", T - 1)
    seen_by_owen(w, "june", T)
    assert not visible(w, "june"), "she was in front of him the turn before too"


def test_not_seen_at_all(scenario):
    w = scenario("metal_fence")
    seen_by_owen(w, "june", T - 1)
    assert not visible(w, "june")
