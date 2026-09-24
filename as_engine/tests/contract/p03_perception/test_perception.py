"""Perception compiler and the single knowledge writer (P3). Rules SKULL-01..06 (mind/perception.py).

SKULL-01 a mind receives only what its body could have perceived (acoustics + optics);
SKULL-03 every percept_log / claim_holdings row is written by perception.grant;
SKULL-04 a sound's source is known only if seen, or (speech) the voice is known;
SKULL-05 strangers are described, never named;
SKULL-06 no internal id ever appears in mind-facing text.
Wording is tested only where the module docstring fixes it; everything else is structural.
"""

from __future__ import annotations

import json
import re

import pytest

from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.mind import perception
from as_engine.mind.perception import BeliefFromPercept
from as_engine.physical import space

pytestmark = pytest.mark.phase(3)

ID_RE = re.compile(r"\b(evt|act|plc|anc|prt|itm|pct|prp|clm|wnd|tsk)_\d{6}\b")


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def percepts(w, holder, where="", params=()):
    return [dict(r) for r in w.store.query(
        f"SELECT * FROM percept_log WHERE holder_id = ? {where} ORDER BY at, percept_id", (w.id(holder), *params))]


def commit(w, **ev):
    with w.store.transaction() as tx:
        return tx.commit_event(Event(turn_index=0, **ev))


def gust(w):
    return commit(w, type=EventType.NOISE, writer="action.propagate", at=now(w),
                  payload={"source_db": 98, "kind": "metal_crash", "text": "a loud metal crash",
                           "place_id": w.id("alley"), "anchor_id": w.id("fence_sheet")})


def scene(w, holder, at=None):
    with w.store.transaction() as tx:
        return perception.compile_scene(tx, w.id(holder), now(w) if at is None else at, 0)


def after(w, holder, events, at=None):
    with w.store.transaction() as tx:
        return perception.compile_aftermath(tx, w.id(holder), events, now(w) if at is None else at, 0)


def all_texts(w):
    return [r[0] for r in w.store.query("SELECT text FROM percept_log")]


# --------------------------------------------------------------------------- grant (SKULL-03)
def test_grant_writes_one_perceive_event(scenario):
    w = scenario("metal_fence")
    ev = gust(w)
    with w.store.transaction() as tx:
        pid = perception.grant(tx, w.id("june"), event_id=ev.event_id, channel="auditory", fidelity="exact",
                               text="A loud metal crash came from the rear alley.", source_id=None, at=ev.at, turn_index=0,
                               beliefs=[BeliefFromPercept("event", None, "noise_out_back", "Something crashed out back.")])
    row = w.store.query_one("SELECT * FROM percept_log WHERE percept_id = ?", (pid,))
    assert row["granted_by"] == "perception.grant" and row["holder_id"] == w.id("june") and row["event_id"] == ev.event_id
    perc = w.store.query("SELECT * FROM events WHERE type = 'PERCEIVE' AND actor_id = ? ORDER BY seq DESC LIMIT 1", (w.id("june"),))[0]
    assert perc["writer"] == "mind.perception" and perc["cause_event_id"] == ev.event_id
    h = w.store.query_one("SELECT h.*, p.predicate FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id "
                          "WHERE h.holder_id = ? AND p.predicate = 'noise_out_back'", (w.id("june"),))
    assert (h["provenance"], h["confidence"], h["fidelity"], h["acquired_via"]) == ("witnessed", 3, "exact", ev.event_id)


def test_only_grant_can_write_percepts(scenario):
    """The schema CHECK on granted_by, plus table ownership, keep everyone else out."""
    w = scenario("metal_fence")
    row = {"percept_id": "pct_999999", "holder_id": w.id("june"), "event_id": "x", "channel": "visual", "fidelity": "exact",
           "at": 0, "text": "forged", "source_id": None, "granted_by": "someone_else", "turn_index": 0}
    with pytest.raises(Exception):
        commit(w, type=EventType.PERCEIVE, writer="mind.perception", at=0, writes=[WriteRecord(op=WriteOp.INSERT, table="percept_log", values=row)])
    with pytest.raises(Exception):
        commit(w, type=EventType.PERCEIVE, writer="mind.packet", at=0,
               writes=[WriteRecord(op=WriteOp.INSERT, table="percept_log", values={**row, "granted_by": "perception.grant"})])


