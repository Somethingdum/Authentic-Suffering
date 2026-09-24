"""Settlements (P9). Rules STL-01..12, SOC-03 (society/settlement.py).

Stores are counted, rations are a level, shortages are declared by content and ended by the daily
draw, and a trader's terms come from what the trader believes.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.events import EventType
from as_engine.mind import mind
from as_engine.society import settlement as stl

from society_kit import DAY, H, hhmm, now, rows, run, settlement

pytestmark = pytest.mark.phase(9)


def test_days_of_and_the_ration_multiplier(settle):
    w = settle
    sid = w.id("pumpwell")
    assert stl.daily_need(w.store, sid) == {"food": 42.0, "water": 62.0}
    assert stl.days_of(w.store, sid, "water") == pytest.approx(192 / 62)
    assert stl.days_of(w.store, sid, "fuel") == float("inf")               # nobody eats fuel
    with w.store.transaction() as tx:
        stl.change_ration(tx, sid, -1, "test", now(w), 0, None)
    assert stl.daily_need(w.store, sid) == {"food": 31.5, "water": 46.5}
    assert not stl.has_shortage(w.store, sid, "water")


def test_receive_never_goes_below_zero(settle):
    w = settle
    sid = w.id("pumpwell")
    with w.store.transaction() as tx:
        e = stl.receive(tx, sid, {"water": -500, "food": 2.25}, "theft", now(w), 0, None)
    assert e.type == EventType.STORES_CHANGE
    assert e.payload == {"settlement_id": sid, "changes": {"food": 2.25, "water": -192}, "after": {"food": 162.25, "water": 0},
                         "reason": "theft"}
    assert settlement(w)["stores"]["water"] == 0
    with pytest.raises(ValueError):
        with w.store.transaction() as tx:
            stl.receive(tx, "stl_999999", {"water": 1}, "x", now(w), 0, None)


def test_shortages_and_rations(settle):
    w = settle
    sid = w.id("pumpwell")
    with w.store.transaction() as tx:
        s1 = stl.declare_shortage(tx, sid, "water", now(w), 0, None)
        assert stl.declare_shortage(tx, sid, "water", now(w), 0, None) is None
        r1 = stl.change_ration(tx, sid, -1, "shortage", now(w), 0, None)
        stl.change_ration(tx, sid, -9, "panic", now(w), 0, None)
        assert stl.change_ration(tx, sid, -1, "panic", now(w), 0, None) is None
        r3 = stl.change_ration(tx, sid, 9, "plenty", now(w), 0, None)
    assert s1.payload["days"] == round(192 / 62, 2) and stl.has_shortage(w.store, sid, "water")
    assert {k: r1.payload[k] for k in ("delta", "level_before", "level_after", "cause")} == \
        {"delta": -1, "level_before": 3, "level_after": 2, "cause": "shortage"}
    assert (r3.payload["level_before"], r3.payload["level_after"]) == (0, 4)


def test_the_daily_draw_feeds_people(settle):
    w = settle
    run(w, 2.5)                                                               # through the 07:00 draw
    day = rows(w, "SETTLEMENT_DAY")
    assert len(day) == 1 and hhmm(day[0]["at"]) == "07:00"
    p = day[0]["payload"]
    assert p["drawn"] == {"food": 42, "water": 62} and p["short"] == {"food": [], "water": []} and p["ration_level"] == 3
    fed = [r for r in rows(w, "NEED_STAGE") if r["cause_event_id"] == day[0]["event_id"]]
    assert {(r["payload"]["body_id"], r["payload"]["need"]) for r in fed} >= {(w.id("pc"), "thirst"), (w.id("pc"), "hunger")}
    assert settlement(w)["next_due_at"] == day[0]["at"] + DAY


def test_hunger_when_the_store_runs_dry(settle):
    w = settle
    sid = w.id("pumpwell")
    with w.store.transaction() as tx:
        stl.receive(tx, sid, {"water": -192}, "spilled", now(w), 0, None)     # the tank is empty ...
    run(w, 2.5)                                                               # ... but for the 31 pumped at 06:00
    p = rows(w, "SETTLEMENT_DAY")[0]["payload"]
    assert p["ration_level"] == 2                                             # the 06:00 cycle already cut rations (CAS-004/005)
    # the youngest drink first, then the elders; eight adults get the rest (2.25 each), by id
    assert p["short"]["water"] == [w.id(x) for x in ("iris", "finn", "kit", "amos", "vera", "jude", "tomas")]
    assert p["drawn"]["water"] == 30.75 and settlement(w)["stores"]["water"] == 0.25
    thirsty = {r["payload"]["body_id"] for r in rows(w, "NEED_STAGE") if r["payload"]["need"] == "thirst"
               and r["cause_event_id"] == rows(w, "SETTLEMENT_DAY")[0]["event_id"]}
    assert w.id("ada") in thirsty and w.id("pc") in thirsty and w.id("tomas") not in thirsty


def test_morale_follows_the_ration(settle):
    w = settle
    sid = w.id("pumpwell")
    with w.store.transaction() as tx:
        stl.change_ration(tx, sid, -1, "test", now(w), 0, None)
        stl.adjust(tx, sid, "morale", -3, now(w), 0, None)
    run(w, 2.5)
    m = [r for r in rows(w, "SETTLEMENT_CHANGE") if r["payload"]["field"] == "morale"]
    assert [(x["payload"]["old"], x["payload"]["new"], x["payload"]["reason"]) for x in m] == [(5, 2, "cascade"), (2, 1, "rations")]


def test_morale_recovers_when_the_stores_are_fine(settle):
    w = settle
    with w.store.transaction() as tx:
        stl.adjust(tx, w.id("pumpwell"), "morale", -2, now(w), 0, None)
    run(w, 2.5)
    m = [r for r in rows(w, "SETTLEMENT_CHANGE") if r["payload"]["reason"] == "recovering"]
    assert [(x["payload"]["old"], x["payload"]["new"]) for x in m] == [(3, 4)]


def test_a_shortage_ends_and_rations_recover_after_a_good_streak(settle):
    w = settle
    sid = w.id("pumpwell")
    with w.store.transaction() as tx:
        stl.declare_shortage(tx, sid, "water", now(w), 0, None)
        stl.change_ration(tx, sid, -1, "shortage", now(w), 0, None)
        stl.receive(tx, sid, {"water": 400, "food": 300}, "a convoy", now(w), 0, None)
    run(w, 2.5)
    ended = rows(w, "SHORTAGE_ENDED")
    assert [(e["payload"]["resource"], hhmm(e["at"])) for e in ended] == [("water", "07:00")]
    assert settlement(w)["shortages"] == []
    run(w, 48)                                                                # three good draws in a row
    up = [r for r in rows(w, "RATION_CHANGE") if r["payload"]["cause"] == "recovered"]
    assert [(u["payload"]["level_before"], u["payload"]["level_after"]) for u in up] == [(2, 3)]
    assert len([r for r in rows(w, "SETTLEMENT_DAY")]) == 3


def test_vacancies(settle):
    w = settle
    sid, pump, hal = w.id("pumpwell"), w.id("pump"), w.id("hal")
    with w.store.transaction() as tx:
        a = stl.add_vacancy(tx, sid, pump, "pump_operator", hal, now(w), 0, None)
        assert stl.add_vacancy(tx, sid, pump, "pump_operator", hal, now(w), 0, None) is None
        stl.add_vacancy(tx, sid, w.id("kitchen_work"), "cook", w.id("mae"), now(w), 0, None)
    assert a.payload["reason"] == "vacancy" and a.payload["old"] == []
    assert [(v["workplace_id"], v["role"]) for v in settlement(w)["vacancies"]] == sorted([(pump, "pump_operator"), (w.id("kitchen_work"), "cook")])
    with w.store.transaction() as tx:
        f = stl.remove_vacancy(tx, sid, pump, "pump_operator", hal, now(w), 0, None)
        assert stl.remove_vacancy(tx, sid, pump, "pump_operator", hal, now(w), 0, None) is None
    assert f.payload["reason"] == "filled" and len(settlement(w)["vacancies"]) == 1


def test_laws_and_their_cost_in_standing(settle):
    w = settle
    sid, g = w.id("pumpwell"), w.id("settlers")
    assert stl.laws_of(w.store, sid) == ["core:law/contamination_quarantine", "core:law/nightfall_curfew", "core:law/ration_law"]
    assert stl.law_def(w.store, sid, "ration_law").kind == "ration"
    assert stl.law_def(w.store, sid, "core:law/nightfall_curfew").name == "Nightfall Curfew"
    assert stl.law_def(w.store, sid, "firearms_discipline") is None           # not a law here
    with w.store.transaction() as tx:
        e = stl.apply_law(tx, sid, "ration_law", w.id("jude"), now(w), 0, None)
        q = stl.apply_law(tx, sid, "contamination_quarantine", w.id("otis"), now(w), 0, None)
        assert stl.apply_law(tx, sid, "firearms_discipline", w.id("jude"), now(w), 0, None) is None
    assert (e.payload["law_ref"], e.payload["kind"], e.actor_id) == ("core:law/ration_law", "ration", w.id("jude"))
    assert mind.standing_toward(w.store, g, w.id("jude")) == -1              # a punishing law costs standing
    assert mind.standing_toward(w.store, g, w.id("otis")) == 0               # quarantine protects; it does not punish
    assert q.payload["kind"] == "contamination"


def test_settlement_of_any_kind_of_id(settle):
    w = settle
    sid = w.id("pumpwell")
    for local in ("pumpwell", "pump", "yard", "brandt", "hal", "pc"):
        assert stl.settlement_of(w.store, w.id(local)) == sid, local
    assert stl.settlement_of(w.store, w.id("bunk_a")) is None              # a place, but not the settlement's
    assert stl.settlement_of(w.store, "zzz_000001") is None


def test_trade_terms_baseline_and_standing(settle):
    w = settle
    sid, g = w.id("pumpwell"), w.id("settlers")
    t = stl.trade_terms(w.store, sid, w.id("pc"))
    assert (t.willing, t.price_mult, t.trader_id, t.reasons) == (True, 1.0, w.id("lena"), [])   # the quartermaster
    with w.store.transaction() as tx:
        mind.adjust_group_standing(tx, g, w.id("pc"), -2, None, now(w), 0)
    t = stl.trade_terms(w.store, sid, w.id("pc"))
    assert (t.willing, t.price_mult) == (True, 1.5) and t.reasons == ["Pumpwell settlers thinks little of them."]
    with w.store.transaction() as tx:
        mind.adjust_group_standing(tx, g, w.id("pc"), -1, None, now(w), 0)
    t = stl.trade_terms(w.store, sid, w.id("pc"))
    assert (t.willing, t.price_mult) == (False, 0.0) and t.reasons == ["Pumpwell settlers will not deal with them."]


def test_trade_terms_from_the_traders_own_feelings(settle):
    w = settle
    with w.store.transaction() as tx:
        for _ in range(2):
            mind.relate(tx, w.id("lena"), w.id("jude"), "trust", -1, None, now(w), 0)
    t = stl.trade_terms(w.store, w.id("pumpwell"), w.id("jude"))
    assert (t.willing, t.price_mult, t.reasons) == (True, 1.25, ["Lena Kaminski does not trust them."])
    with w.store.transaction() as tx:
        for _ in range(2):
            mind.relate(tx, w.id("lena"), w.id("jude"), "resentment", 1, None, now(w), 0)
    t = stl.trade_terms(w.store, w.id("pumpwell"), w.id("jude"))
    assert not t.willing and "Lena Kaminski holds a grudge against them." in t.reasons


def test_ensure_timers(settle):
    w = settle
    with w.store.transaction() as tx:
        q = stl.ensure_timers(tx, w.id("pumpwell"), now(w), 0)
        assert stl.ensure_timers(tx, w.id("pumpwell"), now(w), 0) == []
    due = w.store.query_one("SELECT due_at FROM event_queue WHERE queue_id = ?", (q[0],))[0]
    assert hhmm(due) == "07:00" and due - now(w) == 2 * H
    assert stl.next_hour(now(w), 5) == now(w) + DAY                          # strictly after
