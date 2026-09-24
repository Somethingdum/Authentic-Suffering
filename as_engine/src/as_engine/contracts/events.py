"""Events and typed write records (docs/as/03_DATA_MODEL.md §Events).

LAW (L2/L3, rule STORE-01): every change to runtime state is a WriteRecord carried by exactly one
Event. ``kernel.store.Store.commit_event`` is the only function that applies WriteRecords.
Replaying all events in ``seq`` order onto the genesis snapshot reproduces the state byte for byte.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import Field

from .common import Strict


class EventClass(StrEnum):
    PHYSICAL = "physical"
    BODY = "body"
    ACTION = "action"
    MIND = "mind"
    SOCIAL = "social"
    SOCIETY = "society"
    WORLD = "world"
    SYSTEM = "system"


class EventType(StrEnum):
    # physical
    MOVE = "MOVE"
    PORTAL_CHANGE = "PORTAL_CHANGE"
    ITEM_TRANSFER = "ITEM_TRANSFER"
    ITEM_CONDITION = "ITEM_CONDITION"
    ITEM_CREATED = "ITEM_CREATED"
    ITEM_DESTROYED = "ITEM_DESTROYED"
    STRUCTURE_DAMAGE = "STRUCTURE_DAMAGE"
    NOISE = "NOISE"
    LIGHT_CHANGE = "LIGHT_CHANGE"
    FIRE_STEP = "FIRE_STEP"
    WEATHER_CHANGE = "WEATHER_CHANGE"
    PLACE_DISCOVERED = "PLACE_DISCOVERED"
    PLACE_CHANGE = "PLACE_CHANGE"            # P10: physical.space changes a place (held, props, light)
    # body
    HARM = "HARM"
    WOUND_PROGRESS = "WOUND_PROGRESS"
    TREATMENT = "TREATMENT"
    NEED_STAGE = "NEED_STAGE"
    INFECTION_EXPOSURE = "INFECTION_EXPOSURE"
    INFECTION_STAGE = "INFECTION_STAGE"
    DEATH = "DEATH"
    FALSE_DEATH = "FALSE_DEATH"
    REANIMATION = "REANIMATION"
    AWARENESS_CHANGE = "AWARENESS_CHANGE"
    IMPAIRMENT_CHANGE = "IMPAIRMENT_CHANGE"
    RESOLVE_CHANGE = "RESOLVE_CHANGE"
    POSTURE_CHANGE = "POSTURE_CHANGE"
    # action
    ACTION_START = "ACTION_START"
    ACTION_COMPLETE = "ACTION_COMPLETE"
    ACTION_INTERRUPT = "ACTION_INTERRUPT"
    ACTION_BLOCKED = "ACTION_BLOCKED"
    TASK_STEP = "TASK_STEP"
    CONTROL_ESTABLISH = "CONTROL_ESTABLISH"
    CONTROL_RELEASE = "CONTROL_RELEASE"
    CHECK_RESOLVED = "CHECK_RESOLVED"
    INVOLUNTARY = "INVOLUNTARY"
    # mind
    PERCEIVE = "PERCEIVE"
    BELIEF_FORM = "BELIEF_FORM"
    BELIEF_REVISE = "BELIEF_REVISE"
    RELATION_CHANGE = "RELATION_CHANGE"
    REFUSAL = "REFUSAL"
    PROMISE = "PROMISE"
    PROMISE_KEPT = "PROMISE_KEPT"
    PROMISE_BROKEN = "PROMISE_BROKEN"
    LOOP_OPENED = "LOOP_OPENED"
    LOOP_CLOSED = "LOOP_CLOSED"
    LIE_TOLD = "LIE_TOLD"
    LIE_DISCOVERED = "LIE_DISCOVERED"
    PERSONA_PIERCED = "PERSONA_PIERCED"
    LESSON_LEARNED = "LESSON_LEARNED"
    ANCHOR_MEMORY = "ANCHOR_MEMORY"
    EPISODE_WRITTEN = "EPISODE_WRITTEN"
    REFLECTION = "REFLECTION"
    PLAN_CHANGE = "PLAN_CHANGE"
    # social
    SPEECH = "SPEECH"
    REQUEST = "REQUEST"
    ORDER = "ORDER"
    THREAT = "THREAT"
    OFFER = "OFFER"
    DELIBERATE_QUOTATION = "DELIBERATE_QUOTATION"
    TENSION_CHANGE = "TENSION_CHANGE"
    ESCALATION = "ESCALATION"
    DEFECTION = "DEFECTION"
    LEADERSHIP_CHALLENGE = "LEADERSHIP_CHALLENGE"
    RECONCILIATION = "RECONCILIATION"
    RUMOUR_SPREAD = "RUMOUR_SPREAD"
    LOYALTY_CHECK = "LOYALTY_CHECK"          # P9: society.group records a group benefit check
    STANDING_CHANGE = "STANDING_CHANGE"      # P9: society.group changes a group's standing toward someone
    RUMOUR_DISTORTED = "RUMOUR_DISTORTED"    # P10: world.rumours records how a holder will retell a rumour
    # society
    SHIFT_START = "SHIFT_START"
    SHIFT_MISSED = "SHIFT_MISSED"
    PRODUCTION_CYCLE = "PRODUCTION_CYCLE"
    SHORTAGE = "SHORTAGE"
    RATION_CHANGE = "RATION_CHANGE"
    LAW_APPLIED = "LAW_APPLIED"
    BIRTH = "BIRTH"
    HOUSEHOLD_CHANGE = "HOUSEHOLD_CHANGE"
    ROLE_ASSIGNED = "ROLE_ASSIGNED"
    ROLE_RELEASED = "ROLE_RELEASED"          # P9: society.work ends a cover assignment
    WORKPLACE_CHANGE = "WORKPLACE_CHANGE"    # P9: society.work changes efficiency / machinery condition
    STORES_CHANGE = "STORES_CHANGE"          # P9: society.settlement adds to / draws from its stores
    SETTLEMENT_DAY = "SETTLEMENT_DAY"        # P9: society.settlement's daily draw
    SETTLEMENT_CHANGE = "SETTLEMENT_CHANGE"  # P9: society.settlement changes morale, vacancies, ...
    SHORTAGE_ENDED = "SHORTAGE_ENDED"        # P9: society.settlement clears a shortage
    ROUTINE_STEP = "ROUTINE_STEP"            # P9: society.routine moves a life on to its next step
    GROUP_DAY = "GROUP_DAY"                  # P9: society.group's daily tick
    # world
    FACTION_OPERATION = "FACTION_OPERATION"
    MIGRATION = "MIGRATION"
    TRADE = "TRADE"
    RAID = "RAID"
    CONSTRUCTION = "CONSTRUCTION"
    INFRASTRUCTURE_FAIL = "INFRASTRUCTURE_FAIL"
    TRACE_CREATED = "TRACE_CREATED"
    TRACE_DECAYED = "TRACE_DECAYED"
    POPULATION_CHANGE = "POPULATION_CHANGE"
    MATERIALIZE = "MATERIALIZE"
    INFECTED_DRIFT = "INFECTED_DRIFT"
    OFFSCREEN_DEATH = "OFFSCREEN_DEATH"
    INFECTED_STATE = "INFECTED_STATE"        # P10: world.infected changes an infected body's state / energy / target
    WORLD_DAY = "WORLD_DAY"                  # P10: world.worldmove's daily tick
    # system
    WORLDGEN_STAGE = "WORLDGEN_STAGE"
    SCENE_START = "SCENE_START"
    SCENE_END = "SCENE_END"
    CLOCK_ADVANCE = "CLOCK_ADVANCE"
    TIMER_SET = "TIMER_SET"
    TIMER_FIRED = "TIMER_FIRED"
    TIMER_CANCELLED = "TIMER_CANCELLED"
    DECAY_TIER_1 = "DECAY_TIER_1"
    DECAY_TIER_2 = "DECAY_TIER_2"
    DECAY_TIER_3 = "DECAY_TIER_3"
    OVERRIDE = "OVERRIDE"
    MIGRATION_BACKFILL = "MIGRATION_BACKFILL"
    DEGRADED_FALLBACK = "DEGRADED_FALLBACK"
    CHEAT_ACTIVATED = "CHEAT_ACTIVATED"
    CHEAT_OVERRIDE = "CHEAT_OVERRIDE"
    CHEAT_DEACTIVATED = "CHEAT_DEACTIVATED"
    PLAYER_INPUT = "PLAYER_INPUT"
    PC_CONTROL_CHANGE = "PC_CONTROL_CHANGE"
    SETTINGS_CHANGE = "SETTINGS_CHANGE"
    NARRATION = "NARRATION"                  # P7: narration.narrator writes the turn's prose row
    ECHO_RECORD = "ECHO_RECORD"              # P7: narration.lint records / expires echo_ledger rows
    PENDING_REACTION = "PENDING_REACTION"    # P7: turn.pipeline parks / resolves a pending_reactions row


EVENT_CLASS: dict[EventType, EventClass] = {}
_groups: dict[EventClass, list[str]] = {
    EventClass.PHYSICAL: ["MOVE", "PORTAL_CHANGE", "ITEM_TRANSFER", "ITEM_CONDITION", "ITEM_CREATED",
                          "ITEM_DESTROYED", "STRUCTURE_DAMAGE", "NOISE", "LIGHT_CHANGE", "FIRE_STEP",
                          "WEATHER_CHANGE", "PLACE_DISCOVERED", "PLACE_CHANGE"],
    EventClass.BODY: ["HARM", "WOUND_PROGRESS", "TREATMENT", "NEED_STAGE", "INFECTION_EXPOSURE",
                      "INFECTION_STAGE", "DEATH", "FALSE_DEATH", "REANIMATION", "AWARENESS_CHANGE",
                      "IMPAIRMENT_CHANGE", "RESOLVE_CHANGE", "POSTURE_CHANGE"],
    EventClass.ACTION: ["ACTION_START", "ACTION_COMPLETE", "ACTION_INTERRUPT", "ACTION_BLOCKED",
                        "TASK_STEP", "CONTROL_ESTABLISH", "CONTROL_RELEASE", "CHECK_RESOLVED", "INVOLUNTARY"],
    EventClass.MIND: ["PERCEIVE", "BELIEF_FORM", "BELIEF_REVISE", "RELATION_CHANGE", "REFUSAL", "PROMISE",
                      "PROMISE_KEPT", "PROMISE_BROKEN", "LOOP_OPENED", "LOOP_CLOSED", "LIE_TOLD",
                      "LIE_DISCOVERED", "PERSONA_PIERCED", "LESSON_LEARNED", "ANCHOR_MEMORY",
                      "EPISODE_WRITTEN", "REFLECTION", "PLAN_CHANGE"],
    EventClass.SOCIAL: ["SPEECH", "REQUEST", "ORDER", "THREAT", "OFFER", "DELIBERATE_QUOTATION",
                        "TENSION_CHANGE", "ESCALATION", "DEFECTION", "LEADERSHIP_CHALLENGE",
                        "RECONCILIATION", "RUMOUR_SPREAD", "LOYALTY_CHECK", "STANDING_CHANGE",
                        "RUMOUR_DISTORTED"],
    EventClass.SOCIETY: ["SHIFT_START", "SHIFT_MISSED", "PRODUCTION_CYCLE", "SHORTAGE", "RATION_CHANGE",
                         "LAW_APPLIED", "BIRTH", "HOUSEHOLD_CHANGE", "ROLE_ASSIGNED", "ROLE_RELEASED",
                         "WORKPLACE_CHANGE", "STORES_CHANGE", "SETTLEMENT_DAY", "SETTLEMENT_CHANGE",
                         "SHORTAGE_ENDED", "ROUTINE_STEP", "GROUP_DAY"],
    EventClass.WORLD: ["FACTION_OPERATION", "MIGRATION", "TRADE", "RAID", "CONSTRUCTION",
                       "INFRASTRUCTURE_FAIL", "TRACE_CREATED", "TRACE_DECAYED", "POPULATION_CHANGE",
                       "MATERIALIZE", "INFECTED_DRIFT", "OFFSCREEN_DEATH", "INFECTED_STATE", "WORLD_DAY"],
    EventClass.SYSTEM: ["WORLDGEN_STAGE", "SCENE_START", "SCENE_END", "CLOCK_ADVANCE", "TIMER_SET", "TIMER_FIRED", "TIMER_CANCELLED", "DECAY_TIER_1",
                        "DECAY_TIER_2", "DECAY_TIER_3", "OVERRIDE", "MIGRATION_BACKFILL",
                        "DEGRADED_FALLBACK", "CHEAT_ACTIVATED", "CHEAT_OVERRIDE", "CHEAT_DEACTIVATED",
                        "PLAYER_INPUT", "PC_CONTROL_CHANGE", "SETTINGS_CHANGE", "NARRATION",
                        "ECHO_RECORD", "PENDING_REACTION"],
}
for _cls, _names in _groups.items():
    for _n in _names:
        EVENT_CLASS[EventType(_n)] = _cls
assert set(EVENT_CLASS) == set(EventType), "every EventType must have a class"


class WriteOp(StrEnum):
    INSERT = "insert"
    UPDATE = "update"
    UPSERT = "upsert"
    DELETE = "delete"


class WriteRecord(Strict):
    """One typed mutation of one row.

    * ``table`` must exist in kernel/schema.sql and be listed in kernel.ownership.TABLE_OWNERS.
    * ``key`` holds the primary-key columns (all of them) for UPDATE/UPSERT/DELETE, and may be
      empty for INSERT when every PK column is inside ``values``.
    * ``values`` holds the columns to write. JSON columns are given as Python dict/list and are
      serialised by the store with ``json.dumps(sort_keys=True, separators=(',', ':'))``.
    """

    op: WriteOp
    table: str
    key: dict[str, Any] = Field(default_factory=dict)
    values: dict[str, Any] = Field(default_factory=dict)


class Event(Strict):
    event_id: str | None = Field(default=None, description="Minted by the store on commit (kind 'evt').")
    seq: int | None = Field(default=None, description="Global order, assigned by the store.")
    at: int = Field(ge=0, description="World time in ms since world epoch.")
    type: EventType
    writer: str = Field(description="Owning module id, e.g. 'physical.space'. Must own every table it writes.")
    actor_id: str | None = None
    target_ids: list[str] = Field(default_factory=list)
    place_id: str | None = None
    cause_event_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    writes: list[WriteRecord] = Field(default_factory=list)
    rule_cited: str | None = None
    turn_index: int = Field(ge=0)
    origin: Literal["sim", "worldgen", "cheat", "migration", "system"] = "sim"
