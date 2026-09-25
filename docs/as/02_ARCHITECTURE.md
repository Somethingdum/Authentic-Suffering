# 02 — Architecture

## 1. The decision: fork Talemate, replace its story loop, keep its shell

Talemate 0.39.0 (AGPL-3.0, Python 3.11–3.13 backend + Vue 3/Vuetify 3 frontend) was inspected at
source level before this spec was written. What it gives us, and what it cannot:

| Talemate part | Used? | Why |
|---|---|---|
| Windows/Linux installers (`install.bat`, embedded Python, uv, portable Node), `start.bat`, `update.bat` | **Yes** | One-click install and update on your Windows machines |
| WebSocket server with plugin routing (`server/websocket_server.py`, `server/websocket_plugin.py`) | **Yes** | Our game registers one plugin, router `as_game` |
| Frontend build (Vite, Vuetify 3, served by `frontend_wsgi.py` via uvicorn) | **Yes** | The new Play UI is a second Vue app shell in the same build |
| TTS agent (Kokoro / Chatterbox / F5 / ElevenLabs …) | **Optional (P12)** | "Read narration aloud" setting |
| The original Talemate UI | **Optional** | Reachable as **Workshop** (`?ui=workshop`) for power users; never required |
| Talemate's scene loop, conversation/narrator/director agents, scene history, ChromaDB memory, node editor | **No** | Talemate builds every character prompt from one shared scene history. That breaks Skull Law (L1): a character would "know" things said in rooms they were not in. AS replaces the whole storytelling loop with `as_engine` |
| Talemate's LLM clients | **No** (AS has its own lane client) | Talemate's LM Studio client uses the text-completions endpoint; AS needs chat completions + JSON-schema constrained output and per-lane concurrency |

So: **Talemate is the host (install, run, serve, talk); `as_engine` is the game.** This keeps the
fork's diff against upstream small (list in §4) so future Talemate releases can be merged.

## 2. Hardware and models ("respectively")

| Lane | Machine | Model | Role |
|---|---|---|---|
| **A** | `msi` desktop | **Nemotron Cascade 2 30B-A3B** (1M ctx, thinking + instruct modes, strong instruction following) | Narration, HOT actor cognition (thinking on), worldgen history/people/opening, dossier intake, quick-make |
| **B** | laptop (RTX 5070 8 GB + 32 GB RAM) | **NVIDIA Nemotron 3.5 Lightning 30B-A3B** (built for fast tool calls and structured output) | Player intake, WARM actor cognition, memory writeback, portrayal audit, render lint judge, rumours, guide, summaries, reflection |

- Both run **simultaneously**; each machine holds **one** model. A lane never swaps models
  mid-session (LANE-05 hard stop).
- **LM Link**: when both machines are linked, both models are reachable through the desktop's
  `http://localhost:1234/v1` by model key. The game runs on the desktop. Lanes can also point at two
  different base URLs.
- The audit calls on Lane B judge work produced on Lane A by a *different model* — the strongest
  form of "producer ≠ judge" (L13).
- Suggested LM Studio load settings: Lane A context 32k, Lane B context 16k; flash attention on;
  "max concurrent predictions" 1 until `tools/as/bench.py` shows the laptop handles 2.

## 3. Process model

```
 Browser (Play UI, Vue)            Talemate backend process (Python 3.11, asyncio)
 ┌──────────────────┐   ws :5050   ┌───────────────────────────────────────────────────────────┐
 │ PlayApp.vue      │ ───────────► │ WebsocketHandler.routes["as_game"] = AsGamePlugin          │
 │  Connect / Home  │ ◄─────────── │     │ forwards dict -> GameService.handle(dict)            │
 │  Wizard / Play   │  as_game msgs│     ▼                                                      │
 │  Death / Dev     │              │ as_engine.service.GameService (process singleton)          │
 └──────────────────┘              │   Session: Store(SQLite) + Canon + Rng + LaneClient        │
                                   │   turn.pipeline.run_turn (20 stages)                        │
                                   │        │ HttpTransport (httpx)                              │
                                   └────────┼────────────────────────────────────────────────────┘
                                            ▼
                         LM Studio :1234 ──(LM Link)──► laptop: Lightning (Lane B)
                          desktop: Cascade (Lane A)
```

- One backend process. `GameService` is a process-wide singleton so a browser reload reconnects to
  the running game (PROTO-02).
