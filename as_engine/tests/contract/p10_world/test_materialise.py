"""Naming the unnamed (P10). Rules L11 / CONSERVE-04 (society/population.py take_from_cohort,
materialise) and DOS-01 (mind/actor.py create).

A settlement's people are counted in cohorts; when the world needs one of them as a person (a
DECON operator, a newcomer who walks up to the gate), one is taken from the count — never made from
nothing — and gets a body, a place to stand, a mind and the knowledge of where they are.
"""

from __future__ import annotations

import hashlib
import json

import pytest
from world_kit import all_rows, now, one, rows, turn

from as_engine.contracts.events import EventType
from as_engine.kernel.jsoncanon import canonical_json
from as_engine.mind import actor as mind_actor
from as_engine.society import population
from as_engine.world.worldgen import people

pytestmark = pytest.mark.phase(10)


def cohort_row(s, band="adult", sex=None) -> dict:
    """The fullest settlement cohort of a band (by count, then id)."""
    sql = "SELECT * FROM cohorts WHERE settlement_id IS NOT NULL AND age_band = ? AND count > 0"
    args = [band]
    if sex:
        sql += " AND sex = ?"
        args.append(sex)
    r = one(s, sql + " ORDER BY count DESC, cohort_id LIMIT 1", tuple(args))
    if r is None:
        pytest.skip(f"no {band} cohort left")
    return r


def dossier(name="Wes Harlan", age=34, sex="male", variant=11) -> dict:
    return people.skeleton_dossier(people.PersonSeed(
        name=name, age=age, sex=sex, cohort="pre_fall_adult", occupation="mechanic",
        skills={"mechanics": 2, "firearms": 1}, special={k: 5 for k in "SPECIAL"}, variant=variant,
        settlement_name="Mill Creek", group_name="the Mill Creek folk"))


def site_of(s, settlement_id) -> str:
    return one(s, "SELECT place_id FROM settlements WHERE settlement_id = ?", (settlement_id,))["place_id"]


# =========================================================================== take_from_cohort
def test_one_person_is_taken_from_the_count(gw):
    """take_from_cohort: the settlement's lowest cohort of that band and sex with anyone left
    loses one (POPULATION_CHANGE reason 'materialised'); none left -> None and nothing changes."""
    s = gw
    c = cohort_row(s)
    first = one(s, "SELECT * FROM cohorts WHERE settlement_id = ? AND age_band = ? AND sex = ? AND count > 0 "
                   "ORDER BY cohort_id LIMIT 1", (c["settlement_id"], c["age_band"], c["sex"]))
    with s.store.transaction() as tx:
        ev = population.take_from_cohort(tx, c["settlement_id"], None, c["age_band"], c["sex"], now(s), turn(s), None)
    assert ev.type == EventType.POPULATION_CHANGE
    assert (ev.payload["cohort_id"], ev.payload["delta"], ev.payload["reason"]) == (first["cohort_id"], -1, "materialised")
    assert one(s, "SELECT count FROM cohorts WHERE cohort_id = ?", (first["cohort_id"],))["count"] == first["count"] - 1
    before = s.store.query_one("SELECT COUNT(*) FROM events")[0]
    with s.store.transaction() as tx:
        assert population.take_from_cohort(tx, c["settlement_id"], None, "infant", "neither", now(s), turn(s), None) is None
    assert s.store.query_one("SELECT COUNT(*) FROM events")[0] == before


# =========================================================================== materialise
def test_a_named_person_steps_out_of_the_count(gw):
    """materialise: the cohort loses one; a human body with the dossier's age, height, mass and
    SPECIAL, made 'materialize'; standing at the place's first anchor; a mind (source 'generated',
    controller 'model', named as the dossier says); knowing the place it stands in — every step
    caused by the count's change."""
    s = gw
    c = cohort_row(s, sex="male")
    place = site_of(s, c["settlement_id"])
    d = dossier()
    total = s.store.query_one("SELECT SUM(count) FROM cohorts WHERE settlement_id = ?", (c["settlement_id"],))[0]
    taken = one(s, "SELECT cohort_id FROM cohorts WHERE settlement_id = ? AND age_band = 'adult' AND sex = 'male' "
                   "AND count > 0 ORDER BY cohort_id LIMIT 1", (c["settlement_id"],))["cohort_id"]
    with s.store.transaction() as tx:
        who = population.materialise(tx, s.rng, settlement_id=c["settlement_id"], zone_id=None, band="adult",
                                     sex="male", dossier=d, place_id=place, at=now(s), turn_index=turn(s),
                                     cause_event_id=None)
    assert s.store.query_one("SELECT SUM(count) FROM cohorts WHERE settlement_id = ?", (c["settlement_id"],))[0] == total - 1
    b = one(s, "SELECT * FROM bodies WHERE body_id = ?", (who,))
    assert (b["kind"], b["sex"], b["age_years"], b["height_cm"], b["mass_kg"], b["origin"], b["alive"]) == (
        "human", "male", 34, d["appearance"]["height_cm"], d["appearance"]["mass_kg"], "materialize", 1)
    assert json.loads(b["special"]) == d["capability"]["special"]
    anchor = one(s, "SELECT * FROM anchors WHERE place_id = ? ORDER BY anchor_id LIMIT 1", (place,))
    pos = one(s, "SELECT * FROM positions WHERE body_id = ?", (who,))
    if anchor is None:
        p = one(s, "SELECT width_m, depth_m FROM places WHERE place_id = ?", (place,))
        assert (pos["place_id"], pos["anchor_id"], pos["x_m"], pos["y_m"]) == (place, None, p["width_m"] / 2, p["depth_m"] / 2)
    else:
        assert (pos["place_id"], pos["anchor_id"], pos["x_m"], pos["y_m"]) == (place, anchor["anchor_id"], anchor["x_m"],
                                                                              anchor["y_m"])
    a = one(s, "SELECT * FROM actors WHERE actor_id = ?", (who,))
    assert (a["controller"], a["display_name"], a["lod_hint"], a["stress"]) == ("model", "Wes Harlan", "cold", 0)
    assert one(s, "SELECT source FROM dossiers WHERE actor_id = ?", (who,))["source"] == "generated"
    kp = one(s, "SELECT * FROM known_places WHERE holder_id = ? AND place_id = ?", (who, place))
    assert (kp["first_seen"], kp["last_seen"], kp["visited"]) == (now(s), now(s), 1)
    change = [r for r in rows(s, "POPULATION_CHANGE") if r["payload"]["reason"] == "materialised"][-1]
    assert change["payload"]["cohort_id"] == taken
    made = [r for r in rows(s, "MATERIALIZE") if r["actor_id"] == who]
    assert made and all(r["cause_event_id"] == change["event_id"] for r in made)
    [seen] = [r for r in rows(s, "PERCEIVE") if r["actor_id"] == who]
    assert (seen["writer"], seen["payload"]) == ("mind.perception", {"holder_id": who, "seed": True})


