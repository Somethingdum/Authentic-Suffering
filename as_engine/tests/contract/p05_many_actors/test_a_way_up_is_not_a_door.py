"""A way up is not a door (D-240). mind/perception.py render_portal; physical/space.py PARKOUR_KINDS.

Every way out of a place is seen as it stands — but a drainpipe, the gap between two roofs and the front edge of
a roof were seen as doors: "The gutter downpipe is closed." was in the player's view of every house with one, and
the people inside saw it too. A climb, a gap and an edge say what they are, and how far.
"""

from __future__ import annotations

import pytest

from as_engine.mind.perception import render_portal

pytestmark = pytest.mark.phase(5)


def test_a_way_up_a_way_across_and_a_way_down(scenario):
    w = scenario("rooftops")
    with w.store.transaction() as tx:
        seen = {p: render_portal(tx, w.id(p)) for p in ("drainpipe", "market_gap", "long_gap", "market_edge")}
    assert seen == {"drainpipe": "The drainpipe could be climbed, about 5 metres up.",
                    "market_gap": "The gap between the roofs is about 1.6 metres across.",
                    "long_gap": "The long gap to the apartments is about 2.8 metres across.",
                    "market_edge": "The front edge of the market roof drops about 5 metres."}
    assert not any("open" in t or "closed" in t for t in seen.values())


def test_a_door_is_still_a_door(scenario):
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        assert render_portal(tx, w.id("office_door")) == "The office door is closed."
