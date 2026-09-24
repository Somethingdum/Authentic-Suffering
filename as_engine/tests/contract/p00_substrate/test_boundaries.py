"""Import and identifier boundaries (P0; must stay green for every later phase).
Rules: BOUND-01, BOUND-02 (SKULL-02), BOUND-03, SYM-01, DET-11. docs/as/02_ARCHITECTURE.md §5."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.phase(0)

PKG = Path(__file__).resolve().parents[3] / "src" / "as_engine"


def _modules():
    for path in sorted(PKG.rglob("*.py")):
        rel = path.relative_to(PKG.parent).with_suffix("")
        name = ".".join(rel.parts)
        if name.endswith(".__init__"):
            name = name[: -len(".__init__")]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        tree._is_pkg = path.name == "__init__.py"  # type: ignore[attr-defined]
        yield name, path, tree


def _imports(mod_name: str, tree: ast.AST) -> set[str]:
    """Absolute dotted names imported by a module (relative imports resolved)."""
    out: set[str] = set()
    pkg_parts = mod_name.split(".")
    if getattr(tree, "_is_pkg", False):
        pkg_parts = pkg_parts + ["__init__"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # a module's own package is pkg_parts[:-1]; level 1 = that package
                base = pkg_parts[: len(pkg_parts) - node.level]
                prefix = ".".join(base + ([node.module] if node.module else []))
            else:
                prefix = node.module or ""
            out.add(prefix)
            for a in node.names:
                out.add(f"{prefix}.{a.name}")
    return out


def _under(name: str, *prefixes: str) -> bool:
    return any(name == p or name.startswith(p + ".") for p in prefixes)


ALL = list(_modules())


def test_no_talemate_imports():
    """BOUND-01: nothing under as_engine imports talemate."""
    bad = [(m, i) for m, _, t in ALL for i in _imports(m, t) if _under(i, "talemate")]
    assert not bad, f"talemate imported: {bad}"


TRUTH_ALLOWED = ("as_engine.kernel", "as_engine.mind.perception", "as_engine.action", "as_engine.world",
                 "as_engine.society", "as_engine.audit", "as_engine.cheats", "as_engine.turn",
                 "as_engine.service.death", "as_engine.testing")
TRUTH_FORBIDDEN = ("as_engine.mind.packet", "as_engine.mind.memory", "as_engine.mind.retrieval", "as_engine.mind.cues",
                   "as_engine.narration", "as_engine.service.view")


def test_truth_import_boundary():
    """BOUND-02 / SKULL-02: kernel.truth is imported only by its allow-list, never by the packet
    builder, memory, retrieval, narration or the view model."""
    bad = []
    for m, _, t in ALL:
        if any(_under(i, "as_engine.kernel.truth") for i in _imports(m, t)):
            if _under(m, *TRUTH_FORBIDDEN) or not _under(m, *TRUTH_ALLOWED):
                bad.append(m)
    assert not bad, f"kernel.truth imported by: {bad}"


LOWER = ("as_engine.physical", "as_engine.sense", "as_engine.action", "as_engine.mind")
HIGHER = ("as_engine.service", "as_engine.turn")


def test_lower_bands_never_import_higher():
    """BOUND-03: physical/sense/action/mind never import service or turn."""
    bad = [(m, i) for m, _, t in ALL if _under(m, *LOWER) for i in _imports(m, t) if _under(i, *HIGHER)]
    assert not bad, f"band violation: {bad}"


SIM = ("as_engine.physical", "as_engine.sense", "as_engine.mind", "as_engine.action",
       "as_engine.society", "as_engine.world")
FORBIDDEN_IDENTS = {"controller", "is_pc", "pc_id", "player"}


def test_simulation_modules_do_not_know_who_is_the_player():
    """SYM-01: simulation modules never use the identifiers controller / is_pc / pc_id / player
    (AST names, attributes, arguments, function and class names — not strings or comments). The
    single exception is the function mind.actor.controller, which only turn.pipeline may call."""
    bad = []
    for m, path, t in ALL:
        if not _under(m, *SIM):
            continue
        for node in ast.walk(t):
            names = []
            if isinstance(node, ast.Name):
                names.append(node.id)
            elif isinstance(node, ast.Attribute):
                names.append(node.attr)
            elif isinstance(node, ast.arg):
                names.append(node.arg)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not (m == "as_engine.mind.actor" and node.name == "controller"):
                    names.append(node.name)
            elif isinstance(node, ast.keyword) and node.arg:
                names.append(node.arg)
            for n in names:
                if n in FORBIDDEN_IDENTS:
                    bad.append(f"{m}:{getattr(node, 'lineno', '?')} {n}")
    assert not bad, "player-aware identifiers in simulation code:\n" + "\n".join(bad)


def test_callers_of_actor_controller_are_only_the_pipeline():
    """SYM-01: only as_engine.turn.* (and mind.actor itself) reference mind.actor.controller."""
    bad = []
    for m, _, t in ALL:
        if _under(m, "as_engine.turn") or m == "as_engine.mind.actor":
            continue
        for node in ast.walk(t):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("mind.actor"):
                if any(a.name == "controller" for a in node.names):
                    bad.append(m)
            if isinstance(node, ast.Attribute) and node.attr == "controller" and isinstance(node.value, ast.Name) \
                    and node.value.id in ("actor", "mind_actor"):
                bad.append(m)
    assert not bad, f"mind.actor.controller used outside turn.*: {bad}"


BANNED_MODULES = {"random", "secrets", "uuid", "time"}
WALLCLOCK_OK = ("as_engine.lanes", "as_engine.kernel.store", "as_engine.service.runs")


def test_single_entropy_door():
    """DET-11: random / secrets / uuid / time are never imported under as_engine (lanes/ may use
    time for HTTP timing); os.urandom and datetime.now/utcnow/today are never called outside
    lanes/, kernel.store (created_at_real) and service.runs (save timestamps shown to the user)."""
    bad = []
    for m, _, t in ALL:
        for node in ast.walk(t):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[0] in BANNED_MODULES and not _under(m, "as_engine.lanes"):
                        bad.append(f"{m} imports {a.name}")
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                if node.module.split(".")[0] in BANNED_MODULES and not _under(m, "as_engine.lanes"):
                    bad.append(f"{m} imports from {node.module}")
            elif isinstance(node, ast.Attribute):
                if node.attr == "urandom":
                    bad.append(f"{m} uses os.urandom")
                if node.attr in ("now", "utcnow", "today") and isinstance(node.value, (ast.Name, ast.Attribute)):
                    base = node.value.id if isinstance(node.value, ast.Name) else node.value.attr
                    if base in ("datetime", "date") and not _under(m, *WALLCLOCK_OK):
                        bad.append(f"{m} reads the wall clock ({base}.{node.attr})")
    assert not bad, "\n".join(bad)


def test_pytest_is_never_imported_by_engine_code():
    """Anti-cheating (13 §1 rule 2): src/ never imports pytest or the tests package."""
    bad = [m for m, _, t in ALL for i in _imports(m, t) if _under(i, "pytest") or _under(i, "tests")]
    assert not bad, f"engine imports test machinery: {bad}"
