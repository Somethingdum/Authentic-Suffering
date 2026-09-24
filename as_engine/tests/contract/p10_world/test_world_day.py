"""The world's day without the player (P10, fidelity C01 / C02 / C11). Rules WORLD-02..06, OPS-07,
WEAR-01..04, TRACE-01..06, STL-03 step 2b (world/worldmove.py, world/decay.py, world/traces.py,
society/settlement.py).

Nobody dies of a daily lottery: people die of what happens to them — a wound nobody could stop,
thirst when the water is gone — and the world notices the deaths nobody saw. Things wear because
weather and time touch them; nothing is deleted because the player was away. Marks fade the way
marks fade: faster in the rain, slower under a roof.
"""

from __future__ import annotations

import json

import pytest
from world_kit import DAY, H, all_rows, cause, now, one, rows, run, settlement, turn

from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.contracts.settings import RulesConfig
from as_engine.physical import bodies, objects, space
from as_engine.physical.bodies import WoundSpec
from as_engine.society import settlement as stl
from as_engine.turn.select import active_area
from as_engine.world import decay, traces, worldmove

pytestmark = pytest.mark.phase(10)

BAND_RANK = {"infant": 0, "child": 1, "preteen": 2, "teen": 3, "elder": 4, "adult": 5}


# --------------------------------------------------------------------------- helpers
def pc(s) -> str:
    return s.store.meta("pc_actor_id")


def area(s) -> set[str]:
    with s.store.transaction() as tx:
        return set(active_area(tx, pc(s), turn(s)))


def quiet(s, **world):
    """The run's rules with no operations started (and any other world numbers given)."""
    r = s.store.rules.model_dump()
    r["world"]["op_chance"] = {k: 0.0 for k in r["world"]["op_chance"]}
    r["world"].update(world)
    s.store.attach(rules=RulesConfig.model_validate(r))


def weather(s, kind: str):
    with s.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.WEATHER_CHANGE, writer="kernel.clock", at=now(s), turn_index=turn(s),
                              payload={"weather": kind, "wind_level": 0},
                              writes=[WriteRecord(op=WriteOp.UPDATE, table="world_clock", key={"id": 1},
                                                  values={"weather": kind, "wind_level": 0})]))


def wear_day(s, at=None):
    with s.store.transaction() as tx:
        return decay.day(tx, s.rng, now(s) if at is None else at, turn(s), None)


def far_settlement(s) -> dict:
    """A settlement whose site is outside the active area (by id)."""
    near = area(s)
    for r in all_rows(s, "SELECT settlement_id, place_id FROM settlements ORDER BY settlement_id"):
        if r["place_id"] not in near:
            return settlement(s, r["settlement_id"])
    pytest.skip("every settlement is on screen")


def members(s, sid) -> list[str]:
    return [r["actor_id"] for r in all_rows(
        s, "SELECT m.actor_id FROM group_members m JOIN settlements t ON t.group_id = m.group_id "
           "JOIN bodies b ON b.body_id = m.actor_id WHERE t.settlement_id = ? AND m.status IN ('member', 'probation') "
           "AND b.alive = 1 ORDER BY m.actor_id", (sid,))]


def place_kind(s, place_id) -> tuple[str, int]:
    r = one(s, "SELECT kind, indoor FROM places WHERE place_id = ?", (place_id,))
    return r["kind"], r["indoor"]


def outdoor_place(s, exclude=()) -> str:
    near = area(s)
    for r in all_rows(s, "SELECT place_id FROM places WHERE indoor = 0 ORDER BY place_id"):
        if r["place_id"] not in near and r["place_id"] not in exclude:
            return r["place_id"]
    pytest.skip("no outdoor place off screen")


