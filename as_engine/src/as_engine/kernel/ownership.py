"""Table ownership (rule STORE-02 / SCOPE-01).

Every table in schema.sql has exactly one owner module. ``Store.commit_event`` rejects any
WriteRecord whose table is not owned by the event's ``writer`` with ``ScopeError``.
This dict must match the ``-- OWNER`` comments in schema.sql (tested by STORE-03).
"""

TABLE_OWNERS: dict[str, str] = {
    "meta": "kernel.meta",
    "counters": "kernel.meta",
    "blobs": "kernel.meta",
    "world_clock": "kernel.clock",
    "event_queue": "kernel.clock",
    "rng_streams": "kernel.rng",
    "prng_ledger": "kernel.rng",
    "events": "kernel.events",
    "turn_ledger": "turn.pipeline",
    "player_inputs": "turn.pipeline",
    "pending_reactions": "turn.pipeline",
    "scenes": "turn.pipeline",
    "lm_calls": "lanes",
    "audit_log": "audit",
    "error_repair_log": "audit",
    "commit_gate_log": "audit",
    "cheat_log": "cheats",
    "claims": "kernel.truth",
    "zones": "physical.space",
    "places": "physical.space",
    "anchors": "physical.space",
    "portals": "physical.space",
    "routes": "physical.space",
    "positions": "physical.space",
    "bodies": "physical.bodies",
    "wounds": "physical.bodies",
    "needs": "physical.bodies",
    "infections": "physical.bodies",
    "conditions": "physical.bodies",
    "grips": "physical.bodies",
    "infected_state": "world.infected",
    "items": "physical.objects",
    "lots": "physical.objects",
    "actors": "mind.actor",
    "dossiers": "mind.actor",
    "dossier_deltas": "mind.actor",
    "voice_lines": "mind.actor",
    "plans": "mind.actor",
    "tasks": "action.tasks",
    "propositions": "mind.perception",
    "claim_holdings": "mind.perception",
    "percept_log": "mind.perception",
    "known_places": "mind.perception",
    "acquaintance": "mind.perception",
    "relationships": "mind.mind",
    "refusals": "mind.mind",
    "open_loops": "mind.mind",
    "lessons": "mind.mind",
    "tempers": "mind.temper",
    "episodes": "mind.memory",
    "memory_jobs": "mind.memory",
    "promises": "mind.promise",
    "groups": "society.group",
    "group_members": "society.group",
    "group_standing": "society.group",
    "tension": "society.group",
    "households": "society.household",
    "household_members": "society.household",
    "routines": "society.routine",
    "settlements": "society.settlement",
    "laws_active": "society.settlement",
    "workplaces": "society.work",
    "work_assignments": "society.work",
    "cohorts": "society.population",
    "world_params": "world.worldgen",
    "history_events": "world.worldgen",
    "operations": "world.worldmove",
    "traces": "world.traces",
    "rumours": "world.rumours",
    "infected_pools": "world.hordes",
    "hordes": "world.hordes",
    "narration": "narration.narrator",
    "narrator_state": "narration.narrator",
    "echo_ledger": "narration.lint",
    "story_log": "service",
}

# Bookkeeping tables are written directly by their owner through ``Tx.bookkeep`` (never through
# events). They are the machinery that makes replay possible. Every OTHER table is a "world table"
# and may only change through ``Tx.commit_event`` WriteRecords (rule STORE-01).
BOOKKEEPING_TABLES: frozenset[str] = frozenset({
    "counters", "blobs", "rng_streams", "prng_ledger", "events", "turn_ledger", "lm_calls",
    "audit_log", "error_repair_log", "commit_gate_log", "story_log",
})

# world_state_hash() covers every world table plus `meta` (event-apply replay reproduces these).
# full_state_hash() additionally covers counters, rng_streams, prng_ledger and events
# (re-simulation replay with recorded model outputs reproduces these too).
WORLD_HASH_EXCLUDED: frozenset[str] = BOOKKEEPING_TABLES
FULL_HASH_EXCLUDED: frozenset[str] = frozenset({
    "lm_calls", "turn_ledger", "audit_log", "error_repair_log", "commit_gate_log", "story_log", "blobs",
})

MODULES: tuple[str, ...] = tuple(sorted(set(TABLE_OWNERS.values())))

# Modules that write EVENTS but own no table (their events carry no WriteRecords): the resolver's
# ACTION_* / CHECK_RESOLVED events and propagation's NOISE / SPEECH / LIGHT events. A valid
# events.writer is any of these or a table owner (commit-gate bit G08).
WRITER_ONLY_MODULES: tuple[str, ...] = ("action.propagate", "action.resolve", "world.factions")
EVENT_WRITERS: tuple[str, ...] = tuple(sorted(set(MODULES) | set(WRITER_ONLY_MODULES)))
