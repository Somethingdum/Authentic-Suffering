"""What they are in the middle of (D-238). world/worldgen/opening.py place_pc step 6 (the PC's life.current_project).

A pack character's card leaves what they are working on to the run — "Whatever job is feeding him this week —
decided at worldgen." — and nothing decided it: every prompt that speaks for the player's character, the intake
that reads their words and the memory they write, said "What you are working on: Whatever job is feeding him this
week — decided at worldgen." Now the run's opening — what it asks of them first — is what they are in the middle of.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from as_engine.contracts.settings import EngineConfig, RunSettings
from as_engine.mind import actor, identity
from as_engine.testing.fake_lm import FakeTransport

pytestmark = pytest.mark.phase(10)


def test_what_the_opening_asks_of_them(tmp_path):
    from as_engine.service import runs
    from conftest import REPO_PACKS
    cfg = EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(REPO_PACKS))
    s = asyncio.run(runs.create_run(cfg, "core:pc/owen_marsh", RunSettings(world_detail="gotta_go_to_work_soon", seed=11,
                                                                         era="established", difficulty="normal"), FakeTransport()))
    try:
        objective = json.loads(s.store.query_one("SELECT commit_json FROM world_params WHERE id = 1")[0])["opening"]["first_objective"]
        pc = s.store.meta("pc_actor_id")
        d = actor.fused(s.store, pc)
        assert d.life.current_project == objective
        card = identity.compile_identity(d)
        lines = [ln.text for sec in card.sections for ln in sec.lines]
        assert f"What you are working on: {identity.end(objective)}" in lines
        assert not any("decided at worldgen" in ln for ln in lines)
    finally:
        s.store.close()
