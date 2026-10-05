"""What they call them (D-160). Rule LOOK-07 (mind/perception.py called, thing_ref, describe); LORE-03
(mind/retrieval.py lore_lines); contracts/content.py LoreEntry.called; core lore shamblers / runners / crawlers.

The dead were always 'a shambling figure' or 'a fast figure', to everyone, for ever — "what a thing is has to be
learned" — and nothing ever taught it, though everyone in the world says "watch the walkers" and "keep a runner
chasing". And the dead carry no content ref, so what people say about them never came to mind on seeing one. Now
someone who holds that lore sees a walker, and what everyone says about walkers comes to mind.
"""

from __future__ import annotations

import pytest

from as_engine.mind import perception
from as_engine.mind.retrieval import lore_lines

pytestmark = pytest.mark.phase(3)


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def test_owen_sees_a_walker(scenario):
    w = scenario("two_skills")
    t = now(w)
    with w.store.transaction() as tx:
        assert perception.thing_ref(tx, w.id("shambler")) == "core:infected/ZOMBIE_ARCHETYPE_SHAMBLER01"
        assert perception.describe(tx, w.id("pc"), w.id("shambler")) == "walker"
        perception.compile_scene(tx, w.id("pc"), t + 100, 0)
        texts = [r[0] for r in tx.query("SELECT text FROM percept_log WHERE holder_id = ? AND source_id = ?",
                                        (w.id("pc"), w.id("shambler")))]
        assert texts and all("walker" in x and "shambling" not in x for x in texts), texts
        said = [x["text"] for x in lore_lines(tx, w.id("pc"), 0, t + 100, 5)]
    assert any(x.startswith("Noise brings them") or "both hands on you" in x or "smell you" in x or "muck" in x for x in said), \
        "seeing one brings to mind what everyone says about them"


def test_someone_never_told(scenario):
    w = scenario("two_skills")
    w.store.conn.execute("DELETE FROM lore_held WHERE holder_id = ?", (w.id("pc"),))
    with w.store.transaction() as tx:
        assert perception.called(tx, w.id("pc"), w.id("shambler")) is None
        assert perception.describe(tx, w.id("pc"), w.id("shambler")) == "shambling figure"
