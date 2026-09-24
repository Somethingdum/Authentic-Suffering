"""The player starts in their own clothes (P10, the owner's F1a). Rules LOOK-01, LOOK-02
(world/worldgen/opening.py step 2; physical/bodies.py create looks; physical/objects.py dress).

The generated world is Owen Marsh's (conftest): he starts with his face on record and dressed in
his dossier's outfit, and his gear on top of it, not a second jacket.
"""

from __future__ import annotations

import pytest

from as_engine.physical import bodies, objects

pytestmark = pytest.mark.phase(10)


def test_the_player_starts_in_their_own_clothes(gw, canon):
    pc = gw.pc_id
    looks = canon.get("core:pc/owen_marsh").appearance.looks
    assert bodies.looks_of(gw.store, pc) == looks.model_copy(update={"outfit": []})
    worn = objects.worn(gw.store, pc)
    assert [r["def_ref"] for r in worn if r["clothing"]] == [
        "core:item/work_jacket", "core:item/t_shirt", "core:item/jeans", "core:item/boots"]
    [shirt] = [r for r in worn if r["def_ref"] == "core:item/t_shirt"]
    assert (shirt["colour"], shirt["insignia"]) == ("gray", "a volunteer fire department crest, washed gray")
    assert [r["def_ref"] for r in worn if not r["clothing"]] == ["core:item/hiking_pack"]
    assert objects.coverage(gw.store, pc) >= {"torso", "arms", "groin", "legs", "feet"}
    assert gw.store.query_one("SELECT origin FROM items WHERE item_id = ?", (worn[0]["item_id"],))[0] == "worldgen"
