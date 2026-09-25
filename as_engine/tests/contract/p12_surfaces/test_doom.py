"""The Doom, Willis in the frozen moment, and the Voice (P12). Rules DOOM-01..08, VOICE-01..09;
DECISIONS D-106 (physical/bodies.py; service/voice.py; service/death.py; turn/intake.py;
turn/pipeline.py; cheats/commands.py; docs/as/sources/THE_VOICE.md).

The owner: "by the point you got the message, there was no evading it. No, nothing you have done or
could do could evade it ... And that's how everybody dies." Seconds before somebody dies they start
screaming, and nobody knows why.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from slice_kit import pick, play

from as_engine.cheats import commands as cheats
from as_engine.contracts.calls import ChainBeat, VoiceFacts
from as_engine.contracts.common import CallClass
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.physical import bodies
from as_engine.physical.bodies import WoundSpec
from as_engine.service import death, voice
from as_engine.turn.intake import DOOMED_WORDS

pytestmark = pytest.mark.phase(12)

CUT = "Glass slices your forearm open"


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def cut(w, s, body, anatomy, severity, *, blood=None, by=None, felt=None):
    """A wound on ``body`` now (its blood already at ``blood`` when given)."""
    if blood is not None:
        w.store.conn.execute("UPDATE bodies SET blood_loss_pct = ? WHERE body_id = ?", (blood, body))
    with w.store.transaction() as tx:
        at = tx.query_one("SELECT now_ms FROM world_clock")[0]
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=at, turn_index=0, actor_id=by, payload={"what": "test"}))
        if felt:
            perception.grant(tx, body, event_id=c.event_id, channel="tactile", fidelity="exact", text=felt, source_id=None,
                             at=at, turn_index=0)
        bodies.apply_harm(tx, body, WoundSpec(anatomy, "cut", severity, 0), at, c.event_id, 0, s.rng)
    return at


def cheat_ok(s, line):
    if s.store.meta("cheat_active") != "1":
        cheats.activate(s)
    return asyncio.run(cheats.execute(s, cheats.parse(line)))


def dies(w, s, fake, words="I wait and hold the arm.", by=None):
    """A cut the PC felt; then so much blood already gone that the moment it waits is its last (the
    doom and the death both land inside the turn)."""
    cut(w, s, s.pc_id, "arm_l", "severe", by=by, felt=CUT)
    w.store.conn.execute("UPDATE bodies SET blood_loss_pct = 39.9 WHERE body_id = ?", (s.pc_id,))
    fake.script(CallClass.INTAKE, lambda q: {"choice": pick(w, q, "wait_here"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    out = play(s, "do", words)
    assert out.ok and out.died
    return out


# =========================================================================== the Doom
def test_bleeding_past_saving_is_a_doom(night, fake):
    """DOOM-01: certain only when even the best care, at once, could not stop it in time."""
    w, s = night
    mara, alice, june = w.id("mara"), w.id("alice"), w.id("june")
    cut(w, s, alice, "arm_l", "severe", blood=0)
    assert bodies.doomed(w.store, alice) is None, "a tourniquet would save that arm"
    cut(w, s, june, "chest", "severe", blood=30)
    assert bodies.doomed(w.store, june) is None, "33 minutes even packed: not yet certain"
    at = cut(w, s, mara, "arm_l", "severe", blood=38.5)
    d = bodies.doomed(w.store, mara)
    assert d["kind"] == "bleeding" and d["doomed_at"] == at
    assert d["expected_at"] == at + 30_000, "3% a minute, 1.5% to go"
    assert 1_499_000 <= d["death_by"] - at <= 1_502_000, "even a tourniquet: 0.06% a minute"
    (ev,) = w.store.query("SELECT event_id, cause_event_id FROM events WHERE type = 'DOOM' AND actor_id = ?", (mara,))
    assert json.loads(w.store.query_one("SELECT payload FROM events WHERE event_id = ?", (ev[0],))[0])["kind"] == "bleeding"


def test_the_doomed_scream_and_nobody_knows_why(night, fake):
    """DOOM-04, DOOM-06: a scream the room hears, the doomed feel it, a mind does nothing else — and no
    one is told why."""
    w, s = night
    mara = w.id("mara")
    at = cut(w, s, mara, "arm_l", "severe", blood=38.5)
    d = bodies.doomed(w.store, mara)
    doom_ev = w.store.query_one("SELECT event_id FROM events WHERE type = 'DOOM' AND actor_id = ?", (mara,))[0]
    (noise,) = w.store.query("SELECT payload FROM events WHERE type = 'NOISE' AND cause_event_id = ?", (doom_ev,))
    assert json.loads(noise[0])["kind"] == "screaming"
    assert w.store.query("SELECT 1 FROM percept_log WHERE holder_id = ? AND event_id = ? AND text = 'You are screaming.'",
                         (mara, doom_ev))
    assert bodies.forced(w.store, mara, at) == "screams"
    assert bodies.forced(w.store, mara, d["death_by"] + 60_000) == "screams" and \
        bodies.forced(w.store, mara, d["death_by"] + 121_000) is None
    assert not w.store.query("SELECT 1 FROM claim_holdings WHERE acquired_via = ?", (doom_ev,)), "nobody learns why"


def test_the_torso_packed_and_the_last_half_hour(night, fake):
    w, s = night
    alice = w.id("alice")
    cut(w, s, alice, "chest", "severe", blood=32)
    d = bodies.doomed(w.store, alice)
    assert d is not None and d["kind"] == "bleeding", "8% to go at 0.3% a minute: under half an hour"


def test_an_instant_death_is_a_doom_in_the_instant(night, fake):
    """DOOM-03."""
    w, s = night
    mara = w.id("mara")
    with w.store.transaction() as tx:
        at = now(w)
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=at, turn_index=0, payload={"what": "test"}))
        bodies.apply_harm(tx, mara, WoundSpec("head", "gunshot", "catastrophic", 0), at, c.event_id, 0, s.rng)
    d = bodies.doomed(w.store, mara)
    dead_at = w.store.query_one("SELECT dead_at FROM bodies WHERE body_id = ?", (mara,))[0]
    assert d["kind"] == "instant" and d["doomed_at"] == d["expected_at"] == d["death_by"] == dead_at
    doom_ev = w.store.query_one("SELECT event_id, seq FROM events WHERE type = 'DOOM' AND actor_id = ?", (mara,))
    death_seq = w.store.query_one("SELECT seq FROM events WHERE type = 'DEATH' AND json_extract(payload, '$.body_id') = ?", (mara,))[0]
    assert doom_ev[1] < death_seq, "just before the death"
    assert not w.store.query("SELECT 1 FROM events WHERE type = 'NOISE' AND cause_event_id = ?", (doom_ev[0],)), "no time to scream"


def test_the_strain_is_known_minutes_ahead(night, fake):
    """DOOM-02."""
    w, s = night
    mara = w.id("mara")
    pw = w.store.canon.find("pathway", "wet")
    t = now(w)
    exposed = t - int(pw.death_at_h * 3_600_000) + 3 * 60_000
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=0, payload={"what": "test"}))
    w.store.conn.execute("INSERT INTO infections (body_id, pathway, exposed_at, stage, cause_event) VALUES (?, 'wet', ?, ?, ?)",
                         (mara, exposed, pw.stages[-1].name, c.event_id))
    w.store.conn.execute("UPDATE bodies SET progressed_at = ? WHERE body_id = ?", (t, mara))
    with w.store.transaction() as tx:
        bodies.progress(tx, mara, t + 60_000, 0, s.rng)
    d = bodies.doomed(w.store, mara)
    assert d["kind"] == "infection" and d["death_by"] == d["expected_at"] == exposed + int(pw.death_at_h * 3_600_000)
    assert d["cause_event"] == c.event_id


def test_the_untouchable_are_never_doomed(night, fake):
    """DOOM-01: nobody in god mode, nobody in the reality exception."""
    w, s = night
    mara, alice = w.id("mara"), w.id("alice")
    assert cheat_ok(s, "/god on mara").ok
    with w.store.transaction() as tx:
        bodies.grant_exception(tx, alice, now(w), 0, origin="cheat")
    cut(w, s, mara, "arm_l", "severe", blood=39.5)
    cut(w, s, alice, "arm_l", "severe", blood=39.5)
    assert bodies.doomed(w.store, mara) is None and bodies.doomed(w.store, alice) is None


def test_nothing_undoes_a_doom(night, fake):
    """DOOM-08: the power is Willis's, and the Voice is above him."""
    w, s = night
    mara = w.id("mara")
    cut(w, s, mara, "arm_l", "severe", blood=38.5)
    for line in ("/heal mara", "/god on mara", "/cure mara"):
        r = cheat_ok(s, line)
        assert not r.ok and r.persona_line == cheats.DOOM_REFUSAL, line
    assert w.store.query("SELECT 1 FROM wounds WHERE body_id = ? AND healed_at IS NULL", (mara,))


