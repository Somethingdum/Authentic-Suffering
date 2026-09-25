"""The seal: nothing leaves the owner's own machines (P12). Rules SEAL-01..05; DECISIONS D-104
(lanes/seal.py; contracts/settings.LaneConfig; lanes/transport.HttpTransport; the launchers, the
Talemate server's start, the frontend's fonts).

The owner: "I need this to be a completely sealed up, local build that doesn't put my privacy at
risk"; "No limitations. No privacy leaks. Hard rule."
"""

from __future__ import annotations

import asyncio
import http.server
import os
import re
import socket
import threading
from pathlib import Path

import pytest

from as_engine.contracts.settings import EngineConfig, LaneConfig
from as_engine.lanes import seal

pytestmark = pytest.mark.phase(12)

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def sealed_to():
    """install(hosts) for one test, from an unsealed start; always lifted afterwards (the CLI tests
    seal this process too)."""
    seal.uninstall()
    yield seal.install
    seal.uninstall()


@pytest.fixture
def home_server():
    """A web server on this machine (the stand-in for LM Studio): its port."""
    srv = http.server.HTTPServer(("127.0.0.1", 0), http.server.BaseHTTPRequestHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def test_only_the_owner_s_machines_answer(sealed_to, home_server):
    """SEAL-02: this machine and the model machines, nothing else — not even a name lookup."""
    sealed_to(["http://localhost:1234/v1", "http://192.168.1.40:1234/v1", "http://laptop.local:1234/v1"])
    assert seal.sealed()
    socket.create_connection(("127.0.0.1", home_server), timeout=2).close()
    with pytest.raises(socket.gaierror, match="sealed: huggingface.co"):
        socket.getaddrinfo("huggingface.co", 443)
    for attempt in (lambda: socket.create_connection(("8.8.8.8", 53), timeout=1),
                    lambda: socket.socket().connect(("1.1.1.1", 443)),
                    lambda: socket.socket().connect_ex(("9.9.9.9", 443)),
                    lambda: socket.socket().connect(("192.168.1.99", 80))):     # home, but no model there
        with pytest.raises(ConnectionRefusedError, match="not one of your own machines"):
            attempt()
    assert [h for h, _ in seal.refused()] == ["huggingface.co", "8.8.8.8", "1.1.1.1", "9.9.9.9", "192.168.1.99"]


def test_the_event_loop_is_sealed_too(sealed_to, home_server):
    """SEAL-02: asyncio's own connect (the one httpx and the websocket server use) obeys."""
    sealed_to(["http://localhost:1234/v1"])

    async def go():
        with pytest.raises(ConnectionRefusedError):
            await asyncio.open_connection("9.9.9.9", 443)
        with pytest.raises(socket.gaierror):
            await asyncio.open_connection("example.com", 443)
        _, w = await asyncio.open_connection("127.0.0.1", home_server)
        w.close()
    asyncio.run(go())


def test_no_library_is_let_online_and_no_proxy_carries_the_words(sealed_to, monkeypatch):
    """SEAL-03."""
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:8080")
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    sealed_to([])
    assert {k: os.environ.get(k) for k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE",
                                           "HF_HUB_DISABLE_TELEMETRY", "ANONYMIZED_TELEMETRY", "DO_NOT_TRACK")} == {
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
        "ANONYMIZED_TELEMETRY": "False", "DO_NOT_TRACK": "1"}
    assert "HTTPS_PROXY" not in os.environ
    seal.uninstall()
    assert os.environ["HTTPS_PROXY"] == "http://proxy.example:8080" and os.environ["HF_HUB_OFFLINE"] == "0"
    assert not seal.sealed()


def test_a_model_anywhere_else_never_loads():
    """SEAL-01: the model addresses are the owner's machines or the config is refused."""
    for good in ("http://localhost:1234/v1", "http://127.0.0.1:1234/v1", "http://192.168.1.20:1234/v1",
                 "http://10.0.0.5:1234/v1", "http://laptop:1234/v1", "http://msi.local:1234/v1", "http://[::1]:1234/v1"):
        assert LaneConfig(name="x", base_url=good).base_url == good
    for bad in ("https://api.openai.com/v1", "http://8.8.8.8:1234/v1", "https://openrouter.ai/api/v1", "ftp://localhost/v1",
                "http://0.0.0.0:1234/v1", "localhost:1234"):
        with pytest.raises(ValueError):
            LaneConfig(name="x", base_url=bad)
    with pytest.raises(seal.SealError, match="outside this machine"):
        seal.check_lane_url("https://api.deepseek.com/v1")
    with pytest.raises(ValueError):
        EngineConfig.model_validate({"lanes": {"A": {"name": "x", "base_url": "https://api.openai.com/v1"}}})


