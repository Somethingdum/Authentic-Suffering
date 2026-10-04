"""Call progress (LANE-10, LANE-11; D-110). Nothing here ends a call: it only records whether the
model is moving, so the transport can tell a slow call from a stalled one and the UI can show the wait.

    p = CallProgress(request.call_class, request.lane, expected_s=request.deadline_s)
    p.note_prefill(processed, total, cache)   # the server's prompt-processing progress (when it sends it)
    p.note_text(chars)                        # visible text arrived        (phase 'writing')
    p.note_reasoning(chars)                   # reasoning arrived           (phase 'thinking')
    p.quiet_s()                               # seconds since the last of those
    p.snapshot()                              # a plain dict for the UI and the log

Phases, in order: 'waiting' (nothing yet), 'prefill' (the server reported prompt progress),
'thinking', 'writing'. ``progressed`` is true once anything at all has arrived. ``slow`` is true when
the call has run longer than the regime's ``deadline_s`` (an expectation, never a limit).

stall_window(lane, snapshot) -> float | None   (LANE-10 read from a snapshot, D-114)
  How long the call may stay quiet now: ``lane.stall_window_s`` once it has progressed, once the server has
  reported prompt progress for it (prompt_total > 0), or when the lane says the server reports it
  (prefill_progress 'supported'); else ``lane.silent_prefill_window_s``, 0 meaning no limit (None). The same
  rule the transport applies (lanes/transport.py HttpTransport.window), so the UI can say how long a quiet call
  has before the watchdog ends it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..contracts.common import CallClass, Lane


@dataclass
class CallProgress:
    call_class: CallClass
    lane: Lane
    expected_s: float = 60.0
    started: float = field(default_factory=time.monotonic)
    last_progress: float = field(default_factory=time.monotonic)
    phase: str = "waiting"
    progressed: bool = False
    prompt_total: int = 0
    prompt_cache: int = 0
    prompt_processed: int = 0
    reasoning_chars: int = 0
    text_chars: int = 0
    chunks: int = 0

    def _moved(self) -> None:
        self.last_progress = time.monotonic()
        self.progressed = True

    def note_prefill(self, processed: int, total: int, cache: int = 0) -> bool:
        """True when the server's prompt processing moved forward (that is progress)."""
        if processed > self.prompt_processed or total != self.prompt_total:
            self.prompt_processed, self.prompt_total, self.prompt_cache = processed, total, cache
            if self.phase == "waiting":
                self.phase = "prefill"
            self._moved()
            return True
        return False

    def note_alive(self) -> None:
        """The first chunk of any kind: the server has read the prompt and begun to answer. Counts once."""
        if not self.progressed:
            if self.phase == "waiting":
                self.phase = "thinking"
            self._moved()

    def note_reasoning(self, chars: int) -> None:
        if chars:
            self.reasoning_chars += chars
            self.chunks += 1
            if self.phase != "writing":
                self.phase = "thinking"
            self._moved()

    def note_text(self, chars: int) -> None:
        if chars:
            self.text_chars += chars
            self.chunks += 1
            self.phase = "writing"
            self._moved()

    @property
    def saw_prefill(self) -> bool:
        return self.prompt_total > 0

    def elapsed_s(self) -> float:
        return time.monotonic() - self.started

    def quiet_s(self) -> float:
        return time.monotonic() - self.last_progress

    def snapshot(self) -> dict:
        elapsed = self.elapsed_s()
        return {"call_class": self.call_class.value, "lane": self.lane.value, "phase": self.phase,
                "progressed": self.progressed, "elapsed_s": round(elapsed, 1), "quiet_s": round(self.quiet_s(), 1),
                "slow": elapsed > self.expected_s, "expected_s": self.expected_s,
                "prompt_processed": self.prompt_processed, "prompt_total": self.prompt_total,
                "prompt_cache": self.prompt_cache, "reasoning_chars": self.reasoning_chars,
                "text_chars": self.text_chars}


def stall_window(lane, snap: dict) -> float | None:
    if snap.get("progressed") or snap.get("prompt_total") or lane.prefill_progress == "supported":
        return lane.stall_window_s
    return lane.silent_prefill_window_s or None
