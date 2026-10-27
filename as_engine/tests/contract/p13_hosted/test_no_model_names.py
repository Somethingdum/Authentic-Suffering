"""No model is named in the engine's code (P13, D-299; the host's own rule: what a model can do comes from
its profile and the host's listing, never from its name). Rule HOST-04 (as_engine/host/work.py: the kind of
work, never a model).

The owner's two models are configuration (contracts/default_lanes.json). Comments and docstrings may name a
model, to say why something is there; code, string literals and prompt templates may not. Tests are not code
here, as in the host's own check.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

import pytest

import as_engine

pytestmark = pytest.mark.phase(13)

NAMES = re.compile(r"\b(qwen|gemma|mistral|mixtral|deepseek|phi-?\d|llama-?\d|gpt-oss|granite|devstral|codestral|glm-?\d|"
                   r"smollm|olmo|nemotron|starcoder|codellama|hermes-?\d|boulesis)", re.I)
SRC = Path(as_engine.__file__).parent


def _docstring_lines(tree: ast.AST) -> set[int]:
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                lines |= set(range(body[0].lineno, body[0].end_lineno + 1))
    return lines


def _code(text: str) -> str:
    """The Python code without its comments and docstrings."""
    doc = _docstring_lines(ast.parse(text))
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.COMMENT:
            continue
        if tok.type == tokenize.STRING and tok.start[0] in doc:
            continue
        out.append(tok.string)
    return " ".join(out)


def test_no_python_file_names_a_model_outside_its_comments():
    found = []
    for py in sorted(SRC.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        m = NAMES.search(_code(py.read_text(encoding="utf-8")))
        if m:
            found.append(f"{py.relative_to(SRC).as_posix()}: {m.group(0)}")
    assert found == []


def test_no_prompt_names_a_model():
    found = [f"{j.name}: {m.group(0)}" for j in sorted(SRC.rglob("*.j2"))
             if (m := NAMES.search(j.read_text(encoding="utf-8")))]
    assert found == []


def test_the_owners_models_are_configuration():
    from as_engine.contracts.settings import default_lanes
    lanes = default_lanes()
    assert all(c.model for c in lanes.values()), "the defaults still name the owner's two models — as data"
    assert (SRC / "contracts" / "default_lanes.json").exists()
