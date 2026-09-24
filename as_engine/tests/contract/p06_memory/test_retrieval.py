"""Memory retrieval and its place in the Skull Packet (P6). Rules MEM-10..17, SKULL-09
(mind/retrieval.py; mind/packet.py from P6).

The model never chooses what it remembers: code computes what this moment is about (the key set)
and ranks beliefs, memories, lessons, loops and refusals by fixed arithmetic, ties broken by id.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import LOD, CallClass, OpenLoopKind
from as_engine.contracts.events import Event, EventType
from as_engine.contracts.mind import WritebackOutput
from as_engine.contracts.settings import PacketRules, RulesConfig
from as_engine.mind import firewall, memory, mind, perception, retrieval
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet, estimate_tokens
from as_engine.prompts.render import render

pytestmark = pytest.mark.phase(6)

EVERYONE = ("pc", "mara", "alice", "june", "eli", "nita", "stranger")
HOUR = 3_600_000


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def rb(hours):
    """MEM-12 spelled out."""
    return max(0.0, 20.0 - max(0.0, hours) / 6.0)


def cue_ids(canon):
    return frozenset(r.rsplit("/", 1)[1] for r in canon.refs("cue"))


def moment(w, words="June, stay where you are. Nita is checking the cans.", *, speaker="mara", to="june", at=None):
    """The crash, then someone speaks; everyone takes in the moment (turn 0)."""
    t = now(w) if at is None else at
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", at=t, turn_index=0,
                              payload={"source_db": 98, "kind": "metal_crash", "text": "a loud metal crash",
                                       "place_id": w.id("alley"), "anchor_id": w.id("fence_sheet")}))
        tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=t + 1500, turn_index=0, actor_id=w.id(speaker),
                              payload={"words": words, "volume": "raised", "to": [w.id(to)], "source_db": 70}))
        for x in EVERYONE:
            perception.compile_scene(tx, w.id(x), t + 2000, 0)
    return t


def get(w, local, at, **caps):
    kw = {"max_beliefs": 12, "max_memories": 6, "max_loops": 8, **caps}
    with w.store.transaction() as tx:
        return retrieval.retrieve(tx, w.id(local), 0, at, **kw)


def packet(w, canon, local, at):
    with w.store.transaction() as tx:
        aff = enumerate_affordances(tx, w.id(local), canon.all("affordance"), at, 0)
        return build_packet(tx, w.id(local), LOD.HOT, aff, 0, at)


# =========================================================================== MEM-12
@pytest.mark.parametrize("hours,bonus", [(0, 20.0), (6, 19.0), (60, 10.0), (120, 0.0), (500, 0.0), (-3, 20.0)])
def test_recency_bonus(hours, bonus):
    assert retrieval.recency_bonus(hours) == pytest.approx(bonus)


# =========================================================================== MEM-11
def test_the_key_set_is_what_this_moment_is_about(scenario):
    """MEM-11: the holder's place, the sources of its percepts, the people it can name who are
    named in what it heard, its open loops' subjects and its task's targets. Never its own words."""
    w = scenario("metal_fence")
    t = moment(w)
    with w.store.transaction() as tx:
        mind.open_loop(tx, w.id("june"), OpenLoopKind.FEAR, "The thin man", [w.id("stranger")], 2, None, t, 0)
    r = get(w, "june", t + 2000)
    rows = w.store.query("SELECT source_id FROM percept_log WHERE holder_id = ? AND turn_index = 0", (w.id("june"),))
    bodies = {x[0] for x in w.store.query("SELECT body_id FROM bodies")}
    sources = {x[0] for x in rows if x[0] in bodies}
    place = w.store.query_one("SELECT place_id FROM positions WHERE body_id = ?", (w.id("june"),))[0]
    assert r.moment_keys == {place} | sources | {w.id("nita")}
    assert r.keys == r.moment_keys | {w.id("stranger")}, "the thin man is on her mind, not in front of her"
    assert w.id("mara") in sources, "the voice she knows"
    assert w.id("alice") not in r.keys and w.id("june") not in r.keys


def test_a_first_name_is_enough(scenario):
    """MEM-11: the known name, or its first word when that has 3+ letters, as a whole word."""
    w = scenario("metal_fence")
    t = moment(w, "Where did owen go? Ali said nothing.")
    r = get(w, "june", t + 2000)
    assert w.id("pc") in r.keys, "'owen' names Owen (case-insensitive)"
    assert w.id("alice") not in r.keys, "'Ali' is not a whole-word match for Alice"


# =========================================================================== MEM-13 beliefs
def test_beliefs_rank_by_confidence_recency_and_relevance(scenario):
    """MEM-13: score = confidence*10 + recency_bonus + 15 if its subject is in K; ties by claim id."""
    w = scenario("metal_fence")
    t = now(w)
    first = get(w, "nita", t)
    assert [b["text"] for b in first.beliefs] == ["The alley was clear at eleven.",
                                                  "A thin man has been watching the back fence at night."]
    alley, fence = first.beliefs
    assert (alley["score"], fence["score"]) == (pytest.approx(20 + rb(0) + 15), pytest.approx(20 + rb(0)))
    assert set(alley) == {"claim_id", "text", "confidence", "provenance", "acquired_at", "score"}
    assert (alley["confidence"], alley["provenance"], alley["acquired_at"]) == (2, "witnessed", t)
    with w.store.transaction() as tx:
        mind.open_loop(tx, w.id("nita"), OpenLoopKind.QUESTION, "Who is the thin man?", [w.id("stranger")], 2, None, t, 0)
    later = get(w, "nita", t + 60 * HOUR)
    assert [b["score"] for b in later.beliefs] == [pytest.approx(20 + rb(60) + 15)] * 2
    assert [b["claim_id"] for b in later.beliefs] == sorted(b["claim_id"] for b in later.beliefs), "a tie goes to the lower id"
    assert len(get(w, "nita", t, max_beliefs=1).beliefs) == 1


def test_a_superseded_or_disbelieved_belief_is_never_retrieved(scenario):
    w = scenario("metal_fence")
    t = moment(w)
    mine = [r[0] for r in w.store.query("SELECT percept_id FROM percept_log WHERE holder_id = ? AND channel = 'speech'",
                                        (w.id("june"),))]
    with w.store.transaction() as tx:
        a = perception.infer(tx, w.id("june"), about=("body", w.id("mara")), text="Mara is scared", confidence=2,
                             because=mine, at=t + 2000, turn_index=0)
        b = perception.infer(tx, w.id("june"), about=("body", w.id("mara")), text="Mara is scared!", confidence=1,
                             because=mine, at=t + 3000, turn_index=0)
    ids = [x["claim_id"] for x in get(w, "june", t + 3000).beliefs]
    assert b in ids and a not in ids


# =========================================================================== MEM-14 episodes
def _episode(w, canon, base, *, at, salience, summary, subjects=()):
    """One episode for June with chosen subjects (the packet's P handles decide subject_ids)."""
    s1 = next(h for h in base.handles if h[0] == "S")
    handles = {"S1": base.handles[s1], **{f"P{i}": w.id(x) for i, x in enumerate(subjects, 1)}}
    pkt = base.model_copy(update={"handles": handles, "entities": [], "percepts": [], "utterances": [], "relationships": []})
    with w.store.transaction() as tx:
        memory.apply_writeback(tx, w.id("june"), WritebackOutput(episode=summary, salience=salience), pkt, at, 0,
                               cue_ids=cue_ids(canon))
    return w.store.query_one("SELECT episode_id FROM episodes WHERE holder_id = ? ORDER BY rowid DESC LIMIT 1", (w.id("june"),))[0]


def test_memories_anchors_first_then_by_score(scenario, canon):
    """MEM-14: anchors first (at most two); then salience + 20 (a subject in K) + 15 (matches what
    was just said) + recency; the FTS query is the content words of this turn's heard speech."""
    w = scenario("metal_fence")
    t = moment(w)
    with w.store.transaction() as tx:
        base = memory.build_aftermath(tx, w.id("june"), 0, t + 2000)
    anchor = _episode(w, canon, base, at=t - 100 * HOUR, salience=95, summary="The night the gate fell.")
    relevant = _episode(w, canon, base, at=t - 50 * HOUR, salience=30, summary="Walked the perimeter with someone.",
                        subjects=("nita",))
    recent = _episode(w, canon, base, at=t, salience=30, summary="Heard something outside.")
    fts = _episode(w, canon, base, at=t - 10 * HOUR, salience=20, summary="Lost count of the cans again.")
    low = _episode(w, canon, base, at=t - 200 * HOUR, salience=5, summary="A dull afternoon.")
    at = t + 2000
    got = get(w, "june", at, max_memories=4)
    h = lambda ms: (at - ms) / HOUR  # noqa: E731
    assert [e["episode_id"] for e in got.episodes] == [anchor, relevant, fts, recent]
    by = {e["episode_id"]: e for e in got.episodes}
    assert by[relevant]["score"] == pytest.approx(30 + 20 + rb(h(t - 50 * HOUR)))
    assert by[fts]["score"] == pytest.approx(20 + 15 + rb(h(t - 10 * HOUR)))
    assert by[recent]["score"] == pytest.approx(30 + rb(h(t)))
    assert by[anchor]["anchor"] == 1 and set(by[anchor]) == {"episode_id", "summary", "at", "salience", "anchor", "score"}
    assert low not in by, "max_memories counts the anchors"


def test_at_most_two_anchors_jump_the_queue(scenario, canon):
    w = scenario("metal_fence")
    t = moment(w, "Quiet now.")
    with w.store.transaction() as tx:
        base = memory.build_aftermath(tx, w.id("june"), 0, t + 2000)
    a1 = _episode(w, canon, base, at=t - HOUR, salience=91, summary="First.")
    a2 = _episode(w, canon, base, at=t - 2 * HOUR, salience=99, summary="Second.")
    a3 = _episode(w, canon, base, at=t - 3 * HOUR, salience=95, summary="Third.")
    plain = _episode(w, canon, base, at=t, salience=80, summary="Fourth.")
    got = [e["episode_id"] for e in get(w, "june", t + 2000).episodes]
    assert got[:2] == [a2, a3], "salience desc"
    assert got[2:] == [a1, plain], "the third anchor competes on score: 91 + ~19.8 beats 80 + ~20"


def test_no_speech_no_search_bonus(scenario, canon):
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", at=t, turn_index=0,
                              payload={"source_db": 98, "kind": "metal_crash", "text": "a loud metal crash",
                                       "place_id": w.id("alley"), "anchor_id": w.id("fence_sheet")}))
        perception.compile_scene(tx, w.id("june"), t + 1000, 0)
        base = memory.build_aftermath(tx, w.id("june"), 0, t + 1000)
    e = _episode(w, canon, base, at=t, salience=10, summary="The cans the cans the cans.")
    (got,) = get(w, "june", t + 1000).episodes
    assert got["episode_id"] == e and got["score"] == pytest.approx(10 + rb((t + 1000 - t) / HOUR))


