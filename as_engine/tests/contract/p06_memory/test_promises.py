"""Promises as each person understands them (P6, Actor v2 B5d — Actor Spec §12). Rules PROM-01..07
(mind/promise.py; mind/mind.py close_loop; mind/memory.py apply_writeback; mind/packet.py
open_loops).

At the metal fence Mara tells Owen she will bring him the bandages after dark. What was said is
the SPEECH; what was promised is Mara's understanding and Owen's, each their own, and they agree
only when both understood the same thing. Nita, in the storeroom, heard nothing and can hold
nothing. Nobody is called a liar when they remember the end of it differently.
"""

from __future__ import annotations

import json

import pytest

from as_engine.contracts.common import LOD
from as_engine.contracts.events import Event, EventType
from as_engine.contracts.mind import WritebackOutput
from as_engine.mind import memory, mind, perception, promise
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet

pytestmark = pytest.mark.phase(6)

WORDS = "Owen, I'll bring you the bandages after dark."


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def said(w):
    """Mara says it to Owen; Owen and Nita take in the moment. -> (t, the SPEECH's id)."""
    t = now(w)
    with w.store.transaction() as tx:
        e = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=t, turn_index=0, actor_id=w.id("mara"),
                                  payload={"words": WORDS, "volume": "normal", "to": [w.id("pc")], "source_db": 60}))
        for x in ("pc", "nita"):
            perception.compile_scene(tx, w.id(x), t + 500, 0)
    return t, e.event_id


def hold(w, who, src, at, *, category="deliver", object_id=None, status=None, loop_id=None, promiser="mara"):
    st = status or ("accepted" if who == "mara" else "understood")
    with w.store.transaction() as tx:
        return promise.hold(tx, w.id(who), promiser_id=w.id(promiser), promisee_id=w.id("pc"), category=category,
                            text="  Bandages for Owen after dark ", object_id=object_id, condition="after dark",
                            source_event_id=src, loop_id=loop_id, status=st, at=at, turn_index=0)


def row(w, pid):
    return dict(w.store.query_one("SELECT * FROM promises WHERE promise_id = ?", (pid,)))


def kinds(w, type_):
    return [json.loads(r[0]) for r in w.store.query("SELECT payload FROM events WHERE type = ? ORDER BY seq", (type_,))]


def loop(w, who, kind, subject, src, at):
    with w.store.transaction() as tx:
        return mind.open_loop(tx, w.id(who), kind, "Bandages after dark", [w.id(subject)], 2, src, at, 0)


def close(w, lid, status, at):
    with w.store.transaction() as tx:
        return mind.close_loop(tx, lid, status, None, at, 0)


# --------------------------------------------------------------------------- PROM-01
def test_the_words():
    assert promise.CATEGORIES == ("deliver", "guard", "return", "disclose", "refrain", "assist")
    assert promise.STATUSES == ("proposed", "understood", "accepted", "in_progress", "fulfilled", "failed", "withdrawn",
                                "disputed")
    assert (promise.CATEGORY_OF_DEF["give_item"], promise.CATEGORY_OF_DEF["guard_anchor"],
            promise.CATEGORY_OF_DEF["wait_here"]) == ("deliver", "guard", "refrain")
    assert "open_portal" not in promise.CATEGORY_OF_DEF, "anything else is assist"
    assert promise.NEXT["withdrawn"] == () and promise.NEXT["disputed"] == ()


# --------------------------------------------------------------------------- PROM-02
def test_each_holds_their_own_understanding(scenario):
    w = scenario("metal_fence")
    t, src = said(w)
    m = hold(w, "mara", src, t + 1000)
    r = row(w, m)
    assert (r["holder_id"], r["promiser_id"], r["promisee_id"], r["category"], r["text"], r["condition"], r["status"],
            r["source_event_id"], r["agreement_id"]) == (w.id("mara"), w.id("mara"), w.id("pc"), "deliver",
                                                         "Bandages for Owen after dark", "after dark", "accepted", src, None)
    (held,) = kinds(w, "PROMISE_HELD")
    assert held == {"promise_id": m, "holder_id": w.id("mara"), "promiser_id": w.id("mara"), "promisee_id": w.id("pc"),
                    "category": "deliver", "text": "Bandages for Owen after dark", "object_id": None,
                    "condition": "after dark", "status": "accepted"}
    assert w.store.query_one("SELECT cause_event_id FROM events WHERE type = 'PROMISE_HELD'")[0] == src
    assert hold(w, "mara", src, t + 2000) == m and len(kinds(w, "PROMISE_HELD")) == 1, "held once"


