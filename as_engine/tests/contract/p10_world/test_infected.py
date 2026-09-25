"""The dead up close (P10). Rules INF-01..12 and world.infected's spawn / feed / rise / day
(world/infected.py; physical.bodies death and rising; Lore v1.0 §2-4, CMG §42).

The baseline dead are bodies that code drives the same way everywhere: they hear, they see what
their kind can see, they walk to what draws them, bite what they reach, tire by the hour and lie
still when they run out; the freshly dead get up again. Nothing here is a roll against the player.
The hand-made metal_fence scene (tests/fixtures/scenarios) is the stage: the sales floor is lit
(light 1), the office dark, the alley outdoors.
"""

from __future__ import annotations

import json

import pytest

from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.kernel import clock
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec
from as_engine.turn import timers
from as_engine.world import infected

pytestmark = pytest.mark.phase(10)

SH, CR, RU = infected.SHAMBLER, infected.CRAWLER, infected.RUNNER
S = 1000
MIN = 60 * S
H = 60 * MIN
DAY = 24 * H


# --------------------------------------------------------------------------- helpers
def now(w) -> int:
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def one(w, sql, p=()):
    r = w.store.query_one(sql, p)
    return None if r is None else dict(r)


def stage(scenario, *, keep=("pc",)):
    """metal_fence with nothing scheduled (the scripted crash is called off) and everyone but
    ``keep`` moved to the stockroom, out of sight of the sales floor."""
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        for q in tx.query("SELECT queue_id FROM event_queue WHERE status = 'pending' ORDER BY queue_id"):
            clock.cancel(tx, q[0], "test", now(w), None, 0)
        for k, who in enumerate(("eli", "pc", "mara", "alice", "june")):
            if who not in keep:
                tx.commit_event(space.move_event(tx, w.id(who), w.id("storeroom"), None, 1.0 + k, 2.0, now(w), None, 0))
    return w


def later(w, seconds: float):
    """The clock moves on with nothing happening (kernel.clock.advance_event)."""
    with w.store.transaction() as tx:
        clock.advance_event(tx, now(w) + int(seconds * S), "test")


def put(w, who: str, place: str, x: float, y: float):
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id(who), w.id(place), None, x, y, now(w), None, 0))


def spawn(w, place: str, type_id=SH, *, x=None, y=None, dormant=False) -> str:
    with w.store.transaction() as tx:
        return infected.spawn(tx, w.rng, w.id(place), type_id, now(w), 0, None, x_m=x, y_m=y, dormant=dormant)


def start(w, who: str, verb: str) -> None:
    """Test setup: an ACTION_START by ``who`` with that verb (as action.resolve writes it)."""
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", actor_id=w.id(who), at=now(w),
                              turn_index=0, payload={"actor_id": w.id(who), "def_id": f"test_{verb}", "verb": verb,
                                                     "target_id": None, "destination_id": None, "item_id": None,
                                                     "est_duration_s": 0.0, "visible": True}))


def state(w, b) -> dict:
    r = one(w, "SELECT * FROM infected_state WHERE body_id = ?", (b,))
    r["states"], r["quirks"] = json.loads(r["states"]), json.loads(r["quirks"])
    return r


def set_state(w, b, **values):
    """Test setup: an INFECTED_STATE as world.infected writes it."""
    before = {k: state(w, b)[k] for k in values}
    vals = {k: (list(v) if k == "states" else v) for k, v in values.items()}
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.INFECTED_STATE, writer="world.infected", at=now(w), turn_index=0,
                              actor_id=b, payload={"body_id": b, "changes": vals, "before": before},
                              writes=[WriteRecord(op=WriteOp.UPDATE, table="infected_state", key={"body_id": b},
                                                  values=vals)]))


def infect(w, who: str, pathway: str, stage_name: str, hours_ago: float = 0.0):
    """Test setup: an infections row, as physical.bodies.expose writes one that took."""
    b = w.id(who)
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=now(w), turn_index=0, payload={"what": "test"}))
        tx.commit_event(Event(type=EventType.INFECTION_EXPOSURE, writer="physical.bodies", at=now(w), turn_index=0,
                              actor_id=b, cause_event_id=c.event_id,
                              payload={"body_id": b, "pathway": pathway, "exposure": "test", "infected": True},
                              writes=[WriteRecord(op=WriteOp.INSERT, table="infections", key={"body_id": b, "pathway": pathway},
                                                  values={"body_id": b, "pathway": pathway,
                                                          "exposed_at": now(w) - int(hours_ago * H), "stage": stage_name,
                                                          "cause_event": c.event_id, "known_to_self": 0})]))


