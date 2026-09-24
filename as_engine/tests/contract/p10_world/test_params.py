"""World parameters, WG0 (P10). Rules WG-01..09, WG-34, WG-DET-01, CNT-09 (world/worldgen/params.py,
world/worldgen/conditions.py). CMG §61 Parts III-VIII carried; the tables are canon (tables.py).

The same seed, difficulty, era and PC give the same world, draw for draw: every draw is pinned by the
vectors (tests/fixtures/vectors/params.json), so a mismatch names the first wrong draw.
"""

from __future__ import annotations

import itertools
import json

import pytest

from as_engine.contracts.common import Difficulty, Era
from as_engine.contracts.dossier import WorldgenBias
from as_engine.contracts.settings import ERA_DAYS_RANGE
from as_engine.kernel.errors import SettingsError
from as_engine.kernel.rng import Rng
from as_engine.world.worldgen import conditions, params, tables
from as_engine.world.worldgen.conditions import ConditionSyntaxError

pytestmark = pytest.mark.phase(10)

STREAM = "worldgen:params"


def _gen(store, seed, difficulty, era, bias=None, dsf=None, fall_range=None, pc_name="Test Person"):
    with store.transaction() as tx:
        return params.generate_params(Rng(seed), tx, Difficulty(difficulty), Era(era), WorldgenBias(**(bias or {})), dsf,
                                      fall_range=fall_range, pc_name=pc_name)


def _draws(store):
    return [dict(r) for r in store.query("SELECT purpose, n, value FROM prng_ledger WHERE stream = ? ORDER BY seq", (STREAM,))]


def test_rnd_rounds_half_up(vectors):
    for case in vectors("params")["rnd"]:
        assert params.rnd(case["x"]) == case["rnd"], case


@pytest.mark.parametrize("case", range(4))
def test_generate_params_vectors(store, vectors, case):
    """WG-01..08, WG-DET-01: every value, every patch and every draw of four pinned worlds."""
    c = vectors("params")["generate_params"][case]
    fr = tuple(c["pc_days_since_fall_range"]) if c["pc_days_since_fall_range"] else None
    p, patches = _gen(store, c["seed"], c["difficulty"], c["era"], c["bias"], c["days_since_fall_given"], fr)
    got = _draws(store)
    for i, (want, have) in enumerate(itertools.zip_longest(c["draws"], got)):
        assert have == want, f"draw {i}: expected {want}, got {have}"
    values = params.flat_values(p)
    assert {k: values[k] for k in c["expected_values"]} == c["expected_values"]
    assert patches == c["expected_patches"]
    assert {k: values[k] for k in c["sim_mechanics"]} == c["sim_mechanics"]
    assert p.d.key_resource == c["expected_key_resource"]
    assert params.key_resource_type(values, values["hazard_type"]) == c["expected_key_resource_types"]
    assert p.climate_descriptor == c["expected_climate_descriptor"]
    assert (p.difficulty.value, p.era.value) == (c["difficulty"], c["era"])


def test_difficulty_owned_values_stay_in_their_bands(store):
    """WG-03: every difficulty-owned parameter is drawn inside its difficulty band."""
    for n, diff in enumerate(Difficulty):
        s = store
        p, _ = _gen(s, 100 + n, diff.value, "established")
        v = params.flat_values(p)
        for name, bands in tables.DIFFICULTY_BANDS.items():
            lo, hi = bands[diff]
            assert lo <= v[name] <= hi, (diff, name, v[name])
        snow, warn, rec = tables.SIM_MECHANICS[diff]
        assert (p.sim.snowball_rate, p.sim.warning_slack, p.sim.recovery_slack) == (snow, warn, rec)


def test_era_constraints_hold(store):
    """WG-05: the era's B-block bands (Early caps faction density and social order)."""
    for seed in range(5):
        p, _ = _gen(store, 200 + seed, "normal", "early", {"faction_density": 1.0, "social_order": 1.0})
        assert p.b.faction_density <= 4 and p.b.social_order <= 5
        assert ERA_DAYS_RANGE[Era.EARLY][0] <= p.days_since_fall <= ERA_DAYS_RANGE[Era.EARLY][1]


def test_a_given_days_since_fall_is_used_and_not_drawn(store):
    p, _ = _gen(store, 5, "normal", "mature", dsf=2000, fall_range=(1830, 3650))
    assert p.days_since_fall == 2000
    purposes = [d["purpose"] for d in _draws(store)]
    assert "days_since_fall" not in purposes
    assert purposes[:len(tables.DRAW_ORDER) - 1] == list(tables.DRAW_ORDER[:-1]), "every other draw in DRAW_ORDER"


def test_days_since_fall_is_drawn_inside_era_and_character(store):
    """WG-34: the draw is inside ERA_DAYS_RANGE[era] intersected with the PC's range."""
    p, _ = _gen(store, 9, "normal", "mature", fall_range=(3287, 4018))
    assert 3287 <= p.days_since_fall <= 3650
    d = [x for x in _draws(store) if x["purpose"] == "days_since_fall"]
    assert len(d) == 1 and d[0]["n"] == 3650 - 3287 + 1


@pytest.mark.parametrize("era, dsf", [("early", None), ("mature", 500)])
def test_wg34_a_world_the_character_cannot_live_in_is_refused(store, era, dsf):
    """WG-34: a given age outside the PC's range, or no overlap with the era, is a SettingsError."""
    with pytest.raises(SettingsError) as e:
        _gen(store, 11, "normal", era, dsf=dsf, fall_range=(3287, 4018), pc_name="Addison Flores")
    assert str(e.value) == "Addison Flores's age and history need a world 9-11 years after the Fall."
    assert e.value.rule == "WG-34"


