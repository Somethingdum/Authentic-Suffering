"""Would she do that? (P11). Rules PORT-01..07, AUDIT-01, L13; DECISIONS D-07 (audit/portrayal.py;
turn/cognition.py step 1b; turn/pipeline.py S14/S15; mind/packet.py PORT-07).

June and Owen in a kitchen. When June's choice is a blow, a second call that did not make it
judges it before it happens; out of character, she decides once more and what she then decides
stands. Her other choices are judged after the fact, and a poor fit leaves her a note for next
time — the past is never rewritten.
"""

from __future__ import annotations

import copy
import json

import pytest

from as_engine.contracts.common import CallClass
from as_engine.testing.scenario import load_scenario
from as_engine.service.view import build_view
from slice_kit import cognition, pick, play

pytestmark = pytest.mark.phase(11)

KITCHEN = {
    "schema": "as.scenario.v1", "name": "kitchen_words", "seed": 23, "start": {"day": 400, "time": "18:00"},
    "places": [{"id": "kitchen", "name": "Kitchen", "material": "brick", "light": 3, "width_m": 5, "depth_m": 4,
                "anchors": [{"id": "table", "name": "table", "x": 2, "y": 2}, {"id": "sink", "name": "sink", "x": 3, "y": 2}]}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "kitchen", "anchor": "table"},
        {"id": "june", "dossier": "core:actor/june_okafor", "place": "kitchen", "anchor": "sink"},
    ],
}

FITS = {"verdict": "fits", "reasons": [], "cites": []}
OOC = {"verdict": "out_of_character", "reasons": ["She has never raised a hand to anyone"], "cites": ["moral line"]}


def judge(when_punch=OOC, otherwise=FITS):
    """The judge's answers, by what it is shown: a blow gets ``when_punch``, anything else ``otherwise``."""
    return lambda r: when_punch if r.context.output.goal == "make him stop" else otherwise


@pytest.fixture
def kitchen(fixture_packs, core_pack_dir, fake):
    worlds = []

    def _load():
        w = load_scenario(copy.deepcopy(KITCHEN), packs_root=fixture_packs, core_pack_dir=core_pack_dir, transport=fake)
        worlds.append(w)
        return w
    yield _load
    for w in worlds:
        w.store.close()


def ready(w, fake):
    """Owen takes in the kitchen (turn 1), so June is someone he can speak to. A session."""
    s = w.session()
    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "observe_area"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    assert play(s, "do", "I look around the kitchen.").ok
    return s


def say(w, s, words="June, put that down."):
    """Owen speaks to June; she answers in a reaction (ACTOR_REACTION)."""
    with s.store.transaction() as tx:
        v = build_view(tx, s)
    ref = next(p.ref for p in v.location.people if s.extras["view_refs"][p.ref] == w.id("june"))
    assert play(s, "say", words, addressee_refs=[ref]).ok


def punch(w):
    return cognition(lambda r: pick(w, r, "punch", target="pc"), goal="make him stop", reason="He will not listen.")


def step_back(w):
    return cognition(lambda r: pick(w, r, "wait_here"), speech="I'm not doing this.", goal="calm down", reason="Not like this.")


def rows(w, gate, turn=2):
    return [dict(r) | {"findings": json.loads(r["findings"])} for r in w.store.query(
        "SELECT * FROM audit_log WHERE gate = ? AND turn_index = ? ORDER BY audit_id", (gate, turn))]


def started(w, who, turn=2):
    return [json.loads(r[0])["def_id"] for r in w.store.query(
        "SELECT payload FROM events WHERE type = 'ACTION_START' AND actor_id = ? AND turn_index = ? ORDER BY seq",
        (w.id(who), turn))]


def failures(w):
    return [json.loads(r[0]) for r in w.store.query("SELECT detail FROM error_repair_log WHERE kind = 'portrayal_fail' ORDER BY entry_id")]