def events(w, type_: str) -> list[dict]:
    out = []
    for r in w.store.query("SELECT * FROM events WHERE type = ? ORDER BY seq", (type_,)):
        d = dict(r)
        d["payload"] = json.loads(d["payload"])
        out.append(d)
    return out


def run_for(w, seconds: float) -> list:
    with w.store.transaction() as tx:
        return timers.run_offscreen(tx, w.rng, now(w) + int(seconds * S), 0)


def steps_pending(w, b) -> list[dict]:
    return [dict(r) for r in w.store.query("SELECT * FROM event_queue WHERE type = 'INFECTED_STEP' AND subject_id = ? "
                                           "AND status = 'pending'", (b,))]


# =========================================================================== spawn, INF-01, INF-08
def test_a_spawned_body_is_driven_by_code(scenario):
    """spawn: a body of kind 'infected' with no actors row; its state starts awake, with
    R.energy_start, no target, charged now; a Runner is given its day to slow down (INF-10);
    dormant=True lies still; without x / y it stands somewhere inside the place."""
    w = stage(scenario)
    R = w.store.rules.infected
    t = now(w)
    a = spawn(w, "alley", SH, x=4.0, y=3.0)
    r = spawn(w, "alley", RU)
    d = spawn(w, "alley", CR, dormant=True)
    body = one(w, "SELECT * FROM bodies WHERE body_id = ?", (a,))
    assert (body["kind"], body["alive"], body["origin"], body["awareness"]) == ("infected", 1, "materialize", "awake")
    sh = w.canon.find("infected", SH)
    assert json.loads(body["special"]) == {k: (v.lo + v.hi) // 2 for k, v in sh.special.items()}
    assert one(w, "SELECT 1 FROM actors WHERE actor_id = ?", (a,)) is None, "code drives it: no mind"
    st = state(w, a)
    assert (st["type_id"], st["states"], st["energy"], st["target_id"], st["since"], st["charged_at"],
            st["degrade_at"], st["risen_from"]) == (SH, [], R.energy_start, None, t, t, None, None)
    assert infected.active(w.store, a)
    pos = one(w, "SELECT * FROM positions WHERE body_id = ?", (a,))
    assert (pos["place_id"], pos["x_m"], pos["y_m"]) == (w.id("alley"), 4.0, 3.0)
    lo, hi = R.runner_degrade_days
    assert lo * DAY <= state(w, r)["degrade_at"] - t <= hi * DAY and (state(w, r)["degrade_at"] - t) % DAY == 0
    alley = one(w, "SELECT width_m, depth_m FROM places WHERE place_id = ?", (w.id("alley"),))
    p = one(w, "SELECT x_m, y_m FROM positions WHERE body_id = ?", (r,))
    assert 1 <= p["x_m"] <= max(1, int(alley["width_m"]) - 1) and 1 <= p["y_m"] <= max(1, int(alley["depth_m"]) - 1)
    assert state(w, d)["states"] == ["dormant"] and not infected.active(w.store, d)
    mats = [e["payload"] for e in events(w, "MATERIALIZE") if e["writer"] == "world.infected"]
    assert mats == [{"body_id": a, "type_id": SH}, {"body_id": r, "type_id": RU}, {"body_id": d, "type_id": CR}]


def test_quirks_come_from_the_seed(scenario):
    """INF-08: a body's quirks are its kind's (applies_to), at most R.quirks_max, none twice — and
    the same world makes the same bodies with the same quirks."""
    kinds = (SH, CR, RU, SH, RU, CR, SH, SH, CR, RU)
    got = []
    for _ in range(2):
        w = stage(scenario)
        got.append([state(w, spawn(w, "alley", t))["quirks"] for t in kinds])
    assert got[0] == got[1]
    R = w.store.rules.infected
    for q, t in zip(got[0], kinds, strict=True):
        assert len(q) == len(set(q)) <= R.quirks_max
        assert all(t in w.canon.find("quirk", x).applies_to for x in q)
    assert any(got[0]), "ten bodies and nobody has a single quirk"


def test_states_change_what_a_body_hears_and_how_fast_it_goes(scenario):
    """INF-01 / INF-02: the type gives the base; every state adds its hearing delta and multiplies
    the speed; a dormant body does not move and is not active."""
    w = stage(scenario)
    b = spawn(w, "alley", SH)
    sh = w.canon.find("infected", SH)
    assert infected.threshold(w.store, b) == pytest.approx(sh.senses.hearing_threshold_db)
    assert infected.speed(w.store, b) == pytest.approx(sh.speed_m_s)
    starved, hurt, dormant = (w.canon.find("infected_state", x) for x in ("starved", "injured", "dormant"))
    set_state(w, b, states=["starved", "injured"])
    assert infected.threshold(w.store, b) == pytest.approx(
        sh.senses.hearing_threshold_db + starved.hearing_threshold_delta_db + hurt.hearing_threshold_delta_db)
    assert infected.speed(w.store, b) == pytest.approx(sh.speed_m_s * starved.speed_mult * hurt.speed_mult)
    assert infected.active(w.store, b), "states do not stop a body; only dormancy does"
    set_state(w, b, states=["dormant"])
    assert infected.speed(w.store, b) == 0
    assert infected.threshold(w.store, b) == pytest.approx(sh.senses.hearing_threshold_db + dormant.hearing_threshold_delta_db)
    assert not infected.active(w.store, b)


# =========================================================================== INF-02, INF-05..07 sight
def test_what_the_dead_see(scenario):
    """INF-02: a Shambler sees only what moves (a MOVE or an action start in the last
    R.motion_window_s) within its 4 m; a Runner sees any shape within 12 m; nothing is seen
    through a wall, and no infected body is ever prey (INF-05)."""
    w = stage(scenario, keep=("pc", "june"))
    put(w, "pc", "sales_floor", 6.0, 4.0)
    put(w, "june", "storeroom", 7.0, 1.0)
    near = spawn(w, "sales_floor", SH, x=6.0, y=7.5)     # 3.5 m from the PC
    far = spawn(w, "sales_floor", SH, x=13.0, y=4.0)     # 7 m
    run = spawn(w, "sales_floor", RU, x=13.0, y=8.0)     # 8.1 m
    later(w, w.store.rules.infected.motion_window_s + 1)
    pc = w.id("pc")
    assert not infected.sees(w.store, near, pc, now(w)), "standing still, the PC is part of the furniture"
    assert infected.sees(w.store, run, pc, now(w)), "a Runner sees a shape"
    put(w, "pc", "sales_floor", 6.0, 4.4)
    assert infected.sees(w.store, near, pc, now(w)), "a movement within 4 m"
    assert not infected.sees(w.store, far, pc, now(w)), "a movement 7 m away is beyond a Shambler's sight"
    later(w, w.store.rules.infected.motion_window_s + 1)
    assert not infected.sees(w.store, near, pc, now(w)), "still again"
    assert not infected.sees(w.store, run, w.id("june"), now(w)), "not through a wall"
    assert not infected.sees(w.store, run, near, now(w)), "INF-05: never its own kind"
    # starting to watch, wait, keep guard, hide or talk moves nothing; reaching for something does
    for verb in sorted(infected.STILL_VERBS):
        start(w, "pc", verb)
        assert not infected.sees(w.store, near, pc, now(w)), f"a {verb} action is standing still"
    start(w, "pc", "manipulate")
    assert infected.sees(w.store, near, pc, now(w)), "reaching for something is movement"


def test_the_dead_and_the_senseless_are_not_prey(scenario):
    """sees(): only a living body that is not unconscious — a sleeper lies in plain view."""
    w = stage(scenario, keep=("pc", "mara"))
    put(w, "pc", "sales_floor", 6.0, 4.0)
    put(w, "mara", "sales_floor", 8.0, 4.0)
    run = spawn(w, "sales_floor", RU, x=12.0, y=4.0)
    with w.store.transaction() as tx:
        bodies.posture_event(tx, w.id("mara"), "lying", now(w), None, 0, awareness="asleep")
    assert infected.sees(w.store, run, w.id("mara"), now(w)), "asleep on the floor, in plain view"
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.AWARENESS_CHANGE, writer="physical.bodies", at=now(w), turn_index=0,
                              actor_id=w.id("mara"), payload={"body_id": w.id("mara"), "awareness": "unconscious",
                                                              "from": "asleep"},
                              writes=[WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": w.id("mara")},
                                                  values={"awareness": "unconscious"})]))
        bodies.die(tx, w.rng, w.id("pc"), now(w), None, 0)
    assert not infected.sees(w.store, run, w.id("mara"), now(w))
    assert not infected.sees(w.store, run, w.id("pc"), now(w))


