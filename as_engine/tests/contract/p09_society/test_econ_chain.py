"""ECON-01: one injured worker reaches morale, unprompted (P9). Rules ECON-01, CAS-01..09, WORK-05..09,
STL-03..05, GRP-02, GRP-08.

pump_settlement is balanced on a knife edge: the pump makes exactly what 24 people drink. The test
cuts Hal's arm and lets the world run. Nothing else is scripted: every hop below is a content rule
(core cascade/economy.yaml) applied by code, or the settlement's own daily clock.
"""

from __future__ import annotations

import pytest

from society_kit import DAY, H, cause_chain, heal, hhmm, injure, now, rows, run, settlement, workplace

pytestmark = pytest.mark.phase(9)


def by_rule(w, type_, rule):
    return [r for r in rows(w, type_) if r["rule_cited"] == rule]


def test_one_injury_reaches_rations_and_tension(settle):
    w = settle
    t0 = now(w)
    harm = injure(w, "hal")
    run(w, 15)                                                      # 05:00 -> 20:00

    missed = by_rule(w, "SHIFT_MISSED", "CAS-001")
    assert [(m["payload"]["actor_id"], m["payload"]["reason"], hhmm(m["at"])) for m in missed] == [(w.id("hal"), "injured", "06:00")]
    assert missed[0]["cause_event_id"] == harm.event_id              # the scheduled effect still names the injury

    cover = by_rule(w, "ROLE_ASSIGNED", "CAS-002")
    assert len(cover) == 1 and cover[0]["payload"]["actor_id"] == w.id("ben")      # the off-shift pump hand with fewest hours
    assert cover[0]["payload"]["covering_for"] == w.id("hal") and cover[0]["payload"]["left_workplace_id"] == w.id("pump")
    assert cover[0]["cause_event_id"] == missed[0]["event_id"]

    slow = by_rule(w, "WORKPLACE_CHANGE", "CAS-003")
    assert [(s["payload"]["field"], s["payload"]["old"], s["payload"]["new"]) for s in slow] == [("efficiency", 1.0, 0.75)]
    assert workplace(w, "pump")["efficiency"] == 0.75

    short = by_rule(w, "SHORTAGE", "CAS-004")
    assert [(s["payload"]["resource"], hhmm(s["at"])) for s in short] == [("water", "18:00")]
    cycle = w.store.query_one("SELECT payload FROM events WHERE event_id = ?", (short[0]["cause_event_id"],))
    import json
    cycle = json.loads(cycle[0])
    assert cycle["site_type"] == "water_pump" and cycle["efficiency"] == 0.75 and cycle["output"] == {"water": 23}

    cut = by_rule(w, "RATION_CHANGE", "CAS-005")
    assert [(c["payload"]["level_before"], c["payload"]["level_after"]) for c in cut] == [(3, 2)]
    assert settlement(w)["ration_level"] == 2 and settlement(w)["shortages"] == ["water"]

    tense = by_rule(w, "TENSION_CHANGE", "CAS-006")
    heads = sorted(t["payload"]["a_id"] for t in tense)
    assert heads == sorted(w.id(x) for x in ("hal", "rosa", "ben", "wade", "iris", "jude"))   # the heads with children at home
    assert {t["payload"]["b_id"] for t in tense} == {w.id("settlers")}
    assert w.id("pc") not in heads

    loyal = by_rule(w, "LOYALTY_CHECK", "CAS-006")                  # scheduled an hour after the cut
    assert [(c["payload"]["actor_id"], hhmm(c["at"])) for c in loyal] == [(w.id("iris"), "19:00")]   # alone with two small children
    assert loyal[0]["payload"]["result"] in ("stays", "wavering", "plans_to_leave")
    assert now(w) == t0 + 15 * H


