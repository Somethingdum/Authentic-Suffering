"""What someone looks like to the person looking (P3, the owner's F1a). Rules LOOK-03, LOOK-05
(mind/perception.py appearance_text; mind/cues.py appearance_cues).

"Never judge a book by its cover" is a lie in this world: hair, clothes, a badge, a holstered gun,
blood and filth all read at a glance, and they read differently up close, across a room, and in
poor light. A body whose looks were never recorded makes no claim about its clothes.

The world here is a clinic waiting room (a dict scenario) with one person of each kind: Mara
dressed from her dossier with her revolver on her hip, Vic in a long parka over a holstered
pistol, Nell in nothing but boots, Hank bare to the waist, Ines in a skirt suit over a hidden
turtleneck, Cole in a sheriff's tactical vest, Dale (looks never recorded) with a pipe in his hand
and a crowbar on his belt, and one of the dead.
"""

from __future__ import annotations

import copy

import pytest

from as_engine.mind import cues, perception
from as_engine.physical import bodies, objects
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(3)


def looks(hair_colour, hair_length, eye_colour, complexion, *outfit, **more):
    return {"hair_colour": hair_colour, "hair_length": hair_length, "eye_colour": eye_colour,
            "complexion": complexion, "outfit": list(outfit), **more}


def piece(ref, **props):
    return {"item": f"core:item/{ref}", **props}


def stub(local, name, sex, x, lk, inventory=()):
    return {"id": local, "stub": {"name": name, "age": 40, "sex": sex}, "place": "room", "x": x, "y": 3,
            "dress": True, "looks": lk, "inventory": list(inventory)}


ROOM = {
    "schema": "as.scenario.v1", "name": "waiting_room", "seed": 21, "start": {"day": 300, "time": "10:00"},
    "places": [{"id": "room", "name": "Clinic waiting room", "material": "drywall", "light": 3, "width_m": 30,
                "depth_m": 6}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "room", "x": 1, "y": 1},
        {"id": "mara", "dossier": "core:actor/mara_voss", "place": "room", "x": 3, "y": 3, "dress": True,
         "inventory": [{"item": "core:item/revolver_38", "slot": "worn", "label": "revolver"},
                       {"item": "core:item/flashlight", "slot": "pocket"}]},
        stub("vic", "Vic Lamb", "male", 6,
             looks("", "bald", "brown", "ruddy skin", piece("parka"),
                   piece("t_shirt", colour="black", insignia="a feed store logo"), piece("cargo_pants"),
                   piece("boots", state="soiled"), facial_hair="full_beard",
                   marks=[{"what": "a faded anchor tattoo", "where": "on the left forearm", "shows": "near"}]),
             [{"item": "core:item/glock_19", "slot": "worn", "label": "pistol"}]),
        stub("nell", "Nell Hart", "female", 9,
             looks("red", "long", "green", "freckled skin", piece("boots"), hair_style="in a ponytail")),
        stub("hank", "Hank Moss", "male", 12,
             looks("gray", "short", "blue", "sunburned skin", piece("jeans", state="torn"), piece("boots"),
                   facial_hair="stubble")),
        stub("ines", "Ines Soto", "female", 15,
             looks("black", "collar", "dark brown", "olive skin", piece("turtleneck"), piece("skirt_suit"),
                   piece("pumps"), hair_style="swept back")),
        stub("cole", "Cole Brandt", "male", 18,
             looks("brown", "cropped", "gray", "weathered skin",
                   piece("tactical_vest", insignia="SHERIFF printed in white across the chest"),
                   piece("uniform_shirt"), piece("cargo_pants", colour="black"), piece("combat_boots"),
                   facial_hair="mustache")),
        {"id": "dale", "dossier": "core:actor/dale_pruitt", "place": "room", "x": 21, "y": 3,
         "inventory": [{"item": "core:item/steel_pipe", "slot": "hand_r"}, {"item": "core:item/crowbar", "slot": "worn"}]},
        {"id": "dead", "infected": "ZOMBIE_ARCHETYPE_SHAMBLER01", "controller": "policy", "place": "room", "x": 27,
         "y": 5},
    ],
}


@pytest.fixture
def room(fixture_packs, core_pack_dir):
    worlds = []

    def _load(change=None):
        spec = copy.deepcopy(ROOM)
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


def seen(w, local, level="clear", d=3.0):
    with w.store.transaction() as tx:
        return perception.appearance_text(tx, w.id("pc"), w.id(local), level, d)