# =========================================================================== MEM-15..17
def test_lessons_come_back_when_their_cues_are_present(scenario):
    """MEM-15: cue_tags meeting mind.cues.cues_of; confidence desc, newest first, id; at most 3."""
    w = scenario("metal_fence")
    t = moment(w)
    with w.store.transaction() as tx:
        a = mind.learn(tx, w.id("june"), ["metal_crash"], "Crashes out back mean the fence.", "", "", None, t - 30, 0)
        b = mind.learn(tx, w.id("june"), ["loud_noise"], "Loud means close.", "", "", None, t - 20, 0)
        mind.learn(tx, w.id("june"), ["loud_noise"], "Loud means close.", "", "", None, t - 19, 0)
        d = mind.learn(tx, w.id("june"), ["metal_crash"], "Metal carries far at night.", "", "", None, t - 10, 0)
        e = mind.learn(tx, w.id("june"), ["loud_noise", "gunshot_close"], "Get down first.", "", "", None, t - 5, 0)
        mind.learn(tx, w.id("june"), ["gunshot_close"], "Shots mean run.", "", "", None, t - 1, 0)
    got = get(w, "june", t + 2000).lessons
    assert retrieval.MAX_LESSONS == 3
    assert [x["lesson_id"] for x in got] == [b, e, d], "b is reinforced (3); then the newest confidence-2 ones"
    assert a not in [x["lesson_id"] for x in got]
    assert set(got[0]) == {"lesson_id", "text", "confidence", "cue_tags"} and got[0]["confidence"] == 3


