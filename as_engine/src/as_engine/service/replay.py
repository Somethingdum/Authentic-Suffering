"""Re-simulation replay (P7). Rules DET-02, DET-03 (docs/as/03_DATA_MODEL.md §9).

A run can be played again from its turn-0 snapshot with the model answers it recorded: the same
inputs through the same code must reach the same state after every turn. This is how a divergence
(a nondeterministic iteration order, a hidden clock read, a changed rule) is caught.

resimulate(config, run_id, *, pack_dirs=None) -> list[dict]
  rd = <runs_dir>/<run_id>; no manifest.json or no turn0.sqlite -> service.runs.RunError(
  'not_found', f"There is no run called {run_id} with a starting snapshot."). The original store is
  opened read-only in spirit (world.sqlite; nothing is written to it). A working copy:
  reports/replay/ is emptied and made, turn0.sqlite is copied to reports/replay/world.sqlite, and a
  session is opened on it the same way service.runs opens one
  (``pack_dirs`` or the manifest's), with transport = lanes.calllog.ReplayTransport(original store)
  and run_dir set to None (a replay never autosaves). Its run_id is the working folder's name,
  'replay'.
  For each player_inputs row of the original, in turn_index order (T = its turn_index):
    first (P8, SET-01) every original SETTINGS_CHANGE event whose payload has a 'field' key (a
      mid-run change made by service.session.change_settings — not the {source: 'run_start'} one)
      with turn_index < T that has not been re-applied yet, in seq order: in its own transaction,
      service.session.change_settings(tx, session, {field: payload.new}). A replay therefore makes
      the same settings change at the same moment the player did;
    mode 'suggestion' -> session.extras['suggestions'] = {'r1': {'signature': mapped.signature,
      'label': raw_text}} and InTurnSubmit(mode='do', suggestion_ref='r1');
    otherwise -> session.extras['forced_addressee'] = mapped.addressee (None allowed) and
      InTurnSubmit(mode=row.mode, text=row.raw_text).
    out = await turn.pipeline.run_turn(session, submit); expected = the original turn_ledger stage
    19 detail's full_state_hash for that turn (None when absent); got =
    kernel.hashing.full_state_hash(working store).
    Report entry {turn_index, ok: out.ok and got == expected, expected, got, problem: None when
    out.ok else (out.rejected_code or 'failed')}; the first entry that is not ok ends the replay.
  Both stores are closed at the end (whatever happens). Returns the entries.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.settings import EngineConfig


async def resimulate(config: "EngineConfig", run_id: str, *, pack_dirs: list[str | Path] | None = None) -> list[dict]:
    raise NotImplementedError("P7")
