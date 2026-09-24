#!/usr/bin/env python3
"""One-time setup for the Authentic Suffering build.

  python tools/as/setup.py            install as_engine (editable) with test extras into the ACTIVE
                                      Python environment, copy as_config.example.yaml -> as_config.yaml
                                      when missing, add the AS lines to .gitignore, write the harness
                                      hook files, then run the doctor
  python tools/as/setup.py --hooks    only (re)write the hook files for the active Python

Use Talemate's own virtual environment (the game's backend imports as_engine from it):
  Windows:  .venv\\Scripts\\activate          (made by Talemate's install.bat)
  Linux:    source .venv/bin/activate
It is made by uv and has no pip; this script then installs with uv (on PATH, or Talemate's
embedded_python on Windows).

Hook files (Claude-Code hook format; DeepSeek Harness runs them through its hook bridge plugins):
  .dsh/hooks.json          for @deepseek-ai/dsh-hooks-claude-code (point its configPath here)
  .claude/settings.json    for dsh-hooks-claude-code-per-workspace (and for Claude Code itself)
Both hold the same three hooks, with absolute paths to this machine's Python and scripts:
  SessionStart -> tools/as/gate.py --brief         the current phase and Next task as context
  PreToolUse   -> tools/as/protect.py --hook       blocks writes to protected files (exit 2)
  Stop         -> tools/as/gate.py --stop-check    'Next task' filled and protection intact
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOK_FILES = (ROOT / ".dsh" / "hooks.json", ROOT / ".claude" / "settings.json")


def _q(path: str | Path) -> str:
    """A path for a hook command line: forward slashes (valid for cmd.exe, PowerShell and bash alike)
    and double quotes (paths with spaces)."""
    return '"' + str(path).replace("\\", "/") + '"'


def hook_config(python: str) -> dict:
    py = _q(python)
    tool = lambda name: _q(ROOT / "tools" / "as" / name)  # noqa: E731
    return {"hooks": {
        "SessionStart": [{"hooks": [{"type": "command", "command": f"{py} {tool('gate.py')} --brief",
                                     "timeout": 60}]}],
        "PreToolUse": [{"matcher": ".*",
                        "hooks": [{"type": "command", "command": f"{py} {tool('protect.py')} --hook",
                                   "timeout": 30}]}],
        "Stop": [{"hooks": [{"type": "command", "command": f"{py} {tool('gate.py')} --stop-check",
                             "timeout": 120}]}],
    }}


GITIGNORE_LINES = ("as_runs/", "as_content/_compiled/", "as_config.yaml", ".dsh/hooks.json")


def update_gitignore() -> None:
    """Add the AS lines to Talemate's .gitignore (02 §4.1) so run data, your config and the
    machine-local hook file are never committed. Idempotent."""
    gi = ROOT / ".gitignore"
    text = gi.read_text(encoding="utf-8") if gi.exists() else ""
    missing = [ln for ln in GITIGNORE_LINES if ln not in text.splitlines()]
    if missing:
        block = ("" if text.endswith("\n") or not text else "\n") + "\n# Authentic Suffering\n" + "\n".join(missing) + "\n"
        gi.write_text(text + block, encoding="utf-8")
        print("added to .gitignore:", ", ".join(missing))


def write_hooks() -> None:
    cfg = json.dumps(hook_config(sys.executable), indent=2) + "\n"
    for f in HOOK_FILES:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(cfg, encoding="utf-8")
        print(f"wrote {f.relative_to(ROOT).as_posix()}")
    print("\nDeepSeek Harness: enable ONE of the two hook bridges for the profile you build with.")
    print("  (a) official bridge — add to that profile's cordis.patch.yml:")
    print("      - id: hooks-claude-code")
    print("        name: '@deepseek-ai/dsh-hooks-claude-code'")
    print("        config:")
    print(f"          configPath: {(ROOT / '.dsh' / 'hooks.json').as_posix()}")
    print(f"          projectDir: {ROOT.as_posix()}")
    print("  (b) per-workspace bridge — dsh plugin --profile <profile> add dsh-hooks-claude-code-per-workspace")
    print("      (it reads .claude/settings.json from the workspace you open: open the repo root)")
    print("  Check: a new DSH session in this repo starts with 'Authentic Suffering build — session brief'.")


def _installer() -> list[str] | None:
    """pip when this Python has it; otherwise uv (a uv-made venv, like Talemate's .venv, has no pip).
    Talemate's Windows install keeps uv inside embedded_python/."""
    if importlib.util.find_spec("pip") is not None:
        return [sys.executable, "-m", "pip", "install"]
    uv = shutil.which("uv")
    if uv:
        return [uv, "pip", "install", "--python", sys.executable]
    embedded = ROOT / "embedded_python" / "python.exe"
    if embedded.exists():
        return [str(embedded), "-m", "uv", "pip", "install", "--python", sys.executable]
    return None


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv and argv[0] == "--hooks":
        update_gitignore()
        write_hooks()
        return 0
    if sys.prefix == sys.base_prefix:
        print("warning: no virtual environment is active; installing into the system Python.")
    installer = _installer()
    if installer is None:
        print("neither pip nor uv is available for this Python. Talemate's venv is made by uv and has no pip:")
        print("  install uv (https://docs.astral.sh/uv/) or run: python -m ensurepip")
        return 1
    cmd = [*installer, "-e", str(ROOT / "as_engine") + "[dev]"]
    print("+", " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print("pip install failed; see the output above.")
        return r.returncode
    cfg, example = ROOT / "as_config.yaml", ROOT / "as_config.example.yaml"
    if not cfg.exists() and example.exists():
        shutil.copyfile(example, cfg)
        print("copied as_config.example.yaml -> as_config.yaml (edit the lane URLs and model ids)")
    update_gitignore()
    write_hooks()
    return subprocess.run([sys.executable, str(ROOT / "tools" / "as" / "doctor.py")]).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
