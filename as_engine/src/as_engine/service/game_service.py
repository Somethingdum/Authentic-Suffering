"""GameService: the complete Play UI protocol, without any websocket (P8). Rules PROTO-01..10,
UI-CLARITY-06, SET-01/02. docs/as/10_UI.md (screens, store) and contracts/protocol.py (every model).

    service = GameService(config, transport, config_path='as_config.yaml')
    replies = await service.handle({"type": "as_game", "action": "hello", "client_version": "1"})
    service.subscribe(push)        # async push(dict): turn progress and results arrive here
    await service.idle()           # tests / shutdown: wait for the running turn to finish

The Talemate plugin (02 §6) forwards every browser message to ``handle`` and queues each reply;
it subscribes one ``push`` per connection. Talemate reads a connection's messages one at a time
and awaits each handler, so ``handle`` must return quickly: a turn runs as a background task and
its progress and result are PUSHED (PROTO-04).

Rules:
PROTO-01 Every reply and push is one envelope (below) whose data validates against OUT_MODELS.
PROTO-02 One GameService per process (get_service): a reloaded page reaches the same game, and a
  new connection's subscription receives the pushes of a turn that was already running.
PROTO-03 handle() never raises: a bad message, a refusal or a fault is an error reply.
PROTO-04 A turn runs as a background task: turn_submit answers at once; progress and the result
  are pushed.
PROTO-05 One turn at a time. While it runs, anything that would read or change the run answers
  busy, except view_get / story_get, which answer with the state from before the turn.
PROTO-06 turn_cancel before stage 12 leaves the world, the clock and the input exactly as they
  were; from stage 12 on it is refused (too_late).
PROTO-07 Ask is not a turn: service.guide answers it; nothing in the world changes or hears it.
PROTO-08 Every error message is a plain sentence of at least 20 characters saying what happened
  and what to do; never a stack trace (UI-CLARITY-06).
PROTO-09 An action of a later phase answers not_built_yet until that phase builds it.
PROTO-10 Mid-run settings: only service.session.CHANGEABLE_SETTINGS change (SET-02), one
  SETTINGS_CHANGE per field (SET-01); config_set changes only the lanes and background thinking.

Envelope (PROTO-01): every reply and push is out(action, model) = {"type": "as_game", "action":
action, "data": model.model_dump(mode='json')} with action in OUTBOUND_ACTIONS and data valid for
OUT_MODELS[action]. Replies come back from handle() in the order listed below.

handle(message) -> list[dict]   (never raises, PROTO-03)
  1. action = message.get('action'). Not one of INBOUND_ACTIONS -> [error unknown_action,
     UNKNOWN_ACTION.format(action=action)].
  2. fields = the message without 'type' and 'action'. IN_MODELS[action] is None -> msg = None
     (extra fields are ignored); else msg = the model validated from fields; a ValidationError ->
     [error bad_request, BAD_REQUEST.format(where = the first error's loc joined by '.', problem =
     its msg)].
  3. replies = await getattr(self, 'on_' + action)(msg). Every inbound action has an on_<action>
     method.
  4. ServiceError(code, message) raised by a handler -> [error {code, message}]; a
     service.runs.RunError -> [error {code: its code, message: its message}]; NotImplementedError
     (an action whose phase is not built yet: the P10 / P12 handlers below are stubs until then,
     PROTO-09) -> [error not_built_yet, NOT_BUILT]; any other Exception -> logged with its
     traceback (logging.getLogger('as_engine.service')) and [error internal, INTERNAL]. Logs
     name no session (RUN-13): the action, the error code and the exception type — never a
     run_id, a character's name or the message's text.
  Error data is OutError(code, message, recoverable=True) (PROTO-08).

State kept by the service: config, transport, config_path, client (a LaneClient(config, transport)
  for calls outside a run: hello, models_test), session (the loaded service.session.Session or
  None), turn_task (the running turn's asyncio.Task or None), turn_stage (the last stage it
  reported, None before the first), last_view (the newest PlayView built) and last_story (the
  newest StoryEntry list built).
view(): with session.store.transaction() as tx: v = service.view.build_view(tx, session);
  last_view = v; returns v. story(): the story_log rows by entry_id as StoryEntry(turn_index, kind,
  text, mode); last_story = them. (Helpers the handlers below use; any names will do.)
Busy (PROTO-05): while turn_task is running, the store connection is inside the turn's transaction.
  Handlers that would read or write the run check ``busy`` first and answer BUSY; view_get and
  story_get answer with last_view / last_story instead (the state before the turn: never the
  half-made one).

Handlers (P8):
  on_hello(InHello): health = await client.refresh_health(); models_ok = every lane healthy;
    has_runs = service.runs.list_runs(config) is not empty; screen = 'connect' when not models_ok,
    else 'play' when a session is loaded, else 'home' -> [welcome {server_version =
    as_engine.__version__, screen, has_runs, models_ok}]. A page reloaded during a turn gets 'play'
    and, through its new subscription, that turn's result (PROTO-02).
  on_get_state: [state {screen: 'play' when a session is loaded else 'home', run_id, busy}].
  on_models_list: for lane A then B: models = await transport.list_models(lane, config.lanes[lane])
    (an exception -> [] and reachable False), reachable = await transport.health(...) (an
    exception -> False) -> [models {lane, models, selected = config.lanes[lane].model, reachable}] x2.
  on_models_test(InModelsTest): lc = config.lanes[lane].
    not await transport.health(lane, lc) (or it raises) -> ok False, detail
      NOT_ANSWERING.format(url = lc.base_url).
    lc.model not in await transport.list_models(lane, lc) -> ok False, detail
      MODEL_MISSING.format(model = lc.model).
    Otherwise two PROBE calls through ``client`` (call_class PROBE, lane, messages [system "You
      answer in one word.", user "Say: ready"], thinking False, max_tokens 64, deadline_s 30):
      'hello' without a schema, then 'json' with schema_name 'probe', json_schema = PROBE_SCHEMA
      and output model ProbeAnswer; the json call is made only after a good hello answer. The hello
      answer's parse_status is not 'ok' or its text is empty -> ok False, detail NO_ANSWER,
      latency_ms None, structured_ok None. Else ok True, latency_ms = its latency_ms, detail =
      WORKING.format(secs = latency_ms / 1000) + ('' when the json answer's parse_status is 'ok'
      else ' ' + NO_JSON), structured_ok = (json parse_status == 'ok'), thinking_ok None
      (tools/as/probe.py finds the thinking switch; the Test button checks reachability, the model
      and speed).
    -> [model_test_result {lane, ok, detail, latency_ms, structured_ok, thinking_ok}].
  on_config_get: [config {lanes: config.lanes, background_cognition}].
  on_config_set(InConfigSet): busy -> BUSY. A patch key other than 'lanes' / 'background_cognition',
    a lane other than 'A' / 'B', or a lane field outside CONFIG_LANE_FIELDS -> ServiceError
    ('bad_request', CONFIG_KEYS.format(key = the offending key)). Each patched lane =
    LaneConfig.model_validate({**old lane dump, **its patch}) (a ValidationError -> bad_request as
    in handle step 2). new config = config with those lanes / background_cognition;
    config_loader.save_engine_config(new, config_path); config = new; client = LaneClient(new,
    transport); a loaded session gets session.config = session.config with the same lanes /
    background_cognition (its frozen rules stay) and session.client.config = session.config.
    Regimes are not settable here: a regime change alters every later request and so breaks
    re-simulation (DET-02). -> [config].
  on_packs_list: every folder of config.content_dir holding a pack.yaml, sorted by folder name ->
    PackView(pack_id = manifest id, name, version, description, records = the number of canon
    refs starting f"{pack_id}:" when content.pack.load_canon([content_dir/core] + [the folder]
    unless it is core), core = pack_id == 'core') -> [packs {packs}].
  on_content_validate(InContentValidate): the folder content_dir/pack_id holding a pack.yaml;
    missing -> ServiceError('not_found', PACK_NOT_FOUND.format(pack_id=pack_id)). canon, issues =
    load_canon([content_dir/core] + ([the folder] unless it is core)) -> [content_report {pack_id,
    ok = no issue of severity 'error', errors = the error messages, warnings = the other messages
    (loader order), counts = {kind: number of that pack's refs of that kind} (kinds with none
    left out)}].
  on_runs_list: [runs {runs: service.runs.list_runs(config)}].
  on_run_load(InRunLoad): busy -> BUSY. A loaded session is closed first (its store closed;
    session None), then session = service.runs.load_run(config, run_id, transport, save_slot)
    (a RunError -> [error {code, message}, state {screen 'home'}]) -> [run_loaded {run_id,
    pc_name = actors.display_name of the PC, notices = session.extras['notices'], settings =
    session.settings, ironman = save_mode == 'ironman', sandbox = meta.sandbox == '1'}, view
    {view()}, story {story()}].
  on_run_close: busy -> BUSY; no session -> NO_RUN. The store is closed, session = None,
    last_view / last_story = None -> [state {screen 'home', run_id None, busy False}, runs].
  on_run_save(InRunSave): no session -> NO_RUN; busy -> BUSY. path =
    service.runs.save_run(session, slot_name) (RunError 'ironman' passes through) -> [saved {slot =
    path.stem, label = slot_name, turn_index = world_clock.turn_index}].
  on_run_delete(InRunDelete) (RUN-12): busy -> BUSY. The loaded run is closed first (its store
    closed, session None, last_view and last_story cleared); then service.runs.delete_run(config,
    run_id) (a RunError -> [error {code, message}]) -> [run_deleted {run_id}, runs].
  on_view_get: no session -> NO_RUN; busy -> [view {last_view}] (BUSY when there is none); else
    [view {view()}].
  on_story_get: no session -> NO_RUN; busy -> [story {last_story}] (BUSY when there is none); else
    [story {story()}].
  on_settings_get: no session -> NO_RUN -> [settings {settings: session.settings, changeable:
    service.session.CHANGEABLE_SETTINGS}].
  on_settings_set(InSettingsSet): no session -> NO_RUN; busy -> BUSY. In one transaction
    service.session.change_settings(tx, session, patch): LockedSetting -> ServiceError('locked',
    LOCKED.format(field=the locked field)); ValueError / ValidationError -> ServiceError('bad_request', BAD_SETTING)
    (nothing is changed then) -> [settings {…}, view {view()}] (the receipt and the developer panel
    follow the new settings at once; everything else applies from the next turn, SET-01).
  on_dev_get(InDevGet): no session -> NO_RUN; not session.settings.dev_mode ->
    ServiceError('dev_mode_off', DEV_MODE_OFF); busy -> BUSY. t = turn_index or
    world_clock.turn_index. rows (dicts of the named columns; JSON text columns parsed):
      trace   turn_ledger of t by stage: stage, status, run_count, detail;
      packets lm_calls of t whose call_class is actor_cognition / actor_reaction / intent_repair,
              by seq: seq, call_class, lane, actor_id, status, latency_ms, response_text (the minds'
              answers; requests are kept only as hashes);
      intents events of t of type ACTION_START / ACTION_BLOCKED / DEGRADED_FALLBACK / SPEECH, by
              seq: seq, type, at, actor_id, payload;
      events  every event of t by seq: seq, event_id, type, at, actor_id, writer, payload;
      gate    the commit_gate_log row of t (none -> []): session_bits, world_bits, entities_bits,
              global_bits, passed, failures;
      errors  error_repair_log of t by entry_id: entry_id, kind, stage, rule_id, detail, repaired;
      calls   every lm_calls row of t by seq: seq, call_class, lane, actor_id, status, latency_ms,
              prompt_tokens, completion_tokens, response_text.
    -> [dev_data {what, turn_index: t, rows}]. The one place engine vocabulary may reach the screen.

  on_turn_submit(InTurnSubmit)   (the player's move; answers are turn_rejected, not error)
    no session -> [turn_rejected {no_run, NO_RUN}]; turn_task running -> [turn_rejected {busy,
    BUSY}].
    (P12, CHEAT-01) Then, whatever the mode: cheats.detect_activation(text) -> r =
      cheats.activate(session) -> [cheat_activated {persona_line, ok, detail}, story {story()}] (the
      line is consumed: no turn, no question). meta cheat_active is '1' and the stripped text
      starts with '/' -> cmd = cheats.parse(text): a CheatParseError -> [cheat_result
      {persona_line: its message, ok False, detail ''}]; else r = await cheats.execute(session, cmd)
      -> [cheat_result {r.persona_line, r.ok, r.detail}, view {view()}, story {story()}]. Before
      activation a '/' line is ordinary input (CHEAT-01, CHEAT-03).
    the PC's body is dead -> [turn_rejected {dead, DEAD}] (after the cheat routing: a dead
    character can still be revived by a cheat).
    mode 'ask' (PROTO-07: not a turn): the stripped text empty -> [turn_rejected {empty,
      EMPTY_QUESTION}]; else text = await service.guide.answer(session, question, last_view or
      view()) -> [guide_answer {text}, story {story()}].
    mode 'do' / 'say': turn_stage = None; turn_task = asyncio.create_task(play(msg)) ->
      [state {screen 'play', run_id, busy True}]. The task, ``play``:
        start = the running loop's time(); T = world_clock.turn_index + 1.
        progress(stage, label, frac) (passed to run_turn, awaited): turn_stage = stage; push
          turn_progress {turn_index T, stage, label, pct = round(frac * 100, 1), elapsed_s =
          round(loop time - start, 1)}.
        P10: config.background_cognition true -> first await background.catch_up(session,
          progress = (done, total) -> progress(0, background.QUIET_HOURS, 0.0)) (BG-01: the
          quiet hours end before the move; a turn_cancel meanwhile cancels the job in flight,
          which leaves nothing behind and runs again at the next catch_up).
          Progress v2 (service.progress; every Tracker here pushes through push2(action, data) =
          self.push(out(action, OUT_MODELS[action] validating data)), dev = the session's
          settings.dev_mode): when background.pending(store, T - 1) is not empty (the boundary
          catch_up finishes, world_clock.turn_index), a Tracker('quiet_hours', f"quiet_hours-{T}")
          pushes its plan (quips_for(store.canon, 'quiet_hours')) before catch_up, step('quiet',
          'jobs', done=done, total=total) on each catch_up progress call, and done(True) after it
          (done(False) when it raised or was cancelled).
        Progress v2: tr = Tracker('turn', f"turn-{T}"); await tr.plan(quips_for(store.canon,
          'turn')) just before run_turn; from then on the progress callback above also awaits
          tr.step(*service.progress.TURN_STAGES[stage]) for every stage in TURN_STAGES (the quiet
          hours' stage-0 calls come before the plan and step nothing; no detail: the pipeline's
          callback has none to give); tr.done(outcome.ok) as soon as run_turn returns (before
          turn_result / turn_rejected); on an exception or a cancel tr.done(False).
        outcome = await turn.pipeline.run_turn(session, msg, progress).
        ok -> push turn_result {turn_index, narration, view = view(), notices, degraded}; push
          story {story()}; outcome.died -> await self.on_death() — a P12 stub: its
          NotImplementedError is pushed as error {not_built_yet, NOT_BUILT_DEATH}.
        not ok -> push turn_rejected {reason_code = rejected_code, message = rejected_message,
          clarify}.
        Finally (also after an exception): turn_task = None, turn_stage = None; unless the task
        was cancelled, push state {screen 'play', run_id, busy False}. An exception escaping
        run_turn is logged and pushed as error {internal, INTERNAL}.
  on_turn_cancel   (PROTO-06; the Stop button)
    no turn_task -> ServiceError('nothing_to_cancel', NOTHING_TO_CANCEL); turn_stage is not None
    and >= 12 -> ServiceError('too_late', TOO_LATE) (the world is being committed). Otherwise
    turn_task.cancel() and await it (its CancelledError swallowed): the store transaction rolled
    back, so the world, the clock and the input are exactly as before -> [state {screen 'play',
    run_id, busy False}].

Handlers (P10: the New Life wizard, worldgen and the quiet hours):
  on_pcs_list: canon = content.pack.load_canon over every pack folder of config.content_dir (core
    first, then by folder name) — P12 (CHEAT-10, CHEAT-12): leaving out the 'cheat_' folders until
    the code was taken (codes_unlocked). Per canon record of kind 'pc' (by ref): PCCardView(ref,
    display_name = card.display_name, one_line_identity, survives_by = card.pc_card_survival,
    starts_as = world.worldgen.tables.STARTS_AS[faction_start_type], note =
    card.pc_selection_note, source 'pack', warnings [], world_age_days = [lo, hi] of
    days_since_fall_range or None, world_age_note = f"{first name}'s story needs a world {lo //
    365}-{hi // 365} years after the Fall." or None) -> [pcs {cards}]. Allowed while busy.
  on_run_new(InRunNew): busy (a turn or a worldgen running) -> BUSY. world_id given ->
    ServiceError('not_built_yet', NOT_BUILT) until P12. P12 (CHEAT-12): a pc_ref whose pack id
    starts with 'cheat_', once codes_unlocked, has that pack appended to settings.pack_ids (when
    missing); before the code, settings stay as sent and create_run answers not_found like for any
    unknown character. The background runner is cancelled and a
    loaded session closed (as on_run_close). worldgen_task = asyncio.create_task(the worldgen job)
    -> [state {screen 'worldgen', run_id None, busy True}]. The worldgen job: session = await
    service.runs.create_run(config, pc_ref, settings, transport, progress = a callback pushing
    worldgen_progress {stage, label, pct, eta_s} for every call — and, progress v2, tr.step(stage,
    sub, done=done, total=total) for every stage but COMMIT, where tr = Tracker('worldgen',
    f"worldgen-{n}" (n counts the service's worldgen jobs from 1), push2 as above, dev =
    settings.dev_mode) whose plan (quips_for(content.pack.load_canon([content_dir / 'core'] +
    [content_dir / p for p in settings.pack_ids if p != 'core']) — the canon create_run loads —,
    'worldgen')) is pushed before create_run starts and whose done(ok) follows it (False on any
    failure or cancel)); then push run_loaded (as on_run_load), view,
    story and state {screen 'play', run_id, busy False}. A WorldgenAborted -> push error {code
    'worldgen_aborted', message: its message} then state {screen 'wizard', run_id None, busy
    False}; a RunError -> push error {its code, message} then the same state; a
    kernel.errors.SettingsError (WG-34: settings the world cannot honour) -> push error {code
    'bad_settings', message: its message} then the same state; any other exception ->
    logged, error {internal, INTERNAL}, the same state; cancelled -> nothing is pushed but the
    bar's progress_done {ok False} (on_worldgen_cancel answers). Finally worldgen_task = None.
  on_code_enter(InCodeEnter) (P12, D-79, D-102, CHEAT-12; the menu's "Enter a code" box). A session
    loaded and busy -> BUSY (nothing changes). cheats.commands.detect_activation(code) false ->
    [code_result {accepted False}]
    and nothing else. True -> codes_unlocked = True for as long as this service runs (never
    saved: the New Life list forgets it on restart) -> [code_result {accepted True}]; and, with a
    session loaded, the word acts as if typed in the story box: + [cheat_activated, story] exactly
    as on_turn_submit's activation (cheats.commands.activate; no turn is played).
  on_worldgen_cancel: no worldgen_task -> ServiceError('nothing_to_cancel', NO_WORLDGEN).
    worldgen_task.cancel() and await it (CancelledError swallowed; create_run removed every partial
    folder) -> [state {screen 'wizard', run_id None, busy False}].
  Quiet hours (BG-01, service/background.py): after a turn's result has been pushed, when
    config.background_cognition is true and the PC is alive, background.start(session). A turn
    first awaits background.catch_up (on_turn_submit, above); on_run_load, on_run_close and
    on_run_new first await background.cancel().

Later phases (PROTO-09; stubs raising NotImplementedError until then, so handle() answers
not_built_yet): on_content_import, on_intake_start, on_quickmake_pc, on_death_reveal, on_new_life_here,
on_worlds_list, on_world_export, on_world_import, on_death (P12). In P8 a new run is made with
`as-engine new-scenario <scenario.yaml>` and opened with Continue / Load.

Pushes: push(msg) awaits every subscriber in subscription order; a subscriber that raises is
  unsubscribed (its connection is gone) and the others still get the message. subscribe /
  unsubscribe add and remove callbacks; unsubscribing an unknown one does nothing.
idle(): while turn_task is not None: await it (its exceptions and cancellation are swallowed).

get_service(config, transport): the process-wide singleton (PROTO-02), below.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from pydantic import BaseModel

from ..contracts.common import Strict

PushFn = Callable[[dict[str, Any]], Awaitable[None]]

CONFIG_LANE_FIELDS: tuple[str, ...] = ("name", "base_url", "model", "max_concurrency", "request_timeout_s")
PROBE_SCHEMA: dict = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"],
                      "additionalProperties": False}

UNKNOWN_ACTION = ("The game didn't recognise that request ({action}). Reload the page; if it keeps happening, the "
                  "game and the page are from different versions.")
BAD_REQUEST = "That request had a missing or wrong value ({where}: {problem}). Reload the page and try again."
INTERNAL = ("Something went wrong inside the game. Nothing in your world changed; try again. The details are in "
            "the game's log.")
NOT_BUILT = "That part of the game isn't built yet. It arrives in a later build."
NOT_BUILT_DEATH = ("Your character has died. The death screen arrives in a later build; for now, load a save to go "
                   "on.")
NO_RUN = "No game is loaded. Continue or load a run first."
BUSY = "Your last move is still being worked out. Wait for it to finish, then try again."
DEAD = "Your character is dead. Load a save or start a new life."
EMPTY_QUESTION = "Type a question first, then press Send."
NOTHING_TO_CANCEL = "There is no move in progress to stop."
NO_WORLDGEN = "No world is being built right now, so there is nothing to stop."
TOO_LATE = "Too late to stop: the world has already moved. The result is on its way."
RUN_OPEN = "That run is open right now. Close it first, then delete it."
DEV_MODE_OFF = "Developer mode is off. Turn it on in Settings → Advanced first."
LOCKED = "“{field}” is chosen when a life starts and can't change during it."
BAD_SETTING = "That setting value isn't one the game knows. Nothing was changed; pick one of the offered values."
CONFIG_KEYS = ("Only the model settings and background thinking can be changed here ({key} can't). Nothing was "
               "changed.")
PACK_NOT_FOUND = "There is no content pack called {pack_id}. Check the name in Your characters & world."
NOT_ANSWERING = "Not answering at {url}. Is LM Studio running there with its server on?"
MODEL_MISSING = "Answering, but “{model}” isn't loaded. Load it in LM Studio, or pick a loaded model."
NO_ANSWER = "Reached the model, but it gave no answer. Try again, or reload the model in LM Studio."
WORKING = "Working — answered in {secs:.1f} s."
NO_JSON = "Its structured answers failed; run tools/as/probe.py to fix the settings."


class ProbeAnswer(Strict):
    ok: bool


class ServiceError(Exception):
    """A refusal a handler answers with: error {code, message}."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def out(action: str, data: BaseModel) -> dict[str, Any]:
    """The protocol envelope (PROTO-01): {"type": "as_game", "action": action, "data": data dumped
    with mode='json'}. ``action`` must be one of OUTBOUND_ACTIONS (ValueError otherwise)."""
    raise NotImplementedError("P8")


