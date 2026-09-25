"""Washing, the dead's gore, clothes, and what people cannot stand to be near (P5, the owner's F1c:
DECISIONS D-86). action/effects.py wash / smear / take_off / change_into / strip and the soiling in
strike_melee, treat_wound and butcher; physical/bodies.py wash (LOOK-07); mind/temper.py TEMPER-09.

The owner: covered in zombie juices to trick a horde, "I'm going to smell like hell, look like hell.
And people aren't gonna want to be around me for very long till I shower"; and walking around naked
"there should be consequences for one, and two, that should be an issue for most people. Like 'What
the fuck?'".

A wash house (a dict scenario): Ada with a knife, a jug and a bottle of water and a spare top; Joe
out cold on the floor; Mia, Ada's ten-year-old; Lou, awake; Nan, who has nothing on; one of the dead
by the wall, and a dog.
"""

from __future__ import annotations

import copy
import json

import pytest

import helpers
from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception, temper
from as_engine.physical import bodies, objects
from as_engine.physical.bodies import WoundSpec
from as_engine.physical.objects import Holder
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(5)

MIN = 60_000

LIGHT = [{"item": "core:item/t_shirt"}, {"item": "core:item/jeans"}, {"item": "core:item/sneakers"}]
WARM = [{"item": "core:item/parka"}, {"item": "core:item/thermal_top"}, {"item": "core:item/cargo_pants"},
        {"item": "core:item/combat_boots"}]
KID = [{"item": "core:item/fleece_jacket"}, {"item": "core:item/t_shirt"}, {"item": "core:item/leggings"},
       {"item": "core:item/sneakers"}]


def looks(outfit):
    return {"hair_colour": "brown", "hair_length": "short", "eye_colour": "grey", "complexion": "pale skin",
            "outfit": outfit}


HOUSE = {
    "schema": "as.scenario.v1", "name": "wash_house", "seed": 77, "start": {"day": 400, "time": "10:00"},
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
         "looks": looks(WARM), "dress": True, "awareness": "unconscious", "posture": "lying",
         "wounds": [{"anatomy": "arm_l", "type": "cut", "severity": "significant"},
                    {"anatomy": "hand_l", "type": "cut", "severity": "minor"}]},
        {"id": "mia", "stub": {"name": "Mia Pike", "age": 10, "sex": "female"}, "place": "house", "x": 2, "y": 4,
         "looks": looks(KID), "dress": True,
         "inventory": [{"item": "core:item/athletic_top", "slot": "pack", "label": "top"}]},
        {"id": "lou", "stub": {"name": "Lou Carr", "age": 33, "sex": "male"}, "place": "house", "x": 4, "y": 3},
        {"id": "nan", "stub": {"name": "Nan Ortiz", "age": 29, "sex": "female"}, "place": "house", "x": 6, "y": 3,
         "looks": looks(LIGHT)},
        {"id": "dead", "infected": "ZOMBIE_ARCHETYPE_SHAMBLER01", "controller": "policy", "place": "house", "x": 2.5, "y": 2},
        {"id": "dog", "animal": "core:animal/dog", "place": "house", "x": 1.5, "y": 3},
    ],
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


def commit(w, ev):
    with w.store.transaction() as tx:
        return tx.commit_event(ev)


def cause(w, at=None):
    return commit(w, Event(type=EventType.OVERRIDE, writer="audit", at=now(w) if at is None else at, turn_index=0,
                           payload={"what": "test"}))


def kill(w, local, anatomy="head"):
    c = cause(w)
    with w.store.transaction() as tx:
        bodies.apply_harm(tx, w.id(local), WoundSpec(anatomy, "blunt", "catastrophic", 0), now(w), c.event_id, 0, w.rng)
    assert not w.store.query_one("SELECT alive FROM bodies WHERE body_id = ?", (w.id(local),))[0]


def soil(w, local, **kw):
    with w.store.transaction() as tx:
        bodies.soil(tx, w.id(local), source="test", at=now(w), cause_event_id=None, turn_index=0, **kw)


