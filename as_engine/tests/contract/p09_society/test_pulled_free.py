"""Pulled free (D-207). physical.bodies.loosen (a hand that can no longer hold lets go), action.resolve (after every
landing), action.effects shove and let_go, mind.affordance (break_grip / let_go only where there is a hand), world.infected
step; core CAS-080..082 with action.cascade trigger.rescuer, rescued_by and saw_them_saved.

One of the dead had hold of Cal. Owen put a bullet through its head — and Cal stayed held: a dead hand kept its grip
for ever, Cal could not move, and the corpse stayed out of its horde. Nobody could let go of anyone, a man who walked
off left his hand behind, and "Break Owen's grip on you" was offered to anyone standing next to him in a fight. Now a
hand that is dead, out cold, asleep or out of reach lets go; a shove that knocks the holder down breaks its hold; and
whoever pulls you out of the dead's hands — or out of someone's grip when you were not fighting — has your trust, and
you owe them your life. Those who love you and saw it trust them too.

A farm yard at noon (a dict scenario): Cal with one of the dead at his shoulder, Owen a step away with a gun, June —
Cal's friend — a few metres off, Mara by the gate.
"""

from __future__ import annotations

import copy

import pytest

import helpers
from as_engine.action import cascade
from as_engine.action.resolve import resolve_wave
from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.kernel import clock
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec
from as_engine.testing.scenario import load_scenario
from as_engine.world import infected

pytestmark = pytest.mark.phase(9)

S = 1000
MIN = 60 * S

YARD = {
    "schema": "as.scenario.v1", "name": "the_yard", "seed": 1, "start": {"day": 300, "time": "12:00"},
    "places": [{"id": "yard", "name": "Farm yard", "kind": "outdoor", "indoor": False, "material": "open_air", "light": 3,
                "width_m": 40, "depth_m": 20, "anchors": [{"id": "gate", "name": "gate", "x": 38, "y": 2}]}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "yard", "x": 11.5, "y": 10,
         "inventory": [{"item": "core:item/glock_19", "slot": "hand_r", "label": "gun"}]},
        {"id": "cal", "stub": {"name": "Cal Hobbs", "age": 30, "sex": "male"}, "place": "yard", "x": 10, "y": 10},
        {"id": "june", "dossier": "core:actor/june_okafor", "place": "yard", "x": 8, "y": 12},
        {"id": "mara", "stub": {"name": "Mara Voss", "age": 38, "sex": "female"}, "place": "yard", "x": 37, "y": 2},
        {"id": "dead", "infected": infected.SHAMBLER, "controller": "policy", "place": "yard", "x": 10.5, "y": 10},
    ],
    "relationships": [{"from": "june", "to": "cal", "kind": "friend", "trust": 2, "affection": 2}],
}


@pytest.fixture
def yard(fixture_packs, core_pack_dir):
    worlds = []

    def _load():
        w = load_scenario(copy.deepcopy(YARD), packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        with w.store.transaction() as tx:   # nothing scheduled but what a test starts
            for q in tx.query("SELECT queue_id FROM event_queue WHERE status = 'pending' ORDER BY queue_id"):
                clock.cancel(tx, q[0], "test", now(w), None, 0)
        worlds.append(w)
        return w

    yield _load
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def grab(w, who, whom, at):
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=at, turn_index=0, payload={"what": "test"}))
        bodies.grip_event(tx, w.id(who), w.id(whom), at, c.event_id, 0)


def held(w, whom):
    return [w.local(h) for h in bodies.grips_on(w.store, w.id(whom))], w.store.query_one(
        "SELECT restrained FROM bodies WHERE body_id = ?", (w.id(whom),))[0]


