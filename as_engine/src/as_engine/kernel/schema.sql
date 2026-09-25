-- Authentic Suffering run database, schema version 1.
-- One SQLite file per run: as_runs/<run_id>/world.sqlite  (WAL mode, foreign_keys ON).
-- Conventions:
--   * world time columns are INTEGER milliseconds since the world epoch (Fall day 0, 00:00)
--   * booleans are INTEGER 0/1; JSON columns are TEXT holding canonical JSON
--     (json.dumps(obj, sort_keys=True, separators=(',', ':')))
--   * every table has exactly one OWNER module (kernel/ownership.py TABLE_OWNERS). Only events whose
--     `writer` equals that owner may write it (rule STORE-02 / SCOPE-01).
--   * ids are minted by kernel.ids: '<kind>_<6 digits>' e.g. act_000012, plc_000003.

PRAGMA foreign_keys = ON;

-- ===================================================================== kernel
-- OWNER kernel.meta
CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
-- required keys: run_id, seed, schema_version, created_at_real, content_hash, settings_json,
--                rules_json, pc_actor_id, sandbox ('0'|'1'), cheat_active ('0'|'1'), world_epoch_text
-- optional keys: god_bodies (JSON list), world_id, final ('1' after an Ironman death)

-- OWNER kernel.meta
CREATE TABLE counters (
  kind TEXT PRIMARY KEY,
  next INTEGER NOT NULL CHECK (next >= 1)
);

-- OWNER kernel.meta
CREATE TABLE blobs (
  hash    TEXT PRIMARY KEY,           -- sha256 hex of content
  content TEXT NOT NULL
);

-- OWNER kernel.clock
CREATE TABLE world_clock (
  id          INTEGER PRIMARY KEY CHECK (id = 1),
  now_ms      INTEGER NOT NULL CHECK (now_ms >= 0),
  turn_index  INTEGER NOT NULL CHECK (turn_index >= 0),
  weather     TEXT NOT NULL DEFAULT 'clear',     -- clear|overcast|rain|storm|fog|wind|heat|snow
  wind_level  INTEGER NOT NULL DEFAULT 0 CHECK (wind_level BETWEEN 0 AND 3)
);

-- OWNER kernel.clock   (future scheduled events; the Timer Bank is a view over this + next_due columns)
CREATE TABLE event_queue (
  queue_id        TEXT PRIMARY KEY,
  due_at          INTEGER NOT NULL,
  type            TEXT NOT NULL,
  subject_id      TEXT,
  payload         TEXT NOT NULL DEFAULT '{}',
  source_event_id TEXT,
  status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','fired','cancelled'))
);
CREATE INDEX event_queue_due ON event_queue(status, due_at);

-- OWNER kernel.rng
CREATE TABLE rng_streams (
  stream TEXT PRIMARY KEY,
  state  TEXT NOT NULL                -- 4 x 64-bit words, lowercase hex, '-' separated
);

-- OWNER kernel.rng
CREATE TABLE prng_ledger (
  seq        INTEGER PRIMARY KEY,     -- 1,2,3... assigned by kernel.rng
  turn_index INTEGER NOT NULL,
  stream     TEXT NOT NULL,
  purpose    TEXT NOT NULL,
  n          INTEGER NOT NULL,
  value      INTEGER NOT NULL
);

-- OWNER kernel.events   (the event log; append-only; never UPDATE, never DELETE)
CREATE TABLE events (
  event_id       TEXT PRIMARY KEY,
  seq            INTEGER NOT NULL UNIQUE,
  at             INTEGER NOT NULL,
  type           TEXT NOT NULL,
  writer         TEXT NOT NULL,
  actor_id       TEXT,
  target_ids     TEXT NOT NULL DEFAULT '[]',
  place_id       TEXT,
  cause_event_id TEXT REFERENCES events(event_id),
  payload        TEXT NOT NULL DEFAULT '{}',
  state_delta    TEXT NOT NULL DEFAULT '[]',   -- JSON list of WriteRecord
  rule_cited     TEXT,
  turn_index     INTEGER NOT NULL,
  origin         TEXT NOT NULL DEFAULT 'sim' CHECK (origin IN ('sim','worldgen','cheat','migration','system')),
  links          TEXT NOT NULL DEFAULT '[]'    -- C10 (STORE-12): JSON list of {event_id, role}, the causes besides cause_event_id
);
CREATE INDEX ev_at ON events(at);
CREATE INDEX ev_cause ON events(cause_event_id);
CREATE INDEX ev_place_at ON events(place_id, at);
CREATE INDEX ev_turn ON events(turn_index);
CREATE INDEX ev_type ON events(type);

-- ===================================================================== turn
-- OWNER turn.pipeline
CREATE TABLE turn_ledger (
  turn_index   INTEGER NOT NULL,
  stage        INTEGER NOT NULL CHECK (stage BETWEEN 0 AND 19),
  run_count    INTEGER NOT NULL DEFAULT 1,
  status       TEXT NOT NULL CHECK (status IN ('ok','failed','skipped','degraded','rolled_back')),
  output_ref   TEXT,                 -- blob hash of the stage output summary
  detail       TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY (turn_index, stage)
);

-- OWNER turn.pipeline
CREATE TABLE player_inputs (
  turn_index    INTEGER PRIMARY KEY,
  mode          TEXT NOT NULL CHECK (mode IN ('do','say','ask','suggestion','cheat')),
  raw_text      TEXT NOT NULL,
  received_hash TEXT NOT NULL,       -- sha256 of raw_text as received from the socket
  mapped        TEXT NOT NULL DEFAULT '{}'
);

-- OWNER turn.pipeline
CREATE TABLE pending_reactions (
  reaction_id TEXT PRIMARY KEY,
  actor_id    TEXT NOT NULL,
  intent      TEXT NOT NULL,         -- JSON: validated intent to resolve at the start of next transaction
  created_turn INTEGER NOT NULL,
  status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','resolved','cancelled'))
);

