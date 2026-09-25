"""The dead eat the living (P10, the owner's I1). Rules INF-15..19 (world/infected.py), the feeding
bite (action/effects.py strike_melee, tag 'bite'), physical.bodies.expose for animals, and CAS-024.

The owner: "They don't just bite you and waddle off, they don't attack for the kill either. They
eat you alive. Feast on you while you watch." And "they will eat anything that moves, a dog, a cat,
a man, a kid, a deer, a horse. Only humans get infected."

A yard at noon (a dict scenario): Cal and a dog a few metres apart, one of the dead at Cal's
shoulder, another far across the yard, a water bottle dropped by Cal's feet and another by the
gate, and June watching from the porch. The player is out on the road.
"""

from __future__ import annotations

import copy
import json

import pytest

from as_engine.action import cascade
from as_engine.contracts.events import Event, EventType
from as_engine.kernel import clock
from as_engine.mind import perception
from as_engine.physical import bodies, objects
from as_engine.physical.bodies import WoundSpec
from as_engine.testing.scenario import load_scenario
from as_engine.turn import timers
from as_engine.world import infected

pytestmark = pytest.mark.phase(10)

S = 1000
MIN = 60 * S
SH = infected.SHAMBLER

YARD = {
    "schema": "as.scenario.v1", "name": "the_yard", "seed": 81, "start": {"day": 300, "time": "12:00"},
    "places": [{"id": "yard", "name": "Farm yard", "kind": "outdoor", "indoor": False, "material": "open_air", "light": 3,
                "width_m": 40, "depth_m": 20,
                "anchors": [{"id": "feet", "name": "trough", "x": 10.5, "y": 10.5},
                            {"id": "gate", "name": "gate", "x": 38, "y": 2},
                            {"id": "porch", "name": "porch", "x": 4, "y": 16}]}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "yard", "x": 39, "y": 19},
        {"id": "cal", "stub": {"name": "Cal Hobbs", "age": 30, "sex": "male"}, "place": "yard", "x": 10, "y": 10},
        {"id": "june", "dossier": "core:actor/june_okafor", "place": "yard", "anchor": "porch"},
        {"id": "rex", "animal": "core:animal/dog", "place": "yard", "x": 20, "y": 10},
        {"id": "dead", "infected": SH, "controller": "policy", "place": "yard", "x": 10.5, "y": 10},
        {"id": "far_dead", "infected": SH, "controller": "policy", "place": "yard", "x": 35, "y": 5},
    ],
    "items": [{"item": "core:item/water_bottle", "place": "yard", "anchor": "feet", "label": "near_water"},
              {"item": "core:item/water_bottle", "place": "yard", "anchor": "gate", "label": "far_water"}],
    "relationships": [{"from": "june", "to": "cal", "kind": "friend", "trust": 2, "affection": 2}],
}


@pytest.fixture
def yard(fixture_packs, core_pack_dir):
    worlds = []

    def _load(change=None):
        spec = copy.deepcopy(YARD)
        if change is not None:
            change(spec)
        w = load_scenario(spec, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
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


def cause(tx, at):
    return tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=at, turn_index=0, payload={"what": "test"}))


def grab(w, who, prey):
    """The dead one has hold of its prey and hunts it (as a landed grab leaves it)."""
    t = now(w)
    with w.store.transaction() as tx:
        c = cause(tx, t)
        bodies.grip_event(tx, w.id(who), w.id(prey), t, c.event_id, 0)
        infected.attract(tx, w.id(who), w.id(prey), t, c.event_id, 0, reason="sight")


def run_for(w, seconds):
    with w.store.transaction() as tx:
        return timers.run_offscreen(tx, w.rng, now(w) + int(seconds * S), 0)


def events(w, type_):
    return [dict(r, payload=json.loads(r["payload"])) for r in w.store.query("SELECT * FROM events WHERE type = ? ORDER BY seq",
                                                                             (type_,))]


def bites_on(w, prey):
    return [e for e in events(w, "HARM") if e["payload"]["body_id"] == w.id(prey) and e["payload"]["type"] == "bite"]


def state(w, b):
    r = dict(w.store.query_one("SELECT * FROM infected_state WHERE body_id = ?", (w.id(b),)))
    r["states"] = json.loads(r["states"])
    return r


def set_states(w, b, states, energy):
    before = {k: state(w, b)[k] for k in ("states", "energy")}
    from as_engine.contracts.events import WriteOp, WriteRecord
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.INFECTED_STATE, writer="world.infected", at=now(w), turn_index=0,
                              actor_id=w.id(b), payload={"body_id": w.id(b), "changes": {"states": states, "energy": energy},
                                                          "before": before},
                              writes=[WriteRecord(op=WriteOp.UPDATE, table="infected_state", key={"body_id": w.id(b)},
                                                  values={"states": states, "energy": energy})]))