@pytest.mark.parametrize("case", ["never_heard", "not_the_speaker", "not_words", "category", "status", "empty"])
def test_nobody_holds_what_they_never_heard(scenario, case):
    w = scenario("metal_fence")
    t, src = said(w)
    if case == "not_words":
        with w.store.transaction() as tx:
            src = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=0,
                                        actor_id=w.id("mara"))).event_id   # hers, but not words
    args = {"never_heard": dict(who="nita"), "not_the_speaker": dict(who="pc", promiser="pc"),
            "not_words": dict(who="mara"), "category": dict(who="mara", category="borrow"),
            "status": dict(who="mara", status="fulfilled"), "empty": dict(who="mara")}[case]
    who = args.pop("who")
    with pytest.raises(ValueError):
        if case == "empty":
            with w.store.transaction() as tx:
                promise.hold(tx, w.id(who), promiser_id=w.id("mara"), promisee_id=w.id("pc"), category="deliver", text="  ",
                             object_id=None, condition=None, source_event_id=src, loop_id=None, status="accepted",
                             at=t + 1000, turn_index=0)
        else:
            hold(w, who, src, t + 1000, **args)
    assert kinds(w, "PROMISE_HELD") == []


# --------------------------------------------------------------------------- PROM-03
def test_an_agreement_is_both_understandings_agreeing(scenario):
    w = scenario("metal_fence")
    t, src = said(w)
    m = hold(w, "mara", src, t + 1000, object_id=w.id("fence_sheet"))
    assert kinds(w, "AGREEMENT") == [], "one side alone is no agreement"
    o = hold(w, "pc", src, t + 1500)
    (agr,) = kinds(w, "AGREEMENT")
    assert agr == {"agreement_id": agr["agreement_id"], "promiser_id": w.id("mara"), "promisee_id": w.id("pc"),
                   "category": "deliver", "object_id": w.id("fence_sheet"), "promise_ids": [m, o]}
    assert row(w, m)["agreement_id"] == row(w, o)["agreement_id"] == agr["agreement_id"]
    assert (row(w, m)["status"], row(w, o)["status"]) == ("accepted", "accepted"), "Owen took her at her word"


@pytest.mark.parametrize("theirs", [dict(category="assist"), dict(object_id="other")])
def test_different_understandings_make_no_agreement(scenario, theirs):
    w = scenario("metal_fence")
    t, src = said(w)
    hold(w, "mara", src, t + 1000, object_id=w.id("fence_sheet"))
    if theirs.get("object_id") == "other":
        theirs = dict(object_id=w.id("june"))
    o = hold(w, "pc", src, t + 1500, **theirs)
    assert kinds(w, "AGREEMENT") == [] and row(w, o)["status"] == "understood", "each keeps their own"


# --------------------------------------------------------------------------- PROM-04
def test_a_status_moves_only_forward(scenario):
    w = scenario("metal_fence")
    t, src = said(w)
    m = hold(w, "mara", src, t + 1000)
    with w.store.transaction() as tx:
        assert promise.set_status(tx, m, "accepted", None, t + 1100, 0) is None
        e = promise.set_status(tx, m, "in_progress", None, t + 1200, 0)
    assert e.payload == {"promise_id": m, "holder_id": w.id("mara"), "old": "accepted", "new": "in_progress"}
    assert (row(w, m)["status"], row(w, m)["updated_at"]) == ("in_progress", t + 1200)
    with pytest.raises(ValueError):
        with w.store.transaction() as tx:
            promise.set_status(tx, m, "accepted", None, t + 1300, 0)


# --------------------------------------------------------------------------- PROM-05 / PROM-06
def test_taking_it_back_is_withdrawn(scenario):
    w = scenario("metal_fence")
    t, src = said(w)
    lid = loop(w, "mara", "promise_made", "pc", src, t + 1000)
    m = hold(w, "mara", src, t + 1000, loop_id=lid)
    close(w, lid, "abandoned", t + 5000)
    assert row(w, m)["status"] == "withdrawn"