def rel(w, a, b):
    r = w.store.query_one("SELECT trust, affection FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return tuple(r) if r else (0, 0)


def debts(w, who):
    return [tuple(r) for r in w.store.query("SELECT text, strength FROM open_loops WHERE holder_id = ? AND kind = 'debt_owing' "
                                            "AND status = 'open'", (w.id(who),))]


def blow(w, by, at_whom, at, *, severity=WoundSeverity.CATASTROPHIC, seen=("cal", "june")):
    """``by`` goes for ``at_whom`` and the blow lands; those named take in what they saw; the rescue rules are swept."""
    from as_engine.action._impl_p5b import _events_since
    with w.store.transaction() as tx:
        st = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=1, actor_id=w.id(by),
                                   payload={"actor_id": w.id(by), "def_id": "shoot_head", "verb": "attack",
                                            "target_id": w.id(at_whom), "visible": True,
                                            "seen": "takes careful aim at {target}'s head"}))
        bodies.apply_harm(tx, w.id(at_whom), WoundSpec(Anatomy.HEAD, WoundType.GUNSHOT, severity), at + 300, st.event_id, 1, w.rng)
        evs = _events_since(tx, st.seq - 1)
        for x in seen:
            perception.compile_aftermath(tx, w.id(x), evs, at + 800, 1)
        cascade.sweep(tx, evs, [r for r in w.canon.all("cascade") if r.id in ("CAS-080", "CAS-081", "CAS-082")], at + 900, 1)
    return evs


# --------------------------------------------------------------------------- loosen
def test_a_dead_hand_lets_go(yard):
    w = yard()
    t = now(w)
    grab(w, "dead", "cal", t)
    assert held(w, "cal") == (["dead"], 1)
    evs = blow(w, "pc", "dead", t + 1000, seen=())
    assert held(w, "cal") == ([], 0), "the dead hand let go"
    rel_ = next(e for e in evs if e.type == EventType.CONTROL_RELEASE)
    death = next(e for e in evs if e.type == EventType.DEATH)
    assert rel_.cause_event_id == death.event_id and rel_.payload == {"holder_id": w.id("dead"), "target_id": w.id("cal")}


def test_out_cold_or_asleep_a_hand_lets_go(yard):
    w = yard()
    t = now(w)
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("mara"), w.id("yard"), None, 9.0, 10.0, t, None, 0))
    grab(w, "mara", "cal", t)
    with w.store.transaction() as tx:
        bodies.posture_event(tx, w.id("mara"), "lying", t + 1000, None, 0, awareness="asleep")
    assert held(w, "cal") == ([], 0), "asleep"
    with w.store.transaction() as tx:
        bodies.wake(tx, w.id("mara"), t + 2000, None, 0)
    grab(w, "mara", "cal", t + 3000)
    w.store.conn.execute("UPDATE bodies SET blood_loss_pct = 35 WHERE body_id = ?", (w.id("mara"),))
    with w.store.transaction() as tx:
        out = bodies.death_test(tx, w.id("mara"), t + 4000, 0, w.rng, None)
    assert out.type == EventType.AWARENESS_CHANGE and out.payload["awareness"] == "unconscious"
    assert held(w, "cal") == ([], 0), "out cold"


def test_a_hand_that_walks_off_lets_go(yard):
    """The resolver loosens after every landing: Owen held Cal and walked to the gate."""
    w = yard()
    t = now(w)
    grab(w, "pc", "cal", t)
    it = helpers.make_intent(w, "pc", "move_to_anchor", destination="gate")
    with w.store.transaction() as tx:
        evs = resolve_wave(tx, w.rng, [it], t + 1000, 1, horizon_ms=t + 10 * MIN)
    assert held(w, "cal") == ([], 0)
    assert [e.type for e in evs][-1] == EventType.CONTROL_RELEASE


def test_letting_go(yard):
    w = yard()
    t = now(w)
    grab(w, "pc", "cal", t)
    with w.store.transaction() as tx:
        evs = resolve_wave(tx, w.rng, [helpers.make_intent(w, "pc", "let_go", "cal")], t + 1000, 1, horizon_ms=t + MIN)
    assert held(w, "cal") == ([], 0)
    assert next(e for e in evs if e.type == EventType.ACTION_COMPLETE).payload["result"] == "let_go"


def test_a_grip_is_offered_only_where_there_is_one(yard):
    """break_grip only from a hand on you; let_go only of someone you hold — and nobody standing next to you in a
    fight is offered as a grip to break."""
    w = yard()
    t = now(w)
    grab(w, "dead", "cal", t)

    def offered(who):
        with w.store.transaction() as tx:
            perception.compile_scene(tx, w.id(who), t, 0)
            aff = enumerate_affordances(tx, w.id(who), w.canon.all("affordance"), t, 0)
        return sorted((o.def_id, w.local(o.target_id)) for o in aff.pool if o.def_id in ("break_grip", "let_go"))

    assert offered("cal") == [("break_grip", "dead")], "Owen is a step away and holds nobody"
    assert offered("pc") == []
    grab(w, "pc", "cal", t + 100)
    assert offered("pc") == [("let_go", "cal")]