def glance(w, local, level="clear", d=3.0):
    with w.store.transaction() as tx:
        return cues.appearance_cues(tx, w.id("pc"), w.id(local), level, d)


def soil(w, local, **amounts):
    with w.store.transaction() as tx:
        bodies.soil(tx, w.id(local), source="smeared", at=now(w), cause_event_id=None, turn_index=0, **amounts)


MARA_HAIR = "Shoulder-length dark blonde hair in a tight low bun"
MARA_SKIN = "pale skin freckled across the nose and windburned on the cheeks"
MARA_CLOTHES = "in a navy work jacket, black cargo pants and brown work boots"


# --------------------------------------------------------------------------- distance and light
@pytest.mark.parametrize("d, text", [
    (1.0, f"{MARA_HAIR}, {MARA_SKIN}, a pale crescent scar through the left eyebrow, a hard callus on the inside of "
          f"the right index finger, gray eyes; {MARA_CLOTHES}; carrying a .38 revolver."),
    (1.5, f"{MARA_HAIR}, {MARA_SKIN}, a pale crescent scar through the left eyebrow, a hard callus on the inside of "
          f"the right index finger, gray eyes; {MARA_CLOTHES}; carrying a .38 revolver."),
    (1.6, f"{MARA_HAIR}, {MARA_SKIN}, a pale crescent scar through the left eyebrow; {MARA_CLOTHES}; "
          f"carrying a .38 revolver."),
    (5.0, f"{MARA_HAIR}, {MARA_SKIN}, a pale crescent scar through the left eyebrow; {MARA_CLOTHES}; "
          f"carrying a .38 revolver."),
    (5.1, f"{MARA_HAIR}; {MARA_CLOTHES}; carrying a .38 revolver."),
    (40.0, f"{MARA_HAIR}; {MARA_CLOTHES}; carrying a .38 revolver."),
])
def test_the_closer_you_are_the_more_you_see(room, d, text):
    """LOOK-03: hair and clothes at any distance; skin and near marks within 5 m; close marks and
    eyes within 1.5 m; what is on the belt in plain view. Nothing in a pocket is ever seen."""
    assert seen(room(), "mara", "clear", d) == text


def test_poor_light_shows_the_outline_of_the_clothes_and_nothing_else(room):
    w = room()
    assert seen(w, "mara", "partial", 1.0) == "In a navy work jacket."
    assert seen(w, "mara", "silhouette", 1.0) == "" and seen(w, "mara", "none", 1.0) == ""


def test_a_beard_shows_across_a_room_stubble_does_not(room):
    w = room()
    assert seen(w, "vic", "clear", 1.0) == ("Bald, a full beard, ruddy skin, a faded anchor tattoo on the left forearm, "
                                            "brown eyes; in an olive long parka, khaki cargo pants and soiled brown "
                                            "work boots.")
    assert seen(w, "vic", "clear", 20.0) == "Bald, a full beard; in an olive long parka, khaki cargo pants and soiled brown work boots."
    assert seen(w, "hank", "clear", 5.0) == ("Short gray hair, stubble, sunburned skin; bare to the waist, in torn blue "
                                             "jeans and brown work boots.")
    assert seen(w, "hank", "clear", 8.0) == "Short gray hair; bare to the waist, in torn blue jeans and brown work boots."


# --------------------------------------------------------------------------- clothes
def test_naked_and_half_dressed_read_plainly(room):
    w = room()
    assert seen(w, "nell", "clear", 3.0) == "Long red hair in a ponytail, freckled skin; naked but for brown work boots."
    assert seen(w, "nell", "partial", 3.0) == "Naked."
    assert seen(w, "hank", "partial", 3.0) == "Bare to the waist."


def test_only_the_outer_layer_shows(room):
    """SHOWN: the outermost piece per slot; a one-piece suit hides a shirt of the same layer; an
    insignia shows only on a piece that shows."""
    w = room()
    assert seen(w, "ines", "clear", 3.0) == ("Collar-length black hair swept back, olive skin; in a gray skirt suit and "
                                             "black low-heeled pumps.")
    assert seen(w, "ines", "partial", 3.0) == "In a gray skirt suit."
    assert seen(w, "cole", "clear", 3.0) == ("Cropped brown hair, a mustache, weathered skin; in a black tactical vest, "
                                             "black cargo pants and black combat boots; SHERIFF printed in white across "
                                             "the chest.")
    assert seen(w, "cole", "partial", 3.0) == "In a black tactical vest."


