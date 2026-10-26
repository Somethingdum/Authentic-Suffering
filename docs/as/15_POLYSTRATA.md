# 15 — PolyStrata as a model host (D-297)

The owner, 2026-10-26: *"I want to be able to use Polystrata models instead."* PolyStrata is a public local model
server (github.com/VecSzn/PolyStrata, read at `52c31cf`, 2026-10-26). This page says what it is, what the game
changes to use it (block 1.3 of `14_THREE_DAYS.md`), and how to set the two PCs up.

## 1. What PolyStrata is, and what the game must change

PolyStrata is a local model server with its own engine. It runs a fixed list of model families (Qwen3.6, Ornith
1.5, Gemma 4 26B-A4B, Tiel Coder, MiniCPM-V, LFM2.5, Flint, GLM, DeepSeek; Qwen3.8 on Strata's engine) much
faster than llama.cpp on the same card: on an 8 GB laptop it reports Gemma 4 26B-A4B writing **92–93 tokens a
second** and reading 2,240; Ornith 1.5 76–82 and 1,620. The owner's Writer today writes about 5. **Boulesis v2.1
is a Gemma 4 26B-A4B fine-tune**, and PolyStrata's FAQ says a fine-tune that keeps a supported architecture
should run (its setup takes it with `--family gemma4 … --gguf-dir <folder>`; not tried by anyone here). If it
does, the Writer is some twenty times faster, and the turn-time problem of 14 §7 mostly goes away.

| | PolyStrata (its source) | The game today | Change |
|---|---|---|---|
| Address | `http://127.0.0.1:8080/v1`; another PC reaches it only when its run config says `"host": "0.0.0.0"` and has an `"api_key"` (without a key it refuses unknown Host names: DNS-rebinding protection) | a lane's `base_url`, `api_key` (Bearer) | none in code; the setup steps (§4) |
| One model at a time | holds one model; a call naming another installed model loads it first when `switch_on_request` is on; a call while unloaded loads it | assumes the named model is there | a PolyStrata lane reads `/health` (and `/props`) first and refuses to send when its model is not the one loaded (never-load: the game never loads a model) |
| Model list | `/v1/models`; `/api/models` lists what is installed; `/props` the loaded file; `/v1/status`; `/metrics` | `/v1/models` for the model picker and the swap guard | the picker shows the loaded model per PolyStrata; the swap guard reads `/health` |
| Streaming | OpenAI SSE with `delta.reasoning_content`, `usage` at the end | reads both | none |
| Prompt progress | llama.cpp's `prompt_progress` when asked with `return_progress` | `prefill_progress` (the probe finds it) | none |
| Thinking switch | `chat_template_kwargs: {"enable_thinking": false}`, `reasoning_effort`, and a per-request thinking cap `reasoning_budget_tokens` | `thinking_mode` (the probe picks one) | new optional `LaneConfig.thinking_budget`: sent as `reasoning_budget_tokens` on thinking calls, so a thinking call cannot spend its whole `max_tokens` thinking |
| **Structured output** | **no grammar decoder**: `response_format` json_schema is checked after the answer is written, and a failure comes back as an **error event in the stream** (`structured_output_failed`) | sends `response_format`; an error event raises `LaneUnavailable`, which **marks the lane down** | (a) the probe sets `structured_mode: prompt_only` on a PolyStrata lane (the game then reads the JSON from the text and repairs once, LANE-06); (b) the transport reads `structured_output_failed` as a grammar failure of that one call, never a dead lane |
| Sampling | takes `top_k`, `min_p`, `presence_penalty`, `repetition_penalty` per request (LM Studio's top_k was set in its own window) | sends temperature and top_p only | new optional `LaneConfig.sampling` (e.g. Gemma 4: `top_k: 64`; Ornith 1.5: `top_k: 20`), sent with every call on that lane |
| Parallel requests | one at a time unless its run config sets `"parallel": N` | `max_concurrency` | the probe reads it; the default stays 1 (one prompt per PC: a second prompt at once can crash an 8 GB laptop) |
| Output cap | refuses a `max_tokens` past the window unless the run config has `"fit_max_tokens": true` | sends the regime's `max_tokens` | setup step: turn `fit_max_tokens` on |
| Native API for the bench | `/props`, `/v1/status`, `/api/models`, `/metrics` (no `/api/v1/models`) | bench and fit read LM Studio's native API | bench / fit / tune read PolyStrata's when the server is PolyStrata (`/health` says `"service": "strata"`) |

**LM Link has no PolyStrata twin.** With LM Studio, LM Link put both PCs' models behind one address. With
PolyStrata each PC serves its own, so the game's two lanes have two addresses: the Writer at the desktop's own
`127.0.0.1:8080`, the Clerk at the laptop's address on the home network (`http://192.168.x.y:8080/v1`, which the
seal allows: SEAL-01). Or one PC does both: one model, both lanes, one prompt at a time.

## 2. Setting the two PCs up with PolyStrata (for checkpoint 1 of 14)

1. Install PolyStrata on each PC (`START-HERE.bat`).
2. Desktop, the Writer: give its setup the Boulesis GGUF (`--family gemma4 --model <the size whose name you gave
   the file> --gguf-dir <its folder>`). If PolyStrata refuses it, the Writer stays on LM Studio for now and only
   the Clerk moves.
3. Laptop, the Clerk: Ornith 1.5 (PolyStrata's own) or another model of yours.
4. In each run config (`strata-<model>.json`): `"fit_max_tokens": true`; no `switch_on_request`, no
   `idle_unload_s`. On the laptop also `"host": "0.0.0.0"` and an `"api_key"` of your choosing.
5. In the game (Settings → Models, or `as_config.yaml`): Main model `http://127.0.0.1:8080/v1`; Second model
   `http://<laptop address>:8080/v1` with the laptop's key. Then `python tools\as\tune.py` as usual: it sees
   PolyStrata and sets the lanes for it.
