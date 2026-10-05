"""The dead coming on (D-233). action/reactions.py material_holders (P10 clause; DEAD_NEAR_M).

Every step one of the dead took within twenty metres was news to everyone who saw it, in every wave: with walkers
coming at a building of ten, the first turn sent thirty reactions to the Clerk — each person answering the same
walker three times as it shuffled a few metres closer. Now the first time someone sees it coming in a turn is news,
and after that only when it is upon them.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from as_engine.action import reactions
from as_engine.mind import perception
from as_engine.physical import space

pytestmark = pytest.mark.phase(5)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def step(w, x, y, at, turn=0, who="shambler"):
    """The shambler moves to (x, y) in the garage; Sam (twin_a, at 3, 2) sees it. Is it material to him?"""
    with w.store.transaction() as tx:
        ev = tx.commit_event(space.move_event(tx, w.id(who), w.id("garage"), None, x, y, at, None, turn))
        perception.compile_aftermath(tx, w.id("twin_a"), [ev], at + 200, turn)
        return w.id("twin_a") in [h for h, _t in reactions.material_holders(tx, [ev], turn)]


def test_seen_coming_then_upon_him(scenario):
    w = scenario("two_skills")
    t = now(w)
    assert step(w, 7.9, 5.9, t), "it comes on, 6.3 m away: news"
    assert not step(w, 7.5, 5.5, t + 2000), "a step closer, 5.7 m: he has seen it coming"
    assert step(w, 5.0, 3.0, t + 4000), f"within {reactions.DEAD_NEAR_M} m: it is upon him"


def test_a_new_turn_is_news_again(scenario):
    w = scenario("two_skills")
    t = now(w)
    assert step(w, 7.9, 5.9, t, turn=0)
    assert step(w, 7.5, 5.5, t + 30_000, turn=1), "the next turn he looks again"


def test_another_one_behind_it(fixture_packs, core_pack_dir):
    """A second of the dead coming on behind the first is not a new thing to decide about — until it is upon him."""
    from as_engine.testing.scenario import load_scenario
    spec = yaml.safe_load((Path(__file__).resolve().parents[2] / "fixtures" / "scenarios" / "two_skills.yaml").read_text())
    spec["bodies"].append({"id": "shambler2", "infected": "ZOMBIE_ARCHETYPE_SHAMBLER01", "controller": "policy",
                           "place": "garage", "x": 7.6, "y": 0.6})
    w = load_scenario(spec, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
    try:
        t = now(w)
        assert step(w, 7.9, 5.9, t)
        assert not step(w, 7.9, 0.6, t + 1000, who="shambler2"), "the second one, 5.1 m off: the dead are coming, he knows"
        assert step(w, 4.0, 1.0, t + 2000, who="shambler2"), "upon him"
    finally:
        w.store.close()
