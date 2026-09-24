"""Soak (P7 gate): fifty turns of "Night at Delgado's" with the fake model, then a re-simulation of
every committed turn. Rules DET-02, DET-03, GATE-00, GATE-12, TIME-01, RUN-02 (turn/pipeline.py,
service/replay.py, lanes/calllog.py ReplayTransport).

Nothing here is scripted except the player's words: every mind answers with the fake's default
policy from its own packet, and the player's text goes through INTAKE like any other input (an
input the fake cannot map is rejected cleanly and changes nothing). The soak proves the machine
holds for fifty turns — every committed turn passes all 58 gate bits, time only moves forward,
nothing rolls back — and that a run can be re-simulated from its turn-0 snapshot with the
recorded model answers, reproducing full_state_hash after every turn (DET-02).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from as_engine.contracts.protocol import InTurnSubmit
from as_engine.contracts.settings import EngineConfig
from as_engine.service import replay, runs
from as_engine.turn.pipeline import run_turn

pytestmark = [pytest.mark.phase(7), pytest.mark.slow, pytest.mark.timeout(1200)]

TESTS = Path(__file__).resolve().parents[1]
SCENARIOS = TESTS / "fixtures" / "scenarios"
PACKS = TESTS / "fixtures" / "packs"
CORE = TESTS.parent.parent / "as_content" / "packs" / "core"

TURNS = 50
# One cycle of ten inputs. Only the first is condition-ended (a watch can run to the next due thing,
# at most 8 hours), so fifty turns stay well inside the time people last without water.
CYCLE = (
    ("do", "I watch the front door."),
    ("say", "Mara, anything out back?", "Mara"),
    ("do", "I walk behind the counter."),
    ("do", "I take the fire axe into my hand."),
    ("say", "Keep it down, everyone."),
    ("do", "I put the Glock away."),
    ("do", "I hide at the counter."),
    ("do", "I sneak quietly behind the counter."),
    ("say", "June, you all right back there?", "June"),
    ("do", "I go and look toward the storeroom doorway."),
)


def addressee_refs(s, name):
    """The view ref of the person the PC knows by ``name``, when the PC can see them now (as the UI would send it)."""
    from as_engine.service.view import build_view
    with s.store.transaction() as tx:
        v = build_view(tx, s)
    refs = s.extras["view_refs"]
    return [p.ref for p in v.location.people if p.label == name and refs[p.ref]]


CLEAN_REJECTIONS = {"unclear", "impossible", "not_here", "not_holding", "not_trained", "not_an_action", "intake_failed"}


def test_fifty_turns_hold_then_replay(tmp_path, fake):
    cfg = EngineConfig(runs_dir=str(tmp_path / "runs"))
    s = runs.create_run_from_scenario(cfg, SCENARIOS / "metal_fence.yaml", fake, packs_root=PACKS, core_pack_dir=CORE)
    rid = s.run_id
    committed = 0
    last_now = s.store.query_one("SELECT now_ms FROM world_clock")[0]
    for i in range(TURNS):
        mode, text, *to = CYCLE[i % len(CYCLE)]
        refs = addressee_refs(s, to[0]) if to else []
        out = asyncio.run(run_turn(s, InTurnSubmit(mode=mode, text=text, addressee_refs=refs)))
        now, turn = s.store.query_one("SELECT now_ms, turn_index FROM world_clock")
        if out.ok:
            committed += 1
            assert out.turn_index == turn == committed
            assert now > last_now, "TIME-01/TIME-03: a committed turn always moves the clock forward"
            g = dict(s.store.query_one("SELECT passed, failures FROM commit_gate_log WHERE turn_index = ?", (turn,)))
            assert g["passed"] == 1, f"turn {turn}: gate bits {g['failures']}"
            assert s.store.query_one("SELECT text FROM narration WHERE turn_index = ?", (turn,)) is not None
        else:
            assert out.rejected_code in CLEAN_REJECTIONS, f"input {i} ({text!r}): {out.rejected_code} {out.rejected_message}"
            assert (now, turn) == (last_now, committed), "a rejected input changes nothing"
        last_now = now
    assert committed >= TURNS * 0.6, "most of the inputs must map to something the PC can do"
    reactions = s.store.query_one("SELECT COUNT(*) FROM lm_calls WHERE call_class = 'actor_reaction'")[0]
    assert reactions >= 3, "speaking to someone by name gets a reaction wave: the soak must exercise waves"
    assert not s.store.query_one("SELECT 1 FROM error_repair_log WHERE kind = 'rollback'"), "no turn needed the rollback law"
    assert s.store.query_one("SELECT alive FROM bodies WHERE body_id = ?", (s.pc_id,))[0] == 1
    s.store.close()

    report = asyncio.run(replay.resimulate(cfg, rid))
    assert [r["turn_index"] for r in report] == list(range(1, committed + 1))
    bad = [r for r in report if not r["ok"]]
    assert not bad, "DET-02: re-simulation diverged: " + json.dumps(bad[:2])
