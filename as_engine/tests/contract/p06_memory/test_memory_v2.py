"""What a person did is evidence; a name they could not know is held back; a failed summary is never
a lost memory (P6, Actor v2 B5 — Actor Spec §13, AC10, AC13; fidelity C10). mind/memory.py MEM-01
self_experiences, MEM-02 (O handles), MEM-18 unknown_names, MEM-19 memory jobs; mind/packet.py
'unprocessed' and SKULL-09; mind/retrieval.py MEM-14 and mind/consult.py CONSULT-05 (never a
quarantined episode).

The metal fence at the crash: June goes to look toward the back door, saying she is coming.
"""

from __future__ import annotations

import json

import pytest

import helpers
from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.contracts.common import LOD
from as_engine.contracts.events import Event, EventType
from as_engine.contracts.mind import WritebackOutput
from as_engine.contracts.settings import PacketRules, RulesConfig
from as_engine.mind import consult, memory, perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet

pytestmark = pytest.mark.phase(6)

EVERYONE = ("june", "mara", "pc", "nita", "eli")


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def cue_ids(canon):
    return sorted(c.id for c in canon.all("cue"))


def the_moment(w):
    """The crash, Mara's call, and June going to look while she says she is coming."""
    t = now(w)
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", at=t, turn_index=0,
                              payload={"source_db": 98, "kind": "metal_crash", "text": "a loud metal crash",
                                       "place_id": w.id("alley"), "anchor_id": w.id("fence_sheet")}))
        for x in EVERYONE:
            perception.compile_scene(tx, w.id(x), t + 2000, 0)
    i = helpers.make_intent(w, "june", "go_look", destination="back_door_in",
                            label="Go and look toward the back door (4 m, about 6 seconds)", goal="See what fell out back",
                            speech=("Coming, hold on.", ["mara"], "normal"))
    with w.store.transaction() as tx:
        evs = resolve_wave(tx, w.rng, barrier(tx, [i]), t + 2000, 0, horizon_ms=t + 60_000)
        for x in EVERYONE:
            perception.compile_aftermath(tx, w.id(x), evs, t + 9000, 0)
    return t, evs


def aftermath(w, local, at):
    with w.store.transaction() as tx:
        return memory.build_aftermath(tx, w.id(local), 0, at)


def output(**kw):
    base = {"episode": "Something fell out back and I went to look.", "salience": 40}
    base.update(kw)
    return WritebackOutput.model_validate(base)


def apply(w, local, out, packet, at, canon):
    with w.store.transaction() as tx:
        return memory.apply_writeback(tx, w.id(local), out, packet, at, 0, cue_ids=cue_ids(canon))


# --------------------------------------------------------------------------- MEM-01 self_experiences (AC10)
def test_what_june_did_and_felt_is_evidence(scenario):
    w = scenario("metal_fence")
    t, evs = the_moment(w)
    a = aftermath(w, "june", t + 9000)
    own = [e for e in evs if e.actor_id == w.id("june") and e.type in ("ACTION_START", "SPEECH", "ACTION_COMPLETE", "ACTION_BLOCKED")]
    assert [o.handle for o in a.self_experiences] == [f"O{i}" for i in range(1, len(own) + 1)]
    assert [a.handles[o.handle] for o in a.self_experiences] == [e.event_id for e in own]
    texts = [o.text for o in a.self_experiences]
    assert texts[:2] == ["I chose to go and look toward the back door.", 'I said: "Coming, hold on."']
    assert texts[2:] == ["I did it."], "what she felt, never why"


def test_how_it_went_is_what_she_felt(scenario):
    """A result is felt by how it went (its band); a blocked attempt as not managed — never the cause."""
    w = scenario("metal_fence")
    t = now(w)
    june = w.id("june")
    with w.store.transaction() as tx:
        for i, band in enumerate(("clean", "cost", "fail", "break", None)):
            tx.commit_event(Event(type=EventType.ACTION_COMPLETE, writer="action.resolve", at=t + i, turn_index=0, actor_id=june,
                                  payload={"actor_id": june, "def_id": "force_open", "result": "the lock broke", "band": band,
                                           "visible": False}))
        tx.commit_event(Event(type=EventType.ACTION_BLOCKED, writer="action.resolve", at=t + 9, turn_index=0, actor_id=june,
                              payload={"actor_id": june, "def_id": "force_open", "cause": "locked"}))
    a = aftermath(w, "june", t + 10)
    assert [o.text for o in a.self_experiences] == ["It went cleanly.", "It worked, at a cost.", "It did not work.",
                                                    "It went badly wrong.", "I did it.", "I could not do it."]
    assert not any("lock" in o.text for o in a.self_experiences)


