"""Two of a kind (D-289). world/worldgen/region.py WG1 site names; atlas.CHURCH_NAMES, atlas.SITE_QUALIFIERS.

The core pack has two kinds of shop, and a highway zone of eight sites is all shops — so a run was played in "the gas
station (2)", "the gas station (3)" and "the corner market (4)", and every mind and every line of narration said so
("Where you are: at the front in the gas station (2)"). A wilds zone drew eight sites from eight outdoor names with
repeats ("a hunting blind (2)"). A second building of a kind is called what people would call it: a shop after the
family that ran it, a hall after its church, anything else by where it stands; a wild place is another wild place
while there are any. The region's own draws are what they were (the region vectors).
"""

from __future__ import annotations

import re

import pytest

from as_engine.contracts.common import Difficulty, Era
from as_engine.contracts.dossier import WorldgenBias
from as_engine.kernel.rng import Rng
from as_engine.kernel.store import Store
from as_engine.mind.perception import place_phrase
from as_engine.world.worldgen import atlas, params, region

pytestmark = pytest.mark.phase(10)


def sites(canon, seed):
    st = Store.memory(run_id="t", seed=1, start_ms=0)
    st.attach(canon=canon)
    rng = Rng(seed)
    with st.transaction() as tx:
        p, _ = params.generate_params(rng, tx, Difficulty.NORMAL, Era.ESTABLISHED, WorldgenBias(), 900)
    with st.transaction() as tx:
        reg = region.build_region(rng, tx, p, "standard", canon, 1000)
    out = [[dict(st.query_one("SELECT name, kind, archetype_ref FROM places WHERE place_id = ?", (s,))) for s in z.site_ids]
           for z in reg.zones]
    st.close()
    return out


def test_no_place_is_numbered(canon):
    fam = set(canon.get(canon.refs("names")[0]).family)
    seconds = {}
    for seed in range(1, 13):
        for zone in sites(canon, seed):
            first = {}
            for s in zone:
                assert not re.search(r" \(\d+\)$", s["name"]), (seed, s["name"])
                assert not re.search(r"\b(the|a|an) (the|a|an)\b", place_phrase(s["name"]), re.IGNORECASE)
                key = s["archetype_ref"]
                if key and key in first:
                    seconds.setdefault(canon.get(key).kind, []).append(s["name"])
                first.setdefault(key, s["name"])
            assert len({s["name"] for s in zone}) == len(zone)
    assert seconds.get("shop"), "a zone with two of a kind of shop was made"
    for name in seconds["shop"]:
        owner, _, rest = name.partition("'s ")
        assert owner in fam and rest in ("Gas Station", "Corner Market"), name
    for name in seconds.get("hall", []):
        assert any(name == f"{c} Church Hall" for c in atlas.CHURCH_NAMES), name
    for name in seconds.get("utility", []):
        assert any(name == f"{q} pump house" for q in atlas.SITE_QUALIFIERS), name
    for name in seconds.get("house", []) + seconds.get("apartment", []):
        assert name.startswith("The ") and name[4:].rsplit(" ", 1)[0] in fam, name
