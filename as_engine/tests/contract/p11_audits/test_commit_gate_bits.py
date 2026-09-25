"""Every commit-gate bit is a real check (P11). Rules AUDIT-01, AUDIT-02, AUDIT-03, L13
(audit/commit_gate.py compute, BIT_STAGE; turn/pipeline.py G12).

The night at Delgado's, two turns played. The world as it stands passes all 58 bits. Then each
fault below is injected on its own — straight into the database, the way a bug would leave it —
and exactly its bit drops (AUDIT-02: a bit that never drops is not a check; a fault that drops
two bits means one of them is looking at the wrong thing).
"""

from __future__ import annotations

import hashlib

import pytest

from as_engine.audit.commit_gate import ALL_BITS, BIT_STAGE, compute
from as_engine.contracts.events import Event, EventType
from slice_kit import play, script_night_at_delgados

pytestmark = pytest.mark.phase(11)

T = 2


@pytest.fixture
def night(scenario, fake):
    w = scenario("metal_fence")
    script_night_at_delgados(w, fake)
    s = w.session()
    play(s, "do", "I watch the front window and keep quiet.")
    play(s, "do", "I keep watching the front window.")
    assert w.store.query_one("SELECT turn_index FROM world_clock")[0] == T
    return w


def sql(w, statement, args=()):
    """A write the engine would never make: straight into the file, foreign keys off."""
    c = w.store.conn
    c.execute("PRAGMA foreign_keys=OFF")
    c.execute(statement, args)
    c.execute("PRAGMA foreign_keys=ON")


def one(w, statement, args=()):
    return w.store.query_one(statement, args)


def now(w):
    return one(w, "SELECT now_ms FROM world_clock")[0]


def pc(w):
    return one(w, "SELECT value FROM meta WHERE key = 'pc_actor_id'")[0]


def event(w, **kw):
    """An event committed the ordinary way (the store keeps seq and ids straight)."""
    base = dict(at=now(w), turn_index=T)
    base.update(kw)
    with w.store.transaction() as tx:
        return tx.commit_event(Event(**base))


def raw_event(w, seq_gap=1, **cols):
    """An events row written behind the store's back."""
    seq = one(w, "SELECT MAX(seq) FROM events")[0] + seq_gap
    row = {"event_id": f"evt_9{seq:05d}", "seq": seq, "at": now(w), "type": "NOISE", "writer": "action.propagate",
           "actor_id": None, "target_ids": "[]", "place_id": None, "cause_event_id": None, "payload": "{}",
           "state_delta": "[]", "rule_cited": None, "turn_index": T, "origin": "sim", "links": "[]"}
    row.update(cols)
    sql(w, f"INSERT INTO events ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})", tuple(row.values()))


def someone(w, local="june"):
    return w.id(local)


def an_item(w, where):
    return one(w, f"SELECT item_id FROM items WHERE {where} ORDER BY item_id LIMIT 1")[0]


