"""No two minds alike (D-248). world/worldgen/people.py (life_texts, _fresh): contradictions, decision stacks, silences,
habit gestures and the things a person would never say, dealt like their lives (D-247).

The decision card every cognition call reads is mostly a person's way of weighing things — what pulls them both ways,
what comes first, when they go quiet, what they would never say. Five contradictions, six stacks and six silences
were shared out among a whole world: in one group of seventeen, fourteen people shared a contradiction with someone,
thirteen a list of what comes first, twenty-four a line they would never say. Now nobody in a group shares any of
these while the tables have others (they grew: eight contradictions, six stacks, six silences).
"""

from __future__ import annotations

import asyncio
import collections

import pytest

from as_engine.contracts.settings import EngineConfig, RunSettings
from as_engine.mind.actor import fused
from as_engine.testing.fake_lm import FakeTransport
from as_engine.world.worldgen import people

pytestmark = pytest.mark.phase(10)


def test_one_camp_many_minds(tmp_path):
    from as_engine.service import runs
    from conftest import REPO_PACKS
    cfg = EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(REPO_PACKS))
    s = asyncio.run(runs.create_run(cfg, "core:pc/owen_marsh", RunSettings(world_detail="standard", seed=7, era="established",
                                                                         difficulty="normal"), FakeTransport()))
    try:
        rows = s.store.query("SELECT a.actor_id, (SELECT m.group_id FROM group_members m WHERE m.actor_id = a.actor_id "
                             "ORDER BY m.group_id LIMIT 1) FROM actors a JOIN bodies b ON b.body_id = a.actor_id JOIN dossiers d "
                             "ON d.actor_id = a.actor_id WHERE b.kind = 'human' AND a.controller != 'human' AND d.source = 'generated'")
        shared = collections.Counter()
        for aid, group in rows:
            d = fused(s.store, aid)
            for c in d.contradictions:
                shared[(group, "contradiction", c.belief_a)] += 1
            shared[(group, "stack", tuple(d.decision_stack.layers))] += 1
            shared[(group, "silence", tuple(d.silence.goes_quiet_when))] += 1
            shared[(group, "gesture", d.appearance.habit_gesture)] += 1
            for x in d.voice.would_never_say:
                shared[(group, "never", x)] += 1
        assert len(rows) >= 12
        assert [k for k, n in shared.items() if n > 1] == []
    finally:
        s.store.close()


def test_two_traits_always_drawn():
    """Traits come two at a time: with every trait but one already given out where they live, both are still drawn."""
    base = dict(name="Pat Vale", age=35, sex="female", cohort="pre_fall_adult", occupation="watcher", skills={"firearms": 1},
                special={L: 5 for L in "SPECIAL"}, variant=99, settlement_name="Vale", group_name="the Vale")
    tags = [t[0] for t in people._TRAITS]
    d = people.skeleton_dossier(people.PersonSeed(**base, lives_taken=tuple(tags[1:])))
    assert len({t["tag"] for t in d["traits"]}) == 2
