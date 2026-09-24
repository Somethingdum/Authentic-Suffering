"""Implementation of cli.py."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


def _parser():
    p = argparse.ArgumentParser(prog="as-engine", description="Authentic Suffering engine tools.")
    p.add_argument("--config", default="as_config.yaml", help="path to as_config.yaml (default: ./as_config.yaml)")
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("content-check", help="validate the content packs")
    c.add_argument("--pack", action="append", default=[], help="an extra pack folder (repeatable)")
    n = sub.add_parser("new-scenario", help="create a run from a scenario file")
    n.add_argument("scenario")
    n.add_argument("--packs-root", default=None, help="folder holding the packs the scenario names (default: content_dir)")
    n.add_argument("--fake", action="store_true", help="use the fake model (no LM Studio)")
    pl = sub.add_parser("play", help="a minimal terminal play loop (debug; the real UI is the Play UI)")
    pl.add_argument("run_id")
    pl.add_argument("--fake", action="store_true")
    r = sub.add_parser("replay", help="re-simulate a run's recorded turns and compare state hashes")
    r.add_argument("run_id")
    nr = sub.add_parser("new-run", help="generate a world and start a run in it")
    nr.add_argument("pc_ref")
    from .contracts.common import Difficulty, Era, WorldDetail
    nr.add_argument("--difficulty", default=None, choices=[d.value for d in Difficulty])
    nr.add_argument("--era", default=None, choices=[e.value for e in Era])
    nr.add_argument("--detail", default=None, choices=[w.value for w in WorldDetail])
    nr.add_argument("--days", type=int, default=None)
    nr.add_argument("--seed", type=int, default=None)
    nr.add_argument("--fake", action="store_true")
    for name in ("probe", "bench", "doctor"):
        sub.add_parser(name, help=f"see tools/as/{name}.py")
    return p


def _transport(fake):
    if fake:
        from .testing.fake_lm import FakeTransport
        return FakeTransport()
    from .lanes.transport import HttpTransport
    return HttpTransport()


def main(argv=None):
    from .config_loader import load_engine_config
    argv = list(sys.argv[1:] if argv is None else argv)
    args = _parser().parse_args(argv)
    cfg = load_engine_config(args.config)
    if args.command == "content-check":
        from .content.pack import load_canon
        dirs = [Path(cfg.content_dir) / "core"] + [Path(d) for d in args.pack]
        _canon, issues = load_canon(dirs)
        for i in issues:
            print(f"{i.severity.upper()} {i.code} {i.message}")
        ne = sum(1 for i in issues if i.severity == "error")
        nw = sum(1 for i in issues if i.severity != "error")
        print(f"{ne} errors, {nw} warnings in {len(dirs)} packs.")
        return 1 if ne else 0
    if args.command == "new-scenario":
        from .service.runs import create_run_from_scenario
        s = create_run_from_scenario(cfg, Path(args.scenario), _transport(args.fake),
                                     packs_root=args.packs_root, core_pack_dir=Path(cfg.content_dir) / "core")
        print(f"Created run {s.run_id} in {s.run_dir}")
        s.store.close()
        return 0
    if args.command == "play":
        from .contracts.protocol import InTurnSubmit
        from .service.runs import RunError, load_run
        from .turn.pipeline import run_turn
        try:
            s = load_run(cfg, args.run_id, _transport(args.fake))
        except RunError as e:
            print(f"[{e.code}] {e.message}")
            return 1
        for n in s.extras.get("notices", []):
            print(n)
        last = s.store.query_one("SELECT text FROM narration ORDER BY turn_index DESC LIMIT 1")
        print(last[0] if last else "Ready.")
        from .service.background import BackgroundRunner
        runner = BackgroundRunner()
        try:
            while True:
                try:
                    line = input("> ").strip()
                except EOFError:
                    break
                if not line:
                    continue
                if line.lower() in ("quit", "exit"):
                    break
                if line.lower().startswith("ask "):
                    print("Questions are answered in the Play UI.")
                    continue
                mode, text = ("say", line[4:].strip()) if line.lower().startswith("say ") else ("do", line)
                if cfg.background_cognition and s.store.query_one(
                        "SELECT alive FROM bodies WHERE body_id=?", (s.pc_id,))[0] == 1:
                    asyncio.run(runner.catch_up(s))
                out = asyncio.run(run_turn(s, InTurnSubmit(mode=mode, text=text)))
                print(out.narration if out.ok else f"[{out.rejected_code}] {out.rejected_message}")
        finally:
            s.store.close()
        return 0
    if args.command == "replay":
        from .service.replay import resimulate
        from .service.runs import RunError
        try:
            report = asyncio.run(resimulate(cfg, args.run_id))
        except RunError as e:
            print(f"[{e.code}] {e.message}")
            return 1
        for r in report:
            print(f"turn {r['turn_index']}: " + ("same" if r["ok"] else
                  f"DIFFERENT ({r.get('problem') or 'state hash'}: expected {str(r['expected'])[:12]}, got {str(r['got'])[:12]})"))
        ok = all(r["ok"] for r in report)
        print(f"{len(report)} turns re-simulated: " + ("all the same." if ok else "the run diverged."))
        return 0 if ok else 1
    if args.command == "new-run":
        from pydantic import ValidationError
        from .contracts.settings import RunSettings
        from .kernel.errors import SettingsError
        from .service.runs import RunError, create_run
        from .world.worldgen.pipeline import WorldgenAborted
        kw = {k: v for k, v in (("difficulty", args.difficulty), ("era", args.era), ("world_detail", args.detail),
                                ("days_since_fall", args.days), ("seed", args.seed)) if v is not None}
        try:
            settings = RunSettings(**kw)
        except ValidationError as e:
            print(f"[bad_settings] {e.errors()[0]['msg']}")
            return 1

        def progress(p):
            print(f"{p.pct:.0f}% {p.label}" + (f" ({p.done}/{p.total})" if p.sub is not None else ""))
        try:
            s = asyncio.run(create_run(cfg, args.pc_ref, settings, _transport(args.fake), progress=progress))
        except WorldgenAborted as e:
            print(f"[{e.code}] {e}")
            return 1
        except SettingsError as e:
            print(f"[bad_settings] {e}")
            return 1
        except RunError as e:
            print(f"[{e.code}] {e.message}")
            return 1
        print(f"Created run {s.run_id} in {s.run_dir}")
        s.store.close()
        return 0
    print(f"Run it from the repository: python tools/as/{args.command}.py")
    return 2
