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

1. Desktop (`msi`): load **Nemotron Cascade 2 30B-A3B** (GGUF, Q4_K_M or better), context 32768,
   flash attention on. Start the server (Developer tab or `lms server start`) on port 1234.
2. Laptop: load **NVIDIA Nemotron 3.5 Lightning 30B-A3B** (Unsloth GGUF UD-Q4_K_XL ≈ 20 GB RAM;
   partial GPU offload on the 8 GB card), context 16384.
3. Link the machines with **LM Link** (`lms link enable` on both). Both models now appear in the
   desktop's `http://localhost:1234/v1/models`.
4. In the game's Connect screen (and Settings → Models) pick the **Main model** and the **Second
   model** from the one list LM Studio shows — no typing, no addresses — and press **Test** on each.
   The test runs PROBE calls (below) and records whether structured output and thinking control
   work for that model.

The two models are equals (the owner's pair runs at about the same speed and is about as capable;
Cascade may be a little faster). Lane A is simply the one marked main: it takes the thinking
decisions of the people who matter most and the narration; every other call fills whichever lane
is free. The scheduler plans by `SchedulerRules.estimated_call_s`, placeholders until
`tools/as/bench.py` measures your machines. (Without LM Link, open Advanced on the Second model's
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
and `client.on_progress(request, snapshot)` is called about once a second. Display only.

### 3.1 Thinking control (per lane, `LaneConfig.thinking_mode`)
Nemotron Cascade 2 has thinking and instruct modes (instruct is activated by an empty
`<think></think>` at the start of the reply); Nemotron 3.5 Lightning is a hybrid reasoning model.
How LM Studio exposes the switch depends on the build, so the lane has a mode, chosen by the probe:
`native` (send as-is) · `system_no_think` (append `/no_think` to the system message when thinking
is off) · `chat_template_kwargs` (`{"enable_thinking": false}`) · `prefill_empty_think` (append an
assistant message `<think></think>`) · `none`.
`tools/as/probe.py` tries them in order for `thinking=False` and keeps the first whose reply has no
reasoning and arrives fastest; the result is written to `as_config.yaml`.

### 3.2 Structured output with thinking
Some servers apply the JSON grammar to the whole output, which suppresses reasoning. The probe
records `structured_with_thinking: supported|unsupported`. When unsupported, a thinking call is
sent **without** `response_format`; the JSON is extracted from the visible text (`lanes/parse.py`);
a failure triggers ONE `INTENT_REPAIR` on lane B **with** the schema (LANE-06).

## 4. The call table (`contracts/settings.py::default_regimes`)

| Call class | Lane | Think | Output | When | If ablated (why it exists) |
|---|---|---|---|---|---|
| intake | B | no | IntakeOutput (dynamic enum) | player Do text | player prose would leak unperceived facts into intent; free text can't be trusted to map to legal options |
| actor_cognition (HOT) | A | yes | ActorReplyV2 (dynamic enums; a decision or one consultation first) | salient/mandatory Actors | Skull Law becomes an instruction instead of a fact; F2 returns |
| actor_cognition (WARM) | B | no | ActorReplyV2 | other Actors in budget | same, for more people per turn at no wall-clock cost |
| actor_reaction | B | no | ActorReplyV2 (a decision; no consultation) | reaction waves | Actors could not respond within the same instant |
| intent_repair | B | no | ActorReplyV2 (a decision only) | one per failed structured call | a malformed answer would cost the Actor its turn |
| writeback | B | no | WritebackOutput | per holder (each a memory job, retried when it fails), after commit | memory becomes objective; two people remember the same thing; a failed call forgets |
| portrayal_audit | B | no | PortrayalVerdict | targeted pre-check + retrospective | "would they do that?" answered by the one who did it |
| narration | A | no | prose | every turn | the renderer would see hidden state |
| render_lint | B | no | RenderLintJudgement | every narration draft | leaks and invented dialogue would ship |
| rumour_distort | B | no | RumourDistortion | rumour hops | second-hand information would transmit perfectly |
| cascade_advisory | B | no | CascadeSuggestion | when lanes idle | the cascade table would never learn (output is design debt, never committed) |
| guide | B | no | text | Ask mode | — (player help; no turn) |
| reflection | B | no | ReflectionOutput | idle time between turns | Actors would not grow new goals/grudges off-screen |
| scene_summary / recap | B | no | text | scene end / load | the Journal and "previously" would be empty |
| say_my_way | B | no | SayMyWayOutput | Say mode "my way" | — (optional mode) |
| worldgen_history / actor / opening | A | history & opening yes | JSON (stage schemas) | worldgen only | — (off the turn path) |
| dossier_intake / pc_quickmake | A | no | JSON | content tools | — |
| cheat_persona | B | no | text | cheat commands | falls back to canned persona lines |
| cheat_interpret | A | no | CheatPlan | a plain-words line in the Cheat field (D-103) | the console would understand only /commands |
| willis_roast | A | no | WillisRoast | the PC's Doom, the frozen moment (D-105, D-106): at most 3 lines, 6 in his debt, cut off mid-sentence | falls back to service.death.fallback_roast: Willis still comes (in his debt / met before / a stranger) |
| the_voice | A | no | VoiceMessage | the PC's Doom ('before': the chain, what was near, the upper hand, how long — never how) and after the death ('after': how) (D-106, VOICE-06) | falls back to service.voice.fallback_voice: the architect, the chain walked, the time left |
| doom_guard | B | no | DoomGuardOutput | a doomed PC's Act / Say words: do they tell anything about the end that ordinary people do not know? (DOOM-07) | falls back to turn.intake.doom_words (the phrase check) |
| probe | A/B | per probe | JSON/text | Connect screen, bench | — |

**Ablation duty** (plan §17.3 LAW): `tools/as/eval.py --ablate <call_class>` runs the canonical
eval scenarios plain and with that call disabled — the lane client's `ablated` set (LANE-09): the
call comes back 'cancelled' without reaching the model and every caller takes its fallback path —
and reports what changed. A call whose ablation shows no measurable degradation is removed.
`--fake` runs it on the fake model (a smoke run; P11 D-98).

## 5. Budget and latency

Wall-clock of a turn = the critical path through the call DAG with two concurrent slots, not the
number of calls. A WARM call beside a HOT call is free. Planning figures (`[SAND]`, replaced by
`bench`): intake ≈ 2.3 s, HOT cognition ≈ 21 s, WARM ≈ 3.6 s, reaction ≈ 2.5 s, writeback ≈ 3.7 s,
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

## 7. Live tools (run on your machines; `AS_LIVE=1`)
- `tools/as/probe.py` — reachability, model ids, JSON-schema compliance, thinking control; writes
  results into `as_config.yaml`.
- `tools/as/bench.py --n 5` — per-call-class latency on each lane with realistic packet sizes;
  writes `reports/bench.json`; replaces `SchedulerRules.estimated_call_s` when you accept it.
- `tools/as/eval.py` — plays the canonical scenarios with real models and reports: refusal rate on
  WILL scenarios, echo rejections, lint failures per 10 turns, leak findings, average prose
  metrics, intent repair rate, turn wall-clock. This is how you find quality problems the fake
  model cannot show.
