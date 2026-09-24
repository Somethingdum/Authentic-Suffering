"""The universal check (P5). Rules CHECK-01..07 (action/checks.py, vectors/checks.json).

TARGET = clamp(attr_mod + skill_rank + tag + situation + scale - impairment//2 - resistance, 1, 9);
MARGIN = TARGET - d10; >= 3 CLEAN, 0..2 COST, -1..-2 FAIL, <= -3 BREAK. Identity is never rolled.
"""

from __future__ import annotations

import json

import pytest

import helpers
from as_engine.action import checks
from as_engine.contracts.common import CheckBand
from as_engine.contracts.content import CheckSpec
from as_engine.contracts.settings import CheckRules

pytestmark = pytest.mark.phase(5)


class Scripted:
    """A test rng: returns scripted values in order and records what was asked (no ledger)."""

    def __init__(self, *values):
        self.values = list(values)
        self.asked = []

    def d10(self, tx, stream, purpose):
        self.asked.append((stream, purpose, 10))
        return self.values.pop(0)

    def draw(self, tx, stream, purpose, n):
        self.asked.append((stream, purpose, n))
        return self.values.pop(0)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


# --------------------------------------------------------------------------- pure parts
def test_compute_target_vectors(vectors):
    for v in vectors("checks")["compute_target"]:
        got = checks.compute_target(v["attr"], v["skill_rank"], v["has_tag"], v["situation"], v["scale"],
                                    v["impairment"], v["resistance"], CheckRules())
        assert got == v["target"], v["why"]


def test_band_for_margin_vectors(vectors):
    for v in vectors("checks")["band_for_margin"]:
        assert checks.band_for_margin(v["margin"], CheckRules()) == CheckBand(v["band"]), v


def test_stealth6_vectors(vectors):
    for v in vectors("checks")["stealth6"]:
        assert checks.stealth6(v["margin"]) == v["degree"], v


def test_worked_odds(vectors):
    """07_RULES §1: count the d10 faces per band for the two worked examples."""
    odds = vectors("checks")["worked_odds"]
    for key, target in (("untrained_attr5_target3", 3), ("specialist_attr7_rank2_tag_target8", 8)):
        counts = {"clean": 0, "cost": 0, "fail": 0, "break": 0}
        for face in range(1, 11):
            counts[checks.band_for_margin(target - face, CheckRules()).value] += 1
        assert counts == {k: v for k, v in odds[key].items() if k != "_why"}


# --------------------------------------------------------------------------- roll
def test_roll_reads_the_body_and_the_dossier(scenario):
    """Twin A: firearms 3 (stub skill), P 5 -> attr_mod 3, no tags; impairment 0."""
    w = scenario("two_skills")
    spec = CheckSpec(attribute="P", skill="firearms", tags=["marksman"], resistance="range_band")
    with w.store.transaction() as tx:
        r = checks.roll(tx, w.rng, w.id("twin_a"), "shoot_center_mass", spec, situation=-1, resistance=1,
                        at=now(w), turn_index=0)
    (led,) = [x for x in helpers.ledger_draws(w.store, 0) if x["purpose"] == f"check:{w.id('twin_a')}:shoot_center_mass"]
    assert (led["stream"], led["n"]) == ("resolve", 10)
    assert r.target == 3 + 3 + 0 - 1 + 0 - 0 - 1 == 4
    assert r.draw == led["value"] and r.margin == r.target - r.draw
    assert r.band == checks.band_for_margin(r.margin, CheckRules())
    assert r.components == {"attr_mod": 3, "skill_rank": 3, "tag_bonus": 0, "situation": -1, "scale": 0,
                            "impairment_penalty": 0, "resistance": 1}
    (ev,) = helpers.events_of(w.store, "CHECK_RESOLVED")
    p = json.loads(ev["payload"])
    assert ev["writer"] == "action.resolve" and ev["actor_id"] == w.id("twin_a")
    assert {k: p[k] for k in ("def_id", "attribute", "attr_value", "skill", "skill_rank", "target", "draw", "margin", "band", "ladder")} == {
        "def_id": "shoot_center_mass", "attribute": "P", "attr_value": 5, "skill": "firearms", "skill_rank": 3,
        "target": 4, "draw": r.draw, "margin": r.margin, "band": r.band.value, "ladder": None}
    assert json.loads(ev["state_delta"]) == [], "a check changes nothing by itself"


