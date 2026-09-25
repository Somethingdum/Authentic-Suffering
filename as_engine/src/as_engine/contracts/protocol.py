"""WebSocket protocol between the Play UI and the engine (docs/as/10_UI.md §Protocol).

Transport: Talemate's existing websocket (ws://<host>:5050/ws). Every message in either
direction has ``type == "as_game"``. Client -> server messages carry ``action`` and fields of
the matching ``In*`` model. Server -> client messages carry ``action`` and ``data`` (the
matching ``Out*`` model dumped with ``mode='json'``).

``service.game_service.GameService.handle(message: dict) -> list[dict]`` implements the whole
protocol without any websocket; the Talemate plugin only forwards.

IN_MODELS maps every inbound action to the model its fields must validate against (None: the
action takes no fields; extra fields are then ignored). OUT_MODELS maps every outbound action to the
model its ``data`` validates against (None: defined by the phase that builds it — P10 worldgen,
P12 intake / import / quick-make). docs/as/10_UI.md §4 is the client side.

P10 adds the loading bar (service.progress, PROG-01..07): progress_plan, then progress while the
job runs, then progress_done — pushed for worldgen, a turn and the quiet hours (P12: a time skip)
alongside the older turn_progress / worldgen_progress, which stay as they are.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import Lane, Strict
from .settings import LaneConfig, RunSettings
from .view import DeathView, LanesView, PCCardView, PlayView, RunSummaryView, StoryEntry, WorldSummaryView

INBOUND_ACTIONS = (
    "hello", "get_state", "models_list", "models_test", "config_get", "config_set",
    "packs_list", "pcs_list", "content_validate", "content_import", "intake_start",
    "quickmake_pc", "run_new", "worldgen_cancel", "runs_list", "run_load", "run_delete", "run_save", "run_close",
    "turn_submit", "turn_cancel", "view_get", "story_get", "death_reveal", "new_life_here",
    "dev_get", "worlds_list", "world_export", "world_import", "settings_get", "settings_set", "code_enter",
    "turn_compose",
)

OUTBOUND_ACTIONS = (
    "welcome", "state", "models", "model_test_result", "config", "packs", "pcs", "content_report",
    "import_result", "intake_progress", "intake_result", "quickmake_result", "worldgen_progress",
    "runs", "run_deleted", "run_loaded", "saved", "turn_progress", "turn_result", "turn_rejected", "guide_answer",
    "view", "story", "death", "cheat_activated", "cheat_result", "lanes_status", "dev_data", "error",
    "worlds", "world_file", "settings", "progress_plan", "progress", "progress_done", "code_result", "doom",
)

Screen = Literal["connect", "home", "wizard", "worldgen", "play", "dead"]


class InHello(Strict):
    client_version: str = "0"


class InModelsTest(Strict):
    lane: Lane


class InConfigSet(Strict):
    patch: dict = Field(description="Partial EngineConfig: only 'lanes' (per lane: name, base_url, model, "
                                    "max_concurrency, request_timeout_s) and 'background_cognition' (PROTO-10).")


class InContentValidate(Strict):
    pack_id: str


class InContentImport(Strict):
    filename: str
    data_b64: str
    pack_id: str = "my_content"


class InIntakeStart(Strict):
    filename: str
    data_b64: str
    target_kind: Literal["actor", "pc", "faction", "lore"]
    pack_id: str = "my_content"


class InQuickmakePC(Strict):
    name: str = Field(min_length=1, max_length=60)
    age: int = Field(ge=12, le=90)
    look: str = Field(max_length=300)
    before: str = Field(max_length=300, description="What they did before the Fall.")
    skills: list[str] = Field(min_length=1, max_length=3)
    flaw: str = Field(max_length=200)
    fear: str = Field(max_length=200)
    items: list[str] = Field(default_factory=list, max_length=5)


class InRunNew(Strict):
    pc_ref: str
    settings: RunSettings
    world_id: str | None = Field(default=None, description="Start in an existing world (its genesis snapshot) instead of generating one (RUN-09).")


class InRunLoad(Strict):
    run_id: str
    save_slot: str | None = None


class InRunDelete(Strict):
    run_id: str


class InRunSave(Strict):
    slot_name: str = Field(min_length=1, max_length=40)


class InTurnSubmit(Strict):
    mode: Literal["do", "say", "ask"]
    text: str = Field(default="", max_length=2000)
    suggestion_ref: str | None = None
    addressee_refs: list[str] = Field(default_factory=list)


class InSettingsSet(Strict):
    patch: dict = Field(description="Changed run settings, field -> new value; only the fields of "
                                    "service.session.CHANGEABLE_SETTINGS (SET-01, SET-02).")


class InDevGet(Strict):
    what: Literal["trace", "packets", "intents", "events", "gate", "errors", "calls"]
    turn_index: int | None = None


class InNewLifeHere(Strict):
    pc_ref: str


class InWorldExport(Strict):
    world_id: str


class InWorldImport(Strict):
    filename: str = Field(description="*.asworld (a zip holding genesis.sqlite + world.json).")
    data_b64: str


class InTurnCompose(Strict):
    """P12 (D-103): the Play input — Act, Say and (only while the console is open) Cheat, any of them,
    in one message; ``to`` the view refs Say is for (empty: service.game_service decides)."""

    act: str = Field(default="", max_length=2000)
    say: str = Field(default="", max_length=2000)
    cheat: str = Field(default="", max_length=2000)
    to: list[str] = Field(default_factory=list)


class InCodeEnter(Strict):
    """P12 (D-79, D-102, CHEAT-12): the menu's plainly labelled "Enter a code" box."""

    code: str = Field(min_length=1, max_length=40)


