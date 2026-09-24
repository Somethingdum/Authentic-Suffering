#!/usr/bin/env python3
"""Environment doctor for the Authentic Suffering build (docs/as/12_TESTING.md §10).

  python tools/as/doctor.py            checks; exit 1 when a RED item exists
  python tools/as/doctor.py --lanes    also contacts the LM Studio lanes in as_config.yaml

Colours: OK / WARN (fine for now, needed later) / RED (fix before building).
Only the standard library is required to run it; it reports what else is missing.
"""

from __future__ import annotations

import importlib
import json
import shlex
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

for _stream in (sys.stdout, sys.stderr):          # hook runners read pipes as UTF-8 (Windows default: cp1252)
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT / "tools" / "as"))
import protect  # noqa: E402

results: list[tuple[str, str, str]] = []


def add(level: str, what: str, detail: str = "") -> None:
    results.append((level, what, detail))


def check_python() -> None:
    v = sys.version_info
    add("OK" if v >= (3, 11) else "RED", "python >= 3.11", f"{v.major}.{v.minor}.{v.micro} at {sys.executable}")


def check_packages() -> None:
    for mod, why in (("pydantic", "contracts"), ("jinja2", "prompts"), ("yaml", "content and scenarios"),
                     ("httpx", "lane transport"), ("pytest", "tests"), ("pytest_asyncio", "async tests")):
        try:
            m = importlib.import_module(mod)
            add("OK", f"package {mod}", getattr(m, "__version__", ""))
        except ImportError:
            add("RED", f"package {mod}", f"missing ({why}) — run python tools/as/setup.py")
    try:
        importlib.import_module("as_engine")
        add("OK", "as_engine importable")
    except ImportError as e:
        add("RED", "as_engine importable", f"{e} — run python tools/as/setup.py (pip install -e ./as_engine)")


def check_protection() -> None:
    problems = protect.verify()
    add("OK" if not problems else "RED", "protected files match the manifest",
        "" if not problems else "; ".join(problems[:5]) + (" …" if len(problems) > 5 else ""))


def check_progress() -> None:
    p = ROOT / "docs" / "as" / "PROGRESS.md"
    text = p.read_text(encoding="utf-8") if p.exists() else ""
    line = next((ln for ln in text.splitlines() if ln.startswith("- Next task:")), "")
    add("OK" if line.split(":", 1)[-1].strip() else "RED", "PROGRESS.md has a Next task", line)


def check_hooks() -> None:
    """The harness hook files exist and use this machine's Python by absolute path."""
    for rel in protect.MACHINE_LOCAL:
        f = ROOT / rel
        if not f.exists():
            add("RED", f"hook file {rel}", "missing — run python tools/as/setup.py --hooks")
            continue
        try:
            cmds = [h.get("command", "") for groups in json.loads(f.read_text(encoding="utf-8")).get("hooks", {}).values()
                    for g in groups for h in g.get("hooks", [])]
        except (ValueError, AttributeError) as e:
            add("RED", f"hook file {rel}", f"unreadable: {e}")
            continue
        exe = shlex.split(cmds[0].replace("\\", "/"))[0] if cmds else ""
        if not Path(exe).is_absolute():
            add("WARN", f"hook file {rel}", "uses a relative 'python' — run python tools/as/setup.py --hooks "
                "inside the build venv so the hooks use it by absolute path")
        elif not Path(exe).exists():
            add("RED", f"hook file {rel}", f"{exe} does not exist — rerun python tools/as/setup.py --hooks")
        else:
            add("OK", f"hook file {rel}", exe)
    probe = subprocess.run([sys.executable, str(ROOT / "tools" / "as" / "protect.py"), "--hook"], text=True,
                           capture_output=True, input=json.dumps({"tool_name": "Write", "tool_input": {
                               "file_path": "as_engine/tests/helpers.py", "content": "x"}}), cwd=ROOT)
    add("OK" if probe.returncode == 2 else "RED", "protection hook blocks a protected write",
        "" if probe.returncode == 2 else f"exit {probe.returncode}: {probe.stderr.strip()[:120]}")