@pytest.mark.parametrize("channel,fidelity,addressed,prov,conf", [
    ("visual", "exact", False, "witnessed", 3), ("visual", "partial", False, "witnessed", 2),
    ("visual", "visual_only", False, "witnessed", 2), ("auditory", "tone_only", False, "witnessed", 1),
    ("speech", "exact", True, "told_by", 3), ("speech", "exact", False, "overheard", 3), ("speech", "partial", True, "told_by", 2),
])
def test_provenance_and_confidence(scenario, channel, fidelity, addressed, prov, conf):
    w = scenario("metal_fence")
    speaker = w.id("june")
    with w.store.transaction() as tx:
        perception.grant(tx, w.id("mara"), event_id=f"scene:0", channel=channel, fidelity=fidelity, text="x.", source_id=speaker,
                         at=0, turn_index=0, detail={"addressed_to_me": addressed},
                         beliefs=[BeliefFromPercept("body", speaker, "said", "June said something.")])
    h = w.store.query_one("SELECT h.* FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id WHERE h.holder_id = ? AND p.predicate = 'said'", (w.id("mara"),))
    assert h["confidence"] == conf
    assert h["provenance"] == (f"told_by:{speaker}" if prov == "told_by" else prov)


def test_nothing_is_granted_for_none(scenario):
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        with pytest.raises(ValueError):
            perception.grant(tx, w.id("mara"), event_id="scene:0", channel="auditory", fidelity="none", text="-", source_id=None, at=0, turn_index=0)


def test_a_new_belief_supersedes_never_deletes(scenario):
    """W15: beliefs are superseded, never deleted; the old one points at the new one."""
    w = scenario("metal_fence")
    nita = w.id("nita")
    old = w.store.query_one("SELECT h.claim_id FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id "
                            "WHERE h.holder_id = ? AND p.predicate = 'status'", (nita,))[0]
    with w.store.transaction() as tx:
        perception.grant(tx, nita, event_id="scene:0", channel="visual", fidelity="exact", text="The alley is not clear.",
                         source_id=None, at=now(w), turn_index=0,
                         beliefs=[BeliefFromPercept("place", w.id("alley"), "status", "Someone is in the lot behind the fence.")])
    rows = {r["claim_id"]: r for r in w.store.query("SELECT * FROM claim_holdings WHERE holder_id = ?", (nita,))}
    new = [c for c, r in rows.items() if c != old and r["superseded_by"] is None and c in
           {x[0] for x in w.store.query("SELECT prop_id FROM propositions WHERE predicate = 'status'")}]
    assert old in rows and len(new) == 1 and rows[old]["superseded_by"] == new[0]


def test_one_percept_per_event_and_channel(scenario):
    w = scenario("metal_fence")
    ev = gust(w)
    a = after(w, "june", [ev])
    b = after(w, "june", [ev])
    assert a == b and len(a) == 1
    assert len(percepts(w, "june", "AND event_id = ?", (ev.event_id,))) == 1


# --------------------------------------------------------------------------- SKULL-01/04: three rooms
def test_three_rooms_one_shot_three_truths(scenario):
    """SKULL-01/04: B hears a gunshot through brick (EXACT) but not who fired; C, asleep two walls
    away, gets a tone and wakes; A does not 'perceive' its own shot."""
    w = scenario("three_rooms_gunshot")
    shot = commit(w, type=EventType.NOISE, writer="action.propagate", at=now(w), actor_id=w.id("a"),
                  payload={"source_db": 160, "kind": "gunshot", "text": "a gunshot"})
    (b,) = [dict(w.store.query_one("SELECT * FROM percept_log WHERE percept_id = ?", (p,))) for p in after(w, "b", [shot])]
    assert (b["channel"], b["fidelity"], b["source_id"]) == ("auditory", "exact", None)
    assert b["text"] == "A gunshot came from the other side of the brick wall."
    assert json.loads(b["detail"])["received_db"] == pytest.approx(104.55, abs=0.01)
    (c,) = [dict(w.store.query_one("SELECT * FROM percept_log WHERE percept_id = ?", (p,))) for p in after(w, "c", [shot])]
    assert (c["fidelity"], c["source_id"]) == ("tone_only", None) and c["text"] == "A sound came from the other side of the drywall wall."
    assert w.store.query_one("SELECT awareness FROM bodies WHERE body_id = ?", (w.id("c"),))[0] == "awake"
    wake = w.store.query("SELECT * FROM events WHERE type = 'AWARENESS_CHANGE' AND cause_event_id = ?", (shot.event_id,))
    assert len(wake) == 1 and wake[0]["writer"] == "physical.bodies"
    assert after(w, "a", [shot]) == [], "the shooter's own noise is not a percept"
    owen = w.canon.get("core:pc/owen_marsh")
    for t in (b["text"], c["text"]):
        assert owen.identity.name.split()[0] not in t and "man" not in t


