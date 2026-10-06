"""Hands on someone you love (D-282). mind/temper.py TEMPER-03 (manhandled_bonded); core cascade CAS-119..121.

Someone Mara loves hurt in front of her was answered (CAS-040), nearly killed (D-180), threatened or called names
(D-262) — but shoved about, grabbed and pinned, grabbed at for what was in her hand: nothing. Owen could push June
around the sales floor all evening and Mara thought no worse of him, and did not so much as bristle. Now hands put on
someone she loves anger her as if it were done to her, and she holds it against him, each time.
"""

from __future__ import annotations

import pytest

import helpers
from as_engine.action import cascade
from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.mind import perception, temper
from as_engine.physical import space

pytestmark = pytest.mark.phase(9)

RULES = ("CAS-119", "CAS-120", "CAS-121")


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def scene(w):
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("sales_floor"), None, 5.0, 2.0, t, None, 0))
        tx.commit_event(space.move_event(tx, w.id("pc"), w.id("sales_floor"), None, 5.6, 2.0, t, None, 0))
        for who in ("mara", "alice"):
            perception.compile_scene(tx, w.id(who), t, 0)


def does(w, def_id):
    t = now(w)
    with w.store.transaction() as tx:
        evs = resolve_wave(tx, w.rng, barrier(tx, [helpers.make_intent(w, "pc", def_id, target="june")]), t, 0,
                           horizon_ms=t + 1_800_000)
        start = next(e for e in evs if e.type.value == "ACTION_START")
        for who in ("mara", "alice"):
            perception.compile_aftermath(tx, w.id(who), [start], t + 500, 0)
        got = {who: [(p.kind, w.local(p.toward_id)) for p in temper.provocations(tx, w.id(who), 0, t + 1000)]
               for who in ("mara", "alice")}
        cascade.sweep(tx, [start], [r for r in w.canon.all("cascade") if r.id in RULES], t + 1000, 0)
    return got


def resentment(w, who):
    r = w.store.query_one("SELECT resentment FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(who), w.id("pc")))
    return r[0] if r else 0


@pytest.mark.parametrize("def_id", ["shove", "grapple"])
def test_june_manhandled_in_front_of_mara(scenario, def_id):
    w = scenario("metal_fence")
    scene(w)
    before = resentment(w, "mara"), resentment(w, "alice")
    got = does(w, def_id)
    assert ("manhandled_bonded", "pc") in got["mara"], got
    assert not got["alice"], "Alice has no bond with June"
    assert resentment(w, "mara") == before[0] + 1 and resentment(w, "alice") == before[1]
