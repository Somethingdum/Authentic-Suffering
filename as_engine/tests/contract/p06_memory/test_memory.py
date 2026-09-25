"""Aftermath and memory writeback (P6). Rules MEM-01..09, G13, G14, L8, L12, STORE-11
(mind/memory.py) and the inferred-belief writer (mind/perception.py infer).

After a turn every mind that perceived anything gets an aftermath packet holding only its own
percepts and its own record of what it did; the model writes back a memory in that mind's own
voice. Anything it writes that cites a percept the mind does not have is dropped and logged —
one item at a time; the rest applies.
"""

from __future__ import annotations

import json

import pytest

import helpers
from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.contracts.common import LOD, OpenLoopKind
from as_engine.contracts.events import Event, EventType
from as_engine.contracts.mind import WritebackOutput
from as_engine.mind import memory, mind, perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet
from as_engine.physical import space

pytestmark = pytest.mark.phase(6)

EVERYONE = ("pc", "mara", "alice", "june", "eli", "nita", "stranger")


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def maxseq(w):
    return w.store.query_one("SELECT COALESCE(MAX(seq), 0) FROM events")[0]


def cue_ids(canon):
    return frozenset(r.rsplit("/", 1)[1] for r in canon.refs("cue"))


def crash_and_call(w):
    """Turn 0: the crash in the alley; Mara calls to June; everyone takes in the moment."""
    t = now(w)
    with w.store.transaction() as tx:
        crash = tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", at=t, turn_index=0,
                                      payload={"source_db": 98, "kind": "metal_crash", "text": "a loud metal crash",
                                               "place_id": w.id("alley"), "anchor_id": w.id("fence_sheet")}))
        call = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=t + 1500, turn_index=0,
                                     actor_id=w.id("mara"),
                                     payload={"words": "June, stay where you are. Nita is checking.", "volume": "raised",
                                              "to": [w.id("june")], "source_db": 70}))
        for x in EVERYONE:
            perception.compile_scene(tx, w.id(x), t + 2000, 0)
    return t, crash, call


def june_goes_to_look(w, t):
    i = helpers.make_intent(w, "june", "go_look", destination="back_door_in",
                            label="Go and look toward the back door (4 m, about 6 seconds)", goal="See what fell out back",
                            speech=("Coming, hold on.", ["mara"], "normal"))
    with w.store.transaction() as tx:
        evs = resolve_wave(tx, w.rng, barrier(tx, [i]), t + 2000, 0, horizon_ms=t + 60_000)
        for x in EVERYONE:
            perception.compile_aftermath(tx, w.id(x), evs, t + 9000, 0)
    return evs


def aftermath(w, local, at):
    with w.store.transaction() as tx:
        return memory.build_aftermath(tx, w.id(local), 0, at)


def selected_rows(w, local):
    """The packet's row selection, spelled out: this turn's rows minus older standing views."""
    rows = [dict(r) for r in w.store.query("SELECT * FROM percept_log WHERE holder_id = ? AND turn_index = 0 "
                                           "ORDER BY at, percept_id", (w.id(local),))]
    latest = max((r["at"] for r in rows if r["event_id"].startswith("scene:")), default=None)
    return [r for r in rows if not r["event_id"].startswith("scene:") or r["at"] == latest]


def handle_of_event(pkt, w, event_id):
    for h, pid in pkt.handles.items():
        if h.startswith("S") and w.store.query_one("SELECT event_id FROM percept_log WHERE percept_id = ?", (pid,))[0] == event_id:
            return h
    raise AssertionError("no percept of that event")


def entity(pkt, name):
    return next(e.handle for e in pkt.entities if e.known_name == name)


def output(**kw):
    base = {"episode": "  Mara told me to stay put, and something hit the back fence.  ", "salience": 40}
    return WritebackOutput.model_validate({**base, **kw})


