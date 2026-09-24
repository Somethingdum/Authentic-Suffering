"""Gated worldgen pipeline (P10). docs/as/06_WORLD.md §1. Rules WG-10..37, WG-DET-01, RUN-09.
[SALVAGE: World Generation Protocol v11.3.2d — gates without conversational ceremony.]

async run_worldgen(store, client, canon, pc_ref, settings, config, *, run_id, world_id, world_dir,
                   progress=None) -> WorldgenReport
  ``store`` is a new, empty run store (service.runs.create_run made it with start_ms 0 and the run's
  meta); ``client`` a lanes.client.LaneClient; ``progress`` an optional callable(WorldgenProgress)
  (it may be async: awaited when it returns an awaitable). rng = Rng(meta.seed); pc = the canon
  PCDossier at pc_ref; detail = settings.world_detail value; T = tables.DETAIL_TIERS[detail].
  Stages run in atlas.STAGES order, EACH IN ITS OWN TRANSACTION. Before a stage starts:
  progress(WorldgenProgress(stage, label = atlas.STAGE_LABELS[stage], pct = the sum of
  atlas.STAGE_SHARE of the earlier stages, eta_s = the remaining share x T['est_minutes'] x 60 / 100)).
  Every stage ends with one closing WORLDGEN_STAGE {stage} that writes nothing (COMMIT's is {stage
  'COMMIT', world_id}); worldgen's own rows are written by earlier WORLDGEN_STAGE events of the same
  stage: WG0 {stage, patches: the number of qc patches} (world_params), WG2 {stage, events: n}
  (history_events), WG8 {stage, personal: n} (the PC's history) and {stage, commit: true}
  (world_params.commit_json). All of them: writer 'world.worldgen', origin 'worldgen', turn_index 0,
  at = the stage's at (WG0's row event: the clock before it moves).
    WG0  (params, patches) = params.generate_params(rng, tx, settings.difficulty, settings.era,
         pc.worldgen_bias, settings.days_since_fall); placement = placement.place(...);
         qc = placement.qc(...) — result 'aborted' -> WorldgenAborted('hopeless_start', its message,
         options ['difficulty_lower', 'change_character', 'change_era']). world_params row {id 1,
         params_json = the (possibly patched) WorldParams JSON, commit_json '{}'} in the WG0 row
         event; then kernel.clock.advance_event(tx, dsf x DAY + WorldRules.start_hour x H,
         'worldgen'). at for every later stage = that time.
    WG1  region = region.build_region(...); region.assert_region(tx, region).
    WG2  plan = history.plan_polity(...); events = history.skeleton(...); await
         history.write_history(...); history.mark_held(...).
    WG3  polity.write_groups.   WG4 polity.write_settlements.   WG5 polity.write_cohorts.
    WG6  people = await people.write_people(...).   WG7 polity.write_laws.
    P10 (progress v2, service.progress): WG2's history.write_history and WG6's people.write_people
         are passed progress=sub, an async callable(done, total) that they await after each
         history batch and after each WORLDGEN_ACTOR answer (completion order; done counts
         1..total); sub turns each call into
         progress(WorldgenProgress(stage, label, pct = the stage's start pct + STAGE_SHARE[stage] x
         done / total (rounded to 1), eta_s as above, sub = 'history' | 'dossiers', done, total)).
         With no model calls to make (total 0) nothing is reported.
    GENESIS (after WG7, before WG8; no progress message of its own): world_dir is made; store.backup_to(world_dir /
         'genesis.sqlite', as_world=world_id) — the finished world before any PC exists, naming no
         run (RUN-09) — and world.json =
         {world_id, title = f"{climate_descriptor capitalised} — {atlas.ERA_LABELS[era]}, day {dsf}", difficulty,
         era, day_at_genesis: dsf, climate_text, factions: [planned faction names], created_real:
         kernel.store.wall_clock_iso(), source 'generated', seed, detail} (sorted keys, 2-space indent).
    WG8  opening = await opening.place_pc(...).
    WG9  failures = checks.assert_world(...); any -> WorldgenAborted('invariant', "The world did not
         hold together: " + "; ".join(each failure without its final full stop) + ".").
    COMMIT WORLDGEN_STAGE {stage 'COMMIT', world_id}.
  Origins: every event a worldgen stage commits itself, and every one it commits through a
  function that takes an origin (physical.bodies.create, physical.objects.create, mind.actor.create,
  society.population.materialise, world.infected.spawn), is origin 'worldgen'; the few committed
  through functions without one (physical.space.place_body / change_place, world.traces.create,
  mind.mind relation seeds) keep 'sim'. Nothing reads the origin of a turn-0 event.
  Every stage function is called through its module (region.build_region, history.write_history,
  checks.assert_world, …), never through a name imported into this one: the P10 tests replace one to
  make a stage fail.
  Retry (WG-DET-01): a WorldgenAssertion raised inside a stage rolls that stage's transaction back;
  the stage runs once more, in a new transaction that first makes one rng.draw(tx, stream, 'retry',
  2) on each stream the stage draws from, in this order — WG0 'worldgen:params' and
  'worldgen:placement'; WG1 'worldgen:region'; WG2 'worldgen:history' and 'worldgen:placement'; WG4
  and WG5 'worldgen:polity'; WG6 'worldgen:people'; WG8 'worldgen:opening'; none for WG3, WG7, WG9 —
  so it sees fresh numbers (the rolled-back transaction took its draws with it). The stage's
  progress message is not repeated; the stage name is added to report.retries. A second
  WorldgenAssertion -> WorldgenAborted('stage_failed', f"{label} failed twice: {message}").
  Call log: for the whole run client.on_call is set to record every call into the current stage's
  transaction (lanes.calllog.record, turn_index 0) and count it in report.model_calls; the previous
  on_call is restored at the end, whatever happens.
  Model calls never abort worldgen: every call has a code fallback (history skeleton text, skeleton
  dossiers, fallback_opening), so a world is always complete — with the lanes down it is plainer
  to read, never broken.
  Returns WorldgenReport(world_id, stages: [stage names run], qc_result, qc_patches, skipped_actors:
  [(ref, reason)], retries: [stage names], model_calls: int).
  Determinism (WG-DET-01): the same seed, settings, packs and model answers give the same world:
  every table has the same kernel.hashing.table_digest, except meta, which differs only in
  created_at_real (the wall-clock moment the run was made; so world_state_hash, which covers meta,
  matches once that one value is the same). With the fake model's defaults, the same seed gives
  the same world.

Worldgen never pre-scripts outcomes (who betrays, dies, befriends) — WG-30.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...kernel.errors import ASError


class WorldgenAborted(ASError):
    """Worldgen stopped without a world. ``code``: 'hopeless_start' | 'invariant' | 'stage_failed';
    ``options``: what the New Life wizard offers ('difficulty_lower', 'change_character',
    'change_era')."""

    rule = "WG-14"

    def __init__(self, code: str, message: str, options: list[str] | None = None):
        super().__init__(message)
        self.code = code
        self.options = list(options or [])


class WorldgenAssertion(ASError):
    """A stage's own check failed (the pipeline retries the stage once)."""

    rule = "WG-15"

    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


@dataclass
class WorldgenReport:
    world_id: str
    stages: list[str] = field(default_factory=list)
    qc_result: str = "pass"
    qc_patches: list[str] = field(default_factory=list)
    skipped_actors: list[tuple[str, str]] = field(default_factory=list)
    retries: list[str] = field(default_factory=list)
    model_calls: int = 0


async def run_worldgen(store, client, canon, pc_ref: str, settings, config, *, run_id: str, world_id: str,
                       world_dir, progress=None) -> WorldgenReport:
    raise NotImplementedError("P10")
from ._impl_wg import run_worldgen  # noqa
