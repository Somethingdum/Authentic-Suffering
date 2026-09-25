"""Refusals, friction and lies (P6). Rules WILL-05, WILL-06, WILL-07, WILL-11, STORE-11
(mind/firewall.py, refusal part; action/effects.situation for the re-ask penalty).

A refusal is remembered. Asking again is never better: the same ask from the same person is the
same refusal asked one more time, the third ask breeds resentment, and anyone who has refused you
is harder to talk round.
"""

from __future__ import annotations

import json

import pytest

import helpers
from as_engine.action import effects
from as_engine.contracts.events import Event, EventType
from as_engine.mind import firewall

pytestmark = pytest.mark.phase(6)

SIG = "give_item:{pc}"


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def ask(w, words="Hand me the revolver, Mara.", at=None):
    with w.store.transaction() as tx:
        return tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=at or now(w), turn_index=0,
                                     actor_id=w.id("pc"), payload={"words": words, "volume": "normal", "to": [w.id("mara")],
                                                                   "source_db": 60}))


def refuse(w, *, actor="mara", requester="pc", sig=None, summary="hand over the revolver", reason="loyalty",
           entrenched=False, at=None, cause=None):
    sig = sig or SIG.format(pc=w.id("pc"))
    at = at or now(w)
    cause = cause or ask(w, at=at).event_id
    with w.store.transaction() as tx:
        return firewall.record_refusal(tx, w.id(actor), w.id(requester), sig, summary, reason, [cause], "my duty at the window",
                                       entrenched, at, 0, cause)


def row(w, rid):
    r = dict(w.store.query_one("SELECT * FROM refusals WHERE refusal_id = ?", (rid,)))
    r["reason_event_ids"] = json.loads(r["reason_event_ids"])
    return r


def events(w, type_):
    """Events of this type committed after the scenario was loaded (the loader writes its own)."""
    return [dict(r, payload=json.loads(r["payload"])) for r in
            w.store.query("SELECT * FROM events WHERE type = ? AND turn_index >= 0 AND seq > ? ORDER BY seq",
                          (type_, getattr(w, "_p6_base", 0)))]


@pytest.fixture
def scenario(scenario):
    """The shared scenario fixture, remembering where the loaded world's events end."""
    def _load(name, **kw):
        w = scenario(name, **kw)
        w._p6_base = w.store.query_one("SELECT COALESCE(MAX(seq), 0) FROM events")[0]
        return w
    return _load


def rel(w, a, b, axis):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return None if r is None else r[0]


def test_a_refusal_is_recorded(scenario):
    """WILL-07 (new row), STORE-11: created_event is the REFUSAL event itself."""
    w = scenario("metal_fence")
    t = now(w)
    cause = ask(w, at=t)
    rid = refuse(w, at=t, cause=cause.event_id)
    r = row(w, rid)
    (ev,) = events(w, "REFUSAL")
    sig = SIG.format(pc=w.id("pc"))
    assert rid.startswith("ref_")
    assert (r["actor_id"], r["requester_id"], r["request_summary"], r["request_signature"], r["reason_code"],
            r["reason_event_ids"], r["cost_cited"], r["entrenched"], r["expires_when"], r["created_at"], r["times_asked"],
            r["status"]) == (w.id("mara"), w.id("pc"), "hand over the revolver", sig, "loyalty", [cause.event_id],
                             "my duty at the window", 0, "never", t, 1, "standing")
    assert r["created_event"] == ev["event_id"]
    assert (ev["writer"], ev["actor_id"], ev["cause_event_id"]) == ("mind.mind", w.id("mara"), cause.event_id)
    assert ev["payload"] == {"refusal_id": rid, "actor_id": w.id("mara"), "requester_id": w.id("pc"), "signature": sig,
                             "summary": "hand over the revolver", "reason_code": "loyalty", "reason_event_ids": [cause.event_id],
                             "cost_cited": "my duty at the window", "entrenched": False, "times_asked": 1, "repeat": False}
    assert events(w, "RELATION_CHANGE") == [], "a plain refusal changes no feelings"


