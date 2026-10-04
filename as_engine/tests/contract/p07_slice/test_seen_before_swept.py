"""What was seen is known before the world answers it (D-120). turn/pipeline.py S10 (perceive, then
sweep), S11's timers and S12 (the window's last progress seen, propagated and swept); the rules that
read who saw what: CAS-012 (theft_witnesses_of), CAS-019 (witnesses_of), CAS-025 (onlookers_of).

Until D-120 a wave's cascade swept its events before anyone had perceived them, so every rule that
asks who saw it found nobody in a real turn — they worked only in tests that granted the percepts by
hand first. And what the window's last progress did — a death from bleeding, a need's next stage —
was never swept at all: nobody was strained by the death they watched, nobody blamed the one who
cut her. These run whole turns.
"""

from __future__ import annotations

import copy

import pytest
from slice_kit import pick, play

from as_engine.contracts.common import CallClass
from as_engine.contracts.events import Event, EventType
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(7)

YARD = {
    "schema": "as.scenario.v1", "name": "stall_yard", "seed": 41, "start": {"day": 400, "time": "12:00"},
    "places": [{"id": "yard", "name": "Market yard", "kind": "outdoor", "indoor": False, "material": "open_air",
                "width_m": 30, "depth_m": 20, "light": 3,
                "anchors": [{"id": "stall", "name": "stall", "x": 10, "y": 10}, {"id": "well", "name": "well", "x": 12, "y": 10},
                            {"id": "gate", "name": "gate", "x": 14, "y": 10}, {"id": "bench", "name": "bench", "x": 10, "y": 13}]}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "yard", "anchor": "gate"},
        {"id": "dale", "dossier": "core:actor/dale_pruitt", "place": "yard", "anchor": "stall"},
        {"id": "june", "dossier": "core:actor/june_okafor", "place": "yard", "anchor": "well"},
        {"id": "nita", "dossier": "core:actor/nita_reyes", "place": "yard", "anchor": "bench"},
    ],
    "items": [{"item": "core:item/jerky_pack", "place": "yard", "anchor": "stall", "label": "jerky"}],
    "beliefs": [
        {"holder": "june", "subject_type": "object", "subject": "jerky", "predicate": "owner", "value": "dale",
         "text": "The jerky on the stall is Dale's.", "confidence": 3, "provenance": "witnessed"},
    ],
}


@pytest.fixture
def yard(fixture_packs, core_pack_dir, fake):
    w = load_scenario(copy.deepcopy(YARD), packs_root=fixture_packs, core_pack_dir=core_pack_dir, transport=fake)
    yield w
    w.store.close()


def holds(w, who, about, claim):
    return bool(w.store.query(
        "SELECT 1 FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id WHERE h.holder_id = ? AND "
        "h.superseded_by IS NULL AND p.subject_id = ? AND p.predicate = ?", (w.id(who), w.id(about), claim)))


def cited(w, rule, turn):
    return [r[0] for r in w.store.query("SELECT actor_id FROM events WHERE rule_cited = ? AND turn_index = ? ORDER BY seq",
                                        (rule, turn))]


def test_a_theft_in_a_real_turn_is_seen_before_it_is_answered(yard, fake):
    """The wave: Owen takes Dale's jerky from the stall with June watching; she carries it out of the turn."""
    w = yard
    s = w.session()
    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "pick_up_item", target="jerky"), "none_reason": None,
                                            "manner": "", "remainder": None, "clarify": None})
    out = play(s, "do", "I take the jerky off the stall.")
    assert out.ok
    taken = w.store.query_one("SELECT event_id, turn_index FROM events WHERE type = 'ITEM_TRANSFER' AND actor_id = ?",
                              (w.id("pc"),))
    assert taken is not None, "he took it"
    assert w.store.query("SELECT 1 FROM percept_log WHERE holder_id = ? AND event_id = ? AND fidelity IN ('exact','partial')",
                         (w.id("june"), taken[0])), "June saw it"
    assert holds(w, "june", "pc", "took_what_was_not_theirs"), \
        "CAS-012 found her: she saw it before the world answered it, and she knows whose it was"
    assert not holds(w, "nita", "pc", "took_what_was_not_theirs"), "Nita saw it but has no idea whose it was"


def test_a_death_at_the_window_s_end_is_seen_and_answered(scenario, fake):
    """S12: Owen cut Alice before the moment; she bleeds out as it ends, in the light, in front of Mara."""
    w = scenario("metal_fence")
    s = w.session()
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=0, actor_id=w.id("pc"),
                                  payload={"what": "test"}))
        bodies.apply_harm(tx, w.id("alice"), WoundSpec("arm_l", "cut", "severe", 0), t, c.event_id, 0, s.rng)
    w.store.conn.execute("UPDATE bodies SET blood_loss_pct = 39.9 WHERE body_id = ?", (w.id("alice"),))
    trust = w.store.query_one("SELECT trust FROM relationships WHERE from_id = ? AND to_id = ?", (w.id("mara"), w.id("pc")))
    trust = trust[0] if trust else 0
    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "wait_here"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    assert play(s, "do", "I wait.").ok
    death = w.store.query_one("SELECT event_id, turn_index FROM events WHERE type = 'DEATH' AND target_ids LIKE ?",
                              (f'%{w.id("alice")}%',))
    assert death is not None and death[1] == 1, "she died as the moment ended"
    assert w.store.query("SELECT 1 FROM percept_log WHERE holder_id = ? AND event_id = ? AND fidelity IN ('exact','partial')",
                         (w.id("mara"), death[0])), "Mara saw her go down"
    assert w.id("mara") in cited(w, "CAS-019", 1), "seeing it strains her"
    now_trust = w.store.query_one("SELECT trust FROM relationships WHERE from_id = ? AND to_id = ?", (w.id("mara"), w.id("pc")))[0]
    assert now_trust == max(-3, trust - 2), "she saw who did it (CAS-025)"
    assert holds(w, "mara", "pc", "killed_someone")


def test_off_screen_what_the_body_did_is_answered_too(scenario):
    """turn.timers.run_offscreen: she bleeds out while nobody is deciding. Nobody perceives off-screen,
    so nobody is strained by seeing it — but he still carries it (CAS-026)."""
    from as_engine.turn import timers
    w = scenario("metal_fence")
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=0, actor_id=w.id("pc"),
                                  payload={"what": "test"}))
        bodies.apply_harm(tx, w.id("alice"), WoundSpec("arm_l", "cut", "severe", 0), t, c.event_id, 0, w.rng)
    w.store.conn.execute("UPDATE bodies SET blood_loss_pct = 39.9 WHERE body_id = ?", (w.id("alice"),))
    owen = w.store.query_one("SELECT stress FROM actors WHERE actor_id = ?", (w.id("pc"),))[0]
    with w.store.transaction() as tx:
        timers.run_offscreen(tx, w.rng, t + 3_600_000, 0)
    assert w.store.query_one("SELECT alive FROM bodies WHERE body_id = ?", (w.id("alice"),))[0] == 0
    assert w.store.query("SELECT 1 FROM events WHERE rule_cited = 'CAS-026'"), "the death was swept"
    assert w.store.query_one("SELECT stress FROM actors WHERE actor_id = ?", (w.id("pc"),))[0] == min(10, owen + 2)
    assert not w.store.query("SELECT 1 FROM events WHERE rule_cited IN ('CAS-019', 'CAS-025')"), "nobody saw it"
