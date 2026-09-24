"""Reading an Actor's answer: a decision, or one lookup first; one repair; a failed answer never
becomes a choice (P7, Actor v2 — Actor Spec §7, §14, AC05, AC15). Rules REPLY-01..02,
HOLD-01..02, CONSULT-06 (turn/cognition.py decide, mind/consult.py answer, turn/pipeline.py).

A person thinking with a model gets at most two decision calls (a lookup, then the decision) and
one repair. When the answer still cannot be used, nobody is made to do something they did not
choose: what they had already taken on goes on, or they stay as they are — and when the moment
matters (someone asked them something, or they face a threat) the turn is not played at all.

Direct calls of decide() on the metal-fence store at rest (June has her count to keep working
at; Mara has nothing she already took on), and one whole turn for the held decision.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from as_engine.contracts.common import LOD, CallClass, Lane
from as_engine.contracts.events import Event, EventType
from as_engine.contracts.mind import Consultation
from as_engine.lanes.scheduler import CognitionPlan
from as_engine.mind import consult, perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet
from as_engine.turn.cognition import HELD_MESSAGE, DecisionHeld, decide
from slice_kit import events, pick, play

pytestmark = pytest.mark.phase(7)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def decision(choice, **action):
    """A V2 decision whose choice is ``choice(request)``."""
    def answer(req):
        a = {"choice": choice(req), "goal": action.pop("goal", "carry on"), **action}
        return {"kind": "decision", "action": a, "consultation": None}
    return answer


def consultation(**c):
    def answer(req):
        body = {"kind": "recall", "query": None, "family": None, "template": None, "subjects": [], **c}
        if callable(body.get("family")):
            body["family"] = body["family"](req)
        return {"kind": "consultation", "action": None, "consultation": body}
    return answer


class Moment:
    """One wave of decisions at the world's now, turn 0: decide() for ``actors``."""

    def __init__(self, w, actors, *, speech=None):
        self.w, self.s = w, w.session()
        self.at = now(w)
        with self.s.store.transaction() as tx:
            if speech is not None:
                speaker, to, words = speech
                tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=self.at, turn_index=0,
                                      actor_id=w.id(speaker), payload={"words": words, "volume": "normal",
                                                                      "to": [w.id(to)], "source_db": 60}))
            self.affs = {}
            for a in actors:
                perception.compile_scene(tx, w.id(a), self.at, 0)
                self.affs[w.id(a)] = enumerate_affordances(tx, w.id(a), w.canon.all("affordance"), self.at, 0)
        self.plan = CognitionPlan(lod={w.id(a): LOD.HOT for a in actors}, lane={w.id(a): Lane.A for a in actors})

    def decide(self, **kw):
        async def go():
            with self.s.store.transaction() as tx:
                return await decide(tx, self.s, self.plan, self.affs, 0, self.at, reaction=kw.pop("reaction", False), **kw)
        return asyncio.run(go())

    def repairs(self):
        return [dict(r, detail=json.loads(r["detail"])) for r in self.w.store.query("SELECT * FROM error_repair_log ORDER BY rowid")]


# --------------------------------------------------------------------------- REPLY-01
def test_a_v1_answer_and_a_v2_decision_both_read(scenario, fake):
    w = scenario("metal_fence")
    june = w.id("june")
    fake.script(CallClass.ACTOR_COGNITION, actor_id=june, response=lambda r: {
        "choice": pick(w, r, "observe_area"), "speech": None, "manner": "", "goal": "look", "private_reason": "why"})
    m = Moment(w, ["june"])
    it = m.decide()[june]
    assert (it.bound.def_id, it.source, it.pace, it.goal) == ("observe_area", "model", "normal", "look")
    fake.script(CallClass.ACTOR_COGNITION, actor_id=june,
                response=decision(lambda r: pick(w, r, "search_place"), pace="careful", goal="find the key"))
    it = Moment(w, ["june"]).decide()[june]
    assert (it.bound.def_id, it.pace, it.goal, it.private_reason) == ("search_place", "careful", "find the key", "")
    assert len(fake.calls(CallClass.ACTOR_COGNITION, actor_id=june)) == 2 and not fake.calls(CallClass.INTENT_REPAIR)


