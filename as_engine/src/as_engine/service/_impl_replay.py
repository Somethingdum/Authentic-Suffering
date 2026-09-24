"""Implementation of service/replay.py."""
from __future__ import annotations

import json
import shutil


async def resimulate(config, run_id, *, pack_dirs=None):
    from ..contracts.protocol import InTurnSubmit
    from ..kernel.hashing import full_state_hash
    from ..kernel.store import Store
    from ..lanes.calllog import ReplayTransport
    from ..turn.pipeline import run_turn
    from ._impl_runs import MANIFEST, RunError, _open_session, runs_dir
    rd = runs_dir(config) / run_id
    if not (rd / MANIFEST).exists() or not (rd / "turn0.sqlite").exists():
        raise RunError("not_found", f"There is no run called {run_id} with a starting snapshot.")
    man = json.loads((rd / MANIFEST).read_text(encoding="utf-8"))
    orig = Store.open(rd / "world.sqlite")
    work = rd / "reports" / "replay"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    shutil.copyfile(rd / "turn0.sqlite", work / "world.sqlite")
    s = _open_session(config, work, ReplayTransport(orig), pack_dirs or man.get("pack_dirs") or [])
    s.run_dir = None
    report = []
    from ._impl_session import change_settings
    between = [dict(c) for c in orig.query(
        "SELECT seq, type, at, turn_index, payload FROM events WHERE type IN ('SETTINGS_CHANGE','REFLECTION','RUMOUR_DISTORTED') "
        "ORDER BY seq")]
    between = [c for c in between if c["type"] != "SETTINGS_CHANGE" or "field" in json.loads(c["payload"])]
    done = set()
    try:
        for r in orig.query("SELECT * FROM player_inputs ORDER BY turn_index"):
            r = dict(r)
            for c in between:
                if c["seq"] in done or c["turn_index"] >= r["turn_index"]:
                    continue
                pl = json.loads(c["payload"])
                if c["type"] == "SETTINGS_CHANGE":
                    with s.store.transaction() as tx:
                        change_settings(tx, s, {pl["field"]: pl["new"]})
                else:
                    _recommit_one(s, c)
                done.add(c["seq"])
            mapped = json.loads(r["mapped"])
            if r["mode"] == "suggestion":
                s.extras["suggestions"] = {"r1": {"signature": mapped["signature"], "label": r["raw_text"]}}
                sub = InTurnSubmit(mode="do", suggestion_ref="r1")
            else:
                s.extras["forced_addressee"] = mapped.get("addressee")
                sub = InTurnSubmit(mode=r["mode"], text=r["raw_text"])
            out = await run_turn(s, sub)
            exp = json.loads(orig.query_one("SELECT detail FROM turn_ledger WHERE turn_index=? AND stage=19", (r["turn_index"],))[0]).get("full_state_hash")
            got = full_state_hash(s.store)
            report.append({"turn_index": r["turn_index"], "ok": out.ok and got == exp, "expected": exp, "got": got,
                           "problem": None if out.ok else (out.rejected_code or "failed")})
            if not report[-1]["ok"]:
                break
    finally:
        s.store.close()
        orig.close()
    return report


def _recommit_one(s, e):
    # BG-05: one quiet-hours event, re-applied from its recorded payload.
    from ..contracts.mind import ReflectionOutput, RumourDistortion
    from . import background as B
    pl = json.loads(e["payload"])
    if e["type"] == "REFLECTION":
        job = B.Job(kind="reflection", subject_id=pl["actor_id"], rumour_id=None, request_key=pl["request_key"])
        res = B.JobResult(job=job, answer={"output": ReflectionOutput.model_validate(pl["output"]), "handles": pl["handles"]})
    else:
        job = B.Job(kind="retelling", subject_id=pl["holder_id"], rumour_id=pl["rumour_id"],
                    request_key=f"retelling:{pl['holder_id']}:{pl['rumour_id']}")
        res = B.JobResult(job=job, answer=RumourDistortion(operation=pl["operation"], retold_claim=pl["text"] or "none"))
    with s.store.transaction() as tx:
        B.commit(tx, job, res, e["at"], e["turn_index"])
