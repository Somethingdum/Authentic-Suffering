# 08 — Model Calls

## 1. Why a call exists (plan §4 carried as LAW)

A stage gets its own model call **iff** at least one holds:
- **R1 Containment** — it must not see something (every Actor call, the narrator, rumour distortion).
- **R2 Adversarial independence** — it judges an artifact it did not produce (audits, lint judge).
- **R3 Regime** — it needs a different temperature, grammar, context length or model.

It must NOT be a call when it is computable (N1), would be fully re-validated anyway (N2), is on the
critical path with no measured quality gain (N3), or containment is already achieved by code (N4).
Perception, audibility, line of sight, conflict resolution, checks, timing, inventory,
conservation, cascade application, scoring, selection, commit, save and replay are code.
**Prefer code where a wrong answer would be silent; prefer a model where it would be obvious.**

## 2. LM Studio setup (you do this once; the Connect screen tests it)

1. Desktop (`msi`, 12 GB card): load **Boulesis v2.1 26B-A4B** (`boulesis-v2.1-26b-a4b-i1`, mradermacher's
   GGUF Q4_K_M ≈ 16 GB, a Gemma 4 26B-A4B fine-tune) — the Writer, lane A — with the context LM Studio offers
   for it (143,360), flash attention on. Set its sampling in LM Studio to Google's recommendation for Gemma 4
   (temperature 1.0, top_p 0.95, **top_k 64**: the game sends temperature and top_p per call; top_k is LM
   Studio's). Start the server (Developer tab or `lms server start`) on port 1234.
2. Laptop: load **NVIDIA Nemotron 3.5 Lightning 30B-A3B** with multi-token prediction
   (`nvidia-nemotron-3.5-lightning-30b-a3b-mtp`) — the Clerk, lane B, for now — partial GPU offload on the
   8 GB card, with the context LM Studio offers for it (59,136). More parallel slots there (`max_concurrency`)
   mean more people per turn get a model call. A better laptop model takes the same role.
3. Link the machines with **LM Link** (`lms link enable` on both). Both models now appear in the
   desktop's `http://localhost:1234/v1/models`.
4. In the game's Connect screen (and Settings → Models) pick the **Main model** and the **Second
   model** from the one list LM Studio shows — no typing, no addresses — and press **Test** on each.
   The test runs PROBE calls (below) and records whether structured output and thinking control
   work for that model.
5. Once per model change, run the limits bench overnight: `python tools/as/bench.py --accept` (§7). It finds
   each lane's thinking switch (a Gemma 4 may need `system_think_token`; without a working switch the Writer
   never thinks), the context, reading and writing speeds, parallel slots, how far into a long prompt each
   model still finds facts, how long each of the game's calls takes, and writes the settings that follow into
   `as_config.yaml`. (`python tools/as/probe.py --write` alone does the thinking switch in minutes.)

**The Writer and the Clerk (D-111, D-113).** The two models are not equals. **Lane A, the Writer**
(Boulesis v2.1 26B-A4B, a Gemma 4) is many times smarter and by far the better writer: it keeps a long context
consistent, holds extra directions, and tells in-story from meta. It is also slow on a consumer card — about
5 tokens a second — and the owner takes that trade for the quality. **Lane B, the Clerk** (Nemotron 3.5
Lightning for now) is a capable model, not as smart, and faster: about 19 tokens a second written and some
200 read (a 25K-token prompt in about two minutes), and it thinks a lot. The rule for which lane a call
belongs on:

* **Writer** — everything narrative: every word the player reads as story (narration, the Voice, Willis, the
  recap, the Journal's scene summaries, and the player's own line when they opt in to say-my-way), the
  thinking decisions of the people who matter most (HOT actor cognition — and a HOT reaction: someone the
  player has just spoken to answers on the Writer), and the long-context creative work
  (worldgen history / people / opening, dossier intake, quick-make).