class OutWelcome(Strict):
    server_version: str
    screen: Screen
    has_runs: bool
    models_ok: bool


class OutState(Strict):
    screen: Screen
    run_id: str | None = None
    busy: bool = False


class OutModels(Strict):
    lane: Lane
    models: list[str]
    selected: str
    reachable: bool


class OutModelTest(Strict):
    lane: Lane
    ok: bool
    detail: str
    latency_ms: int | None = None
    structured_ok: bool | None = None
    thinking_ok: bool | None = None


class OutWorldgenProgress(Strict):
    stage: str
    label: str
    pct: float = Field(ge=0, le=100)
    eta_s: float | None = None


class OutTurnProgress(Strict):
    turn_index: int
    stage: int = Field(ge=0, le=19)
    label: str = Field(description="Friendly label, e.g. 'The world moves…'. Never an engine term.")
    pct: float = Field(ge=0, le=100)
    elapsed_s: float = Field(ge=0)


class ProgressSubView(Strict):
    id: str
    label: str


class ProgressPhaseView(Strict):
    id: str
    label: str
    weight: int = Field(ge=0, le=100)
    subs: list[ProgressSubView] = Field(default_factory=list)


class OutProgressPlan(Strict):
    """P10 (service.progress PROG-03): a long job's phases and sub-phases, in order, and the quips
    the UI may show for them."""
    job_id: str
    kind: Literal["worldgen", "turn", "quiet_hours", "time_skip"]
    title: str
    phases: list[ProgressPhaseView]
    quips: dict[str, list[str]] = Field(default_factory=dict)


class OutProgress(Strict):
    """P10 (PROG-03/04/05): where the job is now."""
    job_id: str
    kind: Literal["worldgen", "turn", "quiet_hours", "time_skip"]
    phase: str
    phase_index: int = Field(ge=0)
    sub: str | None = None
    sub_label: str | None = None
    done: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=0)
    pct: float = Field(ge=0, le=100)
    elapsed_s: float = Field(ge=0)
    eta_s: float | None = None
    detail: str | None = Field(default=None, description="Developer mode only (PROG-05).")


class OutProgressDone(Strict):
    job_id: str
    kind: Literal["worldgen", "turn", "quiet_hours", "time_skip"]
    ok: bool
    elapsed_s: float = Field(ge=0)


class OutTurnResult(Strict):
    turn_index: int
    narration: str
    view: PlayView
    notices: list[str] = Field(default_factory=list)
    degraded: bool = False


class OutTurnRejected(Strict):
    reason_code: Literal["impossible", "not_here", "not_holding", "not_trained", "unclear", "not_an_action", "busy", "dead",
                         "no_run", "empty", "suggestion_stale", "intake_failed", "no_models", "model_swapped", "turn_failed",
                         "decision_held", "doomed_words"]
    message: str
    clarify: str | None = None


class OutGuideAnswer(Strict):
    text: str


class OutStory(Strict):
    entries: list[StoryEntry]


class OutRuns(Strict):
    runs: list[RunSummaryView]


class OutRunDeleted(Strict):
    """A session was deleted; the Play UI forgets everything it held for it (RUN-12)."""

    run_id: str


class OutPCs(Strict):
    cards: list[PCCardView]


