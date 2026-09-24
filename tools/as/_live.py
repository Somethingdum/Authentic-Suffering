"""Shared helpers for the live tools (probe, bench, eval). Not part of the engine."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "as_config.yaml"
REPORTS = ROOT / "as_runs" / "reports"


def need(phase: str, what: str):
    print(f"{what} needs the engine through {phase}: that stub still raises NotImplementedError.", file=sys.stderr)
    sys.exit(3)


def load_config():
    try:
        from as_engine.config_loader import load_engine_config
        return load_engine_config(CONFIG)
    except NotImplementedError:
        need("P1", "config_loader.load_engine_config")


def save_config(cfg) -> None:
    try:
        from as_engine.config_loader import save_engine_config
        save_engine_config(cfg, CONFIG)
    except NotImplementedError:
        need("P1", "config_loader.save_engine_config")
