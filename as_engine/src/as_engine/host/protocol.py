"""The bridge protocol between a host and the hosted engine (D-299). Rule HOST-01.

HOST-01 framing. One JSON object per line, UTF-8, ending in "\\n", on the engine process's stdin (from
the host) and stdout (to it); stderr carries only the engine's own error lines, never story text.
Every object has "v": PROTOCOL and "type". A request has an "id" (the host's start with "h", the
engine's with "e"); its answer is {"v", "type": "result", "re": that id, ...} or {"v", "type":
"error", "re": that id, "code", "message"}; a notice has no id and gets no answer.
Binary payloads (worlds) are base64 strings.

The host's requests (HOST_REQUESTS, each validated by its model below; a bad one -> error
'bad_request', an unknown type -> 'unknown_type'):
  hello · menu · begin · open · save · turn · compose · cancel · view · story · settings_get ·
  settings_set · code_enter · cheat_dictionary · death_reveal · quiet · fork · close · ping
The engine's requests, which the host answers: model.call · write · budget.declare · budget.may.
The engine's notices: progress {stage, label, pct} · begin.seed {seed}.
as_engine.host.service says what each request does and answers; as_engine.host.transport says
what model.call and write carry; as_engine.host.governor what the budget messages carry.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Literal

from pydantic import Field

from ..contracts.common import Strict

PROTOCOL = 1

HOST_REQUESTS = ("hello", "menu", "begin", "open", "save", "turn", "compose", "cancel", "view", "story",
                 "settings_get", "settings_set", "code_enter", "cheat_dictionary", "death_reveal", "quiet", "fork",
                 "close", "ping")
ENGINE_REQUESTS = ("model.call", "write", "budget.declare", "budget.may")
ENGINE_NOTICES = ("progress", "begin.seed")


class Recorded(Strict):
    """An answer the host gave before (HOST-13): replayed instead of asking again."""

    turn_index: int = 0
    request_hash: str
    result: dict[str, Any]


class HHello(Strict):
    host: str = ""


class HEmpty(Strict):
    pass


class HBegin(Strict):
    pc_ref: str
    settings: dict[str, Any] = Field(default_factory=dict)
    answers: list[Recorded] = Field(default_factory=list)


class HOpen(Strict):
    world: str = Field(description="base64 of a world envelope (as_engine.host.world)")


class HTurn(Strict):
    mode: Literal["do", "say", "ask"] = "do"
    text: str = ""
    suggestion_ref: str | None = None
    addressee_refs: list[str] = Field(default_factory=list)
    tier: int = Field(default=3, ge=1, le=5)
    focus: int | None = Field(default=None, ge=0, le=12)
    answers: list[Recorded] = Field(default_factory=list)
    decisions: dict[str, bool] = Field(default_factory=dict)


class HCompose(Strict):
    act: str = ""
    say: str = ""
    cheat: str = ""
    to: list[str] = Field(default_factory=list)
    tier: int = Field(default=3, ge=1, le=5)
    focus: int | None = Field(default=None, ge=0, le=12)
    answers: list[Recorded] = Field(default_factory=list)
    decisions: dict[str, bool] = Field(default_factory=dict)


class HSettingsSet(Strict):
    patch: dict[str, Any]


class HCode(Strict):
    code: str


class HQuiet(Strict):
    answers: list[Recorded] = Field(default_factory=list)


class HFork(Strict):
    base: str = Field(description="base64 of the kept world the fork starts from")
    head: str = Field(description="base64 of the branch's latest world: its call log holds every answer")
    turn: int = Field(ge=0)


MODELS: dict[str, type[Strict]] = {
    "hello": HHello, "menu": HEmpty, "begin": HBegin, "open": HOpen, "save": HEmpty, "turn": HTurn,
    "compose": HCompose, "cancel": HEmpty, "view": HEmpty, "story": HEmpty, "settings_get": HEmpty,
    "settings_set": HSettingsSet, "code_enter": HCode, "cheat_dictionary": HEmpty, "death_reveal": HEmpty,
    "quiet": HQuiet, "fork": HFork, "close": HEmpty, "ping": HEmpty,
}


def encode(obj: dict) -> bytes:
    return (json.dumps({"v": PROTOCOL, **obj}, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def decode(line: bytes) -> dict:
    obj = json.loads(line.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("not an object")
    return obj


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"), validate=True)
