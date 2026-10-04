"""Implementation of service/progress.py."""
from __future__ import annotations

import asyncio
import inspect


class Tracker:
    def __init__(self, kind, job_id, push, *, dev=False, clock=None):
        from .progress import PLANS
        if kind not in PLANS:
            raise ValueError(f"no plan for {kind}")
        self.kind, self.job_id, self._push, self.dev, self.clock = kind, job_id, push, dev, clock
        self.phases = PLANS[kind]
        self.t0 = None
        self.last_pct = 0.0

    async def _emit(self, action, data):
        r = self._push(action, data)
        if inspect.isawaitable(r):
            await r

    def _now(self):
        return self.clock() if self.clock is not None else asyncio.get_running_loop().time()

    def _elapsed(self):
        now = self._now()
        return round(max(0.0, now - (self.t0 if self.t0 is not None else now)), 1)

    async def plan(self, quips):
        self.t0 = self._now()
        await self._emit("progress_plan", {
            "job_id": self.job_id, "kind": self.kind, "title": _titles()[self.kind],
            "phases": [{"id": p.id, "label": p.label, "weight": p.weight,
                        "subs": [{"id": s.id, "label": s.label} for s in p.subs]} for p in self.phases],
            "quips": dict(quips)})

    async def step(self, phase, sub=None, *, done=None, total=None, detail=None):
        idx = next((i for i, p in enumerate(self.phases) if p.id == phase), None)
        if idx is None:
            raise ValueError(f"{self.kind} has no phase {phase}")
        ph = self.phases[idx]
        sl = None
        si = 0
        if sub is not None:
            si = next((i for i, s in enumerate(ph.subs) if s.id == sub), None)
            if si is None:
                raise ValueError(f"{self.kind}.{phase} has no sub-phase {sub}")
            sl = ph.subs[si].label
        if self.kind == "turn":
            done = total = None
        before = sum(p.weight for p in self.phases[:idx])
        if done is not None and total:
            f = done / total
        elif ph.subs and sub is not None:
            f = si / len(ph.subs)
        else:
            f = 0.0
        pct = round(min(100.0, before + ph.weight * f), 1)
        pct = max(pct, self.last_pct)
        self.last_pct = pct
        el = self._elapsed()
        eta = round(el * (100 - pct) / pct) if pct >= 5 else None
        await self._emit("progress", {
            "job_id": self.job_id, "kind": self.kind, "phase": phase, "phase_index": idx, "sub": sub, "sub_label": sl,
            "done": done, "total": total, "pct": pct, "elapsed_s": el, "eta_s": eta,
            "detail": detail if self.dev else None})

    async def done(self, ok):
        await self._emit("progress_done", {"job_id": self.job_id, "kind": self.kind, "ok": bool(ok),
                                           "elapsed_s": self._elapsed()})


def _titles():
    from .progress import TITLES
    return TITLES


def quips_for(canon, kind):
    out = {}
    for ref in canon.refs("quips"):
        rec = canon.get(ref)
        for key, lines in rec.lines.items():
            if key != kind and not key.startswith(kind + "."):
                continue
            cur = out.setdefault(key, [])
            for line in lines:
                if line not in cur:
                    cur.append(line)
    return out


# ---------------------------------------------------------------------------- PROG-08 (D-114)
def activity(entries):
    from ..lanes.progress import stall_window
    from .progress import ACTIVITY_ORDER
    if not entries:
        return None
    rank = {p: i for i, p in enumerate(ACTIVITY_ORDER)}
    phases = [("reading" if s.get("phase") == "prefill" else s.get("phase") or "waiting") for s, _l in entries]
    phase = max(phases, key=lambda p: rank.get(p, 0))
    reading = None
    if phase == "reading":
        pcts = [100.0 * s["prompt_processed"] / s["prompt_total"] for (s, _l), p in zip(entries, phases)
                if p == "reading" and s.get("prompt_total")]
        reading = round(min(100.0, max(pcts)), 1) if pcts else None
    left = [max(0.0, w - float(s.get("quiet_s", 0.0))) for s, lane in entries
            for w in [stall_window(lane, s)] if w is not None]
    return {"phase": phase,
            "call_s": round(max(float(s.get("elapsed_s", 0.0)) for s, _l in entries), 1),
            "quiet_s": round(min(float(s.get("quiet_s", 0.0)) for s, _l in entries), 1),
            "slow": any(bool(s.get("slow")) for s, _l in entries),
            "reading_pct": reading,
            "stall_in_s": round(min(left), 1) if left else None}


class ActivityFeed:
    def __init__(self, job_id, kind, push, lanes, *, clock=None, every_s=None):
        from .progress import ACTIVITY_EVERY_S
        self.job_id, self.kind, self._push, self.lanes, self.clock = job_id, kind, push, lanes, clock
        self.every_s = ACTIVITY_EVERY_S if every_s is None else every_s
        self.live = {}
        self.last_at = None
        self.last_phase = None
        self.tasks = set()

    def _now(self):
        return self.clock() if self.clock is not None else asyncio.get_running_loop().time()

    def seen(self, request, snapshot):
        from ..contracts.common import Lane
        key = id(request)
        if snapshot is None:
            if self.live.pop(key, None) is None:
                return
        else:
            lane = self.lanes.get(Lane(snapshot.get("lane"))) if snapshot.get("lane") else None
            if lane is None:
                return
            self.live[key] = (snapshot, lane)
        a = activity(list(self.live.values()))
        phase = a["phase"] if a else "idle"
        now = self._now()
        if phase == self.last_phase and self.last_at is not None and now - self.last_at < self.every_s:
            return
        self.last_phase, self.last_at = phase, now
        data = {"job_id": self.job_id, "kind": self.kind, **(a or {"phase": "idle", "call_s": 0.0, "quiet_s": 0.0,
                                                                     "slow": False, "reading_pct": None,
                                                                     "stall_in_s": None})}
        r = self._push("activity", data)
        if inspect.isawaitable(r):
            t = asyncio.ensure_future(r)
            self.tasks.add(t)
            t.add_done_callback(self.tasks.discard)

    async def flush(self):
        while self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)
