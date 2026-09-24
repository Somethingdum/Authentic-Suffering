"""A loaded run (P7).

Session(run_id, run_dir, store, canon, config: EngineConfig, settings: RunSettings, rng: Rng,
        client: LaneClient, pc_id) — everything a turn needs. Created by service.runs
(create_run_from_scenario / load_run; create_run from P10) and, in tests, by
testing.scenario.ScenarioWorld.session() (run_dir None: an in-memory run that never autosaves).
One Session is active per GameService at a time. ``config`` carries the run's frozen rules
(meta.rules_json, SET-03); ``busy`` is True while run_turn runs.
``extras`` holds per-session UI state that is not world state and is never saved:
  'view_refs'      ref -> internal id of the last PlayView (service.view; UI-REF-01)
  'suggestions'    ref -> {'signature', 'label'} | {'remainder', 'label'} (service.view -> turn.intake)
  'last_addressee' the body the PC last spoke to (turn.intake's default addressee)
  'remainder'      the rest of a multi-step instruction ("Continue: …" next turn)
  'notices'        plain lines service.runs.load_run wants shown once
  'pack_dirs'      the pack folders the run's canon was loaded from (service.runs)
  'forced_addressee' set only by service.replay for one re-simulated input

append_story(tx, turn_index, kind, text, mode=None) -> int   (bookkeeping, owner 'service')
  Insert one story_log row {entry_id = the current max entry_id + 1 (1 when empty), turn_index,
  kind ('narration' | 'player' | 'guide' | 'notice' | 'cheat'), mode, text}; returns entry_id. The
  Play UI's story panel is story_log in entry_id order.

CHANGEABLE_SETTINGS: the RunSettings fields a running game may change (docs/as/11_SETTINGS.md §1.2,
  in the Settings → Gameplay order). Every other field is locked for the run (SET-02).
change_settings(tx, session, patch) -> list[Event]   (P8; SET-01)
  ``patch`` maps field -> new value. A key not in RunSettings.model_fields -> ValueError(f"unknown
  setting: {key}"); a key that is a field but not in CHANGEABLE_SETTINGS -> LockedSetting(key).
  new = RunSettings.model_validate({**session.settings.model_dump(mode='json'), **patch}) (a bad
  value raises pydantic's ValidationError). For each field of CHANGEABLE_SETTINGS, in that order,
  whose value differs: one SETTINGS_CHANGE event {field, old, new} (JSON values; writer
  'kernel.meta', origin 'system', at = world_clock.now_ms, turn_index = world_clock.turn_index)
  updating meta settings_json to the settings as changed SO FAR (after this field) — so the last
  event leaves meta.settings_json = new.model_dump_json(). session.settings = new (it applies from
  the next turn). Returns the committed events (none when nothing differs).
  service.replay re-applies these events between the turns it re-simulates (SET-01: a replay
  reproduces a settings change), so the payload must carry everything needed to redo it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..contracts.settings import EngineConfig, RunSettings
    from ..kernel.rng import Rng
    from ..kernel.store import Store
    from ..lanes.client import LaneClient


@dataclass
class Session:
    run_id: str
    run_dir: Path | None
    store: "Store"
    canon: Any
    config: "EngineConfig"
    settings: "RunSettings"
    rng: "Rng"
    client: "LaneClient"
    pc_id: str
    busy: bool = False
    cheat_active: bool = False
    extras: dict = field(default_factory=dict)


CHANGEABLE_SETTINGS: tuple[str, ...] = (
    "turn_depth", "narration_length", "narration_person", "narration_tense", "pc_voice", "intensity",
    "show_mechanics", "read_aloud", "dev_mode", "autosave_ring",
)


class LockedSetting(ValueError):
    """A run setting that is chosen when a life starts and cannot change during it (SET-02)."""

    def __init__(self, field_name: str):
        super().__init__(f"locked setting: {field_name}")
        self.field_name = field_name


def change_settings(tx, session: "Session", patch: dict) -> list:
    raise NotImplementedError("P8")


def append_story(tx, turn_index: int, kind: str, text: str, mode: str | None = None) -> int:
    raise NotImplementedError("P7")
