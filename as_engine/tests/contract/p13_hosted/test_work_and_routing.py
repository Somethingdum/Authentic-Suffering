"""What every call is, and a client that never decides what is available (P13, D-299). Rules HOST-04,
HOST-05, HOST-10..HOST-13, LANE-12 (as_engine/host/work.py, host/transport.py, lanes/client.py,
lanes/calllog.py).

Hosted, the engine names no model: each call says what kind of work it is — the engine's lane A is
its Writer, so narrative work; lane B its Clerk, so engineering work — and the host decides which
model answers. A host's refusal never marks a lane down, and a call it leaves out for time answers
exactly as an ablated call does.
"""

from __future__ import annotations

import re

import pytest

from as_engine.contracts.common import CallClass, Lane
from as_engine.contracts.lanes import ChatMessage, LMRequest
from as_engine.host import work as W
from as_engine.lanes.errors import CallSkipped, LaneRefused

pytestmark = pytest.mark.phase(13)


def req(cc: CallClass, lane: Lane = Lane.B, thinking: bool = False, max_tokens: int = 400, actor: str | None = None, T: int = 1):
    return LMRequest(call_class=cc, lane=lane, messages=[ChatMessage(role="system", content="s"), ChatMessage(role="user", content="u")],
                     thinking=thinking, max_tokens=max_tokens, actor_id=actor, turn_index=T)


def test_every_call_class_is_described():
    for cc in CallClass:
        assert cc in W.ROLE and cc in W.LABEL, cc


def test_the_kind_is_the_engines_own_role():
    assert W.work_for(req(CallClass.ACTOR_COGNITION, Lane.A), step="focus:0:x")["kind"] == "narrative"
    assert W.work_for(req(CallClass.ACTOR_COGNITION, Lane.B), step="mind:0:x")["kind"] == "engineering"
    w = W.work_for(req(CallClass.NARRATION, Lane.A, thinking=True, max_tokens=8192), step="write")
    assert (w["kind"], w["role"], w["think"], w["max_tokens"]) == ("narrative", "write", "main", 8192)
    assert w["answer"] == W.ANSWER_TOKENS[CallClass.NARRATION]
    w = W.work_for(req(CallClass.WRITEBACK), step="memory")
    assert (w["think"], w["answer"], w["background"], w["idle"], w["optional"]) == ("off", 400, True, False, False)
    assert W.work_for(req(CallClass.REFLECTION), step="quiet")["idle"] is True
    assert W.work_for(req(CallClass.RENDER_LINT, thinking=True), step="judge")["optional"] is True


def test_labels_name_nobody_and_never_get_ahead_of_the_story():
    for cc, label in W.LABEL.items():
        assert not re.search(r"\b[A-Z][a-z]+\b", label), (cc, label)       # no proper names
        assert "doom" not in label.lower() and "voice" not in label.lower().replace("your character's voice", ""), (cc, label)


async def test_a_routed_client_never_marks_a_lane_down(config):
    from as_engine.lanes.client import LaneClient

    class Refusing:
        routed = True

        async def send(self, lane, request):
            raise LaneRefused("no model the host may use")

        async def list_models(self, lane_id, lane):
            raise AssertionError("a routed client asks nothing about models")

        async def health(self, lane_id, lane):
            raise AssertionError("a routed client probes nothing")
    c = LaneClient(config, Refusing())
    assert c.routed
    r = await c.call(req(CallClass.INTAKE))
    assert (r.parse_status, r.error) == ("lane_error", "no model the host may use")
    assert not c.is_down(Lane.B)
    c.mark_down(Lane.A)
    assert not c.is_down(Lane.A)
    assert await c.refresh_health() == {Lane.A: True, Lane.B: True}
    await c.check_models()


async def test_a_skipped_call_answers_like_an_ablated_one(config):
    from as_engine.lanes.client import LaneClient
    seen = []

    class Skipping:
        routed = True

        async def send(self, lane, request):
            raise CallSkipped("not enough time left")
    c = LaneClient(config, Skipping(), on_call=lambda q, r: seen.append(r.parse_status))
    r = await c.call(req(CallClass.AMBIENT_LINE))
    assert (r.parse_status, r.error) == ("cancelled", "skipped: not enough time left") and seen == ["cancelled"]


async def test_a_replayed_skip_is_a_skip_again(config, store):
    from as_engine.lanes.calllog import ReplayTransport, record
    from as_engine.lanes.client import LaneClient
    from as_engine.contracts.lanes import LMResponse
    q = req(CallClass.AMBIENT_LINE, T=1)
    with store.transaction() as tx:
        record(tx, q, LMResponse(call_class=q.call_class, lane=q.lane, parse_status="cancelled", error="skipped"))
    r = await LaneClient(config, ReplayTransport(store, routed=True)).call(q)
    assert r.parse_status == "cancelled"


async def test_the_transport_reads_no_lane_and_knows_no_model(config):
    from as_engine.contracts.settings import LaneConfig
    from as_engine.host.transport import HostTransport
    sent = []

    class Link:
        async def request(self, kind, payload):
            sent.append((kind, payload))
            return {"text": "hello", "model": "whatever-the-host-ran"}
    t = HostTransport(Link())
    nonsense = LaneConfig(name="x", base_url="http://localhost:1/v1", model="not-a-model", api_key="k")
    r = await t.send(nonsense, req(CallClass.GUIDE, T=2))
    kind, p = sent[0]
    assert kind == "model.call" and p["turn_index"] == 2 and p["messages"][0] == {"role": "system", "content": "s"}
    assert "not-a-model" not in str(p) and "localhost" not in str(p) and "api_key" not in str(p)
    assert r.text == "hello" and r.model == "host"          # IFACE-01: the engine never keeps which model it was


async def test_reviews_name_their_author_and_a_stopped_write_is_never_drafted_again():
    from as_engine.host.transport import HostTransport
    sent = []

    class Link:
        async def request(self, kind, payload):
            sent.append((kind, payload))
            if kind == "write":
                return {"failed": "stopped", "why": "stopped"}
            return {"text": "{}"}
    t = HostTransport(Link())
    await t.send(None, req(CallClass.ACTOR_COGNITION, Lane.A, actor="act_a", T=3))
    with pytest.raises(LaneRefused):
        await t.send(None, req(CallClass.NARRATION, Lane.A, T=3))
    await t.send(None, req(CallClass.PORTRAYAL_AUDIT, actor="act_a", T=3))
    await t.send(None, req(CallClass.RENDER_LINT, T=3))
    decision, write, audit, judge = (p for _k, p in sent)
    assert audit["work"]["author"] == decision["call_id"] and audit["work"]["role"] == "review"
    assert judge["work"]["author"] == write["call_id"] and write["attempt"] == 1
    with pytest.raises(LaneRefused):
        await t.send(None, req(CallClass.NARRATION, Lane.A, T=3))
    assert sum(k == "write" for k, _p in sent) == 1, "a stopped turn is told plainly, not drafted again"


async def test_recorded_answers_are_used_before_asking():
    from as_engine.host.transport import HostTransport
    from as_engine.lanes.calllog import request_hash

    class Link:
        async def request(self, kind, payload):
            raise AssertionError("asked again")
    q = req(CallClass.INTAKE, T=4)
    t = HostTransport(Link(), recorded=[{"turn_index": 4, "request_hash": request_hash(q), "result": {"text": "kept"}}])
    assert (await t.send(None, q)).text == "kept"