def test_asking_again_is_the_same_refusal_asked_once_more(scenario):
    """WILL-07: same refuser, same asker, same signature -> the standing row counts up."""
    w = scenario("metal_fence")
    t = now(w)
    first = refuse(w, at=t)
    second = refuse(w, at=t + 1000)
    assert second == first and row(w, first)["times_asked"] == 2
    ev = events(w, "REFUSAL")[-1]
    assert ev["payload"] == {"refusal_id": first, "actor_id": w.id("mara"), "requester_id": w.id("pc"),
                             "signature": SIG.format(pc=w.id("pc")), "times_asked": 2, "entrenched": False, "repeat": True}
    other_sig = refuse(w, sig=f"open_portal:{w.id('front_door')}", summary="open the front door", at=t + 2000)
    other_asker = refuse(w, requester="june", at=t + 3000)
    assert len({first, other_sig, other_asker}) == 3
    assert w.store.query_one("SELECT COUNT(*) FROM refusals")[0] == 3


def test_the_third_ask_breeds_resentment(scenario):
    """WILL-07 friction: resentment +1 on the 3rd and every later ask, citing that REFUSAL."""
    w = scenario("metal_fence")
    t = now(w)
    for i in range(2):
        refuse(w, at=t + i)
    assert rel(w, "mara", "pc", "resentment") == 0
    refuse(w, at=t + 2)
    third = events(w, "REFUSAL")[-1]
    (rc,) = events(w, "RELATION_CHANGE")
    assert rc["cause_event_id"] == third["event_id"] and rc["actor_id"] == w.id("mara")
    assert rc["payload"] == {"from_id": w.id("mara"), "to_id": w.id("pc"), "axis": "resentment", "old": 0, "new": 1, "delta": 1}
    refuse(w, at=t + 3)
    assert rel(w, "mara", "pc", "resentment") == 2 and row(w, events(w, "REFUSAL")[-1]["payload"]["refusal_id"])["times_asked"] == 4


def test_an_unreadable_ask_is_never_a_repeat(scenario):
    """'*:*' cannot be told apart, so each is its own row, with no friction."""
    w = scenario("metal_fence")
    t = now(w)
    ids = [refuse(w, sig="*:*", summary="something she could not follow", at=t + i) for i in range(3)]
    assert len(set(ids)) == 3 and all(row(w, i)["times_asked"] == 1 for i in ids)
    assert events(w, "RELATION_CHANGE") == []


def test_an_ask_that_crosses_a_line_costs_trust_even_when_refused(scenario):
    """WILL-06: a NEW entrenched refusal lowers the refuser's trust in the asker by 1; entrenched
    sticks once set; a later entrenched repeat costs nothing more."""
    w = scenario("metal_fence")
    t = now(w)
    rid = refuse(w, sig=f"abandon_post:{w.id('front_window')}", summary="leave the window", reason="duty", entrenched=True, at=t)
    (rc,) = events(w, "RELATION_CHANGE")
    assert rc["payload"]["axis"] == "trust" and (rc["payload"]["old"], rc["payload"]["new"]) == (1, 0)
    assert rc["cause_event_id"] == events(w, "REFUSAL")[0]["event_id"]
    assert row(w, rid)["entrenched"] == 1
    plain = refuse(w, summary="give me the gun", at=t + 1)
    refuse(w, summary="give me the gun", entrenched=True, at=t + 2)
    assert row(w, plain)["entrenched"] == 1 and len(events(w, "RELATION_CHANGE")) == 1
    refuse(w, summary="give me the gun", entrenched=False, at=t + 3)
    assert row(w, plain)["entrenched"] == 1, "once entrenched, always entrenched"


def test_reason_codes_are_a_closed_list(scenario):
    w = scenario("metal_fence")
    assert firewall.REASON_CODES == ("duty", "dependent", "resource", "fear", "moral", "identity", "loyalty", "cost", "distrust")
    with pytest.raises(ValueError):
        refuse(w, reason="vibes")


@pytest.mark.parametrize("n,penalty", [(1, 0), (2, -1), (3, -2), (5, -4)])
def test_negotiable_target_penalty(n, penalty):
    """WILL-05."""
    assert firewall.negotiable_target_penalty(n) == penalty


def test_negotiable_target_penalty_needs_an_ask():
    with pytest.raises(ValueError):
        firewall.negotiable_target_penalty(0)


