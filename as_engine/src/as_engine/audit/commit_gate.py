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
                                "echo_reject", "portrayal_fail", "decision_held")
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
    import hashlib, json, re
    from ..contracts.events import EventType
    from ..contracts.common import OpenLoopKind
    from ..contracts.narration import NarratorStyle
    from ..kernel.ownership import EVENT_WRITERS as MODULES
    from ..kernel.store import SCHEMA_VERSION
    q = store_or_tx.query
    q1 = store_or_tx.query_one
    T = turn_index
    meta = {r[0]: r[1] for r in q("SELECT key, value FROM meta")}
    pc = meta.get("pc_actor_id", "")
    now = q1("SELECT now_ms, turn_index FROM world_clock WHERE id=1")
    sha = lambda t: hashlib.sha256(t.encode("utf-8")).hexdigest()
    def jobj(t):
        try:
            return isinstance(json.loads(t), dict)
        except Exception:
            return False
    def has_exhaust(t):
        return (t is None) or (t.strip() == "") or any(x.lower() in t.lower() for x in EXHAUST_STRINGS)
    bodies = {r[0] for r in q("SELECT body_id FROM bodies")}
    def body_alive(b):
        r = q1("SELECT alive FROM bodies WHERE body_id=?", (b,))
        return r is not None and r[0] == 1
    checks = {}
    # ---- session
    stages = {r[0] for r in q("SELECT stage FROM turn_ledger WHERE turn_index=?", (T,))}
    checks["S01"] = T < 1 or set(range(12)) <= stages
    checks["S02"] = T < 1 or not q("SELECT 1 FROM turn_ledger WHERE turn_index=? AND status='failed'", (T,))
    r = q1("SELECT received_hash, raw_text FROM player_inputs WHERE turn_index=?", (T,))
    checks["S03"] = r is None or r[0] == sha(r[1])
    bad = False
    for tbl, col in (("voice_lines", "text"), ("episodes", "text"), ("propositions", "text")):
        pass
    ok = True
    for tbl, col, turncol in (("voice_lines", "text", None), ("episodes", "summary", "turn_index"), ("propositions", "text", None)):
        pass
    for r in q("SELECT text FROM voice_lines v JOIN events e ON e.event_id=v.event_id WHERE e.turn_index=?", (T,)):
        ok = ok and not has_exhaust(r[0])
    for r in q("SELECT summary FROM episodes WHERE turn_index=?", (T,)):
        ok = ok and not has_exhaust(r[0])
    for r in q("SELECT p.text FROM propositions p JOIN events e ON e.event_id=p.created_event WHERE e.turn_index=?", (T,)):
        ok = ok and not has_exhaust(r[0])
    checks["S04"] = ok
    ok = True
    for e in q("SELECT payload FROM events WHERE turn_index=? AND type='SPEECH'", (T,)):
        words = json.loads(e[0]).get("words", "").lower()
        if any(m in words for m in META_STRINGS):
            ok = False
    checks["S05"] = ok
    checks["S06"] = now[1] == T
    ns = q1("SELECT style_json FROM narrator_state WHERE id=1")
    try:
        checks["S07"] = ns is not None and bool(NarratorStyle.model_validate_json(ns[0]))
    except Exception:
        checks["S07"] = False
    checks["S08"] = not q("SELECT 1 FROM event_queue WHERE status='pending' AND due_at < ?", (now[0],))
    kinds = {k.value for k in OpenLoopKind}
    checks["S09"] = all(r[0] in kinds and (r[1] or "").strip() for r in q("SELECT kind, text FROM open_loops"))
    checks["S10"] = not q("SELECT 1 FROM tasks WHERE status='active' AND next_due_at IS NULL")
    checks["S11"] = all(r[0] in ERROR_KINDS and (r[1] is None or 0 <= r[1] <= 19) for r in q("SELECT kind, stage FROM error_repair_log WHERE turn_index=?", (T,)))
    checks["S12"] = all(body_alive(r[0]) and q1("SELECT 1 FROM actors WHERE actor_id=?", (r[0],)) for r in q("SELECT actor_id FROM pending_reactions WHERE status='pending'"))
    # ---- world
    checks["W01"] = all((r[0] is None or r[0] in bodies) and (r[1] is None or q1("SELECT 1 FROM items WHERE item_id=?", (r[1],))) and (r[2] is None or q1("SELECT 1 FROM places WHERE place_id=?", (r[2],))) for r in q("SELECT holder_body, container_id, place_id FROM items"))
    checks["W02"] = all(jobj(r[0]) for r in q("SELECT props FROM items"))
    canon = getattr(store_or_tx, "canon", None)
    if canon is None and hasattr(store_or_tx, "store"):
        canon = store_or_tx.store.canon
    ok = True
    if canon is not None:
        for r in q("SELECT item_id, def_ref FROM items"):
            d = canon.get(r[1]) if canon.has(r[1]) else None
            if d is not None and d.container is not None:
                used = 0
                for c in q("SELECT def_ref, qty FROM items WHERE container_id=?", (r[0],)):
                    used += (canon.get(c[0]).bulk if canon.has(c[0]) else 0) * c[1]
                ok = ok and used <= d.container.capacity_bulk
    checks["W03"] = ok
    ledger = {}
    for r in q("SELECT type, payload FROM events WHERE type IN ('ITEM_CREATED','ITEM_DESTROYED')"):
        pl = json.loads(r[1])
        ledger[pl["def_ref"]] = ledger.get(pl["def_ref"], 0) + (pl["qty"] if r[0] == "ITEM_CREATED" else -pl["qty"])
    have = {r[0]: r[1] for r in q("SELECT def_ref, SUM(qty) FROM items GROUP BY def_ref")}
    checks["W04"] = all(have.get(k, 0) == v for k, v in ledger.items()) and all(k in ledger for k in have)
    checks["W05"] = all(q1("SELECT 1 FROM anchors WHERE anchor_id=? AND place_id=?", (r[0], r[1])) for r in q("SELECT anchor_id, place_id FROM positions WHERE anchor_id IS NOT NULL"))
    checks["W06"] = all(jobj(r[0]) for r in q("SELECT props FROM places"))
    checks["W07"] = not q("SELECT 1 FROM traces WHERE (decays_at IS NOT NULL AND decays_at <= created_at) OR (locked=1 AND decays_at IS NOT NULL)")
    checks["W08"] = not q("SELECT 1 FROM portals WHERE is_open=1 AND barricade>0")
    if pc:
        pos = q1("SELECT place_id FROM positions WHERE body_id=?", (pc,))
        checks["W09"] = pos is not None and q1("SELECT 1 FROM known_places WHERE holder_id=? AND place_id=?", (pc, pos[0])) is not None
    else:
        checks["W09"] = True
    checks["W10"] = not q("SELECT 1 FROM groups WHERE next_due_at IS NOT NULL AND next_due_at < ?", (now[0] - 86_400_000,))
    ok = True
    for r in q("SELECT participants FROM operations"):
        ok = ok and all(x in bodies for x in json.loads(r[0]))
    checks["W11"] = ok
    places_ = {r[0] for r in q("SELECT place_id FROM places")}
    checks["W12"] = all(r[0] is None or r[0] in bodies or r[0] in places_ for r in q("SELECT target_id FROM infected_state"))
    ok = True
    for r in q("SELECT stores FROM settlements"):
        d = json.loads(r[0])
        ok = ok and all(isinstance(v, (int, float)) and v >= 0 for v in d.values())
    checks["W13"] = ok
    checks["W14"] = not any(any(n in (r[0] or "") for n in RETIRED_NAMES) for r in q("SELECT text FROM narration WHERE turn_index=?", (T,)))
    checks["W15"] = all(q1("SELECT 1 FROM claims WHERE claim_id=?", (r[0],)) or q1("SELECT 1 FROM propositions WHERE prop_id=?", (r[0],)) for r in q("SELECT superseded_by FROM claim_holdings WHERE superseded_by IS NOT NULL"))
    checks["W16"] = not q("SELECT 1 FROM events e WHERE cause_event_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events c WHERE c.event_id=e.cause_event_id)")
    # ---- entities
    if pc:
        a = q1("SELECT dossier_id FROM actors WHERE actor_id=?", (pc,))
        checks["E01"] = a is not None and q1("SELECT 1 FROM dossiers WHERE dossier_id=?", (a[0],)) is not None
        checks["E02"] = not q("SELECT 1 FROM dossier_deltas WHERE actor_id=? AND path LIKE 'identity.%'", (pc,))
        checks["E03"] = all(r[0] <= 1 for r in q("SELECT COUNT(*) FROM items WHERE holder_body=? AND holder_slot IN ('hand_l','hand_r') GROUP BY holder_slot", (pc,)))
        checks["E04"] = all(r[0] in bodies and r[1] in bodies for r in q("SELECT from_id, to_id FROM relationships WHERE from_id=? OR to_id=?", (pc, pc)))
    else:
        checks["E01"] = checks["E02"] = checks["E03"] = checks["E04"] = True
    checks["E05"] = all(q1("SELECT 1 FROM positions WHERE body_id=?", (r[0],)) for r in q("SELECT a.actor_id FROM actors a JOIN bodies b ON b.body_id=a.actor_id WHERE b.alive=1"))
    checks["E06"] = all(q1("SELECT 1 FROM dossiers WHERE dossier_id=?", (r[0],)) for r in q("SELECT dossier_id FROM actors"))
    checks["E07"] = all(r[0] == sha(r[1]) for r in q("SELECT content_hash, baseline_json FROM dossiers"))
    checks["E08"] = all(r[0] in bodies for r in q("SELECT body_id FROM wounds"))
    checks["E09"] = not q("SELECT 1 FROM items WHERE holder_body IS NOT NULL AND holder_slot IS NULL")
    ok = True
    for r in q("SELECT payload FROM events WHERE turn_index=? AND type='RELATION_CHANGE'", (T,)):
        ok = ok and abs(json.loads(r[0]).get("delta", 0)) <= 2
    checks["E10"] = ok
    if meta.get("cheat_active") != "1":
        texts = [r[0] or "" for r in q("SELECT text FROM narration WHERE turn_index=?", (T,))] + [r[0] or "" for r in q("SELECT text FROM story_log WHERE turn_index=?", (T,))]
        checks["E11"] = not any(any(c in t.lower() for c in CHEAT_STRINGS) for t in texts)
    else:
        checks["E11"] = True
    checks["E12"] = all(q1("SELECT 1 FROM groups WHERE group_id=?", (r[0],)) and r[1] in bodies for r in q("SELECT group_id, actor_id FROM group_members"))
    checks["E13"] = not any(any(x.lower() in (r[0] or "").lower() for x in EXHAUST_STRINGS) for r in q("SELECT baseline_json FROM dossiers"))
    checks["E14"] = not q("SELECT 1 FROM events WHERE turn_index=? AND length(payload) > 65536", (T,))
    checks["E15"] = all(r[0] == sha(r[1]) for r in q("SELECT hash, content FROM blobs"))
    checks["E16"] = not q("SELECT 1 FROM events WHERE origin='migration' AND type!='MIGRATION_BACKFILL'")
    # ---- global
    checks["G01"] = meta.get("schema_version") == str(SCHEMA_VERSION)
    checks["G02"] = all(k in meta for k in REQUIRED_META_KEYS)
    checks["G03"] = bool(meta.get("run_id"))
    checks["G04"] = not q("SELECT 1 FROM events WHERE at > ?", (now[0],))
    checks["G05"] = all(q1("SELECT 1 FROM commit_gate_log WHERE turn_index=?", (t,)) for t in range(1, T))
    checks["G06"] = not q("SELECT 1 FROM turn_ledger WHERE turn_index > ?", (T,))
    ok = True
    for r in q("SELECT type, payload FROM events WHERE type IN ('SPEECH','HARM','DEATH')"):
        p = json.loads(r[1])
        ok = ok and ((r[0] == "SPEECH" and bool(p.get("words"))) or (r[0] == "HARM" and bool(p.get("wound_id"))) or (r[0] == "DEATH" and bool(p.get("cause"))))
    checks["G07"] = ok
    types = {t.value for t in EventType}
    checks["G08"] = all(r[0] in types and r[1] in MODULES for r in q("SELECT type, writer FROM events"))
    ok = True
    for r in q("SELECT state_delta FROM events"):
        try:
            ok = ok and isinstance(json.loads(r[0]), list)
        except Exception:
            ok = False
    checks["G09"] = ok
    checks["G10"] = not q("SELECT 1 FROM turn_ledger WHERE turn_index=? AND run_count > 3", (T,))
    seqs = [r[0] for r in q("SELECT seq FROM prng_ledger ORDER BY seq")]
    checks["G11"] = seqs == list(range(1, len(seqs) + 1))
    seqs = [r[0] for r in q("SELECT seq FROM events ORDER BY seq")]
    checks["G12"] = seqs == list(range(1, len(seqs) + 1))
    checks["G13"] = all(q1("SELECT 1 FROM blobs WHERE hash=?", (r[0],)) for r in q("SELECT output_ref FROM turn_ledger WHERE output_ref IS NOT NULL"))
    checks["G14"] = all(re.fullmatch(r"[0-9a-f]{64}", r[0] or "") for r in q("SELECT request_hash FROM lm_calls"))
    bits = {b.id: ("1" if checks[b.id] else "0") for b in ALL_BITS}
    res = GateResult("".join(bits[b.id] for b in SESSION_BITS), "".join(bits[b.id] for b in WORLD_BITS),
                     "".join(bits[b.id] for b in ENTITY_BITS), "".join(bits[b.id] for b in GLOBAL_BITS),
                     [b.id for b in ALL_BITS if bits[b.id] == "0"])
    return res
