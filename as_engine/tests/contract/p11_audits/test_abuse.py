"""The abuse battery (P11). Rules ABUSE-01..08 (audit/abuse.py).

The author is the threat. A world played honestly and a world freshly generated pass all eight
checks; then each exploit an author (or a bug, or a leaked cheat) could leave is planted on its
own — straight into the database — and exactly its check speaks, in plain words.
"""

from __future__ import annotations

import json

import pytest

from as_engine.audit import abuse
from as_engine.contracts.common import CallClass
from as_engine.contracts.events import Event, EventType
from as_engine.physical import objects
from slice_kit import pick, play, script_night_at_delgados

pytestmark = pytest.mark.phase(11)


def sql(s, statement, args=()):
    c = s.store.conn
    c.execute("PRAGMA foreign_keys=OFF")
    c.execute(statement, args)
    c.execute("PRAGMA foreign_keys=ON")


def one(s, statement, args=()):
    return s.store.query_one(statement, args)


def now(s):
    return one(s, "SELECT now_ms FROM world_clock")[0]


def run(s):
    with s.store.transaction() as tx:
        return abuse.battery(tx)


def generated_person(s):
    return one(s, "SELECT a.actor_id FROM actors a JOIN dossiers d ON d.dossier_id = a.dossier_id "
                  "WHERE d.source = 'generated' ORDER BY a.actor_id")[0]


def test_an_honest_night_passes(scenario, fake):
    w = scenario("metal_fence")
    script_night_at_delgados(w, fake)
    s = w.session()
    play(s, "do", "I watch the front window and keep quiet.")
    play(s, "do", "I keep watching the front window.")
    with w.store.transaction() as tx:
        assert abuse.battery(tx) == []


def test_an_honest_climb_passes(scenario, fake):
    """A real check, rolled and committed, is inside every cap (ABUSE-03 reads its payload)."""
    w = scenario("fence_climb")
    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "climb_obstacle", target="high_fence"), "none_reason": None,
                                            "manner": "", "remainder": None, "clarify": None})
    play(w.session(), "do", "I climb over the fence.")
    assert w.store.query("SELECT 1 FROM events WHERE type = 'CHECK_RESOLVED'")
    with w.store.transaction() as tx:
        assert abuse.battery(tx) == []


def test_a_generated_world_passes(gen):
    assert run(gen) == []


def f01(s):
    b = generated_person(s)
    sp = json.loads(one(s, "SELECT special FROM bodies WHERE body_id = ?", (b,))[0])
    sql(s, "UPDATE bodies SET special = ? WHERE body_id = ?", (json.dumps({**sp, "S": 9}), b))
    return [(b, f"{b}'s S is 9, outside the 3..7 of a generated person")]


def f02(s):
    b = generated_person(s)
    sql(s, "UPDATE bodies SET blood_loss_pct = 45 WHERE body_id = ?", (b,))
    return [(b, f"{b} is alive with 45% of their blood lost")]


def f03(s):
    pc = s.pc_id
    with s.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.CHECK_RESOLVED, writer="action.resolve", at=now(s), turn_index=0, actor_id=pc,
                                   payload={"actor_id": pc, "def_id": "climb_fence", "attribute": "A", "attr_value": 10,
                                            "skill": "athletics", "skill_rank": 3, "tag_bonus": 2, "situation": 3, "scale": 0,
                                            "impairment": 0, "resistance": 0, "target": 10, "draw": 5, "margin": 5,
                                            "band": "clean", "ladder": None}))
    return [(ev.event_id, f"climb_fence by {pc}: target 10 is not the clamped formula 13")]


def f04(s):
    for iid, ref in s.store.query("SELECT item_id, def_ref FROM items ORDER BY item_id"):
        d = s.store.canon.get(ref)
        if not d.stackable:
            sql(s, "UPDATE items SET qty = 3 WHERE item_id = ?", (iid,))
            return [(iid, f"3 {d.plural} in one row: a {d.name} does not stack")]
    raise AssertionError("the world has a thing that does not stack")