def test_loops_about_this_moment_come_first(scenario):
    """MEM-16."""
    w = scenario("metal_fence")
    t = moment(w)
    with w.store.transaction() as tx:
        about_nita = mind.open_loop(tx, w.id("june"), OpenLoopKind.QUESTION, "Is Nita all right?", [w.id("nita")], 1, None, t, 0)
        strong = mind.open_loop(tx, w.id("june"), OpenLoopKind.GOAL, "Finish the count", [], 3, None, t, 0)
        about_alice = mind.open_loop(tx, w.id("june"), OpenLoopKind.GRUDGE, "Alice took the good shelf", [w.id("alice")], 2,
                                     None, t, 0)
    got = get(w, "june", t + 2000).loops
    assert [x["loop_id"] for x in got] == [about_nita, strong, about_alice]
    assert got[0] == {"loop_id": about_nita, "kind": "question", "text": "Is Nita all right?", "strength": 1,
                      "subject_ids": [w.id("nita")]}
    assert [x["loop_id"] for x in get(w, "june", t + 2000, max_loops=2).loops] == [about_nita, strong]


def test_a_standing_refusal_comes_back_when_the_asker_is_here(scenario):
    """MEM-17, WILL-05: here = heard or seen well enough to know who (Mara sees Owen at the dark
    counter only as a figure, but she knows his voice), or named."""
    w = scenario("metal_fence")
    t = moment(w, "Mara, I need that revolver.", speaker="pc", to="mara")
    with w.store.transaction() as tx:
        firewall.record_refusal(tx, w.id("mara"), w.id("pc"), f"give_item:{w.id('pc')}", "hand over the revolver", "loyalty",
                                [], "", False, t - HOUR, 0, None)
        firewall.record_refusal(tx, w.id("mara"), w.id("june"), f"leave_place:{w.id('sales_floor')}", "leave the store", "duty",
                                [], "", False, t - HOUR, 0, None)
    got = get(w, "mara", t + 2000)
    assert w.id("pc") in got.moment_keys and w.id("june") not in got.keys
    assert [x["summary"] for x in got.refusals] == ["hand over the revolver"]
    assert set(got.refusals[0]) == {"refusal_id", "requester_id", "summary", "times_asked", "created_at"}
    t2 = moment(w, "And June wants to leave.", speaker="pc", to="mara", at=t + 5000)
    both = get(w, "mara", t2 + 2000)
    assert [x["summary"] for x in both.refusals] == ["hand over the revolver", "leave the store"], "June is named"