def test_the_dead_coming_near_are_news(scenario):
    """REACT-01 (P10): one of the dead moving to within 20 m, seen clearly or in part, is material to
    whoever sees it, however it moved — a mind reacts and the PC's watch ends; the same move by a
    living body with no run, flight or leaving behind it is not."""
    from as_engine.action import reactions
    from as_engine.mind import perception
    w = stage(scenario, keep=("pc", "mara"))
    put(w, "pc", "sales_floor", 2.0, 4.0)
    put(w, "mara", "sales_floor", 3.0, 4.0)
    b = spawn(w, "storeroom", SH, x=3.0, y=3.0)          # out of sight
    later(w, 1)
    with w.store.transaction() as tx:
        dead = tx.commit_event(space.move_event(tx, b, w.id("sales_floor"), None, 10.0, 4.0, now(w), None, 0))
        alice = tx.commit_event(space.move_event(tx, w.id("alice"), w.id("sales_floor"), None, 9.0, 5.0, now(w), None, 0))
        for who in ("pc", "mara"):
            perception.compile_aftermath(tx, w.id(who), [dead, alice], now(w), 0)
        seen = {r[0] for r in tx.query("SELECT holder_id FROM percept_log WHERE event_id = ? AND channel = 'visual'",
                                       (dead.event_id,))}
        assert seen == {w.id("pc"), w.id("mara")}, "both see it walk in"
        assert reactions.material_holders(tx, [alice], 0) == [], "a walk that is no run, flight or leaving is not news"
        got = reactions.material_holders(tx, [dead, alice], 0)
    assert got == sorted([(w.id("mara"), dead.at), (w.id("pc"), dead.at)], key=lambda x: (x[1], x[0]))


