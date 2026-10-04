"""What was said here (D-117). Rules THREAD-01, THREAD-02 (mind/packet.py thread_lines, the budget;
prompts/actor_cognition.user.j2), DOS-05 (action.resolve: a SPEECH writes its speaker's voice line).

The owner: "I definitely need group dynamics, NPC interaction, conversations and what not buffed." Actor
Spec §11: "Keep a short holder-specific conversation thread: delivered words, recognized speakers,
intended addressee where known, unanswered questions and current topic. Never inject the UI's complete
chat transcript. Remembered statements outside the room enter only through legitimate memory or later
report." A person deciding now sees what was said where they are — as they heard it — and what they
said themselves, and knows when a question to them is still hanging.
"""

from __future__ import annotations

import copy

import pytest

from as_engine.contracts.common import LOD, CallClass
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.contracts.settings import RulesConfig
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet, estimate_tokens
from as_engine.physical import space
from as_engine.prompts.render import render
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(4)

MIN = 60_000
HEADING = "What was said here before this moment (oldest first)"
ROOM = {
    "schema": "as.scenario.v1", "name": "counter", "seed": 4, "start": {"day": 200, "time": "11:00"},
    "places": [{"id": "shop", "name": "Pharmacy", "light": 3, "width_m": 8, "depth_m": 6,
                "anchors": [{"id": "shop_door", "name": "back door", "kind": "door_side", "x": 7.5, "y": 3}]},
               {"id": "back", "name": "Back room", "light": 3, "width_m": 4, "depth_m": 4,
                "anchors": [{"id": "back_door", "name": "back door", "kind": "door_side", "x": 0.3, "y": 2}]}],
    "portals": [{"id": "door", "a": "shop", "b": "back", "anchor_a": "shop_door", "anchor_b": "back_door",
                 "kind": "door", "name": "back door", "open": True, "w": 90, "h": 200}],
    "bodies": [{"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "shop", "x": 6, "y": 3},
               {"id": "june", "dossier": "core:actor/june_okafor", "place": "shop", "x": 2, "y": 3},
               {"id": "mara", "dossier": "core:actor/mara_voss", "place": "shop", "x": 3, "y": 4}],
}


@pytest.fixture
def room(fixture_packs, core_pack_dir):
    worlds = []

    def make(rules=None):
        w = load_scenario(copy.deepcopy(ROOM), packs_root=fixture_packs, core_pack_dir=core_pack_dir, rules=rules)
        worlds.append(w)
        return w
    yield make
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def say(w, who, words, to, at, ti=0, volume="normal"):
    """``who`` says ``words`` at ``at``; everyone in the room perceives it as that turn's scene is compiled."""
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id(who), at=at, turn_index=ti,
                              payload={"words": words, "volume": volume, "to": [w.id(t) for t in to] or ["everyone"],
                                       "source_db": 60}))
        for b in ("june", "mara", "pc"):
            perception.compile_scene(tx, w.id(b), at + 500, ti)


def own_line(w, who, text, at):
    """A voice line as a SPEECH of theirs writes it (action.resolve, DOS-05)."""
    with w.store.transaction() as tx:
        lid = tx.mint("vln")
        tx.commit_event(Event(type=EventType.OVERRIDE, writer="action.propagate", at=at, turn_index=0, actor_id=w.id(who),
                              writes=[WriteRecord(op=WriteOp.INSERT, table="voice_lines", values={
                                  "line_id": lid, "actor_id": w.id(who), "text": text, "at": at, "event_id": "scenario",
                                  "pinned": 0})], payload={"line_id": lid}))


def packet(w, who, at, ti=1):
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(who), at, ti)
        aff = enumerate_affordances(tx, w.id(who), w.canon.all("affordance"), at, ti)
        return build_packet(tx, w.id(who), LOD.HOT, aff, ti, at)


def handle_of(p, w, who):
    (h,) = [e.handle for e in p.entities if p.handles[e.handle] == w.id(who)]
    return h


def user_prompt(p):
    return render(CallClass.ACTOR_COGNITION, p=p)[1].content


# ------------------------------------------------------------------------- THREAD-01 what is in it


