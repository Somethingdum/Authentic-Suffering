"""A New Life, through the protocol and the terminal (P10). GameService on_pcs_list, on_run_new,
on_worldgen_cancel (service/game_service.py; docs/as/10_UI.md §2.3-2.4) and new-run (cli.py
CLI-05).

Choosing a character shows plain cards, including the worlds their story fits. Building a world
runs in the background and ends on the Play screen — or, when that world cannot be made, back in
the wizard with a sentence saying why. Stopping it leaves nothing half-made behind.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest
from world_kit import FIXTURE_PACKS, REPO_PACKS, WORLD_PC

from as_engine.content.pack import load_canon
from as_engine.contracts.common import CallClass
from as_engine.contracts.protocol import OUT_MODELS
from as_engine.contracts.settings import EngineConfig
from as_engine.service import game_service
from as_engine.testing.fake_lm import FakeTransport
from as_engine.world.worldgen import atlas, tables

pytestmark = pytest.mark.phase(10)

SMALL = {"world_detail": "gotta_go_to_work_soon", "seed": 7, "era": "established"}
BAR = ("progress_plan", "progress", "progress_done")


# --------------------------------------------------------------------------- helpers
class Held(FakeTransport):
    """A model that never answers the first history call (worldgen waits there until stopped)."""

    def __init__(self):
        super().__init__()
        self.reached = asyncio.Event()

    async def send(self, lane, request):
        if request.call_class == CallClass.WORLDGEN_HISTORY:
            self.reached.set()
            await asyncio.Event().wait()
        return await super().send(lane, request)


def service(cfg, tmp_path, fake=None):
    svc = game_service.GameService(cfg, fake or FakeTransport(), config_path=str(tmp_path / "as_config.yaml"))
    pushed = []

    async def collect(msg):
        OUT_MODELS[msg["action"]] and OUT_MODELS[msg["action"]].model_validate(msg["data"])
        pushed.append(msg)
    svc.subscribe(collect)
    return svc, pushed


async def send(svc, action, **fields):
    replies = await svc.handle({"type": "as_game", "action": action, **fields})
    for r in replies:
        OUT_MODELS[r["action"]] and OUT_MODELS[r["action"]].model_validate(r["data"])
    return replies


def acts(msgs, bar=False):
    return [m["action"] for m in msgs if bar or m["action"] not in BAR]


def only(msgs, action):
    [d] = [m["data"] for m in msgs if m["action"] == action]
    return d


async def finished(svc):
    t = svc.worldgen_task
    if t is not None:
        await asyncio.wait({t})


def close(svc):
    if svc.session is not None:
        svc.session.store.close()


def leftovers(cfg) -> list[str]:
    root = Path(cfg.runs_dir)
    return [] if not root.exists() else sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_dir()
                                               and p.name != "_worlds")


@pytest.fixture
def hopeless_cfg(tmp_path):
    content = tmp_path / "content"
    shutil.copytree(REPO_PACKS / "core", content / "core")
    shutil.copytree(FIXTURE_PACKS / "p10_hopeless", content / "p10_hopeless")
    return EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(content))


# =========================================================================== the cards
def test_the_cards_say_who_each_character_is(run_cfg, tmp_path):
    """on_pcs_list: one card per playable character in every pack folder (core first), in the
    CMG §61 words — and, for a character whose story needs a certain world, the years it needs.
    (P12, D-102: the cheat_ folders stay out of the list until the code is entered, CHEAT-12.)"""
    svc, _pushed = service(run_cfg, tmp_path)
    [msg] = asyncio.run(send(svc, "pcs_list"))
    assert msg["action"] == "pcs"
    folders = [REPO_PACKS / "core"] + sorted(p for p in REPO_PACKS.iterdir() if p.is_dir() and p.name != "core"
                                             and not p.name.startswith("cheat_"))
    canon, _issues = load_canon(folders)
    refs = sorted(canon.refs("pc"))
    cards = msg["data"]["cards"]
    assert [c["ref"] for c in cards] == refs and refs
    for c in cards:
        rec = canon.get(c["ref"])
        assert (c["display_name"], c["one_line_identity"], c["survives_by"], c["note"], c["source"], c["warnings"]) == (
            rec.card.display_name, rec.card.one_line_identity, rec.card.pc_card_survival, rec.card.pc_selection_note,
            "pack", [])
        assert c["starts_as"] == tables.STARTS_AS[rec.faction_start_type]
        r = rec.days_since_fall_range
        if r is None:
            assert (c["world_age_days"], c["world_age_note"]) == (None, None)
        else:
            first = rec.card.display_name.split()[0]
            assert c["world_age_days"] == [r[0], r[1]]
            assert c["world_age_note"] == f"{first}'s story needs a world {r[0] // 365}-{r[1] // 365} years after the Fall."
    assert any(c["world_age_days"] for c in cards), "Ruth Castillo's story needs its years"


# =========================================================================== building a world
def test_a_new_life_opens_on_the_play_screen(run_cfg, tmp_path):
    """on_run_new: the reply is the worldgen screen, busy; the world is built in the background
    (worldgen_progress for every stage); then the run opens exactly as a loaded one does."""
    svc, pushed = service(run_cfg, tmp_path)

    async def go():
        r = await send(svc, "run_new", pc_ref=WORLD_PC, settings=SMALL)
        assert r == [{"type": "as_game", "action": "state", "data": {"screen": "worldgen", "run_id": None, "busy": True}}]
        await finished(svc)
    try:
        asyncio.run(go())
        a = acts(pushed)
        stages = [m["data"]["stage"] for m in pushed if m["action"] == "worldgen_progress"]
        assert [s for k, s in enumerate(stages) if k == 0 or stages[k - 1] != s] == list(atlas.STAGES)
        assert a[-4:] == ["run_loaded", "view", "story", "state"]
        loaded = only(pushed, "run_loaded")
        assert (loaded["run_id"], loaded["pc_name"], loaded["ironman"], loaded["sandbox"]) == ("owen_marsh_7", "Owen Marsh",
                                                                                              False, False)
        assert pushed[-1]["data"] == {"screen": "play", "run_id": "owen_marsh_7", "busy": False}
        assert svc.worldgen_task is None and svc.session.run_id == "owen_marsh_7"
    finally:
        close(svc)


def test_a_generated_world_plays(made_world, world_cfg, tmp_path):
    """The first moves in a generated world, through the service and the whole turn pipeline with
    its 58-bit gate. Three of the dead are sent from a building up the street: the player's watch
    ends when they come near (REACT-01, not after eight hours), and the next move is made with them
    at hand. (Playing exactly this found four faults: a reaction shown a percept from after its own
    moment — SKULL-10 —, a watch the dead walking up did not end, a street whose buildings all met
    at one point, and a dice receipt that could not name a defence.)"""
    import json

    from world_kit import now

    from as_engine.world import infected
    svc, pushed = service(world_cfg, tmp_path)
    WATCH = "Stay put and watch everything you can see and hear."

    async def go():
        await send(svc, "run_load", run_id=made_world.run_id)
        s = svc.session
        me = s.store.meta("pc_actor_id")
        here = s.store.query_one("SELECT place_id FROM positions WHERE body_id = ?", (me,))[0]
        zone = s.store.query_one("SELECT zone_id FROM places WHERE place_id = ?", (here,))[0]
        site = s.store.query_one("SELECT place_id FROM places WHERE zone_id = ? AND kind = 'building' AND parent_id IS NULL "
                                 "AND place_id != ? ORDER BY place_id", (zone, here))[0]
        with s.store.transaction() as tx:
            t = now(s)
            for _ in range(3):
                b = infected.spawn(tx, s.rng, site, infected.SHAMBLER, t, 0, None)
                infected.attract(tx, b, here, t, None, 0, reason="noise")
        marks = [now(s)]
        turns = []
        for _ in range(2):
            start = len(pushed)
            await send(svc, "turn_submit", mode="do", text=WATCH)
            await svc.idle()
            turns.append(pushed[start:])
            marks.append(now(s))
        return me, marks, turns
    try:
        me, marks, turns = asyncio.run(go())
        s = svc.session
        for msgs in turns:
            assert "turn_result" in acts(msgs) and not {"error", "turn_rejected"} & set(acts(msgs)), acts(msgs)
        gates = [json.loads(r[0])["gate"] for r in s.store.query("SELECT detail FROM turn_ledger WHERE stage = 12 "
                                                                "ORDER BY turn_index")]
        assert gates == ["all 58", "all 58"]
        assert marks[1] - marks[0] < 10 * 60_000, "the dead coming near ended the watch long before eight hours"
        came = s.store.query_one("SELECT COUNT(*) FROM percept_log p JOIN events e ON e.event_id = p.event_id "
                                 "JOIN bodies b ON b.body_id = e.actor_id WHERE p.holder_id = ? AND p.turn_index = 1 "
                                 "AND e.type = 'MOVE' AND b.kind = 'infected' AND p.channel = 'visual'", (me,))[0]
        assert came, "the player saw them come"
        for msgs in turns:
            labels = [x["label"] for x in only(msgs, "turn_result")["view"]["suggestions"]]
            assert len(labels) == len(set(labels)), f"three of the dead read alike; one chip each: {labels}"
    finally:
        close(svc)


def test_the_wizard_hears_why_a_world_cannot_be_made(run_cfg, hopeless_cfg, tmp_path):
    """on_run_new: an unknown character (RunError), settings the world cannot honour
    (SettingsError -> bad_settings) and a start nobody could survive (WorldgenAborted) each end
    with the plain sentence and the wizard again — and nothing left on disk."""
    cases = [
        (run_cfg, {"pc_ref": "core:pc/nobody", "settings": SMALL},
         ("not_found", "There is no character called core:pc/nobody.")),
        (run_cfg, {"pc_ref": "core:pc/ruth_castillo", "settings": SMALL | {"era": "early"}},
         ("bad_settings", "Ruth Castillo's age and history need a world 1-10 years after the Fall.")),
        (hopeless_cfg, {"pc_ref": "p10_hopeless:pc/hopeless_hal",
                        "settings": SMALL | {"difficulty": "normal", "pack_ids": ["core", "p10_hopeless"]}},
         ("worldgen_aborted", "Hal Brandt cannot survive the start this world gives them at Normal. Try one "
                              "difficulty lower, another character, or another era.")),
    ]
    for k, (cfg, fields, (code, message)) in enumerate(cases):
        svc, pushed = service(cfg, tmp_path / str(k))

        async def go(svc, fields):
            await send(svc, "run_new", **fields)
            await finished(svc)
        asyncio.run(go(svc, fields))
        assert acts(pushed)[-2:] == ["error", "state"], code
        assert only(pushed, "error") == {"code": code, "message": message, "recoverable": True}
        assert pushed[-1]["data"] == {"screen": "wizard", "run_id": None, "busy": False}
        assert "run_loaded" not in acts(pushed) and svc.session is None
        assert leftovers(cfg) == []


def test_one_world_at_a_time_and_saved_worlds_later(run_cfg, tmp_path):
    """on_run_new: while a world is being built another New Life is refused (busy); starting in a
    saved world arrives with P12 (not_built_yet); the character cards still answer meanwhile."""
    fake = Held()
    svc, _pushed = service(run_cfg, tmp_path, fake)

    async def go():
        await send(svc, "run_new", pc_ref=WORLD_PC, settings=SMALL)
        await asyncio.wait_for(fake.reached.wait(), 60)
        busy = await send(svc, "run_new", pc_ref=WORLD_PC, settings=SMALL)
        cards = await send(svc, "pcs_list")
        await send(svc, "worldgen_cancel")
        later = await send(svc, "run_new", pc_ref=WORLD_PC, settings=SMALL, world_id="w_7")
        return busy, cards, later
    busy, cards, later = asyncio.run(go())
    assert only(busy, "error") == {"code": "busy", "message": game_service.BUSY, "recoverable": True}
    assert acts(cards) == ["pcs"]
    assert only(later, "error") == {"code": "not_built_yet", "message": game_service.NOT_BUILT, "recoverable": True}


def test_stopping_a_world_leaves_nothing(run_cfg, tmp_path):
    """on_worldgen_cancel: nothing being built -> nothing_to_cancel; otherwise the job is stopped,
    the answer is the wizard, and no folder of the half-made run or world is left."""
    fake = Held()
    svc, pushed = service(run_cfg, tmp_path, fake)

    async def go():
        none = await send(svc, "worldgen_cancel")
        await send(svc, "run_new", pc_ref=WORLD_PC, settings=SMALL)
        await asyncio.wait_for(fake.reached.wait(), 60)
        assert (Path(run_cfg.runs_dir) / "owen_marsh_7").exists()
        stopped = await send(svc, "worldgen_cancel")
        return none, stopped
    none, stopped = asyncio.run(go())
    assert only(none, "error") == {"code": "nothing_to_cancel", "message": game_service.NO_WORLDGEN, "recoverable": True}
    assert stopped == [{"type": "as_game", "action": "state", "data": {"screen": "wizard", "run_id": None, "busy": False}}]
    assert svc.worldgen_task is None and svc.session is None
    assert not {"error", "state", "run_loaded"} & set(acts(pushed)[acts(pushed).index("worldgen_progress"):])
    assert leftovers(run_cfg) == [] and not (Path(run_cfg.runs_dir) / "_worlds" / "w_7").exists()


# =========================================================================== CLI-05
@pytest.fixture
def conf(tmp_path):
    def make(content=REPO_PACKS):
        p = tmp_path / "as_config.yaml"
        p.write_text(f"schema: as.config.v1\nruns_dir: {(tmp_path / 'runs').as_posix()}\n"
                     f"content_dir: {Path(content).as_posix()}\n", encoding="utf-8")
        return str(p)
    return make


def test_the_terminal_makes_a_world(conf, capsys):
    """CLI-05: every progress call printed ("NN% label", with the answers counted where a stage
    waits on the model), then where the run is; exit 0."""
    from as_engine.cli import main
    assert main(["--config", conf(), "new-run", WORLD_PC, "--detail", "gotta_go_to_work_soon", "--era", "established",
                 "--seed", "7", "--fake"]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out[0] == f"0% {atlas.STAGE_LABELS['WG0']}"
    assert out[-1].startswith("Created run owen_marsh_7 in ")
    dossiers = [line for line in out if line.endswith("/3)") and atlas.STAGE_LABELS["WG6"] in line]
    assert [line.rsplit(" (", 1)[1] for line in dossiers] == ["1/3)", "2/3)", "3/3)"]
    assert out[-2] == f"100% {atlas.STAGE_LABELS['COMMIT']}"


def test_the_terminal_says_why_not(conf, capsys, monkeypatch):
    """CLI-05: settings RunSettings refuses, an unknown character, a world the character cannot live
    in and a world that could not be made each print one bracketed line and exit 1; a wrong word is
    argparse's usage error."""
    from as_engine.cli import main
    from as_engine.world.worldgen import region
    from as_engine.world.worldgen.pipeline import WorldgenAssertion
    assert main(["--config", conf(), "new-run", WORLD_PC, "--days", "0", "--fake"]) == 1
    assert capsys.readouterr().out.startswith("[bad_settings] ")
    assert main(["--config", conf(), "new-run", "core:pc/nobody", "--detail", "gotta_go_to_work_soon", "--fake"]) == 1
    assert capsys.readouterr().out.strip().splitlines()[-1] == "[not_found] There is no character called core:pc/nobody."
    assert main(["--config", conf(), "new-run", "core:pc/ruth_castillo", "--era", "early", "--fake"]) == 1
    assert capsys.readouterr().out.strip().splitlines()[-1] == (
        "[bad_settings] Ruth Castillo's age and history need a world 1-10 years after the Fall.")
    def broken(store, reg):
        raise WorldgenAssertion("WG1", "a test broke the region")
    monkeypatch.setattr(region, "assert_region", broken)
    assert main(["--config", conf(), "new-run", WORLD_PC, "--detail", "gotta_go_to_work_soon", "--fake"]) == 1
    assert capsys.readouterr().out.strip().splitlines()[-1] == (
        f"[stage_failed] {atlas.STAGE_LABELS['WG1']} failed twice: a test broke the region")
    with pytest.raises(SystemExit) as e:
        main(["--config", conf(), "new-run", WORLD_PC, "--era", "medieval", "--fake"])
    assert e.value.code == 2