def test_a_doom_made_between_turns_plays_at_the_next_moment(night, fake):
    """VOICE-07: the console (or anything between turns) dooms the PC — the scene comes with the next
    moment, once, and the death screen reads it from there."""
    w, s = night
    cut(w, s, s.pc_id, "chest", "catastrophic", blood=25)
    d = bodies.doomed(w.store, s.pc_id)
    assert d is not None and voice.scene_turn(w.store, s.pc_id) is None
    fake.fail(CallClass.WILLIS_ROAST, "unavailable")
    fake.script(CallClass.INTAKE, lambda q: {"choice": pick(w, q, "wait_here"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    out = play(s, "do", "I press on the wound.")
    assert out.ok and out.turn_index > d["turn_index"] and out.doom and out.doom[0].text == voice.FREEZE_TEXT
    assert voice.scene_turn(w.store, s.pc_id) == out.turn_index
    assert death.roast_stored(w.store, s.pc_id) == [b.text for b in out.doom if b.kind == "willis"]
    if not out.died:
        fake.script(CallClass.INTAKE, lambda q: {"choice": pick(w, q, "wait_here"), "none_reason": None, "manner": "",
                                                "remainder": None, "clarify": None})
        again = play(s, "do", "I wait.")
        assert again.doom == [], "once"


def test_the_scene_never_costs_the_turn(night, fake, monkeypatch):
    """VOICE-07: whatever goes wrong in the scene, the moment still happens, and the failure is logged."""
    w, s = night

    async def broken(session):
        raise RuntimeError("the dark did not come")
    monkeypatch.setattr(voice, "doom_scene", broken)
    out = dies(w, s, fake)
    assert out.ok and out.doom == [] and out.narration
    assert w.store.query("SELECT 1 FROM error_repair_log WHERE rule_id = 'VOICE-07' AND kind = 'degraded'")


def test_revived_the_doom_is_spent(night, fake):
    """DOOM-08's other side: the console cannot stop a doom, but a death fulfils it — /revive brings back
    a body that owes nothing and screams no more."""
    w, s = night
    mara = w.id("mara")
    at = cut(w, s, mara, "arm_l", "severe", blood=38.5)
    assert bodies.forced(w.store, mara, at) == "screams"
    with w.store.transaction() as tx:
        bodies.progress(tx, mara, at + 10 * 60_000, 0, s.rng)
    assert w.store.query_one("SELECT alive FROM bodies WHERE body_id = ?", (mara,))[0] == 0
    assert cheat_ok(s, f"/revive {w.store.query_one('SELECT display_name FROM actors WHERE actor_id = ?', (mara,))[0]}").ok
    t = now(w)
    assert bodies.doomed(w.store, mara) is None and bodies.forced(w.store, mara, t) is None
    with w.store.transaction() as tx:
        bodies.progress(tx, mara, t + 5 * 60_000, 0, s.rng)
    assert w.store.query_one("SELECT alive FROM bodies WHERE body_id = ?", (mara,))[0] == 1
    assert not w.store.query("SELECT 1 FROM error_repair_log WHERE rule_id = 'DOOM-05'"), "no safety net"


def test_the_safety_net_is_a_bug_when_it_fires(night, fake):
    """DOOM-05: a doomed body the world somehow spared still dies — and the log says it was a bug."""
    w, s = night
    mara = w.id("mara")
    at = cut(w, s, mara, "arm_l", "severe", blood=38.5)
    d = bodies.doomed(w.store, mara)
    w.store.conn.execute("UPDATE wounds SET healed_at = ?, clotted = 1 WHERE body_id = ?", (at, mara))
    with w.store.transaction() as tx:
        bodies.progress(tx, mara, d["death_by"] + 3 * 60_000, 0, s.rng)
    assert w.store.query_one("SELECT alive FROM bodies WHERE body_id = ?", (mara,))[0] == 0
    assert w.store.query("SELECT 1 FROM error_repair_log WHERE rule_id = 'DOOM-05'")


# =========================================================================== the scene
def test_the_doom_scene_plays_before_the_moment_s_narration(night, fake):
    """VOICE-01, VOICE-07: freeze, dark, footsteps, Willis, the snatch, nothing, the Voice, the dust."""
    w, s = night
    out = dies(w, s, fake)
    kinds = [b.kind for b in out.doom]
    assert kinds[:3] == ["scene", "scene", "scene"] and kinds[-1] == "scene"
    assert out.doom[0].text == voice.FREEZE_TEXT and out.doom[1].text == voice.DARK_TEXT and out.doom[1].pause_ms == 3000
    assert out.doom[2].text == voice.STEPS_TEXT
    i = kinds.index("snatch")
    assert kinds[3:i] == ["willis"] * (i - 3) and i > 3 and out.doom[i].pause_ms == 250
    assert out.doom[i + 1].text == voice.ALONE_TEXT
    assert kinds[i + 2:-1] == ["voice"] * (len(kinds) - i - 3) and len(kinds) - i - 3 >= 1
    assert out.doom[-1].text == voice.RESUME_TEXT
    story = [(r[0], r[1]) for r in w.store.query("SELECT kind, text FROM story_log WHERE turn_index = ? ORDER BY entry_id",
                                                 (out.turn_index,))]
    assert story[0][0] == "player" and story[-1][0] == "narration"
    assert [k for k, _ in story[1:-1]] == [{"willis": "willis", "voice": "voice"}.get(b.kind, "doom") for b in out.doom]
    assert w.store.query("SELECT 1 FROM percept_log WHERE holder_id = ? AND text = 'You are screaming.'", (s.pc_id,))
    doom_ev = w.store.query_one("SELECT event_id FROM events WHERE type = 'DOOM' AND actor_id = ?", (s.pc_id,))[0]
    assert w.store.query("SELECT 1 FROM percept_log p JOIN events e ON e.event_id = p.event_id WHERE p.holder_id = ? "
                         "AND e.type = 'NOISE' AND e.cause_event_id = ?", (w.id("mara"),  doom_ev)), "the room hears it"


def test_willis_knows_who_he_is_talking_to(night, fake):
    """VOICE-02, DEATH-14: a stranger to him gets "why am I here?", cut off mid-sentence."""
    w, s = night
    out = dies(w, s, fake)
    lines = [b.text for b in out.doom if b.kind == "willis"]
    assert lines == ["Huh.", "Why am I here? I don't know you. Who even are—"]


def test_in_his_debt_he_mocks_twice_as_hard(night, fake):
    """D-106: the console is Willis's power on loan."""
    w, s = night
    assert cheat_ok(s, "/give ammo_38 1").ok
    fake.script(CallClass.WILLIS_ROAST, {"lines": [f"line {i}" for i in range(6)]})
    out = dies(w, s, fake)
    f = fake.calls(CallClass.WILLIS_ROAST)[-1].context.facts
    assert f.in_debt is True and f.borrowed == ["/give ammo_38 1"]
    assert [b.text for b in out.doom if b.kind == "willis"] == [f"line {i}" for i in range(6)], "six lines, not three"
    lines = death.fallback_roast(f)
    assert len(lines) == 6 and lines[0] == "Well, well, well. Look who's in my debt." and lines[-1].endswith("—")
    assert "'/give ammo_38 1'" in lines[1]


def test_he_remembers_the_ones_he_met(night, fake):
    w, s = night
    with w.store.transaction() as tx:
        bodies.grant_exception(tx, w.id("mara"), now(w), 0, origin="cheat")
    fake.fail(CallClass.WILLIS_ROAST, "unavailable")
    out = dies(w, s, fake, by=w.id("mara"))
    lines = [b.text for b in out.doom if b.kind == "willis"]
    assert lines[0] == "Oh, it's you from earlier." and "Yeah, that was me, by the way. Worth it." in lines


def test_the_voice_brags_only_with_the_record(night, fake):
    """VOICE-03..06: the chain, the clue they felt and could not place, what was near them, the upper
    hand — and never how."""
    w, s = night
    mara = w.id("mara")
    fake.script(CallClass.THE_VOICE, {"paragraphs": ["  Oh, my dear fool.  ", "", "Dominoes."]})
    out = dies(w, s, fake, by=mara)
    assert [b.text for b in out.doom if b.kind == "voice"] == ["Oh, my dear fool.", "Dominoes."]
    req = fake.calls(CallClass.THE_VOICE)[-1]
    f = req.context.facts
    assert req.context.moment == "before" and f.manner is None and f.seconds_left >= 0
    assert ChainBeat(when=f.chain[0].when, kind="clue", text=CUT) in f.chain
    names = {r[0] for r in w.store.query("SELECT display_name FROM actors WHERE actor_id = ?", (mara,))}
    assert f.threat in names and f.threat_near is not None
    assert f.threat not in f.upper_hand


def test_the_voice_without_a_model():
    """VOICE-08."""
    f = VoiceFacts(pc_name="Owen Marsh", lived="2 days", seconds_left=30,
                   chain=[ChainBeat(when="day 210, 21:40", kind="choice", text="Fire at the dog", said="I shoot the dog."),
                          ChainBeat(when="day 211, 03:12", kind="clue", text="Something creaks in the stockroom.")],
                   threat="a lurker", threat_near="6 hours", upper_hand=["revolver", "Mara"])
    first, second, third = voice.fallback_voice("before", f)
    assert first == voice.ARCHITECT
    assert 'day 210, 21:40: you chose to fire at the dog, thinking "I shoot the dog."' in second
    assert 'There was "Something creaks in the stockroom". You noticed it. You did nothing.' in second
    assert "I gave you revolver and Mara. And still." in second
    assert third == ("Did you know a lurker has been in here with you? For 6 hours. You never noticed. In about 30 seconds you "
                     "are going to die. I won't tell you how. You should have paid more attention. Like I did.")
    after = voice.fallback_voice("after", f.model_copy(update={"manner": "You bled to death.", "seconds_left": 0}))
    assert after == ["And that is how. You bled to death. Every piece had a cause. Every piece was mine."]


def test_the_voice_has_no_name():
    """VOICE-06 / D-106: canon kept out of the game — no prompt, scene text or fallback names the Voice,
    and nothing in them says what the console is."""
    import re
    from pathlib import Path

    import as_engine
    prompts = Path(as_engine.__file__).parent / "prompts"

    def read(*names):
        return [f.read_text(encoding="utf-8") for f in sorted(prompts.glob("*.j2")) if f.name.split(".")[0] in names]
    persona = read("cheat_persona")
    texts = read("the_voice", "willis_roast", "doom_guard")
    assert len(persona) == 2 and len(texts) == 6
    f = VoiceFacts(pc_name="Owen Marsh", lived="2 days", seconds_left=30, threat="a lurker", threat_near="6 hours")
    texts += [voice.FREEZE_TEXT, voice.FIGHT_TEXT, voice.DARK_TEXT, voice.STEPS_TEXT, voice.SNATCH_TEXT, voice.ALONE_TEXT,
              voice.RESUME_TEXT, voice.RESUME_INSTANT_TEXT, DOOMED_WORDS, *voice.fallback_voice("before", f)]
    assert not any(re.search(r"\bcodex\b", t, re.I) for t in texts + persona)
    assert not any(re.search(r"\b(sandbox|cheats?|console)\b", t, re.I) for t in texts)


@pytest.mark.parametrize("s,words", [(0, "this very instant"), (4, "a few seconds"), (30, "about 30 seconds"),
                                     (89, "about 89 seconds"), (100, "about 2 minutes"), (1500, "about 25 minutes"), (7200, "about 2 hours")])
def test_how_long_they_have(s, words):
    assert voice.when_words(s) == words


# =========================================================================== the doomed cannot tell
def test_the_doomed_cannot_tell(night, fake):
    """DOOM-07: rejected outright — anything about the end that ordinary people don't know."""
    w, s = night
    cut(w, s, s.pc_id, "chest", "catastrophic", blood=25)
    assert bodies.doomed(w.store, s.pc_id) is not None, "15% to go at 1.2% a minute even packed: 12.5 minutes"
    t0 = now(w)
    fake.script(CallClass.DOOM_GUARD, {"tells": True})
    out = play(s, "say", "Mara, a voice just told me I have thirty seconds left.")
    assert (out.ok, out.rejected_code, out.rejected_message) == (False, "doomed_words", DOOMED_WORDS)
    assert fake.calls(CallClass.DOOM_GUARD)[-1].context.text == "Mara, a voice just told me I have thirty seconds left."
    fake.fail(CallClass.DOOM_GUARD, "unavailable")
    out = play(s, "say", "It whispered to me. It told me.")
    assert out.rejected_code == "doomed_words", "the fallback check"
    assert now(w) == t0, "no time passes"
    fake.fail(CallClass.DOOM_GUARD, "unavailable")
    assert play(s, "say", "Mara. I'm hurt bad.").ok, "ordinary words still get out"
