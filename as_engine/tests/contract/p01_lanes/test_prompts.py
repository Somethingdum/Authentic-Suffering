"""Prompt templates (P1 gate: every template renders). Rules PROMPT-01, PROMPT-02."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from as_engine.contracts.common import CallClass
from as_engine.prompts.render import PROMPT_DIR, cache_key, render

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "fixtures" / "prompt_samples"))
from samples import render_kwargs  # noqa: E402

pytestmark = pytest.mark.phase(1)
SAMPLES = render_kwargs()


def test_every_call_class_has_templates_and_a_sample():
    for cc in CallClass:
        assert (PROMPT_DIR / f"{cc.value}.system.j2").exists(), cc
        assert (PROMPT_DIR / f"{cc.value}.user.j2").exists(), cc
        assert cc in SAMPLES, cc


@pytest.mark.parametrize("cc", list(CallClass), ids=lambda c: c.value)
def test_template_renders(cc):
    msgs = render(cc, **SAMPLES[cc])
    assert [m.role for m in msgs] == ["system", "user"]
    assert msgs[0].content.strip() and msgs[1].content.strip()


@pytest.mark.parametrize("cc", list(CallClass), ids=lambda c: c.value)
def test_list_items_are_never_glued_together(cc):
    """Template whitespace: every bullet starts its own line."""
    for m in render(cc, **SAMPLES[cc]):
        for line in m.content.splitlines():
            assert not re.search(r"[^\s\-]- [A-Z]\d+[:( ]", line), f"{cc.value}: glued list item: {line!r}"
            assert not re.search(r'["\).:]\s?(?:WHAT|WHO|PEOPLE|HOW|THINGS)\b', line), f"{cc.value}: glued heading: {line!r}"


VOLATILE = ("Mara", "Owen", "June", "23:14", "Day 18", "metal crash", "Delgado")


@pytest.mark.parametrize("cc", list(CallClass), ids=lambda c: c.value)
def test_system_prompt_is_stable(cc):
    """PROMPT-01: the system message carries no volatile value (names, times, percepts) — so the
    KV cache prefix is shared across every call of the class."""
    system = render(cc, **SAMPLES[cc])[0].content
    for v in VOLATILE:
        assert v not in system, f"{cc.value} system prompt contains {v!r}"


def test_cache_key_is_the_system_prefix():
    a = render(CallClass.ACTOR_COGNITION, **SAMPLES[CallClass.ACTOR_COGNITION])
    b = render(CallClass.ACTOR_REACTION, **SAMPLES[CallClass.ACTOR_REACTION])
    assert cache_key(a) != cache_key(b) or a[0].content == b[0].content
    assert len(cache_key(a)) == 64


PSEUDO = (r"\bdef \w+\(", r"\breturn\b", r"==", r"!=", r"&&", r"\|\|", r"=>", r"\bif \(", r"\belif\b")


@pytest.mark.parametrize("cc", list(CallClass), ids=lambda c: c.value)
def test_no_pseudo_code(cc):
    """PROMPT-02: plain organised English; JSON only as the answer shape."""
    for m in render(cc, **SAMPLES[cc]):
        for pat in PSEUDO:
            assert not re.search(pat, m.content), f"{cc.value}: pseudo-code {pat!r}"