def test_shoved_off(yard):
    """A shove that knocks the holder down breaks its hold (the yard's seed: Owen's shove lands)."""
    w = yard()
    t = now(w)
    grab(w, "dead", "cal", t)
    with w.store.transaction() as tx:
        evs = resolve_wave(tx, w.rng, [helpers.make_intent(w, "pc", "shove", "dead")], t + 1000, 1, horizon_ms=t + MIN)
    assert next(e for e in evs if e.type == EventType.ACTION_COMPLETE).payload["result"] == "knocked_down"
    assert held(w, "cal") == ([], 0)


def test_done_feeding_it_lets_go_and_goes_back_to_its_horde(yard):
    w = yard()
    t = now(w)
    grab(w, "dead", "cal", t)
    with w.store.transaction() as tx:
        bodies.kill(tx, w.id("cal"), "harm", t + 1000, 0, w.rng)
        bodies.loosen(tx, w.id("dead"), t + 2000, None, 0)
    assert held(w, "cal")[0] == ["dead"], "still feeding"
    with w.store.transaction() as tx:
        late = t + 1000 + tx.rules.infected.feed_on_dead_min * MIN
        out = bodies.loosen(tx, w.id("dead"), late, None, 0)
    assert [e.type for e in out] == [EventType.CONTROL_RELEASE] and held(w, "cal")[0] == []


# --------------------------------------------------------------------------- CAS-080..082
def test_out_of_the_dead_s_hands(yard):
    w = yard()
    t = now(w)
    grab(w, "dead", "cal", t)
    before = rel(w, "june", "pc")
    blow(w, "pc", "dead", t + 1000)
    assert rel(w, "cal", "pc") == (2, 1)
    assert debts(w, "cal") == [("A tall, heavyset man got you out of the dead's hands. You owe them your life.", 3)], \
        "a stranger saved him: he knows him by sight"
    assert rel(w, "june", "pc") == (min(3, before[0] + 1), min(3, before[1] + 1)), "June saw Owen save her friend"


def test_it_has_to_be_seen_and_it_has_to_free_you(yard):
    w = yard()
    t = now(w)
    grab(w, "dead", "cal", t)
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=0, payload={"what": "test"}))
        tx.commit_event(space.move_event(tx, w.id("mara"), w.id("yard"), None, 9.5, 10.0, t, None, 0))
        bodies.grip_event(tx, w.id("mara"), w.id("cal"), t, c.event_id, 0)
    blow(w, "pc", "dead", t + 1000)
    assert rel(w, "cal", "pc") == (0, 0) and debts(w, "cal") == [], "Mara still has him: he is not free"


def test_breaking_free_yourself_owes_nobody(yard):
    w = yard()
    t = now(w)
    grab(w, "dead", "cal", t)
    with w.store.transaction() as tx:
        st = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=t + 1000, turn_index=1,
                                   actor_id=w.id("cal"), payload={"actor_id": w.id("cal"), "def_id": "break_grip", "verb": "escape",
                                                                  "target_id": w.id("dead")}))
        ev = bodies.release_event(tx, w.id("dead"), w.id("cal"), t + 2000, st.event_id, 1)
        assert cascade.select(tx, "rescued_by(trigger.event_id)", ev) == []
        assert cascade.evaluate_precondition(tx, "trigger.rescuer == 'x'", ev) is False


def test_freed_from_someone_s_grip(yard):
    """CAS-081: Mara had hold of Cal, who was not fighting her; Owen put her down."""
    w = yard()
    t = now(w)
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("mara"), w.id("yard"), None, 9.0, 10.0, t, None, 0))
    grab(w, "mara", "cal", t)
    w.store.conn.execute("DELETE FROM grips WHERE holder_id = ?", (w.id("dead"),))
    blow(w, "pc", "mara", t + 1000, severity=WoundSeverity.CATASTROPHIC)
    assert rel(w, "cal", "pc") == (2, 1)
    assert debts(w, "cal") == [("A tall, heavyset man got you free of a woman. You owe them.", 3)]
