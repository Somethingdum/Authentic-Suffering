"""A killing seen (D-119). Rules CAS-025..028 (core cascade/people.yaml); action/cascade.py paths
trigger.killer and trigger.killer_provoked, selectors onlookers_of and groups_that_saw, STANDING_CHANGE;
world/rumours.py claim 'killed_someone'.

The owner: "What happens if I say, kill one of my squad mates for the hell of it, in front of everybody?
... I'm going to immediately commit war crimes, I hope you know that. And there better be some Authentic
Suffering in there when I do." Owen kills Alice on the sales floor with Mara watching, all three of
Delgado's crew. Mara stops trusting him and is afraid of him, and carries the story; telling it costs him
with whoever believes her; the crew thinks less of him; and he carries it. Had Alice gone for him — or
for anyone — first, none of that follows from the killing itself. And the night is dark: with the work
lights off, Mara sees a figure go down and cannot say who did it; only he knows.
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.mind import mind, perception
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec
from as_engine.world import rumours

pytestmark = pytest.mark.phase(9)

KILLING = ("CAS-025", "CAS-026", "CAS-027", "CAS-028")


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def rules(w, ids=KILLING):
    return [r for r in w.canon.all("cascade") if r.id in ids]


def rel(w, a, b, axis):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def stress(w, who):
    return w.store.query_one("SELECT stress FROM actors WHERE actor_id = ?", (w.id(who),))[0]


def lit(w):
    """The work lights on the sales floor are on."""
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", now(w), None, 0)


def kill(w, killer, victim, at, *, went_for=None):
    """``killer`` strikes ``victim`` dead at ``at``; everyone there perceives it. ``went_for``: the victim
    swung at that person 4 s before. Returns the DEATH event."""
    with w.store.transaction() as tx:
        evs = []
        if went_for:
            evs.append(tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at - 4000, turn_index=0,
                                             actor_id=w.id(victim), payload={"actor_id": w.id(victim), "def_id": "punch",
                                                                             "verb": "attack", "target_id": w.id(went_for)})))
        start = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0,
                                      actor_id=w.id(killer),
                                      payload={"actor_id": w.id(killer), "def_id": "strike_melee", "verb": "attack",
                                               "target_id": w.id(victim)}))
        hurt = bodies.apply_harm(tx, w.id(victim), WoundSpec(Anatomy.NECK, WoundType.CUT, WoundSeverity.CATASTROPHIC),
                                 at + 500, start.event_id, 0, w.rng)
        evs += [start] + hurt
        death = [e for e in hurt if e.type == EventType.DEATH]
        if not death:
            harm = next(e for e in hurt if e.type == EventType.HARM)
            death = [bodies.kill(tx, w.id(victim), "blood_loss", at + 1000, 0, w.rng, cause_event_id=harm.event_id)]
            evs += death
        for who in ("pc", "mara", "alice", "june", "eli", "nita"):
            if w.store.query_one("SELECT alive FROM bodies WHERE body_id = ?", (w.id(who),))[0] or who == victim:
                perception.compile_aftermath(tx, w.id(who), evs, at + 1500, 0)
    return death[0]


def sweep(w, ev, at, ids=KILLING):
    with w.store.transaction() as tx:
        return cascade.sweep(tx, [ev], rules(w, ids), at, 0)


def test_a_squad_mate_killed_in_front_of_everybody(scenario):
    w = scenario("metal_fence")
    lit(w)
    t = now(w)
    crew = w.store.query_one("SELECT group_id FROM group_members WHERE actor_id = ?", (w.id("alice"),))[0]
    with w.store.transaction() as tx:
        standing_before = mind.standing_toward(tx, crew, w.id("pc"))
    trust_before, fear_before, owen_before = rel(w, "mara", "pc", "trust"), rel(w, "mara", "pc", "fear"), stress(w, "pc")
    death = kill(w, "pc", "alice", t)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "actor(trigger.killer)", death) == [w.id("pc")]
        assert cascade.select(tx, "onlookers_of(trigger.event_id)", death) == [w.id("mara")], \
            "the people who saw it — never the killer, never the dead, never June in the back"
        assert cascade.select(tx, "groups_that_saw(trigger.event_id)", death) == [crew]
    out = sweep(w, death, t + 2000)
    assert {e.rule_cited for e in out} >= {"CAS-025", "CAS-026", "CAS-027"}
    assert rel(w, "mara", "pc", "trust") == max(-3, trust_before - 3) and rel(w, "mara", "pc", "fear") == min(3, fear_before + 2)
    (loop,) = [r for r in w.store.query("SELECT kind, text, subject_ids FROM open_loops WHERE holder_id = ? AND kind = 'fear'",
                                        (w.id("mara"),)) if w.id("pc") in r[2]]
    assert "killed someone in front of you" in loop[1]
    held = [r[0] for r in w.store.query("SELECT r.rumour_id FROM rumours r WHERE r.origin_holder = ?", (w.id("mara"),))]
    assert held, "Mara carries the story"
    assert stress(w, "pc") == min(10, owen_before + 2), "he carries it"
    with w.store.transaction() as tx:
        assert mind.standing_toward(tx, crew, w.id("pc")) == max(-5, standing_before - 2), "the crew thinks less of him"
    assert rel(w, "pc", "pc", "trust") == 0 and not w.store.query(
        "SELECT 1 FROM rumours WHERE origin_holder IN (?, ?)", (w.id("pc"), w.id("alice"))), "never the killer or the dead"


def test_telling_it_costs_him_with_whoever_believes_it(scenario):
    w = scenario("metal_fence")
    lit(w)
    t = now(w)
    sweep(w, kill(w, "pc", "alice", t), t + 2000)
    (rid,) = [r[0] for r in w.store.query("SELECT rumour_id FROM rumours WHERE origin_holder = ?", (w.id("mara"),))]
    eli, nita = rel(w, "eli", "pc", "trust"), rel(w, "nita", "pc", "trust")
    with w.store.transaction() as tx:
        told = rumours.spread_one(tx, rid, w.id("mara"), w.id("eli"), t + 60_000, 0, None)
        mind.relate(tx, w.id("nita"), w.id("mara"), "trust", -6, "test", t + 60_000, 0)
        told_nita = rumours.spread_one(tx, rid, w.id("mara"), w.id("nita"), t + 61_000, 0, None)
    assert told.payload["believed"] and not told_nita.payload["believed"]
    assert [e.rule_cited for e in sweep(w, told, t + 60_000)] == ["CAS-028"] and rel(w, "eli", "pc", "trust") == max(-3, eli - 2)
    assert sweep(w, told_nita, t + 61_000) == [] and rel(w, "nita", "pc", "trust") == nita, \
        "a teller she does not believe changes nothing"


def test_in_the_dark_nobody_can_say_who(scenario):
    """No lights: Mara sees a figure go down. Nobody saw who did it — only he knows."""
    w = scenario("metal_fence")
    t = now(w)
    crew = w.store.query_one("SELECT group_id FROM group_members WHERE actor_id = ?", (w.id("alice"),))[0]
    with w.store.transaction() as tx:
        standing = mind.standing_toward(tx, crew, w.id("pc"))
    trust, owen = rel(w, "mara", "pc", "trust"), stress(w, "pc")
    death = kill(w, "pc", "alice", t)
    seen = w.store.query("SELECT fidelity, text FROM percept_log WHERE holder_id = ? AND event_id = ?",
                         (w.id("mara"), death.event_id))
    assert [r[0] for r in seen] == ["visual_only"], "she saw something go down"
    with w.store.transaction() as tx:
        assert cascade.select(tx, "onlookers_of(trigger.event_id)", death) == []
        assert cascade.select(tx, "groups_that_saw(trigger.event_id)", death) == []
    out = sweep(w, death, t + 2000)
    assert [e.rule_cited for e in out] == ["CAS-026"] and stress(w, "pc") == min(10, owen + 2), "he carries it"
    assert rel(w, "mara", "pc", "trust") == trust and not w.store.query("SELECT 1 FROM rumours")
    with w.store.transaction() as tx:
        assert mind.standing_toward(tx, crew, w.id("pc")) == standing


def test_she_went_for_him_first(scenario):
    """Self-defence: the killing itself costs nothing more (the death still strains everyone, CAS-019)."""
    w = scenario("metal_fence")
    lit(w)
    t = now(w)
    death = kill(w, "pc", "alice", t, went_for="pc")
    with w.store.transaction() as tx:
        assert cascade.evaluate_precondition(tx, "trigger.killer_provoked == true", death)
    trust, owen = rel(w, "mara", "pc", "trust"), stress(w, "pc")
    assert sweep(w, death, t + 2000) == []
    assert (rel(w, "mara", "pc", "trust"), stress(w, "pc")) == (trust, owen)
    assert not w.store.query("SELECT 1 FROM rumours")


def test_she_went_for_mara_and_he_stopped_her(scenario):
    """Defending someone else is not murder either."""
    w = scenario("metal_fence")
    lit(w)
    t = now(w)
    death = kill(w, "pc", "alice", t, went_for="mara")
    with w.store.transaction() as tx:
        assert cascade.evaluate_precondition(tx, "trigger.killer_provoked == true", death)
    trust = rel(w, "mara", "pc", "trust")
    assert sweep(w, death, t + 2000) == [] and rel(w, "mara", "pc", "trust") == trust


def test_what_owen_feels_about_it_is_the_player_s(scenario):
    """Mara kills Alice in front of Owen: nothing is written into Owen's mind for him (C06)."""
    w = scenario("metal_fence")
    lit(w)
    t = now(w)
    mara = stress(w, "mara")
    death = kill(w, "mara", "alice", t)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "actor(trigger.killer)", death) == [w.id("mara")]
        assert cascade.select(tx, "onlookers_of(trigger.event_id)", death) == []
    out = sweep(w, death, t + 2000)
    assert [e.rule_cited for e in out] == ["CAS-026"] and stress(w, "mara") == min(10, mara + 2), "she carries it"
    assert rel(w, "pc", "mara", "trust") == 0 and not w.store.query("SELECT 1 FROM rumours") and not w.store.query(
        "SELECT 1 FROM open_loops WHERE holder_id = ? AND text LIKE '%killed someone%'", (w.id("pc"),))