def indoor_place(s) -> str:
    """A room: the first building site off screen, discovered (physical.space.discover_layout)."""
    r = one(s, "SELECT place_id FROM places WHERE indoor = 1 ORDER BY place_id LIMIT 1")
    if r is None:
        near = area(s)
        site = next(x["place_id"] for x in all_rows(
            s, "SELECT place_id FROM places WHERE kind = 'building' AND layout_generated = 0 ORDER BY place_id")
            if x["place_id"] not in near)
        with s.store.transaction() as tx:
            space.discover_layout(tx, s.rng, site, now(s), turn(s))
        r = one(s, "SELECT place_id FROM places WHERE indoor = 1 ORDER BY place_id LIMIT 1")
    return r["place_id"]


def lay(s, def_ref, place_id, qty=1, props=None) -> str:
    with s.store.transaction() as tx:
        ev = objects.create(tx, def_ref, qty, objects.Holder("place", place_id), "loot", props or {}, now(s), None, turn(s))
    return ev.payload["item_id"]


def item(s, item_id) -> dict | None:
    r = one(s, "SELECT * FROM items WHERE item_id = ?", (item_id,))
    if r is not None:
        r["props"] = json.loads(r["props"])
    return r


def cohorts(s, sid) -> list[dict]:
    return all_rows(s, "SELECT cohort_id, age_band, count FROM cohorts WHERE settlement_id = ? ORDER BY cohort_id", (sid,))


# =========================================================================== C01 no lottery
def test_a_supplied_protected_people_do_not_die_of_nothing(gw):
    """C01: with nothing lethal happening (no operations, full stores) thirty days pass and nobody
    but the unfed PC dies, named or unnamed."""
    s = gw
    quiet(s)
    with s.store.transaction() as tx:
        for r in all_rows(s, "SELECT settlement_id FROM settlements"):
            stl.receive(tx, r["settlement_id"], {"food": 50_000, "water": 50_000}, "test", now(s), turn(s), None)
    counts = {r["cohort_id"]: r["count"] for r in all_rows(s, "SELECT cohort_id, count FROM cohorts")}
    run(s, 30 * 24)
    assert len(rows(s, "WORLD_DAY")) == 30
    dead = [r["payload"]["body_id"] for r in rows(s, "DEATH")]
    assert set(dead) <= {pc(s)}
    assert rows(s, "OFFSCREEN_DEATH") == []
    assert {r["cohort_id"]: r["count"] for r in all_rows(s, "SELECT cohort_id, count FROM cohorts")} == counts


def test_the_unseen_dead_are_noticed_once(gw):
    """WORLD-05 / C01: a named person off screen who bleeds out dies of it (physical.bodies), and the
    next WORLD_DAY gives the world's notice: OFFSCREEN_DEATH {body_id, place_id, cause} caused by
    the DEATH (core CAS-013 leaves a corpse trace there). A later day does not notice it again."""
    s = gw
    quiet(s)
    near = area(s)
    who = next(a for a in members(s, far_settlement(s)["settlement_id"]))
    place = one(s, "SELECT place_id FROM positions WHERE body_id = ?", (who,))["place_id"]
    assert place not in near
    with s.store.transaction() as tx:
        bodies.apply_harm(tx, who, WoundSpec("chest", "laceration", "catastrophic", 0), now(s), cause(tx, now(s)).event_id,
                          turn(s), s.rng)
    run(s, 26)
    [death] = [r for r in rows(s, "DEATH") if r["payload"]["body_id"] == who]
    [notice] = rows(s, "OFFSCREEN_DEATH")
    assert notice["payload"] == {"body_id": who, "place_id": place, "cause": death["payload"]["cause"]}
    assert notice["cause_event_id"] == death["event_id"] and notice["actor_id"] == who
    first_day = min(r["seq"] for r in rows(s, "WORLD_DAY") if r["seq"] > death["seq"])
    assert notice["seq"] > first_day
    assert any(t["kind"] == "corpse" and t["place_id"] == place for t in all_rows(s, "SELECT * FROM traces"))
    run(s, 48)
    assert len(rows(s, "OFFSCREEN_DEATH")) == 1


