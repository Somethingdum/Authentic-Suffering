"""Command line (P7; new-run P10). Rules CLI-01..05. `as-engine [--config PATH] <command> …` —
the debugging surface of the slice. main(argv=None) -> int (argv None: sys.argv[1:]); every command
returns an exit code and prints plain lines to stdout; nothing raises to the shell for an expected
problem.

Global: --config PATH (default 'as_config.yaml'): config_loader.load_engine_config(PATH) (a
missing file means the defaults; relative paths resolve against the file's folder).
Parsing: argparse with prog 'as-engine' and one required sub-command (argparse's own usage errors
exit 2 as argparse does).

CLI-01 content-check [--pack DIR] (repeatable: --pack A --pack B; argparse action 'append')
  content.pack.load_canon([content_dir/core] + each --pack DIR as given). One line per issue in the
  loader's order: f"{severity.upper()} {code} {message}", then f"{errors} errors, {warnings}
  warnings in {n} packs." (warnings = every issue that is not an error; n = the number of folders
  given to the loader). Exit 1 when any issue is an error, else 0.
CLI-02 new-scenario SCENARIO [--packs-root DIR] [--fake]
  service.runs.create_run_from_scenario(config, SCENARIO, transport, packs_root = --packs-root
  (None: content_dir), core_pack_dir = content_dir/core); prints f"Created run {run_id} in
  {run_dir}"; closes the store; exit 0. transport: --fake -> testing.fake_lm.FakeTransport(),
  else lanes.transport.HttpTransport().
CLI-03 play RUN_ID [--fake]
  service.runs.load_run(config, RUN_ID, transport); a RunError prints f"[{code}] {message}" and
  exits 1. Prints each load notice, then the last narration (narration table, highest turn) or
  'Ready.'. Then a loop reading lines with input('> ') (each stripped) until EOF or 'quit' /
  'exit' (case-insensitive): an empty line is skipped; a line starting 'ask ' (case-insensitive,
  WITH the space) prints 'Questions are answered in the Play UI.' (Ask is not a turn); a line
  starting 'say ' plays mode 'say' with the rest stripped; anything else (a bare 'say' or 'ask'
  included) plays mode 'do' with the whole line. Each turn
  is asyncio.run(turn.pipeline.run_turn(session, InTurnSubmit(mode, text))) and prints the
  narration, or f"[{rejected_code}] {rejected_message}". P10: when config.background_cognition
  is true and the PC's body is alive, each turn first runs asyncio.run(runner.catch_up(
  session)) with one service.background.BackgroundRunner for the whole loop (the quiet hours,
  BG-01: the terminal has no idle time, so they happen before the next move). The store is
  closed at the end; exit 0.
CLI-04 replay RUN_ID
  asyncio.run(service.replay.resimulate(config, RUN_ID)); a RunError prints f"[{code}] {message}"
  and exits 1. One line per entry: f"turn {n}: same", or f"turn {n}: DIFFERENT ({problem or 'state
  hash'}: expected {str(expected)[:12]}, got {str(got)[:12]})" (expected may be None); then
  f"{count} turns re-simulated: " + ('all the same.' | 'the run diverged.'). Exit 0 when every
  entry is ok, else 1.
CLI-05 new-run PC_REF [--difficulty D] [--era E] [--detail T] [--days N] [--seed S] [--fake]   (P10)
  A generated world. --difficulty / --era / --detail take the Difficulty / Era / WorldDetail values
  (argparse choices, so a wrong word is argparse's usage error); --days and --seed are ints.
  settings = RunSettings(difficulty, era, world_detail, days_since_fall, seed — only the options
  given; the rest are the defaults); a value RunSettings refuses (a pydantic ValidationError, e.g.
  --days 0) prints f"[bad_settings] {its first error's msg}" and exits 1. session =
  asyncio.run(service.runs.create_run(config, PC_REF, settings, transport, progress = a callable
  printing f"{pct:.0f}% {label}" per call — P10 progress v2: a call with a sub-phase (WG2 / WG6
  counting their model answers) prints f"{pct:.0f}% {label} ({done}/{total})")); prints
  f"Created run {run_id} in {run_dir}"; closes the store; exit 0. A WorldgenAborted prints
  f"[{code}] {message}" (message = str(error)), a
  kernel.errors.SettingsError f"[bad_settings] {message}", a RunError f"[{code}] {message}"; each
  exits 1. transport as for new-scenario.
probe | bench | doctor
  These are repository tools (they need the live models or the repo): print f"Run it from the
  repository: python tools/as/{command}.py" and exit 2.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    raise NotImplementedError("P7")