# =========================================================================== MEM-01 aftermath
def test_the_aftermath_holds_exactly_what_the_holder_perceived(scenario):
    """MEM-01, G13, L8: the S handles are this holder's rows of this turn (older standing views
    excluded), in (at, percept_id) order; nobody else's percept is in it."""
    w = scenario("metal_fence")
    t, crash, call = crash_and_call(w)
    june_goes_to_look(w, t)
    a = aftermath(w, "june", t + 9000)
    s = sorted((h for h in a.handles if h.startswith("S")), key=lambda h: int(h[1:]))
    assert [a.handles[h] for h in s] == [r["percept_id"] for r in selected_rows(w, "june")]
    assert sorted([*[p.handle for p in a.percepts], *[u.handle for u in a.utterances]], key=lambda h: int(h[1:])) == s
    others = {r[0] for r in w.store.query("SELECT percept_id FROM percept_log WHERE holder_id != ?", (w.id("june"),))}
    assert not others & set(a.handles.values())
    (u,) = a.utterances
    assert (u.words, u.addressed_to_me, a.handles[u.speaker_handle]) == \
        ("June, stay where you are. Nita is checking.", True, w.id("mara"))
    assert all(p.seconds_ago == (t + 9000 - w.store.query_one("SELECT at FROM percept_log WHERE percept_id = ?",
                                                              (a.handles[p.handle],))[0]) / 1000 for p in a.percepts)


def test_the_aftermath_and_the_packet_agree(scenario, canon):
    """MEM-01: same rows, same handles, same people, same words as the Skull Packet at that moment."""
    w = scenario("metal_fence")
    t, crash, call = crash_and_call(w)
    at = t + 2000
    a = aftermath(w, "june", at)
    with w.store.transaction() as tx:
        aff = enumerate_affordances(tx, w.id("june"), canon.all("affordance"), at, 0)
        p = build_packet(tx, w.id("june"), LOD.HOT, aff, 0, at)
    assert {h: v for h, v in a.handles.items() if h[0] in "SP"} == {h: v for h, v in p.handles.items() if h[0] in "SP"}
    assert a.percepts == p.perceived_now and a.utterances == p.utterances
    assert a.entities == p.entities and a.relationships == p.relationships
    assert a.identity == p.identity and not a.identity.minimum  # the whole card: this person reads what happened


def test_a_flood_of_words_is_remembered_as_it_was_heard(scenario):
    """MEM-01 with Actor Spec §5: the aftermath cuts a flood of words exactly as the packet does."""
    w = scenario("metal_fence")
    t = now(w)
    flood = " ".join(["sorry"] * 150) + " where did the shelf go?"
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=t + 500, turn_index=0,
                              actor_id=w.id("mara"),
                              payload={"words": flood, "volume": "raised", "to": [w.id("june")], "source_db": 70}))
        perception.compile_scene(tx, w.id("june"), t + 1000, 0)
    (u,) = aftermath(w, "june", t + 1000).utterances
    assert u.words == " ".join(["sorry"] * 133) + " …"


def test_what_the_holder_did_itself_comes_from_its_own_record(scenario):
    """MEM-01: own_action_text from its own ACTION_START / SPEECH (label without the cost part),
    own_expectation_text from the start's goal. A mind never perceives its own actions."""
    w = scenario("metal_fence")
    t, crash, call = crash_and_call(w)
    evs = june_goes_to_look(w, t)
    assert [e.type for e in evs if e.actor_id == w.id("june")][:2] == [EventType.ACTION_START, EventType.SPEECH]
    a = aftermath(w, "june", t + 9000)
    assert a.own_action_text == 'Chose to go and look toward the back door. Said: "Coming, hold on."'
    assert a.own_expectation_text == "See what fell out back"
    alice = aftermath(w, "alice", t + 9000)
    assert (alice.own_action_text, alice.own_expectation_text) == (None, None)
    assert any(u.words.startswith("Coming") for u in alice.utterances), "Alice caught part of it"
    assert not any(u.words.startswith("Coming") for u in a.utterances), "June remembers saying it, not hearing it"


def test_speaking_is_said_once_and_a_goal_that_is_just_the_label_is_no_expectation(scenario):
    w = scenario("metal_fence")
    t = now(w)
    talk = helpers.make_intent(w, "alice", "speak", target="pc", label="Say something to Owen (you choose the words and how loud)",
                               goal="Say something to Owen (you choose the words and how loud)",
                               speech=("Did you hear that?", ["pc"], "low"))
    with w.store.transaction() as tx:
        resolve_wave(tx, w.rng, barrier(tx, [talk]), t, 0, horizon_ms=t + 60_000)
    a = aftermath(w, "alice", t + 5000)
    assert a.own_action_text == 'Said: "Did you hear that?"'
    assert a.own_expectation_text is None