- Talemate reads one connection's messages one at a time and awaits each handler
  (`server/api.py`), so a long job cannot run inside `handle`: a turn runs as a background asyncio
  task, `turn_submit` answers at once, and progress and the result are pushed to every subscribed
  connection (PROTO-04). That is also what lets Stop (`turn_cancel`) arrive while a turn runs.
- SQLite work is milliseconds; model calls are awaited with `httpx.AsyncClient`. Heavy CPU steps
  (worldgen layout, content compile) run in `asyncio.to_thread`.
- The engine never touches the network except the configured lane URLs (no web access for the
  simulation, ever — plan §13.1 law).

## 4. Repository layout (fork root)

```
AGENTS.md                         builder rules (DSH loads it into every session)
as_config.example.yaml            install config template -> copy to as_config.yaml (git-ignored)
as_engine/                        THE GAME ENGINE — separate package, no talemate imports
  pyproject.toml                  package 'as-engine'
  src/as_engine/
    contracts/                    pydantic contracts (data model in code)
    kernel/                       store, schema.sql, ownership, ids, clock, rng, events, truth, hashing
    lanes/                        transports, client, parse, schemas, repair, scheduler, calllog, requests
    content/                      pack loader/validator/compiler, importers, intake
    physical/  sense/             space, bodies, objects; acoustics, optics
    mind/                         perception, packet, retrieval, affordance, actor, resolve,
                                  firewall, memory, mind
    action/                       intent, checks, conflict, effects, resolve, propagate, cascade,
                                  reactions, tasks
    society/  world/              society layer; worldgen, infected, worldmove, traces, decay, rumours
    narration/                    narrator, lint, location, style
    audit/                        commit gate (58 bits), portrayal, abuse
    turn/                         pipeline (20 stages), select, intake, cognition, timers
    cheats/                       activation, parser, executor, persona
    service/                      session, runs, view, replay, death, game_service (UI protocol)
    prompts/                      Jinja templates + render.py
    testing/                      fake_lm.py (implemented), scenario.py (to implement)
    cli.py
  tests/                          contract/ (protected), unit/, sim/, live/, fixtures/
as_content/packs/core/            core content pack (canon infected, items, affordances, laws, …)
as_content/packs/my_content/      where YOUR imports and edits go (created on first import)
as_runs/                          saves (git-ignored)
src/talemate/server/as_game_plugin.py   the only backend file added inside talemate
tests/test_as_game_plugin.py      the Talemate-side plugin test (protected)
talemate_frontend/src/play/       the Play UI (new)
tools/as/                         setup.py, gate.py, doctor.py, protect.py (+ protected_manifest.json),
                                  probe.py, bench.py, eval.py
docs/as/                          this spec
.dsh/skills/<name>/SKILL.md       on-demand builder skills (DSH)
.dsh/hooks.json                   harness hooks (written by tools/as/setup.py; git-ignored)
.claude/settings.json             the same hooks for the per-workspace hook bridge (git-ignored upstream)
```

### 4.1 Upstream files the fork modifies (keep this list exact — nothing else upstream changes)

