"""Items, containers, firearms, conservation (P2). Rules CONSERVE-01/02, OBJ-02..06 (physical/objects.py).

Item stats are read from canon (the core pack), never hard-coded, so content tuning cannot break
these tests; the RULES are what is under test.
"""

from __future__ import annotations

import json

import pytest

from as_engine.audit.commit_gate import compute
from as_engine.contracts.events import EventType
from as_engine.physical import objects
from as_engine.physical.objects import Holder

pytestmark = pytest.mark.phase(2)


def item(w, iid):
    r = dict(w.store.query_one("SELECT * FROM items WHERE item_id = ?", (iid,)))
    r["props"] = json.loads(r["props"])
    return r


def cause(tx, make_event, actor=None):
    return tx.commit_event(make_event(actor_id=actor)).event_id


def mag_of(w, gun_id):
    return w.store.query_one("SELECT item_id FROM items WHERE container_id = ?", (gun_id,))[0]


def gate_ok(w, *bits):
    res = compute(w.store, 0)
    return all(res.bit(b) == 1 for b in bits)


# --------------------------------------------------------------------------- location
def test_location_of(scenario):
    w = scenario("metal_fence")
    assert objects.location_of(w.store, w.id("glock")) == Holder("body", w.id("pc"), "hand_r")
    assert objects.location_of(w.store, mag_of(w, w.id("glock"))) == Holder("container", w.id("glock"))


# --------------------------------------------------------------------------- transfer
def test_transfer_to_the_floor_and_back(scenario, make_event):
    w = scenario("metal_fence")
    ledger = w.store.query_one("SELECT item_id FROM items WHERE holder_body = ?", (w.id("alice"),))[0]
    with w.store.transaction() as tx:
        ev = objects.transfer(tx, ledger, Holder("place", w.id("sales_floor"), anchor_id=w.id("counter")), None, 5, w.id("alice"), None, 0)
    assert ev.type == EventType.ITEM_TRANSFER and ev.writer == "physical.objects" and ev.event_id
    assert ev.payload["from"] == {"kind": "body", "id": w.id("alice"), "slot": "hand_l", "anchor_id": None}
    assert ev.payload["to"] == {"kind": "place", "id": w.id("sales_floor"), "slot": None, "anchor_id": w.id("counter")}
    assert ev.payload["new_item_id"] is None
    it = item(w, ledger)
    assert (it["holder_body"], it["place_id"], it["anchor_id"]) == (None, w.id("sales_floor"), w.id("counter"))
    assert objects.access_time_s(w.store, ledger) == 1.0
    assert gate_ok(w, "W01", "W04", "E09")


def test_one_item_per_hand(scenario):
    w = scenario("metal_fence")
    ledger = w.store.query_one("SELECT item_id FROM items WHERE holder_body = ?", (w.id("alice"),))[0]
    with w.store.transaction() as tx:
        with pytest.raises(ValueError):
            objects.transfer(tx, ledger, Holder("body", w.id("pc"), "hand_r"), None, 0, None, None, 0)  # the Glock is there
        objects.transfer(tx, ledger, Holder("body", w.id("pc"), "hand_l"), None, 0, None, None, 0)
    assert gate_ok(w, "E03")


def test_split_a_stack_conserves_quantity(scenario):
    w = scenario("metal_fence")
    ammo = w.store.query_one("SELECT item_id FROM items WHERE def_ref = 'core:item/ammo_38'")[0]
    before = objects.total_qty(w.store, "core:item/ammo_38")
    with w.store.transaction() as tx:
        ev = objects.transfer(tx, ammo, Holder("body", w.id("pc"), "pocket"), 5, 0, w.id("mara"), None, 0)
    new = ev.payload["new_item_id"]
    assert new and new != ammo and len(ev.writes) == 2, "one ITEM_TRANSFER carries both writes"
    a, b = item(w, ammo), item(w, new)
    assert (a["qty"], a["holder_body"]) == (6, w.id("mara")) and (b["qty"], b["holder_body"], b["holder_slot"]) == (5, w.id("pc"), "pocket")
    assert (b["def_ref"], b["props"], b["lot_id"], b["condition"]) == (a["def_ref"], a["props"], a["lot_id"], a["condition"])
    assert objects.total_qty(w.store, "core:item/ammo_38") == before == 11
    assert gate_ok(w, "W04")


