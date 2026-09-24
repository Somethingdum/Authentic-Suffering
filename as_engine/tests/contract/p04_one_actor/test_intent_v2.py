"""Intent construction from an Actor v2 decision (P4 — Actor Spec §7). Rules INTENT-07..09
(action/intent.py to_intent).

A decision says what the person tries and how: at their normal pace, carefully or in a rush where
the attempt allows it; what they say (at most 100 words, 12 when something just reached them); a
gesture, where they look, or a note they write — only what the packet offered. Anything else is an
error the model is asked to repair, never a guess.

June after the crash and Mara's call (the same moment as test_intent.py).
"""

from __future__ import annotations

import dataclasses

import pytest

import helpers
from as_engine.action.intent import InscriptionAct, Intent, IntentError, to_intent
from as_engine.contracts.common import LOD
from as_engine.contracts.events import Event, EventType
from as_engine.contracts.mind import ActionPayload, CognitionOutput, Inscription, IntakeOutput, SpeechOut
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet

pytestmark = pytest.mark.phase(4)

WORDS_100 = " ".join(["word"] * 100)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


@pytest.fixture
def june(scenario):
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


def act(choice, **kw):
    kw.setdefault("goal", "Find out what fell")
    return ActionPayload(choice=choice, **kw)


def bound_of(pkt, aff, handle):
    (o,) = [o for o in aff.pool if o.signature == pkt.handles[handle]]
    return o


# --------------------------------------------------------------------------- INTENT-07 pace
@pytest.mark.parametrize("pace, mult, db", [("careful", 1.5, -6.0), ("rushed", 0.6, 6.0)])
def test_careful_and_rushed_change_time_and_noise_where_the_attempt_allows_it(june, pace, mult, db):
    w, pkt, aff = june
    h = helpers.handle_for(pkt, "search_place")
    base = bound_of(pkt, aff, h)
    assert pace in base.paces
    it = to_intent(pkt, aff, act(h, pace=pace), lod=LOD.HOT, source="model")
    assert isinstance(it, Intent) and it.pace == pace
    assert it.bound.est_duration_s == pytest.approx(base.est_duration_s * mult)
    assert it.bound.noise_db == pytest.approx(base.noise_db + db)
    assert base.est_duration_s == bound_of(pkt, aff, h).est_duration_s, "the offered option is not changed"


def test_normal_pace_changes_nothing(june):
    w, pkt, aff = june
    h = helpers.handle_for(pkt, "search_place")
    it = to_intent(pkt, aff, act(h), lod=LOD.HOT, source="model")
    assert it.pace == "normal" and it.bound == bound_of(pkt, aff, h)


@pytest.mark.parametrize("def_id, pace", [("go_look", "careful"), ("go_look", "rushed"), ("holster_item", "careful")])
def test_a_pace_the_attempt_does_not_allow_is_refused(june, def_id, pace):
    w, pkt, aff = june
    h = helpers.handle_for(pkt, def_id)
    assert pace not in bound_of(pkt, aff, h).paces
    err = to_intent(pkt, aff, act(h, pace=pace), lod=LOD.HOT, source="model")
    assert isinstance(err, IntentError) and err.kind == "unsupported_pace"


def test_the_players_words_are_not_a_protocol(june):
    """INTENT-07: an IntakeOutput whose pace the option does not support is read as normal."""
    w, pkt, aff = june
    h = helpers.handle_for(pkt, "go_look")
    it = to_intent(pkt, aff, IntakeOutput(choice=h, pace="careful", manner="carefully"), lod=LOD.HOT, source="human")
    assert isinstance(it, Intent) and it.pace == "normal" and it.bound == bound_of(pkt, aff, h)
    s = helpers.handle_for(pkt, "search_place")
    it = to_intent(pkt, aff, IntakeOutput(choice=s, pace="rushed", manner="quickly"), lod=LOD.HOT, source="human")
    assert it.pace == "rushed" and it.bound.est_duration_s == pytest.approx(bound_of(pkt, aff, s).est_duration_s * 0.6)


def test_a_v1_answer_is_at_normal_pace(june):
    w, pkt, aff = june
    h = helpers.handle_for(pkt, "search_place")
    it = to_intent(pkt, aff, CognitionOutput(choice=h, goal="look", private_reason="why not"), lod=LOD.HOT, source="model")
    assert it.pace == "normal" and it.bound == bound_of(pkt, aff, h)


def test_pace_applies_after_the_time_speech_takes(june):
    w, pkt, aff = june
    h = helpers.handle_for(pkt, "search_place")
    words = " ".join(["now"] * 25)
    it = to_intent(pkt, aff, act(h, pace="rushed", speech=SpeechOut(text=words, to=["everyone"])), lod=LOD.HOT,
                   source="model")
    assert it.bound.est_duration_s == pytest.approx((bound_of(pkt, aff, h).est_duration_s + 25 / 2.5) * 0.6)


