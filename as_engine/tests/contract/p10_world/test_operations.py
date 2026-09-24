"""People go out (P10). Rules OPS-01..03, OPS-08 (world/worldmove.py; fidelity C01, C11). The
first aid on the road is in test_world_day.py; DECON in test_ghosts.py.

Every day a settlement may send a few of its people out — to scavenge, to walk a patrol, to trade —
and a hostile band may raid. Who goes is who is free; where they go is what is there; what happens
to them depends on how thick the dead are where they go. A trip leaves the marks a trip leaves,
and what it brings home is in the stores.
"""

from __future__ import annotations

import asyncio
import json
import math

import pytest
from world_kit import (
    REPO_PACKS,
    WORLD_PC,
    H,
    all_rows,
    area,
    now,
    one,
    rows,
    run,
    settlement,
    tune,
    turn,
)

from as_engine.contracts.settings import EngineConfig, RunSettings
from as_engine.world import hordes, worldmove

pytestmark = pytest.mark.phase(10)

NONE = {"scavenge": 0.0, "patrol": 0.0, "trade_run": 0.0, "raid": 0.0}


# --------------------------------------------------------------------------- helpers
def only_kind(s, kind, **world):
    """Every settlement that can go out goes out on ``kind`` today (and nothing else)."""
    tune(s, world={"op_chance": NONE | {kind: 1.0}, "op_leg_h": 2.0, "op_dwell_h": 3.0, **world})


def safe_roads(s):
    """No dead in any district, so nobody on a trip gets hurt (OPS-03's harm is the district's density)."""
    with s.store.transaction() as tx:
        for z in [r["zone_id"] for r in all_rows(s, "SELECT zone_id FROM zones ORDER BY zone_id")]:
            for t, (a, d) in hordes.pool(tx, z).items():
                if a or d:
                    hordes.change(tx, z, t, -a, -d, "test", now(s), turn(s), None)


def plan(s):
    with s.store.transaction() as tx:
        return worldmove.plan_operations(tx, s.rng, now(s), turn(s), None)


def ops(s, status="active") -> list[dict]:
    out = all_rows(s, "SELECT * FROM operations WHERE status = ? ORDER BY op_id", (status,))
    for o in out:
        o["participants"], o["route"] = json.loads(o["participants"]), json.loads(o["route"])
        o["outcome"] = json.loads(o["outcome"]) if o["outcome"] else None
    return out


def op(s, op_id) -> dict:
    [o] = [x for x in ops(s, "active") + ops(s, "done") if x["op_id"] == op_id]
    return o


def place_of(s, body):
    r = one(s, "SELECT place_id FROM positions WHERE body_id = ?", (body,))
    return None if r is None else r["place_id"]


def zone_of(s, place):
    return one(s, "SELECT zone_id FROM places WHERE place_id = ?", (place,))["zone_id"]


def hub(s, zone_id):
    return one(s, "SELECT p.place_id FROM places p JOIN zones z ON z.zone_id = p.zone_id AND z.name = p.name "
                  "WHERE p.zone_id = ? AND p.kind = 'street'", (zone_id,))["place_id"]


def traces_at(s, place, kind):
    return [r["payload"]["text"] for r in rows(s, "TRACE_CREATED") if r["payload"]["place_id"] == place
            and r["payload"]["kind"] == kind]


def stores(s, sid) -> dict:
    return settlement(s, sid)["stores"]


