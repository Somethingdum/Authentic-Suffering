"""What an animal looks like, and what being eaten looks like (P3, the owner's I1).
mind/perception.py describe (animals: the AnimalDef's words) and the HARM wording for a bite.

A barn (a dict scenario): the player, a dog and a horse. What the player sees of an animal is what
it is; what he sees of a bite is what it is — the narrator does the rest (narration.system.j2).
"""

from __future__ import annotations

import pytest

from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import bodies
from as_engine.physical.bodies import WoundSpec
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(3)

BARN = {
    "schema": "as.scenario.v1", "name": "barn", "seed": 6, "start": {"day": 300, "time": "12:00"},
    "places": [{"id": "barn", "name": "Barn", "material": "wood", "light": 3, "width_m": 12, "depth_m": 8}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "barn", "x": 2, "y": 4},
        {"id": "rex", "animal": "core:animal/dog", "place": "barn", "x": 3, "y": 4},
        {"id": "cal", "stub": {"name": "Cal Hobbs", "age": 30, "sex": "male"}, "place": "barn", "x": 4, "y": 4},
    ],
}


@pytest.fixture
def barn(fixture_packs, core_pack_dir):
    w = load_scenario(BARN, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
    yield w
    w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def seen(w, holder, at):
    with w.store.transaction() as tx:
        ids = perception.compile_scene(tx, w.id(holder), at, 0)
    return [w.store.query_one("SELECT text FROM percept_log WHERE percept_id = ?", (i,))[0] for i in ids]


def bite(w, who, at):
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=at, turn_index=0, payload={"what": "test"}))
        return bodies.apply_harm(tx, w.id(who), WoundSpec("arm_l", "bite", "significant", 2), at, c.event_id, 0, w.rng)[0]


def test_a_dog_is_a_dog(barn):
    w = barn
    with w.store.transaction() as tx:
        assert perception.describe(tx, w.id("pc"), w.id("rex")) == "scrawny grey dog"
    texts = seen(w, "pc", now(w))
    assert any(t.startswith("A scrawny grey dog stands") for t in texts), texts


def test_being_eaten_alive_is_called_what_it_is(barn):
    w = barn
    t = now(w)
    seen(w, "pc", t)
    h = bite(w, "cal", t + 1000)
    texts = seen(w, "pc", t + 1000)
    assert "A man is being eaten alive." in texts or any(x.endswith("is being eaten alive.") for x in texts), texts
    h2 = bite(w, "rex", t + 2000)
    texts = seen(w, "pc", t + 2000)
    assert any(x.startswith("A scrawny grey dog is being eaten alive") for x in texts), texts
    assert h.payload["type"] == h2.payload["type"] == "bite"


def test_the_dead_are_eaten_too(barn):
    w = barn
    t = now(w)
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=0, payload={"what": "test"}))
        bodies.die(tx, w.rng, w.id("cal"), t, c.event_id, 0, cause="test")
    bite(w, "cal", t + 1000)
    texts = seen(w, "pc", t + 1000)
    assert any(x.endswith("is being eaten.") for x in texts) and not any(x.endswith("eaten alive.") for x in texts), texts
