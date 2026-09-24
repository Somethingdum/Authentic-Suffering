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
    import yaml
    from pydantic import ValidationError
    p = Path(path)
    if not p.exists():
        return EngineConfig()
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    try:
        cfg = EngineConfig.model_validate(data)
    except ValidationError as e:
        msgs = []
        for er in e.errors():
            loc = ".".join(str(x) for x in er["loc"])
            if er["type"] == "extra_forbidden":
                msgs.append(f"{p.name}: unknown setting '{loc}' (check the spelling)")
            else:
                msgs.append(f"{p.name}: '{loc}': {er['msg']}")
        raise ValueError("; ".join(msgs)) from None
    base = p.parent.resolve()
    upd = {}
    for k in ("runs_dir", "content_dir", "compiled_dir"):
        v = getattr(cfg, k)
        if not Path(v).is_absolute():
            upd[k] = str((base / v).resolve())
    return cfg.model_copy(update=upd)


def save_engine_config(config: EngineConfig, path: str | Path = "as_config.yaml") -> None:
    import yaml
    Path(path).write_text(yaml.safe_dump(config.model_dump(mode="json", by_alias=True), sort_keys=False), encoding="utf-8")
