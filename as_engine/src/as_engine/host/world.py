"""A hosted world: bytes the host keeps, never a file the engine writes (D-299). Rules HOST-02, HOST-03.

HOST-02 the envelope. pack(store, packs) -> bytes:
  MAGIC (b"ASWORLD\\n") + len(header) as 4 bytes big-endian + header (canonical JSON, UTF-8) +
  zlib.compress(store.to_bytes(), 6). header = {format: FORMAT, engine: as_engine.__version__,
  schema: kernel.store.SCHEMA_VERSION, turn: world_clock.turn_index, packs: the run's pack list,
  world_state_hash, full_state_hash}. The host names a world by sha256(the envelope) and keeps it
  as it likes (sealed, written once); the engine only ever holds it in memory.
  ``packs`` are the run's content packs, each relative to config.content_dir (posix, 'core',
  'cheat_willis') when it is inside it, else an absolute path: the same world opens on another
  machine whose content folder is somewhere else.
  unpack(data) -> (header, Store): a bad magic or header, or bytes that are not a run ->
  WorldError('not_a_world'); header.format above FORMAT or header.schema above SCHEMA_VERSION ->
  WorldError('newer', NEWER) — never opened, never written over; a schema below it ->
  WorldError('older', OLDER) (there is no older schema yet: the first change brings its
  conversion, made on load into a new world, never over the old one).
HOST-03 opening. open_session(config, store, transport, packs, *, run_id=None) -> Session, as
  service.runs opens a run but with no run folder: config' = host_config(config) with the run's
  frozen rules (meta.rules_json, SET-03); canon = content.pack.load_canon(pack_dirs(config,
  packs)); Session(run_id = run_id or meta.run_id, run_dir None — a hosted run never autosaves,
  the host keeps the bytes the turn hands back —, store, canon, config', settings from
  meta.settings_json, Rng(meta.seed), LaneClient(config', transport), pc_id = meta.pc_actor_id);
  extras['packs'] = packs. Then the checks service.runs.load_run makes (RUN-10): every content ref
  must resolve (else the store is closed and WorldError('content_missing', the plain lines));
  notices: the content-changed line when meta.content_hash differs; every actor fused; the FTS
  index rebuilt.
host_config(config) -> EngineConfig: config with lanes = HOST_LANES — two lanes that address
  nothing a host could be told about (a loopback placeholder, model 'host', no key), structured
  output always sent with or without thinking (the host decides how it is enforced), concurrency 8
  (the host's queue, not the engine, decides how many run at once). The run's requests are then the
  same whatever lanes the engine's own config names (LANE-12).
"""

from __future__ import annotations

import json
import zlib
from pathlib import Path
from typing import Any

from ..kernel.errors import ASError

MAGIC = b"ASWORLD\n"
FORMAT = 1
NEWER = "This story was saved by a newer version of the game. Update to open it; it was left as it is."
OLDER = "This story was saved by an older version of the game that this one cannot convert yet."


class WorldError(ASError):
    rule = "HOST-02"

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def host_lanes() -> dict:
    from ..contracts.common import Lane
    from ..contracts.settings import LaneConfig
    common = dict(base_url="http://127.0.0.1:9/v1", model="host", api_key="", max_concurrency=8,
                  structured_mode="json_schema", structured_with_thinking="supported", thinking_mode="native")
    return {Lane.A: LaneConfig(name="narrative work", **common), Lane.B: LaneConfig(name="engineering work", **common)}


def host_config(config: Any) -> Any:
    return config.model_copy(update={"lanes": host_lanes()})


def pack_dirs(config: Any, packs: list[str]) -> list[Path]:
    base = Path(config.content_dir)
    return [Path(p) if Path(p).is_absolute() else base / p for p in packs]


def packs_for(config: Any, dirs: list[str | Path]) -> list[str]:
    base = Path(config.content_dir).resolve()
    out = []
    for d in dirs:
        p = Path(d).resolve()
        try:
            out.append(p.relative_to(base).as_posix())
        except ValueError:
            out.append(str(p))
    return out


