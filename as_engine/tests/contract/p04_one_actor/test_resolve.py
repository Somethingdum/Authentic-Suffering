"""Resolve pool (P4). Rules RES-01..05 (mind/resolve.py, mind/actor.resolve_max).

Resolve gates what a person can bring themselves to attempt; it never changes a roll.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import Verb
from as_engine.contracts.content import AffordanceDef
from as_engine.contracts.events import EventType
from as_engine.contracts.settings import ResolveRules
from as_engine.mind import resolve
from as_engine.mind.actor import resolve_max

pytestmark = pytest.mark.phase(4)


def cur(w, local):
    return w.store.query_one("SELECT resolve_cur, resolve_max FROM actors WHERE actor_id = ?", (w.id(local),))


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


# --------------------------------------------------------------------------- max
@pytest.mark.parametrize("E,C,mod,base,expected", [
    (5, 6, 0, 3, 5),     # 3 + 11 // 4
    (5, 6, -2, 3, 3),
    (8, 8, 2, 3, 9),     # 3 + 4 + 2
    (1, 1, -2, 0, 1),    # never below 1
])
def test_resolve_max_formula(E, C, mod, base, expected):
    assert resolve_max(E, C, mod, ResolveRules(base=base)) == expected


# --------------------------------------------------------------------------- drain / recover
def test_drain_commits_resolve_change(scenario):
    w = scenario("request_firewall")
    before, mx = cur(w, "mara")
    with w.store.transaction() as tx:
        ev = resolve.drain(tx, w.id("mara"), "coerced", None, now(w), 0)
    assert ev.type == EventType.RESOLVE_CHANGE and ev.writer == "mind.actor"
    assert ev.payload == {"actor_id": w.id("mara"), "reason": "coerced", "delta": -1, "resolve": before - 1}
    assert cur(w, "mara")[0] == before - 1


def test_drain_clamps_at_zero_then_does_nothing(scenario):
    w = scenario("request_firewall")
    with w.store.transaction() as tx:
        for _ in range(10):
            resolve.drain(tx, w.id("mara"), "lost_dependent", None, now(w), 0)
        assert tx.query_one("SELECT resolve_cur FROM actors WHERE actor_id = ?", (w.id("mara"),))[0] == 0
        n = tx.query_one("SELECT COUNT(*) FROM events WHERE type = 'RESOLVE_CHANGE'")[0]
        assert resolve.drain(tx, w.id("mara"), "coerced", None, now(w), 0) is None
        assert tx.query_one("SELECT COUNT(*) FROM events WHERE type = 'RESOLVE_CHANGE'")[0] == n, "no event for no change"


def test_recover_clamps_at_max(scenario):
    w = scenario("request_firewall")
    before, mx = cur(w, "mara")
    with w.store.transaction() as tx:
        assert resolve.recover(tx, w.id("mara"), "safe_night", None, now(w), 0) is None, "already at max"
        resolve.drain(tx, w.id("mara"), "betrayed", None, now(w), 0)
        ev = resolve.recover(tx, w.id("mara"), "protected_dependent", None, now(w), 0)
    assert ev.payload["delta"] == 1 and ev.payload["resolve"] == mx - 1


def test_unknown_reasons_are_errors(scenario):
    w = scenario("request_firewall")
    with w.store.transaction() as tx:
        with pytest.raises(ValueError):
            resolve.drain(tx, w.id("mara"), "bad_day", None, now(w), 0)
        with pytest.raises(ValueError):
            resolve.recover(tx, w.id("mara"), "good_day", None, now(w), 0)




# --------------------------------------------------------------------------- gate (RES-03)
def _def(canon, bare):
    return canon.find("affordance", bare)


def _custom(**over):
    base = {"schema": "as.affordance.v1", "id": "defy_order", "verb": "speak", "label": "Tell them no",
            "ui_label": "Refuse", "binds": "speech", "range": "audible", "duration": {"base_s": 1},
            "noise_db": 0, "effect": "speak", "tags": ["speech", "opposes_authority"]}
    base.update(over)
    return AffordanceDef.model_validate(base)


def test_gate_at_zero(canon):
    """RES-03 at 0 (AC08): fear and impairment, never obedience — they keep their voice, silence,
    their eyes, retreat, cover, hiding, protecting someone and surrender; complying under threat is
    one option among them. What needs nerve they do not have is gone."""
    ok = lambda bare: resolve.gate(0, _def(canon, bare))[0]  # noqa: E731
    assert ok("surrender") and ok("wait_here") and ok("shield_dependent")
    assert ok("speak") and ok("observe_area") and ok("take_cover") and ok("hide")
    assert ok("give_item") or ok("drop_item"), "comply_under_threat defs stay open"
    assert not ok("shoot_center_mass") and not ok("move_to_anchor") and not ok("punch")
    for bare in ("surrender", "wait_here"):
        assert _def(canon, bare).verb in (Verb.SURRENDER, Verb.WAIT)
    low = _def(canon, "move_to_anchor").model_copy(update={"tags": ["low_exposure"]})
    assert resolve.gate(0, low) == (True, None), "an attempt the content marks low_exposure stays open"


def test_gate_at_one_blocks_fear_exposure_only(canon):
    assert resolve.gate(1, _def(canon, "shoot_center_mass")) == (False, None)
    assert resolve.gate(1, _def(canon, "punch"))[0] is False
    assert resolve.gate(1, _def(canon, "observe_area")) == (True, None)
    assert resolve.gate(1, _def(canon, "move_to_anchor")) == (True, None)


def test_gate_at_two_notes_authority():
    assert resolve.gate(2, _custom(), "Ray") == (True, "It means going against Ray.")
    assert resolve.gate(2, _custom()) == (True, "It means going against the people in charge.")
    assert resolve.gate(3, _custom(), "Ray") == (True, None)
    assert resolve.gate(1, _custom(), "Ray") == (True, None)


def test_gate_is_pure(canon, scenario):
    w = scenario("metal_fence")
    n = w.store.query_one("SELECT COUNT(*) FROM events")[0]
    for r in range(5):
        resolve.gate(r, _def(canon, "shoot_center_mass"))
    assert w.store.query_one("SELECT COUNT(*) FROM events")[0] == n, "gate reads and writes nothing"
