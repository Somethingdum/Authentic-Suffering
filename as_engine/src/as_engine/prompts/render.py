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

(D-277) doubts(lines), the 'doubts' filter: the actor prompt's What remains uncertain says the doubts of many
percepts once each way — 'You could not make out S1, S2 or S5 in full.', 'You did not catch S3 or S4 in full.' — a
single one as the packet has it, and any other line as it is, in order.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ..contracts.common import CallClass
from ..contracts.content import AFFORDANCE_FAMILIES
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
# D-168: who the speaker is to the one who heard (mind.firewall Standing), in words, not an enum ('(peer)')
STANDING_WORDS = {"valid_order": "someone whose orders you follow", "claimed_authority": "someone acting as if they give you orders",
                  "peer": "someone you know", "stranger": "a stranger", "subordinate": "someone who answers to you",
                  "hostile": "someone against you"}
# D-166: how someone spoke, as a verb ('spoke normal to you', 'spoke shout' read as broken English to every mind)
VOLUME_WORDS = {"whisper": "whispered", "low": "spoke quietly", "normal": "spoke", "raised": "called out", "shout": "shouted"}
# D-158: how a percept that is not speech came through, by channel (FIDELITY_WORDS speak of words; a sighting is
# not 'some words lost', a sound not 'seen, not heard'). Missing pairs fall back to FIDELITY_WORDS.
PERCEPT_WORDS = {
    "visual:exact": "clearly", "visual:partial": "only partly", "visual:visual_only": "only as a shape",
    "auditory:exact": "clearly", "auditory:partial": "not clearly", "auditory:tone_only": "barely",
    "olfactory:exact": "clearly", "olfactory:partial": "faintly",
}


# D-277: the doubts of many percepts said once each way ('You could not make out S1, S2 or S5 in full.')
_DOUBTS = {"You could not make out all of ": "You could not make out {} in full.",
           "You did not catch all of ": "You did not catch {} in full."}


def doubts(lines: list[str]) -> list[str]:
    heads: dict[str, list[str]] = {}
    out: list[str] = []
    for ln in lines:
        head = next((h for h in _DOUBTS if ln.startswith(h) and ln.endswith(".")), None)
        if head is None:
            out.append(ln)
            continue
        if head not in heads:
            heads[head] = []
            out.append(head)
        heads[head].append(ln[len(head):-1])
    return [ln if ln not in heads else f"{ln}{heads[ln][0]}." if len(heads[ln]) == 1 else
            _DOUBTS[ln].format(", ".join(heads[ln][:-1]) + " or " + heads[ln][-1]) for ln in out]


_env.filters["doubts"] = doubts


def render(call_class: CallClass, **ctx: Any) -> list[ChatMessage]:
    name = call_class.value
    words = {"fidelity_words": FIDELITY_WORDS, "percept_words": PERCEPT_WORDS, "volume_words": VOLUME_WORDS,
             "standing_words": STANDING_WORDS, "family_words": AFFORDANCE_FAMILIES}
    system = _env.get_template(f"{name}.system.j2").render(**words, **ctx).strip()
    user = _env.get_template(f"{name}.user.j2").render(**words, **ctx).strip()
    return [ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)]


def cache_key(messages: list[ChatMessage]) -> str:
    return hashlib.sha256(messages[0].content.encode("utf-8")).hexdigest()
