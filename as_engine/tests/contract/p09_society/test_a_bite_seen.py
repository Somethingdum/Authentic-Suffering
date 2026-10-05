"""A bite seen (D-124). Core CAS-015 (cascade/people.yaml), action/cascade.py's settlements_seeing and
LAW_APPLIED's where_in_force; society/settlement.py apply_law; core law contamination_quarantine.

Until D-124 CAS-015 waited on a belief nothing ever wrote ('bitten'), so the quarantine law of a
settlement never came into force for anyone: a bite in the middle of the yard, in front of everyone,
was nobody's business. Now a bite on a person seen clearly by members of a settlement brings its
quarantine law into force for the bitten — where that settlement has the law, and nowhere else.
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

pytestmark = pytest.mark.phase(9)

YARD = {
    "schema": "as.scenario.v1", "name": "quarantine_yard", "seed": 12, "start": {"day": 500, "time": "12:00"},
    "places": [{"id": "yard", "name": "Settlement yard", "kind": "outdoor", "indoor": False, "material": "open_air",
                "width_m": 30, "depth_m": 20, "light": 4,
                "anchors": [{"id": "well", "name": "well", "x": 10, "y": 10}, {"id": "gate", "name": "gate", "x": 15, "y": 1}]},
               {"id": "shed", "name": "Shed", "light": 1, "width_m": 4, "depth_m": 4,
                "anchors": [{"id": "bench", "name": "bench", "x": 2, "y": 2}]}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "yard", "x": 5, "y": 5},
        {"id": "hal", "stub": {"name": "Hal Brandt", "age": 44, "sex": "male"}, "place": "yard", "x": 10, "y": 9},
        {"id": "mae", "stub": {"name": "Mae Brandt", "age": 41, "sex": "female"}, "place": "yard", "x": 11, "y": 10},
        {"id": "otis", "stub": {"name": "Otis Reyes", "age": 61, "sex": "male"}, "place": "shed", "x": 2, "y": 2},
    ],
    "groups": [{"id": "settlers", "name": "Pumpwell settlers", "members": [{"actor": "hal", "role": "member"},
                                                                           {"actor": "mae", "role": "member"},
                                                                           {"actor": "otis", "role": "member"}]}],
    "settlements": [{"id": "pumpwell", "name": "Pumpwell", "place": "yard", "group": "settlers",
                     "stores": {"water": 50, "food": 50, "medicine": 2, "fuel": 10}, "ration_level": 3, "morale": 5,
                     "cohesion": 5, "laws": ["core:law/contamination_quarantine"]}],
}


@pytest.fixture
def yard(fixture_packs, core_pack_dir):
    worlds = []

    def make(change=None):
        spec = copy.deepcopy(YARD)
        if change:
            change(spec)
        w = load_scenario(spec, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        return w
    yield make
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def bite(w, who, at):
    """Something bites ``who`` on the forearm; everyone perceives what they can."""
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=at, turn_index=0, payload={"what": "test"}))
        hurt = bodies.apply_harm(tx, w.id(who), WoundSpec(Anatomy.ARM_L, WoundType.BITE, WoundSeverity.SIGNIFICANT), at,
                                 c.event_id, 0, w.rng)
        for x in ("pc", "hal", "mae", "otis"):
            perception.compile_aftermath(tx, w.id(x), hurt, at + 500, 0)
    return next(e for e in hurt if e.type == EventType.HARM)


def law_applied(w):
    return [dict(r) for r in w.store.query("SELECT actor_id, json_extract(payload, '$.law_ref') AS law FROM events "
                                           "WHERE type = 'LAW_APPLIED'")]


def rule(w):
    return [r for r in w.canon.all("cascade") if r.id == "CAS-015"]


def test_a_bite_in_the_yard_is_the_settlement_s_business(yard):
    w = yard()
    t = now(w)
    ev = bite(w, "hal", t)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "settlements_seeing(trigger.event_id)", ev) == [w.id("pumpwell")], \
            "Mae saw it — Hal's own bite is not a sighting, and Owen belongs to no settlement"
        out = cascade.sweep(tx, [ev], rule(w), t + 1000, 0)
    assert [(e.type, e.rule_cited) for e in out] == [(EventType.LAW_APPLIED, "CAS-015"), (EventType.LOOP_OPENED, "CAS-015"),
                                                     (EventType.LOOP_OPENED, "CAS-015")], "and kept by people (D-188)"
    assert law_applied(w) == [{"actor_id": w.id("hal"), "law": "core:law/contamination_quarantine"}]


def test_nobody_from_the_settlement_saw_it(yard):
    """Only Otis's in the dark shed when the bite happens out there — and Owen, who belongs nowhere."""
    def mae_in_the_shed(spec):
        spec["bodies"][2].update({"place": "shed", "x": 3, "y": 3})
    w = yard(mae_in_the_shed)
    t = now(w)
    ev = bite(w, "hal", t)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "settlements_seeing(trigger.event_id)", ev) == []
        assert cascade.sweep(tx, [ev], rule(w), t + 1000, 0) == []
    assert law_applied(w) == []


def test_where_there_is_no_such_law_nothing_happens_and_nothing_complains(yard):
    def no_law(spec):
        spec["settlements"][0]["laws"] = []
    w = yard(no_law)
    t = now(w)
    ev = bite(w, "hal", t)
    with w.store.transaction() as tx:
        assert cascade.sweep(tx, [ev], rule(w), t + 1000, 0) == []
    assert law_applied(w) == []
    assert not w.store.query("SELECT 1 FROM audit_log WHERE findings LIKE '%law_not_active%'"), \
        "a settlement without the law is not a fault"