def test_they_remember_the_end_of_it_differently(scenario):
    """Mara says she brought them; Owen says she never did. Both are kept, disputed; nobody is
    called a liar here."""
    w = scenario("metal_fence")
    t, src = said(w)
    lm = loop(w, "mara", "promise_made", "pc", src, t + 1000)
    lo = loop(w, "pc", "promise_owed", "mara", src, t + 1000)
    m = hold(w, "mara", src, t + 1000, loop_id=lm)
    o = hold(w, "pc", src, t + 1500, loop_id=lo)
    close(w, lm, "fulfilled", t + 9000)
    assert (row(w, m)["status"], row(w, o)["status"]) == ("fulfilled", "accepted")
    close(w, lo, "broken", t + 9500)
    assert (row(w, m)["status"], row(w, o)["status"]) == ("disputed", "disputed")
    assert [(k["promise_id"], k["new"]) for k in kinds(w, "PROMISE_STATUS")] == [
        (m, "fulfilled"), (o, "failed"), (m, "disputed"), (o, "disputed")]
    assert kinds(w, "LIE_TOLD") == []
    assert len(kinds(w, "PROMISE_BROKEN")) == 1, "what Owen decided is still his (LOOP-04)"


# --------------------------------------------------------------------------- PROM-07
def test_the_packet_says_how_it_stands(scenario):
    w = scenario("metal_fence")
    t, src = said(w)
    lid = loop(w, "mara", "promise_made", "pc", src, t + 1000)
    hold(w, "mara", src, t + 1000, loop_id=lid)

    def line(at):
        with w.store.transaction() as tx:
            aff = enumerate_affordances(tx, w.id("mara"), w.canon.all("affordance"), at, 0)
            p = build_packet(tx, w.id("mara"), LOD.HOT, aff, 0, at)
        return next(x.text for x in p.open_loops if p.handles[x.handle] == lid)
    assert line(t + 2000) == "Bandages after dark (you took it on)"
    hold(w, "pc", src, t + 2500)
    assert line(t + 3000) == "Bandages after dark (agreed between you)"
    close(w, lid, "fulfilled", t + 4000)
    with w.store.transaction() as tx:
        assert promise.suffix(tx, lid) == ""


# --------------------------------------------------------------------------- MEM-02 (B5d)
def test_what_he_took_from_her_words_is_his_own(scenario, canon):
    w = scenario("metal_fence")
    t, src = said(w)
    with w.store.transaction() as tx:
        a = memory.build_aftermath(tx, w.id("pc"), 0, t + 1000)
    words = next(u.handle for u in a.utterances if a.handles[u.handle] and u.words)
    her = next(e.handle for e in a.entities if a.handles[e.handle] == w.id("mara"))
    out = WritebackOutput.model_validate({
        "episode": "Mara said she would bring the bandages after dark.", "salience": 40,
        "new_loops": [{"kind": "promise_owed", "text": "Mara will bring the bandages", "subject": her, "strength": 2,
                       "because": words, "category": "deliver"},
                      {"kind": "promise_made", "text": "I will wait for her", "subject": her, "strength": 1,
                       "because": words}]})
    with w.store.transaction() as tx:
        memory.apply_writeback(tx, w.id("pc"), out, a, t + 1000, 0,
                               cue_ids=frozenset(r.rsplit("/", 1)[1] for r in canon.refs("cue")))
    rows = [dict(r) for r in w.store.query("SELECT * FROM promises WHERE holder_id = ?", (w.id("pc"),))]
    assert len(rows) == 1, "his own promise_made was never said by him: the loop alone"
    (r,) = rows
    owed = w.store.query_one("SELECT loop_id FROM open_loops WHERE holder_id = ? AND kind = 'promise_owed'", (w.id("pc"),))[0]
    assert (r["promiser_id"], r["promisee_id"], r["category"], r["status"], r["source_event_id"], r["loop_id"]) == \
        (w.id("mara"), w.id("pc"), "deliver", "understood", src, owed)
    assert w.store.query("SELECT 1 FROM open_loops WHERE holder_id = ? AND kind = 'promise_made'", (w.id("pc"),))
