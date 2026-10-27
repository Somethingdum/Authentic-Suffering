"""A branch's earlier turn, a turn interrupted, a turn stopped (P13, D-299). Rules HOST-12, HOST-13,
HOST-19, HOST-21..HOST-23 (host/fork.py, host/transport.py, host/service.py).

A host keeps some worlds and the latest of each branch. The engine rebuilds any earlier turn of a
branch from the nearest kept world with the answers the latest world recorded — no model call, the
same world exactly, or a refusal that says why. A turn the host plays again after a crash, with the
answers it already gave, asks the models nothing. A stopped writing is told plainly, never drafted
again behind the player's back.
"""

from __future__ import annotations

import json

import pytest
from host_kit import call, header, only, same_world

from as_engine.host import world as W
from as_engine.host.protocol import b64, unb64

pytestmark = pytest.mark.phase(13)

MOVES = ["I look over the fence.", "I walk to the storeroom doorway.", '"Who\'s there?"']


async def play(svc, moves=MOVES, tier=4):
    kept = {}
    for text in moves:
        got = await call(svc, "turn", mode="do", text=text, tier=tier)
        assert "error" not in got, got
        kept[got["turn"]] = got["world"]
    return kept


async def test_a_fork_rebuilds_an_earlier_turn_exactly(world0, host, hosted):
    svc = hosted(host())
    await call(svc, "open", world=b64(world0))
    kept = await play(svc)
    h2 = host()
    got = await call(hosted(h2), "fork", base=b64(world0), head=kept[3], turn=2)
    assert "error" not in got, got
    assert h2.calls == [], "a fork asks the models nothing"
    assert got["turn"] == 2 and header(got["world"])["full_state_hash"] == header(kept[2])["full_state_hash"]


async def test_a_fork_to_either_end_is_that_world(world0, host, hosted):
    svc = hosted(host())
    await call(svc, "open", world=b64(world0))
    kept = await play(svc, MOVES[:2])
    a = await call(hosted(host()), "fork", base=kept[1], head=kept[2], turn=2)
    b = await call(hosted(host()), "fork", base=kept[1], head=kept[2], turn=1)
    assert header(a["world"])["full_state_hash"] == header(kept[2])["full_state_hash"]
    assert header(b["world"])["full_state_hash"] == header(kept[1])["full_state_hash"]


async def test_a_forked_story_plays_on(world0, host, hosted):
    svc = hosted(host())
    await call(svc, "open", world=b64(world0))
    kept = await play(svc, MOVES[:2])
    h2 = host()
    s2 = hosted(h2)
    await call(s2, "fork", base=b64(world0), head=kept[2], turn=1)
    got = await call(s2, "turn", mode="do", text="I run for the back door.", tier=3)
    assert "error" not in got and got["turn"] == 2 and h2.calls, "after the fork the host answers again"


async def test_forks_that_cannot_be_are_refused(world0, host, hosted, hcfg):
    svc = hosted(host())
    await call(svc, "open", world=b64(world0))
    kept = await play(svc, MOVES[:2])
    other = host_world_other(hcfg)
    assert (await call(hosted(host()), "fork", base=b64(world0), head=kept[2], turn=5))["error"]["code"] == "bad_fork"
    assert (await call(hosted(host()), "fork", base=kept[2], head=kept[1], turn=1))["error"]["code"] == "bad_fork"
    got = await call(hosted(host()), "fork", base=b64(other), head=kept[2], turn=1)
    assert got["error"]["code"] == "not_ancestor"


def host_world_other(cfg):
    from host_kit import scenario_world
    return scenario_world(cfg, "three_rooms_gunshot")


async def test_a_world_that_does_not_replay_is_never_passed_off(world0, host, hosted):
    svc = hosted(host())
    await call(svc, "open", world=b64(world0))
    kept = await play(svc, MOVES[:2])
    _h, head = W.unpack(unb64(kept[2]))
    row = head.query_one("SELECT detail FROM turn_ledger WHERE turn_index=1 AND stage=19")
    d = json.loads(row[0])
    d["full_state_hash"] = "0" * 64
    head.conn.execute("UPDATE turn_ledger SET detail=? WHERE turn_index=1 AND stage=19", (json.dumps(d),))
    tampered = W.pack(head, ["core"])
    head.close()
    got = await call(hosted(host()), "fork", base=b64(world0), head=b64(tampered), turn=1)
    assert got["error"]["code"] == "diverged"


async def test_a_turn_played_again_with_its_answers_asks_nothing(world0, host, hosted):
    first = host()
    s1 = hosted(first)
    await call(s1, "open", world=b64(world0))
    a = await call(s1, "turn", mode="do", text=MOVES[0], tier=3)
    again = host()
    s2 = hosted(again)
    await call(s2, "open", world=b64(world0))
    b = await call(s2, "turn", mode="do", text=MOVES[0], tier=3, answers=first.results, decisions=a["steps"])
    assert again.calls == [] and again.asked == []
    assert header(a["world"])["full_state_hash"] == header(b["world"])["full_state_hash"]


async def test_stop_while_writing_tells_the_turn_plainly(world0, host, hosted):
    h = host(fail={"narration": {"failed": "stopped", "why": "stopped"}})
    svc = hosted(h)
    await call(svc, "open", world=b64(world0))
    got = await call(svc, "turn", mode="do", text=MOVES[0], tier=3)
    r = only(got, "turn_result")
    assert r["narration"] and got["turn"] == 1, "the world was committed at stage 12; the moment is told plainly"
    assert sum(1 for k, _p in h.calls if k == "write") == 1, "a stopped writing is never drafted again"


async def test_a_refusal_for_every_call_rolls_nothing_forward(world0, host, hosted):
    h = host(fail={c: {"failed": "refused", "why": "no model"} for c in ("intake", "actor_cognition", "narration")})
    svc = hosted(h)
    await call(svc, "open", world=b64(world0))
    got = await call(svc, "turn", mode="do", text=MOVES[0], tier=3)
    assert "turn_rejected" in [m["action"] for m in got["messages"]]
    assert svc.session.store.query_one("SELECT turn_index FROM world_clock")[0] == 0
    assert not svc.session.client.is_down(svc.session.client.config.hot_cognition.lane), "a refusal marks nothing down"


async def test_the_console_between_turns_asks_the_host_to_keep_the_world(world0, host, hosted):
    svc = hosted(host())
    await call(svc, "open", world=b64(world0))
    await call(svc, "turn", mode="do", text=MOVES[0], tier=3)
    got = await call(svc, "turn", mode="do", text="2508", tier=3)          # CHEAT-01: the console opens
    assert "error" not in got and "cheat_activated" in [m["action"] for m in got["messages"]]
    assert got.get("keep") is True, "a console change cannot be played again, so the host keeps this world"
    plain = await call(svc, "turn", mode="do", text=MOVES[1], tier=3)
    assert plain.get("keep") is False
