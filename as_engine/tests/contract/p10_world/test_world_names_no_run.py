"""A world names no run (P10; the owner's hard delete, RUN-12). Rule RUN-09 (world/worldgen/
pipeline.py GENESIS; kernel/store.py Store.backup_to(..., as_world=)).

A world outlives the lives played in it, so its genesis — the world before any character was
placed — holds nothing that names the run that made it: its meta says the world's own id and it
keeps no model traffic. Deleting that run leaves the world, and no trace of the run in it.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from as_engine.kernel.store import Store
from as_engine.service import runs

pytestmark = pytest.mark.phase(10)


def read(path: Path) -> tuple[dict, int]:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
        calls = con.execute("SELECT COUNT(*) FROM lm_calls").fetchone()[0]
    finally:
        con.close()
    return meta, calls


def test_the_genesis_names_no_run(made_world):
    meta, calls = read(made_world.root / "runs" / "_worlds" / made_world.world_id / "genesis.sqlite")
    assert meta["run_id"] == made_world.world_id
    assert calls == 0, "no model traffic in a world"
    assert not any(made_world.run_id in str(v) for v in meta.values())


def test_a_world_copy_changes_only_the_copy(world_cfg, made_world, tmp_path):
    live = Store.open(Path(world_cfg.runs_dir) / made_world.run_id / "world.sqlite")
    try:
        calls = live.query_one("SELECT COUNT(*) FROM lm_calls")[0]
        assert calls > 0, "worldgen asked the model"
        live.backup_to(tmp_path / "copy.sqlite", as_world="w_copy")
        assert live.meta("run_id") == made_world.run_id
        assert live.query_one("SELECT COUNT(*) FROM lm_calls")[0] == calls
    finally:
        live.close()
    meta, n = read(tmp_path / "copy.sqlite")
    assert (meta["run_id"], n) == ("w_copy", 0)


def test_deleting_the_run_leaves_the_world(world_cfg, made_world):
    root = Path(world_cfg.runs_dir)
    runs.delete_run(world_cfg, made_world.run_id)
    assert not (root / made_world.run_id).exists()
    assert (root / "_worlds" / made_world.world_id / "genesis.sqlite").exists()
    assert (root / "_worlds" / made_world.world_id / "world.json").exists()