* **Clerk** — rapid, clearly scoped background work: a call whose answer is *closed* (a schema or a short
  verdict), *checked by code*, *stateless*, fits in about 8K tokens of context, and whose failure is *cheap*
  (a fallback exists): intake, the WARM minds, the reactions with little at stake (a sound, a glance — the
  room's small talk), repair, writeback, the audits and the lint judge,
  rumours, the guide, reflection, the cheat interpreter and persona, the doom guard.

Lanes are roles, not a pool: a call goes to the lane its regime names and is never moved to balance load
(the planner, `lanes/scheduler.py`); only a lane that is **down** sends a Clerk call to the Writer
(DEGRADE-01, thinking off). Narration is never written by the Clerk: with lane A down the moment is told
plainly by code (NARR-FALLBACK). The HOT decisions follow `hot_cognition.lane` (A by default, thinking on).
What that costs is measured, not guessed: the bench times a HOT decision on both lanes and shows a turn either
way (§7); `hot_cognition.lane: B` moves them to the Clerk.
The scheduler plans by `SchedulerRules.estimated_call_s`, placeholders until `tools/as/bench.py` measures your
machines. (Without LM Link, open Advanced on the Second model's
card and give that machine's own address, e.g. `http://192.168.1.50:1234/v1`, with LM Studio's
"Serve on local network" enabled.)

## 3. Adapter boundary

`LMRequest` (`contracts/lanes.py`) → `LaneClient.call` → `Transport.send` → `LMResponse`.
Nothing above this boundary knows which model answered; swapping a model is a config change
(IFACE-01: the P7 slice is byte-identical under a stub transport returning the same outputs).

HTTP (`lanes/transport.py`): `POST {base_url}/chat/completions` with `model`, `messages`,
`temperature`, `top_p`, `max_tokens`, `stream: true` (+ `stream_options: {include_usage: true}`), and — for
structured calls — `response_format: {"type": "json_schema", "json_schema": {"name", "strict": true, "schema"}}`.
The reply is read as server-sent events: text from `delta.content`; reasoning from `delta.reasoning_content`
or `delta.reasoning` when LM Studio separates it; `<think>…</think>` blocks are stripped from content either
way. A server that ignores `stream` and sends one JSON body (`choices[0].message`) is read the old way.

### 3.0 No deadlines: stalls, not timeouts (LANE-10, LANE-11; D-110)
The owner's rule: *a model that thinks for four minutes is working, not hung; a timeout can cut off good work
and throw it away.* So **nothing ends a call for taking long.** A call ends when it finishes, when the server
fails (`lane_error`), when the player presses Stop (the connection closes, which stops the model), or when it
**stalls**: no progress for `lane.stall_window_s` (default **300 s**). Progress is a streamed token, a streamed
reasoning token, or the server's prompt-processing counter moving forward; SSE comments, empty deltas and a
counter that stays put are not. A stalled call comes back as `parse_status` `timeout` with the error "no
progress for N s (phase); the model may have hung" (`LaneStalled`, a `LaneTimeout`), and the lane is **not**
marked down. `max_tokens` is still the bound on how much a call may say, so a model stuck in a loop ends there.

**The silent wait.** Before the first token the server may say nothing while it reads the prompt, and the first
prompt of a long context can take ten minutes. `lane.prefill_progress` says whether the server reports it
(llama.cpp's `return_progress`, which the transport asks for only when the lane is `supported`; the probe
finds out and writes it). Supported: the stall window applies from the first second, to the counter. Not
supported: the engine cannot see inside the server, so the silent wait is limited only by
`lane.silent_prefill_window_s` (default 0 = no limit; the Stop button is the way out). Once anything arrives the
window applies as normal.

`request.deadline_s` / `regimes.*.deadline_s` / `hot_cognition.deadline_s` are only the call's **expected**
seconds: past it the call's progress snapshot says `slow: true` (for the UI) and nothing else happens.

**Progress.** `client.live` holds a snapshot per call in flight (`lanes/progress.py`: `phase` waiting / prefill /
thinking / writing, `elapsed_s`, `quiet_s`, `slow`, the prompt counters, characters of reasoning and text so far)
and `client.on_progress(request, snapshot)` is called about once a second, and with None when the call ends.
Display only. The transport's sink routes each report to the client that made the call (several clients share
one transport). The Play UI shows it under the loading bar — what the models are doing, how long, how long
quiet — never who or how many (`service/progress.py` PROG-08, D-114).