# --------------------------------------------------------------------------- INF-15
def test_once_it_has_you_it_does_not_let_go(yard):
    """Even overfed (bite_commitment 0.2), a body that holds Cal keeps biting, step after step:
    no disengaging from what it has."""
    w = yard()
    set_states(w, "dead", ["overfed"], 95)
    grab(w, "dead", "cal")
    run_for(w, 12)
    assert len(bites_on(w, "cal")) >= 3
    assert state(w, "dead")["target_id"] == w.id("cal")
    assert w.id("dead") in bodies.grips_on(w.store, w.id("cal"))


def test_they_eat_they_do_not_kill(yard):
    """Never the head or the neck; the first bite significant, every later one severe — flesh torn
    away while he is still alive to feel it."""
    w = yard()
    grab(w, "dead", "cal")
    run_for(w, 12)
    bites = bites_on(w, "cal")
    assert bites and all(b["payload"]["anatomy"] not in ("head", "neck") for b in bites)
    assert [b["payload"]["severity"] for b in bites[:3]] == ["significant", "severe", "severe"]
    assert {a for a, _w in infected.FEED_ANATOMY}.isdisjoint({"head", "neck"})
    starts = {e["event_id"]: e for e in events(w, "ACTION_START")}
    assert all(starts[b["cause_event_id"]]["actor_id"] == w.id("dead") for b in bites)


def test_he_screams_and_the_rest_of_them_come(yard):
    """Every bite on a conscious man makes him scream (90 dB) where he lies; the scream carries
    across the yard and draws the other one in."""
    w = yard()
    grab(w, "dead", "cal")
    run_for(w, 4)
    screams = [e for e in events(w, "NOISE") if e["payload"].get("kind") == "screaming"]
    assert screams and screams[0]["actor_id"] == w.id("cal") and screams[0]["writer"] == "action.propagate"
    assert screams[0]["payload"]["source_db"] == w.store.rules.infected.scream_db
    assert screams[0]["payload"]["text"] == "someone screaming"
    run_for(w, 30)
    assert state(w, "far_dead")["target_id"] in (w.id("cal"), w.id("yard")), "it heard him"


def test_busy_eating_it_is_not_drawn_away(yard):
    w = yard()
    grab(w, "dead", "cal")
    with w.store.transaction() as tx:
        assert infected.attract(tx, w.id("dead"), w.id("june"), now(w), None, 0, reason="sight") is None
        assert infected.attract(tx, w.id("dead"), w.id("yard"), now(w), None, 0, reason="noise") is None
    assert state(w, "dead")["target_id"] == w.id("cal"), "whoever is left to them buys the rest time"


def test_they_stay_on_what_they_killed_then_leave_it(yard):
    w = yard()
    grab(w, "dead", "cal")
    t = now(w)
    with w.store.transaction() as tx:
        d = bodies.die(tx, w.rng, w.id("cal"), t, cause(tx, t).event_id, 0, cause="test")
    assert d is not None
    before = len(bites_on(w, "cal"))
    run_for(w, 60)
    after_dead = [b for b in bites_on(w, "cal")[before:]]
    assert after_dead and all(b["payload"]["severity"] == "severe" for b in after_dead)
    assert not [e for e in events(w, "NOISE") if e["payload"].get("kind") == "screaming" and e["at"] > t], "the dead do not scream"
    window = w.store.rules.infected.feed_on_dead_min
    run_for(w, window * 60 + 30)
    assert state(w, "dead")["target_id"] is None, "sated, it drops what is left"
    assert not [b for b in bites_on(w, "cal") if b["at"] > t + window * MIN + 5 * S]


def test_the_devoured_do_not_get_up(yard):
    """A corpse bitten devoured_bites times has too little left of it to rise."""
    w = yard()
    t = now(w)
    with w.store.transaction() as tx:
        c = cause(tx, t)
        for k in range(w.store.rules.infected.devoured_bites):
            bodies.apply_harm(tx, w.id("cal"), WoundSpec("arm_l" if k % 2 else "leg_r", "bite", "severe", 2), t, c.event_id, 0, w.rng)
        if w.store.query_one("SELECT alive FROM bodies WHERE body_id = ?", (w.id("cal"),))[0]:
            bodies.die(tx, w.rng, w.id("cal"), t, c.event_id, 0, cause="test")
        row = {"queue_id": "q_test", "subject_id": w.id("cal"), "due_at": t + 3600 * S, "type": "REANIMATION",
               "payload": json.dumps({"body_id": w.id("cal"), "pathway": "cold_start"})}
        fired = cause(tx, t)
        assert infected.rise(tx, w.rng, row, fired, 0) == []


