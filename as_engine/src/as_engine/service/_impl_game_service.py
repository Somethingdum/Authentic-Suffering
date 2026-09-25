"""Implementation of service/game_service.py."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from pydantic import ValidationError

log = logging.getLogger("as_engine.service")


def _bgmod():
    from . import background
    return background


def _G():
    from . import game_service
    return game_service


def out(action, data):
    from ..contracts.protocol import OUTBOUND_ACTIONS
    if action not in OUTBOUND_ACTIONS:
        raise ValueError(f"not an outbound action: {action}")
    return {"type": "as_game", "action": action, "data": data.model_dump(mode="json")}


def _err(code, message):
    from ..contracts.protocol import OutError
    return out("error", OutError(code=code, message=message, recoverable=True))


def _bad(e):
    first = e.errors()[0]
    where = ".".join(str(x) for x in first["loc"]) or "request"
    return _G().BAD_REQUEST.format(where=where, problem=first["msg"])


class GameService:
    def __init__(self, config, transport, *, config_path="as_config.yaml"):
        from ..lanes.client import LaneClient
        self.config = config
        self.transport = transport
        self.config_path = config_path
        self.client = LaneClient(config, transport)
        self.session = None
        self.turn_task = None
        self.turn_stage = None
        self.last_view = None
        self.last_story = None
        self._subscribers = []
        self.worldgen_task = None
        self._background = None
        self.codes_unlocked = False

    @property
    def background(self):
        if self._background is None:
            from .background import BackgroundRunner
            self._background = BackgroundRunner()
        return self._background

    # ------------------------------------------------------------------ plumbing
    def subscribe(self, fn):
        self._subscribers.append(fn)

    def unsubscribe(self, fn):
        if fn in self._subscribers:
            self._subscribers.remove(fn)

    @property
    def busy(self):
        return any(t is not None and not t.done() for t in (self.turn_task, self.worldgen_task))

    async def push(self, msg):
        for fn in list(self._subscribers):
            try:
                await fn(msg)
            except Exception:  # noqa: BLE001
                log.warning("dropping a subscriber that failed", exc_info=True)
                self.unsubscribe(fn)

    async def idle(self):
        while self.turn_task is not None:
            t = self.turn_task
            try:
                await asyncio.wait({t})
            except Exception:  # noqa: BLE001
                pass
            if self.turn_task is t:     # the task has not cleared itself (cancelled before it started)
                self.turn_task = None

    async def handle(self, message):
        from ..contracts.protocol import IN_MODELS, INBOUND_ACTIONS
        from .runs import RunError
        from .session import LockedSetting  # noqa: F401
        G = _G()
        action = message.get("action") if isinstance(message, dict) else None
        if action not in INBOUND_ACTIONS:
            return [_err("unknown_action", G.UNKNOWN_ACTION.format(action=action))]
        fields = {k: v for k, v in message.items() if k not in ("type", "action")}
        model = IN_MODELS[action]
        msg = None
        if model is not None:
            try:
                msg = model.model_validate(fields)
            except ValidationError as e:
                return [_err("bad_request", _bad(e))]
        try:
            return await getattr(self, "on_" + action)(msg)
        except G.ServiceError as e:
            return [_err(e.code, e.message)]
        except RunError as e:
            return [_err(e.code, e.message)]
        except NotImplementedError:
            return [_err("not_built_yet", G.NOT_BUILT)]
        except Exception:  # noqa: BLE001
            log.exception("GameService.%s failed", action)
            return [_err("internal", G.INTERNAL)]

    # ------------------------------------------------------------------ helpers
    def _need_run(self):
        if self.session is None:
            raise _G().ServiceError("no_run", _G().NO_RUN)

    def _not_busy(self):
        if self.busy:
            raise _G().ServiceError("busy", _G().BUSY)

    def _view(self):
        from .view import build_view
        with self.session.store.transaction() as tx:
            v = build_view(tx, self.session)
        self.last_view = v
        return v

    def _story(self):
        from ..contracts.view import StoryEntry
        rows = self.session.store.query("SELECT turn_index, kind, text, mode FROM story_log ORDER BY entry_id")
        self.last_story = [StoryEntry(turn_index=r[0], kind=r[1], text=r[2], mode=r[3]) for r in rows]
        return self.last_story

    def _state(self, screen=None):
        from ..contracts.protocol import OutState
        s = screen or ("play" if self.session is not None else "home")
        return out("state", OutState(screen=s, run_id=self.session.run_id if self.session else None, busy=self.busy))

    def _close(self):
        if self.session is not None:
            self.session.store.close()
        self.session = None
        self.last_view = None
        self.last_story = None

    # ------------------------------------------------------------------ P8 handlers
    async def on_hello(self, msg):
        import as_engine
        from ..contracts.protocol import OutWelcome
        from .runs import list_runs
        health = await self.client.refresh_health()
        ok = all(health.values())
        screen = "connect" if not ok else ("play" if self.session is not None else "home")
        return [out("welcome", OutWelcome(server_version=as_engine.__version__, screen=screen,
                                          has_runs=bool(list_runs(self.config)), models_ok=ok))]

    async def on_get_state(self, msg):
        return [self._state()]

    async def on_models_list(self, msg):
        from ..contracts.common import Lane
        from ..contracts.protocol import OutModels
        res = []
        for lane in (Lane.A, Lane.B):
            lc = self.config.lanes[lane]
            try:
                models = await self.transport.list_models(lane, lc)
            except Exception:  # noqa: BLE001
                models = []
            try:
                reach = bool(await self.transport.health(lane, lc))
            except Exception:  # noqa: BLE001
                reach = False
            res.append(out("models", OutModels(lane=lane, models=models, selected=lc.model, reachable=reach)))
        return res

    async def on_models_test(self, msg):
        from ..contracts.common import CallClass
        from ..contracts.lanes import ChatMessage, LMRequest
        from ..contracts.protocol import OutModelTest
        G = _G()
        lane = msg.lane
        lc = self.config.lanes[lane]

        def result(**kw):
            return [out("model_test_result", OutModelTest(lane=lane, **kw))]
        try:
            healthy = bool(await self.transport.health(lane, lc))
        except Exception:  # noqa: BLE001
            healthy = False
        if not healthy:
            return result(ok=False, detail=G.NOT_ANSWERING.format(url=lc.base_url))
        try:
            models = await self.transport.list_models(lane, lc)
        except Exception:  # noqa: BLE001
            models = []
        if lc.model not in models:
            return result(ok=False, detail=G.MODEL_MISSING.format(model=lc.model))
        msgs = [ChatMessage(role="system", content="You answer in one word."), ChatMessage(role="user", content="Say: ready")]
        hello = await self.client.call(LMRequest(call_class=CallClass.PROBE, lane=lane, messages=msgs, thinking=False,
                                                 max_tokens=64, deadline_s=30))
        if hello.parse_status != "ok" or not (hello.text or "").strip():
            return result(ok=False, detail=G.NO_ANSWER)
        js = await self.client.call(LMRequest(call_class=CallClass.PROBE, lane=lane, messages=msgs, thinking=False, max_tokens=64,
                                              deadline_s=30, schema_name="probe", json_schema=G.PROBE_SCHEMA), G.ProbeAnswer)
        sok = js.parse_status == "ok"
        detail = G.WORKING.format(secs=hello.latency_ms / 1000) + ("" if sok else " " + G.NO_JSON)
        return result(ok=True, detail=detail, latency_ms=hello.latency_ms, structured_ok=sok, thinking_ok=None)

    async def on_config_get(self, msg):
        from ..contracts.protocol import OutConfig
        return [out("config", OutConfig(lanes=self.config.lanes, background_cognition=self.config.background_cognition))]

    async def on_config_set(self, msg):
        from ..config_loader import save_engine_config
        from ..contracts.common import Lane
        from ..contracts.settings import LaneConfig
        from ..lanes.client import LaneClient
        G = _G()
        self._not_busy()
        patch = msg.patch
        for k in patch:
            if k not in ("lanes", "background_cognition"):
                raise G.ServiceError("bad_request", G.CONFIG_KEYS.format(key=k))
        lanes = dict(self.config.lanes)
        for lk, lp in (patch.get("lanes") or {}).items():
            if lk not in ("A", "B"):
                raise G.ServiceError("bad_request", G.CONFIG_KEYS.format(key=f"lanes.{lk}"))
            for f in lp:
                if f not in G.CONFIG_LANE_FIELDS:
                    raise G.ServiceError("bad_request", G.CONFIG_KEYS.format(key=f"lanes.{lk}.{f}"))
            try:
                lanes[Lane(lk)] = LaneConfig.model_validate({**lanes[Lane(lk)].model_dump(mode="json"), **lp})
            except ValidationError as e:
                raise G.ServiceError("bad_request", _bad(e)) from None
        upd = {"lanes": lanes}
        if "background_cognition" in patch:
            if not isinstance(patch["background_cognition"], bool):
                raise G.ServiceError("bad_request", G.BAD_REQUEST.format(where="background_cognition", problem="must be true or false"))
            upd["background_cognition"] = patch["background_cognition"]
        new = self.config.model_copy(update=upd)
        save_engine_config(new, self.config_path)
        self.config = new
        self.client = LaneClient(new, self.transport)
        if self.session is not None:
            self.session.config = self.session.config.model_copy(update=upd)
            self.session.client.config = self.session.config
        return await self.on_config_get(None)

    def _pack_dirs(self):
        root = Path(self.config.content_dir)
        return [d for d in sorted(root.iterdir()) if d.is_dir() and (d / "pack.yaml").exists()] if root.exists() else []

    async def on_packs_list(self, msg):
        import yaml
        from ..content.pack import load_canon
        from ..contracts.content import PackManifest
        from ..contracts.protocol import OutPacks, PackView
        core = Path(self.config.content_dir) / "core"
        res = []
        for d in self._pack_dirs():
            man = PackManifest.model_validate(yaml.safe_load((d / "pack.yaml").read_text(encoding="utf-8")))
            canon, _issues = load_canon([core] + ([] if d.resolve() == core.resolve() else [d]))
            n = sum(1 for recs in canon.by_kind.values() for ref in recs if ref.startswith(f"{man.id}:"))
            res.append(PackView(pack_id=man.id, name=man.name, version=man.version, description=man.description, records=n,
                                core=man.id == "core"))
        return [out("packs", OutPacks(packs=res))]

    async def on_content_validate(self, msg):
        from ..content.pack import load_canon
        from ..contracts.protocol import OutContentReport
        G = _G()
        core = Path(self.config.content_dir) / "core"
        d = Path(self.config.content_dir) / msg.pack_id
        if not (d / "pack.yaml").exists():
            raise G.ServiceError("not_found", G.PACK_NOT_FOUND.format(pack_id=msg.pack_id))
        canon, issues = load_canon([core] + ([] if d.resolve() == core.resolve() else [d]))
        errors = [i.message for i in issues if i.severity == "error"]
        warnings = [i.message for i in issues if i.severity != "error"]
        counts = {}
        for kind, recs in canon.by_kind.items():
            n = sum(1 for ref in recs if ref.startswith(f"{msg.pack_id}:"))
            if n:
                counts[kind] = n
        return [out("content_report", OutContentReport(pack_id=msg.pack_id, ok=not errors, errors=errors, warnings=warnings,
                                                       counts=counts))]

    async def on_runs_list(self, msg):
        from ..contracts.protocol import OutRuns
        from .runs import list_runs
        return [out("runs", OutRuns(runs=list_runs(self.config)))]

    async def on_run_load(self, msg):
        from ..contracts.protocol import OutRunLoaded, OutStory, OutView
        from .runs import RunError, load_run
        self._not_busy()
        await self.background.cancel()
        self._close()
        try:
            s = load_run(self.config, msg.run_id, self.transport, msg.save_slot)
        except RunError as e:
            return [_err(e.code, e.message), self._state("home")]
        self.session = s
        name = s.store.query_one("SELECT display_name FROM actors WHERE actor_id=?", (s.pc_id,))[0]
        loaded = OutRunLoaded(run_id=s.run_id, pc_name=name, notices=list(s.extras.get("notices", [])), settings=s.settings,
                              ironman=s.settings.save_mode == "ironman", sandbox=s.store.meta("sandbox") == "1")
        return [out("run_loaded", loaded), out("view", OutView(view=self._view())), out("story", OutStory(entries=self._story()))]

    async def on_run_close(self, msg):
        self._not_busy()
        self._need_run()
        await self.background.cancel()
        self._close()
        return [self._state("home")] + await self.on_runs_list(None)

    async def on_run_save(self, msg):
        from ..contracts.protocol import OutSaved
        from .runs import save_run
        self._need_run()
        self._not_busy()
        p = save_run(self.session, msg.slot_name)
        t = self.session.store.query_one("SELECT turn_index FROM world_clock")[0]
        return [out("saved", OutSaved(slot=Path(p).stem, label=msg.slot_name, turn_index=t))]

    async def on_run_delete(self, msg):
        from .runs import delete_run
        G = _G()
        if self.session is not None and self.session.run_id == msg.run_id:
            raise G.ServiceError("run_open", G.RUN_OPEN)
        delete_run(self.config, msg.run_id)
        return await self.on_runs_list(None)

    async def on_view_get(self, msg):
        from ..contracts.protocol import OutView
        self._need_run()
        if self.busy:
            if self.last_view is None:
                self._not_busy()
            return [out("view", OutView(view=self.last_view))]
        return [out("view", OutView(view=self._view()))]

    async def on_story_get(self, msg):
        from ..contracts.protocol import OutStory
        self._need_run()
        if self.busy:
            if self.last_story is None:
                self._not_busy()
            return [out("story", OutStory(entries=self.last_story))]
        return [out("story", OutStory(entries=self._story()))]

    async def on_settings_get(self, msg):
        from ..contracts.protocol import OutSettings
        from .session import CHANGEABLE_SETTINGS
        self._need_run()
        return [out("settings", OutSettings(settings=self.session.settings, changeable=list(CHANGEABLE_SETTINGS)))]

    async def on_settings_set(self, msg):
        from ..contracts.protocol import OutView
        from .session import LockedSetting, change_settings
        G = _G()
        self._need_run()
        self._not_busy()
        try:
            with self.session.store.transaction() as tx:
                change_settings(tx, self.session, msg.patch)
        except LockedSetting as e:
            raise G.ServiceError("locked", G.LOCKED.format(field=e.field_name)) from None
        except (ValueError, ValidationError):
            raise G.ServiceError("bad_request", G.BAD_SETTING) from None
        return await self.on_settings_get(None) + [out("view", OutView(view=self._view()))]

    async def on_dev_get(self, msg):
        from ..contracts.protocol import OutDevData
        G = _G()
        self._need_run()
        if not self.session.settings.dev_mode:
            raise G.ServiceError("dev_mode_off", G.DEV_MODE_OFF)
        self._not_busy()
        st = self.session.store
        t = msg.turn_index if msg.turn_index is not None else st.query_one("SELECT turn_index FROM world_clock")[0]

        def rows(sql, cols, parse=()):
            res = []
            for r in st.query(sql, (t,)):
                d = {c: r[c] for c in cols}
                for p in parse:
                    d[p] = json.loads(d[p]) if isinstance(d[p], str) else d[p]
                res.append(d)
            return res
        call_cols = ["seq", "call_class", "lane", "actor_id", "status", "latency_ms"]
        what = msg.what
        if what == "trace":
            data = rows("SELECT * FROM turn_ledger WHERE turn_index=? ORDER BY stage", ["stage", "status", "run_count", "detail"], ["detail"])
        elif what == "packets":
            data = rows("SELECT * FROM lm_calls WHERE turn_index=? AND call_class IN ('actor_cognition','actor_reaction','intent_repair') "
                        "ORDER BY seq", call_cols + ["response_text"])
        elif what == "intents":
            data = rows("SELECT * FROM events WHERE turn_index=? AND type IN ('ACTION_START','ACTION_BLOCKED','DEGRADED_FALLBACK','SPEECH') "
                        "ORDER BY seq", ["seq", "type", "at", "actor_id", "payload"], ["payload"])
        elif what == "events":
            data = rows("SELECT * FROM events WHERE turn_index=? ORDER BY seq",
                        ["seq", "event_id", "type", "at", "actor_id", "writer", "payload"], ["payload"])
        elif what == "gate":
            data = rows("SELECT * FROM commit_gate_log WHERE turn_index=?",
                        ["session_bits", "world_bits", "entities_bits", "global_bits", "passed", "failures"], ["failures"])
        elif what == "errors":
            data = rows("SELECT * FROM error_repair_log WHERE turn_index=? ORDER BY entry_id",
                        ["entry_id", "kind", "stage", "rule_id", "detail", "repaired"], ["detail"])
        else:
            data = rows("SELECT * FROM lm_calls WHERE turn_index=? ORDER BY seq",
                        call_cols + ["prompt_tokens", "completion_tokens", "response_text"])
        return [out("dev_data", OutDevData(what=what, turn_index=t, rows=data))]

    async def on_turn_submit(self, msg):
        from ..contracts.protocol import OutGuideAnswer, OutStory, OutTurnRejected, OutView
        from . import guide
        G = _G()

        def reject(code, message):
            return [out("turn_rejected", OutTurnRejected(reason_code=code, message=message))]
        if self.session is None:
            return reject("no_run", G.NO_RUN)
        if self.busy:
            return reject("busy", G.BUSY)
        from ..cheats import commands as cheats
        from ..contracts.protocol import OutCheat
        text = msg.text or ""
        if cheats.detect_activation(text):                     # CHEAT-01: the line is consumed
            r = cheats.activate(self.session)
            return [out("cheat_activated", OutCheat(persona_line=r.persona_line, ok=r.ok, detail=r.detail)),
                    out("story", OutStory(entries=self._story()))]
        if self.session.store.meta("cheat_active") == "1" and text.strip().startswith("/"):
            cmd = cheats.parse(text)
            if isinstance(cmd, cheats.CheatParseError):
                return [out("cheat_result", OutCheat(persona_line=cmd.message, ok=False, detail=""))]
            r = await cheats.execute(self.session, cmd)
            return [out("cheat_result", OutCheat(persona_line=r.persona_line, ok=r.ok, detail=r.detail)),
                    out("view", OutView(view=self._view())), out("story", OutStory(entries=self._story()))]
        if self.session.store.query_one("SELECT alive FROM bodies WHERE body_id=?", (self.session.pc_id,))[0] == 0:
            return reject("dead", G.DEAD)
        if msg.mode == "ask":
            q = msg.text.strip()
            if not q:
                return reject("empty", G.EMPTY_QUESTION)
            text = await guide.answer(self.session, q, self.last_view or self._view())
            return [out("guide_answer", OutGuideAnswer(text=text)), out("story", OutStory(entries=self._story()))]
        self.turn_stage = None
        self.turn_task = asyncio.create_task(self._play(msg))
        return [self._state("play")]

    async def _play(self, msg):
        from ..contracts.protocol import OutError, OutStory, OutTurnProgress, OutTurnRejected, OutTurnResult
        from ..turn import pipeline
        G = _G()
        loop = asyncio.get_running_loop()
        start = loop.time()
        s = self.session
        T = s.store.query_one("SELECT turn_index FROM world_clock")[0] + 1
        cancelled = False

        from ..contracts.protocol import OUT_MODELS
        from . import progress as pv2
        dev = bool(getattr(s.settings, "dev_mode", False))

        async def push_v2(action, data):
            await self.push(out(action, OUT_MODELS[action].model_validate(data)))
        tr = pv2.Tracker("turn", f"turn-{T}", push_v2, dev=dev)
        live = {"turn": False, "quiet": None}

        async def progress(stage, label, frac):
            self.turn_stage = stage
            await self.push(out("turn_progress", OutTurnProgress(turn_index=T, stage=stage, label=label, pct=round(frac * 100, 1),
                                                                 elapsed_s=round(loop.time() - start, 1))))
            if live["turn"] and stage in pv2.TURN_STAGES:
                await tr.step(*pv2.TURN_STAGES[stage])

        async def quiet_progress(done, total):
            await progress(0, _bgmod().QUIET_HOURS, 0.0)
            if live["quiet"] is not None:
                await live["quiet"].step("quiet", "jobs", done=done, total=total)
        try:
            if self.config.background_cognition:
                if _bgmod().pending(s.store, T - 1):
                    live["quiet"] = pv2.Tracker("quiet_hours", f"quiet_hours-{T}", push_v2, dev=dev)
                    await live["quiet"].plan(pv2.quips_for(s.store.canon, "quiet_hours"))
                try:
                    await self.background.catch_up(s, quiet_progress)
                except BaseException:
                    if live["quiet"] is not None:
                        await live["quiet"].done(False)
                    raise
                if live["quiet"] is not None:
                    await live["quiet"].done(True)
            await tr.plan(pv2.quips_for(s.store.canon, "turn"))
            live["turn"] = True
            try:
                o = await pipeline.run_turn(s, msg, progress)
            except BaseException:
                await tr.done(False)
                raise
            await tr.done(o.ok)
            if o.ok:
                await self.push(out("turn_result", OutTurnResult(turn_index=o.turn_index, narration=o.narration, view=self._view(),
                                                                 notices=o.notices, degraded=o.degraded)))
                await self.push(out("story", OutStory(entries=self._story())))
                if o.died:
                    try:
                        await self.on_death()
                    except NotImplementedError:
                        await self.push(out("error", OutError(code="not_built_yet", message=G.NOT_BUILT_DEATH)))
                elif self.config.background_cognition and s.store.query_one(
                        "SELECT alive FROM bodies WHERE body_id=?", (s.pc_id,))[0] == 1:
                    self.background.start(s)
            else:
                await self.push(out("turn_rejected", OutTurnRejected(reason_code=o.rejected_code, message=o.rejected_message,
                                                                     clarify=o.clarify)))
        except asyncio.CancelledError:
            cancelled = True
            raise
        except Exception:  # noqa: BLE001
            log.exception("turn failed")
            await self.push(out("error", OutError(code="internal", message=G.INTERNAL)))
        finally:
            self.turn_task = None
            self.turn_stage = None
            if not cancelled:
                await self.push(self._state("play"))

    async def on_turn_cancel(self, msg):
        G = _G()
        t = self.turn_task
        if t is None or t.done():
            raise G.ServiceError("nothing_to_cancel", G.NOTHING_TO_CANCEL)
        if self.turn_stage is not None and self.turn_stage >= 12:
            raise G.ServiceError("too_late", G.TOO_LATE)
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
        self.turn_task = None
        self.turn_stage = None
        return [self._state("play")]

    # ------------------------------------------------------------------ later phases
    async def on_run_new(self, msg):
        from ..contracts.protocol import OutState
        G = _G()
        self._not_busy()
        if msg.world_id is not None:
            raise G.ServiceError("not_built_yet", G.NOT_BUILT)
        pack = msg.pc_ref.split(":", 1)[0]
        if pack.startswith("cheat_") and self.codes_unlocked and pack not in msg.settings.pack_ids:   # CHEAT-12
            msg = msg.model_copy(update={"settings": msg.settings.model_copy(
                update={"pack_ids": [*msg.settings.pack_ids, pack]})})
        await self.background.cancel()
        self._close()
        self.worldgen_task = asyncio.create_task(self._worldgen(msg))
        return [out("state", OutState(screen="worldgen", run_id=None, busy=True))]

    async def _worldgen(self, msg):
        import inspect  # noqa: F401
        from ..contracts.protocol import OutError, OutRunLoaded, OutState, OutStory, OutView, OutWorldgenProgress
        from ..kernel.errors import SettingsError
        from ..world.worldgen.pipeline import WorldgenAborted
        from .runs import RunError, create_run
        G = _G()
        wizard = out("state", OutState(screen="wizard", run_id=None, busy=False))

        from pathlib import Path

        from ..content.pack import load_canon
        from ..contracts.protocol import OUT_MODELS
        from . import progress as pv2
        self._worldgen_jobs = getattr(self, "_worldgen_jobs", 0) + 1

        async def push_v2(action, data):
            await self.push(out(action, OUT_MODELS[action].model_validate(data)))
        tr = pv2.Tracker("worldgen", f"worldgen-{self._worldgen_jobs}", push_v2, dev=bool(msg.settings.dev_mode))
        ok = False
        planned = False

        async def progress(p):
            await self.push(out("worldgen_progress", OutWorldgenProgress(stage=p.stage, label=p.label, pct=p.pct, eta_s=p.eta_s)))
            if p.stage != "COMMIT":
                await tr.step(p.stage, p.sub, done=p.done, total=p.total)
        try:
            try:
                cd = Path(self.config.content_dir)
                qcanon, _issues = load_canon([cd / "core"] + [cd / p for p in msg.settings.pack_ids if p != "core"])
                await tr.plan(pv2.quips_for(qcanon, "worldgen"))
                planned = True
                s = await create_run(self.config, msg.pc_ref, msg.settings, self.transport, progress=progress)
                ok = True
            finally:
                if planned:
                    await tr.done(ok)
            self.session = s
            name = s.store.query_one("SELECT display_name FROM actors WHERE actor_id=?", (s.pc_id,))[0]
            loaded = OutRunLoaded(run_id=s.run_id, pc_name=name, notices=list(s.extras.get("notices", [])), settings=s.settings,
                                  ironman=s.settings.save_mode == "ironman", sandbox=s.store.meta("sandbox") == "1")
            await self.push(out("run_loaded", loaded))
            await self.push(out("view", OutView(view=self._view())))
            await self.push(out("story", OutStory(entries=self._story())))
            await self.push(out("state", OutState(screen="play", run_id=s.run_id, busy=False)))
        except asyncio.CancelledError:
            raise
        except WorldgenAborted as e:
            await self.push(out("error", OutError(code="worldgen_aborted", message=str(e))))
            await self.push(wizard)
        except RunError as e:
            await self.push(out("error", OutError(code=e.code, message=e.message)))
            await self.push(wizard)
        except SettingsError as e:
            await self.push(out("error", OutError(code="bad_settings", message=str(e))))
            await self.push(wizard)
        except Exception:  # noqa: BLE001
            log.exception("worldgen failed")
            await self.push(out("error", OutError(code="internal", message=G.INTERNAL)))
            await self.push(wizard)
        finally:
            self.worldgen_task = None

    async def on_worldgen_cancel(self, msg):
        from ..contracts.protocol import OutState
        G = _G()
        t = self.worldgen_task
        if t is None or t.done():
            raise G.ServiceError("nothing_to_cancel", G.NO_WORLDGEN)
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
        self.worldgen_task = None
        return [out("state", OutState(screen="wizard", run_id=None, busy=False))]

    async def on_pcs_list(self, msg):
        from ..content.pack import load_canon
        from ..contracts.protocol import OutPCs
        from ..contracts.view import PCCardView
        from ..world.worldgen.tables import STARTS_AS
        core = Path(self.config.content_dir) / "core"
        dirs = [core] + [d for d in self._pack_dirs() if d.resolve() != core.resolve()
                         and (self.codes_unlocked or not d.name.startswith("cheat_"))]     # CHEAT-10, CHEAT-12
        canon, _issues = load_canon(dirs)
        cards = []
        for ref in canon.refs("pc"):
            pc = canon.get(ref)
            r = pc.days_since_fall_range
            first = pc.card.display_name.split()[0]
            cards.append(PCCardView(ref=ref, display_name=pc.card.display_name, one_line_identity=pc.card.one_line_identity,
                                    survives_by=pc.card.pc_card_survival, starts_as=STARTS_AS[pc.faction_start_type],
                                    note=pc.card.pc_selection_note, source="pack", warnings=[],
                                    world_age_days=[r[0], r[1]] if r else None,
                                    world_age_note=(f"{first}'s story needs a world {r[0] // 365}-{r[1] // 365} years after the Fall."
                                                    if r else None)))
        return [out("pcs", OutPCs(cards=cards))]

    async def on_code_enter(self, msg):
        from ..cheats import commands as cheats
        from ..contracts.protocol import OutCheat, OutCodeResult, OutStory
        if self.session is not None:
            self._not_busy()
        if not cheats.detect_activation(msg.code):
            return [out("code_result", OutCodeResult(accepted=False))]
        self.codes_unlocked = True
        replies = [out("code_result", OutCodeResult(accepted=True))]
        if self.session is not None:
            r = cheats.activate(self.session)
            replies += [out("cheat_activated", OutCheat(persona_line=r.persona_line, ok=r.ok, detail=r.detail)),
                        out("story", OutStory(entries=self._story()))]
        return replies

    async def on_content_import(self, msg):
        raise NotImplementedError("P12")

    async def on_intake_start(self, msg):
        raise NotImplementedError("P12")

    async def on_quickmake_pc(self, msg):
        raise NotImplementedError("P12")

    async def on_death_reveal(self, msg):
        raise NotImplementedError("P12")

    async def on_new_life_here(self, msg):
        raise NotImplementedError("P12")

    async def on_worlds_list(self, msg):
        raise NotImplementedError("P12")

    async def on_world_export(self, msg):
        raise NotImplementedError("P12")

    async def on_world_import(self, msg):
        raise NotImplementedError("P12")

    async def on_death(self):
        raise NotImplementedError("P12")


def get_service(config=None, transport=None):
    G = _G()
    if G._SERVICE is None:
        G._SERVICE = G.GameService(config, transport)
    return G._SERVICE