# --------------------------------------------------------------------------- REPLY-02 / CONSULT-06
def test_a_lookup_then_the_decision_on_the_same_moment(scenario, fake):
    w = scenario("metal_fence")
    june = w.id("june")
    fake.script(CallClass.ACTOR_COGNITION, actor_id=june, response=consultation(query="Where did Nita go tonight?"))
    fake.script(CallClass.ACTOR_COGNITION, actor_id=june, response=decision(lambda r: pick(w, r, "observe_area")))
    m = Moment(w, ["june"])
    it = m.decide()[june]
    first, second = fake.calls(CallClass.ACTOR_COGNITION, actor_id=june)
    assert "recall" in first.context.consult_kinds
    with w.store.transaction() as tx:
        want = consult.recall(tx, first.context, "Where did Nita go tonight?", [], 0, m.at)
    assert second.context.looked_up == want, "the lookup's lines are shown under 'What you looked up'"
    assert second.context.consult_kinds == [] and second.context.families == [], "one consultation per decision"
    assert second.context.handles == first.context.handles, "the same snapshot"
    assert it.bound.def_id == "observe_area" and it.source == "model"
    assert not fake.calls(CallClass.INTENT_REPAIR)


def test_more_of_one_kind_adds_options_after_the_menu(scenario, fake):
    w = scenario("metal_fence")
    june = w.id("june")
    fake.script(CallClass.ACTOR_COGNITION, actor_id=june, response=consultation(kind="more_actions",
                                                                                family=lambda r: r.context.families[0]))
    fake.script(CallClass.ACTOR_COGNITION, actor_id=june,
                response=decision(lambda r: f"A{len(r.context.affordances)}"))   # the last one added
    m = Moment(w, ["june"])
    it = m.decide()[june]
    first, second = fake.calls(CallClass.ACTOR_COGNITION, actor_id=june)
    n = len(first.context.affordances)
    fam = first.context.families[0]
    shown = {first.context.handles[a.handle] for a in first.context.affordances}
    defs = {d.id: d for d in w.canon.all("affordance")}
    more = consult.more_actions(m.affs[june], fam, [], defs)
    assert [second.context.handles[f"A{n + i}"] for i in range(1, len(more) + 1)] == [o.signature for o in more]
    assert second.context.looked_up[0].startswith("More ways of ")
    assert it.bound.signature == more[-1].signature and it.bound.signature not in shown


def test_answer_reads_a_perception_handle_as_the_one_it_came_from(scenario, fake):
    w = scenario("metal_fence")
    m = Moment(w, ["mara"], speech=("pc", "mara", "Mara, stay where you are."))
    mara = w.id("mara")
    with w.store.transaction() as tx:
        p = build_packet(tx, mara, LOD.HOT, m.affs[mara], 0, m.at)
        heard = next(u.handle for u in p.utterances if "stay where you are" in (u.words or ""))
        defs = {d.id: d for d in w.canon.all("affordance")}
        got = consult.answer(tx, p, m.affs[mara], Consultation(kind="recall", subjects=[heard]), defs, 0, m.at)
        want = consult.recall(tx, p, None, [w.id("pc")], 0, m.at)
    assert got == consult.Consulted("recall", lines=want)


