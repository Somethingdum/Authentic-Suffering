"""How they sound (D-261). service/background.py BG-03 voicing card.

The card a voice is written from gave age, sex and work, how they talk and what they grew up hearing — but not where
they come from, nor the dossier's own words on how they sound. So a woman from Indianapolis whose mother's Nigerian
English comes out when she is very tired got a voice as flat as anyone's: the one thing that made her sound like
herself was in her dossier and never reached the call that writes her voice.
"""

from __future__ import annotations

import asyncio

import pytest

from as_engine.contracts.common import CallClass
from as_engine.service import background as bg

pytestmark = pytest.mark.phase(10)


def card(w, fake, who):
    fake.fail(CallClass.PERSON_VOICE, "grammar_fail")
    job = bg.Job(kind="voicing", subject_id=w.id(who), rumour_id=None, request_key=f"voicing:{w.id(who)}:sound")
    asyncio.run(bg.run_job(w.session(), job))
    [req] = fake.calls(CallClass.PERSON_VOICE)
    return req.context.card


def test_where_they_come_from_and_how_they_sound(scenario, fake):
    w = scenario("metal_fence")
    d = w.canon.get("core:actor/june_okafor")
    got = card(w, fake, "june")
    assert f"From: {d.identity.birthplace}" in got
    assert f"How they sound: {d.voice.dialect_notes.strip()}" in got


def test_nothing_said_when_the_dossier_has_nothing(scenario, fake):
    w = scenario("metal_fence")
    assert not w.canon.get("core:actor/eli_voss").voice.dialect_notes.strip()
    got = card(w, fake, "eli")
    assert not [c for c in got if c.startswith("How they sound")]
    assert "" not in got