### 3.1 Thinking control (per lane, `LaneConfig.thinking_mode`)
Nemotron 3.5 Lightning is a hybrid reasoning model (thinking on unless told otherwise). Gemma 4 (the Writer's
family) is the opposite: it thinks only when the token `<|think|>` opens the system prompt, and its reasoning comes back in a
thought channel, `<|channel>thought … <channel|>` (read like a `<think>` block when a server passes it
through: `lanes/parse.strip_think`). How LM Studio exposes the switch depends on the build, so the lane has a
mode, chosen by the probe:
`native` (send as-is) · `system_no_think` (append `/no_think` to the system message when thinking
is off) · `chat_template_kwargs` (`{"enable_thinking": thinking}`) · `prefill_empty_think` (append an
assistant message `<think></think>` when thinking is off) · `system_think_token` (put `<|think|>` at the start of
the system message when thinking is ON — Gemma 4) · `none`.
`tools/as/probe.py` tries every mode both ways (D-111) and keeps the fastest whose reply has no reasoning with
thinking off AND has reasoning with thinking on; when no mode does both it keeps the fastest that at least turns
thinking off and says so (`thinking_on_works: false`). The result is written to `as_config.yaml`.

### 3.2 Structured output with thinking
Some servers apply the JSON grammar to the whole output, which suppresses reasoning. The probe
records `structured_with_thinking: supported|unsupported`. When unsupported, a thinking call is
sent **without** `response_format`; the JSON is extracted from the visible text (`lanes/parse.py`);
a failure triggers ONE `INTENT_REPAIR` on lane B **with** the schema (LANE-06).

## 4. The call table (`contracts/settings.py::default_regimes`)

