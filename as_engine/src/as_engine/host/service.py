"""The hosted game: the Play UI's service, driven by a host (D-299). Rules HOST-14..HOST-20.

HostService(config, link) is service.game_service.GameService over a host.transport.HostTransport
(config' = host.world.host_config(config)), so a hosted story plays exactly as the Play UI's does —
cheats and the console, the guide, the Doom, death and its reveal — and adds what a host needs:
worlds in and out as bytes, world creation, forks and the quiet hours on request.

HOST-14 answers. handle(type, payload) -> dict. Every answer that may have changed the world
  carries "world": the world envelope (host.world.pack) in base64, "world_sha256" and "turn" —
  when the store's connection made any change during the request (sqlite total_changes) — and
  "keep": true when it changed the world between turns in a way a fork cannot replay (HOST-19), so
  the host keeps that world. "messages" are the Play UI protocol's outbound messages
  (contracts.protocol, {type, action, data}) the request produced, in order, with the Play UI's own
  progress lines left out. A ServiceError, RunError or WorldError -> error {code, message}.
HOST-15 progress. A turn's or a world's stage reaches the host as the notice progress {stage, label,
  pct} (label: the player-facing words, UI-CLARITY-01).
HOST-16 requests:
  hello -> {engine, protocol, world_format, schema, sealed: lanes.seal.sealed() — the host can check
    that the process it started cannot reach the network}.
  menu -> {pcs: the character cards (Play UI 'pcs'), settings: RunSettings' JSON schema, defaults}.
  begin {pc_ref, settings, answers} -> a new world in memory, made as service.runs.create_run makes
    one but with no file: settings validated (a bad one -> error 'bad_settings'); seed = settings.seed,
    else derived as create_run derives it, and sent at once as the notice begin.seed {seed} so a host
    that has to begin again (a crash) passes the same seed and its recorded answers (HOST-13) and no
    model call is made twice; run_id from the PC's display name and the seed, world_id f"w_{seed:x}";
    world.worldgen.pipeline.run_worldgen(..., world_dir=None) — its genesis comes back as bytes —;
    the kernel.meta SETTINGS_CHANGE {source 'worldgen', world_id}; a cheat life's start_life; then the
    session. Answers {world…, genesis: the genesis as a world envelope (base64), world_summary,
    notices, messages: [view, story]} (the story holds the opening).
  open {world} -> the session on that world (host.world.unpack, open_session); {turn, notices,
    messages: [view, story]}. A newer world -> error 'newer' and nothing is written (HOST-02).
  save -> {world…} always.
  turn {mode, text, suggestion_ref, addressee_refs, tier, focus, answers, decisions} and compose {act,
    say, cheat, to, tier, focus, answers, decisions} (HOST-17) -> the Play UI's turn_submit /
    turn_compose, played to the end; {messages, steps: the budget's decisions, world…}.
  cancel -> while a world is being made (begin): it is cancelled and nothing of it is kept (begin
    answers error 'cancelled'); else the Play UI's turn_cancel: before stage 12 the turn rolls back;
    after it, 'too_late' (the world stands; a stopped write ends the drafting, HOST-12). A world
    creation's own refusals keep their words: WorldgenAborted -> error 'worldgen_aborted', a
    SettingsError -> 'bad_settings'.
  view, story, settings_get, settings_set {patch}, code_enter {code}, cheat_dictionary, death_reveal
    -> the Play UI's handlers of those names.
  quiet {answers} -> the quiet hours (service.background catch-up) for the turn just played;
    {done, world…}. Between turns nothing runs unless the host asks (HOST-18).
  fork {base, head, turn} -> host.fork.fork; the session becomes the world at that turn; {world…,
    messages: [view, story]}.
  close -> {} and the bridge exits. ping -> {pong: true}.
HOST-17 a hosted turn. governor = host.governor.LinkGovernor(the link, tier, focus, recorded =
  decisions); transport.governor = it and the answers are added (HOST-13); when TIERS[tier]'s depth
  differs from settings.turn_depth, service.session.change_settings({turn_depth: it}) in its own
  transaction (a between-turns SETTINGS_CHANGE, replayed like any, SET-01); governor.start_turn
  declares the turn's steps; then the Play UI's handler, and the turn task awaited. Afterwards
  transport.governor = None whatever happened.
HOST-18 the quiet hours never start on their own: the Play UI's runner starts them when a turn ends;
  the hosted one does not (HostBackground.start does nothing), so the world the host was handed is
  the world until it asks again. A turn still catches up on what is pending first, as the Play UI's
  does.
HOST-19 keep. The events a request committed (seq above the store's max before it) whose
  turn_index is below the world clock's turn index after it, or all of them when no turn was
  played, are between-turn events; one whose type is not in host.fork.REPLAYABLE -> keep true.
HOST-20 nothing the engine writes names a story outside its world: the bridge's log lines carry
  request types, codes and exception types only (RUN-13).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..service._impl_background import BackgroundRunner
from ..service._impl_game_service import GameService, out
from .protocol import PROTOCOL, b64, unb64
from .transport import HostTransport
from .world import FORMAT, WorldError, header_of, host_config, open_session, pack, packs_for, unpack

log = logging.getLogger("as_engine.host")

DROPPED = frozenset({"progress_plan", "progress", "progress_done", "activity", "state", "turn_progress",
                     "worldgen_progress"})


class HostBackground(BackgroundRunner):
    """HOST-18: between turns the host asks for the quiet hours ('quiet'); nothing starts on its own."""

    def start(self, session):
        return None


class HostError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


class HostService(GameService):
    def __init__(self, config: Any, link: Any):
        self.link = link
        self.host_transport = HostTransport(link)
        super().__init__(host_config(config), self.host_transport)
        self._collected: list | None = None

    # ---------------------------------------------------------------- plumbing
    @property
    def background(self):
        if self._background is None:
            self._background = HostBackground()
        return self._background

    async def push(self, msg):
        action = msg.get("action")
        if action == "turn_progress":
            d = msg["data"]
            self.link.notify("progress", {"stage": d.get("stage"), "label": d.get("label"), "pct": d.get("pct")})
            return
        if action == "worldgen_progress":
            d = msg["data"]
            self.link.notify("progress", {"stage": d.get("stage"), "label": d.get("label"), "pct": d.get("pct")})
            return
        if action in DROPPED:
            return
        if self._collected is not None:
            self._collected.append(msg)

    def _world(self) -> dict:
        import hashlib
        s = self.session
        data = pack(s.store, s.extras.get("packs", []))
        return {"world": b64(data), "world_sha256": hashlib.sha256(data).hexdigest(),
                "turn": s.store.query_one("SELECT turn_index FROM world_clock")[0]}

    def _mark(self):
        if self.session is None:
            return None
        st = self.session.store
        return (st.conn.total_changes, st.query_one("SELECT COALESCE(MAX(seq), 0) FROM events")[0],
                st.query_one("SELECT turn_index FROM world_clock")[0])

    def _keep(self, before) -> bool:
        from .fork import REPLAYABLE
        st = self.session.store
        _changes, seq, turn_before = before
        turn_after = st.query_one("SELECT turn_index FROM world_clock")[0]
        rows = st.query("SELECT type, turn_index FROM events WHERE seq > ? ORDER BY seq", (seq,))
        for r in rows:
            between = turn_after == turn_before or r["turn_index"] < turn_after
            if between and r["type"] not in REPLAYABLE:
                return True
        return False

    async def handle(self, kind: str, payload: Any) -> dict:
        from ..service import game_service as G
        from ..service.runs import RunError
        before = self._mark()
        self._collected = []
        try:
            got = await getattr(self, "h_" + kind.replace(".", "_"))(payload)
        except (G.ServiceError, RunError, WorldError, HostError) as e:
            return {"error": {"code": e.code, "message": e.message}}
        finally:
            collected, self._collected = self._collected, None
        if collected:
            got["messages"] = got.get("messages", []) + collected
        if self.session is not None and kind not in ("save", "open", "fork", "begin", "hello", "ping", "close", "cancel"):
            if before is not None and self._mark()[0] != before[0]:
                got.update(self._world())
                got["keep"] = self._keep(before)
        return got

    # ---------------------------------------------------------------- requests
    async def h_hello(self, p):
        import as_engine
        from ..kernel.store import SCHEMA_VERSION
        from ..lanes import seal
        return {"engine": as_engine.__version__, "protocol": PROTOCOL, "world_format": FORMAT, "schema": SCHEMA_VERSION,
                "sealed": seal.sealed()}

    async def h_ping(self, p):
        return {"pong": True}

    async def h_close(self, p):
        if self.turn_task is not None and not self.turn_task.done():
            self.turn_task.cancel()
        self._close()
        return {}

    async def h_menu(self, p):
        from ..contracts.settings import RunSettings
        msgs = await self.on_pcs_list(None)
        cards = msgs[0]["data"]["cards"] if msgs else []
        return {"pcs": cards, "settings": RunSettings.model_json_schema(), "defaults": RunSettings().model_dump(mode="json")}

    async def h_open(self, p):
        from ..contracts.protocol import OutStory, OutView
        self._not_busy()
        header, store = unpack(unb64(p.world))
        await self.background.cancel()
        self._close()
        self.session = open_session(self.config, store, self.host_transport, header.get("packs") or ["core"])
        return {"turn": header.get("turn", 0), "notices": list(self.session.extras.get("notices", [])),
                "messages": [out("view", OutView(view=self._view())), out("story", OutStory(entries=self._story()))]}

    async def h_save(self, p):
        if self.session is None:
            raise HostError("no_run", "No story is open.")
        return self._world()

    async def h_begin(self, p):
        from ..contracts.protocol import OutStory, OutView
        from ..contracts.settings import RunSettings
        self._not_busy()
        try:
            settings = RunSettings.model_validate(p.settings)
        except Exception as e:  # noqa: BLE001 — pydantic's message names the field, never content
            raise HostError("bad_settings", "Those settings are not valid: " + str(e).splitlines()[0][:200]) from e
        self.host_transport.new_turn()
        self.host_transport.add_recorded([a.model_dump() for a in p.answers])
        await self.background.cancel()
        self._close()
        loop = asyncio.get_running_loop()

        async def progress(pr):
            await self.push(out("worldgen_progress", _wg_progress(pr)))
        self.worldgen_task = loop.create_task(create_world(self.config, p.pc_ref, settings, self.host_transport,
                                                           self.link, progress))
        from ..kernel.errors import SettingsError
        from ..world.worldgen.pipeline import WorldgenAborted
        try:
            s, report = await self.worldgen_task
        except WorldgenAborted as e:
            raise HostError("worldgen_aborted", str(e)) from e
        except SettingsError as e:
            raise HostError("bad_settings", str(e)) from e
        finally:
            self.worldgen_task = None
        self.session = s
        got = self._world()
        if report.genesis is not None:
            from ..kernel.store import Store
            g = Store.from_bytes(report.genesis)
            try:
                got["genesis"] = b64(pack(g, s.extras.get("packs", [])))
            finally:
                g.close()
        got.update({"world_summary": report.world, "notices": list(s.extras.get("notices", [])),
                    "messages": [out("view", OutView(view=self._view())), out("story", OutStory(entries=self._story()))]})
        return got

    async def _hosted(self, play) -> dict:
        from ..service.session import change_settings
        from .governor import TIERS, LinkGovernor
        if self.session is None:
            raise HostError("no_run", "No story is open.")
        gov = LinkGovernor(self.link.request, tier=play.tier, focus=play.focus, recorded=dict(play.decisions))
        if not self.busy:
            self.host_transport.new_turn()
        self.host_transport.add_recorded([a.model_dump() for a in play.answers])
        self.host_transport.governor = gov
        try:
            depth = TIERS[gov.tier]["depth"]
            s = self.session
            if s.settings.turn_depth != depth and not self.busy:
                with s.store.transaction() as tx:
                    change_settings(tx, s, {"turn_depth": depth})
            await gov.start_turn(s.config)
            replies = await play.run()
            t = self.turn_task
            if t is not None:
                await asyncio.wait({t})          # a turn the host cancelled ends here; this request is not cancelled
        finally:
            self.host_transport.governor = None
        return {"messages": [m for m in replies if m.get("action") not in DROPPED], "steps": dict(gov.decisions)}

    async def h_turn(self, p):
        from ..contracts.protocol import InTurnSubmit
        sub = InTurnSubmit(mode=p.mode, text=p.text, suggestion_ref=p.suggestion_ref, addressee_refs=list(p.addressee_refs))
        return await self._hosted(_Play(p, lambda: self.on_turn_submit(sub)))

    async def h_compose(self, p):
        from ..contracts.protocol import InTurnCompose
        msg = InTurnCompose(act=p.act, say=p.say, cheat=p.cheat, to=list(p.to))
        return await self._hosted(_Play(p, lambda: self.on_turn_compose(msg)))

    async def h_cancel(self, p):
        w = self.worldgen_task
        if w is not None and not w.done():          # Stop while a world is made: nothing of it is kept
            w.cancel()
            await asyncio.wait({w})
            return {"messages": []}
        return {"messages": await self.on_turn_cancel(None)}

    async def h_view(self, p):
        return {"messages": await self.on_view_get(None)}

    async def h_story(self, p):
        return {"messages": await self.on_story_get(None)}

    async def h_settings_get(self, p):
        return {"messages": await self.on_settings_get(None)}

    async def h_settings_set(self, p):
        from ..contracts.protocol import InSettingsSet
        return {"messages": await self.on_settings_set(InSettingsSet(patch=p.patch))}

    async def h_code_enter(self, p):
        from ..contracts.protocol import InCodeEnter
        return {"messages": await self.on_code_enter(InCodeEnter(code=p.code))}

    async def h_cheat_dictionary(self, p):
        return {"messages": await self.on_cheat_dictionary_get(None)}

    async def h_death_reveal(self, p):
        return {"messages": await self.on_death_reveal(None)}

    async def h_quiet(self, p):
        if self.session is None:
            raise HostError("no_run", "No story is open.")
        self._not_busy()
        self.host_transport.new_turn()
        self.host_transport.add_recorded([a.model_dump() for a in p.answers])

        async def quiet_progress(done, total):
            self.link.notify("progress", {"stage": "quiet", "label": "The quiet hours…", "pct": round(100 * done / max(1, total), 1)})
        if self.config.background_cognition:
            await self.background.catch_up(self.session, quiet_progress)
        return {"done": True}

    async def h_fork(self, p):
        from ..contracts.protocol import OutStory, OutView
        from .fork import fork
        self._not_busy()
        await self.background.cancel()
        self._close()
        from ..lanes.client import LaneClient
        s = await fork(self.config, unb64(p.base), unb64(p.head), p.turn)
        s.client = LaneClient(s.config, self.host_transport)          # the replay is over: the host answers again
        self.session = s
        got = self._world()
        got["messages"] = [out("view", OutView(view=self._view())), out("story", OutStory(entries=self._story()))]
        return got


class _Play:
    def __init__(self, p, run):
        self.tier, self.focus, self.answers, self.decisions = p.tier, p.focus, p.answers, p.decisions
        self.run = run


def _wg_progress(pr):
    from ..contracts.protocol import OutWorldgenProgress
    return OutWorldgenProgress(stage=pr.stage, label=pr.label, pct=pr.pct, eta_s=pr.eta_s)


async def create_world(config: Any, pc_ref: str, settings: Any, transport: Any, link: Any, progress=None):
    """HOST-16 begin: service.runs.create_run in memory. Returns (Session, WorldgenReport)."""
    import hashlib
    from pathlib import Path

    from ..content.pack import cheat_records, load_canon
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    from ..kernel.clock import now
    from ..kernel.store import Store, wall_clock_iso
    from ..lanes.client import LaneClient
    from ..service._impl_runs import slug
    from ..service.runs import RunError
    from ..world.worldgen.pipeline import run_worldgen
    cd = Path(config.content_dir)
    own = pc_ref.split(":", 1)[0]
    dirs = [cd / "core"] + [cd / p for p in settings.pack_ids
                            if p != "core" and (not p.startswith("cheat_") or p == own)]      # CHEAT-10, CHEAT-12
    if settings.wild_card:                                                                   # CHEAT-15
        wild = sorted({r.split(":", 1)[0] for r, rec in cheat_records(cd).items() if "wild_card" in (rec.tags or [])})
        dirs += [cd / p for p in wild if cd / p not in dirs]
    canon, issues = load_canon(dirs)
    if any(i.severity == "error" for i in issues):
        raise RunError("content_missing", "A content pack this story needs has errors; check it on the Content screen.")
    try:
        pc = canon.get(pc_ref)
        ok = pc_ref.split(":", 1)[1].split("/", 1)[0] == "pc"
    except (KeyError, IndexError):
        ok = False
    if not ok:
        raise RunError("not_found", f"There is no character called {pc_ref}.")
    seed = settings.seed if settings.seed is not None else int(hashlib.sha256((wall_clock_iso() + pc_ref).encode()).hexdigest()[:15], 16)
    settings = settings.model_copy(update={"seed": seed})
    link.notify("begin.seed", {"seed": seed})
    rid = f"{slug(pc.card.display_name)}_{seed:x}"
    wid = f"w_{seed:x}"
    store = Store.create_memory(run_id=rid, seed=seed, settings_json=settings.model_dump_json(),
                                content_hash=canon.content_hash, start_ms=0, rules_json=config.rules.model_dump_json())
    try:
        store.attach(canon=canon, rules=config.rules)
        client = LaneClient(config, transport)
        report = await run_worldgen(store, client, canon, pc_ref, settings, config, run_id=rid, world_id=wid,
                                    world_dir=None, progress=progress)
        with store.transaction() as tx:
            tx.commit_event(Event(type=EventType.SETTINGS_CHANGE, writer="kernel.meta", at=now(tx), turn_index=0, origin="system",
                                  payload={"source": "worldgen", "world_id": wid},
                                  writes=[WriteRecord(op=WriteOp.UPSERT, table="meta", key={"key": "world_id"},
                                                      values={"key": "world_id", "value": wid})]))
        if pc.generation == "cheat":                                 # D-102: a life the code opened
            from ..cheats.commands import start_life
            with store.transaction() as tx:
                start_life(tx, tx.query_one("SELECT value FROM meta WHERE key='pc_actor_id'")[0], pc)
    except BaseException:
        store.close()
        raise
    s = open_session(config, store, transport, packs_for(config, dirs), run_id=rid)
    s.extras["notices"] = [f"{canon.get(ref).identity.name} is not in this world: {why}." for ref, why in report.skipped_actors] \
        + list(s.extras.get("notices", []))
    s.extras["worldgen_report"] = report
    return s, report


__all__ = ["HostService", "create_world", "header_of"]
