"""Install config loading (P1). Rule CFG-01..03.

load_engine_config(path='as_config.yaml') -> EngineConfig
  Missing file -> defaults (EngineConfig()). YAML mapping validated with EngineConfig.model_validate
  (unknown keys are errors with a plain-language message naming the key). Relative paths
  (runs_dir, content_dir, compiled_dir) resolve against the directory holding the config file.
save_engine_config(config, path) writes YAML with sort_keys=False, preserving comments is NOT
  required. Only the UI's config_set may call it at runtime.
"""

from __future__ import annotations

from pathlib import Path

from .contracts.settings import EngineConfig


def load_engine_config(path: str | Path = "as_config.yaml") -> EngineConfig:
    raise NotImplementedError("P1")


def save_engine_config(config: EngineConfig, path: str | Path = "as_config.yaml") -> None:
    raise NotImplementedError("P1")
