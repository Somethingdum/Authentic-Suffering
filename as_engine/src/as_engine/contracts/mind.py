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

from typing import Any, Literal

from pydantic import Field, model_validator

from .dossier import VoiceExample
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
# The identity card (Actor Spec §4, AC02 / AC04) — compiled ONLY by mind.identity.compile_identity
# ---------------------------------------------------------------------------


class CardLine(Strict):
    text: str = Field(min_length=1)
    sources: list[str] = Field(min_length=1, description="The dossier paths this line is made from, dotted, "
                               "list items by index: 'decision_stack.inversion_conditions[1]'.")


class CardSection(Strict):
    key: Literal["who", "priorities", "values", "contradictions", "private_life", "habits", "temper", "voice", "silence",
                 "competence"]
    heading: str | None = Field(description="None only for 'who', the card's opening.")
    lines: list[CardLine] = Field(min_length=1)


class IdentityCard(Strict):
    """Who a person is, as a decision call shows it: the whole dossier's person in plain lines, each
    traceable to the fields it came from (mind.identity, IDN-01..04). Never trimmed for budget."""

    name: str
    age: int
    one_line: str
    compiler: Literal["card-1"] = "card-1"
    dossier_hash: str = Field(description="sha256 of kernel.jsoncanon.canonical_json(dossier dump, by alias).")
    minimum: bool = Field(default=False, description="The reaction card (IDN-05).")
    sections: list[CardSection] = Field(min_length=1)

    def section(self, key: str) -> CardSection | None:
        """The section with that key, or None (implemented)."""
        return next((s for s in self.sections if s.key == key), None)

    def as_text(self) -> str:
        """The card as a prompt shows it (implemented): each section's heading on its own line (none
        for 'who'), then its lines, one per line; a blank line between sections."""
        blocks = []
        for s in self.sections:
            lines = ([s.heading] if s.heading else []) + [line.text for line in s.lines]
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Skull Packet (AS Rebuild Plan §6.1) — built ONLY by mind.packet.build_packet
# ---------------------------------------------------------------------------


class PacketEntity(Strict):
    handle: str = Field(pattern=r"^P\d+$")
    description: str = Field(description="How THIS mind perceives/knows them: name if known, else a description.")
    known_name: str | None = None
    relation_summary: str | None = None
    whereabouts: str = Field(description="'here', 'heard, not seen', 'last seen in <place> <age>' or 'not seen' "
                             "(mind.packet; Actor Spec AC14).")
    appearance: str = Field(default="", description="What you see and smell of them right now (F1a/F1b, LOOK-06); "
                            "'' when you do not see them now.")
    feeling: str = Field(default="", description="How you feel about them right now (H1, TEMPER-08): 'you are "
                         "furious with them', 'they are getting under your skin', 'you hold a grudge against "
                         "them' or ''.")


class PerceivedItem(Strict):
    handle: str = Field(pattern=r"^S\d+$")
    channel: Channel
    fidelity: Fidelity
    text: str = Field(description="Plain English, e.g. 'A loud metal crash from behind the back wall.'")
    source_handle: str | None = None
    seconds_ago: float = Field(ge=0)


class ThreadLine(Strict):
    """D-117 (THREAD-01, Actor Spec §11): one line of what was said where this mind is, before this moment,
    as this mind heard it or said it."""

    speaker: str = Field(description="'you', a P-handle of this packet, or what this mind calls the speaker "
                         "('Someone' when it could not tell).")
    to_me: bool = False
    words: str = Field(description="As heard: exact, gap-marked, or '' when only the tone came through.")
    ago_text: str
    unanswered: bool = Field(default=False, description="A question put to this mind that it has not answered.")


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


class ExpressionOption(Strict):
    """B4 (Actor Spec §9): a gesture (G#) or a thing to keep your eyes on (F#) that may go with an
    attempt. It changes nothing by itself: a gesture is seen, attention is where you look."""

    handle: str = Field(pattern=r"^[GF]\d+$")
    label: str
    hands: int = Field(default=0, ge=0, le=2, description="Free hands a gesture needs (0 for attention).")