# --------------------------------------------------------------------------- the standing view
def test_standing_view_in_the_dark_store(scenario):
    w = scenario("metal_fence")
    scene(w, "pc")
    vis = percepts(w, "pc", "AND channel = 'visual'")
    bodies = [p for p in vis if p["source_id"] and p["source_id"].startswith("act_")]
    assert [(p["source_id"], p["fidelity"]) for p in bodies] == [(w.id("mara"), "partial")], "Alice behind the counter is invisible"
    assert bodies[0]["text"] == "A woman stands at the front window.", "partial: no name even though Owen knows her"
    portals = {p["source_id"]: p["text"] for p in vis if p["source_id"] and p["source_id"].startswith("prt_")}
    assert set(portals) == {w.id("storeroom_door"), w.id("office_door"), w.id("front_door"), w.id("front_window_pane")}
    assert portals[w.id("front_door")] == "The front door is closed, barricaded.", "a lock is never visible"
    assert portals[w.id("storeroom_door")] == "The storeroom door is open."
    kp = w.store.query_one("SELECT * FROM known_places WHERE holder_id = ? AND place_id = ?", (w.id("pc"), w.id("sales_floor")))
    assert (kp["last_seen"], kp["visited"]) == (now(w), 1)


def test_the_stranger_through_the_fence(scenario):
    """SKULL-05: Nita knows the stranger only as a description, and that is how she sees him."""
    w = scenario("metal_fence")
    scene(w, "nita")
    seen = [p for p in percepts(w, "nita", "AND channel = 'visual'") if p["source_id"] == w.id("stranger")]
    assert len(seen) == 1 and seen[0]["fidelity"] == "partial"
    assert seen[0]["text"] == "The thin man who watches the back fence stands in the lot behind the fence."
    fence = [p for p in percepts(w, "nita") if p["source_id"] == w.id("rear_fence")]
    assert fence and fence[0]["text"] == "The chain-link fence is intact."
    scene(w, "stranger")
    assert not [p for p in percepts(w, "stranger") if p["source_id"] and p["source_id"].startswith("act_")]
    scene(w, "eli")
    assert percepts(w, "eli") == [], "asleep: no standing view"


def test_first_sight_creates_an_acquaintance(scenario):
    """Seeing a stranger clearly for the first time gives the mind a description to use, not a name."""
    w = scenario("crowd_accusation")
    before = {r[0] for r in w.store.query("SELECT subject_id FROM acquaintance WHERE holder_id = ?", (w.id("pc"),))}
    scene(w, "pc")
    rows = {r["subject_id"]: dict(r) for r in w.store.query("SELECT * FROM acquaintance WHERE holder_id = ?", (w.id("pc"),))}
    new = set(rows) - before
    assert w.id("l01") in new and all(rows[s]["known_name"] is None for s in new)
    assert rows[w.id("l01")]["description"] == "woman"
    texts = [p["text"] for p in percepts(w, "pc") if p["source_id"] == w.id("l01")]
    assert texts and "Rosa" not in texts[0] and texts[0].startswith("A woman ")


# --------------------------------------------------------------------------- sounds and speech
def test_the_gust_reaches_everyone_it_should(scenario, vectors):
    """SKULL-01: the anchor scene's first second, per listener (acoustics vector 'metal_fence_gust')."""
    w = scenario("metal_fence")
    ev = gust(w)
    expect = {e["listener"]: e["fidelity"] for e in vectors("acoustics")["scenarios"]["metal_fence_gust"]["receptions"]}
    for who, fid in expect.items():
        got = [p for p in percepts(w, who) if p["event_id"] == ev.event_id]
        assert got == [], "nothing until perception runs"
        scene(w, who)
        got = [p for p in percepts(w, who) if p["event_id"] == ev.event_id]
        assert [(p["channel"], p["fidelity"], p["source_id"]) for p in got] == [("auditory", fid, None)], who
    texts = {who: [p["text"] for p in percepts(w, who) if p["event_id"] == ev.event_id][0] for who in expect}
    assert texts["june"] == "A loud metal crash came from the rear alley."
    assert texts["nita"] == "A loud metal crash came from the loose metal sheet on the fence."
    assert texts["eli"] == "A sound came from the other side of the boarded office window."
    assert w.store.query_one("SELECT awareness FROM bodies WHERE body_id = ?", (w.id("eli"),))[0] == "awake"


