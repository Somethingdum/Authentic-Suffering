"""Relationships, open loops and lessons (P6). Rules REL-01..05, LOOP-01..06, LESSON-01..03,
STORE-11, CAS-011 (mind/mind.py).

A relationship is what ONE mind feels about another; a loop is what hangs over a mind; a lesson
is what experience taught it. Every change is one event with its cause, and nothing here ever
changes a second mind.
"""

from __future__ import annotations

import json

import pytest

from as_engine.action import cascade
from as_engine.contracts.common import OpenLoopKind, RelationAxis
from as_engine.contracts.events import Event, EventType
from as_engine.mind import cues, mind, perception

pytestmark = pytest.mark.phase(6)

A = RelationAxis


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def noise(w, at=None):
    """A real committed event to use as a cause."""
    with w.store.transaction() as tx:
        return tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", at=at or now(w), turn_index=0,
                                     payload={"source_db": 98, "kind": "metal_crash", "text": "a loud metal crash",
                                              "place_id": w.id("alley"), "anchor_id": w.id("fence_sheet")}))


def rel(w, a, b):
    r = w.store.query_one("SELECT * FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return None if r is None else dict(r)


def loop_row(w, loop_id):
    r = dict(w.store.query_one("SELECT * FROM open_loops WHERE loop_id = ?", (loop_id,)))
    r["subject_ids"] = json.loads(r["subject_ids"])
    return r


def count(w, type_):
    return w.store.query_one("SELECT COUNT(*) FROM events WHERE type = ?", (type_,))[0]


def last(w, type_):
    r = w.store.query_one("SELECT event_id, payload, cause_event_id, writer, actor_id FROM events WHERE type = ? "
                          "ORDER BY seq DESC LIMIT 1", (type_,))
    return dict(r, payload=json.loads(r["payload"]))


# =========================================================================== relationships
def test_the_first_change_creates_the_row(scenario):
    """REL-01, REL-03: a missing row is created by the change itself, kind 'acquaintance'."""
    w = scenario("metal_fence")
    t = now(w)
    cause = noise(w)
    assert rel(w, "june", "nita") is None
    with w.store.transaction() as tx:
        ev = mind.relate(tx, w.id("june"), w.id("nita"), A.RESPECT, 2, cause.event_id, t + 5, 0)
    r = rel(w, "june", "nita")
    assert (r["kind"], r["respect"], r["trust"], r["fear"], r["affection"], r["resentment"], r["obligation"]) == \
        ("acquaintance", 2, 0, 0, 0, 0, 0)
    assert json.loads(r["causes"]) == {"respect": cause.event_id} and r["updated_at"] == t + 5
    assert (ev.type, ev.writer, ev.actor_id, ev.cause_event_id, ev.at) == \
        (EventType.RELATION_CHANGE, "mind.mind", w.id("june"), cause.event_id, t + 5)
    assert ev.payload == {"from_id": w.id("june"), "to_id": w.id("nita"), "axis": "respect", "old": 0, "new": 2, "delta": 2}


def test_values_clamp_and_no_change_is_no_event(scenario):
    """REL-02: the event records what actually changed; nothing changed, nothing committed."""
    w = scenario("metal_fence")
    t = now(w)
    cause = noise(w)
    n = count(w, "RELATION_CHANGE")
    with w.store.transaction() as tx:
        assert mind.relate(tx, w.id("mara"), w.id("eli"), A.TRUST, +1, cause.event_id, t, 0) is None, "already 3"
        assert mind.relate(tx, w.id("mara"), w.id("eli"), A.FEAR, -1, cause.event_id, t, 0) is None, "fear starts at 0"
        assert mind.relate(tx, w.id("mara"), w.id("eli"), A.RESPECT, 0, cause.event_id, t, 0) is None
    assert count(w, "RELATION_CHANGE") == n
    with w.store.transaction() as tx:
        down = mind.relate(tx, w.id("mara"), w.id("eli"), A.TRUST, -9, cause.event_id, t, 0)
        up = mind.relate(tx, w.id("mara"), w.id("eli"), A.RESENTMENT, 5, cause.event_id, t, 0)
    assert (down.payload["old"], down.payload["new"], down.payload["delta"]) == (3, -3, -6)
    assert (up.payload["old"], up.payload["new"], up.payload["delta"]) == (0, 3, 3)
    assert (rel(w, "mara", "eli")["trust"], rel(w, "mara", "eli")["resentment"]) == (-3, 3)


def test_each_axis_keeps_its_latest_cause(scenario):
    """REL-03: causes is per axis; a standing-view reference is kept in the row but is not an event."""
    w = scenario("metal_fence")
    t = now(w)
    c1, c2 = noise(w, t), noise(w, t + 1)
    with w.store.transaction() as tx:
        mind.relate(tx, w.id("june"), w.id("mara"), A.FEAR, 1, c1.event_id, t, 0)
        mind.relate(tx, w.id("june"), w.id("mara"), A.TRUST, -1, c1.event_id, t, 0)
        mind.relate(tx, w.id("june"), w.id("mara"), A.FEAR, 1, c2.event_id, t + 1, 0)
        scene = mind.relate(tx, w.id("june"), w.id("mara"), A.RESPECT, 1, "scene:0", t + 2, 0)
    assert json.loads(rel(w, "june", "mara")["causes"]) == {"fear": c2.event_id, "trust": c1.event_id, "respect": "scene:0"}
    assert scene.cause_event_id is None, "'scene:0' is a reference, not an event (committed_or_none)"


def test_a_relationship_is_one_directional_and_keeps_its_kind(scenario):
    """REL-04, REL-05."""
    w = scenario("metal_fence")
    t = now(w)
    cause = noise(w)
    before = rel(w, "june", "mara")
    with w.store.transaction() as tx:
        mind.relate(tx, w.id("mara"), w.id("june"), A.TRUST, -2, cause.event_id, t, 0)
    assert rel(w, "june", "mara") == before, "Mara's change of heart is hers alone"
    assert (rel(w, "mara", "june")["trust"], rel(w, "mara", "june")["kind"]) == (0, "friend")
    with w.store.transaction() as tx, pytest.raises(ValueError):
        mind.relate(tx, w.id("mara"), w.id("mara"), A.TRUST, 1, cause.event_id, t, 0)


# =========================================================================== open loops
def test_open_loop_writes_the_row_and_names_its_own_event(scenario):
    """LOOP-01, STORE-11: created_event is the LOOP_OPENED event itself."""
    w = scenario("metal_fence")
    t = now(w)
    cause = noise(w)
    with w.store.transaction() as tx:
        lid = mind.open_loop(tx, w.id("nita"), OpenLoopKind.QUESTION, "Who is the thin man at the fence?",
                             [w.id("stranger")], 2, cause.event_id, t, 0)
    assert lid.startswith("olp_")
    r = loop_row(w, lid)
    ev = last(w, "LOOP_OPENED")
    assert (r["holder_id"], r["kind"], r["text"], r["subject_ids"], r["strength"], r["status"], r["created_at"], r["due_at"]) == \
        (w.id("nita"), "question", "Who is the thin man at the fence?", [w.id("stranger")], 2, "open", t, None)
    assert r["created_event"] == ev["event_id"] and r["resolved_event"] is None
    assert (ev["writer"], ev["actor_id"], ev["cause_event_id"]) == ("mind.mind", w.id("nita"), cause.event_id)
    assert ev["payload"] == {"loop_id": lid, "holder_id": w.id("nita"), "kind": "question",
                             "text": "Who is the thin man at the fence?", "subject_ids": [w.id("stranger")], "strength": 2,
                             "due_at": None}


@pytest.mark.parametrize("kind,etype", [(OpenLoopKind.PROMISE_MADE, "PROMISE"), (OpenLoopKind.PROMISE_OWED, "PROMISE"),
                                        (OpenLoopKind.GOAL, "LOOP_OPENED"), (OpenLoopKind.GRUDGE, "LOOP_OPENED"),
                                        (OpenLoopKind.DEBT_OWING, "LOOP_OPENED"), (OpenLoopKind.SECRET_KEPT, "LOOP_OPENED")])
def test_promises_open_with_a_promise_event(scenario, kind, etype):
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        lid = mind.open_loop(tx, w.id("june"), kind, "Bring the water up by morning", [w.id("pc")], 2, None, now(w), 0,
                             due_at=now(w) + 3_600_000)
    ev = last(w, etype)
    assert ev["payload"]["loop_id"] == lid and ev["payload"]["due_at"] == now(w) + 3_600_000
    assert loop_row(w, lid)["due_at"] == now(w) + 3_600_000


def test_the_subject_placeholder_uses_the_holders_own_word(scenario):
    """LOOP-01: '{subject}' becomes what THIS holder calls the subject; the text starts with a capital."""
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        a = mind.open_loop(tx, w.id("june"), OpenLoopKind.GRUDGE, "{subject} broke a promise to you.", [w.id("pc")], 2,
                           None, now(w), 0)
        b = mind.open_loop(tx, w.id("alice"), OpenLoopKind.FEAR, "{subject} keeps watching the fence.", [w.id("stranger")], 1,
                           None, now(w), 0)
        stranger_word = perception.word_for(tx, w.id("alice"), w.id("stranger"))
    assert loop_row(w, a)["text"] == "Owen broke a promise to you."
    assert loop_row(w, b)["text"] == stranger_word[:1].upper() + stranger_word[1:] + " keeps watching the fence."
    assert not stranger_word.lower().startswith("the thin man"), "Alice has never been told what Nita calls him"


@pytest.mark.parametrize("kind,text,strength", [("grievance", "He lied", 2), ("grudge", "   ", 2),
                                                ("grudge", "He lied", 0), ("grudge", "He lied", 4)])
def test_a_malformed_loop_is_refused(scenario, kind, text, strength):
    """LOOP-01: kind must be an OpenLoopKind ('grievance' is not one), text non-empty, strength 1..3."""
    w = scenario("metal_fence")
    with w.store.transaction() as tx, pytest.raises(ValueError):
        mind.open_loop(tx, w.id("june"), kind, text, [], strength, None, now(w), 0)


def test_the_same_loop_is_not_held_twice(scenario):
    """LOOP-02: same kind, same subjects (any order), same words (case and end punctuation aside)."""
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        a = mind.open_loop(tx, w.id("nita"), OpenLoopKind.GOAL, "Watch the fence with Mara", [w.id("stranger"), w.id("mara")], 2,
                           None, t, 0)
    n = count(w, "LOOP_OPENED")
    with w.store.transaction() as tx:
        again = mind.open_loop(tx, w.id("nita"), OpenLoopKind.GOAL, "  watch the fence   with mara!", [w.id("mara"), w.id("stranger")],
                               3, None, t + 10, 0)
        other_kind = mind.open_loop(tx, w.id("nita"), OpenLoopKind.PLAN, "Watch the fence with Mara", [w.id("stranger"), w.id("mara")],
                                    2, None, t + 10, 0)
    assert again == a and loop_row(w, a)["strength"] == 2, "no second loop, strength unchanged"
    assert other_kind != a and count(w, "LOOP_OPENED") == n + 1
    with w.store.transaction() as tx:
        mind.close_loop(tx, a, "fulfilled", None, t + 20, 0)
        reopened = mind.open_loop(tx, w.id("nita"), OpenLoopKind.GOAL, "Watch the fence with Mara", [w.id("mara"), w.id("stranger")],
                                  2, None, t + 30, 0)
    assert reopened != a, "a closed loop does not block a new one"


def test_close_loop(scenario):
    """LOOP-03, LOOP-06."""
    w = scenario("metal_fence")
    t = now(w)
    cause = noise(w)
    with w.store.transaction() as tx:
        lid = mind.open_loop(tx, w.id("june"), OpenLoopKind.GOAL, "Finish counting the cans", [], 2, None, t, 0)
        ev = mind.close_loop(tx, lid, "abandoned", cause.event_id, t + 100, 0)
    r = loop_row(w, lid)
    assert (r["status"], r["resolved_event"]) == ("abandoned", ev.event_id)
    assert (ev.type, ev.writer, ev.actor_id, ev.cause_event_id, ev.at) == \
        (EventType.LOOP_CLOSED, "mind.mind", w.id("june"), cause.event_id, t + 100)
    assert ev.payload == {"loop_id": lid, "holder_id": w.id("june"), "kind": "goal", "status": "abandoned"}
    with w.store.transaction() as tx:
        with pytest.raises(ValueError):
            mind.close_loop(tx, lid, "fulfilled", None, t, 0)            # not open any more
        other = mind.open_loop(tx, w.id("june"), OpenLoopKind.GOAL, "Sleep", [], 1, None, t, 0)
        with pytest.raises(ValueError):
            mind.close_loop(tx, other, "done", None, t, 0)               # not a status
        with pytest.raises(ValueError):
            mind.close_loop(tx, "olp_999999", "broken", None, t, 0)
    assert w.store.query_one("SELECT COUNT(*) FROM open_loops WHERE loop_id = ?", (lid,))[0] == 1, "never deleted"


def test_only_the_promisee_decides_a_promise_was_broken(scenario):
    """LOOP-04, LOOP-05, L1: the owed side's conclusion is a world event; the promiser's private
    verdict on itself is not, and closing a loop changes nobody's feelings by itself."""
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        owed = mind.open_loop(tx, w.id("june"), OpenLoopKind.PROMISE_OWED, "Owen said he'd bring water up", [w.id("pc")], 2,
                              None, t, 0)
        made = mind.open_loop(tx, w.id("pc"), OpenLoopKind.PROMISE_MADE, "Bring June water", [w.id("june")], 2, None, t, 0)
        kept_owed = mind.open_loop(tx, w.id("alice"), OpenLoopKind.PROMISE_OWED, "Owen will help sort", [w.id("pc")], 1,
                                   None, t, 0)
    rels_before = [dict(r) for r in w.store.query("SELECT * FROM relationships ORDER BY from_id, to_id")]
    with w.store.transaction() as tx:
        broken = mind.close_loop(tx, owed, "broken", None, t + 10, 0)
        private = mind.close_loop(tx, made, "broken", None, t + 10, 0)
        kept = mind.close_loop(tx, kept_owed, "fulfilled", None, t + 10, 0)
    assert broken.type == EventType.PROMISE_BROKEN
    assert broken.payload == {"loop_id": owed, "holder_id": w.id("june"), "status": "broken", "promisee_id": w.id("june"),
                              "promiser_id": w.id("pc")}
    assert private.type == EventType.LOOP_CLOSED and private.payload["kind"] == "promise_made"
    assert kept.type == EventType.PROMISE_KEPT and kept.payload["promiser_id"] == w.id("pc")
    assert [dict(r) for r in w.store.query("SELECT * FROM relationships ORDER BY from_id, to_id")] == rels_before


def test_a_broken_promise_costs_the_promisee_through_cascade_content(scenario, canon):
    """LOOP-05 + core CAS-011: June's trust in Owen drops by 2 and she opens a grudge worded in her
    own words; Owen's feelings are untouched; the promise_broken cue is present for June."""
    w = scenario("metal_fence")
    t = now(w)
    rules = [r for r in canon.all("cascade") if r.trigger_event == "PROMISE_BROKEN"]
    assert [r.id for r in rules] == ["CAS-011"]
    with w.store.transaction() as tx:
        owed = mind.open_loop(tx, w.id("june"), OpenLoopKind.PROMISE_OWED, "Owen said he'd bring water up", [w.id("pc")], 2,
                              None, t, 0)
        ev = mind.close_loop(tx, owed, "broken", None, t + 10, 0)
        out = cascade.sweep(tx, [ev], rules, t + 10, 0)
        present = cues.cues_of(tx, w.id("june"), 0, t + 10)
    assert [e.type for e in out] == [EventType.RELATION_CHANGE, EventType.LOOP_OPENED]
    assert all(e.rule_cited == "CAS-011" and e.cause_event_id == ev.event_id for e in out)
    assert all(e.payload["_cascade_depth"] == 1 for e in out)
    assert {k: v for k, v in out[0].payload.items() if k != "_cascade_depth"} == \
        {"from_id": w.id("june"), "to_id": w.id("pc"), "axis": "trust", "old": 1, "new": -1, "delta": -2}
    grudge = loop_row(w, out[1].payload["loop_id"])
    assert (grudge["holder_id"], grudge["kind"], grudge["text"], grudge["subject_ids"], grudge["strength"]) == \
        (w.id("june"), "grudge", "Owen broke a promise to you.", [w.id("pc")], 2)
    assert rel(w, "pc", "june") is None, "the promiser's mind is not touched"
    assert "promise_broken" in present


# =========================================================================== lessons
def test_learn_writes_a_lesson(scenario):
    """LESSON-01, STORE-11."""
    w = scenario("metal_fence")
    t = now(w)
    cause = noise(w)
    with w.store.transaction() as tx:
        lid = mind.learn(tx, w.id("june"), ["metal_crash", "loud_noise"], "A crash out back means someone is at the fence.",
                         "that it was the wind", "Nita was out there", cause.event_id, t, 0)
    r = dict(w.store.query_one("SELECT * FROM lessons WHERE lesson_id = ?", (lid,)))
    ev = last(w, "LESSON_LEARNED")
    assert lid.startswith("lsn_")
    assert (json.loads(r["cue_tags"]), r["text"], r["expectation"], r["outcome"], r["confidence"], r["at"]) == \
        (["loud_noise", "metal_crash"], "A crash out back means someone is at the fence.", "that it was the wind",
         "Nita was out there", 2, t)
    assert r["source_event"] == ev["event_id"] and ev["cause_event_id"] == cause.event_id
    assert ev["payload"] == {"lesson_id": lid, "holder_id": w.id("june"), "cue_tags": ["loud_noise", "metal_crash"],
                             "text": "A crash out back means someone is at the fence.", "expectation": "that it was the wind",
                             "outcome": "Nita was out there", "confidence": 2, "reinforced": False}


def test_learning_the_same_thing_again_reinforces_it(scenario):
    """LESSON-02, LESSON-03."""
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        lid = mind.learn(tx, w.id("june"), ["metal_crash"], "Crashes mean trouble.", "", "", None, t, 0)
        again = mind.learn(tx, w.id("june"), ["metal_crash"], "crashes mean trouble!", "", "", None, t + 1, 0)
    assert again == lid
    ev = last(w, "LESSON_LEARNED")
    assert ev["payload"] == {"lesson_id": lid, "holder_id": w.id("june"), "confidence": 3, "reinforced": True}
    n = count(w, "LESSON_LEARNED")
    with w.store.transaction() as tx:
        assert mind.learn(tx, w.id("june"), ["metal_crash"], "Crashes mean trouble", "", "", None, t + 2, 0) == lid
        other = mind.learn(tx, w.id("june"), ["metal_crash", "loud_noise"], "Crashes mean trouble", "", "", None, t + 3, 0)
    assert count(w, "LESSON_LEARNED") == n + 1, "at 3 nothing more; different tags = a different lesson"
    assert other != lid
    assert w.store.query_one("SELECT confidence FROM lessons WHERE lesson_id = ?", (lid,))[0] == 3


@pytest.mark.parametrize("tags,text", [([], "Crashes mean trouble"), ([""], "Crashes mean trouble"), (["metal_crash"], "  ")])
def test_a_lesson_needs_cues_and_words(scenario, tags, text):
    w = scenario("metal_fence")
    with w.store.transaction() as tx, pytest.raises(ValueError):
        mind.learn(tx, w.id("june"), tags, text, "", "", None, now(w), 0)
