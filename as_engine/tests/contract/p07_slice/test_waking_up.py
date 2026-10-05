"""Waking up (D-171, D-172). Rule SLEEP-03: physical/bodies.py capacity(as_awake), mind/affordance.py
enumerate_affordances(waking), turn/intake.py INTAKE-01, service/view.py suggestions; narration/narrator.py the
sleeping and waking lines, world_time_text, ASLEEP AT THE END.

SLEEP-02 promised that the player decides when the character wakes. But the player's menu was built for a sleeper,
and a sleeper can do nothing — so once a night passed in quiet, whatever the player typed failed the whole turn
("empty affordance set"), and only a noise could ever wake him. And the night itself was told as nothing: the prose
was given "Owen chose to lie down and sleep" with the room at dawn and asked to end on what he faced, and the
morning after only "Owen chose to stand up".
"""

from __future__ import annotations

import pytest
from slice_kit import pick, play

from as_engine.contracts.common import CallClass
from as_engine.kernel.clock import format_clock
from as_engine.mind.affordance import enumerate_affordances
from as_engine.physical import bodies

pytestmark = pytest.mark.phase(7)

H = 3_600_000


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def choose(w, fake, def_id, looks=1):
    """The player means ``def_id``; when it is not on the short first list, the intake looks again (INTAKE-07)."""
    def answer(r):
        try:
            return {"choice": pick(w, r, def_id), "none_reason": None, "manner": "", "remainder": None, "clarify": None}
        except KeyError:
            return {"choice": "NONE", "none_reason": "impossible", "manner": "", "remainder": None, "clarify": None}
    fake.script(CallClass.INTAKE, answer, times=looks)


def narrated(fake):
    return [r for r in fake.requests if r.call_class == CallClass.NARRATION][-1].context


def awake(w, who):
    return tuple(w.store.query_one("SELECT awareness, posture FROM bodies WHERE body_id = ?", (w.id(who),)))


def a_quiet_night(w, fake, s):
    """The crash out back has come and gone; then Owen has been asleep eight hours, and nothing woke him."""
    choose(w, fake, "wait_here")
    assert play(s, "do", "I wait.").ok
    with w.store.transaction() as tx:
        bodies.posture_event(tx, s.pc_id, "lying", now(w) - 8 * H, None, 1, awareness="asleep")


def test_he_gets_up_when_the_player_says(scenario, fake):
    w = scenario("metal_fence")
    s = w.session()
    a_quiet_night(w, fake, s)
    choose(w, fake, "stand_up", looks=2)
    assert play(s, "do", "I get up.").ok, "the menu is what he could do on waking"
    assert awake(w, "pc") == ("awake", "standing")
    k = narrated(fake)
    told = [ln.text for ln in k.lines]
    assert told[:2] == ["Owen woke after about 8 hours asleep.", "Owen chose to stand up."], told


def test_asleep_at_the_end(scenario, fake):
    w = scenario("metal_fence")
    s = w.session()
    choose(w, fake, "wait_here")
    assert play(s, "do", "I wait.").ok
    t0 = now(w)
    choose(w, fake, "sleep", looks=2)
    assert play(s, "do", "I lie down and sleep.").ok
    assert awake(w, "pc") == ("asleep", "lying")
    k = narrated(fake)
    assert [ln.text for ln in k.lines if ln.kind == "outcome"][-1] == "Owen fell asleep."
    assert k.choice_prompt_hint == "Owen asleep", "nothing faced: he is asleep"
    assert (k.people_present, k.people_looks) == ([], []), "a sleeper sees nobody"
    assert now(w) - t0 >= 10 * 60_000, "a quiet night passes in one turn"
    assert k.world_time_text.startswith(f"{format_clock(t0)} to "), k.world_time_text


def test_only_the_player_wakes_by_choice(scenario):
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        bodies.posture_event(tx, w.id("june"), "lying", t, None, 0, awareness="asleep")
        assert bodies.capacity(tx, w.id("june")).conscious is False
        assert bodies.capacity(tx, w.id("june"), as_awake=True).conscious is True
        assert enumerate_affordances(tx, w.id("june"), tx.canon.all("affordance"), t, 0).options == [], \
            "June asleep decides nothing (SLEEP-02): her own menu is not built waking"
        assert enumerate_affordances(tx, w.id("june"), tx.canon.all("affordance"), t, 0, waking=True).options
    w.store.conn.execute("UPDATE bodies SET awareness = 'unconscious' WHERE body_id = ?", (w.id("june"),))
    with w.store.transaction() as tx:
        assert bodies.capacity(tx, w.id("june"), as_awake=True).conscious is False, "out cold is not asleep"