def _june_and_mara(w):
    t = now(w)
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("storeroom"), w.id("doorway"), 7.5, 0.5, t + 800, None, 0))
    quiet = commit(w, type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("mara"), at=t + 400,
                   payload={"words": "Quiet.", "volume": "normal", "to": ["everyone"], "source_db": 60})
    call = commit(w, type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("june"), at=t + 900,
                  payload={"words": "What was that?", "volume": "raised", "to": ["everyone"], "source_db": 70})
    return quiet, call


def test_known_voices_are_named_unknown_ones_are_someone(scenario):
    """SKULL-04/05: Owen knows both voices (EXACT) -> names; Nita hears June only partly from the
    stockroom -> 'Someone'; the stranger gets a voice with no words."""
    w = scenario("metal_fence")
    quiet, call = _june_and_mara(w)
    pc = {p["event_id"]: p for p in (dict(w.store.query_one("SELECT * FROM percept_log WHERE percept_id = ?", (i,))) for i in after(w, "pc", [quiet, call]))}
    assert pc[quiet.event_id]["text"] == 'Mara says, "Quiet."' and pc[quiet.event_id]["source_id"] == w.id("mara")
    assert pc[call.event_id]["text"] == 'June calls out, "What was that?"'
    d = json.loads(pc[call.event_id]["detail"])
    assert {k: d[k] for k in ("words", "volume", "addressed_to_me", "speaker_known_as", "armed_at_me", "via_portal")} == {
        "words": "What was that?", "volume": "raised", "addressed_to_me": False, "speaker_known_as": "June",
        "armed_at_me": False, "via_portal": w.id("storeroom_door")}
    (nita,) = [dict(w.store.query_one("SELECT * FROM percept_log WHERE percept_id = ?", (i,))) for i in after(w, "nita", [call])]
    assert nita["fidelity"] == "partial" and nita["source_id"] is None
    assert nita["text"].startswith("Someone calls out from the stockroom, not all of it clear: \"")
    (stranger,) = [dict(w.store.query_one("SELECT * FROM percept_log WHERE percept_id = ?", (i,))) for i in after(w, "stranger", [call])]
    assert stranger["fidelity"] == "tone_only" and stranger["text"] == "Someone calls out from the other side of the chain-link fence; the words are lost."
    assert json.loads(stranger["detail"])["words"] == "" and "What" not in stranger["text"]


def test_talking_costs_attention(scenario):
    """AUD-04 through perception: Mara was speaking 500 ms before June called, so June's words
    reach her only partly (15.25 - 4 = 11.25 dB margin)."""
    w = scenario("metal_fence")
    quiet, call = _june_and_mara(w)
    (m,) = [dict(w.store.query_one("SELECT * FROM percept_log WHERE percept_id = ?", (i,))) for i in after(w, "mara", [call])]
    assert m["fidelity"] == "partial"


def test_addressed_speech_is_marked(scenario):
    w = scenario("metal_fence")
    ev = commit(w, type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("mara"), at=now(w),
                payload={"words": "Owen, stay here.", "volume": "normal", "to": [w.id("pc")], "source_db": 60})
    (p,) = after(w, "pc", [ev])
    assert json.loads(w.store.query_one("SELECT detail FROM percept_log WHERE percept_id = ?", (p,))[0])["addressed_to_me"] is True
    (a,) = after(w, "alice", [ev])
    assert json.loads(w.store.query_one("SELECT detail FROM percept_log WHERE percept_id = ?", (a,))[0])["addressed_to_me"] is False


# --------------------------------------------------------------------------- visual events
def test_visible_events(scenario, rules):
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        mv = tx.commit_event(space.move_event(tx, w.id("mara"), w.id("sales_floor"), w.id("rear_cover"), 12.5, 8.0, t, None, 0))
        door = tx.commit_event(space.portal_change_event(tx, w.id("office_door"), {"is_open": True}, t, w.id("mara"), None, 0))
    pc = {p: dict(w.store.query_one("SELECT * FROM percept_log WHERE percept_id = ?", (p,))) for p in after(w, "pc", [mv, door])}
    texts = sorted(r["text"] for r in pc.values())
    # at the end of the rear shelving (concealment 2) she is only a figure to Owen: 1 + 0 - 0 - 2 + 1 (moving) = 0
    assert texts == ["A figure moves to the end of the rear shelving.", "The office door opens."]
    assert after(w, "mara", [mv]) == [], "nobody perceives their own movement"
    assert after(w, "eli", [door]) == [], "asleep behind it"
    assert after(w, "june", [door]) == [], "not a side of that portal"
    hidden = commit(w, type=EventType.ACTION_START, writer="action.resolve", actor_id=w.id("mara"), at=t,
                    payload={"def_id": "wait", "visible": False})
    shown = commit(w, type=EventType.ACTION_START, writer="action.resolve", actor_id=w.id("mara"), at=t,
                   payload={"def_id": "take_cover", "visible": True, "seen": "ducks behind the shelving"})
    got = [w.store.query_one("SELECT text FROM percept_log WHERE percept_id = ?", (p,))[0] for p in after(w, "pc", [hidden, shown])]
    assert got == ["A figure ducks behind the shelving."]