def test_the_chain_reaches_morale_the_next_morning(settle):
    w = settle
    injure(w, "hal")
    run(w, 27)                                                      # to 08:00 the next day
    drops = [r for r in rows(w, "SETTLEMENT_CHANGE") if r["payload"]["field"] == "morale"]
    assert [(d["payload"]["old"], d["payload"]["new"], d["payload"]["reason"]) for d in drops] == [(5, 4, "rations")]
    day = [r for r in rows(w, "SETTLEMENT_DAY") if r["at"] == drops[0]["at"]][0]
    assert day["payload"]["ration_level"] == 2 and drops[0]["cause_event_id"] == day["event_id"]


def test_every_hop_can_be_walked_back_to_the_injury(settle):
    w = settle
    harm = injure(w, "hal")
    run(w, 15)
    slow = by_rule(w, "WORKPLACE_CHANGE", "CAS-003")[0]
    chain = [t for _e, t in cause_chain(w, slow["event_id"])]
    assert chain[:4] == ["WORKPLACE_CHANGE", "ROLE_ASSIGNED", "SHIFT_MISSED", "HARM"]
    assert cause_chain(w, slow["event_id"])[3][0] == harm.event_id
    tension = by_rule(w, "TENSION_CHANGE", "CAS-006")[0]
    assert [t for _e, t in cause_chain(w, tension["event_id"])][:4] == ["TENSION_CHANGE", "RATION_CHANGE", "SHORTAGE", "PRODUCTION_CYCLE"]


def test_without_the_injury_nothing_happens(settle):
    w = settle
    run(w, 27)
    assert rows(w, "SHIFT_MISSED") == [] and rows(w, "SHORTAGE") == [] and rows(w, "RATION_CHANGE") == []
    s = settlement(w)
    assert (s["ration_level"], s["morale"], s["shortages"]) == (3, 5, [])
    assert workplace(w, "pump")["efficiency"] == 1.0


def test_a_worker_who_is_fit_again_by_the_shift_does_not_miss_it(settle):
    w = settle
    injure(w, "hal")
    heal(w, "hal")
    run(w, 2)
    assert rows(w, "SHIFT_MISSED") == [] and rows(w, "ROLE_ASSIGNED") == []
    notes = [dict(r) for r in w.store.query("SELECT findings FROM audit_log WHERE gate = 'G10-cascade' AND producer = 'society.work'")]
    assert any("shift_not_missed" in n["findings"] for n in notes)


def test_nobody_free_to_cover_puts_the_post_on_the_vacancies(settle):
    w = settle
    for who in ("ben", "cora", "hal"):                              # the whole off-shift crew is hurt too
        injure(w, who)
    run(w, 13)                                                      # to 18:00
    assert [r for r in rows(w, "ROLE_ASSIGNED") if r["payload"]["covering_for"] == w.id("hal")] == []   # nobody free by day
    vac = settlement(w)["vacancies"]
    assert {(v["workplace_id"], v["role"], v["for_actor"]) for v in vac} >= {(w.id("pump"), "pump_operator", w.id("hal"))}
    day = [r for r in rows(w, "PRODUCTION_CYCLE") if r["payload"]["site_type"] == "water_pump" and hhmm(r["at"]) == "18:00"][0]
    # Rosa worked the day alone, and at 18:00 she was pulled onto Ben's night shift as well (CAS-002/003):
    assert (day["payload"]["staffed"], day["payload"]["efficiency"], day["payload"]["output"]) == (0.5, 0.75, {"water": 11})


def test_the_cover_ends_when_the_worker_returns_and_the_pump_recovers(settle):
    w = settle
    injure(w, "hal")
    run(w, 15)
    heal(w, "hal")
    run(w, 12)                                                      # through the 06:00 cycle
    released = rows(w, "ROLE_RELEASED")
    assert [(r["payload"]["actor_id"], r["payload"]["covering_for"], r["payload"]["reason"]) for r in released] == \
        [(w.id("ben"), w.id("hal"), "returned")]
    assert w.store.query_one("SELECT COUNT(*) FROM work_assignments WHERE covering_for IS NOT NULL")[0] == 0
    rec = [r for r in rows(w, "WORKPLACE_CHANGE") if r["payload"]["reason"] == "recovering"]
    assert rec and rec[-1]["payload"]["new"] == 1.0 and workplace(w, "pump")["efficiency"] == 1.0