def test_the_infected_leave_their_own_alone(scenario):
    """INF-06: a Lurker-to-be past its first stage is never a target, by sight or by sound. INF-07
    (W1): a wet host R.wet_ignore_after_h into it is seen as prey only within half the type's
    range — and a sound it makes still draws them to where it is."""
    w = stage(scenario, keep=("pc", "mara"))
    put(w, "pc", "sales_floor", 6.0, 4.0)
    put(w, "mara", "sales_floor", 8.0, 4.0)
    run = spawn(w, "sales_floor", RU, x=12.0, y=4.0)
    first, second = (st.name for st in w.canon.find("pathway", "lurker_deep").stages[:2])
    infect(w, "pc", "lurker_deep", first)
    assert infected.sees(w.store, run, w.id("pc"), now(w)), "the first stage is still just a person"
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.INFECTION_STAGE, writer="physical.bodies", at=now(w), turn_index=0,
                              actor_id=w.id("pc"), payload={"body_id": w.id("pc"), "pathway": "lurker_deep",
                                                            "stage": second},
                              writes=[WriteRecord(op=WriteOp.UPDATE, table="infections",
                                                  key={"body_id": w.id("pc"), "pathway": "lurker_deep"},
                                                  values={"stage": second})]))
    assert not infected.sees(w.store, run, w.id("pc"), now(w))
    with w.store.transaction() as tx:
        assert infected.attract(tx, run, w.id("pc"), now(w), None, 0, reason="noise") is None
    R = w.store.rules.infected
    infect(w, "mara", "wet", "living_spreader_week3", hours_ago=R.wet_ignore_after_h)
    assert infected.sees(w.store, run, w.id("mara"), now(w)), "INF-07 (W1): less of their eye, not none — 4 m of 12"
    put(w, "mara", "sales_floor", 4.0, 4.0)
    assert not infected.sees(w.store, run, w.id("mara"), now(w)), "INF-07: 8 m is past half a Runner's 12"
    with w.store.transaction() as tx:
        ev = infected.attract(tx, run, w.id("mara"), now(w), None, 0, reason="noise")
    assert ev is not None and ev.payload["target_kind"] == "body", "a sound still draws them"


