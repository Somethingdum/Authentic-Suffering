"""Letting it pass (D-270). turn/select.py SEL-03 owed_answer.

The player asked a woman whether the water was safe; she heard him, thought about it, and said nothing — and on every
turn after, for half an hour of the world's time, she was made to think it over again with the main model, because
the question was still "unanswered". Letting a question pass is an answer. It is put to her again only when someone
asks her something after she last made up her mind.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import CallClass
from as_engine.turn import select

from slice_kit import pick, play

pytestmark = pytest.mark.phase(7)


def flags(w, who):
    st = w.store
    with st.transaction() as tx:
        T = st.query_one("SELECT turn_index FROM world_clock")[0] + 1
        at = st.query_one("SELECT now_ms FROM world_clock")[0]
        return select.salience_flags(tx, w.id(who), [w.id(who)], w.id("pc"), T, at)


def calls(w, who, turn):
    return dict(w.store.query("SELECT call_class, COUNT(*) FROM lm_calls WHERE turn_index=? AND actor_id=? GROUP BY call_class",
                              (turn, w.id(who))))


def test_a_question_she_let_pass(scenario, fake):
    w = scenario("metal_fence")
    s = w.session()
    s.extras["forced_addressee"] = w.id("mara")
    o = play(s, "say", "Mara, is the water here safe to drink?")
    assert o.ok and calls(w, "mara", o.turn_index).get("actor_reaction") == 1, "she heard it and made up her mind"
    assert not w.store.query("SELECT 1 FROM events WHERE type='SPEECH' AND actor_id=?", (w.id("mara"),)), "and said nothing"
    f = flags(w, "mara")
    assert not f["owed_answer"], "a question let pass is not put to her again"
    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "observe_area"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    o = play(s, "do", "I keep watching.")
    assert o.ok and calls(w, "mara", o.turn_index).get(CallClass.ACTOR_COGNITION.value) is None


def test_asked_again_after_she_decided(scenario, fake):
    w = scenario("metal_fence")
    s = w.session()
    s.extras["forced_addressee"] = w.id("mara")
    play(s, "say", "Mara, is the water here safe to drink?")
    from as_engine.contracts.events import Event, EventType
    from as_engine.mind import perception
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("pc"), at=t,
                                   turn_index=w.store.query_one("SELECT turn_index FROM world_clock")[0],
                                   payload={"words": "Mara? The water?", "volume": "normal", "to": [w.id("mara")],
                                            "source_db": 60, "armed": False}))
        perception.compile_aftermath(tx, w.id("mara"), [ev], t + 500, ev.turn_index)
    assert flags(w, "mara")["owed_answer"], "asked again after she made up her mind, it is hers to answer again"
