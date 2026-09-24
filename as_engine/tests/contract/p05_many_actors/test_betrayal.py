"""When it is them or you (P5, the owner's H1). Rules: action/effects.py shove_toward and the 'leg'
shot, physical/bodies.py capacity can_run, mind/affordance.py requires.can_run, and the strain and
betrayal cascades CAS-019..023 (as_content/packs/core/cascade/stress.yaml; action/cascade.py
adjust_stress).

The owner: "Somebody pushing the person who's been pissing them off into a horde of oncoming
shamblers as a distraction is not unheard of. That can happen to anybody. Shot in the leg and left
to feed the crowd." And it costs: whoever saw it will not trust the one who did it again, the story
travels, and whoever lived through it never forgets.

A street at noon (a dict scenario): Ray a step from Cal, June watching from the kerb, Nita across
the road with a revolver, and one of the dead four metres past Cal.
"""

from __future__ import annotations

import copy

import pytest

import helpers
from as_engine.action import cascade, effects
from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.contracts.events import Event, EventType
from as_engine.mind import mind as mindmod, perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.physical import bodies
from as_engine.physical.bodies import WoundSpec
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(5)

HORIZON = 600_000

STREET = {
    "schema": "as.scenario.v1", "name": "the_street", "seed": 61, "start": {"day": 300, "time": "12:00"},
    "places": [{"id": "street", "name": "Main Street", "kind": "outdoor", "indoor": False, "material": "open_air",
                "light": 3, "width_m": 40, "depth_m": 20,
                "anchors": [{"id": "far_corner", "name": "far corner", "x": 38, "y": 18}]}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "street", "x": 36, "y": 3},
        {"id": "ray", "dossier": "core:actor/ray_delgado", "place": "street", "x": 9.5, "y": 10},
        {"id": "cal", "stub": {"name": "Cal Hobbs", "age": 30, "sex": "male"}, "place": "street", "x": 10, "y": 10},
        {"id": "june", "dossier": "core:actor/june_okafor", "place": "street", "x": 8, "y": 13},
        {"id": "nita", "dossier": "core:actor/nita_reyes", "place": "street", "x": 10, "y": 2,
         "inventory": [{"item": "core:item/revolver_38", "slot": "hand_r", "label": "revolver", "props": {"rounds": 6}}]},
        {"id": "dead", "infected": "ZOMBIE_ARCHETYPE_SHAMBLER01", "controller": "policy", "place": "street", "x": 14, "y": 10},
    ],
    "relationships": [{"from": "june", "to": "cal", "kind": "friend", "trust": 2, "affection": 2}],
}


@pytest.fixture
def street(fixture_packs, core_pack_dir):
    worlds = []

    def _load(change=None):
        spec = copy.deepcopy(STREET)
        if change is not None:
            change(spec)
        w = load_scenario(spec, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        return w

    yield _load
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def run(w, *intents, rng, at=None):
    t = now(w) if at is None else at
    with w.store.transaction() as tx:
        return resolve_wave(tx, rng, barrier(tx, list(intents)), t, 0, horizon_ms=t + HORIZON)


def of(evs, type_, actor=None):
    return [e for e in evs if e.type == type_ and (actor is None or e.actor_id == actor)]


def one(evs, type_, actor=None):
    got = of(evs, type_, actor)
    assert len(got) == 1, [(e.type, e.payload) for e in evs]
    return got[0]


def pos(w, local):
    r = w.store.query_one("SELECT x_m, y_m FROM positions WHERE body_id = ?", (w.id(local),))
    return (r[0], r[1])


def posture(w, local):
    return w.store.query_one("SELECT posture FROM bodies WHERE body_id = ?", (w.id(local),))[0]


def move_dead(w, x, y):
    def change(spec):
        next(b for b in spec["bodies"] if b["id"] == "dead").update(x=x, y=y)
    return change


def strain(w, local):
    return w.store.query_one("SELECT stress FROM actors WHERE actor_id = ?", (w.id(local),))[0]


def wound(w, local, anatomy, severity, wtype="cut", at=None):
    t = now(w) if at is None else at
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=0, payload={"what": "test"}))
        bodies.apply_harm(tx, w.id(local), WoundSpec(anatomy, wtype, severity, 0), t, c.event_id, 0, w.rng)


def strain_rules(w, *ids):
    return [r for r in w.canon.all("cascade") if r.id in ids]


