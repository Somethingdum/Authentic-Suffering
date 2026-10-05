"""Names called (D-192). Rule TEMPER-03 'insulted' (mind/temper.py INSULT_WORDS).

The player called Mara a whore, told June to go to hell and Eli he was a waste of space, and nobody's temper
moved: the list of what wounds held nineteen words and phrases, and none of those. Now the common names people are
called and the things said to hurt are on it — and ordinary words that only sound like them are not.
"""

from __future__ import annotations

import pytest

from as_engine.mind.temper import INSULT_WORDS, _words_have

pytestmark = pytest.mark.phase(5)


def wounds(words):
    return any(_words_have(words, x) for x in INSULT_WORDS)


@pytest.mark.parametrize("words", [
    "You're a whore, Mara.", "Go to hell, June.", "Eli, you're a waste of space.", "Drop dead.", "You scum.",
    "Listen to me, you halfwit.", "Piss off.", "Nobody wants you here.", "You disgust me.", "Shut your mouth, you maggot.",
    "You motherfucker.", "Son of a bitch.", "You're nothing.", "You\u2019re nothing.",
])
def test_said_to_wound(words):
    assert wounds(words), words


@pytest.mark.parametrize("words", [
    "Take the garbage out back.", "The water's filthy.", "Drop the bag.", "Go to the hall.", "That was dumb luck.",
    "Kill the light.", "Is anybody there?", "A scummy film on the water.", "Don't fool around.", "Vermin got into the stores.",
])
def test_ordinary_words_are_not(words):
    assert not wounds(words), words


@pytest.mark.parametrize("gesture, wounds_her", [("spit_at", True), ("the_finger", True), ("point_at", False)])
def test_contempt_without_a_word(scenario, gesture, wounds_her):
    """D-204: spitting at someone's feet, or giving them the finger, is an insult (TEMPER-03); pointing is not."""
    from as_engine.action.effects import GESTURES
    from as_engine.contracts.events import Event, EventType
    from as_engine.mind import perception, temper
    from as_engine.physical import space
    w = scenario("metal_fence")
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        for who, x in (("pc", 5.0), ("june", 6.5)):
            tx.commit_event(space.move_event(tx, w.id(who), w.id("sales_floor"), None, x, 4.0, t, None, 0))
        ev = tx.commit_event(Event(type=EventType.GESTURE, writer="action.propagate", at=t + 100, turn_index=0, actor_id=w.id("pc"),
                                   payload={"actor_id": w.id("pc"), "gesture": gesture, "target_id": w.id("june")}))
        perception.compile_aftermath(tx, w.id("june"), [ev], t + 200, 0)
        seen = tx.query_one("SELECT text FROM percept_log WHERE holder_id = ? AND event_id = ?", (w.id("june"), ev.event_id))
        got = [(p.kind, p.event_id) for p in temper.provocations(tx, w.id("june"), 0, t + 200)]
    assert seen is not None and "you" in seen[0] and "you's" not in seen[0], seen
    assert (("insulted", ev.event_id) in got) is wounds_her, got
    assert gesture in GESTURES
    if gesture == "spit_at":
        assert seen[0] == "Owen spits at your feet.", seen

@pytest.mark.parametrize("audience", [True, False])
def test_shamed_in_front_of_others(scenario, audience):
    """D-204 (CAS-079): given the finger with Mara watching, June is worn down and resents Owen; with nobody else
    there it is only an insult (TEMPER-03)."""
    from as_engine.action import cascade
    from as_engine.contracts.events import Event, EventType
    from as_engine.mind import perception
    from as_engine.physical import space
    w = scenario("metal_fence")
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    there = ("pc", "june", "mara") if audience else ("pc", "june")
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", t, None, 0)
        for who, x in zip(there, (5.0, 6.5, 8.0)):
            tx.commit_event(space.move_event(tx, w.id(who), w.id("sales_floor"), None, x, 4.0, t, None, 0))
        if not audience:
            tx.commit_event(space.move_event(tx, w.id("mara"), w.id("office"), None, 2.0, 2.0, t, None, 0))
    before = w.store.query_one("SELECT resentment FROM relationships WHERE from_id = ? AND to_id = ?", (w.id("june"), w.id("pc")))
    before = before[0] if before else 0
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.GESTURE, writer="action.propagate", at=t + 100, turn_index=0, actor_id=w.id("pc"),
                                   payload={"actor_id": w.id("pc"), "gesture": "the_finger", "target_id": w.id("june")}))
        for x in ("june", "mara"):
            perception.compile_aftermath(tx, w.id(x), [ev], t + 200, 0)
        cascade.sweep(tx, [ev], [r for r in w.canon.all("cascade") if r.id == "CAS-079"], t + 300, 0)
    after = w.store.query_one("SELECT resentment FROM relationships WHERE from_id = ? AND to_id = ?", (w.id("june"), w.id("pc")))
    after = after[0] if after else 0
    shamed = w.store.query("SELECT 1 FROM events WHERE type = 'RESOLVE_CHANGE' AND actor_id = ? AND "
                           "json_extract(payload, '$.reason') = 'humiliated_publicly'", (w.id("june"),))
    assert (after == min(3, before + 1)) is audience and bool(shamed) is audience