def _base():
    v = {name: 5 for name in ("tech_preservation", "instability", "social_order", "atrocity_capacity", "survivor_mentality",
                              "faction_density", "faction_fragmentation", "wildcard_level", "mystery", "tech_baseline",
                              "faction_relations")}
    return v


def _flagged(v, era):
    ops = {">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, "==": lambda a, b: a == b}
    out = []
    for cid, hp, hop, hv, lp, lop, lv, _ov in tables.CONTRADICTIONS:
        hi = (era == Era.EARLY) if hp == "era=early" else ops[hop](v[hp], hv)
        if hi and ops[lop](v[lp], lv):
            out.append(cid)
    return out


@pytest.mark.parametrize("era, changes, patches", [
    ("established", {}, []),
    ("established", {"tech_preservation": 8, "instability": 9}, ["#1: instability 9->7"]),
    ("established", {"social_order": 8, "atrocity_capacity": 9, "survivor_mentality": 10},
     ["#2: atrocity_capacity 9->6", "#3: survivor_mentality 10->7"]),
    ("early", {"faction_density": 7, "social_order": 8, "tech_preservation": 9},
     ["#4: faction_density 7->4", "#5: social_order 8->5", "#6: tech_preservation 9->7"]),
    ("established", {"faction_fragmentation": 9, "faction_density": 1}, ["#7: faction_density 1->3"]),
    ("established", {"wildcard_level": 9, "mystery": 1, "tech_preservation": 2, "tech_baseline": 9},
     ["#9: mystery 1->3", "#10: tech_baseline 9->6"]),
    ("established", {"social_order": 1, "faction_relations": 10, "instability": 10},
     ["#11: faction_relations 10->7"]),
    ("established", {"instability": 9, "social_order": 9}, ["#12: social_order 9->6"]),
])
def test_contradictions(era, changes, patches):
    """WG-07 (Part VII): the lower parameter moves to the nearest value that clears its condition."""
    v = _base() | changes
    out, got = params.apply_contradictions(dict(v), Era(era))
    assert got == patches
    assert _flagged(out, Era(era)) == []
    assert v == _base() | changes, "the caller's dict is not changed"


def test_no_contradiction_survives(store):
    """WG-07: whatever the draw, no row of the table is still flagged afterwards."""
    for seed in range(40):
        diff = list(Difficulty)[seed % 6]
        era = list(Era)[seed % 3]
        p, _ = _gen(store, 1000 + seed, diff.value, era.value, {"instability": 1.0, "faction_density": -1.0})
        assert _flagged(params.flat_values(p), era) == [], seed


@pytest.mark.parametrize("changes, hazard, types", [
    ({"food": 3}, "environmental", ["supply node"]),
    ({"water": 2, "tech_preservation": 9, "tech_baseline": 9}, "environmental", ["supply node"]),
    ({"tech_preservation": 7, "tech_baseline": 6}, "biological", ["infrastructure"]),
    ({"hazard_severity": 6}, "biological", ["biological"]),
    ({"hazard_severity": 6}, "structural", ["supply node", "infrastructure", "biological", "territory", "information source"]),
    ({"faction_density": 6, "faction_fragmentation": 6}, "environmental", ["territory"]),
    ({"hostile_human": 9}, "environmental", ["information source", "territory"]),
    ({"runner_pressure": 8}, "environmental", ["supply node", "infrastructure"]),
    ({"ambient_danger": 8}, "environmental", ["supply node", "infrastructure", "biological", "territory", "information source"]),
    ({"hostile_human": 8, "zombie_common": 8}, "environmental",
     ["supply node", "infrastructure", "biological", "territory", "information source"]),
])
def test_key_resource_type(changes, hazard, types):
    """WG-08 (Part VIII): the rules in order; the first that applies decides."""
    v = {k: 5 for k in ("food", "water", "tech_preservation", "tech_baseline", "hazard_severity", "faction_density",
                        "faction_fragmentation", "ambient_danger", "zombie_common", "horde_pressure", "runner_pressure",
                        "lurker_pressure", "hostile_human")} | changes
    assert params.key_resource_type(v, hazard) == types


def test_key_resource_is_one_of_the_atlas_descriptors(store):
    from as_engine.world.worldgen import atlas

    for seed in range(12):
        p, _ = _gen(store, 300 + seed, list(Difficulty)[seed % 6].value, "mature")
        kind, desc = p.d.key_resource.split(" — ")
        assert desc in atlas.KEY_RESOURCE_DESCRIPTORS[kind] and len(p.d.key_resource) <= 50


def test_params_round_trip_as_json(store):
    p, _ = _gen(store, 42, "realism", "established")
    again = type(p).model_validate(json.loads(p.model_dump_json()))
    assert again == p


# ------------------------------------------------------------------------------------ conditions
VALUES = {"ammo": 3, "food": 6, "faction_density": 2, "days_since_fall": 400, "start_trust": 5, "entity_type": "group"}


@pytest.mark.parametrize("expr, result", [
    ("ammo >= 3", True),
    ("ammo>3", False),
    ("ammo >= 1 and food <= 6 and days_since_fall > 365", True),
    ("ammo >= 1 and food < 6", False),
    ("entity_type = group", True),
    ("entity_type = faction and start_trust >= 4", False),
    ("faction_density != 2", False),
    ("start_trust == 5", True),
])
def test_evaluate(expr, result):
    """CNT-09: every clause must hold (AND)."""
    assert conditions.evaluate(expr, VALUES) is result


def test_evaluate_never_guesses_a_missing_name():
    with pytest.raises(ConditionSyntaxError):
        conditions.evaluate("meds >= 1", VALUES)
    with pytest.raises(ConditionSyntaxError):
        conditions.evaluate("ammo >= 1 or food >= 1", VALUES)