| Call class | Lane | Think | Output | When | If ablated (why it exists) |
|---|---|---|---|---|---|
| intake | B | no | IntakeOutput (dynamic enum) | player Do text | player prose would leak unperceived facts into intent; free text can't be trusted to map to legal options |
| actor_cognition (HOT) | A (`hot_cognition.lane`) | yes | ActorReplyV2 (dynamic enums; a decision or one consultation first) | salient/mandatory Actors | Skull Law becomes an instruction instead of a fact; F2 returns |
| actor_cognition (WARM) | B | no | ActorReplyV2 | other Actors in budget with something new, talk last turn, or due to take stock (D-190) — not for standing conditions (D-228), for being in view all along (D-229) or for the room's small talk (D-232); a room due to take stock does it a third at a time (D-231) | same, for more people per turn at no wall-clock cost |
| actor_reaction | B (HOT: `hot_cognition.lane`, A, thinking on) | no (HOT: yes) | ActorReplyV2 (a decision; no consultation) | reaction waves, planned like any wave: HOT for the mandatory and salience ≥ `hot_min_salience` (someone spoken to), else WARM | Actors could not respond within the same instant |
| intent_repair | B | no | ActorReplyV2 (a decision only) | one per failed structured call | a malformed answer would cost the Actor its turn |
| writeback | B | no | WritebackOutput | per holder (each a memory job, retried when it fails), after commit — only when something new reached them (D-189): not a voice through the wall nobody made out (D-227) nor the room's small talk not said to them (D-232) | memory becomes objective; two people remember the same thing; a failed call forgets |
| portrayal_audit | B | yes | PortrayalVerdict | targeted pre-check + retrospective | "would they do that?" answered by the one who did it |
| narration | A | yes | prose | every turn | the renderer would see hidden state |
| render_lint | B | yes | RenderLintJudgement | every narration draft | leaks and invented dialogue would ship |
| rumour_distort | B | no | RumourDistortion | between turns, a fresh story's holders (at most four): what they were told, in their voice, bent by how they feel about the one it is about and what they grew up hearing (D-235); never for a holder with nobody to tell (D-250) | second-hand information would transmit perfectly, and everyone would tell it the same way |
| cascade_advisory | B | no | CascadeSuggestion | when lanes idle | the cascade table would never learn (output is design debt, never committed) |
| guide | B | no | text | Ask mode | — (player help; no turn) |
| reflection | B | no | ReflectionOutput | idle time between turns | Actors would not grow new goals/grudges off-screen |
| scene_summary / recap | A | yes | text | scene end / load | the Journal and "previously" would be empty |
| say_my_way | A | yes | SayMyWayOutput | Say mode "my way" — only when the player opts in (`pc_voice: my_way`; the default `exact` sends their words as typed, D-113) | — (optional mode) |
| worldgen_history / actor / opening | A | history & opening yes | JSON (stage schemas) | worldgen only | — (off the turn path) |
| dossier_intake / pc_quickmake | A | no | JSON | content tools | — |
| cheat_persona | B | no | text | cheat commands | falls back to canned persona lines |
| cheat_interpret | B | yes | CheatPlan | a plain-words line in the Cheat field (D-103) | the console would understand only /commands |
| willis_roast | A | yes | WillisRoast | the PC's Doom, the frozen moment (D-105, D-106): at most 3 lines, 6 in his debt, cut off mid-sentence | falls back to service.death.fallback_roast: Willis still comes (in his debt / met before / a stranger) |
| the_voice | A | yes | VoiceMessage | the PC's Doom ('before': the chain, what was near, the upper hand, how long — never how) and after the death ('after': how) (D-106, VOICE-06) | falls back to service.voice.fallback_voice: the architect, the chain walked, the time left |
| doom_guard | B | no | DoomGuardOutput | a doomed PC's Act / Say words: do they tell anything about the end that ordinary people do not know? (DOOM-07) | falls back to turn.intake.doom_words (the phrase check) |
| ambient_line | B | no | AmbientLine | stage 6, the people past the model budget (COLD) in the PC's place that something reached: one short line each, in their own voice, at most `max_ambient` per wave by depth, most salient first (D-128, AMB-01..03); in a calm turn when nobody has spoken, one idle line from one of them, who goes round (D-150, AMB-04) | a crowd stands mute while two or three people talk; a failed line is silence (never a held decision, never lane A) |
| person_voice | B | no | PersonVoice | the quiet hours: a generated person the PC has exchanged at least three lines with, once — their voice written from what they actually said (D-149, BG-02..05) | the people the player gets to know play as code's sketch forever; a failed or empty answer leaves the card |
| probe | A/B | per probe | JSON/text | Connect screen, bench | — |

**Ablation duty** (plan §17.3 LAW): `tools/as/eval.py --ablate <call_class>` runs the canonical
eval scenarios plain and with that call disabled — the lane client's `ablated` set (LANE-09): the
call comes back 'cancelled' without reaching the model and every caller takes its fallback path —
and reports what changed. A call whose ablation shows no measurable degradation is removed.
`--fake` runs it on the fake model (a smoke run; P11 D-98).

## 5. Budget and latency

Wall-clock of a turn = the critical path through the call DAG with two concurrent slots, not the
number of calls. A WARM call (the Clerk) beside a HOT call (the Writer) is free. These budgets size the
cognition wave only; they never cut a call off (LANE-10). Planning figures (`[SAND]`, replaced by
`bench`): intake ≈ 2.3 s, HOT cognition ≈ 21 s (a HOT reaction — someone answering the player — the same), WARM ≈ 3.6 s, reaction ≈ 2.5 s, writeback ≈ 3.7 s,
audit ≈ 2.6 s, narration ≈ 18.6 s, lint judge ≈ 2.1 s → a medium scene (5 Actors: 2 HOT, 3 WARM,
one reaction wave) ≈ 48–50 s. **Turn depth** setting: quick (40 s budget, 1 HOT), balanced (75 s,
2 HOT), deep (150 s, 3 HOT). Mandatory Actors always get a call, even past budget.