# =========================================================================== INF-09 attract, INF-03
def test_a_noise_sets_a_body_walking(scenario):
    """INF-09: attract to a place -> INFECTED_DRIFT {target_kind 'place'}, the target set, and an
    INFECTED_STEP R.step_min_s later; drawn again to the same target on its way -> nothing."""
    w = stage(scenario)
    b = spawn(w, "alley", SH)
    t = now(w)
    with w.store.transaction() as tx:
        ev = infected.attract(tx, b, w.id("street"), t, None, 0, reason="noise")
    assert ev.type == EventType.INFECTED_DRIFT and ev.actor_id == b
    assert ev.payload == {"body_id": b, "target_id": w.id("street"), "target_kind": "place", "reason": "noise", "woke": False}
    assert state(w, b)["target_id"] == w.id("street")
    [row] = steps_pending(w, b)
    assert row["due_at"] == t + round(w.store.rules.infected.step_min_s * S)
    assert json.loads(row["payload"]) == {"body_id": b, "leg": None}
    with w.store.transaction() as tx:
        assert infected.attract(tx, b, w.id("street"), t, None, 0, reason="noise") is None
    assert len(steps_pending(w, b)) == 1


def test_prey_in_reach_beats_a_noise(scenario):
    """INF-09: a body hunting someone in its own place is not drawn off by a sound elsewhere; the
    dead never target the dead (INF-05)."""
    w = stage(scenario)
    put(w, "pc", "sales_floor", 6.0, 4.0)
    b = spawn(w, "sales_floor", RU, x=10.0, y=4.0)
    other = spawn(w, "sales_floor", SH, x=12.0, y=4.0)
    with w.store.transaction() as tx:
        assert infected.attract(tx, b, w.id("pc"), now(w), None, 0, reason="sight") is not None
        assert infected.attract(tx, b, w.id("street"), now(w), None, 0, reason="noise") is None
        assert infected.attract(tx, b, other, now(w), None, 0, reason="sight") is None
    assert state(w, b)["target_id"] == w.id("pc")


def test_a_body_drawn_to_where_it_stands_looks_around(scenario):
    """INF-09: drawn to the place it already stands in, a body looks: someone it sees becomes its
    target (reason 'sight'); nobody in sight -> nothing happens, and a dormant body stays down."""
    w = stage(scenario)
    put(w, "pc", "sales_floor", 6.0, 4.0)
    b = spawn(w, "sales_floor", RU, x=10.0, y=4.0)
    with w.store.transaction() as tx:
        ev = infected.attract(tx, b, w.id("sales_floor"), now(w), None, 0, reason="noise")
    assert (ev.payload["target_id"], ev.payload["target_kind"], ev.payload["reason"]) == (w.id("pc"), "body", "sight")
    d = spawn(w, "alley", SH, dormant=True)
    with w.store.transaction() as tx:
        assert infected.attract(tx, d, w.id("alley"), now(w), None, 0, reason="noise") is None
    assert state(w, d)["states"] == ["dormant"] and steps_pending(w, d) == []


def test_energy_is_spent_by_the_hour_and_a_sound_wakes_the_spent(scenario):
    """INF-03: active time costs 1 energy per R.energy_period_s; at 0 the body goes dormant and
    forgets its target (no further steps); a stimulus reboots it (woke: true), and the time it lay
    still cost nothing."""
    w = stage(scenario)
    R = w.store.rules.infected
    b = spawn(w, "alley", SH)
    set_state(w, b, energy=3)
    with w.store.transaction() as tx:
        infected.attract(tx, b, w.id("street"), now(w), None, 0, reason="noise")   # the way out is barred
    period = R.energy_period_s[SH]
    run_for(w, 4 * period + 30)
    st = state(w, b)
    assert (st["energy"], st["target_id"]) == (0, None) and "dormant" in st["states"]
    assert steps_pending(w, b) == [], "it lies still: nothing more is scheduled"
    later(w, 6 * H)
    assert state(w, b)["energy"] == 0, "lying still costs nothing"
    with w.store.transaction() as tx:
        ev = infected.attract(tx, b, w.id("street"), now(w), None, 0, reason="noise")
    assert ev.payload["woke"] is True
    st = state(w, b)
    assert "dormant" not in st["states"] and st["charged_at"] == now(w), "the clock starts again from the wake"


