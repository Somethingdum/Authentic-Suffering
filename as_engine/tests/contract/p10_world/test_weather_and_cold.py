"""Time, rain and the cold on a person (P10, the owner's F1c: DECISIONS D-86). physical/bodies.py
progress (LOOK-08 grime and weather, LOOK-09 cold_need and chill), the death test's cold.

The owner: walk around naked and "there should be consequences"; smeared in the dead you reek until
you wash. Out here the rain washes it off you whether you like it or not, days without a wash make
anyone grimy, and a night in the open with nothing on can kill.

A farmyard and its shed in a mild country (no world_params: climate_heat 5), from ten in the
morning: Ada in summer clothes and Ben in a parka out in the yard; Cal, who has nothing on, in the
yard; Dot, whose looks were never recorded, in the yard; Eve with nothing on in the shed.
"""

from __future__ import annotations

import copy
import json

import pytest

from as_engine.contracts.dossier import OutfitPiece
from as_engine.contracts.events import EventType
from as_engine.physical import bodies, objects
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(10)

MIN = 60_000
H = 3_600_000
DAY = 24 * H

LIGHT = [{"item": "core:item/t_shirt"}, {"item": "core:item/jeans"}, {"item": "core:item/sneakers"}]
WARM = [{"item": "core:item/parka"}, {"item": "core:item/thermal_top"}, {"item": "core:item/cargo_pants"},
        {"item": "core:item/combat_boots"}]


def looks(outfit):
    return {"hair_colour": "brown", "hair_length": "short", "eye_colour": "grey", "complexion": "pale skin",
            "outfit": outfit}


FARM = {
    "schema": "as.scenario.v1", "name": "farmyard", "seed": 90, "start": {"day": 400, "time": "10:00"},
    "places": [
        {"id": "yard", "name": "Farmyard", "kind": "outdoor", "indoor": False, "material": "open_air",
         "width_m": 30, "depth_m": 20, "light": 3},
        {"id": "shed", "name": "Shed", "width_m": 6, "depth_m": 4},
    ],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "shed", "x": 5, "y": 3},
        {"id": "ada", "stub": {"name": "Ada Pike", "age": 34, "sex": "female"}, "place": "yard", "x": 5, "y": 5,
         "looks": looks(LIGHT), "dress": True},
        {"id": "ben", "stub": {"name": "Ben Ruiz", "age": 40, "sex": "male"}, "place": "yard", "x": 6, "y": 5,
         "looks": looks(WARM), "dress": True},
        {"id": "cal", "stub": {"name": "Cal Hobbs", "age": 30, "sex": "male"}, "place": "yard", "x": 7, "y": 5,
         "looks": looks(LIGHT)},
        {"id": "dot", "stub": {"name": "Dot Reyes", "age": 50, "sex": "female"}, "place": "yard", "x": 8, "y": 5},
        {"id": "eve", "stub": {"name": "Eve Lund", "age": 27, "sex": "female"}, "place": "shed", "x": 2, "y": 2,
         "looks": looks(LIGHT)},
    ],
}


