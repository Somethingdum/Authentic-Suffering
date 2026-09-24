"""The Ghosts (P10): an enclave sealed under an industrial depot, a council of seats that meets every
week, a route watch that sees the Mega Horde form, a lockdown while it passes, and DECON for any
Ghost killed by a human hand. Rules FAC-01..06 (world/factions.py), WG-10/18/23/27 amendments,
HRD-08/12/14 and OPS-01/02/08 amendments, INF-13's sealed gate, STL-13, CNT-15. Source: Ghosts_6.

The generated test world (seed 7) holds The Depot; its seat holders' names are whatever that world
drew — nothing here names them.
"""

from __future__ import annotations

import json

import pytest
from world_kit import DAY, H, all_rows, area, now, one, pc, rows, run, tune, turn

from as_engine.contracts.events import Event, EventType
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec
from as_engine.world import factions, hordes, infected
from as_engine.world.worldgen import params as wg_params
from as_engine.world.worldgen import placement

pytestmark = pytest.mark.phase(10)

GHOSTS = "core:faction/ghosts"
SEATS = ["black_top_hat", "gray_top_hat", "white_top_hat", "red_top_hat", "blue_top_hat", "front_man"]
MIN = 60_000
QUIET = {"op_chance": {"scavenge": 0.0, "patrol": 0.0, "trade_run": 0.0, "raid": 0.0}}


def ghosts(s) -> dict:
    return one(s, "SELECT * FROM groups WHERE content_ref = ?", (GHOSTS,))


def depot(s) -> dict:
    g = ghosts(s)
    return one(s, "SELECT * FROM settlements WHERE group_id = ?", (g["group_id"],))


def seat_holders(s) -> dict[str, str]:
    g = ghosts(s)
    out = {"black_top_hat": g["leader_id"]}
    for r in all_rows(s, "SELECT role, actor_id FROM group_members WHERE group_id = ? ORDER BY actor_id", (g["group_id"],)):
        if r["role"] in SEATS:
            out[r["role"]] = r["actor_id"]
    return out


def ghost_record(s):
    return s.store.canon.get(GHOSTS)


def hold_still(s, **more):
    tune(s, world=QUIET, hordes={"drift_chance": 0.0, "mega_daily_chance": {k: 0.0 for k in
                                                                             s.store.rules.hordes.mega_daily_chance}},
         **more)


# =========================================================================== worldgen
def test_the_depot_is_built_to_outlast_the_world(gw):
    """WG-18/23: one sealed place behind one locked gate, in the first zone of the record's
    zone_kinds the region has; twenty-odd thousand people; defences, sanitation 10, its own power;
    never anyone's home settlement."""
    s = gw
    rec = ghost_record(s).behaviour.enclave
    d = depot(s)
    site = one(s, "SELECT * FROM places WHERE place_id = ?", (d["place_id"],))
    assert (site["kind"], site["indoor"], site["name"], site["held"], site["parent_id"]) == ("tunnel", 1, rec.name, 1, None)
    assert json.loads(site["props"])["enclave"] == GHOSTS
    kinds = [r["kind"] for r in all_rows(s, "SELECT kind FROM zones WHERE kind != 'exterior' ORDER BY zone_id")]
    want = next((k for k in rec.zone_kinds if k in kinds), None)
    zone = one(s, "SELECT * FROM zones WHERE zone_id = ?", (site["zone_id"],))
    if want:
        first = one(s, "SELECT zone_id FROM zones WHERE kind = ? ORDER BY zone_id", (want,))["zone_id"]
        assert zone["zone_id"] == first
    [gate] = all_rows(s, "SELECT * FROM portals WHERE place_a = ? OR place_b = ?", (d["place_id"], d["place_id"]))
    hub = one(s, "SELECT place_id FROM places WHERE zone_id = ? AND kind = 'street' AND name = ?",
              (zone["zone_id"], zone["name"]))["place_id"]
    assert {gate["place_a"], gate["place_b"]} == {hub, d["place_id"]}
    assert (gate["kind"], gate["name"], gate["is_open"], gate["is_locked"], gate["lock_quality"]) == ("door", rec.gate, 0, 1, 4)
    anchors = {r["name"] for r in all_rows(s, "SELECT name FROM anchors WHERE place_id = ?", (d["place_id"],))}
    assert anchors == {"the intake crown", "the council room"}
    unnamed = s.store.query_one("SELECT SUM(count) FROM cohorts WHERE settlement_id = ?", (d["settlement_id"],))[0]
    named = s.store.query_one("SELECT COUNT(*) FROM group_members WHERE group_id = ?", (ghosts(s)["group_id"],))[0]
    assert rec.population[0] <= unnamed + named <= rec.population[1]
    assert (d["defences"], d["sanitation"], d["power"], d["lockdown"]) == (10, 10, 1, 0)
    assert s.store.query_one("SELECT COUNT(*) FROM positions WHERE body_id = ? AND place_id = ?", (pc(s), d["place_id"]))[0] == 0


