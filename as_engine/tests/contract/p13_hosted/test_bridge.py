"""The bridge a host starts (P13, D-299). Rules HOST-01, HOST-24..HOST-27, HOST-14, HOST-15, HOST-20
(host/bridge.py, host/protocol.py, as_engine/bridge.py).

JSON lines on a child process's pipes. Requests either way carry an id, answers name it; the host's
requests run one at a time, but Stop and ping get through at once. The process is sealed before
anything else runs, and nothing of the story reaches its error stream.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys

import pytest
from host_kit import REPO_PACKS, Pipe

from as_engine.host.protocol import b64, decode, encode

pytestmark = pytest.mark.phase(13)


class Wire:
    """The host's end of an in-process bridge: lines from the engine arrive on ``inbox``."""

    def __init__(self, monkeypatch, *, hold=frozenset()):
        from as_engine.host.transport import HostTransport
        from as_engine.lanes.calllog import request_hash
        from as_engine.testing.fake_lm import FakeTransport
        self.pipe = Pipe()
        self.inbox: asyncio.Queue = asyncio.Queue()
        self.fake = FakeTransport()
        self.requests: dict[str, list] = {}
        self.hold = set(hold)
        self.held = asyncio.Event()
        self.release = asyncio.Event()
        self._n = 0
        orig = HostTransport.send
        requests = self.requests

        async def send(t, lane, request):
            requests.setdefault(request_hash(request), []).append(request)
            return await orig(t, lane, request)
        monkeypatch.setattr(HostTransport, "send", send)

    def write_line(self, b: bytes) -> None:
        self.inbox.put_nowait(decode(b))

    def send(self, **obj) -> str:
        self._n += 1
        rid = obj.pop("id", f"h{self._n}")
        self.pipe.send(encode({"id": rid, **obj}))
        return rid

    async def answer_engine(self, msg: dict) -> None:
        kind = msg["type"]
        if kind in ("model.call", "write"):
            if msg["work"]["call_class"] in self.hold:
                self.held.set()
                await self.release.wait()
            req = self.requests[msg["request_hash"]].pop(0)
            r = await self.fake.send(None, req)
            self.pipe.send(encode({"type": "result", "re": msg["id"], "text": r.text}))
        elif kind == "budget.declare":
            self.pipe.send(encode({"type": "result", "re": msg["id"]}))
        elif kind == "budget.may":
            self.pipe.send(encode({"type": "result", "re": msg["id"], "may": True}))

    async def until(self, rid: str, seen: list | None = None) -> dict:
        while True:
            msg = await asyncio.wait_for(self.inbox.get(), 60)
            if seen is not None:
                seen.append(msg)
            if msg.get("re") == rid and msg["type"] in ("result", "error"):
                return msg
            if msg["type"] in ("model.call", "write", "budget.declare", "budget.may"):
                asyncio.get_running_loop().create_task(self.answer_engine(msg))


@pytest.fixture
def wire(monkeypatch):
    return Wire(monkeypatch)


async def start(wire, hcfg):
    from as_engine.host.bridge import serve
    return asyncio.get_running_loop().create_task(serve(hcfg, read_lines=wire.pipe, write_line=wire.write_line))


async def test_the_protocol_basics(wire, hcfg):
    task = await start(wire, hcfg)
    r = await wire.until(wire.send(type="hello", host="tests"))
    assert r["type"] == "result" and r["protocol"] == 1 and r["world_format"] == 1 and "sealed" in r
    assert (await wire.until(wire.send(type="ping")))["pong"] is True
    wire.pipe.send(b"this is not json\n")
    bad = await asyncio.wait_for(wire.inbox.get(), 10)
    assert (bad["type"], bad["re"], bad["code"]) == ("error", None, "bad_json")
    r = await wire.until(wire.send(type="dance"))
    assert (r["type"], r["code"]) == ("error", "unknown_type")
    r = await wire.until(wire.send(type="turn", tier=9))
    assert (r["type"], r["code"]) == ("error", "bad_request") and "tier" in r["message"]
    r = await wire.until(wire.send(type="turn", text="hello"))
    assert (r["type"], r["code"]) == ("error", "no_run")
    await wire.until(wire.send(type="close"))
    assert await asyncio.wait_for(task, 10) == 0


