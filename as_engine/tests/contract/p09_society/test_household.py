"""Households (P9). Rules HH-01..07, CAS-007 (society/household.py).

The engine knows who somebody's child is, who heads a home, and which home a shortage hurts most.
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.society import household

from society_kit import DAY, now, rows

pytestmark = pytest.mark.phase(9)


def kill(w, local):
    at = now(w)
    with w.store.transaction() as tx:
        d = tx.commit_event(Event(type=EventType.DEATH, writer="physical.bodies", at=at, turn_index=0,
                                  payload={"body_id": w.id(local), "cause": "fell from the tower", "cause_event_id": None},
                                  writes=[WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": w.id(local)},
                                                      values={"alive": 0, "awareness": "dead", "dead_at": at})]))
        cascade.sweep(tx, [d], tx.canon.all("cascade"), at, 0)
    return d


def test_members_heads_and_dependents(settle):
    w = settle
    brandt = w.id("brandt")
    assert household.members(w.store, brandt) == sorted(w.id(x) for x in ("hal", "mae", "pip"))
    assert household.household_of(w.store, w.id("pip")) == brandt
    assert household.household_of(w.store, w.id("pc")) is None
    assert household.head_of(w.store, brandt) == w.id("hal")
    assert household.head_of(w.store, w.id("reyes")) == w.id("otis")
    assert household.dependents_of(w.store, w.id("hal")) == [w.id("pip")]
    assert household.dependents_of(w.store, w.id("iris")) == sorted([w.id("noah"), w.id("june2")])
    assert household.dependents_of(w.store, w.id("otis")) == []
    assert household.has_dependents(w.store, brandt) and not household.has_dependents(w.store, w.id("reyes"))


def test_the_head_falls_to_the_partner_then_the_eldest(settle):
    w = settle
    kill(w, "hal")
    assert household.head_of(w.store, w.id("brandt")) == w.id("mae")
    assert household.members(w.store, w.id("brandt")) == sorted([w.id("mae"), w.id("pip")])
    assert w.id("hal") in household.members(w.store, w.id("brandt"), living=False)
    kill(w, "mae")
    assert household.head_of(w.store, w.id("brandt")) is None      # an 8-year-old heads nothing
    assert household.dependents_of(w.store, w.id("hal")) == [w.id("pip")]


def test_households_of_a_settlement_and_the_worst_hit(settle):
    w = settle
    assert household.households_of(w.store, w.id("pumpwell")) == sorted(
        w.id(h) for h in ("brandt", "quintero", "oduya", "kaminski", "vance", "reyes", "ramos", "walsh", "salazar", "tate",
                          "lindqvist", "farrow"))
    assert household.worst_hit(w.store, w.id("pumpwell")) == w.id("vance")    # one adult, two small children


def test_a_death_grieves_the_household_and_opens_the_post(settle):
    w = settle
    d = kill(w, "rosa")
    ch = [r for r in rows(w, "HOUSEHOLD_CHANGE") if r["cause_event_id"] == d.event_id]
    assert len(ch) == 1 and ch[0]["rule_cited"] == "CAS-007"
    assert {k: ch[0]["payload"][k] for k in ("change", "actor_id", "grief_before", "grief_after")} == \
        {"change": "member_died", "actor_id": w.id("rosa"), "grief_before": 0, "grief_after": 1}
    missed = [r for r in rows(w, "SHIFT_MISSED") if r["rule_cited"] == "CAS-007"]
    assert [(m["payload"]["actor_id"], m["payload"]["reason"]) for m in missed] == [(w.id("rosa"), "dead")]
    assert w.store.query_one("SELECT COUNT(*) FROM work_assignments WHERE actor_id = ?", (w.id("rosa"),))[0] == 0


def test_apply_change_joins_leaves_and_refuses_nonsense(settle):
    w = settle
    hh = w.id("reyes")
    with w.store.transaction() as tx:
        j = household.apply_change(tx, hh, "member_joined", w.id("pc"), now(w), 0, None)     # the newcomer takes a bunk
    assert j.writer == "society.household" and j.actor_id == w.id("pc")
    row = w.store.query_one("SELECT role, guardian_of FROM household_members WHERE household_id = ? AND actor_id = ?", (hh, w.id("pc")))
    assert (row[0], row[1]) == ("lodger", "[]")
    assert household.household_of(w.store, w.id("pc")) == hh
    with w.store.transaction() as tx:
        household.apply_change(tx, hh, "member_left", w.id("pc"), now(w), 0, None)
    assert household.household_of(w.store, w.id("pc")) is None
    for args in (("member_joined", w.id("otis")), ("member_left", w.id("pc")), ("moved_house", w.id("otis"))):
        with pytest.raises(ValueError):
            with w.store.transaction() as tx:
                household.apply_change(tx, hh, args[0], args[1], now(w), 0, None)
    with pytest.raises(ValueError):
        with w.store.transaction() as tx:
            household.apply_change(tx, "hh_999999", "grief_eased", None, now(w), 0, None)


def test_grief_eases_a_week_after_the_last_change(settle):
    w = settle
    kill(w, "rosa")
    hh = w.id("quintero")
    t = now(w)
    with w.store.transaction() as tx:
        assert household.day(tx, hh, t + 6 * DAY, 0, None) is None
        e = household.day(tx, hh, t + 7 * DAY, 0, None)
    assert e.payload["change"] == "grief_eased" and (e.payload["grief_before"], e.payload["grief_after"]) == (1, 0)
    with w.store.transaction() as tx:
        assert household.day(tx, hh, t + 30 * DAY, 0, None) is None   # nothing left to ease
