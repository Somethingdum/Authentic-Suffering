"""The Doom, deepened (P12). Rules DOOM-09..15, RES-06..07, RESOLVE-07; DECISIONS D-107
(physical/bodies.py; mind/resolve.py; action/resolve.py; turn/cognition.py despair; service/voice.py;
lore the_screaming; affordances despair.yaml).

The owner: "Nobody knows why the people scream before dying. It has no in world explanation. But it
only started after the Fall. It's a bizarre unexplained occurrence that happens to most people, some
short period before they die." "The talk ... usually breaks the mind of the victim. They have little
capacity to speak or act rationally." "Codex is a cruel god, and had on numerous occasions 'Doomed'
someone after being bitten. So they have to go through all 4 weeks ... Either that, or they can't
take it and kill themselves (real reaction)."
"""

from __future__ import annotations

import json

import pytest
from slice_kit import pick, play

from as_engine.contracts.common import CallClass
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception, resolve
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import MIND_LINES
from as_engine.physical import bodies
from as_engine.physical.bodies import WoundSpec
from as_engine.service import death, voice
from as_engine.turn import timers

pytestmark = pytest.mark.phase(12)

H = 3_600_000
DAY = 24 * H


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def cut(w, s, body, anatomy, severity, *, blood=None):
    """A wound on ``body`` now (its blood already at ``blood`` when given)."""
    if blood is not None:
        w.store.conn.execute("UPDATE bodies SET blood_loss_pct = ? WHERE body_id = ?", (blood, body))
    with w.store.transaction() as tx:
        at = tx.query_one("SELECT now_ms FROM world_clock")[0]
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=at, turn_index=0, payload={"what": "test"}))
        bodies.apply_harm(tx, body, WoundSpec(anatomy, "cut", severity, 0), at, c.event_id, 0, s.rng)
    return at


def rules(w, **harm):
    R = w.store.rules
    w.store.rules = R.model_copy(update={"harm": R.harm.model_copy(update=harm)})


def mind(w, which):
    """What the talk will leave: 'shattered', 'broken' or 'held'."""
    rules(w, doom_held_base={"held": 1.0}.get(which, 0.0), doom_held_per_resolve=0.0, doom_held_max=1.0,
          doom_shatter_share=1.0 if which == "shattered" else 0.0)


def resolve_of(w, who):
    return w.store.query_one("SELECT resolve_cur FROM actors WHERE actor_id = ?", (who,))[0]


def bitten(w, s, who):
    """A bite that takes (the wet strain) — and Codex's cruelty, forced (DOOM-12)."""
    rules(w, doom_bite_chance=1.0)
    for k in range(8):
        with w.store.transaction() as tx:
            at = tx.query_one("SELECT now_ms FROM world_clock")[0]
            c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=at, turn_index=0, payload={"what": f"bite {k}"}))
            bodies.expose(tx, s.rng, who, "wet", "bite", at, c.event_id, 0)
        if bodies.doomed(w.store, who) is not None:
            return at, c.event_id
    raise AssertionError("the bite never took")


def alive(w, who):
    return w.store.query_one("SELECT alive FROM bodies WHERE body_id = ?", (who,))[0] == 1


def offscreen(w, s, ms):
    with w.store.transaction() as tx:
        timers.run_offscreen(tx, s.rng, now(w) + ms, 0)


# =========================================================================== the screaming
def test_most_people_scream_a_short_while_before_they_die(night, fake):
    """DOOM-09: not at the doom — a short while before the end; the room hears the scream everyone knows."""
    w, s = night
    june = w.id("june")
    rules(w, doom_scream_chance=1.0, doom_scream_lead_s=(60, 60))
    at = cut(w, s, june, "chest", "severe", blood=32)
    d = bodies.doomed(w.store, june)
    assert d["kind"] == "bleeding" and d["scream_at"] == d["expected_at"] - 60_000 and d["scream_at"] > at
    assert not d["screaming"] and bodies.forced(w.store, june, at) is None, "not yet"
    with w.store.transaction() as tx:
        bodies.progress(tx, june, d["scream_at"] - 1000, 0, s.rng)
    assert not bodies.doomed(w.store, june)["screaming"]
    with w.store.transaction() as tx:
        bodies.progress(tx, june, d["scream_at"] + 1000, 0, s.rng)
    assert bodies.doomed(w.store, june)["screaming"] == 1
    doom_ev = w.store.query_one("SELECT event_id FROM events WHERE type = 'DOOM' AND actor_id = ?", (june,))[0]
    (payload, t) = w.store.query_one("SELECT payload, at FROM events WHERE type = 'NOISE' AND cause_event_id = ?", (doom_ev,))
    assert t == d["scream_at"] and json.loads(payload)["text"] == "the scream people make before they die"
    assert bodies.forced(w.store, june, d["scream_at"]) == "screams"
    assert w.store.query("SELECT 1 FROM percept_log WHERE holder_id = ? AND text = 'You are screaming.'", (june,))


