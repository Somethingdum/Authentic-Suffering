"""What wears the will down (D-123). 05 §5's Resolve drains, as cascade rules: CAS-008 a bonded death
seen (and a dependent's, the worst), CAS-030 word of a dependent's death, CAS-031 a first kill, CAS-032
killing a child, CAS-033 severe pain, CAS-034 going hungry, CAS-035 going without sleep (core
cascade/people.yaml and stress.yaml); action/cascade.py drain_resolve's scale_by, the path
body(<path>).<column>, trigger.killer_first and the selector seen_clearly_by.

Until D-123 ten of the sixteen drains in RulesConfig.resolve.drains had nothing that could ever cause
them, and CAS-008 waited on a belief nothing ever wrote: nobody's will was worn by grief, a first kill,
a child's death, pain, hunger or sleeplessness. A loss is grieved once.
"""

from __future__ import annotations

import copy

import pytest

from as_engine.action import cascade
from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import bodies
from as_engine.physical.bodies import WoundSpec
from as_engine.testing.scenario import load_scenario
from as_engine.world import rumours

pytestmark = pytest.mark.phase(9)

KITCHEN = {
    "schema": "as.scenario.v1", "name": "kitchen", "seed": 9, "start": {"day": 300, "time": "13:00"},
    "places": [{"id": "kitchen", "name": "Kitchen", "light": 4, "width_m": 6, "depth_m": 5,
                "anchors": [{"id": "table", "name": "table", "x": 3, "y": 2.5}]},
               {"id": "yard", "name": "Yard", "light": 4, "width_m": 20, "depth_m": 20, "kind": "outdoor", "indoor": False,
                "material": "open_air", "anchors": [{"id": "gate", "name": "gate", "x": 10, "y": 1}]}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "kitchen", "x": 1, "y": 1},
        {"id": "rosa", "stub": {"name": "Rosa Quintero", "age": 34, "sex": "female"}, "place": "kitchen", "x": 2, "y": 2},
        {"id": "teo", "stub": {"name": "Teo Quintero", "age": 8, "sex": "male"}, "place": "kitchen", "x": 3, "y": 2},
        {"id": "dale", "dossier": "core:actor/dale_pruitt", "place": "kitchen", "x": 4, "y": 3},
        {"id": "nita", "dossier": "core:actor/nita_reyes", "place": "yard", "x": 10, "y": 10},
    ],
    "households": [{"id": "quintero", "members": [{"actor": "rosa", "role": "head", "guardian_of": ["teo"]},
                                                  {"actor": "teo", "role": "child"}]}],
    "relationships": [{"from": "dale", "to": "rosa", "kind": "friend", "trust": 2, "affection": 2}],
}


@pytest.fixture
def kitchen(fixture_packs, core_pack_dir):
    worlds = []

    def make():
        w = load_scenario(copy.deepcopy(KITCHEN), packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        return w
    yield make
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def resolve(w, who):
    return w.store.query_one("SELECT resolve_cur FROM actors WHERE actor_id = ?", (w.id(who),))[0]


def full(w, *who):
    for x in who:
        w.store.conn.execute("UPDATE actors SET resolve_cur = 5, resolve_max = 6 WHERE actor_id = ?", (w.id(x),))


def rules(w, *ids):
    return [r for r in w.canon.all("cascade") if r.id in ids]


def kill(w, killer, victim, at):
    """``killer`` cuts ``victim``'s throat at ``at``; everyone in the kitchen sees it."""
    with w.store.transaction() as tx:
        start = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0,
                                      actor_id=w.id(killer), payload={"actor_id": w.id(killer), "def_id": "strike_melee",
                                                                      "verb": "attack", "target_id": w.id(victim)}))
        hurt = bodies.apply_harm(tx, w.id(victim), WoundSpec(Anatomy.NECK, WoundType.CUT, WoundSeverity.CATASTROPHIC),
                                 at + 500, start.event_id, 0, w.rng)
        death = [e for e in hurt if e.type == EventType.DEATH]
        if not death:
            harm = next(e for e in hurt if e.type == EventType.HARM)
            death = [bodies.kill(tx, w.id(victim), "blood_loss", at + 1000, 0, w.rng, cause_event_id=harm.event_id)]
        for who in ("pc", "rosa", "teo", "dale"):
            if who != victim:
                perception.compile_aftermath(tx, w.id(who), [start] + hurt + death, at + 1500, 0)
    return death[0]


def sweep(w, ev, at, *ids):
    with w.store.transaction() as tx:
        return cascade.sweep(tx, [ev], rules(w, *ids), at, 0)


def test_a_mother_sees_her_son_killed(kitchen):
    """CAS-008: Rosa is Teo's guardian — the worst there is (lost_dependent, 3); nobody else was bonded to
    him. CAS-031 and CAS-032: Dale's first kill, and a child — the killer pays too."""
    w = kitchen()
    full(w, "rosa", "dale")
    t = now(w)
    death = kill(w, "dale", "teo", t)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "seen_clearly_by(trigger.event_id)", death) == sorted(
            [w.id("pc"), w.id("rosa"), w.id("dale")]), "never the dead"
        assert cascade.evaluate_precondition(tx, "trigger.killer_first == true", death)
        assert cascade.evaluate_precondition(tx, "body(trigger.payload.body_id).age_years <= 14", death)
    out = sweep(w, death, t + 2000, "CAS-008", "CAS-031", "CAS-032")
    assert {e.rule_cited for e in out} == {"CAS-008", "CAS-031", "CAS-032"}
    assert resolve(w, "rosa") == 5 - 3, "her child (lost_dependent)"
    assert resolve(w, "dale") == 5 - 1 - 3, "a first kill, and a child"


