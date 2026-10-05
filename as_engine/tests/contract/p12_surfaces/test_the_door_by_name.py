"""The door by name (D-237). cheats/interpret.py (the 'door' step's outcome); cheats console names.

Opening a door with plain words told the Boss "The prt_000001 is open now." — the console's names knew people,
places, groups and things, never a door.
"""

from __future__ import annotations

import asyncio

import pytest

from as_engine.cheats import commands as cheats
from as_engine.cheats import interpret
from as_engine.contracts.common import CallClass

pytestmark = pytest.mark.phase(12)


def plain(s, text):
    cheats.activate(s)
    return asyncio.run(interpret.run(s, text))


def plan(*ops):
    return {"ops": list(ops), "clarify": None, "summary": ""}


def test_the_door_by_name(night, fake):
    w, s = night
    fake.script(CallClass.CHEAT_INTERPRET,
                lambda r: plan({"op": "door", "target": next(d.handle for d in r.context.scene.doors if d.label == "office door"),
                                "state": "open"}))
    r = plain(s, "Open the office door")
    assert r.ok and r.detail == "The office door is open now."