def test_the_council_and_the_front_man_have_names_of_their_own(gw):
    """WG-27: one generated person per seat — the Black Top Hat leads; the Front Man is about
    forty; each holds the seat as their group role and the title as their occupation."""
    s = gw
    held = seat_holders(s)
    assert sorted(held) == sorted(SEATS)
    assert len(set(held.values())) == len(SEATS)
    titles = {ld.seat: ld.title for ld in ghost_record(s).leaders}
    for seat, actor in held.items():
        dossier = json.loads(one(s, "SELECT d.baseline_json FROM dossiers d JOIN actors a ON a.dossier_id = d.dossier_id "
                                    "WHERE a.actor_id = ?", (actor,))["baseline_json"])
        if seat != "black_top_hat":
            assert dossier["identity"]["occupation_now"] == titles[seat]
        assert one(s, "SELECT alive FROM bodies WHERE body_id = ?", (actor,))["alive"] == 1
    age = one(s, "SELECT age_years FROM bodies WHERE body_id = ?", (held["front_man"],))["age_years"]
    assert 38 <= age <= 44


def test_enclave_factions_are_listed_apart(canon, store):
    """WG-10: an enclave faction is never a character's placement faction nor one of WG-18's k."""
    from as_engine.contracts.common import Difficulty, Era
    from as_engine.contracts.dossier import WorldgenBias
    from as_engine.kernel.rng import Rng
    with store.transaction() as tx:
        p, _ = wg_params.generate_params(Rng(5), tx, Difficulty.NORMAL, Era.MATURE, WorldgenBias(), 2000)
    v = wg_params.flat_values(p)
    assert GHOSTS not in [ref for ref, _ in placement.eligible_factions(canon, v)]
    assert [ref for ref, _ in placement.enclave_factions(canon, v)] == ([GHOSTS] if v["faction_density"] >= 2 else [])


def test_a_council_seat_must_be_a_leaders_seat(tmp_path, core_pack_dir):
    """CNT-15."""
    import shutil

    from as_engine.content.pack import load_canon
    pack = tmp_path / "core"
    shutil.copytree(core_pack_dir, pack)
    f = pack / "factions" / "ghosts.yaml"
    f.write_text(f.read_text(encoding="utf-8").replace("seats: [black_top_hat, gray_top_hat,",
                                                       "seats: [black_top_hat, green_top_hat,"), encoding="utf-8")
    _c, issues = load_canon([pack])
    assert any(i.code == "CNT-15" and "green_top_hat" in i.message for i in issues if i.severity == "error")