class Commitments(Strict):
    current_task: str | None = None
    plan_goal: str | None = None
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
    identity: IdentityCard
    recent_lines: list[str] = Field(default_factory=list)
    unprocessed: list[str] = Field(default_factory=list, description="B5 MEM-19: raw experience no writeback has settled yet.")
    body_lines: list[str] = Field(min_length=1)
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
    lore: list[str] = Field(default_factory=list, description="D-130 (LORE-03): what people say about what is in front of "
                            "them, as they hold it: '<text> (everyone says so)'.")
    open_loops: list[LoopLine] = Field(default_factory=list)
    refusals: list[str] = Field(default_factory=list)
    commitments: Commitments = Field(default_factory=Commitments)
    stakes: Stakes = Field(default_factory=Stakes)
    resources: list[str] = Field(default_factory=list)
    affordances: list[AffordanceOption] = Field(min_length=1)
    gestures: list[ExpressionOption] = Field(default_factory=list, description="B4 GEST-01: what may go with the attempt.")
    attention_points: list[ExpressionOption] = Field(default_factory=list, description="B4 FOCUS-01: what you may keep your eyes on.")
    hands_free: int = Field(default=0, ge=0, le=2, description="B4: free hands now (a gesture and the attempt share them).")
    uncertainty: list[str] = Field(default_factory=list)
    handles: dict[str, str] = Field(default_factory=dict, description="handle -> internal id. NEVER rendered.")
    omitted: list[str] = Field(default_factory=list, description="What the budget dropped, in drop order "
                               "(SKULL-09, Actor Spec AC16). NEVER rendered: an audit of what was cut.")
    families: list[str] = Field(default_factory=list, description="The kinds of thing this person could also "
                                "try that the menu does not show (mind.consult.FAMILIES keys, in that order; "
                                "Actor Spec §8: the visible list of supported families).")
    consult_kinds: list[Literal["recall", "more_actions", "compose"]] = Field(
        default_factory=list, description="What this call may consult (mind.consult, CONSULT-01); empty in a "
        "reaction and once a consultation has been answered.")
    looked_up: list[str] = Field(default_factory=list, description="What a consultation brought back "
                                 "(mind.consult), shown under 'What you looked up'.")
    outburst: str | None = Field(default=None, description="H1 (TEMPER-08): you have snapped at someone this "
                                 "moment and are going to have it out with them; None otherwise.")
    portrayal_note: str | None = Field(default=None, description="P11 PORT-07 (D-07): what someone who knows "
                                       "you would say about something you did lately that was not like you; None otherwise.")
    voice_examples: list[VoiceExample] = Field(default_factory=list, description="D-116 (EXAMPLE-02): moments "
                                               "in this person's own words, shown as things they already said.")
    thread: list[ThreadLine] = Field(default_factory=list, description="D-117 (THREAD-01): what was said "
                                     "here before this moment, oldest first.")


# ---------------------------------------------------------------------------
# Model outputs
# ---------------------------------------------------------------------------


# The answer models below reach the model as JSON-schema descriptions (lanes.schemas keeps
# "description"): their docstrings and Field descriptions are written TO the person answering.
# Engineering notes stay in comments.


class SpeechOut(Strict):
    """What you say: exactly these words. Who hears them depends on where everyone is."""

    # At most 800 characters here; 100 words (12 in a reaction) — action.intent.to_intent INTENT-08.
    text: str = Field(min_length=1, max_length=800, description="Exactly the words, at most 100 words "
                      "(at most 12 when something just reached you).")
    to: list[str] = Field(default_factory=list, description="Person handles, or ['everyone'].")
    volume: Volume = Volume.NORMAL
    delivery: Literal["ordinary", "hesitant", "clipped", "soothing", "strained"] = Field(
        default="ordinary", description="How you say it. It cannot make anyone feel anything.")
    timing: Literal["before", "alongside", "after"] = Field(
        default="alongside", description="Before, alongside or after your attempt.")


