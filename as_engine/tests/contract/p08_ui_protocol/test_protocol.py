"""The protocol's shape (P8). Rules PROTO-01..03, PROTO-08, PROTO-09 (service/game_service.py).

Every message is one envelope, handle() never raises, and every refusal is a plain sentence the
player can act on. Talemate itself is not needed: the service is tested without any websocket.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from as_engine.contracts.common import Lane
from as_engine.contracts.protocol import IN_MODELS, INBOUND_ACTIONS, OUT_MODELS, OUTBOUND_ACTIONS
from as_engine.service import game_service
from as_engine.service.game_service import GameService, get_service, out
from protocol_kit import actions, error_code, only, send

pytestmark = pytest.mark.phase(8)

SRC = Path(game_service.__file__).resolve().parent


def test_the_action_tables_are_complete():
    """Every inbound action has a model entry and a handler; every outbound one a model entry."""
    assert set(IN_MODELS) == set(INBOUND_ACTIONS)
    assert set(OUT_MODELS) == set(OUTBOUND_ACTIONS)
    for a in INBOUND_ACTIONS:
        assert callable(getattr(GameService, "on_" + a, None)), f"GameService.on_{a} is missing"


def test_the_envelope():
    """PROTO-01: {"type": "as_game", "action", "data"} with data dumped in JSON mode."""
    from as_engine.contracts.protocol import OutState
    assert out("state", OutState(screen="home")) == {"type": "as_game", "action": "state",
                                                     "data": {"screen": "home", "run_id": None, "busy": False}}
    with pytest.raises(ValueError):
        out("launch_rockets", OutState(screen="home"))


async def test_hello_on_a_fresh_install(svc):
    """No runs, both models answering -> Home."""
    welcome = only(await send(svc, "hello", client_version="1"), "welcome")
    assert welcome["screen"] == "home" and welcome["models_ok"] is True and welcome["has_runs"] is False
    import as_engine
    assert welcome["server_version"] == as_engine.__version__


async def test_hello_with_a_model_down_goes_to_connect(svc, gated, make_run):
    """A lane that does not answer -> the Connect screen (10_UI §2.1), even with runs on disk."""
    make_run()
    gated.down(Lane.B)
    welcome = only(await send(svc, "hello"), "welcome")
    assert (welcome["screen"], welcome["models_ok"], welcome["has_runs"]) == ("connect", False, True)


async def test_get_state_without_a_run(svc):
    assert only(await send(svc, "get_state"), "state") == {"screen": "home", "run_id": None, "busy": False}


async def test_unknown_action_and_bad_request_are_error_replies(svc):
    """PROTO-03 / PROTO-08: never an exception, always a plain sentence."""
    r = await send(svc, "launch_rockets")
    assert actions(r) == ["error"] and error_code(r) == "unknown_action"
    r = await svc.handle({"type": "as_game"})
    assert r[0]["action"] == "error" and r[0]["data"]["code"] == "unknown_action"
    r = await send(svc, "models_test", lane="C")
    assert error_code(r) == "bad_request"
    assert "lane" in only(r, "error")["message"]
    r = await send(svc, "run_save", slot_name="")
    assert error_code(r) == "bad_request"


async def test_a_fault_inside_a_handler_is_an_internal_error(svc, monkeypatch):
    async def boom(msg):
        raise KeyError("act_000002")
    monkeypatch.setattr(svc, "on_runs_list", boom)
    r = await send(svc, "runs_list")
    data = only(r, "error")
    assert data["code"] == "internal" and data["recoverable"] is True
    assert data["message"] == game_service.INTERNAL
    assert "act_000002" not in data["message"], "no internal ids in a message (UI-CLARITY-02)"


async def test_a_later_phase_answers_not_built_yet(svc, monkeypatch):
    """PROTO-09: a handler that is still a stub for a later phase answers not_built_yet."""
    async def stub(msg):
        raise NotImplementedError("P12")
    monkeypatch.setattr(svc, "on_worlds_list", stub)
    r = await send(svc, "worlds_list")
    assert only(r, "error") == {"code": "not_built_yet", "message": game_service.NOT_BUILT, "recoverable": True}


def test_every_message_constant_is_a_plain_sentence():
    """PROTO-08 / UI-CLARITY-06: at least 20 characters, a full stop, no engine words."""
    import re
    banned = re.compile(r"\b(packet|affordance|percept|lod|claim|intent|handle|lane|schema|token|stage|event|actor|"
                        r"dossier)s?\b", re.I)
    names = [n for n in dir(game_service) if n.isupper() and isinstance(getattr(game_service, n), str)]
    assert len(names) >= 20
    for n in names:
        text = getattr(game_service, n)
        assert len(text) >= 20, n
        assert text.rstrip().endswith((".", "?")), n
        assert not banned.search(text), (n, text)


def test_the_service_is_a_process_singleton(cfg, gated, monkeypatch):
    """PROTO-02: the first call creates it; later calls return it and ignore their arguments."""
    monkeypatch.setattr(game_service, "_SERVICE", None)
    a = get_service(cfg, gated)
    b = get_service(None, None)
    assert a is b and isinstance(a, GameService) and a.config is cfg and a.transport is gated
    monkeypatch.setattr(game_service, "_SERVICE", None)
    assert get_service(cfg, gated) is not a


async def test_a_subscriber_that_fails_is_dropped(svc):
    """A connection that has gone away must not stop pushes reaching the others."""
    got = []

    async def dead(msg):
        raise ConnectionError("gone")

    async def alive(msg):
        got.append(msg)
    svc.unsubscribe(svc.collect)
    svc.subscribe(dead)
    svc.subscribe(alive)
    msg = out("state", game_service_state())
    await svc.push(msg)
    await svc.push(msg)
    assert got == [msg, msg]
    svc.unsubscribe(dead)       # already gone: nothing happens
    svc.unsubscribe(alive)


def game_service_state():
    from as_engine.contracts.protocol import OutState
    return OutState(screen="home")


def test_the_guide_and_the_view_cannot_see_the_truth():
    """UI-SKULL-01: neither the guide nor the service imports the truth accessor."""
    for name in ("guide.py", "game_service.py", "view.py"):
        tree = ast.parse((SRC / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = (node.module or "")
                assert "truth" not in mod and not any(a.name == "truth" for a in node.names), (name, mod)
            if isinstance(node, ast.Import):
                assert not any("truth" in a.name for a in node.names), name