def test_a_blow_is_judged_before_it_lands(kitchen, fake):
    w = kitchen()
    s = ready(w, fake)
    fake.script(CallClass.ACTOR_REACTION, actor_id=w.id("june"), response=punch(w))
    say(w, s)
    (q,) = [q for q in fake.calls(CallClass.PORTRAYAL_AUDIT) if q.turn_index == 2 and q.context.output.goal == "make him stop"]
    assert q.actor_id == w.id("june") and "fists" in q.context.chosen_label
    assert q.context.output.private_reason == "He will not listen."
    (r,) = rows(w, "G06-portrayal")
    assert r["result"] == "pass" and r["producer"] != r["judge"]
    assert r["producer"].startswith(f"actor_reaction:{w.id('june')}:") and r["judge"].startswith(f"portrayal_audit:{w.id('june')}:")
    assert r["findings"] == [{"actor_id": w.id("june"), "when": "precheck", "reason": "moral", "def_id": "punch",
                              "label": q.context.chosen_label, "verdict": "fits", "reasons": [], "cites": []}]
    assert started(w, "june")[-1] == "punch", "the judge judges; June decides"


def test_out_of_character_she_decides_once_more(kitchen, fake):
    w = kitchen()
    s = ready(w, fake)
    fake.script(CallClass.ACTOR_REACTION, actor_id=w.id("june"), response=punch(w))
    fake.script(CallClass.INTENT_REPAIR, actor_id=w.id("june"), response=step_back(w))
    fake.script(CallClass.PORTRAYAL_AUDIT, judge(), times=10)
    say(w, s)
    (again,) = fake.calls(CallClass.INTENT_REPAIR, actor_id=w.id("june"))
    assert "never raised a hand to anyone" in again.messages[-1].content, "the reasons go with the second asking"
    assert [x["findings"][0]["when"] for x in rows(w, "G06-portrayal")] == ["precheck", "precheck_again"]
    assert [x["result"] for x in rows(w, "G06-portrayal")] == ["fail", "pass"]
    assert started(w, "june")[-1] == "wait_here" and failures(w) == []


def test_a_second_misfit_stands_and_is_on_record(kitchen, fake):
    w = kitchen()
    s = ready(w, fake)
    fake.script(CallClass.ACTOR_REACTION, actor_id=w.id("june"), response=punch(w))
    fake.script(CallClass.INTENT_REPAIR, actor_id=w.id("june"), response=punch(w))
    fake.script(CallClass.PORTRAYAL_AUDIT, judge(), times=10)
    say(w, s)
    assert started(w, "june")[-1] == "punch", "what she decides the second time stands"
    assert failures(w) == [{"actor_id": w.id("june"), "reasons": OOC["reasons"], "kept": "second"}]


def test_no_second_asking_once_the_repair_is_spent(kitchen, fake):
    w = kitchen()
    s = ready(w, fake)
    fake.script(CallClass.ACTOR_REACTION, actor_id=w.id("june"), response="{not json")
    fake.script(CallClass.INTENT_REPAIR, actor_id=w.id("june"), response=punch(w))
    fake.script(CallClass.PORTRAYAL_AUDIT, judge(), times=10)
    say(w, s)
    assert len(fake.calls(CallClass.INTENT_REPAIR, actor_id=w.id("june"))) == 1, "the decision's one repair, already spent"
    assert started(w, "june")[-1] == "punch"
    assert failures(w) == [{"actor_id": w.id("june"), "reasons": OOC["reasons"], "kept": "first"}]


def test_the_rest_are_judged_after_and_leave_a_note(kitchen, fake):
    w = kitchen()
    s = ready(w, fake)
    fake.script(CallClass.ACTOR_REACTION, actor_id=w.id("june"), response=step_back(w))
    loud = {"verdict": "out_of_character", "reasons": ["She would say what she thinks"], "cites": ["voice"]}
    fake.script(CallClass.PORTRAYAL_AUDIT, lambda r: loud if r.context.output.speech is not None else FITS, times=10)
    say(w, s)
    assert rows(w, "G06-portrayal") == [], "nothing high-stakes: no judging before"
    (r,) = [x for x in rows(w, "G15-portrayal") if x["result"] == "fail"]
    assert r["result"] == "fail" and r["findings"][0]["when"] == "retrospective" and r["producer"] != r["judge"]
    assert started(w, "june")[-1] == "wait_here", "the past is not rewritten"
    say(w, s, "June, listen to me.")
    nxt = fake.calls(CallClass.ACTOR_REACTION, actor_id=w.id("june"))[-1]
    label = r["findings"][0]["label"]
    note = (f"Looking back on what you did ({label}): someone who knows you would say that was not like you — "
            "She would say what she thinks.")
    assert nxt.context.portrayal_note == note and note in nxt.messages[-1].content