def test_a_memory_can_cite_what_she_said(scenario, canon):
    """MEM-02: an O handle is evidence wherever a percept handle is — a promise she now carries,
    caused by her own words."""
    w = scenario("metal_fence")
    t, evs = the_moment(w)
    a = aftermath(w, "june", t + 9000)
    said = next(o.handle for o in a.self_experiences if o.text.startswith("I said"))
    mara = next(e.handle for e in a.entities if a.handles[e.handle] == w.id("mara"))
    out = output(new_loops=[{"kind": "promise_made", "text": "Told Mara I was coming", "subject": mara, "strength": 1,
                             "because": said}],
                 beliefs=[{"about": "self", "claim": "I said I would come", "confidence": 3, "because": [said]}])
    apply(w, "june", out, a, t + 9000, canon)
    (loop,) = [dict(r) for r in w.store.query("SELECT * FROM open_loops WHERE holder_id = ? AND kind = 'promise_made'", (w.id("june"),))]
    ev = w.store.query_one("SELECT cause_event_id FROM events WHERE type = 'PROMISE' AND json_extract(payload, '$.loop_id') = ?",
                           (loop["loop_id"],))
    assert ev[0] == a.handles[said]
    ep = dict(w.store.query_one("SELECT * FROM episodes WHERE holder_id = ?", (w.id("june"),)))
    assert json.loads(ep["self_event_ids"]) == [a.handles[o.handle] for o in a.self_experiences]
    assert w.store.query("SELECT 1 FROM error_repair_log WHERE kind = 'hallucinated_ref'") == []


# --------------------------------------------------------------------------- MEM-18 unknown names (AC13)
def names(w, holder):
    """(names the holder knows, names it could not know) among the world's people."""
    known = {r[0] for r in w.store.query("SELECT known_name FROM acquaintance WHERE holder_id = ? AND known_name IS NOT NULL",
                                         (w.id(holder),))}
    known |= {r[0] for r in w.store.query("SELECT a.display_name FROM relationships r JOIN actors a ON a.actor_id = r.to_id "
                                          "WHERE r.from_id = ?", (w.id(holder),))}
    others = [r[0] for r in w.store.query("SELECT display_name FROM actors WHERE actor_id != ? ORDER BY actor_id", (w.id(holder),))]
    return sorted(n for n in others if n in known), sorted(n for n in others if n not in known and n.split()[0] not in
                                                           {k.split()[0] for k in known})


def test_a_name_she_could_not_know_is_held_back(scenario, canon):
    """An episode naming someone June never learned the name of is kept as raw evidence but
    quarantined — never recalled — and a belief naming them is dropped."""
    w = scenario("metal_fence")
    t, _ = the_moment(w)
    known, unknown = names(w, "june")
    assert known and unknown, "the fixture has both kinds"
    stranger = unknown[0]
    with w.store.transaction() as tx:
        first = stranger.split()[0]
        expected = sorted({stranger} | ({first} if len(first) >= 3 else set()))
        assert memory.unknown_names(tx, w.id("june"), f"{known[0]} called and {stranger} was out back.") == expected
        assert memory.unknown_names(tx, w.id("june"), f"{known[0]} called.") == []
    a = aftermath(w, "june", t + 9000)
    out = output(episode=f"{stranger} knocked the fence down, I think.",
                 beliefs=[{"about": "place", "claim": f"{stranger} is out back", "confidence": 2,
                           "because": [a.percepts[0].handle]}])
    apply(w, "june", out, a, t + 9000, canon)
    ep = dict(w.store.query_one("SELECT * FROM episodes WHERE holder_id = ?", (w.id("june"),)))
    assert ep["quarantined"] == 1 and ep["summary"].startswith(stranger), "the raw evidence stays"
    kinds = [json.loads(r[0]) for r in w.store.query("SELECT detail FROM error_repair_log WHERE kind = 'unknown_name' ORDER BY entry_id")]
    assert [k["item"] for k in kinds] == ["belief", "episode"]
    assert not w.store.query("SELECT 1 FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id WHERE h.holder_id = ? "
                             "AND p.text LIKE ?", (w.id("june"), f"%{stranger}%"))
    with w.store.transaction() as tx:
        aff = enumerate_affordances(tx, w.id("june"), w.canon.all("affordance"), t + 10_000, 0)
        pkt = build_packet(tx, w.id("june"), LOD.HOT, aff, 0, t + 10_000)
        looked = consult.recall(tx, pkt, "knocked fence", [], 0, t + 10_000)
    assert not any(stranger in m.text for m in pkt.memories), "a quarantined memory is never recalled"
    assert not any(stranger in ln for ln in looked), "nor found by looking it up"


