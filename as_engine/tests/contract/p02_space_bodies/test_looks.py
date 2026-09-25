"""How people look, what they wear and what is on them (P2, the owner's F1a). Rules LOOK-01,
LOOK-02, LOOK-04, CNT-12 (clothing), CNT-17 (contracts/dossier.py Looks; contracts/content.py
ClothingProps; physical/bodies.py looks_of, condition_of, soil, create; physical/objects.py worn,
coverage, visible_gear, dress; testing/scenario.py dress / looks; content/pack.py).

Everyone has a visual identity — hair, skin, marks, clothes — and what is on them (grime, blood,
gore, rain) shows. The world here is a church hall (a dict scenario): Owen and Mara dressed from
their dossiers, Vic Lamb (a stub with his own looks) in a long parka over a holstered pistol, and
Dale Pruitt, whose looks were never recorded.
"""

from __future__ import annotations

import copy
import json

import pytest
import yaml

from as_engine.content.pack import load_canon
from as_engine.contracts.dossier import Looks
from as_engine.contracts.events import EVENT_CLASS, EventClass, EventType
from as_engine.kernel.jsoncanon import canonical_json
from as_engine.physical import bodies, objects
from as_engine.testing.scenario import StubSpec, load_scenario, stub_dossier

pytestmark = pytest.mark.phase(2)

VIC_LOOKS = {
    "hair_colour": "", "hair_length": "bald", "facial_hair": "full_beard", "eye_colour": "brown",
    "complexion": "ruddy skin",
    "marks": [{"what": "a faded anchor tattoo", "where": "on the left forearm", "shows": "near"}],
    "outfit": [{"item": "core:item/parka"},
               {"item": "core:item/t_shirt", "colour": "black", "insignia": "a feed store logo"},
               {"item": "core:item/cargo_pants"},
               {"item": "core:item/boots", "state": "soiled"}],
}

HALL = {
    "schema": "as.scenario.v1", "name": "church_hall", "seed": 12, "start": {"day": 300, "time": "10:00"},
    "places": [{"id": "hall", "name": "Church hall", "material": "brick", "light": 3, "width_m": 14, "depth_m": 10,
                "anchors": [{"id": "door", "name": "door", "x": 1, "y": 5},
                            {"id": "table", "name": "long table", "x": 7, "y": 5}]}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "hall", "x": 2, "y": 5,
         "dress": True, "inventory": [{"item": "core:item/fire_axe", "slot": "hand_r", "label": "axe"}]},
        {"id": "mara", "dossier": "core:actor/mara_voss", "place": "hall", "x": 4, "y": 5, "dress": True,
         "inventory": [{"item": "core:item/revolver_38", "slot": "worn", "label": "revolver", "props": {"rounds": 6}},
                       {"item": "core:item/flashlight", "slot": "pocket", "label": "torch"}]},
        {"id": "vic", "stub": {"name": "Vic Lamb", "age": 52, "sex": "male"}, "place": "hall", "x": 6, "y": 5,
         "dress": True, "looks": VIC_LOOKS,
         "inventory": [{"item": "core:item/glock_19", "slot": "worn", "label": "pistol"}]},
        {"id": "dale", "dossier": "core:actor/dale_pruitt", "place": "hall", "x": 8, "y": 5,
         "inventory": [{"item": "core:item/steel_pipe", "slot": "hand_r", "label": "pipe"},
                       {"item": "core:item/crowbar", "slot": "worn", "label": "bar"}]},
    ],
    "items": [{"item": "core:item/jerky_pack", "place": "hall", "anchor": "table", "label": "jerky"}],
}


