"""What people say stays said (D-117). Rules DOS-05 (action.resolve: a SPEECH writes its speaker's voice
line), THREAD-01 (mind/packet.py), through whole turns on the Night at Delgado's.

Until D-117 nothing wrote voice_lines: a person never saw what they had said themselves, and on the next
turn nobody saw what anyone had said. Now Mara's "Quiet." and June's "What was that?" are their voice
lines, and on the next turn each person there has the words as they heard them.
"""

from __future__ import annotations

import pytest
from slice_kit import pick, play, script_night_at_delgados

from as_engine.contracts.common import CallClass
from as_engine.mind import actor
from as_engine.prompts.render import render

pytestmark = pytest.mark.phase(7)


def packets(fake, w, who):
    out = []
    for r in fake.calls(CallClass.ACTOR_COGNITION, actor_id=w.id(who)):
        out.append(r.context.packet if hasattr(r.context, "packet") else r.context)
    return out


def test_what_people_say_is_kept_and_heard_the_next_turn(scenario, fake):
    w = scenario("metal_fence")
    s = w.session()
    script_night_at_delgados(w, fake)
    assert play(s, "do", "I watch the front window and keep quiet.").ok
    lines = [(w.local(r["actor_id"]), r["text"], r["event_id"]) for r in
             w.store.query("SELECT actor_id, text, event_id FROM voice_lines ORDER BY at, line_id")]
    assert [(who, text) for who, text, _e in lines] == [("mara", "Quiet."), ("june", "What was that?")]
    for who, text, eid in lines:
        sp = w.store.query_one("SELECT actor_id, at FROM events WHERE type = 'SPEECH' AND cause_event_id = ?", (eid,))
        st = w.store.query_one("SELECT type, actor_id FROM events WHERE event_id = ?", (eid,))
        assert (st["type"], st["actor_id"], sp["actor_id"]) == ("ACTION_START", w.id(who), w.id(who)), \
            "the line names the utterance it came from"
    assert actor.recent_lines(w.store, w.id("mara"), 5) == ["Quiet."], "she knows what she said (DOS-05)"
    assert not w.store.query("SELECT 1 FROM voice_lines WHERE actor_id IN (?, ?)", (w.id("alice"), w.id("nita")))

    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "observe_area"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    assert play(s, "do", "I keep watching.").ok
    first, second = packets(fake, w, "alice")
    assert first.thread == [], "nothing was said before the first moment"
    mara = next(e.handle for e in second.entities if second.handles[e.handle] == w.id("mara"))
    june = next(e.handle for e in second.entities if second.handles[e.handle] == w.id("june"))   # D-153: kept in mind
    assert [(x.speaker, x.words) for x in second.thread] == [(mara, "Quiet."), (june, "What was that?")], \
        "Alice heard both, in the order they were said, each named as she knows them"
    assert 'What was said here before this moment (oldest first)\n' in render(CallClass.ACTOR_COGNITION, p=second)[1].content
    _m1, m2 = packets(fake, w, "mara")
    assert [x.speaker for x in m2.thread][0] == "you" and m2.thread[0].words == "Quiet.", "her own words come first"
    _j1, j2 = packets(fake, w, "june")
    assert ("you", "What was that?") in [(x.speaker, x.words) for x in j2.thread]