def test_a_name_she_knows_is_fine(scenario, canon):
    w = scenario("metal_fence")
    t, _ = the_moment(w)
    known, _unknown = names(w, "june")
    a = aftermath(w, "june", t + 9000)
    apply(w, "june", output(episode=f"{known[0]} called out after the crash."), a, t + 9000, canon)
    assert w.store.query_one("SELECT quarantined FROM episodes WHERE holder_id = ?", (w.id("june"),))[0] == 0


# --------------------------------------------------------------------------- MEM-19 memory jobs (C10)
def test_a_failed_summary_is_never_a_lost_memory(scenario, canon):
    w = scenario("metal_fence")
    t, _ = the_moment(w)
    june = w.id("june")
    with w.store.transaction() as tx:
        key = memory.queue_writeback(tx, june, 0, t + 9000)
        assert memory.queue_writeback(tx, june, 0, t + 9000) == key == f"{june}:0"
    jobs = [json.loads(r[0]) for r in w.store.query("SELECT payload FROM events WHERE type = 'MEMORY_JOB' ORDER BY seq")]
    assert jobs == [{"job_key": key, "holder_id": june, "turn_index": 0, "status": "pending", "attempts": 0}]
    with w.store.transaction() as tx:
        memory.finish_writeback(tx, key, False, t + 9500, 0)
    assert tuple(w.store.query_one("SELECT status, attempts FROM memory_jobs WHERE job_key = ?", (key,))) == ("failed", 1)
    a = aftermath(w, "june", t + 9000)
    with w.store.transaction() as tx:
        raw = memory.unprocessed(tx, june)
        aff = enumerate_affordances(tx, june, w.canon.all("affordance"), t + 10_000, 0)
        pkt = build_packet(tx, june, LOD.HOT, aff, 0, t + 10_000)
    assert raw == [(0, [o.text for o in a.self_experiences] + [p.text for p in a.percepts])]
    assert pkt.unprocessed == raw[0][1], "before her next decision, what she did and saw is in front of her"
    assert 'I said: "Coming, hold on."' in pkt.unprocessed
    apply(w, "june", output(), a, t + 12_000, canon)
    with w.store.transaction() as tx:
        memory.finish_writeback(tx, key, True, t + 12_000, 0)
        assert memory.unprocessed(tx, june) == []
    n = w.store.query_one("SELECT COUNT(*) FROM episodes WHERE holder_id = ?", (june,))[0]
    assert apply(w, "june", output(), a, t + 13_000, canon) == [], "a done job is never applied twice"
    assert w.store.query_one("SELECT COUNT(*) FROM episodes WHERE holder_id = ?", (june,))[0] == n


def test_the_oldest_raw_lines_go_first_the_latest_never(scenario):
    """SKULL-09 (B5): short of room, the raw lines of older unsettled turns go, the oldest first;
    the latest turn's stay, whatever the budget."""
    w = scenario("metal_fence", rules=RulesConfig(packet=PacketRules(token_budget={"hot": 10, "warm": 10, "reaction": 10})))
    t, _ = the_moment(w)
    june = w.id("june")
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=t + 20_000, turn_index=1, actor_id=june,
                              payload={"words": "Anyone there?", "volume": "normal", "to": [], "source_db": 60}))
        for tix in (0, 1):
            memory.finish_writeback(tx, memory.queue_writeback(tx, june, tix, t + 21_000), False, t + 21_000, tix)
        raw = memory.unprocessed(tx, june)
        aff = enumerate_affordances(tx, june, w.canon.all("affordance"), t + 22_000, 1)
        pkt = build_packet(tx, june, LOD.HOT, aff, 1, t + 22_000)
    assert [tix for tix, _ in raw] == [0, 1] and raw[0][1]
    assert pkt.unprocessed == raw[1][1] == ['I said: "Anyone there?"']
    assert [o for o in pkt.omitted if o.startswith("unprocessed: ")] == [f"unprocessed: {x}" for x in raw[0][1]]
