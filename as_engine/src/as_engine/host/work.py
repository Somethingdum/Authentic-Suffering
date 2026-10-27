"""What each model call is, for the host that routes it (D-299). Rules HOST-04, HOST-05.

The engine never chooses a model when it is hosted (as_engine.host). It says what each call IS, and
the host decides which model answers, when, how much it may think and how long it may take.

work_for(request, *, step, author=None) -> dict   (HOST-04)
  {kind, role, call_class, step, think, answer, max_tokens, background, idle, optional, label}:
  kind        'narrative' when request.lane is Lane.A, else 'engineering'. The engine's two lanes have
              always been roles, not machines (D-111): lane A is the Writer — every word the player
              reads as story, the people in focus, the long creative work — and lane B the Clerk —
              scoped work whose answer code can check. Hosted, that role is all a lane means.
  role        ROLE[call_class].
  call_class  request.call_class value (content-free).
  step        the turn step the call belongs to (as_engine.host.governor), given by the caller.
  author      for a review (role 'review'): the call_id of the work it reads, so the host can give
              it to the model that did not make it; None otherwise.
  think       'main' for NARRATION (the turn's own reply); else 'full' when request.thinking, else
              'off'. The engine's regimes say which calls are worth thinking for; the host says how
              much thinking it can afford.
  answer      ANSWER_TOKENS[call_class] when the class thinks (its expected answer without the
              thinking), else request.max_tokens — for the host's time estimates.
  max_tokens  request.max_tokens: the most the call may write, its thinking included.
  background  call_class in BACKGROUND: it runs beside the turn's critical path (memories, the
              Journal's summaries).
  idle        call_class in IDLE: work for the quiet hours between turns, which may wait for a moment
              nobody else needs the models and may be pre-empted.
  optional    call_class in OPTIONAL_AT_CALL: the host may leave it out for time; the engine then
              takes the path it already has for a call that did not come back (LANE-12).
  label       LABEL[call_class]: plain words for progress lines, never content and never a name —
              and never ahead of the story: the Doom's guard reads as "reading your move" and the
              Voice and Willis as "writing", so a label never tells the player what the story has
              not (DOOM-07).

HOST-05 a review's author: a PORTRAYAL_AUDIT reads the decision of the person it names
  (request.actor_id) made earlier in the same turn; a RENDER_LINT reads the last narration draft of
  the turn. The transport remembers those call ids per turn (as_engine.host.transport).
"""

from __future__ import annotations

from ..contracts.common import CallClass, Lane
from ..contracts.lanes import LMRequest

ROLE: dict[CallClass, str] = {
    CallClass.INTAKE: "read", CallClass.ACTOR_COGNITION: "decide", CallClass.ACTOR_REACTION: "react",
    CallClass.INTENT_REPAIR: "extract", CallClass.WRITEBACK: "extract", CallClass.PORTRAYAL_AUDIT: "review",
    CallClass.NARRATION: "write", CallClass.RENDER_LINT: "review", CallClass.RUMOUR_DISTORT: "generate",
    CallClass.CASCADE_ADVISORY: "judge", CallClass.GUIDE: "write", CallClass.REFLECTION: "summarize",
    CallClass.SCENE_SUMMARY: "summarize", CallClass.RECAP: "summarize", CallClass.SAY_MY_WAY: "write",
    CallClass.WORLDGEN_HISTORY: "generate", CallClass.WORLDGEN_ACTOR: "generate",
    CallClass.WORLDGEN_OPENING: "generate", CallClass.DOSSIER_INTAKE: "extract", CallClass.PC_QUICKMAKE: "generate",
    CallClass.CHEAT_PERSONA: "write", CallClass.CHEAT_INTERPRET: "read", CallClass.WILLIS_ROAST: "write",
    CallClass.THE_VOICE: "write", CallClass.DOOM_GUARD: "judge", CallClass.AMBIENT_LINE: "generate",
    CallClass.PERSON_VOICE: "generate", CallClass.PROBE: "judge",
}

