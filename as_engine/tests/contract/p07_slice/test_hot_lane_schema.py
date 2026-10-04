"""D-111: a HOT decision goes to the hot lane, and whether its JSON schema is sent with thinking on is read from
THAT lane's structured_with_thinking (turn.cognition.cognition_request), not from lane A's."""

from __future__ import annotations

import pytest

from as_engine.contracts.common import LOD, Lane
from as_engine.contracts.settings import EngineConfig
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet
from as_engine.turn.cognition import cognition_request

pytestmark = pytest.mark.phase(7)


def hot_packet(w):
    at = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id("mara"), at, 0)
        aff = enumerate_affordances(tx, w.id("mara"), w.canon.all("affordance"), at, 0)
        return build_packet(tx, w.id("mara"), LOD.HOT, aff, 0, at)


def config(a, b):
    cfg = EngineConfig()
    cfg.lanes[Lane.A].structured_with_thinking = a
    cfg.lanes[Lane.B].structured_with_thinking = b
    return cfg


def test_the_hot_call_reads_structured_with_thinking_from_its_own_lane(scenario):
    pkt = hot_packet(scenario("metal_fence"))
    on_b = cognition_request(config("unsupported", "supported"), pkt, LOD.HOT, Lane.B, reaction=False, turn_index=1)
    assert on_b.lane == Lane.B and on_b.thinking and on_b.json_schema is not None
    off_b = cognition_request(config("supported", "unsupported"), pkt, LOD.HOT, Lane.B, reaction=False, turn_index=1)
    assert off_b.json_schema is None, "lane B cannot hold a schema while it thinks: the JSON is read from the text"
    on_a = cognition_request(config("supported", "unsupported"), pkt, LOD.HOT, Lane.A, reaction=False, turn_index=1)
    assert on_a.lane == Lane.A and on_a.json_schema is not None
