"""Forks: a branch's world at an earlier turn, played again exactly (D-299). Rules HOST-21..HOST-23.

A host keeps some of a story's worlds (each a host.world envelope) and the latest world of each
branch. The latest world's call log holds every model answer its branch ever got (lanes.calllog,
DET-03), and its turn ledger every decision the host's budget made (HOST-08), so the world at any
earlier turn of that branch can be rebuilt from the nearest world kept at or before it, with no
model call.

HOST-21 fork(config, base, head, turn) -> Session
  base, head: world envelopes; K = base's turn, N = head's turn. turn < K or turn > N ->
  WorldError('bad_fork'). base must be an ancestor of head: the same meta run_id and seed, and
  head's events up to base's highest seq exactly base's events (a digest of seq, event_id, type,
  payload and state_delta in seq order; ids alone are counters every story shares) — else
  WorldError('not_ancestor'). turn == N -> the session on
  head; turn == K -> the session on base. Otherwise the session on base (host.world.open_session)
  over ForkTransport(head) — lanes.calllog.ReplayTransport(head, routed=True) that carries a
  governor —, and for T = K+1 .. turn in order:
    1. HOST-22 between turns: every head event with seq above the session store's highest and
       turn_index < T, in seq order, must be REPLAYABLE (else WorldError('needs_kept_world'), and the
       host forks from a world it kept after that point — the bridge tells it which, HOST-19):
       a SETTINGS_CHANGE whose payload has 'field' -> service.session.change_settings({field: new});
       a REFLECTION, RUMOUR_DISTORTED or VOICE_WRITTEN -> re-committed from its payload as
       service.replay does (BG-05).
    2. head's player_inputs row for T (none -> WorldError('not_ancestor')) becomes the submit as
       service.replay builds it (a suggestion's signature, a forced addressee).
    3. transport.governor = host.governor.RecordedGovernor(the steps of every wave of head's
       stage-4 ledger for T, tier and focus from it); turn.pipeline.run_turn.
    4. HOST-23 the result must be the same world: full_state_hash of the session store equals head's
       stage-19 ledger hash for T — else WorldError('diverged', DIVERGED), never a silently
       different world.
  head is closed at the end; the session's store is the forked world.
REPLAYABLE: the between-turn event types step 1 can redo.
"""

from __future__ import annotations

import json
from typing import Any

from ..lanes.calllog import ReplayTransport
from .world import WorldError, open_session, unpack

REPLAYABLE: frozenset[str] = frozenset({"SETTINGS_CHANGE", "REFLECTION", "RUMOUR_DISTORTED", "VOICE_WRITTEN"})
DIVERGED = ("That earlier moment could not be rebuilt exactly (the game changed since it was played), so the story "
            "was not moved there. Go back to a moment saved after the update.")


class ForkTransport(ReplayTransport):
    def __init__(self, store):
        super().__init__(store, routed=True)
        self.governor = None


def _events_digest(store, upto: int) -> str:
    import hashlib
    h = hashlib.sha256()
    for r in store.query("SELECT seq, event_id, type, payload, state_delta FROM events WHERE seq <= ? ORDER BY seq", (upto,)):
        h.update(f"{r[0]}\x1f{r[1]}\x1f{r[2]}\x1f{r[3]}\x1f{r[4]}\n".encode("utf-8"))
    return h.hexdigest()


def _recorded_plan(head, T: int) -> tuple[dict, int, int | None]:
    row = head.query_one("SELECT detail FROM turn_ledger WHERE turn_index=? AND stage=4 ORDER BY run_count DESC", (T,))
    steps, tier, focus = {}, 3, None
    if row is not None:
        for w in json.loads(row[0]).get("waves", []):
            steps.update(w.get("steps") or {})
            tier = w.get("tier", tier)
            focus = w.get("focus", focus)
    return steps, tier, focus


async def fork(config: Any, base_bytes: bytes, head_bytes: bytes, turn: int) -> Any:
    from ..contracts.protocol import InTurnSubmit
    from ..kernel.hashing import full_state_hash
    from ..service._impl_replay import _recommit_one
    from ..service.session import change_settings
    from ..turn.pipeline import run_turn
    from .governor import RecordedGovernor
    bh, base = unpack(base_bytes)
    try:
        hh, head = unpack(head_bytes)
    except BaseException:
        base.close()
        raise
    kept = None                           # the store handed back in the session
    try:
        K, N = int(bh.get("turn", 0)), int(hh.get("turn", 0))
        if turn < K or turn > N:
            raise WorldError("bad_fork", f"There is no turn {turn} between the saved moments {K} and {N}.")
        top = base.query_one("SELECT COALESCE(MAX(seq), 0) FROM events")[0]
        if (base.meta("run_id"), base.meta("seed")) != (head.meta("run_id"), head.meta("seed")) \
                or _events_digest(base, top) != _events_digest(head, top):
            raise WorldError("not_ancestor", "Those two saved moments are not from the same story.")
        packs = hh.get("packs") or ["core"]
        if turn == N:
            kept = head
            return open_session(config, head, ReplayTransport(head, routed=True), packs)
        tr = ForkTransport(head)
        kept = base
        s = open_session(config, base, tr, packs)
        if turn == K:
            return s
        for T in range(K + 1, turn + 1):
            cur = s.store.query_one("SELECT COALESCE(MAX(seq), 0) FROM events")[0]
            for c in head.query("SELECT seq, type, at, turn_index, payload FROM events WHERE seq > ? AND turn_index < ? ORDER BY seq",
                                (cur, T)):
                if c["type"] not in REPLAYABLE:
                    raise WorldError("needs_kept_world", f"The story changed between turns {T - 1} and {T} in a way that "
                                                         "cannot be played again; go back from a moment saved after it.")
                pl = json.loads(c["payload"])
                if c["type"] == "SETTINGS_CHANGE":
                    if "field" not in pl:
                        raise WorldError("needs_kept_world", "The story's settings changed in a way that cannot be played again.")
                    with s.store.transaction() as tx:
                        change_settings(tx, s, {pl["field"]: pl["new"]})
                else:
                    _recommit_one(s, dict(c))
            r = head.query_one("SELECT * FROM player_inputs WHERE turn_index=?", (T,))
            if r is None:
                raise WorldError("not_ancestor", f"Turn {T} is not in the later saved moment.")
            r = dict(r)
            mapped = json.loads(r["mapped"])
            if r["mode"] == "suggestion":
                s.extras["suggestions"] = {"r1": {"signature": mapped["signature"], "label": r["raw_text"]}}
                sub = InTurnSubmit(mode="do", suggestion_ref="r1")
            else:
                s.extras["forced_addressee"] = mapped.get("addressee")
                sub = InTurnSubmit(mode=r["mode"], text=r["raw_text"])
            steps, tier, focus = _recorded_plan(head, T)
            tr.governor = RecordedGovernor(steps, tier=tier, focus=focus)
            try:
                out = await run_turn(s, sub)
            finally:
                tr.governor = None
            exp = head.query_one("SELECT detail FROM turn_ledger WHERE turn_index=? AND stage=19", (T,))
            want = json.loads(exp[0]).get("full_state_hash") if exp is not None else None
            if not out.ok or want is None or full_state_hash(s.store) != want:
                raise WorldError("diverged", DIVERGED)
        return s
    except BaseException:
        kept = None
        raise
    finally:
        for st in (base, head):
            if st is not kept:
                try:
                    st.close()
                except Exception:  # noqa: BLE001 — closed already (open_session closes a store it refuses)
                    pass
