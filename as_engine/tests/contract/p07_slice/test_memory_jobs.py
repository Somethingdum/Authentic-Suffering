"""A failed summary is never a lost memory (P7, Actor v2 B5 — fidelity C10, Actor Spec §13). Rule
MEM-19 (turn/pipeline.py S13/S14; mind/memory.py queue_writeback, finish_writeback, unprocessed;
mind/packet.py 'unprocessed').

The anchor night at Delgado's, except that June's writeback times out. Her job is kept, failed;
at her next decision what she did and saw is still in front of her ("Still raw from before"); the
next turn tries her summary again and, when it works, the job is done and the raw lines go.
"""

from __future__ import annotations

import json

import pytest

from as_engine.contracts.common import LOD, CallClass
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet
from as_engine.prompts.render import render
from slice_kit import play, script_night_at_delgados

pytestmark = pytest.mark.phase(7)


def jobs(w, holder):
    return [dict(r) for r in w.store.query("SELECT * FROM memory_jobs WHERE holder_id = ? ORDER BY turn_index", (holder,))]


def test_a_timed_out_summary_is_kept_and_tried_again(scenario, fake):
    w = scenario("metal_fence")
    june = w.id("june")
    fake.fail(CallClass.WRITEBACK, "timeout", actor_id=june)          # before the anchor turn's scripts: June's first try times out
    script_night_at_delgados(w, fake)
    s = w.session()
    play(s, "do", "I watch the front window and keep quiet.")
    (j1,) = jobs(w, june)
    assert (j1["job_key"], j1["status"], j1["attempts"]) == (f"{june}:1", "failed", 1)
    assert w.store.query("SELECT 1 FROM episodes WHERE holder_id = ?", (june,)) == [], "nothing written for her yet"
    assert [r["status"] for r in jobs(w, w.id("mara"))] == ["done"]
    kinds = [json.loads(r[0]) for r in w.store.query("SELECT payload FROM events WHERE type = 'MEMORY_JOB' ORDER BY seq")]
    assert {(k["holder_id"], k["status"]) for k in kinds} >= {(june, "pending"), (june, "failed"), (w.id("mara"), "done")}

    at = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        aff = enumerate_affordances(tx, june, w.canon.all("affordance"), at, 1)
        pkt = build_packet(tx, june, LOD.HOT, aff, 1, at)
    assert any(ln.startswith("I chose to go and look toward the back door") for ln in pkt.unprocessed)
    user = render(CallClass.ACTOR_COGNITION, p=pkt)[1].content
    assert "Still raw from before" in user
    play(s, "do", "I keep watching the front window.")
    retried = [r for r in fake.calls(CallClass.WRITEBACK, actor_id=june)]
    assert len(retried) >= 2, "her turn-1 summary is asked for again"
    assert [(r["turn_index"], r["status"]) for r in jobs(w, june)][0] == (1, "done")
    assert w.store.query("SELECT 1 FROM episodes WHERE holder_id = ? AND summary LIKE 'Something crashed out back%'", (june,))
