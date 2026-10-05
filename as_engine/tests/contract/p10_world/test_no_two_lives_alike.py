"""No two lives alike (D-247). world/worldgen/people.py (PersonSeed.lives_taken / lives_heard, life_texts, world_lives,
_fresh); WG6 dealing; world/factions.py.

Each generated person's inner life is drawn field by field (D-127), so no two share all of it — but each field on its
own came from a short table, and in one group of seventeen people up to ten shared a motive with someone, up to nine
a signature habit, eight a past wound: two people in one camp had both "hid in a freezer for two days while the street
was eaten". Now, while a table has others, nobody is given a life already given out where they live, then anywhere.
Having no secret is not dealt out: most people have none.
"""

from __future__ import annotations

import asyncio
import collections

import pytest

from as_engine.contracts.settings import EngineConfig, RunSettings
from as_engine.mind.actor import fused
from as_engine.testing.fake_lm import FakeTransport
from as_engine.world.worldgen import people

pytestmark = pytest.mark.phase(10)


def test_one_camp_many_lives(tmp_path):
    from as_engine.service import runs
    from conftest import REPO_PACKS
    cfg = EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(REPO_PACKS))
    s = asyncio.run(runs.create_run(cfg, "core:pc/owen_marsh", RunSettings(world_detail="standard", seed=7, era="established",
                                                                         difficulty="normal"), FakeTransport()))
    try:
        rows = s.store.query("SELECT a.actor_id, (SELECT m.group_id FROM group_members m WHERE m.actor_id = a.actor_id "
                             "ORDER BY m.group_id LIMIT 1) FROM actors a JOIN bodies b ON b.body_id = a.actor_id JOIN dossiers d "
                             "ON d.actor_id = a.actor_id WHERE b.kind = 'human' AND a.controller != 'human' AND d.source = 'generated'")
        shared = collections.Counter()
        for aid, group in rows:
            d = fused(s.store, aid)
            for what, text in (("motive", d.motive.motive), ("wound", d.motive.past_wound), ("conflict", d.motive.inner_conflict),
                               ("habit", d.motive.signature_behaviour), ("hope", d.life.aspiration),
                               ("secret", d.persona.private.concealed_history)):
                if text != "none worth telling":
                    shared[(group, what, text)] += 1
        assert len(rows) >= 12
        assert [k for k, n in shared.items() if n > 1] == []
    finally:
        s.store.close()


def test_a_life_heard_is_drawn_last():
    base = dict(name="Pat Vale", age=35, sex="female", cohort="pre_fall_adult", occupation="watcher", skills={"firearms": 1},
                special={L: 5 for L in "SPECIAL"}, variant=123, settlement_name="Vale", group_name="the Vale")
    wounds = people._WOUNDS["pre_fall_adult"]
    for keep in (0, len(wounds) - 1):
        d = people.skeleton_dossier(people.PersonSeed(**base, lives_heard=tuple(w for i, w in enumerate(wounds) if i != keep)))
        assert d["motive"]["past_wound"] == wounds[keep]
        assert d["motive"]["past_wound"] in people.life_texts(d)


def test_having_no_secret_is_not_used_up():
    """Every real secret given out where they live: an adult then has none, never a repeat."""
    base = dict(name="Pat Vale", age=35, sex="female", cohort="pre_fall_adult", occupation="watcher", skills={"firearms": 1},
                special={L: 5 for L in "SPECIAL"}, settlement_name="Vale", group_name="the Vale")
    real = [x for x in people._SECRETS if x != "none worth telling"]
    got = {people.skeleton_dossier(people.PersonSeed(**base, variant=v, lives_taken=tuple(real[1:])))["persona"]["private"]
           ["concealed_history"] for v in range(60)}
    assert got == {"none worth telling", real[0]}
