"""The release audit (P11). Rules REL-01..06, WG-37 (audit/release.py; world/worldgen/checks.py
reassert; D-45, D-95).

Before a release the developer runs it on a generated world: the world as it began is checked
again, the world then runs on its own for days and the dead are counted in and out, the abuse
battery runs, the logs are read for rules nobody built, and every record that can hold a child is
read for the words that must never be there. It works on copies: the run itself does not change.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from as_engine.audit import release
from as_engine.content.safety import MINOR_UNSAFE_TERMS
from as_engine.contracts.settings import EngineConfig
from as_engine.service.runs import RunError
from as_engine.turn import timers

pytestmark = pytest.mark.phase(11)

REPO_PACKS = Path(__file__).resolve().parents[4] / "as_content" / "packs"


@pytest.fixture
def rel(p11_world, tmp_path):
    """(config, run_id, run folder) of a private copy of the generated world."""
    src, run_id = p11_world
    shutil.copytree(src, tmp_path / "runs")
    cfg = EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(REPO_PACKS))
    return cfg, run_id, tmp_path / "runs" / run_id


def edit(db: Path, statement: str, args=()):
    c = sqlite3.connect(db)
    c.execute("PRAGMA foreign_keys=OFF")
    c.execute(statement, args)
    c.commit()
    c.close()


def read(db: Path, statement: str, args=()):
    c = sqlite3.connect(db)
    try:
        return c.execute(statement, args).fetchall()
    finally:
        c.close()


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_a_generated_world_passes(rel):
    cfg, run_id, rd = rel
    before = {n: digest(rd / n) for n in ("world.sqlite", "turn0.sqlite")}
    r = release.release_audit(cfg, run_id, days=3)
    assert r.world_checks == [] and r.abuse == [] and r.unbuilt == [] and r.content == []
    assert r.census["holds"] and r.census["after"] - r.census["before"] == r.census["risen"] - r.census["destroyed"]
    assert r.soak["days"] == r.soak["world_days"] == 3 and r.soak["holds"] and r.soak["events"] > 0
    assert set(r.soak) >= {"death", "offscreen_death", "birth", "raid", "horde_formed", "shortage", "rumour_spread",
                           "faction_operation"}
    assert r.passed
    assert {n: digest(rd / n) for n in before} == before, "the audit works on copies"
    assert (rd / "reports" / "release" / "soak" / run_id / "world.sqlite").exists()


def test_no_run_no_audit(rel):
    cfg, _, _ = rel
    with pytest.raises(RunError) as e:
        release.release_audit(cfg, "nobody_here", days=1)
    assert e.value.code == "not_found"


def test_the_world_as_it_began_is_checked_again(rel):
    """REL-01: turn0 is the world WG9 checked; a threat that is not there is caught again."""
    cfg, run_id, rd = rel
    sk = json.loads(read(rd / "turn0.sqlite", "SELECT commit_json FROM world_params WHERE id = 1")[0][0])["skeleton"]
    assert sk["opening"]["threat_ids"], "the generated opening has a threat near the start"
    for t in sk["opening"]["threat_ids"]:
        edit(rd / "turn0.sqlite", "UPDATE bodies SET alive = 0 WHERE body_id = ?", (t,))
    r = release.release_audit(cfg, run_id, days=1)
    assert r.world_checks == ["Nothing dangerous is near the start."]
    assert not r.passed


def test_a_world_with_no_skeleton_cannot_be_checked(rel):
    cfg, run_id, rd = rel
    wc = json.loads(read(rd / "turn0.sqlite", "SELECT commit_json FROM world_params WHERE id = 1")[0][0])
    wc.pop("skeleton")
    edit(rd / "turn0.sqlite", "UPDATE world_params SET commit_json = ? WHERE id = 1", (json.dumps(wc),))
    assert release.release_audit(cfg, run_id, days=1).world_checks == ["There is no generated world here to check."]


def test_a_leak_in_the_long_quiet_is_caught(rel, monkeypatch):
    """REL-02 / HRD-15: a step that loses one of the dead each day is a step built wrong."""
    cfg, run_id, _ = rel
    real = timers.run_offscreen

    def leaky(tx, rng, until_ms, turn_index):
        out = real(tx, rng, until_ms, turn_index)
        tx.store.conn.execute("UPDATE infected_pools SET active = active - 1 WHERE rowid = "
                              "(SELECT rowid FROM infected_pools WHERE active > 0 ORDER BY zone_id, type_id LIMIT 1)")
        return out
    monkeypatch.setattr(timers, "run_offscreen", leaky)
    r = release.release_audit(cfg, run_id, days=2)
    assert not r.census["holds"] and not r.passed
    assert r.census["after"] - r.census["before"] == r.census["risen"] - r.census["destroyed"] - 2


def test_rules_nobody_built_are_named(rel):
    cfg, run_id, rd = rel
    for i, f in enumerate([{"kind": "timer_unbuilt", "type": "BARTER_DUE", "queue_id": "q1"},
                           {"kind": "cascade_unbuilt", "rule_id": "CAS-099", "what": "a flood"},
                           {"kind": "timer_unbuilt", "type": "BARTER_DUE", "queue_id": "q2"}]):
        edit(rd / "world.sqlite", "INSERT INTO audit_log (audit_id, turn_index, gate, producer, judge, result, findings) "
                                  "VALUES (?, 0, 'G0-timers', 'turn.timers', 'turn.pipeline', 'warn', ?)", (f"aud_9{i}", json.dumps([f])))
    r = release.release_audit(cfg, run_id, days=1)
    assert r.unbuilt == ["A BARTER_DUE timer fired with nothing built to handle it.",
                         "Cascade rule CAS-099 needs a flood, which is not built."]
    assert not r.passed


def test_no_record_of_a_child_carries_the_words(rel):
    """REL-05 (CNT-11): the world's own dossiers are read again, generated and imported alike."""
    cfg, run_id, rd = rel
    term = sorted(MINOR_UNSAFE_TERMS)[0]
    did, bj = read(rd / "world.sqlite", "SELECT dossier_id, baseline_json FROM dossiers ORDER BY dossier_id")[0]
    b = json.loads(bj)
    b["identity"]["age"] = 12
    b["writers_notes"] = f"Scan probe word: {term}."
    edit(rd / "world.sqlite", "UPDATE dossiers SET baseline_json = ? WHERE dossier_id = ?", (json.dumps(b), did))
    r = release.release_audit(cfg, run_id, days=1)
    assert r.content == [f"{did}: a record for someone under 18 contains the word '{term}'."]
    assert not r.passed