async def test_a_turn_over_the_wire(wire, hcfg, world0):
    task = await start(wire, hcfg)
    assert (await wire.until(wire.send(type="open", world=b64(world0))))["type"] == "result"
    seen = []
    r = await wire.until(wire.send(type="turn", mode="do", text="I look over the fence.", tier=3), seen)
    assert r["type"] == "result" and r["turn"] == 1 and r["world"]
    kinds = {m["type"] for m in seen}
    assert {"model.call", "write", "budget.declare", "budget.may", "progress"} <= kinds
    prog = [m for m in seen if m["type"] == "progress"]
    assert all(set(m) >= {"stage", "label", "pct"} for m in prog) and all("act_" not in str(m["label"]) for m in prog)
    assert any(m["action"] == "turn_result" for m in r["messages"])
    await wire.until(wire.send(type="close"))
    await asyncio.wait_for(task, 10)


async def test_stop_reaches_a_turn_before_it_is_locked_in(monkeypatch, hcfg, world0):
    w = Wire(monkeypatch, hold={"actor_cognition"})
    task = await start(w, hcfg)
    await w.until(w.send(type="open", world=b64(world0)))
    turn = w.send(type="turn", mode="do", text="I look over the fence.", tier=3)
    pump = asyncio.get_running_loop().create_task(w.until(turn))
    await asyncio.wait_for(w.held.wait(), 30)
    stop = w.send(type="cancel")
    # the turn's answer and the cancel's both come back; the world did not move
    got = await asyncio.wait_for(pump, 60)
    assert got["type"] == "result"
    save = await w.until(w.send(type="save"))
    assert save["turn"] == 0, "nothing happened: a turn stopped before stage 12 leaves the world as it was"
    w.release.set()
    await w.until(w.send(type="close"))
    await asyncio.wait_for(task, 10)
    assert stop


def test_the_real_process(hcfg, world0, tmp_path):
    """python -I -m as_engine.bridge: sealed, answers, plays a turn whose every call the host
    refuses, writes no story text to stderr, exits 0 on close."""
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "SYSTEMROOT", "HOME", "TMPDIR", "TEMP", "TMP")}
    p = subprocess.Popen([sys.executable, "-I", "-m", "as_engine.bridge", "--content", str(REPO_PACKS)],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=tmp_path, env=env)
    n = 0

    def send(**obj):
        nonlocal n
        n += 1
        p.stdin.write(encode({"id": f"h{n}", **obj}))
        p.stdin.flush()
        return f"h{n}"

    def until(rid):
        while True:
            line = p.stdout.readline()
            assert line, p.stderr.read().decode()
            msg = json.loads(line)
            if msg.get("re") == rid and msg["type"] in ("result", "error"):
                return msg
            if msg["type"] in ("model.call", "write"):
                p.stdin.write(encode({"type": "result", "re": msg["id"], "failed": "refused", "why": "no model"}))
                p.stdin.flush()
            elif msg["type"] in ("budget.declare", "budget.may"):
                p.stdin.write(encode({"type": "result", "re": msg["id"], "may": True}))
                p.stdin.flush()
    try:
        hello = until(send(type="hello"))
        assert hello["sealed"] is True, "the process cannot reach the network"
        menu = until(send(type="menu"))
        assert menu["pcs"] and "properties" in menu["settings"]
        assert until(send(type="open", world=b64(world0)))["type"] == "result"
        r = until(send(type="turn", mode="say", text='"Zebrawood. Nobody touches it."', tier=2))
        assert r["type"] == "result"
        assert until(send(type="close"))["type"] == "result"
        assert p.wait(30) == 0
        err = p.stderr.read().decode()
        assert "Zebrawood" not in err and "zebrawood" not in err.lower()
        assert list(tmp_path.iterdir()) == []
    finally:
        if p.poll() is None:
            p.kill()
