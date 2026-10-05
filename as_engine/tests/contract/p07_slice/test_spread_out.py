"""Spread out (D-231). turn/pipeline.py S4: minds due only because they are restless.

After D-229 a room that took stock together took stock together again — twelve Clerk calls in one turn in three,
about forty seconds on one lane, and none in between. Now of the minds whose only reason to think is that it has been
a while (and that have thought before), a third take stock in a wave, by actor id; the rest stay restless and come up
in the next. Someone who has never thought with a model still thinks at once.
"""

from __future__ import annotations

import math

import pytest
from slice_kit import ledger, play, script_night_at_delgados

from as_engine.turn import select

pytestmark = pytest.mark.phase(7)


def test_a_room_that_took_stock_together(scenario, fake, monkeypatch):
    w = scenario("metal_fence")
    script_night_at_delgados(w, fake)
    s = w.session()
    assert play(s, "do", "I watch the front window and keep quiet.").ok
    thought = {r[0] for r in w.store.query("SELECT DISTINCT actor_id FROM lm_calls WHERE call_class IN ('actor_cognition', "
                                           "'actor_reaction') AND status = 'ok'")}
    monkeypatch.setattr(select, "salience_flags", lambda tx, a, minds, pc, T, at: {"restless": True})
    assert play(s, "do", "I keep watching the front window.").ok
    w0 = ledger(w, 2, 4)["detail"]["waves"][0]
    due = sorted(a for a in w0["salience"] if a not in w0["mandatory"] and a in thought)
    assert len(due) >= 3, "enough of them to spread"
    kept = [a for a in due if w0["salience"][a] > 0]
    assert kept == due[:math.ceil(len(due) / w.store.rules.scheduler.rethink_turns)], (kept, due)
    never = [a for a in w0["salience"] if a not in thought and a not in w0["mandatory"]]
    assert all(w0["salience"][a] > 0 for a in never), "one who never thought with a model thinks now"