def test_a_consultation_where_none_is_offered_is_repaired_into_a_decision(scenario, fake):
    w = scenario("metal_fence")
    june = w.id("june")
    fake.script(CallClass.ACTOR_COGNITION, actor_id=june, response=consultation(kind="compose", template="x"))
    fake.script(CallClass.INTENT_REPAIR, actor_id=june, response=decision(lambda r: pick(w, r, "observe_area")))
    m = Moment(w, ["june"])
    it = m.decide()[june]
    assert it.bound.def_id == "observe_area" and it.source == "model"
    assert len(fake.calls(CallClass.ACTOR_COGNITION, actor_id=june)) == 1
    (rep,) = fake.calls(CallClass.INTENT_REPAIR, actor_id=june)
    if rep.json_schema is not None:
        assert rep.json_schema["properties"]["kind"]["enum"] == ["decision"], "a repair always answers with a decision"
    (row,) = m.repairs()
    assert (row["kind"], row["rule_id"], row["repaired"]) == ("schema_fail", "LANE-06", 1)
    assert row["detail"]["actor_id"] == june and row["detail"]["reason"] == "bad_consultation"


def test_a_second_lookup_is_not_answered(scenario, fake):
    w = scenario("metal_fence")
    june = w.id("june")
    fake.script(CallClass.ACTOR_COGNITION, actor_id=june, response=consultation(query="the cans"), times=2)
    fake.script(CallClass.INTENT_REPAIR, actor_id=june, response=decision(lambda r: pick(w, r, "observe_area")))
    it = Moment(w, ["june"]).decide()[june]
    assert len(fake.calls(CallClass.ACTOR_COGNITION, actor_id=june)) == 2
    assert len(fake.calls(CallClass.INTENT_REPAIR, actor_id=june)) == 1 and it.bound.def_id == "observe_area"


def test_a_reaction_offers_no_lookup(scenario, fake):
    w = scenario("metal_fence")
    june = w.id("june")
    fake.script(CallClass.ACTOR_REACTION, actor_id=june, response=consultation(query="the cans"))
    fake.script(CallClass.INTENT_REPAIR, actor_id=june, response=decision(lambda r: pick(w, r, "observe_area")))
    it = Moment(w, ["june"]).decide(reaction=True)[june]
    (req,) = fake.calls(CallClass.ACTOR_REACTION, actor_id=june)
    assert req.context.consult_kinds == [] and it.bound.def_id == "observe_area"


# --------------------------------------------------------------------------- HOLD-01 / HOLD-02
def test_a_failed_answer_goes_on_with_what_they_already_took_on(scenario, fake):
    w = scenario("metal_fence")
    june = w.id("june")
    fake.fail(CallClass.ACTOR_COGNITION, "grammar_fail", actor_id=june)
    fake.fail(CallClass.INTENT_REPAIR, "grammar_fail", actor_id=june)
    m = Moment(w, ["june"])
    it = m.decide()[june]
    assert (it.bound.def_id, it.source) == ("keep_working", "fallback"), "her count goes on; nothing new is invented"
    (ev,) = [e for e in events(w, "DEGRADED_FALLBACK") if e["actor_id"] == june]
    assert ev["payload"] == {"actor_id": june, "reason": "grammar_fail", "path": "continued"}
    (row,) = m.repairs()
    assert (row["kind"], row["rule_id"], row["repaired"]) == ("grammar_fail", "LANE-06", 0)
    assert row["detail"] == {"actor_id": june, "reason": "grammar_fail", "path": "continued"}


def test_with_nothing_taken_on_a_failed_answer_is_no_attempt_at_all(scenario, fake):
    w = scenario("metal_fence")
    mara = w.id("mara")
    fake.fail(CallClass.ACTOR_COGNITION, "schema_fail", actor_id=mara)
    fake.fail(CallClass.INTENT_REPAIR, "schema_fail", actor_id=mara)
    m = Moment(w, ["mara"])
    out = m.decide()
    assert mara not in out, "no observe / wait / first-option default: nobody is made to choose"
    (ev,) = [e for e in events(w, "DEGRADED_FALLBACK") if e["actor_id"] == mara]
    assert ev["payload"] == {"actor_id": mara, "reason": "schema_fail", "path": "held"}