def pack(store: Any, packs: list[str]) -> bytes:
    import as_engine
    from ..kernel.hashing import full_state_hash, world_state_hash
    from ..kernel.jsoncanon import canonical_json
    from ..kernel.store import SCHEMA_VERSION
    turn = store.query_one("SELECT turn_index FROM world_clock")[0]
    header = {"format": FORMAT, "engine": as_engine.__version__, "schema": SCHEMA_VERSION, "turn": turn,
              "packs": list(packs), "world_state_hash": world_state_hash(store), "full_state_hash": full_state_hash(store)}
    h = canonical_json(header).encode("utf-8")
    return MAGIC + len(h).to_bytes(4, "big") + h + zlib.compress(store.to_bytes(), 6)


def header_of(data: bytes) -> dict:
    if not data.startswith(MAGIC) or len(data) < len(MAGIC) + 4:
        raise WorldError("not_a_world", "That is not a saved story.")
    n = int.from_bytes(data[len(MAGIC):len(MAGIC) + 4], "big")
    try:
        header = json.loads(data[len(MAGIC) + 4:len(MAGIC) + 4 + n].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise WorldError("not_a_world", "That is not a saved story.") from e
    if not isinstance(header, dict):
        raise WorldError("not_a_world", "That is not a saved story.")
    return header


def unpack(data: bytes) -> tuple[dict, Any]:
    from ..kernel.errors import SchemaError
    from ..kernel.store import SCHEMA_VERSION, Store
    header = header_of(data)
    if int(header.get("format", 0)) > FORMAT or int(header.get("schema", 0)) > SCHEMA_VERSION:
        raise WorldError("newer", NEWER)
    if int(header.get("schema", 0)) < SCHEMA_VERSION:
        raise WorldError("older", OLDER)
    n = int.from_bytes(data[len(MAGIC):len(MAGIC) + 4], "big")
    try:
        raw = zlib.decompress(data[len(MAGIC) + 4 + n:])
        store = Store.from_bytes(raw)
    except (zlib.error, SchemaError) as e:
        raise WorldError("not_a_world", "That saved story is damaged and cannot be opened.") from e
    return header, store


def open_session(config: Any, store: Any, transport: Any, packs: list[str], *, run_id: str | None = None) -> Any:
    from ..content.pack import load_canon
    from ..contracts.settings import RulesConfig, RunSettings
    from ..kernel.rng import Rng
    from ..lanes.client import LaneClient
    from ..mind.actor import fused
    from ..service._impl_runs import _content_refs
    from ..service.session import Session
    canon, _issues = load_canon(pack_dirs(config, packs))
    rj = store.meta("rules_json")
    rules = RulesConfig.model_validate_json(rj) if rj not in (None, "", "{}") else RulesConfig()
    store.attach(canon=canon, rules=rules)
    cfg = host_config(config).model_copy(update={"rules": rules})
    st = RunSettings.model_validate_json(store.meta("settings_json"))
    s = Session(run_id=run_id or store.meta("run_id"), run_dir=None, store=store, canon=canon, config=cfg, settings=st,
                rng=Rng(int(store.meta("seed"))), client=LaneClient(cfg, transport), pc_id=store.meta("pc_actor_id"))
    s.extras["packs"] = list(packs)
    missing = [r for r in _content_refs(store) if not canon.has(r)]
    if missing:
        store.close()
        raise WorldError("content_missing", "\n".join(f"Your story uses '{m}', which is no longer in any pack." for m in missing))
    notices = []
    if store.meta("content_hash") != canon.content_hash:
        notices.append("Your content changed since this story started. People already in the world keep who they were.")
    for r in store.query("SELECT actor_id FROM actors ORDER BY actor_id"):
        fused(store, r[0])
    store.rebuild_fts()
    s.extras["notices"] = notices
    return s