def cond(w, local):
    c = bodies.condition_of(w.store, w.id(local))
    return (c.grime, c.blood, c.gore, c.wet)


def run(w, intent, rng=None):
    t = now(w)
    with w.store.transaction() as tx:
        return resolve_wave(tx, rng or helpers.ScriptedRng(), barrier(tx, [intent]), t, 0, horizon_ms=t + 30 * MIN)


def of(evs, type_):
    return [e for e in evs if e.type == type_]


def result(evs):
    (end,) = of(evs, "ACTION_COMPLETE")
    return end.payload["result"]


def item(w, local_holder, def_ref, slot=None):
    rows = w.store.query("SELECT item_id, holder_slot FROM items WHERE holder_body = ? AND def_ref = ? ORDER BY item_id",
                         (w.id(local_holder), def_ref))
    return [r[0] for r in rows if slot is None or r[1] == slot][0]


def where(w, item_id):
    r = w.store.query_one("SELECT holder_body, holder_slot FROM items WHERE item_id = ?", (item_id,))
    return None if r is None else (r[0], r[1])


def conditions(w, local):
    return [json.loads(r[0]) for r in w.store.query(
        "SELECT payload FROM events WHERE type = 'BODY_CONDITION' AND json_extract(payload, '$.body_id') = ? ORDER BY seq",
        (w.id(local),))]


# --------------------------------------------------------------------------- wash
def test_a_jug_of_water_washes_you_clean(house):
    """wash: five litres is a real wash — everything off, a little wet, and washed_at is now; the
    water is gone (nobody drinks it)."""
    w = house()
    soil(w, "ada", grime=4, blood=3, gore=5)
    jug = w.id("jug")
    evs = run(w, helpers.make_intent(w, "ada", "wash_self", item="jug"))
    assert result(evs) == "washed"
    assert cond(w, "ada") == (0, 0, 0, 1)
    assert conditions(w, "ada")[-1]["source"] == "washed"
    (end,) = of(evs, "ACTION_COMPLETE")
    assert bodies.condition_of(w.store, w.id("ada")).washed_at == end.at
    assert w.store.query_one("SELECT qty FROM items WHERE item_id = ?", (jug,)) is None


def test_a_bottle_only_wipes_the_worst_off(house):
    w = house()
    soil(w, "ada", grime=4, blood=3, gore=5)
    evs = run(w, helpers.make_intent(w, "ada", "wash_self", item="bottle"))
    assert result(evs) == "wiped"
    assert cond(w, "ada") == (3, 1, 3, 1), "grime -1, blood -2, gore -2, wet +1"
    assert bodies.condition_of(w.store, w.id("ada")).washed_at < of(evs, "ACTION_COMPLETE")[0].at, "a wipe is not a wash"


def test_fouled_water_gets_in_your_eyes_and_mouth(house):
    """Washing in water a host or the dead fouled is their fluids all over you (D-77) — the
    'fluid_contact' exposure; water only you spat in is only yours."""
    w = house()
    with w.store.transaction() as tx:
        objects.contaminate(tx, w.id("jug"), "wet", w.id("dead"), now(w), None, 0, lasting=True)
    evs = run(w, helpers.make_intent(w, "ada", "wash_self", item="jug"), rng=helpers.ScriptedRng(False))
    (exp,) = of(evs, "INFECTION_EXPOSURE")
    assert (exp.payload["body_id"], exp.payload["exposure"]) == (w.id("ada"), "fluid_contact")
    w2 = house()
    with w2.store.transaction() as tx:
        objects.contaminate(tx, w2.id("bottle"), "wet", w2.id("ada"), now(w2), None, 0)
    evs = run(w2, helpers.make_intent(w2, "ada", "wash_self", item="bottle"))
    assert not of(evs, "INFECTION_EXPOSURE")


