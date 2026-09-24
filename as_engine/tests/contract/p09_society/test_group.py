"""Groups: tension, drift, animosity, loyalty, standing (P9). Rules GRP-01..12, STAND-01..02, SOC-02
(society/group.py, mind/mind.py).

Relationships move while the player is nowhere near (SOC-02); resentment has a cost at work;
crossing a loyalty threshold starts a plan, never an instant betrayal.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import RelationAxis
from as_engine.contracts.events import EventType
from as_engine.mind import mind
from as_engine.society import group, settlement as stl

from society_kit import DAY, H, hhmm, now, rel, rows, run

pytestmark = pytest.mark.phase(9)

A = RelationAxis


def resent(w, a, b, n):
    with w.store.transaction() as tx:
        for _ in range(n):
            mind.relate(tx, w.id(a), w.id(b), A.RESENTMENT, 1, None, now(w), 0)


def test_members_and_the_leader(settle):
    w = settle
    g = w.id("settlers")
    assert len(group.members(w.store, g)) == 24 and group.leader_of(w.store, g) == w.id("tomas")


def test_tension_rises_boils_over_and_leaves_resentment(settle):
    w = settle
    a, b = w.id("jude"), w.id("amos")
    with w.store.transaction() as tx:
        ev = group.adjust_tension(tx, a, b, 60, "an argument over tools", now(w), 0, None)
    assert [e.type for e in ev] == [EventType.TENSION_CHANGE] and group.tension_of(w.store, a, b) == 60
    assert group.tension_of(w.store, b, a) == 0                               # tension is one-way
    with w.store.transaction() as tx:
        ev = group.adjust_tension(tx, a, b, 15, "he did it again", now(w), 0, None)
    assert [e.type for e in ev] == [EventType.TENSION_CHANGE, EventType.ESCALATION, EventType.RELATION_CHANGE]
    assert ev[1].payload == {"a_id": a, "b_id": b, "form": "verbal", "score": 75} and ev[1].cause_event_id == ev[0].event_id
    assert rel(w, "jude", "amos")["resentment"] == 1
    with w.store.transaction() as tx:
        assert group.adjust_tension(tx, a, b, 50, "x", now(w), 0, None)[0].payload["new"] == 100
        assert group.adjust_tension(tx, a, b, 5, "x", now(w), 0, None) == []   # already at 100
        assert [e.type for e in group.adjust_tension(tx, a, b, -40, "x", now(w), 0, None)] == [EventType.TENSION_CHANGE]


def test_boiling_over_toward_a_group_turns_on_its_leader(settle):
    w = settle
    with w.store.transaction() as tx:
        group.adjust_tension(tx, w.id("lena"), w.id("settlers"), 70, "the ration list", now(w), 0, None)
    assert rel(w, "lena", "tomas")["resentment"] == 1


def test_contacts_and_pairs(settle):
    w = settle
    g = w.id("settlers")
    assert group.contacts(w.store, w.id("finn"), g) == sorted([w.id("gus"), w.id("kit")])      # watch crew + a friend
    assert group.contacts(w.store, w.id("hal"), g) == sorted([w.id(x) for x in ("mae", "pip", "rosa", "ben", "cora")])
    prs = group.pairs(w.store, g)
    assert prs == sorted(prs) and all(a < b for a, b in prs)
    assert all(w.id("pc") not in p for p in prs)                             # the PC is never a drift pair
    assert (min(w.id("finn"), w.id("kit")), max(w.id("finn"), w.id("kit"))) in prs


def test_soc_02_relationships_drift_with_the_player_away(settle):
    w = settle
    before = {(r[0], r[1]): tuple(r[2:]) for r in w.store.query(
        "SELECT from_id, to_id, trust, affection, resentment FROM relationships")}
    run(w, 63)                                                                # three group days (20:00)
    days = rows(w, "GROUP_DAY")
    assert [hhmm(d["at"]) for d in days] == ["20:00"] * 3
    drift = [r for r in rows(w, "RELATION_CHANGE") if r["cause_event_id"] in {d["event_id"] for d in days}]
    assert len(drift) >= 10, "a settlement's relationships move on their own"
    assert all(w.id("pc") not in (d["payload"]["from_id"], d["payload"]["to_id"]) for d in drift)
    assert all(abs(d["payload"]["delta"]) == 1 for d in drift)
    after = {(r[0], r[1]): tuple(r[2:]) for r in w.store.query("SELECT from_id, to_id, trust, affection, resentment FROM relationships")}
    assert after != before
    assert all(v[0] <= 2 and v[1] <= 2 for k, v in after.items() if before.get(k, (0, 0, 0))[0] < 2), "drift never pushes past +2"
    assert rows(w, "PLAYER_INPUT") == []


def test_sour_ties_sour_further(settle):
    w = settle
    resent(w, "rosa", "hal", 1)
    run(w, 15 + 24 * 6)                                                       # a week of shared shifts
    assert rel(w, "rosa", "hal")["resentment"] >= 2


def test_animosity_at_work_is_a_check_and_it_costs(settle):
    w = settle
    resent(w, "rosa", "hal", 3)                                              # Rosa can hardly stand working beside Hal
    run(w, 13.5)                                                              # the 18:00 day-shift cycle
    checks = [r for r in rows(w, "CHECK_RESOLVED") if r["payload"]["def_id"] == "animosity"]
    assert [c["actor_id"] for c in checks] == [w.id("rosa")]                  # only the one who resents rolls
    c = checks[0]["payload"]
    assert (c["attribute"], c["resistance"]) == ("I", 3)
    day = [r for r in rows(w, "PRODUCTION_CYCLE") if r["payload"]["site_type"] == "water_pump" and hhmm(r["at"]) == "18:00"][0]
    expected = {"clean": 1.0, "cost": 1.0, "fail": 0.9, "break": 0.75}[c["band"]]
    assert day["payload"]["spite"] == expected
    if c["band"] in ("fail", "break"):
        assert group.tension_of(w.store, w.id("rosa"), w.id("hal")) == (10 if c["band"] == "fail" else 20)


def test_defection_pressure_terms(settle):
    w = settle
    g = w.id("settlers")
    p = group.defection_pressure(w.store, w.id("iris"), g)
    assert (p.value, p.terms) == (0, {"grievance": 0, "deprivation": 0, "dependents": 0, "endangered": 0, "viability": 0,
                                      "leader": 0, "standing": 0})
    with w.store.transaction() as tx:
        stl.change_ration(tx, w.id("pumpwell"), -2, "x", now(w), 0, None)       # level 1
        stl.adjust(tx, w.id("pumpwell"), "morale", -4, now(w), 0, None)         # morale 1
        group.adjust_tension(tx, w.id("iris"), g, 45, "x", now(w), 0, None)
    resent(w, "iris", "tomas", 2)
    p = group.defection_pressure(w.store, w.id("iris"), g)
    assert p.terms == {"grievance": 2, "deprivation": 2, "dependents": 1, "endangered": 0, "viability": 2, "leader": 1, "standing": 0}
    assert p.value == 8


def test_loyalty_check_starts_a_plan_not_a_betrayal(settle):
    w = settle
    g = w.id("settlers")
    with w.store.transaction() as tx:
        stl.change_ration(tx, w.id("pumpwell"), -2, "x", now(w), 0, None)
        out = group.loyalty_check(tx, w.id("iris"), g, "test", now(w), 0, None)
    lc = [e for e in out if e.type == EventType.LOYALTY_CHECK][0]
    assert (lc.payload["pressure"], lc.payload["threshold"], lc.payload["result"]) == (3, 4, "wavering")
    with w.store.transaction() as tx:
        stl.adjust(tx, w.id("pumpwell"), "morale", -2, now(w), 0, None)        # morale 3: the place looks doomed
        out = group.loyalty_check(tx, w.id("iris"), g, "test", now(w), 0, None)
    lc = [e for e in out if e.type == EventType.LOYALTY_CHECK][0]
    assert (lc.payload["pressure"], lc.payload["result"]) == (4, "plans_to_leave")
    loops = w.store.query("SELECT kind, text FROM open_loops WHERE holder_id = ?", (w.id("iris"),))
    assert [(r[0], r[1]) for r in loops] == [("plan", "Leave Pumpwell settlers before it is too late.")]
    assert w.store.query_one("SELECT status FROM group_members WHERE group_id = ? AND actor_id = ?", (g, w.id("iris")))[0] == "member"
    with w.store.transaction() as tx:
        assert group.loyalty_check(tx, w.id("pc"), g, "test", now(w), 0, None) == []    # the player decides for the PC


def test_stand_01_02_standing(settle):
    w = settle
    g, pc = w.id("settlers"), w.id("pc")
    assert mind.standing_toward(w.store, g, pc) == 0
    with w.store.transaction() as tx:
        e = mind.adjust_group_standing(tx, g, pc, -2, None, now(w), 0)
        big = mind.adjust_group_standing(tx, g, pc, -9, e.event_id, now(w), 0)
        assert mind.adjust_group_standing(tx, g, pc, -1, None, now(w), 0) is None
    assert (e.type, e.writer, e.payload) == (EventType.STANDING_CHANGE, "society.group",
                                             {"group_id": g, "actor_id": pc, "old": 0, "new": -2, "delta": -2})
    assert big.payload["new"] == -5 and mind.standing_toward(w.store, g, pc) == -5
    import json
    reasons = json.loads(w.store.query_one("SELECT reasons FROM group_standing WHERE group_id = ? AND actor_id = ?", (g, pc))[0])
    assert reasons == [e.event_id]
    with pytest.raises(ValueError):
        with w.store.transaction() as tx:
            mind.adjust_group_standing(tx, "grp_999999", pc, 1, None, now(w), 0)


def test_the_group_day_reschedules_itself(settle):
    w = settle
    run(w, 16)                                                                # past 20:00
    d = rows(w, "GROUP_DAY")[0]
    assert w.store.query_one("SELECT next_due_at FROM groups WHERE group_id = ?", (w.id("settlers"),))[0] == d["at"] + DAY
    q = w.store.query("SELECT due_at FROM event_queue WHERE type = 'GROUP_DAY' AND status = 'pending'")
    assert [r[0] for r in q] == [d["at"] + DAY]
