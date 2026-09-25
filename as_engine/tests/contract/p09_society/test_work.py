"""Work and production (P9). Rules WORK-01..12 (society/work.py).

Workplaces run cycles; output depends on who actually worked, how hard, and on what machinery.
Skill decides who can cover a post; an injury decides who cannot.
"""

from __future__ import annotations

import json
import math

import pytest

from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.kernel import clock
from as_engine.society import work

from society_kit import DAY, H, injure, now, rows, run, workplace

pytestmark = pytest.mark.phase(9)


def test_keys_parse_and_refuse_garbage():
    assert work.parse_key("wkp_000001:pump_operator:act_000004:6") == ("wkp_000001", "pump_operator", "act_000004", 6)
    for bad in ("wkp_000001:pump_operator:act_000004", "a:b:c:d:e", "wkp_000001:pump_operator:act_000004:six"):
        with pytest.raises(ValueError):
            work.parse_key(bad)


def test_qualified_by_skill(settle):
    w = settle
    assert work.qualified(w.store, w.id("hal"), "pump_operator")          # mechanics 2
    assert not work.qualified(w.store, w.id("amos"), "pump_operator")     # a builder, no mechanics
    assert work.qualified(w.store, w.id("amos"), "watcher")               # anyone can watch
    assert work.qualified(w.store, w.id("mae"), "cook") and not work.qualified(w.store, w.id("wade"), "cook")


def test_able_and_why_not(settle):
    w = settle
    assert work.able(w.store, w.id("hal"), "pump_operator") == (True, "")   # asleep is able
    injure(w, "hal")
    assert work.able(w.store, w.id("hal"), "pump_operator") == (False, "hurt")
    assert work.able(w.store, w.id("hal"), "watcher") == (True, "")         # a hurt arm can still keep watch
    injure(w, "kit", anatomy="leg_l")
    assert work.able(w.store, w.id("kit"), "cook") == (True, "")            # a leg is not an arm


def test_overlap_of_a_shift_with_a_window():
    d = 1100 * DAY
    assert work.overlap_h(6, 18, d + 6 * H, d + 18 * H) == 12
    assert work.overlap_h(18, 6, d + 6 * H, d + 18 * H) == 0
    assert work.overlap_h(18, 6, d - 6 * H, d + 6 * H) == 12                 # the night that began the day before
    assert work.overlap_h(6, 20, d - H, d + 7 * H) == 1                      # the cooks' first hour counts (kitchen 23 -> 07)
    assert work.overlap_h(0, 0, d, d + 12 * H) == 12                         # a whole-day post
    assert work.shifts_overlap(6, 18, 17, 1) and not work.shifts_overlap(6, 18, 18, 6)


def test_crew_and_staffing(settle):
    w = settle
    t = now(w)                                                               # 05:00: the night crew is ending
    assert work.crew(w.store, w.id("pump"), t - 11 * H, t + H) == sorted([(w.id("ben"), "pump_operator"), (w.id("cora"), "pump_operator")],
                                                                         key=lambda x: (x[1], x[0]))
    assert work.staffed_fraction(["pump_operator", "pump_operator"], [("a", "pump_operator")]) == 0.5
    assert work.staffed_fraction(["pump_operator", "pump_operator"], [("a", "pump_operator"), ("b", "pump_operator"), ("c", "pump_operator")]) == 1.0
    assert work.staffed_fraction(["cook", "watcher"], [("a", "watcher")]) == 0.5
    assert work.staffed_fraction([], []) == 1.0


def test_pick_cover_never_takes_the_player(settle):
    w = settle
    # Owen has mechanics 2 and no post — the most rested qualified body in the settlement — but code never
    # assigns a human-controlled body (SEL-06). Ben is the off-shift pump hand with the lower id.
    assert work.pick_cover(w.store, w.id("pump"), "pump_operator", 6, 18, w.id("hal")) == w.id("ben")
    assert work.pick_cover(w.store, w.id("pump"), "pump_operator", 18, 6, w.id("ben")) == w.id("hal")
    assert work.pick_cover(w.store, w.id("kitchen_work"), "cook", 6, 20, w.id("mae")) is None   # nobody else can cook


