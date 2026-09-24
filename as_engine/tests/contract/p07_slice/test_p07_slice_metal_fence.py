"""The slice: one whole turn of "Night at Delgado's" (P7). Rules GATE-00..19, L1, L2, L5, L8, L9,
SKULL-01, TIME-02, REACT-01, CAS-014, MEM-01..08, NARR-01..06, DISC-01, SEL-01..06, HOR-01..04.
docs/as/04_TURN_PIPELINE.md §7 is the trace this module walks; docs/as/13_BUILD_ORDER.md §5.7
lists the pivot items it proves.

The player typed "I watch the front window and keep quiet." The gust timer is due at t0, so a
98 dB crash at the fence sheet is the first thing that happens. Everybody hears it their own way;
Mara (standing order: loud_noise) must think; Nita sees the man behind the fence run and reacts in
a second wave; June's count pauses; the PC hears the crash, Mara's "Quiet." and June's shout —
and never learns about the man, or Nita, or the dumpster.
"""

from __future__ import annotations

import json

import pytest

from as_engine.contracts.common import CallClass
from slice_kit import events, ledger

pytestmark = pytest.mark.phase(7)

COGNITION = (CallClass.ACTOR_COGNITION, CallClass.ACTOR_REACTION)


def percepts(w, local, turn=1):
    return [dict(r, detail=json.loads(r["detail"])) for r in w.store.query(
        "SELECT * FROM percept_log WHERE holder_id = ? AND turn_index = ? ORDER BY at, percept_id", (w.id(local), turn))]


def test_the_turn_commits_through_every_gate(metal_turn):
    """GATE-00..19: one transaction for 0-12 with all 58 bits, then 13-19; the clock ends at the horizon."""
    m = metal_turn
    w = m.w
    assert m.out.ok and m.out.turn_index == 1 and m.out.rejected_code is None
    stages = {r["stage"]: r["status"] for r in w.store.query("SELECT stage, status FROM turn_ledger WHERE turn_index = 1")}
    assert sorted(stages) == list(range(20))
    assert stages[19] == "skipped", "an in-memory session has no run folder to autosave into"
    assert all(stages[i] == "ok" for i in range(19))
    g = dict(w.store.query_one("SELECT * FROM commit_gate_log WHERE turn_index = 1"))
    assert g["passed"] == 1 and json.loads(g["failures"]) == []
    assert (g["session_bits"], g["world_bits"], g["entities_bits"], g["global_bits"]) == ("1" * 12, "1" * 16, "1" * 16, "1" * 14)
    clock = dict(w.store.query_one("SELECT now_ms, turn_index FROM world_clock"))
    assert clock["turn_index"] == 1
    assert clock["now_ms"] == m.t0 + 3000, "HOR-03: the crash is material to the PC at t0, so the window closes 3 s later"


def test_stage_zero_fires_the_gust_before_anything_else(metal_turn):
    """TIME-06 / 04 §7 stage 0: the timer due at t0 fires first; the PC's input is recorded after it."""
    w = metal_turn.w
    first = [dict(r) for r in w.store.query("SELECT type, at FROM events WHERE turn_index = 1 ORDER BY seq LIMIT 3")]
    assert [f["type"] for f in first] == ["CLOCK_ADVANCE", "TIMER_FIRED", "NOISE"]
    (noise,) = [e for e in events(w, "NOISE", 1) if e["actor_id"] is None]
    assert noise["payload"]["source_db"] == 98 and noise["at"] == metal_turn.t0
    (inp,) = events(w, "PLAYER_INPUT", 1)
    assert inp["seq"] > noise["seq"]
    row = dict(w.store.query_one("SELECT * FROM player_inputs WHERE turn_index = 1"))
    assert row["mode"] == "do" and row["raw_text"] == "I watch the front window and keep quiet."
    import hashlib
    assert row["received_hash"] == hashlib.sha256(row["raw_text"].encode("utf-8")).hexdigest(), "S03"


