"""Theirs to doubt (D-294). world/worldgen/people.py WG6 brief (WORLDGEN_ACTOR): what people around them say.

The Writer was handed every saying a person grew up hearing under "What people around them say, and they believe
too (nothing in the dossier contradicts it …)" — "Only the bitten come back" beside "Put every body down … bitten or
not", "Bite the strip" beside "A bite is a death sentence, full stop" — so every person was written believing every
saying alike, one more way for a world's people to come out the same. They all heard it; what each makes of it is
their own.
"""

from __future__ import annotations

import asyncio

import pytest

from as_engine.contracts.common import CallClass
from as_engine.contracts.settings import EngineConfig, RunSettings
from as_engine.testing.fake_lm import FakeTransport

pytestmark = pytest.mark.phase(10)

HEAD = ("What people around them say — they grew up hearing all of it, and some of it contradicts the rest; which of it "
        "they swear by, doubt or laugh at is theirs (let it show only where it would):")


def test_what_they_make_of_it_is_theirs(tmp_path):
    from as_engine.service import runs
    from conftest import REPO_PACKS
    fake = FakeTransport()
    cfg = EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(REPO_PACKS))
    s = asyncio.run(runs.create_run(cfg, "core:pc/owen_marsh", RunSettings(world_detail="gotta_go_to_work_soon", seed=11,
                                                                         era="established", difficulty="normal"), fake))
    try:
        asked = fake.calls(CallClass.WORLDGEN_ACTOR)
        assert asked
        for r in asked:
            u = r.messages[-1].content
            assert "and they believe too" not in u
            lines = u.split("\n")
            i = lines.index(HEAD)
            assert lines[i + 1].startswith("- "), "the sayings follow"
    finally:
        s.store.close()