def test_some_never_scream(night, fake):
    """DOOM-09: most people — not everyone."""
    w, s = night
    june = w.id("june")
    rules(w, doom_scream_chance=0.0)
    at = cut(w, s, june, "chest", "severe", blood=32)
    assert bodies.doomed(w.store, june)["scream_at"] is None
    with w.store.transaction() as tx:
        bodies.progress(tx, june, at + 40 * 60_000, 0, s.rng)
    assert not alive(w, june)
    assert not w.store.query("SELECT 1 FROM events WHERE type = 'NOISE' AND actor_id = ? AND json_extract(payload, '$.kind') = "
                             "'screaming'", (june,))


def test_everyone_knows_the_scream_and_nothing_more(night, fake):
    """DOOM-09: public knowledge since the Fall — the lore, the cue — and no hint of why."""
    w, _s = night
    lore = w.store.canon.find("lore", "the_screaming")
    common = [b.text for b in lore.beliefs if b.held_by == "common"]
    assert "Since the Fall, people scream before they die. Nobody knows why." in common
    assert any("knows_the_screaming" in b.cues for b in lore.beliefs)
    text = " ".join([lore.truth, lore.body or "", *(b.text for b in lore.beliefs)]).lower()
    assert "voice" not in text and "codex" not in text and "willis" not in text


# =========================================================================== the talk breaks the mind
@pytest.mark.parametrize("which", ["shattered", "broken", "held"])
def test_what_the_talk_leaves(night, fake, which):
    """DOOM-10, RES-06, RES-07."""
    w, s = night
    mara = w.id("mara")
    mind(w, which)
    r0 = resolve_of(w, mara)
    bitten(w, s, mara)
    assert bodies.mind_of(w.store, mara) == which
    r1 = resolve_of(w, mara)
    assert r1 == {"shattered": 0, "broken": min(r0, 1), "held": max(0, r0 - 2)}[which]
    assert resolve.ceiling(w.store, mara) == {"shattered": 0, "broken": 1, "held": None}[which]
    with w.store.transaction() as tx:
        resolve.recover(tx, mara, "safe_night", None, now(w), 0)
        resolve.recover(tx, mara, "safe_night", None, now(w), 0)
    r2 = resolve_of(w, mara)
    assert r2 == {"shattered": 0, "broken": 1, "held": min(r0, r1 + 2)}[which], "it never comes back further"


def test_a_shattered_mind_s_first_hours(night, fake):
    """DOOM-11: after the first hours it can come back to 1 — never further."""
    w, s = night
    mara = w.id("mara")
    mind(w, "shattered")
    at, _ = bitten(w, s, mara)
    offscreen(w, s, 5 * H)
    assert resolve_of(w, mara) == 0 and not bodies.doomed(w.store, mara)["shock_over"]
    offscreen(w, s, 2 * H)
    assert bodies.doomed(w.store, mara)["shock_over"] == 1 and resolve_of(w, mara) == 1
    assert w.store.query("SELECT 1 FROM events WHERE type = 'RESOLVE_CHANGE' AND json_extract(payload, '$.reason') = 'shock_passes'")


def test_a_broken_mind_feels_it_and_knows_nothing(night, fake):
    """DOOM-10, DOOM-06: the packet says how it feels from inside — never what happened."""
    from as_engine.contracts.common import LOD
    from as_engine.mind.packet import build_packet
    w, s = night
    mara = w.id("mara")
    mind(w, "broken")
    bitten(w, s, mara)
    with w.store.transaction() as tx:
        affs = enumerate_affordances(tx, mara, tx.canon.all("affordance"), now(w), 0)
        pk = build_packet(tx, mara, LOD.HOT, affs, 0, now(w))
    assert MIND_LINES["broken"] in pk.body_lines
    known = " ".join([*pk.body_lines, *(b.text for b in pk.beliefs), *(m.text for m in pk.memories), *pk.lessons]).lower()
    assert not any(x in known for x in ("voice", "doom", "willis", "dominoes")), "how it feels, never what happened"