class Inscription(Strict):
    """A short note you write, only when your attempt is writing one."""

    text: str = Field(min_length=1, max_length=200, description="At most 200 characters and 35 words.")
    quotation_source: str | None = Field(default=None, description="An S or E handle when you copy that "
                                         "word for word.")


class ActionPayload(Strict):
    """Your decision: one attempt, and what goes with it. It says what you try, never how it turns out."""

    # Actor Spec §7, AC05. It cannot express results, damage, success, another body's state, or any
    # comply/accept/agree/refuse field (L2, L6). gesture / attention / inscription are null-only in
    # the schema until a packet offers G / F handles or a writing attempt (lanes.schemas SCHEMA-04).
    choice: str = Field(description="The handle of one offered attempt.")
    pace: Literal["normal", "careful", "rushed"] = Field(
        default="normal", description="Careful or rushed only where that attempt allows it.")
    speech: SpeechOut | None = None
    gesture: str | None = None
    attention: str | None = None
    inscription: Inscription | None = None
    goal: str = Field(min_length=1, max_length=200, description="What you want to come of it.")
    private_reason: str | None = Field(default=None, max_length=240, description="Why, briefly. Never spoken.")


class Consultation(Strict):
    """One thing you look up in your own head before you decide."""

    # mind.consult: a lookup in the person's own records and menu, never a look through a drawer.
    kind: Literal["recall", "more_actions", "compose"]
    query: str | None = Field(default=None, max_length=160, description="For recall: what you try to remember.")
    family: str | None = Field(default=None, description="For more_actions: one of the kinds offered.")
    template: str | None = None
    subjects: list[str] = Field(default_factory=list, max_length=4,
                                description="Person or perception handles it is about.")


class ActorReplyV2(Strict):
    """Your answer: a decision, or — only when it is offered — one consultation first."""

    # ACTOR_COGNITION / ACTOR_REACTION / INTENT_REPAIR output (Actor Spec §7, AC05). A decision
    # carries exactly one action payload, a consultation exactly one consultation payload — checked
    # here whatever the provider's grammar enforced (_one_payload).
    # V1 adapter (the spec's temporary adapter; turn.cognition REPLY-01): a JSON object without
    # ``kind`` but with ``choice`` is a V1 CognitionOutput and is read as {kind: 'decision', action:
    # {choice, speech, goal, private_reason}} — pace normal, no gesture, attention or inscription,
    # the speech with ordinary delivery alongside; its ``manner`` is dropped (a legacy manner
    # string is never read as a mechanical command).
    kind: Literal["decision", "consultation"]
    action: ActionPayload | None = None
    consultation: Consultation | None = None

    @model_validator(mode="before")
    @classmethod
    def _v1(cls, data: Any) -> Any:
        """The V1 adapter (implemented)."""
        if isinstance(data, dict) and "kind" not in data and "choice" in data:
            action = {k: data[k] for k in ("choice", "speech", "goal", "private_reason") if k in data}
            return {"kind": "decision", "action": action}
        return data

    @model_validator(mode="after")
    def _one_payload(self) -> "ActorReplyV2":
        """Exclusivity (implemented)."""
        if self.kind == "decision" and (self.action is None or self.consultation is not None):
            raise ValueError("a decision carries exactly one action payload and no consultation")
        if self.kind == "consultation" and (self.consultation is None or self.action is not None):
            raise ValueError("a consultation carries exactly one consultation payload and no action")
        return self


class CognitionOutput(Strict):
    """The V1 actor answer — read only through ActorReplyV2's adapter and by tests that script V1
    answers (the fake model's scripts). New answers are ActorReplyV2."""

    choice: str = Field(description="Affordance handle, restricted by enum in the dynamic schema.")
    speech: SpeechOut | None = None
    manner: str = Field(default="", max_length=120)
    goal: str = Field(min_length=3, max_length=200)
    private_reason: str = Field(min_length=3, max_length=400)