def test_retrieval_is_deterministic_and_reads_only_the_holder(scenario, canon):
    """MEM-10: the same state gives the same answer; nothing of another mind comes back."""
    w = scenario("metal_fence")
    t = moment(w)
    with w.store.transaction() as tx:
        mbase = memory.build_aftermath(tx, w.id("mara"), 0, t + 2000)
        memory.apply_writeback(tx, w.id("mara"), WritebackOutput(episode="Told June to stay put.", salience=50), mbase, t + 2000, 0,
                               cue_ids=cue_ids(canon))
    one, two = get(w, "june", t + 2000), get(w, "june", t + 2000)
    assert one == two
    assert one.episodes == []
    theirs = {r[0] for r in w.store.query("SELECT claim_id FROM claim_holdings WHERE holder_id != ?", (w.id("june"),))}
    mine = {r[0] for r in w.store.query("SELECT claim_id FROM claim_holdings WHERE holder_id = ?", (w.id("june"),))}
    assert {b["claim_id"] for b in one.beliefs} <= mine and theirs - mine


# =========================================================================== the packet from P6
def test_the_packet_carries_what_retrieval_found(scenario, canon):
    """packet.py from P6: memories as E handles in retrieval order, lessons as 'Experience taught
    you' lines, beliefs / loops / refusals in retrieval order."""
    w = scenario("metal_fence")
    t = moment(w)
    with w.store.transaction() as tx:
        base = memory.build_aftermath(tx, w.id("june"), 0, t + 2000)
    e1 = _episode(w, canon, base, at=t - HOUR, salience=60, summary="Nita said she'd walk the fence.", subjects=("nita",))
    e2 = _episode(w, canon, base, at=t - 2 * HOUR, salience=20, summary="Counted the tins twice.")
    with w.store.transaction() as tx:
        mind.learn(tx, w.id("june"), ["metal_crash"], "Crashes out back mean the fence.", "", "", None, t, 0)
        loop = mind.open_loop(tx, w.id("june"), OpenLoopKind.QUESTION, "Is Nita all right?", [w.id("nita")], 1, None, t, 0)
    p = packet(w, canon, "june", t + 2000)
    r = get(w, "june", t + 2000)
    assert [(m.handle, p.handles[m.handle]) for m in p.memories] == [("E1", e1), ("E2", e2)]
    assert [m.text for m in p.memories] == ["Nita said she'd walk the fence.", "Counted the tins twice."]
    assert p.memories[0].age_text == "1 hour ago"
    assert p.lessons == ["Experience taught you: Crashes out back mean the fence."]
    assert [b.text for b in p.beliefs] == [b["text"] for b in r.beliefs]
    assert [p.handles[x.handle] for x in p.open_loops] == [x["loop_id"] for x in r.loops] and loop in p.handles.values()
    text = render(CallClass.ACTOR_COGNITION, p=p)[1].content
    assert "What experience has taught you:\n- Experience taught you: Crashes out back mean the fence." in text
    assert "- E1 (1 hour ago): Nita said she'd walk the fence." in text