def test_a_question_to_her_hangs_until_she_answers(room):
    w = room()
    t = now(w)
    say(w, "mara", "June, did you lock the back door?", ["june"], t + 1000)
    say(w, "mara", "Lock it when you can.", ["june"], t + 4000)
    p = packet(w, "june", t + 2 * MIN)
    mara = handle_of(p, w, "mara")
    got = [(x.speaker, x.to_me, x.words, x.ago_text, x.unanswered) for x in p.thread]
    assert got == [(mara, True, "June, did you lock the back door?", "1 minute ago", True),
                   (mara, True, "Lock it when you can.", "1 minute ago", False)], "only a question hangs"
    user = user_prompt(p)
    assert f'{HEADING}\n- 1 minute ago, {mara} to you: "June, did you lock the back door?" (you have not answered)\n' \
           f'- 1 minute ago, {mara} to you: "Lock it when you can."\n' in user
    assert user.index("Where you are:") < user.index(HEADING) < user.index("What reaches you")
    own_line(w, "june", "I did. Twice.", t + 2500)
    p2 = packet(w, "june", t + 2 * MIN)
    assert [(x.speaker, x.words, x.unanswered) for x in p2.thread] == [
        (mara, "June, did you lock the back door?", False), ("you", "I did. Twice.", False),
        (mara, "Lock it when you can.", False)], "her own words, in order; an answered question no longer hangs"
    assert '- 1 minute ago, you: "I did. Twice."' in user_prompt(p2)
    assert packet(w, "mara", t + 2 * MIN).thread == [], \
        "a speaker does not hear herself: her own words reach her thread only as her voice lines"


def test_only_this_turn_s_words_are_utterances_and_nothing_from_later(room):
    w = room()
    t = now(w)
    say(w, "mara", "Back door. Now.", ["june"], t + 1000, ti=0)
    say(w, "mara", "Did you hear me?", ["june"], t + 70_000, ti=1)
    p = packet(w, "june", t + 75_000, ti=1)
    assert [x.words for x in p.thread] == ["Back door. Now."], "this turn's words are the utterances, not the thread"
    assert [u.words for u in p.utterances] == ["Did you hear me?"]
    early = packet(w, "june", t + 500, ti=1)
    assert early.thread == [], "nothing said after the moment reaches a mind (SKULL-10)"


def test_the_window_and_the_room(room):
    w = room()
    t = now(w)
    say(w, "mara", "The generator needs gas.", [], t + 1000)
    assert [x.words for x in packet(w, "june", t + 31 * MIN).thread] == [], "past the window (30 minutes)"
    w2 = room(rules=RulesConfig(packet={"thread_window_min": 60}))
    t2 = now(w2)
    say(w2, "mara", "The generator needs gas.", [], t2 + 1000)
    assert [x.words for x in packet(w2, "june", t2 + 31 * MIN).thread] == ["The generator needs gas."]
    say(w2, "mara", "Did you hear me?", [], t2 + 32 * MIN)
    with w2.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w2.id("june"), w2.id("back"), None, 1.0, 1.0, t2 + 33 * MIN, None, 0))
        tx.commit_event(space.move_event(tx, w2.id("june"), w2.id("shop"), None, 2.0, 3.0, t2 + 34 * MIN, None, 0))
    assert packet(w2, "june", t2 + 35 * MIN).thread == [], \
        "she left and came back: what was said before she arrived reaches her only through memory"
    with w2.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w2.id("june"), w2.id("shop"), None, 3.0, 3.0, t2 + 36 * MIN, None, 0))
    say(w2, "mara", "Gas. Generator.", [], t2 + 37 * MIN)
    assert [x.words for x in packet(w2, "june", t2 + 38 * MIN).thread] == ["Gas. Generator."], \
        "a step within the room is not an arrival"


def test_a_short_thread_and_never_an_id(room):
    w = room(rules=RulesConfig(packet={"max_thread_lines": 3}))
    t = now(w)
    for i, words in enumerate(["One.", "Two.", "Three.", "Four.", "Five."]):
        say(w, "mara", words, [], t + 1000 * (i + 1))
    p = packet(w, "june", t + MIN)
    assert [x.words for x in p.thread] == ["Three.", "Four.", "Five."], "the last few, oldest first"
    assert all(x.speaker == handle_of(p, w, "mara") for x in p.thread)
    assert "act_" not in user_prompt(p)


# ------------------------------------------------------------------------- THREAD-02 the budget


def test_what_was_said_gives_way_after_memories_oldest_first(room):
    w = room()
    t = now(w)
    for i, words in enumerate(["First thing.", "Second thing.", "Third thing."]):
        say(w, "mara", words, [], t + 1000 * (i + 1))
    full = packet(w, "june", t + MIN)
    assert full.memories == [] and full.lessons == [] and full.voice_examples == []
    msgs = render(CallClass.ACTOR_COGNITION, p=full)
    need = estimate_tokens(msgs[0].content + "\n" + msgs[1].content)
    w2 = room(rules=RulesConfig(packet={"token_budget": {"hot": need - 1, "warm": 4000, "reaction": 3000}}))
    t2 = now(w2)
    for i, words in enumerate(["First thing.", "Second thing.", "Third thing."]):
        say(w2, "mara", words, [], t2 + 1000 * (i + 1))
    p = packet(w2, "june", t2 + MIN)
    assert [x.words for x in p.thread] == ["Second thing.", "Third thing."]
    assert p.omitted == ["thread: First thing."]