# --------------------------------------------------------------------------- INTENT-08 speech
@pytest.mark.parametrize("n, reaction, ok", [(100, False, True), (101, False, False), (12, True, True), (13, True, False)])
def test_an_actor_says_at_most_a_hundred_words_and_twelve_in_a_reaction(june, n, reaction, ok):
    w, pkt, aff = june
    h = helpers.handle_for(pkt, "speak")
    text = " ".join(["word"] * n)
    out = to_intent(pkt, aff, act(h, speech=SpeechOut(text=text, to=["everyone"])), lod=LOD.HOT, source="model",
                    reaction=reaction)
    if ok:
        assert isinstance(out, Intent) and out.speech.text == text
    else:
        assert isinstance(out, IntentError) and out.kind == "speech_too_long"


def test_the_players_own_words_are_never_refused_for_length(june):
    w, pkt, aff = june
    h = helpers.handle_for(pkt, "speak")
    text = WORDS_100 + " and then some more"
    out = to_intent(pkt, aff, CognitionOutput(choice=h, speech=SpeechOut(text=text, to=["everyone"]), goal="talk",
                                              private_reason="talk"), lod=LOD.HOT, source="human")
    assert isinstance(out, Intent) and out.speech.text == text


def test_delivery_and_timing_travel_with_the_words(june):
    w, pkt, aff = june
    h = helpers.handle_for(pkt, "speak")
    it = to_intent(pkt, aff, act(h, speech=SpeechOut(text="Mara? It's me.", to=["everyone"], delivery="hesitant",
                                                    timing="before")), lod=LOD.HOT, source="model")
    assert (it.speech.delivery, it.speech.timing) == ("hesitant", "before")
    it = to_intent(pkt, aff, CognitionOutput(choice=h, speech=SpeechOut(text="Mara?", to=["everyone"]), goal="call",
                                             private_reason="call"), lod=LOD.HOT, source="model")
    assert (it.speech.delivery, it.speech.timing) == ("ordinary", "alongside")


def test_a_decisions_goal_and_reason_become_the_intents(june):
    w, pkt, aff = june
    h = helpers.handle_for(pkt, "go_look")
    it = to_intent(pkt, aff, act(h, goal="See who is out back", private_reason="It could be Nita."), lod=LOD.HOT,
                   source="model")
    assert (it.goal, it.private_reason, it.manner) == ("See who is out back", "It could be Nita.", "")
    it = to_intent(pkt, aff, act(h, goal="See who is out back"), lod=LOD.HOT, source="model")
    assert it.private_reason == ""


# --------------------------------------------------------------------------- INTENT-09 expression and writing
@pytest.mark.parametrize("field, value", [("gesture", "G1"), ("attention", "F1"), ("attention", "P1"), ("gesture", "A1")])
def test_a_gesture_or_a_look_the_packet_did_not_offer_is_refused(june, field, value):
    w, pkt, aff = june
    h = helpers.handle_for(pkt, "go_look")
    err = to_intent(pkt, aff, act(h, **{field: value}), lod=LOD.HOT, source="model")
    assert isinstance(err, IntentError) and err.kind == "hallucinated_expression"


def test_writing_needs_an_attempt_that_writes(june):
    w, pkt, aff = june
    h = helpers.handle_for(pkt, "go_look")
    err = to_intent(pkt, aff, act(h, inscription=Inscription(text="Gone to the back.")), lod=LOD.HOT, source="model")
    assert isinstance(err, IntentError) and err.kind == "bad_inscription"


@pytest.fixture
def writing(june):
    """June's moment with one attempt that writes (no core attempt does yet; a pack's may)."""
    w, pkt, aff = june
    h = helpers.handle_for(pkt, "search_place")
    sig = pkt.handles[h]

    def tag(o):
        return dataclasses.replace(o, tags=tuple(o.tags) + ("write",)) if o.signature == sig else o

    aff2 = dataclasses.replace(aff, options=[tag(o) for o in aff.options], pool=[tag(o) for o in aff.pool])
    heard = next(u.handle for u in pkt.utterances if "stay where you are" in (u.words or ""))
    return w, pkt, aff2, h, heard


def test_a_note_of_at_most_thirty_five_words(writing):
    w, pkt, aff, h, _heard = writing
    ok = to_intent(pkt, aff, act(h, inscription=Inscription(text=" ".join(["x"] * 35))), lod=LOD.HOT, source="model")
    assert isinstance(ok, Intent) and ok.inscription == InscriptionAct(text=" ".join(["x"] * 35), quotation_source=None)
    err = to_intent(pkt, aff, act(h, inscription=Inscription(text=" ".join(["x"] * 36))), lod=LOD.HOT, source="model")
    assert isinstance(err, IntentError) and err.kind == "bad_inscription"


def test_a_quotation_must_be_word_for_word_from_what_they_perceived(writing):
    w, pkt, aff, h, heard = writing
    ok = to_intent(pkt, aff, act(h, inscription=Inscription(text="stay where you are", quotation_source=heard)),
                   lod=LOD.HOT, source="model")
    assert isinstance(ok, Intent) and ok.inscription.quotation_source == pkt.handles[heard]
    for text, src in [("stay right where you are", heard), ("stay where you are", "A1"), ("stay where you are", "S99")]:
        err = to_intent(pkt, aff, act(h, inscription=Inscription(text=text, quotation_source=src)), lod=LOD.HOT,
                        source="model")
        assert isinstance(err, IntentError) and err.kind == "bad_inscription", (text, src)
