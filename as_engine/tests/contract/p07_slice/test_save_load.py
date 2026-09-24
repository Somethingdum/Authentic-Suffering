"""The run library: create from a scenario, autosave, save, load, list, delete (P7). Rules RUN-01..06,
RUN-10, STYLE-03, L8 (service/runs.py).

Save and reload preserve subjective history exactly — including the beliefs that are wrong. A
reloaded run is the same world: same state hash, same minds, same narrator.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from as_engine.contracts.settings import EngineConfig, RunSettings
from as_engine.kernel.hashing import world_state_hash
from as_engine.service import runs
from slice_kit import play, script_night_at_delgados

pytestmark = pytest.mark.phase(7)

TESTS = Path(__file__).resolve().parents[2]
SCENARIOS = TESTS / "fixtures" / "scenarios"
PACKS = TESTS / "fixtures" / "packs"
CORE = TESTS.parent.parent / "as_content" / "packs" / "core"


@pytest.fixture
def cfg(tmp_path):
    return EngineConfig(runs_dir=str(tmp_path / "runs"))


def new_run(cfg, fake, name="metal_fence", **kw):
    return runs.create_run_from_scenario(cfg, SCENARIOS / f"{name}.yaml", fake, packs_root=PACKS, core_pack_dir=CORE, **kw)


@pytest.fixture
def ids(scenario):
    """Fixture-local ids -> real ids (minting is deterministic, so a loaded copy of the fixture has the same ones)."""
    w = scenario("metal_fence")
    return SimpleNamespace(id=w.id, local=w.local, ids=w.ids)


def beliefs(store, holder):
    return [dict(r) for r in store.query(
        "SELECT h.claim_id, h.believed, h.confidence, h.provenance, h.fidelity, h.superseded_by, p.text "
        "FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id WHERE h.holder_id = ? ORDER BY h.claim_id", (holder,))]


def test_a_run_is_created_from_a_scenario(cfg, fake):
    """RUN-01: <runs_dir>/<run_id>/ with world.sqlite, turn0.sqlite (turn 0, for re-simulation) and manifest.json."""
    s = new_run(cfg, fake)
    rd = Path(cfg.runs_dir) / s.run_id
    assert s.run_id == "owen_marsh_71a", "slug(PC name) + '_' + seed in hex (1818)"
    for f in ("world.sqlite", "turn0.sqlite", "manifest.json"):
        assert (rd / f).exists()
    m = json.loads((rd / "manifest.json").read_text(encoding="utf-8"))
    assert (m["run_id"], m["pc_name"], m["day"], m["alive"], m["ironman"], m["turn_index"]) == (s.run_id, "Owen Marsh", 18, True, False, 0)
    assert m["world_state_hash"] == world_state_hash(s.store)
    again = new_run(cfg, fake)
    assert again.run_id == "owen_marsh_71a_2", "a taken id gets a counter"


def test_false_belief_survives_reload(cfg, fake, ids):
    """Pivot / RUN-05: wrong beliefs, memories and the narrator's texture survive save and reload exactly."""
    s = new_run(cfg, fake)
    script_night_at_delgados(ids, fake)
    out = play(s, "do", "I watch the front window and keep quiet.")
    assert out.ok
    rd = Path(cfg.runs_dir) / s.run_id
    assert (rd / "autosave" / "auto_1.sqlite").exists(), "stage 19 autosaved into the ring"
    mara, nita = ids.id("mara"), ids.id("nita")
    before = {"mara": beliefs(s.store, mara), "nita": beliefs(s.store, nita),
              "episodes": [tuple(r) for r in s.store.query("SELECT * FROM episodes ORDER BY episode_id")],
              "style": s.store.query_one("SELECT style_json FROM narrator_state")[0], "hash": world_state_hash(s.store)}
    assert any(b["text"] == "Nita walks the alley at eleven; it's clear." and b["believed"] == 1 for b in before["mara"]), \
        "Mara still believes the alley is clear — it is not"
    assert any(b["text"] == "The thin man ran because June shouted." for b in before["nita"])
    path = runs.save_run(s, "Before the back door")
    assert path.name == "before_the_back_door.sqlite"
    meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["turn_index"] == 1 and meta["sha256"] == runs.sha256_file(path)
    s.store.close()
    s2 = runs.load_run(cfg, s.run_id, fake)
    assert (s2.pc_id, s2.run_id, s2.settings) == (s.pc_id, s.run_id, s.settings)
    assert s2.extras.get("notices", []) == []
    assert beliefs(s2.store, mara) == before["mara"] and beliefs(s2.store, nita) == before["nita"]
    assert [tuple(r) for r in s2.store.query("SELECT * FROM episodes ORDER BY episode_id")] == before["episodes"]
    assert s2.store.query_one("SELECT style_json FROM narrator_state")[0] == before["style"], "STYLE-03"
    assert world_state_hash(s2.store) == before["hash"]
    hits = [r[0] for r in s2.store.query("SELECT rowid FROM episodes_fts WHERE episodes_fts MATCH 'shouted'")]
    assert len(hits) == 1, "the memory index is rebuilt on load"
    assert play(s2, "do", "I watch the front window.").ok
    s2.store.close()
    s3 = runs.load_run(cfg, s.run_id, fake, save_slot="Before the back door")
    assert s3.store.query_one("SELECT turn_index FROM world_clock")[0] == 1, "loading a save goes back to it"
    assert world_state_hash(s3.store) == before["hash"]
    s3.store.close()