def test_a_friend_sees_a_friend_die_and_grieves_once(kitchen):
    """CAS-008 witness_bonded_death (2) for Dale, who loves Rosa, and for Teo, her son (one household);
    Owen, a stranger to her, loses nothing to grief. The same death is grieved once."""
    w = kitchen()
    full(w, "dale", "teo", "pc")
    t = now(w)
    death = kill(w, "pc", "rosa", t)
    sweep(w, death, t + 2000, "CAS-008")
    assert (resolve(w, "dale"), resolve(w, "teo"), resolve(w, "pc")) == (5 - 2, 5 - 2, 5)
    sweep(w, death, t + 3000, "CAS-008")
    assert (resolve(w, "dale"), resolve(w, "teo")) == (5 - 2, 5 - 2), "grieved once"


def test_word_of_it_reaches_the_guardian(kitchen):
    """CAS-030: Rosa was in the yard; Nita tells her Teo is dead, and she believes it."""
    w = kitchen()
    full(w, "rosa")
    with w.store.transaction() as tx:
        from as_engine.physical import space
        tx.commit_event(space.move_event(tx, w.id("rosa"), w.id("yard"), None, 9.0, 9.0, now(w), None, 0))
    t = now(w)
    death = kill(w, "dale", "teo", t)
    sweep(w, death, t + 2000, "CAS-008")
    assert resolve(w, "rosa") == 5, "she did not see it"
    with w.store.transaction() as tx:
        rid = rumours.seed(tx, w.id("nita"), w.id("teo"), "dead", t + 60_000, 0, None)
        told = rumours.spread_one(tx, rid, w.id("nita"), w.id("rosa"), t + 120_000, 0, None)
    assert told.payload["believed"]
    out = sweep(w, told, t + 120_000, "CAS-030")
    assert [e.rule_cited for e in out] == ["CAS-030"] and resolve(w, "rosa") == 5 - 3
    with w.store.transaction() as tx:
        again = rumours.spread_one(tx, rid, w.id("nita"), w.id("rosa"), t + 180_000, 0, None)
    sweep(w, again, t + 180_000, "CAS-030")
    assert resolve(w, "rosa") == 5 - 3, "told twice, grieved once"


def test_a_second_kill_is_not_a_first(kitchen):
    w = kitchen()
    full(w, "dale")
    t = now(w)
    sweep(w, kill(w, "dale", "pc", t), t + 2000, "CAS-031")
    assert resolve(w, "dale") == 4
    second = kill(w, "dale", "rosa", t + 60_000)
    with w.store.transaction() as tx:
        assert not cascade.evaluate_precondition(tx, "trigger.killer_first == true", second)
    assert sweep(w, second, t + 62_000, "CAS-031") == [] and resolve(w, "dale") == 4


def test_pain_hunger_and_no_sleep(kitchen):
    """CAS-033 severe pain; CAS-034 each new stage of hunger; CAS-035 a day and more awake."""
    w = kitchen()
    full(w, "dale")
    t = now(w)
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=0, payload={"what": "test"}))
        minor = [e for e in bodies.apply_harm(tx, w.id("dale"), WoundSpec(Anatomy.ARM_L, WoundType.CUT, WoundSeverity.MINOR),
                                              t, c.event_id, 0, w.rng) if e.type == EventType.HARM][0]
        severe = [e for e in bodies.apply_harm(tx, w.id("dale"), WoundSpec(Anatomy.LEG_L, WoundType.STAB, WoundSeverity.SEVERE),
                                               t, c.event_id, 0, w.rng) if e.type == EventType.HARM][0]
        assert cascade.sweep(tx, [minor], rules(w, "CAS-033"), t, 0) == [], "a scratch is not severe pain"
        assert [e.rule_cited for e in cascade.sweep(tx, [severe], rules(w, "CAS-033"), t, 0)] == ["CAS-033"]
    assert resolve(w, "dale") == 4

    def stage(need, n):
        with w.store.transaction() as tx:
            ev = tx.commit_event(Event(type=EventType.NEED_STAGE, writer="physical.bodies", at=t, turn_index=0,
                                       target_ids=[w.id("dale")], payload={"body_id": w.id("dale"), "need": need, "stage": n}))
            return cascade.sweep(tx, [ev], rules(w, "CAS-034", "CAS-035"), t, 0)
    assert stage("hunger", 0) == [] and stage("fatigue", 2) == [], "fed; sixteen hours awake"
    assert [e.rule_cited for e in stage("hunger", 1)] == ["CAS-034"]
    assert [e.rule_cited for e in stage("fatigue", 3)] == ["CAS-035"]
    assert resolve(w, "dale") == 2
