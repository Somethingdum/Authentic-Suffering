"""Actions fail, and the failure is the story (P7 pivot "Actions fail"). Rules RESOLVE-01..06,
EFF-02, NARR-02, L2, L12 (turn/pipeline.py stage 8, narration/narrator.py outcome lines).

Owen tries to climb a 250 cm fence (obstacle class 5): the check is rolled by code at the landing,
committed as CHECK_RESOLVED before anything changes, and the failure — not a softened success —
is what the narrator is given to tell. The neighbour who watched sees a man try the fence.
"""

from __future__ import annotations

import json

import pytest

from as_engine.contracts.common import CallClass
from slice_kit import events, pick, play

pytestmark = pytest.mark.phase(7)


def test_a_failed_climb_is_committed_and_narrated(scenario, fake):
    w = scenario("fence_climb")
    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "climb_obstacle", target="high_fence"), "none_reason": None,
                                            "manner": "", "remainder": None, "clarify": None})
    s = w.session()
    out = play(s, "do", "I climb over the fence.")
    assert out.ok
    (chk,) = events(w, "CHECK_RESOLVED", 1)
    assert chk["actor_id"] == w.id("pc") and chk["payload"]["def_id"] == "climb_obstacle"
    assert chk["payload"]["resistance"] == 5, "250 cm: obstacle class 5"
    assert chk["payload"]["band"] in ("fail", "break")
    (done,) = [e for e in events(w, "ACTION_COMPLETE", 1) if e["actor_id"] == w.id("pc")]
    assert done["payload"]["result"] in ("no_progress", "fell") and done["seq"] > chk["seq"]
    pos = dict(w.store.query_one("SELECT * FROM positions WHERE body_id = ?", (w.id("pc"),)))
    assert pos["place_id"] == w.id("yard"), "he did not get over"
    (req,) = fake.calls(CallClass.NARRATION)
    outcome = [l.text for l in req.context.lines if l.kind == "outcome"]
    assert outcome[0] == "Owen chose to climb over the high chain-link fence."
    band_text = {"fail": "It doesn't work.", "break": "It goes badly wrong."}[chk["payload"]["band"]]
    result_text = {"no_progress": "No progress.", "fell": "Owen falls."}[done["payload"]["result"]]
    assert band_text in outcome and result_text in outcome
    assert band_text in out.narration and result_text in out.narration
    if done["payload"]["result"] == "fell":
        assert [l.kind for l in req.context.lines].count("touch") == 1, "he feels the fall"
    seen = [json.loads(r[0]) for r in w.store.query(
        "SELECT detail FROM percept_log WHERE holder_id = ? AND turn_index = 1 AND source_id = ? AND event_id NOT LIKE 'scene:%'",
        (w.id("ada"), w.id("pc")))]
    assert seen, "Ada watched him try"
