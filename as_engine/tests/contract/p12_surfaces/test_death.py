"""The death screen and Willis at every death (P12). Rules DEATH-10..14; DECISIONS D-105, D-106
(service/death.py; service/voice.py; GameService.on_death, on_death_reveal; prompts willis_roast.*).

The owner: "When you die, regardless of Wildcard activation, you see Willis. He mocks and roasts you
joyously over your mistakes." He comes in the frozen moment when the death becomes certain (the Doom,
test_doom.py); the death screen keeps his lines and the Voice's words. What he has to work with is
the dead person's own record; the world's secrets wait for 'Show me everything'.
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
from as_engine.cheats import commands as cheats
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
    """Doomed and dead in the same turn: Willis and the Voice come in the frozen moment."""
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


STRANGER = ["Huh.", "Why am I here? I don't know you. Who even are\u2014"]


def voice_by_moment(q):
    return {"paragraphs": [f"{q.context.moment} one.", f"{q.context.moment} two."]}


def test_the_death_screen_is_the_dead_person_s_own_story(night, fake):
    """DEATH-11: the cause as they felt it, the last moments, their own choices; Willis's lines from
    the frozen moment; the Voice's words, its last word still to come."""
    w, s = night
    fake.fail(CallClass.WILLIS_ROAST, "unavailable")
    fake.script(CallClass.THE_VOICE, voice_by_moment)
    out = dies(w, s, fake)
    dv = death.build_death_view(w.store, s.pc_id)
    assert dv.cause_text == f"You bled to death. {CUT}."
    assert dv.pc_name == w.store.query_one("SELECT display_name FROM actors WHERE actor_id = ?", (s.pc_id,))[0]
    assert dv.last_turns == [r[0] for r in w.store.query("SELECT text FROM narration ORDER BY turn_index")][-3:]
    assert dv.contributing and dv.contributing[0] == json.loads(w.store.query_one(
        "SELECT payload FROM events WHERE type = 'ACTION_START' AND actor_id = ? ORDER BY seq DESC", (s.pc_id,))[0])["label"]
    assert dv.willis == STRANGER and dv.willis_pending is False
    assert dv.voice == ["before one.", "before two."] and dv.voice_pending is True
    assert [b.text for b in out.doom if b.kind == "voice"] == dv.voice
    assert dv.can_load and dv.can_new_life_here and dv.truth_reveal == []


def test_willis_roasts_in_the_frozen_moment_from_the_record(night, fake):
    """DEATH-12, DEATH-13: one call with the dead person's own record; at most three lines; his lines
    are kept in the story at the doom's turn and never asked for twice."""
    w, s = night
    fake.script(CallClass.WILLIS_ROAST, lambda r: {"lines": ["  You WAITED.  ", "", "Coffee?", "Three.", "Four."]})
    out = dies(w, s, fake, words="I wait and hold the arm.")
    assert [b.text for b in out.doom if b.kind == "willis"] == ["You WAITED.", "Coffee?", "Three."]
    f = fake.calls(CallClass.WILLIS_ROAST)[-1].context.facts
    assert f.typed[-1] == "I wait and hold the arm." and f.turns == 1 and f.cause_text == "", "he does not know how"
    assert f.bent_rules is False and f.by_his_hand is False and f.met_him is False
    assert f.borrowed == [] and f.in_debt is False and f.rises is False
    doom_turn = bodies.doomed(w.store, s.pc_id)["turn_index"]
    assert [r[0] for r in w.store.query("SELECT text FROM story_log WHERE kind = 'willis' AND turn_index = ? ORDER BY entry_id",
                                        (doom_turn,))] == ["You WAITED.", "Coffee?", "Three."]
    n = len(fake.calls(CallClass.WILLIS_ROAST))
    assert roast(s) == ["You WAITED.", "Coffee?", "Three."] and len(fake.calls(CallClass.WILLIS_ROAST)) == n, "kept, not re-asked"
    dv = death.build_death_view(w.store, s.pc_id)
    assert dv.willis == ["You WAITED.", "Coffee?", "Three."] and dv.willis_pending is False