# --------------------------------------------------------------------------- shoved to the dead
def test_shoved_into_the_dead(street):
    """Ray wins the shove (d10 1 against 10): Cal is pushed two metres toward the shambler, lands on
    his back and it turns on him — by sight, the way the dead always find you."""
    w = street()
    t = now(w)
    i = helpers.make_intent(w, "ray", "shove_toward_dead", target="cal")
    evs = run(w, i, rng=helpers.ScriptedRng(1, 10))
    start = one(evs, "ACTION_START", w.id("ray"))
    assert start.payload["def_id"] == "shove_toward_dead" and start.payload["seen"] == "shoves {target} toward the dead"
    mv = one(evs, "MOVE", w.id("cal"))
    assert mv.cause_event_id == start.event_id
    assert pos(w, "cal") == pytest.approx((12.0, 10.0)), "at most two metres from where he stood"
    pc = [e for e in of(evs, "POSTURE_CHANGE") if e.payload["body_id"] == w.id("cal")]
    assert [e.payload["posture"] for e in pc] == ["lying"] and posture(w, "cal") == "lying"
    drift = one(evs, "INFECTED_DRIFT")
    assert (drift.payload["body_id"], drift.payload["target_id"], drift.payload["reason"]) == \
        (w.id("dead"), w.id("cal"), "sight")
    assert drift.cause_event_id == mv.event_id and drift.at == mv.at
    assert w.store.query_one("SELECT target_id FROM infected_state WHERE body_id = ?", (w.id("dead"),))[0] == w.id("cal")
    assert one(evs, "ACTION_COMPLETE", w.id("ray")).payload["result"] == "shoved_to_the_dead"


def test_right_into_its_arms_but_not_through_it(street):
    """The dead one a metre and a half off: Cal lands half a metre short of it."""
    w = street(move_dead(None, 11.5, 10))
    run(w, helpers.make_intent(w, "ray", "shove_toward_dead", target="cal"), rng=helpers.ScriptedRng(1, 10))
    assert pos(w, "cal") == pytest.approx((11.0, 10.0))


def test_the_nearest_of_the_dead_to_him(street):
    """With two of the dead about, Cal goes toward the one nearest HIM — the one at his back, not the
    one in front of Ray."""
    def two(spec):
        next(b for b in spec["bodies"] if b["id"] == "dead").update(x=10, y=14)
        spec["bodies"].append({"id": "other_dead", "infected": "ZOMBIE_ARCHETYPE_SHAMBLER01", "controller": "policy",
                               "place": "street", "x": 5, "y": 10})
    w = street(two)
    evs = run(w, helpers.make_intent(w, "ray", "shove_toward_dead", target="cal"), rng=helpers.ScriptedRng(1, 10))
    assert pos(w, "cal") == pytest.approx((10.0, 12.0))
    assert one(evs, "INFECTED_DRIFT").payload["body_id"] == w.id("dead")


def test_keeping_your_feet(street):
    """Cal wins the contest: he stays where he is and nothing turns toward him."""
    w = street()
    evs = run(w, helpers.make_intent(w, "ray", "shove_toward_dead", target="cal"), rng=helpers.ScriptedRng(10, 1))
    assert one(evs, "ACTION_COMPLETE", w.id("ray")).payload["result"] == "braced"
    assert not of(evs, "MOVE", w.id("cal")) and not of(evs, "INFECTED_DRIFT")
    assert pos(w, "cal") == (10, 10) and posture(w, "cal") == "standing"


def test_with_the_dead_gone_it_is_only_a_shove(street):
    def no_dead(spec):
        spec["bodies"] = [b for b in spec["bodies"] if b["id"] != "dead"]
    w = street(no_dead)
    evs = run(w, helpers.make_intent(w, "ray", "shove_toward_dead", target="cal"), rng=helpers.ScriptedRng(1, 10))
    assert one(evs, "ACTION_COMPLETE", w.id("ray")).payload["result"] == "knocked_down"
    assert not of(evs, "MOVE", w.id("cal")) and posture(w, "cal") == "lying"


# --------------------------------------------------------------------------- shot in the leg
def test_shot_in_the_leg_you_go_down(street):
    """Nita hits (d10 1): the leg the dice pick (choice index 1 -> the right), a revolver's wound for
    the band it landed, and Cal goes down. He can still crawl and walk; he cannot run."""
    w = street()
    evs = run(w, helpers.make_intent(w, "nita", "shoot_leg", target="cal", item="revolver"), rng=helpers.ScriptedRng(1, 1))
    band = one(evs, "CHECK_RESOLVED").payload["band"]
    harm = one(evs, "HARM").payload
    assert (harm["body_id"], harm["anatomy"], harm["type"], harm["severity"]) == \
        (w.id("cal"), "leg_r", "gunshot", effects.WEAPON_WOUNDS["medium"][band])
    down = [e for e in of(evs, "POSTURE_CHANGE") if e.payload["body_id"] == w.id("cal")]
    assert [e.payload["posture"] for e in down] == ["lying"]
    assert down[0].cause_event_id == one(evs, "HARM").event_id
    assert one(evs, "ACTION_COMPLETE", w.id("nita")).payload["result"] == "hit"
    cap = bodies.capacity(w.store, w.id("cal"))
    assert cap.conscious and not cap.can_run


