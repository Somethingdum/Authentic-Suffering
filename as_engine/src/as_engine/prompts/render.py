"""Prompt rendering (IMPLEMENTED). Templates: prompts/<call_class>.system.j2 + <call_class>.user.j2.

Keyword arguments per call class (the templates rely on these names):
  actor_cognition, actor_reaction ........ p=SkullPacket
  writeback .............................. a=AftermathPacket, cue_ids=list[str]
  narration .............................. k=NarratorPacket, words=(min, max), fix=list[str]
  every other call class ................. ctx=<the matching contracts.calls *Context model>
      (cascade_advisory / worldgen_* / pc_quickmake use WorldgenContext with a code-built brief)

KV-cache law (PROMPT-01): the system template must not contain any volatile value (time, percepts,
names of present people); stable per-actor content goes FIRST in the user template, volatile
content LAST. PROMPT-02: no pseudo-code in anything the model reads — plain organised English;
JSON appears only as the required answer shape.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ..contracts.common import CallClass
from ..contracts.lanes import ChatMessage

PROMPT_DIR = Path(__file__).parent
_env = Environment(
    loader=FileSystemLoader(str(PROMPT_DIR)),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=False,
    autoescape=False,
)

FIDELITY_WORDS = {
    "exact": "clearly",
    "partial": "only partly, some words lost",
    "tone_only": "only the tone, no words",
    "visual_only": "seen, not heard",
    "none": "not at all",
}


def render(call_class: CallClass, **ctx: Any) -> list[ChatMessage]:
    name = call_class.value
    system = _env.get_template(f"{name}.system.j2").render(fidelity_words=FIDELITY_WORDS, **ctx).strip()
    user = _env.get_template(f"{name}.user.j2").render(fidelity_words=FIDELITY_WORDS, **ctx).strip()
    return [ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)]


def cache_key(messages: list[ChatMessage]) -> str:
    return hashlib.sha256(messages[0].content.encode("utf-8")).hexdigest()
