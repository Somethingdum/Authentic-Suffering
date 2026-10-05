"""Names in a sentence (D-256). world/worldgen/history.py WG-19 skeleton (group names as they read inside a sentence);
world/worldgen/people.py (a motive that reads as English).

Every history line starts "Day N: …", so a group's name is always inside the sentence — and the Ghosts came out
capitalised there while the settlers did not: "They say the Diallo People and The Ghosts fought over Sawyer's Fields."
And a pump mechanic's motive read "keep the pump mechanic work going".
"""

from __future__ import annotations

import asyncio

import pytest

from as_engine.contracts.settings import EngineConfig, RunSettings
from as_engine.testing.fake_lm import FakeTransport
from as_engine.world.worldgen import people

pytestmark = pytest.mark.phase(10)


def test_a_group_inside_a_sentence(tmp_path):
    from as_engine.service import runs
    from conftest import REPO_PACKS
    cfg = EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(REPO_PACKS))
    s = asyncio.run(runs.create_run(cfg, "core:pc/owen_marsh", RunSettings(world_detail="standard", seed=7, era="established",
                                                                         difficulty="normal"), FakeTransport()))
    try:
        names = [r[0] for r in s.store.query("SELECT name FROM groups WHERE name LIKE 'The %'")]
        texts = [r[0] for r in s.store.query("SELECT truth_text FROM history_events")]
        assert names and texts
        named = [t for t in texts if any(n[4:] in t for n in names)]
        assert named, "some history names a 'The …' group"
        assert not [t for t in named for n in names if n in t], "never capitalised inside a sentence"
    finally:
        s.store.close()


def test_every_motive_reads_as_english():
    for motive, _method in people._MOTIVES:
        text = motive.format(group="the Vale", settlement="Pumpwell", occupation="pump mechanic")
        assert "pump mechanic work" not in text, text
