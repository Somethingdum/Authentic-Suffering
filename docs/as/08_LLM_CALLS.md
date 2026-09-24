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
4. In the game's **Models** screen pick the Lane A and Lane B model ids from the dropdowns and press
   **Test** on each. The test runs PROBE calls (below) and records whether structured output and
   thinking control work for that model.

(If LM Link is not used, give Lane B the laptop's own URL, e.g. `http://192.168.1.50:1234/v1`,
with LM Studio's "Serve on local network" enabled.)

## 3. Adapter boundary

`LMRequest` (`contracts/lanes.py`) → `LaneClient.call` → `Transport.send` → `LMResponse`.
Nothing above this boundary knows which model answered; swapping a model is a config change
(IFACE-01: the P7 slice is byte-identical under a stub transport returning the same outputs).

HTTP (`lanes/transport.py`): `POST {base_url}/chat/completions` with `model`, `messages`,
`temperature`, `top_p`, `max_tokens`, `stream: false`, and — for structured calls —
`response_format: {"type": "json_schema", "json_schema": {"name", "strict": true, "schema"}}`.
Response text from `choices[0].message.content`; reasoning from `reasoning_content` or `reasoning`
when LM Studio separates it; `<think>…</think>` blocks are stripped from content either way.

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
| writeback | B | no | WritebackOutput | per holder / identical group, after commit | memory becomes objective; two people remember the same thing |
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
| probe | A/B | per probe | JSON/text | Connect screen, bench | — |

**Ablation duty** (plan §17.3 LAW): `tools/as/eval.py --ablate <call_class>` runs the canonical
eval scenarios with that call disabled (fallback path) and reports what degrades. A call whose
ablation shows no measurable degradation is removed.

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
