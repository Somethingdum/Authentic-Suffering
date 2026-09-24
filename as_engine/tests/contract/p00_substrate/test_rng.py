"""The single entropy door (P0). Rules DET-10, DET-11 (AST part lives in test_boundaries)."""

from __future__ import annotations

import pytest

from as_engine.kernel.rng import Rng, bounded, derive_state, encode_state, splitmix64, xoshiro_next
from as_engine.kernel.store import Store

pytestmark = pytest.mark.phase(0)


def test_core_matches_reference_algorithms(vectors):
    """DET-10: the implemented core is xoshiro256** / SplitMix64 exactly (reference values)."""
    v = vectors("rng")
    st = tuple(v["reference_xoshiro256ss"]["state"])
    outs = []
    for _ in range(len(v["reference_xoshiro256ss"]["first_outputs"])):
        st, o = xoshiro_next(st)
        outs.append(str(o))
    assert outs == v["reference_xoshiro256ss"]["first_outputs"]
    assert hex(splitmix64(0)[1]) == v["reference_splitmix64_seed0_first"]


def test_core_vectors(vectors):
    """DET-10: derive_state + bounded reproduce the recorded sequences."""
    for case in vectors("rng")["streams"]:
        s = derive_state(case["seed"], case["stream"])
        assert encode_state(s) == case["state"]
        st, d10 = s, []
        for _ in range(12):
            st, x = bounded(st, 10)
            d10.append(x)
        assert d10 == case["d10_first_12"], case["stream"]


def test_rng_draw_reproduces_vectors_and_ledgers(vectors):
    """DET-10: Rng.draw follows the stream sequence, persists state, and writes one prng_ledger row
    per draw (seq contiguous from 1, purpose recorded)."""
    case = next(c for c in vectors("rng")["streams"] if c["seed"] == 1818 and c["stream"] == "resolve")
    s = Store.memory(run_id="r", seed=1818)
    r = Rng(1818)
    got = []
    with s.transaction() as tx:
        for i in range(6):
            got.append(r.d10(tx, "resolve", f"check:test:{i}"))
    with s.transaction() as tx:  # state persisted between transactions
        for i in range(6, 12):
            got.append(r.draw(tx, "resolve", f"check:test:{i}", 10))
    assert got == case["d10_first_12"]
    rows = s.query("SELECT seq, stream, purpose, n, value FROM prng_ledger ORDER BY seq")
    assert [r_["seq"] for r_ in rows] == list(range(1, 13))
    assert rows[0]["purpose"] == "check:test:0" and rows[0]["n"] == 10
    assert [r_["value"] for r_ in rows] == got
    s.close()


def test_streams_are_independent(vectors):
    """DET-10: draws on one stream never shift another stream's sequence."""
    case = next(c for c in vectors("rng")["streams"] if c["seed"] == 1818 and c["stream"] == "resolve")
    s = Store.memory(run_id="r", seed=1818)
    r = Rng(1818)
    with s.transaction() as tx:
        for _ in range(50):
            r.draw(tx, "perception", "noise", 1000)
        first = [r.d10(tx, "resolve", "x") for _ in range(5)]
    assert first == case["d10_first_12"][:5]
    s.close()


def test_state_survives_reopen(tmp_path, vectors):
    """DET-10: the stream state lives in rng_streams, so a reload continues the same sequence."""
    case = next(c for c in vectors("rng")["streams"] if c["seed"] == 1818 and c["stream"] == "resolve")
    p = tmp_path / "w.sqlite"
    s = Store.create(p, run_id="r", seed=1818)
    with s.transaction() as tx:
        a = [Rng(1818).d10(tx, "resolve", "x") for _ in range(4)]
    s.close()
    s = Store.open(p)
    with s.transaction() as tx:
        b = [Rng(1818).d10(tx, "resolve", "x") for _ in range(4)]
    s.close()
    assert a + b == case["d10_first_12"][:8]


def test_derived_methods(vectors):
    """DET-10: range_int / chance / choice / weighted / shuffle follow the docstring formulas."""
    dm = vectors("rng")["derived_methods"]
    s = Store.memory(run_id="r", seed=1818)
    r = Rng(1818)
    with s.transaction() as tx:
        assert [r.range_int(tx, "test", "ri", 3, 7) for _ in range(5)] == dm["range_int_3_7_x5"]
        assert [r.chance(tx, "test", "ch", 0.25) for _ in range(5)] == dm["chance_0.25_x5"]
        assert [r.choice(tx, "test", "c", ["a", "b", "c", "d"]) for _ in range(4)] == dm["choice_abcd_x4"]
        assert [r.weighted(tx, "test", "w", [("x", 0.5), ("y", 1.5), ("z", 1.0)]) for _ in range(4)] == dm["weighted_x0.5_y1.5_z1.0_x4"]
        assert r.shuffle(tx, "test", "s", list(range(6))) == dm["shuffle_0_to_5"]
        with pytest.raises(ValueError):
            r.choice(tx, "test", "c", [])
    s.close()