def test_the_aftermath_lists_only_open_loops_strongest_first(scenario):
    w = scenario("metal_fence")
    t, crash, call = crash_and_call(w)
    with w.store.transaction() as tx:
        weak = mind.open_loop(tx, w.id("june"), OpenLoopKind.QUESTION, "Where did Nita go?", [w.id("nita")], 1, None, t, 0)
        strong = mind.open_loop(tx, w.id("june"), OpenLoopKind.GOAL, "Finish the count", [], 3, None, t + 1, 0)
        done = mind.open_loop(tx, w.id("june"), OpenLoopKind.PLAN, "Eat", [], 3, None, t + 2, 0)
        mind.close_loop(tx, done, "fulfilled", None, t + 3, 0)
    a = aftermath(w, "june", t + 2000)
    assert [(line.handle, a.handles[line.handle]) for line in a.open_loops] == [("L1", strong), ("L2", weak)]
    assert [line.kind for line in a.open_loops] == [OpenLoopKind.GOAL, OpenLoopKind.QUESTION]


# =========================================================================== MEM-03 groups
def test_every_named_person_reads_it_as_themselves(scenario):
    """MEM-03 (B5, Actor Spec §13, AC11): no two people share one reading, even of the very same
    sound — every holder is a group of one, in holder id order."""
    w = scenario("metal_fence")
    t, crash, call = crash_and_call(w)
    base = aftermath(w, "stranger", t + 2000)
    twin = base.model_copy(update={"holder_id": "act_900001"})
    twin2 = base.model_copy(update={"holder_id": "act_900000"})
    groups = memory.writeback_groups({x.holder_id: x for x in (base, twin, twin2)})
    assert groups == [[h] for h in sorted([base.holder_id, "act_900000", "act_900001"])]


def test_relationship_lines_are_private(scenario):
    w = scenario("metal_fence")
    t, crash, call = crash_and_call(w)
    j = aftermath(w, "june", t + 2000)
    assert j.relationships
    assert memory.writeback_groups({j.holder_id: j, "act_900001": j.model_copy(update={"holder_id": "act_900001"})}) == \
        [[j.holder_id], ["act_900001"]]


# =========================================================================== MEM-02/04..07 apply
def test_writeback_writes_the_episode(scenario, canon):
    """MEM-04, STORE-11: one EPISODE_WRITTEN, the episode row and its search index."""
    w = scenario("metal_fence")
    t, crash, call = crash_and_call(w)
    june_goes_to_look(w, t)
    a = aftermath(w, "june", t + 9000)
    base = maxseq(w)
    with w.store.transaction() as tx:
        ids = memory.apply_writeback(tx, w.id("june"), output(), a, t + 9000, 0, cue_ids=cue_ids(canon))
    assert ids == [r[0] for r in w.store.query("SELECT event_id FROM events WHERE seq > ? ORDER BY seq", (base,))]
    ev = dict(w.store.query_one("SELECT * FROM events WHERE event_id = ?", (ids[0],)))
    ep = dict(w.store.query_one("SELECT * FROM episodes WHERE holder_id = ?", (w.id("june"),)))
    s = sorted((h for h in a.handles if h[0] == "S"), key=lambda h: int(h[1:]))
    p = sorted((h for h in a.handles if h[0] == "P"), key=lambda h: int(h[1:]))
    first_event = next(r for r in selected_rows(w, "june") if not r["event_id"].startswith("scene:"))["event_id"]
    assert (ev["type"], ev["writer"], ev["actor_id"], ev["cause_event_id"]) == ("EPISODE_WRITTEN", "mind.memory", w.id("june"), first_event)
    assert json.loads(ev["payload"]) == {"episode_id": ep["episode_id"], "holder_id": w.id("june"), "salience": 40, "anchor": 0}
    assert (ep["at"], ep["turn_index"], ep["summary"], ep["salience"], ep["anchor"], ep["decayed"]) == \
        (t + 9000, 0, "Mara told me to stay put, and something hit the back fence.", 40, 0, 0)
    assert ep["place_id"] == w.store.query_one("SELECT place_id FROM positions WHERE body_id = ?", (w.id("june"),))[0]
    assert json.loads(ep["percept_ids"]) == [a.handles[h] for h in s]
    assert json.loads(ep["subject_ids"]) == [a.handles[h] for h in p]
    hits = w.store.query("SELECT e.episode_id FROM episodes_fts f JOIN episodes e ON e.rowid = f.rowid "
                         "WHERE episodes_fts MATCH '\"fence\"'")
    assert [r[0] for r in hits] == [ep["episode_id"]]


