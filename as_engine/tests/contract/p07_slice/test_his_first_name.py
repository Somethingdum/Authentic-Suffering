"""His first name (D-264). narration/narrator.py build_narrator_packet allowed_names; narration/lint.py DISC-NAME.

The player's character knows most of the people of a generated world by their full names — "Marcus Castillo" — and the
Writer, told it may use that name, wrote "Marcus" the second time, as anyone would; the lint rejected it as a name he
never learned (every display name's first word is a name somebody could write) and the turn's prose went back for a
repair — the slowest call of the turn, spent on nothing. A man known by his full name is called by his first; a
surname he never heard is still not his to use.
"""

from __future__ import annotations

import pytest

from as_engine.mind import perception
from as_engine.narration import lint
from as_engine.narration.narrator import build_narrator_packet, known_names
from as_engine.physical import space

pytestmark = pytest.mark.phase(7)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def owen_looks(w, known_as):
    t = now(w)
    w.store.conn.execute("UPDATE acquaintance SET known_name=? WHERE holder_id=? AND subject_id=?",
                         (known_as, w.id("pc"), w.id("mara")))
    w.store.conn.commit()
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 1)
        perception.compile_scene(tx, w.id("pc"), t + 100, 1)
        names = known_names(tx)
        return build_narrator_packet(tx, w.id("pc"), 1, t, w.session().settings), names


def disc(text, k, names, canon):
    from as_engine.contracts.settings import RulesConfig
    rep = lint.lint_prose(text, k, canon.find("style", "narration"), RulesConfig().style, names)
    return [f.detail for f in rep.findings if f.rule == "DISC-NAME"]


def test_known_by_her_full_name(scenario, canon):
    w = scenario("metal_fence")
    k, names = owen_looks(w, "Mara Voss")
    assert {"Mara Voss", "Mara"} <= set(k.allowed_names)
    assert disc("Mara Voss looks up from the window. Mara says nothing.", k, names, canon) == []


def test_a_surname_he_never_heard(scenario, canon):
    w = scenario("metal_fence")
    k, names = owen_looks(w, "Mara")
    assert "Mara" in k.allowed_names and "Mara Voss" not in k.allowed_names
    assert disc("Mara Voss looks up from the window.", k, names, canon) == ["Mara Voss"]
    assert "Nita" not in k.allowed_names, "nobody he does not perceive this turn"
