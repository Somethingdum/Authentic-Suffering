"""No telepathy (P5, re-run inside the slice at P7). Rule TELEPATHY-01, SKULL-01.

What one mind is shown must not depend on the order minds are processed in, nor on what another
mind has decided before the barrier: contexts are built from each mind's own percepts, and intents
change nothing until the resolver runs.
"""

from __future__ import annotations

import itertools

import pytest

from as_engine.action.intent import to_intent
from as_engine.contracts.common import LOD, CallClass
from as_engine.contracts.events import Event, EventType
from as_engine.contracts.mind import CognitionOutput
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet
from as_engine.prompts.render import render

pytestmark = pytest.mark.phase(5)

ACTORS = ("june", "mara", "alice")


def _crash(w):
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", at=t, turn_index=0,
                              payload={"source_db": 98, "kind": "metal_crash", "text": "a loud metal crash",
                                       "place_id": w.id("alley"), "anchor_id": w.id("fence_sheet")}))
        tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=t + 600, turn_index=0,
                              actor_id=w.id("pc"), payload={"words": "Everyone stay put.", "volume": "raised",
                                                           "to": ["everyone"], "source_db": 70}))
    return t + 1000


def _context(w, local, at):
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(local), at, 0)
        aff = enumerate_affordances(tx, w.id(local), w.canon.all("affordance"), at, 0)
        pkt = build_packet(tx, w.id(local), LOD.WARM, aff, 0, at)
    msgs = render(CallClass.ACTOR_COGNITION, p=pkt)
    return msgs[0].content + "\n" + msgs[1].content, pkt, aff


def test_order_permutation_identical_contexts(scenario):
    seen = None
    for order in itertools.permutations(ACTORS):
        w = scenario("metal_fence")
        at = _crash(w)
        texts = {local: _context(w, local, at)[0] for local in order}
        if seen is None:
            seen = texts
        else:
            assert texts == seen, f"context depends on processing order {order}"


def test_deciding_changes_nothing_another_mind_can_see(scenario):
    w = scenario("metal_fence")
    at = _crash(w)
    before, _p, _a = _context(w, "june", at)
    _t, mpkt, maff = _context(w, "mara", at)
    run = next(o.handle for o in mpkt.affordances if mpkt.handles[o.handle].startswith("run_to_anchor"))
    n = w.store.query_one("SELECT COUNT(*) FROM events")[0]
    intent = to_intent(mpkt, maff, CognitionOutput(choice=run, speech={"text": "June, back door, now.", "to": ["everyone"]},
                                                   goal="cover the back", private_reason="the crash"), lod=LOD.WARM, source="model")
    assert intent.bound.def_id == "run_to_anchor"
    assert w.store.query_one("SELECT COUNT(*) FROM events")[0] == n, "an intent is not an event"
    after, _p, _a = _context(w, "june", at)
    assert after == before, "Mara's decision leaked into June's context before the barrier"
