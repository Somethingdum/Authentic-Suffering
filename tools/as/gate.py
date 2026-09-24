#!/usr/bin/env python3
"""The phase gate for the Authentic Suffering build (docs/as/13_BUILD_ORDER.md §1, §3).

  python tools/as/gate.py --phase N --quick   phase N's contract tests only; prints the first failures
  python tools/as/gate.py --phase N           the full gate: protection, P0..PN tests, anti-cheat scan;
                                              on success writes the evidence row in docs/as/PROGRESS.md
  python tools/as/gate.py --scan              only the anti-cheat / determinism scan of as_engine/src
  python tools/as/gate.py --rules             rule ids named in src docstrings but in no contract test docstring
  python tools/as/gate.py --upstream-diff     Talemate upstream files changed outside 02_ARCHITECTURE §4.1
  python tools/as/gate.py --docstrings        contract docstrings/signatures that differ from the kit's
                                              snapshot (docs/as/reference/docstrings_v1.json)
  AS_MAINTAINER=1 python tools/as/gate.py --write-reference   (human/kit maintainer) snapshot docstrings
  AS_MAINTAINER=1 python tools/as/gate.py --write-rules       (human/kit maintainer) regenerate RULES.md
  python tools/as/gate.py --stop-check        end-of-turn check (Stop hook): protection intact and the
                                              'Next task' line filled; exit 2 asks the agent to fix it
  python tools/as/gate.py --brief             session-start context (SessionStart hook): the Current block
                                              of PROGRESS.md and the protection status, as hook JSON

Exit code 0 = pass. Uses only the standard library plus pytest from the active environment.
"""

from __future__ import annotations

import ast
import datetime as _dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

for _stream in (sys.stdout, sys.stderr):          # hook runners read pipes as UTF-8 (Windows default: cp1252)
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
ENGINE = ROOT / "as_engine"
SRC = ENGINE / "src" / "as_engine"
CONTRACT = ENGINE / "tests" / "contract"
PROGRESS = ROOT / "docs" / "as" / "PROGRESS.md"
sys.path.insert(0, str(ROOT / "tools" / "as"))
import protect  # noqa: E402

PHASE_NAMES = {0: "P0 Substrate", 1: "P1 Lane harness", 2: "P2 Bodies, space, objects, content",
               3: "P3 Perception", 4: "P4 One Actor", 5: "P5 Many Actors", 6: "P6 Memory",
               7: "P7 The Slice", 8: "P8 Play UI", 9: "P9 Society", 10: "P10 Wide world",
               11: "P11 Audits", 12: "P12 Surfaces"}
UPSTREAM_ALLOWED = {
    "src/talemate/server/websocket_server.py", "talemate_frontend/src/App.vue",
    "talemate_frontend/package.json", "talemate_frontend/pnpm-lock.yaml",
    "talemate_frontend/vite.config.mjs", "install.bat", "install.sh", "update.bat", "update.sh",
    ".gitignore",
}
FIXTURE_NAMES = ("metal_fence", "three_rooms_gunshot", "crowd_accusation", "request_firewall",
                 "empty_gun", "pump_settlement", "two_skills")
ENTROPY = {"random", "secrets", "uuid"}
ENTROPY_CALLS = ("time.time", "time.monotonic", "time.perf_counter", "datetime.now", "datetime.utcnow",
                 "os.urandom", "date.today")


def phase_dirs(upto: int, only: int | None = None) -> list[Path]:
    out = []
    for d in sorted(CONTRACT.glob("p[0-9][0-9]_*")):
        n = int(d.name[1:3])
        if (only is None and n <= upto) or n == only:
            out.append(d)
    return out


def run_pytest(dirs: list[Path], extra: list[str]) -> tuple[int, str]:
    cmd = [sys.executable, "-m", "pytest", *[str(d.relative_to(ENGINE)) for d in dirs], "-q", "-p", "no:randomly",
           "--tb=line", "-rfE", *extra]
    proc = subprocess.run(cmd, cwd=ENGINE, capture_output=True, text=True, env={**os.environ, "COLUMNS": "240"})
    return proc.returncode, proc.stdout + proc.stderr


