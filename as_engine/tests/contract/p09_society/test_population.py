"""Who lives here (P9). Rules DEMO-01..04, CONSERVE-04 (society/population.py).

A settlement's people are its named members (bodies with a place in the governing group) plus its
unnamed people (cohort counts). Without age bands no amount of prose produces children (F1).
"""

from __future__ import annotations

import pytest

from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.contracts.settings import SocietyRules
from as_engine.society import population
from as_engine.society.population import Census

from society_kit import now

pytestmark = pytest.mark.phase(9)

BANDS = ("infant", "child", "preteen", "teen", "adult", "elder")


def add_cohort(w, band, count, local_settlement="pumpwell"):
    with w.store.transaction() as tx:
        cid = tx.mint("coh")
        tx.commit_event(Event(type=EventType.MATERIALIZE, writer="society.population", at=now(w), turn_index=0,
                              payload={"cohort_id": cid},
                              writes=[WriteRecord(op=WriteOp.INSERT, table="cohorts", values={
                                  "cohort_id": cid, "settlement_id": w.id(local_settlement), "zone_id": None, "age_band": band,
                                  "sex": "female", "cohort_kind": "post_fall_born", "count": count, "archetype": None})]))
    return cid


def test_census_counts_the_named_and_the_unnamed(settle):
    w = settle
    c = population.census(w.store, w.id("pumpwell"))
    assert c.total == 24 and c.unnamed == 0 and len(c.named) == 24
    assert w.id("pc") in c.named                                    # the PC is counted like anyone (L12)
    assert c.by_band == {"infant": 2, "child": 3, "preteen": 1, "teen": 1, "adult": 15, "elder": 2}
    assert list(c.named) == sorted(c.named)
    add_cohort(w, "child", 4)
    c2 = population.census(w.store, w.id("pumpwell"))
    assert (c2.total, c2.unnamed, c2.by_band["child"], len(c2.named)) == (28, 4, 7, 24)


def test_the_dead_are_not_counted(settle):
    w = settle
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.DEATH, writer="physical.bodies", at=now(w), turn_index=0,
                              payload={"body_id": w.id("otis"), "cause": "old age", "cause_event_id": None},
                              writes=[WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": w.id("otis")},
                                                  values={"alive": 0, "awareness": "dead", "dead_at": now(w)})]))
    c = population.census(w.store, w.id("pumpwell"))
    assert c.total == 23 and w.id("otis") not in c.named and c.by_band["elder"] == 1


def test_unknown_settlement(settle):
    with pytest.raises(ValueError):
        population.census(settle.store, "stl_999999")


def census_of(**bands):
    by = {b: bands.get(b, 0) for b in BANDS}
    return Census("stl_000001", tuple(), by, sum(by.values()), sum(by.values()))


def test_demo_01_the_survivor_pyramid():
    R = SocietyRules()
    assert population.demographic_issues(census_of(infant=2, child=3, preteen=1, teen=1, adult=15, elder=2), R) == []
    assert population.demographic_issues(census_of(adult=15), R) == []          # 15 or fewer: no bounds
    issues = population.demographic_issues(census_of(adult=20), R)
    assert issues == ["Too few children: 0 of 20 (0%), expected 10-30%.",
                      "Too few young people: 0 of 20 (0%), expected 8-20%.",
                      "Too many adults: 20 of 20 (100%), expected 40-70%.",
                      "Too few elders: 0 of 20 (0%), expected 3-15%."]
    assert population.demographic_issues(census_of(infant=4, child=6, teen=3, adult=10, elder=2), R) == \
        ["Too many children: 10 of 25 (40%), expected 10-30%."]


def test_the_fixture_is_a_plausible_settlement(settle):
    c = population.census(settle.store, settle.id("pumpwell"))
    assert population.demographic_issues(c, SocietyRules()) == []


def test_consumption_is_what_the_fixture_was_built_on(settle):
    c = population.census(settle.store, settle.id("pumpwell"))
    assert population.consumption(c, SocietyRules()) == {"food": 42.0, "water": 62.0}


def test_conserve_04_a_cohort_never_goes_below_zero(settle):
    w = settle
    cid = add_cohort(w, "adult", 3)
    with w.store.transaction() as tx:
        ev = population.adjust_cohort(tx, cid, -2, "died of fever", now(w), 0, None)
    assert ev.type == EventType.POPULATION_CHANGE and ev.writer == "society.population"
    assert {k: ev.payload[k] for k in ("delta", "count_before", "count_after", "reason")} == \
        {"delta": -2, "count_before": 3, "count_after": 1, "reason": "died of fever"}
    assert w.store.query_one("SELECT count FROM cohorts WHERE cohort_id = ?", (cid,))[0] == 1
    for bad in (-2, 0):
        with pytest.raises(ValueError):
            with w.store.transaction() as tx:
                population.adjust_cohort(tx, cid, bad, "x", now(w), 0, None)
    with pytest.raises(ValueError):
        with w.store.transaction() as tx:
            population.adjust_cohort(tx, "coh_999999", 1, "x", now(w), 0, None)
