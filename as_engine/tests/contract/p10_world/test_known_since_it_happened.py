"""Known since it happened (D-255). world/worldgen/people.py history as belief (acquired_at).

What a settlement's people say happened there — "They say the Diallo People took and held Crossroads." — reached every
one of their prompts as "(everyone says so, just now)": the holdings were dated to the moment the world was made, so
the oldest story in the place read as news, and with the recency bonus it came first of everything they believed.
"""

from __future__ import annotations

import asyncio

import pytest

from as_engine.contracts.common import LOD
from as_engine.contracts.settings import EngineConfig, RunSettings
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet
from as_engine.testing.fake_lm import FakeTransport

pytestmark = pytest.mark.phase(10)

DAY = 86_400_000


def test_the_old_stories_are_old(tmp_path):
    from as_engine.service import runs
    from conftest import REPO_PACKS
    cfg = EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(REPO_PACKS))
    s = asyncio.run(runs.create_run(cfg, "core:pc/owen_marsh", RunSettings(world_detail="gotta_go_to_work_soon", seed=11,
                                                                         era="established", difficulty="normal"), FakeTransport()))
    try:
        st = s.store
        rows = st.query("SELECT h.holder_id, h.acquired_at, e.day FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id "
                        "JOIN history_events e ON e.hist_id = p.subject_id WHERE p.predicate = 'history' ORDER BY h.holder_id")
        assert rows
        made = st.query_one("SELECT MIN(at) FROM events WHERE type = 'PERCEIVE' AND json_extract(payload, '$.seed') = 1")[0]
        for _holder, acquired, day in rows:
            assert acquired == min(made, max(0, day) * DAY + 12 * 3_600_000)
        holder = rows[0][0]
        t = st.query_one("SELECT now_ms FROM world_clock")[0]
        with st.transaction() as tx:
            pkt = build_packet(tx, holder, LOD.WARM, enumerate_affordances(tx, holder, tx.canon.all("affordance"), t, 0), 0, t)
        told = [b for b in pkt.beliefs if b.provenance_text == "everyone says so"]
        assert told and not [b for b in told if b.age_text == "just now"], [b.age_text for b in told]
    finally:
        s.store.close()