def test_willis_needs_no_model(night, fake):
    """DEATH-14: the model down (or answering nothing), Willis still comes — and to a stranger he
    has nothing to say but "why am I here?", before the thing takes him."""
    w, s = night
    fake.fail(CallClass.WILLIS_ROAST, "unavailable")
    out = dies(w, s, fake, words="I wait and hold the arm.")
    assert [b.text for b in out.doom if b.kind == "willis"] == STRANGER
    fake.script(CallClass.WILLIS_ROAST, {"lines": []})
    assert death.fallback_roast(death.roast_facts(w.store, s.pc_id)) == STRANGER


def test_whatever_the_settings(night, fake):
    """DEATH-13: regardless of the Wild Card, the console or Ironman."""
    w, s = night
    assert s.settings.wild_card is False
    w.store.conn.execute("UPDATE meta SET value = '1' WHERE key = 'sandbox'")
    settings = json.loads(w.store.meta("settings_json"))
    w.store.conn.execute("UPDATE meta SET value = ? WHERE key = 'settings_json'", (json.dumps({**settings, "save_mode": "ironman"}),))
    fake.fail(CallClass.WILLIS_ROAST, "unavailable")
    dies(w, s, fake)
    f = death.roast_facts(w.store, s.pc_id)
    assert f.bent_rules is True and f.ironman is True
    dv = death.build_death_view(w.store, s.pc_id)
    assert dv.can_load is False and dv.can_new_life_here is False and dv.willis == STRANGER


def test_no_secrets_until_asked(night, fake):
    """DEATH-12 / DEATH-10: Willis works from the dead person's record; the reveal, asked for, tells
    who was where by their true names, and what the dead never saw."""
    w, s = night
    fake.fail(CallClass.WILLIS_ROAST, "unavailable")
    dies(w, s, fake)
    facts = death.roast_facts(w.store, s.pc_id)
    assert set(RoastFacts.model_fields) == {"pc_name", "lived", "turns", "cause_text", "choices", "typed", "bent_rules",
                                            "borrowed", "in_debt", "ironman", "rises", "met_him", "by_his_hand"}
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
    fake.fail(CallClass.WILLIS_ROAST, "unavailable")
    out = dies(w, s, fake, by=w.id("mara"))
    f = death.roast_facts(w.store, s.pc_id)
    assert f.met_him is True and f.by_his_hand is True
    assert [b.text for b in out.doom if b.kind == "willis"] == [
        "Oh, it's you from earlier.", "Yeah, that was me, by the way. Worth it.",
        "Yeah, this is going to be neat. Hold still. Well, you can't not, can you\u2014"]


def test_the_fallback_s_order_and_length():
    """DEATH-14: in his debt, six lines — twice as hard; he never finishes the last."""
    f = RoastFacts(pc_name="Owen", lived="2 days", turns=3, typed=["I kick the door."], borrowed=["/give ammo_38 1", "/heal"],
                   in_debt=True, by_his_hand=True, met_him=True)
    assert death.fallback_roast(f) == [
        "Well, well, well. Look who's in my debt.",
        "You borrowed my power 2 times, and you spent it on '/heal'.",
        "That's not a loan, that's a confession.",
        "You had MY power. Mine. And you still ended up here, frozen, about to die like everybody else.",
        "And yes, I helped. You had it coming, and I had a free minute.",
        "Ha! Now, about collecting. See, the thing about borrowing from me is\u2014"]
    one = death.fallback_roast(f.model_copy(update={"borrowed": ["/heal"], "by_his_hand": False}))
    assert one[1] == "You borrowed my power 1 time, and you spent it on '/heal'."
    assert one[4] == "Do you know what I do to people who owe me? Nothing. I watch. It's funnier."
    assert death.fallback_roast(f.model_copy(update={"in_debt": False, "by_his_hand": False})) == [
        "Oh, it's you from earlier.", "Yeah, this is going to be neat. Hold still. Well, you can't not, can you\u2014"]
    assert death.fallback_roast(RoastFacts(pc_name="Owen", lived="2 days", turns=3)) == STRANGER
    assert all(ln[-1] == "\u2014" for ln in (death.fallback_roast(f)[-1], STRANGER[-1])), "cut off: the thing takes him"


@pytest.mark.parametrize("ms,words", [(0, "a second"), (40 * 60_000, "40 minutes"), (60 * 60_000, "1 hour"),
                                      (5 * 3_600_000, "5 hours"), (47 * 3_600_000, "47 hours"), (2 * 86_400_000, "2 days"),
                                      (9 * 86_400_000 + 5, "9 days")])
