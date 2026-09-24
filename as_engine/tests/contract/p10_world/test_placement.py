"""Faction and group placement, the plausibility gate and the hard-fail protocol (P10, WG0 steps 9-12).
Rules WG-10..14 (world/worldgen/placement.py). CMG §61 Parts X and XII carried.

Where the player's character stands with the powers of the world is decided by code from the
character's start type and the world's numbers; a start the character cannot survive is patched,
and when even the patch cannot save it (at Bitch Mode .. Realism) the world is refused, not faked.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import Difficulty, Era
from as_engine.contracts.dossier import WorldgenBias
from as_engine.contracts.worldgen import Placement
from as_engine.kernel.rng import Rng
from as_engine.world.worldgen import atlas, params, placement, tables

pytestmark = pytest.mark.phase(10)

MAFIA = "core:faction/mafia_remnants"
STREAM = "worldgen:placement"


@pytest.fixture
def base_params(store):
    """A world to edit: seed 5, Normal, Mature."""
    with store.transaction() as tx:
        p, _ = params.generate_params(Rng(5), tx, Difficulty.NORMAL, Era.MATURE, WorldgenBias(), 2000)
    return p


def edit(p, **changes):
    """WorldParams with some block values replaced (a test's own world)."""
    blocks = {}
    for name, value in changes.items():
        if name == "days_since_fall":
            p = p.model_copy(update={"days_since_fall": value})
            continue
        for b in ("a", "b", "c", "d", "e", "sim"):
            if name in type(getattr(p, b)).model_fields:
                blocks.setdefault(b, {})[name] = value
                break
        else:
            raise KeyError(name)
    return p.model_copy(update={b: getattr(p, b).model_copy(update=u) for b, u in blocks.items()})


def pc(canon, name, **changes):
    rec = canon.get(f"core:pc/{name}")
    return rec.model_copy(update=changes) if changes else rec


def draws(store):
    return [r["purpose"] for r in store.query("SELECT purpose FROM prng_ledger WHERE stream = ? ORDER BY seq", (STREAM,))]


def place(store, canon, values, who):
    with store.transaction() as tx:
        return placement.place(Rng(3), tx, values, who, canon)


def test_wg10_eligible_factions(canon, base_params):
    """WG-10: a faction is eligible when ALL its presence conditions hold (kind 'faction' only)."""
    v = params.flat_values(edit(base_params, days_since_fall=500, faction_density=3, social_order=2))
    assert [ref for ref, _ in placement.eligible_factions(canon, v)] == [MAFIA]
    for change in ({"days_since_fall": 399}, {"faction_density": 2}, {"social_order": 1}):
        v = params.flat_values(edit(base_params, **({"days_since_fall": 500, "faction_density": 3, "social_order": 2} | change)))
        assert placement.eligible_factions(canon, v) == [], change


@pytest.mark.parametrize("density, presence", [(6, "dominant"), (4, "active"), (3, "active")])
def test_wg11_inside_a_faction(store, canon, base_params, density, presence):
    """always_in_faction: the faction, the strongest presence the density allows, ally trust."""
    v = params.flat_values(edit(base_params, faction_density=density, social_order=6))
    ruth = pc(canon, "ruth_castillo")
    got = place(store, canon, v, ruth)
    assert (got.entity_type, got.faction_id, got.faction_presence, got.start_relationship) == ("faction", MAFIA, presence, "ally")
    assert got.group_descriptor is None
    lo, hi = max(7, ruth.start_constraints.start_trust_range[0]), min(10, ruth.start_constraints.start_trust_range[1])
    assert lo <= got.start_trust <= hi
    assert draws(store) == ["faction", "start_trust"]


def test_wg11_inside_a_faction_that_is_not_here(store, canon, base_params):
    """always_in_faction with nothing eligible: entity 'faction' without a faction (QC-2 decides)."""
    v = params.flat_values(edit(base_params, social_order=1))
    got = place(store, canon, v, pc(canon, "ruth_castillo"))
    assert (got.entity_type, got.faction_id, got.faction_presence) == ("faction", None, None)
    assert draws(store) == ["start_trust"]


def test_wg11_adjacent(store, canon, base_params):
    """usually_adjacent: a faction when one is eligible and density >= 3, else a local group."""
    addison = pc(canon, "addison_flores")
    got = place(store, canon, params.flat_values(edit(base_params, faction_density=5, social_order=5)), addison)
    assert (got.entity_type, got.faction_id, got.faction_presence, got.start_relationship) == ("faction", MAFIA, "active", "neutral")
    assert 4 <= got.start_trust <= 6
    store2 = store
    before = len(draws(store2))
    got = place(store2, canon, params.flat_values(edit(base_params, faction_density=2)), addison)
    assert (got.entity_type, got.faction_id, got.start_relationship) == ("group", None, "neutral")
    assert got.group_descriptor and 4 <= got.start_trust <= 6
    assert draws(store2)[before:] == ["dynamic", "location", "rule", "start_trust"]


def test_wg11_adjacent_that_prefers_no_faction(store, canon, base_params):
    addison = pc(canon, "addison_flores")
    addison = addison.model_copy(update={"start_constraints": addison.start_constraints.model_copy(
        update={"faction_present_preferred": "no"})})
    got = place(store, canon, params.flat_values(edit(base_params, faction_density=7)), addison)
    assert got.entity_type == "group"


@pytest.mark.parametrize("density, entity", [(2, "group"), (1, "none")])
def test_wg11_alone(store, canon, base_params, density, entity):
    """outsider_solo: a local group when there is any structure to speak of, else nobody."""
    got = place(store, canon, params.flat_values(edit(base_params, faction_density=density)), pc(canon, "owen_marsh"))
    assert got.entity_type == entity
    if entity == "none":
        assert (got.start_relationship, got.start_trust, got.faction_id, got.group_descriptor) == ("none", None, None, None)
        assert draws(store) == []
    else:
        assert got.start_relationship == "neutral" and 4 <= got.start_trust <= 6


def test_wg11_tied_from_the_outside(store, canon, base_params):
    """outsider_tied: the faction at peripheral presence when one is eligible, else nobody."""
    tied = pc(canon, "addison_flores", faction_start_type="outsider_tied")
    got = place(store, canon, params.flat_values(edit(base_params, faction_density=7, social_order=5)), tied)
    assert (got.entity_type, got.faction_id, got.faction_presence) == ("faction", MAFIA, "peripheral")
    got = place(store, canon, params.flat_values(edit(base_params, social_order=1)), tied)
    assert got.entity_type == "none"


def test_wg11_the_same_draws_give_the_same_placement(canon, base_params):
    from as_engine.kernel.store import Store

    v = params.flat_values(edit(base_params, faction_density=2))
    out = []
    for _ in range(2):
        s = Store.memory(run_id="t", seed=1, start_ms=0)
        out.append(place(s, canon, v, pc(canon, "addison_flores")))
        s.close()
    assert out[0] == out[1]


def test_wg12_descriptor(store):
    """WG-12: [dynamic] [location type] [rule], at most 60 characters, cut at a word."""
    with store.transaction() as tx:
        rng = Rng(11)
        texts = [placement.descriptor(rng, tx, hostile=False) for _ in range(20)]
        hostile = [placement.descriptor(rng, tx, hostile=True) for _ in range(10)]
    for t in texts:
        assert len(t) <= 60 and not t.endswith(" ")
        assert any(t.startswith(d + " ") for d in atlas.GROUP_DYNAMICS)
        assert any(f" {loc}" in t for loc in atlas.GROUP_LOCATIONS)
    for t in hostile:
        assert any(t.startswith(d + " ") for d in atlas.HOSTILE_DYNAMICS)
        assert any(f" {loc}" in t for loc in atlas.HOSTILE_LOCATIONS)
    assert draws(store)[:3] == ["dynamic", "location", "rule"]


def P(entity, trust=5, faction=None, presence=None, rel="neutral"):
    return Placement(entity_type=entity, faction_id=faction, faction_presence=presence,
                     group_descriptor="Quiet market collective that owes no one" if entity == "group" else None,
                     start_trust=None if entity == "none" else trust, start_relationship="none" if entity == "none" else rel)


def test_wg13_plausibility(canon, base_params):
    """WG-13 (QC-2 sub-question 1)."""
    owen, ruth, addison = pc(canon, "owen_marsh"), pc(canon, "ruth_castillo"), pc(canon, "addison_flores")
    v = params.flat_values(edit(base_params, ammo=1))
    assert placement.plausibility(v, P("none"), owen) == "pass"
    assert placement.plausibility(params.flat_values(edit(base_params, ammo=0)), P("none"), owen) == "fail"
    assert placement.plausibility(v, P("faction", 7, MAFIA, "active", "ally"), ruth) == "pass"
    assert placement.plausibility(v, P("faction", 4, MAFIA, "active", "ally"), ruth) == "fail"
    assert placement.plausibility(v, P("group", 7), ruth) == "hard_fail", "the faction protection rule"
    assert placement.plausibility(v, P("faction", 7, None, None, "ally"), ruth) == "hard_fail", "inside no faction"
    hopeless = params.flat_values(edit(base_params, hostile_human=9, faction_density=1, social_order=1))
    assert placement.plausibility(hopeless, P("none"), addison) == "hard_fail"
    assert placement.plausibility(hopeless, P("group", 5), addison) != "hard_fail"


def qc(store, canon, p, where, who, difficulty="normal", given=()):
    with store.transaction() as tx:
        return placement.qc(Rng(4), tx, p, where, who, canon, Difficulty(difficulty), list(given))


def test_wg14_a_soft_fail_is_patched_and_kept(store, canon, base_params):
    """Part XII: density raised to 2, a procedural group for a PC with nobody, the soft fail recorded."""
    p = edit(base_params, ammo=0, faction_density=1)
    r = qc(store, canon, p, P("none"), pc(canon, "owen_marsh"), given=["#10: tech_baseline 7->6"])
    assert r.result == "patched"
    assert r.patches == ["#10: tech_baseline 7->6", "QC-2: faction_density 1->2", "QC-2: procedural group added",
                         "QC-2: soft fail kept"]
    assert r.params.b.faction_density == 2 and r.params.d == p.d, "only the density changes"
    assert (r.placement.entity_type, r.placement.start_relationship) == ("group", "neutral")
    assert r.placement.group_descriptor and 4 <= r.placement.start_trust <= 6


def test_wg14_nothing_is_patched_above_realism(store, canon, base_params):
    """QC-2 is enforced at Bitch Mode .. Realism only."""
    p = edit(base_params, ammo=0, faction_density=1)
    r = qc(store, canon, p, P("none"), pc(canon, "owen_marsh"), difficulty="actually_hell")
    assert (r.result, r.patches, r.placement.entity_type, r.params) == ("pass", [], "none", p)


def test_wg14_a_hard_fail_is_placed_again(store, canon, base_params):
    """A faction-protected PC placed outside a faction is placed again; inside one it passes."""
    p = edit(base_params, faction_density=6, social_order=6, days_since_fall=2000)
    r = qc(store, canon, p, P("group", 7), pc(canon, "ruth_castillo"))
    assert r.patches == ["QC-2: placed again"]
    assert r.result == "patched" and r.placement.entity_type == "faction" and r.placement.faction_id == MAFIA
    assert r.placement.start_relationship == "ally" and 7 <= r.placement.start_trust <= 8


def test_wg14_a_hopeless_start_is_refused(store, canon, base_params):
    """No faction to be inside, even after the patch: aborted, nothing else runs."""
    p = edit(base_params, faction_density=1, social_order=1)
    r = qc(store, canon, p, P("faction", 7, None, None, "ally"), pc(canon, "ruth_castillo"))
    assert r.result == "aborted"
    assert r.patches == ["QC-2: faction_density 1->2", "QC-2: placed again"]


def test_wg14_the_same_start_at_fuck_you_goes_ahead(store, canon, base_params):
    p = edit(base_params, faction_density=1, social_order=1)
    r = qc(store, canon, p, P("faction", 7, None, None, "ally"), pc(canon, "ruth_castillo"), difficulty="fuck_you")
    assert r.result == "pass"


def test_wg14_qc3_density_and_trust(store, canon, base_params):
    """QC-3: a presence the density cannot carry raises the density; trust outside its range is clamped."""
    p = edit(base_params, faction_density=4, social_order=6)
    r = qc(store, canon, p, P("faction", 3, MAFIA, "dominant", "ally"), pc(canon, "ruth_castillo"), difficulty="fuck_you")
    assert r.patches == ["QC-3: faction_density 4->6", "QC-3: start_trust 3->7"]
    assert r.result == "patched" and r.params.b.faction_density == 6 and r.placement.start_trust == 7


def test_presence_table_is_the_canon_one():
    """Part X tables are carried verbatim (a canon change is a DECISIONS entry first)."""
    assert tables.PRESENCE_MIN_DENSITY == {"dominant": 6, "active": 3, "peripheral": 1}
    assert tables.START_TYPE_PRESENCE["outsider_tied"] == ("peripheral",)
    assert tables.QC2_ENFORCED == (Difficulty.BITCH_MODE, Difficulty.EASY, Difficulty.NORMAL, Difficulty.REALISM)
