"""A long speech does not arrive at once (P5, Actor v2 — Actor Spec §9). Rules SEG-01, SEG-03, SEG-04
(action/intent.py segments; action/resolve.py resolve_wave, say_pending; kernel.clock SPEECH_SEGMENT).

Words go out at most eight at a time, split at punctuation when they can be, each segment when the
words before it have been said (2.5 words a second). Listeners hear what has been said and nothing
more: a speaker who dies, drops, or starts doing something else stops mid-sentence, and the rest of
the words never exist. One voice, one utterance at a time.

A kitchen (a dict scenario): Mara by the stove, June a step away, the player by the door.
"""

from __future__ import annotations

import dataclasses
import json
import math

import pytest

import helpers
from as_engine.action.intent import SEGMENT_WORDS, barrier, segments
from as_engine.action.resolve import resolve_wave, say_pending
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import bodies
from as_engine.physical.bodies import WoundSpec
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(5)

KITCHEN = {
    "schema": "as.scenario.v1", "name": "kitchen_talk", "seed": 21, "start": {"day": 400, "time": "18:00"},
    "places": [{"id": "kitchen", "name": "Kitchen", "material": "brick", "light": 3, "width_m": 8, "depth_m": 6,
                "anchors": [{"id": "stove", "name": "stove", "x": 2, "y": 2}, {"id": "door", "name": "door", "x": 7, "y": 5}]}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "kitchen", "anchor": "door"},
        {"id": "mara", "stub": {"name": "Mara Voss", "age": 38, "sex": "female"}, "place": "kitchen", "x": 2, "y": 2.5},
        {"id": "june", "stub": {"name": "June Okafor", "age": 29, "sex": "female"}, "place": "kitchen", "x": 3, "y": 2.5},
    ],
}

SIXTEEN = "stay low and keep away from that window because they can see the light from outside"   # 16 words, no stops
TWENTY_FOUR = SIXTEEN + " so we wait here until it is dark"                                         # 24 words


@pytest.fixture
def kitchen(fixture_packs, core_pack_dir):
    worlds = []

    def _load():
        w = load_scenario(KITCHEN, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        return w

    yield _load
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def talk(w, text, *, def_id="speak", timing="alongside", est_s=None, destination=None):
    words = len(text.split())
    it = helpers.make_intent(w, "mara", def_id, destination=destination, speech=(text, ["june"], "normal"),
                             est_s=est_s if est_s is not None else words / 2.5)
    return dataclasses.replace(it, speech=dataclasses.replace(it.speech, timing=timing))


def wave(w, *intents, at=None, horizon_s=10):
    t = now(w) if at is None else at
    with w.store.transaction() as tx:
        return resolve_wave(tx, helpers.ScriptedRng(), barrier(tx, list(intents)), t, 0, horizon_ms=t + int(horizon_s * 1000))


def of(evs, type_):
    return [e for e in evs if e.type == type_]


def fire(tx, row):
    """As the pipeline does: TIMER_FIRED, then the SPEECH_SEGMENT handler."""
    from as_engine.kernel import clock
    clock.fire(tx, row, 0)
    return say_pending(tx, row, 0)


def queued(w, status="pending"):
    return [dict(r, payload=json.loads(r["payload"])) for r in w.store.query(
        "SELECT * FROM event_queue WHERE type = 'SPEECH_SEGMENT' AND status = ? ORDER BY due_at", (status,))]


# --------------------------------------------------------------------------- SEG-01
@pytest.mark.parametrize("text,expected", [
    ("June, stay where you are. Nita is checking the cans out back.",
     ["June, stay where you are.", "Nita is checking the cans out back."]),
    (SIXTEEN, ["stay low and keep away from that window", "because they can see the light from outside"]),
    ("Down!", ["Down!"]),
    ("", []),
    ("Wait, no. We should go back and check the storeroom first before it gets dark",
     ["Wait, no. We should go back and check", "the storeroom first before it gets dark"]),
    ("If the gate holds — and it will — we sleep here tonight",
     ["If the gate holds —", "and it will — we sleep here tonight"]),
    ("Go to the door, then wait, keep still and do not move at all.",
     ["Go to the door, then wait,", "keep still and do not move at all."]),
])
def test_eight_words_at_most_cut_at_a_pause(text, expected):
    """A segment is the next eight words; when more follow, it ends at the last of its 4th..8th words
    that ends a clause (. , ; : ! ? … —) — never at the 1st..3rd."""
    assert SEGMENT_WORDS == 8
    assert segments(text) == expected
    assert " ".join(segments(text)) == " ".join(text.split())


# --------------------------------------------------------------------------- SEG-03
def test_a_long_warning_arrives_a_segment_at_a_time(kitchen):
    w = kitchen()
    t = now(w)
    evs = wave(w, talk(w, SIXTEEN))
    (start,) = of(evs, "ACTION_START")
    s1, s2 = of(evs, "SPEECH")
    assert (s1.at, s2.at) == (t, t + math.ceil(1000 * 8 / 2.5))
    assert [s.payload["words"] for s in (s1, s2)] == segments(SIXTEEN)
    assert [(s.payload["utterance_id"], s.payload["segment"], s.payload["segments"]) for s in (s1, s2)] == \
        [(start.event_id, 1, 2), (start.event_id, 2, 2)]
    assert all(s.cause_event_id == start.event_id and s.payload["to"] == [w.id("june")] for s in (s1, s2))


def test_what_is_not_yet_said_waits_on_the_clock(kitchen):
    """A segment due after the horizon is a SPEECH_SEGMENT row; say_pending says it when it falls due."""
    w = kitchen()
    t = now(w)
    evs = wave(w, talk(w, SIXTEEN), horizon_s=1)
    assert [s.payload["segment"] for s in of(evs, "SPEECH")] == [1]
    (row,) = queued(w)
    assert row["due_at"] == t + 3200 and row["payload"]["segment"] == 2 and row["payload"]["words"] == segments(SIXTEEN)[1]
    with w.store.transaction() as tx:
        said = fire(tx, row)
    (s2,) = [e for e in said if e.type == EventType.SPEECH]
    assert (s2.at, s2.payload["segment"], s2.payload["utterance_id"]) == (t + 3200, 2, row["payload"]["utterance_id"])


def test_a_dead_woman_finishes_nothing(kitchen):
    """SEG-04: at a segment's time the speaker must be alive and conscious; if not, that segment and
    every later one is never said, and one SPEECH_CUT says where the words stopped."""
    w = kitchen()
    wave(w, talk(w, TWENTY_FOUR), horizon_s=1)
    first, second = queued(w)
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=now(w) + 1000, turn_index=0, payload={"what": "test"}))
        bodies.apply_harm(tx, w.id("mara"), WoundSpec("head", "blunt", "catastrophic", 0), now(w) + 1000, c.event_id, 0, w.rng)
        evs = fire(tx, first)
    assert not [e for e in evs if e.type == EventType.SPEECH]
    (cut,) = [e for e in evs if e.type == EventType.SPEECH_CUT]
    assert cut.payload == {"actor_id": w.id("mara"), "utterance_id": first["payload"]["utterance_id"], "delivered": 1, "of": 3,
                           "cause": "dead"}
    assert queued(w) == [] and [r["queue_id"] for r in queued(w, "cancelled")] == [second["queue_id"]]