# =========================================================================== OPS-01 / OPS-08
def test_who_goes_out_and_how_they_leave(gw):
    """OPS-01: at most one outing per settlement a day, only from settlements off screen, crewed by
    free, able, living members who are not the player and not on the council; OPS-08: the
    operation is written, everyone walks to their district's hub first, and the arrival is timed."""
    s = gw
    only_kind(s, "scavenge")
    near = area(s)
    stl_sites = {r["place_id"] for r in all_rows(s, "SELECT place_id FROM settlements")}
    evs = plan(s)
    made = ops(s)
    assert made, "no settlement went out"
    assert len({o["route"][0] for o in made}) == len(made), "one outing per settlement"
    W = s.store.rules.world
    for o in made:
        st = one(s, "SELECT * FROM settlements WHERE place_id = ?", (o["route"][0],))
        assert st["place_id"] not in near and st["lockdown"] == 0
        assert o["group_id"] == st["group_id"] and o["kind"] == "scavenge" and o["status"] == "active"
        lo, hi = W.op_party
        assert 1 <= len(o["participants"]) <= hi
        for p in o["participants"]:
            m = one(s, "SELECT status FROM group_members WHERE group_id = ? AND actor_id = ?", (o["group_id"], p))
            assert m["status"] == "member"
            assert one(s, "SELECT controller FROM actors WHERE actor_id = ?", (p,))["controller"] != "human"
            assert one(s, "SELECT alive FROM bodies WHERE body_id = ?", (p,))["alive"] == 1
        dest = one(s, "SELECT * FROM places WHERE place_id = ?", (o["route"][1],))
        assert dest["kind"] == "building" and dest["parent_id"] is None and dest["place_id"] not in stl_sites
        [dep] = [e for e in evs if e.type == "FACTION_OPERATION" and e.payload["op_id"] == o["op_id"]]
        assert dep.payload == {"op_id": o["op_id"], "group_id": o["group_id"], "kind": "scavenge",
                               "participants": o["participants"], "destination": o["route"][1], "status": "active",
                               "step": "depart"}
        for p in o["participants"]:
            [mv] = [e for e in evs if e.type == "MOVE" and e.actor_id == p]
            assert mv.cause_event_id == dep.event_id and place_of(s, p) == hub(s, zone_of(s, o["route"][0]))
        assert o["next_due_at"] == now(s) + int(W.op_leg_h * H)
        [row] = [dict(r) for r in s.store.query("SELECT * FROM event_queue WHERE type = 'OPERATION_STEP' AND subject_id = ? "
                                                "AND status = 'pending'", (o["op_id"],))]
        assert row["due_at"] == o["next_due_at"] and json.loads(row["payload"]) == {"op_id": o["op_id"], "step": "arrive"}
    busy = [p for o in made for p in o["participants"]]
    assert len(busy) == len(set(busy)), "nobody is on two outings"
    ghosts = one(s, "SELECT group_id, leader_id FROM groups WHERE content_ref = 'core:faction/ghosts'")
    seats = [ld.seat for ld in s.store.canon.get("core:faction/ghosts").leaders if ld.seat]
    council = {ghosts["leader_id"]} | {r["actor_id"] for r in all_rows(
        s, "SELECT actor_id, role FROM group_members WHERE group_id = ?", (ghosts["group_id"],)) if r["role"] in seats}
    assert len(council) == len(seats) and not council & set(busy), "the council does not go scavenging"


def test_a_scavenging_trip_there_and_back(gw):
    """OPS-02 / OPS-03: they arrive (the building is laid out as they walk in), take up to three
    loose things into their packs and leave the marks a search leaves; after the dwell they walk
    home, and what they found (2..8 food and water each, when they found anything) goes into the
    stores ('scavenged'). A trip a day until one comes home with something."""
    s = gw
    only_kind(s, "scavenge")
    safe_roads(s)
    hauled = False
    for day in range(6):
        plan(s)
        mine = ops(s)
        assert mine, f"day {day}: nobody went out"
        o = mine[0]
        home = one(s, "SELECT settlement_id FROM settlements WHERE place_id = ?", (o["route"][0],))["settlement_id"]
        run(s, 2.1)
        dest = o["route"][1]
        assert all(place_of(s, p) == dest for p in o["participants"])
        assert one(s, "SELECT layout_generated FROM places WHERE place_id = ?", (dest,))["layout_generated"] == 1
        assert "Boot prints in the dust, a few people, coming and going." in traces_at(s, dest, "tracks")
        marks = ",".join("?" * len(o["participants"]))
        carried = [r for r in all_rows(s, f"SELECT * FROM items WHERE holder_slot = 'pack' AND holder_body IN ({marks})",
                                       tuple(o["participants"])) if r["origin"] == "loot"]
        assert len(carried) <= 3 * (day + 1)
        haul = op(s, o["op_id"])["outcome"]["haul"]
        n = len(o["participants"])
        if haul:
            assert set(haul) == {"food", "water"} and haul["food"] % n == 0 and haul["water"] % n == 0
            assert 2 * n <= haul["food"] <= 8 * n and 2 * n <= haul["water"] <= 8 * n
        else:
            assert haul == {}
        run(s, 3.1)
        done = op(s, o["op_id"])
        assert done["status"] == "done" and done["next_due_at"] is None
        back = [e for e in rows(s, "MOVE") if e["cause_event_id"] in {r["event_id"] for r in rows(s, "TIMER_FIRED")}
                and e["actor_id"] in o["participants"] and e["at"] == done_at(s, o["op_id"])]
        assert {e["actor_id"] for e in back} <= set(o["participants"]) and all(
            e["payload"]["to_place"] == o["route"][0] for e in back), f"day {day}: they walk home"
        got = [r["payload"] for r in rows(s, "STORES_CHANGE") if r["payload"]["settlement_id"] == home
               and r["payload"]["reason"] == "scavenged" and r["at"] == done_at(s, o["op_id"])]
        if haul:
            assert [g["changes"] for g in got] == [dict(sorted(haul.items()))], "the haul, into the home stores"
            hauled = True
            break
        assert got == []
        run(s, 24 - 5.2)            # the next morning
    assert hauled, "six days of scavenging and nothing found"