# Expected answer tokens, thinking excluded, for the classes whose regime thinks (for estimates only).
ANSWER_TOKENS: dict[CallClass, int] = {
    CallClass.NARRATION: 900, CallClass.PORTRAYAL_AUDIT: 300, CallClass.RENDER_LINT: 300,
    CallClass.SCENE_SUMMARY: 600, CallClass.RECAP: 600, CallClass.SAY_MY_WAY: 150,
    CallClass.WORLDGEN_HISTORY: 3000, CallClass.WORLDGEN_OPENING: 1200, CallClass.CHEAT_INTERPRET: 600,
    CallClass.WILLIS_ROAST: 700, CallClass.THE_VOICE: 900, CallClass.ACTOR_COGNITION: 400,
    CallClass.ACTOR_REACTION: 250,
}

BACKGROUND: frozenset[CallClass] = frozenset({CallClass.WRITEBACK, CallClass.SCENE_SUMMARY, CallClass.RECAP})
IDLE: frozenset[CallClass] = frozenset({CallClass.REFLECTION, CallClass.RUMOUR_DISTORT, CallClass.PERSON_VOICE,
                                        CallClass.CASCADE_ADVISORY})
OPTIONAL_AT_CALL: frozenset[CallClass] = frozenset({CallClass.AMBIENT_LINE, CallClass.PORTRAYAL_AUDIT,
                                                    CallClass.RENDER_LINT, CallClass.CASCADE_ADVISORY})

LABEL: dict[CallClass, str] = {
    CallClass.INTAKE: "reading your move", CallClass.ACTOR_COGNITION: "people deciding",
    CallClass.ACTOR_REACTION: "people reacting", CallClass.INTENT_REPAIR: "a decision read again",
    CallClass.WRITEBACK: "memories settling", CallClass.PORTRAYAL_AUDIT: "checking people acted like themselves",
    CallClass.NARRATION: "writing", CallClass.RENDER_LINT: "a second reading of the prose",
    CallClass.RUMOUR_DISTORT: "word getting around", CallClass.CASCADE_ADVISORY: "the world's rules, read again",
    CallClass.GUIDE: "answering your question", CallClass.REFLECTION: "the quiet hours",
    CallClass.SCENE_SUMMARY: "the journal", CallClass.RECAP: "the story so far",
    CallClass.SAY_MY_WAY: "your words in your character's voice", CallClass.WORLDGEN_HISTORY: "the world's history",
    CallClass.WORLDGEN_ACTOR: "the people of the world", CallClass.WORLDGEN_OPENING: "the opening",
    CallClass.DOSSIER_INTAKE: "reading a character's papers", CallClass.PC_QUICKMAKE: "making your character",
    CallClass.CHEAT_PERSONA: "the console", CallClass.CHEAT_INTERPRET: "the console",
    CallClass.WILLIS_ROAST: "writing", CallClass.THE_VOICE: "writing", CallClass.DOOM_GUARD: "reading your move",
    CallClass.AMBIENT_LINE: "the room talking", CallClass.PERSON_VOICE: "how someone sounds",
    CallClass.PROBE: "a probe",
}


def kind_of(request: LMRequest) -> str:
    return "narrative" if request.lane == Lane.A else "engineering"


def work_for(request: LMRequest, *, step: str, author: str | None = None) -> dict:
    cc = request.call_class
    if cc == CallClass.NARRATION:
        think = "main"
    else:
        think = "full" if request.thinking else "off"
    answer = ANSWER_TOKENS.get(cc, request.max_tokens) if request.thinking else request.max_tokens
    return {
        "kind": kind_of(request),
        "role": ROLE.get(cc, "generate"),
        "call_class": cc.value,
        "step": step,
        "author": author,
        "think": think,
        "answer": min(answer, request.max_tokens),
        "max_tokens": request.max_tokens,
        "background": cc in BACKGROUND,
        "idle": cc in IDLE,
        "optional": cc in OPTIONAL_AT_CALL,
        "label": LABEL.get(cc, "the story"),
    }
