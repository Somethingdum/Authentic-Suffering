"""A Sandbox twin (P12). Rules CHEAT-02, CHEAT-05 (cheats/commands.py; CHEATS.md §7).

The same night twice. In the twin the Boss spawns Fredrick and a crate of ammunition; then both
worlds live one day on their own. Leave the cheat-made things out, and every world invariant is
the same: a superhuman companion cannot silently re-tune the world.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from as_engine.cheats import commands as cheats
from as_engine.turn import timers

pytestmark = pytest.mark.phase(12)

DAY = 86_400_000
REPO_PACKS = Path(__file__).resolve().parents[4] / "as_content" / "packs"


def invariants(w) -> dict:
    q = w.store.query
    return {
        "living": sorted(tuple(r) for r in q("SELECT kind, COUNT(*) FROM bodies WHERE alive = 1 AND origin != 'cheat' GROUP BY kind")),
        "dead": sorted(tuple(r) for r in q("SELECT kind, COUNT(*) FROM bodies WHERE alive = 0 AND origin != 'cheat' GROUP BY kind")),
        "items": sorted(tuple(r) for r in q("SELECT def_ref, SUM(qty) FROM items WHERE origin != 'cheat' GROUP BY def_ref")),
        "stores": sorted(tuple(r) for r in q("SELECT settlement_id, stores FROM settlements")),
        "standing": sorted(tuple(r) for r in q(
            "SELECT g.group_id, g.actor_id, g.standing FROM group_standing g JOIN bodies b ON b.body_id = g.actor_id "
            "WHERE b.origin != 'cheat'")),
        "clock": tuple(q("SELECT now_ms, weather FROM world_clock")[0]),
    }


def test_a_sandbox_twin_holds_the_same_world(scenario, fake):
    clean, twin = scenario("metal_fence"), scenario("metal_fence")
    s = twin.session()
    s.config = s.config.model_copy(update={"content_dir": str(REPO_PACKS)})
    cheats.activate(s)
    for line in ("/spawn fredrick ally", "/give ammo_38 50"):
        assert asyncio.run(cheats.execute(s, cheats.parse(line))).ok
    assert twin.store.query_one("SELECT value FROM meta WHERE key = 'sandbox'")[0] == "1"
    for w in (clean, twin):
        with w.store.transaction() as tx:
            now = tx.query_one("SELECT now_ms FROM world_clock")[0]
            timers.run_offscreen(tx, w.rng, now + DAY, 0)
    assert invariants(twin) == invariants(clean)
