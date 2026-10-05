"""A friend of yours (D-221). action/cascade.py LOOP_OPENED '{whom}' (the D-221 note).

Every grudge for a wrong done to someone the holder is bonded to read "{whom}, someone you love" — and bonded is
affection 1, which a friend is, and which one kindness from a stranger earns. "Ray shoved Cal, someone you love, to
the dead" was said of a man June had shared a meal with. Now love is affection 2 or one household; a friend is a
friend of yours.
"""

from __future__ import annotations

import copy

import pytest
from test_fed_to_the_dead import SHOVE, STREET, loops, now, shove, sweep

from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(9)


@pytest.mark.parametrize("affection, words", [(1, "Ray shoved Cal, a friend of yours, to the dead."),
                                              (2, "Ray shoved Cal, someone you love, to the dead.")])
def test_a_friend_or_a_loved_one(fixture_packs, core_pack_dir, affection, words):
    spec = copy.deepcopy(STREET)
    spec["relationships"][0]["affection"] = affection
    w = load_scenario(spec, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
    try:
        t = now(w)
        start = shove(w, t)
        sweep(w, start, SHOVE, t + 2000)
        assert words in loops(w, "june"), loops(w, "june")
    finally:
        w.store.close()