def test_a_death_in_the_players_sight_gets_no_notice(gw):
    """WORLD-04: what the player could see happen is not announced by the world."""
    s = gw
    quiet(s)
    here = one(s, "SELECT place_id FROM positions WHERE body_id = ?", (pc(s),))["place_id"]
    who = next(a for a in members(s, far_settlement(s)["settlement_id"]))
    with s.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, who, here, None, 1.0, 1.0, now(s), None, turn(s)))
        bodies.apply_harm(tx, who, WoundSpec("chest", "laceration", "catastrophic", 0), now(s), cause(tx, now(s)).event_id,
                          turn(s), s.rng)
    run(s, 26)
    assert any(r["payload"]["body_id"] == who for r in rows(s, "DEATH"))
    assert rows(s, "OFFSCREEN_DEATH") == []


# =========================================================================== STL-03 2b privation
def _dry(s, sid):
    """The settlement's water is gone and nothing refills it."""
    stores = settlement(s, sid)["stores"]
    with s.store.transaction() as tx:
        stl.receive(tx, sid, {"water": -stores.get("water", 0)}, "test", now(s), turn(s), None)
        for w in all_rows(s, "SELECT workplace_id FROM workplaces WHERE settlement_id = ?", (sid,)):
            tx.commit_event(Event(type=EventType.WORKPLACE_CHANGE, writer="society.work", at=now(s), turn_index=turn(s),
                                  payload={"workplace_id": w["workplace_id"], "outputs": {}},
                                  writes=[WriteRecord(op=WriteOp.UPDATE, table="workplaces",
                                                      key={"workplace_id": w["workplace_id"]}, values={"outputs": {}})]))


