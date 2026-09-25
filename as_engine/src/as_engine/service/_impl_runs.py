"""Implementation of service/runs.py (P7 part)."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

MANIFEST = "manifest.json"


class RunError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def slug(text):
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s or "run"


def _now_text():
    from ..kernel.store import wall_clock_iso
    return wall_clock_iso()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def runs_dir(config):
    return Path(config.runs_dir)


def _manifest_for(store, run_id, pack_dirs, *, created=None, prev=None):
    from ..kernel.clock import now, turn_index, world_time
    from ..kernel.hashing import world_state_hash
    from ..kernel.store import SCHEMA_VERSION
    from .. import __version__
    from ..contracts.settings import RunSettings
    pc = store.meta("pc_actor_id")
    name = store.query_one("SELECT display_name FROM actors WHERE actor_id=?", (pc,))[0]
    alive = store.query_one("SELECT alive FROM bodies WHERE body_id=?", (pc,))[0] == 1
    st = RunSettings.model_validate_json(store.meta("settings_json"))
    day = world_time(now(store)).day
    return {"run_id": run_id, "title": f"{name}, day {day}", "pc_name": name,
            "created_at_real": (prev or {}).get("created_at_real") or created or _now_text(), "last_played_real": _now_text(),
            "day": day, "turn_index": turn_index(store), "alive": alive, "final": bool((prev or {}).get("final", False)),
            "difficulty": st.difficulty.value, "ironman": st.save_mode == "ironman", "sandbox": store.meta("sandbox") == "1",
            "schema_version": SCHEMA_VERSION, "content_hash": store.meta("content_hash"), "engine_version": __version__,
            "world_state_hash": world_state_hash(store), "pack_dirs": [str(p) for p in pack_dirs],
            "world_id": store.meta("world_id") or None}


def write_manifest(session):
    p = session.run_dir / MANIFEST
    prev = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    m = _manifest_for(session.store, session.run_id, session.extras.get("pack_dirs", []), prev=prev)
    p.write_text(json.dumps(m, indent=2, sort_keys=True), encoding="utf-8")
    return m


def _new_run_id(config, pc_name, seed):
    base = f"{slug(pc_name)}_{seed:x}"
    rid, n = base, 1
    while (runs_dir(config) / rid).exists():
        n += 1
        rid = f"{base}_{n}"
    return rid


def create_run_from_scenario(config, scenario_path, transport, *, settings=None, packs_root=None, core_pack_dir=None):
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    from ..kernel.clock import now
    from ..kernel.rng import Rng
    from ..kernel.store import Store
    from ..lanes.client import LaneClient
    from ..testing.scenario import load_scenario, parse_scenario
    from .session import Session
    spec = parse_scenario(scenario_path)
    packs_root = Path(packs_root) if packs_root else Path(config.content_dir)
    core = Path(core_pack_dir) if core_pack_dir else Path(config.content_dir) / "core"
    w = load_scenario(scenario_path, packs_root=packs_root, core_pack_dir=core, transport=transport)
    if settings is not None:
        with w.store.transaction() as tx:
            tx.commit_event(Event(type=EventType.SETTINGS_CHANGE, writer="kernel.meta", at=now(tx), turn_index=0, origin="system",
                                  payload={"source": "run_start"},
                                  writes=[WriteRecord(op=WriteOp.UPDATE, table="meta", key={"key": "settings_json"},
                                                      values={"value": settings.model_dump_json()})]))
    pc = w.pc_id
    name = w.store.query_one("SELECT display_name FROM actors WHERE actor_id=?", (pc,))[0]
    rid = _new_run_id(config, name, spec.seed)
    rd = runs_dir(config) / rid
    for sub in ("saves", "autosave", "logs", "reports"):
        (rd / sub).mkdir(parents=True, exist_ok=True)
    w.store.backup_to(rd / "world.sqlite")
    w.store.backup_to(rd / "turn0.sqlite")
    w.store.close()
    pack_dirs = [core] + [packs_root / p for p in spec.packs]
    s = _open_session(config, rd, transport, pack_dirs, canon=w.canon)
    s.extras["pack_dirs"] = [str(p) for p in pack_dirs]
    write_manifest(s)
    return s


def _open_session(config, rd, transport, pack_dirs, canon=None):
    from ..content.pack import load_canon
    from ..contracts.settings import RulesConfig, RunSettings
    from ..kernel.rng import Rng
    from ..kernel.store import Store
    from ..lanes.client import LaneClient
    from .session import Session
    store = Store.open(rd / "world.sqlite")
    if canon is None:
        canon, issues = load_canon([Path(p) for p in pack_dirs])
    rules = RulesConfig.model_validate_json(store.meta("rules_json")) if store.meta("rules_json") not in (None, "", "{}") else RulesConfig()
    store.attach(canon=canon, rules=rules)
    cfg = config.model_copy(update={"rules": rules})
    st = RunSettings.model_validate_json(store.meta("settings_json"))
    s = Session(run_id=store.meta("run_id") if False else rd.name, run_dir=rd, store=store, canon=canon, config=cfg, settings=st,
                rng=Rng(int(store.meta("seed"))), client=LaneClient(cfg, transport), pc_id=store.meta("pc_actor_id"))
    s.extras["pack_dirs"] = [str(p) for p in pack_dirs]
    return s


def _write_copy(store, dst):
    tmp = dst.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    store.backup_to(tmp)
    digest = sha256_file(tmp)
    return tmp, digest


def save_run(session, slot_name):
    if session.settings.save_mode == "ironman":
        raise RunError("ironman", "Ironman runs keep only the autosave. Your progress is saved after every turn.")
    from ..kernel.clock import turn_index
    from ..kernel.hashing import world_state_hash
    slot = slug(slot_name)
    dst = session.run_dir / "saves" / f"{slot}.sqlite"
    tmp, digest = _write_copy(session.store, dst)
    if sha256_file(tmp) != digest:
        tmp.rename(dst.with_suffix(".partial"))
        raise RunError("save_corrupt", "The save did not write correctly; your previous save is kept.")
    tmp.replace(dst)
    (session.run_dir / "saves" / f"{slot}.json").write_text(json.dumps({
        "slot": slot, "label": slot_name, "turn_index": turn_index(session.store), "sha256": digest,
        "world_state_hash": world_state_hash(session.store), "saved_real": _now_text()}, indent=2, sort_keys=True), encoding="utf-8")
    write_manifest(session)
    return dst


def autosave(session):
    from ..kernel.clock import turn_index
    from ..kernel.hashing import world_state_hash
    t = turn_index(session.store)
    k = t % session.settings.autosave_ring
    dst = session.run_dir / "autosave" / f"auto_{k}.sqlite"
    tmp, digest = _write_copy(session.store, dst)
    tmp.replace(dst)
    (session.run_dir / "autosave" / f"auto_{k}.json").write_text(json.dumps({
        "slot": f"auto_{k}", "turn_index": t, "sha256": digest, "world_state_hash": world_state_hash(session.store),
        "saved_real": _now_text()}, indent=2, sort_keys=True), encoding="utf-8")
    write_manifest(session)
    return dst


def _content_refs(store):
    refs = set()
    for r in store.query("SELECT DISTINCT def_ref FROM items"):
        refs.add(r[0])
    for r in store.query("SELECT DISTINCT content_ref FROM bodies WHERE content_ref IS NOT NULL"):
        refs.add(r[0])
    for r in store.query("SELECT DISTINCT content_ref FROM dossiers WHERE content_ref IS NOT NULL"):
        refs.add(r[0])
    for r in store.query("SELECT DISTINCT law_ref FROM laws_active"):
        refs.add(r[0])
    for r in store.query("SELECT DISTINCT content_ref FROM groups WHERE content_ref IS NOT NULL"):
        refs.add(r[0])
    return sorted(refs)


def load_run(config, run_id, transport, save_slot=None, *, pack_dirs=None):
    from ..kernel.hashing import world_state_hash
    from ..mind.actor import fused
    rd = runs_dir(config) / run_id
    mp = rd / MANIFEST
    if not mp.exists():
        raise RunError("not_found", f"There is no run called {run_id}.")
    man = json.loads(mp.read_text(encoding="utf-8"))
    if man.get("final"):
        raise RunError("run_final", "That run ended with a death in Ironman. You can look back at it, but not play on.")
    if save_slot is not None:
        if man.get("ironman"):
            raise RunError("ironman", "Ironman runs load from the autosave only.")
        sp = rd / "saves" / f"{slug(save_slot)}.sqlite"
        sj = rd / "saves" / f"{slug(save_slot)}.json"
        if not sp.exists() or not sj.exists():
            raise RunError("not_found", f"There is no save called {save_slot}.")
        meta = json.loads(sj.read_text(encoding="utf-8"))
        if sha256_file(sp) != meta["sha256"]:
            raise RunError("save_corrupt", "That save file is damaged and cannot be loaded.")
        shutil.copyfile(sp, rd / "world.sqlite")
        man["world_state_hash"] = meta["world_state_hash"]
    dirs = pack_dirs or man.get("pack_dirs") or []
    s = _open_session(config, rd, transport, dirs)
    missing = [r for r in _content_refs(s.store) if not s.canon.has(r)]
    if missing:
        s.store.close()
        raise RunError("content_missing", "\n".join(f"Your run uses '{m}', which is no longer in any pack." for m in missing))
    notices = []
    if s.store.meta("content_hash") != s.canon.content_hash:
        notices.append("Your content changed since this run started. People already in the world keep who they were.")
    for r in s.store.query("SELECT actor_id FROM actors ORDER BY actor_id"):
        fused(s.store, r[0])
    s.store.rebuild_fts()
    if world_state_hash(s.store) != man.get("world_state_hash"):
        notices.append("This run's files do not match their last save record. It loaded, but something may have been changed outside the game.")
    s.extras["notices"] = notices
    return s


def list_runs(config):
    from ..contracts.view import RunSummaryView
    out = []
    root = runs_dir(config)
    if not root.exists():
        return out
    for d in sorted(root.iterdir()):
        mp = d / MANIFEST
        if d.name.startswith("_") or not mp.exists():
            continue
        m = json.loads(mp.read_text(encoding="utf-8"))
        lp = m["last_played_real"]
        out.append((lp, m["run_id"], RunSummaryView(run_id=m["run_id"], title=m["title"], pc_name=m["pc_name"], day=m["day"], alive=m["alive"],
                                                    difficulty=m["difficulty"], last_played_text=lp[:16].replace("T", " "),
                                                    sandbox=m["sandbox"], ironman=m["ironman"], world_id=m.get("world_id"))))
    out.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [x[2] for x in out]


def delete_run(config, run_id):
    rd = runs_dir(config) / run_id
    if not (rd / MANIFEST).exists():
        raise RunError("not_found", f"There is no run called {run_id}.")
    shutil.rmtree(rd)


# ============================================================ P10: create_run (worldgen path)
def _new_world_id(config, seed):
    base = f"w_{seed:x}"
    wid, n = base, 1
    while (runs_dir(config) / "_worlds" / wid).exists():
        n += 1
        wid = f"{base}_{n}"
    return wid


async def create_run(config, pc_ref, settings, transport, progress=None, world_id=None):
    from ..content.pack import load_canon
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    from ..kernel.clock import now
    from ..kernel.store import Store, wall_clock_iso
    from ..lanes.client import LaneClient
    from ..world.worldgen.pipeline import run_worldgen
    if world_id is not None:
        raise NotImplementedError("P12")
    cd = Path(config.content_dir)
    own = pc_ref.split(":", 1)[0]
    dirs = [cd / "core"] + [cd / p for p in settings.pack_ids
                            if p != "core" and (not p.startswith("cheat_") or p == own)]      # CHEAT-10, CHEAT-12
    if settings.wild_card:                                                                   # CHEAT-15
        from ..content.pack import cheat_records
        wild = sorted({r.split(":", 1)[0] for r, rec in cheat_records(cd).items() if "wild_card" in (rec.tags or [])})
        dirs += [cd / p for p in wild if cd / p not in dirs]
    canon, issues = load_canon(dirs)
    if any(i.severity == "error" for i in issues):
        raise RunError("content_missing", "A content pack this run needs has errors; check it on the Content screen.")
    try:
        pc = canon.get(pc_ref)
        ok = pc_ref.split(":", 1)[1].split("/", 1)[0] == "pc"
    except (KeyError, IndexError):
        ok = False
    if not ok:
        raise RunError("not_found", f"There is no character called {pc_ref}.")
    seed = settings.seed if settings.seed is not None else int(hashlib.sha256((wall_clock_iso() + pc_ref).encode()).hexdigest()[:15], 16)
    settings = settings.model_copy(update={"seed": seed})
    rid = _new_run_id(config, pc.card.display_name, seed)
    wid = _new_world_id(config, seed)
    rd = runs_dir(config) / rid
    wdir = runs_dir(config) / "_worlds" / wid
    store = None
    try:
        for sub in ("saves", "autosave", "logs", "reports"):
            (rd / sub).mkdir(parents=True, exist_ok=True)
        store = Store.create(str(rd / "world.sqlite"), run_id=rid, seed=seed, settings_json=settings.model_dump_json(),
                             content_hash=canon.content_hash, start_ms=0, rules_json=config.rules.model_dump_json())
        store.attach(canon=canon, rules=config.rules)
        client = LaneClient(config, transport)
        report = await run_worldgen(store, client, canon, pc_ref, settings, config, run_id=rid, world_id=wid,
                                    world_dir=wdir, progress=progress)
        with store.transaction() as tx:
            tx.commit_event(Event(type=EventType.SETTINGS_CHANGE, writer="kernel.meta", at=now(tx), turn_index=0, origin="system",
                                  payload={"source": "worldgen", "world_id": wid},
                                  writes=[WriteRecord(op=WriteOp.UPSERT, table="meta", key={"key": "world_id"},
                                                      values={"key": "world_id", "value": wid})]))
        if pc.generation == "cheat":                                 # D-102: a life the code opened
            from ..cheats.commands import start_life
            with store.transaction() as tx:
                start_life(tx, tx.query_one("SELECT value FROM meta WHERE key='pc_actor_id'")[0], pc)
        store.backup_to(rd / "turn0.sqlite")
        store.close()
        store = None
    except BaseException:
        if store is not None:
            try:
                store.close()
            except Exception:  # noqa: BLE001
                pass
        shutil.rmtree(rd, ignore_errors=True)
        shutil.rmtree(wdir, ignore_errors=True)
        raise
    s = _open_session(config, rd, transport, dirs, canon=canon)
    s.extras["pack_dirs"] = [str(p) for p in dirs]
    s.extras["notices"] = [f"{canon.get(ref).identity.name} is not in this world: {why}." for ref, why in report.skipped_actors]
    s.extras["worldgen_report"] = report
    write_manifest(s)
    return s