def test_someone_who_refused_you_is_harder_to_talk_round(scenario):
    """WILL-05 in action.effects.situation: a 'negotiable' def (calm_person) against a body that
    refused the actor gets the penalty of the most-asked standing refusal; others are unaffected."""
    w = scenario("metal_fence")
    t = now(w)
    calm = helpers.make_intent(w, "pc", "calm_person", target="mara")
    calm_june = helpers.make_intent(w, "june", "calm_person", target="mara")
    with w.store.transaction() as tx:
        base, base_june = effects.situation(tx, calm, t), effects.situation(tx, calm_june, t)
    refuse(w, at=t)
    with w.store.transaction() as tx:
        assert effects.situation(tx, calm, t) == base, "one refusal: penalty 0"
    refuse(w, at=t + 1)
    refuse(w, sig=f"open_portal:{w.id('front_door')}", summary="open the door", at=t + 2)
    with w.store.transaction() as tx:
        assert effects.situation(tx, calm, t) == max(-3, base - 1), "the most-asked refusal counts (2 asks)"
        assert effects.situation(tx, calm_june, t) == base_june, "Mara has refused Owen, not June"
    wait = helpers.make_intent(w, "pc", "watch_target", target="mara")
    with w.store.transaction() as tx:
        assert effects.situation(tx, wait, t) == 0, "not a negotiable def"


def test_false_compliance_is_a_recorded_lie(scenario):
    """WILL-11: LIE_TOLD, caused by the liar's SPEECH; nothing else changes."""
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        sp = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=t, turn_index=0, actor_id=w.id("mara"),
                                   payload={"words": "Sure, I'll come.", "volume": "normal", "to": [w.id("pc")], "source_db": 60}))
        n = w.store.query_one("SELECT COUNT(*) FROM events")[0]
        ev = firewall.record_lie(tx, w.id("mara"), w.id("pc"), f"follow_body:{w.id('pc')}", "Sure, I'll come.", sp.event_id,
                                 t + 10, 0)
    assert (ev.type, ev.writer, ev.actor_id, ev.cause_event_id, ev.at, ev.writes) == \
        (EventType.LIE_TOLD, "mind.mind", w.id("mara"), sp.event_id, t + 10, [])
    assert ev.payload == {"liar_id": w.id("mara"), "to_id": w.id("pc"), "signature": f"follow_body:{w.id('pc')}",
                          "words": "Sure, I'll come."}
    assert w.store.query_one("SELECT COUNT(*) FROM events")[0] == n + 1


# --------------------------------------------------------------------------- WILL-12 / WILL-13 (AC09)
def test_a_person_can_change_their_mind(scenario):
    """WILL-12: asking again is never better — but doing what you refused marks the refusal revised,
    and the row and its history stay."""
    w = scenario("metal_fence")
    t = now(w)
    rid = refuse(w, at=t)
    sig = SIG.format(pc=w.id("pc"))
    with w.store.transaction() as tx:
        ev = firewall.revise_refusal(tx, w.id("mara"), w.id("pc"), sig, t + 60_000, 0, None)
    assert (ev.type, ev.writer, ev.actor_id) == (EventType.REFUSAL_REVISED, "mind.mind", w.id("mara"))
    assert ev.payload == {"refusal_id": rid, "actor_id": w.id("mara"), "requester_id": w.id("pc"), "signature": sig}
    r = row(w, rid)
    assert r["status"] == "revised" and r["times_asked"] == 1 and r["request_summary"] == "hand over the revolver"
    with w.store.transaction() as tx:
        assert firewall.revise_refusal(tx, w.id("mara"), w.id("pc"), sig, t + 70_000, 0, None) is None, "nothing left standing"
        assert firewall.revise_refusal(tx, w.id("june"), w.id("pc"), sig, t + 70_000, 0, None) is None, "June refused nothing"


def test_a_yes_and_something_else_is_recorded_not_judged(scenario):
    """WILL-13: ASSENT_UNMET says what was said and what was done — no lie, no lost trust, no
    resentment manufactured from it."""
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        sp = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=t, turn_index=0, actor_id=w.id("mara"),
                                   payload={"words": "Sure.", "volume": "normal", "to": [w.id("pc")], "source_db": 60}))
    before = (rel(w, "pc", "mara", "trust"), rel(w, "pc", "mara", "resentment"))
    sig = f"follow_body:{w.id('pc')}"
    with w.store.transaction() as tx:
        ev = firewall.record_unmet_assent(tx, w.id("mara"), w.id("pc"), sig, "Sure.", "keep_working", sp.event_id, t + 10, 0)
    assert (ev.type, ev.writer, ev.actor_id, ev.cause_event_id, ev.writes) == \
        (EventType.ASSENT_UNMET, "mind.mind", w.id("mara"), sp.event_id, [])
    assert ev.payload == {"actor_id": w.id("mara"), "to_id": w.id("pc"), "signature": sig, "words": "Sure.",
                          "chosen_def_id": "keep_working"}
    assert events(w, "LIE_TOLD") == [] and (rel(w, "pc", "mara", "trust"), rel(w, "pc", "mara", "resentment")) == before