def test_the_unnamed_say_how_many_went_short(gw):
    """STL-03 step 1 (P10): unnamed_short = the unnamed served one at a time, cohorts in (band rank,
    cohort_id) order, after the named; the first whose share does not fit and everyone after
    are short."""
    s = gw
    quiet(s)
    sid = far_settlement(s)["settlement_id"]
    _dry(s, sid)
    R = s.store.rules.society
    bands = [one(s, "SELECT age_band FROM bodies WHERE body_id = ?", (a,))["age_band"] for a in members(s, sid)]
    water_named = sum(R.water_per_day[b] for b in bands)
    serving = sorted(cohorts(s, sid), key=lambda c: (BAND_RANK[c["age_band"]], c["cohort_id"]))
    give = water_named + serving[0]["count"] * R.water_per_day[serving[0]["age_band"]] + 1.5
    with s.store.transaction() as tx:
        stl.receive(tx, sid, {"water": give}, "test", now(s), turn(s), None)
    run(s, 24)
    [day] = [r for r in rows(s, "SETTLEMENT_DAY") if r["payload"]["settlement_id"] == sid]
    level = day["payload"]["ration_level"]
    assert level >= 2            # the dry pump's cycle may already have cut rations (CAS-004/005)
    mult = R.ration_mult[level]
    left = give - water_named * mult
    assert day["payload"]["short"]["water"] == []
    short, broke = 0, False
    for c in serving:
        sh = R.water_per_day[c["age_band"]] * mult
        fit = 0 if broke else min(c["count"], int((left + 1e-9) // sh))
        left -= fit * sh
        if fit < c["count"]:
            short += c["count"] - fit
            broke = True
    assert short > 0 and day["payload"]["unnamed_short"]["water"] == short


def test_three_days_without_water_kill_the_last_in_line(gw):
    """STL-03 step 2b: after R.privation_days['water'] draws in a row with unnamed people short, the
    fewest short on any of those days die of thirst, the last in line first (reverse serving
    order); POPULATION_CHANGE reason 'thirst' caused by the third SETTLEMENT_DAY."""
    s = gw
    quiet(s)
    sid = far_settlement(s)["settlement_id"]
    _dry(s, sid)
    before = cohorts(s, sid)
    run(s, 2 * 24 + 20)
    days = [r for r in rows(s, "SETTLEMENT_DAY") if r["payload"]["settlement_id"] == sid]
    assert len(days) == 2 and not [r for r in rows(s, "POPULATION_CHANGE") if r["payload"]["reason"] == "thirst"]
    run(s, 24)
    days = [r for r in rows(s, "SETTLEMENT_DAY") if r["payload"]["settlement_id"] == sid]
    assert len(days) == 3
    n = min(d["payload"]["unnamed_short"]["water"] for d in days)
    died = [r for r in rows(s, "POPULATION_CHANGE") if r["payload"]["reason"] == "thirst"]
    assert died and all(r["cause_event_id"] == days[-1]["event_id"] for r in died)
    assert sum(-r["payload"]["delta"] for r in died) == n
    order = sorted([c for c in before if c["count"] > 0], key=lambda c: (BAND_RANK[c["age_band"]], c["cohort_id"]), reverse=True)
    expect, rest = [], n
    for c in order:
        m = min(c["count"], rest)
        if m:
            expect.append((c["cohort_id"], -m))
            rest -= m
    assert [(r["payload"]["cohort_id"], r["payload"]["delta"]) for r in died] == expect


def test_food_lasts_three_weeks(gw):
    """STL-03 step 2b: hunger takes R.privation_days['food'] draws; three days without food kill
    nobody."""
    s = gw
    quiet(s)
    sid = far_settlement(s)["settlement_id"]
    stores = settlement(s, sid)["stores"]
    with s.store.transaction() as tx:
        stl.receive(tx, sid, {"food": -stores.get("food", 0), "water": 50_000}, "test", now(s), turn(s), None)
        for w in all_rows(s, "SELECT workplace_id FROM workplaces WHERE settlement_id = ?", (sid,)):
            tx.commit_event(Event(type=EventType.WORKPLACE_CHANGE, writer="society.work", at=now(s), turn_index=turn(s),
                                  payload={"workplace_id": w["workplace_id"], "outputs": {}},
                                  writes=[WriteRecord(op=WriteOp.UPDATE, table="workplaces",
                                                      key={"workplace_id": w["workplace_id"]}, values={"outputs": {}})]))
    assert s.store.rules.society.privation_days["food"] == 21
    run(s, 4 * 24)
    assert [r for r in rows(s, "POPULATION_CHANGE") if r["payload"]["reason"] == "hunger"] == []
    assert all(d["payload"]["unnamed_short"]["food"] > 0 for d in rows(s, "SETTLEMENT_DAY")
               if d["payload"]["settlement_id"] == sid)


# =========================================================================== WEAR (C02)
def test_rain_rusts_metal_and_rots_paper_left_out(gw):
    """WEAR-03: on a wet day, loose things in exposed places wear by kind; indoors, and on a dry
    day, nothing does. A document worn to 0 falls apart (ITEM_DESTROYED)."""
    s = gw
    out = outdoor_place(s)
    inside = indoor_place(s)
    gun_out, gun_in = lay(s, "core:item/glock_19", out), lay(s, "core:item/glock_19", inside)
    book = lay(s, "core:item/ledger_book", out)
    jacket = lay(s, "core:item/windbreaker", out)
    beans = lay(s, "core:item/batteries_aa", out)
    weather(s, "clear")
    assert wear_day(s) == []
    weather(s, "rain")
    D = s.store.rules.decay
    evs = wear_day(s)
    worn = {e.payload["item_id"]: e.payload for e in evs if str(getattr(e.type, "value", e.type)) == "ITEM_WEAR"}
    assert worn[gun_out] == {"item_id": gun_out, "cause": "rust", "condition_before": 100,
                             "condition": 100 - D.rust_per_wet_day}
    assert worn[book]["cause"] == "pulp" and worn[book]["condition"] == 100 - D.pulp_per_wet_day
    assert worn[jacket]["cause"] == "rot" and worn[jacket]["condition"] == 100 - D.rot_per_wet_day
    assert gun_in not in worn and beans not in worn
    assert item(s, gun_in)["condition"] == 100
    for _ in range(3):
        wear_day(s)
    assert item(s, book) is None
    assert any(r["payload"]["item_id"] == book for r in rows(s, "ITEM_DESTROYED"))
    assert item(s, gun_out)["condition"] == 100 - 4 * D.rust_per_wet_day


def test_food_goes_off_wherever_it_is(gw):
    """WEAR-03/04: a perishable made now carries props.made_at; it spoils after spoil_days, held or
    loose, rain or not; once."""
    s = gw
    weather(s, "clear")
    t0 = now(s)
    with s.store.transaction() as tx:
        ev = objects.create(tx, "core:item/jerky_pack", 2, objects.Holder("body", pc(s), "pack"), "loot", {}, t0, None, turn(s))
    jerky = ev.payload["item_id"]
    assert ev.payload["props"]["made_at"] == t0 and item(s, jerky)["props"]["made_at"] == t0
    kept = lay(s, "core:item/jerky_pack", outdoor_place(s), props={"made_at": t0 - 100 * DAY})
    beans = lay(s, "core:item/canned_beans", outdoor_place(s))
    mine = {jerky, kept, beans}
    evs = [e for e in wear_day(s, t0 + 89 * DAY) if e.payload["item_id"] in mine]
    assert [e.payload["item_id"] for e in evs] == [kept]
    evs = [e for e in wear_day(s, t0 + 90 * DAY) if e.payload["item_id"] in mine]
    assert [e.payload for e in evs] == [{"item_id": jerky, "cause": "spoiled", "condition_before": 100, "condition": 0}]
    assert item(s, jerky)["props"]["spoiled"] is True and item(s, jerky)["condition"] == 0
    assert [e for e in wear_day(s, t0 + 91 * DAY) if e.payload["item_id"] in mine] == []
    assert item(s, beans)["condition"] == 100


def test_nothing_is_forgotten_for_being_unimportant(gw):
    """C02: a thing left in a place nobody visits is still there after two months of world days
    (dry weather, no scavengers going out) — no score, tier or overhaul deletes it."""
    s = gw
    quiet(s, weather_change_chance=0.0)
    weather(s, "clear")
    thing = lay(s, "core:item/crowbar", outdoor_place(s))
    run(s, 60 * 24)
    assert item(s, thing)["condition"] == 100
    assert not [r for r in rows(s, "ITEM_DESTROYED") if r["payload"]["item_id"] == thing]


# =========================================================================== TRACE (C02 / C11)
def test_marks_under_a_roof_last_longer(gw):
    """TRACE-01: the kind's days in the open; times W.sheltered_trace_mult under a roof."""
    s = gw
    W = s.store.rules.world
    out, inside = outdoor_place(s), indoor_place(s)
    with s.store.transaction() as tx:
        a = traces.create(tx, out, "blood", "Blood on the ground.", None, now(s), turn(s))
        b = traces.create(tx, inside, "blood", "Blood on the floor.", None, now(s), turn(s))
    rows_ = {t["trace_id"]: t for t in all_rows(s, "SELECT * FROM traces")}
    assert rows_[a]["decays_at"] == now(s) + int(W.trace_decay_days["blood"] * DAY)
    assert rows_[b]["decays_at"] == now(s) + int(W.trace_decay_days["blood"] * W.sheltered_trace_mult * DAY)


def test_rain_washes_out_tracks_in_the_open(gw):
    """TRACE-06: rain, storm or snow delete exposed traces whose kind is in W.washes_out (reason
    'weather', their decay rows cancelled); marks indoors and other kinds stay."""
    s = gw
    out, inside = outdoor_place(s), indoor_place(s)
    with s.store.transaction() as tx:
        t_out = traces.create(tx, out, "tracks", "Boot prints.", None, now(s), turn(s))
        t_in = traces.create(tx, inside, "tracks", "Boot prints.", None, now(s), turn(s))
        g_out = traces.create(tx, out, "graffiti", "A name, sprayed.", None, now(s), turn(s))
    weather(s, "clear")
    with s.store.transaction() as tx:
        assert traces.washout(tx, now(s), turn(s), None) == []
    weather(s, "storm")
    with s.store.transaction() as tx:
        evs = traces.washout(tx, now(s), turn(s), None)
    gone = [e.payload for e in evs if str(getattr(e.type, "value", e.type)) == "TRACE_DECAYED"
            and e.payload["trace_id"] in (t_out, t_in, g_out)]
    assert gone == [{"trace_id": t_out, "place_id": out, "kind": "tracks", "reason": "weather"}]
    left = {t["trace_id"] for t in all_rows(s, "SELECT trace_id FROM traces")}
    assert {t_in, g_out} <= left and t_out not in left
    assert one(s, "SELECT status FROM event_queue WHERE type = 'TRACE_DECAY' AND subject_id = ?", (t_out,))["status"] != "pending"


def test_a_mark_fades_with_time(gw):
    """TRACE-02: the TRACE_DECAY timer deletes it with reason 'time'."""
    s = gw
    quiet(s, weather_change_chance=0.0)
    weather(s, "clear")
    with s.store.transaction() as tx:
        t = traces.create(tx, indoor_place(s), "tracks", "Boot prints.", None, now(s), turn(s), decay_days=0.5)
    run(s, 13)
    [gone] = [r for r in rows(s, "TRACE_DECAYED") if r["payload"]["trace_id"] == t]
    assert gone["payload"]["reason"] == "time"


# =========================================================================== OPS-07 first aid
def test_the_hurt_are_packed_and_sutured_at_home(gw):
    """OPS-07: a mover bleeding from a significant wound at arrival is packed at once and the party
    heads home after W.op_leg_h (not the dwell); at home the wound is sutured for one medicine."""
    s = gw
    quiet(s)
    r = s.store.rules.model_dump()
    r["world"]["op_chance"] = {"scavenge": 1.0, "patrol": 0.0, "trade_run": 0.0, "raid": 0.0}
    r["world"]["op_leg_h"] = 2.0
    r["world"]["op_dwell_h"] = 6.0
    s.store.attach(rules=RulesConfig.model_validate(r))
    with s.store.transaction() as tx:
        worldmove.plan_operations(tx, s.rng, now(s), turn(s), None)
    ops = all_rows(s, "SELECT * FROM operations WHERE status = 'active' ORDER BY op_id")
    assert ops
    op = ops[0]
    who = json.loads(op["participants"])[0]
    home = one(s, "SELECT settlement_id, stores FROM settlements WHERE place_id = ?", (json.loads(op["route"])[0],))
    meds = json.loads(home["stores"]).get("medicine", 0)
    assert meds >= 1
    with s.store.transaction() as tx:
        bodies.apply_harm(tx, who, WoundSpec("leg_l", "laceration", "significant", 0), now(s), cause(tx, now(s)).event_id,
                          turn(s), s.rng)
    wound = one(s, "SELECT wound_id FROM wounds WHERE body_id = ? ORDER BY created_at DESC LIMIT 1", (who,))["wound_id"]
    run(s, 2.2)
    arrive = [e for e in rows(s, "FACTION_OPERATION") if e["payload"]["op_id"] == op["op_id"] and e["payload"].get("step") == "arrive"]
    assert len(arrive) == 1
    packed = [e for e in rows(s, "TREATMENT") if e["payload"].get("wound_id") == wound]
    assert packed and packed[0]["payload"]["method"] == "packing"
    assert one(s, "SELECT next_due_at FROM operations WHERE op_id = ?", (op["op_id"],))["next_due_at"] == arrive[0]["at"] + 2 * H
    run(s, 2.1)
    assert one(s, "SELECT status FROM operations WHERE op_id = ?", (op["op_id"],))["status"] == "done"
    methods = [e["payload"]["method"] for e in rows(s, "TREATMENT") if e["payload"].get("wound_id") == wound]
    assert methods == ["packing", "suture"]
    sutures = [e for e in rows(s, "TREATMENT") if e["payload"]["method"] == "suture"]
    assert json.loads(one(s, "SELECT stores FROM settlements WHERE settlement_id = ?", (home["settlement_id"],))["stores"])[
        "medicine"] == meds - len(sutures)             # one each (the party's own roll may have hurt another)
    assert one(s, "SELECT alive FROM bodies WHERE body_id = ?", (who,))["alive"] == 1
