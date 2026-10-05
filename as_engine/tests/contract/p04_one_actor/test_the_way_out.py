"""The way out is on the list (D-181). Rule AFF-07 (mind/affordance.py: the move group's inner order).

In the garage with a walker at hand, the short first list held four ways to reach the far side of the car — walk,
run, creep, go and look — and not the open side door to the yard. Leaving the room is the commonest thing anyone
does; with it off the list, the player's "I go out into the yard" cost a second look, and a person deciding had to
ask for more options before they could go.
"""

from __future__ import annotations

import pytest

from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances

pytestmark = pytest.mark.phase(4)


def test_the_side_door_before_the_fourth_way_to_the_car(scenario):
    w = scenario("two_skills")
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id("pc"), t, 0)
        aff = enumerate_affordances(tx, w.id("pc"), tx.canon.all("affordance"), t, 0)
    sigs = [o.signature for o in aff.options]
    out = f"move_through_portal:{w.id('side_door')}:{w.id('yard')}:*"
    assert out in sigs, sigs
    moves = [o for o in aff.options if o.def_id in ("leave_place", "move_through_portal", "go_look", "move_to_anchor",
                                                     "run_to_anchor", "sneak_to_anchor")]
    assert [o.def_id for o in moves][:2] == ["leave_place", "move_through_portal"], "going elsewhere comes first"
    assert any(o.def_id == "sneak_to_anchor" for o in aff.options), "and creeping about the room is still there"
