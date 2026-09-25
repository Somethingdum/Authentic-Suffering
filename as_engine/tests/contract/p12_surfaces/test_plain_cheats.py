"""Plain-words cheats and the Act / Say / Cheat input (P12). Rules CHEAT-16..19; DECISIONS D-103
(cheats/interpret.py; physical/bodies.py force_act, forced, blast; world/infected.py step;
turn/cognition; turn/intake.py addressee_for; service/game_service.py on_turn_compose).

The owner: "The whole schtick with cheats in the Narrative game is that you can do ANYTHING ... I want
to be able to say 'Make that infected jig joyously' and have it happen." The console turns plain words
into what the world can do, names things the way the Boss's character would, asks back when it cannot
tell which one, and shows — and says it shows — what the world has no rules for.
"""

from __future__ import annotations

import asyncio

import pytest
from protocol_kit import actions, only, send
from slice_kit import pick, play

from as_engine.cheats import commands as cheats
from as_engine.cheats import interpret
from as_engine.contracts.common import CallClass
from as_engine.physical import bodies

pytestmark = pytest.mark.phase(12)


def plain(s, text):
    if s.store.meta("cheat_active") != "1":
        cheats.activate(s)
    return asyncio.run(interpret.run(s, text))


def handle(req, *, kind=None, label=None, note=None):
    sc = req.context.scene
    for p in sc.people:
        if (kind is None or p.kind == kind) and (label is None or label in p.label) and (note is None or note in p.note):
            return p.handle
    raise KeyError((kind, label, note, [(p.handle, p.label, p.kind, p.note) for p in sc.people]))


def plan(*ops, clarify=None):
    return {"ops": list(ops), "clarify": clarify, "summary": ""}


def shambler_in_front(w, s):
    """A shambler a step from Owen, and Owen looking at it."""
    assert cheat_ok(s, "/spawn shambler")
    sh = w.store.query_one("SELECT body_id FROM bodies WHERE kind = 'infected' AND origin = 'cheat'")[0]
    w.store.conn.execute("UPDATE actors SET attention_target = ? WHERE actor_id = ?", (sh, s.pc_id))
    return sh


def cheat_ok(s, line):
    if s.store.meta("cheat_active") != "1":
        cheats.activate(s)
    return asyncio.run(cheats.execute(s, cheats.parse(line))).ok


def test_the_scene_is_the_boss_s_side_of_the_glass(night, fake):
    """CHEAT-16: handles for what the Boss's character sees and knows; what it looks at is marked."""
    w, s = night
    sh = shambler_in_front(w, s)
    with w.store.transaction() as tx:
        sc = interpret.scene(tx, s)
    assert sc.me.handle == "P0" and sc.here.handle == "L0"
    (mine,) = [p for p in sc.people if "looking at" in p.note]
    assert mine.kind == "infected"
    assert "Mara" in [p.label for p in sc.people], "known by name"
    assert sc.makeable and sc.spawnable and "wet" in sc.strains
    assert sh