def test_a_bad_install_changes_nothing(sealed_to):
    sealed_to(["http://localhost:1234/v1"])
    with pytest.raises(seal.SealError):
        seal.install(["https://api.openai.com/v1"])
    with pytest.raises(socket.gaierror):
        socket.getaddrinfo("api.openai.com", 443)


def test_the_lane_client_reads_no_proxy():
    """SEAL-04."""
    from as_engine.lanes.transport import HttpTransport
    assert HttpTransport()._c.trust_env is False


def test_the_server_seals_itself_before_anything_else():
    """SEAL-04: the Talemate server's first act, from the engine's config — or this machine alone
    when the config cannot be read; and it never goes online for tokenizer data."""
    run = (ROOT / "src" / "talemate" / "server" / "run.py").read_text(encoding="utf-8")
    first = next(ln for ln in run.splitlines() if ln.startswith(("import ", "from ")))
    assert first.startswith("from as_engine.lanes import seal"), first
    assert "seal.install_from_config(load_engine_config(" in run and "seal.install([])" in run
    assert re.search(r"if not seal\.sealed\(\):[^\n]*\n\s*loop\.create_task\(install_punkt\(\)\)", run)
    assert "nltk.download('punkt'" in (ROOT / "tools" / "as" / "setup.py").read_text(encoding="utf-8")


def test_every_cli_command_runs_sealed(sealed_to, tmp_path):
    """SEAL-04."""
    from as_engine.cli import main
    conf = tmp_path / "as_config.yaml"
    conf.write_text(f"content_dir: {(ROOT / 'as_content' / 'packs').as_posix()}\n", encoding="utf-8")
    main(["--config", str(conf), "content-check"])
    assert seal.sealed() and seal.allowed() == {"names": ["localhost"], "ips": []}


async def test_a_changed_model_address_reseals(svc, sealed_to):
    """SEAL-04 and SEAL-01 through the Connect screen."""
    from protocol_kit import error_code, only, send
    sealed_to(["http://localhost:1234/v1"])
    r = await send(svc, "config_set", patch={"lanes": {"B": {"base_url": "http://192.168.1.20:1234/v1"}}})
    assert only(r, "config")["lanes"]["B"]["base_url"] == "http://192.168.1.20:1234/v1"
    assert seal.allowed()["ips"] == ["192.168.1.20"]
    r = await send(svc, "config_set", patch={"lanes": {"B": {"base_url": "https://api.openai.com/v1"}}})
    assert error_code(r) == "bad_request" and "outside this machine" in only(r, "error")["message"]
    assert seal.allowed()["ips"] == ["192.168.1.20"], "nothing changed"


def test_nothing_reaches_out_on_its_own():
    """SEAL-05: the launchers stay on this machine and offline; no font or script from outside."""
    seen = []
    for f in sorted(ROOT.glob("start*.sh")) + sorted(ROOT.glob("start*.bat")):
        t = f.read_text(encoding="utf-8", errors="replace")
        if "0.0.0.0" in t:
            seen.append((f.name, "0.0.0.0"))
        for line in t.splitlines():
            if line.lstrip().upper().startswith(("REM", "#", "::")):
                continue
            if re.search(r"\buv\s+run\s", line) and not ("--offline" in line and "--no-sync" in line):
                seen.append((f.name, line.strip()))
    for f in sorted(ROOT.glob("docker-compose*.yml")):
        for m in re.finditer(r'^\s*-\s*"([^"]+)"\s*$', f.read_text(encoding="utf-8"), re.M):
            if ":" in m.group(1) and not m.group(1).startswith("127.0.0.1:") and "/" not in m.group(1):
                seen.append((f.name, m.group(1)))
    front = ROOT / "talemate_frontend"
    for f in [front / "index.html", *sorted((front / "src").rglob("*.js")), *sorted((front / "src").rglob("*.vue")),
              *sorted((front / "src").rglob("*.css"))]:
        if "__tests__" in f.parts or not f.exists():
            continue
        t = f.read_text(encoding="utf-8", errors="replace")
        for w in ("fonts.googleapis.com", "fonts.gstatic.com", "google: {", "cdn.jsdelivr", "unpkg.com", "cdnjs"):
            if w in t:
                seen.append((str(f.relative_to(ROOT)), w))
    assert seen == []