# =========================================================================== FAC-02 the council
def test_the_council_meets_every_week(gw):
    """FAC-02: the first meeting on a day divisible by every_days at the council hour; the seats
    gather in the council room; in_session while it sits; adjourned after its hours; the next one a
    week on."""
    s = gw
    hold_still(s)
    c = ghost_record(s).behaviour.council
    g = ghosts(s)["group_id"]
    t0 = now(s)
    run(s, 0.01)
    q = one(s, "SELECT * FROM event_queue WHERE type = 'COUNCIL' AND status = 'pending'")
    assert q is not None and q["subject_id"] == g
    due = q["due_at"]
    assert due == factions.next_meeting(t0, c) and (due // DAY) % c.every_days == 0 and due % DAY == c.hour * H
    run(s, (due - now(s)) / H + 0.5)
    [meet] = [r for r in rows(s, "COUNCIL_MEETING")]
    held = seat_holders(s)
    council = {held[x] for x in c.seats}
    assert set(meet["payload"]["present"]) | set(meet["payload"]["absent"]) == council
    room = one(s, "SELECT anchor_id FROM anchors WHERE place_id = ? AND name = 'the council room'", (depot(s)["place_id"],))
    for a in meet["payload"]["present"]:
        pos = one(s, "SELECT place_id, anchor_id FROM positions WHERE body_id = ?", (a,))
        assert (pos["place_id"], pos["anchor_id"]) == (depot(s)["place_id"], room["anchor_id"])
    assert held["front_man"] not in council, "the Front Man is not a seat of the council"
    assert factions.in_session(s.store, g, now(s)) == meet["event_id"]
    run(s, c.hours)
    [adj] = rows(s, "COUNCIL_ADJOURNED")
    assert adj["payload"] == {"group_id": g, "meeting": meet["event_id"]} and adj["at"] == meet["at"] + int(c.hours * H)
    assert factions.in_session(s.store, g, now(s)) is None
    nxt = one(s, "SELECT due_at FROM event_queue WHERE type = 'COUNCIL' AND status = 'pending'")
    assert nxt["due_at"] == meet["at"] + c.every_days * DAY


# =========================================================================== FAC-03 route watch
def _force_mega(s, eta=6, size=20000):
    tune(s, world=QUIET, hordes={"drift_chance": 0.0,
                                 "mega_daily_chance": {k: 50.0 for k in s.store.rules.hordes.mega_daily_chance},
                                 "mega_ramp_days": 1, "mega_eta_days": [eta, eta],
                                 "mega_size": {k: [size, size] for k in s.store.rules.hordes.mega_size}})
    run(s, 24)
    m = one(s, "SELECT * FROM hordes WHERE kind = 'mega'")
    tune(s, hordes={"mega_daily_chance": {k: 0.0 for k in s.store.rules.hordes.mega_daily_chance}})
    return m


def test_the_route_watch_sees_it_form(gw):
    """FAC-03: at the Mega Horde's forming, ROUTE_WATCH_REPORT and every seat holder holds that a
    horde is coming by the gateway's hub — days before any bird flies."""
    s = gw
    m = _force_mega(s, eta=10)
    [rep] = rows(s, "ROUTE_WATCH_REPORT")
    formed = next(r for r in rows(s, "HORDE_FORMED") if r["payload"]["horde_id"] == m["horde_id"])
    gate = json.loads(m["route"])[1]
    assert rep["payload"] == {"group_id": ghosts(s)["group_id"], "horde_id": m["horde_id"], "gateway_hub": gate,
                              "eta_at": json.loads(m["props"])["eta_at"]}
    assert rep["at"] == formed["at"] and rep["seq"] > formed["seq"]
    assert rows(s, "HORDE_SIGN") == [], "ten days out: no bird has flown yet"
    for actor in seat_holders(s).values():
        h = one(s, "SELECT p.* FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id WHERE h.holder_id = ? "
                   "AND p.predicate = 'horde_coming' AND h.superseded_by IS NULL", (actor,))
        assert h is not None and (h["subject_type"], h["subject_id"]) == ("place", gate), actor


def test_the_depot_seals_while_it_passes_and_is_never_broken(gw):
    """FAC-01/03: lockdown from the Mega Horde's first region passage until it is gone; the Depot
    is pressed but never breached (HRD-08); no operation leaves it while sealed (OPS-01)."""
    s = gw
    m = _force_mega(s, eta=2, size=20000)
    d = depot(s)
    eta = json.loads(m["props"])["eta_at"]
    run(s, (eta - now(s)) / H + 24)
    locks = [r["payload"] for r in rows(s, "SETTLEMENT_CHANGE") if r["payload"]["field"] == "lockdown"]
    assert locks and locks[0] == {"settlement_id": d["settlement_id"], "field": "lockdown", "old": 0, "new": 1,
                                  "reason": "mega horde"}
    assert depot(s)["lockdown"] == 1
    tune(s, world={"op_chance": {"scavenge": 1.0, "patrol": 1.0, "trade_run": 1.0, "raid": 0.0}})
    run(s, 24)
    g = ghosts(s)["group_id"]
    assert not [r for r in rows(s, "FACTION_OPERATION") if r["payload"]["group_id"] == g and r["payload"].get("step") == "depart"]
    tune(s, world=QUIET)
    presses = [r["payload"] for r in rows(s, "HORDE_PRESSED") if r["payload"]["settlement_id"] == d["settlement_id"]]
    assert all(p["breached"] is False and p["killed"] == 0 for p in presses)
    run(s, 40 * 24)
    gone = [r for r in rows(s, "HORDE_GONE") if r["payload"]["horde_id"] == m["horde_id"]]
    assert gone
    locks = [r["payload"] for r in rows(s, "SETTLEMENT_CHANGE") if r["payload"]["field"] == "lockdown"]
    assert locks[-1]["new"] == 0 and locks[-1]["reason"] == "horde gone" and depot(s)["lockdown"] == 0


def test_a_crowd_at_the_depot_gate_never_gets_in(gw):
    """INF-13: the enclave's gate strains like any door and holds whatever the strain."""
    s = gw
    hold_still(s)
    d = depot(s)
    zone = one(s, "SELECT zone_id FROM places WHERE place_id = ?", (d["place_id"],))["zone_id"]
    z = one(s, "SELECT * FROM zones WHERE zone_id = ?", (zone,))
    hub = one(s, "SELECT place_id FROM places WHERE zone_id = ? AND kind = 'street' AND name = ?", (zone, z["name"]))["place_id"]
    [gate] = all_rows(s, "SELECT * FROM portals WHERE place_a = ? OR place_b = ?", (d["place_id"], d["place_id"]))
    tune(s, infected={"portal_holds_min": {"door": 3}, "energy_period_s": {infected.SHAMBLER: 100000}})
    target = seat_holders(s)["gray_top_hat"]
    with s.store.transaction() as tx:
        x, y = space.portal_point(tx, gate["portal_id"], hub)
        made = [infected.spawn(tx, s.rng, hub, infected.SHAMBLER, now(s), turn(s), None, x_m=x, y_m=y) for _ in range(4)]
        for b in made:
            infected.attract(tx, b, target, now(s), None, turn(s), reason="noise")
    run(s, 0.2)
    g = one(s, "SELECT * FROM portals WHERE portal_id = ?", (gate["portal_id"],))
    assert g["strain_min"] >= 3 and (g["is_open"], g["is_locked"]) == (0, 1)
    assert not any(r["payload"].get("kind") == "breaking" for r in rows(s, "NOISE"))


# =========================================================================== FAC-04/05 DECON
def _kill(s, victim, killer):
    """Test setup: ``killer`` puts a catastrophic wound in ``victim``'s head (the HARM names the
    killer as its actor, as a real attack's does)."""
    with s.store.transaction() as tx:
        blow = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=now(s), turn_index=turn(s),
                                     actor_id=killer, payload={"actor_id": killer, "def_id": "strike_melee", "verb": "attack",
                                                               "target_id": victim}))
        bodies.apply_harm(tx, victim, WoundSpec("head", "blunt", "catastrophic", 0), now(s), blow.event_id, turn(s), s.rng)
    assert one(s, "SELECT alive FROM bodies WHERE body_id = ?", (victim,))["alive"] == 0


