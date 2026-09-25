"""A theft somebody saw becomes talk (P9, Actor v2 B6 — the known CAS-012 fault). Rule CAS-05's
theft_witnesses_of (action/cascade.py), core cascade CAS-012, world/rumours.py seed.

Whether a taking is theft is for those who see it and what they know (AFF-11), never for the
taker's menu. In a market yard Dale takes the jerky from the stall. June saw it and knows the
jerky is Ruth's; Nita saw it too but has no idea whose it is; Tess thinks it is Dale's own. Only
June now carries it — and from her, talk spreads.
"""

from __future__ import annotations

import copy

import pytest

from as_engine.action import cascade
from as_engine.mind import perception
from as_engine.physical import objects
from as_engine.physical.objects import Holder
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(9)

THEFT = "took_what_was_not_theirs"

YARD = {
    "schema": "as.scenario.v1", "name": "stall_yard", "seed": 41, "start": {"day": 400, "time": "12:00"},
    "places": [{"id": "yard", "name": "Market yard", "kind": "outdoor", "indoor": False, "material": "open_air",
                "width_m": 30, "depth_m": 20, "light": 3,
                "anchors": [{"id": "stall", "name": "stall", "x": 10, "y": 10}, {"id": "well", "name": "well", "x": 12, "y": 10},
                            {"id": "gate", "name": "gate", "x": 14, "y": 10}, {"id": "bench", "name": "bench", "x": 10, "y": 13}]}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "yard", "anchor": "gate"},
        {"id": "dale", "dossier": "core:actor/dale_pruitt", "place": "yard", "anchor": "stall"},
        {"id": "june", "dossier": "core:actor/june_okafor", "place": "yard", "anchor": "well"},
        {"id": "nita", "dossier": "core:actor/nita_reyes", "place": "yard", "anchor": "bench"},
        {"id": "tess", "stub": {"name": "Tess Hale", "age": 31, "sex": "female"}, "place": "yard", "x": 11, "y": 12},
        {"id": "ruth", "stub": {"name": "Ruth Kell", "age": 52, "sex": "female"}, "place": "yard", "x": 25, "y": 5},
    ],
    "items": [{"item": "core:item/jerky_pack", "place": "yard", "anchor": "stall", "label": "jerky"}],
    "beliefs": [
        {"holder": "june", "subject_type": "object", "subject": "jerky", "predicate": "owner", "value": "ruth",
         "text": "The jerky on the stall is Ruth's.", "confidence": 3, "provenance": "witnessed"},
        {"holder": "tess", "subject_type": "object", "subject": "jerky", "predicate": "owner", "value": "dale",
         "text": "Dale's jerky is on the stall.", "confidence": 2, "provenance": "witnessed"},
    ],
}


@pytest.fixture
def yard(fixture_packs, core_pack_dir):
    worlds = []

    def _load(change=None):
        spec = copy.deepcopy(YARD)
        if change is not None:
            change(spec)
        w = load_scenario(spec, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        return w
    yield _load
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def take(w, to=None):
    """Dale takes the jerky (into his hand, or wherever ``to`` says); everyone there sees what they see."""
    t = now(w)
    with w.store.transaction() as tx:
        ev = objects.transfer(tx, w.id("jerky"), to or Holder("body", w.id("dale"), "hand_l"), None, t, w.id("dale"), None, 0)
        for x in ("june", "nita", "tess", "ruth", "pc"):
            perception.compile_aftermath(tx, w.id(x), [ev], t + 500, 0)
    return ev


def holds_it(w, who):
    return bool(w.store.query(
        "SELECT 1 FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id WHERE h.holder_id = ? AND "
        "h.superseded_by IS NULL AND p.subject_id = ? AND p.predicate = ?", (w.id(who), w.id("dale"), THEFT)))


def rule(w):
    return [r for r in w.canon.all("cascade") if r.id == "CAS-012"]


def test_only_who_saw_it_and_knows_whose_it_is(yard):
    w = yard()
    ev = take(w)
    seen = {r[0] for r in w.store.query("SELECT holder_id FROM percept_log WHERE event_id = ? AND fidelity IN ('exact','partial')",
                                        (ev.event_id,))}
    assert {w.id("june"), w.id("nita"), w.id("tess")} <= seen, "the three at the stall saw it"
    with w.store.transaction() as tx:
        assert cascade.select(tx, "theft_witnesses_of(trigger.event_id)", ev) == [w.id("june")]


def test_the_rumour_starts_with_her(yard):
    w = yard()
    ev = take(w)
    with w.store.transaction() as tx:
        out = cascade.sweep(tx, [ev], rule(w), now(w), 0)
    assert out and all(e.rule_cited == "CAS-012" for e in out)
    assert holds_it(w, "june")
    assert not any(holds_it(w, x) for x in ("nita", "tess", "ruth", "pc")), \
        "nobody else was told yet: from June, talk spreads (world.rumours)"


def test_what_is_their_own_is_no_theft(yard):
    """Taking back what the taker's own household or group owns, or putting a thing down, is not
    theft to anyone."""
    def dale_owns(spec):
        spec["beliefs"][0]["value"] = "dale"
    w = yard(dale_owns)
    ev = take(w)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "theft_witnesses_of(trigger.event_id)", ev) == []
    w2 = yard()
    down = take(w2, to=Holder("place", w2.id("yard"), anchor_id=w2.id("bench")))
    with w2.store.transaction() as tx:
        assert cascade.select(tx, "theft_witnesses_of(trigger.event_id)", down) == [], "moved, not taken"
