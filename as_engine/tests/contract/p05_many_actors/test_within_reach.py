"""Within reach (D-278). mind/affordance.py (ranges touch / reach / same_place); action/effects.py EFF-02 'target_gone'.

A man in a yard with an axe in his hand and one of the dead on the far side of a chain-link fence was offered "Bring
your fire axe down on its head", "Hit it", "Shove it" — first on his list, since it was the threat — and every one of
them came back blocked: a body in another place is never a target of a blow (EFF-02), and nobody swings an axe through
a fence, a shut window or a gateway they are not standing in. Owen, at the front of a house, was offered the same for
a walker out in the crossroads. A blow, a shove or a grab is offered for someone in the same place; to hit the
one beyond the gate, go through it first.
"""

from __future__ import annotations

import pytest

from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(5)

FENCE = {"kind": "fence", "name": "chain-link fence", "w": 0, "h": 0, "seal_db": 2, "transparent": True, "height": 180}
WINDOW = {"kind": "window", "name": "window", "open": False, "w": 100, "h": 100, "seal_db": 20, "transparent": True,
          "height": 90}
GATE = {"kind": "door", "name": "gate", "open": True, "w": 100, "h": 200, "seal_db": 2}
BLOWS = {"strike_melee", "strike_head", "finish_downed", "punch", "grapple", "shove", "shove_toward_dead", "disarm"}


def yard(fixture_packs, core_pack_dir, portal, dead_in="lot"):
    sc = {"schema": "as.scenario.v1", "name": "fence", "seed": 7, "start": {"day": 400, "time": "12:00"},
          "places": [{"id": "yard", "name": "Yard", "material": "open_air", "indoor": False, "light": 4, "width_m": 10,
                      "depth_m": 6, "anchors": [{"id": "f_in", "name": "fence", "kind": "feature", "x": 5, "y": 5.8}]},
                     {"id": "lot", "name": "Lot", "material": "open_air", "indoor": False, "light": 4, "width_m": 10,
                      "depth_m": 6, "anchors": [{"id": "f_out", "name": "far side of the fence", "kind": "feature", "x": 5,
                                                 "y": 0.3}]}],
          "portals": [dict({"id": "fence", "a": "yard", "b": "lot", "anchor_a": "f_in", "anchor_b": "f_out"}, **portal)],
          "bodies": [{"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "yard", "x": 5, "y": 5.4,
                      "inventory": [{"item": "core:item/fire_axe", "slot": "hand_r", "label": "axe"}]},
                     {"id": "dead", "infected": "ZOMBIE_ARCHETYPE_SHAMBLER01", "controller": "policy", "place": dead_in,
                      "x": 5, "y": 0.6 if dead_in == "lot" else 4.6}]}
    return load_scenario(sc, packs_root=fixture_packs, core_pack_dir=core_pack_dir)


def blows(w):
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id("pc"), t, 0)
        a = enumerate_affordances(tx, w.id("pc"), w.canon.all("affordance"), t + 100, 0)
    return {o.def_id for o in a.options if o.target_id == w.id("dead")} & BLOWS, a


@pytest.mark.parametrize("portal", [FENCE, WINDOW, GATE], ids=["fence", "shut window", "open gate"])
def test_not_through_it(fixture_packs, core_pack_dir, portal):
    w = yard(fixture_packs, core_pack_dir, portal)
    got, a = blows(w)
    assert not got, got
    assert w.id("dead") in a.threats, "it is still the danger in front of him"


def test_on_his_side_of_it(fixture_packs, core_pack_dir):
    w = yard(fixture_packs, core_pack_dir, FENCE, dead_in="yard")
    got, _ = blows(w)
    assert {"strike_melee", "strike_head", "shove"} <= got, got
