"""What washing, the dead's gore and clothes look like on a menu, and what a person knows of their own
cold and clothes (P4, the owner's F1c: DECISIONS D-86). mind/affordance.py (item_carried per effect:
wash, take_off, change_into; AFF-02 strip_clothing; CNT-11), mind/packet.py body_lines (COLD_LINES,
BARE_LINES), core law public_decency (a known law is a cost, C05).

A wash house in a settlement (a dict scenario): Ada, who lives there, with a knife, water and a spare
top; Joe out cold; Mia, ten; Nan, who has nothing on; one of the dead by the wall.
"""

from __future__ import annotations

import copy

import pytest

from as_engine.contracts.common import LOD
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import BARE_LINES, COLD_LINES, build_packet
from as_engine.physical import bodies
from as_engine.physical.bodies import WoundSpec
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(4)

LIGHT = [{"item": "core:item/t_shirt"}, {"item": "core:item/jeans"}, {"item": "core:item/sneakers"}]
WARM = [{"item": "core:item/parka"}, {"item": "core:item/thermal_top"}, {"item": "core:item/cargo_pants"},
        {"item": "core:item/combat_boots"}]
KID = [{"item": "core:item/fleece_jacket"}, {"item": "core:item/t_shirt"}, {"item": "core:item/leggings"},
       {"item": "core:item/sneakers"}]
DECENCY = "core:law/public_decency"
MEMBERS = "Stripping where people can see you gets you marched to the wash house by the watch and talked about for a week."


def looks(outfit):
    return {"hair_colour": "brown", "hair_length": "short", "eye_colour": "grey", "complexion": "pale skin",
            "outfit": outfit}


HOUSE = {
    "schema": "as.scenario.v1", "name": "wash_house_menu", "seed": 78, "start": {"day": 400, "time": "10:00"},
    "rules": {"packet": {"max_affordances": 80}},
    "places": [{"id": "house", "name": "Wash house", "material": "brick", "light": 3, "width_m": 12, "depth_m": 8}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "house", "x": 11, "y": 7},
        {"id": "ada", "stub": {"name": "Ada Pike", "age": 34, "sex": "female"}, "place": "house", "x": 2, "y": 3,
         "looks": looks(LIGHT), "dress": True,
         "inventory": [{"item": "core:item/kitchen_knife", "slot": "hand_r", "label": "knife"},
                       {"item": "core:item/water_jug", "slot": "pack", "label": "jug"},
                       {"item": "core:item/water_bottle", "slot": "pack", "label": "bottle"},
                       {"item": "core:item/thermal_top", "slot": "pack", "label": "thermal"}]},
        {"id": "joe", "stub": {"name": "Joe Varga", "age": 41, "sex": "male"}, "place": "house", "x": 3, "y": 3,
         "looks": looks(WARM), "dress": True, "awareness": "unconscious", "posture": "lying"},
        {"id": "mia", "stub": {"name": "Mia Pike", "age": 10, "sex": "female"}, "place": "house", "x": 2, "y": 4,
         "looks": looks(KID), "dress": True,
         "inventory": [{"item": "core:item/athletic_top", "slot": "pack", "label": "top"}]},
        {"id": "nan", "stub": {"name": "Nan Ortiz", "age": 29, "sex": "female"}, "place": "house", "x": 6, "y": 3,
         "looks": looks(LIGHT)},
        {"id": "dead", "infected": "ZOMBIE_ARCHETYPE_SHAMBLER01", "controller": "policy", "place": "house", "x": 2.5, "y": 2},
    ],
    "groups": [{"id": "folk", "name": "Wash house folk", "members": [{"actor": "ada", "role": "member"}]}],
    "settlements": [{"id": "hold", "name": "The Hold", "place": "house", "group": "folk"}],
}


@pytest.fixture
def house(fixture_packs, core_pack_dir):
    worlds = []

    def _load(change=None):
        spec = copy.deepcopy(HOUSE)
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


def menu(w, local, at=None):
    t = now(w) if at is None else at
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(local), t, 0)
        return enumerate_affordances(tx, w.id(local), w.canon.all("affordance"), t, 0)


def bound(aset, def_id):
    return {(o.target_id, o.item_id) for o in aset.pool if o.def_id == def_id}


def items_of(w, local, *refs):
    out = set()
    for ref in refs:
        out |= {r[0] for r in w.store.query("SELECT item_id FROM items WHERE holder_body = ? AND def_ref = ?",
                                            (w.id(local), ref))}
    return out


def packet(w, local, at=None):
    t = now(w) if at is None else at
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(local), t, 0)
        aff = enumerate_affordances(tx, w.id(local), w.canon.all("affordance"), t, 0)
        return build_packet(tx, w.id(local), LOD.HOT, aff, 0, t)


