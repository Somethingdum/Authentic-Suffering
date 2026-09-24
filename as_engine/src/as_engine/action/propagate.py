"""Causal propagation (Stage 9). Owner 'action.propagate' (writer of NOISE / SPEECH / LIGHT events;
they carry no table writes). Rules PROP-01..04.

propagate(tx, outcome_events, at, turn_index) -> list[Event]
  P5 scope — the parts whose owners exist by P5:
  * Sound needs no step here: NOISE and SPEECH events are already committed by the effects and the
    resolver; perception (stage 11 reactions, stage 13 aftermath) computes receptions from them.
  * Infected attraction (PROP-04, P10): for every NOISE and SPEECH among ``outcome_events`` (seq
    order): the receptions of its sound (sense.acoustics.receptions(tx, payload.source_db,
    sense.acoustics.source_point(tx, payload, event.actor_id), event.at, rules.acoustics)) — for
    each listener that is an active
    infected body (world.infected.active) whose received_db >= world.infected.threshold(...):
    world.infected.attract(tx, listener, target = the speaker's body for SPEECH, else the NOISE's
    place_id, event.at, cause = that event, turn_index, reason 'noise').
  * Infected sight (INF-02, P10): for every MOVE among ``outcome_events`` whose body is not infected:
    each active infected body in its to_place (by body_id) that has no living body target in that
    place and world.infected.sees(tx, it, the mover, event.at) -> attract(target = the mover,
    reason 'sight').
  * Evidence (P10, world.traces.create; source = the event): HARM whose wound bleeds at 1 %/min or
    more and is not clotted -> TRACE 'blood' "Blood on the ground, still wet." in the body's place;
    PORTAL_CHANGE raising damage -> TRACE 'damage' f"The {portal name} has been forced." in the place
    of that portal's side where the actor stood (place_a when unknown); DEATH whose cause is not
    'offscreen' -> TRACE 'corpse' "A body lies here." in the body's place (off-screen deaths get
    theirs from content, CAS-013).
  Returns the events it committed (P5: always []; P10: the drifts and traces). Conservation holds
  after propagation (G9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.store import Tx


def propagate(tx: "Tx", outcome_events: list["Event"], at: int, turn_index: int) -> list["Event"]:
    raise NotImplementedError("P5")
