"""Recall: looking one thing up in your own head before you decide (P6, Actor v2 — Actor Spec §7).
Rule CONSULT-05 (mind/consult.py recall).

What a person remembers beyond what the moment brought to mind: their own episodes and beliefs
that the packet did not show, found by the words they try to remember or by who it is about, each
line saying how they know it and how long ago. Nobody else's records, and "nothing comes back" is
never "it did not happen".

June at the metal fence, with a packet that shows one memory and one belief.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import LOD
from as_engine.contracts.events import Event, EventType
from as_engine.contracts.mind import WritebackOutput
from as_engine.contracts.settings import PacketRules, RulesConfig
from as_engine.mind import consult, memory, perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet

pytestmark = pytest.mark.phase(6)

HOUR = 3_600_000
NOTHING = ["Nothing more comes back to you."]


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def cue_ids(canon):
    return frozenset(r.rsplit("/", 1)[1] for r in canon.refs("cue"))


@pytest.fixture
def june(scenario):
    """(world, t, base): the crash, then Mara calls to June; June's aftermath packet to write episodes with."""
    w = scenario("metal_fence", rules=RulesConfig(packet=PacketRules(max_memories=1, max_beliefs=1)))
    t = now(w)
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", at=t, turn_index=0,
                              payload={"source_db": 98, "kind": "metal_crash", "text": "a loud metal crash",
                                       "place_id": w.id("alley"), "anchor_id": w.id("fence_sheet")}))
        tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=t + 1500, turn_index=0,
                              actor_id=w.id("mara"), payload={"words": "June, stay where you are.", "volume": "raised",
                                                             "to": [w.id("june")], "source_db": 70}))
        for x in ("june", "nita"):
            perception.compile_scene(tx, w.id(x), t + 2000, 0)
        base = memory.build_aftermath(tx, w.id("june"), 0, t + 2000)
    return w, t, base


def episode(w, canon, base, *, at, salience, summary, subjects=(), holder="june"):
    s1 = next(h for h in base.handles if h[0] == "S")
    handles = {"S1": base.handles[s1], **{f"P{i}": w.id(x) for i, x in enumerate(subjects, 1)}}
    pkt = base.model_copy(update={"handles": handles, "entities": [], "percepts": [], "utterances": [], "relationships": []})
    with w.store.transaction() as tx:
        memory.apply_writeback(tx, w.id(holder), WritebackOutput(episode=summary, salience=salience), pkt, at, 0,
                               cue_ids=cue_ids(canon))
    return w.store.query_one("SELECT episode_id FROM episodes WHERE holder_id = ? ORDER BY rowid DESC LIMIT 1",
                             (w.id(holder),))[0]


def guess(w, t, text, about="nita", confidence=2):
    """A belief June forms for herself (perception.infer), citing what she heard."""
    mine = [r[0] for r in w.store.query("SELECT percept_id FROM percept_log WHERE holder_id = ? AND channel = 'speech'",
                                        (w.id("june"),))]
    with w.store.transaction() as tx:
        return perception.infer(tx, w.id("june"), about=("body", w.id(about)), text=text, confidence=confidence,
                                because=mine, at=t + 2000, turn_index=0)


def recall(w, at, query, subjects=()):
    with w.store.transaction() as tx:
        aff = enumerate_affordances(tx, w.id("june"), w.canon.all("affordance"), at, 0)
        p = build_packet(tx, w.id("june"), LOD.HOT, aff, 0, at)
        return p, consult.recall(tx, p, query, [w.id(s) for s in subjects], 0, at)


def shown_episodes(p):
    return {v for k, v in p.handles.items() if k.startswith("E")}


def test_recall_brings_back_what_the_moment_did_not(june, canon):
    w, t, base = june
    big = episode(w, canon, base, at=t - 100 * HOUR, salience=95, summary="The night the gate fell.")
    key = episode(w, canon, base, at=t - 5 * HOUR, salience=10, summary="Nita hid the spare key under the floorboard.")
    at = t + 2000
    p, lines = recall(w, at, "Where did the spare key go?")
    assert big in shown_episodes(p) and key not in shown_episodes(p), "the packet shows one memory"
    assert lines == ["You remember (5 hours ago): Nita hid the spare key under the floorboard."]


def test_what_the_packet_already_shows_is_not_repeated(june, canon):
    w, t, base = june
    big = episode(w, canon, base, at=t - 100 * HOUR, salience=95, summary="The night the gate fell.")
    p, lines = recall(w, t + 2000, "What happened the night the gate fell?")
    assert big in shown_episodes(p) and lines == NOTHING


def test_recall_about_someone_finds_memories_then_beliefs_about_them(june, canon):
    w, t, base = june
    episode(w, canon, base, at=t - 100 * HOUR, salience=95, summary="The night the gate fell.")
    walk = episode(w, canon, base, at=t - 30 * HOUR, salience=20, summary="Walked the perimeter together.",
                   subjects=("nita",))
    guess(w, t, "Mara is scared.", about="mara", confidence=2)     # shown: the packet's one belief
    guess(w, t, "Nita keeps a knife in her boot.", confidence=1)
    at = t + 2000
    p, lines = recall(w, at, None, subjects=("nita",))
    assert walk not in shown_episodes(p)
    assert [b.text for b in p.beliefs] == ["Mara is scared."]
    assert lines == ["You remember (1 day ago): Walked the perimeter together.",
                     "You believe (your own guess, just now): Nita keeps a knife in her boot."]


def test_a_belief_matches_on_a_whole_word(june, canon):
    w, t, base = june
    guess(w, t, "Mara is scared.", about="mara", confidence=2)
    guess(w, t, "Nita counts the cans every night.", confidence=1)
    _p, lines = recall(w, t + 2000, "cans")
    assert lines == ["You believe (your own guess, just now): Nita counts the cans every night."]
    _p, lines = recall(w, t + 2000, "canst")
    assert lines == NOTHING, "a longer word is not the same word"


def test_at_most_three_lines_memories_first(june, canon):
    w, t, base = june
    episode(w, canon, base, at=t - 100 * HOUR, salience=95, summary="The night the gate fell.")
    for i, s in enumerate((30, 20, 10, 5)):
        episode(w, canon, base, at=t - (i + 1) * HOUR, salience=s, summary=f"The water barrel was low, day {i + 1}.")
    guess(w, t, "Mara is scared.", about="mara", confidence=2)
    guess(w, t, "The water barrel leaks.", confidence=1)
    _p, lines = recall(w, t + 2000, "the water barrel")
    assert len(lines) == consult.MAX_RECALL == 3
    assert [ln.split(": ", 1)[1] for ln in lines] == ["The water barrel was low, day 1.", "The water barrel was low, day 2.",
                                                      "The water barrel was low, day 3."], "salience desc"


def test_nothing_found_is_only_that(june, canon):
    w, t, base = june
    _p, lines = recall(w, t + 2000, "zeppelins")
    assert lines == NOTHING


def test_recall_reads_only_the_holders_own_records(june, canon):
    w, t, base = june
    with w.store.transaction() as tx:
        nb = memory.build_aftermath(tx, w.id("nita"), 0, t + 2000)
    episode(w, canon, nb, at=t - HOUR, salience=50, summary="Hid the spare key under the floorboard.", holder="nita")
    _p, lines = recall(w, t + 2000, "spare key")
    assert lines == NOTHING, "Nita's memory is not June's"
