"""The story knows when the player is freezing or has nothing on (P7, the owner's F1c: DECISIONS D-86).
narration/narrator.py pc_state_lines (mind.packet COLD_LINES, BARE_LINES).

What the people who see it make of it is theirs (mind.temper TEMPER-09); the prose has to know it is
so. A shed at night (a dict scenario): the player, whose looks are recorded, and nothing else.
"""

from __future__ import annotations

import copy

import pytest

from as_engine.contracts.dossier import OutfitPiece
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.mind.packet import BARE_LINES, COLD_LINES
from as_engine.narration.narrator import build_narrator_packet
from as_engine.physical import objects
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(7)

LOOKS = {"hair_colour": "brown", "hair_length": "short", "eye_colour": "grey", "complexion": "pale skin",
         "outfit": [{"item": "core:item/t_shirt"}, {"item": "core:item/jeans"}]}

SHED = {
    "schema": "as.scenario.v1", "name": "night_shed", "seed": 9, "start": {"day": 400, "time": "22:00"},
    "places": [{"id": "shed", "name": "Shed", "width_m": 6, "depth_m": 4}],
    "bodies": [{"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "shed", "x": 3, "y": 2,
                "looks": LOOKS}],
}


@pytest.fixture
def shed(fixture_packs, core_pack_dir):
    worlds = []

    def _load():
        w = load_scenario(copy.deepcopy(SHED), packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        return w

    yield _load
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def state(w):
    with w.store.transaction() as tx:
        return build_narrator_packet(tx, w.id("pc"), 0, now(w), w.session().settings).pc_state_lines


def test_the_story_knows_the_player_has_nothing_on(shed):
    w = shed()
    assert BARE_LINES[0] in state(w)
    with w.store.transaction() as tx:
        objects.dress(tx, w.id("pc"), [OutfitPiece(item="core:item/jeans")], now(w), None, 0, "scenario")
    lines = state(w)
    assert BARE_LINES[1] in lines and BARE_LINES[0] not in lines
    with w.store.transaction() as tx:
        objects.dress(tx, w.id("pc"), [OutfitPiece(item="core:item/t_shirt")], now(w), None, 0, "scenario")
    lines = state(w)
    assert BARE_LINES[0] not in lines and BARE_LINES[1] not in lines


def test_the_story_knows_the_player_is_freezing(shed):
    w = shed()
    pc = w.id("pc")
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.NEED_STAGE, writer="physical.bodies", at=now(w), turn_index=0, target_ids=[pc],
                              writes=[WriteRecord(op=WriteOp.UPDATE, table="needs", key={"body_id": pc},
                                                  values={"chill": 20, "cold_stage": 5})],
                              payload={"body_id": pc, "need": "cold", "stage": 5, "chill": 20}))
    lines = state(w)
    assert COLD_LINES[5] in lines
    assert lines.index(COLD_LINES[5]) < lines.index(BARE_LINES[0]), "the cold first, then what they have on"