def test_what_bears_on_the_moment_is_never_cut(scenario, canon):
    """Actor Spec AC16 (SKULL-09): Owen asks Mara for the revolver again; her nine-day-old refusal
    of him stays in the packet whatever the budget, because he is the one asking now. June's
    eight-day-old refusal comes back only because she is named, and goes like any old line. Every
    line the budget cut is on record in ``omitted``, in drop order — never in the prompt."""
    DAY = 24 * HOUR

    def world(rules=None):
        w = scenario("metal_fence", rules=rules)
        t = moment(w, "Mara, give me the revolver. June wants to leave too.", speaker="pc", to="mara")
        with w.store.transaction() as tx:
            firewall.record_refusal(tx, w.id("mara"), w.id("pc"), f"give_item:{w.id('pc')}", "hand over the revolver",
                                    "loyalty", [], "", False, t - 9 * DAY, 0, None)
            firewall.record_refusal(tx, w.id("mara"), w.id("june"), f"leave_place:{w.id('sales_floor')}",
                                    "leave the store", "duty", [], "", False, t - 8 * DAY, 0, None)
        return w, t

    w, t = world()
    full = packet(w, canon, "mara", t + 2000)
    assert full.refusals == ["You refused: hand over the revolver.", "You refused: leave the store."]
    assert full.omitted == []
    w2, t2 = world(RulesConfig(packet=PacketRules(token_budget={"hot": 10, "warm": 10, "reaction": 10})))
    p = packet(w2, canon, "mara", t2 + 2000)
    assert p.refusals == ["You refused: hand over the revolver."], "the one asking now"
    sources = {full.handles[x.source_handle] for x in full.perceived_now if x.source_handle} | \
              {full.handles[u.speaker_handle] for u in full.utterances if u.speaker_handle}
    assert w.id("pc") in sources and w.id("june") not in sources
    assert p.omitted == ([f"memory: {m.text}" for m in reversed(full.memories)]
                         + [f"lesson: {x}" for x in reversed(full.lessons)]
                         + [f"belief: {b.text}" for b in reversed(full.beliefs)]
                         + [f"relationship: {r.handle}: {r.text}" for r in reversed(full.relationships)
                            if full.handles[r.handle] not in sources]
                         + ["refusal: You refused: leave the store."]
                         + [f"uncertainty: {x}" for x in reversed(full.uncertainty)])
    assert "belief: Nita walks the alley at eleven; it's clear." in p.omitted
    text = "\n".join(m.content for m in render(CallClass.ACTOR_COGNITION, p=p))
    assert "hand over the revolver" in text and "leave the store" not in text
    assert "omitted" not in text and "belief: " not in text


