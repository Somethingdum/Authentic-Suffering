"""Intent construction (P4). Rules INTENT-01..02, L2, L3, TIME-05 (action/intent.py to_intent).

A model's answer names an option handle; code turns it into an Intent by looking the handle up in
the packet it was shown. Anything the packet did not offer is an error, never a guess.
"""

from __future__ import annotations

import pytest

import helpers
from as_engine.action.intent import Intent, IntentError, SpeechAct, to_intent
from as_engine.contracts.common import LOD, Volume
from as_engine.contracts.events import Event, EventType
from as_engine.contracts.mind import CognitionOutput, IntakeOutput
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet

pytestmark = pytest.mark.phase(4)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


@pytest.fixture
def june(scenario):
    """June after the crash and Mara's call: her packet and the AffordanceSet it was built from."""
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", at=t, turn_index=0,
                              payload={"source_db": 98, "kind": "metal_crash", "text": "a loud metal crash",
                                       "place_id": w.id("alley"), "anchor_id": w.id("fence_sheet")}))
        tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=t + 1500, turn_index=0,
                              actor_id=w.id("mara"), payload={"words": "June, stay where you are.", "volume": "raised",
                                                             "to": [w.id("june")], "source_db": 70}))
        perception.compile_scene(tx, w.id("june"), t + 2000, 0)
        aff = enumerate_affordances(tx, w.id("june"), w.canon.all("affordance"), t + 2000, 0)
        pkt = build_packet(tx, w.id("june"), LOD.HOT, aff, 0, t + 2000)
    return w, pkt, aff


def cog(choice, speech=None, manner="quietly", goal="See what fell out back", reason="It could be Nita."):
    return CognitionOutput(choice=choice, speech=speech, manner=manner, goal=goal, private_reason=reason)


def test_a_chosen_handle_becomes_the_offered_option(june):
    w, pkt, aff = june
    h = helpers.handle_for(pkt, "go_look", "back_door_in", w)
    it = to_intent(pkt, aff, cog(h), lod=LOD.HOT, source="model")
    assert isinstance(it, Intent)
    (opt,) = [o for o in aff.options if o.signature == pkt.handles[h]]
    assert it.bound == opt and it.actor_id == w.id("june") and it.speech is None
    assert (it.manner, it.goal, it.private_reason, it.source, it.lod) == (
        "quietly", "See what fell out back", "It could be Nita.", "model", LOD.HOT)


@pytest.mark.parametrize("choice", ["A99", "A0", "P1", "S1", "go_look", "a1"])
def test_anything_not_offered_is_a_hallucinated_choice(june, choice):
    w, pkt, aff = june
    it = to_intent(pkt, aff, cog(choice), lod=LOD.HOT, source="model")
    assert isinstance(it, IntentError) and it.kind == "hallucinated_choice"


def test_a_handle_whose_option_is_gone_is_hallucinated(june):
    """The handle exists in the packet but its signature is not in THIS AffordanceSet (neither its
    menu nor its pool — the pool is what a consultation may add from)."""
    w, pkt, aff = june
    h = helpers.handle_for(pkt, "go_look", "back_door_in", w)
    aff.options = [o for o in aff.options if o.def_id != "go_look"]
    aff.pool = [o for o in aff.pool if o.def_id != "go_look"]
    assert to_intent(pkt, aff, cog(h), lod=LOD.HOT, source="model").kind == "hallucinated_choice"


def test_speech_targets_map_to_ids(june):
    w, pkt, aff = june
    mara_h = next(e.handle for e in pkt.entities if pkt.handles[e.handle] == w.id("mara"))
    speak = helpers.handle_for(pkt, "speak", "mara", w)
    it = to_intent(pkt, aff, cog(speak, speech={"text": "I'm staying. What was that?", "to": [mara_h], "volume": "raised"}),
                   lod=LOD.HOT, source="model")
    assert it.speech == SpeechAct(text="I'm staying. What was that?", to=(w.id("mara"),), volume=Volume.RAISED)
    it2 = to_intent(pkt, aff, cog(speak, speech={"text": "Hello?", "to": []}), lod=LOD.HOT, source="model")
    assert it2.speech.to == ("everyone",) and it2.speech.volume == Volume.NORMAL
    it3 = to_intent(pkt, aff, cog(speak, speech={"text": "Hello?", "to": ["everyone"]}), lod=LOD.HOT, source="model")
    assert it3.speech.to == ("everyone",)


@pytest.mark.parametrize("to", [["P99"], ["A1"], ["Mara"], ["S2"]])
def test_speech_to_someone_not_in_the_packet_is_an_error(june, to):
    w, pkt, aff = june
    speak = helpers.handle_for(pkt, "speak", None)
    it = to_intent(pkt, aff, cog(speak, speech={"text": "Hey.", "to": to}), lod=LOD.HOT, source="model")
    assert isinstance(it, IntentError) and it.kind == "hallucinated_target"


def test_speak_without_words_is_empty(june):
    w, pkt, aff = june
    speak = helpers.handle_for(pkt, "speak", None)
    assert to_intent(pkt, aff, cog(speak), lod=LOD.HOT, source="model").kind == "empty"


def test_talking_while_acting_costs_time(june):
    """TIME-05, SEG-02: words said alongside an attempt overlap it — the longer of the two (a V1
    answer's speech is alongside)."""
    w, pkt, aff = june
    h = helpers.handle_for(pkt, "go_look", "back_door_in", w)
    base = next(o for o in aff.options if o.signature == pkt.handles[h])
    short = to_intent(pkt, aff, cog(h, speech={"text": "Coming, hang on.", "to": []}), lod=LOD.HOT, source="model")
    assert short.bound.est_duration_s == pytest.approx(max(base.est_duration_s, 3 / 2.5))
    words = "Okay so I am going to go and look at the back door right now all right"   # 17 words
    long = to_intent(pkt, aff, cog(h, speech={"text": words, "to": []}), lod=LOD.HOT, source="model")
    assert long.bound.est_duration_s == pytest.approx(max(base.est_duration_s, 17 / 2.5))
    assert base.est_duration_s == pytest.approx(next(o for o in aff.options if o.signature == pkt.handles[h]).est_duration_s), \
        "the AffordanceSet itself is not modified"


def test_intake_output(june):
    w, pkt, aff = june
    h = helpers.handle_for(pkt, "wait_here", None)
    it = to_intent(pkt, aff, IntakeOutput(choice=h, manner="holding my breath"), lod=LOD.WARM, source="human")
    assert (it.goal, it.private_reason, it.source) == ("holding my breath", "", "human")
    bare = to_intent(pkt, aff, IntakeOutput(choice=h), lod=LOD.WARM, source="human")
    assert bare.goal == bare.bound.label
    none = to_intent(pkt, aff, IntakeOutput(choice="NONE", none_reason="not_holding"), lod=LOD.WARM, source="human")
    assert isinstance(none, IntentError) and (none.kind, none.detail) == ("none_choice", "not_holding")


def test_to_intent_is_pure(june):
    w, pkt, aff = june
    n = w.store.query_one("SELECT COUNT(*) FROM events")[0]
    to_intent(pkt, aff, cog(helpers.handle_for(pkt, "wait_here", None)), lod=LOD.HOT, source="model")
    assert w.store.query_one("SELECT COUNT(*) FROM events")[0] == n
