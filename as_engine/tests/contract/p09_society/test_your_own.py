"""Your own (D-138). action/cascade.py selector loved_ones_threatened; core CAS-055..057.

A threat at weapon point frightened the one it was made to (CAS-038) and nobody else: Mara could watch Owen
hold a gun on June and tell her what he would do to her, and feel nothing about it. Now whoever loves the one
threatened — the player's character among those who can be — trusts the one who did it less and resents them.
And taking clothes from the dead is how people live now, unless the dead was yours: whoever loved them holds it
against the one who did it, and stripping someone alive who cannot stop it costs anyone's trust.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from as_engine.action import cascade
from as_engine.action.effects import SEEN
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import bodies, objects, space
from as_engine.physical.objects import Holder
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(9)

FENCE = yaml.safe_load((Path(__file__).resolve().parents[2] / "fixtures" / "scenarios" / "metal_fence.yaml").read_text())
EYES = ("pc", "mara", "alice", "june")


@pytest.fixture
def floor(fixture_packs, core_pack_dir):
    """The metal fence world, lights on, June at the counter; June has come to love Owen."""
    worlds = []

    def _load():
        spec = copy.deepcopy(FENCE)
        for b in spec["bodies"]:
            if b["id"] == "june":
                b["place"], b["anchor"] = "sales_floor", "counter"
                b.pop("task", None)
        for r in spec["relationships"]:
            if r["from"] == "june" and r["to"] == "pc":
                r["affection"] = 2
        w = load_scenario(spec, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        with w.store.transaction() as tx:
            space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", now(w), None, 0)
        return w
    yield _load
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def rel(w, a, b, axis):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def sweep(w, evs, at, ids):
    with w.store.transaction() as tx:
        return cascade.sweep(tx, list(evs), [r for r in w.canon.all("cascade") if r.id in ids], at, 0)


def threaten(w, who, whom, words, at):
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id(who), at=at, turn_index=0,
                                   payload={"words": words, "volume": "normal", "to": [w.id(whom)], "source_db": 60, "armed": True}))
        for x in EYES:
            perception.compile_aftermath(tx, w.id(x), [ev], at + 500, 0)
    return ev


def strip(w, who, whom, at):
    with w.store.transaction() as tx:
        worn = objects.create(tx, "core:item/cardigan", 1, Holder("body", w.id(whom), "worn"), "scenario", {}, at - 500, None,
                              0).payload["item_id"]
        ev = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0, actor_id=w.id(who),
                                   payload={"actor_id": w.id(who), "def_id": "strip_clothing", "verb": "manipulate", "visible": True,
                                            "seen": SEEN["strip_clothing"], "target_id": w.id(whom), "item_id": worn}))
        for x in EYES:
            if x != whom:
                perception.compile_aftermath(tx, w.id(x), [ev], at + 500, 0)
    return ev


def test_june_at_gunpoint(floor):
    """Owen holds his Glock on June and tells her what he will do: June is afraid of him (CAS-038); Mara, who loves
    her, trusts him less and resents him (CAS-055); Alice, who does not, is unmoved."""
    w = floor()
    t = now(w)
    before = {x: (rel(w, x, "pc", "trust"), rel(w, x, "pc", "resentment")) for x in ("mara", "alice")}
    fear = rel(w, "june", "pc", "fear")
    ev = threaten(w, "pc", "june", "Open the register or I'll shoot you.", t + 500)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "loved_ones_threatened(trigger.event_id)", ev) == [w.id("mara")]
    sweep(w, [ev], t + 2000, ("CAS-038", "CAS-055"))
    assert rel(w, "june", "pc", "fear") == min(3, fear + 1)
    trust, res = before["mara"]
    assert (rel(w, "mara", "pc", "trust"), rel(w, "mara", "pc", "resentment")) == (max(-3, trust - 1), min(3, res + 1))
    assert (rel(w, "alice", "pc", "trust"), rel(w, "alice", "pc", "resentment")) == before["alice"]


def test_owen_at_knifepoint(floor):
    """Alice holds a knife on Owen and threatens him: nothing is written into Owen (C06), but June, who has come to
    love him, holds it against Alice."""
    w = floor()
    t = now(w)
    with w.store.transaction() as tx:
        objects.create(tx, "core:item/kitchen_knife", 1, Holder("body", w.id("alice"), "hand_r"), "scenario", {}, t, None, 0)
    trust, res = rel(w, "june", "alice", "trust"), rel(w, "june", "alice", "resentment")
    owen = (rel(w, "pc", "alice", "fear"), rel(w, "pc", "alice", "trust"))
    ev = threaten(w, "alice", "pc", "Back off or I'll cut you open.", t + 500)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "threatened_by(trigger.event_id)", ev) == []
        assert cascade.select(tx, "loved_ones_threatened(trigger.event_id)", ev) == [w.id("june")]
    sweep(w, [ev], t + 2000, ("CAS-038", "CAS-055"))
    assert (rel(w, "june", "alice", "trust"), rel(w, "june", "alice", "resentment")) == (max(-3, trust - 1), min(3, res + 1))
    assert (rel(w, "pc", "alice", "fear"), rel(w, "pc", "alice", "trust")) == owen


def test_stripping_her_dead(floor):
    """June lies dead; Alice starts taking her clothes. Mara, who loved her, trusts Alice less and holds it; Owen is
    unchanged. The dead are stripped every day — CAS-057 asks for the living."""
    w = floor()
    t = now(w)
    with w.store.transaction() as tx:
        bodies.kill(tx, w.id("june"), "blood_loss", t + 100, 0, w.rng)
    trust = rel(w, "mara", "alice", "trust")
    owen = rel(w, "pc", "alice", "trust")
    out = sweep(w, [strip(w, "alice", "june", t + 1000)], t + 2000, ("CAS-056", "CAS-057"))
    assert {e.rule_cited for e in out} == {"CAS-056"}
    assert rel(w, "mara", "alice", "trust") == max(-3, trust - 1)
    assert w.store.query("SELECT strength FROM open_loops WHERE holder_id = ? AND kind = 'grudge' AND text LIKE ?",
                         (w.id("mara"), "%stripped the clothes off someone you loved%"))[0][0] == 2
    assert rel(w, "pc", "alice", "trust") == owen


def test_stripping_her_out_cold(floor):
    """June is out cold; Alice starts taking her clothes. Mara loves her: trust down 2 in all. Owen sees it too,
    and nothing is written into him."""
    w = floor()
    t = now(w)
    w.store.conn.execute("UPDATE bodies SET awareness = 'unconscious' WHERE body_id = ?", (w.id("june"),))
    trust, owen = rel(w, "mara", "alice", "trust"), rel(w, "pc", "alice", "trust")
    out = sweep(w, [strip(w, "alice", "june", t + 1000)], t + 2000, ("CAS-056", "CAS-057"))
    assert {e.rule_cited for e in out} == {"CAS-056", "CAS-057"}
    assert rel(w, "mara", "alice", "trust") == max(-3, trust - 2)
    assert rel(w, "pc", "alice", "trust") == owen
