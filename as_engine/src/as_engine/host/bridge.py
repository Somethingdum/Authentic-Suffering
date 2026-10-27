"""The bridge process a host starts: ``python -I -m as_engine.bridge`` (D-299). Rules HOST-24..HOST-27.

HOST-24 start. main(argv=None) -> int. Arguments: --content DIR (the content packs folder; default
  content_root() — the as_content/packs folder beside this package's source tree), --config FILE
  (an as_config.yaml for the engine's rules and regimes; none: the defaults; its lanes are never
  used, host.world.host_config). Before anything else the seal is installed with no model machine
  at all (lanes.seal.install([]): every name lookup and every connection but loopback is refused,
  SEAL-02), so nothing in the process can reach out; the engine itself opens no socket. Logging
  goes to stderr at WARNING; a line names a request type and an exception type, never story text
  (HOST-20, RUN-13); AS_BRIDGE_DEBUG=1 adds the traceback, for development.
HOST-25 the loop. A reader thread reads stdin's file descriptor (os.read, no buffered reader: nothing
  it holds can stop the process ending) line by line and hands each line to the event loop. A
  'result' or 'error' with "re" answers the engine's request of that id (Link). A host request:
  'ping' and 'cancel' are answered at once; every other one waits its turn behind the one before
  (one at a time, in the order they came), each in its own task so 'cancel' reaches a turn.
  'close' is answered, then the loop ends. Answers and the engine's own requests and notices are
  written to stdout one line each (protocol.encode), from the loop's thread only.
HOST-26 a line that is not a JSON object -> error {re: null, code 'bad_json'}; an unknown type ->
  'unknown_type'; a request whose fields do not validate -> 'bad_request' (the first field's place
  and the problem, never its value); an exception in a handler -> 'internal'; a handler's own
  refusal -> its code and message (HostService.handle).
HOST-27 the end. stdin closed or 'close': every request the engine still waits on is answered as
  failed ('the host is gone'), the running task is cancelled, the session's store is closed, and
  main returns 0.
Link(write): request(type, payload) -> the answer's fields (an 'error' answer -> {failed:
  'refused', why: its message}); notify(type, payload); resolve(message); fail_all().
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import threading
from pathlib import Path

from .protocol import HOST_REQUESTS, MODELS, decode, encode

log = logging.getLogger("as_engine.host")


class Link:
    def __init__(self, write):
        self._write = write
        self._n = 0
        self._waiting: dict[str, asyncio.Future] = {}

    async def request(self, kind: str, payload: dict) -> dict:
        self._n += 1
        rid = f"e{self._n}"
        fut = asyncio.get_running_loop().create_future()
        self._waiting[rid] = fut
        try:
            self._write({"type": kind, "id": rid, **payload})
            msg = await fut
        finally:
            self._waiting.pop(rid, None)
        if msg.get("type") == "error":
            return {"failed": "refused", "why": str(msg.get("message") or msg.get("code") or "error")}
        return {k: v for k, v in msg.items() if k not in ("v", "type", "re")}

    def notify(self, kind: str, payload: dict) -> None:
        self._write({"type": kind, **payload})

    def resolve(self, msg: dict) -> None:
        fut = self._waiting.get(str(msg.get("re")))
        if fut is not None and not fut.done():
            fut.set_result(msg)

    def fail_all(self) -> None:
        for fut in list(self._waiting.values()):
            if not fut.done():
                fut.set_result({"type": "error", "code": "gone", "message": "the host is gone"})


def _fd_lines(fd: int, size: int = 1 << 16):
    """Lines read straight from a file descriptor: no buffered reader and so no lock a reader thread
    could still hold when the process ends (a daemon thread inside sys.stdin.buffer aborts the
    interpreter at shutdown)."""
    buf = b""
    while True:
        chunk = os.read(fd, size)
        if not chunk:
            if buf:
                yield buf
            return
        buf += chunk
        while True:
            i = buf.find(b"\n")
            if i < 0:
                break
            yield buf[:i + 1]
            buf = buf[i + 1:]


def content_root() -> Path:
    here = Path(__file__).resolve()
    for up in here.parents:
        cand = up / "as_content" / "packs"
        if (cand / "core").is_dir():
            return cand
    return Path("as_content/packs")


def _bad(e) -> str:
    first = e.errors()[0]
    where = ".".join(str(x) for x in first.get("loc", ())) or "request"
    return f"{where}: {first.get('msg', 'not valid')}"


async def serve(config, read_lines=None, write_line=None) -> int:
    """HOST-25. ``read_lines``: an iterable of byte lines (stdin's buffer); ``write_line``: a
    callable taking one encoded line (stdout's buffer write + flush). Tests pass their own."""
    from pydantic import ValidationError

    from .service import HostService
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    if read_lines is None:
        read_lines = _fd_lines(sys.stdin.fileno())
    if write_line is None:
        out = sys.stdout.buffer

        def write_line(b):
            out.write(b)
            out.flush()

    def write(obj: dict) -> None:
        write_line(encode(obj))

    link = Link(write)
    svc = HostService(config, link)

    def reader():
        try:
            for line in read_lines:
                loop.call_soon_threadsafe(queue.put_nowait, line)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    threading.Thread(target=reader, name="as-bridge-stdin", daemon=True).start()
    order = asyncio.Lock()
    tasks: set[asyncio.Task] = set()

    async def answer(msg: dict) -> None:
        rid, kind = msg.get("id"), msg.get("type")
        if kind not in HOST_REQUESTS:
            write({"type": "error", "re": rid, "code": "unknown_type", "message": f"There is no request called {kind}."})
            return
        fields = {k: v for k, v in msg.items() if k not in ("v", "type", "id")}
        try:
            p = MODELS[kind].model_validate(fields)
        except ValidationError as e:
            write({"type": "error", "re": rid, "code": "bad_request", "message": _bad(e)})
            return
        try:
            got = await svc.handle(kind, p)
        except asyncio.CancelledError:
            write({"type": "error", "re": rid, "code": "cancelled", "message": "Stopped."})
            raise
        except Exception as e:  # noqa: BLE001
            log.error("request %s failed: %s", kind, type(e).__name__, exc_info=os.environ.get("AS_BRIDGE_DEBUG") == "1")
            write({"type": "error", "re": rid, "code": "internal", "message": "Something went wrong in the game engine."})
            return
        if "error" in got:
            write({"type": "error", "re": rid, **got["error"]})
        else:
            write({"type": "result", "re": rid, **got})

    async def in_order(msg: dict) -> None:
        async with order:
            await answer(msg)

    def spawn(coro) -> None:
        t = loop.create_task(coro)
        tasks.add(t)
        t.add_done_callback(tasks.discard)

    try:
        while True:
            line = await queue.get()
            if line is None:
                break
            if not line.strip():
                continue
            try:
                msg = decode(line)
            except (ValueError, UnicodeDecodeError):
                write({"type": "error", "re": None, "code": "bad_json", "message": "That line is not a JSON object."})
                continue
            kind = msg.get("type")
            if kind in ("result", "error") and "re" in msg:
                link.resolve(msg)
            elif kind in ("ping", "cancel"):
                spawn(answer(msg))
            elif kind == "close":
                async with order:
                    await answer(msg)
                break
            else:
                spawn(in_order(msg))
    finally:
        link.fail_all()
        for t in list(tasks):
            t.cancel()
        for t in list(tasks):
            try:
                await t
            except BaseException:  # noqa: BLE001 — every task ends here, however it ended
                pass
        svc._close()
    return 0


def main(argv: list[str] | None = None) -> int:
    from ..config_loader import load_engine_config
    from ..lanes import seal
    seal.install([])
    ap = argparse.ArgumentParser(prog="as_engine.bridge")
    ap.add_argument("--content", default=None)
    ap.add_argument("--config", default=None)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format="%(levelname)s %(name)s %(message)s")
    from ..contracts.settings import EngineConfig
    config = load_engine_config(a.config) if a.config else EngineConfig()
    config = config.model_copy(update={"content_dir": str(Path(a.content) if a.content else content_root())})
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass
    return asyncio.run(serve(config))