def _test_rules(nodeid: str) -> list[str]:
    """Rule ids named by the failing test's own docstring, else by its module docstring."""
    path, _, name = nodeid.partition("::")
    name = name.split("[", 1)[0].split("::")[-1]
    try:
        tree = ast.parse((ENGINE / path).read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            ids = _ids_in(ast.get_docstring(node) or "")
            if ids:
                return ids[:4]
    return _ids_in(ast.get_docstring(tree) or "")[:4]


def summarise_failures(output: str, limit: int = 12) -> list[str]:
    """One line per failure: test id, its rule ids, where it failed (source file:line when the
    failure was raised inside as_engine/src) and the error."""
    body = output
    a, b = output.find("= FAILURES ="), output.find("short test summary info")
    if a >= 0 and b > a:
        body = output[a:b]
    tb = [(m.group(1), m.group(2)) for m in re.finditer(r"^(\S+\.py:\d+): (\w.*)$", body, re.M)] if a >= 0 else []
    lines = []
    for i, m in enumerate(re.finditer(r"^(FAILED|ERROR) (\S+)(?: - (.*))?$", output, re.M)):
        kind, nodeid, msg = m.group(1), m.group(2), (m.group(3) or "").strip()
        rules = ", ".join(_test_rules(nodeid)) or "—"
        loc, err = tb[i] if i < len(tb) and kind == "FAILED" else ("", "")
        msg = err or msg
        if loc:
            loc = loc.replace("\\", "/")
            k = loc.find("src/as_engine/")
            loc = loc[k + 4:] if k >= 0 else loc.rsplit("/tests/", 1)[-1]
        lines.append(f"{'ERROR ' if kind == 'ERROR' else ''}{nodeid}\n      rules: {rules}"
                     + (f" · at {loc}" if loc else "") + f"\n      {msg[:200]}")
    return lines[:limit]


def scan_src() -> list[str]:
    """Anti-cheat and determinism scan (13 §1 rule 2, DET-11)."""
    problems = []
    for py in sorted(SRC.rglob("*.py")):
        rel = py.relative_to(ROOT).as_posix()
        if "__pycache__" in rel or "/testing/" in rel:
            continue
        text = py.read_text(encoding="utf-8")
        for name in FIXTURE_NAMES:
            if re.search(rf"['\"]{name}['\"]", text):
                problems.append(f"{rel}: fixture name '{name}' in source")
        for m in re.finditer(r"['\"](act|itm|plc|anc|prt|evt|wnd|tsk)_\d{6}['\"]", text):
            problems.append(f"{rel}: literal id {m.group(0)} in source")
        try:
            tree = ast.parse(text)
        except SyntaxError as e:
            problems.append(f"{rel}: syntax error {e}")
            continue
        in_lanes = "/lanes/" in rel
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    top = a.name.split(".")[0]
                    if top == "pytest":
                        problems.append(f"{rel}: imports pytest")
                    if top in ENTROPY:
                        problems.append(f"{rel}: imports {top} (entropy goes through kernel.rng)")
                    if top in ("time", "datetime") and not in_lanes:
                        problems.append(f"{rel}: imports {top} (the clock is kernel.clock)")
            elif isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                if top == "pytest":
                    problems.append(f"{rel}: imports pytest")
                if top in ENTROPY:
                    problems.append(f"{rel}: imports from {top}")
                if top in ("time", "datetime") and not in_lanes:
                    problems.append(f"{rel}: imports from {top} (the clock is kernel.clock)")
    return problems


RULE_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,11}-\d{2,3})\b")


def _docstrings(paths: list[Path]) -> str:
    out = []
    for py in paths:
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                d = ast.get_docstring(node)
                if d:
                    out.append(d)
    return "\n".join(out)