def test_no_killer_no_killing(scenario):
    w = scenario("metal_fence")
    lit(w)
    t = now(w)
    with w.store.transaction() as tx:
        death = bodies.kill(tx, w.id("alice"), "blood_loss", t, 0, w.rng)
        assert cascade.select(tx, "actor(trigger.killer)", death) == []
        assert not cascade.evaluate_precondition(tx, "trigger.killer_provoked == false", death)
    assert sweep(w, death, t + 1000) == [], "a death nobody caused — the cold, the dead — is not a killing"
    w2 = scenario("metal_fence")
    t2 = now(w2)
    with w2.store.transaction() as tx:
        start = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=t2, turn_index=0,
                                      actor_id=w2.id("pc"), payload={"actor_id": w2.id("pc"), "def_id": "punch",
                                                                     "verb": "attack", "target_id": w2.id("alice")}))
        bodies.apply_harm(tx, w2.id("alice"), WoundSpec(Anatomy.ARM_L, WoundType.BLUNT, WoundSeverity.MINOR), t2 + 500,
                          start.event_id, 0, w2.rng)
        cold = bodies.kill(tx, w2.id("alice"), "cold", t2 + 3_600_000, 0, w2.rng)
        assert cascade.select(tx, "actor(trigger.killer)", cold) == [], "he hit her; the cold killed her"
    assert rumours.CLAIM_TEXT["killed_someone"] == "{about} killed someone who was not fighting back."
