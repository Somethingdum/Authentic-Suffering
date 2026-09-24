"""The 58-bit commit gate (Stage 12, G12). Rules AUDIT-01..03, L13.
[SALVAGE: S/U Turn-5 Final Audit Gate — SESSION_CHECK 12b, WORLD_CHECK 16b, ENTITIES_CHECK 16b,
GLOBAL_CHECK 14b]. The S/U bit names are carried unchanged; each bit is re-grounded as a property
of the run database that CODE computes. The model never prints or grades these (L13).

compute(tx, turn_index) -> GateResult(session, world, entities, global_, failures)
  Each bit is 1 iff its check passes. A check must only look at what its description says, so
  that injecting the fault listed in tests/contract/p11_audits/test_commit_gate_bits.py drops
  EXACTLY that bit (AUDIT-02: a bit that never drops is not a check).
  "this turn" = rows/events whose turn_index == turn_index.
  Genesis (no PC yet, or turn 0): the PC bits (W09, E01, E02, E03, E04) are 1 when
  meta.pc_actor_id == ''; the turn-ledger bits (S01, S02, S10's turn part is none) apply only when
  turn_index >= 1. Every other check is written so that an EMPTY world (fresh Store.memory())
  passes it — the P0 framework test computes all 58 bits = 1 on a fresh store at turn 0.
  failures lists the ids of the zero bits, in ALL_BITS order.
Turn pipeline behaviour (G12): all 58 must be 1 or the transaction does not commit. On a zero:
  identify the failing stage (BIT_STAGE), roll back, rerun from that stage once in strict mode
  (repair calls on, reactions capped at 1), recompute; if a bit is still 0, write
  error_repair_log(kind='rollback', rule_id=bit id), leave the world at the previous committed
  state, and report the failure to the UI (turn_rejected / error, player input NOT consumed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..kernel.store import Store, Tx


@dataclass(frozen=True)
class Bit:
    id: str
    legacy: str
    check: str


SESSION_BITS: tuple[Bit, ...] = (
    Bit("S01", "TurnLedger_Exactly4Stages", "turn_ledger has a row for every stage 0..11 of this turn"),
    Bit("S02", "OneOutputPerStage", "no turn_ledger row of this turn has final status 'failed'"),
    Bit("S03", "PlayerInput_NotSynthesized", "if a player_inputs row exists for this turn, received_hash == sha256(raw_text utf-8) hex"),
    Bit("S04", "NoPlaceholdersOrEmptySections", "no voice_lines/episodes/propositions text written this turn is empty or contains a CNT-01 exhaust/placeholder string"),
    Bit("S05", "NoMetaOrDevText", "no SPEECH event payload.words of this turn contains META_STRINGS (case-insensitive)"),
    Bit("S06", "FinalTurnContext_Present", "world_clock.turn_index == this turn"),
    Bit("S07", "CodexNarrativeState_Present", "narrator_state row id=1 exists and its style_json validates as NarratorStyle"),
    Bit("S08", "TENCL_Present", "no event_queue row with status 'pending' has due_at < world_clock.now_ms"),
    Bit("S09", "Objectives_Present", "every open_loops.kind is an OpenLoopKind value and text is non-empty"),
    Bit("S10", "Timers_Present", "every tasks row with status 'active' has a non-NULL next_due_at"),
    Bit("S11", "ErrorLog_Windowed_Present", "every error_repair_log.kind of this turn is in ERROR_KINDS and stage is NULL or 0..19"),
    Bit("S12", "QueuedAction_Preserved", "every pending_reactions row with status 'pending' references an actors row whose body is alive"),
)
WORLD_BITS: tuple[Bit, ...] = (
    Bit("W01", "PWOSS_Present", "every item's holder_body / container_id / place_id references an existing row"),
    Bit("W02", "PWOSS_Format_Valid", "every items.props parses as a JSON object"),
    Bit("W03", "PWOSS_Window_Bounded", "no container item holds more total bulk than its container.capacity_bulk (canon ItemDef)"),
    Bit("W04", "PWOSS_LastWriterReduce_Applied", "for every def_ref, sum(items.qty) == created - destroyed per ITEM_CREATED/ITEM_DESTROYED event payload qty"),
    Bit("W05", "LSDL_Present", "every positions.anchor_id (when not NULL) belongs to positions.place_id"),
    Bit("W06", "LSDL_Format_Valid", "every places.props parses as a JSON object"),
    Bit("W07", "LSDL_Window_Bounded", "every traces.decays_at is NULL or > created_at, and locked traces have decays_at NULL"),
    Bit("W08", "LSDL_LastWriterReduce_Applied", "no portal is both is_open = 1 and barricade > 0"),
    Bit("W09", "PLMP_CurrentLoc_Present", "the PC has a known_places row for the place it is in"),
    Bit("W10", "SOL_Present_Windowed", "no groups.next_due_at is earlier than world_clock.now_ms - 1 day"),
    Bit("W11", "SOL<->MEMORY_Crossref_OK", "every id in operations.participants references an existing body"),
    Bit("W12", "THREATS_Table_Present", "every infected_state.target_id is NULL or an existing body or place id"),
    Bit("W13", "ECON_Snapshot_Present", "every settlements.stores value is a number >= 0"),
    Bit("W14", "No_Deprecated_World_Fields", "no narration.text of this turn contains a retired name (RETIRED_NAMES, case-sensitive)"),
    Bit("W15", "No_AgedOrSuperseded_Deltas", "every claim_holdings.superseded_by (when not NULL) references an existing claims.claim_id or propositions.prop_id"),
    Bit("W16", "IDs_Unique_And_Resolvable", "every events.cause_event_id (when not NULL) references an existing event"),
)
ENTITY_BITS: tuple[Bit, ...] = (
    Bit("E01", "PC_Dossier_Present", "meta.pc_actor_id references an actors row whose dossier_id references a dossiers row"),
    Bit("E02", "PC_Identity_Immutables_Intact", "no dossier_deltas row for the PC has a path starting with 'identity.'"),
    Bit("E03", "PC_Inventory_Delta_Valid", "the PC holds at most one item in hand_l and at most one in hand_r"),
    Bit("E04", "PC_Relationships_Delta_Valid", "every relationships row with from_id or to_id = PC references existing bodies on both ends"),
    Bit("E05", "NPC_Set_ActiveOrRecent_Covered", "every living body with an actors row has a positions row"),
    Bit("E06", "Each_NPC_Dossier_Present", "every actors.dossier_id references a dossiers row"),
    Bit("E07", "NPC_Identity_Immutables_Intact", "every dossiers.content_hash == sha256(baseline_json utf-8) hex"),
    Bit("E08", "NPC_Traits_Wounds_Goals_Present", "every wounds.body_id references an existing body"),
    Bit("E09", "NPC_INV_EQ_PERSONAL_KEY_Present_IfRequired", "every items row with holder_body NOT NULL has holder_slot NOT NULL"),
    Bit("E10", "REL_Deltas_Bounded_To_Window", "every RELATION_CHANGE event of this turn has |payload.delta| <= 2"),
    Bit("E11", "Cheat_Surface_Redacted", "when meta.cheat_active != '1', no narration or story_log text of this turn contains CHEAT_STRINGS (case-insensitive)"),
    Bit("E12", "SOL<->NPC_Crossref_OK", "every group_members row references an existing group and an existing body"),
    Bit("E13", "No_MetaOrPlaceholders_In_Dossiers", "no dossiers.baseline_json contains a CNT-01 exhaust/placeholder string"),
    Bit("E14", "Annex_Used_When_Large", "no events.payload of this turn is longer than 65536 characters (large payloads go to blobs)"),
    Bit("E15", "Annex_Hash_Present_ForEach", "every blobs.hash == sha256(content utf-8) hex"),
    Bit("E16", "Backfill_Flags_Correct", "every event with origin 'migration' has type MIGRATION_BACKFILL"),
)
GLOBAL_BITS: tuple[Bit, ...] = (
    Bit("G01", "Schema_Envelope_Valid", "meta.schema_version == str(SCHEMA_VERSION)"),
    Bit("G02", "Slot_Coverage_Full", "meta has every key in REQUIRED_META_KEYS"),
    Bit("G03", "Baseline_ID_Recorded", "meta.run_id is non-empty"),
    Bit("G04", "Window_Timestamps_Valid", "no events.at is greater than world_clock.now_ms"),
    Bit("G05", "Hash_Manifest_Written", "every turn t with 0 < t < this turn has a commit_gate_log row"),
    Bit("G06", "No_Fused_Turns_Detected", "no turn_ledger row has turn_index > this turn"),
    Bit("G07", "No_EmptyOrPlaceholder_Sections", "every SPEECH event has payload.words non-empty, every HARM event has payload.wound_id, every DEATH event has payload.cause"),
    Bit("G08", "No_NonWhitelisted_Sources", "every events.type is an EventType value and every events.writer is in ownership.EVENT_WRITERS"),
    Bit("G09", "Serialization_Readiness", "every events.state_delta parses as a JSON list"),
    Bit("G10", "Retry_Budget_Remaining>=0", "no turn_ledger row of this turn has run_count > 3"),
    Bit("G11", "SaveFile_Size_Within_Limit", "prng_ledger.seq values are exactly 1..max(seq) with no gaps"),
    Bit("G12", "Deterministic_Orderings", "events.seq values are exactly 1..max(seq) with no gaps"),
    Bit("G13", "Annex_Used_All_Stages", "every turn_ledger.output_ref (when not NULL) references an existing blob"),
    Bit("G14", "Annex_Hash_Present_ForEach", "every lm_calls.request_hash is 64 lowercase hex characters"),
)
ALL_BITS: tuple[Bit, ...] = SESSION_BITS + WORLD_BITS + ENTITY_BITS + GLOBAL_BITS
assert len(ALL_BITS) == 58

META_STRINGS: tuple[str, ...] = ("as an ai", "language model", "skull packet", "affordance", "json",
                                 "system prompt", "i cannot comply", "handle a")
CHEAT_STRINGS: tuple[str, ...] = ("2508", "mr. cheater man", "cheat code", "cheat mode")
RETIRED_NAMES: tuple[str, ...] = ("sotry", "PWOSS", "LSDL", "PLMP", "TENCL", "MEMORY_LOG", "SOL_ADD")
EXHAUST_STRINGS: tuple[str, ...] = ("IGNORE_WHEN_COPYING", "content_copy", "Use code with caution",
                                    "As an AI", "[INSERT", "TODO", "lorem ipsum")
ERROR_KINDS: tuple[str, ...] = ("grammar_fail", "schema_fail", "hallucinated_ref", "lane_down", "timeout",
                                "lint_fail", "rollback", "degraded", "migration", "budget_overrun",
                                "echo_reject", "portrayal_fail")
REQUIRED_META_KEYS: tuple[str, ...] = ("run_id", "seed", "schema_version", "created_at_real",
                                       "content_hash", "settings_json", "rules_json", "pc_actor_id",
                                       "sandbox", "cheat_active", "world_epoch_text")
BIT_STAGE: dict[str, int] = {b.id: 12 for b in ALL_BITS}  # refine per bit when implementing


@dataclass
class GateResult:
    session: str
    world: str
    entities: str
    global_: str
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures

    def bit(self, bit_id: str) -> int:
        seq = self.session + self.world + self.entities + self.global_
        return int(seq[[b.id for b in ALL_BITS].index(bit_id)])


def compute(store_or_tx: "Store | Tx", turn_index: int) -> GateResult:
    raise NotImplementedError("P11 (framework in P0; checks added as subsystems land)")
