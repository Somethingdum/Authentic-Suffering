"""Implementation of service/session.py additions."""
from __future__ import annotations


def append_story(tx, turn_index, kind, text, mode=None):
    from ..contracts.events import WriteOp
    n = tx.query_one("SELECT COALESCE(MAX(entry_id), 0) FROM story_log")[0] + 1
    tx.bookkeep("service", "story_log", WriteOp.INSERT, {}, {"entry_id": n, "turn_index": turn_index, "kind": kind, "mode": mode, "text": text})
    return n


def session_from_world(w, run_dir=None):
    from ..contracts.settings import RunSettings
    from .session import Session
    st = RunSettings.model_validate_json(w.store.meta("settings_json"))
    return Session(run_id=w.store.meta("run_id"), run_dir=run_dir, store=w.store, canon=w.canon, config=w.config, settings=st,
                   rng=w.rng, client=w.client, pc_id=w.pc_id)


def change_settings(tx, session, patch):
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    from ..contracts.settings import RunSettings
    from .session import CHANGEABLE_SETTINGS, LockedSetting
    for k in patch:
        if k not in RunSettings.model_fields:
            raise ValueError(f"unknown setting: {k}")
        if k not in CHANGEABLE_SETTINGS:
            raise LockedSetting(k)
    old = session.settings.model_dump(mode="json")
    new = RunSettings.model_validate({**old, **patch})
    newd = new.model_dump(mode="json")
    now, turn = tx.query_one("SELECT now_ms, turn_index FROM world_clock")
    cur = dict(old)
    evs = []
    for f in CHANGEABLE_SETTINGS:
        if newd[f] == old[f]:
            continue
        cur[f] = newd[f]
        so_far = RunSettings.model_validate(cur).model_dump_json()
        evs.append(tx.commit_event(Event(type=EventType.SETTINGS_CHANGE, writer="kernel.meta", origin="system", at=now,
                                         turn_index=turn, payload={"field": f, "old": old[f], "new": newd[f]},
                                         writes=[WriteRecord(op=WriteOp.UPDATE, table="meta", key={"key": "settings_json"},
                                                             values={"value": so_far})])))
    session.settings = new
    return evs