class OutContentReport(Strict):
    pack_id: str
    ok: bool
    errors: list[str] = Field(default_factory=list, description="Plain-language problems, each naming the file and field.")
    warnings: list[str] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)


class OutCheat(Strict):
    persona_line: str
    ok: bool = True
    detail: str = ""


class OutCodeResult(Strict):
    """Whether the code was taken — and nothing about what a code does (CHEATS §2)."""

    accepted: bool


class OutError(Strict):
    code: str
    message: str
    recoverable: bool = True


class OutLanes(Strict):
    lanes: LanesView


class OutDeath(Strict):
    death: DeathView


class DoomBeat(Strict):
    """D-106 (service.voice VOICE-01): one beat of the Doom scene, shown after ``pause_ms``."""

    kind: Literal["scene", "willis", "snatch", "voice"]
    text: str
    pause_ms: int = Field(ge=0, le=10_000)


class OutDoom(Strict):
    """D-106: the Doom scene, pushed before the result of the moment in which the PC's death became certain."""

    beats: list[DoomBeat]


class OutView(Strict):
    view: PlayView


class OutWorlds(Strict):
    worlds: list[WorldSummaryView]


class OutWorldFile(Strict):
    filename: str
    data_b64: str


class OutConfig(Strict):
    lanes: dict[Lane, LaneConfig]
    background_cognition: bool


class PackView(Strict):
    pack_id: str
    name: str
    version: str
    description: str
    records: int = Field(ge=0, description="Records this pack adds to the canon (loaded together with core).")
    core: bool


class OutPacks(Strict):
    packs: list[PackView]


class OutRunLoaded(Strict):
    run_id: str
    pc_name: str
    notices: list[str] = Field(default_factory=list, description="Plain lines to show once (content changed, files changed).")
    settings: RunSettings
    ironman: bool
    sandbox: bool


class OutSaved(Strict):
    slot: str
    label: str
    turn_index: int


class OutSettings(Strict):
    settings: RunSettings
    changeable: list[str] = Field(description="The fields settings_set accepts, in the Settings → Gameplay order.")


class OutDevData(Strict):
    what: Literal["trace", "packets", "intents", "events", "gate", "errors", "calls"]
    turn_index: int
    rows: list[dict]


IN_MODELS: dict[str, type[Strict] | None] = {
    "hello": InHello, "get_state": None, "models_list": None, "models_test": InModelsTest, "config_get": None,
    "config_set": InConfigSet, "packs_list": None, "pcs_list": None, "content_validate": InContentValidate,
    "content_import": InContentImport, "intake_start": InIntakeStart, "quickmake_pc": InQuickmakePC, "run_new": InRunNew,
    "worldgen_cancel": None, "runs_list": None, "run_load": InRunLoad, "run_delete": InRunDelete, "run_save": InRunSave,
    "run_close": None, "turn_submit": InTurnSubmit, "turn_cancel": None, "view_get": None, "story_get": None,
    "death_reveal": None, "new_life_here": InNewLifeHere, "dev_get": InDevGet, "worlds_list": None,
    "world_export": InWorldExport, "world_import": InWorldImport, "settings_get": None, "settings_set": InSettingsSet,
    "code_enter": InCodeEnter, "turn_compose": InTurnCompose,
}

OUT_MODELS: dict[str, type[Strict] | None] = {
    "welcome": OutWelcome, "state": OutState, "models": OutModels, "model_test_result": OutModelTest, "config": OutConfig,
    "packs": OutPacks, "pcs": OutPCs, "content_report": OutContentReport, "import_result": None, "intake_progress": None,
    "intake_result": None, "quickmake_result": None, "worldgen_progress": OutWorldgenProgress, "runs": OutRuns, "run_deleted": OutRunDeleted,
    "run_loaded": OutRunLoaded, "saved": OutSaved, "turn_progress": OutTurnProgress, "turn_result": OutTurnResult,
    "turn_rejected": OutTurnRejected, "guide_answer": OutGuideAnswer, "view": OutView, "story": OutStory,
    "death": OutDeath, "doom": OutDoom, "cheat_activated": OutCheat, "cheat_result": OutCheat, "lanes_status": OutLanes,
    "dev_data": OutDevData, "error": OutError, "worlds": OutWorlds, "world_file": OutWorldFile, "settings": OutSettings,
    "progress_plan": OutProgressPlan, "progress": OutProgress, "progress_done": OutProgressDone,
    "code_result": OutCodeResult,
}
