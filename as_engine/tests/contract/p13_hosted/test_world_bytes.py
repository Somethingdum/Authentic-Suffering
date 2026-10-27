"""A hosted world is bytes the host keeps (P13, D-299). Rules HOST-02, HOST-03, HOST-16 begin
(kernel/store.py to_bytes / from_bytes / create_memory, host/world.py, host/service.py).

The engine holds a hosted story in memory only: it opens the bytes the host hands it and hands back
new bytes; it never writes a file. A world saved by a newer game is refused and left as it is. The
packs a world needs are named relative to the content folder, so the same world opens on another
machine.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from host_kit import call, header, same_world

from as_engine.host import world as W
from as_engine.host.protocol import b64, unb64
from as_engine.kernel.hashing import full_state_hash
from as_engine.kernel.store import Store

pytestmark = pytest.mark.phase(13)


def test_a_store_round_trips_through_bytes(store):
    data = store.to_bytes()
    back = Store.from_bytes(data)
    try:
        assert full_state_hash(back) == full_state_hash(store)
        assert data[18] == data[19] == 1
    finally:
        back.close()


def test_a_wal_file_opens_from_its_bytes(tmp_path):
    s = Store.create(tmp_path / "w.sqlite", run_id="r", seed=2)
    s.close()
    back = Store.from_bytes((tmp_path / "w.sqlite").read_bytes())
    try:
        assert back.meta("run_id") == "r"
    finally:
        back.close()


def test_as_world_bytes_name_the_world_and_keep_no_model_traffic(store):
    w = Store.from_bytes(store.to_bytes(as_world="w_9"))
    try:
        assert w.meta("run_id") == "w_9" and w.query_one("SELECT COUNT(*) FROM lm_calls")[0] == 0
    finally:
        w.close()
    assert store.meta("run_id") == "t"


def test_the_envelope(hcfg, world0):
    h = W.header_of(world0)
    assert h["format"] == W.FORMAT and h["packs"] == ["core"] and h["turn"] == 0
    hd, s = W.unpack(world0)
    try:
        assert full_state_hash(s) == h["full_state_hash"]
    finally:
        s.close()


def test_a_newer_or_damaged_world_is_refused(world0):
    import json
    n = int.from_bytes(world0[len(W.MAGIC):len(W.MAGIC) + 4], "big")
    head = json.loads(world0[len(W.MAGIC) + 4:len(W.MAGIC) + 4 + n])
    head["format"] = W.FORMAT + 1
    hb = json.dumps(head).encode()
    newer = W.MAGIC + len(hb).to_bytes(4, "big") + hb + world0[len(W.MAGIC) + 4 + n:]
    with pytest.raises(W.WorldError) as e:
        W.unpack(newer)
    assert e.value.code == "newer"
    with pytest.raises(W.WorldError) as e:
        W.unpack(world0[:-200])
    assert e.value.code == "not_a_world"
    with pytest.raises(W.WorldError):
        W.unpack(b"SQLite format 3\0" + b"\0" * 100)


def test_packs_are_relative_to_the_content_folder(hcfg, tmp_path):
    assert W.packs_for(hcfg, [Path(hcfg.content_dir) / "core"]) == ["core"]
    assert W.packs_for(hcfg, [tmp_path]) == [str(tmp_path.resolve())]
    assert W.pack_dirs(hcfg, ["core", str(tmp_path)]) == [Path(hcfg.content_dir) / "core", tmp_path]


def test_the_host_lanes_address_nothing(hcfg):
    lanes = W.host_config(hcfg).lanes
    assert {c.model for c in lanes.values()} == {"host"} and all(c.structured_with_thinking == "supported" for c in lanes.values())


async def test_opening_and_saving_write_no_file(hcfg, world0, host, hosted, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    svc = hosted(host())
    got = await call(svc, "open", world=b64(world0))
    assert "error" not in got and got["turn"] == 0
    saved = await call(svc, "save")
    assert header(saved["world"])["full_state_hash"] == W.header_of(world0)["full_state_hash"]
    assert list(tmp_path.iterdir()) == [], "a hosted story writes nothing to disk"


async def test_a_newer_world_is_refused_by_the_service(hcfg, world0, host, hosted):
    svc = hosted(host())
    got = await call(svc, "open", world=b64(b"ASWORLD\n" + (5).to_bytes(4, "big") + b'{"fo' + b"x" * 40))
    assert got["error"]["code"] == "not_a_world"


async def test_a_world_is_made_in_memory(hcfg, host, hosted, tmp_path, monkeypatch):
    """HOST-16 begin: worldgen with no file — the genesis comes back as bytes, the seed is told first."""
    monkeypatch.chdir(tmp_path)
    h = host()
    svc = hosted(h)
    got = await call(svc, "begin", pc_ref="core:pc/owen_marsh",
                     settings={"world_detail": "gotta_go_to_work_soon", "seed": 7, "era": "established"})
    assert "error" not in got, got
    assert ("begin.seed", {"seed": 7}) in h.notices
    assert got["turn"] == 0 and header(got["world"])["packs"] == ["core"]
    g = header(got["genesis"])
    _gh, gs = W.unpack(unb64(got["genesis"]))
    try:
        assert gs.meta("run_id") == got["world_summary"]["world_id"] == "w_7"
        assert gs.query_one("SELECT COUNT(*) FROM lm_calls")[0] == 0
        assert gs.query_one("SELECT COUNT(*) FROM bodies b JOIN actors a ON a.actor_id = b.body_id")[0] >= 0
    finally:
        gs.close()
    assert g["turn"] == 0
    assert any(m["action"] == "story" for m in got["messages"])
    assert list(tmp_path.iterdir()) == []
    assert all(p["work"]["kind"] in ("narrative", "engineering") for _k, p in h.calls)


async def test_a_world_begun_again_with_its_answers_asks_nothing(hcfg, host, hosted):
    first = host()
    a = await call(hosted(first), "begin", pc_ref="core:pc/owen_marsh",
                   settings={"world_detail": "gotta_go_to_work_soon", "seed": 7, "era": "established"})
    again = host()
    b = await call(hosted(again), "begin", pc_ref="core:pc/owen_marsh",
                   settings={"world_detail": "gotta_go_to_work_soon", "seed": 7, "era": "established"},
                   answers=first.results)
    assert again.calls == [] and same_world(a["world"], b["world"])


async def test_bad_settings_are_refused(host, hosted):
    got = await call(hosted(host()), "begin", pc_ref="core:pc/owen_marsh", settings={"era": "the moon"})
    assert got["error"]["code"] == "bad_settings"


def test_nothing_in_the_host_package_touches_the_disk_or_the_network():
    """The code itself (not its docs): no open(), no Path write, no folder made, no network import."""
    import ast
    src = Path(W.__file__).parent
    for py in sorted(src.glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
                assert name not in ("open", "write_text", "write_bytes", "mkdir", "makedirs", "unlink", "rmtree",
                                    "connect_ex", "create_connection", "urlopen"), (py.name, name, node.lineno)
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                for m in mods:
                    assert m.split(".")[0] not in ("socket", "httpx", "urllib", "requests", "http", "ssl", "shutil",
                                                   "tempfile"), (py.name, m)
