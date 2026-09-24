"""Structured *contexts* attached to LMRequest.context for each call class.

Prompts are rendered from these objects by the Jinja templates in as_engine/prompts/. The fake
transport (as_engine/testing/fake_lm.py) reads these objects directly instead of parsing prompt
text, so tests stay independent of prompt wording.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import Strict
from .mind import ActionPayload, AftermathPacket, SkullPacket
from .narration import NarratorPacket


class IntakeContext(Strict):
    packet: SkullPacket = Field(description="The PC's own packet (L12: built by the same builder).")
    player_text: str
    quoted_speech: list[str] = Field(default_factory=list, description="Text inside quotes, extracted by code; speech only.")


class RepairContext(Strict):
    packet: SkullPacket
    raw_text: str
    error: str


class AuditContext(Strict):
    packet: SkullPacket
    output: ActionPayload = Field(description="The decision under audit (an ActorReplyV2's action).")
    chosen_label: str


class LintContext(Strict):
    packet: NarratorPacket
    prose: str
    sentences: list[str]


class GuideContext(Strict):
    question: str
    pc_name: str
    pc_facts: list[str] = Field(default_factory=list, description="Only what the PC knows.")
    rules_snippets: list[str] = Field(default_factory=list)
    cheat_query: bool = Field(default=False, description="Set by code when the question is about cheats/codes before activation; the template then uses the in-world deflection style.")


class WritebackContext(Strict):
    aftermath: AftermathPacket


class SummaryContext(Strict):
    holder_name: str
    lines: list[str]
    purpose: Literal["scene_summary", "recap"]


class SayMyWayContext(Strict):
    packet: SkullPacket
    seed_text: str
    behavior_notes: list[str] = Field(default_factory=list, description="PCDossier.behavior_law topic_handling, plan_carry, distortion and pressure lines, in that order (empty when absent).")


class ReflectionContext(Strict):
    packet: SkullPacket
    recent_episodes: list[str]


class RumourContext(Strict):
    teller_identity: str
    claim_text: str
    teller_confidence: int


class ProbeContext(Strict):
    probe: Literal["hello", "json", "thinking_off", "thinking_on"]


class CheatPersonaContext(Strict):
    command: str
    outcome: str
    recent_lines: list[str] = Field(default_factory=list, max_length=5, description="Persona lines already used; must not be repeated.")


class WorldgenContext(Strict):
    """Generic context for worldgen calls; ``brief`` is code-built plain English."""

    stage: str
    brief: str
    fields: dict = Field(default_factory=dict)


class DossierIntakeContext(Strict):
    target_kind: Literal["actor", "pc", "faction", "lore"]
    source_text: str
    pack_id: str