## 6. Prompts
`as_engine/prompts/*.j2`, rendered by `prompts/render.py` (implemented). Two laws:
- **PROMPT-01 KV-cache order**: stable → volatile. The system template never contains volatile
  values; per-actor stable content comes first in the user message; percepts and options last.
- **PROMPT-02 No pseudo-code in what the model reads**: plain organised English. Bracket-colon
  labels, arrows, ALL_CAPS field names and symbol operators bleed into model output (a lesson
  learned on this project). JSON appears only as the required answer shape.
- **The actor prompts are a person's own** (Actor Spec §6, AC01): `_actor_core.j2` is the spec's
  text verbatim, `_actor_answer.j2` the answer's shape; a reaction adds only its last paragraph. No
  story, narrator, player, author or audience appears in them, and the user message opens with
  *Who you are* and the identity card (05 §2.1; p04 `test_identity.py`).
- **A person's own moments** (D-116, 05 §2.2): right after the card, the voice examples that fit
  `PacketRules.voice_example_tokens` (600 — about four seconds of reading on the Writer at the speeds
  assumed until the bench measures them); they are stable per person, so they sit in the cached part of
  the prompt, and they are the first thing the packet budget drops. Say-my-way and Willis's roast show
  examples the same way.

## 7. Live tools (run on your machines; `AS_LIVE=1`)
- `tools/as/probe.py` — reachability, model ids, JSON-schema compliance, thinking control (each mode tried both
  off and on); writes results into `as_config.yaml` with `--write`.
- `tools/as/bench.py` — **the limits bench** (D-112). Unattended: one command, every stage, both lanes,
  `--resume` after a Stop or a crash. It grades nothing; it finds where each model's limits are:
  the context it was loaded with (LM Studio's native API, or found by halving the gap between a prompt read and
  one refused or silently cut), reading speed from 1K tokens to that limit, recall (five facts at five depths of
  every long prompt — the same prompts, so long contexts are read once), what the prompt cache saves, writing
  speed with thinking off and on and how much of it is thinking, whether parallel requests add throughput, and
  every call class the game makes at its own regime (time, prompt size, thinking, whether `max_tokens` cut it
  short, whether it parsed) — with the HOT decision timed on both lanes, the thinking calls on every move's path
  (the HOT decision, the narration and its judge) timed without thinking too, and each narration draft put through
  the game's own code lint (how many would pass, which rules fail the rest: each failure costs a redraft). It writes `reports/bench.json` and a
  readable `reports/bench.md` (each lane's limits, the call table, a medium scene's turn time per depth with
  the HOT minds on either lane and with those calls not thinking — the as_config.yaml lines to do that are
  printed, never applied — and what `--accept` would change). `--accept` writes the thinking switch,
  JSON-with-thinking, prompt progress, `max_concurrency`, the stall window (only raised), the `max_tokens` of
  any call it saw cut short (raised), each regime's expected seconds, `estimated_call_s`, and turn budgets that
  still admit the minds each depth was designed for (`--keep-budgets` to leave them). It never moves a call to
  another lane and never turns thinking off (the owner's call). On the owner's pair (5 and 19 tokens a second) a full run takes about three hours — run it
  overnight; `--quick` about one. `--fake` runs it on two simulated lanes with known limits
  (`tools/as/benchsim.py`); the contract test checks that it finds them (p01 `test_bench_limits.py`).
- `tools/as/eval.py` — plays the canonical scenarios with real models and reports: refusal rate on
  WILL scenarios, echo rejections, lint failures per 10 turns, leak findings, average prose
  metrics, intent repair rate, turn wall-clock. This is how you find quality problems the fake
  model cannot show.