def test_how_a_move_reads_from_where_you_are(scenario):
    """render MOVE without an anchor (P10 wording): leaving the watcher's place reads 'moves away',
    coming into it 'arrives', and going between two other places the watcher can see into 'moves
    into <place>' — never 'moves away' for someone who is coming."""
    w = scenario("metal_fence")
    t = now(w)

    def seen(holder, ev):
        return [w.store.query_one("SELECT text FROM percept_log WHERE percept_id = ?", (p,))[0] for p in after(w, holder, [ev])]
    with w.store.transaction() as tx:
        out = tx.commit_event(space.move_event(tx, w.id("june"), w.id("alley"), None, 3.0, 1.0, t, None, 0))
    assert seen("nita", out) == ["June arrives."]
    assert seen("stranger", out) == ["A woman moves into the rear alley."]
    with w.store.transaction() as tx:
        back = tx.commit_event(space.move_event(tx, w.id("mara"), w.id("storeroom"), None, 6.0, 1.0, t, None, 0))
    assert seen("pc", back) == ["A woman moves away."]


def test_harm_is_seen_by_others_and_felt_by_the_victim(scenario):
    from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
    from as_engine.physical import bodies
    from as_engine.physical.bodies import WoundSpec

    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        cause = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=0)).event_id
        (harm,) = bodies.apply_harm(tx, w.id("mara"), WoundSpec(Anatomy.ARM_L, WoundType.STAB, WoundSeverity.SEVERE), t, cause, 0, w.rng)
    (felt,) = after(w, "mara", [harm])
    row = w.store.query_one("SELECT * FROM percept_log WHERE percept_id = ?", (felt,))
    assert (row["channel"], row["fidelity"], row["text"], row["source_id"]) == ("tactile", "exact", "Pain: a deep stab wound to the left arm.", None)
    (seen,) = after(w, "pc", [harm])
    assert w.store.query_one("SELECT text FROM percept_log WHERE percept_id = ?", (seen,))[0] == "A woman is hurt."


# --------------------------------------------------------------------------- aftermath scope and ids
def test_aftermath_returns_only_this_turns_percepts_of_these_events(scenario):
    w = scenario("metal_fence")
    ev = gust(w)
    scene(w, "june")  # the gust percept is granted here, during the wave
    quiet, call = _june_and_mara(w)
    ids = after(w, "june", [ev])
    assert len(ids) == 1, "granted earlier this turn, still returned; nothing else"
    rows = [w.store.query_one("SELECT event_id FROM percept_log WHERE percept_id = ?", (i,))[0] for i in ids]
    assert rows == [ev.event_id]


def test_unconscious_and_dead_minds_receive_nothing(scenario):
    w = scenario("metal_fence")
    commit(w, type=EventType.AWARENESS_CHANGE, writer="physical.bodies", at=now(w),
           writes=[WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": w.id("june")}, values={"awareness": "unconscious"})])
    ev = gust(w)
    assert after(w, "june", [ev]) == [] and scene(w, "june") == []


def test_no_internal_id_in_any_text(scenario):
    """SKULL-06 over everything this module rendered in the anchor scene."""
    w = scenario("metal_fence")
    gust(w)
    _june_and_mara(w)
    for who in ("pc", "mara", "alice", "june", "eli", "nita", "stranger"):
        scene(w, who, now(w) + 1000)
    texts = all_texts(w)
    assert len(texts) > 20
    assert not [t for t in texts if ID_RE.search(t)]
    assert not [t for t in texts if "Dale" in t or "Pruitt" in t], "nobody knows the stranger's name"


def test_a_second_look_at_the_same_moment_adds_nothing(scenario):
    w = scenario("metal_fence")
    first = scene(w, "pc")
    assert first
    assert scene(w, "pc") == [], "same holder, same moment: the standing view is not granted twice"
    later = scene(w, "pc", at=now(w) + 5_000)
    assert len(later) == len(first), "a later moment is described again"