class IntakeOutput(Strict):
    """INTAKE output for the player's Do-mode text (05_ACTORS.md §PC side of the firewall). The
    player's words reach the same action vocabulary as an actor's: ``pace`` is the mechanical mode
    ('carefully', 'quietly' -> careful; 'quickly', 'in a hurry' -> rushed) where the option supports
    it; ``manner`` is colour only; (D-136) ``gesture`` is a G# handle of the packet when the words
    make one of its gestures alongside the option (a nod, a shrug, empty hands held up); (D-147) a
    none_reason 'wont' is a line the character does not cross (its own card's, L12); (D-290) ``words``
    is what the character says aloud when the player told it without quotation marks ('I ask Mara
    where the keys are' -> 'Mara, where are the keys?'), else null."""

    choice: str = Field(description="Affordance handle or 'NONE'.")
    none_reason: Literal[
        "impossible", "not_here", "not_holding", "not_trained", "unclear", "not_an_action", "wont"
    ] | None = None
    pace: Literal["normal", "careful", "rushed"] = "normal"
    manner: str = Field(default="", max_length=120)
    gesture: str | None = Field(default=None, description="G# handle of a gesture the player's words make, or null.")
    remainder: str | None = Field(default=None, max_length=200, description="Rest of a multi-step instruction, queued as a suggestion.")
    clarify: str | None = Field(default=None, max_length=200)
    words: str | None = Field(default=None, max_length=300,
                              description="What the character says aloud when the player only told it, or null.")


class BeliefWrite(Strict):
    about: str = Field(description="Entity handle, 'self' or 'place'.")
    claim: str = Field(min_length=3, max_length=300)
    confidence: int = Field(ge=0, le=3)
    because: list[str] = Field(min_length=1, description="Percept handles S#, or O# for what you did yourself.")


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
    category: Literal["deliver", "guard", "return", "disclose", "refrain", "assist"] | None = Field(
        default=None, description="B5d (PROM-01): for promise_made / promise_owed, what kind of promise; None -> assist.")


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


class SelfExperience(Strict):
    """B5 (Actor Spec §13, AC10): what the holder did and felt itself — 'I said…', 'I chose to…',
    'It did not work.' — evidence a memory can cite (O#), never more than was felt."""

    handle: str = Field(pattern=r"^O\d+$")
    text: str


class AftermathPacket(Strict):
    """Built by mind.memory.build_aftermath: ONLY this holder's percepts of committed events (L8)."""

    holder_id: str
    turn_index: int
    identity: IdentityCard
    percepts: list[PerceivedItem] = Field(default_factory=list)
    self_experiences: list[SelfExperience] = Field(default_factory=list)
    utterances: list[UtteranceView] = Field(default_factory=list)
    entities: list[PacketEntity] = Field(default_factory=list)
    own_action_text: str | None = None
    own_expectation_text: str | None = None
    open_loops: list[LoopLine] = Field(default_factory=list)
    relationships: list[RelationshipLine] = Field(default_factory=list)
    lore: list[str] = Field(default_factory=list, description="D-196: what this person grew up hearing about what "
                            "reached them (mind.retrieval.lore_lines), as in their Skull Packet.")
    told: list[str] = Field(default_factory=list, description="D-226: what this person had been told before about the "
                            "people in it and the place they are, and by whom (mind.memory build_aftermath) — which can "
                            "turn out not to be so.")
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


class CheatOp(Strict):
    """One step of a plain-words cheat (cheats.interpret OPS; CHEAT-17). Handles name the scene's
    entries: P0 is the Boss's own character."""

    op: Literal["teleport", "give", "make", "destroy", "spawn", "despawn", "kill", "revive", "heal", "hurt", "god",
                "set", "time", "weather", "noise", "will", "forget", "brief", "believe", "feel", "rep", "infect",
                "cure", "horde", "mega", "force", "reshape", "door", "blast", "show", "census", "reveal", "mind"]
    who: str | None = Field(default=None, max_length=8)
    target: str | None = Field(default=None, max_length=8)
    to: str | None = Field(default=None, max_length=8)
    item: str | None = Field(default=None, max_length=80)
    text: str | None = Field(default=None, max_length=300)
    n: int | None = Field(default=None, ge=-1000, le=1000)
    stat: str | None = Field(default=None, max_length=40)
    state: str | None = Field(default=None, max_length=40)
    size: Literal["small", "large", "huge"] | None = None