# --------------------------------------------------------------------------- INF-18
def test_a_dog_is_prey_like_anyone(yard):
    """The dead go for the dog the same way — and eat it. It never takes the strain, and it never
    gets up."""
    w = yard(lambda s: [b.update(x=19.5, y=10) for b in s["bodies"] if b["id"] == "dead"])
    grab(w, "dead", "rex")
    run_for(w, 12)
    bites = bites_on(w, "rex")
    assert bites, "anything that moves"
    assert not w.store.query("SELECT 1 FROM infections WHERE body_id = ?", (w.id("rex"),))
    exposures = [e for e in events(w, "INFECTION_EXPOSURE") if e["payload"]["body_id"] == w.id("rex")]
    assert exposures == [], "only people take the strain"
    assert not [e for e in events(w, "NOISE") if e["payload"].get("kind") == "screaming" and e["actor_id"] == w.id("rex")]
    t = now(w)
    with w.store.transaction() as tx:
        if w.store.query_one("SELECT alive FROM bodies WHERE body_id = ?", (w.id("rex"),))[0]:
            bodies.die(tx, w.rng, w.id("rex"), t, cause(tx, t).event_id, 0, cause="test")
    assert not w.store.query("SELECT 1 FROM event_queue WHERE type = 'REANIMATION' AND subject_id = ? AND status = 'pending'",
                             (w.id("rex"),))


def test_expose_takes_only_people(yard):
    w = yard()
    with w.store.transaction() as tx:
        c = cause(tx, now(w))
        assert bodies.expose(tx, w.rng, w.id("rex"), "wet", "bite", now(w), c.event_id, 0) is None


# --------------------------------------------------------------------------- INF-19
def test_what_comes_out_of_them_fouls_the_water(yard):
    """The bottle by Cal's feet (0.7 m) is fouled for good by the first bite; the one by the gate
    is not."""
    w = yard()
    grab(w, "dead", "cal")
    run_for(w, 4)
    near, far = w.id("near_water"), w.id("far_water")
    mark = objects.contaminated(w.store, near, now(w) + 1000 * 3600 * S)
    assert mark is not None and mark["lasting"] is True and mark["pathway"] == "wet" and mark["by"] == w.id("dead")
    assert objects.contaminated(w.store, far, now(w)) is None
    (ev,) = [e for e in events(w, "ITEM_CONTAMINATED") if e["payload"]["item_id"] == near]
    assert ev["payload"]["lasting"] is True
    assert ev["cause_event_id"] in {b["event_id"] for b in bites_on(w, "cal")}


def test_a_passing_mark_still_dries(yard):
    w = yard()
    t = now(w)
    with w.store.transaction() as tx:
        objects.contaminate(tx, w.id("far_water"), "wet", w.id("cal"), t, cause(tx, t).event_id, 0)
    hours = w.store.rules.infected.saliva_hours
    assert objects.contaminated(w.store, w.id("far_water"), t + int(hours * 3600 * S))["lasting"] is False
    assert objects.contaminated(w.store, w.id("far_water"), t + int(hours * 3600 * S) + 1) is None


# --------------------------------------------------------------------------- what it does to the ones who see it
def test_every_bite_seen_wears_you_down(yard):
    w = yard()
    grab(w, "dead", "cal")
    evs = run_for(w, 4)
    bites = bites_on(w, "cal")
    assert bites
    t = now(w)
    with w.store.transaction() as tx:
        perception.compile_aftermath(tx, w.id("june"), [e for e in evs if e.type == EventType.HARM], t, 0)
        before = tx.query_one("SELECT stress FROM actors WHERE actor_id = ?", (w.id("june"),))[0]
        harm = next(e for e in evs if e.type == EventType.HARM)
        cascade.sweep(tx, [harm], [r for r in w.canon.all("cascade") if r.id == "CAS-024"], t, 0)
        after = tx.query_one("SELECT stress FROM actors WHERE actor_id = ?", (w.id("june"),))[0]
    assert after == min(10, before + 1)
    texts = [r[0] for r in w.store.query("SELECT text FROM percept_log WHERE holder_id = ? AND event_id = ?",
                                         (w.id("june"), harm.event_id))]
    assert any(t.endswith("is being eaten alive.") for t in texts), texts