class GameService:
    def __init__(self, config, transport, *, config_path: str = "as_config.yaml"):
        self.config = config
        self.transport = transport
        self.config_path = config_path
        self.session = None
        self.turn_task = None
        self.turn_stage: int | None = None
        self.last_view = None
        self.last_story = None
        self._subscribers: list[PushFn] = []

    def subscribe(self, fn: PushFn) -> None:
        self._subscribers.append(fn)

    def unsubscribe(self, fn: PushFn) -> None:
        if fn in self._subscribers:
            self._subscribers.remove(fn)

    @property
    def busy(self) -> bool:
        """True while a turn task (or, P10, a worldgen task) is running."""
        running = [t for t in (self.turn_task, self.worldgen_task) if t is not None]
        return any(not t.done() for t in running)

    async def handle(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        raise NotImplementedError("P8")

    async def push(self, msg: dict[str, Any]) -> None:
        raise NotImplementedError("P8")

    async def idle(self) -> None:
        raise NotImplementedError("P8")

    # ---------------------------------------------------------------- P8 handlers (module docstring)
    async def on_hello(self, msg):
        raise NotImplementedError("P8")

    async def on_get_state(self, msg):
        raise NotImplementedError("P8")

    async def on_models_list(self, msg):
        raise NotImplementedError("P8")

    async def on_models_test(self, msg):
        raise NotImplementedError("P8")

    async def on_config_get(self, msg):
        raise NotImplementedError("P8")

    async def on_config_set(self, msg):
        raise NotImplementedError("P8")

    async def on_packs_list(self, msg):
        raise NotImplementedError("P8")

    async def on_content_validate(self, msg):
        raise NotImplementedError("P8")

    async def on_runs_list(self, msg):
        raise NotImplementedError("P8")

    async def on_run_load(self, msg):
        raise NotImplementedError("P8")

    async def on_run_close(self, msg):
        raise NotImplementedError("P8")

    async def on_run_save(self, msg):
        raise NotImplementedError("P8")

    async def on_run_delete(self, msg):
        raise NotImplementedError("P8")

    async def on_view_get(self, msg):
        raise NotImplementedError("P8")

    async def on_story_get(self, msg):
        raise NotImplementedError("P8")

    async def on_settings_get(self, msg):
        raise NotImplementedError("P8")

    async def on_settings_set(self, msg):
        raise NotImplementedError("P8")

    async def on_dev_get(self, msg):
        raise NotImplementedError("P8")

    async def on_turn_submit(self, msg):
        raise NotImplementedError("P8")

    async def on_turn_cancel(self, msg):
        raise NotImplementedError("P8")

    # ---------------------------------------------------------------- later phases (PROTO-09)
    worldgen_task = None      # P10: the running create_run task (on_run_new); None when idle
    _background = None

    @property
    def background(self):
        """P10: this service's quiet-hours runner (service.background.BackgroundRunner, BG-01),
        made on first use (implemented)."""
        if self._background is None:
            from .background import BackgroundRunner
            self._background = BackgroundRunner()
        return self._background

    async def on_run_new(self, msg):
        """P10: create_run as a background task with worldgen_progress pushes, then run_loaded."""
        raise NotImplementedError("P10")

    async def on_worldgen_cancel(self, msg):
        """P10: cancel the create_run task; state {screen 'wizard'} once it has ended."""
        raise NotImplementedError("P10")

    async def on_pcs_list(self, msg):
        """P10: PC cards from every loaded pack (and P12: imported / quick-made drafts)."""
        raise NotImplementedError("P10")

    codes_unlocked = False    # P12 (CHEAT-12): the code was taken in the "Enter a code" box

    async def on_code_enter(self, msg):
        """P12: the menu's "Enter a code" box (CHEAT-12)."""
        raise NotImplementedError("P12")

    async def on_content_import(self, msg):
        """P12: content.importers."""
        raise NotImplementedError("P12")

    async def on_intake_start(self, msg):
        """P12: dossier intake as a background task."""
        raise NotImplementedError("P12")

    async def on_quickmake_pc(self, msg):
        """P12: PC_QUICKMAKE."""
        raise NotImplementedError("P12")

    async def on_death_reveal(self, msg):
        """P12: service.death, truth_reveal filled."""
        raise NotImplementedError("P12")

    async def on_new_life_here(self, msg):
        """P12: RUN-07."""
        raise NotImplementedError("P12")

    async def on_worlds_list(self, msg):
        """P12: RUN-09."""
        raise NotImplementedError("P12")

    async def on_world_export(self, msg):
        """P12: RUN-09."""
        raise NotImplementedError("P12")

    async def on_world_import(self, msg):
        """P12: RUN-09."""
        raise NotImplementedError("P12")

    async def on_death(self):
        """P12: after a turn in which the PC died, push death {DeathView} and state {screen 'dead'}."""
        raise NotImplementedError("P12")


_SERVICE: GameService | None = None


def get_service(config=None, transport=None) -> GameService:
    """Process-wide singleton so a page reload reconnects to the running game (PROTO-02).

    The first call creates ``GameService(config, transport)`` and stores it in ``_SERVICE``; every
    later call returns that same instance and ignores its arguments. (Each browser connection makes
    a new Talemate plugin, which calls this again.) Tests start fresh by setting
    ``game_service._SERVICE = None``."""
    raise NotImplementedError("P8")
from ._impl_game_service import GameService, out, get_service  # noqa
