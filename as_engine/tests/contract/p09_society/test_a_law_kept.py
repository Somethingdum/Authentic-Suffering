"""A law kept (D-188). society/settlement.py STL-09 (a law in force is kept by people); core CAS-015, CAS-074,
CAS-075 and the contamination quarantine law.

A bite in the yard brought Pumpwell's quarantine law into force for Hal (D-124) — and then nothing: the law was a
line in the event log that nobody read. Mae, who watched it happen and grew up under that law, went on with her day;
Hal did not fear what was coming. Now whoever saw it means to see the law kept, in its own words, and the one it
falls on knows what is coming. And someone seen spitting into a sleeper's mouth comes under the same law, with the one
it was put into.
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

EVERYONE = ("pc", "hal", "mae", "otis")


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


def rules(w, *ids):
    return [r for r in w.canon.all("cascade") if r.id in ids]


def loops(w, who, kind):
    return [(r[0], r[1]) for r in w.store.query("SELECT text, subject_ids FROM open_loops WHERE holder_id = ? AND kind = ? "
                                                  "AND status = 'open'", (w.id(who), kind))]


def bite(w, who, at):
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=at, turn_index=0, payload={"what": "test"}))
        hurt = bodies.apply_harm(tx, w.id(who), WoundSpec(Anatomy.ARM_L, WoundType.BITE, WoundSeverity.SIGNIFICANT), at,
                                 c.event_id, 0, w.rng)
        for x in EVERYONE:
            perception.compile_aftermath(tx, w.id(x), hurt, at + 500, 0)
        ev = next(e for e in hurt if e.type == EventType.HARM)
        cascade.sweep(tx, [ev], rules(w, "CAS-015"), at + 1000, 0)
    return ev


def test_mae_means_to_see_it_kept(yard):
    w = yard()
    bite(w, "hal", now(w))
    ((text, subj),) = loops(w, "mae", "goal")
    assert text.endswith("comes under the contamination quarantine. Whoever confirms the exposure reports it immediately; "
                         "the caretaker and one witness move the person to quarantine together, never one person alone."), text
    assert w.id("hal") in subj
    assert loops(w, "otis", "goal") == [], "Otis was in the shed and saw nothing"
    assert loops(w, "hal", "fear") == [("You come under the contamination quarantine of Pumpwell.", "[]")]
    assert not w.store.query("SELECT 1 FROM open_loops WHERE holder_id = ?", (w.id("pc"),)), "never the player's character"


def test_a_second_bite_is_the_same_law(yard):
    w = yard()
    t = now(w)
    bite(w, "hal", t)
    bite(w, "hal", t + 60_000)
    assert len(loops(w, "mae", "goal")) == 1 and len(loops(w, "hal", "fear")) == 1


def test_owen_bitten_among_his_own(yard):
    """The player's character is one of them now: Mae means to see him quarantined; what Owen feels is the player's."""
    def owen_joins(spec):
        spec["groups"][0]["members"].append({"actor": "pc", "role": "member"})
    w = yard(owen_joins)
    bite(w, "pc", now(w))
    ((text, subj),) = loops(w, "mae", "goal")
    assert w.id("pc") in subj and "contamination quarantine" in text
    assert not w.store.query("SELECT 1 FROM open_loops WHERE holder_id = ?", (w.id("pc"),))


def test_seen_spitting_into_a_sleeper_s_mouth(yard):
    """CAS-074: Hal spits into sleeping Otis's mouth by the well, in front of Mae. The law falls on both — and Otis,
    asleep through it, does not know."""
    def otis_asleep_in_the_yard(spec):
        spec["bodies"][3].update({"place": "yard", "x": 10, "y": 10})
    w = yard(otis_asleep_in_the_yard)
    t = now(w)
    with w.store.transaction() as tx:
        bodies.posture_event(tx, w.id("otis"), "lying", t, None, 0, awareness="asleep")
    at = t + 1000
    with w.store.transaction() as tx:
        st = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0, actor_id=w.id("hal"),
                                   payload={"actor_id": w.id("hal"), "def_id": "spit_in_mouth", "verb": "manipulate",
                                            "target_id": w.id("otis"), "visible": True, "seen": "bends over {target}'s sleeping face"}))
        for x in EVERYONE:
            perception.compile_aftermath(tx, w.id(x), [st], at + 200, 0)
        cascade.sweep(tx, [st], rules(w, "CAS-074"), at + 500, 0)
    applied = sorted(r[0] for r in w.store.query("SELECT actor_id FROM events WHERE type = 'LAW_APPLIED'"))
    assert applied == sorted([w.id("hal"), w.id("otis")])
    assert sorted(s for _t, s in loops(w, "mae", "goal")) == sorted([f'["{w.id("hal")}"]', f'["{w.id("otis")}"]'])
    assert loops(w, "otis", "fear") == [], "he slept through it"
    assert loops(w, "hal", "fear") == [("You come under the contamination quarantine of Pumpwell.", "[]")], "he knows what he did"


def test_seen_spitting_into_the_water(yard):
    w = yard()
    at = now(w) + 1000
    with w.store.transaction() as tx:
        st = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0, actor_id=w.id("hal"),
                                   payload={"actor_id": w.id("hal"), "def_id": "spit_into", "verb": "manipulate", "item_id": None,
                                            "visible": True, "seen": "leans low over the water"}))
        for x in EVERYONE:
            perception.compile_aftermath(tx, w.id(x), [st], at + 200, 0)
        cascade.sweep(tx, [st], rules(w, "CAS-075"), at + 500, 0)
    assert [r[0] for r in w.store.query("SELECT actor_id FROM events WHERE type = 'LAW_APPLIED'")] == [w.id("hal")]
    assert len(loops(w, "mae", "goal")) == 1