@pytest.fixture
def farm(fixture_packs, core_pack_dir):
    worlds = []

    def _load(change=None):
        spec = copy.deepcopy(FARM)
        if change is not None:
            change(spec)
        w = load_scenario(spec, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        return w

    yield _load
    for w in worlds:
        w.store.close()


def start(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def rain(spec):
    spec["weather"] = {"kind": "rain"}


def night(spec):
    spec["start"] = {"day": 400, "time": "21:00"}


def progress(w, local, to_ms):
    with w.store.transaction() as tx:
        return bodies.progress(tx, w.id(local), to_ms, 0, w.rng)


def live(w, local, days):
    """Day by day, fed, watered and rested (nobody dies of thirst while the grime builds)."""
    t = start(w)
    for d in range(days):
        with w.store.transaction() as tx:
            for need in ("thirst", "hunger", "fatigue"):
                bodies.refresh_need(tx, w.id(local), need, t + d * DAY, None, 0)
        progress(w, local, t + (d + 1) * DAY)


def soil(w, local, **kw):
    with w.store.transaction() as tx:
        bodies.soil(tx, w.id(local), source="test", at=start(w), cause_event_id=None, turn_index=0, **kw)


def cond(w, local):
    c = bodies.condition_of(w.store, w.id(local))
    return (c.grime, c.blood, c.gore, c.wet)


def cold(w, local):
    r = w.store.query_one("SELECT chill, cold_stage FROM needs WHERE body_id = ?", (w.id(local),))
    return (r[0], r[1])


def sources(w, local):
    return [json.loads(r[0])["source"] for r in w.store.query(
        "SELECT payload FROM events WHERE type = 'BODY_CONDITION' AND json_extract(payload, '$.body_id') = ? ORDER BY seq",
        (w.id(local),))]


# --------------------------------------------------------------------------- LOOK-08 unwashed
def test_days_without_a_wash_make_anyone_grimy(farm):
    """A day at a time to 'grimy' (3) and no further: filthy takes dirt, not days."""
    w = farm()
    t = start(w)
    progress(w, "ben", t + DAY - MIN)
    assert cond(w, "ben")[0] == 0
    progress(w, "ben", t + DAY)
    assert cond(w, "ben")[0] == 1 and sources(w, "ben") == ["unwashed"]
    w2 = farm()
    live(w2, "ben", 5)
    assert bodies.is_alive(w2.store, w2.id("ben"))
    assert cond(w2, "ben")[0] == 3 and sources(w2, "ben") == ["unwashed"] * 3


def test_a_wash_starts_the_count_again(farm):
    w = farm()
    t = start(w)
    progress(w, "ben", t + 2 * DAY)
    with w.store.transaction() as tx:
        bodies.wash(tx, w.id("ben"), full=True, at=t + 2 * DAY, cause_event_id=None, turn_index=0)
    progress(w, "ben", t + 3 * DAY - MIN)
    assert cond(w, "ben")[0] == 0
    progress(w, "ben", t + 3 * DAY)
    assert cond(w, "ben")[0] == 1


# --------------------------------------------------------------------------- LOOK-08 weather
def test_the_rain_soaks_you_and_takes_the_gore_off(farm):
    """Out in the rain: every 20 minutes wet +1, blood -1, gore -1 — the dead's gore washes away in the
    open, and with it the camouflage (INF-14 needs gore 4)."""
    w = farm(rain)
    soil(w, "ben", gore=5, blood=3)
    t = start(w)
    progress(w, "ben", t + 20 * MIN)
    assert cond(w, "ben") == (0, 2, 4, 1)
    progress(w, "ben", t + 40 * MIN)
    assert cond(w, "ben") == (0, 1, 3, 2), "forty minutes of rain and the dead would know him"
    progress(w, "ben", t + 2 * H)
    assert cond(w, "ben") == (0, 0, 0, 3)
    assert set(sources(w, "ben")) == {"test", "rain"}


def test_under_a_roof_the_rain_is_nothing(farm):
    w = farm(rain)
    soil(w, "eve", gore=5)
    progress(w, "eve", start(w) + 2 * H)
    assert cond(w, "eve") == (0, 0, 5, 0)


def test_out_of_the_rain_you_dry(farm):
    w = farm()
    soil(w, "ben", wet=3)
    t = start(w)
    progress(w, "ben", t + 20 * MIN)
    assert cond(w, "ben")[3] == 2
    progress(w, "ben", t + 60 * MIN)
    assert cond(w, "ben")[3] == 0 and "dried" in sources(w, "ben")


# --------------------------------------------------------------------------- LOOK-09 cold
def test_what_the_place_and_the_weather_ask(farm):
    """cold_need: a mild country asks 1 in the open by day, 2 at night, nothing indoors; a soaked body
    asks one more anywhere; a cold country asks more (C.cold_need)."""
    w = farm()
    t = start(w)
    assert bodies.cold_need(w.store, w.id("ada"), t) == 1
    assert bodies.cold_need(w.store, w.id("ada"), t + 12 * H) == 2, "22:00 is night"
    assert bodies.cold_need(w.store, w.id("eve"), t + 12 * H) == 0, "a roof: mild 1 - shelter 2, never below 0"
    soil(w, "ada", wet=2)
    assert bodies.cold_need(w.store, w.id("ada"), t) == 2
    cold_country = farm(lambda s: s.update(rules={"condition": {"cold_need": {"cold": 3, "mild": 3, "hot": 0}}}))
    assert bodies.cold_need(cold_country.store, cold_country.id("ada"), t + 12 * H) == 4
    assert bodies.cold_need(cold_country.store, cold_country.id("eve"), t) == 1


def test_a_night_in_the_open(farm):
    """Chill is counted on the hour: what the night asks minus what they wear. Four hours of a mild
    night: Cal with nothing on (2 an hour) is shivering; Ada in a t-shirt (1 an hour) is cold; Ben in a
    parka is fine; Dot, whose looks the world never recorded, makes no claim either way."""
    w = farm(night)
    t = start(w)
    for who in ("ada", "ben", "cal", "dot"):
        progress(w, who, t + 4 * H)
    assert cold(w, "cal") == (8, 2)
    assert cold(w, "ada") == (4, 1)
    assert cold(w, "ben") == (0, 0)
    assert cold(w, "dot") == (0, 0)
    ev = [json.loads(r[0]) for r in w.store.query(
        "SELECT payload FROM events WHERE type = 'NEED_STAGE' AND json_extract(payload, '$.need') = 'cold' "
        "AND json_extract(payload, '$.body_id') = ? ORDER BY seq", (w.id("cal"),))]
    assert [(e["chill"], e["stage"]) for e in ev] == [(2, 0), (4, 1), (6, 1), (8, 2)]


def test_the_cold_takes_the_strength_out_of_you(farm):
    w = farm(night)
    progress(w, "cal", start(w) + 6 * H)
    assert cold(w, "cal")[1] == 3
    assert bodies.impairment(w.store, w.id("cal")) >= 1


def test_naked_on_a_wet_night_in_a_cold_country_kills(farm):
    """Rain soaks him, the soaking asks one more, the cold country more again: a few hours."""
    w = farm(lambda s: (night(s), rain(s), s.update(rules={"condition": {"cold_need": {"cold": 3, "mild": 3, "hot": 0}}})))
    t = start(w)
    progress(w, "cal", t + 4 * H)
    assert bodies.is_alive(w.store, w.id("cal"))
    evs = progress(w, "cal", t + 6 * H)
    (death,) = [e for e in evs if e.type == EventType.DEATH]
    assert death.payload["cause"] == "cold"


def test_warm_again_the_chill_goes(farm):
    """Enough on (or a roof) and the chill falls by 4 an hour."""
    w = farm(night)
    t = start(w)
    progress(w, "cal", t + 4 * H)
    with w.store.transaction() as tx:
        objects.dress(tx, w.id("cal"), [OutfitPiece(item=x["item"]) for x in WARM], t + 4 * H, None, 0, "scenario")
    progress(w, "cal", t + 5 * H)
    assert cold(w, "cal") == (4, 1)
    progress(w, "cal", t + 6 * H)
    assert cold(w, "cal") == (0, 0)
