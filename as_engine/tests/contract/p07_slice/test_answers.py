"""A yes is not a lie by itself; a no can be reconsidered (P7, Actor v2 — Actor Spec §10, §12; AC09).
turn/cognition.py record_responses; mind/firewall.py WILL-09, WILL-12, WILL-13; mind/mind.py
open_loop (promise_made); kernel/store.py STORE-12 (the answer links the ask, B5c).

Owen asks Mara to open the yard door. What she answers and what she does are recorded first; code
then only sorts it: a yes with a condition is a promise she now holds; a yes and a step toward the
door is preparing; a question back is not an answer yet; a yes and something else is recorded as
said and done, and nobody is called a liar for it. If she once refused and now does it, the refusal
is marked revised — she changed her mind — and kept. The door and the spots at either side of it
share the name 'yard door', as doors in the core buildings do: 'open the yard door' means the door.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

import helpers
from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.contracts.events import Event, EventType
from as_engine.mind import firewall, perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.testing.scenario import load_scenario
from as_engine.turn import cognition

pytestmark = pytest.mark.phase(7)

ROOM = {
    "schema": "as.scenario.v1", "name": "asked_room", "seed": 23, "start": {"day": 400, "time": "12:00"},
    "places": [
        {"id": "room", "name": "Back room", "material": "brick", "light": 3, "width_m": 8, "depth_m": 6,
         "anchors": [{"id": "door_in", "name": "yard door", "kind": "door_side", "x": 7.7, "y": 3},
                     {"id": "bench", "name": "bench", "x": 2, "y": 5}]},
        {"id": "yard", "name": "Yard", "kind": "outdoor", "indoor": False, "material": "open_air", "light": 3,
         "width_m": 20, "depth_m": 20, "anchors": [{"id": "door_out", "name": "yard door", "kind": "door_side", "x": 0.3, "y": 10}]},
    ],
    "portals": [{"id": "yard_door", "a": "room", "b": "yard", "anchor_a": "door_in", "anchor_b": "door_out",
                 "kind": "door", "name": "yard door", "w": 90, "h": 200}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "room", "x": 4, "y": 3},
        {"id": "mara", "stub": {"name": "Mara Voss", "age": 38, "sex": "female"}, "place": "room", "x": 3, "y": 3},
    ],
}

ASK = "Mara, open the yard door."


@pytest.fixture
def room(fixture_packs, core_pack_dir):
    worlds = []

    def _load():
        w = load_scenario(ROOM, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        return w

    yield _load
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def answer(w, def_id, words=None, *, destination=None, target=None):
    """Owen asks; Mara hears it, then does ``def_id`` saying ``words``; record_responses sorts it."""
    t = now(w)
    mara = w.id("mara")
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=t, turn_index=0, actor_id=w.id("pc"),
                              payload={"words": ASK, "volume": "normal", "to": [mara], "source_db": 60}))
        perception.compile_scene(tx, mara, t, 0)
        asks = {mara: cognition.asks_for(tx, mara, 0, set())}
        affs = {mara: enumerate_affordances(tx, mara, w.canon.all("affordance"), t, 0)}
    it = helpers.make_intent(w, "mara", def_id, destination=destination, target=target,
                             speech=(words, ["pc"], "normal") if words else None)
    with w.store.transaction() as tx:
        first = tx.query_one("SELECT COALESCE(MAX(seq), 0) FROM events")[0]
        resolve_wave(tx, helpers.ScriptedRng(), barrier(tx, [it]), t + 500, 0, horizon_ms=t + 20_000)
        return cognition.record_responses(tx, {mara: it}, affs, asks, 0, t + 500, first)


def kinds(w, type_):
    return [json.loads(r[0]) for r in w.store.query("SELECT payload FROM events WHERE type = ? ORDER BY seq", (type_,))]


def answers_the_ask(w, type_):
    """C10 (Actor v2 B5c, STORE-12): the event links the ask it replies to."""
    ask = w.store.query_one("SELECT event_id FROM events WHERE type = 'SPEECH' AND actor_id = ? ORDER BY seq", (w.id("pc"),))[0]
    return [json.loads(r[0]) for r in w.store.query("SELECT links FROM events WHERE type = ? ORDER BY seq", (type_,))] == \
        [[{"event_id": ask, "role": "answered"}]]


def test_a_yes_with_a_condition_is_a_promise_she_holds(room):
    w = room()
    ((_, _, resp),) = answer(w, "wait_here", "Yes, after I finish this.")
    assert resp == "deferred_assent"
    loops = [dict(r) for r in w.store.query("SELECT * FROM open_loops WHERE holder_id = ? AND kind = 'promise_made'",
                                             (w.id("mara"),))]
    assert len(loops) == 1 and json.loads(loops[0]["subject_ids"]) == [w.id("pc")]
    assert "open the yard door" in loops[0]["text"].lower() and "after i finish this" in loops[0]["text"].lower()
    assert kinds(w, "ASSENT_UNMET") == [] and kinds(w, "LIE_TOLD") == []
    assert answers_the_ask(w, "PROMISE"), "her own words are the cause; the ask is what they answer"


def test_a_yes_and_a_step_toward_it_is_preparing(room):
    w = room()
    ((_, _, resp),) = answer(w, "move_to_anchor", "Okay.", destination="door_in")
    assert resp == "preparing"
    assert kinds(w, "ASSENT_UNMET") == [] and kinds(w, "LIE_TOLD") == []


def test_a_question_back_is_not_an_answer_yet(room):
    w = room()
    ((_, _, resp),) = answer(w, "wait_here", "Okay, what exactly do you mean?")
    assert resp == "clarifying"
    assert kinds(w, "ASSENT_UNMET") == [] and kinds(w, "REFUSAL") == []


def test_a_yes_and_something_else_is_recorded_not_judged(room):
    w = room()
    ((_, eid, resp),) = answer(w, "move_to_anchor", "Sure.", destination="bench")
    assert resp == "unresolved_assent"
    (u,) = kinds(w, "ASSENT_UNMET")
    assert (u["actor_id"], u["to_id"], u["words"], u["chosen_def_id"]) == (w.id("mara"), w.id("pc"), "Sure.", "move_to_anchor")
    assert u["signature"] == f"open_portal:{w.id('yard_door')}"
    assert answers_the_ask(w, "ASSENT_UNMET")
    assert kinds(w, "LIE_TOLD") == []
    assert w.store.query("SELECT 1 FROM relationships WHERE from_id = ? AND to_id = ?", (w.id("pc"), w.id("mara"))) == [], \
        "nobody's trust moves on a code guess"


def test_she_changed_her_mind(room):
    w = room()
    sig = f"open_portal:{w.id('yard_door')}"
    with w.store.transaction() as tx:
        earlier = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=now(w) - 60_000, turn_index=0,
                                        payload={"what": "an ask she refused a while ago"}))
        rid = firewall.record_refusal(tx, w.id("mara"), w.id("pc"), sig, "open the yard door", "cost", [earlier.event_id], "",
                                      False, now(w) - 60_000, 0, earlier.event_id)
    ((_, _, resp),) = answer(w, "open_portal", target="yard_door")
    assert resp in ("ready_compliance", "reluctant_compliance")
    (rev,) = kinds(w, "REFUSAL_REVISED")
    assert rev["refusal_id"] == rid
    assert w.store.query_one("SELECT status FROM refusals WHERE refusal_id = ?", (rid,))[0] == "revised"
