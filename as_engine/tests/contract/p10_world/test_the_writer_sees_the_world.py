"""The Writer sees what it is asked to write (D-131). world/worldgen/history.py WG-20 (WORLDGEN_HISTORY),
people.py WG6 (WORLDGEN_ACTOR), opening.py WG8 (WORLDGEN_OPENING); prompts worldgen_*.user.j2; core lore.

The owner: "If they all talk the same. If they're all the same, I'll crash out." and "The lore needs merged
into ever crevice of this." Every worldgen call put what the Writer needed beside the prompt and never in
it: the history call was told to "keep each id" of events it was never shown, so every event fell back to its
skeleton; the opening call was told to cite "the listed entities and parameters" that were never listed, so
every opening was written by code; the people were written from a name, an age and a job — not their
generation, not the sketch that makes each one different, not what happened here, not what everyone in this
world says. The fake model read the hidden fields directly, so nothing failed. Now each prompt carries them.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from as_engine.contracts.common import CallClass
from as_engine.contracts.settings import EngineConfig, RunSettings
from as_engine.testing.fake_lm import FakeTransport

pytestmark = pytest.mark.phase(10)


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    from as_engine.service import runs
    from conftest import REPO_PACKS
    fake = FakeTransport()
    cfg = EngineConfig(runs_dir=str(tmp_path_factory.mktemp("writer") / "runs"), content_dir=str(REPO_PACKS))
    s = asyncio.run(runs.create_run(cfg, "core:pc/owen_marsh", RunSettings(world_detail="gotta_go_to_work_soon", seed=11,
                                                                         era="established", difficulty="normal"), fake))
    try:
        dsf = int(json.loads(s.store.query_one("SELECT params_json FROM world_params WHERE id = 1")[0])["days_since_fall"])
    finally:
        s.store.close()
    return fake, dsf


def user(r):
    return r.messages[-1].content


def test_the_history_call_is_shown_the_events_it_must_answer_for(made):
    fake, _dsf = made
    asked = fake.calls(CallClass.WORLDGEN_HISTORY)
    assert asked
    for r in asked:
        for e in r.context.fields["events"]:
            assert f"- {e['id']}: day {e['day']} since the Fall" in user(r) and e["skeleton"] in user(r)


def test_a_person_is_written_knowing_their_world_their_generation_and_what_everyone_says(made):
    fake, dsf = made
    asked = fake.calls(CallClass.WORLDGEN_ACTOR)
    assert asked, "the first generated people are written by the Writer"
    for r in asked:
        u = user(r)
        assert f"It is day {dsf} since the Fall" in u
        assert any(w in u for w in ("Born after the Fall", "A child when the Fall came", "Grown when the Fall came"))
        skel = r.context.fields["skeleton"]
        assert f"- How they talk: {skel['voice']['capsule']}" in u and f"- What hurt them: {skel['motive']['past_wound']}" in u
        assert "- If it's not the head, it's not dead." in u and "- There's no cure. Anybody selling one is selling you a grave." in u
        for h in r.context.fields["history"][:8]:
            assert f"- {h}" in u
    for r in asked:
        if "Born after the Fall" in user(r):
            assert "- Walkers are sleepwalking people. Wake them up and they get angry." in user(r)
            assert "- Shoot them enough and they stay down." not in user(r), "that is what the old say"


def test_the_opening_call_is_shown_what_it_must_cite(made):
    fake, _dsf = made
    asked = fake.calls(CallClass.WORLDGEN_OPENING)
    assert asked
    r = asked[0]
    assert "Your last answer was refused" not in user(r), "the first call is not a retry"
    for e in r.context.fields["entities"]:
        assert f"- {e['id']}: {e['what']}" in user(r)
    for k, v in r.context.fields["params"].items():
        assert f"- {k}: {v}" in user(r)
