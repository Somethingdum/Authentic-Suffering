"""Word gets around (D-216). action/cascade.py heard_it; core CAS-018, CAS-028, CAS-048 and CAS-091..CAS-102.

The owner: "If I treat them like shit, or do something just absolutely evil. I do expect reactions, and proper
ones." Whoever saw a wrong told it (create_rumour), and the story moved through the settlement — and whoever heard
it, from someone they believed, thought no less of the one it was about, unless it was a theft, a killing or eating
the dead. Pushing someone to the dead, killing a man who was tied, hurting a child, spitting in the water: heard
and shrugged off. Now every story of a wrong costs its subject the believer's trust (never more than seeing it
would), and nothing heard is written into the player's character (C06).
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.world import rumours

from society_kit import accident, now, rel

pytestmark = pytest.mark.phase(9)

HEARD = [
    ("hurt_someone", "CAS-091", {"trust": -1}),
    ("tried_to_kill_someone", "CAS-092", {"trust": -1}),
    ("shut_someone_out", "CAS-093", {"trust": -1}),
    ("fed_someone_to_the_dead", "CAS-094", {"trust": -2}),
    ("beat_a_captive", "CAS-095", {"trust": -1}),
    ("killed_a_captive", "CAS-096", {"trust": -1}),
    ("hit_one_who_gave_up", "CAS-097", {"trust": -1}),
    ("killed_one_who_gave_up", "CAS-098", {"trust": -1}),
    ("hurt_a_child", "CAS-099", {"trust": -1}),
    ("left_their_child", "CAS-100", {"trust": -1}),
    ("spat_in_a_mouth", "CAS-101", {"trust": -1, "fear": 1}),
    ("spoiled_the_food", "CAS-102", {"trust": -1, "fear": 1}),
    ("killed_someone", "CAS-028", {"trust": -2}),
    ("ate_the_dead", "CAS-048", {"trust": -2}),
    ("took_what_was_not_theirs", "CAS-018", {"trust": -1}),
]


def seed(w, holder, about, claim):
    with w.store.transaction() as tx:
        cause = accident(tx, now(w), "something seen")
        return rumours.seed(tx, w.id(holder), w.id(about), claim, now(w), 0, cause.event_id, confidence=3)


def tell(w, rid, teller, listener):
    with w.store.transaction() as tx:
        rs = rumours.spread_one(tx, rid, w.id(teller), w.id(listener), now(w), 0, None)
        return rs, cascade.sweep(tx, [rs], tx.canon.all("cascade"), now(w), 0)


def axes(w, a, b):
    r = rel(w, a, b)
    return {"trust": 0, "fear": 0} if r is None else {"trust": r["trust"], "fear": r["fear"]}


@pytest.mark.parametrize("claim, rule, cost", HEARD)
def test_heard_from_someone_she_believes(settle, claim, rule, cost):
    """Finn saw Jude do it; he tells Kit, who believes him."""
    w = settle
    rid = seed(w, "finn", "jude", claim)
    before = axes(w, "kit", "jude")
    rs, made = tell(w, rid, "finn", "kit")
    assert rs.payload["believed"] is True
    after = axes(w, "kit", "jude")
    assert {k: after[k] - before[k] for k in cost} == cost
    assert {e.rule_cited for e in made if e.type == "RELATION_CHANGE"} == {rule}
    assert axes(w, "finn", "jude") == {"trust": 0, "fear": 0}, "the one who saw it is not changed by the telling (hops 0)"


def test_not_from_someone_she_distrusts(settle):
    """Amos does not believe Jude (trust -2): Jude's story about Vera costs her nothing with him."""
    w = settle
    rid = seed(w, "jude", "vera", "fed_someone_to_the_dead")
    before = axes(w, "amos", "vera")
    rs, made = tell(w, rid, "jude", "amos")
    assert rs.payload["believed"] is False
    assert axes(w, "amos", "vera") == before and not [e for e in made if e.type == "RELATION_CHANGE"]


@pytest.mark.parametrize("claim", ["fed_someone_to_the_dead", "killed_someone", "took_what_was_not_theirs"])
def test_never_written_into_the_player_character(settle, claim):
    """Finn tells Owen. Owen hears it — what he makes of it is his."""
    w = settle
    rid = seed(w, "finn", "jude", claim)
    rs, made = tell(w, rid, "finn", "pc")
    assert rs.payload["listener_id"] == w.id("pc")
    assert rel(w, "pc", "jude") is None and not [e for e in made if e.type == "RELATION_CHANGE"]
    with w.store.transaction() as tx:
        assert cascade.select(tx, "heard_it(trigger.event_id)", rs) == []