def test_cycle_output_follows_crew_efficiency_and_machinery(settle):
    w = settle
    run(w, 1.5)
    first = [r for r in rows(w, "PRODUCTION_CYCLE") if r["payload"]["site_type"] == "water_pump"][0]
    p = first["payload"]
    assert (p["staffed"], p["efficiency"], p["condition_factor"], p["spite"], p["output"]) == (1.0, 1.0, 1.0, 1.0, {"water": 31})
    assert (p["window_start"], p["window_end"]) == (first["at"] - 12 * H, first["at"])
    assert workplace(w, "pump")["next_due_at"] == first["at"] + 12 * H
    got = [r for r in rows(w, "STORES_CHANGE") if r["cause_event_id"] == first["event_id"]]
    assert got and got[0]["payload"]["changes"] == {"water": 31}


def test_worn_machinery_makes_less(settle):
    w = settle
    with w.store.transaction() as tx:
        e = work.adjust(tx, w.id("pump"), "machinery_condition", -40, now(w), 0, None)        # 70 -> 30
    assert (e.payload["old"], e.payload["new"], e.payload["reason"]) == (70, 30, "cascade")
    run(w, 1.5)
    p = [r for r in rows(w, "PRODUCTION_CYCLE") if r["payload"]["site_type"] == "water_pump"][0]["payload"]
    assert p["condition_factor"] == 0.6 and p["output"] == {"water": math.floor(31 * 0.6 + 1e-9)}, \
        "B6 (C04): 30 of the 50 full output needs is three fifths, never half for nothing"


def test_broken_machinery_makes_nothing(settle):
    """WORK-05 (B6, fidelity C04): at condition 0 the pump is broken — no water, nothing burned,
    and the stall says why."""
    w = settle
    with w.store.transaction() as tx:
        work.adjust(tx, w.id("pump"), "machinery_condition", -500, now(w), 0, None)
    run(w, 1.5)
    first = [r for r in rows(w, "PRODUCTION_CYCLE") if r["payload"]["site_type"] == "water_pump"][0]
    assert (first["payload"]["condition_factor"], first["payload"]["output"], first["payload"]["inputs_used"]) == (0.0, {"water": 0}, {})
    assert json.loads(workplace(w, "pump")["stall_reasons"]) == ["broken"]
    assert not [r for r in rows(w, "STORES_CHANGE") if r["cause_event_id"] == first["event_id"]]


def test_a_pump_runs_on_what_it_has(settle):
    """WORK-05 (B6, fidelity C04): a fuelled pump burns its fuel out of the settlement's stores —
    one draw, in the same ledger as everything else — makes what the fuel allows, and stops when
    the fuel is gone."""
    w = settle
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.WORKPLACE_CHANGE, writer="society.work", at=now(w), turn_index=0,
                              payload={"workplace_id": w.id("pump"), "field": "inputs", "reason": "test"},
                              writes=[WriteRecord(op=WriteOp.UPDATE, table="workplaces", key={"workplace_id": w.id("pump")},
                                                  values={"inputs": {"fuel": 30}})]))
    run(w, 30)
    cyc = [r for r in rows(w, "PRODUCTION_CYCLE") if r["payload"]["site_type"] == "water_pump"][:3]
    got = [(c["payload"]["input_factor"], c["payload"]["inputs_used"], c["payload"]["output"]) for c in cyc]
    third = round(10 / 30, 10)
    assert [(round(f, 10), u, o) for f, u, o in got] == [
        (1.0, {"fuel": 30.0}, {"water": 31}),
        (third, {"fuel": 10.0}, {"water": math.floor(31 * (10 / 30) + 1e-9)}),
        (0.0, {}, {"water": 0})], "40 fuel: a full cycle, a third of one, then nothing"
    drawn = [r["payload"]["changes"] for r in rows(w, "STORES_CHANGE") if r["payload"]["reason"] == "production_input"]
    assert drawn == [{"fuel": -30}, {"fuel": -10}]
    assert json.loads(workplace(w, "pump")["stall_reasons"]) == ["no_fuel"]


