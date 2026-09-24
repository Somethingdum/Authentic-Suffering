"""Install config (P1). Rules CFG-01..02 (config_loader.py)."""

from __future__ import annotations

import pytest

from as_engine.config_loader import load_engine_config, save_engine_config
from as_engine.contracts.settings import EngineConfig

pytestmark = pytest.mark.phase(1)


def test_missing_file_gives_defaults(tmp_path):
    """CFG-01: no as_config.yaml -> EngineConfig() defaults."""
    cfg = load_engine_config(tmp_path / "nope.yaml")
    assert cfg.lanes == EngineConfig().lanes


def test_unknown_key_is_a_named_error(tmp_path):
    """CFG-02: unknown keys are errors that name the key in plain language."""
    p = tmp_path / "as_config.yaml"
    p.write_text("schema: as.config.v1\nrunz_dir: somewhere\n", encoding="utf-8")
    with pytest.raises(Exception) as ei:
        load_engine_config(p)
    assert "runz_dir" in str(ei.value)


def test_relative_paths_resolve_next_to_the_config(tmp_path):
    p = tmp_path / "cfg" / "as_config.yaml"
    p.parent.mkdir()
    p.write_text("schema: as.config.v1\nruns_dir: my_runs\n", encoding="utf-8")
    cfg = load_engine_config(p)
    assert cfg.runs_dir == str((p.parent / "my_runs").resolve())


def test_round_trip(tmp_path):
    p = tmp_path / "as_config.yaml"
    cfg = EngineConfig()
    save_engine_config(cfg, p)
    again = load_engine_config(p)
    assert again.regimes == cfg.regimes and again.lanes == cfg.lanes
