"""A refusal persists into the next scene, across a save and a reload (P7 pivot). Rules WILL-04..09,
WILL-07, MEM-17, SCENE-01, RUN-05, L6, L7 (turn/cognition.py record_responses, mind/firewall.py).

A stranger asks Mara for her revolver. The ask reaches her as speech she hears; she decides for
herself (the fake answers from her own packet) and says no. The pipeline — not the model — reads
that as a refusal and records it. The stranger leaves, the game is saved and reloaded, he comes
back and asks again: Mara's packet reminds her she already refused him, and the second ask is the
same refusal asked once more.
"""

from __future__ import annotations

import json

import pytest

from as_engine.contracts.common import CallClass
from as_engine.service.view import build_view
from slice_kit import cognition, events, pick, play

pytestmark = pytest.mark.phase(7)


def person_ref(w, s, local):
    with s.store.transaction() as tx:
        v = build_view(tx, s)
    refs = s.extras["view_refs"]
    return next(p.ref for p in v.location.people if refs[p.ref] == w.id(local))


def test_refusal_reloads_after_scene_change(scenario, fake, tmp_path):
    from as_engine.contracts.settings import EngineConfig
    from as_engine.service import runs
    from pathlib import Path
    tests = Path(__file__).resolve().parents[2]
    cfg = EngineConfig(runs_dir=str(tmp_path / "runs"))
    w = scenario("request_firewall")          # for fixture-local ids only
    s = runs.create_run_from_scenario(cfg, tests / "fixtures" / "scenarios" / "request_firewall.yaml", fake,
                                      packs_root=tests / "fixtures" / "packs", core_pack_dir=tests.parent.parent / "as_content" / "packs" / "core")
    mara, pc = w.id("mara"), w.id("pc")
    refuse = cognition(lambda r: pick(w, r, "observe_area"), speech="No.", to=("everyone",), goal="keep an eye on him",
                       reason="I don't hand my gun to a stranger.")
    fake.script(CallClass.ACTOR_REACTION, actor_id=mara, response=refuse, times=2)
    assert play(s, "do", "I watch.").ok                                                  # turn 1: he looks around
    out = play(s, "say", "Hand me the revolver.", addressee_refs=[person_ref(w, s, "mara")])  # turn 2: he asks
    assert out.ok
    (ask,) = [e for e in events(s, "SPEECH", 2) if e["actor_id"] == pc]
    assert ask["payload"]["to"] == [mara] and ask["payload"]["words"] == "Hand me the revolver."
    (ref_ev,) = events(s, "REFUSAL", 2)
    assert ref_ev["actor_id"] == mara and ref_ev["cause_event_id"] == ask["event_id"]
    assert ref_ev["payload"]["signature"] == f"give_item:{pc}" and ref_ev["payload"]["times_asked"] == 1
    assert ref_ev["payload"]["summary"] == "hand me the revolver"
    assert ref_ev["payload"]["reason_code"] == "distrust", "no relationship with a stranger: distrust"
    assert ref_ev["payload"]["cost_cited"] == "I don't hand my gun to a stranger."
    responses = json.loads(s.store.query_one("SELECT detail FROM turn_ledger WHERE turn_index = 2 AND stage = 8")[0])["responses"]
    assert [mara, ask["event_id"], "refusal"] in responses

    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "move_through_portal", target="front_door"), "none_reason": None,
                                            "manner": "", "remainder": None, "clarify": None})
    assert play(s, "do", "I step out onto the porch.").ok                                 # turn 3: he leaves
    (ended,) = events(s, "SCENE_END", 3)
    assert ended["payload"]["reason"] == "left"
    rid = s.run_id
    runs.save_run(s, "porch")
    s.store.close()
    s = runs.load_run(cfg, rid, fake)                                                   # the game is reloaded

    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "leave_place"), "none_reason": None,
                                            "manner": "", "remainder": None, "clarify": None})
    assert play(s, "do", "I go back inside.").ok                                         # turn 4: a new scene
    assert len(events(s, "SCENE_START")) == 3
    out = play(s, "say", "Hand me the revolver.", addressee_refs=[person_ref(w, s, "mara")])  # turn 5: he asks again
    assert out.ok
    (req,) = [r for r in fake.calls(CallClass.ACTOR_REACTION, actor_id=mara) if r.turn_index == 5]
    assert "You refused: hand me the revolver." in req.context.refusals, "MEM-17: the one who asked is here"
    (again,) = events(s, "REFUSAL", 5)
    assert again["payload"]["repeat"] is True and again["payload"]["times_asked"] == 2
    assert again["payload"]["refusal_id"] == ref_ev["payload"]["refusal_id"]
    s.store.close()