def _outsider(s) -> str:
    """A living named human of another group, away from the PC."""
    g = ghosts(s)["group_id"]
    near = area(s)
    for r in all_rows(s, "SELECT m.actor_id FROM group_members m JOIN bodies b ON b.body_id = m.actor_id "
                         "WHERE m.group_id != ? AND b.alive = 1 AND b.kind = 'human' ORDER BY m.actor_id", (g,)):
        where = one(s, "SELECT place_id FROM positions WHERE body_id = ?", (r["actor_id"],))
        if where and where["place_id"] not in near and r["actor_id"] != pc(s):
            return r["actor_id"]
    pytest.skip("nobody outside the PC's area")


def _to_next_meeting(s, fed=()):
    """Run to just past the next council meeting; the bodies in ``fed`` eat and drink every 12
    hours on the way (the player's character would)."""
    q = one(s, "SELECT due_at FROM event_queue WHERE type = 'COUNCIL' AND status = 'pending'")
    if q is None:
        run(s, 0.01)
        q = one(s, "SELECT due_at FROM event_queue WHERE type = 'COUNCIL' AND status = 'pending'")
    while q["due_at"] - now(s) > 12 * H:
        run(s, 12)
        with s.store.transaction() as tx:
            for b in fed:
                for need in ("thirst", "hunger"):
                    bodies.refresh_need(tx, b, need, now(s), None, turn(s))
    run(s, (q["due_at"] - now(s)) / H + 0.01)