# --------------------------------------------------------------------------- smear
def test_smeared_with_the_dead(house):
    """smear: enough of them to walk among them (gore 4, INF-14), some blood and dirt with it — and
    the strain: on whole skin it is the eyes and mouth ('gore_smear')."""
    w = house()
    kill(w, "dead")
    evs = run(w, helpers.make_intent(w, "ada", "smear_gore", target="dead"), rng=helpers.ScriptedRng(False))
    assert result(evs) == "smeared"
    assert cond(w, "ada") == (1, 1, 4, 0)
    (c,) = of(evs, "BODY_CONDITION")
    assert c.payload["source"] == "smeared"
    (exp,) = of(evs, "INFECTION_EXPOSURE")
    assert (exp.payload["exposure"], exp.cause_event_id) == ("gore_smear", c.event_id)


def test_into_an_open_wound_is_worse(house):
    """An unhealed wound without a bandage lets it in ('gore_in_wound'); a bandaged one does not."""
    w = house(lambda s: [b.update(wounds=[{"anatomy": "hand_r", "type": "cut", "severity": "minor"}])
                         for b in s["bodies"] if b["id"] == "ada"])
    kill(w, "dead")
    evs = run(w, helpers.make_intent(w, "ada", "smear_gore", target="dead"), rng=helpers.ScriptedRng(False))
    assert of(evs, "INFECTION_EXPOSURE")[0].payload["exposure"] == "gore_in_wound"
    w2 = house(lambda s: [b.update(wounds=[{"anatomy": "hand_r", "type": "cut", "severity": "minor", "treated": ["bandage"]}])
                          for b in s["bodies"] if b["id"] == "ada"])
    kill(w2, "dead")
    evs = run(w2, helpers.make_intent(w2, "ada", "smear_gore", target="dead"), rng=helpers.ScriptedRng(False))
    assert of(evs, "INFECTION_EXPOSURE")[0].payload["exposure"] == "gore_smear"


def test_nobody_smears_themselves_with_one_still_on_its_feet(house):
    w = house()
    evs = run(w, helpers.make_intent(w, "ada", "smear_gore", target="dead"))
    assert result(evs) == "nothing_to_smear" and cond(w, "ada") == (0, 0, 0, 0)


# --------------------------------------------------------------------------- clothes
def test_take_off_goes_to_a_free_hand_then_the_pack(house):
    w = house()
    shoes = item(w, "ada", "core:item/sneakers")
    evs = run(w, helpers.make_intent(w, "ada", "take_off_clothing", item=shoes))
    assert result(evs) == "took_off" and where(w, shoes) == (w.id("ada"), "hand_l")
    jeans = item(w, "ada", "core:item/jeans")
    evs = run(w, helpers.make_intent(w, "ada", "take_off_clothing", item=jeans))
    assert result(evs) == "took_off" and where(w, jeans) == (w.id("ada"), "pack"), "both hands full: into the pack"
    assert "groin" not in objects.coverage(w.store, w.id("ada")), "an adult may strip to nothing"


def test_changing_is_one_move_never_bare_between(house):
    """change_into: what is worn at the same slot and layer comes off to where the new piece was, in
    the same action."""
    w = house()
    shirt = item(w, "ada", "core:item/t_shirt")
    evs = run(w, helpers.make_intent(w, "ada", "change_into", item="thermal"))
    assert result(evs) == "changed"
    assert where(w, w.id("thermal")) == (w.id("ada"), "worn") and where(w, shirt) == (w.id("ada"), "pack")
    assert {"torso", "groin"} <= objects.coverage(w.store, w.id("ada"))


def test_nobody_under_18_is_ever_left_bare(house):
    """CNT-11 in the world: a child can take off a jacket or change a top, never what leaves the
    torso or the groin uncovered."""
    w = house()
    mia = w.id("mia")
    fleece = item(w, "mia", "core:item/fleece_jacket")
    assert result(run(w, helpers.make_intent(w, "mia", "take_off_clothing", item=fleece))) == "took_off", \
        "the shirt under it still covers her"
    shirt = item(w, "mia", "core:item/t_shirt")
    assert result(run(w, helpers.make_intent(w, "mia", "take_off_clothing", item=shirt))) == "kept_on"
    assert where(w, shirt) == (mia, "worn")
    legs = item(w, "mia", "core:item/leggings")
    assert result(run(w, helpers.make_intent(w, "mia", "take_off_clothing", item=legs))) == "kept_on"
    assert result(run(w, helpers.make_intent(w, "mia", "change_into", item="top"))) == "changed"
    assert {"torso", "groin"} <= objects.coverage(w.store, mia)


