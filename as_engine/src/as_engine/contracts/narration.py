"""Narration contracts (docs/as/04_TURN_PIPELINE.md stages 16-18, 05 §Narration).

L9: the narrator receives committed events filtered to PC perception. It cannot see intents,
hidden state, or unperceived events. Actor speech reaches the narrator as committed SPEECH
lines that must be rendered verbatim; the narrator may not invent dialogue (rule NARR-06).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import Strict


class NarratorLine(Strict):
    """One committed, PC-perceived fact in order of occurrence."""

    seconds: float = Field(ge=0, description="Offset from the start of this transaction.")
    kind: Literal["outcome", "sound", "sight", "speech", "touch", "smell", "body", "environment", "time"]
    text: str
    speaker: str | None = Field(default=None, description="Name or description as the PC knows them (speech only).")
    words: str | None = Field(default=None, description="Exact perceived words (speech only). Must appear verbatim.")


class NarratorStyle(Strict):
    """Narrator continuity state (AS Plan §12.5), saved with the run."""

    pacing: Literal["slow", "measured", "quick", "breathless"] = "measured"
    descriptive_density: Literal["spare", "moderate", "rich"] = "moderate"
    sentence_length: Literal["short", "mixed", "long"] = "mixed"
    vocabulary_register: Literal["plain", "coarse", "literary"] = "plain"
    emotional_register: Literal["cold", "tense", "grim", "tender", "numb"] = "tense"
    recent_scene_type: str = "arrival"
    portrayal_notes: list[str] = Field(default_factory=list, max_length=12)
    dialogue_texture: str = "clipped"
    recently_used_images: list[str] = Field(default_factory=list, max_length=30)


class NarratorPacket(Strict):
    turn_index: int
    world_time_text: str
    place_text: str
    pc_name: str
    pc_state_lines: list[str] = Field(default_factory=list)
    comprehension: Literal["low", "average", "high"] = "average"
    lines: list[NarratorLine] = Field(default_factory=list)
    establish_place: bool = False
    place_details: list[str] = Field(default_factory=list)
    people_present: list[str] = Field(default_factory=list, description="As the PC perceives them.")
    choice_prompt_hint: str | None = None
    allowed_names: list[str] = Field(default_factory=list, description="Proper names the PC knows and may be written.")
    style: NarratorStyle = Field(default_factory=NarratorStyle)
    length: Literal["short", "medium", "long"] = "medium"
    person: Literal["third_limited", "second"] = "third_limited"
    tense: Literal["past", "present"] = "past"
    banned_phrases: list[str] = Field(default_factory=list)
    intensity: Literal["full", "softer"] = "full"
    player_input_echo_block: list[str] = Field(default_factory=list, description="PC 4-grams the narrator must not repeat.")


class LintFinding(Strict):
    rule: str = Field(description="Rule id, e.g. STYLE-PASSIVE, DISC-NAME, DISC-SPEECH, ECHO-01")
    detail: str
    sentence_index: int | None = None
    severity: Literal["error", "warning"] = "error"


class ProseMetrics(Strict):
    words: int
    sentences: int
    passive_ratio: float
    adverb_ratio: float
    similes_per_200w: float
    abstract_ratio: float
    vague_timers: int
    banned_phrases: int
    leak_phrases: int
    max_same_opener_bigram: int
    max_consecutive_same_first_word: int


class LintReport(Strict):
    passed: bool
    metrics: ProseMetrics
    findings: list[LintFinding] = Field(default_factory=list)


class RenderLintJudgement(Strict):
    """RENDER_LINT model output: sentences asserting facts not supported by the packet."""

    unsupported: list["UnsupportedSentence"] = Field(default_factory=list, max_length=10)


class UnsupportedSentence(Strict):
    sentence_index: int = Field(ge=0)
    reason: Literal["not_in_packet", "reveals_hidden", "invented_dialogue", "meta_commentary"]


RenderLintJudgement.model_rebuild()