-- OWNER turn.pipeline
CREATE TABLE scenes (
  scene_id     TEXT PRIMARY KEY,
  problem      TEXT NOT NULL,
  place_id     TEXT,
  participants TEXT NOT NULL DEFAULT '[]',
  started_at   INTEGER NOT NULL,
  ended_at     INTEGER,
  agency_level TEXT NOT NULL CHECK (agency_level IN ('high','low','passive')),
  chunk_count  INTEGER NOT NULL DEFAULT 0,
  chunk_estimate INTEGER NOT NULL,
  chunk_max    INTEGER NOT NULL,
  completion_conditions TEXT NOT NULL DEFAULT '[]',
  failure_conditions    TEXT NOT NULL DEFAULT '[]',
  open_loops   TEXT NOT NULL DEFAULT '[]',
  status       TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','ended'))
);

-- OWNER lanes
CREATE TABLE lm_calls (
  turn_index   INTEGER NOT NULL,
  seq          INTEGER NOT NULL,
  call_class   TEXT NOT NULL,
  lane         TEXT NOT NULL,
  actor_id     TEXT,
  status       TEXT NOT NULL,
  latency_ms   INTEGER NOT NULL,
  prompt_tokens INTEGER NOT NULL DEFAULT 0,
  completion_tokens INTEGER NOT NULL DEFAULT 0,
  request_hash TEXT NOT NULL,
  response_text TEXT NOT NULL,       -- kept for deterministic replay (ReplayTransport)
  cache_key    TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (turn_index, seq)
);

-- ===================================================================== audit
-- OWNER audit
CREATE TABLE audit_log (
  audit_id   TEXT PRIMARY KEY,
  turn_index INTEGER NOT NULL,
  gate       TEXT NOT NULL,          -- e.g. 'G15-portrayal', 'G18-lint'
  producer   TEXT NOT NULL,          -- call id or module that produced the artifact
  judge      TEXT NOT NULL,          -- call id or module that judged it; MUST differ from producer
  result     TEXT NOT NULL CHECK (result IN ('pass','fail','warn')),
  findings   TEXT NOT NULL DEFAULT '[]',
  CHECK (producer <> judge)
);

-- OWNER audit
CREATE TABLE error_repair_log (
  entry_id   TEXT PRIMARY KEY,
  turn_index INTEGER NOT NULL,
  at_ms      INTEGER NOT NULL,
  kind       TEXT NOT NULL,          -- grammar_fail|schema_fail|hallucinated_ref|lane_down|timeout|lint_fail|rollback|degraded|migration|budget_overrun|unknown_name (B5 MEM-18)
  stage      INTEGER,
  rule_id    TEXT,
  detail     TEXT NOT NULL DEFAULT '{}',
  repaired   INTEGER NOT NULL DEFAULT 0
);

-- OWNER audit
CREATE TABLE commit_gate_log (
  turn_index INTEGER PRIMARY KEY,
  session_bits  TEXT NOT NULL,       -- 12 chars of 0/1
  world_bits    TEXT NOT NULL,       -- 16
  entities_bits TEXT NOT NULL,       -- 16
  global_bits   TEXT NOT NULL,       -- 14
  passed     INTEGER NOT NULL,
  failures   TEXT NOT NULL DEFAULT '[]'
);

-- OWNER cheats
CREATE TABLE cheat_log (
  entry_id    TEXT PRIMARY KEY,
  turn_index  INTEGER NOT NULL,
  command     TEXT NOT NULL,         -- verbatim
  outcome     TEXT NOT NULL,
  persona_line TEXT NOT NULL DEFAULT '',
  event_id    TEXT
);

-- ===================================================================== truth (kernel.truth)
-- OWNER kernel.truth   what is true. Read by resolver/worldgen/perception compiler ONLY.
CREATE TABLE claims (
  claim_id     TEXT PRIMARY KEY,
  subject_type TEXT NOT NULL CHECK (subject_type IN ('body','place','object','group','event','fact')),
  subject_id   TEXT NOT NULL,
  predicate    TEXT NOT NULL,
  object_value TEXT,
  true_from    INTEGER NOT NULL,
  true_until   INTEGER,
  origin_event TEXT NOT NULL
);
CREATE INDEX claims_subject ON claims(subject_type, subject_id);

-- ===================================================================== physical
-- OWNER physical.space
CREATE TABLE zones (
  zone_id    TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  kind       TEXT NOT NULL,          -- downtown|residential|industrial|riverside|rural|highway|wilds
  content_ref TEXT,
  danger     TEXT NOT NULL DEFAULT '{}'   -- JSON: infected density per type, hostile humans, hazards
);

-- OWNER physical.space
CREATE TABLE places (
  place_id     TEXT PRIMARY KEY,
  zone_id      TEXT REFERENCES zones(zone_id),
  parent_id    TEXT REFERENCES places(place_id),
  kind         TEXT NOT NULL CHECK (kind IN ('building','room','street','outdoor','vehicle','tunnel')),
  name         TEXT NOT NULL,
  archetype_ref TEXT,
  width_m      REAL NOT NULL DEFAULT 10,
  depth_m      REAL NOT NULL DEFAULT 10,
  indoor       INTEGER NOT NULL DEFAULT 1,
  material     TEXT NOT NULL DEFAULT 'drywall',
  light_level  INTEGER NOT NULL DEFAULT 2 CHECK (light_level BETWEEN 0 AND 4),  -- 0 pitch dark .. 4 bright
  ambient_db   REAL NOT NULL DEFAULT 30,
  layout_generated INTEGER NOT NULL DEFAULT 0,   -- rooms generated on first observation (PLMP, discovery)
  held         INTEGER NOT NULL DEFAULT 0,   -- 1 = the structure held through the Fall (WG-32): no interior damage pass
  props        TEXT NOT NULL DEFAULT '{}'
);

-- OWNER physical.space
CREATE TABLE anchors (
  anchor_id   TEXT PRIMARY KEY,
  place_id    TEXT NOT NULL REFERENCES places(place_id),
  name        TEXT NOT NULL,
  kind        TEXT NOT NULL,
  x_m         REAL NOT NULL,
  y_m         REAL NOT NULL,
  cover       INTEGER NOT NULL DEFAULT 0 CHECK (cover BETWEEN 0 AND 3),
  concealment INTEGER NOT NULL DEFAULT 0 CHECK (concealment BETWEEN 0 AND 3),
  capacity    INTEGER NOT NULL DEFAULT 4
);

