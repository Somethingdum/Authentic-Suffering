"""The way out (D-259). mind/perception.py portal_name, render_portal; mind/affordance.py AFF-07 labels; mind/packet.py
FOCUS-01; narration/location exits.

Worldgen names the way into a house from the street — "the way to the Salazar house" — and a woman inside that house
was told "The way to the Salazar house is open.", offered "Go through the way to the Salazar house into the
crossroads" and "Watch the way to the Salazar house": from inside, the way out read as the way in.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import LOD
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet

pytestmark = pytest.mark.phase(3)


def named(w):
    """The back door, renamed as worldgen names a way into a place: after the place on its far side."""
    p = w.store.query_one("SELECT place_a, place_b FROM portals WHERE portal_id=?", (w.id("back_door"),))
    inside, outside = p[0], p[1]
    name = w.store.query_one("SELECT name FROM places WHERE place_id=?", (inside,))[0]
    w.store.conn.execute("UPDATE portals SET name=? WHERE portal_id=?", (f"the way to {name}", w.id("back_door")))
    w.store.conn.commit()
    out = w.store.query_one("SELECT name FROM places WHERE place_id=?", (outside,))[0]
    return inside, outside, name, perception.place_phrase(out)


def test_from_inside_it_is_the_way_out(scenario):
    w = scenario("metal_fence")
    inside, outside, name, out = named(w)
    with w.store.transaction() as tx:
        assert perception.portal_name(tx, w.id("back_door"), inside) == f"the way out to {out}"
        assert perception.portal_name(tx, w.id("back_door"), outside) == f"the way to {name}"
        assert perception.portal_name(tx, w.id("back_door")) == f"the way to {name}"
        assert perception.render_portal(tx, w.id("back_door"), inside).startswith(f"The way out to {out} is ")


def test_what_she_is_offered_and_can_watch(scenario):
    w = scenario("metal_fence")
    inside, _outside, name, out = named(w)
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    who = w.store.query_one("SELECT body_id FROM positions WHERE place_id=? AND body_id IN (SELECT actor_id FROM actors) "
                            "ORDER BY body_id LIMIT 1", (inside,))
    assert who is not None, "someone is on the inside of it"
    with w.store.transaction() as tx:
        perception.compile_scene(tx, who[0], t, 0)
        a = enumerate_affordances(tx, who[0], w.canon.all("affordance"), t, 0)
        pkt = build_packet(tx, who[0], LOD.HOT, a, 0, t)
    labels = [o.label for o in a.pool if o.target_id == w.id("back_door")]
    assert labels and not [x for x in labels if f"the way to {name}" in x], labels
    assert not [x for x in labels if x.count(out) > 1], "the destination is not said twice"
    watch = [f.label for f in pkt.attention_points if pkt.handles[f.handle] == w.id("back_door")]
    assert watch in ([], [f"Watch the way out to {out}"])