def test_a_graze_to_the_leg_still_hobbles(street):
    """A light rifle's COST hit would be a minor wound anywhere else; in the leg it is at least
    significant — function loss 1, no running. The target number is read off a first, missed shot
    (d10 10); the second shot draws exactly that number (margin 0: COST)."""
    def rifle(spec):
        next(b for b in spec["bodies"] if b["id"] == "ray").update(x=20, y=16)   # nobody at Cal's shoulder for a stray
        nita = next(b for b in spec["bodies"] if b["id"] == "nita")
        nita["inventory"] = [{"item": "core:item/rifle_22", "slot": "hand_r", "label": "rifle", "props": {"rounds": 10}}]
    w = street(rifle)
    probe = run(w, helpers.make_intent(w, "nita", "shoot_leg", target="cal", item="rifle"), rng=helpers.ScriptedRng(10))
    target = one(probe, "CHECK_RESOLVED").payload["target"]
    assert not of(probe, "HARM")
    w2 = street(rifle)
    evs = run(w2, helpers.make_intent(w2, "nita", "shoot_leg", target="cal", item="rifle"),
              rng=helpers.ScriptedRng(target, 0))
    assert one(evs, "CHECK_RESOLVED").payload["band"] == "cost"
    harm = one(evs, "HARM").payload
    assert (harm["anatomy"], harm["severity"]) == ("leg_l", "significant")
    assert not bodies.capacity(w2.store, w2.id("cal")).can_run
    assert bodies.capacity(w2.store, w2.id("cal")).mobile, "he can still get up and walk"


def test_the_body_shot_is_unchanged(street):
    """Centre mass stays centre mass: no leg is picked and nobody is put down by the leg rule."""
    w = street()
    rng = helpers.ScriptedRng(1, 0)
    evs = run(w, helpers.make_intent(w, "nita", "shoot_center_mass", target="cal", item="revolver"), rng=rng)
    assert one(evs, "HARM").payload["anatomy"] == "chest"
    assert not any(purpose.startswith("leg:") for _, _, purpose in rng.asked)
    assert not [e for e in of(evs, "POSTURE_CHANGE") if e.payload["body_id"] == w.id("cal")]


# --------------------------------------------------------------------------- can_run
@pytest.mark.parametrize("anatomy,severity,runs", [
    ("leg_l", "minor", True), ("leg_l", "significant", False), ("foot_r", "significant", False),
    ("arm_l", "severe", True), ("chest", "severe", True),
])
def test_a_hurt_leg_or_foot_stops_you_running(street, anatomy, severity, runs):
    w = street()
    wound(w, "cal", anatomy, severity)
    cap = bodies.capacity(w.store, w.id("cal"))
    assert cap.can_run is runs and cap.mobile


def test_running_is_not_offered_on_a_shot_leg(street):
    w = street()
    t = now(w)

    def menu():
        with w.store.transaction() as tx:
            perception.compile_scene(tx, w.id("cal"), t, 0)
            return {o.def_id for o in enumerate_affordances(tx, w.id("cal"), w.canon.all("affordance"), t, 0).pool}

    before = menu()
    assert {"run_to_anchor", "flee_threat"} <= before
    wound(w, "cal", "leg_r", "significant", "gunshot", t)
    after = menu()
    assert not {"run_to_anchor", "flee_threat"} & after
    assert "move_to_anchor" in after, "he can still walk"


# --------------------------------------------------------------------------- what it costs, and what wears people down
def witnessed_shove(w):
    t = now(w)
    evs = run(w, helpers.make_intent(w, "ray", "shove_toward_dead", target="cal"), rng=helpers.ScriptedRng(1, 10))
    with w.store.transaction() as tx:
        for who in ("cal", "june", "nita"):
            perception.compile_aftermath(tx, w.id(who), evs, t + 5000, 0)
    return evs, t