def test_how_long_they_lasted(ms, words):
    assert death.lifespan_words(ms) == words


# =========================================================================== through the GameService
async def test_the_doom_the_death_and_the_last_word_through_the_service(svc, make_run, fake):
    """VOICE-07, VOICE-09, DEATH-11: the Doom scene before the turn's result; the death screen at once
    with Willis and the Voice; the Voice's last word a moment later; then the dead screen; the truth
    only when asked; nothing to reveal while alive."""
    await send(svc, "run_load", run_id=make_run())
    assert error_code(await send(svc, "death_reveal")) == "bad_request"
    s = svc.session
    bleeding_out(s.store, s.pc_id, s.rng)
    fake.script(CallClass.INTAKE, lambda q: {"choice": offered(q, "wait_here"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    fake.script(CallClass.WILLIS_ROAST, {"lines": ["Oh, bravo.", "Coffee."]})
    fake.script(CallClass.THE_VOICE, voice_by_moment, times=2)
    svc.pushed.clear()
    await send(svc, "turn_submit", mode="do", text="I wait.")
    await wait_for(lambda: not svc.busy)
    got = actions(svc.pushed)
    assert got.index("doom") < got.index("turn_result") < got.index("death")
    beats = only(svc.pushed, "doom")["beats"]
    assert [b["text"] for b in beats if b["kind"] == "willis"] == ["Oh, bravo.", "Coffee."]
    assert [b["text"] for b in beats if b["kind"] == "voice"] == ["before one.", "before two."]
    deaths = [m["data"]["death"] for m in svc.pushed if m["action"] == "death"]
    assert len(deaths) == 2
    assert deaths[0]["willis"] == ["Oh, bravo.", "Coffee."] and deaths[0]["willis_pending"] is False
    assert deaths[0]["voice"] == ["before one.", "before two."] and deaths[0]["voice_pending"] is True
    assert deaths[1]["voice"] == ["before one.", "before two.", "after one.", "after two."] and deaths[1]["voice_pending"] is False
    assert [q.context.moment for q in fake.calls(CallClass.THE_VOICE)] == ["before", "after"]
    assert s.store.query_one("SELECT COUNT(*) FROM lm_calls WHERE call_class = 'the_voice'")[0] == 2, "both recorded"
    story = [m for m in svc.pushed if m["action"] == "story"][-1]["data"]["entries"]
    assert [e["text"] for e in story if e["kind"] == "willis"] == ["Oh, bravo.", "Coffee."]
    assert [e["text"] for e in story if e["kind"] == "voice_after"] == ["after one.", "after two."]
    assert svc.pushed[-1]["action"] == "state" and svc.pushed[-1]["data"]["screen"] == "dead"
    r = only(await send(svc, "death_reveal"), "death")["death"]
    assert r["truth_reveal"] and r["willis"] == ["Oh, bravo.", "Coffee."]


async def test_willis_collects(svc, make_run, fake):
    """D-106: the console is Willis's power, on loan. In his debt he mocks twice as hard; after the
    death he collects: the console closes."""
    await send(svc, "run_load", run_id=make_run())
    s = svc.session
    cheats.activate(s)
    assert (await cheats.execute(s, cheats.parse("/give ammo_38 1"))).ok
    bleeding_out(s.store, s.pc_id, s.rng)
    fake.script(CallClass.INTAKE, lambda q: {"choice": offered(q, "wait_here"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    fake.fail(CallClass.WILLIS_ROAST, "unavailable")
    fake.fail(CallClass.THE_VOICE, "unavailable", times=2)
    await send(svc, "turn_submit", mode="do", text="I wait.")
    await wait_for(lambda: not svc.busy)
    dv = death.build_death_view(s.store, s.pc_id)
    assert len(dv.willis) == 6 and dv.willis[0] == "Well, well, well. Look who's in my debt."
    assert s.store.meta("cheat_active") == "0"
    (payload,) = s.store.query_one("SELECT payload FROM events WHERE type = 'CHEAT_DEACTIVATED' ORDER BY seq DESC")
    assert json.loads(payload)["reason"] == "willis_collects"
    assert dv.voice[-1].startswith("And that is how. You bled to death.") and dv.voice_pending is False