-- OWNER physical.space   (orthogonal facts: open, locked, barricaded, damaged are independent)
CREATE TABLE portals (
  portal_id     TEXT PRIMARY KEY,
  place_a       TEXT NOT NULL REFERENCES places(place_id),
  place_b       TEXT NOT NULL REFERENCES places(place_id),
  anchor_a      TEXT REFERENCES anchors(anchor_id),
  anchor_b      TEXT REFERENCES anchors(anchor_id),
  kind          TEXT NOT NULL,
  name          TEXT NOT NULL,
  is_open       INTEGER NOT NULL DEFAULT 0,
  is_locked     INTEGER NOT NULL DEFAULT 0,
  lock_quality  INTEGER NOT NULL DEFAULT 0 CHECK (lock_quality BETWEEN 0 AND 4),
  barricade     INTEGER NOT NULL DEFAULT 0 CHECK (barricade BETWEEN 0 AND 3),
  damage        INTEGER NOT NULL DEFAULT 0 CHECK (damage BETWEEN 0 AND 3),
  strain_min    INTEGER NOT NULL DEFAULT 0 CHECK (strain_min >= 0),   -- P10: minutes a crowd leaned on it (INF-13)
  aperture_w_cm INTEGER NOT NULL,
  aperture_h_cm INTEGER NOT NULL,
  seal_db       REAL NOT NULL DEFAULT 25,
  open_loss_db  REAL NOT NULL DEFAULT 3,
  transparent   INTEGER NOT NULL DEFAULT 0,
  height_cm     INTEGER NOT NULL DEFAULT 0     -- obstacle height for climbing fences/walls/windows (0 = not climbable)
);

-- OWNER physical.space
CREATE TABLE routes (
  route_id    TEXT PRIMARY KEY,
  from_place  TEXT NOT NULL REFERENCES places(place_id),
  to_place    TEXT NOT NULL REFERENCES places(place_id),
  distance_m  REAL NOT NULL,
  terrain     TEXT NOT NULL DEFAULT 'street',
  danger      INTEGER NOT NULL DEFAULT 1 CHECK (danger BETWEEN 0 AND 10),
  known_by_default INTEGER NOT NULL DEFAULT 1
);

-- OWNER physical.space
CREATE TABLE positions (
  body_id    TEXT PRIMARY KEY,
  place_id   TEXT NOT NULL REFERENCES places(place_id),
  anchor_id  TEXT REFERENCES anchors(anchor_id),
  x_m        REAL NOT NULL,
  y_m        REAL NOT NULL,
  facing_deg REAL NOT NULL DEFAULT 0,
  hidden     INTEGER NOT NULL DEFAULT 0,   -- set by the hide effect (P5), cleared by any MOVE; optics subtracts 2
  since_ms   INTEGER NOT NULL
);
CREATE INDEX positions_place ON positions(place_id);

-- OWNER physical.bodies
CREATE TABLE bodies (
  body_id      TEXT PRIMARY KEY,
  kind         TEXT NOT NULL CHECK (kind IN ('human','infected','lurker','animal')),
  content_ref  TEXT,
  sex          TEXT,
  age_years    INTEGER,
  age_band     TEXT,
  height_cm    INTEGER NOT NULL,
  mass_kg      INTEGER NOT NULL,
  alive        INTEGER NOT NULL DEFAULT 1,
  dead_at      INTEGER,
  death_event  TEXT,
  awareness    TEXT NOT NULL DEFAULT 'awake',
  posture      TEXT NOT NULL DEFAULT 'standing',
  blood_loss_pct REAL NOT NULL DEFAULT 0,
  pain         INTEGER NOT NULL DEFAULT 0 CHECK (pain BETWEEN 0 AND 6),
  impairment   INTEGER NOT NULL DEFAULT 0 CHECK (impairment BETWEEN 0 AND 6),
  restrained   INTEGER NOT NULL DEFAULT 0,
  special      TEXT NOT NULL,        -- JSON {"S":..,"P":..,...}
  progressed_at INTEGER NOT NULL DEFAULT 0,   -- world time up to which bodies.progress() has run this body's clocks
  false_dead_until INTEGER,          -- infected only: lies still until this time (FALSE_DEATH), then REANIMATION
  core_intact  INTEGER NOT NULL DEFAULT 1,   -- infected only: 0 once the brainstem/upper spine is destroyed (true death)
  looks        TEXT,                          -- F1a: JSON contracts.dossier.Looks without outfit (what anyone can see); NULL = height and build only
  grime        INTEGER NOT NULL DEFAULT 0 CHECK (grime BETWEEN 0 AND 5),   -- F1a condition (LOOK-04)
  blood        INTEGER NOT NULL DEFAULT 0 CHECK (blood BETWEEN 0 AND 5),
  gore         INTEGER NOT NULL DEFAULT 0 CHECK (gore BETWEEN 0 AND 5),    -- the fluids of the dead on skin and clothes
  wet          INTEGER NOT NULL DEFAULT 0 CHECK (wet BETWEEN 0 AND 3),
  washed_at    INTEGER NOT NULL DEFAULT 0,
  origin       TEXT NOT NULL DEFAULT 'worldgen' CHECK (origin IN ('worldgen','birth','materialize','cheat','reanimation','scenario'))
);

-- OWNER physical.bodies
CREATE TABLE wounds (
  wound_id     TEXT PRIMARY KEY,
  body_id      TEXT NOT NULL REFERENCES bodies(body_id),
  anatomy      TEXT NOT NULL,
  type         TEXT NOT NULL,
  severity     TEXT NOT NULL CHECK (severity IN ('minor','significant','severe','catastrophic')),
  bleed_pct_per_min REAL NOT NULL,
  pain         INTEGER NOT NULL,
  contamination INTEGER NOT NULL DEFAULT 0 CHECK (contamination BETWEEN 0 AND 3),
  function_loss INTEGER NOT NULL DEFAULT 0 CHECK (function_loss BETWEEN 0 AND 2),
  cause_event  TEXT NOT NULL,
  treatment    TEXT NOT NULL DEFAULT '[]',
  clotted      INTEGER NOT NULL DEFAULT 0,
  created_at   INTEGER NOT NULL,
  next_due_at  INTEGER,
  healed_at    INTEGER
);