FAULTS = {
    # ---- session
    "S01": lambda w: sql(w, "DELETE FROM turn_ledger WHERE turn_index = ? AND stage = 5", (T,)),
    "S02": lambda w: sql(w, "UPDATE turn_ledger SET status = 'failed' WHERE turn_index = ? AND stage = 3", (T,)),
    "S03": lambda w: sql(w, "UPDATE player_inputs SET received_hash = ? WHERE turn_index = ?", ("0" * 64, T)),
    "S04": lambda w: sql(w, "INSERT INTO episodes (episode_id, holder_id, at, turn_index, place_id, summary, salience) "
                            "VALUES ('epi_999999', ?, ?, ?, NULL, 'TODO: write what she remembers', 10)",
                         (someone(w), now(w), T)),
    "S05": lambda w: event(w, type=EventType.SPEECH, writer="action.propagate", actor_id=someone(w, "mara"),
                           payload={"words": "As an AI I cannot say that.", "volume": "normal", "to": [], "source_db": 60}),
    "S06": lambda w: sql(w, "UPDATE world_clock SET turn_index = turn_index + 1"),
    "S07": lambda w: sql(w, "UPDATE narrator_state SET style_json = 'not a style' WHERE id = 1"),
    "S08": lambda w: sql(w, "INSERT INTO event_queue (queue_id, due_at, type, status) VALUES ('que_999999', ?, 'NOISE', 'pending')",
                         (now(w) - 1,)),
    "S09": lambda w: sql(w, "INSERT INTO open_loops (loop_id, holder_id, kind, subject_ids, text, strength, created_event, "
                            "created_at, status) VALUES ('olp_999999', ?, 'vendetta', '[]', 'Settle it', 2, 'evt_000001', ?, 'open')",
                         (someone(w), now(w))),
    "S10": lambda w: sql(w, "INSERT INTO tasks (task_id, actor_id, kind, label, steps_total, step_s, started_at, next_due_at, status) "
                            "VALUES ('tsk_999999', ?, 'work', 'mend the fence', 3, 60, ?, NULL, 'active')", (someone(w), now(w))),
    "S11": lambda w: sql(w, "INSERT INTO error_repair_log (entry_id, turn_index, at_ms, kind, stage) VALUES ('err_999999', ?, ?, 'oops', 4)",
                         (T, now(w))),
    "S12": lambda w: sql(w, "INSERT INTO pending_reactions (reaction_id, actor_id, intent, created_turn, status) "
                            "VALUES ('rct_999999', 'act_999999', '{}', ?, 'pending')", (T,)),
    # ---- world
    "W01": lambda w: sql(w, "UPDATE items SET holder_body = 'act_999999' WHERE item_id = ?",
                         (an_item(w, f"holder_body = '{someone(w, 'mara')}'"),)),
    "W02": lambda w: sql(w, "UPDATE items SET props = 'not json' WHERE item_id = ?", (an_item(w, "1 = 1"),)),
    "W03": lambda w: _overfill(w),
    "W04": lambda w: sql(w, "INSERT INTO items (item_id, def_ref, qty, place_id, props, origin) VALUES ('itm_999999', "
                            "'core:item/fire_axe', 1, ?, '{}', 'loot')", (w.id("alley"),)),
    "W05": lambda w: sql(w, "UPDATE positions SET anchor_id = ? WHERE body_id = ?", (w.id("fence_sheet"), someone(w, "eli"))),
    "W06": lambda w: sql(w, "UPDATE places SET props = 'x' WHERE place_id = ?", (w.id("office"),)),
    "W07": lambda w: sql(w, "INSERT INTO traces (trace_id, place_id, kind, text, source_event, created_at, decays_at, locked) "
                            "VALUES ('trc_999999', ?, 'blood', 'Blood on the step.', 'evt_000001', ?, ?, 0)",
                         (w.id("alley"), now(w), now(w))),
    "W08": lambda w: sql(w, "UPDATE portals SET is_open = 1, barricade = 1 WHERE portal_id = (SELECT MIN(portal_id) FROM portals "
                            "WHERE kind != 'wall')"),
    "W09": lambda w: sql(w, "DELETE FROM known_places WHERE holder_id = ? AND place_id = (SELECT place_id FROM positions "
                            "WHERE body_id = ?)", (pc(w), pc(w))),
    "W10": lambda w: sql(w, "INSERT INTO groups (group_id, kind, name, next_due_at) VALUES ('grp_999999', 'group', 'The lost', 0)"),
    "W11": lambda w: sql(w, "INSERT INTO operations (op_id, kind, participants) VALUES ('ops_999999', 'patrol', '[\"act_999999\"]')"),
    "W12": lambda w: sql(w, "INSERT INTO infected_state (body_id, type_id, target_id) VALUES (?, 'ZOMBIE_ARCHETYPE_SHAMBLER01', 'nowhere')",
                         (someone(w, "eli"),)),
    "W13": lambda w: sql(w, "INSERT INTO settlements (settlement_id, name, stores) VALUES ('stl_999999', 'Nowhere', '{\"food\": -3}')"),
    "W14": lambda w: sql(w, "UPDATE narration SET text = text || ' The PWOSS says so.' WHERE turn_index = ?", (T,)),
    "W15": lambda w: sql(w, "UPDATE claim_holdings SET superseded_by = 'prp_999999' WHERE rowid = (SELECT MIN(rowid) FROM claim_holdings)"),
    "W16": lambda w: raw_event(w, cause_event_id="evt_888888"),
    # ---- entities
    "E01": lambda w: sql(w, "DELETE FROM actors WHERE actor_id = ?", (pc(w),)),
    "E02": lambda w: sql(w, "INSERT INTO dossier_deltas (delta_id, actor_id, event_id, path, op, value_json, at) "
                            "VALUES ('ddl_999999', ?, 'evt_000001', 'identity.name', 'set', '\"Nobody\"', ?)", (pc(w), now(w))),
    "E03": lambda w: sql(w, "UPDATE items SET holder_body = ?, holder_slot = 'hand_r', container_id = NULL WHERE item_id = ?",
                         (pc(w), an_item(w, "def_ref = 'core:item/fire_axe'"))),
    "E04": lambda w: sql(w, "INSERT INTO relationships (from_id, to_id, updated_at) VALUES (?, 'act_999999', ?)", (pc(w), now(w))),
    "E05": lambda w: sql(w, "DELETE FROM positions WHERE body_id = ?", (someone(w, "eli"),)),
    "E06": lambda w: sql(w, "UPDATE actors SET dossier_id = 'dos_999999' WHERE actor_id = ?", (someone(w, "eli"),)),
    "E07": lambda w: sql(w, "UPDATE dossiers SET content_hash = ? WHERE dossier_id = (SELECT MIN(dossier_id) FROM dossiers)", ("0" * 64,)),
    "E08": lambda w: sql(w, "INSERT INTO wounds (wound_id, body_id, anatomy, type, severity, bleed_pct_per_min, pain, cause_event, created_at) "
                            "VALUES ('wnd_999999', 'act_999999', 'arm_l', 'cut', 'minor', 0.2, 1, 'evt_000001', ?)", (now(w),)),
    "E09": lambda w: sql(w, "UPDATE items SET holder_slot = NULL WHERE item_id = ?", (an_item(w, f"holder_body = '{someone(w, 'mara')}'"),)),
    "E10": lambda w: event(w, type=EventType.RELATION_CHANGE, writer="mind.mind", actor_id=someone(w),
                           payload={"from_id": someone(w), "to_id": someone(w, "mara"), "axis": "trust", "delta": 3}),
    "E11": lambda w: sql(w, "UPDATE narration SET text = text || ' Cheat code accepted.' WHERE turn_index = ?", (T,)),
    "E12": lambda w: sql(w, "INSERT INTO group_members (group_id, actor_id, role, since) VALUES ('grp_424242', ?, 'member', 0)",
                         (someone(w),)),
    "E13": lambda w: _poison_dossier(w),
    "E14": lambda w: event(w, type=EventType.NOISE, writer="action.propagate",
                           payload={"source_db": 30, "kind": "hum", "text": "h" * 70_000, "place_id": w.id("office")}),
    "E15": lambda w: sql(w, "INSERT INTO blobs (hash, content) VALUES ('abc', 'x')"),
    "E16": lambda w: event(w, type=EventType.NOISE, writer="action.propagate", origin="migration",
                           payload={"source_db": 30, "kind": "hum", "text": "a hum", "place_id": w.id("office")}),
    # ---- global
    "G01": lambda w: sql(w, "UPDATE meta SET value = '999' WHERE key = 'schema_version'"),
    "G02": lambda w: sql(w, "DELETE FROM meta WHERE key = 'world_epoch_text'"),
    "G03": lambda w: sql(w, "UPDATE meta SET value = '' WHERE key = 'run_id'"),
    "G04": lambda w: event(w, type=EventType.NOISE, writer="action.propagate", at=now(w) + 3_600_000,
                           payload={"source_db": 30, "kind": "hum", "text": "a hum", "place_id": w.id("office")}),
    "G05": lambda w: sql(w, "DELETE FROM commit_gate_log WHERE turn_index = 1"),
    "G06": lambda w: sql(w, "INSERT INTO turn_ledger (turn_index, stage, status) VALUES (?, 0, 'ok')", (T + 1,)),
    "G07": lambda w: event(w, type=EventType.HARM, writer="physical.bodies", actor_id=someone(w), payload={"body_id": someone(w)}),
    "G08": lambda w: event(w, type=EventType.NOISE, writer="somebody.else",
                           payload={"source_db": 30, "kind": "hum", "text": "a hum", "place_id": w.id("office")}),
    "G09": lambda w: raw_event(w, state_delta="not a list"),
    "G10": lambda w: sql(w, "UPDATE turn_ledger SET run_count = 4 WHERE turn_index = ? AND stage = 0", (T,)),
    "G11": lambda w: sql(w, "INSERT INTO prng_ledger (seq, turn_index, stream, purpose, n, value) VALUES "
                            "((SELECT COALESCE(MAX(seq), 0) + 2 FROM prng_ledger), ?, 'test', 'a gap', 1, 1)", (T,)),
    "G12": lambda w: raw_event(w, seq_gap=5),
    "G13": lambda w: sql(w, "UPDATE turn_ledger SET output_ref = 'deadbeef' WHERE turn_index = ? AND stage = 0", (T,)),
    "G14": lambda w: sql(w, "UPDATE lm_calls SET request_hash = 'xyz' WHERE seq = (SELECT MIN(seq) FROM lm_calls)"),
}


