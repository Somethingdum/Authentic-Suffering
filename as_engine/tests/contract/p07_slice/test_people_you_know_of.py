"""People you know of (D-153). Rule SKULL-11 (mind/packet.py P-handles (4) known_elsewhere; mind/memory.py MEM-01;
contracts/settings.py PacketRules.max_known_elsewhere; prompts intake.*).

A packet named only the people a mind could see or hear this moment, the people it has a relationship row with and
its household. The player's character has no relationship rows at all (C06: nothing writes feelings into the PC),
so its packet knew nobody it could not see: "I walk over to June and shove her." met an intake that had never heard
of June, though Owen had seen her go into the stockroom a minute before. Now everyone keeps in mind the people they
know by name, where they last saw them — and nobody they saw die.
"""

from __future__ import annotations

import pytest
from slice_kit import pick, play

from as_engine.contracts.common import LOD, CallClass
from as_engine.contracts.settings import PacketRules, RulesConfig
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet
from as_engine.physical import bodies

pytestmark = pytest.mark.phase(7)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def where(w, local, at, turn=0):
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(local), at, turn)
        aff = enumerate_affordances(tx, w.id(local), w.canon.all("affordance"), at, turn)
        p = build_packet(tx, w.id(local), LOD.WARM, aff, turn, at)
    return {w.local(p.handles[e.handle]): e.whereabouts for e in p.entities}


def test_owen_knows_where_his_crew_went(scenario):
    w = scenario("metal_fence")
    known = where(w, "pc", now(w) + 100)
    assert known["june"] == "last seen in the stockroom just now"
    assert known["eli"] == "last seen in the office just now" and known["nita"] == "last seen in the rear alley just now"


def test_at_most_a_few_and_never_the_dead_you_saw(scenario):
    w = scenario("metal_fence", rules=RulesConfig(packet=PacketRules(max_known_elsewhere=2)))
    t = now(w)
    with w.store.transaction() as tx:
        w.store.conn.execute("UPDATE acquaintance SET last_seen = ? WHERE holder_id = ? AND subject_id = ?",
                             (t - 1000, w.id("pc"), w.id("eli")))
        ev = bodies.kill(tx, w.id("nita"), "test", t, 0, w.rng)
        perception.grant(tx, w.id("pc"), event_id=ev.event_id, channel="visual", fidelity="exact", text="Nita falls and lies still.",
                         source_id=w.id("nita"), at=t, turn_index=0)
    known = where(w, "pc", t + 100, turn=1)                      # a turn later: she is no source of this one
    assert "nita" not in known, "seen dead: not someone you expect to find"
    assert [k for k, v in known.items() if v != "here"] == ["alice", "june"], "two at most, the most recently seen (Eli longest ago)"


def test_walk_over_to_june(scenario, fake):
    w = scenario("metal_fence")
    s = w.session()
    seen = {}

    def answer(r):
        seen["prompt"], seen["system"] = r.messages[-1].content, r.messages[0].content
        try:
            h = pick(w, r, "move_through_portal", target="storeroom_door")
        except KeyError:
            return {"choice": "NONE", "none_reason": "impossible", "manner": "", "remainder": None, "clarify": None}
        return {"choice": h, "none_reason": None, "manner": "", "remainder": "shove June", "clarify": None}
    fake.script(CallClass.INTAKE, answer, times=2)
    out = play(s, "do", "I walk over to June and shove her.")
    assert out.ok, out.rejected_message
    assert "- P" in seen["prompt"] and ": June (last seen in the stockroom" in seen["prompt"]
    assert "the first step is going there" in seen["system"]
    assert s.extras["remainder"] == "shove June"
    start = w.store.query_one("SELECT json_extract(payload, '$.def_id') FROM events WHERE type = 'ACTION_START' AND actor_id = ? "
                              "ORDER BY seq DESC LIMIT 1", (s.pc_id,))
    assert start[0] == "move_through_portal"
