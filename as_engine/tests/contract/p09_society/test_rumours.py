"""Rumours (P9). Rules INFO-01..07, SOC-03, SKULL-05, CAS-018 (world/rumours.py).

Talk moves along households, work crews and friendships, a few people a day, losing certainty at
every mouth. Every hop is a percept through the one knowledge writer — nobody simply knows. And a
rumour that reaches the trader changes the price (SOC-03).
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import RelationAxis
from as_engine.contracts.events import EventType
from as_engine.mind import mind
from as_engine.society import settlement as stl
from as_engine.world import rumours

from society_kit import accident, now, rel, rows, run

pytestmark = pytest.mark.phase(9)

THEFT = "took_what_was_not_theirs"


def holding(w, holder, about, claim=THEFT):
    r = w.store.query_one(
        "SELECT h.* FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id WHERE h.holder_id = ? AND "
        "h.superseded_by IS NULL AND p.subject_id = ? AND p.predicate = ?", (w.id(holder), w.id(about), claim))
    return None if r is None else dict(r)


def seed(w, holder, about, claim=THEFT, confidence=3):
    with w.store.transaction() as tx:
        cause = accident(tx, now(w), "a sack of meal went missing")
        return rumours.seed(tx, w.id(holder), w.id(about), claim, now(w), 0, cause.event_id, confidence=confidence)


def test_claim_sentences():
    assert rumours.claim_sentence(THEFT, "Jude") == "Jude took what was not theirs."
    assert rumours.claim_sentence("dead", "the old man") == "The old man is dead."
    assert rumours.claim_sentence("sleeps_on_watch", "Finn") == "Finn: sleeps on watch."


def test_info_07_a_seed_is_heard_not_known(settle):
    w = settle
    rid = seed(w, "finn", "jude")
    h = holding(w, "finn", "jude")
    assert (h["confidence"], h["provenance"], h["believed"]) == (3, "overheard", 1)
    r = dict(w.store.query_one("SELECT * FROM rumours WHERE rumour_id = ?", (rid,)))
    assert (r["prop_id"], r["origin_holder"], r["hops"]) == (h["claim_id"], w.id("finn"), 0)
    sp = rows(w, "RUMOUR_SPREAD")
    assert len(sp) == 1 and sp[0]["payload"]["teller_id"] is None and sp[0]["payload"]["hops"] == 0
    pct = w.store.query_one("SELECT channel, text FROM percept_log WHERE holder_id = ? AND event_id = ?", (w.id("finn"), f"rumour:{rid}"))
    assert pct[0] == "speech" and pct[1].startswith("Word is: ")


def test_info_02_each_hop_is_told_and_less_sure(settle):
    w = settle
    rid = seed(w, "finn", "jude")
    with w.store.transaction() as tx:
        rs = rumours.spread_one(tx, rid, w.id("finn"), w.id("kit"), now(w), 0, None)
        rs2 = rumours.spread_one(tx, rid, w.id("kit"), w.id("gus"), now(w), 0, None)
    assert (rs.type, rs.writer, rs.actor_id) == (EventType.RUMOUR_SPREAD, "world.rumours", w.id("finn"))
    assert {k: rs.payload[k] for k in ("teller_id", "listener_id", "confidence", "believed", "hops")} == \
        {"teller_id": w.id("finn"), "listener_id": w.id("kit"), "confidence": 2, "believed": True, "hops": 1}
    k, g = holding(w, "kit", "jude"), holding(w, "gus", "jude")
    assert (k["confidence"], k["provenance"], k["acquired_via"]) == (2, f"told_by:{w.id('finn')}", rs.event_id)
    assert (g["confidence"], g["provenance"]) == (1, f"told_by:{w.id('kit')}")      # SKULL-05: from B, not from A
    assert rs2.payload["hops"] == 2 and w.store.query_one("SELECT hops FROM rumours WHERE rumour_id = ?", (rid,))[0] == 2
    with w.store.transaction() as tx:
        rumours.spread_one(tx, rid, w.id("gus"), w.id("wade"), now(w), 0, None)
    assert holding(w, "wade", "jude")["confidence"] == 0
    with pytest.raises(ValueError):                                                  # confidence 0 is held, never passed on
        with w.store.transaction() as tx:
            rumours.spread_one(tx, rid, w.id("wade"), w.id("lena"), now(w), 0, None)


def test_nobody_believes_a_teller_they_distrust(settle):
    w = settle
    rid = seed(w, "jude", "amos")                                                    # the rivals
    with w.store.transaction() as tx:
        rs = rumours.spread_one(tx, rid, w.id("jude"), w.id("amos"), now(w), 0, None)   # telling the subject himself
        rs2 = rumours.spread_one(tx, rid, w.id("jude"), w.id("vera"), now(w), 0, None)
    assert rs.payload["believed"] is False                                           # amos distrusts jude (trust -2)
    assert holding(w, "amos", "amos")["believed"] == 0
    assert rs2.payload["believed"] is True
    assert [h for h, _c in rumours.holders(w.store, rid)] == sorted([w.id("jude"), w.id("vera")])


def test_cas_018_hearing_that_someone_steals_costs_them_trust(settle):
    w = settle
    rid = seed(w, "finn", "jude")
    with w.store.transaction() as tx:
        rs = rumours.spread_one(tx, rid, w.id("finn"), w.id("kit"), now(w), 0, None)
        from as_engine.action import cascade
        cascade.sweep(tx, [rs], tx.canon.all("cascade"), now(w), 0)
    r = rel(w, "kit", "jude")
    assert r["trust"] == -1
    ch = [x for x in rows(w, "RELATION_CHANGE") if x["rule_cited"] == "CAS-018"]
    assert len(ch) == 1 and ch[0]["cause_event_id"] == rs.event_id
    assert rel(w, "finn", "jude") is None                                            # the seed itself is not a hop


def test_info_05_spread_day_moves_a_few_people_a_day(settle):
    w = settle
    rid = seed(w, "finn", "jude")
    with w.store.transaction() as tx:
        out = rumours.spread_day(tx, w.id("settlers"), now(w), 0, None)
    told = [e.payload["listener_id"] for e in out if e.type == EventType.RUMOUR_SPREAD]
    assert told == [w.id("kit"), w.id("gus")]                                        # the friend first, then the crew mate
    with w.store.transaction() as tx:
        out2 = rumours.spread_day(tx, w.id("settlers"), now(w), 0, None)
    told2 = [(e.payload["teller_id"], e.payload["listener_id"]) for e in out2 if e.type == EventType.RUMOUR_SPREAD]
    assert (w.id("gus"), w.id("wade")) in told2 and (w.id("gus"), w.id("lena")) in told2
    assert all(l != w.id("jude") for _t, l in told2)                                 # nobody tells the subject


def test_info_01_neither_universal_nor_confined(settle):
    w = settle
    seed(w, "finn", "jude")
    run(w, 15 + 48)                                                                  # three group days
    holders = {h for h, _c in rumours.holders(w.store, w.store.query_one("SELECT rumour_id FROM rumours")[0])}
    assert len(holders) > 2, "it left the first conversation"
    assert len(holders) < 20, "and it did not reach everyone"
    assert w.id("jude") not in holders


def test_soc_03_a_rumour_reaches_trade(settle):
    w = settle
    sid = w.id("pumpwell")
    before = stl.trade_terms(w.store, sid, w.id("jude"))
    assert (before.willing, before.price_mult) == (True, 1.0)
    seed(w, "finn", "jude")                                                          # Finn saw Jude take a sack of meal
    run(w, 15 + 24)                                                                  # two evenings of talk
    lena = holding(w, "lena", "jude")
    assert lena is not None and lena["provenance"].startswith("told_by:")           # she was told, second-hand
    assert lena["confidence"] == 1
    after = stl.trade_terms(w.store, sid, w.id("jude"))
    assert (after.willing, after.price_mult) == (True, 1.5)
    assert after.reasons == ["Lena Kaminski has heard they steal."]
    chain = [r for r in rows(w, "RUMOUR_SPREAD") if r["payload"]["listener_id"] == w.id("lena")]
    assert len(chain) == 1 and chain[0]["payload"]["hops"] == 2


def test_the_player_hears_gossip_too_and_it_is_in_the_journal(settle):
    from as_engine.service.view import build_view
    w = settle
    rid = seed(w, "finn", "jude")
    with w.store.transaction() as tx:
        rumours.spread_one(tx, rid, w.id("finn"), w.id("pc"), now(w), 0, None)    # Finn tells the newcomer
    h = holding(w, "pc", "jude")
    assert (h["provenance"], h["confidence"]) == (f"told_by:{w.id('finn')}", 2)
    s = w.session()
    with w.store.transaction() as tx:
        v = build_view(tx, s)
    # SKULL-01: the sentence uses the PC's own word for the subject. The newcomer has never been told
    # Jude's name, so the journal says what the PC could say.
    assert v.journal.rumours == ["A man took what was not theirs."]