class CheatPlan(Strict):
    """CHEAT_INTERPRET output: what to do, in order — or the one question to ask back."""

    ops: list[CheatOp] = Field(default_factory=list, max_length=12)
    clarify: str | None = Field(default=None, max_length=200, description="Ask this instead of acting (which one?).")
    summary: str = Field(default="", max_length=200)


class VoiceMessage(Strict):
    """THE_VOICE output (D-106)."""

    paragraphs: list[str] = Field(min_length=1, max_length=3)


class DoomGuardOutput(Strict):
    """DOOM_GUARD output (D-106): does it pass on anything about the dying that is not common knowledge?"""

    tells: bool


class AmbientPerson(Strict):
    """D-128: someone the speaker can see, as they know them."""

    handle: str                      # P1.. (resolved by code, never shown as an id)
    word: str                        # the name they know, else how they look ('a tall man')
    feeling: str = ""                # how they feel about them now (mind.packet's TEMPER-08 words), or ''


class AmbientPacket(Strict):
    """AMBIENT_LINE context (D-128, AMB-01): what a COLD person — someone past this moment's model
    budget — has to go on to say one thing, or nothing. Built only from their own records (Skull Law)."""

    actor_id: str
    name: str
    voice: list[str]                 # how they talk: the capsule, tendencies, the three exemplars, never-says
    where: str
    when: str = ""                   # D-159: the time as they know it (the SkullPacket's world_time_text)
    doing: str = ""                  # what code has them doing (their continuation's label), or ''
    state: list[str] = Field(default_factory=list)   # how their body and mind are (max 3), or none
    reached: list[str]               # what has reached them since they last spoke, oldest first (max 4)
    said: list[str] = Field(default_factory=list)    # their own last lines (max 3): never say them again
    knows: list[str] = Field(default_factory=list)   # D-130: what people say about what is in front of them (max 2)
    mind: list[str] = Field(default_factory=list)    # D-257: in a quiet moment, what is on their mind (max 2)
    people: list[AmbientPerson] = Field(default_factory=list)
    handles: dict[str, str] = Field(default_factory=dict)


class AmbientLine(Strict):
    """AMBIENT_LINE output (D-128): one short line in their own voice, or nothing (line null)."""

    line: str | None = Field(default=None, max_length=200)
    to: str | None = None            # a P-handle of the packet, or null: to whoever is there
    volume: Literal["low", "normal", "raised"] = "normal"


class PersonVoice(Strict):
    """PERSON_VOICE output (D-149): a generated person's voice, written from what they have actually said. Each
    field is null (or empty) to keep what the card has."""

    capsule: str | None = Field(default=None, max_length=200, description="How they talk, one sentence, third person.")
    tendencies: list[str] = Field(default_factory=list, max_length=3, description="Two or three habits of speech.")
    low_stakes: str | None = Field(default=None, max_length=160, description="A line of theirs when nothing is at stake.")
    under_pressure: str | None = Field(default=None, max_length=160, description="A line of theirs when it is.")
    at_the_limit: str | None = Field(default=None, max_length=160, description="A line of theirs at the end of their rope.")


class WillisRoast(Strict):
    """WILLIS_ROAST output (D-105): what Willis says to the dead, line by line."""

    lines: list[str] = Field(min_length=1, max_length=6)


class SayMyWayOutput(Strict):
    line: str = Field(min_length=1, max_length=400)
    survived: Literal["intact", "softened", "garbled", "withheld"]
