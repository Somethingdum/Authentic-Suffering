"""One search where many did (D-212). sense.acoustics receptions (one sound-path search from the source for every
listener), physical.space route searches (each place's portals read once per search), mind.affordance (each
distance once per menu), lanes.schemas.to_lm_schema (made once per model).

A turn in a generated world spent more time finding paths than anything else: the same distances were worked out
again for every kind of act on a menu, every route search read the whole portal table at every step, and every
sound searched the map afresh for each listener — twice. These checks hold the faster ways to exactly what the slow
ways gave.
"""

from __future__ import annotations

import itertools

import pytest

from as_engine.lanes import schemas
from as_engine.sense import acoustics

pytestmark = pytest.mark.phase(3)


def test_one_sound_search_reaches_every_listener_as_one_search_each_would(scenario):
    w = scenario("metal_fence")
    places = [r[0] for r in w.store.query("SELECT place_id FROM places ORDER BY place_id")]
    with w.store.transaction() as tx:
        for src in places:
            every = acoustics._min_loss_paths(tx, src)
            for dst in places:
                one = acoustics._min_loss_path(tx, src, dst)
                assert every.get(dst) == one, (src, dst)


def _slow_dijkstra(store, start_place, start_pt, goal_place, goal_pt):
    """The search as it was before D-212: every portal read and scanned at every step, every point read again."""
    import heapq

    from as_engine.physical.space import distance_m, portal_point
    portals = [dict(r) for r in store.query("SELECT * FROM portals ORDER BY portal_id")]
    heap = [(0.0, 1, (), 0, start_place, start_pt, ())]
    settled, n = set(), 0
    while heap:
        cost, flag, seq, _, place, pt, legs = heapq.heappop(heap)
        if flag == 0:
            return cost, [x[0] for x in legs]
        if (place, pt) in settled:
            continue
        settled.add((place, pt))
        if place == goal_place:
            n += 1
            heapq.heappush(heap, (cost + distance_m(*pt, *goal_pt), 0, seq, n, place, pt, legs + ((None, goal_place, 0),)))
        for p in portals:
            if place not in (p["place_a"], p["place_b"]) or p["place_a"] == p["place_b"]:
                continue
            other = p["place_b"] if p["place_a"] == place else p["place_a"]
            if other == start_place or any(pl == other for _, pl, _ in legs):
                continue
            here, there = portal_point(store, p["portal_id"], place), portal_point(store, p["portal_id"], other)
            if (other, there) in settled:
                continue
            n += 1
            heapq.heappush(heap, (cost + distance_m(*pt, *here), 1, seq + (p["portal_id"],), n, other, there,
                                  legs + ((p["portal_id"], other, 0),)))
    return None


def test_routes_and_distances_as_the_slow_search_gave(scenario):
    from as_engine.physical import space
    for name in ("metal_fence", "rooftops", "three_rooms_gunshot"):
        w = scenario(name)
        bodies = [r[0] for r in w.store.query("SELECT body_id FROM positions ORDER BY body_id")]
        with w.store.transaction() as tx:
            for a, b in itertools.combinations(bodies, 2):
                pa, pta = space._body_pt(tx, a)
                pb, ptb = space._body_pt(tx, b)
                if pa == pb:
                    continue
                slow = _slow_dijkstra(tx, pa, pta, pb, ptb)
                fast = space._dijkstra(tx, pa, pta, pb, ptb, lambda p, _pl: True)
                assert (slow is None) == (fast is None), (name, a, b)
                if slow is not None:
                    assert fast[0] == pytest.approx(slow[0], abs=1e-9) and [x.portal_id for x in fast[1]] == slow[1], (name, a, b)


def test_a_schema_is_made_once_and_every_caller_gets_its_own():
    a = schemas.cognition_schema(["A1", "A2"], ["P1"])
    b = schemas.cognition_schema(["A1"], ["P1"])
    assert a != b, "enums set on one copy never leak into another"
    from as_engine.contracts.mind import ActorReplyV2
    x, y = schemas.to_lm_schema(ActorReplyV2), schemas.to_lm_schema(ActorReplyV2)
    assert x == y and x is not y
