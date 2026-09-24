"""Tasks: work continues through talk (P5). Owner 'action.tasks' (writes ``tasks`` only).
Rules TASK-01..03, CROWD-04.

A task is counted work: steps_total steps of step_s seconds each. Time spent is the only thing that
advances it; a conversation never pauses it unless the actor starts another action (CAS-014 pauses
it) — the actor's own choice, prompted when a cue in ``interrupt_on`` is present (mind.cues).
Every TASK_STEP payload is {task_id, actor_id, kind, label, steps_done, steps_total, status}.

start(tx, actor_id, kind, label, steps_total, step_s, at, interrupt_on, target_ids, turn_index,
      *, focus=False) -> task_id
  Kind 'tsk'. Commits TASK_STEP (status 'active', steps_done 0) inserting the row with
  started_at = at, next_due_at = at + step_ms (step_ms = round(step_s x 1000)). An actor with
  another ACTIVE task -> that task is paused first (pause(), same at).
advance(tx, actor_id, to_ms, turn_index) -> list[Event]
  The actor's active task (none -> []). done = min(steps_total, (to_ms - started_at) //
  step_ms) — started_at is the virtual start that makes previously done steps count (resume sets
  it). If done > steps_done: ONE TASK_STEP at at = started_at + done x step_ms with steps_done =
  done; status 'done' (next_due_at NULL) when done == steps_total, else 'active' with next_due_at
  = started_at + (done + 1) x step_ms. Returns [that event] or [].
pause(tx, task_id, at, cause_event_id, turn_index) -> Event
  advance(actor, at) first, then TASK_STEP status 'paused' (next_due_at NULL). A task that is
  not active -> ValueError.
resume(tx, task_id, at, cause_event_id, turn_index) -> Event
  A paused task becomes active again with started_at = at - steps_done x step_ms and next_due_at
  = at + step_ms (it resumes where it stood, never from zero — CAS-014). Only one active task per
  actor: resuming pauses any other active one first.
interrupt(tx, task_id, cause_event_id, at, turn_index) = pause (the cascade name for it).
active_task(store, actor_id) -> dict | None   the active row (first by started_at, task_id).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.store import Store, Tx


def start(tx: "Tx", actor_id: str, kind: str, label: str, steps_total: int, step_s: float, at: int,
          interrupt_on: list[str], target_ids: list[str], turn_index: int, *, focus: bool = False) -> str:
    raise NotImplementedError("P5")


def advance(tx: "Tx", actor_id: str, to_ms: int, turn_index: int) -> list["Event"]:
    raise NotImplementedError("P5")


def pause(tx: "Tx", task_id: str, at: int, cause_event_id: str | None, turn_index: int) -> "Event":
    raise NotImplementedError("P5")


def resume(tx: "Tx", task_id: str, at: int, cause_event_id: str | None, turn_index: int) -> "Event":
    raise NotImplementedError("P5")


def interrupt(tx: "Tx", task_id: str, cause_event_id: str | None, at: int, turn_index: int) -> "Event":
    """= pause(tx, task_id, at, cause_event_id, turn_index)."""
    raise NotImplementedError("P5")


def active_task(store: "Store | Tx", actor_id: str) -> dict | None:
    raise NotImplementedError("P5")
from ._impl_p5a import start, advance, pause, resume, interrupt, active_task  # noqa
