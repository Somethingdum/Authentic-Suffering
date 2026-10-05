"""No two strangers alike (D-245). world/worldgen/people.py (PersonSeed.voices_heard, world_voices); WG6 dealing;
world/factions.py (a new operator).

Nobody in one place sounds like someone else there (D-199, D-203) — but a world dealt its voices settlement by
settlement, so a settler and a Ghost two miles apart, or a Remnant and a Ghost, greeted the player with the same
words ("Look at that. Another lovely day…"): three pairs of strangers in one world of eighteen people. While the
world has voices left, nobody is given one already heard anywhere in it.
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


def test_a_world_of_strangers(tmp_path):
    from as_engine.service import runs
    from conftest import REPO_PACKS
    cfg = EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(REPO_PACKS))
    s = asyncio.run(runs.create_run(cfg, "core:pc/owen_marsh", RunSettings(world_detail="standard", seed=7, era="established",
                                                                         difficulty="normal"), FakeTransport()))
    try:
        ids = [r[0] for r in s.store.query("SELECT a.actor_id FROM actors a JOIN bodies b ON b.body_id = a.actor_id JOIN dossiers d "
                                           "ON d.actor_id = a.actor_id WHERE b.kind = 'human' AND a.controller != 'human' "
                                           "AND d.source = 'generated' ORDER BY a.actor_id")]
        firsts = collections.Counter(fused(s.store, a).voice.exemplars.low_stakes for a in ids)
        assert len(ids) >= 12
        assert [k for k, n in firsts.items() if n > 1] == [], "nobody greets the player with someone else's words"
        with s.store.transaction() as tx:
            heard = people.world_voices(tx)
        assert set(firsts) <= set(heard)
    finally:
        s.store.close()


def test_the_heard_are_drawn_last():
    """A seed whose every voice but one has been heard somewhere gets that one."""
    base = dict(name="Pat Vale", age=35, sex="female", cohort="pre_fall_adult", occupation="watcher", skills={"firearms": 1},
                special={L: 5 for L in "SPECIAL"}, variant=123, settlement_name="Vale", group_name="the Vale")
    lines = [ex[0] for ex in people._EXEMPLARS]
    for keep in (0, 17, len(lines) - 1):
        d = people.skeleton_dossier(people.PersonSeed(**base, voices_heard=tuple(x for i, x in enumerate(lines) if i != keep)))
        assert d["voice"]["exemplars"]["low_stakes"] == lines[keep]
