"""It missed (D-161, D-162). action/cascade.py paths trigger.missed_attacker / missed_provoked / missed_lethal and
selectors attacked_by_someone, attack_onlookers_of; core CAS-066..068; world/rumours.py INFO-07 seen and the claim
'tried_to_kill_someone'.

Being hurt was answered (D-126). A shot at Mara that missed, in a room full of her crew, was answered by nothing —
no fear, no grudge, nobody trusting Owen less — because every rule waited for a wound. And whoever did see a thing
done and told it held it as talk they had overheard ("Word is: ..."), not as something they saw.
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec

pytestmark = pytest.mark.phase(9)

EYES = ("pc", "mara", "alice", "june")
RULES = ("CAS-066", "CAS-067", "CAS-068", "CAS-036")


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def rel(w, a, b, axis):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def lit(w):
    t = now(w)
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("sales_floor"), None, 7.0, 4.0, t, None, 0))
    return t + 1000


def attack(w, who, whom, def_id, at, *, result="miss", wound=None):
    with w.store.transaction() as tx:
        st = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0, actor_id=w.id(who),
                                   payload={"actor_id": w.id(who), "def_id": def_id, "verb": "attack", "target_id": w.id(whom),
                                            "visible": True, "seen": "goes for {target}"}))
        evs = [st]
        if wound:
            evs += bodies.apply_harm(tx, w.id(whom), wound, at + 200, st.event_id, 0, w.rng)
        done = tx.commit_event(Event(type=EventType.ACTION_COMPLETE, writer="action.resolve", at=at + 300, turn_index=0,
                                     actor_id=w.id(who), cause_event_id=st.event_id,
                                     payload={"actor_id": w.id(who), "def_id": def_id, "band": "fail", "result": result,
                                              "visible": False}))
        evs.append(done)
        for x in EYES:
            perception.compile_aftermath(tx, w.id(x), evs, at + 500, 0)
    return evs


def sweep(w, evs, at):
    with w.store.transaction() as tx:
        return cascade.sweep(tx, list(evs), [r for r in w.canon.all("cascade") if r.id in RULES], at, 0)


def test_owen_shoots_at_mara_and_misses(scenario):
    w = scenario("metal_fence")
    t = lit(w)
    before = {x: (rel(w, x, "pc", "trust"), rel(w, x, "pc", "fear")) for x in ("mara", "alice", "june")}
    evs = attack(w, "pc", "mara", "shoot_center_mass", t)
    sweep(w, evs, t + 1000)
    assert (rel(w, "mara", "pc", "trust"), rel(w, "mara", "pc", "fear")) == (max(-3, before["mara"][0] - 2), min(3, before["mara"][1] + 2))
    (text, strength), = w.store.query("SELECT text, strength FROM open_loops WHERE holder_id = ? AND kind = 'grudge'", (w.id("mara"),))
    assert (text, strength) == ("Owen tried to kill you, and you were not fighting them.", 3)
    for x in ("alice", "june"):
        assert (rel(w, x, "pc", "trust"), rel(w, x, "pc", "fear")) == (max(-3, before[x][0] - 1), min(3, before[x][1] + 1)), x
    rows = w.store.query("SELECT p.predicate, h.provenance FROM rumours r JOIN propositions p ON p.prop_id = r.prop_id "
                         "JOIN claim_holdings h ON h.claim_id = r.prop_id WHERE r.origin_holder = ?", (w.id("june"),))
    assert [(r[0], r[1]) for r in rows] == [("tried_to_kill_someone", "witnessed")], "she saw it — she did not overhear it (D-162)"


def test_a_shove_that_did_not_hurt(scenario):
    w = scenario("metal_fence")
    t = lit(w)
    trust, res = rel(w, "june", "pc", "trust"), rel(w, "june", "pc", "resentment")
    sweep(w, attack(w, "pc", "june", "shove", t, result="knocked_down"), t + 1000)
    assert (rel(w, "june", "pc", "trust"), rel(w, "june", "pc", "resentment")) == (max(-3, trust - 1), min(3, res + 1))
    assert not w.store.query("SELECT 1 FROM open_loops WHERE holder_id = ? AND kind = 'grudge'", (w.id("june"),))
    assert not w.store.query("SELECT 1 FROM rumours")


def test_not_when_it_landed_or_she_was_fighting(scenario):
    w = scenario("metal_fence")
    t = lit(w)
    hit = attack(w, "pc", "mara", "shoot_center_mass", t, result="hit",
                 wound=WoundSpec(Anatomy.ARM_L, WoundType.GUNSHOT, WoundSeverity.MINOR))
    done = hit[-1]
    with w.store.transaction() as tx:
        assert cascade.select(tx, "attacked_by_someone(trigger.event_id)", done) == [], "a wound is CAS-036's"
    attack(w, "mara", "pc", "punch", t + 5000)
    back = attack(w, "pc", "mara", "shoot_center_mass", t + 9000)
    with w.store.transaction() as tx:
        assert cascade.evaluate_precondition(tx, "trigger.missed_provoked == false", back[-1]) is False, "she had gone for him"


def test_never_into_the_player(scenario):
    w = scenario("metal_fence")
    t = lit(w)
    done = attack(w, "mara", "pc", "shoot_center_mass", t)[-1]
    with w.store.transaction() as tx:
        assert cascade.select(tx, "attacked_by_someone(trigger.event_id)", done) == []
        assert w.id("pc") not in cascade.select(tx, "attack_onlookers_of(trigger.event_id)", done)
