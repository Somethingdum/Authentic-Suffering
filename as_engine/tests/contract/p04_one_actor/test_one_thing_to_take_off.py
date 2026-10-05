"""One thing to take off (D-258). Rule AFF-07 (mind/affordance.py: the act group's inner rank and per-def cap).

A woman a man with an axe had just called a coward saw, among her two dozen choices, "Take off your hooded
sweatshirt", "Take off your running jacket" and "Take off your pair of jeans" — three places of a short menu for a
change of clothes. Now a change of one's own clothes comes after every other thing to do with one's hands, and the
first menu offers one piece; the rest are there when asked for more (the pool).
"""

from __future__ import annotations

import asyncio

import pytest

from as_engine.contracts.common import Verb
from as_engine.contracts.settings import EngineConfig, RunSettings
from as_engine.mind.affordance import enumerate_affordances
from as_engine.testing.fake_lm import FakeTransport

pytestmark = pytest.mark.phase(4)

WARDROBE = ("take_off_clothing", "change_into")
ACTS = (Verb.MANIPULATE, Verb.SEARCH, Verb.TREAT, Verb.SIGNAL)


def test_one_piece_on_the_first_menu(tmp_path):
    from as_engine.service import runs
    from pathlib import Path
    REPO_PACKS = Path(__file__).resolve().parents[4] / "as_content" / "packs"
    cfg = EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(REPO_PACKS))
    s = asyncio.run(runs.create_run(cfg, "core:pc/owen_marsh", RunSettings(world_detail="gotta_go_to_work_soon", seed=11,
                                                                         era="established", difficulty="normal"), FakeTransport()))
    try:
        st = s.store
        t = st.query_one("SELECT now_ms FROM world_clock")[0]
        people = [r[0] for r in st.query("SELECT a.actor_id FROM actors a JOIN bodies b ON b.body_id = a.actor_id WHERE "
                                         "b.kind = 'human' AND b.alive = 1 AND a.controller = 'model' ORDER BY a.actor_id LIMIT 8")]
        seen = 0
        for who in people:
            with st.transaction() as tx:
                a = enumerate_affordances(tx, who, tx.canon.all("affordance"), t, 0)
            if len([o for o in a.pool if o.def_id == "take_off_clothing"]) < 2:
                continue
            seen += 1
            shown = [o for o in a.options if o.def_id in WARDROBE]
            assert len([o for o in shown if o.def_id == "take_off_clothing"]) <= 1, who
            acts = [a.options.index(o) for o in a.options if o.verb in ACTS and o.def_id not in WARDROBE]
            if shown and acts:
                assert max(acts) < min(a.options.index(o) for o in shown), "every other act comes first"
        assert seen, "someone wears more than one thing"
    finally:
        s.store.close()


def test_dressing_is_not_looting(canon):
    """A change of one's own clothes is a def tagged 'clothing'; taking clothes off the dead is tagged 'loot' too, and
    keeps its three places (AFF-07)."""
    for d in WARDROBE:
        assert "clothing" in canon.find("affordance", d).tags and "loot" not in canon.find("affordance", d).tags
    assert "loot" in canon.find("affordance", "strip_clothing").tags