-- OWNER physical.bodies
CREATE TABLE needs (
  body_id      TEXT PRIMARY KEY REFERENCES bodies(body_id),
  thirst_stage INTEGER NOT NULL DEFAULT 0 CHECK (thirst_stage BETWEEN 0 AND 6),
  hunger_stage INTEGER NOT NULL DEFAULT 0 CHECK (hunger_stage BETWEEN 0 AND 6),
  fatigue_stage INTEGER NOT NULL DEFAULT 0 CHECK (fatigue_stage BETWEEN 0 AND 6),
  last_drink_ms INTEGER NOT NULL,
  last_meal_ms  INTEGER NOT NULL,
  last_sleep_ms INTEGER NOT NULL,
  cold_stage   INTEGER NOT NULL DEFAULT 0,
  heat_stage   INTEGER NOT NULL DEFAULT 0,
  chill        INTEGER NOT NULL DEFAULT 0     -- F1c LOOK-09: cold counted on the hour; cold_stage = chill // chill_per_stage
);

-- OWNER physical.bodies
CREATE TABLE infections (
  body_id     TEXT NOT NULL REFERENCES bodies(body_id),
  pathway     TEXT NOT NULL CHECK (pathway IN ('air','wet','lurker_deep','cold_start')),
  exposed_at  INTEGER NOT NULL,
  stage       TEXT NOT NULL,
  cause_event TEXT NOT NULL,
  known_to_self INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (body_id, pathway)
);