def test_ironman_and_the_library(cfg, fake):
    """RUN-04 (no named saves in Ironman), RUN-06 (hard delete), list_runs."""
    s = new_run(cfg, fake, settings=RunSettings(save_mode="ironman"))
    with pytest.raises(runs.RunError) as e:
        runs.save_run(s, "cheat")
    assert e.value.code == "ironman"
    (row,) = runs.list_runs(cfg)
    assert (row.run_id, row.pc_name, row.ironman, row.alive, row.day) == (s.run_id, "Owen Marsh", True, True, 18)
    s.store.close()
    runs.delete_run(cfg, s.run_id)
    assert runs.list_runs(cfg) == [] and not (Path(cfg.runs_dir) / s.run_id).exists()
    with pytest.raises(runs.RunError) as e:
        runs.load_run(cfg, s.run_id, fake)
    assert e.value.code == "not_found"


def test_content_drift_refuses_the_load(cfg, fake, tmp_path):
    """RUN-10: every content ref the run uses must still resolve; the refusal lists them plainly."""
    s = new_run(cfg, fake)
    rid = s.run_id
    s.store.close()
    empty = tmp_path / "empty_pack"
    empty.mkdir()
    (empty / "pack.yaml").write_text("schema: as.pack.v1\nid: empty\nname: Empty\nversion: 0.1.0\ndescription: nothing at all\n", encoding="utf-8")
    with pytest.raises(runs.RunError) as e:
        runs.load_run(cfg, rid, fake, pack_dirs=[empty])
    assert e.value.code == "content_missing"
    assert "Your run uses 'core:item/glock_19', which is no longer in any pack." in e.value.message.splitlines()


def test_the_autosave_ring(cfg, fake):
    """RUN-02: auto_<turn % ring>.sqlite, each with its own manifest."""
    s = new_run(cfg, fake, settings=RunSettings(autosave_ring=2))
    for _ in range(3):
        assert play(s, "do", "I watch.").ok
    ad = Path(cfg.runs_dir) / s.run_id / "autosave"
    assert sorted(p.name for p in ad.glob("*.sqlite")) == ["auto_0.sqlite", "auto_1.sqlite"]
    assert json.loads((ad / "auto_1.json").read_text(encoding="utf-8"))["turn_index"] == 3
    assert json.loads((ad / "auto_0.json").read_text(encoding="utf-8"))["turn_index"] == 2
    m = json.loads((Path(cfg.runs_dir) / s.run_id / "manifest.json").read_text(encoding="utf-8"))
    assert m["turn_index"] == 3 and m["world_state_hash"] == world_state_hash(s.store)
    s.store.close()