def test_items_citing_the_unperceived_are_dropped_one_by_one(scenario, canon):
    """MEM-02, G14: each bad item is dropped and logged; every good item still applies."""
    w = scenario("metal_fence")
    t, crash, call = crash_and_call(w)
    june_goes_to_look(w, t)
    with w.store.transaction() as tx:
        loop = mind.open_loop(tx, w.id("june"), OpenLoopKind.QUESTION, "Is Nita all right?", [w.id("nita")], 2, None, t, 0)
    a = aftermath(w, "june", t + 9000)
    sp, cr, mara = a.utterances[0].handle, handle_of_event(a, w, crash.event_id), entity(a, "Mara")
    lh = next(line.handle for line in a.open_loops if a.handles[line.handle] == loop)
    out = output(
        beliefs=[{"about": "P9", "claim": "Someone else is in the alley.", "confidence": 2, "because": [cr]},
                 {"about": mara, "claim": "Mara sounded scared.", "confidence": 2, "because": [sp, "S99"]},
                 {"about": mara, "claim": "Mara wants me to stay put.", "confidence": 3, "because": [sp]}],
        relationships=[{"with": mara, "axis": "trust", "delta": 1, "because": "S42"},
                       {"with": "P77", "axis": "fear", "delta": 1, "because": sp},
                       {"with": mara, "axis": "affection", "delta": 1, "because": sp}],
        new_loops=[{"kind": "question", "text": "What fell out back?", "strength": 2, "because": cr},
                   {"kind": "goal", "text": "Find the man", "subject": "P50", "strength": 2, "because": cr}],
        closed_loops=[{"loop": lh, "status": "fulfilled", "because": sp}, {"loop": "L7", "status": "broken", "because": sp}],
        lesson={"cue_tags": ["made_up_cue"], "text": "Crashes mean trouble.", "because": cr})
    with w.store.transaction() as tx:
        memory.apply_writeback(tx, w.id("june"), out, a, t + 9000, 0, cue_ids=cue_ids(canon))
    logged = [dict(r, detail=json.loads(r["detail"])) for r in w.store.query("SELECT * FROM error_repair_log ORDER BY entry_id")]
    assert all((r["kind"], r["stage"], r["rule_id"], r["repaired"], r["turn_index"], r["at_ms"]) ==
               ("hallucinated_ref", 14, "MEM-02", 0, 0, t + 9000) for r in logged)
    j = w.id("june")
    assert [r["detail"] for r in logged] == [
        {"holder_id": j, "item": "belief", "index": 0, "ref": "P9"},
        {"holder_id": j, "item": "belief", "index": 1, "ref": "S99"},
        {"holder_id": j, "item": "relationship", "index": 0, "ref": "S42"},
        {"holder_id": j, "item": "relationship", "index": 1, "ref": "P77"},
        {"holder_id": j, "item": "new_loop", "index": 1, "ref": "P50"},
        {"holder_id": j, "item": "closed_loop", "index": 1, "ref": "L7"},
        {"holder_id": j, "item": "lesson", "index": 0, "ref": "made_up_cue"}]
    held = [r[0] for r in w.store.query("SELECT p.text FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id "
                                        "WHERE h.holder_id = ? AND h.provenance = 'inferred'", (j,))]
    assert held == ["Mara wants me to stay put."]
    assert tuple(w.store.query_one("SELECT affection, trust, fear FROM relationships WHERE from_id = ? AND to_id = ?",
                                   (j, w.id("mara")))) == (2, 2, 0)
    assert [r[0] for r in w.store.query("SELECT text FROM open_loops WHERE holder_id = ? AND status = 'open' ORDER BY created_at, loop_id",
                                        (j,))] == ["What fell out back?"]
    assert w.store.query_one("SELECT status FROM open_loops WHERE loop_id = ?", (loop,))[0] == "fulfilled"
    assert w.store.query_one("SELECT COUNT(*) FROM lessons WHERE holder_id = ? AND text = 'Crashes mean trouble.'", (j,))[0] == 0
    assert w.store.query_one("SELECT COUNT(*) FROM episodes WHERE holder_id = ?", (j,))[0] == 1, "the episode is always written"


