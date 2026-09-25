"""The word in any box, and what the world never learns (P12). Rules CHEAT-01, CHEAT-03, CHEAT-06,
CHEAT-11 (service/game_service.py on_turn_submit; service/guide.py; turn/pipeline.py S4).
"""

from __future__ import annotations

import asyncio

import pytest

from as_engine.cheats import commands as cheats
from as_engine.contracts.common import CallClass
from protocol_kit import actions, only, send, wait_for
from slice_kit import play, script_night_at_delgados

pytestmark = pytest.mark.phase(12)


async def loaded(svc, make_run):
    await send(svc, "run_load", run_id=make_run())


def meta(svc, key):
    r = svc.session.store.query_one("SELECT value FROM meta WHERE key = ?", (key,))
    return None if r is None else r[0]


async def test_the_word_in_any_box(svc, make_run):
    await loaded(svc, make_run)
    r = await send(svc, "turn_submit", mode="say", text="2508")
    assert actions(r) == ["cheat_activated", "story"]
    assert only(r, "cheat_activated") == {"persona_line": cheats.ACTIVATION_LINE, "ok": True, "detail": cheats.SHIMMER_NOTICE}
    assert svc.session.store.query_one("SELECT turn_index FROM world_clock")[0] == 0, "the line is consumed: no turn"
    r = await send(svc, "turn_submit", mode="do", text="/give ammo_38 3")
    assert actions(r) == ["cheat_result", "view", "story"] and only(r, "cheat_result")["ok"] is True
    assert only(r, "view")["view"]["sandbox"] is True
    r = await send(svc, "turn_submit", mode="do", text="/nonsense")
    assert actions(r) == ["cheat_result"] and only(r, "cheat_result")["ok"] is False


async def test_before_the_word_a_slash_is_only_words(svc, make_run):
    await loaded(svc, make_run)
    r = await send(svc, "turn_submit", mode="do", text="/god on")
    assert actions(r) == ["state"], "an ordinary move"
    await wait_for(lambda: not svc.busy)
    assert meta(svc, "cheat_active") == "0" and not svc.session.store.query("SELECT 1 FROM cheat_log")


async def test_a_cheat_question_gets_the_world_back(svc, make_run, fake):
    await loaded(svc, make_run)
    await send(svc, "turn_submit", mode="ask", text="Is there a god mode I can turn on?")
    assert fake.calls(CallClass.GUIDE)[-1].context.cheat_query is True
    await send(svc, "turn_submit", mode="say", text="2508")
    await send(svc, "turn_submit", mode="ask", text="Is there a god mode I can turn on?")
    assert fake.calls(CallClass.GUIDE)[-1].context.cheat_query is False, "after the word, nothing to hide"


async def test_the_dead_can_still_be_brought_back(svc, make_run):
    await loaded(svc, make_run)
    await send(svc, "turn_submit", mode="say", text="2508")
    assert only(await send(svc, "turn_submit", mode="do", text="/kill me"), "cheat_result")["ok"] is True
    r = await send(svc, "turn_submit", mode="do", text="I get up.")
    assert only(r, "turn_rejected")["reason_code"] == "dead"
    assert only(await send(svc, "turn_submit", mode="do", text="/revive me"), "cheat_result")["ok"] is True
    assert svc.session.store.query_one("SELECT alive FROM bodies WHERE body_id = ?", (svc.session.pc_id,))[0] == 1


def cheat(s, line):
    if s.store.meta("cheat_active") != "1":
        cheats.activate(s)
    return asyncio.run(cheats.execute(s, cheats.parse(line)))


def test_fredrick_is_briefed_every_turn_he_thinks(night, fake):
    w, s = night
    assert cheat(s, "/spawn fredrick ally").ok
    fred = w.store.query_one("SELECT actor_id FROM actors WHERE display_name LIKE 'Fredrick%'")[0]
    script_night_at_delgados(w, fake)
    play(s, "do", "I watch the front window and keep quiet.")
    lod = w.store.query_one("SELECT detail FROM turn_ledger WHERE turn_index = 1 AND stage = 4")[0]
    assert fred in lod, "he stands by the Boss: he thinks this turn"
    got = w.store.query("SELECT p.predicate, h.acquired_at FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id "
                        "JOIN percept_log q ON q.holder_id = h.holder_id AND q.event_id = h.acquired_via "
                        "WHERE h.holder_id = ? AND h.provenance = 'cheat' AND q.turn_index = 1", (fred,))
    assert {g[0] for g in got} >= {"location"}, "the truth of the room, through the ordinary door"
    assert not w.store.query("SELECT 1 FROM claim_holdings WHERE provenance = 'cheat' AND holder_id != ?", (fred,)), \
        "nobody else learns anything from it"


def test_what_the_console_says_reaches_no_mind(night, fake):
    w, s = night
    told = [cheat(s, "/mind Mara").detail, cheat(s, "/reveal").detail]
    script_night_at_delgados(w, fake)
    play(s, "do", "I watch the front window and keep quiet.")
    for q in fake.calls():
        text = " ".join(m.content for m in q.messages)
        for d in told:
            for line in d.splitlines():
                assert line not in text, f"{q.call_class.value} saw the console's answer (CHEAT-06)"