def test_a_bite_that_lands_feeds_it(scenario):
    """feed: energy + R.energy_per_feed (at most 100), and 'starved' / 'overfed' follow the energy;
    nothing changes -> None; not an infected body -> None."""
    w = stage(scenario)
    R = w.store.rules.infected
    b = spawn(w, "alley", SH)
    set_state(w, b, energy=R.starved_below - 1, states=["starved"])
    with w.store.transaction() as tx:
        ev = infected.feed(tx, b, now(w), None, 0)
    assert ev.type == EventType.INFECTED_STATE
    st = state(w, b)
    assert st["energy"] == R.starved_below - 1 + R.energy_per_feed and "starved" not in st["states"]
    set_state(w, b, energy=R.overfed_above - 5)
    with w.store.transaction() as tx:
        infected.feed(tx, b, now(w), None, 0)
    st = state(w, b)
    assert st["energy"] == min(100, R.overfed_above - 5 + R.energy_per_feed) and "overfed" in st["states"]
    set_state(w, b, energy=100)
    with w.store.transaction() as tx:
        assert infected.feed(tx, b, now(w), None, 0) is None
        assert infected.feed(tx, w.id("pc"), now(w), None, 0) is None


# =========================================================================== INF-10, day
def test_a_runner_slows_down_and_never_speeds_up(scenario):
    """INF-10 (world.infected.day): a Runner whose degrade_at has come becomes a Shambler or a
    Crawler; the others stay what they are; a dormant body recovers R.idle_recover_per_day."""
    w = stage(scenario)
    R = w.store.rules.infected
    r = spawn(w, "alley", RU)
    s = spawn(w, "alley", SH)
    d = spawn(w, "alley", CR, dormant=True)
    set_state(w, d, energy=10)
    with w.store.transaction() as tx:
        infected.day(tx, w.rng, now(w), 0, None)
    assert state(w, r)["type_id"] == RU, "not yet"
    assert state(w, d)["energy"] == 10 + R.idle_recover_per_day
    with w.store.transaction() as tx:
        infected.day(tx, w.rng, state(w, r)["degrade_at"], 0, None)
    assert state(w, r)["type_id"] in (SH, CR) and state(w, r)["degrade_at"] is None
    assert state(w, s)["type_id"] == SH


# =========================================================================== INF-04 the dead rise
def _die_and_rise(w, who: str) -> str | None:
    """Kill ``who`` (physical.bodies.die) and let the world run to just past the rise it scheduled.
    Returns the risen body, or None."""
    b = w.id(who)
    with w.store.transaction() as tx:
        bodies.die(tx, w.rng, b, now(w), None, 0)
    rows = [dict(r) for r in w.store.query("SELECT * FROM event_queue WHERE type = 'REANIMATION' AND subject_id = ? "
                                           "AND status = 'pending'", (b,))]
    if not rows:
        return None
    with w.store.transaction() as tx:
        timers.run_offscreen(tx, w.rng, rows[0]["due_at"] + S, 0)
    r = one(w, "SELECT body_id FROM infected_state WHERE risen_from = ?", (b,))
    return None if r is None else r["body_id"]


def test_the_freshly_dead_get_up(scenario):
    """INF-04: a wet host dead of it rises as a Runner where the corpse lay — its place and its spot;
    the corpse's position goes to the new body in the same MOVE; everything it held comes with it;
    and it goes for the living it sees."""
    w = stage(scenario, keep=("pc", "alice"))
    put(w, "pc", "sales_floor", 12.0, 7.0)
    put(w, "alice", "sales_floor", 6.0, 5.5)
    alice = w.id("alice")
    wet = w.canon.find("pathway", "wet")
    infect(w, "alice", "wet", wet.stages[-1].name, hours_ago=wet.death_at_h + 1)
    held = sorted(r[0] for r in w.store.query("SELECT item_id FROM items WHERE holder_body = ?", (alice,)))
    assert held, "Alice holds her ledger"
    new = _die_and_rise(w, "alice")
    assert new is not None and new != alice
    st = state(w, new)
    assert (st["type_id"], st["risen_from"]) == (RU, alice)
    assert one(w, "SELECT alive FROM bodies WHERE body_id = ?", (alice,))["alive"] == 0, "the corpse stays a corpse"
    pos = one(w, "SELECT * FROM positions WHERE body_id = ?", (new,))
    assert (pos["place_id"], pos["x_m"], pos["y_m"]) == (w.id("sales_floor"), 6.0, 5.5)
    assert one(w, "SELECT 1 FROM positions WHERE body_id = ?", (alice,)) is None
    [mv] = [e for e in events(w, "MOVE") if e["payload"].get("replaces") == alice]
    assert mv["payload"]["body_id"] == new
    assert sorted(r[0] for r in w.store.query("SELECT item_id FROM items WHERE holder_body = ?", (new,))) == held
    assert st["target_id"] == w.id("pc"), "a Runner sees the living across the room"


