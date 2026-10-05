"""Talked about (D-253). mind/temper.py TEMPER-11 (take_in: what was said to their face is their story);
world/rumours.py CLAIM_TEXT / CLAIM_WHOM insulted_someone, threatened_someone; core CAS-113, CAS-114; action/cascade.py
humiliated_by (its own drain does not hide its target from CAS-042's other effects).

The owner: "If I treat them like shit ... I do expect reactions, and proper ones." Insult someone or threaten them to
their face and they held it against you — and that was all: nobody else ever heard of it, so a man could abuse a
whole camp one person at a time and each of the others still took him as they found him. Now it is the story the one
it was done to tells, once, and whoever hears it from someone they believe thinks less of you.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from as_engine.action import cascade
from as_engine.world import rumours

from society_kit import accident, now, rel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "p07_slice"))
from slice_kit import play  # noqa: E402

pytestmark = pytest.mark.phase(9)


def stories(w, holder, about, claim):
    return w.store.query("SELECT r.rumour_id, p.text FROM rumours r JOIN claim_holdings h ON h.claim_id = r.prop_id "
                         "JOIN propositions p ON p.prop_id = r.prop_id WHERE r.origin_holder=? AND p.subject_id=? AND "
                         "p.predicate=?", (w.id(holder), w.id(about), claim))


@pytest.mark.parametrize("words, claim, text", [
    ("June, you useless idiot.", "insulted_someone", "insulted you."),
    ("June, I'm gonna kill you.", "threatened_someone", "threatened you."),
])
def test_what_you_said_to_her_is_her_story(scenario, fake, words, claim, text):
    w = scenario("metal_fence")
    pc = w.store.query_one("SELECT place_id, x_m, y_m FROM positions WHERE body_id=?", (w.id("pc"),))
    w.store.conn.execute("UPDATE positions SET place_id=?, anchor_id=NULL, x_m=?, y_m=? WHERE body_id=?",   # to her face
                         (pc[0], (pc[1] or 0) + 1.0, pc[2] or 0, w.id("june")))
    w.store.conn.commit()
    s = w.session()
    s.extras["forced_addressee"] = w.id("june")
    assert play(s, "say", words).ok
    [(rid, said)] = stories(w, "june", "pc", claim)
    assert said.endswith(text), said
    s.extras["forced_addressee"] = w.id("june")
    assert play(s, "say", words).ok
    assert len(stories(w, "june", "pc", claim)) == 1, "the same wrong again is the story she already tells"
    assert not w.store.query("SELECT 1 FROM rumours WHERE origin_holder=?", (w.id("pc"),)), "nothing is written into the PC"


def seed(w, holder, about, claim):
    with w.store.transaction() as tx:
        cause = accident(tx, now(w), "something said")
        return rumours.seed(tx, w.id(holder), w.id(about), claim, now(w), 0, cause.event_id, confidence=3,
                            seen=True, whom_id=w.id(holder))


@pytest.mark.parametrize("claim, rule, axis", [("insulted_someone", "CAS-113", "respect"), ("threatened_someone", "CAS-114", "trust")])
def test_whoever_hears_it_thinks_less_of_him(settle, claim, rule, axis):
    """Finn tells Kit, who believes him, what Jude said to him."""
    w = settle
    rid = seed(w, "finn", "jude", claim)
    before = (rel(w, "kit", "jude") or {}).get(axis, 0)
    with w.store.transaction() as tx:
        rs = rumours.spread_one(tx, rid, w.id("finn"), w.id("kit"), now(w), 0, None)
        made = cascade.sweep(tx, [rs], tx.canon.all("cascade"), now(w), 0)
    assert rs.payload["believed"] is True
    assert rel(w, "kit", "jude")[axis] - before == -1
    assert {e.rule_cited for e in made if e.type == "RELATION_CHANGE"} == {rule}


def test_shamed_in_front_of_others_she_resents_it(scenario, fake):
    """CAS-042's first effect (the drain) hid her from its others: shamed in front of the room, she lost heart and
    resented no one. Now the drain this very insult caused does not count as the one already taken this hour."""
    w = scenario("metal_fence")
    pc = w.store.query_one("SELECT place_id, x_m, y_m FROM positions WHERE body_id=?", (w.id("pc"),))
    w.store.conn.execute("UPDATE positions SET place_id=?, anchor_id=NULL, x_m=?, y_m=? WHERE body_id=?",
                         (pc[0], (pc[1] or 0) + 1.0, pc[2] or 0, w.id("june")))
    w.store.conn.commit()
    s = w.session()
    s.extras["forced_addressee"] = w.id("june")
    out = play(s, "say", "June, you useless idiot.")
    cited = [r[0] for r in w.store.query("SELECT rule_cited FROM events WHERE turn_index=? AND actor_id=? AND rule_cited='CAS-042'",
                                         (out.turn_index, w.id("june")))]
    made = [json.loads(r[0]) for r in w.store.query("SELECT payload FROM events WHERE turn_index=? AND type='RELATION_CHANGE' "
                                                     "AND rule_cited='CAS-042'", (out.turn_index,))]
    assert cited, "in front of others"
    assert [(m["from_id"], m["to_id"], m["axis"]) for m in made] == [(w.id("june"), w.id("pc"), "resentment")]