def test_beliefs_become_the_minds_own_guesses(scenario, canon):
    """MEM-05: a written belief goes through perception.infer: provenance 'inferred', confidence at
    most 2, fidelity of the weakest cited percept; the packet calls it 'your own guess'."""
    w = scenario("metal_fence")
    t, crash, call = crash_and_call(w)
    a = aftermath(w, "june", t + 2000)
    sp, cr, mara = a.utterances[0].handle, handle_of_event(a, w, crash.event_id), entity(a, "Mara")
    out = output(beliefs=[{"about": mara, "claim": "Mara knows who was out back.", "confidence": 3, "because": [sp, cr]},
                          {"about": "self", "claim": "I should not have left the shelves.", "confidence": 1, "because": [sp]},
                          {"about": "place", "claim": "This room is not safe tonight.", "confidence": 2, "because": [cr]}])
    with w.store.transaction() as tx:
        memory.apply_writeback(tx, w.id("june"), out, a, t + 2000, 0, cue_ids=cue_ids(canon))
    rows = {r["text"]: dict(r) for r in w.store.query(
        "SELECT p.*, h.confidence, h.provenance, h.fidelity, h.acquired_at, h.acquired_via, h.believed FROM claim_holdings h "
        "JOIN propositions p ON p.prop_id = h.claim_id WHERE h.holder_id = ? AND h.provenance = 'inferred'", (w.id("june"),))}
    fid = {h: w.store.query_one("SELECT fidelity FROM percept_log WHERE percept_id = ?", (a.handles[h],))[0] for h in (sp, cr)}
    order = ["tone_only", "visual_only", "partial", "exact"]
    m = rows["Mara knows who was out back."]
    assert (m["subject_type"], m["subject_id"], m["predicate"], m["confidence"], m["believed"], m["acquired_at"]) == \
        ("body", w.id("mara"), "inferred:mara knows who was out back", 2, 1, t + 2000)
    assert m["fidelity"] == min(fid.values(), key=order.index) and m["acquired_via"] == call.event_id == m["created_event"]
    assert (rows["I should not have left the shelves."]["subject_id"], rows["I should not have left the shelves."]["confidence"]) == \
        (w.id("june"), 1)
    assert (rows["This room is not safe tonight."]["subject_type"], rows["This room is not safe tonight."]["subject_id"]) == \
        ("place", w.store.query_one("SELECT place_id FROM positions WHERE body_id = ?", (w.id("june"),))[0])
    with w.store.transaction() as tx:
        aff = enumerate_affordances(tx, w.id("june"), canon.all("affordance"), t + 2000, 0)
        p = build_packet(tx, w.id("june"), LOD.HOT, aff, 0, t + 2000)
    guess = next(b for b in p.beliefs if b.text == "Mara knows who was out back.")
    assert (guess.provenance_text, guess.confidence, guess.age_text) == ("your own guess", 2, "just now")


def test_infer_directly(scenario):
    """perception.infer: only the holder's own percepts; the same guess again supersedes the old one."""
    w = scenario("metal_fence")
    t, crash, call = crash_and_call(w)
    mine = [r["percept_id"] for r in selected_rows(w, "june") if r["event_id"] == call.event_id]
    theirs = [r["percept_id"] for r in selected_rows(w, "mara")]
    with w.store.transaction() as tx:
        first = perception.infer(tx, w.id("june"), about=("body", w.id("mara")), text="Mara is scared.", confidence=2,
                                 because=mine, at=t + 2000, turn_index=0)
        second = perception.infer(tx, w.id("june"), about=("body", w.id("mara")), text="  mara is SCARED ", confidence=1,
                                  because=mine, at=t + 3000, turn_index=0)
        with pytest.raises(ValueError):
            perception.infer(tx, w.id("june"), about=("self", None), text="x y z", confidence=1, because=theirs[:1],
                             at=t, turn_index=0)
        with pytest.raises(ValueError):
            perception.infer(tx, w.id("june"), about=("self", None), text="x y z", confidence=1, because=[], at=t, turn_index=0)
    old = w.store.query_one("SELECT superseded_by FROM claim_holdings WHERE claim_id = ?", (first,))[0]
    assert old == second
    ev = json.loads(w.store.query_one("SELECT payload FROM events WHERE type = 'BELIEF_FORM' ORDER BY seq DESC LIMIT 1")[0])
    assert ev == {"prop_id": second, "holder_id": w.id("june"), "because": mine, "superseded": [first]}