def test_container_capacity(scenario, canon):
    w = scenario("metal_fence")
    box_def = canon.get("core:item/cardboard_box")
    axe_bulk = canon.get("core:item/fire_axe").bulk
    with w.store.transaction() as tx:
        box = objects.create(tx, "core:item/cardboard_box", 1, Holder("place", w.id("storeroom")), "scenario", {}, 0, None, 0).payload["item_id"]
        axe = w.store.query_one("SELECT item_id FROM items WHERE def_ref = 'core:item/fire_axe'")[0]
        fits = box_def.container.capacity_bulk // axe_bulk
        assert fits >= 1
        objects.transfer(tx, axe, Holder("container", box), None, 0, None, None, 0)
        # fill with ledger books (bulk from canon) until exactly full, then one more must fail
        ledger_bulk = canon.get("core:item/ledger_book").bulk
        free = box_def.container.capacity_bulk - axe_bulk
        for _ in range(free // ledger_bulk):
            objects.create(tx, "core:item/ledger_book", 1, Holder("container", box), "scenario", {}, 0, None, 0)
        with pytest.raises(ValueError):
            objects.create(tx, "core:item/ledger_book", 1, Holder("container", box), "scenario", {}, 0, None, 0)
    assert gate_ok(w, "W03", "W04")
    assert objects.access_time_s(w.store, axe) == box_def.container.access_time_s + 1.0  # box lies on the floor


def test_nothing_goes_inside_itself_or_into_a_non_container(scenario):
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        box = objects.create(tx, "core:item/cardboard_box", 1, Holder("place", w.id("storeroom")), "scenario", {}, 0, None, 0).payload["item_id"]
        inner = objects.create(tx, "core:item/shoulder_bag", 1, Holder("container", box), "scenario", {}, 0, None, 0).payload["item_id"]
        with pytest.raises(ValueError):
            objects.transfer(tx, box, Holder("container", box), None, 0, None, None, 0)
        with pytest.raises(ValueError):
            objects.transfer(tx, box, Holder("container", inner), None, 0, None, None, 0)
        ledger = w.store.query_one("SELECT item_id FROM items WHERE holder_body = ?", (w.id("june"),))[0]
        with pytest.raises(ValueError):
            objects.transfer(tx, box, Holder("container", ledger), None, 0, None, None, 0)  # a book holds nothing


def test_magazines_fit_only_their_gun(scenario):
    w = scenario("metal_fence")
    glock = w.id("glock")
    with w.store.transaction() as tx:
        spare = objects.create(tx, "core:item/magazine_9mm_15", 1, Holder("body", w.id("pc"), "pocket"), "scenario", {"rounds": 15}, 0, None, 0).payload["item_id"]
        with pytest.raises(ValueError):
            objects.transfer(tx, spare, Holder("container", glock), None, 0, None, None, 0)  # one magazine at a time
        ammo = w.store.query_one("SELECT item_id FROM items WHERE def_ref = 'core:item/ammo_38'")[0]
        with pytest.raises(ValueError):
            objects.transfer(tx, ammo, Holder("container", glock), 1, 0, None, None, 0)  # loose rounds are not a magazine
        old = mag_of(w, glock)
        objects.transfer(tx, old, Holder("body", w.id("pc"), "pack"), None, 0, None, None, 0)
        objects.transfer(tx, spare, Holder("container", glock), None, 0, None, None, 0)
    assert mag_of(w, glock) == spare
    assert objects.access_time_s(w.store, spare) == 1.0  # 1 s release + 0 s (the gun is in hand)


# --------------------------------------------------------------------------- create / destroy
def test_create_rules(scenario):
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        with pytest.raises(ValueError):
            objects.create(tx, "core:item/fire_axe", 2, Holder("place", w.id("storeroom")), "scenario", {}, 0, None, 0)  # not stackable
        with pytest.raises(ValueError):
            objects.create(tx, "core:item/fire_axe", 1, Holder("place", w.id("storeroom")), "magic", {}, 0, None, 0)
        ev = objects.create(tx, "core:item/ammo_9mm", 20, Holder("place", w.id("storeroom"), anchor_id=w.id("shelves")), "loot", {}, 0, None, 0,
                            event_origin="system")
    assert ev.type == EventType.ITEM_CREATED and ev.origin == "system"
    assert {k: ev.payload[k] for k in ("def_ref", "qty", "origin")} == {"def_ref": "core:item/ammo_9mm", "qty": 20, "origin": "loot"}
    assert item(w, ev.payload["item_id"])["origin"] == "loot"
    assert gate_ok(w, "W04")


def test_destroy_needs_a_cause_and_an_empty_container(scenario, make_event):
    w = scenario("metal_fence")
    ledger = w.store.query_one("SELECT item_id FROM items WHERE holder_body = ?", (w.id("june"),))[0]
    with w.store.transaction() as tx:
        c = cause(tx, make_event)
        with pytest.raises(ValueError):
            objects.destroy(tx, w.id("glock"), 0, c, 0)  # it still holds its magazine
        ev = objects.destroy(tx, ledger, 0, c, 0)
    assert ev.type == EventType.ITEM_DESTROYED and ev.payload == {"item_id": ledger, "def_ref": "core:item/ledger_book", "qty": 1, "cause_event_id": c}
    assert w.store.query_one("SELECT 1 FROM items WHERE item_id = ?", (ledger,)) is None
    assert objects.total_qty(w.store, "core:item/ledger_book") == 1  # Alice still has hers
    assert gate_ok(w, "W04")


# --------------------------------------------------------------------------- firearms (OBJ-05)
def test_a_magazine_fed_pistol_fires_until_empty_then_clicks(scenario):
    """Owen's Glock: one chambered + 14 in the magazine = 15 shots, then a click."""
    w = scenario("metal_fence")
    glock, pc = w.id("glock"), w.id("pc")
    mag = mag_of(w, glock)
    results = []
    with w.store.transaction() as tx:
        for _ in range(16):
            fired, ev = objects.fire(tx, glock, 0, pc, None, 0)
            results.append((fired, ev.payload["result"], ev.payload["rounds_left"]))
    assert results[0] == (True, "fired", 14)
    assert results[13] == (True, "fired", 1)
    assert results[14] == (True, "fired", 0)
    assert results[15] == (False, "click", 0)
    assert item(w, glock)["props"]["chambered"] is False and item(w, mag)["props"]["rounds"] == 0


def test_an_unloaded_pistol_only_clicks(scenario):
    """INTENT-03 at the object level: nothing chambered -> click, no writes, every time."""
    w = scenario("empty_gun")
    gun = w.store.query_one("SELECT item_id FROM items WHERE holder_body = ? AND holder_slot = 'hand_r'", (w.id("reggie"),))[0]
    with w.store.transaction() as tx:
        for _ in range(3):
            fired, ev = objects.fire(tx, gun, 0, w.id("reggie"), None, 0)
            assert (fired, ev.payload["result"], ev.writes) == (False, "click", [])
    assert ev.type == EventType.ITEM_CONDITION and ev.writer == "physical.objects"


def test_a_revolver_counts_its_own_rounds(scenario):
    w = scenario("metal_fence")
    rev = w.id("revolver")
    with w.store.transaction() as tx:
        shots = [objects.fire(tx, rev, 0, w.id("mara"), None, 0)[0] for _ in range(7)]
    assert shots == [True] * 6 + [False]
    assert item(w, rev)["props"]["rounds"] == 0 and item(w, rev)["props"]["holstered"] is True


# --------------------------------------------------------------------------- carrying
def test_access_times(scenario):
    w = scenario("metal_fence")
    assert objects.access_time_s(w.store, w.id("glock")) == 0.0
    axe = w.store.query_one("SELECT item_id FROM items WHERE def_ref = 'core:item/fire_axe'")[0]
    assert objects.access_time_s(w.store, axe) == 1.0
    ammo = w.store.query_one("SELECT item_id FROM items WHERE def_ref = 'core:item/ammo_38'")[0]
    assert objects.access_time_s(w.store, ammo) == 2.0


def test_carried_mass_and_load_word(scenario, canon):
    w = scenario("metal_fence")
    kg = sum(canon.get(r).mass_g for r in ("core:item/glock_19", "core:item/magazine_9mm_15", "core:item/fire_axe")) / 1000
    assert objects.carried_mass_kg(w.store, w.id("pc")) == pytest.approx(kg)
    assert objects.load_word(w.store, w.id("pc")) == "light"
    assert objects.carried_mass_kg(w.store, w.id("eli")) == 0.0


@pytest.mark.parametrize("threshold,below,above", [(0.20, "light", "moderate"), (0.35, "moderate", "heavy"), (0.50, "heavy", "overloaded")])
def test_load_word_bands(scenario, canon, threshold, below, above):
    """OBJ-06 bands: <= 20 % light, <= 35 % moderate, <= 50 % heavy, else overloaded. The load is
    built from 9 mm rounds: the most that stays at or under the threshold, then one more."""
    import math

    w = scenario("metal_fence")
    eli = w.id("eli")
    mass_g = w.store.query_one("SELECT mass_kg FROM bodies WHERE body_id = ?", (eli,))[0] * 1000
    g = canon.get("core:item/ammo_9mm").mass_g
    n = math.floor(threshold * mass_g / g)
    with w.store.transaction() as tx:
        stack = objects.create(tx, "core:item/ammo_9mm", n, Holder("body", eli, "pack"), "scenario", {}, 0, None, 0).payload["item_id"]
    assert objects.load_word(w.store, eli) == below
    with w.store.transaction() as tx:
        objects.create(tx, "core:item/ammo_9mm", 1, Holder("body", eli, "pocket"), "scenario", {}, 0, None, 0)
    assert objects.load_word(w.store, eli) == above
    assert stack


def test_inventory_tree(scenario, canon):
    w = scenario("metal_fence")
    tree = objects.inventory_tree(w.store, w.id("pc"))
    assert [(n["def_ref"], n["slot"]) for n in tree] == [("core:item/glock_19", "hand_r"), ("core:item/fire_axe", "worn")]
    glock = tree[0]
    assert glock["name"] == canon.get("core:item/glock_19").name and glock["props"] == {"chambered": True}
    assert [(c["def_ref"], c["slot"], c["props"]) for c in glock["contents"]] == [("core:item/magazine_9mm_15", None, {"rounds": 14})]
    mara = objects.inventory_tree(w.store, w.id("mara"))
    assert [n["slot"] for n in mara] == ["worn", "pocket"]
    assert mara[1]["name"] == canon.get("core:item/ammo_38").plural and mara[1]["qty"] == 11