def test_words_come_out_in_pieces(night, fake):
    """RESOLVE-07, DOOM-13: a shattered mind always; a broken one in its first hours."""
    from as_engine.action.resolve import broken_words
    w, s = night
    with w.store.transaction() as tx:
        out = broken_words(tx, s.rng, "x", "Mara, get to the roof right now, they're coming.", 0)
    pieces = out.rstrip("—").split("— ")
    assert out.endswith("—") and 1 <= len(pieces) <= 5
    assert pieces[0] == "Mara" and all(p in ("Mara", "get", "to", "the") for p in pieces)
    mara = w.id("mara")
    mind(w, "broken")
    at, _ = bitten(w, s, mara)
    assert bodies.speaks_broken(w.store, mara, at) and not bodies.speaks_broken(w.store, mara, at + 7 * H)


def test_the_player_s_words_break_too(night, fake):
    """RESOLVE-07 through a turn: what the player's character says comes out in pieces."""
    w, s = night
    mind(w, "shattered")
    bitten(w, s, s.pc_id)
    fake.script(CallClass.DOOM_GUARD, {"tells": False})
    out = play(s, "say", "Mara, get to the roof right now, they're coming.")
    assert out.ok
    said = [json.loads(r[0])["words"] for r in w.store.query("SELECT payload FROM events WHERE type = 'SPEECH' AND actor_id = ? "
                                                              "ORDER BY seq", (s.pc_id,))]
    assert said and all(x.endswith("—") for x in said)


# =========================================================================== Codex's cruelty
def test_codex_dooms_some_at_the_bite(night, fake):
    """DOOM-12: four weeks to live with it."""
    w, s = night
    mara = w.id("mara")
    at, c = bitten(w, s, mara)
    d = bodies.doomed(w.store, mara)
    pw = w.store.canon.find("pathway", "wet")
    assert d["kind"] == "bitten" and d["expected_at"] == d["death_by"] == at + int(pw.death_at_h * H)
    assert d["cause_event"] == c
    assert w.store.query_one("SELECT 1 FROM event_queue WHERE type = 'DESPAIR' AND status = 'pending' AND due_at = ?",
                             (at + DAY,))


def test_the_bite_alone_is_not_a_doom(night, fake):
    """DOOM-12: numerous occasions — not every one."""
    w, s = night
    mara = w.id("mara")
    rules(w, doom_bite_chance=0.0)
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=now(w), turn_index=0, payload={"what": "bite"}))
        for _ in range(3):
            bodies.expose(tx, s.rng, mara, "wet", "bite", now(w), c.event_id, 0)
    assert bodies.doomed(w.store, mara) is None


def test_the_voice_tells_the_bitten_how_long(night, fake):
    """VOICE-03/08 with DOOM-12: about four weeks, never how."""
    w, s = night
    bitten(w, s, s.pc_id)
    f = voice.voice_facts(w.store, s.pc_id, "before")
    assert f.seconds_left == 672 * 3600 and voice.when_words(f.seconds_left) == "about 4 weeks"
    assert f.manner is None


@pytest.mark.parametrize("sec,words", [(2 * 86400, "about 2 days"), (10 * 86400, "about 10 days"),
                                       (21 * 86400, "about 3 weeks"), (100000, "about 28 hours")])
def test_how_long_in_days_and_weeks(sec, words):
    assert voice.when_words(sec) == words


@pytest.mark.parametrize("which", ["shattered", "broken", "held"])
def test_the_dust_moves_again_on_what_is_left(night, fake, which):
    """VOICE-01 step 8: what the talk left, unless the screaming already started."""
    w, s = night
    mind(w, which)
    rules(w, doom_scream_chance=0.0)
    bitten(w, s, s.pc_id)
    beats = voice.scene(w.store, s.pc_id, ["Huh."], ["Dominoes."])
    assert beats[-1].text == voice.RESUME_MIND_TEXT[which]


# =========================================================================== they can't take it
def test_they_cant_take_it(night, fake):
    """DOOM-14, DOOM-15: a check a day; with the means, a real reaction — the revolver she carries."""
    w, s = night
    mara = w.id("mara")
    mind(w, "shattered")
    rules(w, doom_despair_chance={"shattered": 1.0, "broken": 1.0, "held": 1.0})
    at, _ = bitten(w, s, mara)
    assert bodies.means(w.store, mara)[:1] == [w.store.query_one(
        "SELECT item_id FROM items WHERE holder_body = ? AND def_ref = 'core:item/revolver_38'", (mara,))[0]]
    offscreen(w, s, 23 * H)
    assert alive(w, mara), "not before the first day is out"
    offscreen(w, s, 2 * H)
    assert not alive(w, mara)
    (payload,) = w.store.query_one("SELECT payload FROM events WHERE type = 'DEATH' AND json_extract(payload, '$.body_id') = ?", (mara,))
    p = json.loads(payload)
    assert p["cause"] == "suicide" and p["method"] == "firearm"
    assert w.store.query("SELECT 1 FROM events WHERE type = 'NOISE' AND actor_id = ? AND json_extract(payload, '$.kind') = 'shoot'",
                         (mara,))