| File | Change |
|---|---|
| `src/talemate/server/websocket_server.py` | `from talemate.server import as_game_plugin` and add `as_game_plugin.AsGamePlugin.router: as_game_plugin.AsGamePlugin(self),` to `self.routes` |
| `talemate_frontend/src/App.vue` | Render `PlayApp` by default; render `TalemateApp` when the URL has `?ui=workshop` |
| `talemate_frontend/package.json` + `talemate_frontend/pnpm-lock.yaml` | devDependencies `"vitest": "^3.2.4"`, `"@vue/test-utils": "^2.4.6"`, `"jsdom": "^26.1.0"`; script `"test:play": "vitest run src/play"`. The frontend uses **pnpm through corepack** and the install scripts run `pnpm install --frozen-lockfile`, so the lockfile must be regenerated and committed: `cd talemate_frontend && corepack pnpm install` |
| `talemate_frontend/vite.config.mjs` | the config is a function returning an object; add to that returned object: `test: { environment: 'jsdom', globals: true, setupFiles: ['src/play/__tests__/setup.js'], server: { deps: { inline: ['vuetify'] } } }` |
| `install.bat` | after the line `"%PYTHON%" -m uv sync …`: `"%PYTHON%" -m uv pip install -e "./as_engine[dev]" \|\| CALL :die "as_engine install failed."` |
| `update.bat` | after the line `embedded_python\python.exe -m uv sync …` (an exact sync removes packages Talemate's lock does not list): `embedded_python\python.exe -m uv pip install -e "./as_engine[dev]" \|\| CALL :die "as_engine install failed."` |
| `install.sh`, `update.sh` | after the line `uv pip install -e ".[dev]"`: `uv pip install -e "./as_engine[dev]"` |
| `src/talemate/server/run.py` | D-104 (SEAL-04): its first import is `from as_engine.lanes import seal`, then `seal.install_from_config(load_engine_config("as_config.yaml"))` — on any problem `seal.install([])` and a printed line; `install_punkt()` is started only when not sealed (`tools/as/setup.py` fetches punkt at install) |
| `start.sh`, `start-backend.sh`, `start.bat`, `start-backend.bat`, `start-local.bat` | D-104 (SEAL-05): `uv run --offline --no-sync …` and `--host 127.0.0.1` |
| `start-frontend.sh`, `start-frontend.bat`, `start-debug.bat` | D-104 (SEAL-05): `--host 127.0.0.1` |
| `docker-compose.cpu.yml` | D-104 (SEAL-05): both ports published as `127.0.0.1:<port>:<port>` |
| `talemate_frontend/src/plugins/webfontloader.js` | D-104 (SEAL-05): `loadFonts` loads nothing (Talemate asked Google Fonts for Roboto on every page load) |
| `.gitignore` | `as_runs/`, `as_content/_compiled/`, `as_config.yaml`, `.dsh/hooks.json` (`.claude` is already ignored upstream). `tools/as/setup.py` adds these lines at install, so this change is already made when P8 starts |

Every other change lives in new files. `tools/as/gate.py --upstream-diff` lists upstream files that
differ from tag `0.39.0` and fails if one is not in this table.

## 5. The engine: bands, owners, boundaries

Twenty-nine-plus modules in eight bands (plan §5.1 carried, adapted to Python packages). The wall
matters most in three places, each enforced by a test:

1. **`kernel.store` is the only writer.** World tables change only through `Tx.commit_event`;
   each WriteRecord's table must be owned by the event's `writer` (STORE-01/02).
2. **`kernel.rng` is the only entropy door** (DET-10/11: `random`, `secrets`, `uuid4`, `time.time`,
   `os.urandom` are banned under `as_engine` except `lanes/` for HTTP timing).
3. **`mind.perception.grant` is the only knowledge writer** (percept_log `granted_by` CHECK), and
   the packet builder cannot import the truth accessor (SKULL-02).

Import boundaries (BOUND-*, checked by `tests/contract/p00_substrate/test_boundaries.py`):

| Module | May NOT import |
|---|---|
| anything under `as_engine` | `talemate` (BOUND-01) |
| `mind.packet`, `mind.memory`, `mind.retrieval`, `narration.*`, `service.view` | `kernel.truth` (BOUND-02 / SKULL-02) |
| `physical.*`, `sense.*`, `action.*`, `mind.*` | `service.*`, `turn.*` (lower bands never import higher) (BOUND-03) |
| `narration.*` | any module that writes world tables other than `narration.*` (NARR-00) |
| every simulation module (physical, sense, mind except actor.controller, action, society, world) | the identifiers `controller`, `is_pc`, `pc_id`, `player` (SYM-01, AST scan) |

## 6. The Talemate plugin (backend adapter)

`src/talemate/server/as_game_plugin.py` (P8) — the full file is small and specified here:

```python
import asyncio, structlog
from talemate.server.websocket_plugin import Plugin
from as_engine.service.game_service import get_service
from as_engine.config_loader import load_engine_config   # reads as_config.yaml (or defaults)
from as_engine.lanes.transport import HttpTransport

log = structlog.get_logger("talemate.server.as_game")

class AsGamePlugin(Plugin):
    router = "as_game"

    def connect(self):
        self.service = get_service(load_engine_config(), HttpTransport())
        self._push = self._make_push()
        self.service.subscribe(self._push)

    def disconnect(self):
        self.service.unsubscribe(self._push)

    def _make_push(self):
        async def push(msg: dict):
            self.websocket_handler.queue_put(msg)
        return push

    async def handle(self, data: dict):          # overrides Plugin.handle (no handle_<action> methods)
        for reply in await self.service.handle(data):
            self.websocket_handler.queue_put(reply)
```

Everything else about the protocol lives in `as_engine` (`service/game_service.py`,
`contracts/protocol.py`) and is tested there without Talemate. One Talemate-side test
(`tests/test_as_game_plugin.py`, run in the full Talemate environment) checks the route is
registered and a `hello` round-trips.

## 7. Data locations at runtime

| What | Where |
|---|---|
| Install config | `as_config.yaml` (lanes, paths, rules overrides) — edited by the Play UI "Models" screen |
| Content | `as_content/packs/<pack>/` (source), `as_content/_compiled/canon.sqlite` (built) |
| A run | `as_runs/<run_id>/world.sqlite` + `manifest.json` + `saves/` + `autosave/` + `logs/` + `reports/` |
| Logs | `as_runs/<run_id>/logs/calls.jsonl` (every model call with timing), `sim_trace.jsonl` (stage outputs), `errors.jsonl` |

## 8. What is deliberately NOT here

- No vector database in v1 (retrieval is deterministic SQL + FTS5; see 05 §Retrieval).
- No web access for the simulation.
- No cloud models. Everything runs on your two machines.
- No telemetry, no update checks, no downloads while playing, nothing served to the network: the
  seal (§9).
- No pre-written plot: the Vector Register may *show* what is in motion; nothing reads it to decide
  outcomes (NARR-04).

## 9. Privacy: the seal (D-104; `as_engine/lanes/seal.py`)

The owner: "I need this to be a completely sealed up, local build that doesn't put my privacy at
risk"; "No limitations. No privacy leaks. Hard rule." The game talks to the models on the owner's
own machines (§2: the desktop and the laptop) and to nothing else, whatever any library inside the
process would like to do. Everything the seal refuses fails as if the network were down.

| Rule | What |
|---|---|
| SEAL-01 | A model address is this machine or its home network (loopback, a private or link-local address, a single-label or `.local` / `.lan` / `.home.arpa` / `.internal` name); `LaneConfig` refuses anything else, so such a config never loads and the Connect screen cannot set one |
| SEAL-02 | Installed, the seal refuses every name lookup and every connection (plain sockets and both asyncio loops) to anything but loopback and the model machines, and keeps the last 100 refusals |
| SEAL-03 | Installed, the seal switches every library it knows of offline (Hugging Face, transformers, datasets, ChromaDB telemetry, DO_NOT_TRACK) and removes proxy settings — a proxy would carry the game's words off the machine; lifting it puts them back |
| SEAL-04 | The Talemate server seals itself before anything else starts (this machine alone when the config cannot be read), every `as-engine` command runs sealed, a changed model address re-seals, and the lane client reads no proxy from the environment |
| SEAL-05 | Nothing reaches out on its own: the launchers bind 127.0.0.1 and run `uv` offline without syncing, Docker publishes on 127.0.0.1 only, and the frontend loads no font, script or style from outside |

What the seal found in Talemate and now stops: the start scripts served the game on every network
interface (0.0.0.0); the page asked Google Fonts for Roboto on every load; a configured model's name
was sent to Hugging Face to guess its prompt template; the NLTK tokenizer was downloaded from GitHub
at every start; cloud model, voice and image clients (OpenRouter, DeepSeek, OpenAI, Anthropic,
Google, Mistral, Cohere, Groq, ElevenLabs) and Hugging Face voice downloads are unreachable. Local
image generation through ComfyUI (Talemate's `comfyui` backend, `http://127.0.0.1:8188`) stays
possible on this machine; ComfyUI is its own program, and its Manager add-on checks GitHub unless
it is told not to.

## 10. Freedom of the narrative (D-104)

The owner: "I expect the finished product to have total freedom of narrative, amongst every Actor
and myself included. No limitations." The models are uncensored; the prompts do not hold them back.

| Rule | What |
|---|---|
| FREE-01 | Nothing that was perceived is skipped, summarised away or faded out because it is ugly: the narrator tells violence, cruelty, degradation, drugs and sex between adults as plainly as anything else (`prompts/narration.system.j2`) |
| FREE-02 | A person may lie, steal, threaten, hurt, kill, betray or abandon someone when that follows from who they are (`prompts/_actor_core.j2`); no prompt steers anyone toward decency, and no prompt carries a softening or refusal phrase |
| FREE-03 | The only content levers: the owner's Intensity setting (Full by default; Softer keeps violence at the edge of the frame) and CNT-11 (09 §CNT: nothing sexual ever involves a minor), which nothing disables. The narrator's framing when a child is eaten (I1: the sound and the faces, not the body) stays |