def _overfill(w):
    """Two axes in a shoulder bag that holds 10 bulk: both made the ordinary way, moved in behind the store's back."""
    from as_engine.physical import objects
    with w.store.transaction() as tx:
        floor = objects.Holder("place", w.id("office"))
        bag = objects.create(tx, "core:item/shoulder_bag", 1, floor, "loot", {}, now(w), None, T).payload["item_id"]
        axes = [objects.create(tx, "core:item/fire_axe", 1, floor, "loot", {}, now(w), None, T).payload["item_id"] for _ in range(2)]
    for a in axes:
        sql(w, "UPDATE items SET place_id = NULL, anchor_id = NULL, container_id = ? WHERE item_id = ?", (bag, a))


def _poison_dossier(w):
    """Exhaust text inside a dossier whose hash is kept honest (so only E13 can see it)."""
    did, js = one(w, "SELECT dossier_id, baseline_json FROM dossiers ORDER BY dossier_id LIMIT 1")
    bad = js.replace('"schema"', '"note": "lorem ipsum", "schema"', 1)
    sql(w, "UPDATE dossiers SET baseline_json = ?, content_hash = ? WHERE dossier_id = ?",
        (bad, hashlib.sha256(bad.encode("utf-8")).hexdigest(), did))


def test_every_bit_has_its_fault():
    assert sorted(FAULTS) == sorted(b.id for b in ALL_BITS)


def test_the_night_as_played_passes_every_bit(night):
    r = compute(night.store, T)
    assert r.failures == [] and r.passed


@pytest.mark.parametrize("bit", [b.id for b in ALL_BITS])
def test_each_fault_drops_exactly_its_bit(night, bit):
    """AUDIT-02."""
    FAULTS[bit](night)
    assert compute(night.store, T).failures == [bit]


def test_every_bit_names_the_stage_that_writes_what_it_checks():
    """AUDIT-03: BIT_STAGE says where a failure is repaired; the gate itself (12) is never the answer."""
    assert set(BIT_STAGE) == {b.id for b in ALL_BITS}
    assert all(0 <= s <= 11 or 13 <= s <= 19 for s in BIT_STAGE.values()), \
        {k: v for k, v in BIT_STAGE.items() if v == 12}
    assert (BIT_STAGE["S03"], BIT_STAGE["S05"], BIT_STAGE["W04"], BIT_STAGE["E10"], BIT_STAGE["W14"]) == (1, 6, 8, 10, 17)