def test_or_they_go_through_all_of_it(night, fake):
    """DOOM-14: the check comes again every day it runs; without the means nothing happens."""
    w, s = night
    june = w.id("june")
    mind(w, "shattered")
    rules(w, doom_despair_chance={"shattered": 1.0, "broken": 1.0, "held": 1.0})
    at, _ = bitten(w, s, june)
    assert bodies.means(w.store, june) == []
    offscreen(w, s, 2 * DAY + H)
    assert alive(w, june)
    due = [r[0] for r in w.store.query("SELECT due_at FROM event_queue WHERE type = 'DESPAIR' AND subject_id = ? ORDER BY due_at", (june,))]
    assert due[:3] == [at + DAY, at + 2 * DAY, at + 3 * DAY]


def test_the_player_decides_for_themselves(night, fake):
    """DOOM-14, SYM-01: no roll ever takes the player's character."""
    w, s = night
    mind(w, "shattered")
    rules(w, doom_despair_chance={"shattered": 1.0, "broken": 1.0, "held": 1.0})
    bitten(w, s, s.pc_id)
    offscreen(w, s, DAY + H)
    assert alive(w, s.pc_id)
    assert not w.store.query("SELECT 1 FROM event_queue WHERE type = 'DESPAIR' AND subject_id = ? AND status = 'pending'", (s.pc_id,))


def test_end_it_is_on_the_menu_only_at_the_end_of_the_rope(night, fake):
    """DOOM-15 (requires.despair, RES-03): never for someone who can still bear it; for the doomed, and
    for anyone at Resolve 0 — even then."""
    w, s = night
    pc = s.pc_id

    def offered():
        with w.store.transaction() as tx:
            a = enumerate_affordances(tx, pc, tx.canon.all("affordance"), now(w), 0)
        return {o.def_id for o in a.pool}, {(r.def_id, r.gate) for r in a.rejected}
    got, why = offered()
    assert "end_life_firearm" not in got and ("end_life_firearm", "physical") in why
    w.store.conn.execute("UPDATE actors SET resolve_cur = 0 WHERE actor_id = ?", (pc,))
    got, _ = offered()
    assert "end_life_firearm" in got, "Resolve 0: the one thing left"
    assert "end_life_blade" not in got, "only what is in hand"


def test_the_player_can_end_it(night, fake):
    """DOOM-15 through a turn: the gun in hand; the death is theirs; the death screen says so."""
    w, s = night
    mind(w, "broken")
    rules(w, doom_scream_chance=0.0)
    bitten(w, s, s.pc_id)
    fake.script(CallClass.INTAKE, lambda q: {"choice": pick(w, q, "end_life_firearm"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    out = play(s, "do", "I put the gun to my head.")
    assert out.ok and out.died
    assert out.doom and out.doom[0].text == voice.FREEZE_TEXT, "the frozen moment comes with the next moment, even this one"
    dv = death.build_death_view(w.store, s.pc_id)
    assert dv.cause_text.startswith("You took your own life.")


def test_an_empty_gun_only_clicks(night, fake):
    """DOOM-15: they are still here."""
    w, s = night
    rules(w, doom_scream_chance=0.0)
    bitten(w, s, s.pc_id)
    gun = w.store.query_one("SELECT item_id FROM items WHERE holder_body = ? AND holder_slot = 'hand_r'", (s.pc_id,))[0]
    w.store.conn.execute("UPDATE items SET props = json_set(props, '$.rounds', 0, '$.chambered', json('false')) "
                         "WHERE item_id = ? OR container_id = ?", (gun, gun))
    with w.store.transaction() as tx:
        evs = bodies.end_own_life(tx, s.rng, s.pc_id, gun, now(w), 0, None)
    assert [json.loads(json.dumps(e.payload))["kind"] for e in evs] == ["click"] and alive(w, s.pc_id)


def test_willis_cannot_end_himself(night, fake):
    """DOOM-15: the reality exception (and god mode): nothing happens."""
    w, s = night
    with w.store.transaction() as tx:
        bodies.grant_exception(tx, s.pc_id, now(w), 0, origin="cheat")
    gun = w.store.query_one("SELECT item_id FROM items WHERE holder_body = ? AND holder_slot = 'hand_r'", (s.pc_id,))[0]
    with w.store.transaction() as tx:
        assert bodies.end_own_life(tx, s.rng, s.pc_id, gun, now(w), 0, None) == []
    assert alive(w, s.pc_id) and perception is not None
