"""How long an attempt with words takes (P4, Actor v2 — Actor Spec §9). Rule SEG-02
(action/intent.py to_intent).

Words take 2.5 per second, however few. Said alongside an attempt they overlap it (the longer of
the two); said before or after it they add. Someone hiding or sneaking cannot talk while doing it:
their words come first. The option on the menu never changes.

June after the crash and Mara's call (the moment of test_intent.py).
"""

from __future__ import annotations

import pytest

import helpers
from as_engine.action.intent import Intent, to_intent
from as_engine.contracts.common import LOD
from as_engine.contracts.events import Event, EventType
from as_engine.contracts.mind import ActionPayload, SpeechOut
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet

pytestmark = pytest.mark.phase(4)

TEN = "Mara, I am going to look at the back door."              # 10 words: 4 seconds


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
        perception.compile_scene(tx, w.id("june"), t + 2000, 0)
        aff = enumerate_affordances(tx, w.id("june"), w.canon.all("affordance"), t + 2000, 0)
        pkt = build_packet(tx, w.id("june"), LOD.HOT, aff, 0, t + 2000)
    return w, pkt, aff


def said(pkt, aff, def_id, text, timing, **kw):
    h = helpers.handle_for(pkt, def_id, kw.pop("target", None), kw.pop("w", None))
    base = next(o for o in aff.pool if o.signature == pkt.handles[h])
    it = to_intent(pkt, aff, ActionPayload(choice=h, goal="go and see",
                                           speech=SpeechOut(text=text, to=["everyone"], timing=timing)),
                   lod=LOD.HOT, source="model")
    assert isinstance(it, Intent)
    return base, it


def test_words_alongside_overlap_the_attempt(june):
    w, pkt, aff = june
    base, it = said(pkt, aff, "observe_area", TEN, "alongside")
    assert base.est_duration_s < 4.0
    assert it.bound.est_duration_s == pytest.approx(4.0), "the longer of the two: the words"
    assert it.speech.timing == "alongside"
    base, it = said(pkt, aff, "search_place", TEN, "alongside")
    assert it.bound.est_duration_s == pytest.approx(base.est_duration_s), "the longer of the two: the search"


@pytest.mark.parametrize("timing", ["before", "after"])
def test_words_before_or_after_add_to_it(june, timing):
    w, pkt, aff = june
    base, it = said(pkt, aff, "search_place", TEN, timing)
    assert it.bound.est_duration_s == pytest.approx(base.est_duration_s + 4.0)
    assert it.speech.timing == timing


def test_even_one_word_takes_time(june):
    w, pkt, aff = june
    base, it = said(pkt, aff, "observe_area", "Quiet.", "before")
    assert it.bound.est_duration_s == pytest.approx(base.est_duration_s + 1 / 2.5)


@pytest.mark.parametrize("def_id", ["hide", "sneak_to_anchor"])
def test_nobody_hides_or_sneaks_while_talking(june, def_id):
    w, pkt, aff = june
    base, it = said(pkt, aff, def_id, TEN, "alongside")
    assert {"hide", "sneak"} & set(base.tags)
    assert it.speech.timing == "before", "the words come first"
    assert it.bound.est_duration_s == pytest.approx(base.est_duration_s + 4.0)


def test_when_the_words_are_the_attempt(june):
    w, pkt, aff = june
    h = helpers.handle_for(pkt, "speak")
    base = next(o for o in aff.pool if o.signature == pkt.handles[h])
    for timing in ("before", "alongside", "after"):
        it = to_intent(pkt, aff, ActionPayload(choice=h, goal="warn her",
                                               speech=SpeechOut(text=TEN, to=["everyone"], timing=timing)),
                       lod=LOD.HOT, source="model")
        assert it.bound.est_duration_s == pytest.approx(max(base.est_duration_s, 4.0)), timing


def test_the_menu_is_never_changed(june):
    w, pkt, aff = june
    before = [(o.signature, o.est_duration_s) for o in aff.pool]
    said(pkt, aff, "search_place", TEN, "after")
    assert [(o.signature, o.est_duration_s) for o in aff.pool] == before
