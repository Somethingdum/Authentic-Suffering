"""Run library (P7 create-from-scenario, P10 create-from-worldgen, P12 worlds). Rules RUN-01..11.

Layout (RUN-01): <runs_dir>/<run_id>/ world.sqlite (the live run), turn0.sqlite (the run at
  turn 0, before any turn: service.replay re-simulates from it, DET-02; not a world's genesis), manifest.json,
  saves/<slot>.sqlite + saves/<slot>.json, autosave/auto_<k>.sqlite + auto_<k>.json, logs/,
  reports/. Folders whose name starts with '_' (e.g. _worlds/) are not runs.
run_id = f"{slug(pc display name)}_{seed:x}", then '_2', '_3', … while that folder exists.
slug(text) = lowercase, every run of characters other than a-z 0-9 -> '_', stripped of '_'
  ('run' when empty). sha256_file(path) = sha256 hex of the file's bytes.
RunError(code, message): every refusal here; ``code`` is machine-readable, ``message`` a plain
  sentence (codes: not_found, ironman, run_final, save_corrupt, content_missing).

manifest.json (write_manifest(session) -> dict, written sorted-keys, 2-space indent):
  {run_id, title = f"{pc display name}, day {day}", pc_name, created_at_real (kept from the old
  manifest), last_played_real (kernel.store.wall_clock_iso(): the wall clock appears only in meta
  and in files outside the store), day (world_time(now).day), turn_index, alive, final (kept from
  the old manifest, else false; RUN-08), difficulty (settings value), ironman (save_mode ==
  'ironman'), sandbox (meta.sandbox == '1'), schema_version, content_hash (meta), engine_version
  (as_engine.__version__), world_state_hash, pack_dirs (session.extras['pack_dirs'], as strings),
  world_id (meta or null)}. created_at_real: the old manifest's, else now.

create_run_from_scenario(config, scenario_path, transport, *, settings=None, packs_root=None,
                         core_pack_dir=None) -> Session   (P7; tests and `as-engine new-scenario`)
  packs_root defaults to config.content_dir, core_pack_dir to content_dir/core.
  w = testing.scenario.load_scenario(path, packs_root, core_pack_dir, transport). settings given
  -> one SETTINGS_CHANGE event {source: 'run_start'} (writer 'kernel.meta', origin 'system', at
  now, turn 0) updating meta settings_json to settings.model_dump_json(). run_id from the PC's
  display name and the scenario's seed (above). The run folder and its sub-folders are made; the
  store is copied with Store.backup_to to world.sqlite AND turn0.sqlite; the memory store is closed;
  the session is
  opened on world.sqlite (below) with the scenario's canon; extras['pack_dirs'] = [core] +
  [packs_root / p for p in the scenario's packs]; write_manifest.
Opening a session (create and load): Store.open(world.sqlite); canon = content.pack.load_canon(
  pack dirs) (the loaded one when creating); rules = RulesConfig from meta.rules_json (the run's
  frozen rules, SET-03; the defaults when it is missing, '' or '{}'); store.attach(canon, rules);
  config' = config with those rules; settings
  from meta.settings_json; Session(run_id = the folder name, run_dir, store, canon, config',
  settings, Rng(meta.seed), LaneClient(config', transport), pc_id = meta.pc_actor_id);
  extras['pack_dirs'] = the pack dirs as strings.

save_run(session, slot_name) -> Path   (RUN-03)
  Ironman -> RunError('ironman', "Ironman runs keep only the autosave. Your progress is saved after
  every turn."). slot = slug(slot_name). The copy: saves/<slot>.tmp (an old one is removed first)
  = Store.backup_to, and its sha256; the file re-hashed must match (else it is renamed
  saves/<slot>.partial and RunError('save_corrupt', "The save did not write correctly; your
  previous save is kept.")); then it replaces saves/<slot>.sqlite and saves/<slot>.json = {slot,
  label = slot_name, turn_index, sha256, world_state_hash, saved_real = wall_clock_iso()} (sorted
  keys, 2-space indent); write_manifest. Returns the .sqlite path.
autosave(session) -> Path   (RUN-02; stage 19)
  k = turn_index % settings.autosave_ring; the same copy-then-replace (autosave/auto_<k>.tmp) into
  autosave/auto_<k>.sqlite with auto_<k>.json {slot: f"auto_{k}", turn_index, sha256,
  world_state_hash, saved_real}; write_manifest. Returns the .sqlite path.
load_run(config, run_id, transport, save_slot=None, *, pack_dirs=None) -> Session   (RUN-05)
  No manifest -> RunError('not_found', f"There is no run called {run_id}."); manifest final ->
  RunError('run_final', "That run ended with a death in Ironman. You can look back at it, but not
  play on."). save_slot given: manifest ironman -> RunError('ironman', "Ironman runs load from the
  autosave only."); saves/<slug>.sqlite OR its .json missing -> RunError('not_found', f"There is
  no save called {save_slot}."); its sha256 differs from the .json's -> RunError('save_corrupt',
  "That save file is damaged and cannot be loaded."); else it is copied over world.sqlite
  (loading a save goes back to it) and the expected world_state_hash becomes the save's. Open the
  session with ``pack_dirs`` or the manifest's. RUN-10: every content ref the run uses
  (items.def_ref, bodies.content_ref,
  dossiers.content_ref, laws_active.law_ref, groups.content_ref; sorted, distinct) must resolve in
  the canon, else the store is closed and RunError('content_missing', one line per ref: "Your run
  uses '<ref>', which is no longer in any pack.", lines joined by newlines). Then, in this order:
  notices (extras['notices']) start with "Your content changed since this run started. People
  already in the world keep who they were." when meta.content_hash != canon.content_hash;
  mind.actor.fused for every actor (by id: a dossier that no longer fuses fails here, not
  mid-turn); store.rebuild_fts(); then "This run's files do not match their last save record. It
  loaded, but something may have been changed outside the game." when world_state_hash != the
  expected one.
list_runs(config) -> list[RunSummaryView]
  Every non-'_' folder with a manifest: RunSummaryView(run_id, title, pc_name, day, alive,
  difficulty, last_played_text = last_played_real[:16] with 'T' -> ' ', sandbox, ironman,
  world_id), newest last_played_real first (then run_id descending).
delete_run(config, run_id)   (RUN-06): no manifest -> RunError('not_found'); else the folder is
  removed (hard delete).
Ironman (RUN-04): the run keeps only the autosave ring and world.sqlite; save_run and loading a
  named save are refused (code 'ironman'); "Continue" = load_run without a slot.
New life in the same world (RUN-07, free save mode only, P12): after the PC dies, a new PC dossier is
  materialised into the same run at a place chosen like worldgen WG8 would; the dead PC stays a
  body (corpse, items) and every relationship/rumour about them persists. PC_CONTROL_CHANGE event.
Ironman death (RUN-08): death ends the run. The run folder is kept read-only (manifest
  alive=false, final=true) so the death screen and the reveal still work, but run_load refuses it
  (error code 'run_final'), new_life_here is refused (error code 'ironman'), and the autosave
  ring is deleted. The player may start a NEW run in the same world's genesis (RUN-09) or a new world.
  (Carries the Codex Ultima ruling "death is permadeath" as the Ironman rule; free mode keeps
  loading and new-life-here. See DECISIONS.md D-12.)
Worlds (RUN-09): every worldgen run writes <runs_dir>/_worlds/<world_id>/genesis.sqlite — a backup
  of the store taken after stage WG7 (world built, laws set) and BEFORE WG8 places a PC — plus
  world.json (WorldSummaryView fields + params + content_hash). world_id = the creating run_id.
  create_run(..., world_id=X) copies X's genesis.sqlite into the new run and runs only WG8-WG9 for
  the new PC (the PC's worldgen_bias is ignored because the world already exists; its plausibility
  gate is evaluated against the stored WorldParams and a hard fail at Bitch..Realism refuses the
  start with a plain message). Model-written worldgen text is not reproducible from a seed, so a
  world is shared as a FILE, never as a seed: world_export zips genesis.sqlite + world.json into
  '<world_id>.asworld'; world_import validates the zip (schema_version, required meta keys,
  content_hash — a content mismatch is a warning), assigns a new world_id if taken, source
  'imported'. (Carries the Codex Ultima BaselineWorldFile ruling; D-13.)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.settings import EngineConfig, RunSettings
    from ..contracts.view import RunSummaryView
    from .session import Session


class RunError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def slug(text: str) -> str:
    raise NotImplementedError("P7")


def sha256_file(path: str | Path) -> str:
    raise NotImplementedError("P7")


def write_manifest(session: "Session") -> dict:
    raise NotImplementedError("P7")


def list_runs(config: "EngineConfig") -> list["RunSummaryView"]:
    raise NotImplementedError("P7")


def create_run_from_scenario(config: "EngineConfig", scenario_path: str | Path, transport, *,
                             settings: "RunSettings | None" = None, packs_root: str | Path | None = None,
                             core_pack_dir: str | Path | None = None) -> "Session":
    """Used by tests, `as-engine new-scenario` and the 'First playable' slice: a run from a scenario YAML."""
    raise NotImplementedError("P7")


async def create_run(config: "EngineConfig", pc_ref: str, settings: "RunSettings", transport,
                     progress=None, world_id: str | None = None) -> "Session":
    """Worldgen path (P10, RUN-11); world_id reuse path (P12, RUN-09).

    world_id given -> NotImplementedError('P12'). canon = content.pack.load_canon([content_dir /
    'core'] + [content_dir / p for p in settings.pack_ids if p != 'core']) (an error-severity issue
    -> RunError('content_missing', "A content pack this run needs has errors; check it on the
    Content screen.")). pc = the canon record at pc_ref, which must be of kind 'pc' (none, or
    another kind -> RunError('not_found', f"There is no character called {pc_ref}.")). seed = settings.seed, else int(sha256((wall_clock_iso() +
    pc_ref).encode()).hexdigest()[:15], 16) — the one place a new seed comes from outside the Rng.
    run_id as RUN-01 (pc.card.display_name); world_id = f"w_{seed:x}", then '_2', '_3', … while
    <runs_dir>/_worlds/<world_id> exists. The run folder and its sub-folders (saves, autosave,
    logs, reports) are made; store = Store.create(run_dir / 'world.sqlite', run_id=run_id,
    seed=seed, settings_json = settings JSON (seed filled in), content_hash = canon.content_hash,
    start_ms 0, rules_json = config.rules JSON);
    store.attach(canon, config.rules); client = LaneClient(config, transport).
    report = await world.worldgen.pipeline.run_worldgen(store, client, canon, pc_ref, settings,
    config, run_id=run_id, world_id=world_id, world_dir = runs_dir / '_worlds' / world_id,
    progress=progress). One kernel.meta event SETTINGS_CHANGE {source: 'worldgen', world_id}
    (at kernel.clock.now, turn_index 0, origin 'system') writes meta UPSERT {key 'world_id', value
    world_id}. Every model call worldgen made is in lm_calls (turn 0). Then
    store.backup_to(run_dir / 'turn0.sqlite'); the store is closed; the session is opened as
    "Opening a session" says, with extras['pack_dirs'] = the pack dirs used, extras['notices'] =
    one plain line per report.skipped_actors entry (f"{name} is not in this world: {reason}.",
    name = that dossier's identity.name) and
    extras['worldgen_report'] = report; write_manifest(session). Returns the session.

    Cancellation (worldgen_cancel): the caller cancels the task running this coroutine. The
    CancelledError arrives at the next await (a CPU step already running in a thread finishes
    first); create_run then closes the store, deletes the partial <runs_dir>/<run_id>/ folder (and,
    for a new world, its _worlds/<world_id>/ folder) and re-raises. A WorldgenAborted or any other
    exception cleans up the same way and propagates. A cancelled or failed run never appears in
    list_runs, and no world is left half-made."""
    raise NotImplementedError("P10")


def list_worlds(config: "EngineConfig") -> list:
    """WorldSummaryView per <runs_dir>/_worlds/* (P12)."""
    raise NotImplementedError("P12")


def export_world(config: "EngineConfig", world_id: str) -> tuple[str, bytes]:
    """(filename, zip bytes) (P12)."""
    raise NotImplementedError("P12")


def import_world(config: "EngineConfig", filename: str, data: bytes) -> str:
    """Returns the new world_id (P12)."""
    raise NotImplementedError("P12")


def load_run(config: "EngineConfig", run_id: str, transport, save_slot: str | None = None, *,
             pack_dirs: list[str | Path] | None = None) -> "Session":
    raise NotImplementedError("P7")


def save_run(session: "Session", slot_name: str) -> Path:
    raise NotImplementedError("P7")


def autosave(session: "Session") -> Path:
    raise NotImplementedError("P7")


def delete_run(config: "EngineConfig", run_id: str) -> None:
    raise NotImplementedError("P7")
from ._impl_runs import RunError, slug, sha256_file, create_run_from_scenario, save_run, autosave, load_run, list_runs, delete_run, write_manifest  # noqa
from ._impl_runs import create_run  # noqa
