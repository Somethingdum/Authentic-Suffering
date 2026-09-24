"""Mind-layer contracts: the Skull Packet, model outputs, aftermath and audits
(docs/as/05_ACTORS.md, docs/as/08_LLM_CALLS.md).

Handles
-------
Prompts never show internal ids. Every entity, affordance, percept, memory and open loop in a
packet gets a short per-packet *handle* ("P1", "A3", "S2", "E1", "L4"). The handle map lives in
``SkullPacket.handles`` (never rendered) and code translates model output handles back to ids.
Dynamic JSON schemas restrict handle fields to ``enum`` lists, so a model cannot pick an
affordance or target that code did not offer (L3, rule INTENT-02).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import (
    LOD,
    Channel,
    Fidelity,
    OpenLoopKind,
    RelationAxis,
    Standing,
    Strict,
    UtteranceForm,
    Verb,
    Volume,
)


# ---------------------------------------------------------------------------
# Skull Packet (AS Rebuild Plan §6.1) — built ONLY by mind.packet.build_packet
# ---------------------------------------------------------------------------


class PacketEntity(Strict):
    handle: str = Field(pattern=r"^P\d+$")
    description: str = Field(description="How THIS mind perceives/knows them: name if known, else a description.")
    known_name: str | None = None
    relation_summary: str | None = None


class PerceivedItem(Strict):
    handle: str = Field(pattern=r"^S\d+$")
    channel: Channel
    fidelity: Fidelity
    text: str = Field(description="Plain English, e.g. 'A loud metal crash from behind the back wall.'")
    source_handle: str | None = None
    seconds_ago: float = Field(ge=0)


class UtteranceView(Strict):
    """A perceived utterance addressed to (or overheard by) this mind.

    Firewall rule WILL-00: requests reach a mind ONLY as this record, labelled with the form and
    standing *as this receiver classifies them*. There is no field named request/order/task/ask.
    """

    handle: str = Field(pattern=r"^S\d+$")
    speaker_handle: str | None
    words: str = Field(description="Exact words for EXACT fidelity; gap-marked for PARTIAL; '' for TONE_ONLY.")
    fidelity: Fidelity
    form: UtteranceForm
    standing: Standing
    addressed_to_me: bool
    volume: Volume


class BeliefLine(Strict):
    text: str
    confidence: int = Field(ge=0, le=3)
    provenance_text: str
    age_text: str


class RelationshipLine(Strict):
    handle: str
    text: str


class MemoryLine(Strict):
    handle: str = Field(pattern=r"^E\d+$")
    text: str
    age_text: str


class LoopLine(Strict):
    handle: str = Field(pattern=r"^L\d+$")
    kind: OpenLoopKind
    text: str


class AffordanceOption(Strict):
    handle: str = Field(pattern=r"^A\d+$")
    verb: Verb
    label: str = Field(description="Plain English option, e.g. 'Move to the rear door (4 m, about 3 seconds)'.")
    cost_note: str | None = None
    risk_note: str | None = None


class Commitments(Strict):
    current_task: str | None = None
    plan_step: str | None = None
    standing_orders: list[str] = Field(default_factory=list)
    deadline: str | None = None


class Stakes(Strict):
    dependents: list[str] = Field(default_factory=list)
    obligations: list[str] = Field(default_factory=list)
    would_lose: list[str] = Field(default_factory=list)


class SkullPacket(Strict):
    actor_id: str
    turn_index: int
    lod: LOD
    world_time_text: str
    identity_text: str
    voice_capsule: str
    voice_exemplars: list[str] = Field(min_length=3, max_length=3)
    recent_lines: list[str] = Field(default_factory=list)
    would_never_say: list[str] = Field(default_factory=list)
    body_lines: list[str] = Field(min_length=1)
    capability_lines: list[str] = Field(min_length=1)
    resolve_cur: int = Field(ge=0)
    resolve_max: int = Field(ge=1)
    position_text: str
    perceived_now: list[PerceivedItem] = Field(default_factory=list)
    utterances: list[UtteranceView] = Field(default_factory=list)
    entities: list[PacketEntity] = Field(default_factory=list)
    beliefs: list[BeliefLine] = Field(default_factory=list)
    relationships: list[RelationshipLine] = Field(default_factory=list)
    memories: list[MemoryLine] = Field(default_factory=list)
    lessons: list[str] = Field(default_factory=list, description="'Experience taught you: …' lines (P6, MEM-15).")
    open_loops: list[LoopLine] = Field(default_factory=list)
    refusals: list[str] = Field(default_factory=list)
    commitments: Commitments = Field(default_factory=Commitments)
    stakes: Stakes = Field(default_factory=Stakes)
    resources: list[str] = Field(default_factory=list)
    motive_lines: list[str] = Field(default_factory=list)
    persona_lines: list[str] = Field(default_factory=list)
    moral_lines: list[str] = Field(default_factory=list)
    decision_lines: list[str] = Field(default_factory=list)
    active_traits: list[str] = Field(default_factory=list)
    writers_notes: str | None = None
    affordances: list[AffordanceOption] = Field(min_length=1)
    uncertainty: list[str] = Field(default_factory=list)
    handles: dict[str, str] = Field(default_factory=dict, description="handle -> internal id. NEVER rendered.")


# ---------------------------------------------------------------------------
# Model outputs
# ---------------------------------------------------------------------------


class SpeechOut(Strict):
    text: str = Field(min_length=1, max_length=400)
    to: list[str] = Field(default_factory=list, description="Entity handles, or ['everyone'].")
    volume: Volume = Volume.NORMAL


class CognitionOutput(Strict):
    """ACTOR_COGNITION / ACTOR_REACTION output. Note what it cannot express: results, damage,
    success, another body's state, or any comply/accept/agree/refuse field (L2, L6)."""

    choice: str = Field(description="Affordance handle, restricted by enum in the dynamic schema.")
    speech: SpeechOut | None = None
    manner: str = Field(default="", max_length=120)
    goal: str = Field(min_length=3, max_length=200)
    private_reason: str = Field(min_length=3, max_length=400)


