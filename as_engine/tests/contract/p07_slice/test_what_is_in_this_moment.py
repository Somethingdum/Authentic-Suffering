"""What is in this moment (D-273). turn/pipeline.py S14 (the WRITEBACK request's cue words).

Every memory call carried the whole cue registry — seventy-odd words ("knows_lurker_mimicry, ration_cut, shift_change,
…") — as the words a lesson may be tagged with, whatever had happened. A lesson drawn from this moment names what is
in it: the cue words present for the person now. (The lesson is still checked against the whole registry, and the
quiet hours' reflection still sees it all, D-234.)
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import CallClass
from slice_kit import play, script_night_at_delgados

pytestmark = pytest.mark.phase(7)


def cue_line(req):
    user = req.messages[-1].content
    lines = [ln for ln in user.splitlines() if ln.startswith("Cue words you may use for a lesson: ")]
    return lines[0].split(": ", 1)[1].split(", ") if lines else []


def test_the_crash_and_not_the_registry(scenario, fake):
    w = scenario("metal_fence")
    script_night_at_delgados(w, fake)
    assert play(w.session(), "do", "I watch the front window and keep quiet.").ok
    reqs = {r.actor_id: r for r in fake.calls(CallClass.WRITEBACK)}
    registry = {r.rsplit("/", 1)[1] for r in w.canon.refs("cue")}
    mara = cue_line(reqs[w.id("mara")])
    assert "metal_crash" in mara, mara
    assert set(mara) <= registry and len(mara) < len(registry) // 4, mara
    assert "knows_lurker_mimicry" not in mara and "ration_cut" not in mara