def test_a_dead_ghost_is_answered_off_screen(gw):
    """FAC-04/05: the next council orders DECON — five people of the Depot's own count, masked
    operators — who go where the killer is, kill them (cause 'decon'), leave the smile, and come home."""
    s = gw
    hold_still(s)
    victim = seat_holders(s)["white_top_hat"]
    killer = _outsider(s)
    d = depot(s)
    adults0 = s.store.query_one("SELECT SUM(count) FROM cohorts WHERE settlement_id = ? AND age_band = 'adult'",
                                (d["settlement_id"],))[0]
    _kill(s, victim, killer)
    _to_next_meeting(s)
    [meet] = rows(s, "COUNCIL_MEETING")
    [op] = [r for r in rows(s, "FACTION_OPERATION") if r["payload"].get("kind") == "decon"]
    team = op["payload"]["participants"]
    rec = ghost_record(s).behaviour.decon
    assert len(team) == rec.team and op["payload"]["target_id"] == killer and op["cause_event_id"] == meet["event_id"]
    assert s.store.query_one("SELECT SUM(count) FROM cohorts WHERE settlement_id = ? AND age_band = 'adult'",
                             (d["settlement_id"],))[0] == adults0 - rec.team, "taken from the Depot's own people"
    g = ghosts(s)["group_id"]
    for b in team:
        assert one(s, "SELECT role FROM group_members WHERE group_id = ? AND actor_id = ?", (g, b))["role"] == "operator"
        dossier = json.loads(one(s, "SELECT d.baseline_json FROM dossiers d JOIN actors a ON a.dossier_id = d.dossier_id "
                                    "WHERE a.actor_id = ?", (b,))["baseline_json"])
        assert dossier["identity"]["occupation_now"] == rec.occupation
        assert dossier["appearance"]["clothing_usual"] == rec.appearance
        assert [m["faction"] for m in dossier["social"]["memberships"]] == [GHOSTS]
    where = one(s, "SELECT place_id FROM positions WHERE body_id = ?", (killer,))["place_id"]
    run(s, 2 * s.store.rules.world.op_leg_h + s.store.rules.world.op_dwell_h + 1)
    death = next(r for r in rows(s, "DEATH") if r["payload"]["body_id"] == killer)
    assert death["payload"]["cause"] == "decon"
    mark = [t for t in all_rows(s, "SELECT * FROM traces WHERE kind = 'mark'") if t["place_id"] == hordes.target(s.store, where)
            or t["place_id"] == where]
    assert mark and mark[0]["text"] == rec.mark
    assert one(s, "SELECT status FROM operations WHERE op_id = ?", (op["payload"]["op_id"],))["status"] == "done"


