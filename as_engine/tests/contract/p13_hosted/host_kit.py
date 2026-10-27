"""Helpers for the hosted-engine tests (PROTECTED; D-299)."""

from __future__ import annotations

import queue
from pathlib import Path

TESTS = Path(__file__).resolve().parents[2]
REPO_PACKS = TESTS.parent.parent / "as_content" / "packs"
CORE = REPO_PACKS / "core"
SCENARIOS = TESTS / "fixtures" / "scenarios"
FIXTURE_PACKS = TESTS / "fixtures" / "packs"


def scenario_world(cfg, name: str = "metal_fence") -> bytes:
    from as_engine.host import world as W
    from as_engine.testing.fake_lm import FakeTransport
    from as_engine.testing.scenario import load_scenario
    w = load_scenario(SCENARIOS / f"{name}.yaml", packs_root=FIXTURE_PACKS, core_pack_dir=CORE, transport=FakeTransport())
    try:
        return W.pack(w.store, W.packs_for(cfg, [CORE]))
    finally:
        w.store.close()


class FakeHost:
    """A host for tests. model.call / write are answered by the engine's fake model; budget.may by
    ``may(step)``; every request, answer and notice is kept. ``fail`` maps a call class value to a
    result dict to answer with instead (e.g. {"failed": "refused", "why": "no model"})."""

    def __init__(self, may=None, fail=None):
        from as_engine.testing.fake_lm import FakeTransport
        self.fake = FakeTransport()
        self.may_fn = may or (lambda step: True)
        self.fail = dict(fail or {})
        self.requests: dict[str, list] = {}
        self.calls: list[tuple[str, dict]] = []          # (kind, payload) of model.call and write
        self.declared: list[dict] = []
        self.asked: list[str] = []
        self.notices: list[tuple[str, dict]] = []
        self.results: list[dict] = []                     # what a host would record (HOST-13)

    async def request(self, kind: str, payload: dict) -> dict:
        if kind in ("model.call", "write"):
            self.calls.append((kind, payload))
            req = self.requests[payload["request_hash"]].pop(0)
            res = self.fail.get(payload["work"]["call_class"])
            if res is None:
                r = await self.fake.send(None, req)
                res = {"text": r.text, "reasoning": r.reasoning, "prompt_tokens": r.prompt_tokens,
                       "completion_tokens": r.completion_tokens}
            self.results.append({"turn_index": payload["turn_index"], "request_hash": payload["request_hash"], "result": res})
            return res
        if kind == "budget.declare":
            self.declared.extend(payload["steps"])
            return {}
        if kind == "budget.may":
            self.asked.append(payload["step"])
            return {"may": bool(self.may_fn(payload["step"]))}
        raise AssertionError(f"unexpected engine request {kind}")

    def notify(self, kind: str, payload: dict) -> None:
        self.notices.append((kind, payload))

    def works(self, call_class: str) -> list[dict]:
        return [p["work"] for _k, p in self.calls if p["work"]["call_class"] == call_class]


def service(cfg, h):
    from as_engine.host.service import HostService
    from as_engine.lanes.calllog import request_hash
    svc = HostService(cfg, h)
    orig = svc.host_transport.send

    async def send(lane, request):
        h.requests.setdefault(request_hash(request), []).append(request)
        return await orig(lane, request)
    svc.host_transport.send = send
    return svc


async def call(svc, kind: str, **fields) -> dict:
    from as_engine.host.protocol import MODELS
    return await svc.handle(kind, MODELS[kind].model_validate(fields))


def actions(got: dict) -> list[str]:
    return [m["action"] for m in got.get("messages", [])]


def only(got: dict, action: str) -> dict:
    found = [m["data"] for m in got.get("messages", []) if m["action"] == action]
    assert len(found) == 1, (action, actions(got))
    return found[0]


def header(world_b64: str) -> dict:
    from as_engine.host import world as W
    from as_engine.host.protocol import unb64
    return W.header_of(unb64(world_b64))


class Pipe:
    """A blocking line iterator a test writes to (the bridge's stdin in-process)."""

    def __init__(self):
        self.q: queue.Queue = queue.Queue()

    def send(self, line: bytes | None) -> None:
        self.q.put(line)

    def __iter__(self):
        while True:
            line = self.q.get()
            if line is None:
                return
            yield line


def same_world(a_b64: str, b_b64: str) -> bool:
    """Every world table equal, and meta equal but for created_at_real (the one wall-clock value a
    store keeps, kernel.store.create)."""
    from as_engine.host import world as W
    from as_engine.host.protocol import unb64
    from as_engine.kernel.hashing import table_digest
    from as_engine.kernel.ownership import WORLD_HASH_EXCLUDED
    _ha, a = W.unpack(unb64(a_b64))
    _hb, b = W.unpack(unb64(b_b64))
    try:
        tables = [r[0] for r in a.query("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                                        "AND name NOT LIKE 'episodes_fts%' ORDER BY name")]
        for t in tables:
            if t in WORLD_HASH_EXCLUDED or t == "meta":
                continue
            if table_digest(a, t) != table_digest(b, t):
                return False
        ma = {r[0]: r[1] for r in a.query("SELECT key, value FROM meta") if r[0] != "created_at_real"}
        mb = {r[0]: r[1] for r in b.query("SELECT key, value FROM meta") if r[0] != "created_at_real"}
        return ma == mb
    finally:
        a.close()
        b.close()