def test_make_that_infected_jig_joyously(night, fake):
    """CHEAT-19: the one the Boss is looking at jigs, and does nothing else while it does — seen by the
    Boss's character, on the record, a Sandbox."""
    w, s = night
    sh = shambler_in_front(w, s)
    fake.script(CallClass.CHEAT_INTERPRET, lambda r: plan({"op": "force", "who": handle(r, kind="infected", note="looking at"),
                                                           "text": "jigs joyously", "n": 10}))
    r = plain(s, "Make that infected jig joyously")
    assert r.ok and "jigs joyously for 10 minutes" in r.detail
    at = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        assert bodies.forced(tx, sh, at) == "jigs joyously"
        assert bodies.forced(tx, sh, at + 11 * 60_000) is None
    (log,) = [x for x in w.store.query("SELECT command FROM cheat_log") if x[0] == "Make that infected jig joyously"]
    assert log and w.store.meta("sandbox") == "1"
    fake.script(CallClass.INTAKE, lambda q: {"choice": pick(w, q, "observe_area"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    assert play(s, "do", "I watch it.").ok
    seen = [x[0] for x in w.store.query("SELECT text FROM percept_log WHERE holder_id = ? AND turn_index = 1", (s.pc_id,))]
    assert [t for t in seen if t.endswith("jigs joyously.")], seen
    assert not w.store.query("SELECT 1 FROM events WHERE type = 'HARM' AND actor_id = ? AND turn_index = 1", (sh,))


def test_which_one_is_asked_back(night, fake):
    """CHEAT-17: when it cannot tell which one, it asks, and nothing is written."""
    w, s = night
    fake.script(CallClass.CHEAT_INTERPRET, lambda r: plan(clarify="Which one, Boss — Mara or June?"))
    r = plain(s, "Make her dance")
    assert not r.ok and r.persona_line == "Which one, Boss — Mara or June?"
    assert not w.store.query("SELECT 1 FROM cheat_log") and w.store.meta("sandbox") != "1"


def test_a_bad_step_runs_nothing(night, fake):
    """CHEAT-17: every step is checked before any runs."""
    w, s = night
    fake.script(CallClass.CHEAT_INTERPRET, lambda r: plan({"op": "hurt", "who": handle(r, label="Mara")}, {"op": "kill", "who": "P99"}))
    r = plain(s, "Hurt Mara and kill the ghost")
    assert not r.ok and r.persona_line.startswith("I got tangled up at step 2, Boss:")
    assert not w.store.query("SELECT 1 FROM wounds WHERE body_id = ?", (w.id("mara"),))
    assert not w.store.query("SELECT 1 FROM cheat_log")


def test_something_impossible_halfway_undoes_the_rest(night, fake):
    w, s = night
    fake.script(CallClass.CHEAT_INTERPRET, lambda r: plan({"op": "hurt", "who": handle(r, label="Mara")},
                                                          {"op": "revive", "who": handle(r, label="June")}))
    r = plain(s, "Hurt Mara, then bring June back")
    assert not r.ok and "breathing" in r.persona_line
    assert not w.store.query("SELECT 1 FROM wounds WHERE body_id = ?", (w.id("mara"),)), "all or nothing"


def test_anyone_anywhere_and_anything_in_their_heads(night, fake):
    """CHEAT-17: several steps in the order asked, each through the world's own rules."""
    w, s = night
    mara, june, alice = w.id("mara"), w.id("june"), w.id("alice")
    elsewhere = w.store.query_one("SELECT p.place_id FROM places p WHERE p.place_id != (SELECT place_id FROM positions "
                                  "WHERE body_id = ?) ORDER BY p.place_id LIMIT 1", (s.pc_id,))[0]

    def answer(r):
        places = {p.label: p.handle for p in r.context.scene.places}
        far = next(h for h in places.values() if h != "L0")
        return plan({"op": "teleport", "who": handle(r, label="Mara"), "to": far},
                    {"op": "believe", "who": handle(r, label="June"), "text": "The back gate is unlocked.", "target": "L0"},
                    {"op": "feel", "who": handle(r, label="Alice"), "target": "P0", "stat": "trust", "n": 2},
                    {"op": "make", "item": r.context.scene.makeable[0], "n": 1, "to": "L0"})
    fake.script(CallClass.CHEAT_INTERPRET, answer)
    here = w.store.query_one("SELECT place_id FROM positions WHERE body_id = ?", (mara,))[0]
    r = plain(s, "Put Mara somewhere else, make June think the back gate is open, make Alice trust me, and drop something here")
    assert r.ok and len(r.detail.splitlines()) == 4
    assert w.store.query_one("SELECT place_id FROM positions WHERE body_id = ?", (mara,))[0] != here
    assert w.store.query("SELECT 1 FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id WHERE h.holder_id = ? "
                         "AND p.text = 'The back gate is unlocked.' AND h.superseded_by IS NULL", (june,))
    assert (w.store.query_one("SELECT trust FROM relationships WHERE from_id = ? AND to_id = ?", (alice, s.pc_id)) or [0])[0] >= 2
    assert elsewhere
    (row,) = w.store.query("SELECT command FROM cheat_log")
    assert row[0].startswith("Put Mara somewhere else")


def test_a_blast(night, fake):
    """CHEAT-19: wounds by distance, doors blown open, and a bang the district hears."""
    w, s = night
    mara = w.id("mara")
    fake.script(CallClass.CHEAT_INTERPRET, lambda r: plan({"op": "blast", "to": handle(r, label="Mara"), "size": "large"}))
    r = plain(s, "Blow Mara up")
    assert r.ok
    sev = w.store.query_one("SELECT severity FROM wounds WHERE body_id = ? ORDER BY wound_id DESC", (mara,))[0]
    assert sev == "catastrophic"
    assert w.store.query("SELECT 1 FROM events WHERE type = 'NOISE' AND json_extract(payload, '$.kind') = 'blast' "
                         "AND json_extract(payload, '$.source_db') = 180")


def test_what_the_world_cannot_hold_is_shown_and_said_so(night, fake):
    """CHEAT-18: a show happens as the next moment begins — everyone there sees it, the story tells it
    — and the Boss is told it was only a show."""
    w, s = night
    fake.script(CallClass.CHEAT_INTERPRET, lambda r: plan({"op": "show", "text": "confetti pours out of the ceiling"}))
    r = plain(s, "Make it rain confetti")
    assert r.ok and "a show" in r.detail
    fake.script(CallClass.INTAKE, lambda q: {"choice": pick(w, q, "observe_area"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    assert play(s, "do", "I look up.").ok
    got = w.store.query("SELECT holder_id FROM percept_log WHERE text = 'Confetti pours out of the ceiling.' AND turn_index = 1")
    holders = {x[0] for x in got}
    assert s.pc_id in holders and len(holders) > 1
    lines = [ln.text for ln in fake.calls(CallClass.NARRATION)[-1].context.lines]
    assert "Confetti pours out of the ceiling." in lines


# =========================================================================== Act / Say / Cheat
def test_say_knows_who_it_is_for(night, scenario, fake):
    """D-103 (INTAKE addressee_for): with no chip chosen, a name the words start with picks the
    listener — in Say, or in the quoted words of an Act — when that one is here; otherwise the words
    go to the last one spoken to, and the view offers that one first."""
    import json

    from as_engine.service.view import build_view

    def heard(world, turn):
        (mapped,) = world.store.query_one("SELECT mapped FROM player_inputs WHERE turn_index = ?", (turn,))
        return (json.loads(mapped) if isinstance(mapped, str) else mapped)["addressee"]

    w, s = night
    mara = w.id("mara")
    assert play(s, "say", "Mara, keep it shut.").ok
    assert heard(w, 1) == mara
    assert play(s, "say", "June, get in here.").ok           # June is in the stockroom
    assert heard(w, 2) == mara
    with s.store.transaction() as tx:
        v = build_view(tx, s)
    assert s.extras["view_refs"][v.say_to] == mara

    w2 = scenario("metal_fence")
    s2 = w2.session()
    assert play(s2, "do", '"Mara: watch the counter."').ok
    assert heard(w2, 1) == w2.id("mara")


async def test_act_say_cheat_in_one_message(svc, make_run, fake):
    """D-103: the Cheat field is not there until the word; Act and Say are one moment; Say knows who
    it is for."""
    await send(svc, "run_load", run_id=make_run())
    assert only(await send(svc, "view_get"), "view")["view"]["console"] is False
    r = await send(svc, "turn_compose", cheat="make me rich")
    assert actions(r) == ["turn_rejected"] and only(r, "turn_rejected")["reason_code"] == "empty", "no console, no field"
    r = await send(svc, "turn_compose", cheat="2508")
    assert actions(r) == ["cheat_activated", "story"]
    assert only(await send(svc, "view_get"), "view")["view"]["console"] is True
    r = await send(svc, "turn_compose", cheat="/give ammo_38 1")
    assert only(r, "cheat_result")["ok"] is True
    assert only(await send(svc, "turn_compose"), "turn_rejected")["reason_code"] == "empty"
