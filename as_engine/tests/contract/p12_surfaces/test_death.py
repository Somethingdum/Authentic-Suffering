"""The death screen and Willis at every death (P12). Rules DEATH-10..14; DECISIONS D-105
(service/death.py; GameService.on_death, on_death_reveal; prompts willis_roast.*).

The owner: "When you die, regardless of Wildcard activation, you see Willis. He mocks and roasts you
joyously over your mistakes." What he has to work with is the dead person's own record; the world's
secrets wait for 'Show me everything'.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from protocol_kit import actions, error_code, only, send, wait_for
from slice_kit import pick, play

from as_engine.contracts.calls import RoastFacts
from as_engine.contracts.common import CallClass
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import bodies
from as_engine.physical.bodies import WoundSpec
from as_engine.service import death

pytestmark = pytest.mark.phase(12)

CUT = "Glass slices your forearm open"


def bleeding_out(store, pc_id, rng, by=None):
    """A deep cut the PC felt, and so much blood already gone that the next moment is the last."""
    with store.transaction() as tx:
        at = tx.query_one("SELECT now_ms FROM world_clock")[0]
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=at, turn_index=0, actor_id=by,
                                  payload={"what": "test"}))
        perception.grant(tx, pc_id, event_id=c.event_id, channel="tactile", fidelity="exact", text=CUT, source_id=None,
                         at=at, turn_index=0)
        bodies.apply_harm(tx, pc_id, WoundSpec("arm_l", "cut", "severe", 0), at, c.event_id, 0, rng)
    store.conn.execute("UPDATE bodies SET blood_loss_pct = 39.9 WHERE body_id = ?", (store.meta("pc_actor_id"),))


def dies(w, s, fake, words="I wait and hold the arm.", by=None):
    bleeding_out(w.store, s.pc_id, s.rng, by=by)
    fake.script(CallClass.INTAKE, lambda q: {"choice": pick(w, q, "wait_here"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    out = play(s, "do", words)
    assert out.ok and out.died, "the next moment is the last"
    return out


def roast(s):
    return asyncio.run(death.roast(s))


def offered(request, def_id):
    p = request.context.packet
    return next(a.handle for a in p.affordances if p.handles[a.handle].split(":")[0] == def_id)


def test_the_death_screen_is_the_dead_person_s_own_story(night, fake):
    """DEATH-11: the cause as they felt it, the last moments, their own choices; Willis on his way."""
    w, s = night
    dies(w, s, fake)
    dv = death.build_death_view(w.store, s.pc_id)
    assert dv.cause_text == f"You bled to death. {CUT}."
    assert dv.pc_name == w.store.query_one("SELECT display_name FROM actors WHERE actor_id = ?", (s.pc_id,))[0]
    assert dv.last_turns == [r[0] for r in w.store.query("SELECT text FROM narration ORDER BY turn_index")][-3:]
    assert dv.contributing and dv.contributing[0] == json.loads(w.store.query_one(
        "SELECT payload FROM events WHERE type = 'ACTION_START' AND actor_id = ? ORDER BY seq DESC", (s.pc_id,))[0])["label"]
    assert dv.willis == [] and dv.willis_pending is True
    assert dv.can_load and dv.can_new_life_here and dv.truth_reveal == []


def test_willis_roasts_every_death_from_the_record(night, fake):
    """DEATH-12, DEATH-13: one call with the dead person's own record; his lines are kept in the story
    and never asked for twice."""
    w, s = night
    dies(w, s, fake, words="I wait and hold the arm.")
    fake.script(CallClass.WILLIS_ROAST, lambda r: {"lines": ["  You WAITED.  ", "", "Coffee?"]})
    assert roast(s) == ["You WAITED.", "Coffee?"]
    f = fake.calls(CallClass.WILLIS_ROAST)[-1].context.facts
    assert f.typed[-1] == "I wait and hold the arm." and f.turns == 1 and f.cause_text.startswith("You bled to death.")
    assert f.bent_rules is False and f.by_his_hand is False and f.met_him is False
    assert [r[0] for r in w.store.query("SELECT text FROM story_log WHERE kind = 'willis' ORDER BY entry_id")] == \
        ["You WAITED.", "Coffee?"]
    n = len(fake.calls(CallClass.WILLIS_ROAST))
    assert roast(s) == ["You WAITED.", "Coffee?"] and len(fake.calls(CallClass.WILLIS_ROAST)) == n, "kept, not re-asked"
    dv = death.build_death_view(w.store, s.pc_id)
    assert dv.willis == ["You WAITED.", "Coffee?"] and dv.willis_pending is False


def test_willis_needs_no_model(night, fake):
    """DEATH-14: the model down (or answering nothing), Willis still comes."""
    w, s = night
    dies(w, s, fake, words="I wait and hold the arm.")
    fake.fail(CallClass.WILLIS_ROAST, "unavailable")
    lines = roast(s)
    assert death.roast_facts(w.store, s.pc_id).rises, "everyone who dies here gets up again"
    assert lines == ["Ha! Oh, that was beautiful. Do it again.",
                     "\"I wait and hold the arm.\" — that's what you went with. Incredible.",
                     "You bled to death. I've watched mayflies plan better.",
                     "Don't worry, you'll be back on your feet in a few hours. Just not as you.",
                     "Anyway. Coffee's getting cold. Go on, try again. I'll be watching."]


def test_whatever_the_settings(night, fake):
    """DEATH-13: regardless of the Wild Card, the console or Ironman."""
    w, s = night
    assert s.settings.wild_card is False
    w.store.conn.execute("UPDATE meta SET value = '1' WHERE key = 'sandbox'")
    settings = json.loads(w.store.meta("settings_json"))
    w.store.conn.execute("UPDATE meta SET value = ? WHERE key = 'settings_json'", (json.dumps({**settings, "save_mode": "ironman"}),))
    dies(w, s, fake)
    fake.fail(CallClass.WILLIS_ROAST, "unavailable")
    lines = roast(s)
    assert "You bent the rules of reality and STILL managed this. I'm genuinely impressed." in lines
    assert lines[-1] == "Anyway. Coffee's getting cold. That was your only one, by the way."
    dv = death.build_death_view(w.store, s.pc_id)
    assert dv.can_load is False and dv.can_new_life_here is False and dv.willis == lines


def test_no_secrets_until_asked(night, fake):
    """DEATH-12 / DEATH-10: Willis works from the dead person's record; the reveal, asked for, tells
    who was where by their true names, and what the dead never saw."""
    w, s = night
    dies(w, s, fake)
    fake.fail(CallClass.WILLIS_ROAST, "unavailable")
    roast(s)
    facts = death.roast_facts(w.store, s.pc_id)
    assert set(RoastFacts.model_fields) == {"pc_name", "lived", "turns", "cause_text", "choices", "typed", "bent_rules",
                                            "ironman", "rises", "met_him", "by_his_hand"}
    names = {r[0] for r in w.store.query("SELECT display_name FROM actors WHERE actor_id != ?", (s.pc_id,))}
    assert not any(n in " ".join([facts.cause_text, *facts.choices, *facts.typed]) for n in names if n)
    reveal = death.truth_reveal(w.store, s.pc_id)
    mara = w.store.query_one("SELECT display_name FROM actors WHERE actor_id = ?", (w.id("mara"),))[0]
    (floor,) = [ln for ln in reveal if ln.startswith("In the Sales floor: ")]
    assert mara in floor
    assert all(not ln.startswith("You never saw it: ") or ": " in ln[len("You never saw it: "):] for ln in reveal)


def test_willis_remembers_his_own_work(night, fake):
    """DEATH-12: met_him and by_his_hand come from the record — someone in the reality exception the
    dead knew, whose doing is on the chain of events that killed them."""
    w, s = night
    with w.store.transaction() as tx:
        bodies.grant_exception(tx, w.id("mara"), tx.query_one("SELECT now_ms FROM world_clock")[0], 0, origin="cheat")
    dies(w, s, fake, by=w.id("mara"))
    f = death.roast_facts(w.store, s.pc_id)
    assert f.met_him is True and f.by_his_hand is True
    assert "And yes, that was me. You had it coming, and I had a free minute." in death.fallback_roast(f)


def test_the_fallback_s_order_and_length():
    """DEATH-14."""
    f = RoastFacts(pc_name="Owen", lived="2 days", turns=3, cause_text="A wound to the head killed you. Teeth.",
                   typed=["I kick the door."], by_his_hand=True, bent_rules=True, rises=True, ironman=True)
    lines = death.fallback_roast(f)
    assert len(lines) == 6
    assert lines[:3] == ["Ha! Oh, that was beautiful. Do it again.",
                         "\"I kick the door.\" — that's what you went with. Incredible.",
                         "A wound to the head killed you. I've watched mayflies plan better."]
    assert lines[3] == "And yes, that was me. You had it coming, and I had a free minute."
    assert lines[4] == "You bent the rules of reality and STILL managed this. I'm genuinely impressed."
    assert lines[5] == "Anyway. Coffee's getting cold. That was your only one, by the way."


@pytest.mark.parametrize("ms,words", [(0, "a second"), (40 * 60_000, "40 minutes"), (60 * 60_000, "1 hour"),
                                      (5 * 3_600_000, "5 hours"), (47 * 3_600_000, "47 hours"), (2 * 86_400_000, "2 days"),
                                      (9 * 86_400_000 + 5, "9 days")])
def test_how_long_they_lasted(ms, words):
    assert death.lifespan_words(ms) == words


# =========================================================================== through the GameService
async def test_the_death_screen_and_willis_through_the_service(svc, make_run, fake):
    """DEATH-11, DEATH-13: the screen at once, Willis a moment later, then the dead screen; the truth
    only when asked; nothing to reveal while alive."""
    await send(svc, "run_load", run_id=make_run())
    assert error_code(await send(svc, "death_reveal")) == "bad_request"
    s = svc.session
    bleeding_out(s.store, s.pc_id, s.rng)
    fake.script(CallClass.INTAKE, lambda q: {"choice": offered(q, "wait_here"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    fake.script(CallClass.WILLIS_ROAST, {"lines": ["Oh, bravo.", "Coffee."]})
    svc.pushed.clear()
    await send(svc, "turn_submit", mode="do", text="I wait.")
    await wait_for(lambda: not svc.busy)
    got = actions(svc.pushed)
    deaths = [m["data"]["death"] for m in svc.pushed if m["action"] == "death"]
    assert len(deaths) == 2
    assert deaths[0]["willis_pending"] is True and deaths[0]["willis"] == []
    assert deaths[1]["willis_pending"] is False and deaths[1]["willis"] == ["Oh, bravo.", "Coffee."]
    assert got.index("death") > got.index("turn_result")
    story = [m for m in svc.pushed if m["action"] == "story"][-1]["data"]["entries"]
    assert [e["text"] for e in story if e["kind"] == "willis"] == ["Oh, bravo.", "Coffee."]
    assert svc.pushed[-1]["action"] == "state" and svc.pushed[-1]["data"]["screen"] == "dead"
    r = only(await send(svc, "death_reveal"), "death")["death"]
    assert r["truth_reveal"] and r["willis"] == ["Oh, bravo.", "Coffee."]
