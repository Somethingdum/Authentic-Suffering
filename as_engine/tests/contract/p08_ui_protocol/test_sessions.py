"""Every session, and a delete that leaves nothing (P8 — the owner's sessions browser). Rules RUN-12,
RUN-13, RUN-06 (service/runs.py wipe_tree, delete_run, list_runs; service/game_service.py
on_run_delete; docs/as/10_UI.md §2.2.1).

The player sees every life they have played, ended ones too, and deletes one with a single
confirmation. A deleted session is gone: every file the game wrote for it is overwritten with zeros
before it is removed, and nothing outside its folder ever named it.

A second name for a file (a hard link) shows what happened to its bytes after the first name is
gone: that is how these tests see the overwrite.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pytest

from as_engine.contracts.common import CallClass
from as_engine.service import game_service, runs
from protocol_kit import only, send, wait_for

pytestmark = pytest.mark.phase(8)


def linked(path: Path, peek_dir: Path) -> tuple[Path, int]:
    peek_dir.mkdir(exist_ok=True)
    peek = peek_dir / f"{len(list(peek_dir.iterdir()))}_{path.name}"
    os.link(path, peek)
    return peek, path.stat().st_size


def zeros(peek: Path, size: int) -> bool:
    data = peek.read_bytes()
    return len(data) == size and data == b"\0" * size


def test_wipe_tree_overwrites_every_file_then_removes_it(tmp_path):
    root = tmp_path / "some_run"
    (root / "saves").mkdir(parents=True)
    (root / "logs" / "deep").mkdir(parents=True)
    files = {root / "world.sqlite": b"S" * 4096, root / "world.sqlite-wal": b"W" * 100,
             root / "saves" / "slot.json": b'{"name": "before the storm"}',
             root / "logs" / "deep" / "turn.log": b"x" * 7, root / "empty.txt": b""}
    for f, data in files.items():
        f.write_bytes(data)
    peeks = [linked(f, tmp_path / "peek") for f in files]
    runs.wipe_tree(root)
    assert not root.exists()
    for peek, size in peeks:
        assert zeros(peek, size), peek.name
    runs.wipe_tree(root)                                   # already gone: nothing to do


def test_every_session_is_listed_ended_ones_too(cfg, make_run):
    alive = make_run()
    ended = make_run()
    m = Path(cfg.runs_dir) / ended / "manifest.json"
    data = json.loads(m.read_text(encoding="utf-8"))
    data.update(alive=False, final=True)
    m.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")
    got = {r.run_id: r for r in runs.list_runs(cfg)}
    assert set(got) == {alive, ended}
    assert (got[ended].final, got[ended].alive) == (True, False) and got[alive].final is False


def test_delete_leaves_nothing_of_the_session(cfg, make_run, gated, tmp_path):
    keep = make_run()
    rid = make_run()
    s = runs.load_run(cfg, rid, gated)
    runs.save_run(s, "before the storm")
    runs.autosave(s)
    s.store.close()
    run_dir = Path(cfg.runs_dir) / rid
    (run_dir / "logs" / "turns.log").write_text("Hand me the keys, she said.", encoding="utf-8")
    files = sorted(p for p in run_dir.rglob("*") if p.is_file())
    names = {p.name for p in files}
    assert {"world.sqlite", "turn0.sqlite", "manifest.json", "turns.log"} <= names
    assert {p.parent.name for p in files} >= {"saves", "autosave", "logs"}
    peeks = [linked(p, tmp_path / "peek") for p in files]
    runs.delete_run(cfg, rid)
    assert not run_dir.exists()
    assert all(zeros(peek, size) for peek, size in peeks), "every file was overwritten before it went"
    assert [r.run_id for r in runs.list_runs(cfg)] == [keep], "the other session is untouched"
    assert (Path(cfg.runs_dir) / keep / "world.sqlite").stat().st_size > 0


async def test_nothing_is_deleted_while_a_turn_runs(svc, make_run, gated, cfg):
    rid = make_run()
    await send(svc, "run_load", run_id=rid)
    gated.hold = {CallClass.NARRATION}
    await send(svc, "turn_submit", mode="do", text="I watch the front door.")
    await wait_for(lambda: gated.reached.is_set())
    r = await send(svc, "run_delete", run_id=rid)
    assert only(r, "error") == {"code": "busy", "message": game_service.BUSY, "recoverable": True}
    gated.release.set()
    await svc.idle()
    assert (Path(cfg.runs_dir) / rid / "world.sqlite").exists()


async def test_the_log_never_names_a_session(svc, make_run, caplog):
    """RUN-13: the process-wide log holds actions, codes and exception types — never a run id, a
    save's name or anything typed in a run, whatever happens."""
    caplog.set_level(logging.DEBUG)
    rid = make_run()
    await send(svc, "run_load", run_id=rid)
    await send(svc, "turn_submit", mode="say", text="Nobody touches the zebrawood box tonight.")
    await svc.idle()
    await send(svc, "run_save", slot_name="zebrawood night")
    await send(svc, "run_delete", run_id=rid)
    await send(svc, "run_load", run_id=rid)                # gone: refused
    await send(svc, "run_delete", run_id=rid)              # gone: refused
    text = "\n".join(f"{r.name} {r.getMessage()} {r.exc_text or ''}" for r in caplog.records).lower()
    for secret in (rid, "zebrawood"):
        assert secret.lower() not in text, secret