def test_clothes_off_someone_who_cannot_stop_you(house):
    """strip: off an adult who is out cold (or dead), into your hand."""
    w = house(lambda s: [b.update(inventory=[]) for b in s["bodies"] if b["id"] == "ada"])
    parka = item(w, "joe", "core:item/parka")
    evs = run(w, helpers.make_intent(w, "ada", "strip_clothing", target="joe", item=parka))
    assert result(evs) == "stripped" and where(w, parka) == (w.id("ada"), "hand_r")


def test_never_off_a_child_nor_off_someone_awake(house):
    w = house(lambda s: [b.update(awareness="unconscious", posture="lying") for b in s["bodies"] if b["id"] == "mia"])
    fleece = item(w, "mia", "core:item/fleece_jacket")
    assert result(run(w, helpers.make_intent(w, "ada", "strip_clothing", target="mia", item=fleece))) == "kept_on"
    assert where(w, fleece) == (w.id("mia"), "worn")
    w2 = house(lambda s: [b.update(awareness="awake", posture="standing") for b in s["bodies"] if b["id"] == "joe"])
    boots = item(w2, "joe", "core:item/combat_boots")
    assert result(run(w2, helpers.make_intent(w2, "ada", "strip_clothing", target="joe", item=boots))) == "kept_on"
    assert where(w2, boots) == (w2.id("joe"), "worn")


# --------------------------------------------------------------------------- who gets bloodied (LOOK-07)
def test_a_blow_that_opens_them_splashes_you(house):
    """strike_melee: a wound of significant or worse gets their blood on you — the dead's fluids are
    gore."""
    w = house()
    evs = run(w, helpers.make_intent(w, "ada", "strike_melee", target="lou", item="knife"), rng=helpers.ScriptedRng(1, 10, 0))
    assert of(evs, "HARM")[0].payload["severity"] == "significant"
    assert cond(w, "ada") == (0, 1, 0, 0) and conditions(w, "ada")[-1]["source"] == "splashed"
    w2 = house()
    run(w2, helpers.make_intent(w2, "ada", "strike_melee", target="dead", item="knife"), rng=helpers.ScriptedRng(1, 10, 0, False))
    assert cond(w2, "ada") == (0, 0, 1, 0)
    w3 = house()
    run(w3, helpers.make_intent(w3, "ada", "strike_melee", target="lou", item="knife"), rng=helpers.ScriptedRng(1, 3, 0))
    assert cond(w3, "ada") == (0, 0, 0, 0), "a nick splashes nothing"


def test_stopping_the_bleeding_is_bloody_work(house):
    w = house(lambda s: [b.update(inventory=[]) for b in s["bodies"] if b["id"] == "ada"])
    deep, nick = [r[0] for r in w.store.query("SELECT wound_id FROM wounds WHERE body_id = ? ORDER BY severity DESC",
                                              (w.id("joe"),))]
    run(w, helpers.make_intent(w, "ada", "apply_pressure", target=deep))
    assert cond(w, "ada") == (0, 1, 0, 0) and conditions(w, "ada")[-1]["source"] == "treated"
    run(w, helpers.make_intent(w, "ada", "apply_pressure", target=nick))
    assert cond(w, "ada") == (0, 1, 0, 0), "a nick is not bloody work"


def test_butchering_is_bloody_work(house):
    w = house()
    kill(w, "dog", "neck")
    evs = run(w, helpers.make_intent(w, "ada", "butcher_carcass", target="dog"))
    assert result(evs) == "butchered"
    assert cond(w, "ada") == (0, 2, 0, 0) and conditions(w, "ada")[-1]["source"] == "butchered"