def done_at(s, op_id) -> int:
    return [r["at"] for r in rows(s, "FACTION_OPERATION") if r["payload"]["op_id"] == op_id
            and r["payload"].get("step") == "return"][-1]


def test_a_patrol_walks_to_the_next_district_and_leaves_tracks(gw):
    """OPS-01 / OPS-03: a patrol goes to the far end of a road out of its own district — never into
    the exterior — and leaves a loose line of boot prints."""
    s = gw
    only_kind(s, "patrol", op_chance=NONE | {"patrol": 100.0})
    safe_roads(s)
    plan(s)
    made = ops(s)
    assert made
    for o in made:
        dest = o["route"][1]
        z = one(s, "SELECT z.kind FROM places p JOIN zones z ON z.zone_id = p.zone_id WHERE p.place_id = ?", (dest,))
        assert z["kind"] != "exterior"
        mine = hub(s, zone_of(s, o["route"][0]))
        assert one(s, "SELECT 1 FROM routes WHERE (from_place = ? AND to_place = ?) OR (from_place = ? AND to_place = ?)",
                   (mine, dest, dest, mine)), "the far end of one of its district's roads"
    run(s, 2.1)
    for o in made:
        assert traces_at(s, o["route"][1], "tracks") == ["Boot prints in a loose line, walking a route."]


def test_a_trade_run_swaps_water_for_food(gw):
    """OPS-03: the origin gives a tenth of what it has most of (food on a tie) for as much of the
    other; TRADE says so at the destination; on the way home both settlements' stores change
    ('trade')."""
    s = gw
    only_kind(s, "trade_run", op_chance=NONE | {"trade_run": 100.0})
    safe_roads(s)
    from as_engine.society import settlement as stl
    with s.store.transaction() as tx:     # food is what everyone has most of this week (the swap gives it)
        for r in all_rows(s, "SELECT settlement_id, stores FROM settlements ORDER BY settlement_id"):
            st = json.loads(r["stores"])
            stl.receive(tx, r["settlement_id"], {"food": st.get("water", 0) - st.get("food", 0) + 45}, "test", now(s),
                        turn(s), None)
    plan(s)
    made = ops(s)
    assert made
    o = made[0]
    home = one(s, "SELECT settlement_id FROM settlements WHERE place_id = ?", (o["route"][0],))["settlement_id"]
    other = one(s, "SELECT settlement_id FROM settlements WHERE place_id = ?", (o["route"][1],))["settlement_id"]
    st = stores(s, home)
    give, get = "food", "water"
    assert st["food"] > st["water"]
    amount = math.floor(0.1 * st["food"] + 0.5)
    b_home, b_other = stores(s, home), stores(s, other)
    run(s, 2.1)
    [trade] = [r for r in rows(s, "TRADE") if r["payload"]["op_id"] == o["op_id"]]
    assert (trade["writer"], trade["payload"]) == ("world.worldmove", {"op_id": o["op_id"], "from": home, "to": other,
                                                                       "gave": {give: amount}, "got": {get: amount}})
    assert op(s, o["op_id"])["outcome"]["haul"] == {give: -amount, get: amount}
    run(s, 3.1)
    a_home, a_other = stores(s, home), stores(s, other)
    assert a_home[give] == pytest.approx(b_home[give] - amount, abs=0.01) or a_home[give] == 0
    assert a_home[get] == pytest.approx(b_home.get(get, 0) + amount, abs=0.01)
    assert a_other[give] == pytest.approx(b_other.get(give, 0) + amount, abs=0.01)
    trades = [r["payload"]["settlement_id"] for r in rows(s, "STORES_CHANGE") if r["payload"]["reason"] == "trade"]
    assert trades[-2:] == [home, other]


# =========================================================================== raids
@pytest.fixture(scope="module")
def raiders(tmp_path_factory):
    """A world with a hostile band (seed 1: two named raiders and their people)."""
    from as_engine.service import runs
    from as_engine.testing.fake_lm import FakeTransport
    root = tmp_path_factory.mktemp("raid_world")
    cfg = EngineConfig(runs_dir=str(root / "runs"), content_dir=str(REPO_PACKS))
    s = asyncio.run(runs.create_run(cfg, WORLD_PC, RunSettings(world_detail="gotta_go_to_work_soon", seed=1,
                                                                 era="established"), FakeTransport()))
    run_id = s.run_id
    s.store.close()
    return cfg, run_id


