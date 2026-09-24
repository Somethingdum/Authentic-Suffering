"""Playing through the protocol (P8). Rules PROTO-02, PROTO-04..07 (service/game_service.py:
on_turn_submit, on_turn_cancel; service/guide.py).

A turn is long (up to minutes on real models) and Talemate reads one message at a time, so the
turn runs in the background: turn_submit answers at once, progress and the result are pushed,
the Stop button works until the world starts moving, and a reloaded page finds the turn still
running.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import CallClass
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.contracts.view import PlayView
from as_engine.kernel.hashing import full_state_hash
from as_engine.service import game_service, guide
from as_engine.turn.intake import NONE_MESSAGES
from as_engine.turn.pipeline import STAGE_LABELS
from protocol_kit import actions, check, error_code, only, pushed_after, send, wait_for

pytestmark = pytest.mark.phase(8)

AFTER_COMMIT = [12, 13, 16, 17, 14, 15, 19]
PER_WAVE = {3, 4, 5, 6, 7, 8, 11}


def world(svc):
    st = svc.session.store
    return {"turn": st.query_one("SELECT turn_index FROM world_clock")[0],
            "now": st.query_one("SELECT now_ms FROM world_clock")[0],
            "events": st.query_one("SELECT COUNT(*) FROM events")[0],
            "inputs": st.query_one("SELECT COUNT(*) FROM player_inputs")[0],
            "story": st.query_one("SELECT COUNT(*) FROM story_log")[0],
            "hash": full_state_hash(st)}


async def loaded(svc, make_run):
    rid = make_run()
    await send(svc, "run_load", run_id=rid)
    return rid


async def test_a_turn_runs_in_the_background_and_is_pushed(svc, make_run):
    """PROTO-04: the reply is only 'busy'; progress, the result and the story arrive as pushes."""
    rid = await loaded(svc, make_run)
    start = len(svc.pushed)
    r = await send(svc, "turn_submit", mode="do", text="I watch the front door.")
    assert actions(r) == ["state"] and only(r, "state") == {"screen": "play", "run_id": rid, "busy": True}
    await svc.idle()
    msgs = pushed_after(svc, start)
    progress = [m["data"] for m in msgs if m["action"] == "turn_progress"]
    stages = [p["stage"] for p in progress]
    assert stages[:3] == [0, 1, 2] and stages[-len(AFTER_COMMIT):] == AFTER_COMMIT
    assert set(stages[3:-len(AFTER_COMMIT)]) <= PER_WAVE and stages[3] == 3
    for p in progress:
        assert p["turn_index"] == 1 and p["label"] == STAGE_LABELS[p["stage"]]
        assert p["pct"] == round(p["stage"] / 19 * 100, 1)
    assert [p["elapsed_s"] for p in progress] == sorted(p["elapsed_s"] for p in progress)
    assert actions(msgs)[len(progress):] == ["turn_result", "story", "state"]
    res = only(msgs, "turn_result")
    view = PlayView.model_validate(res["view"])
    assert res["turn_index"] == 1 and res["narration"] and view.turn_index == 1 and svc.last_view == view
    entries = only(msgs, "story")["entries"]
    assert (entries[0]["kind"], entries[0]["mode"], entries[0]["text"]) == ("player", "do", "I watch the front door.")
    assert entries[-1] == {"turn_index": 1, "kind": "narration", "text": res["narration"], "mode": None}
    assert only(msgs, "state") == {"screen": "play", "run_id": rid, "busy": False}
    assert svc.turn_task is None and svc.turn_stage is None and not svc.busy


async def test_a_rejected_move_changes_nothing(svc, make_run, gated):
    """The intake cannot bind the words: a plain rejection with the question, and no time passes."""
    await loaded(svc, make_run)
    before = world(svc)
    gated.script(CallClass.INTAKE, {"choice": "NONE", "none_reason": "impossible", "manner": "", "remainder": None,
                                    "clarify": "Do you want to climb the fence instead?"})
    start = len(svc.pushed)
    await send(svc, "turn_submit", mode="do", text="I fly over the fence.")
    await svc.idle()
    msgs = pushed_after(svc, start)
    assert actions(msgs) == ["turn_progress", "turn_progress", "turn_rejected", "state"]
    assert only(msgs, "turn_rejected") == {"reason_code": "impossible", "message": NONE_MESSAGES["impossible"],
                                           "clarify": "Do you want to climb the fence instead?"}
    assert world(svc) == before


async def test_refusals_before_a_turn_starts(svc, make_run):
    r = await send(svc, "turn_submit", mode="do", text="I wait.")
    assert only(r, "turn_rejected") == {"reason_code": "no_run", "message": game_service.NO_RUN, "clarify": None}
    await loaded(svc, make_run)
    r = await send(svc, "turn_submit", mode="ask", text="   ")
    assert only(r, "turn_rejected")["reason_code"] == "empty"
    pc = svc.session.pc_id
    with svc.session.store.transaction() as tx:
        now = tx.query_one("SELECT now_ms FROM world_clock")[0]
        tx.commit_event(Event(type=EventType.DEATH, writer="physical.bodies", at=now, turn_index=0, actor_id=pc,
                              payload={"cause": "set up by the test"},
                              writes=[WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": pc},
                                                  values={"alive": 0})]))
    r = await send(svc, "turn_submit", mode="do", text="I get up.")
    assert only(r, "turn_rejected") == {"reason_code": "dead", "message": game_service.DEAD, "clarify": None}


async def test_one_turn_at_a_time(svc, make_run, gated):
    """PROTO-05: while a turn runs, anything that would read or change the run answers busy — except
    the view and the story, which show the moment before the turn (never the half-made one)."""
    await loaded(svc, make_run)
    before_view = svc.last_view
    gated.hold = {CallClass.NARRATION}
    await send(svc, "turn_submit", mode="do", text="I watch the front door.")
    await wait_for(lambda: gated.reached.is_set())
    assert svc.busy and only(await send(svc, "get_state"), "state")["busy"] is True
    r = await send(svc, "turn_submit", mode="say", text="Hello?")
    assert only(r, "turn_rejected") == {"reason_code": "busy", "message": game_service.BUSY, "clarify": None}
    for action, fields in (("run_save", {"slot_name": "x"}), ("run_close", {}), ("settings_set", {"patch": {"dev_mode": True}}),
                           ("run_load", {"run_id": svc.session.run_id}), ("config_set", {"patch": {"background_cognition": False}})):
        r = await send(svc, action, **fields)
        assert only(r, "error") == {"code": "busy", "message": game_service.BUSY, "recoverable": True}, action
    v = PlayView.model_validate(only(await send(svc, "view_get"), "view")["view"])
    assert v == before_view and v.turn_index == 0
    assert only(await send(svc, "story_get"), "story") == {"entries": []}
    gated.release.set()
    await svc.idle()
    assert not svc.busy and svc.last_view.turn_index == 1


async def test_stop_before_the_world_moves(svc, make_run, gated):
    """PROTO-06: Stop while the move is being read: the world, the clock and the input are exactly as
    they were, and the next move plays normally (the store transaction was rolled back)."""
    await loaded(svc, make_run)
    before = world(svc)
    gated.hold = {CallClass.INTAKE}
    start = len(svc.pushed)
    await send(svc, "turn_submit", mode="do", text="I check the back door.")
    await wait_for(lambda: gated.reached.is_set())
    assert svc.turn_stage == 1
    r = await send(svc, "turn_cancel")
    assert actions(r) == ["state"] and only(r, "state")["busy"] is False
    assert svc.turn_task is None and not svc.session.busy
    assert world(svc) == before
    assert "state" not in actions(pushed_after(svc, start)), "a cancelled turn pushes no result and no state"
    assert error_code(await send(svc, "turn_cancel")) == "nothing_to_cancel"
    gated.hold = set()
    await send(svc, "turn_submit", mode="do", text="I watch the front door.")
    await svc.idle()
    assert world(svc)["turn"] == 1 and "turn_result" in actions(pushed_after(svc, start))


async def test_too_late_to_stop(svc, make_run, gated):
    """From stage 12 on the world is being committed: Stop is refused and the result still arrives."""
    await loaded(svc, make_run)
    gated.hold = {CallClass.NARRATION}
    start = len(svc.pushed)
    await send(svc, "turn_submit", mode="do", text="I watch the front door.")
    await wait_for(lambda: gated.reached.is_set())
    assert svc.turn_stage >= 12
    r = await send(svc, "turn_cancel")
    assert only(r, "error") == {"code": "too_late", "message": game_service.TOO_LATE, "recoverable": True}
    gated.release.set()
    await svc.idle()
    assert "turn_result" in actions(pushed_after(svc, start)) and world(svc)["turn"] == 1


async def test_a_reloaded_page_reaches_the_running_turn(svc, make_run, gated):
    """PROTO-02: the tab closes mid-turn and a new one connects: it lands on the Play screen, sees the
    turn is still running, and receives its result."""
    rid = await loaded(svc, make_run)
    gated.hold = {CallClass.NARRATION}
    await send(svc, "turn_submit", mode="do", text="I watch the front door.")
    await wait_for(lambda: gated.reached.is_set())
    old = len(svc.pushed)
    svc.unsubscribe(svc.collect)
    fresh = []

    async def new_tab(msg):
        fresh.append(check(msg))
    svc.subscribe(new_tab)
    assert only(await send(svc, "hello"), "welcome")["screen"] == "play"
    assert only(await send(svc, "get_state"), "state") == {"screen": "play", "run_id": rid, "busy": True}
    gated.release.set()
    await svc.idle()
    assert len(svc.pushed) == old, "the closed tab gets nothing more"
    assert actions(fresh)[-3:] == ["turn_result", "story", "state"]


async def test_ask_is_not_a_turn(svc, make_run, gated):
    """PROTO-07 / GUIDE-01..02: the guide answers from what the character knows and the rules text; no
    time passes, nothing in the world changes, and the question and answer join the story."""
    await loaded(svc, make_run)
    before = world(svc)
    view = svc.last_view
    r = await send(svc, "turn_submit", mode="ask", text="How does bleeding work?")
    assert actions(r) == ["guide_answer", "story"]
    facts = guide.pc_facts(view, None)
    assert only(r, "guide_answer")["text"] == "Here is what you know: " + "; ".join(facts[:3])
    (req,) = gated.calls(CallClass.GUIDE)
    assert req.turn_index is None
    assert req.context.pc_facts == facts and req.context.pc_name == "Owen Marsh"
    assert req.context.rules_snippets == [guide.GUIDE_TOPICS[1][1]], "the bleeding topic"
    assert req.context.cheat_query is False
    entries = only(r, "story")["entries"]
    assert [(e["kind"], e["mode"], e["text"]) for e in entries] == [
        ("player", "ask", "How does bleeding work?"), ("guide", None, only(r, "guide_answer")["text"])]
    after = world(svc)
    assert {k: after[k] for k in ("turn", "now", "events", "inputs", "hash")} == \
           {k: before[k] for k in ("turn", "now", "events", "inputs", "hash")}
    row = svc.session.store.query_one("SELECT turn_index, call_class FROM lm_calls WHERE call_class = 'guide'")
    assert tuple(row) == (0, "guide"), "the call is logged outside any turn"


async def test_the_guide_down_is_not_an_error(svc, make_run, gated):
    """GUIDE-03."""
    await loaded(svc, make_run)
    gated.fail(CallClass.GUIDE, "timeout")
    r = await send(svc, "turn_submit", mode="ask", text="What was that noise?")
    assert only(r, "guide_answer") == {"text": guide.GUIDE_DOWN}