def test_a_lane_that_times_out_gets_no_repair(scenario, fake):
    w = scenario("metal_fence")
    june = w.id("june")
    fake.fail(CallClass.ACTOR_COGNITION, "timeout", actor_id=june)
    m = Moment(w, ["june"])
    it = m.decide()[june]
    assert not fake.calls(CallClass.INTENT_REPAIR), "the lane is the problem, not the answer"
    assert (it.bound.def_id, it.source) == ("keep_working", "fallback")
    (ev,) = [e for e in events(w, "DEGRADED_FALLBACK") if e["actor_id"] == june]
    assert ev["payload"]["reason"] == "timeout"


def test_someone_asked_a_question_is_never_answered_by_a_fallback(scenario, fake):
    """HOLD-02: an unanswered ask makes the decision consequential; HOLD-01 raises DecisionHeld."""
    w = scenario("metal_fence")
    mara = w.id("mara")
    fake.fail(CallClass.ACTOR_COGNITION, "grammar_fail", actor_id=mara)
    fake.fail(CallClass.INTENT_REPAIR, "grammar_fail", actor_id=mara)
    m = Moment(w, ["mara"], speech=("pc", "mara", "Mara, give me the keys."))
    with pytest.raises(DecisionHeld) as held:
        m.decide()
    assert (held.value.actor_id, held.value.kind, held.value.code) == (mara, "grammar_fail", "decision_held")
    assert str(held.value.message) == HELD_MESSAGE and "Mara" not in HELD_MESSAGE


def test_an_ask_already_answered_is_not_consequential_again(scenario, fake):
    w = scenario("metal_fence")
    mara = w.id("mara")
    fake.fail(CallClass.ACTOR_COGNITION, "grammar_fail", actor_id=mara)
    fake.fail(CallClass.INTENT_REPAIR, "grammar_fail", actor_id=mara)
    m = Moment(w, ["mara"], speech=("pc", "mara", "Mara, give me the keys."))
    ask = next(e for e in events(w, "SPEECH") if e["actor_id"] == w.id("pc"))
    out = m.decide(answered=frozenset({(mara, ask["event_id"])}))
    assert mara not in out, "not consequential any more: HOLD-01's ordinary path"
    (ev,) = [e for e in events(w, "DEGRADED_FALLBACK") if e["actor_id"] == mara]
    assert ev["payload"]["path"] == "held"


# --------------------------------------------------------------------------- HOLD-01 in a whole turn
def test_a_held_decision_leaves_the_turn_unplayed(scenario, fake):
    from as_engine.service.view import build_view
    w = scenario("metal_fence")
    mara = w.id("mara")
    s = w.session()
    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "observe_area"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    assert play(s, "do", "I look around.").ok             # turn 1: the player takes in the room
    t0 = now(w)
    before = w.store.query_one("SELECT COUNT(*) FROM events")[0]
    fake.fail(CallClass.ACTOR_REACTION, "grammar_fail", actor_id=mara)
    fake.fail(CallClass.INTENT_REPAIR, "grammar_fail", actor_id=mara)
    with s.store.transaction() as tx:
        v = build_view(tx, s)
    ref = next(p.ref for p in v.location.people if s.extras["view_refs"][p.ref] == mara)
    out = play(s, "say", "Mara, give me the keys.", addressee_refs=[ref])
    assert (out.ok, out.rejected_code, out.rejected_message) == (False, "decision_held", HELD_MESSAGE)
    assert now(w) == t0 and w.store.query_one("SELECT COUNT(*) FROM events")[0] == before, "nothing happened"
    (row,) = [dict(r) for r in w.store.query("SELECT * FROM error_repair_log WHERE kind = 'decision_held'")]
    assert row["rule_id"] == "HOLD-01" and json.loads(row["detail"]) == {"actor_id": mara, "reason": "grammar_fail"}
