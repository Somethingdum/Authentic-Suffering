#!/usr/bin/env python3
"""Protected files for the Authentic Suffering build (PROTECTED — never edit this file).

Usage:
  python tools/as/protect.py --list              print the protected patterns and files
  python tools/as/protect.py --verify            compare every protected file with the manifest (exit 1 on drift)
  python tools/as/protect.py --check PATH        exit 1 if PATH is protected
  python tools/as/protect.py --hook              PreToolUse hook (Claude-Code hook format, also used by
                                                 DSH's dsh-hooks-claude-code plugin): reads the tool call
                                                 JSON on stdin and exits 2 (block) when it would write a
                                                 protected path.
  AS_MAINTAINER=1 python tools/as/protect.py --write-manifest    (kit maintainer only)
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

for _stream in (sys.stdout, sys.stderr):          # hook runners read pipes as UTF-8 (Windows default: cp1252)
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
MANIFEST = ROOT / "tools" / "as" / "protected_manifest.json"

PROTECTED: tuple[str, ...] = (
    "as_engine/tests/contract/**",
    "as_engine/tests/fixtures/**",
    "as_engine/tests/sim/**",
    "as_engine/tests/live/**",
    "talemate_frontend/src/play/__tests__/**",
    "talemate_frontend/src/play/README.md",
    "tests/test_as_game_plugin.py",
    "as_engine/tests/conftest.py",
    "as_engine/tests/helpers.py",
    "as_engine/src/as_engine/testing/fake_lm.py",
    "as_engine/src/as_engine/kernel/jsoncanon.py",
    "as_engine/src/as_engine/content/safety.py",
    "docs/as/*.md",
    "docs/as/reference/**",
    "tools/as/protect.py",
    "tools/as/gate.py",
    "tools/as/doctor.py",
    "tools/as/protected_manifest.json",
    "AGENTS.md",
    ".dsh/**",
    ".claude/settings.json",
)
# Inside docs/as these two are the builder's to edit.
EDITABLE: tuple[str, ...] = ("docs/as/PROGRESS.md", "docs/as/SPEC_ISSUES.md")
# Hook files hold this machine's Python path (tools/as/setup.py writes them): guarded against edits by
# the hook like any protected file, but checked for the required hook commands instead of by hash.
MACHINE_LOCAL: tuple[str, ...] = (".dsh/hooks.json", ".claude/settings.json")
HOOK_MARKERS: tuple[str, ...] = ("protect.py", "--hook", "gate.py", "--stop-check", "--brief")
SKIP_PARTS = ("__pycache__", ".pytest_cache")


def _rel(path: str | Path) -> str:
    """`path` relative to the repo root in / form (absolute form when it lies outside the repo)."""
    p = Path(str(path).replace("\\", "/"))
    if not p.is_absolute():
        p = Path.cwd() / p
    try:
        p = p.resolve()
    except (OSError, ValueError):
        pass
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def _fold(s: str) -> str:
    return s.lower() if os.name == "nt" else s


def _match_rel(rel: str) -> bool:
    """True when the repo-relative path `rel` is protected (case-insensitive on Windows)."""
    r = _fold(rel)
    if r in {_fold(e) for e in EDITABLE} or any(part in r.split("/") for part in SKIP_PARTS):
        return False
    for pat in map(_fold, PROTECTED):
        if pat.endswith("/**"):
            if r == pat[:-3] or r.startswith(pat[:-2]):
                return True
        elif fnmatch.fnmatchcase(r, pat):
            return True
    return False


def is_protected(path: str | Path) -> bool:
    return _match_rel(_rel(path))


def protected_files() -> list[str]:
    """Every hashed protected file (machine-local hook files and the manifest itself excluded)."""
    out = []
    for p in sorted(ROOT.rglob("*")):
        if p.is_file() and is_protected(p) and p != MANIFEST:
            rel = p.relative_to(ROOT).as_posix()
            if rel not in MACHINE_LOCAL:
                out.append(rel)
    return out


def hook_file_problems() -> list[str]:
    """The machine-local hook files must exist and still call the protection and gate hooks."""
    out = []
    for rel in MACHINE_LOCAL:
        f = ROOT / rel
        if not f.exists():
            out.append(f"missing: {rel} (run python tools/as/setup.py --hooks)")
            continue
        try:
            text = json.dumps(json.loads(f.read_text(encoding="utf-8")))
        except ValueError:
            out.append(f"changed: {rel} is not valid JSON")
            continue
        lost = [m for m in HOOK_MARKERS if m not in text]
        if lost:
            out.append(f"changed: {rel} no longer calls {', '.join(lost)}")
    return out


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def verify() -> list[str]:
    """Problems: files missing, changed or added under protected patterns."""
    if not MANIFEST.exists():
        return ["tools/as/protected_manifest.json is missing"]
    want = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
    have = protected_files()
    problems = []
    for rel, digest in sorted(want.items()):
        p = ROOT / rel
        if not p.exists():
            problems.append(f"missing: {rel}")
        elif _sha(p) != digest:
            problems.append(f"changed: {rel}")
    for rel in have:
        if rel not in want:
            problems.append(f"added under a protected path: {rel}")
    return problems + hook_file_problems()


# ---------------------------------------------------------------------------------------------
# PreToolUse hook. Harness tool names are not fixed (DSH, Claude Code and others differ), so the
# hook is registered for every tool and decides from the call itself:
#   * a file tool WRITES when its name says so (write/edit/patch/delete/move/...) or when its input
#     carries content to write (content/new_string/edits/patch/...); READING a protected file is fine;
#   * a shell tool (input key command/cmd/script) is checked for writes to protected paths:
#     redirections, rm/mv/cp-into/tee/sed -i/perl -i, PowerShell Set-Content/Remove-Item/...,
#     git rm/mv/reset/stash, python -c writes; `cd` inside the command is followed;
#   * patch text (apply_patch "*** Update File:" or unified "+++ b/") names the files it changes.
# This is a guard rail, not the proof: `--verify` (run by gate.py and doctor.py) compares hashes.
# ---------------------------------------------------------------------------------------------
_WRITE_NAME = re.compile(r"write|edit|patch|creat|delet|remov|move|renam|replac|insert|append|save|"
                         r"updat|notebook|str_replace|apply|touch|mkdir|copy", re.I)
_DESTROY_NAME = re.compile(r"delet|remov|move|renam", re.I)
_CONTENT_KEYS = {"content", "contents", "new_string", "old_string", "new_str", "old_str", "text",
                 "edits", "patch", "diff", "replacement", "new_source", "data", "lines", "insert_text"}
_PATH_KEYS = ("file_path", "path", "filePath", "target_file", "notebook_path", "filename", "file",
              "destination", "dest", "target", "new_path", "old_path", "source", "src")
_CMD_KEYS = ("command", "cmd", "script", "commandLine", "command_line")
_PATCH_HEADER = re.compile(r"^(?:\*\*\* (?:Update|Add|Delete) File: |\*\*\* Move to: |\+\+\+ b/|--- a/)(\S.*?)\s*$",
                           re.M)
_DESTROY = {"rm", "rmdir", "rd", "del", "erase", "mv", "move", "ren", "rename", "tee", "truncate",
            "unlink", "touch", "chmod", "chown", "shred", "remove-item", "move-item", "rename-item",
            "set-content", "add-content", "out-file", "new-item", "clear-content", "sc", "ac", "ni",
            "ri", "mi", "rni"}
_COPY_INTO = {"cp", "copy", "xcopy", "robocopy", "copy-item", "cpi", "install", "ln", "rsync"}
_GIT_WRITE = {"rm", "mv", "reset", "clean", "stash", "apply", "am", "update-index", "commit"}
_PY_WRITE = ("'w'", '"w"', "'a'", '"a"', "'wb'", '"wb"', "write_text", "write_bytes", "unlink",
             "remove(", "rename(", "replace(", "rmtree", "shutil.", "os.system", "subprocess")


def _candidates(path: str, cwd: str | None) -> list[str]:
    """Repo-relative readings of `path`. A relative path is read against the working directory the
    call reports (or this process's), the repo root (a harness may run hooks from elsewhere) and
    as_engine/ (where most commands run); any reading that is protected blocks the call."""
    p = path.strip().strip("'\"").replace("\\", "/")
    if not p:
        return []
    if Path(p).is_absolute():
        return [_rel(p)]
    base = Path(cwd) if cwd else Path.cwd()
    return list(dict.fromkeys([_rel(base / p), _rel(ROOT / p), _rel(ROOT / "as_engine" / p)]))


def _is_file_hit(path: str, cwd: str | None) -> bool:
    return any(_match_rel(r) for r in _candidates(path, cwd))


def _is_tree_hit(path: str, cwd: str | None) -> bool:
    """Protected, or a directory that contains protected files (the repo root included)."""
    for rel in _candidates(path, cwd):
        if _match_rel(rel):
            return True
        r = _fold(rel).rstrip("/")
        if r in ("", ".", _fold(ROOT.as_posix())):
            return True
        if Path(rel).is_absolute():
            if _fold(ROOT.as_posix()).startswith(r + "/"):
                return True                               # a parent of the whole repo
        elif any(_fold(pat).startswith(r + "/") for pat in PROTECTED):
            return True
    return False


def _split_commands(command: str) -> list[list[str]]:
    out = []
    for part in re.split(r"\|\||&&|[;\n|&]", command):
        part = part.strip()
        if not part:
            continue
        try:
            windows_paths = os.name == "nt" or re.search(r"\\[A-Za-z_.]", part) is not None
            toks = shlex.split(part, posix=not windows_paths)
        except ValueError:
            toks = part.split()
        out.append([t.strip("'\"") for t in toks if t.strip("'\"")])
    return out


def _shell_hits(command: str, cwd: str | None) -> list[str]:
    hits: list[str] = []
    low = command.lower()
    if re.search(r"(?:protect|gate)\.py[\"']?\s+--write-(?:manifest|reference|rules)", low) or re.search(
            r"(?:^|[\s;&|(])(?:export\s+|set\s+\"?)?as_maintainer\s*=|\$env:as_maintainer\s*=", low):
        return ["tools/as/protected_manifest.json (only the human rewrites the manifest)"]
    for m in _PATCH_HEADER.finditer(command):
        if _is_file_hit(m.group(1), cwd):
            hits.append(m.group(1))
    here = cwd
    for toks in _split_commands(command):
        for i, t in enumerate(toks):                      # redirections: > file, >> file, 2>file
            m = re.match(r"^\d?>{1,2}(.*)$", t)
            if m:
                target = m.group(1) or (toks[i + 1] if i + 1 < len(toks) else "")
                if target and not target.startswith("&") and target.lower() not in ("/dev/null", "nul", "$null") \
                        and _is_file_hit(target, here):
                    hits.append(target)
        while toks and toks[0].lower() in ("sudo", "env", "command", "exec", "time", "nohup", "call"):
            toks = toks[1:]
        if not toks:
            continue
        prog = toks[0].replace("\\", "/").rsplit("/", 1)[-1].lower().removesuffix(".exe")
        args = [t for t in toks[1:] if not re.match(r"^\d?>", t)]
        paths = [a for a in args if not a.startswith("-") and (not a.startswith("/") or Path(a).is_absolute())]
        if prog in ("cd", "pushd", "set-location", "sl", "chdir") and paths:
            base = Path(here) if here else Path.cwd()
            here = str((base / paths[0].replace("\\", "/")) if not Path(paths[0]).is_absolute() else Path(paths[0]))
        elif prog in _DESTROY:
            hits += [a for a in paths if _is_tree_hit(a, here)]
        elif prog in _COPY_INTO and paths:
            if _is_tree_hit(paths[-1], here):
                hits.append(paths[-1])
        elif prog in ("sed", "gsed", "perl") and any(
                a.startswith("--in-place") or (a.startswith("-") and not a.startswith("--") and "i" in a[1:])
                for a in args):
            hits += [a for a in paths if _is_file_hit(a, here)]
        elif prog == "git" and paths and paths[0] in _GIT_WRITE:
            hits += [a for a in paths[1:] if _is_tree_hit(a, here)]
        elif prog in ("python", "python3", "py", "pythonw") and "-c" in args:
            k = args.index("-c")
            code = args[k + 1] if k + 1 < len(args) else ""
            if any(w in code for w in _PY_WRITE):
                for m in re.finditer(r"[\w./\\-]+", code):
                    if ("/" in m.group(0) or "\\" in m.group(0)) and _is_tree_hit(m.group(0), here):
                        hits.append(m.group(0))
    return hits


def check_tool_call(data: dict) -> list[str]:
    """The protected paths a tool call (Claude-Code hook JSON) would change; empty when it is fine."""
    tool = str(data.get("tool_name") or data.get("toolName") or data.get("name") or "")
    ti = data.get("tool_input")
    for k in ("toolInput", "input", "arguments", "args", "params", "parameters"):
        if ti is None:
            ti = data.get(k)
    if isinstance(ti, str):
        try:
            ti = json.loads(ti)
        except json.JSONDecodeError:
            ti = {"command": ti} if re.search(r"shell|bash|exec|run|terminal|cmd|powershell", tool, re.I) else {}
    if not isinstance(ti, dict):
        return []
    cwd = ti.get("cwd") if isinstance(ti.get("cwd"), str) else data.get("cwd") if isinstance(data.get("cwd"), str) else None
    hits: list[str] = []
    for k in _CMD_KEYS:
        if isinstance(ti.get(k), str):
            hits += _shell_hits(ti[k], cwd)
    viewing = str(ti.get("command", "")).lower() in ("view", "read", "list", "show", "cat")
    if not viewing and (_WRITE_NAME.search(tool) or any(k in ti for k in _CONTENT_KEYS)):
        tree = bool(_DESTROY_NAME.search(tool))
        for k in (_PATH_KEYS if tree else [k for k in _PATH_KEYS if k not in ("source", "src")]):
            v = ti.get(k)
            if isinstance(v, str) and (_is_tree_hit(v, cwd) if tree else _is_file_hit(v, cwd)):
                hits.append(v)
        for e in ti.get("edits") or []:
            if isinstance(e, dict):
                hits += [e[k] for k in _PATH_KEYS if isinstance(e.get(k), str) and _is_file_hit(e[k], cwd)]
        for k in ("patch", "diff", "input", "content"):
            if isinstance(ti.get(k), str) and (k in ("patch", "diff") or re.search(r"apply|patch", tool, re.I)):
                hits += [m.group(1) for m in _PATCH_HEADER.finditer(ti[k]) if _is_file_hit(m.group(1), cwd)]
    return sorted(set(hits))


def _hook() -> int:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(data, dict):
        return 0
    hits = check_tool_call(data)
    if hits:
        print("BLOCKED: this would change protected file(s): " + ", ".join(hits) +
              ". Protected files are never edited, moved or deleted (AGENTS.md rule 1). If you believe "
              "one is wrong, add an entry to docs/as/SPEC_ISSUES.md (skill as-spec-issue) and take the "
              "next task. To undo an accidental change: git restore <path>.", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd == "--list":
        print("patterns:", *PROTECTED, sep="\n  ")
        print("files:", *protected_files(), sep="\n  ")
        return 0
    if cmd == "--check":
        return 1 if is_protected(argv[1]) else 0
    if cmd == "--verify":
        problems = verify()
        for p in problems:
            print(p)
        print("protection: OK" if not problems else f"protection: {len(problems)} problem(s)")
        return 1 if problems else 0
    if cmd == "--hook":
        return _hook()
    if cmd == "--write-manifest":
        if os.environ.get("AS_MAINTAINER") != "1":
            print("refused: only the kit maintainer writes the manifest (AS_MAINTAINER=1)", file=sys.stderr)
            return 1
        files = {rel: _sha(ROOT / rel) for rel in protected_files()}
        MANIFEST.write_text(json.dumps({"files": files}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"manifest: {len(files)} files")
        return 0
    print(f"unknown option {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
