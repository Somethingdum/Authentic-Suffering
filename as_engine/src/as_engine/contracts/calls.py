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


class SceneEntry(Strict):
    """One thing the plain-words console may name (cheats.interpret.scene, CHEAT-16)."""

    handle: str
    label: str
    kind: str = ""
    where: str = ""
    note: str = ""


class CheatScene(Strict):
    """What 'that', 'him', 'the door' can mean: the PC's side of the glass (cheats.interpret.scene)."""

    me: SceneEntry
    here: SceneEntry
    people: list[SceneEntry] = Field(default_factory=list)
    places: list[SceneEntry] = Field(default_factory=list)
    doors: list[SceneEntry] = Field(default_factory=list)
    items: list[SceneEntry] = Field(default_factory=list)
    groups: list[SceneEntry] = Field(default_factory=list)
    makeable: list[str] = Field(default_factory=list)
    spawnable: list[str] = Field(default_factory=list)
    strains: list[str] = Field(default_factory=list)
    weather: list[str] = Field(default_factory=list)
    willis: bool = False


class CheatInterpretContext(Strict):
    """P12, D-103: the Boss's plain words and the scene they are said in (CHEAT_INTERPRET)."""

    request: str
    scene: CheatScene


class CheatPersonaContext(Strict):
    command: str
    outcome: str
    recent_lines: list[str] = Field(default_factory=list, max_length=5, description="Persona lines already used; must not be repeated.")
    willis: bool = Field(default=False, description="D-79: the Boss is playing Willis (the PC is in the reality exception); "
                         "he takes the voice for a demon in his head.")


class RoastFacts(Strict):
    """D-105, D-106 (service.death.roast_facts): what Willis has in the frozen moment — the doomed
    person's own record only; the world's secrets are the Voice's to tell."""

    pc_name: str
    lived: str = Field(description="How long this life lasted: '2 days', '5 hours', '40 minutes'.")
    turns: int = Field(ge=0, description="Moments the player played in this life.")
    cause_text: str = Field(default="", description="D-106: empty in the frozen moment — Willis does not know how, and does not care.")
    choices: list[str] = Field(default_factory=list, max_length=5, description="Their own last choices, newest first.")
    typed: list[str] = Field(default_factory=list, max_length=5, description="What the player typed last, oldest first.")
    bent_rules: bool = Field(default=False, description="The run is a Sandbox: the console was used.")
    borrowed: list[str] = Field(default_factory=list, max_length=8, description="D-106: what they did with his power this life "
                                "(the console lines), oldest first.")
    in_debt: bool = Field(default=False, description="D-106: they used his power and are not him — a loan; he mocks twice as hard.")
    ironman: bool = False
    rises: bool = Field(default=False, description="The body will get up again.")
    met_him: bool = Field(default=False, description="The dead person had met Willis in the world.")
    by_his_hand: bool = Field(default=False, description="Willis himself is on the chain of events that killed them.")


class WillisRoastContext(Strict):
    """WILLIS_ROAST input (D-105)."""

    facts: RoastFacts


class ChainBeat(Strict):
    """D-106: one link of the chain that killed them, from the record (service.voice)."""

    when: str = Field(description="'day 212, 06:05'")
    kind: Literal["choice", "consequence", "unseen", "clue"]
    text: str = Field(max_length=300)
    said: str | None = Field(default=None, max_length=300, description="For a choice: what the player typed that moment.")


class VoiceFacts(Strict):
    """D-106 (service.voice.voice_facts): everything the Voice brags with — all of it from the record."""

    pc_name: str
    lived: str
    seconds_left: int = Field(ge=0, description="Before the death: about how long they have; after: 0.")
    chain: list[ChainBeat] = Field(default_factory=list, max_length=24, description="Oldest first.")
    threat: str | None = Field(default=None, description="What has been with them, by what it truly is ('a lurker', 'Mara Voss').")
    threat_near: str | None = Field(default=None, description="For how long it has been near them ('6 hours').")
    upper_hand: list[str] = Field(default_factory=list, max_length=8, description="What they had going for them.")
    manner: str | None = Field(default=None, description="Only after the death: how it happened.")
    said_before: list[str] = Field(default_factory=list, max_length=3, description="After the death: what the Voice said before it.")


class VoiceContext(Strict):
    """THE_VOICE input (D-106)."""

    moment: Literal["before", "after"]
    facts: VoiceFacts


class DoomGuardContext(Strict):
    """DOOM_GUARD input (D-106, DOOM-07): what a doomed player just tried to do or say."""

    text: str = Field(max_length=2000)


class WorldgenContext(Strict):
    """Generic context for worldgen calls; ``brief`` is code-built plain English."""

    stage: str
    brief: str
    fields: dict = Field(default_factory=dict)


class DossierIntakeContext(Strict):
    target_kind: Literal["actor", "pc", "faction", "lore"]
    source_text: str
    pack_id: str