def f05(s):
    sid, name, pid = one(s, "SELECT settlement_id, name, place_id FROM settlements ORDER BY settlement_id")
    sql(s, "DELETE FROM portals WHERE place_a = ? OR place_b = ?", (pid, pid))
    return [(sid, f"{name} has no way in")]


def f06(s):
    pid = one(s, "SELECT place_id FROM positions WHERE body_id = ?", (s.pc_id,))[0]
    with s.store.transaction() as tx:
        ev = objects.create(tx, "core:item/jerky_pack", 1, objects.Holder("place", pid), "loot", {}, now(s), None, 0)
    return [(ev.event_id, "loot core:item/jerky_pack came from nothing, not from a discovery")]


def f07(s):
    b = generated_person(s)
    sql(s, "UPDATE bodies SET progressed_at = progressed_at - 600000 WHERE body_id = ?", (b,))
    return [(b, f"{b}'s clocks stand 10 minutes behind the world")]


def f08(s):
    iid = one(s, "SELECT item_id FROM items ORDER BY item_id")[0]
    sql(s, "UPDATE items SET origin = 'cheat' WHERE item_id = ?", (iid,))
    return [("items", "cheat-made items in a run that is not a sandbox: 1")]


FAULTS = {"ABUSE-01": f01, "ABUSE-02": f02, "ABUSE-03": f03, "ABUSE-04": f04, "ABUSE-05": f05, "ABUSE-06": f06,
          "ABUSE-07": f07, "ABUSE-08": f08}


def test_every_rule_has_its_exploit():
    assert [c.__name__ for c in abuse.CHECKS] == ["stat_bands", "mortality", "check_caps", "gear_limits", "ways_in",
                                                   "no_farming", "clock_sync", "cheat_leakage"]
    assert sorted(FAULTS) == [f"ABUSE-0{i}" for i in range(1, 9)]


@pytest.mark.parametrize("rule", sorted(FAULTS))
def test_each_exploit_is_named_by_its_rule_alone(gen, rule):
    expected = FAULTS[rule](gen)
    got = run(gen)
    assert [(f.rule, f.subject, f.text) for f in got] == [(rule, subj, text) for subj, text in expected]


def test_the_bands_bind_generated_people_only(gen):
    """A person someone wrote (a pack dossier) may be strong; a generated one is drawn from 3..7."""
    b = one(gen, "SELECT a.actor_id FROM actors a JOIN dossiers d ON d.dossier_id = a.dossier_id "
                 "WHERE d.source = 'pack' ORDER BY a.actor_id")[0]
    sp = json.loads(one(gen, "SELECT special FROM bodies WHERE body_id = ?", (b,))[0])
    sql(gen, "UPDATE bodies SET special = ? WHERE body_id = ?", (json.dumps({**sp, "S": 9}), b))
    assert run(gen) == []
    sql(gen, "UPDATE bodies SET special = ? WHERE body_id = ?", (json.dumps({**sp, "S": 11}), b))
    assert [f.text for f in run(gen)] == [f"{b}'s SPECIAL is not seven values from 1 to 10"]


def test_god_mode_belongs_to_a_sandbox(gen):
    b = generated_person(gen)
    sql(gen, "UPDATE bodies SET blood_loss_pct = 45 WHERE body_id = ?", (b,))
    sql(gen, "INSERT INTO meta (key, value) VALUES ('god_bodies', ?)", (json.dumps([b]),))
    assert [f.text for f in run(gen)] == [f"{b} is alive with 45% of their blood lost",
                                          "god mode is on in a run that is not a sandbox (1 bodies)"]
    sql(gen, "UPDATE meta SET value = '1' WHERE key = 'sandbox'")
    assert run(gen) == [], "in a sandbox, god mode is what the player asked for"


def test_a_cheat_made_person_does_not_count_in_a_sandbox(gen):
    b = generated_person(gen)
    sql(gen, "UPDATE meta SET value = '1' WHERE key = 'sandbox'")
    sql(gen, "UPDATE bodies SET origin = 'cheat' WHERE body_id = ?", (b,))
    assert [f.text for f in run(gen)] == [f"{b} was made by a cheat and still counts in the world's sums"]
    sql(gen, "UPDATE actors SET quarantine = 1 WHERE actor_id = ?", (b,))
    assert run(gen) == []