def test_untrained_twin_and_infected_roll_at_rank_zero(scenario):
    w = scenario("two_skills")
    spec = CheckSpec(attribute="P", skill="firearms")
    with w.store.transaction() as tx:
        b = checks.roll(tx, Scripted(1), w.id("twin_b"), "x", spec, situation=0, resistance=0, at=now(w), turn_index=0)
        z = checks.roll(tx, Scripted(1), w.id("shambler"), "x", spec, situation=0, resistance=0, at=now(w), turn_index=0)
    assert b.components["skill_rank"] == 0 and z.components["skill_rank"] == 0


def test_a_capability_tag_adds_two_once(scenario):
    w = scenario("metal_fence")   # June: capability tag calm_voice
    spec = CheckSpec(attribute="C", skill="persuasion", tags=["calm_voice", "marksman"])
    with w.store.transaction() as tx:
        r = checks.roll(tx, Scripted(5), w.id("june"), "calm_person", spec, situation=0, resistance=0, at=now(w), turn_index=0)
    assert r.components["tag_bonus"] == 2


def test_stealth_ladder_word_is_recorded(scenario):
    w = scenario("metal_fence")
    spec = CheckSpec(attribute="A", skill="stealth", consequence_ladder="stealth6")
    with w.store.transaction() as tx:
        r = checks.roll(tx, Scripted(1), w.id("nita"), "hide", spec, situation=0, resistance=0, at=now(w), turn_index=0)
    p = json.loads(helpers.events_of(w.store, "CHECK_RESOLVED")[-1]["payload"])
    assert p["ladder"] == checks.stealth6(r.margin)


def test_impairment_costs_half_a_step(scenario):
    w = scenario("metal_fence")   # Mara: fatigue 3 -> impairment 1 -> penalty 0
    spec = CheckSpec(attribute="P", skill="firearms")
    with w.store.transaction() as tx:
        r = checks.roll(tx, Scripted(5), w.id("mara"), "x", spec, situation=0, resistance=0, at=now(w), turn_index=0)
    assert r.components["impairment_penalty"] == 0


# --------------------------------------------------------------------------- opposed (CHECK-06)
def _opp(w, rng, **kw):
    a = CheckSpec(attribute="S", skill="brawling", opposed=True, opposed_attribute="A", opposed_skill="brawling")
    b = CheckSpec(attribute="A", skill="brawling")
    with w.store.transaction() as tx:
        return checks.opposed(tx, rng, w.id("twin_a"), a, w.id("twin_b"), b, def_id="grapple", a_situation=0,
                              b_situation=0, at=now(w), turn_index=0, **kw)


def test_opposed_clean_and_cost(scenario):
    w = scenario("two_skills")
    # twin_a: S 5 (mod 3) + brawling 2 = target 5 ; twin_b: A 5 (mod 3) + rank 0 = target 3
    win, ra, rb, how = _opp(w, Scripted(1, 5))       # margins 4 vs -2: difference 6
    assert (win, how, ra.margin, rb.margin) == (w.id("twin_a"), "clean", 4, -2)
    win, ra, rb, how = _opp(w, Scripted(5, 1))       # margins 0 vs 2: twin_b by 2
    assert (win, how) == (w.id("twin_b"), "cost")


def test_opposed_ties(scenario):
    w = scenario("two_skills")
    # equal margins (5-4 = 1, 3-2 = 1), equal attribute mods (3 vs 3) -> one tie draw of 2
    rng = Scripted(4, 2, 2)
    win, ra, rb, how = _opp(w, rng)
    assert ra.margin == rb.margin == 1
    assert (how, win) == ("tie", w.id("twin_b")) and rng.asked[-1] == ("resolve", f"tie:{w.id('twin_a')}:{w.id('twin_b')}", 2)
    win, _a, _b, how = _opp(w, Scripted(4, 2, 1))
    assert (how, win) == ("tie", w.id("twin_a"))
    rng = Scripted(4, 2)
    win, _a, _b, how = _opp(w, rng, established_control=w.id("twin_b"))
    assert (how, win) == ("control", w.id("twin_b")) and len(rng.asked) == 2, "control settles it: no tie draw"


def test_both_sides_draw_attacker_first(scenario):
    w = scenario("two_skills")
    rng = Scripted(3, 3)
    _opp(w, rng)
    assert [p for _s, p, _n in rng.asked] == [f"check:{w.id('twin_a')}:grapple", f"check:{w.id('twin_b')}:grapple:defend"]
    assert len(helpers.events_of(w.store, "CHECK_RESOLVED")) == 2
