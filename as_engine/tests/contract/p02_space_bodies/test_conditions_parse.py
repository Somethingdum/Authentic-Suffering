"""Plausibility-gate grammar (P2 parse; evaluate is P10). Rule CNT-09 (world/worldgen/conditions.py)."""

from __future__ import annotations

import pytest

from as_engine.world.worldgen.conditions import CONDITION_NAMES, ConditionSyntaxError, parse

pytestmark = pytest.mark.phase(2)


@pytest.mark.parametrize("expr,expected", [
    ("faction_density >= 2", [("faction_density", ">=", "2")]),
    ("ammo>=1", [("ammo", ">=", "1")]),
    ("  hostile_human<=6 ", [("hostile_human", "<=", "6")]),
    ("entity_type = faction and start_trust >= 4", [("entity_type", "=", "faction"), ("start_trust", ">=", "4")]),
    ("hostile_human >= 8 and faction_density <= 1 and social_order <= 1 and entity_type = none",
     [("hostile_human", ">=", "8"), ("faction_density", "<=", "1"), ("social_order", "<=", "1"), ("entity_type", "=", "none")]),
    ("days_since_fall != 400", [("days_since_fall", "!=", "400")]),
    ("water == 3 and food < 2 and meds > 0", [("water", "==", "3"), ("food", "<", "2"), ("meds", ">", "0")]),
])
def test_valid_expressions(expr, expected):
    assert parse(expr) == expected


@pytest.mark.parametrize("expr", [
    "",                                   # nothing
    "ammo >> 1",                          # not an operator
    "bogus_name >= 1",                    # not a world parameter
    "entity_type = martians",             # not faction/group/none
    "ammo >= one",                        # not a whole number
    "ammo >= -1",                         # no sign
    "ammo = 1",                           # single '=' is only for entity_type
    "entity_type == faction",             # entity_type uses '='
    "ammo >= 1 or food >= 2",             # no 'or'
    "(ammo >= 1)",                        # no parentheses
    "ammo >= 1 and",                      # dangling 'and'
    "ammo >= 1 AND food >= 1",            # 'and' is lower case
    "ammo >= 1 food >= 1",                # missing 'and'
    "difficulty >= 2",                    # an enum, not an integer parameter
    "key_resource = water",               # a string parameter
])
def test_invalid_expressions_raise(expr):
    with pytest.raises(ConditionSyntaxError) as ei:
        parse(expr)
    assert ei.value.rule == "CNT-09"


def test_name_table_is_the_integer_world_parameters():
    """CONDITION_NAMES = every integer field of WorldParams (+ days_since_fall) and start_trust."""
    must = {"faction_density", "hostile_human", "social_order", "ammo", "days_since_fall", "start_trust",
            "zombie_common", "lurker_pressure", "recovery_slack", "climate_heat"}
    assert must <= CONDITION_NAMES
    assert not ({"difficulty", "era", "key_resource", "hazard_type", "climate_descriptor"} & CONDITION_NAMES)


def test_every_core_expression_parses(canon):
    exprs = []
    for pc in canon.all("pc"):
        exprs += list(pc.plausibility_gate.pass_any)
        if pc.plausibility_gate.hard_fail_all:
            exprs.append(pc.plausibility_gate.hard_fail_all)
    for f in canon.all("faction"):
        exprs += list(f.presence.presence_conditions)
    assert len(exprs) >= 8
    for e in exprs:
        assert parse(e)
