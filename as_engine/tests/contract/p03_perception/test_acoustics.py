"""Audibility compiler (P3). Rules AUD-01..08, CROWD-01..02 (sense/acoustics.py).

Every expected number is in tests/fixtures/vectors/acoustics.json with its arithmetic in 'why'.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import Fidelity
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.sense import acoustics
from as_engine.sense.acoustics import Point

pytestmark = pytest.mark.phase(3)

SCEN = {"metal_fence_gust": "metal_fence", "metal_fence_june_call": "metal_fence",
        "three_rooms_gunshot": "three_rooms_gunshot", "crowd_normal_voice": "crowd_accusation"}


def test_fidelity_bands(vectors, rules):
    """AUD-02: EXACT >= 12, PARTIAL >= 5, TONE_ONLY >= 0, else NONE (margins in dB)."""
    for case in vectors("acoustics")["fidelity_for_margin"]:
        assert acoustics.fidelity_for_margin(case["margin"], rules.acoustics).value == case["fidelity"], case


@pytest.mark.parametrize("key", sorted(SCEN))
def test_reception_vectors(scenario, vectors, rules, key):
    """AUD-01/03: received dB, margin, fidelity and the min-loss portal path for every listener."""
    v = vectors("acoustics")["scenarios"][key]
    w = scenario(SCEN[key])
    src = Point(w.id(v["source"][0]), v["source"][1], v["source"][2])
    got = {r.listener_id: r for r in acoustics.receptions(w.store, v["source_db"], src, 0, rules.acoustics)}
    for e in v["receptions"]:
        r = got[w.id(e["listener"])]
        assert r.received_db == pytest.approx(e["received_db"], abs=0.01), e["why"]
        assert r.margin_db == pytest.approx(e["margin_db"], abs=0.01), e["why"]
        assert r.fidelity.value == e["fidelity"], (e["listener"], e["why"])
        assert list(r.path_portals) == [w.id(p) for p in e["path_portals"]], e["listener"]


def test_receptions_cover_linked_living_bodies_sorted(scenario, rules):
    w = scenario("three_rooms_gunshot")
    src = Point(w.id("room1"), 2.5, 2.5)
    recs = acoustics.receptions(w.store, 160, src, 0, rules.acoustics, exclude={w.id("a")})
    assert [r.listener_id for r in recs] == sorted([w.id("b"), w.id("c")])


def test_sleepers_hear_loud_things_as_tone_and_wake(scenario, vectors, rules):
    """AUD-05: a sleeper registers only >= 55 dB received, never better than TONE_ONLY."""
    w = scenario("three_rooms_gunshot")
    src = Point(w.id("room1"), 2.5, 2.5)
    c = {r.listener_id: r for r in acoustics.receptions(w.store, 160, src, 0, rules.acoustics)}[w.id("c")]
    assert c.margin_db >= rules.acoustics.exact_margin_db, "margin alone would be EXACT"
    assert (c.fidelity, c.wakes) == (Fidelity.TONE_ONLY, True)
    quiet = {r.listener_id: r for r in acoustics.receptions(w.store, 100, src, 0, rules.acoustics)}[w.id("c")]
    assert quiet.received_db < rules.acoustics.asleep_threshold_db and (quiet.fidelity, quiet.wakes) == (Fidelity.NONE, False)


def test_ambient_formula(scenario):
    """AUD-06: place ambient + wind x 8 outdoors, rain/storm floors, never below 20 dB."""
    w = scenario("metal_fence")  # wind level 2
    assert acoustics.ambient_db(w.store, w.id("sales_floor")) == 35.0  # indoor: wind ignored
    assert acoustics.ambient_db(w.store, w.id("alley")) == 30.0 + 2 * 8
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.WEATHER_CHANGE, writer="kernel.clock", at=0, turn_index=0, writes=[
            WriteRecord(op=WriteOp.UPDATE, table="world_clock", key={"id": 1}, values={"weather": "storm", "wind_level": 0})]))
    assert acoustics.ambient_db(w.store, w.id("alley")) == 65.0
    assert acoustics.ambient_db(w.store, w.id("office")) == 30.0


def test_masking_and_divided_attention(scenario, rules):
    """AUD-04: the loudest other sound (passed by the caller) and talking/focus raise the floor."""
    w = scenario("crowd_accusation")
    src = Point(w.id("hall"), 7.5, 29.0)
    base = {r.listener_id: r for r in acoustics.receptions(w.store, 60, src, 0, rules.acoustics)}
    l04 = w.id("l04")
    masked = {r.listener_id: r for r in acoustics.receptions(w.store, 60, src, 0, rules.acoustics, masking={l04: 48.0})}
    assert masked[l04].margin_db == pytest.approx(base[l04].received_db - 48.0)
    assert masked[l04].fidelity == Fidelity.TONE_ONLY and base[l04].fidelity == Fidelity.PARTIAL
    with w.store.transaction() as tx:  # l02 speaks at the same moment
        tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=500, turn_index=0, actor_id=w.id("l02"),
                              payload={"words": "Hey.", "volume": "low", "to": ["everyone"], "source_db": 50}))
    talk = {r.listener_id: r for r in acoustics.receptions(w.store, 60, src, 1000, rules.acoustics)}
    assert talk[w.id("l02")].margin_db == pytest.approx(base[w.id("l02")].margin_db - rules.acoustics.divided_attention_penalty_db)
    assert talk[w.id("l01")].margin_db == pytest.approx(base[w.id("l01")].margin_db)


def test_privacy_is_physical(scenario, rules):
    """CROWD-02: privacy is volume and distance, never a declaration. A whisper (30 dB) in a 40 dB
    hall reaches nobody, not even at 1 m; a shout (85 dB) reaches the observer by the doors."""
    w = scenario("crowd_accusation")
    src = Point(w.id("hall"), 7.5, 29.0)
    whisper = acoustics.receptions(w.store, rules.acoustics.speech_db["whisper"], src, 0, rules.acoustics, exclude={w.id("pc")})
    assert {r.fidelity for r in whisper} == {Fidelity.NONE}
    shout = {r.listener_id: r for r in acoustics.receptions(w.store, rules.acoustics.speech_db["shout"], src, 0, rules.acoustics)}
    assert shout[w.id("observer")].fidelity == Fidelity.EXACT


def test_unconscious_listeners_get_nothing(scenario, rules):
    w = scenario("three_rooms_gunshot")
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.AWARENESS_CHANGE, writer="physical.bodies", at=0, turn_index=0, writes=[
            WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": w.id("b")}, values={"awareness": "unconscious"})]))
    b = {r.listener_id: r for r in acoustics.receptions(w.store, 160, Point(w.id("room1"), 2.5, 2.5), 0, rules.acoustics)}[w.id("b")]
    assert b.fidelity == Fidelity.NONE


def test_partial_words_vectors(vectors):
    """AUD-07: deterministic per (event, listener); one ellipsis per dropped run."""
    for case in vectors("acoustics")["partial_words"]:
        assert acoustics.partial_words(case["text"], case["event_id"], case["listener_id"]) == case["expected"]


def test_partial_words_differ_between_listeners():
    a = acoustics.partial_words("Reggie has been skimming the tribute for months", "evt_000042", "act_000003")
    b = acoustics.partial_words("Reggie has been skimming the tribute for months", "evt_000042", "act_000004")
    assert a != b, "two partial listeners hear different fragments (and form different wrong beliefs)"


def test_source_point(scenario):
    w = scenario("metal_fence")
    assert acoustics.source_point(w.store, {"anchor_id": w.id("fence_sheet")}, None) == Point(w.id("alley"), 5.0, 5.8)
    assert acoustics.source_point(w.store, {"place_id": w.id("alley")}, None) == Point(w.id("alley"), 6.0, 3.0)
    assert acoustics.source_point(w.store, {}, w.id("mara")) == Point(w.id("sales_floor"), 3.0, 0.5)
    with pytest.raises(ValueError):
        acoustics.source_point(w.store, {}, None)