def test_everyone_who_saw_it_stops_trusting_him(street):
    w = street()
    evs, t = witnessed_shove(w)
    start = one(evs, "ACTION_START", w.id("ray"))
    with w.store.transaction() as tx:
        out = cascade.sweep(tx, [start], strain_rules(w, "CAS-022"), t + 5000, 0)
    changes = [e for e in out if e.type == "RELATION_CHANGE"]
    assert sorted(w.local(e.payload["from_id"]) for e in changes) == ["cal", "june", "nita"]
    assert all(e.payload["to_id"] == w.id("ray") and e.payload["axis"] == "trust" and e.rule_cited == "CAS-022"
               for e in changes)
    trust = dict(w.store.query("SELECT from_id, trust FROM relationships WHERE to_id = ?", (w.id("ray"),)))
    assert trust[w.id("june")] <= -3


def test_he_never_forgets_it(street):
    w = street()
    evs, t = witnessed_shove(w)
    start = one(evs, "ACTION_START", w.id("ray"))
    resolve0 = w.store.query_one("SELECT resolve_cur FROM actors WHERE actor_id = ?", (w.id("cal"),))[0]
    with w.store.transaction() as tx:
        cascade.sweep(tx, [start], strain_rules(w, "CAS-023"), t + 5000, 0)
    loops = [dict(r) for r in w.store.query("SELECT * FROM open_loops WHERE holder_id = ? AND kind = 'grudge'", (w.id("cal"),))]
    assert len(loops) == 1 and loops[0]["strength"] == 3
    assert w.id("ray") in loops[0]["subject_ids"]
    assert "shoved you to the dead" in loops[0]["text"] and "{subject}" not in loops[0]["text"]
    resolve1 = w.store.query_one("SELECT resolve_cur FROM actors WHERE actor_id = ?", (w.id("cal"),))[0]
    assert resolve1 < resolve0


def test_seeing_someone_die_wears_you_down_more_if_you_loved_them(street):
    """CAS-019: June (affection 2 toward Cal) and Nita (none) both see Cal die: +2 for Nita, +4 for
    June (the bond adds its affection, max 3); Ray saw it too: +2. Nothing for the one who died."""
    w = street()
    t = now(w)
    with w.store.transaction() as tx:
        d = bodies.die(tx, w.rng, w.id("cal"), t, None, 0, cause="test")
        for who in ("june", "nita", "ray"):
            perception.compile_aftermath(tx, w.id(who), [d], t + 1000, 0)
    before = {x: strain(w, x) for x in ("june", "nita", "ray")}
    with w.store.transaction() as tx:
        out = cascade.sweep(tx, [d], strain_rules(w, "CAS-019"), t + 1000, 0)
    assert strain(w, "nita") == min(10, before["nita"] + 2)
    assert strain(w, "june") == min(10, before["june"] + 4)
    assert strain(w, "ray") == min(10, before["ray"] + 2)
    assert all(e.actor_id != w.id("cal") for e in out if e.type == "RESOLVE_CHANGE"), "not the one who died"
    assert all(e.rule_cited == "CAS-019" for e in out if e.type == "RESOLVE_CHANGE")


@pytest.mark.parametrize("stage,delta", [(1, 0), (2, 1), (3, 1)])
def test_hunger_past_the_first_pangs_wears_you_down(street, stage, delta):
    w = street()
    t = now(w)
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.NEED_STAGE, writer="physical.bodies", actor_id=w.id("june"), at=t,
                                   turn_index=0, target_ids=[w.id("june")],
                                   payload={"body_id": w.id("june"), "need": "hunger", "stage": stage}))
    before = strain(w, "june")
    with w.store.transaction() as tx:
        cascade.sweep(tx, [ev], strain_rules(w, "CAS-020"), t, 0)
    assert strain(w, "june") == min(10, before + delta)


def test_a_night_s_sleep_takes_the_edge_off(street):
    w = street()
    t = now(w)
    with w.store.transaction() as tx:
        from as_engine.mind import actor
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=0, payload={"what": "test"}))
        actor.adjust_stress(tx, w.id("june"), 5, c.event_id, t, 0)
        ev = tx.commit_event(Event(type=EventType.ACTION_COMPLETE, writer="action.resolve", actor_id=w.id("june"), at=t,
                                   turn_index=0, payload={"actor_id": w.id("june"), "def_id": "sleep", "result": "done",
                                                          "band": None}))
    before = strain(w, "june")
    with w.store.transaction() as tx:
        cascade.sweep(tx, [ev], strain_rules(w, "CAS-021"), t, 0)
    assert strain(w, "june") == before - 2