def test_feelings_loops_and_lessons_go_through_their_owners(scenario, canon):
    """MEM-07: relate / open_loop / close_loop / learn, each caused by the cited percept's event."""
    w = scenario("metal_fence")
    t, crash, call = crash_and_call(w)
    june_goes_to_look(w, t)
    a = aftermath(w, "june", t + 9000)
    sp, cr, mara = a.utterances[0].handle, handle_of_event(a, w, crash.event_id), entity(a, "Mara")
    crash_text = w.store.query_one("SELECT text FROM percept_log WHERE percept_id = ?", (a.handles[cr],))[0]
    out = output(relationships=[{"with": mara, "axis": "respect", "delta": 2, "because": sp}],
                 new_loops=[{"kind": "question", "text": "What did Mara see?", "subject": mara, "strength": 2, "because": sp}],
                 lesson={"cue_tags": ["metal_crash", "made_up_cue"], "text": "A crash out back means someone is at the fence.",
                         "because": cr})
    with w.store.transaction() as tx:
        memory.apply_writeback(tx, w.id("june"), out, a, t + 9000, 0, cue_ids=cue_ids(canon))
    r = w.store.query_one("SELECT respect, causes FROM relationships WHERE from_id = ? AND to_id = ?", (w.id("june"), w.id("mara")))
    assert r[0] == 2 and json.loads(r[1])["respect"] == call.event_id
    q = dict(w.store.query_one("SELECT * FROM open_loops WHERE holder_id = ? AND text = 'What did Mara see?'", (w.id("june"),)))
    assert json.loads(q["subject_ids"]) == [w.id("mara")]
    loop_ev = w.store.query_one("SELECT cause_event_id FROM events WHERE event_id = ?", (q["created_event"],))[0]
    assert loop_ev == call.event_id
    les = dict(w.store.query_one("SELECT * FROM lessons WHERE holder_id = ? AND text LIKE 'A crash out back%'", (w.id("june"),)))
    assert (json.loads(les["cue_tags"]), les["expectation"], les["outcome"]) == (["metal_crash"], "See what fell out back", crash_text)
    assert w.store.query_one("SELECT COUNT(*) FROM error_repair_log")[0] == 0, "an unknown tag is removed, not an error, when one is left"


def test_a_standing_view_can_be_cited_but_is_not_an_event(scenario, canon):
    """MEM-07: the cited reference is kept ('scene:0'); the event's cause is NULL."""
    w = scenario("metal_fence")
    t, crash, call = crash_and_call(w)
    a = aftermath(w, "pc", t + 2000)
    view = next(h for h in sorted(a.handles) if h[0] == "S"
                and w.store.query_one("SELECT event_id FROM percept_log WHERE percept_id = ?", (a.handles[h],))[0] == "scene:0"
                and w.store.query_one("SELECT source_id FROM percept_log WHERE percept_id = ?", (a.handles[h],))[0] == w.id("mara"))
    out = output(relationships=[{"with": entity(a, "Mara"), "axis": "respect", "delta": 1, "because": view}])
    base = maxseq(w)
    with w.store.transaction() as tx:
        memory.apply_writeback(tx, w.id("pc"), out, a, t + 2000, 0, cue_ids=cue_ids(canon))
    rc = w.store.query_one("SELECT cause_event_id FROM events WHERE type = 'RELATION_CHANGE' AND seq > ?", (base,))
    assert rc[0] is None
    assert json.loads(w.store.query_one("SELECT causes FROM relationships WHERE from_id = ? AND to_id = ?",
                                        (w.id("pc"), w.id("mara")))[0])["respect"] == "scene:0"


