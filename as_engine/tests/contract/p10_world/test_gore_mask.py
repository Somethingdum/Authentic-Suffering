"""Gore camouflage (P10, the owner's F1b). Rule INF-14 (world/infected.py sees; InfectedRules
gore_mask_min, mask_window_s, mask_break_db).

Caked in the gore of the dead, a living body moves among them as one of them: they do not pick it
out — until it gives itself away with a voice, a run, a strike, or a hand on one of them. What
already has you keeps on. (What it costs — the smell people will not stand, the fluids that carry
the wet strain — is the rest of the owner's F1 work.)

The stage is metal_fence's sales floor (light 1), with everyone but the PC out of sight.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.events import Event, EventType
from as_engine.kernel import clock
from as_engine.physical import bodies, space
from as_engine.turn import timers
from as_engine.world import infected

pytestmark = pytest.mark.phase(10)

SH, CR, RU = infected.SHAMBLER, infected.CRAWLER, infected.RUNNER
S = 1000


def now(w) -> int:
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def stage(scenario):
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        for q in tx.query("SELECT queue_id FROM event_queue WHERE status = 'pending' ORDER BY queue_id"):
            clock.cancel(tx, q[0], "test", now(w), None, 0)
        for k, who in enumerate(("eli", "mara", "alice", "june")):
            tx.commit_event(space.move_event(tx, w.id(who), w.id("storeroom"), None, 1.0 + k, 2.0, now(w), None, 0))
        tx.commit_event(space.move_event(tx, w.id("pc"), w.id("sales_floor"), None, 6.0, 4.0, now(w), None, 0))
    return w


def later(w, seconds: float):
    with w.store.transaction() as tx:
        clock.advance_event(tx, now(w) + int(seconds * S), "test")


def move(w, x: float, y: float):
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("pc"), w.id("sales_floor"), None, x, y, now(w), None, 0))


def spawn(w, type_id, x, y) -> str:
    with w.store.transaction() as tx:
        return infected.spawn(tx, w.rng, w.id("sales_floor"), type_id, now(w), 0, None, x_m=x, y_m=y)


def gore(w, amount: int):
    with w.store.transaction() as tx:
        bodies.soil(tx, w.id("pc"), gore=amount, source="smeared", at=now(w), cause_event_id=None, turn_index=0)


def speak(w, volume: str):
    db = w.store.rules.acoustics.speech_db[volume]
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("pc"), at=now(w),
                              turn_index=0, payload={"words": "Easy now.", "volume": volume, "to": ["everyone"],
                                                     "source_db": db}))


def noise(w, db: float):
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", actor_id=w.id("pc"), at=now(w),
                              turn_index=0, payload={"source_db": db, "kind": "footsteps", "text": "running feet",
                                                     "place_id": w.id("sales_floor"), "x_m": 6.0, "y_m": 4.0}))


def touch(w, body: str):
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", actor_id=w.id("pc"), at=now(w),
                              turn_index=0, payload={"actor_id": w.id("pc"), "def_id": "test_shove", "verb": "shove",
                                                     "target_id": body, "destination_id": None, "item_id": None,
                                                     "est_duration_s": 0.0, "visible": True}))


def sees(w, b) -> bool:
    return infected.sees(w.store, b, w.id("pc"), now(w))


def test_caked_in_gore_you_move_among_them(scenario):
    """A Shambler 3.5 m off sees the PC move, a Runner sees his shape: with gore at the mask they
    see neither; a smear short of it is not enough."""
    w = stage(scenario)
    near = spawn(w, SH, 6.0, 7.5)
    crawl = spawn(w, CR, 8.0, 5.0)
    run = spawn(w, RU, 13.0, 8.0)
    move(w, 6.0, 4.4)
    assert sees(w, near) and sees(w, crawl) and sees(w, run)
    R = w.store.rules.infected
    gore(w, R.gore_mask_min - 1)
    assert sees(w, near) and sees(w, run), "a smear is not a mask"
    gore(w, 1)
    move(w, 6.0, 4.0)
    assert not sees(w, near) and not sees(w, crawl) and not sees(w, run), "walking among them as one of them"


@pytest.mark.parametrize("give_away, seen", [
    ("whisper", False), ("low", False), ("normal", True), ("shout", True),
    ("noise_50", False), ("noise_55", True), ("touch", True),
])
def test_what_gives_you_away(scenario, give_away, seen):
    w = stage(scenario)
    run = spawn(w, RU, 13.0, 8.0)
    gore(w, 5)
    later(w, 1)
    assert not sees(w, run)
    if give_away.startswith("noise_"):
        noise(w, float(give_away.split("_")[1]))
    elif give_away == "touch":
        touch(w, run)
    else:
        speak(w, give_away)
    assert sees(w, run) is seen
    later(w, w.store.rules.infected.mask_window_s + 1)
    assert not sees(w, run), "and once it has passed, the mask holds again"


def test_touching_another_body_is_not_touching_the_dead(scenario):
    w = stage(scenario)
    run = spawn(w, RU, 13.0, 8.0)
    gore(w, 5)
    touch(w, w.id("mara"))
    assert not sees(w, run)


def test_masked_you_are_not_picked_out_but_what_has_you_keeps_on(scenario):
    """A body looking around the room it stands in finds nobody to go for; one already hunting the
    PC reaches him and grabs, gore or no gore."""
    w = stage(scenario)
    gore(w, 5)
    later(w, 1)
    fresh = spawn(w, RU, 13.0, 8.0)
    with w.store.transaction() as tx:
        assert infected.attract(tx, fresh, w.id("sales_floor"), now(w), None, 0, reason="noise") is None
    speak(w, "normal")
    with w.store.transaction() as tx:
        ev = infected.attract(tx, fresh, w.id("sales_floor"), now(w), None, 0, reason="noise")
    assert ev is not None and ev.payload["target_id"] == w.id("pc"), "a voice gave him away"
    with w.store.transaction() as tx:
        timers.run_offscreen(tx, w.rng, now(w) + 12 * S, 0)
    acts = [r[0] for r in w.store.query("SELECT payload FROM events WHERE type = 'ACTION_START' AND actor_id = ?",
                                        (fresh,))]
    assert acts, "once it has him, the gore does not shake it off"