@pytest.fixture
def hall(fixture_packs, core_pack_dir):
    """hall(change=None) -> a loaded copy of HALL after ``change(spec)`` edited it."""
    worlds = []

    def _load(change=None):
        spec = copy.deepcopy(HALL)
        if change is not None:
            change(spec)
        w = load_scenario(spec, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        return w

    yield _load
    for w in worlds:
        w.store.close()


def body_spec(spec, local):
    return next(b for b in spec["bodies"] if b["id"] == local)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def worn_refs(w, local):
    return [r["def_ref"] for r in objects.worn(w.store, w.id(local))]


def item_of(w, local, def_ref):
    [r] = [r for r in objects.worn(w.store, w.id(local)) if r["def_ref"] == def_ref]
    return r["item_id"]


# --------------------------------------------------------------------------- the core pack
def test_every_core_person_has_looks_and_is_dressed_by_them(canon):
    """LOOK-01/02, CNT-17: the ten people and three playable characters each have looks; each
    outfit is clothing that covers the torso and the groin; nothing they wear is listed twice."""
    people = canon.all("actor") + canon.all("pc")
    assert len(people) == 13
    for rec in people:
        looks = rec.appearance.looks
        assert looks is not None, rec.id
        assert looks.eye_colour and "skin" in looks.complexion, rec.id
        covered = set()
        for piece in looks.outfit:
            item = canon.get(piece.item)
            assert item.kind == "clothing" and item.clothing is not None, (rec.id, piece.item)
            covered |= set(item.clothing.covers)
        assert {"torso", "groin"} <= covered, rec.id
        for g in rec.starting_inventory:
            assert not (g.slot == "worn" and canon.get(g.item).clothing is not None), (rec.id, g.item)


def test_every_core_clothing_item_says_how_it_is_worn(canon):
    """LOOK-02: kind 'clothing' <=> a clothing block (CNT-12); a piece has at least one place it
    covers and words that read without an article problem."""
    items = canon.all("item")
    assert [i.id for i in items if (i.kind == "clothing") != (i.clothing is not None)] == []
    wear = [i for i in items if i.clothing is not None]
    assert len(wear) >= 40
    assert {i.clothing.slot for i in wear} >= {"head", "face", "torso", "body", "legs", "feet"}
    assert any(i.clothing.conceals for i in wear), "a long coat hides what is on the belt"
    assert {s for i in wear for s in i.clothing.style} >= {"work", "casual", "formal", "uniform", "tactical", "medical"}


# --------------------------------------------------------------------------- CNT-12 / CNT-17
def _make_pack(tmp, pack_id, files):
    root = tmp / pack_id
    root.mkdir(parents=True)
    manifest = {"schema": "as.pack.v1", "id": pack_id, "name": f"Test pack {pack_id}", "version": "1.0.0",
                "description": "Built by a contract test.", "depends_on": ["core"]}
    (root / "pack.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    for rel, obj in files.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(yaml.safe_dump(obj, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return root


def _person(pid="tester", name="Hal Brenner"):
    d = stub_dossier(pid, StubSpec(name=name, age=40, sex="male", occupation="welder"))
    d.update(id=pid, generation="authored", tags=[])
    return d


def _looks(*items, **over):
    return {"hair_colour": "brown", "hair_length": "short", "eye_colour": "hazel", "complexion": "tanned skin",
            "outfit": [{"item": i} for i in items], **over}


def test_cnt12_clothing_needs_its_block_and_only_clothing_has_one(tmp_path, core_pack_dir):
    base = {"schema": "as.item.v1", "plural": "things", "mass_g": 300, "bulk": 1, "description": "Test item for CNT-12."}
    wear = {"slot": "torso", "covers": ["torso"], "words": "vest"}
    root = _make_pack(tmp_path, "items12c", {"items/x.yaml": [
        dict(base, id="bare_shirt", name="shirt", kind="clothing"),
        dict(base, id="shirt_tool", name="rag", kind="tool", clothing=wear),
        dict(base, id="good_vest", name="vest", kind="clothing", clothing=wear),
    ]})
    canon, issues = load_canon([core_pack_dir, root])
    assert {(i.field, i.message.split(": ", 1)[1].split("'")[1]) for i in issues if i.code == "CNT-12"} == {
        ("clothing", "bare_shirt"), ("clothing", "shirt_tool")}
    assert canon.get("items12c:item/good_vest").clothing.layer == "mid", "the default layer"


def test_cnt17_no_looks_is_a_warning(tmp_path, core_pack_dir):
    root = _make_pack(tmp_path, "plain", {"actors/hal.yaml": _person()})
    _, issues = load_canon([core_pack_dir, root])
    [hit] = [i for i in issues if i.code == "CNT-17"]
    assert (hit.severity, hit.file, hit.field) == ("warning", "actors/hal.yaml", "appearance.looks")
    assert hit.message.startswith("actors/hal.yaml")


def test_cnt17_nobody_is_made_naked_by_accident(tmp_path, core_pack_dir):
    top_only = _person("top_only", "Ned Top")
    top_only["appearance"]["looks"] = _looks("core:item/t_shirt", "core:item/boots")
    nothing = _person("no_clothes", "Abe Bare")
    nothing["appearance"]["looks"] = _looks()
    dressed = _person("dressed", "Cal Dressed")
    dressed["appearance"]["looks"] = _looks("core:item/t_shirt", "core:item/jeans")
    root = _make_pack(tmp_path, "bare", {"actors/top.yaml": top_only, "actors/none.yaml": nothing,
                                         "actors/dressed.yaml": dressed})
    canon, issues = load_canon([core_pack_dir, root])
    hits = {i.file: i for i in issues if i.code == "CNT-17"}
    assert set(hits) == {"actors/top.yaml", "actors/none.yaml"}
    assert all((i.severity, i.field) == ("error", "appearance.looks.outfit") for i in hits.values())
    assert "groin" in hits["actors/top.yaml"].message and "torso" not in hits["actors/top.yaml"].message
    assert "groin" in hits["actors/none.yaml"].message and "torso" in hits["actors/none.yaml"].message
    assert canon.get("bare:actor/dressed").appearance.looks.outfit[1].item == "core:item/jeans"


def test_cnt17_an_outfit_is_clothing_and_worn_clothing_is_listed_once(tmp_path, core_pack_dir):
    torch = _person("torch", "Kit Torch")
    torch["appearance"]["looks"] = _looks("core:item/t_shirt", "core:item/jeans", "core:item/flashlight")
    twice = _person("twice", "Bo Twice")
    twice["appearance"]["looks"] = _looks("core:item/t_shirt", "core:item/jeans")
    twice["starting_inventory"] = [{"item": "core:item/crowbar", "slot": "worn"},
                                   {"item": "core:item/boots", "slot": "worn"},
                                   {"item": "core:item/windbreaker", "slot": "pack"}]
    typo = _person("typo", "Di Typo")
    typo["appearance"]["looks"] = _looks("core:item/t_shirt", "core:item/jeans", "core:item/jeanz")
    root = _make_pack(tmp_path, "wrong", {"actors/torch.yaml": torch, "actors/twice.yaml": twice,
                                          "actors/typo.yaml": typo})
    _, issues = load_canon([core_pack_dir, root])
    got = sorted((i.file, i.code, i.field, i.severity) for i in issues if i.code in ("CNT-04", "CNT-17"))
    assert got == [("actors/torch.yaml", "CNT-17", "appearance.looks.outfit[2]", "error"),
                   ("actors/twice.yaml", "CNT-17", "starting_inventory[1]", "error"),
                   ("actors/typo.yaml", "CNT-04", "appearance.looks.outfit[2].item", "error")], \
        "a crowbar on the belt and a jacket in the pack are fine; a ref that does not resolve is CNT-04's"


# --------------------------------------------------------------------------- LOOK-01 / LOOK-04 bodies
def test_looks_are_written_without_the_outfit(hall):
    w = hall()
    row = w.store.query_one("SELECT looks FROM bodies WHERE body_id = ?", (w.id("vic"),))[0]
    want = {**Looks.model_validate(VIC_LOOKS).model_dump(mode="json"), "outfit": []}
    assert json.loads(row) == want and row == canonical_json(want)
    assert bodies.looks_of(w.store, w.id("vic")) == Looks.model_validate({**VIC_LOOKS, "outfit": []})
    mara = w.canon.get("core:actor/mara_voss").appearance.looks
    assert bodies.looks_of(w.store, w.id("mara")) == mara.model_copy(update={"outfit": []})
    assert bodies.looks_of(w.store, w.id("dale")) is None, "never recorded: height and build only"
    assert w.store.query_one("SELECT looks FROM bodies WHERE body_id = ?", (w.id("dale"),))[0] is None


def test_create_writes_looks_and_the_dead_start_filthy(hall):
    w = hall()
    looks = Looks.model_validate(VIC_LOOKS)
    with w.store.transaction() as tx:
        man = bodies.create(tx, kind="human", sex="male", age_years=40, height_cm=180, mass_kg=80,
                            special={k: 5 for k in "SPECIAL"}, at=now(w), turn_index=0, origin="materialize",
                            looks=looks)
        dead = bodies.create(tx, kind="infected", sex=None, age_years=None, height_cm=170, mass_kg=65,
                             special={k: 5 for k in "SPECIAL"}, at=now(w), turn_index=0, origin="materialize")
    assert bodies.looks_of(w.store, man) == looks.model_copy(update={"outfit": []})
    assert w.store.query("SELECT 1 FROM items WHERE holder_body = ?", (man,)) == [], "create dresses nobody"
    assert bodies.condition_of(w.store, man) == bodies.BodyCondition(0, 0, 0, 0, now(w)), "(F1c) a new body starts clean, now"
    assert bodies.looks_of(w.store, dead) is None
    assert bodies.condition_of(w.store, dead) == bodies.BodyCondition(grime=5, blood=3, gore=5, wet=0, washed_at=now(w))


def condition(w, local):
    c = bodies.condition_of(w.store, w.id(local))
    return (c.grime, c.blood, c.gore, c.wet)


def test_a_scenario_s_dead_start_filthy_too(scenario):
    """LOOK-04: every infected body, however it came to be, is filthy and caked in gore."""
    w = scenario("two_skills")
    assert condition(w, "shambler") == (5, 3, 5, 0)
    assert condition(w, "pc") == (0, 0, 0, 0)


def test_soil_clamps_and_says_what_changed(hall):
    w = hall()
    vic, t = w.id("vic"), now(w)
    with w.store.transaction() as tx:
        ev = bodies.soil(tx, vic, grime=2, wet=9, source="rain", at=t, cause_event_id=None, turn_index=0)
        same = bodies.soil(tx, vic, wet=1, source="rain", at=t, cause_event_id=None, turn_index=0)
        nothing = bodies.soil(tx, vic, source="rain", at=t, cause_event_id=None, turn_index=0)
        down = bodies.soil(tx, vic, grime=-10, gore=4, source="smeared", at=t + 1000, cause_event_id=ev.event_id,
                           turn_index=0)
    assert (ev.type, ev.writer, ev.actor_id, EVENT_CLASS[ev.type]) == (EventType.BODY_CONDITION, "physical.bodies", vic,
                                                                        EventClass.BODY)
    assert ev.payload == {"body_id": vic, "grime": 2, "blood": 0, "gore": 0, "wet": 3, "source": "rain"}
    assert same is None and nothing is None, "wet is already at its top; nothing changes, no event"
    assert down.payload == {"body_id": vic, "grime": 0, "blood": 0, "gore": 4, "wet": 3, "source": "smeared"}
    assert down.cause_event_id == ev.event_id
    assert bodies.condition_of(w.store, vic) == bodies.BodyCondition(grime=0, blood=0, gore=4, wet=3, washed_at=t), \
        "soil never washes: washed_at stays when the scenario began (F1c)"


# --------------------------------------------------------------------------- LOOK-02 clothes
def test_dressing_puts_the_outfit_on_after_every_fixture_item(hall):
    """The loader dresses each body given dress: true, in body order, after every fixture item:
    every fixture id is the same as in the same world undressed."""
    def undressed(spec):
        for b in spec["bodies"]:
            b.pop("dress", None)
            b.pop("looks", None)
    w, plain = hall(), hall(undressed)
    assert w.ids == plain.ids
    assert worn_refs(w, "pc") == ["core:item/work_jacket", "core:item/t_shirt", "core:item/jeans", "core:item/boots"]
    assert worn_refs(plain, "pc") == []
    fixture_items = {r[0] for r in plain.store.query("SELECT item_id FROM items")}
    outfit = [r[0] for r in w.store.query("SELECT item_id FROM items ORDER BY item_id")
              if r[0] not in fixture_items]
    assert len(outfit) == 4 + 4 + 4, "Owen, Mara and Vic; Dale was not asked to dress"
    owners = [w.local(w.store.query_one("SELECT holder_body FROM items WHERE item_id = ?", (i,))[0]) for i in outfit]
    assert owners == ["pc"] * 4 + ["mara"] * 4 + ["vic"] * 4
    assert {r[0] for r in w.store.query("SELECT origin FROM items WHERE item_id IN (%s)" % ",".join("?" * 12),
                                        tuple(outfit))} == {"scenario"}


def test_what_is_worn_reads_outside_in(hall):
    """worn(): clothing by slot, then layer (outer first), then the gear worn without a clothing
    block; colour, state and insignia as the outfit set them."""
    w = hall()
    got = [(r["def_ref"], r["colour"], r["state"], r["insignia"]) for r in objects.worn(w.store, w.id("vic"))]
    assert got == [("core:item/parka", "olive", "worn", None),
                   ("core:item/t_shirt", "black", "worn", "a feed store logo"),
                   ("core:item/cargo_pants", "khaki", "worn", None),
                   ("core:item/boots", "brown", "soiled", None),
                   ("core:item/glock_19", "", "worn", None)]
    first = objects.worn(w.store, w.id("vic"))[0]
    assert first["name"] == "parka"
    assert first["clothing"] == w.canon.get("core:item/parka").clothing.model_dump(mode="json")
    assert objects.worn(w.store, w.id("vic"))[-1]["clothing"] is None
    assert objects.coverage(w.store, w.id("vic")) == {"torso", "arms", "groin", "legs", "feet"}
    assert objects.coverage(w.store, w.id("dale")) == set()


def test_a_body_already_in_clothes_is_not_dressed_again(hall):
    def own_coat(spec):
        body_spec(spec, "vic")["inventory"].append({"item": "core:item/windbreaker", "slot": "worn"})
    w = hall(own_coat)
    assert worn_refs(w, "vic") == ["core:item/windbreaker", "core:item/glock_19"]
    assert bodies.looks_of(w.store, w.id("vic")).hair_length == "bald", "the looks are still his"


def test_dress_needs_something_to_dress_in(fixture_packs, core_pack_dir):
    spec = copy.deepcopy(HALL)
    body_spec(spec, "vic").pop("looks")
    with pytest.raises(ValueError):
        load_scenario(spec, packs_root=fixture_packs, core_pack_dir=core_pack_dir)


def test_looks_without_dress_leave_a_body_with_nothing_on(hall):
    def bare(spec):
        body_spec(spec, "vic").pop("dress")
    w = hall(bare)
    assert bodies.looks_of(w.store, w.id("vic")).facial_hair == "full_beard"
    assert worn_refs(w, "vic") == ["core:item/glock_19"] and objects.coverage(w.store, w.id("vic")) == set()


def test_what_anyone_can_see_they_carry(hall):
    """visible_gear: hands first, then worn gear; a handgun under a long parka is hidden until the
    parka comes off; pockets are never seen."""
    w = hall()
    assert objects.visible_gear(w.store, w.id("pc")) == [w.id("axe")]
    assert objects.visible_gear(w.store, w.id("mara")) == [w.id("revolver")], "a work jacket hides nothing"
    assert objects.visible_gear(w.store, w.id("dale")) == [w.id("pipe"), w.id("bar")]
    assert objects.visible_gear(w.store, w.id("vic")) == []
    with w.store.transaction() as tx:
        objects.transfer(tx, item_of(w, "vic", "core:item/parka"), objects.Holder("place", w.id("hall"), anchor_id=w.id("table")),
                         None, now(w), w.id("vic"), None, 0)
    assert objects.visible_gear(w.store, w.id("vic")) == [w.id("pistol")]
    assert objects.coverage(w.store, w.id("vic")) == {"torso", "groin", "legs", "feet"}