def _goes_down(w, kind, anchor, dx, dy):
    """Move June next to ``anchor`` in the sales floor and have her go down; Mara and Alice take it in."""
    t = now(w)
    ax, ay = w.store.query_one("SELECT x_m, y_m FROM anchors WHERE anchor_id = ?", (w.id(anchor),))
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("sales_floor"), w.id(anchor), ax + dx, ay + dy, t, None, 0))
        payload = {"body_id": w.id("june"), "cause": "test", "cause_event_id": None} if kind == EventType.DEATH else \
            {"body_id": w.id("june"), "false_dead_until": t + 600_000}
        down = tx.commit_event(Event(type=kind, writer="physical.bodies", at=t + 1000, turn_index=0, payload=payload))
        for x in ("mara", "alice"):
            perception.compile_aftermath(tx, w.id(x), [down], t + 2000, 0)
    return t, down


def _anchor_after(w, canon, local, t, down):
    a = aftermath(w, local, t + 2000)
    seen = [p for p in a.percepts
            if w.store.query_one("SELECT event_id FROM percept_log WHERE percept_id = ?", (a.handles[p.handle],))[0] == down.event_id]
    assert seen, f"{local} saw it"
    with w.store.transaction() as tx:
        memory.apply_writeback(tx, w.id(local), output(salience=50), a, t + 2000, 0, cue_ids=cue_ids(canon))
    return w.store.query_one("SELECT anchor FROM episodes WHERE holder_id = ?", (w.id(local),))[0], seen[0]


@pytest.mark.parametrize("kind", [EventType.DEATH, EventType.FALSE_DEATH])
def test_seeing_someone_you_love_go_down_is_an_anchor_memory(scenario, canon, kind):
    """MEM-06: salience >= 90, or a DEATH / FALSE_DEATH percept of a bonded body (affection >= 2 or a
    family kind) — the holder cannot tell a false death from a true one, and neither can the rule."""
    w = scenario("metal_fence")
    t, down = _goes_down(w, kind, "front_window", 0.8, 0.5)          # right beside Mara
    mara, seen = _anchor_after(w, canon, "mara", t, down)
    assert seen.source_handle is not None, "close enough to know it is June"
    assert mara == 1, "Mara loves June (affection 2)"
    alice, _ = _anchor_after(w, canon, "alice", t, down)
    assert alice == 0, "Alice has no bond with June"
    assert memory.BONDED_KINDS == ("parent", "child", "sibling", "spouse", "partner")


def test_a_figure_going_down_in_the_dark_is_nobody_you_know(scenario, canon):
    """MEM-06 with Skull Law: at the counter, in the dim store, Mara sees only 'a figure' — the
    percept has no source, so it cannot be a bonded person's death to her."""
    w = scenario("metal_fence")
    t, down = _goes_down(w, EventType.DEATH, "counter", 0, 0)
    mara, seen = _anchor_after(w, canon, "mara", t, down)
    assert seen.source_handle is None and seen.text.startswith("A figure")
    assert mara == 0


def test_salience_ninety_is_an_anchor(scenario, canon):
    w = scenario("metal_fence")
    t, crash, call = crash_and_call(w)
    a = aftermath(w, "nita", t + 2000)
    with w.store.transaction() as tx:
        memory.apply_writeback(tx, w.id("nita"), output(salience=90), a, t + 2000, 0, cue_ids=cue_ids(canon))
        memory.apply_writeback(tx, w.id("nita"), output(salience=89), a, t + 2000, 0, cue_ids=cue_ids(canon))
    assert [r[0] for r in w.store.query("SELECT anchor FROM episodes WHERE holder_id = ? ORDER BY salience DESC",
                                        (w.id("nita"),))] == [1, 0]


def test_the_player_character_remembers_too(scenario, canon):
    """MEM-08, L12: the PC's writeback is the same code path."""
    w = scenario("metal_fence")
    t, crash, call = crash_and_call(w)
    a = aftermath(w, "pc", t + 2000)
    with w.store.transaction() as tx:
        ids = memory.apply_writeback(tx, w.id("pc"), output(episode="I heard the fence go down out back."), a, t + 2000, 0,
                                     cue_ids=cue_ids(canon))
    assert w.store.query_one("SELECT type FROM events WHERE event_id = ?", (ids[0],))[0] == "EPISODE_WRITTEN"
    assert w.store.query_one("SELECT summary FROM episodes WHERE holder_id = ?", (w.id("pc"),))[0] == \
        "I heard the fence go down out back."