def test_a_coat_off_shows_what_it_hid(room):
    w = room()
    [parka] = [r["item_id"] for r in objects.worn(w.store, w.id("vic")) if r["def_ref"] == "core:item/parka"]
    with w.store.transaction() as tx:
        objects.transfer(tx, parka, objects.Holder("place", w.id("room")), None, now(w), w.id("vic"), None, 0)
    assert seen(w, "vic", "clear", 20.0) == ("Bald, a full beard; in a black T-shirt, khaki cargo pants and soiled brown "
                                             "work boots; a feed store logo; carrying a Glock 19.")


def test_no_looks_on_record_no_claim_about_clothes(room):
    """Dale's looks were never recorded: nobody is told he is naked. What is in his hand is the
    visual percept's to say; the crowbar on his belt is plain to see."""
    w = room()
    assert objects.coverage(w.store, w.id("dale")) == set()
    assert seen(w, "dale", "clear", 3.0) == "Carrying a crowbar."
    assert seen(w, "dale", "partial", 3.0) == ""


# --------------------------------------------------------------------------- what is on them
def test_the_dead_look_like_the_dead(room):
    w = room()
    assert seen(w, "dead", "clear", 3.0) == "Caked in gore, bloodied, filthy."
    assert seen(w, "dead", "partial", 3.0) == "Caked in gore."


@pytest.mark.parametrize("amounts, clear, partial", [
    ({"gore": 1, "blood": 2, "grime": 2, "wet": 1}, "", ""),
    ({"gore": 2, "blood": 3, "grime": 3, "wet": 2}, "smeared with gore, bloodied, grimy, soaked through", ""),
    ({"gore": 3, "blood": 4, "grime": 4, "wet": 3}, "smeared with gore, bloodied, filthy, soaked through", "bloodied"),
    ({"gore": 4, "blood": 5, "grime": 5}, "caked in gore, soaked in blood, filthy", "caked in gore, soaked in blood"),
])
def test_blood_gore_grime_and_rain_show(room, amounts, clear, partial):
    w = room()
    soil(w, "vic", **amounts)
    base = "Bald, a full beard; in an olive long parka, khaki cargo pants and soiled brown work boots"
    assert seen(w, "vic", "clear", 20.0) == base + (f"; {clear}." if clear else ".")
    assert seen(w, "vic", "partial", 20.0) == "In an olive long parka" + (f"; {partial}." if partial else ".")


def test_the_same_look_gives_the_same_words(room):
    w = room()
    soil(w, "cole", blood=3)
    assert seen(w, "cole", "clear", 1.2) == seen(w, "cole", "clear", 1.2)
    assert seen(room(), "cole", "clear", 1.2) != seen(w, "cole", "clear", 1.2)


# --------------------------------------------------------------------------- LOOK-05 cues
@pytest.mark.parametrize("local, clear, partial", [
    ("mara", ["visibly_armed"], []),
    ("vic", [], []),
    ("nell", ["naked"], ["naked"]),
    ("hank", ["half_dressed"], ["half_dressed"]),
    ("ines", ["formally_dressed"], ["formally_dressed"]),
    ("cole", ["uniformed", "wearing_insignia"], ["uniformed"]),
    ("dale", ["visibly_armed"], []),
    ("dead", ["bloodied", "filthy", "gore_covered"], ["gore_covered"]),
])
def test_what_a_glance_tells_you(room, local, clear, partial):
    w = room()
    assert glance(w, local, "clear") == clear
    assert glance(w, local, "partial") == partial
    assert glance(w, local, "silhouette") == [] and glance(w, local, "none") == []


def test_a_glance_at_the_bloodied(room):
    w = room()
    soil(w, "vic", gore=4, blood=5, grime=3, wet=2)
    assert glance(w, "vic", "clear") == ["bloodied", "gore_covered", "soaked"]
    assert glance(w, "vic", "partial") == ["bloodied", "gore_covered"]
    [parka] = [r["item_id"] for r in objects.worn(w.store, w.id("vic")) if r["def_ref"] == "core:item/parka"]
    with w.store.transaction() as tx:
        objects.transfer(tx, parka, objects.Holder("place", w.id("room")), None, now(w), w.id("vic"), None, 0)
    assert glance(w, "vic", "clear") == ["bloodied", "gore_covered", "soaked", "visibly_armed", "wearing_insignia"]


def test_every_appearance_cue_is_in_the_registry(canon):
    assert cues.APPEARANCE_CUES <= {c.id for c in canon.all("cue")}
