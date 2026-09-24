"""Actors and dossier fusion (P4). Rules DOS-01..05 (mind/actor.py).

A dossier is stored whole (baseline) plus deltas; fusion replays the deltas in order and must still
validate. Deltas edit fields; they never invent them.
"""

from __future__ import annotations

import json

import pytest

from as_engine.contracts.dossier import ActorDossier, PCDossier
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.mind import actor

pytestmark = pytest.mark.phase(4)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def delta(w, local, path, op, value, at=None):
    """Commit one dossier delta the way mind.actor would (REFLECTION, writer mind.actor)."""
    t = now(w) if at is None else at
    with w.store.transaction() as tx:
        did = tx.mint("ddl")
        tx.commit_event(Event(type=EventType.REFLECTION, writer="mind.actor", at=t, turn_index=0, actor_id=w.id(local),
                              writes=[WriteRecord(op=WriteOp.INSERT, table="dossier_deltas", values={
                                  "delta_id": did, "actor_id": w.id(local), "event_id": "scenario", "path": path,
                                  "op": op, "value_json": json.dumps(value), "at": t})],
                              payload={"actor_id": w.id(local), "delta_id": did}))
    return did


def line(w, local, text, at, pinned=False):
    with w.store.transaction() as tx:
        lid = tx.mint("vln")
        tx.commit_event(Event(type=EventType.REFLECTION, writer="mind.actor", at=at, turn_index=0, actor_id=w.id(local),
                              writes=[WriteRecord(op=WriteOp.INSERT, table="voice_lines", values={
                                  "line_id": lid, "actor_id": w.id(local), "text": text, "at": at,
                                  "event_id": "scenario", "pinned": int(pinned)})],
                              payload={"actor_id": w.id(local), "line_id": lid}))
    return lid


# --------------------------------------------------------------------------- fusion (DOS-01..03)
def test_fused_without_deltas_is_the_baseline(scenario, canon):
    w = scenario("metal_fence")
    d = actor.fused(w.store, w.id("mara"))
    assert isinstance(d, ActorDossier)
    assert d == canon.get("core:actor/mara_voss"), "the stored baseline is the whole record (DOS-01)"
    assert isinstance(actor.fused(w.store, w.id("pc")), PCDossier)


def test_set_append_remove_in_order(scenario):
    w = scenario("metal_fence")
    t = now(w)
    delta(w, "mara", "life.current_project", "set", "Get the office window boarded properly", at=t + 1)
    delta(w, "mara", "life.fears", "append", "That the fence sheet was not the wind", at=t + 2)
    delta(w, "mara", "voice.would_never_say", "remove", actor.fused(w.store, w.id("mara")).voice.would_never_say[0], at=t + 3)
    delta(w, "mara", "life.current_project", "set", "Find out who is behind the fence", at=t + 4)
    d = actor.fused(w.store, w.id("mara"))
    assert d.life.current_project == "Find out who is behind the fence", "later delta wins"
    assert d.life.fears[-1] == "That the fence sheet was not the wind"
    base = json.loads(w.store.query_one("SELECT d.baseline_json FROM actors a JOIN dossiers d ON d.dossier_id = a.dossier_id "
                                        "WHERE a.actor_id = ?", (w.id("mara"),))[0])
    assert d.voice.would_never_say == base["voice"]["would_never_say"][1:]
    assert base["life"]["current_project"] != d.life.current_project, "the baseline row is never edited"


def test_deltas_apply_by_time_then_id(scenario):
    w = scenario("metal_fence")
    t = now(w)
    delta(w, "june", "life.current_project", "set", "Second", at=t + 10)
    delta(w, "june", "life.current_project", "set", "First", at=t + 5)
    assert actor.fused(w.store, w.id("june")).life.current_project == "Second"


@pytest.mark.parametrize("path,op,value", [
    ("life.favourite_colour", "set", "blue"),          # not a field
    ("nonsense.path", "set", 1),
    ("life.fears", "remove", "Something she never feared"),
])
def test_deltas_never_invent_fields(scenario, path, op, value):
    w = scenario("metal_fence")
    delta(w, "mara", path, op, value)
    with pytest.raises(ValueError):
        actor.fused(w.store, w.id("mara"))


def test_a_delta_that_breaks_the_contract_is_an_error(scenario):
    """DOS-03: the fused result validates again — an age of 300 is not a person."""
    w = scenario("metal_fence")
    delta(w, "mara", "identity.age", "set", 300)
    with pytest.raises(ValueError):
        actor.fused(w.store, w.id("mara"))


# --------------------------------------------------------------------------- names, controller, voice
def test_display_name_and_controller(scenario):
    w = scenario("metal_fence")
    assert actor.display_name(w.store, w.id("mara")) == "Mara Voss"
    assert actor.controller(w.store, w.id("pc")) == "human"
    assert actor.controller(w.store, w.id("june")) == "model"


def test_recent_lines_pinned_first_then_latest(scenario):
    w = scenario("metal_fence")
    t = now(w)
    line(w, "mara", "One.", t + 1)
    line(w, "mara", "Eli stays in the office.", t + 2, pinned=True)
    line(w, "mara", "Two.", t + 3)
    line(w, "mara", "Three.", t + 4)
    line(w, "mara", "Four.", t + 5)
    line(w, "june", "Not Mara.", t + 6)
    assert actor.recent_lines(w.store, w.id("mara"), 3) == ["Eli stays in the office.", "Three.", "Four."]
    assert actor.recent_lines(w.store, w.id("mara"), 10) == ["Eli stays in the office.", "One.", "Two.", "Three.", "Four."]
    assert actor.recent_lines(w.store, w.id("mara"), 1) == ["Eli stays in the office."]
    assert actor.recent_lines(w.store, w.id("eli"), 5) == []
