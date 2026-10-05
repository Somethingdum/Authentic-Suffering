"""What the body wants comes first (D-182). Rule AFF-07 (mind/affordance.py NEED_PRESSING; the act and hold groups'
inner order).

Playing a day through in the store: nobody slept. The people without a timetable stood where they stood until their
fatigue reached the stage where a body drops where it stands, because "sleep" sat last in the hold group, behind
waiting and watching and guarding, and never made the short first list — and the jerky in a starving man's pocket sat
behind everything else he could pick up. Now what answers a pressing need comes first in its group.
"""

from __future__ import annotations

import pytest

from as_engine.mind import perception
from as_engine.mind.affordance import NEED_PRESSING, enumerate_affordances
from as_engine.physical import objects
from as_engine.physical.objects import Holder

pytestmark = pytest.mark.phase(4)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def menu(w, who, t):
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(who), t, 0)
        return enumerate_affordances(tx, w.id(who), tx.canon.all("affordance"), t, 0).options


def test_the_exhausted_see_sleep(scenario):
    w = scenario("metal_fence")
    t = now(w)
    before = [o.def_id for o in menu(w, "june", t)]
    w.store.conn.execute("UPDATE needs SET fatigue_stage = ? WHERE body_id = ?", (NEED_PRESSING + 2, w.id("june")))
    after = [o.def_id for o in menu(w, "june", t + 1000)]
    assert "sleep" in after, after
    hold = [d for d in after if d in ("wait_here", "observe_area", "sleep", "rest", "guard_anchor", "watch_portal")]
    assert hold[0] in ("sleep", "rest") or hold[1] in ("sleep", "rest"), hold
    assert "sleep" not in before or before.index("sleep") > after.index("sleep")


def test_the_starving_see_their_food(scenario):
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        objects.create(tx, "core:item/jerky_pack", 1, Holder("body", w.id("june"), "pocket"), "scenario", {}, t, None, 0)
    w.store.conn.execute("UPDATE needs SET hunger_stage = ? WHERE body_id = ?", (NEED_PRESSING + 2, w.id("june")))
    acts = [o.def_id for o in menu(w, "june", t + 1000)]
    assert "eat_food" in acts, acts
