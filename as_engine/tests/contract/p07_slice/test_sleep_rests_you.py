"""Sleep rests you (D-122). Rules SLEEP-01 (physical/bodies.py wake, progress), SLEEP-02 (action/resolve.py),
core CAS-021 (a night's unbroken sleep) and CAS-029 (a promise kept), mind/resolve.py recover; the cascade's
recover_resolve (action/cascade.py).

Until D-122 only a settlement's timetable ever reset anyone's fatigue: the player's character could lie
down and sleep for a whole night and get up exactly as tired — and once he slept, everything the player
typed was blocked as 'incapable' until some sound happened to wake him. And
nothing ever gave Resolve back (05 §5: a night asleep somewhere safe, an obligation fulfilled) — it only
ever drained.
"""

from __future__ import annotations

import pytest
from slice_kit import pick, play

from as_engine.action import cascade
from as_engine.contracts.common import CallClass
from as_engine.contracts.events import EventType
from as_engine.mind import mind
from as_engine.physical import bodies

pytestmark = pytest.mark.phase(7)

H = 3_600_000


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def needs(w, who):
    return dict(w.store.query_one("SELECT fatigue_stage, last_sleep_ms FROM needs WHERE body_id = ?", (w.id(who),)))


def asleep_since(w, who, at, awake_for_h):
    """``who`` has been awake ``awake_for_h`` hours when they lie down to sleep at ``at``."""
    w.store.conn.execute("UPDATE needs SET last_sleep_ms = ?, fatigue_stage = ? WHERE body_id = ?",
                         (at - awake_for_h * H, min(6, awake_for_h // 8), w.id(who)))
    with w.store.transaction() as tx:
        bodies.posture_event(tx, w.id(who), "lying", at, None, 0, awareness="asleep")


def rules(w, *ids):
    return [r for r in w.canon.all("cascade") if r.id in ids]


def test_a_night_s_sleep_pays_off_a_day_awake(scenario):
    """SLEEP-01: 16 hours awake, 8 asleep: rested. While asleep the fatigue does not climb."""
    w = scenario("metal_fence")
    t = now(w)
    asleep_since(w, "june", t, 16)
    with w.store.transaction() as tx:
        bodies.progress(tx, w.id("june"), t + 8 * H, 0, w.rng)
    assert needs(w, "june")["fatigue_stage"] == 2, "held where it was when she lay down (16 h / 8)"
    with w.store.transaction() as tx:
        ev = bodies.wake(tx, w.id("june"), t + 8 * H, None, 0)
    assert ev.payload["slept_ms"] == 8 * H
    assert needs(w, "june") == {"fatigue_stage": 0, "last_sleep_ms": t + 8 * H}


def test_a_nap_pays_a_little(scenario):
    w = scenario("metal_fence")
    t = now(w)
    asleep_since(w, "june", t, 16)
    with w.store.transaction() as tx:
        ev = bodies.wake(tx, w.id("june"), t + 2 * H, None, 0)
    assert ev.payload["slept_ms"] == 2 * H
    assert needs(w, "june") == {"fatigue_stage": 1, "last_sleep_ms": t + 2 * H - 12 * H}, "16 owed, 4 paid: 12 left"


def test_the_player_decides_when_he_wakes(scenario, fake):
    """SLEEP-02 through a turn: Owen has slept seven hours; "I wait" wakes him first, rested, and a whole
    night's sleep takes the edge off and gives back a little Resolve (CAS-021)."""
    w = scenario("metal_fence")
    s = w.session()
    t = now(w)
    asleep_since(w, "pc", t - 7 * H, 10)
    w.store.conn.execute("UPDATE actors SET resolve_cur = 1, stress = 4 WHERE actor_id = ?", (s.pc_id,))
    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "wait_here"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    assert play(s, "do", "I wait.").ok
    woke = w.store.query("SELECT payload FROM events WHERE type = 'AWARENESS_CHANGE' AND turn_index = 1 AND actor_id IS NULL "
                         "AND json_extract(payload, '$.body_id') = ?", (s.pc_id,))
    assert woke, "he woke before he did anything"
    assert w.store.query_one("SELECT awareness FROM bodies WHERE body_id = ?", (s.pc_id,))[0] != "asleep"
    assert needs(w, "pc")["last_sleep_ms"] == t, "10 hours owed, 7 slept pays 14: rested the moment he woke"
    resolve, stress = w.store.query_one("SELECT resolve_cur, stress FROM actors WHERE actor_id = ?", (s.pc_id,))
    assert (resolve, stress) == (2, 2), "CAS-021: the edge off, a little Resolve back"


def test_a_short_sleep_is_not_a_night(scenario):
    w = scenario("metal_fence")
    t = now(w)
    asleep_since(w, "june", t, 12)
    w.store.conn.execute("UPDATE actors SET resolve_cur = 1 WHERE actor_id = ?", (w.id("june"),))
    with w.store.transaction() as tx:
        ev = bodies.wake(tx, w.id("june"), t + 5 * H, None, 0)
        assert cascade.sweep(tx, [ev], rules(w, "CAS-021"), t + 5 * H, 0) == [], "five hours is not a night"
    with w.store.transaction() as tx:
        bodies.posture_event(tx, w.id("june"), "lying", t + 6 * H, None, 0, awareness="asleep")
        ev = bodies.wake(tx, w.id("june"), t + 12 * H, None, 0)
        out = cascade.sweep(tx, [ev], rules(w, "CAS-021"), t + 12 * H, 0)
    assert out and {e.rule_cited for e in out} == {"CAS-021"}
    assert w.store.query_one("SELECT resolve_cur FROM actors WHERE actor_id = ?", (w.id("june"),))[0] == 2


def test_a_promise_kept_steadies_the_one_who_kept_it(scenario):
    """CAS-029: Mara promised June to check the back door; it is done."""
    w = scenario("metal_fence")
    t = now(w)
    w.store.conn.execute("UPDATE actors SET resolve_cur = 1 WHERE actor_id = ?", (w.id("mara"),))
    with w.store.transaction() as tx:
        loop_id = mind.open_loop(tx, w.id("june"), "promise_owed", "Mara said she would check the back door.",
                                 [w.id("mara")], 2, None, t, 0)
        kept = mind.close_loop(tx, loop_id, "fulfilled", None, t + 60_000, 0)
        assert kept.type == EventType.PROMISE_KEPT and kept.payload["promiser_id"] == w.id("mara")
        out = cascade.sweep(tx, [kept], rules(w, "CAS-029"), t + 60_000, 0)
    assert [e.rule_cited for e in out] == ["CAS-029"]
    assert w.store.query_one("SELECT resolve_cur FROM actors WHERE actor_id = ?", (w.id("mara"),))[0] == 2


def test_the_player_wakes_him_and_sleeping_on_is_not_waking(scenario):
    """SLEEP-02 in the resolver: Owen, asleep, does anything but sleep — he wakes first; sleeping on
    leaves him asleep, and all of the sleep counts. June asleep is woken by nothing she decides: her
    act is blocked, as ever (people wake to a sound or their routine)."""
    import helpers
    from as_engine.action.intent import barrier
    from as_engine.action.resolve import resolve_wave
    w = scenario("metal_fence")
    t = now(w)
    asleep_since(w, "pc", t - 3 * H, 12)
    with w.store.transaction() as tx:
        resolve_wave(tx, w.rng, barrier(tx, [helpers.make_intent(w, "pc", "sleep")]), t, 0, horizon_ms=t + 60_000)
    assert w.store.query_one("SELECT awareness FROM bodies WHERE body_id = ?", (w.id("pc"),))[0] == "asleep"
    with w.store.transaction() as tx:
        resolve_wave(tx, w.rng, barrier(tx, [helpers.make_intent(w, "pc", "wait_here")]), t + 60_000, 0,
                     horizon_ms=t + 120_000)
    woke, start = w.store.query("SELECT type, json_extract(payload, '$.slept_ms') FROM events WHERE seq > (SELECT MAX(seq) "
                                "FROM events WHERE type = 'ACTION_START' AND json_extract(payload, '$.def_id') = 'sleep') AND "
                                "(type = 'AWARENESS_CHANGE' OR type = 'ACTION_START') ORDER BY seq")[:2]
    assert (woke[0], start[0]) == ("AWARENESS_CHANGE", "ACTION_START"), "awake first, then he acts"
    assert woke[1] == 3 * H + 60_000, "sleeping on is not falling asleep again: all of it counts"
    assert w.store.query_one("SELECT awareness FROM bodies WHERE body_id = ?", (w.id("pc"),))[0] == "awake"
    asleep_since(w, "june", t, 12)
    with w.store.transaction() as tx:
        resolve_wave(tx, w.rng, barrier(tx, [helpers.make_intent(w, "june", "stand_up")]), t + 120_000, 0,
                     horizon_ms=t + 180_000)
    assert w.store.query_one("SELECT awareness FROM bodies WHERE body_id = ?", (w.id("june"),))[0] == "asleep"