def rules_report() -> tuple[set[str], set[str]]:
    """Rule ids named by src docstrings, and by contract test files (ranges expanded)."""
    src_ids = set(_ids_in(_docstrings(sorted(SRC.rglob("*.py")))))
    test_ids: set[str] = set()
    for py in sorted(CONTRACT.rglob("*.py")):
        test_ids |= set(_ids_in(py.read_text(encoding="utf-8")))
    return src_ids, test_ids


REFERENCE = ROOT / "docs" / "as" / "reference" / "docstrings_v1.json"
RULES_MD = ROOT / "docs" / "as" / "RULES.md"


def collect_docstrings(src_root: Path = SRC) -> dict[str, dict[str, dict[str, str]]]:
    """{module: {qualname or '<module>': {'doc': ..., 'sig': ...}}} for every docstring in src.
    Only documented names are the contract; nested functions are not walked."""
    out: dict[str, dict[str, dict[str, str]]] = {}
    for py in sorted(src_root.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        mod = ".".join(("as_engine", *py.relative_to(src_root).with_suffix("").parts))
        mod = mod.removesuffix(".__init__")
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        entries: dict[str, dict[str, str]] = {}
        d = ast.get_docstring(tree, clean=True)
        if d:
            entries["<module>"] = {"doc": d, "sig": ""}

        def walk(body: list, prefix: str) -> None:
            for node in body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    doc = ast.get_docstring(node, clean=True)
                    if doc:
                        sig = "(" + ast.unparse(node.args) + ")" + (" -> " + ast.unparse(node.returns) if node.returns else "")
                        entries[prefix + node.name] = {"doc": doc, "sig": sig}
                elif isinstance(node, ast.ClassDef):
                    doc = ast.get_docstring(node, clean=True)
                    if doc:
                        entries[prefix + node.name] = {"doc": doc, "sig": "(" + ", ".join(ast.unparse(b) for b in node.bases) + ")"}
                    walk(node.body, prefix + node.name + ".")

        walk(tree.body, "")
        if entries:
            out[mod] = entries
    return out


def docstring_drift() -> list[str]:
    """Contract drift: a documented name whose docstring or signature changed, or that disappeared."""
    if not REFERENCE.exists():
        return [f"{REFERENCE.relative_to(ROOT).as_posix()} is missing"]
    want = json.loads(REFERENCE.read_text(encoding="utf-8"))
    have = collect_docstrings()
    problems = []
    for mod, names in sorted(want.items()):
        for q, ref in sorted(names.items()):
            cur = have.get(mod, {}).get(q)
            where = f"{mod}::{q}" if q != "<module>" else f"{mod} (module docstring)"
            if cur is None:
                problems.append(f"{where}: documented name is gone (or its docstring was removed)")
            elif cur["doc"] != ref["doc"]:
                problems.append(f"{where}: docstring changed — the docstring is the contract; restore it")
            elif cur["sig"] != ref["sig"]:
                problems.append(f"{where}: signature changed {ref['sig']} -> {cur['sig']}")
    return problems


_NOT_RULES = re.compile(r"^(?:SI|D|O)-\d+$")
_ANY_ID = re.compile(r"(?<![\w-])([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{2,3}[a-z]?)(?![\w-])")


def _clip(text: str, n: int = 220) -> str:
    text = re.sub(r"\s+", " ", text.replace("|", "/")).strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


_RANGE = re.compile(r"(?<![\w-])([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*)-(\d{2,3})\s*(?:\.\.|–|—)\s*(?:\1-)?(\d{2,3})(?![\w-])")


def _ids_in(text: str) -> list[str]:
    """Rule ids in `text`, with ranges ("SKULL-01..06", "AUD-01–08") expanded."""
    out = [m.group(1) for m in _ANY_ID.finditer(text)]
    for m in _RANGE.finditer(text):
        fam, a, b = m.group(1), int(m.group(2)), int(m.group(3))
        width = len(m.group(2))
        if a < b <= a + 40:
            out += [f"{fam}-{n:0{width}d}" for n in range(a + 1, b)]
    return [i for i in dict.fromkeys(out) if not _NOT_RULES.match(i)]


def build_rules_md() -> str:
    """RULES.md: every rule id the kit mentions, with its best statement and where it lives.
    Statement priority: a doc table row whose first cell is the id > a line that starts with the id
    (doc or docstring) > the first src docstring mention (docstrings are the contract) > the first
    doc mention."""
    best: dict[str, tuple[int, str, str]] = {}      # id -> (score, statement, where)

    def offer(rid: str, score: int, stmt: str, where: str) -> None:
        if rid not in best or score < best[rid][0]:
            best[rid] = (score, _clip(stmt), where)

    def starts_with(line: str, rid: str) -> bool:
        return re.match(r"^[\s\-*#`>]*\**" + re.escape(rid) + r"\b", line) is not None

    skip_docs = {"RULES.md", "PROGRESS.md", "SPEC_ISSUES.md", "CHANGELOG_AS.md"}
    for md in sorted((ROOT / "docs" / "as").glob("*.md")):
        if md.name in skip_docs:
            continue
        section = ""
        for line in md.read_text(encoding="utf-8").splitlines():
            h = re.match(r"^#{2,3}\s+(\d+(?:\.\d+)*)\.?\s", line)
            if h:
                section = " §" + h.group(1)
            where = md.stem + section
            cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.lstrip().startswith("|") else []
            head = cells[0].strip("*` ") if cells else ""
            if cells and len(cells) > 1 and _ANY_ID.fullmatch(head) and not _NOT_RULES.match(head):
                offer(head, 0, cells[1], where)
            for rid in _ids_in(line):
                offer(rid, 1 if starts_with(line, rid) else 3, line.lstrip("-*# "), where)
    enforced: dict[str, set[str]] = {}
    for py in sorted(SRC.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        rel = py.relative_to(SRC.parent).as_posix()
        lines = _docstrings([py]).splitlines()
        for i, line in enumerate(lines):
            for rid in _ids_in(line):
                enforced.setdefault(rid, set()).add(rel)
                if starts_with(line, rid):
                    full = [line]
                    for nxt in lines[i + 1:]:          # the rule's indented continuation lines
                        if not nxt.startswith("  ") or _ANY_ID.match(nxt.strip()):
                            break
                        full.append(nxt)
                    offer(rid, 1, " ".join(full), rel)
                else:
                    offer(rid, 2, line, rel)
    tested: dict[str, set[str]] = {}
    for py in sorted(CONTRACT.rglob("*.py")):
        rel = py.relative_to(ENGINE / "tests").as_posix()
        for rid in _ids_in(py.read_text(encoding="utf-8")):
            tested.setdefault(rid, set()).add(rel)
    import yaml  # the engine's own dependency; only the maintainer's --write-rules gets here

    content: dict[str, set[str]] = {}
    for y in sorted((ROOT / "as_content").rglob("*.yaml")):
        text = y.read_text(encoding="utf-8")
        for rid in _ids_in(text):
            content.setdefault(rid, set()).add(y.relative_to(ROOT).as_posix())
            offer(rid, 4, "(content rule id)", y.relative_to(ROOT).as_posix())
        try:                                               # a content record's own description defines it
            records = yaml.safe_load(text)
        except yaml.YAMLError:
            records = None
        for rec in records if isinstance(records, list) else [records]:
            if isinstance(rec, dict) and isinstance(rec.get("id"), str) and isinstance(rec.get("description"), str) \
                    and _ANY_ID.fullmatch(rec["id"]) and not _NOT_RULES.match(rec["id"]):
                offer(rec["id"], 0, rec["description"], y.relative_to(ROOT).as_posix())
    ids = sorted(set(best) | set(tested), key=lambda i: (i.rsplit("-", 1)[0], i))
    own = {i for i in ids if best.get(i, (9,))[0] <= 1}
    lines = ["# RULES — rule id registry", "",
             "Generated from the kit by `AS_MAINTAINER=1 python tools/as/gate.py --write-rules`; do not edit by hand.",
             "Use it to find a rule named by a failing test or a validator. *Statement* is the rule's defining",
             "table row when one exists, else a line that starts with the id, else its first mention in a",
             "source docstring, else in a doc (a range",
             "such as `SKULL-01..06` counts as naming every id in it). *Stated in* is the doc (and section) or",
             "module holding that text. *Enforced in* lists the source modules whose docstrings name the id",
             "(and content files for content rules); *Tested by* the contract test files that name it. An id",
             "with no test yet belongs to a later phase or to the live/sim suites.", "",
             "A statement in *italics* is context, not a definition: the id is only named inside a range or a",
             "sentence there, and its behaviour is specified by the module docstring or doc section named under",
             "*Stated in* (read that; the contract tests pin it).", "",
             f"{len(ids)} ids; {len(own)} with their own statement, {len(ids) - len(own)} named only in context.", ""]
    family = None
    for rid in ids:
        fam = rid.rsplit("-", 1)[0]
        if fam != family:
            family = fam
            lines += ["", f"## {fam}", "", "| Id | Statement | Stated in | Enforced in | Tested by |",
                      "|---|---|---|---|---|"]
        score, stmt, where = best.get(rid, (9, "(named only by tests)", ""))
        if score > 1 and score != 9:
            stmt = "*" + stmt.replace("*", "") + "*"
        enf = [f"`{e}`" for e in sorted(enforced.get(rid, ()))] + [f"`{c}`" for c in sorted(content.get(rid, ()))]
        tst = [f"`{t}`" for t in sorted(tested.get(rid, ()))]
        lines.append(f"| {rid} | {stmt} | {where} | {', '.join(enf) or '—'} | {', '.join(tst) or '—'} |")
    return "\n".join(lines).rstrip() + "\n"


def upstream_diff() -> list[str]:
    try:
        out = subprocess.run(["git", "diff", "--name-only", "0.39.0"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ["git tag 0.39.0 not found: run this inside the Talemate fork"]
    bad = []
    for f in out.split():
        if f.startswith(("as_engine/", "as_content/", "docs/as/", "tools/as/", ".dsh/", "talemate_frontend/src/play/")) \
                or f in ("AGENTS.md", "README_FIRST.md", "as_config.example.yaml", "src/talemate/server/as_game_plugin.py",
                         "tests/test_as_game_plugin.py"):
            continue
        if f not in UPSTREAM_ALLOWED:
            bad.append(f)
    return bad


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "(not a git repo)"


def write_evidence(n: int, command: str, artifact: str) -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    name = PHASE_NAMES[n]
    today = _dt.date.today().isoformat()
    row = f"| {name} | green | {git_commit()} | `{command}` | tools/as/gate.py --phase {n} | {artifact} | {today} |"
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(f"| {name} |"):
            lines[i] = row
            break
    PROGRESS.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run(cmd: list[str] | str, cwd: Path) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=isinstance(cmd, str))
    except OSError as e:
        return 127, str(e)
    return proc.returncode, proc.stdout + proc.stderr


def _last_line(out: str) -> str:
    lines = [ln for ln in out.strip().splitlines() if ln.strip()]
    return lines[-1][:200] if lines else "(no output)"


def later_phase_steps(n: int) -> list[tuple[str, bool, str]]:
    """Gate steps that start at later phases (12 §1, 13 §3): the sim soak from P7; from P8 the
    Talemate plugin test, the Play UI tests and the upstream-diff check."""
    steps: list[tuple[str, bool, str]] = []
    if n >= 7:
        sim = ENGINE / "tests" / "sim"
        if not any(sim.glob("test_*.py")):
            steps.append(("5 sim soak", False, "as_engine/tests/sim has no tests — the kit is incomplete; tell the human"))
        else:
            code, out = _run([sys.executable, "-m", "pytest", "tests/sim", "-q", "-m", "slow", "-p", "no:randomly"], ENGINE)
            steps.append(("5 sim soak", code == 0, _last_line(out)))
    if n >= 8:
        plugin = ROOT / "tests" / "test_as_game_plugin.py"
        code, out = _run([sys.executable, "-m", "pytest", str(plugin.relative_to(ROOT)), "-q", "-o", "addopts="], ROOT)
        steps.append(("6 Talemate plugin test", code == 0, _last_line(out)))
        code, out = _run("corepack pnpm run test:play", ROOT / "talemate_frontend")
        steps.append(("7 Play UI tests (vitest)", code == 0, _last_line(out)))
        bad = upstream_diff()
        steps.append(("8 upstream changes only as listed in 02 §4.1", not bad, "; ".join(bad[:8])))
    return steps


def gate(n: int, quick: bool) -> int:
    if quick:
        dirs = phase_dirs(n, only=n)
        if not dirs:
            print(f"no contract tests for P{n} yet")
            return 1
        code, out = run_pytest(dirs, [])
        print(out.strip().splitlines()[-1] if out.strip() else "(no output)")
        for line in summarise_failures(out):
            print("  " + line)
        return code
    ok = True
    problems = protect.verify()
    print("1 protection:", "OK" if not problems else f"{len(problems)} problem(s)")
    for p in problems[:20]:
        print("   " + p)
    ok &= not problems
    dirs = phase_dirs(n)
    code, out = run_pytest(dirs, [])
    print("2 contract tests P0..P%d:" % n, out.strip().splitlines()[-1] if out.strip() else "(no output)")
    for line in summarise_failures(out):
        print("   " + line)
    ok &= code == 0
    scan = scan_src()
    print("3 source scan:", "OK" if not scan else f"{len(scan)} finding(s)")
    for s in scan[:30]:
        print("   " + s)
    ok &= not scan
    drift = docstring_drift()
    print("4 contract docstrings:", "OK" if not drift else f"{len(drift)} changed")
    for s in drift[:30]:
        print("   " + s)
    ok &= not drift
    for label, passed, detail in later_phase_steps(n):
        print(f"{label}:", "OK" if passed else "RED", detail)
        ok &= passed
    if not ok:
        print(f"GATE P{n}: RED — nothing written. Wording until green: 'observed implementation, not proven gate'.")
        return 1
    runs = ROOT / "as_runs" / "gate"
    runs.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    art = runs / f"p{n:02d}_{stamp}.txt"
    art.write_text(out, encoding="utf-8")
    write_evidence(n, f"python tools/as/gate.py --phase {n}", art.relative_to(ROOT).as_posix())
    print(f"GATE P{n}: GREEN — evidence written to docs/as/PROGRESS.md ({art.relative_to(ROOT).as_posix()})")
    return 0


def _hook_input() -> dict:
    """The hook JSON on stdin when run as a hook; {} when run by hand."""
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


_STOP_STATE = Path(tempfile.gettempdir()) / f"as_stop_check_{hashlib.sha1(str(ROOT).encode()).hexdigest()[:10]}.json"
STOP_RETRIES = 2            # blocks in a row before the turn is allowed to end anyway
STOP_WINDOW_S = 900         # ... counted within this many seconds


def stop_check() -> int:
    """Stop hook. Exit 2 (with the reason on stderr) makes the agent take another step to fix it.
    Never blocks more than STOP_RETRIES times in a row: a problem the agent cannot fix (e.g. a
    protected file it changed and cannot restore) is left for the human instead of looping."""
    _hook_input()
    problems = protect.verify()
    text = PROGRESS.read_text(encoding="utf-8") if PROGRESS.exists() else ""
    m = re.search(r"^- Next task:[ \t]*(\S.*)$", text, re.M)
    if not m:
        problems.append("docs/as/PROGRESS.md: the '- Next task:' line is empty — write the exact next "
                        "function (module::function) before you stop")
    now = _dt.datetime.now().timestamp()
    try:
        state = json.loads(_STOP_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {"blocks": []}
    recent = [t for t in state.get("blocks", []) if now - t < STOP_WINDOW_S]
    if not problems:
        _STOP_STATE.unlink(missing_ok=True)
        return 0
    if len(recent) >= STOP_RETRIES:        # (stop_hook_active from the harness is not needed: we count)
        _STOP_STATE.unlink(missing_ok=True)
        print("stop-check: problems remain after %d attempts; stopping so the human can look: %s"
              % (len(recent), "; ".join(problems[:5])))
        return 0
    recent.append(now)
    try:
        _STOP_STATE.write_text(json.dumps({"blocks": recent}), encoding="utf-8")
    except OSError:
        pass
    print("Before you stop, fix:", file=sys.stderr)
    for p in problems[:10]:
        print("  - " + p, file=sys.stderr)
    if any(p.startswith(("changed:", "missing:", "added under")) for p in problems):
        print("  Protected files must match the manifest: git restore <path> (or delete a file you added "
              "under a protected folder). If you cannot, write what happened under Stuck in "
              "docs/as/PROGRESS.md.", file=sys.stderr)
    return 2


def brief() -> int:
    """SessionStart hook: the Current block of PROGRESS.md and the protection status as context."""
    _hook_input()
    text = PROGRESS.read_text(encoding="utf-8") if PROGRESS.exists() else ""
    m = re.search(r"^## Current\s*\n(.*?)(?=^## )", text, re.M | re.S)
    current = (m.group(1).strip() if m else "(docs/as/PROGRESS.md has no Current block)")
    green = [ln.split("|")[1].strip() for ln in text.splitlines() if re.match(r"^\| P\d+ .*\| green \|", ln)]
    problems = protect.verify()
    lines = ["Authentic Suffering build — session brief (tools/as/gate.py --brief)", current,
             "Phases green: " + (", ".join(green) if green else "none yet"),
             "Protection: OK" if not problems else "Protection: %d problem(s) — run python tools/as/doctor.py first"
             % len(problems),
             "Start with AGENTS.md §1 step 4: python tools/as/gate.py --phase N --quick"]
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                             "additionalContext": "\n".join(lines)}}))
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "--phase":
        n = int(argv[1])
        return gate(n, quick="--quick" in argv)
    if argv[0] == "--scan":
        s = scan_src()
        print(*s, sep="\n") if s else print("scan: OK")
        return 1 if s else 0
    if argv[0] == "--rules":
        src_ids, test_ids = rules_report()
        listed = set(re.findall(r"^\| ([A-Z][A-Z0-9-]*-\d{2,3}[a-z]?) \|", RULES_MD.read_text(encoding="utf-8"), re.M)) \
            if RULES_MD.exists() else set()
        print(f"rule ids in src docstrings: {len(src_ids)}; named by contract tests: {len(src_ids & test_ids)}; "
              f"in docs/as/RULES.md: {len(listed)}")
        new = sorted((src_ids | test_ids) - listed - {i for i in src_ids | test_ids if _NOT_RULES.match(i)})
        for r in new:
            print("  not in RULES.md (a docstring or test names an id the registry does not know):", r)
        return 1 if new else 0
    if argv[0] == "--upstream-diff":
        bad = upstream_diff()
        print(*bad, sep="\n") if bad else print("upstream: OK")
        return 1 if bad else 0
    if argv[0] == "--stop-check":
        return stop_check()
    if argv[0] == "--brief":
        return brief()
    if argv[0] == "--docstrings":
        d = docstring_drift()
        print(*d, sep="\n") if d else print("docstrings: OK")
        return 1 if d else 0
    if argv[0] in ("--write-reference", "--write-rules"):
        if os.environ.get("AS_MAINTAINER") != "1":
            print("refused: only the human / kit maintainer regenerates protected references (AS_MAINTAINER=1)",
                  file=sys.stderr)
            return 1
        if argv[0] == "--write-reference":
            REFERENCE.parent.mkdir(parents=True, exist_ok=True)
            data = collect_docstrings()
            REFERENCE.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"reference: {sum(len(v) for v in data.values())} docstrings in {len(data)} modules")
        else:
            RULES_MD.write_text(build_rules_md(), encoding="utf-8")
            print(f"wrote {RULES_MD.relative_to(ROOT).as_posix()}")
        print("now refresh the hashes: AS_MAINTAINER=1 python tools/as/protect.py --write-manifest")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