def test_the_budget_drops_memories_then_lessons_then_beliefs(scenario, canon):
    """SKULL-09 from P6: memories (last first), then lessons (last first), then beliefs."""

    def seeded(rules=None):
        w = scenario("metal_fence", rules=rules)
        t = moment(w)
        with w.store.transaction() as tx:
            base = memory.build_aftermath(tx, w.id("june"), 0, t + 2000)
        _episode(w, canon, base, at=t - HOUR, salience=60, summary="Nita said she'd walk the fence.")
        _episode(w, canon, base, at=t - 2 * HOUR, salience=20, summary="Counted the tins twice.")
        heard = [r[0] for r in w.store.query("SELECT percept_id FROM percept_log WHERE holder_id = ? AND channel = 'speech'",
                                             (w.id("june"),))]
        with w.store.transaction() as tx:
            mind.learn(tx, w.id("june"), ["metal_crash"], "Crashes out back mean the fence.", "", "", None, t, 0)
            mind.learn(tx, w.id("june"), ["loud_noise"], "Loud means close.", "", "", None, t + 1, 0)
            perception.infer(tx, w.id("june"), about=("body", w.id("mara")), text="Mara is worried about Nita.", confidence=2,
                             because=heard, at=t + 2000, turn_index=0)
        return packet(w, canon, "june", t + 2000)

    full = seeded()
    size = estimate_tokens("\n".join(m.content for m in render(CallClass.ACTOR_COGNITION, p=full)))
    assert (len(full.memories), len(full.lessons), len(full.beliefs)) == (2, 2, 1)

    def cut(n):
        return seeded(RulesConfig(packet=PacketRules(token_budget={"hot": n, "warm": n, "reaction": n})))

    one_less = cut(size - 1)
    assert [m.text for m in one_less.memories] == [full.memories[0].text] and one_less.lessons == full.lessons
    seen_lesson_drop = seen_belief_drop = False
    for n in range(size - 1, 0, -max(1, size // 14)):
        p = cut(n)
        assert [m.text for m in p.memories] == [m.text for m in full.memories][:len(p.memories)], "last first"
        assert p.lessons == full.lessons[:len(p.lessons)]
        assert [b.text for b in p.beliefs] == [b.text for b in full.beliefs][:len(p.beliefs)]
        if len(p.lessons) < len(full.lessons):
            seen_lesson_drop = True
            assert p.memories == [], "no lesson goes while a memory is left"
        if len(p.beliefs) < len(full.beliefs):
            seen_belief_drop = True
            assert p.memories == [] and p.lessons == [], "no belief goes while a memory or lesson is left"
    assert seen_lesson_drop and seen_belief_drop
    bare = cut(10)
    assert bare.memories == [] and bare.lessons == [] and bare.beliefs == []
    assert bare.omitted[:5] == ([f"memory: {m.text}" for m in reversed(full.memories)]
                                + [f"lesson: {x}" for x in reversed(full.lessons)]
                                + [f"belief: {b.text}" for b in reversed(full.beliefs)]), "last first, kind by kind"
