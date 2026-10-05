"""The Writer knows where they come from (D-260). world/worldgen/people.py WG6 brief (WORLDGEN_ACTOR).

Where a generated person comes from and what they did before the Fall are fixed by their skeleton (D-251) and copied
over whatever the Writer answers — but the Writer was never told them, so it could write a wound in a city the card
says they never lived in, or a nurse who was a trucker. And it never saw what they are in the middle of.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from as_engine.contracts.common import CallClass
from as_engine.contracts.settings import EngineConfig, RunSettings
from as_engine.testing.fake_lm import FakeTransport

pytestmark = pytest.mark.phase(10)


def test_the_fixed_facts_are_in_the_brief(tmp_path):
    from as_engine.service import runs
    from conftest import REPO_PACKS
    fake = FakeTransport()
    cfg = EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(REPO_PACKS))
    s = asyncio.run(runs.create_run(cfg, "core:pc/owen_marsh", RunSettings(world_detail="gotta_go_to_work_soon", seed=11,
                                                                         era="established", difficulty="normal"), fake))
    try:
        idents = {}
        for (j,) in s.store.query("SELECT baseline_json FROM dossiers WHERE source = 'generated'"):
            d = json.loads(j)
            idents[d["identity"]["name"]] = (d["identity"], d["life"].get("current_project"))
        asked = fake.calls(CallClass.WORLDGEN_ACTOR)
        assert asked
        for r in asked:
            u = r.messages[-1].content
            name = u.split(",", 1)[0]
            ident, project = idents[name]
            assert f"They come from {ident['birthplace']}; before the Fall: {ident['occupation_before']}." in u, name
            assert f"- What they are in the middle of: {project}" in u, name
    finally:
        s.store.close()
