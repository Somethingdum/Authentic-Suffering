"""Out cold (D-173). Rules OUT-01 (physical/bodies.py progress step 1, the death test, comes_to_at; contracts
HarmRules.blood_regain_pct_per_h / blood_regain_after_min) and OUT-02 (turn/intake.py, turn/pipeline.py S6,
service/view.py suggestions).

Losing a third of your blood puts you out. Nothing ever gave blood back, so nobody who went out ever came to — and
when it was the player's character, every turn after failed outright ("empty affordance set"): the game was over
without the character being dead. Now the body makes blood back once the bleeding has stopped, a person out cold
comes to when enough is back, and while the character is out the player's turns let the time pass around him.
"""

from __future__ import annotations

import pytest
from slice_kit import play

from as_engine.contracts.common import Anatomy, CallClass, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.physical import bodies
from as_engine.physical.bodies import WoundSpec
from as_engine.service.view import build_view

pytestmark = pytest.mark.phase(7)

H = 3_600_000


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def state(w, who):
    return tuple(w.store.query_one("SELECT awareness, posture FROM bodies WHERE body_id = ?", (w.id(who),)))


def out_cold(w, who, blood, *, wounded_h_ago=3, bleeding=False):
    """``who`` took a deep cut ``wounded_h_ago`` hours ago and lies out cold with ``blood`` % of their blood lost."""
    t = now(w)
    with w.store.transaction() as tx:
        why = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=0, payload={"what": "test"}))
        bodies.apply_harm(tx, w.id(who), WoundSpec(Anatomy.ARM_L, WoundType.CUT, WoundSeverity.SEVERE), t, why.event_id, 0, w.rng)
    w.store.conn.execute("UPDATE wounds SET created_at = ?, clotted = ? WHERE body_id = ?",
                         (t - wounded_h_ago * H, 0 if bleeding else 1, w.id(who)))
    w.store.conn.execute("UPDATE bodies SET awareness = 'unconscious', posture = 'lying', blood_loss_pct = ?, progressed_at = ? "
                         "WHERE body_id = ?", (blood, t, w.id(who)))
    return t


def test_june_comes_to(scenario):
    """OUT-01: 32 % lost, the bleeding long stopped: at half a percent an hour she is under 30 % in four hours."""
    w = scenario("metal_fence")
    t = out_cold(w, "june", 32.0)
    with w.store.transaction() as tx:
        came = bodies.comes_to_at(tx, w.id("june"), t)
        assert came == t + 4 * H + 1000
        evs = bodies.progress(tx, w.id("june"), t + 5 * H, 0, w.rng)
    up = [e for e in evs if e.type == EventType.AWARENESS_CHANGE]
    assert [(e.at, e.payload["awareness"], e.payload["from"]) for e in up] == [(came, "awake", "unconscious")]
    assert state(w, "june") == ("awake", "lying"), "she comes to where she lay"
    lost = w.store.query_one("SELECT blood_loss_pct FROM bodies WHERE body_id = ?", (w.id("june"),))[0]
    assert lost == pytest.approx(32.0 - 0.5 * 5), "and the blood keeps coming back"


def test_not_while_she_bleeds_or_just_hurt(scenario):
    w = scenario("metal_fence")
    t = out_cold(w, "june", 31.0, bleeding=True)
    with w.store.transaction() as tx:
        assert bodies.comes_to_at(tx, w.id("june"), t) is None, "still bleeding: she is going the other way"
    w.store.conn.execute("UPDATE wounds SET clotted = 1, created_at = ? WHERE body_id = ?", (t, w.id("june")))
    with w.store.transaction() as tx:
        assert bodies.comes_to_at(tx, w.id("june"), t) == t + H + 2 * H + 1000, "nothing comes back in the first hour"
        bodies.progress(tx, w.id("june"), t + 30 * 60_000, 0, w.rng)
    assert w.store.query_one("SELECT blood_loss_pct FROM bodies WHERE body_id = ?", (w.id("june"),))[0] == 31.0


def test_the_player_s_turns_let_the_time_pass(scenario, fake):
    """OUT-02: whatever the player sends while Owen is out, no model is asked what it means, Owen does nothing,
    and the time passes until he comes to."""
    w = scenario("metal_fence")
    s = w.session()
    t = out_cold(w, "pc", 31.0)
    for _ in range(4):
        out = play(s, "do", "I get up and grab my gun.")
        assert out.ok, out
        if state(w, "pc")[0] != "unconscious":
            break
    assert state(w, "pc") == ("awake", "lying")
    assert now(w) >= t + 2 * H, "one percent back at half a percent an hour"
    assert fake.calls(CallClass.INTAKE) == [], "nothing the player sent was read while he was out"
    assert not w.store.query("SELECT 1 FROM events WHERE type = 'ACTION_START' AND actor_id = ?", (s.pc_id,))
    told = [ln.text for ln in fake.calls(CallClass.NARRATION)[-1].context.lines]
    assert "Owen came to." in told, told


def test_the_one_chip(scenario, fake):
    w = scenario("metal_fence")
    s = w.session()
    out_cold(w, "pc", 33.0)
    with w.store.transaction() as tx:
        v = build_view(tx, s)
    assert [(x.ref, x.label, x.mode) for x in v.suggestions] == [("s1", "Let the time pass", "do")]
    assert play(s, "do", "", suggestion_ref="s1").ok
