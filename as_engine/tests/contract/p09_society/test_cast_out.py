"""Cast out (D-220). society/group.py cast_out (GRP-13, CAST_OUT_AT); action/cascade.py cast_out_by and
groups_that_saw_hurt; core CAS-109, CAS-110, CAS-027 (three now).

The owner: "If I treat them like shit, or do something just absolutely evil. I do expect reactions, and proper
ones." Pumpwell's laws speak of banishment, and nothing ever banished anyone: a group's standing toward one of
its own could sink as low as it liked and they slept in the same bunkhouse, drew the same ration and stood the
same watch. Now a group done with one of its own casts them out, and a killing in front of them is the end of it.
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.mind import mind, perception
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec
from as_engine.society import group

from society_kit import accident, now

pytestmark = pytest.mark.phase(9)


def status(w, who):
    return w.store.query_one("SELECT status FROM group_members WHERE group_id = ? AND actor_id = ?",
                             (w.id("settlers"), w.id(who)))[0]


def loops(w, who):
    return [r[0] for r in w.store.query("SELECT text FROM open_loops WHERE holder_id = ? AND status = 'open'", (w.id(who),))]


def test_finn_is_cast_out(settle):
    w = settle
    with w.store.transaction() as tx:
        cause = accident(tx, now(w), "the settlement has had enough")
        made = group.cast_out(tx, w.id("settlers"), w.id("finn"), now(w), 0, cause.event_id)
    d = next(e for e in made if e.type == EventType.DEFECTION)
    assert d.payload == {"actor_id": w.id("finn"), "group_id": w.id("settlers"), "cast_out": True}
    assert status(w, "finn") == "expelled"
    assert w.store.query_one("SELECT 1 FROM household_members WHERE actor_id = ?", (w.id("finn"),)) is None, "out of his house"
    assert w.store.query_one("SELECT 1 FROM work_assignments WHERE actor_id = ?", (w.id("finn"),)) is None, "and off the watch"
    released = [e for e in made if e.type == EventType.ROLE_RELEASED]
    assert [(e.payload["role"], e.payload["reason"]) for e in released] == [("watcher", "cast_out")]
    assert "Pumpwell has cast you out. You cannot stay." in loops(w, "finn")
    kept = [tuple(r) for r in w.store.query("SELECT text, subject_ids FROM open_loops WHERE holder_id = ? AND status = 'open' AND "
                                            "text LIKE '%has been cast out of Pumpwell. They are not to come back.'", (w.id("wade"),))]
    assert len(kept) == 1 and w.id("finn") in kept[0][1], "everyone keeps him out (his name as Wade knows him)"
    assert not loops(w, "pc"), "never written into the player's character (C06)"
    with w.store.transaction() as tx:
        assert group.cast_out(tx, w.id("settlers"), w.id("finn"), now(w), 0, cause.event_id) == [], "once"


def test_standing_at_the_bottom_casts_them_out(settle):
    w = settle
    g = w.id("settlers")
    with w.store.transaction() as tx:
        e1 = mind.adjust_group_standing(tx, g, w.id("jude"), -2, None, now(w), 0)
        rules = [r for r in tx.canon.all("cascade") if r.id == "CAS-109"]
        assert cascade.select(tx, "cast_out_by(trigger.event_id)", e1) == [], "not yet"
        e2 = mind.adjust_group_standing(tx, g, w.id("jude"), -2, None, now(w), 0)
        assert e2.payload["new"] <= group.CAST_OUT_AT < e2.payload["old"]
        cascade.sweep(tx, [e2], rules, now(w), 0)
    assert status(w, "jude") == "expelled"


def test_the_player_character_can_be_cast_out(settle):
    w = settle
    g = w.id("settlers")
    with w.store.transaction() as tx:
        e = mind.adjust_group_standing(tx, g, w.id("pc"), -3, None, now(w), 0)
        cascade.sweep(tx, [e], [r for r in tx.canon.all("cascade") if r.id == "CAS-109"], now(w), 0)
    assert status(w, "pc") == "expelled"
    assert not loops(w, "pc")
    assert any("has been cast out of Pumpwell" in x for x in loops(w, "tomas"))


def yard(w):
    """The yard lit; Jude, Finn, Wade and Kit up and out in it."""
    t = now(w)
    for who in ("jude", "finn", "wade", "kit"):
        w.store.conn.execute("UPDATE bodies SET awareness = 'awake', posture = 'standing' WHERE body_id = ?", (w.id(who),))
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("yard"), {"light_level": 4}, "test", t, None, 0)
        for who, x in (("jude", 5.0), ("finn", 6.0), ("wade", 9.0), ("kit", 10.0)):
            tx.commit_event(space.move_event(tx, w.id(who), w.id("yard"), None, x, 5.0, t, None, 0))
    return t + 1000


def strike(w, at, severity=WoundSeverity.MINOR):
    with w.store.transaction() as tx:
        st = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0, actor_id=w.id("jude"),
                                   payload={"actor_id": w.id("jude"), "def_id": "strike_melee", "verb": "attack",
                                            "target_id": w.id("finn")}))
        hurt = bodies.apply_harm(tx, w.id("finn"), WoundSpec(Anatomy.NECK if severity == WoundSeverity.CATASTROPHIC else Anatomy.ARM_L,
                                                              WoundType.CUT, severity), at + 500, st.event_id, 0, w.rng)
        evs = [st, *hurt]
        if severity == WoundSeverity.CATASTROPHIC and not any(e.type == EventType.DEATH for e in hurt):
            harm = next(e for e in hurt if e.type == EventType.HARM)
            evs.append(bodies.kill(tx, w.id("finn"), "blood_loss", at + 1000, 0, w.rng, cause_event_id=harm.event_id))
        for x in ("wade", "kit"):
            perception.compile_aftermath(tx, w.id(x), evs, at + 1500, 0)
    return evs


def sweep(w, evs, ids, at):
    with w.store.transaction() as tx:
        return cascade.sweep(tx, [e for e in evs if e.type in (EventType.HARM, EventType.DEATH)],
                             [r for r in tx.canon.all("cascade") if r.id in ids], at, 0)


def test_hurting_one_of_their_own_costs_a_point_a_day(settle):
    w = settle
    at = yard(w)
    g = w.id("settlers")
    before = mind.standing_toward(w.store, g, w.id("jude"))
    sweep(w, strike(w, at), ("CAS-110",), at + 2000)
    assert mind.standing_toward(w.store, g, w.id("jude")) == before - 1
    sweep(w, strike(w, at + 60_000), ("CAS-110",), at + 62_000)
    assert mind.standing_toward(w.store, g, w.id("jude")) == before - 1, "a beating is one wrong, not ten"


def test_a_killing_in_front_of_them_is_the_end_of_it(settle):
    """Jude cuts Finn's throat in the yard with Wade and Kit watching: one point for the blow, three for the killing —
    from where he stood with them, he is out."""
    w = settle
    at = yard(w)
    assert mind.standing_toward(w.store, w.id("settlers"), w.id("jude")) - 4 <= group.CAST_OUT_AT
    sweep(w, strike(w, at, WoundSeverity.CATASTROPHIC), ("CAS-027", "CAS-109", "CAS-110"), at + 2000)
    assert status(w, "jude") == "expelled"
    assert "Pumpwell has cast you out. You cannot stay." in loops(w, "jude")


def test_a_leader_cast_out_leads_no_more(settle):
    w = settle
    g = w.id("settlers")
    assert group.leader_of(w.store, g) == w.id("tomas")
    with w.store.transaction() as tx:
        cause = accident(tx, now(w), "the settlement has had enough of him")
        group.cast_out(tx, g, w.id("tomas"), now(w), 0, cause.event_id)
    assert group.leader_of(w.store, g) != w.id("tomas")