# --------------------------------------------------------------------------- TEMPER-09
def take_in(w, holder, at, rng=None):
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(holder), at, 0)
        return temper.take_in(tx, rng or w.rng, w.id(holder), 0, at)


def tempers(w, holder, kind):
    return [json.loads(r[0]) for r in w.store.query(
        "SELECT payload FROM events WHERE type = 'TEMPER_CHANGE' AND actor_id = ? AND json_extract(payload, '$.kind') = ? "
        "ORDER BY seq", (w.id(holder), kind))]


def test_the_reek_of_the_dead_grates(house):
    """reeked: close enough to smell the dead on you plainly — heat toward you, and again every ten
    minutes you stay; not once more in the same breath."""
    w = house()
    soil(w, "ada", gore=4)
    t = now(w)
    take_in(w, "lou", t)
    (first,) = tempers(w, "lou", "reeked")
    assert (first["toward_id"], first["heat"], first["event_id"]) == (w.id("ada"), 1, None)
    take_in(w, "lou", t + 5 * MIN)
    assert len(tempers(w, "lou", "reeked")) == 1
    take_in(w, "lou", t + 10 * MIN + 1)
    assert [x["heat"] for x in tempers(w, "lou", "reeked")] == [1, 2]
    assert temper.heat(w.store, w.id("lou"), w.id("ada"), t + 10 * MIN + 1) == 2


def test_only_the_reek_of_the_dead_and_only_on_a_living_person(house):
    """Sweat and dirt are everyone's; the dead themselves are not a person to be angry with."""
    w = house()
    soil(w, "ada", grime=5, blood=4)
    take_in(w, "lou", now(w))
    assert tempers(w, "lou", "reeked") == []


def test_stay_next_to_it_long_enough_and_it_boils_over(house):
    """The reek builds heat faster than it fades: fifty minutes of it and Lou (a fuse of 3) snaps."""
    w = house()
    soil(w, "ada", gore=5)
    t = now(w)
    outs = [take_in(w, "lou", t + k * 10 * MIN + 1, rng=helpers.ScriptedRng(False)) for k in range(6)]
    assert outs[:5] == [None] * 5
    assert outs[5] is not None and outs[5].toward_id == w.id("ada")


def test_a_naked_adult_in_plain_sight(house):
    """bared: 'What the fuck?' — a shock (strain +1) and heat toward them; again every half hour they
    stay like that in sight."""
    w = house()
    t = now(w)
    s0 = w.store.query_one("SELECT stress FROM actors WHERE actor_id = ?", (w.id("lou"),))[0]
    take_in(w, "lou", t)
    (b,) = tempers(w, "lou", "bared")
    assert (b["toward_id"], b["heat"]) == (w.id("nan"), 2)
    assert w.store.query_one("SELECT stress FROM actors WHERE actor_id = ?", (w.id("lou"),))[0] == s0 + 1
    take_in(w, "lou", t + 20 * MIN)
    assert len(tempers(w, "lou", "bared")) == 1
    take_in(w, "lou", t + 30 * MIN + 1)
    assert len(tempers(w, "lou", "bared")) == 2


def test_bare_to_the_waist_is_not_naked(house):
    w = house(lambda s: [b.update(looks=looks([{"item": "core:item/jeans"}]), dress=True) for b in s["bodies"] if b["id"] == "nan"])
    take_in(w, "lou", now(w))
    assert tempers(w, "lou", "bared") == []


def test_the_player_feels_it_and_keeps_their_hand(house):
    """The PC is provoked like anyone (its anger is real and on record) but never made to snap."""
    w = house(lambda s: [b.update(x=5.5, y=3) for b in s["bodies"] if b["id"] == "pc"])
    assert take_in(w, "pc", now(w)) is None
    assert [x["toward_id"] for x in tempers(w, "pc", "bared")] == [w.id("nan")]