-- OWNER physical.bodies   (who holds whom: grapples and the infected contact chain's GRIP step, P5)
CREATE TABLE grips (
  holder_id   TEXT NOT NULL REFERENCES bodies(body_id),
  target_id   TEXT NOT NULL REFERENCES bodies(body_id),
  since_ms    INTEGER NOT NULL,
  cause_event TEXT NOT NULL,
  PRIMARY KEY (holder_id, target_id)
);

-- OWNER physical.bodies   (one condition model for bodies, vehicles, structures, tools — plan §11.4)
CREATE TABLE conditions (
  condition_id TEXT PRIMARY KEY,
  subject_id   TEXT NOT NULL,
  subject_kind TEXT NOT NULL CHECK (subject_kind IN ('body','item','vehicle','structure')),
  component    TEXT NOT NULL,
  condition    INTEGER NOT NULL CHECK (condition BETWEEN 0 AND 100),
  damage_cause TEXT,
  function_loss INTEGER NOT NULL DEFAULT 0,
  repair_req   TEXT NOT NULL DEFAULT '[]',
  degrade_per_day REAL NOT NULL DEFAULT 0
);

-- OWNER world.infected
CREATE TABLE infected_state (
  body_id      TEXT PRIMARY KEY REFERENCES bodies(body_id),
  type_id      TEXT NOT NULL,        -- e.g. ZOMBIE_ARCHETYPE_SHAMBLER01
  states       TEXT NOT NULL DEFAULT '[]',   -- dormant|starved|overfed|injured
  energy       INTEGER NOT NULL DEFAULT 50 CHECK (energy BETWEEN 0 AND 100),
  quirks       TEXT NOT NULL DEFAULT '[]',
  target_id    TEXT,
  lurker_clan  TEXT,
  risen_from   TEXT,                 -- P10: the corpse this body rose from (world.infected.rise)
  since        INTEGER NOT NULL DEFAULT 0,   -- P10: when it came to be here (spawn / rise)
  degrade_at   INTEGER,              -- P10: a Runner's decline into a Shambler or Crawler (INF-10)
  horde_id     TEXT,                 -- P10: the horde it was promoted from (world.hordes HRD-07)
  charged_at   INTEGER,              -- P10: when its energy was last charged (INF-03; NULL: not yet)
  folded_at    INTEGER               -- P10: when it went back into a count (world.hordes HRD-18); NULL while it is a body in the world
);

-- OWNER physical.objects
CREATE TABLE items (
  item_id     TEXT PRIMARY KEY,
  def_ref     TEXT NOT NULL,
  qty         INTEGER NOT NULL CHECK (qty >= 1),
  condition   INTEGER NOT NULL DEFAULT 100 CHECK (condition BETWEEN 0 AND 100),
  holder_body TEXT REFERENCES bodies(body_id),
  holder_slot TEXT CHECK (holder_slot IN ('hand_l','hand_r','worn','pocket','pack') OR holder_slot IS NULL),
  container_id TEXT REFERENCES items(item_id),
  place_id    TEXT REFERENCES places(place_id),
  anchor_id   TEXT REFERENCES anchors(anchor_id),
  lot_id      TEXT,
  props       TEXT NOT NULL DEFAULT '{}',   -- e.g. {"rounds": 15, "chambered": true}
  origin      TEXT NOT NULL DEFAULT 'worldgen' CHECK (origin IN ('worldgen','scenario','production','loot','cheat','craft','drop')),
  -- exactly one location: held by a body, inside a container, or lying in a place
  CHECK ( (holder_body IS NOT NULL) + (container_id IS NOT NULL) + (place_id IS NOT NULL) = 1 )
);
CREATE INDEX items_holder ON items(holder_body);
CREATE INDEX items_container ON items(container_id);
CREATE INDEX items_place ON items(place_id);

-- OWNER physical.objects
CREATE TABLE lots (
  lot_id      TEXT PRIMARY KEY,
  product_ref TEXT NOT NULL,
  origin_site TEXT,
  cycle       INTEGER NOT NULL DEFAULT 0,
  quantity    INTEGER NOT NULL,
  quality     INTEGER NOT NULL DEFAULT 2 CHECK (quality BETWEEN 0 AND 4),
  adulteration TEXT,
  chain       TEXT NOT NULL DEFAULT '[]'
);

-- ===================================================================== mind
-- OWNER mind.actor
CREATE TABLE actors (
  actor_id      TEXT PRIMARY KEY REFERENCES bodies(body_id),
  dossier_id    TEXT NOT NULL,
  controller    TEXT NOT NULL DEFAULT 'model' CHECK (controller IN ('model','human','policy')),
  display_name  TEXT NOT NULL,
  resolve_cur   INTEGER NOT NULL CHECK (resolve_cur >= 0),
  resolve_max   INTEGER NOT NULL CHECK (resolve_max >= 1),
  stress        INTEGER NOT NULL DEFAULT 0 CHECK (stress BETWEEN 0 AND 10),
  attention_target TEXT,
  current_task  TEXT,
  goal_text     TEXT NOT NULL DEFAULT '',
  lod_hint      TEXT NOT NULL DEFAULT 'cold',
  duty_anchor   TEXT,                -- standing post (ABANDON_POST gate)
  accepted_authority TEXT NOT NULL DEFAULT '[]',
  next_due_at   INTEGER,
  quarantine    INTEGER NOT NULL DEFAULT 0   -- 1 = cheat-origin (excluded from balance maths)
);

-- OWNER mind.actor
CREATE TABLE dossiers (
  dossier_id    TEXT PRIMARY KEY,
  actor_id      TEXT,
  source        TEXT NOT NULL CHECK (source IN ('pack','generated','imported','cheat','quickmade','fixture')),
  content_ref   TEXT,
  baseline_json TEXT NOT NULL,       -- full ActorDossier/PCDossier JSON. NEVER trimmed.
  content_hash  TEXT NOT NULL
);

-- OWNER mind.actor
CREATE TABLE dossier_deltas (
  delta_id   TEXT PRIMARY KEY,
  actor_id   TEXT NOT NULL,
  event_id   TEXT NOT NULL,
  path       TEXT NOT NULL,          -- dotted path into the dossier, e.g. 'life.current_project'
  op         TEXT NOT NULL CHECK (op IN ('set','append','remove')),
  value_json TEXT NOT NULL,
  at         INTEGER NOT NULL
);

-- OWNER mind.actor
CREATE TABLE voice_lines (
  line_id  TEXT PRIMARY KEY,
  actor_id TEXT NOT NULL,
  text     TEXT NOT NULL,
  at       INTEGER NOT NULL,
  event_id TEXT NOT NULL,
  pinned   INTEGER NOT NULL DEFAULT 0
);

-- OWNER mind.actor
CREATE TABLE plans (
  actor_id   TEXT PRIMARY KEY,
  goal_text  TEXT NOT NULL,
  steps      TEXT NOT NULL DEFAULT '[]',
  standing_orders TEXT NOT NULL DEFAULT '[]',
  updated_at INTEGER NOT NULL
);

-- OWNER action.tasks
CREATE TABLE tasks (
  task_id     TEXT PRIMARY KEY,
  actor_id    TEXT NOT NULL,
  kind        TEXT NOT NULL,
  label       TEXT NOT NULL,
  steps_total INTEGER NOT NULL CHECK (steps_total >= 1),
  steps_done  INTEGER NOT NULL DEFAULT 0,
  step_s      REAL NOT NULL,
  started_at  INTEGER NOT NULL,
  next_due_at INTEGER,
  interrupt_on TEXT NOT NULL DEFAULT '[]',
  target_ids  TEXT NOT NULL DEFAULT '[]',
  focus       INTEGER NOT NULL DEFAULT 0,   -- 1 = needs concentration: divided-attention penalty (AUD-04)
  status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','paused','done','abandoned'))
);

-- OWNER mind.perception   (propositions that are NOT canonical truth: inferences, statements heard, rumours)
CREATE TABLE propositions (
  prop_id      TEXT PRIMARY KEY,
  subject_type TEXT NOT NULL,
  subject_id   TEXT,
  predicate    TEXT NOT NULL DEFAULT '',   -- what the proposition is about ('location', 'watching', 'status'...): supersession key
  object_value TEXT,                 -- machine value when there is one: an anchor/place id for 'location', 'true'/'false'...
  text         TEXT NOT NULL,
  matches_claim TEXT,                -- claim_id when code can link it to truth (may be true or false!)
  created_event TEXT NOT NULL
);

-- OWNER mind.perception   (what somebody thinks is true. THIS is what a mind reads.)
CREATE TABLE claim_holdings (
  holder_id     TEXT NOT NULL,
  claim_id      TEXT NOT NULL,       -- a claims.claim_id OR a propositions.prop_id
  believed      INTEGER NOT NULL,    -- may differ from the claim; this is the point
  confidence    INTEGER NOT NULL CHECK (confidence BETWEEN 0 AND 3),
  provenance    TEXT NOT NULL,       -- witnessed|overheard|told_by:<id>|read:<id>|common|childhood|rumour:<id>|inferred
  fidelity      TEXT NOT NULL CHECK (fidelity IN ('exact','partial','tone_only','visual_only')),
  acquired_at   INTEGER NOT NULL,
  acquired_via  TEXT NOT NULL,       -- event_id
  last_confirmed INTEGER,
  superseded_by TEXT,                -- never delete a belief; supersede it
  PRIMARY KEY (holder_id, claim_id)
);

-- OWNER mind.perception   (every percept that ever reached a mind: the audit surface)
CREATE TABLE percept_log (
  percept_id  TEXT PRIMARY KEY,
  holder_id   TEXT NOT NULL,
  event_id    TEXT NOT NULL,
  channel     TEXT NOT NULL CHECK (channel IN ('visual','auditory','speech','tactile','olfactory','vibration')),
  fidelity    TEXT NOT NULL CHECK (fidelity IN ('exact','partial','tone_only','visual_only')),
  at          INTEGER NOT NULL,
  text        TEXT NOT NULL,         -- plain-English rendering as this holder perceived it
  source_id   TEXT,                  -- NULL when the holder could not tell the source
  detail      TEXT NOT NULL DEFAULT '{}',   -- channel facts the packet needs (words, volume, level...): mind.perception docstring
  granted_by  TEXT NOT NULL CHECK (granted_by = 'perception.grant'),
  turn_index  INTEGER NOT NULL
);
CREATE INDEX percept_holder ON percept_log(holder_id, turn_index);

-- OWNER mind.perception
CREATE TABLE known_places (
  holder_id  TEXT NOT NULL,
  place_id   TEXT NOT NULL,
  first_seen INTEGER NOT NULL,
  last_seen  INTEGER NOT NULL,
  visited    INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (holder_id, place_id)
);

-- OWNER mind.perception   (what a holder knows another body as: name or description)
CREATE TABLE acquaintance (
  holder_id  TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  known_name TEXT,
  description TEXT NOT NULL,
  first_met  INTEGER NOT NULL,
  last_seen  INTEGER NOT NULL,
  last_seen_place TEXT,
  PRIMARY KEY (holder_id, subject_id)
);

-- OWNER mind.mind
CREATE TABLE relationships (
  from_id    TEXT NOT NULL,
  to_id      TEXT NOT NULL,
  trust      INTEGER NOT NULL DEFAULT 0 CHECK (trust BETWEEN -3 AND 3),
  fear       INTEGER NOT NULL DEFAULT 0 CHECK (fear BETWEEN 0 AND 3),
  respect    INTEGER NOT NULL DEFAULT 0 CHECK (respect BETWEEN -3 AND 3),
  affection  INTEGER NOT NULL DEFAULT 0 CHECK (affection BETWEEN -3 AND 3),
  resentment INTEGER NOT NULL DEFAULT 0 CHECK (resentment BETWEEN 0 AND 3),
  obligation INTEGER NOT NULL DEFAULT 0 CHECK (obligation BETWEEN -3 AND 3),
  kind       TEXT NOT NULL DEFAULT 'acquaintance',
  causes     TEXT NOT NULL DEFAULT '{}',   -- JSON axis -> last cause event_id
  updated_at INTEGER NOT NULL,
  PRIMARY KEY (from_id, to_id)
);

-- OWNER mind.temper
CREATE TABLE tempers (                  -- H1: anger one person carries toward another, now (mind.temper TEMPER-02)
  holder_id  TEXT NOT NULL,
  toward_id  TEXT NOT NULL,
  heat       INTEGER NOT NULL DEFAULT 0 CHECK (heat BETWEEN 0 AND 20),
  updated_at INTEGER NOT NULL,
  last_kind  TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (holder_id, toward_id)
);

-- OWNER mind.mind
CREATE TABLE refusals (
  refusal_id      TEXT PRIMARY KEY,
  actor_id        TEXT NOT NULL,
  requester_id    TEXT NOT NULL,
  request_summary TEXT NOT NULL,
  request_signature TEXT NOT NULL,   -- '<verb>:<target_id or *>' used to recognise a repeated ask
  reason_code     TEXT NOT NULL,     -- duty|dependent|resource|fear|moral|identity|loyalty|cost|distrust
  reason_event_ids TEXT NOT NULL DEFAULT '[]',
  cost_cited      TEXT NOT NULL DEFAULT '',
  entrenched      INTEGER NOT NULL DEFAULT 0,
  expires_when    TEXT NOT NULL DEFAULT 'never',
  created_event   TEXT NOT NULL,
  created_at      INTEGER NOT NULL,
  times_asked     INTEGER NOT NULL DEFAULT 1,
  status          TEXT NOT NULL DEFAULT 'standing' CHECK (status IN ('standing','reopened','expired','revised'))
);

-- OWNER mind.mind
CREATE TABLE open_loops (
  loop_id    TEXT PRIMARY KEY,
  holder_id  TEXT NOT NULL,
  kind       TEXT NOT NULL,
  subject_ids TEXT NOT NULL DEFAULT '[]',
  text       TEXT NOT NULL,
  strength   INTEGER NOT NULL DEFAULT 2 CHECK (strength BETWEEN 0 AND 3),
  created_event TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  due_at     INTEGER,
  status     TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','fulfilled','broken','abandoned','expired')),
  resolved_event TEXT
);
CREATE INDEX loops_holder ON open_loops(holder_id, status);

-- OWNER mind.mind
CREATE TABLE lessons (
  lesson_id  TEXT PRIMARY KEY,
  holder_id  TEXT NOT NULL,
  cue_tags   TEXT NOT NULL,          -- JSON list of cue ids
  text       TEXT NOT NULL,
  expectation TEXT NOT NULL DEFAULT '',
  outcome    TEXT NOT NULL DEFAULT '',
  confidence INTEGER NOT NULL DEFAULT 2 CHECK (confidence BETWEEN 0 AND 3),
  source_event TEXT NOT NULL,
  at         INTEGER NOT NULL
);

-- OWNER mind.memory
CREATE TABLE episodes (
  episode_id TEXT PRIMARY KEY,
  holder_id  TEXT NOT NULL,
  at         INTEGER NOT NULL,
  turn_index INTEGER NOT NULL,
  place_id   TEXT,
  summary    TEXT NOT NULL,          -- in the holder's own voice
  salience   INTEGER NOT NULL CHECK (salience BETWEEN 0 AND 100),
  percept_ids TEXT NOT NULL DEFAULT '[]',
  subject_ids TEXT NOT NULL DEFAULT '[]',
  anchor     INTEGER NOT NULL DEFAULT 0,  -- anchor memory: never decays
  decayed    INTEGER NOT NULL DEFAULT 0,
  self_event_ids TEXT NOT NULL DEFAULT '[]',   -- B5 AC10: the holder's own events the memory cites (O#)
  quarantined INTEGER NOT NULL DEFAULT 0       -- B5 AC13 (MEM-18): names someone the holder cannot know; never retrieved
);
CREATE INDEX episodes_holder ON episodes(holder_id, at);

-- OWNER mind.memory
CREATE TABLE memory_jobs (                     -- B5 MEM-19 (fidelity C10): a writeback is never lost to a failed call
  job_key     TEXT PRIMARY KEY,                -- f'{holder_id}:{turn_index}'
  holder_id   TEXT NOT NULL,
  turn_index  INTEGER NOT NULL,
  status      TEXT NOT NULL CHECK (status IN ('pending','done','failed')),
  attempts    INTEGER NOT NULL DEFAULT 0,
  updated_at  INTEGER NOT NULL
);
CREATE VIRTUAL TABLE episodes_fts USING fts5(summary, content='episodes', content_rowid='rowid');
-- derived index maintenance (not state; excluded from the state hash; rebuilt after replay)
CREATE TRIGGER episodes_ai AFTER INSERT ON episodes BEGIN
  INSERT INTO episodes_fts(rowid, summary) VALUES (new.rowid, new.summary);
END;
CREATE TRIGGER episodes_ad AFTER DELETE ON episodes BEGIN
  INSERT INTO episodes_fts(episodes_fts, rowid, summary) VALUES ('delete', old.rowid, old.summary);
END;
CREATE TRIGGER episodes_au AFTER UPDATE OF summary ON episodes BEGIN
  INSERT INTO episodes_fts(episodes_fts, rowid, summary) VALUES ('delete', old.rowid, old.summary);
  INSERT INTO episodes_fts(rowid, summary) VALUES (new.rowid, new.summary);
END;

-- ===================================================================== society
-- OWNER society.group   (factions AND procedural groups)
CREATE TABLE groups (
  group_id    TEXT PRIMARY KEY,
  kind        TEXT NOT NULL CHECK (kind IN ('faction','group','household_cluster','lurker_clan')),
  name        TEXT NOT NULL,
  content_ref TEXT,
  descriptor  TEXT,
  presence    TEXT,                  -- dominant|active|peripheral (start region)
  doctrine    TEXT NOT NULL DEFAULT '{}',
  cohesion    INTEGER NOT NULL DEFAULT 5 CHECK (cohesion BETWEEN 0 AND 10),
  morale      INTEGER NOT NULL DEFAULT 5 CHECK (morale BETWEEN 0 AND 10),
  leader_id   TEXT,
  next_due_at INTEGER
);

-- OWNER society.group
CREATE TABLE group_members (
  group_id  TEXT NOT NULL,
  actor_id  TEXT NOT NULL,
  role      TEXT NOT NULL,
  standing  INTEGER NOT NULL DEFAULT 0 CHECK (standing BETWEEN -3 AND 3),
  since     INTEGER NOT NULL,
  status    TEXT NOT NULL DEFAULT 'member' CHECK (status IN ('member','probation','departed','expelled','dead')),
  PRIMARY KEY (group_id, actor_id)
);

-- OWNER society.group   (standing of a group toward any actor, incl. the PC: the world's memory of you)
CREATE TABLE group_standing (
  group_id  TEXT NOT NULL,
  actor_id  TEXT NOT NULL,
  standing  INTEGER NOT NULL DEFAULT 0 CHECK (standing BETWEEN -5 AND 5),
  reasons   TEXT NOT NULL DEFAULT '[]',   -- event ids
  PRIMARY KEY (group_id, actor_id)
);

-- OWNER society.group
CREATE TABLE tension (
  a_id   TEXT NOT NULL,              -- actor or group
  b_id   TEXT NOT NULL,
  score  INTEGER NOT NULL DEFAULT 0 CHECK (score BETWEEN 0 AND 100),
  boiling_point INTEGER NOT NULL DEFAULT 70,
  causes TEXT NOT NULL DEFAULT '[]',
  PRIMARY KEY (a_id, b_id)
);

-- OWNER society.household
CREATE TABLE households (
  household_id TEXT PRIMARY KEY,
  dwelling_place TEXT,
  shared_stores TEXT NOT NULL DEFAULT '{}',
  grief_state  INTEGER NOT NULL DEFAULT 0 CHECK (grief_state BETWEEN 0 AND 3),
  settlement_id TEXT
);

-- OWNER society.household
CREATE TABLE household_members (
  household_id TEXT NOT NULL,
  actor_id     TEXT NOT NULL,
  role         TEXT NOT NULL,        -- head|partner|child|elder|dependent|lodger
  guardian_of  TEXT NOT NULL DEFAULT '[]',
  protection_priority INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (household_id, actor_id)
);

-- OWNER society.routine
CREATE TABLE routines (
  routine_id TEXT PRIMARY KEY,
  actor_id   TEXT NOT NULL,
  steps      TEXT NOT NULL,          -- JSON list of {start_hh,end_hh,activity,place_id}
  next_due_at INTEGER
);

-- OWNER society.settlement
CREATE TABLE settlements (
  settlement_id TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  place_id    TEXT,
  group_id    TEXT,
  stores      TEXT NOT NULL DEFAULT '{}',   -- food, water, medicine, fuel, ammunition, repair_materials (units)
  morale      INTEGER NOT NULL DEFAULT 5,
  cohesion    INTEGER NOT NULL DEFAULT 5,
  defences    INTEGER NOT NULL DEFAULT 2 CHECK (defences BETWEEN 0 AND 10),
  sanitation  INTEGER NOT NULL DEFAULT 2 CHECK (sanitation BETWEEN 0 AND 10),
  power       INTEGER NOT NULL DEFAULT 0 CHECK (power BETWEEN 0 AND 10),
  ration_level INTEGER NOT NULL DEFAULT 3 CHECK (ration_level BETWEEN 0 AND 4),
  shortages   TEXT NOT NULL DEFAULT '[]',
  vacancies   TEXT NOT NULL DEFAULT '[]',
  next_due_at INTEGER,
  lockdown    INTEGER NOT NULL DEFAULT 0 CHECK (lockdown IN (0, 1))   -- P10: sealed (world.factions FAC-01)
);

-- OWNER society.settlement
CREATE TABLE laws_active (
  settlement_id TEXT NOT NULL,
  law_ref       TEXT NOT NULL,
  since         INTEGER NOT NULL,
  PRIMARY KEY (settlement_id, law_ref)
);

-- OWNER society.work
CREATE TABLE workplaces (
  workplace_id TEXT PRIMARY KEY,
  settlement_id TEXT,
  place_id     TEXT,
  site_type    TEXT NOT NULL,        -- water_pump|kitchen|garden|workshop|clinic|watch|laundry|school
  inputs       TEXT NOT NULL DEFAULT '{}',
  outputs      TEXT NOT NULL DEFAULT '{}',
  cycle_h      REAL NOT NULL,
  required_roles TEXT NOT NULL DEFAULT '[]',
  machinery_condition INTEGER NOT NULL DEFAULT 70,
  efficiency   REAL NOT NULL DEFAULT 1.0,
  stall_reasons TEXT NOT NULL DEFAULT '[]',
  next_due_at  INTEGER
);

-- OWNER society.work
CREATE TABLE work_assignments (
  workplace_id TEXT NOT NULL,
  actor_id     TEXT NOT NULL,
  role         TEXT NOT NULL,
  shift_start_hh INTEGER NOT NULL,
  shift_end_hh   INTEGER NOT NULL,
  covering_for TEXT,
  PRIMARY KEY (workplace_id, actor_id, role, shift_start_hh)   -- P9: a cover shift may sit beside the worker's own
);

-- OWNER society.population   (unnamed people; materialising one decrements a cohort — L11)
CREATE TABLE cohorts (
  cohort_id    TEXT PRIMARY KEY,
  settlement_id TEXT,
  zone_id      TEXT,
  age_band     TEXT NOT NULL,
  sex          TEXT NOT NULL,
  cohort_kind  TEXT NOT NULL,        -- pre_fall_adult|fall_child|post_fall_born
  count        INTEGER NOT NULL CHECK (count >= 0),
  archetype    TEXT
);

-- ===================================================================== world
-- OWNER world.worldgen
CREATE TABLE world_params (
  id          INTEGER PRIMARY KEY CHECK (id = 1),
  params_json TEXT NOT NULL,         -- WorldParams
  commit_json TEXT NOT NULL          -- WorldgenCommit
);

-- OWNER world.worldgen
CREATE TABLE history_events (
  hist_id     TEXT PRIMARY KEY,
  day         INTEGER NOT NULL,      -- days since Fall (negative = before)
  kind        TEXT NOT NULL,         -- disaster|battle|schism|migration|failed_settlement|deposed_leader|massacre|discovery|epidemic|betrayal|infrastructure_collapse|founding|personal (P10: the PC's own past, WG-33)
  subject_ids TEXT NOT NULL DEFAULT '[]',
  cause_hist_id TEXT,
  truth_text  TEXT NOT NULL,
  belief_text TEXT NOT NULL
);

-- OWNER world.worldmove
CREATE TABLE operations (
  op_id      TEXT PRIMARY KEY,
  group_id   TEXT,
  kind       TEXT NOT NULL,          -- patrol|trade_run|raid|scavenge|construction|recruit|diplomacy|migration
  status     TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','active','done','failed','cancelled')),
  route      TEXT NOT NULL DEFAULT '[]',
  participants TEXT NOT NULL DEFAULT '[]',
  next_due_at INTEGER,
  outcome    TEXT,
  target_id  TEXT                    -- P10: whom a 'decon' operation is for (world.factions FAC-04)
);

-- OWNER world.hordes   (P10: a district's dead nobody has met yet, counted — fidelity E01)
CREATE TABLE infected_pools (
  zone_id    TEXT NOT NULL,
  type_id    TEXT NOT NULL,
  active     INTEGER NOT NULL DEFAULT 0 CHECK (active >= 0),
  dormant    INTEGER NOT NULL DEFAULT 0 CHECK (dormant >= 0),
  PRIMARY KEY (zone_id, type_id)
);

-- OWNER world.hordes   (P10: the dead on the move — fidelity E02; the Mega Horde)
CREATE TABLE hordes (
  horde_id     TEXT PRIMARY KEY,
  kind         TEXT NOT NULL CHECK (kind IN ('drift','drawn','mega')),
  composition  TEXT NOT NULL DEFAULT '{}',   -- JSON {type_id: count}
  zone_id      TEXT NOT NULL,
  place_id     TEXT NOT NULL,
  route        TEXT NOT NULL DEFAULT '[]',   -- JSON list of the places still to walk
  target_place TEXT,
  status       TEXT NOT NULL CHECK (status IN ('moving','milling','gone')),
  origin       TEXT NOT NULL,
  since        INTEGER NOT NULL,
  props        TEXT NOT NULL DEFAULT '{}'
);

-- OWNER world.traces
CREATE TABLE traces (
  trace_id   TEXT PRIMARY KEY,
  place_id   TEXT NOT NULL,
  kind       TEXT NOT NULL,          -- tracks|blood|corpse|graffiti|missing_stock|damage|smoke|dropped_item|new_goods|changed_checkpoint|...
  text       TEXT NOT NULL,          -- what an observer can perceive
  source_event TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  decays_at  INTEGER,
  locked     INTEGER NOT NULL DEFAULT 0   -- a permanent mark: no decay clock (TRACE-01)
);

-- OWNER world.rumours
CREATE TABLE rumours (
  rumour_id  TEXT PRIMARY KEY,
  prop_id    TEXT NOT NULL,          -- the proposition being passed on
  origin_holder TEXT NOT NULL,
  hops       INTEGER NOT NULL DEFAULT 0,
  distortions TEXT NOT NULL DEFAULT '[]',
  created_at INTEGER NOT NULL
);

-- ===================================================================== narration
-- OWNER narration.narrator
CREATE TABLE narration (
  turn_index  INTEGER PRIMARY KEY,
  text        TEXT NOT NULL,
  packet_hash TEXT NOT NULL,
  lint_passed INTEGER NOT NULL,
  attempts    INTEGER NOT NULL DEFAULT 1
);

-- OWNER narration.narrator
CREATE TABLE narrator_state (
  id         INTEGER PRIMARY KEY CHECK (id = 1),
  style_json TEXT NOT NULL           -- NarratorStyle
);

-- OWNER narration.lint
CREATE TABLE echo_ledger (
  turn_index INTEGER NOT NULL,
  ngram      TEXT NOT NULL,
  source     TEXT NOT NULL CHECK (source IN ('pc_input','actor_line','narrator_image')),
  licensed_uses INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (turn_index, ngram, source)
);

-- OWNER service
CREATE TABLE story_log (
  entry_id   INTEGER PRIMARY KEY,
  turn_index INTEGER NOT NULL,
  kind       TEXT NOT NULL CHECK (kind IN ('narration','player','guide','notice','cheat')),
  mode       TEXT,
  text       TEXT NOT NULL
);

-- ===================================================================== views (read-only, derived)
CREATE VIEW canonical_truth AS
  SELECT * FROM claims WHERE true_until IS NULL;

CREATE VIEW timer_bank AS
  SELECT 'queue' AS source, queue_id AS id, subject_id, type AS what, due_at FROM event_queue WHERE status = 'pending'
  UNION ALL SELECT 'task', task_id, actor_id, label, next_due_at FROM tasks WHERE status = 'active' AND next_due_at IS NOT NULL
  UNION ALL SELECT 'wound', wound_id, body_id, severity, next_due_at FROM wounds WHERE healed_at IS NULL AND next_due_at IS NOT NULL
  UNION ALL SELECT 'actor', actor_id, actor_id, 'next decision', next_due_at FROM actors WHERE next_due_at IS NOT NULL
  UNION ALL SELECT 'group', group_id, group_id, 'group operation', next_due_at FROM groups WHERE next_due_at IS NOT NULL
  UNION ALL SELECT 'workplace', workplace_id, workplace_id, 'production cycle', next_due_at FROM workplaces WHERE next_due_at IS NOT NULL;
