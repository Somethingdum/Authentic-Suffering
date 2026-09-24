"""P8 test kit (PROTECTED): send a message, check every envelope, pick replies apart."""

from __future__ import annotations

import asyncio
import re

from as_engine.contracts.protocol import OUT_MODELS, OUTBOUND_ACTIONS

TRACE = re.compile(r"Traceback|File \"|line \d+, in ")


def check(msg: dict) -> dict:
    """PROTO-01: one envelope, a known action, data valid for its model; PROTO-08 for errors."""
    assert set(msg) == {"type", "action", "data"}, msg
    assert msg["type"] == "as_game"
    assert msg["action"] in OUTBOUND_ACTIONS, msg["action"]
    model = OUT_MODELS[msg["action"]]
    if model is not None:
        model.model_validate(msg["data"])
    if msg["action"] == "error":
        text = msg["data"]["message"]
        assert len(text) >= 20 and not TRACE.search(text), f"PROTO-08: {text!r}"
    return msg


async def send(svc, action: str, **fields) -> list[dict]:
    replies = await svc.handle({"type": "as_game", "action": action, **fields})
    assert isinstance(replies, list)
    for r in replies:
        check(r)
    return replies


def actions(msgs) -> list[str]:
    return [m["action"] for m in msgs]


def only(msgs, action: str) -> dict:
    """The data of the single message with this action."""
    found = [m["data"] for m in msgs if m["action"] == action]
    assert len(found) == 1, f"expected one {action}, got {actions(msgs)}"
    return found[0]


def error_code(msgs) -> str:
    return only(msgs, "error")["code"]


async def wait_for(pred, timeout: float = 30.0):
    """Wait (yielding to the running turn) until pred() is true."""
    async def loop():
        while not pred():
            await asyncio.sleep(0.005)
    await asyncio.wait_for(loop(), timeout)


# P10 added the loading bar's pushes (service.progress): P8's sequence checks read the pushes
# without them; the bar's own tests read them with bar_after().
BAR_ACTIONS = frozenset({"progress_plan", "progress", "progress_done"})


def pushed_after(svc, start: int) -> list[dict]:
    """Every push since ``start``, each checked (PROTO-01) — the loading bar's left out."""
    for m in svc.pushed[start:]:
        check(m)
    return [m for m in svc.pushed[start:] if m["action"] not in BAR_ACTIONS]


def bar_after(svc, start: int) -> list[dict]:
    """The loading bar's pushes since ``start`` (P10), each checked."""
    for m in svc.pushed[start:]:
        check(m)
    return [m for m in svc.pushed[start:] if m["action"] in BAR_ACTIONS]