def check_agent_files() -> None:
    """DSH loads AGENTS.md and CLAUDE.md from the repo root down; only ours should be there."""
    for name in ("CLAUDE.md", "claude.md"):
        f = ROOT / name
        if f.exists() and "Authentic Suffering" not in f.read_text(encoding="utf-8", errors="replace")[:400]:
            add("WARN", f"{name} at the repo root", "not ours — the harness loads it next to AGENTS.md; "
                "rename it (e.g. CLAUDE.talemate.md) so the builder reads only AGENTS.md")
    size = sum((ROOT / n).stat().st_size for n in ("AGENTS.md", "CLAUDE.md") if (ROOT / n).exists())
    add("OK" if size < 48_000 else "WARN", "always-loaded instructions size", f"{size} bytes (DSH budget 64 KB)")


def check_config() -> None:
    cfg = ROOT / "as_config.yaml"
    if cfg.exists():
        add("OK", "as_config.yaml present")
    else:
        add("WARN", "as_config.yaml present", "copy as_config.example.yaml (setup.py does) — needed for live play, not for tests")


def check_git() -> None:
    if shutil.which("git") is None:
        add("WARN", "git", "not found — gate evidence will say '(not a git repo)'")
        return
    r = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT, capture_output=True, text=True)
    add("OK" if r.returncode == 0 else "WARN", "git work tree", "" if r.returncode == 0 else "not a git repo — commit the kit first")
    t = subprocess.run(["git", "tag", "--list", "0.39.0"], cwd=ROOT, capture_output=True, text=True)
    add("OK" if t.stdout.strip() else "WARN", "Talemate tag 0.39.0", "" if t.stdout.strip() else "needed by gate.py --upstream-diff (P8)")


def check_frontend() -> None:
    """P8 needs Node >= 22.13 (Talemate's pnpm 11 via corepack). Talemate's Windows installer keeps its
    own Node in embedded_node/; either one is fine."""
    node = shutil.which("node") or next((str(p) for p in (ROOT / "embedded_node").glob("node*") if p.is_file()), None)
    if not node:
        add("WARN", "node >= 22.13", "not found — needed from P8 (Play UI tests)")
        return
    try:
        v = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=20).stdout.strip()
        major, minor = (int(x) for x in v.lstrip("v").split(".")[:2])
        ok = (major, minor) >= (22, 13)
        add("OK" if ok else "WARN", "node >= 22.13", v + ("" if ok else " — too old for pnpm 11 (needed from P8)"))
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        add("WARN", "node >= 22.13", f"{node}: {e}")
    add("OK" if shutil.which("corepack") else "WARN", "corepack (runs Talemate's pinned pnpm)",
        "" if shutil.which("corepack") else "not on PATH — needed from P8; it ships with Node")


def check_lanes() -> None:
    cfg = ROOT / "as_config.yaml"
    if not cfg.exists():
        add("WARN", "lanes", "no as_config.yaml")
        return
    try:
        import yaml
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
    except Exception as e:  # noqa: BLE001
        add("RED", "as_config.yaml parses", str(e))
        return
    for name, lane in (data.get("lanes") or {}).items():
        url = str(lane.get("base_url", "")).rstrip("/") + "/models"
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                ids = [m.get("id") for m in json.load(r).get("data", [])]
            want = lane.get("model", "")
            add("OK" if (not want or want in ids) else "RED", f"lane {name} reachable",
                f"{url} models={ids[:4]}" + ("" if (not want or want in ids) else f" — configured model '{want}' not loaded"))
        except Exception as e:  # noqa: BLE001
            add("WARN", f"lane {name} reachable", f"{url}: {e}")


def main(argv: list[str]) -> int:
    check_python()
    check_packages()
    check_protection()
    check_hooks()
    check_agent_files()
    check_progress()
    check_config()
    check_git()
    check_frontend()
    if "--lanes" in argv:
        check_lanes()
    width = max(len(w) for _l, w, _d in results)
    for level, what, detail in results:
        print(f"{level:4}  {what.ljust(width)}  {detail}")
    red = [r for r in results if r[0] == "RED"]
    print(f"\n{len(red)} red, {sum(r[0] == 'WARN' for r in results)} warn")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
