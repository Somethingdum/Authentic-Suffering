"""The same memory twice (D-272). mind/retrieval.py MEM-14.

A person who wrote down the same thing on two turns ("A tall, heavyset man stands, an axe in his hand.") was shown it
twice under 'What you remember', and two of their few memory slots said one thing. The same memory twice is one
memory; the slot goes to another.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.mind import WritebackOutput
from as_engine.mind import memory, retrieval

pytestmark = pytest.mark.phase(6)

HOUR = 3_600_000


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def episode(w, base, at, summary, salience=30):
    with w.store.transaction() as tx:
        memory.apply_writeback(tx, w.id("june"), WritebackOutput(episode=summary, salience=salience), base, at, 0,
                               cue_ids=frozenset())
    return w.store.query_one("SELECT episode_id FROM episodes WHERE holder_id = ? ORDER BY rowid DESC LIMIT 1", (w.id("june"),))[0]


def test_said_once(scenario):
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        base = memory.build_aftermath(tx, w.id("june"), 0, t)
    base = base.model_copy(update={"entities": [], "percepts": [], "utterances": [], "relationships": []})
    first = episode(w, base, t - 2 * HOUR, "A tall man stands by the door, an axe in his hand.")
    again = episode(w, base, t - HOUR, "a tall man stands by the door, an axe in his hand. ")
    other = episode(w, base, t - 3 * HOUR, "Counted the cans twice and got two numbers.")
    with w.store.transaction() as tx:
        got = retrieval.retrieve(tx, w.id("june"), 1, t, max_beliefs=6, max_memories=2, max_loops=3)
    ids = [e["episode_id"] for e in got.episodes]
    assert len(ids) == 2 and other in ids, ids
    assert len({first, again} & set(ids)) == 1, "one of the two, not both"
    assert again in ids, "the newer of the two: it scores higher"
