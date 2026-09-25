"""Play UI view model (docs/as/10_UI.md §View model).

Everything in a PlayView is built from the PC's own perception, beliefs and body — never from
the truth layer (L1 applied to the UI, rule UI-SKULL-01). Every string is plain player-facing
English: no internal ids, no engine vocabulary (rule UI-CLARITY-01 bans words like 'packet',
'affordance', 'percept', 'LOD', 'claim', 'intent' outside the developer panel).

``ref`` fields are opaque per-view handles ("i3", "p2", "s5", "x1") that the UI sends back in
requests; the server maps them to ids. They are never displayed.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import Strict


class ClockView(Strict):
    day: int = Field(ge=0, description="Days since the Fall.")
    time_text: str = Field(description="24h clock, e.g. '23:14'.")
    part_of_day: Literal["dawn", "morning", "midday", "afternoon", "evening", "night", "late night"]
    weather_text: str
    light_text: str


class SeenThing(Strict):
    ref: str | None = None
    name: str
    detail: str = ""


class PersonChip(Strict):
    ref: str
    label: str = Field(description="Name if the PC knows it, else a short description.")
    status_words: list[str] = Field(default_factory=list, description="e.g. ['asleep'], ['armed', 'hurt']")
    known: bool
    looks: str = Field(default="", description="F1a-2: how they look and smell to the PC now (as mind.packet LOOK-06); "
                       "'' when not seen clearly or partly.")


class ExitView(Strict):
    ref: str
    label: str
    state_words: list[str] = Field(default_factory=list, description="e.g. ['closed', 'barricaded']")
    leads_to: str = Field(description="Known destination or 'unknown'.")


class LocationView(Strict):
    place_name: str
    area_name: str
    description_lines: list[str] = Field(min_length=1, description="Code-rendered description, 1-6 lines.")
    can_see: list[SeenThing] = Field(default_factory=list)
    people: list[PersonChip] = Field(default_factory=list)
    exits: list[ExitView] = Field(default_factory=list)
    dangers: list[str] = Field(default_factory=list, description="Threats the PC believes in, with how they know.")
    noise_text: str


class ItemView(Strict):
    ref: str
    name: str
    qty: int = Field(ge=1)
    condition_word: Literal["pristine", "good", "worn", "damaged", "failing", "broken"]
    detail: str = ""
    mass_text: str = ""
    actions: list[str] = Field(default_factory=list, description="Labels that compose a Do command, e.g. 'Reload'.")


class ContainerView(Strict):
    item: ItemView
    bulk_used: int = Field(ge=0)
    bulk_max: int = Field(ge=1)
    contents: list["ItemView | ContainerView"] = Field(default_factory=list)


class InventoryView(Strict):
    hands: list[ItemView] = Field(default_factory=list, max_length=2)
    worn: list[ItemView] = Field(default_factory=list)
    containers: list[ContainerView] = Field(default_factory=list)
    carried_mass_kg: float = Field(ge=0)
    load_word: Literal["light", "moderate", "heavy", "overloaded"]


class WoundView(Strict):
    where: str
    what: str
    severity_word: Literal["minor", "serious", "severe", "critical"]
    bleeding_word: Literal["none", "oozing", "bleeding", "bleeding badly", "pouring"]
    treated: bool


class NeedView(Strict):
    name: Literal["Thirst", "Hunger", "Tiredness", "Pain", "Cold", "Heat"]
    level: int = Field(ge=0, le=5)
    word: str


class ResolveView(Strict):
    cur: int = Field(ge=0)
    max: int = Field(ge=1)
    word: Literal["steady", "shaken", "fraying", "breaking", "broken"]


class BodyView(Strict):
    wounds: list[WoundView] = Field(default_factory=list)
    needs: list[NeedView] = Field(default_factory=list)
    impairment_word: Literal["clear-headed", "slowed", "impaired", "badly impaired", "barely functioning"]
    resolve: ResolveView
    status_words: list[str] = Field(default_factory=list)
    infection_known: str | None = Field(default=None, description="Only what the PC believes about their own infection.")


class PersonView(Strict):
    ref: str
    label: str
    relation_words: list[str] = Field(default_factory=list, description="The PC's own feelings, e.g. ['trust her', 'owe her'].")
    last_seen_text: str
    what_you_know: list[str] = Field(default_factory=list)
    promises: list[str] = Field(default_factory=list)
    alive_known: Literal["alive", "dead", "unknown"]


class JournalView(Strict):
    promises_made: list[str] = Field(default_factory=list)
    promises_owed: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    rumours: list[str] = Field(default_factory=list)
    lessons: list[str] = Field(default_factory=list)
    the_dead: list[str] = Field(default_factory=list)
    reputation_heard: list[str] = Field(default_factory=list, description="Things the PC has heard people say about them.")


class MapPlace(Strict):
    ref: str
    label: str
    visited: bool
    here: bool
    exits_known: list[str] = Field(default_factory=list)
    travel_text: str = ""


class MapView(Strict):
    places: list[MapPlace] = Field(default_factory=list)


class SuggestionView(Strict):
    ref: str
    label: str
    mode: Literal["do", "say"]


class LaneStatus(Strict):
    label: str
    ok: bool
    model: str = ""
    detail: str = ""


class LanesView(Strict):
    A: LaneStatus
    B: LaneStatus


class StoryEntry(Strict):
    turn_index: int
    kind: Literal["narration", "player", "guide", "notice", "cheat"]
    text: str
    mode: Literal["do", "say", "ask"] | None = None


class MechanicsReceipt(Strict):
    lines: list[str] = Field(default_factory=list, description="e.g. 'Climb the fence: skilled (+2), wet (-1) -> success with a cost'")


class PlayView(Strict):
    run_id: str
    turn_index: int = Field(ge=0)
    pc_name: str
    alive: bool
    clock: ClockView
    location: LocationView
    inventory: InventoryView
    body: BodyView
    people: list[PersonView] = Field(default_factory=list)
    journal: JournalView = Field(default_factory=JournalView)
    map: MapView = Field(default_factory=MapView)
    suggestions: list[SuggestionView] = Field(default_factory=list, max_length=6)
    lanes: LanesView
    sandbox: bool = False
    mechanics: MechanicsReceipt | None = None


ContainerView.model_rebuild()


class PCCardView(Strict):
    ref: str
    display_name: str
    one_line_identity: str
    survives_by: str
    starts_as: str
    note: str
    source: Literal["pack", "imported", "quickmade"]
    warnings: list[str] = Field(default_factory=list)
    world_age_days: list[int] | None = Field(default=None, description="P10 (WG-34): [lo, hi] days since the Fall the character's story fits; None = any world.")
    world_age_note: str | None = Field(default=None, description="P10: the plain sentence the wizard shows on eras that do not fit.")


class RunSummaryView(Strict):
    run_id: str
    title: str
    pc_name: str
    day: int
    alive: bool
    difficulty: str
    last_played_text: str
    sandbox: bool
    ironman: bool
    world_id: str | None = None
    final: bool = Field(default=False, description="An Ironman life that has ended (RUN-08): it can be "
                        "deleted, not played on.")


class WorldSummaryView(Strict):
    """A reusable world: the genesis snapshot of a generated (or imported) world (RUN-09)."""

    world_id: str
    title: str = Field(description="e.g. 'Hot, humid, overgrown ruin — Mature, day 2214'.")
    difficulty: str
    era: str
    day_at_genesis: int
    climate_text: str
    factions: list[str] = Field(default_factory=list, description="Faction names present (player-facing).")
    created_text: str
    source: Literal["generated", "imported"]
    runs_using: int = 0


class DeathView(Strict):
    pc_name: str
    cause_text: str
    day: int
    time_text: str
    last_turns: list[str] = Field(default_factory=list, max_length=3)
    contributing: list[str] = Field(default_factory=list, description="Decisions that led here, from the PC's own record.")
    truth_reveal: list[str] = Field(default_factory=list, description="Shown only after the player clicks 'Show me everything'.")
    can_new_life_here: bool = Field(default=True, description="False in Ironman runs: death ends that run (RUN-08).")
    can_load: bool = Field(default=True, description="False in Ironman runs.")
    world_id: str | None = Field(default=None, description="The run's world, for 'Start fresh in this world'.")
