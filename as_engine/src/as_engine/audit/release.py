"""Release audit (P11). Rules REL-01..06. Run by the developer before a release (tools/as/eval.py
--release, or directly), never during play: it works on copies of a run and changes nothing in it.

release_audit(config, run_id, *, days=30, pack_dirs=None) -> ReleaseReport
  rd = <runs_dir>/<run_id>; no manifest.json or no turn0.sqlite -> service.runs.RunError(
  'not_found', f"There is no run called {run_id} with a starting snapshot."). The work folder
  rd/reports/release/ is emptied and made; in it, for each of 'turn0' (from turn0.sqlite) and
  'soak' (from world.sqlite), <name>/<run_id>/ holds a copy of manifest.json and the snapshot as
  world.sqlite (kernel.store.Store.open(snapshot).backup_to: a consistent copy even while the game
  has the run open), opened with service.runs.load_run(config with runs_dir = <work>/<name>, run_id,
  transport None, pack_dirs = the argument, else the manifest's). No model is ever called.
  REL-01 the world as it began: report.world_checks = world.worldgen.checks.reassert(turn0 store)
    (WG-35 again; D-45, D-95).
  REL-02 the long quiet (HRD-15 over days): on the soak store, before = world.hordes.census(store)
    ['total'] and the three counts below; then `days` times, each in its own transaction:
    turn.timers.run_offscreen(tx, session.rng, now + 1 day, the world_clock turn_index); then
    after = census total and the counts again. risen = the sum of active_delta + dormant_delta of
    POOL_CHANGE events with reason 'risen' + the infected_state rows with risen_from set;
    destroyed = infected bodies with alive 0; cheat = infected bodies with origin 'cheat'.
    report.census = {before, after, risen, destroyed, cheat (each the change over the soak), holds:
    after - before == risen - destroyed + cheat}.
  REL-03 report.abuse = audit.abuse.battery on the soaked world.
  REL-04 report.unbuilt: every finding of the soaked world's audit_log rows (by turn_index, then
    audit_id) whose kind is 'timer_unbuilt' -> f"A {type} timer fired with nothing built to handle
    it." or 'cascade_unbuilt' -> f"Cascade rule {rule_id} needs {what}, which is not built.";
    each sentence once, first occurrence kept.
  REL-05 report.content — CNT-11 over everything a run can hold: for each pack dir,
    content.pack.load_pack's issues with code 'CNT-11' -> f"{pack}: {message}" (the issue's pack id;
    the message starts with the file); then
    every dossiers row of the soaked world (by dossier_id) whose baseline identity.age < 18, one
    sentence per term of content.safety.unsafe_terms found in any string VALUE (never a key) of its
    baseline_json, terms sorted, each once -> f"{dossier_id}: a record for someone under 18
    contains the word '{term}'."
  REL-06 report.soak = {days, world_days: the WORLD_DAY events the soak committed, events: every
    event it committed, and the count of each of DEATH, OFFSCREEN_DEATH, BIRTH, RAID, HORDE_FORMED,
    SHORTAGE, RUMOUR_SPREAD, FACTION_OPERATION it committed (keys lowercased)}; holds when
    world_days == days (the world kept moving every day).
  report.passed = no world_checks, census holds, no abuse, no unbuilt, no content, soak holds.
  Both sessions' stores are closed at the end, whatever happens.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..contracts.settings import EngineConfig
    from .abuse import AbuseFinding

DAY_MS = 86_400_000
SOAK_TYPES = ("DEATH", "OFFSCREEN_DEATH", "BIRTH", "RAID", "HORDE_FORMED", "SHORTAGE", "RUMOUR_SPREAD", "FACTION_OPERATION")


@dataclass
class ReleaseReport:
    world_checks: list[str] = field(default_factory=list)
    census: dict[str, Any] = field(default_factory=dict)
    abuse: list["AbuseFinding"] = field(default_factory=list)
    unbuilt: list[str] = field(default_factory=list)
    content: list[str] = field(default_factory=list)
    soak: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return (not self.world_checks and bool(self.census.get("holds")) and not self.abuse and not self.unbuilt
                and not self.content and bool(self.soak.get("holds")))


def _counts(store) -> tuple[int, int, int, int]:
    from ..world import hordes
    risen = sum(json.loads(r[0]).get("active_delta", 0) + json.loads(r[0]).get("dormant_delta", 0)
                for r in store.query("SELECT payload FROM events WHERE type='POOL_CHANGE' "
                                     "AND json_extract(payload,'$.reason')='risen'"))
    risen += store.query_one("SELECT COUNT(*) FROM infected_state WHERE risen_from IS NOT NULL")[0]
    destroyed = store.query_one("SELECT COUNT(*) FROM bodies WHERE kind='infected' AND alive=0")[0]
    cheat = store.query_one("SELECT COUNT(*) FROM bodies WHERE kind='infected' AND origin='cheat'")[0]
    return hordes.census(store)["total"], risen, destroyed, cheat


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)


def _open(config, rd: Path, work: Path, name: str, snapshot: str, run_id: str, pack_dirs):
    from ..kernel.store import Store
    from ..service import runs
    d = work / name / run_id
    d.mkdir(parents=True)
    shutil.copyfile(rd / "manifest.json", d / "manifest.json")
    src = Store.open(rd / snapshot)
    try:
        src.backup_to(d / "world.sqlite")
    finally:
        src.close()
    return runs.load_run(config.model_copy(update={"runs_dir": str(work / name)}), run_id, None, pack_dirs=pack_dirs)


def release_audit(config: "EngineConfig", run_id: str, *, days: int = 30,
                  pack_dirs: list[str | Path] | None = None) -> ReleaseReport:
    from ..content.pack import load_pack
    from ..content.safety import unsafe_terms
    from ..service import runs
    from ..turn import timers
    from ..world.worldgen import checks
    from . import abuse
    rd = Path(config.runs_dir) / run_id
    if not (rd / "manifest.json").exists() or not (rd / "turn0.sqlite").exists():
        raise runs.RunError("not_found", f"There is no run called {run_id} with a starting snapshot.")
    man = json.loads((rd / "manifest.json").read_text(encoding="utf-8"))
    dirs = [str(p) for p in (pack_dirs or man.get("pack_dirs") or [])]
    work = rd / "reports" / "release"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    rep = ReleaseReport()
    opened = []
    try:
        t0 = _open(config, rd, work, "turn0", "turn0.sqlite", run_id, dirs or None)
        opened.append(t0)
        rep.world_checks = checks.reassert(t0.store)
        s = _open(config, rd, work, "soak", "world.sqlite", run_id, dirs or None)
        opened.append(s)
        st = s.store
        first_seq = st.query_one("SELECT COALESCE(MAX(seq), 0) FROM events")[0]
        before = _counts(st)
        for _ in range(days):
            with st.transaction() as tx:
                now, turn = tx.query_one("SELECT now_ms, turn_index FROM world_clock")
                timers.run_offscreen(tx, s.rng, now + DAY_MS, turn)
        after = _counts(st)
        d = [a - b for a, b in zip(after, before, strict=True)]
        rep.census = {"before": before[0], "after": after[0], "risen": d[1], "destroyed": d[2], "cheat": d[3],
                      "holds": d[0] == d[1] - d[2] + d[3]}
        with st.transaction() as tx:
            rep.abuse = abuse.battery(tx)
        seen: list[str] = []
        for r in st.query("SELECT findings FROM audit_log ORDER BY turn_index, audit_id"):
            for f in json.loads(r[0]) if r[0] else []:
                if not isinstance(f, dict):
                    continue
                if f.get("kind") == "timer_unbuilt":
                    line = f"A {f.get('type')} timer fired with nothing built to handle it."
                elif f.get("kind") == "cascade_unbuilt":
                    line = f"Cascade rule {f.get('rule_id')} needs {f.get('what')}, which is not built."
                else:
                    continue
                if line not in seen:
                    seen.append(line)
        rep.unbuilt = seen
        for p in dirs:
            _pack, issues = load_pack(p)
            rep.content += [f"{i.pack}: {i.message}" for i in issues if i.code == "CNT-11"]
        for did, bj in st.query("SELECT dossier_id, baseline_json FROM dossiers ORDER BY dossier_id"):
            b = json.loads(bj)
            try:
                age = int((b.get("identity") or {}).get("age"))
            except (TypeError, ValueError):
                continue
            if age >= 18:
                continue
            terms = sorted({t for text in _strings(b) for t in unsafe_terms(text)})
            rep.content += [f"{did}: a record for someone under 18 contains the word '{t}'." for t in terms]
        soak = {k.lower(): st.query_one("SELECT COUNT(*) FROM events WHERE type=? AND seq>?", (k, first_seq))[0]
                for k in SOAK_TYPES}
        soak.update(days=days, events=st.query_one("SELECT COUNT(*) FROM events WHERE seq>?", (first_seq,))[0],
                    world_days=st.query_one("SELECT COUNT(*) FROM events WHERE type='WORLD_DAY' AND seq>?", (first_seq,))[0])
        soak["holds"] = soak["world_days"] == days
        rep.soak = soak
    finally:
        for x in opened:
            x.store.close()
    return rep