def test_the_plain_dead_rise_slowly(scenario):
    """INF-04: a death with no wet strain in it rises through the cold start — later, and as a
    Shambler or a Crawler."""
    w = stage(scenario, keep=("pc", "alice"))
    t = now(w)
    new = _die_and_rise(w, "alice")
    cold = w.canon.find("pathway", "cold_start")
    assert state(w, new)["type_id"] in cold.rise_as
    lo, hi = cold.rise_after_death_h
    assert lo * H <= state(w, new)["since"] - t <= hi * H + S


def test_a_destroyed_head_stays_down(scenario):
    """INF-04: a death by a catastrophic head wound schedules no rise; nothing gets up."""
    w = stage(scenario, keep=("pc", "alice"))
    alice = w.id("alice")
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=now(w), turn_index=0, payload={"what": "test"}))
        bodies.apply_harm(tx, alice, WoundSpec("head", "gunshot", "catastrophic", 0), now(w), c.event_id, 0, w.rng)
    assert one(w, "SELECT alive FROM bodies WHERE body_id = ?", (alice,))["alive"] == 0
    assert _die_and_rise(w, "alice") is None
    assert not [r for r in w.store.query("SELECT 1 FROM event_queue WHERE type = 'REANIMATION' AND subject_id = ?", (alice,))]


# =========================================================================== INF-12 step
def test_it_walks_up_and_bites(scenario):
    """INF-12: a body hunting someone across the room walks to them (MOVE legs) and, within 1.5 m,
    bites or grabs (a reflex action through action.resolve)."""
    w = stage(scenario)
    put(w, "pc", "sales_floor", 2.0, 4.0)
    b = spawn(w, "sales_floor", RU, x=12.0, y=4.0)
    with w.store.transaction() as tx:
        infected.attract(tx, b, w.id("pc"), now(w), None, 0, reason="sight")
    run_for(w, 12)
    moves = [e for e in events(w, "MOVE") if e["actor_id"] == b]
    assert moves, "it closes the distance"
    last = one(w, "SELECT x_m, y_m FROM positions WHERE body_id = ?", (b,))
    assert abs(last["x_m"] - 2.0) + abs(last["y_m"] - 4.0) < 1.5
    acts = [e["payload"]["def_id"] for e in events(w, "ACTION_START") if e["actor_id"] == b]
    assert acts and all(d.endswith(("infected_bite", "infected_grab")) for d in acts), acts


def test_the_overfed_walk_away(scenario):
    """INF-12: an engaged body follows through only with its states' lowest bite_commitment; an
    overfed one mostly lets go and walks off (target None)."""
    w = stage(scenario)
    put(w, "pc", "sales_floor", 6.0, 4.0)
    walked = 0
    for k in range(6):
        b = spawn(w, "sales_floor", RU, x=6.5, y=4.0 + 0.1 * k)
        set_state(w, b, energy=95, states=["overfed"])
        with w.store.transaction() as tx:
            infected.attract(tx, b, w.id("pc"), now(w), None, 0, reason="sight")
        run_for(w, 3)
        walked += state(w, b)["target_id"] is None
    assert walked >= 3, "an overfed body (bite_commitment 0.2) mostly walks off"


def test_the_same_rules_run_off_screen(scenario):
    """INF-12: a body two rooms away from anyone who could see it still walks, bangs and tires on
    the same clock — the step rows fire in run_offscreen as in a turn."""
    w = stage(scenario)
    b = spawn(w, "alley", SH, x=6.0, y=3.0)
    with w.store.transaction() as tx:
        infected.attract(tx, b, w.id("street"), now(w), None, 0, reason="noise")
    run_for(w, 60)
    assert [e for e in events(w, "INFECTED_DRIFT") if e["actor_id"] == b]
    assert [e for e in events(w, "MOVE") if e["actor_id"] == b], "it set off"
