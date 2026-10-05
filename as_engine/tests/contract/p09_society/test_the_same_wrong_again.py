"""The same wrong again (D-194). Core CAS-036 (resentment); action/cascade.py LOOP_OPENED (a loop already held
deepens, mind.mind.strengthen_loop).

Punching June in the face left her trusting Owen less and afraid of him, holding it against him — and no angrier
with him than a shove that missed would have (CAS-067 gives resentment, CAS-036 gave none). And the second punch,
and the fifth, changed nothing she held: a grudge already open is never opened twice (LOOP-02), so the cascade's
"Owen hurt you" fell silent after the first time. Now being hurt makes you angry with the one who did it, and the
same wrong done again is held harder.
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec

pytestmark = pytest.mark.phase(9)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def rel(w, a, b, axis):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def hit(w, who, whom, at):
    with w.store.transaction() as tx:
        start = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0,
                                      actor_id=w.id(who), payload={"actor_id": w.id(who), "def_id": "punch", "verb": "attack",
                                                                   "target_id": w.id(whom)}))
        hurt = bodies.apply_harm(tx, w.id(whom), WoundSpec(Anatomy.ARM_L, WoundType.BLUNT, WoundSeverity.MINOR), at + 300,
                                 start.event_id, 0, w.rng)
        for x in ("pc", "mara", "alice"):
            perception.compile_aftermath(tx, w.id(x), [start] + hurt, at + 800, 0)
    return next(e for e in hurt if e.type == EventType.HARM)


def sweep(w, ev, at):
    with w.store.transaction() as tx:
        return cascade.sweep(tx, [ev], [r for r in w.canon.all("cascade") if r.id == "CAS-036"], at, 0)


def grudges(w, who):
    return [tuple(r) for r in w.store.query("SELECT text, strength FROM open_loops WHERE holder_id = ? AND kind = 'grudge' "
                                            "AND status = 'open'", (w.id(who),))]


def test_hurt_and_angry(scenario):
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", now(w), None, 0)
    t = now(w)
    before = rel(w, "alice", "pc", "resentment")
    sweep(w, hit(w, "pc", "alice", t), t + 1000)
    assert rel(w, "alice", "pc", "resentment") == min(3, before + 1)
    assert grudges(w, "alice") == [("Owen hurt you, and you were not fighting them.", 2)]


def test_again_and_again(scenario):
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", now(w), None, 0)
    t = now(w)
    first = hit(w, "pc", "alice", t)
    sweep(w, first, t + 1000)
    second = hit(w, "pc", "alice", t + 60_000)
    sweep(w, second, t + 61_000)
    assert grudges(w, "alice") == [("Owen hurt you, and you were not fighting them.", 3)], "held harder the second time"
    sweep(w, second, t + 62_000)
    third = hit(w, "pc", "alice", t + 120_000)
    sweep(w, third, t + 121_000)
    assert grudges(w, "alice") == [("Owen hurt you, and you were not fighting them.", 3)], "and no further than it goes"
    assert len(w.store.query("SELECT 1 FROM events WHERE type = 'LOOP_STRENGTH'")) == 1, \
        "one deepening: the same blow swept twice is one blow, and a grudge at its strongest stays there"