class IntakeOutput(Strict):
    """INTAKE output for the player's Do-mode text (05_ACTORS.md §PC side of the firewall)."""

    choice: str = Field(description="Affordance handle or 'NONE'.")
    none_reason: Literal[
        "impossible", "not_here", "not_holding", "not_trained", "unclear", "not_an_action"
    ] | None = None
    manner: str = Field(default="", max_length=120)
    remainder: str | None = Field(default=None, max_length=200, description="Rest of a multi-step instruction, queued as a suggestion.")
    clarify: str | None = Field(default=None, max_length=200)


class BeliefWrite(Strict):
    about: str = Field(description="Entity handle, 'self' or 'place'.")
    claim: str = Field(min_length=3, max_length=300)
    confidence: int = Field(ge=0, le=3)
    because: list[str] = Field(min_length=1, description="Percept handles S#.")


class RelationWrite(Strict):
    with_: str = Field(alias="with")
    axis: RelationAxis
    delta: int = Field(ge=-2, le=2)
    because: str
    model_config = Strict.model_config | {"populate_by_name": True}


class LoopWrite(Strict):
    kind: Literal["goal", "desire", "grudge", "fear", "question", "plan", "promise_made", "promise_owed", "debt_owing", "debt_owed", "secret_kept"]
    text: str = Field(min_length=3, max_length=200)
    subject: str | None = None
    strength: int = Field(ge=1, le=3)
    because: str


class LoopClose(Strict):
    loop: str = Field(pattern=r"^L\d+$")
    status: Literal["fulfilled", "broken", "abandoned"]
    because: str


class LessonWrite(Strict):
    cue_tags: list[str] = Field(min_length=1, max_length=4)
    text: str = Field(min_length=5, max_length=200)
    because: str


class WritebackOutput(Strict):
    episode: str = Field(min_length=5, max_length=700, description="What happened, in this mind's own voice.")
    salience: int = Field(ge=0, le=100)
    beliefs: list[BeliefWrite] = Field(default_factory=list, max_length=6)
    relationships: list[RelationWrite] = Field(default_factory=list, max_length=6)
    new_loops: list[LoopWrite] = Field(default_factory=list, max_length=4)
    closed_loops: list[LoopClose] = Field(default_factory=list, max_length=4)
    lesson: LessonWrite | None = None


class AftermathPacket(Strict):
    """Built by mind.memory.build_aftermath: ONLY this holder's percepts of committed events (L8)."""

    holder_id: str
    turn_index: int
    identity_text: str
    voice_capsule: str
    percepts: list[PerceivedItem] = Field(default_factory=list)
    utterances: list[UtteranceView] = Field(default_factory=list)
    entities: list[PacketEntity] = Field(default_factory=list)
    own_action_text: str | None = None
    own_expectation_text: str | None = None
    open_loops: list[LoopLine] = Field(default_factory=list)
    relationships: list[RelationshipLine] = Field(default_factory=list)
    handles: dict[str, str] = Field(default_factory=dict)


class PortrayalVerdict(Strict):
    verdict: Literal["fits", "doubtful", "out_of_character"]
    reasons: list[str] = Field(default_factory=list, max_length=3)
    cites: list[str] = Field(default_factory=list, max_length=4, description="Dossier section names relied on.")


class ReflectionOutput(Strict):
    goals_add: list[LoopWrite] = Field(default_factory=list, max_length=3)
    loops_close: list[LoopClose] = Field(default_factory=list, max_length=3)
    lesson: LessonWrite | None = None
    plan_goal: str | None = Field(default=None, max_length=200)
    plan_steps: list[str] = Field(default_factory=list, max_length=5)


class RumourDistortion(Strict):
    operation: Literal["drop_detail", "shift_attribution", "sharpen_emotion", "add_inference", "none"]
    retold_claim: str = Field(min_length=3, max_length=300)


class CascadeSuggestion(Strict):
    suggestions: list[str] = Field(default_factory=list, max_length=5)


class SayMyWayOutput(Strict):
    line: str = Field(min_length=1, max_length=400)
    survived: Literal["intact", "softened", "garbled", "withheld"]