# --------------------------------------------------------------------------- the menu
def test_her_water_and_her_clothes(house):
    """wash for what holds water (never the knife); take_off for what she wears; change_into for the
    clothes she carries that are not on."""
    w = house()
    a = menu(w, "ada")
    assert {i for _, i in bound(a, "wash_self")} == {w.id("jug"), w.id("bottle")}
    assert {i for _, i in bound(a, "take_off_clothing")} == items_of(w, "ada", "core:item/t_shirt", "core:item/jeans",
                                                                   "core:item/sneakers")
    assert {i for _, i in bound(a, "change_into")} == {w.id("thermal")}


def test_the_gore_of_the_dead_only_once_they_are_down(house):
    w = house()
    assert bound(menu(w, "ada"), "smear_gore") == set(), "one still on its feet is not a thing to smear yourself with"
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=now(w), turn_index=0, payload={"what": "test"}))
        bodies.apply_harm(tx, w.id("dead"), WoundSpec("head", "blunt", "catastrophic", 0), now(w), c.event_id, 0, w.rng)
    assert bound(menu(w, "ada", now(w) + 1000), "smear_gore") == {(w.id("dead"), None)}


def test_off_someone_out_cold_what_comes_off_first(house):
    """strip_clothing: the outermost piece at each slot — the parka, not the thermal under it."""
    w = house()
    got = {i for t, i in bound(menu(w, "ada"), "strip_clothing") if t == w.id("joe")}
    assert got == items_of(w, "joe", "core:item/parka", "core:item/cargo_pants", "core:item/combat_boots")


def test_nothing_ever_offers_to_bare_a_child(house):
    """CNT-11: nobody is offered a child's clothes, and a child is never offered what would leave
    the torso or the groin uncovered — the fleece or the shirt while the other covers her, the
    shoes, a different top; never the leggings."""
    w = house(lambda s: [b.update(awareness="unconscious", posture="lying") for b in s["bodies"] if b["id"] == "mia"])
    assert not {t for t, _ in bound(menu(w, "ada"), "strip_clothing")} & {w.id("mia")}
    w2 = house()
    m = menu(w2, "mia")
    assert {i for _, i in bound(m, "take_off_clothing")} == items_of(w2, "mia", "core:item/fleece_jacket", "core:item/t_shirt",
                                                                    "core:item/sneakers")
    assert {i for _, i in bound(m, "change_into")} == {w2.id("top")}


def test_undressing_in_front_of_people_is_against_the_law_here(house):
    """public_decency: to someone who knows it (Ada lives here), taking clothes off — hers or anyone's
    — carries the law's cost; changing and washing do not."""
    w = house(lambda s: s["settlements"][0].update(laws=[DECENCY]))
    a = menu(w, "ada")
    for def_id in ("take_off_clothing", "strip_clothing"):
        assert {o.cost_note for o in a.pool if o.def_id == def_id} == {MEMBERS}, def_id
    for def_id in ("change_into", "wash_self"):
        assert {o.cost_note for o in a.pool if o.def_id == def_id} == {None}, def_id
    free = house()
    assert {o.cost_note for o in menu(free, "ada").pool if o.def_id == "take_off_clothing"} == {None}


def test_the_law_is_in_the_core_pack(canon):
    law = canon.get(DECENCY)
    assert law.kind == "decency" and {e.affordance_tag for e in law.affordance_effects} == {"undress"}
    assert {d.id for d in canon.all("affordance") if "undress" in d.tags} == {"take_off_clothing", "strip_clothing"}


# --------------------------------------------------------------------------- what they know of themselves
def test_you_know_when_you_have_nothing_on(house):
    w = house(lambda s: [b.update(looks=looks([{"item": "core:item/jeans"}]), awareness="awake", posture="standing")
                         for b in s["bodies"] if b["id"] == "joe"])
    assert BARE_LINES[0] in packet(w, "nan").body_lines
    assert BARE_LINES[1] in packet(w, "joe").body_lines, "jeans and nothing else: bare to the waist"
    dressed = packet(w, "ada").body_lines
    assert BARE_LINES[0] not in dressed and BARE_LINES[1] not in dressed
    pc = packet(w, "pc").body_lines
    assert BARE_LINES[0] not in pc and BARE_LINES[1] not in pc, "a body whose looks were never recorded makes no claim"


@pytest.mark.parametrize("stage,line", [(1, "You are cold."), (3, "You are shivering hard."), (6, "You are freezing to death.")])
def test_you_know_when_you_are_cold(house, stage, line):
    w = house()
    ada = w.id("ada")
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.NEED_STAGE, writer="physical.bodies", at=now(w), turn_index=0, target_ids=[ada],
                              writes=[WriteRecord(op=WriteOp.UPDATE, table="needs", key={"body_id": ada},
                                                  values={"chill": stage * 4, "cold_stage": stage})],
                              payload={"body_id": ada, "need": "cold", "stage": stage, "chill": stage * 4}))
    assert COLD_LINES[stage] == line and line in packet(w, "ada").body_lines
    assert not any(ln in packet(w, "nan").body_lines for ln in set(COLD_LINES.values()))