def _raid(raiders, tmp_path, success):
    import shutil

    from as_engine.service import runs
    from as_engine.testing.fake_lm import FakeTransport
    cfg, run_id = raiders
    shutil.copytree(cfg.runs_dir, tmp_path / "runs")
    s = runs.load_run(EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(REPO_PACKS)), run_id, FakeTransport())
    band = one(s, "SELECT DISTINCT archetype FROM cohorts WHERE archetype IS NOT NULL")
    if band is None:
        s.store.close()
        pytest.skip("no hostile band in this world")
    tune(s, world={"op_chance": NONE | {"raid": 1000.0}, "op_leg_h": 2.0, "op_dwell_h": 3.0})
    safe_roads(s)
    near = area(s)
    away = next(h for h in (hub(s, z["zone_id"]) for z in all_rows(
        s, "SELECT zone_id FROM zones WHERE kind != 'exterior' ORDER BY zone_id")) if h not in near)
    from as_engine.physical import space
    with s.store.transaction() as tx:
        tx.commit_event(_defences(s, 0 if success else 10))
        # the band starts near the player (the opening's threat); here it has walked off
        for r in tx.query("SELECT actor_id FROM group_members WHERE group_id = ? ORDER BY actor_id", (band["archetype"],)):
            tx.commit_event(space.move_event(tx, r[0], away, None, 30.0, 10.0, now(s), None, turn(s)))
    return s, band["archetype"]


def _defences(s, value):
    from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
    ids = [r[0] for r in s.store.query("SELECT settlement_id FROM settlements ORDER BY settlement_id")]
    return Event(type=EventType.SETTLEMENT_CHANGE, writer="society.settlement", at=now(s), turn_index=turn(s),
                 payload={"settlement_id": ids[0], "field": "defences", "before": None, "after": value, "reason": "test"},
                 writes=[WriteRecord(op=WriteOp.UPDATE, table="settlements", key={"settlement_id": i},
                                     values={"defences": value}) for i in ids])


def test_a_raid_that_gets_in(raiders, tmp_path):
    """OPS-01 / OPS-03: a band with two or more free members raids a settlement; getting in costs
    the target a tenth to a quarter of its food and water, a point of morale, a forced door and
    blood on the ground — and its people will not forget who did it."""
    s, band = _raid(raiders, tmp_path, success=True)
    try:
        plan(s)
        [o] = [x for x in ops(s) if x["kind"] == "raid"]
        assert o["group_id"] == band and len(o["participants"]) >= 2
        target = one(s, "SELECT * FROM settlements WHERE place_id = ?", (o["route"][1],))
        before = json.loads(target["stores"])
        run(s, 2.1)
        [raid] = [r["payload"] for r in rows(s, "RAID") if r["payload"]["op_id"] == o["op_id"]]
        if not raid["success"]:
            pytest.skip("the dice kept them out (success is at most 0.9)")
        assert raid == {"op_id": o["op_id"], "group_id": band, "settlement_id": target["settlement_id"], "success": True}
        after = stores(s, target["settlement_id"])
        for k in ("food", "water"):
            lost = before.get(k, 0) - after.get(k, 0)
            assert 0.10 * before.get(k, 0) - 0.01 <= lost <= 0.25 * before.get(k, 0) + 0.01, k
        assert traces_at(s, target["place_id"], "damage") == ["Broken boards and a forced door."]
        assert "Blood on the ground, still wet." in traces_at(s, target["place_id"], "blood")
        assert [r["payload"] for r in rows(s, "SETTLEMENT_CHANGE") if r["payload"].get("reason") == "raid"]
        if target["group_id"]:
            t = [r["payload"] for r in rows(s, "TENSION_CHANGE") if r["payload"]["a_id"] == target["group_id"]
                 and r["payload"]["b_id"] == band]
            assert t and t[-1]["cause"] == "raid"
    finally:
        s.store.close()


def test_a_raid_that_is_driven_off(raiders, tmp_path):
    """OPS-03: behind strong defences a raid mostly fails; the first raider takes a bullet and
    bleeds on the target's ground; the target loses nothing."""
    s, _band = _raid(raiders, tmp_path, success=False)
    try:
        plan(s)
        [o] = [x for x in ops(s) if x["kind"] == "raid"]
        target = one(s, "SELECT * FROM settlements WHERE place_id = ?", (o["route"][1],))
        before = json.loads(target["stores"])
        run(s, 2.1)
        [raid] = [r["payload"] for r in rows(s, "RAID") if r["payload"]["op_id"] == o["op_id"]]
        if raid["success"]:
            pytest.skip("one in ten gets in anyway")
        shot = [r["payload"] for r in rows(s, "HARM") if r["payload"]["body_id"] == o["participants"][0]]
        assert shot and shot[-1]["type"] == "gunshot" and shot[-1]["severity"] == "significant"
        assert "Blood on the ground, still wet." in traces_at(s, target["place_id"], "blood")
        assert stores(s, target["settlement_id"]) == before
    finally:
        s.store.close()
