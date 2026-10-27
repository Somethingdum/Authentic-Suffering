"""Stop while a world is being made (P13, D-299). Rules HOST-16, HOST-25 (host/service.py cancel, begin).

The host may stop a world's creation at any moment: the request that began it answers 'cancelled',
nothing of the half-made world is kept, and the engine is ready for the next request.
"""

from __future__ import annotations

import asyncio

import pytest
from test_bridge import Wire, start

pytestmark = pytest.mark.phase(13)


async def test_stop_reaches_a_world_being_made(monkeypatch, hcfg):
    w = Wire(monkeypatch, hold={"worldgen_history", "worldgen_actor", "worldgen_opening"})
    task = await start(w, hcfg)
    begin = w.send(type="begin", pc_ref="core:pc/owen_marsh",
                   settings={"world_detail": "gotta_go_to_work_soon", "seed": 7, "era": "established"})
    pump = asyncio.get_running_loop().create_task(w.until(begin))
    await asyncio.wait_for(w.held.wait(), 60)
    stop = await w.until(w.send(type="cancel"))
    assert stop["type"] == "result"
    got = await asyncio.wait_for(pump, 60)
    assert (got["type"], got["code"]) == ("error", "cancelled")
    nothing = await w.until(w.send(type="save"))
    assert (nothing["type"], nothing["code"]) == ("error", "no_run"), "nothing of the half-made world is kept"
    w.release.set()
    await w.until(w.send(type="close"))
    await asyncio.wait_for(task, 10)
