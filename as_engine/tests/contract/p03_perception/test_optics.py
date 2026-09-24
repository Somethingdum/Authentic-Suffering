"""Sight (P3). Rules VIS-01..05 (sense/optics.py) and line of sight (physical/space.line_of_sight).

The metal_fence store is dark (light 1) at 23:14, so most of what anyone sees is partial or a
silhouette — that is the point of the scene.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.kernel.clock import MS_PER_DAY, MS_PER_H
from as_engine.physical import objects, space
from as_engine.physical.objects import Holder
from as_engine.sense import optics

pytestmark = pytest.mark.phase(3)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def vis(w, a, b, at=None):
    return optics.visibility(w.store, w.id(a), w.id(b), now(w) if at is None else at)


def write(w, writer, type_, table, key, values, at=None, actor=None):
    with w.store.transaction() as tx:
        return tx.commit_event(Event(type=type_, writer=writer, at=now(w) if at is None else at, turn_index=0, actor_id=actor,
                                     writes=[WriteRecord(op=WriteOp.UPDATE, table=table, key=key, values=values)]))


def test_score_vectors(vectors):
    """VIS-01: the formula and the bands, hand-checked."""
    for c in vectors("optics")["cases"]:
        s = optics.visibility_score(c["light"], c["observer_p"], c["distance_m"], c["concealment"], c["hidden"], c["moved"])
        assert s == c["score"], c["why"]
        assert optics.band(s) == c["band"]


def test_line_of_sight(scenario):
    w = scenario("metal_fence")
    los = lambda a, b: space.line_of_sight(w.store, w.id(a), w.id(b))  # noqa: E731
    assert los("pc", "mara") and los("mara", "pc"), "same place"
    assert los("nita", "stranger"), "a chain-link fence is transparent and the stranger stands at it"
    assert not los("pc", "june"), "the storeroom door is open, but neither is within 3 m of it"
    assert not los("june", "eli"), "a wall never"
    assert not los("pc", "eli"), "the office door is shut"
    assert not los("pc", "nita"), "two portals away"
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("storeroom"), w.id("doorway"), 7.5, 0.5, now(w), None, 0))
    assert los("pc", "june") and los("june", "pc"), "June in the doorway is at the portal"


def test_the_dark_store(scenario):
    """Light 1 inside. Owen (P 5) sees Mara (4.6 m, no concealment) partly; Alice behind the counter
    (concealment 3) not at all; Mara (P 7) makes Owen out at the counter (concealment 2) only as a
    silhouette. Nita (P 8) sees the stranger through the fence partly (optics vector case 2)."""
    w = scenario("metal_fence")
    assert vis(w, "pc", "mara") == "partial"
    assert vis(w, "pc", "alice") == "none"
    assert vis(w, "mara", "pc") == "silhouette"
    assert vis(w, "nita", "stranger") == "partial"
    assert vis(w, "stranger", "nita") == "none", "she is at the dumpster (concealment 3) and he has P 5"
    assert vis(w, "eli", "mara") == "none", "asleep"


def test_hidden_moved_and_crouching(scenario):
    w = scenario("metal_fence")
    write(w, "physical.space", EventType.OVERRIDE, "positions", {"body_id": w.id("mara")}, {"hidden": 1})
    assert vis(w, "pc", "mara") == "silhouette", "hidden: -2"
    t = now(w)
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("alice"), w.id("sales_floor"), w.id("behind_counter"), 6, 5.5, t, None, 0))
    assert vis(w, "pc", "alice", t) == "silhouette", "movement this second: +1"
    assert vis(w, "pc", "alice", t + 1500) == "none", "and only this second"
    assert w.store.query_one("SELECT hidden FROM positions WHERE body_id = ?", (w.id("alice"),))[0] == 0, "moving clears hidden"
    # Alice (P 6) sees Owen at the counter (cover 2, concealment 2): 1 + 0 - 0 - 2 = -1 -> silhouette
    assert vis(w, "alice", "pc") == "silhouette"
    write(w, "physical.bodies", EventType.POSTURE_CHANGE, "bodies", {"body_id": w.id("pc")}, {"posture": "crouched"})
    assert vis(w, "alice", "pc") == "none", "crouched behind cover >= 2: +1 concealment"
    write(w, "physical.bodies", EventType.POSTURE_CHANGE, "bodies", {"body_id": w.id("mara")}, {"posture": "crouched"})
    write(w, "physical.space", EventType.OVERRIDE, "positions", {"body_id": w.id("mara")}, {"hidden": 0})
    assert vis(w, "pc", "mara") == "partial", "crouching at a window (cover 0) hides nothing"


def test_a_flashlight_lights_its_surroundings(scenario):
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        objects.create(tx, "core:item/flashlight", 1, Holder("body", w.id("pc"), "hand_l"), "scenario", {"on": True}, now(w), None, 0)
    # light 3 within 6 m of Owen: Alice (1.5 m away) 3 + 0 - 0 - 3 = 0 -> silhouette; Mara 3 -> clear
    assert vis(w, "pc", "alice") == "silhouette"
    assert vis(w, "pc", "mara") == "clear"


def test_outdoor_light_follows_the_sun(scenario):
    w = scenario("metal_fence")
    noon = (now(w) // MS_PER_DAY + 1) * MS_PER_DAY + 12 * MS_PER_H
    write(w, "kernel.clock", EventType.CLOCK_ADVANCE, "world_clock", {"id": 1}, {"now_ms": noon}, at=noon)
    assert vis(w, "nita", "stranger", noon) == "clear", "midday light 4 outdoors"
    assert vis(w, "pc", "mara", noon) == "partial", "indoor light does not change with the sun"
