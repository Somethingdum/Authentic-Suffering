"""Said once (D-244). mind/packet.py ambient_packet voice (AMB-02).

The room's small talk is written from a short card of how the speaker talks. For most of a world's people — the
generated ones — the capsule is their two habits, so the card said them twice ("Marcus picks fights with words when
drinking; turns maudlin when sober." and "How you talk: Picks fights with words when drinking. Turns maudlin when
sober."), and their way of sounding came last as a bare fragment ("drops the 'g' on every -ing").
"""

from __future__ import annotations

import json

import pytest

from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.mind import perception
from as_engine.mind.packet import ambient_packet
from as_engine.physical import space

pytestmark = pytest.mark.phase(7)


def voice_of(w, who, capsule, tendencies, dialect):
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:                          # Mara and June on the sales floor, the lights up
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        for x, at_x in (("june", 5.0), ("mara", 8.0)):
            tx.commit_event(space.move_event(tx, w.id(x), w.id("sales_floor"), None, at_x, 4.0, t, None, 0))
        tx.commit_event(Event(type=EventType.VOICE_WRITTEN, writer="mind.actor", at=t, turn_index=0, actor_id=w.id(who),
                              writes=[WriteRecord(op=WriteOp.INSERT, table="dossier_deltas", values={
                                  "delta_id": tx.mint("ddl"), "actor_id": w.id(who), "event_id": "test", "path": p, "op": "set",
                                  "value_json": json.dumps(v), "at": t})
                                  for p, v in (("voice.capsule", capsule), ("voice.speech_tendencies", tendencies),
                                               ("voice.dialect_notes", dialect))],
                              payload={"actor_id": w.id(who)}))
        perception.compile_scene(tx, w.id(who), t, 0)
        return ambient_packet(tx, w.id(who), 0, t, idle=True)


def test_a_generated_voice_is_said_once(scenario):
    w = scenario("metal_fence")
    pk = voice_of(w, "mara", "Mara picks fights with words when drinking; turns maudlin when sober.",
                  ["picks fights with words when drinking", "turns maudlin when sober"], "drops the 'g' on every -ing")
    assert pk.voice[0] == "Mara picks fights with words when drinking; turns maudlin when sober."
    assert not any(v.startswith("How you talk: ") for v in pk.voice), pk.voice
    assert pk.voice[-1] == "How you sound: drops the 'g' on every -ing."


def test_a_written_voice_keeps_its_habits(scenario):
    w = scenario("metal_fence")
    pk = voice_of(w, "mara", "Quick and quiet, always half a step from apologising.",
                  ["Counts under her breath", "Says sorry before she asks"], "")
    assert "How you talk: Counts under her breath. Says sorry before she asks." in pk.voice
    assert not any(v.startswith("How you sound") for v in pk.voice)
