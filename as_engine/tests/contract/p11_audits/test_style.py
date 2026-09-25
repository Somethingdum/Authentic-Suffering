"""The narrator does not paint the same picture twice (P11). Rules NARR-09, STYLE-03
(narration/style.py; turn/pipeline.py S17).

After each turn the narrator's own 'adjective noun' pictures go into its continuity state; the
next narration prompt names them as already used. The state is a world table: it is saved with
the run and a reload keeps it (STYLE-03, p07 test_save_load).
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import CallClass
from as_engine.contracts.narration import NarratorLine, NarratorPacket, NarratorStyle
from as_engine.narration import style
from slice_kit import play, script_night_at_delgados

pytestmark = pytest.mark.phase(11)

PROSE = ("Owen kept still by the rusted gate. A thin wind came through the broken window, and the cold air "
         "smelled of wet ash.")


def test_images_are_the_narrators_own_pictures():
    assert style.images('The rusted gate hung open. "The old dog," she said. A thin wind came through the broken '
                        'window.') == ["rusted gate", "thin wind", "broken window"], "quoted speech is the Actor's"
    assert style.images("The heavy door swung shut on its rusted hinges, by the heavy door.") == ["heavy door", "rusted hinges"]
    assert style.images("The cold, dark night. A Rusted Gate. The Delgado house.") == [], \
        "a comma breaks the run; a capital is a name"
    assert style.images("The enemy fired. The children ran. Mara turned toward the door.") == [], "verbs are not nouns"
    assert style.images("") == []


def test_the_last_thirty_are_kept_and_a_reused_one_moves_to_the_end():
    old = NarratorStyle(recently_used_images=[f"grey wall{i}" for i in range(29)] + ["rusted gate"])
    new = style.update_after_turn(old, PROSE, "talk")
    assert new.recently_used_images[-4:] == ["rusted gate", "thin wind", "broken window", "cold air"]
    assert len(new.recently_used_images) == 30 and new.recently_used_images[0] == "grey wall3"
    assert new.recent_scene_type == "talk"
    assert new.model_dump(exclude={"recently_used_images", "recent_scene_type"}) == \
        old.model_dump(exclude={"recently_used_images", "recent_scene_type"}), "nothing else changes"


@pytest.mark.parametrize("lines,establish,expected", [
    ([], True, "arrival"),
    ([NarratorLine(seconds=0, kind="speech", text="Mara says", speaker="Mara", words="Down.")], False, "talk"),
    ([NarratorLine(seconds=0, kind="outcome", text="Owen chose to wait.")], False, "action"),
    ([NarratorLine(seconds=0, kind="sound", text="A dog barks.")], False, "quiet"),
])
def test_the_scene_type(lines, establish, expected):
    pk = NarratorPacket(turn_index=1, world_time_text="t", place_text="p", pc_name="Owen", lines=lines,
                        establish_place=establish)
    assert style.scene_type(pk) == expected


def test_a_played_turn_remembers_its_pictures_and_the_next_prompt_names_them(scenario, fake):
    w = scenario("metal_fence")
    script_night_at_delgados(w, fake)
    fake.script(CallClass.NARRATION, PROSE)
    s = w.session()
    play(s, "do", "I watch the front window and keep quiet.")
    assert w.store.query_one("SELECT text FROM narration WHERE turn_index = 1")[0] == PROSE
    with w.store.transaction() as tx:
        st = style.load(tx)
    assert st.recently_used_images == ["rusted gate", "thin wind", "broken window", "cold air"]
    first = fake.calls(CallClass.NARRATION)[0].context
    assert st.recent_scene_type == style.scene_type(first)
    ev = w.store.query("SELECT writer, payload FROM events WHERE type = 'SETTINGS_CHANGE' AND turn_index = 1")
    assert [tuple(r) for r in ev] == [("narration.narrator", '{"source":"narrator_state"}')]
    play(s, "do", "I keep watching the front window.")
    second = fake.calls(CallClass.NARRATION)[-1]
    assert second.context.style.recently_used_images[:4] == ["rusted gate", "thin wind", "broken window", "cold air"]
    assert "Images already used recently (do not reuse): rusted gate; thin wind; broken window; cold air" in \
        second.messages[-1].content


def test_nothing_new_writes_nothing(scenario):
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        st = style.load(tx)
        assert style.save(tx, st, 0) is None
        ev = style.save(tx, style.update_after_turn(st, PROSE, st.recent_scene_type), 0)
        assert ev is not None and style.load(tx).recently_used_images == ["rusted gate", "thin wind", "broken window", "cold air"]