def test_worldgen_s_people_are_marked_as_worldgen_s(gw):
    """materialise(event_origin='worldgen'): the body's origin is 'worldgen' and so is the events'."""
    s = gw
    c = cohort_row(s, sex="female")
    with s.store.transaction() as tx:
        who = population.materialise(tx, s.rng, settlement_id=c["settlement_id"], zone_id=None, band="adult",
                                     sex="female", dossier=dossier("Ada Pryce", 41, "female", 3),
                                     place_id=site_of(s, c["settlement_id"]), at=now(s), turn_index=turn(s),
                                     cause_event_id=None, event_origin="worldgen")
    assert one(s, "SELECT origin FROM bodies WHERE body_id = ?", (who,))["origin"] == "worldgen"
    assert {r["origin"] for r in all_rows(s, "SELECT origin FROM events WHERE type = 'MATERIALIZE' AND actor_id = ?", (who,))} == {"worldgen"}


def test_nobody_is_made_who_is_not_there(gw):
    """materialise: no cohort of that band and sex with anyone left -> ValueError, nothing written."""
    s = gw
    c = cohort_row(s)
    before = s.store.query_one("SELECT COUNT(*) FROM events")[0]
    with s.store.transaction() as tx, pytest.raises(ValueError):
        population.materialise(tx, s.rng, settlement_id=c["settlement_id"], zone_id=None, band="adult", sex="neither",
                               dossier=dossier(), place_id=site_of(s, c["settlement_id"]), at=now(s),
                               turn_index=turn(s), cause_event_id=None)
    assert s.store.query_one("SELECT COUNT(*) FROM events")[0] == before


# =========================================================================== mind.actor.create
def test_a_mind_is_its_whole_dossier(gw):
    """DOS-01 / actor.create: the dossier is stored whole (canonical JSON of the validated record)
    with its sha256; the actors row starts calm at full resolve; one MATERIALIZE {actor_id, source}."""
    s = gw
    from as_engine.physical import bodies
    d = dossier("Cole Mercer", 29, "male", 5)
    with s.store.transaction() as tx:
        b = bodies.create(tx, kind="human", sex="male", age_years=29, height_cm=180, mass_kg=80,
                          special=d["capability"]["special"], at=now(s), turn_index=turn(s), origin="materialize")
        ev = mind_actor.create(tx, b, d, "generated", now(s), turn(s), goal="Find the pump parts")
    assert (ev.type, ev.writer, ev.actor_id, ev.payload) == (EventType.MATERIALIZE, "mind.actor", b,
                                                             {"actor_id": b, "source": "generated"})
    row = one(s, "SELECT * FROM dossiers WHERE actor_id = ?", (b,))
    from as_engine.contracts.dossier import ActorDossier
    want = canonical_json(ActorDossier.model_validate(d).model_dump(mode="json", by_alias=True))
    assert row["baseline_json"] == want and row["content_hash"] == hashlib.sha256(want.encode("utf-8")).hexdigest()
    a = one(s, "SELECT * FROM actors WHERE actor_id = ?", (b,))
    assert a["resolve_cur"] == a["resolve_max"] > 0 and a["goal_text"] == "Find the pump parts" and a["quarantine"] == 0
    with s.store.transaction() as tx, pytest.raises(ValueError):
        mind_actor.create(tx, b, d, "generated", now(s), turn(s))


def test_a_broken_dossier_is_refused(gw):
    """actor.create: a dossier that does not validate -> ValueError, and no mind."""
    s = gw
    from as_engine.physical import bodies
    d = dossier()
    d["identity"].pop("name")
    with s.store.transaction() as tx:
        b = bodies.create(tx, kind="human", sex="male", age_years=34, height_cm=180, mass_kg=80,
                          special={k: 5 for k in "SPECIAL"}, at=now(s), turn_index=turn(s), origin="materialize")
    with s.store.transaction() as tx, pytest.raises(ValueError):
        mind_actor.create(tx, b, d, "generated", now(s), turn(s))
    assert one(s, "SELECT 1 FROM actors WHERE actor_id = ?", (b,)) is None