def test_the_player_is_hunted_on_screen(gw):
    """FAC-05: a killer in the active area — the PC — is not killed by code: the team walks into
    the PC's place with a goal and hunts."""
    s = gw
    hold_still(s)
    with s.store.transaction() as tx:        # the opening's dead are put down first: this is about the Ghosts
        for r in tx.query("SELECT body_id FROM bodies WHERE kind = 'infected' AND alive = 1 ORDER BY body_id"):
            bodies.die(tx, s.rng, r[0], now(s), None, turn(s), cause="test")
    victim = seat_holders(s)["red_top_hat"]
    _kill(s, victim, pc(s))
    _to_next_meeting(s, fed=[pc(s)])
    [op] = [r for r in rows(s, "FACTION_OPERATION") if r["payload"].get("kind") == "decon"]
    run(s, s.store.rules.world.op_leg_h + 0.01)
    assert one(s, "SELECT alive FROM bodies WHERE body_id = ?", (pc(s),))["alive"] == 1
    here = one(s, "SELECT place_id FROM positions WHERE body_id = ?", (pc(s),))["place_id"]
    steps = [r["payload"].get("step") for r in rows(s, "FACTION_OPERATION") if r["payload"]["op_id"] == op["payload"]["op_id"]]
    assert "hunt" in steps and one(s, "SELECT alive FROM bodies WHERE body_id = ?", (pc(s),))["alive"] == 1
    near = area(s)
    for b in op["payload"]["participants"]:
        where = one(s, "SELECT place_id FROM positions WHERE body_id = ?", (b,))["place_id"]
        moved = [r for r in rows(s, "MOVE") if r["actor_id"] == b and r["payload"]["to_place"] == here]
        assert where in near and (moved or where != here), "on screen now: the turn moves them from here on (WORLD-04)"
        goal = one(s, "SELECT goal_text FROM actors WHERE actor_id = ?", (b,))["goal_text"]
        assert goal.endswith("killed one of ours. Deconstruct them and leave nothing that points home.")


def test_the_dead_do_not_start_a_war(gw):
    """FAC-04: a Ghost killed by the dead (an infected HARM names no one) orders nothing."""
    s = gw
    hold_still(s)
    victim = seat_holders(s)["blue_top_hat"]
    with s.store.transaction() as tx:
        z = one(s, "SELECT place_id FROM positions WHERE body_id = ?", (victim,))["place_id"]
        biter = infected.spawn(tx, s.rng, z, infected.SHAMBLER, now(s), turn(s), None)
        bite = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=now(s), turn_index=turn(s),
                                     actor_id=biter, payload={"actor_id": biter, "def_id": "infected_bite"}))
        bodies.apply_harm(tx, victim, WoundSpec("neck", "bite", "catastrophic", 3), now(s), bite.event_id, turn(s), s.rng)
    _to_next_meeting(s)
    assert rows(s, "COUNCIL_MEETING") and not [r for r in rows(s, "FACTION_OPERATION") if r["payload"].get("kind") == "decon"]


def test_the_depot_is_pressed_never_broken_into(gw):
    """HRD-08 + FAC-01: however many press on it, the Depot's p is 0 — pressure recorded, nobody
    killed, nobody bitten."""
    s = gw
    hold_still(s)
    d = depot(s)
    zone = one(s, "SELECT zone_id FROM places WHERE place_id = ?", (d["place_id"],))["zone_id"]
    with s.store.transaction() as tx:
        hordes.change(tx, zone, infected.SHAMBLER, 50000, 0, "test", now(s), turn(s), None)
        hid = hordes.form(tx, "drift", zone, {infected.SHAMBLER: 50000}, d["place_id"], now(s), turn(s), None)
        got = [hordes.press(tx, s.rng, hid, d["settlement_id"], now(s) + k, turn(s), None) for k in range(5)]
    assert all(e.payload["breached"] is False and e.payload["killed"] == 0 and e.payload["bitten"] == [] for e in got)
    assert all(e.payload["pressure"] > 1 for e in got)
