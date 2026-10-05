"""A theft seen (D-225). Core CAS-112; action/cascade.py saw_them_steal.

June saw Dale take the jerky she knows is Ruth's. She carried the story (CAS-012), and anyone she told who believed
her trusted Dale less (CAS-018) — but June, who saw it with her own eyes, trusted him exactly as before. Now seeing it
costs what hearing it costs, once a day however much he takes; Ruth, whose it was, is answered as before (CAS-039).
"""

from __future__ import annotations

import copy

import pytest
from test_theft_seen import YARD

from as_engine.action import cascade
from as_engine.mind import perception
from as_engine.physical import objects
from as_engine.physical.objects import Holder
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(9)


def owner(holder, item, whose):
    return {"holder": holder, "subject_type": "object", "subject": item, "predicate": "owner", "value": whose,
            "text": f"The {item} is {whose.title()}'s.", "confidence": 3, "provenance": "witnessed"}


@pytest.fixture
def yard(fixture_packs, core_pack_dir):
    """The stall yard with Ruth at the stall, a water bottle beside the jerky, and everyone who knows whose things
    they are: June knows both are Ruth's, Ruth knows they are hers, and so does the player's character."""
    spec = copy.deepcopy(YARD)
    spec["bodies"][-1].update({"x": 10, "y": 11})
    spec["items"].append({"item": "core:item/water_bottle", "place": "yard", "anchor": "stall", "label": "bottle"})
    spec["beliefs"] += [owner("june", "bottle", "ruth"), owner("ruth", "jerky", "ruth"), owner("ruth", "bottle", "ruth"),
                        owner("pc", "jerky", "ruth"), owner("pc", "bottle", "ruth")]
    w = load_scenario(spec, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
    yield w
    w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def take(w, item, at):
    """Dale takes ``item`` into his hand at ``at``; everyone there sees it; the theft rules answer."""
    rules = [r for r in w.canon.all("cascade") if r.id in ("CAS-039", "CAS-112")]
    with w.store.transaction() as tx:
        ev = objects.transfer(tx, w.id(item), Holder("body", w.id("dale"), "hand_l" if item == "jerky" else "hand_r"), None, at,
                              w.id("dale"), None, 0)
        for x in ("june", "nita", "tess", "ruth", "pc"):
            perception.compile_aftermath(tx, w.id(x), [ev], at + 500, 0)
        return cascade.sweep(tx, [ev], rules, at + 500, 0)


def trust(w, who):
    r = w.store.query_one("SELECT trust FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(who), w.id("dale")))
    return 0 if r is None else r[0]


def test_june_saw_it(yard):
    w = yard
    before = {x: trust(w, x) for x in ("june", "nita", "tess", "ruth", "pc")}
    made = take(w, "jerky", now(w))
    assert trust(w, "june") == before["june"] - 1, "she saw him take what she knows is Ruth's"
    assert trust(w, "nita") == before["nita"] and trust(w, "tess") == before["tess"], \
        "Nita has no idea whose it is; Tess thinks it is his own"
    assert trust(w, "ruth") == before["ruth"] - 2, "Ruth is answered as the one robbed (CAS-039), not twice"
    assert trust(w, "pc") == before["pc"], "never the player's character (C06)"
    assert [e.rule_cited for e in made if e.type == "RELATION_CHANGE" and e.actor_id == w.id("june")] == ["CAS-112"]


def test_a_days_takings_count_once(yard):
    w = yard
    t = now(w)
    take(w, "jerky", t)
    after_one = trust(w, "june")
    take(w, "bottle", t + 60_000)
    assert trust(w, "june") == after_one, "the bottle the same day is the same thief, already trusted less"


def test_another_day_another_theft(yard):
    w = yard
    t = now(w)
    take(w, "jerky", t)
    after_one = trust(w, "june")
    take(w, "bottle", t + 86_400_000)
    assert trust(w, "june") == after_one - 1