def test_adjust_clamps_and_refuses(settle):
    w = settle
    with w.store.transaction() as tx:
        assert work.adjust(tx, w.id("pump"), "efficiency", 0.9, now(w), 0, None).payload["new"] == 1.5
        assert work.adjust(tx, w.id("pump"), "efficiency", 0.1, now(w), 0, None) is None           # already at the cap
        assert work.adjust(tx, w.id("pump"), "machinery_condition", -500, now(w), 0, None).payload["new"] == 0
    for field, wid in (("output", w.id("pump")), ("efficiency", "wkp_999999")):
        with pytest.raises(ValueError):
            with w.store.transaction() as tx:
                work.adjust(tx, wid, field, 1, now(w), 0, None)


def test_assign_cover_records_where_the_cover_came_from(settle):
    w = settle
    with w.store.transaction() as tx:
        e = work.assign_cover(tx, w.id("ben"), w.id("pump"), "pump_operator", 6, 18, w.id("hal"), now(w), 0, None)
    assert e.type.value == "ROLE_ASSIGNED" and e.actor_id == w.id("ben")
    assert {k: e.payload[k] for k in ("covering_for", "shift_start_hh", "shift_end_hh", "is_cover", "left_workplace_id")} == \
        {"covering_for": w.id("hal"), "shift_start_hh": 6, "shift_end_hh": 18, "is_cover": True, "left_workplace_id": w.id("pump")}
    with w.store.transaction() as tx:
        e2 = work.assign_cover(tx, w.id("amos"), w.id("watch"), "watcher", 18, 6, w.id("kit"), now(w), 0, None)
    assert e2.payload["left_workplace_id"] is None                          # Amos had no post to leave


def test_miss_shift_refuses_a_fit_worker(settle):
    w = settle
    key = f"{w.id('pump')}:pump_operator:{w.id('hal')}:6"
    with w.store.transaction() as tx:
        assert work.miss_shift(tx, key, "injured", now(w), 0, None) is None
        assert work.miss_shift(tx, f"{w.id('pump')}:pump_operator:{w.id('amos')}:6", "injured", now(w), 0, None) is None   # no such post


def test_shift_start_only_for_the_able(settle):
    w = settle
    with w.store.transaction() as tx:
        e = work.shift_start(tx, w.id("rosa"), w.id("pump"), "pump_operator", now(w), 0, None)
    assert e.payload == {"workplace_id": w.id("pump"), "role": "pump_operator", "actor_id": w.id("rosa")}
    injure(w, "rosa")
    with w.store.transaction() as tx:
        assert work.shift_start(tx, w.id("rosa"), w.id("pump"), "pump_operator", now(w), 0, None) is None


def test_ensure_timers_starts_every_workplace_once(settle):
    w = settle
    with w.store.transaction() as tx:
        q = work.ensure_timers(tx, w.id("pumpwell"), now(w), 0)
        assert work.ensure_timers(tx, w.id("pumpwell"), now(w), 0) == []
    assert len(q) == 3
    due = {r[0]: r[1] for r in w.store.query("SELECT subject_id, due_at FROM event_queue WHERE type = 'PRODUCTION_CYCLE' AND status = 'pending'")}
    assert due == {w.id("pump"): workplace(w, "pump")["next_due_at"], w.id("kitchen_work"): workplace(w, "kitchen_work")["next_due_at"],
                   w.id("watch"): workplace(w, "watch")["next_due_at"]}


def test_an_unstaffed_workplace_stalls(settle):
    w = settle
    for who in ("mae", "iris"):
        injure(w, who)                                                        # both cooks cut
    run(w, 3)                                                                 # the 07:00 kitchen cycle
    k = [r for r in rows(w, "PRODUCTION_CYCLE") if r["payload"]["site_type"] == "kitchen"][0]
    assert (k["payload"]["staffed"], k["payload"]["output"]) == (0.0, {"food": 0})
    assert workplace(w, "kitchen_work")["stall_reasons"] == '["unstaffed"]'