def test_new_words_cut_the_old(kitchen):
    """One voice, one utterance: whatever she starts next stops the rest of what she was saying."""
    w = kitchen()
    t = now(w)
    wave(w, talk(w, TWENTY_FOUR), horizon_s=1)
    evs = wave(w, talk(w, "Wait."), at=t + 2000)
    (cut,) = of(evs, "SPEECH_CUT")
    assert (cut.payload["delivered"], cut.payload["of"], cut.payload["cause"]) == (1, 3, "new_action")
    assert queued(w) == [] and len(queued(w, "cancelled")) == 2
    assert [s.payload["words"] for s in of(evs, "SPEECH")] == ["Wait."]


def test_words_after_the_attempt_come_when_it_is_done(kitchen):
    """timing 'after': the action lands first (its own time), then the words start."""
    w = kitchen()
    t = now(w)
    it = talk(w, "I am at the door now.", def_id="move_to_anchor", timing="after", destination="door", est_s=4.0 + 6 / 2.5)
    evs = wave(w, it)
    (done,) = of(evs, "ACTION_COMPLETE")
    (s1,) = of(evs, "SPEECH")
    assert done.at == t + 4000 and s1.at == t + 4000
    assert [e.type for e in evs].index(EventType.ACTION_COMPLETE) < [e.type for e in evs].index(EventType.SPEECH)


def test_she_hears_only_what_was_said(kitchen):
    """Listeners perceive the segments said, one percept each — never the words that never came."""
    w = kitchen()
    t = now(w)
    wave(w, talk(w, TWENTY_FOUR), horizon_s=1)
    first, _ = queued(w)
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t + 1000, turn_index=0, payload={"what": "test"}))
        bodies.apply_harm(tx, w.id("mara"), WoundSpec("head", "blunt", "catastrophic", 0), t + 1000, c.event_id, 0, w.rng)
        fire(tx, first)
        perception.compile_scene(tx, w.id("june"), t + 5000, 0)
    heard = [json.loads(r[0])["words"] for r in w.store.query(
        "SELECT detail FROM percept_log WHERE holder_id = ? AND channel = 'speech' ORDER BY at", (w.id("june"),))]
    assert heard == [segments(TWENTY_FOUR)[0]]
