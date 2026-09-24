"""The Authentic Suffering plugin inside Talemate (P8). Rules PROTO-01, PROTO-02.

Protected. Runs in Talemate's own environment (the fork root, Talemate's .venv with as_engine
installed):

    python -m pytest tests/test_as_game_plugin.py -q -o addopts=""

(`-o addopts=""` drops Talemate's `-n auto`, which needs pytest-xdist.) Checked against Talemate
0.39.0: `Plugin.__init__` stores `websocket_handler` and calls `connect()`; `WebsocketHandler.route`
sends every message whose `type` is a key of `self.routes` to that plugin's `handle`; a plugin
talks back through `websocket_handler.queue_put(dict)`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from talemate.server import as_game_plugin
from talemate.server.websocket_plugin import Plugin

from as_engine.contracts.settings import EngineConfig
from as_engine.service import game_service
from as_engine.testing.fake_lm import FakeTransport

ROOT = Path(__file__).resolve().parents[1]
WEBSOCKET_SERVER = ROOT / "src" / "talemate" / "server" / "websocket_server.py"


class _MockWebsocketHandler:
    """What a Talemate plugin sees of the websocket: queue_put and scene."""

    def __init__(self):
        self.messages: list[dict] = []
        self.scene = None

    def queue_put(self, data):
        self.messages.append(data)


class _FakeService:
    def __init__(self):
        self.subscribers = []
        self.handled = []

    def subscribe(self, fn):
        self.subscribers.append(fn)

    def unsubscribe(self, fn):
        self.subscribers.remove(fn)

    async def handle(self, message):
        self.handled.append(message)
        return [{"type": "as_game", "action": "state", "data": {"screen": "home"}},
                {"type": "as_game", "action": "runs", "data": {"runs": []}}]


@pytest.fixture
def fake_service(monkeypatch):
    svc = _FakeService()
    monkeypatch.setattr(as_game_plugin, "get_service", lambda *a, **k: svc)
    monkeypatch.setattr(as_game_plugin, "load_engine_config", lambda *a, **k: EngineConfig())
    monkeypatch.setattr(as_game_plugin, "HttpTransport", lambda *a, **k: FakeTransport())
    return svc


@pytest.fixture
def real_service(monkeypatch, tmp_path):
    """The real GameService singleton, with the fake model transport and runs in tmp_path."""
    monkeypatch.setattr(game_service, "_SERVICE", None)
    cfg = EngineConfig(runs_dir=str(tmp_path / "runs"))
    monkeypatch.setattr(as_game_plugin, "load_engine_config", lambda *a, **k: cfg)
    monkeypatch.setattr(as_game_plugin, "HttpTransport", lambda *a, **k: FakeTransport())
    yield
    monkeypatch.setattr(game_service, "_SERVICE", None)


def _routes_dict(tree: ast.Module) -> ast.Dict:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "WebsocketHandler":
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Assign) and len(sub.targets) == 1
                        and ast.unparse(sub.targets[0]) == "self.routes" and isinstance(sub.value, ast.Dict)):
                    return sub.value
    raise AssertionError("WebsocketHandler.__init__ no longer assigns a dict to self.routes")


def test_the_route_is_registered_in_the_websocket_handler():
    """02 §4.1: websocket_server.py imports as_game_plugin and adds exactly one route for it."""
    tree = ast.parse(WEBSOCKET_SERVER.read_text(encoding="utf-8"))
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == "talemate.server"
                for a in n.names}
    assert "as_game_plugin" in imported, "add as_game_plugin to the `from talemate.server import (...)` list"
    routes = _routes_dict(tree)
    pairs = [(ast.unparse(k), ast.unparse(v)) for k, v in zip(routes.keys, routes.values)]
    assert ("as_game_plugin.AsGamePlugin.router", "as_game_plugin.AsGamePlugin(self)") in pairs
    assert sum("as_game_plugin" in k or "as_game_plugin" in v for k, v in pairs) == 1


def test_the_plugin_is_a_talemate_plugin_on_router_as_game():
    assert issubclass(as_game_plugin.AsGamePlugin, Plugin)
    assert as_game_plugin.AsGamePlugin.router == "as_game"


async def test_every_reply_is_queued_in_order(fake_service):
    """The plugin forwards the whole message and queues each reply, in order, untouched (PROTO-01)."""
    ws = _MockWebsocketHandler()
    plugin = as_game_plugin.AsGamePlugin(ws)
    msg = {"type": "as_game", "action": "get_state"}
    await plugin.handle(msg)
    assert fake_service.handled == [msg]
    assert ws.messages == [{"type": "as_game", "action": "state", "data": {"screen": "home"}},
                           {"type": "as_game", "action": "runs", "data": {"runs": []}}]


async def test_pushes_reach_the_socket_until_disconnect(fake_service):
    ws = _MockWebsocketHandler()
    plugin = as_game_plugin.AsGamePlugin(ws)
    assert len(fake_service.subscribers) == 1, "connect() subscribes exactly once"
    push = {"type": "as_game", "action": "turn_progress", "data": {"label": "Thinking", "pct": 40}}
    await fake_service.subscribers[0](push)
    assert ws.messages == [push]
    plugin.disconnect()
    assert fake_service.subscribers == [], "disconnect() unsubscribes"


async def test_hello_round_trips_through_the_real_service(real_service):
    ws = _MockWebsocketHandler()
    plugin = as_game_plugin.AsGamePlugin(ws)
    await plugin.handle({"type": "as_game", "action": "hello", "client_version": "test"})
    (reply,) = [m for m in ws.messages if m.get("action") == "welcome"]
    assert reply["type"] == "as_game"
    assert reply["data"]["models_ok"] is True and reply["data"]["has_runs"] is False
    assert reply["data"]["screen"] == "home"
    plugin.disconnect()


def test_a_new_connection_reaches_the_same_running_game(real_service):
    """PROTO-02: a page reload makes a new WebsocketHandler (so a new plugin); the game is the same."""
    first = as_game_plugin.AsGamePlugin(_MockWebsocketHandler())
    first.disconnect()
    second = as_game_plugin.AsGamePlugin(_MockWebsocketHandler())
    assert second.service is first.service
    second.disconnect()


async def test_an_unknown_action_is_an_error_reply_not_an_exception(real_service):
    ws = _MockWebsocketHandler()
    plugin = as_game_plugin.AsGamePlugin(ws)
    await plugin.handle({"type": "as_game", "action": "launch_rockets"})
    (reply,) = ws.messages
    assert reply["type"] == "as_game" and reply["action"] == "error"
    assert reply["data"]["code"] == "unknown_action"
    plugin.disconnect()
