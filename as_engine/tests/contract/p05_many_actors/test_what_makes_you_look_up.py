"""What makes you look up (D-137). Rule REACT-01 (action/reactions.py material_holders).

A reaction inside the turn used to need a blow, a gun pointed, a word to you, a loud noise or the dead coming
near. Someone drawing a knife beside you, pulling your clothes off, taking what is yours out of your hand,
beckoning you, or the one you were fighting putting their hands up — all waited for next turn, while the world
went on around you. Now each is news the moment you see it.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from as_engine.action.effects import SEEN
from as_engine.action.reactions import material_holders
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import objects, space
from as_engine.physical.objects import Holder
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(5)

FENCE = yaml.safe_load((Path(__file__).resolve().parents[2] / "fixtures" / "scenarios" / "metal_fence.yaml").read_text())
EYES = ("pc", "mara", "alice", "june")


@pytest.fixture
def floor(fixture_packs, core_pack_dir):
    """The metal fence world, lights on, June at the counter; Alice knows the ledger in her hand is hers."""
    worlds = []

    def _load():
        spec = copy.deepcopy(FENCE)
        for b in spec["bodies"]:
            if b["id"] == "june":
                b["place"], b["anchor"] = "sales_floor", "counter"
                b.pop("task", None)
        spec["beliefs"] = spec.get("beliefs", []) + [
            {"holder": "alice", "subject_type": "object", "subject": "alice_ledger", "predicate": "owner", "value": "alice",
             "text": "The ledger is mine.", "confidence": 3, "provenance": "witnessed"}]
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


def seen(w, ev, at):
    """Everyone looks; returns who it is news to."""
    with w.store.transaction() as tx:
        for x in EYES:
            perception.compile_aftermath(tx, w.id(x), [ev], at, 0)
        return {w.local(h) for h, _at in material_holders(tx, [ev], 0)}


def start(w, who, def_id, at, *, verb, target=None, item=None):
    with w.store.transaction() as tx:
        return tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=0, actor_id=w.id(who),
                                     payload={"actor_id": w.id(who), "def_id": def_id, "verb": verb, "visible": True,
                                              "seen": SEEN[def_id], "target_id": w.id(target) if target else None,
                                              "item_id": item}))


def gesture(w, who, gid, at, toward=None):
    with w.store.transaction() as tx:
        return tx.commit_event(Event(type=EventType.GESTURE, writer="action.propagate", at=at, turn_index=0, actor_id=w.id(who),
                                     payload={"actor_id": w.id(who), "gesture": gid, "target_id": w.id(toward) if toward else None}))


def test_a_knife_drawn(floor):
    """Mara takes a knife out of her pocket: everyone who sees it looks up. Glasses out of a pocket are no news."""
    w = floor()
    t = now(w)
    with w.store.transaction() as tx:
        pocket = Holder("body", w.id("mara"), "pocket")
        knife = objects.create(tx, "core:item/kitchen_knife", 1, pocket, "scenario", {}, t, None, 0).payload["item_id"]
        glasses = objects.create(tx, "core:item/glasses", 1, pocket, "scenario", {}, t, None, 0).payload["item_id"]
    assert "june" in seen(w, start(w, "mara", "equip_item", t + 500, verb="manipulate", item=knife), t + 700)
    assert seen(w, start(w, "mara", "equip_item", t + 5000, verb="manipulate", item=glasses), t + 5200) == set()


def test_something_done_to_you(floor):
    """Alice pulls at June's clothes: it is news to June, and to Mara, who loves her — not to Owen."""
    w = floor()
    t = now(w)
    assert seen(w, start(w, "alice", "strip_clothing", t + 500, verb="manipulate", target="june"), t + 700) == {"june", "mara"}


def test_your_things_taken(floor):
    """Owen takes the ledger out of Alice's hand: it is news to her."""
    w = floor()
    t = now(w)
    with w.store.transaction() as tx:
        ev = objects.transfer(tx, w.id("alice_ledger"), Holder("body", w.id("pc"), "hand_l"), None, t + 500, w.id("pc"), None, 0)
    assert "alice" in seen(w, ev, t + 700)


def test_a_gesture_at_you(floor):
    w = floor()
    t = now(w)
    assert seen(w, gesture(w, "mara", "beckon", t + 500, toward="june"), t + 700) == {"june"}
    assert seen(w, gesture(w, "mara", "shrug", t + 2000), t + 2200) == set()


def test_the_one_you_were_fighting_gives_up(floor):
    """June swung at Mara; Mara holds up empty hands: it is news to June, who was fighting her, and to no one else."""
    w = floor()
    t = now(w)
    start(w, "june", "punch", t + 500, verb="attack", target="mara")
    assert seen(w, gesture(w, "mara", "empty_hands", t + 3000), t + 3200) == {"june"}
    assert seen(w, gesture(w, "mara", "empty_hands", t + 90_000), t + 90_200) == set(), "a minute later it is no fight"
