"""The command line (P7). Rules CLI-01..04 (cli.py).

`as-engine` is the debugging surface for the slice: check content, make a run from a scenario,
play it in a terminal with the fake model, and re-simulate it. Every command takes --config
(as_config.yaml) and returns an exit code instead of raising.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from as_engine.cli import main

pytestmark = pytest.mark.phase(7)

TESTS = Path(__file__).resolve().parents[2]
SCENARIO = TESTS / "fixtures" / "scenarios" / "metal_fence.yaml"
PACKS = TESTS.parent.parent / "as_content" / "packs"


@pytest.fixture
def conf(tmp_path):
    p = tmp_path / "as_config.yaml"
    p.write_text(f"schema: as.config.v1\nruns_dir: {(tmp_path / 'runs').as_posix()}\ncontent_dir: {PACKS.as_posix()}\n",
                 encoding="utf-8")
    return p


def test_content_check(conf, capsys):
    """CLI-01: the core pack is clean -> exit 0 and a one-line summary."""
    assert main(["--config", str(conf), "content-check"]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out[-1].startswith("0 errors, ") and out[-1].endswith(" in 1 packs.")


def test_new_scenario_play_and_replay(conf, capsys, monkeypatch, tmp_path):
    """CLI-02..04: create a run from a scenario, play two turns in the terminal with the fake model,
    then re-simulate them."""
    assert main(["--config", str(conf), "new-scenario", str(SCENARIO), "--fake"]) == 0
    first = capsys.readouterr().out.strip()
    assert first == f"Created run owen_marsh_71a in {tmp_path / 'runs' / 'owen_marsh_71a'}"
    monkeypatch.setattr("sys.stdin", io.StringIO("I watch the front door.\nsay Keep it down.\nask Who is Mara?\nquit\n"))
    assert main(["--config", str(conf), "play", "owen_marsh_71a", "--fake"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Ready.\n")
    assert 'Owen says, "Keep it down."' in out
    assert "Questions are answered in the Play UI." in out
    assert main(["--config", str(conf), "replay", "owen_marsh_71a"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines == ["turn 1: same", "turn 2: same", "2 turns re-simulated: all the same."]
    assert main(["--config", str(conf), "play", "nobody_1", "--fake"]) == 1
    assert capsys.readouterr().out.startswith("[not_found] ")


def test_live_tools_live_in_the_repository(conf, capsys):
    """probe / bench / doctor are repository tools, not engine commands: exit 2 with the path to run."""
    assert main(["--config", str(conf), "doctor"]) == 2
    assert capsys.readouterr().out.strip() == "Run it from the repository: python tools/as/doctor.py"