def test_the_pc_does_what_the_player_asked_and_nothing_more(metal_turn):
    """L12 / G1: the PC's intent is its own affordance, resolved like everyone's; no movement invented."""
    w = metal_turn.w
    pc_starts = [e for e in events(w, "ACTION_START", 1) if e["actor_id"] == w.id("pc")]
    assert [e["payload"]["def_id"] for e in pc_starts] == ["observe_area"]
    assert not [e for e in events(w, "MOVE", 1) if e["actor_id"] == w.id("pc")]
    assert not [r for r in metal_turn.fake.calls() if r.call_class in COGNITION and r.actor_id == w.id("pc")], \
        "the PC never gets a cognition call: the player decides"


def test_mara_must_think_and_june_pauses_her_count(metal_turn):
    """SEL-02 (a standing order's trigger makes a mind mandatory), CAS-014 (starting something else pauses a task)."""
    w = metal_turn.w
    waves = ledger(w, 1, 4)["detail"]["waves"]
    w0 = waves[0]
    assert w0["wave"] == 0 and w.id("mara") in w0["mandatory"] and w0["lod"][w.id("mara")] == "hot"
    assert w.id("pc") not in w0["lod"], "the PC is never a cognition candidate"
    assert set(w0["lod"]) == {w.id(x) for x in ("mara", "alice", "june", "eli", "nita", "stranger")}, \
        "the loud crash brings the alley's neighbour (the lot) into the active area"
    (step,) = [e for e in events(w, "TASK_STEP", 1) if e["actor_id"] == w.id("june")]
    assert step["payload"]["status"] == "paused" and step["payload"]["steps_done"] == 41 and step["rule_cited"] == "CAS-014"


def test_nita_reacts_in_a_second_wave_and_holds(metal_turn):
    """REACT-01 / TIME-02: a stranger running within 20 m is material to Nita; she reacts after her
    reaction time and, choosing to keep hiding, carries on (no second start)."""
    w = metal_turn.w
    waves = ledger(w, 1, 4)["detail"]["waves"]
    assert len(waves) == 2 and list(waves[1]["lod"]) == [w.id("nita")]
    (move,) = [e for e in events(w, "MOVE", 1) if e["actor_id"] == w.id("stranger")]
    lo, hi = w.store.rules.acoustics.reaction_window_ms
    assert move["at"] + lo <= waves[1]["at"] <= move["at"] + hi
    nita_starts = [e for e in events(w, "ACTION_START", 1) if e["actor_id"] == w.id("nita")]
    assert [e["payload"]["def_id"] for e in nita_starts] == ["hide"], "same choice again: the hide carries on"
    assert [c.actor_id for c in metal_turn.fake.calls(CallClass.ACTOR_REACTION)] == [w.id("nita")]


def test_packets_contain_only_own_percepts(metal_turn):
    """SKULL-01 / L1 (pivot): every line a mind was shown is one of its own percept rows, word for word."""
    w = metal_turn.w
    calls = [r for r in metal_turn.fake.calls() if r.call_class in COGNITION]
    assert len(calls) >= 6
    for req in calls:
        p = req.context
        mine = {r["percept_id"]: r for r in (dict(x) for x in w.store.query(
            "SELECT * FROM percept_log WHERE holder_id = ?", (p.actor_id,)))}
        for item in p.perceived_now:
            pid = p.handles[item.handle]
            assert pid in mine and mine[pid]["text"] == item.text, f"{w.local(p.actor_id)} was shown {item.text!r}"
        for u in p.utterances:
            assert p.handles[u.handle] in mine
        text = " ".join(i.text for i in p.perceived_now)
        if p.actor_id != w.id("nita") and p.actor_id != w.id("stranger"):
            assert "thin man" not in text and "tall weeds" not in text, f"{w.local(p.actor_id)} saw what only Nita saw"


