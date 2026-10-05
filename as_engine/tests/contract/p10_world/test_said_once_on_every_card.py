"""Said once on every card (D-246); what they grew up hearing (D-249). mind/identity.py (the voice section); service/background.py BG-03 voicing card.

For a generated person — most of a world — the voice capsule is their two habits, and every card that shows how they
talk listed them twice: the decision card ("Victor is soft-spoken and exact; never shouts, even now." then "How you
tend to speak: Is soft-spoken and exact. Never shouts, even now.") and the card the quiet hours write their voice
from. A written voice, whose habits say more than its capsule, keeps both.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from as_engine.contracts.common import CallClass
from as_engine.contracts.dossier import ActorDossier
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.mind import identity
from as_engine.prompts.render import render
from as_engine.service import background as bg
from as_engine.world.worldgen import people

pytestmark = pytest.mark.phase(10)


def lines(card):
    return [ln.text for sec in card.sections for ln in sec.lines]


def test_the_decision_card(canon):
    d = people.skeleton_dossier(people.PersonSeed(name="Victor Hale", age=40, sex="male", cohort="pre_fall_adult",
                                                  occupation="watcher", skills={"firearms": 1},
                                                  special={L: 5 for L in "SPECIAL"}, variant=211, settlement_name="Vale",
                                                  group_name="the Vale"))
    got = lines(identity.compile_identity(ActorDossier.model_validate(d)))
    assert any(t.startswith("Victor ") for t in got) and not any(t.startswith("How you tend to speak") for t in got)
    mara = lines(identity.compile_identity(canon.get("core:actor/mara_voss")))
    assert any(t.startswith("How you tend to speak: ") for t in mara), "a written voice keeps its habits"


def test_the_card_a_voice_is_written_from(scenario, fake):
    w = scenario("metal_fence")
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.VOICE_WRITTEN, writer="mind.actor", at=t, turn_index=0, actor_id=w.id("mara"),
                              writes=[WriteRecord(op=WriteOp.INSERT, table="dossier_deltas", values={
                                  "delta_id": tx.mint("ddl"), "actor_id": w.id("mara"), "event_id": "test", "path": p,
                                  "op": "set", "value_json": json.dumps(v), "at": t})
                                  for p, v in (("voice.capsule", "Mara is grim and literal; states the odds."),
                                               ("voice.speech_tendencies", ["is grim and literal", "states the odds"]))],
                              payload={"actor_id": w.id("mara")}))
    fake.fail(CallClass.PERSON_VOICE, "grammar_fail")
    job = bg.Job(kind="voicing", subject_id=w.id("mara"), rumour_id=None, request_key=f"voicing:{w.id('mara')}:test")
    asyncio.run(bg.run_job(w.session(), job))
    [req] = fake.calls(CallClass.PERSON_VOICE)
    assert "How they talk: Mara is grim and literal; states the odds." in req.context.card
    assert not any(c.startswith("Habits of speech") for c in req.context.card)


def test_the_voice_is_written_knowing_what_they_grew_up_hearing(scenario, fake):
    """(D-249) The card a voice is written from carries what they grew up hearing — their people's words first."""
    w = scenario("metal_fence")
    fake.fail(CallClass.PERSON_VOICE, "grammar_fail")
    job = bg.Job(kind="voicing", subject_id=w.id("june"), rumour_id=None, request_key=f"voicing:{w.id('june')}:lore")
    asyncio.run(bg.run_job(w.session(), job))
    [req] = fake.calls(CallClass.PERSON_VOICE)
    held = [tuple(r) for r in w.store.query("SELECT lore_ref, belief, confidence, provenance FROM lore_held WHERE holder_id = ?",
                                            (w.id("june"),))]
    assert held and 0 < len(req.context.heard) <= bg.VOICE_LORE
    rank = {"group": 0, "childhood": 1, "common": 2}
    best = sorted(held, key=lambda r: (rank.get(r[3], 3), -r[2], r[0], r[1]))[0]
    assert req.context.heard[0] == w.canon.get(best[0]).beliefs[best[1]].text
    system, user = (m.content for m in render(CallClass.PERSON_VOICE, ctx=req.context))
    assert "grew up hearing, and believes:\n- " + req.context.heard[0] in user
    assert "what they call the dead" in system
