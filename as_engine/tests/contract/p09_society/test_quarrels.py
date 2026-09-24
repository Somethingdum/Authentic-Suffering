"""People who live on top of each other, short of everything, fight (P9, the owner's H1). Rule
STL-15 (society/settlement.py friction; STL-03 step 8b).

The owner: "If I don't see two NPCs in my group cussing each other out, or two fuckers on the
street of a walled-in Haven-esque faction, then I'm not convinced." At Pumpwell, Jude and Amos
are rivals; once one of them resents the other, the settlement's day can turn into a row — or a
fight — and the whole place hears about it.
"""

from __future__ import annotations

import pytest

from as_engine.action.effects import CENTRE_MASS
from as_engine.contracts.settings import RulesConfig, SocietyRules
from as_engine.mind import actor, mind as mindmod, temper
from as_engine.society import settlement as stl
from society_kit import DAY, accident, now, rows, run

pytestmark = pytest.mark.phase(9)


class Dice:
    """Records every chance asked (purpose, p) and answers from a script by purpose prefix."""

    def __init__(self, answers):
        self.answers = answers
        self.asked = []

    def chance(self, tx, stream, purpose, p):
        self.asked.append((stream, purpose, round(p, 6)))
        return self.answers[purpose.split(":")[0]]

    def weighted(self, tx, stream, purpose, items):
        self.asked.append((stream, purpose, None))
        return items[0][0]

    def range_int(self, tx, stream, purpose, lo, hi):
        return lo

    def d10(self, tx, stream, purpose):
        return 5


def sour(w, a, b, at, stress_a=0, stress_b=0):
    """``a`` resents ``b`` (resentment 2); strain as given."""
    with w.store.transaction() as tx:
        c = accident(tx, at, "an old argument over the pump rota")
        mindmod.relate(tx, w.id(a), w.id(b), "resentment", 2, c.event_id, at, 0)
        if stress_a:
            actor.adjust_stress(tx, w.id(a), stress_a, c.event_id, at, 0)
        if stress_b:
            actor.adjust_stress(tx, w.id(b), stress_b, c.event_id, at, 0)
        return c


def sid(w):
    return w.store.query_one("SELECT settlement_id FROM settlements")[0]


def friction(w, dice, at, cause):
    with w.store.transaction() as tx:
        return stl.friction(tx, dice, sid(w), at, 0, cause)


def test_nobody_sore_nobody_fights(settle):
    w = settle
    dice = Dice({})
    with w.store.transaction() as tx:
        c = accident(tx, now(w))
    assert friction(w, dice, now(w), c.event_id) == [] and dice.asked == []


def test_a_row_the_whole_place_hears_about(settle):
    """Amos (stress 6) is sore at Jude: the chance of a row is 0.05 + 0.05 x 6; it happens. Amos,
    the more strained, starts it; he is no brawler (a stub: outlet 'words'), so blows are a quarter
    as likely — and this time none land. Both are angrier at each other after, and people talk."""
    w = settle
    t = now(w)
    c = sour(w, "amos", "jude", t, stress_a=6)
    dice = Dice({"quarrel": True, "brawl": False})
    out = friction(w, dice, t, c.event_id)
    a, b = sorted([w.id("amos"), w.id("jude")])
    day = t // DAY
    assert dice.asked == [("society", f"quarrel:{a}:{b}:{day}", 0.35), ("society", f"brawl:{a}:{b}:{day}", 0.075)]
    (q,) = [e for e in out if e.type == "QUARREL"]
    assert (q.writer, q.actor_id, q.cause_event_id) == ("society.settlement", w.id("amos"), c.event_id)
    assert q.payload == {"settlement_id": sid(w), "a": a, "b": b, "instigator_id": w.id("amos"), "brawl": False}
    changes = [e for e in out if e.type == "TEMPER_CHANGE"]
    assert [(e.payload["holder_id"], e.payload["toward_id"], e.payload["kind"], e.payload["heat"]) for e in changes] == \
        [(a, b, "quarreled", 3), (b, a, "quarreled", 3)]
    assert all(e.cause_event_id == q.event_id for e in changes)
    assert not [e for e in out if e.type == "HARM"], "words only"
    heard = {r[0] for r in w.store.query(
        "SELECT h.holder_id FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id "
        "WHERE p.subject_id = ? AND p.predicate = 'fell_out'", (w.id("amos"),))}
    assert w.id("tomas") in heard and w.id("vera") in heard and w.id("amos") not in heard


def test_when_it_comes_to_blows(settle):
    w = settle
    t = now(w)
    c = sour(w, "jude", "amos", t, stress_a=3, stress_b=3)
    dice = Dice({"quarrel": True, "brawl": True})
    out = friction(w, dice, t, c.event_id)
    a, b = sorted([w.id("amos"), w.id("jude")])
    (q,) = [e for e in out if e.type == "QUARREL"]
    assert q.payload["instigator_id"] == a and q.payload["brawl"] is True, "equal strain: the first of the two starts it"
    harms = [e for e in out if e.type == "HARM"]
    assert [(e.payload["body_id"], e.payload["anatomy"], e.payload["type"], e.payload["severity"]) for e in harms] == \
        [(a, CENTRE_MASS[0][0], "blunt", "minor"), (b, CENTRE_MASS[0][0], "blunt", "minor")]
    assert all(e.cause_event_id == q.event_id for e in harms)
    standing = [e for e in out if e.type == "STANDING_CHANGE"]
    assert sorted(e.payload["actor_id"] for e in standing) == [a, b]
    heard = {r[0] for r in w.store.query(
        "SELECT h.holder_id FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id "
        "WHERE p.subject_id = ? AND p.predicate = 'lost_it'", (a,))}
    assert w.id("tomas") in heard


def test_a_grudge_is_enough(settle):
    w = settle
    t = now(w)
    with w.store.transaction() as tx:
        c = accident(tx, t)
        mindmod.open_loop(tx, w.id("kit"), "grudge", "She took my watch shift and my rations.", [w.id("cora")], 2,
                          c.event_id, t, 0)
    dice = Dice({"quarrel": False, "brawl": False})
    assert friction(w, dice, t, c.event_id) == []
    a, b = sorted([w.id("kit"), w.id("cora")])
    assert [p for _s, p, _x in dice.asked] == [f"quarrel:{a}:{b}:{t // DAY}"], "asked, and it did not happen today"


def test_the_player_is_never_in_a_row_they_did_not_choose(settle):
    w = settle
    t = now(w)
    c = sour(w, "tomas", "pc", t, stress_a=9)
    dice = Dice({"quarrel": True, "brawl": True})
    assert friction(w, dice, t, c.event_id) == [] and dice.asked == []


def test_the_settlement_day_has_its_rows(scenario):
    """STL-03 step 8b: with the odds forced to certain, the day's rows happen off-screen, caused by
    the settlement day."""
    w = scenario("pump_settlement", rules=RulesConfig(society=SocietyRules(quarrel_base=1.0, brawl_chance=0.0)))
    sour(w, "amos", "jude", now(w))
    run(w, 26)
    days = {r["event_id"]: r for r in rows(w, "SETTLEMENT_DAY")}
    qs = rows(w, "QUARREL")
    assert qs and len(qs) == len(days), "one row a day between the two of them"
    for q in qs:
        assert {q["payload"]["a"], q["payload"]["b"]} == {w.id("amos"), w.id("jude")} and q["payload"]["brawl"] is False
        assert days[q["cause_event_id"]]["payload"]["settlement_id"] == sid(w)
    assert temper.heat(w.store, w.id("jude"), w.id("amos"), qs[0]["at"]) == 3