def test_divergent_intents_from_divergent_percepts(metal_turn):
    """Pivot: the same crash reaches each mind differently, and they choose differently."""
    w = metal_turn.w
    crash = {x: next(r["text"] for r in percepts(w, x) if r["text"].startswith("A loud metal crash"))
             for x in ("pc", "nita", "stranger")}
    assert crash["pc"] == "A loud metal crash came from the rear alley."
    assert crash["nita"] == "A loud metal crash came from the loose metal sheet on the fence."
    assert crash["stranger"] == "A loud metal crash came from the other side of the chain-link fence."
    june_heard = [r for r in percepts(w, "june") if r["channel"] == "speech"]
    assert [(r["fidelity"], r["detail"]["words"]) for r in june_heard] == [("tone_only", "")], "Mara's 'Quiet.' is a voice to June"
    offered = {req.actor_id: {req.context.handles[a.handle].split(":")[0] for a in req.context.affordances}
               for req in metal_turn.fake.calls(CallClass.ACTOR_COGNITION)}
    assert not {d for d in offered[w.id("june")] if d.startswith("shoot")}, "June has no firearm training and no gun"
    chose = {e["actor_id"]: e["payload"]["def_id"] for e in events(w, "ACTION_START", 1)}
    assert len({chose[w.id(x)] for x in ("mara", "june", "alice", "nita", "stranger")}) == 5


def test_partial_overhear_makes_partial_belief(metal_turn):
    """Pivot: Nita half-hears June; the guess she builds on it is only as good as what she heard."""
    w = metal_turn.w
    (heard,) = [r for r in percepts(w, "nita") if r["channel"] == "speech"]
    assert heard["fidelity"] == "partial" and heard["detail"]["words"] == "What … that?"
    rows = [dict(r) for r in w.store.query(
        "SELECT h.*, p.text FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id "
        "WHERE h.holder_id = ? AND h.provenance = 'inferred'", (w.id("nita"),))]
    (b,) = rows
    assert b["text"] == "The thin man ran because June shouted."
    assert (b["fidelity"], b["confidence"], b["believed"]) == ("partial", 2, 1), "MEM-05: never surer than seeing it"
    for other in ("pc", "mara", "alice", "june"):
        assert not w.store.query_one("SELECT 1 FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id "
                                     "WHERE h.holder_id = ? AND p.text LIKE '%thin man%'", (w.id(other),))


def test_four_memories_one_absent(metal_turn):
    """Pivot / MEM-01, MEM-09: each of the crew remembers the crash from its own percepts; nobody but
    Nita remembers the man running."""
    w = metal_turn.w
    ep = {w.local(r["holder_id"]): dict(r, percept_ids=json.loads(r["percept_ids"])) for r in
          w.store.query("SELECT * FROM episodes WHERE turn_index = 1")}
    for x in ("mara", "june", "alice", "nita"):
        own = {r["percept_id"] for r in percepts(w, x)}
        assert ep[x]["percept_ids"] and set(ep[x]["percept_ids"]) <= own
    assert ep["nita"]["summary"] == "Someone was watching the back and ran when June shouted."
    (move,) = [e for e in events(w, "MOVE", 1) if e["actor_id"] == w.id("stranger")]
    saw_run = {w.local(r[0]) for r in w.store.query("SELECT holder_id FROM percept_log WHERE event_id = ?", (move["event_id"],))}
    assert saw_run == {"nita"}
    for x, e in ep.items():
        if x != "nita":
            assert "ran" not in e["summary"] and "thin man" not in e["summary"]


def test_narration_withholds_alley(metal_turn):
    """Pivot / L9, DISC-01: the narrator is told only what the PC perceived; the prose names nobody
    the PC did not perceive and quotes only what the PC heard."""
    w = metal_turn.w
    (req,) = [r for r in metal_turn.fake.calls(CallClass.NARRATION)]
    k = req.context
    lines = " ".join(l.text for l in k.lines) + " " + " ".join(k.people_present)
    for secret in ("thin man", "tall weeds", "dumpster", "Nita", "figure runs"):
        assert secret not in lines
    assert "Nita" not in k.allowed_names
    speech = [(l.speaker, l.words) for l in k.lines if l.kind == "speech"]
    assert speech == [("Mara", "Quiet."), ("June", "What was that?")]
    row = dict(w.store.query_one("SELECT * FROM narration WHERE turn_index = 1"))
    assert row["lint_passed"] == 1 and row["text"] == metal_turn.out.narration
    for secret in ("thin man", "Nita", "dumpster", "weeds"):
        assert secret not in row["text"]
    story = [(r[0], r[1]) for r in w.store.query("SELECT kind, text FROM story_log WHERE turn_index = 1 ORDER BY entry_id")]
    assert story == [("player", "I watch the front window and keep quiet."), ("narration", row["text"])]
