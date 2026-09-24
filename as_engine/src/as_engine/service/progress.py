"""The loading bar (P10, progress v2). Rules PROG-01..07. docs/as/10_UI.md §progress.

Every long job first announces its PLAN — its phases, in order, each with its sub-phases, in order
— and then says where it is, live: which phase, which sub-phase, how far through, how long so far,
how long to go. The UI draws the whole plan as a bar with the current step lit, and under it a
rotating line from the QUIPS (content: ui/quips.yaml) for the step it is on — "Rolling…", but
about the step. Code never picks a quip: which line shows, and when, is the UI's (10_UI.md).

PROG-01 Jobs: 'worldgen' (service.runs.create_run), 'turn' (turn.pipeline.run_turn), 'quiet_hours'
  (service.background.catch_up before a move) and 'time_skip' (sleeping or waiting a long while —
  P12 wires it). One Tracker per job run.
PROG-02 Plans are fixed (PLANS below): kind -> tuple[Phase]; Phase(id, label, weight, subs:
  tuple[Sub(id, label)]). Weights of a plan sum to 100. Labels are plain words (UI-CLARITY-01:
  never an engine term). A turn's sub-phases are its stages, grouped: TURN_STAGES maps each stage
  number to (phase id, sub id), in the order the pipeline announces them; worldgen's phases are
  its stages (atlas.STAGES without COMMIT, labels atlas.STAGE_LABELS, weights atlas.STAGE_SHARE)
  and only two of them have sub-phases, the long ones that call the model: WG2 'history' (a batch
  of history at a time) and WG6 'dossiers' (a person at a time).
PROG-03 Tracker(kind, job_id, push, *, dev=False, clock=None) (clock: seconds, a zero-argument
  callable; None -> the running asyncio loop's time(), read when a message is made — the clock
  turn_progress's elapsed_s already uses; DET-11: nothing here imports time). plan(quips) -> pushes
  progress_plan {job_id, kind, title: TITLES[kind], phases: [{id, label, weight, subs: [{id,
  label}]}], quips} (quips: the lines of quips_for(canon, kind), below). step(phase, sub=None, *,
  done=None, total=None, detail=None) -> pushes progress {job_id, kind, phase, phase_index, sub,
  sub_label, done, total, pct, elapsed_s, eta_s, detail}. done(ok) -> pushes progress_done
  {job_id, kind, ok, elapsed_s}. push may be async (awaited). A step naming a phase or sub the
  plan does not have -> ValueError (a plan is a promise).
PROG-04 pct = the weights of the phases before this one + this phase's weight x f, where f =
  done / total when both are given (total > 0), else the sub's position (index / number of subs;
  0 without subs); rounded to 1 decimal; never lower than the last pct pushed (a turn's second
  round of reactions does not send the bar backwards — it holds). elapsed_s = clock() - the
  plan's time, rounded to 1. eta_s = round(elapsed_s x (100 - pct) / pct) when pct >= 5, else None.
PROG-05 No leaks (normal mode). A progress message's detail is None unless dev is True (the run's
  dev_mode): step() drops it otherwise. No message says who is thinking, how many minds are, where
  anything is or what a roll came to; done / total are sent only for worldgen, quiet hours and time
  skips (how much work is left), never for a turn (step() drops them for kind 'turn'). (No P10
  job passes a detail; the field is there for the developer panel, P12.)
PROG-06 quips_for(canon, kind) -> dict[str, list[str]]: every canon 'quips' record's lines whose key
  starts with kind (keys: kind, f"{kind}.{phase}", f"{kind}.{phase}.{sub}"), merged over the packs
  in load order (a later pack ADDS lines to a key, never removes one), each list without
  duplicates in first-seen order. Content rule CNT-16: a quips key names a plan (kind), a phase of
  it, or a sub of that phase; no line is empty or longer than 80 characters.
PROG-07 (the UI's side, 10_UI.md) The bar shows every phase of the plan in order with the current
  one lit, the sub-phase label under it, and one quip: the most specific non-empty list for (kind,
  phase, sub), then (kind, phase), then (kind); a new line every 2.5 s, drawn at random but never
  one of the last three shown; the quip is never the only thing on screen (the label is always
  there).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..world.worldgen import atlas


@dataclass(frozen=True)
class Sub:
    id: str
    label: str


@dataclass(frozen=True)
class Phase:
    id: str
    label: str
    weight: int
    subs: tuple[Sub, ...] = ()


TITLES: dict[str, str] = {
    "worldgen": "Making your world", "turn": "Your move", "quiet_hours": "Everyone else catches up",
    "time_skip": "Time passes",
}

PLANS: dict[str, tuple[Phase, ...]] = {
    "turn": (
        Phase("read", "Reading your move", 8, (Sub("check", "Checking the world"), Sub("read", "Reading your move"),
                                               Sub("weigh", "Weighing your words"))),
        Phase("senses", "Everyone takes it in", 12, (Sub("see", "Eyes and ears"), Sub("notice", "Who noticed what"),
                                                     Sub("think", "What it means to them"))),
        Phase("minds", "People decide", 30, (Sub("decide", "People decide"),)),
        Phase("world", "The world moves", 15, (Sub("act", "Everyone acts"), Sub("land", "It lands"),
                                               Sub("react", "Reactions"))),
        Phase("commit", "Locking it in", 3, (Sub("lock", "Locking it in"),)),
        Phase("after", "Writing it down", 30, (Sub("remember", "What they will remember"),
                                               Sub("write", "Writing it down"), Sub("choose", "Choosing the words"),
                                               Sub("ties", "What it changes between them"),
                                               Sub("loose", "Loose ends"))),
        Phase("save", "Saving", 2, (Sub("save", "Saving"),)),
    ),
    "worldgen": tuple(
        Phase(stage, atlas.STAGE_LABELS[stage], atlas.STAGE_SHARE[stage],
              {"WG2": (Sub("history", "Remembering what happened"),),
               "WG6": (Sub("dossiers", "Writing the people down"),)}.get(stage, ()))
        for stage in atlas.STAGES if stage != "COMMIT"
    ),
    "quiet_hours": (Phase("quiet", "Everyone else catches up", 100, (Sub("jobs", "Thinking it over"),)),),
    "time_skip": (Phase("world", "Time passes", 100, (Sub("hours", "Hour by hour"),)),),
}

# turn stage -> (phase, sub), in the order turn.pipeline announces them (9, 10 and 18 never are)
TURN_STAGES: dict[int, tuple[str, str]] = {
    0: ("read", "check"), 1: ("read", "read"), 2: ("read", "weigh"),
    3: ("senses", "see"), 4: ("senses", "notice"), 5: ("senses", "think"),
    6: ("minds", "decide"), 7: ("world", "act"), 8: ("world", "land"), 11: ("world", "react"),
    12: ("commit", "lock"), 13: ("after", "remember"), 16: ("after", "write"), 17: ("after", "choose"),
    14: ("after", "ties"), 15: ("after", "loose"), 19: ("save", "save"),
}


class Tracker:
    """PROG-03. The pure part of the bar: what to push, when told where the job is."""

    def __init__(self, kind: str, job_id: str, push: Callable[[str, dict], Any], *, dev: bool = False,
                 clock: Callable[[], float] | None = None):
        raise NotImplementedError("P10")

    async def plan(self, quips: dict[str, list[str]]) -> None:
        raise NotImplementedError("P10")

    async def step(self, phase: str, sub: str | None = None, *, done: int | None = None, total: int | None = None,
                   detail: str | None = None) -> None:
        raise NotImplementedError("P10")

    async def done(self, ok: bool) -> None:
        raise NotImplementedError("P10")


def quips_for(canon, kind: str) -> dict[str, list[str]]:
    raise NotImplementedError("P10")
from ._impl_progress import Tracker, quips_for  # noqa
