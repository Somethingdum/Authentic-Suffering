"""Two simulated lanes with KNOWN limits, for ``tools/as/bench.py --fake`` and its tests (D-112).

A real bench finds limits nobody wrote down; this one has them written down, so a run on it shows whether
the bench finds what is there. Each lane is a ``SimModel``: how much context it holds and whether LM Studio
reports it, how fast it reads a prompt and writes, how many requests it serves at once, how far into a long
prompt it still finds a fact, whether it keeps the last prompt cached, how its thinking switch works, how
much it thinks, and whether it reports prompt-processing progress. Time is simulated: one simulated second
lasts ``scale`` real seconds, and ``clock()`` reads simulated seconds.

Answers: a request with a ``context`` (a real call class, from the prompt samples) gets the engine's fake
model's answer (testing/fake_lm.FakeTransport), or "Done." when the fake has none; the bench's own prompts
are recognised by their wording (a recall question, a story, "Reply with the single word: …").
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import time
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class SimModel:
    model: str
    ctx: int                         # tokens the loaded model holds
    reports_ctx: bool                # does the LM Studio native API report loaded_context_length?
    prefill_tps: float               # prompt tokens read per second
    decode_tps: float                # tokens written per second (per request)
    slots: int                       # requests served at once
    recall_tokens: int               # beyond this prompt length, facts in the middle are lost
    family: str                      # 'gemma' (thinks only when switched on) | 'nemotron' (thinks unless switched off)
    think_tokens: int                # reasoning tokens per answer when it thinks
    reports_prefill: bool            # streams prompt_progress when asked
    max_ctx: int = 262144            # the model's training maximum (LM Studio's max_context_length)


# The owner's pair as far as it is known (2026-10): Boulesis writes about 5 tokens a second; the Nemotron about
# 19, and reads about 200 (25K tokens in some two minutes) and thinks a lot. The rest is a guess on the slow
# side — consumer cards, partial offload. ``SMALL`` keeps the same speeds in small contexts, for quick tests.
DEFAULT_MODELS = {
    "A": SimModel(model="boulesis-v2.1-26b-a4b-i1", ctx=143360, reports_ctx=True, prefill_tps=150.0, decode_tps=5.0,
                  slots=1, recall_tokens=32000, family="gemma", think_tokens=800, reports_prefill=True),
    "B": SimModel(model="nvidia-nemotron-3.5-lightning-30b-a3b-mtp", ctx=59136, reports_ctx=False, prefill_tps=200.0,
                  decode_tps=19.0, slots=1, recall_tokens=16000, family="nemotron", think_tokens=1200,
                  reports_prefill=False),
}
SMALL = {
    "A": replace(DEFAULT_MODELS["A"], ctx=24576, recall_tokens=12000),
    "B": replace(DEFAULT_MODELS["B"], ctx=16384, recall_tokens=6000, slots=2),
}
TOKENS_PER_WORD = 1.3
NEEDLE = re.compile(r"the (\w+) door's code word is ([A-Z]+-\d+)")


def tokens(text: str) -> int:
    return math.ceil(len(text.split()) * TOKENS_PER_WORD)


class SimTransport:
    """A Transport (lanes/transport.py) over simulated models. ``sink`` gets CallProgress like HttpTransport's."""

    def __init__(self, models: dict[str, SimModel] | None = None, scale: float = 0.002):
        from as_engine.testing.fake_lm import FakeTransport
        self.models = dict(models or DEFAULT_MODELS)
        self.scale = scale
        self.sink = None
        self.fake = FakeTransport(latency_ms=0)
        self._slots = {k: asyncio.Semaphore(m.slots) for k, m in self.models.items()}
        self._cached: dict[str, str] = {}

    def clock(self) -> float:
        return time.perf_counter() / self.scale

    async def _wait(self, timer: list, seconds: float) -> None:
        """Advance this request's own timeline by ``seconds`` (simulated), sleeping against its start so the
        small sleeps do not add up to drift: timer = [real start, simulated seconds so far]."""
        timer[1] += seconds
        await asyncio.sleep(max(0.0, timer[0] + timer[1] * self.scale - time.perf_counter()))

    # -- the Transport protocol -------------------------------------------------------------------------

    async def list_models(self, lane_id, lane) -> list[str]:
        return [m.model for m in self.models.values()]

    async def health(self, lane_id, lane) -> bool:
        return True

    async def native_info(self, lane) -> dict:
        m = next((x for x in self.models.values() if x.model == lane.model), None)
        if m is None:
            return {}
        out = {"id": m.model, "max_context_length": m.max_ctx, "state": "loaded", "quantization": "Q4_K_M"}
        if m.reports_ctx:
            out["loaded_context_length"] = m.ctx
        return out

    async def aclose(self) -> None:
        return None

    def _thinks(self, m: SimModel, mode: str, thinking: bool) -> bool:
        if m.family == "gemma":
            return thinking and mode in ("system_think_token", "chat_template_kwargs")
        return thinking or mode not in ("system_no_think", "chat_template_kwargs", "prefill_empty_think")

    async def send(self, lane, request):
        from as_engine.contracts.lanes import LMResponse
        from as_engine.lanes.errors import LaneUnavailable
        from as_engine.lanes.progress import CallProgress
        key = request.lane.value
        m = self.models[key]
        prompt = "\n".join(msg.content for msg in request.messages)
        n_in = tokens(prompt)
        if n_in > m.ctx:
            raise LaneUnavailable(f"HTTP 400: the prompt ({n_in} tokens) is longer than the context ({m.ctx})")
        prog = CallProgress(request.call_class, request.lane, expected_s=request.deadline_s)
        report = (lambda: self.sink(request, prog)) if self.sink else (lambda: None)
        async with self._slots[key]:
            timer = [time.perf_counter(), 0.0]
            old = self._cached.get(key, "")
            same = len(_common_prefix(old, prompt))
            cached = int(n_in * same / max(len(prompt), 1)) if same > 200 else 0
            self._cached[key] = prompt
            done = cached
            ask_progress = lane.prefill_progress == "supported" and m.reports_prefill
            while done < n_in:
                step = min(2048, n_in - done)
                await self._wait(timer, step / m.prefill_tps)
                done += step
                if ask_progress:
                    prog.note_prefill(done, n_in, cached)
                    report()
            text = await self._answer(lane, request, m, n_in)
            r_tokens = m.think_tokens if self._thinks(m, lane.thinking_mode, request.thinking) else 0
            r_out = min(r_tokens, request.max_tokens)
            t_out = min(tokens(text), request.max_tokens - r_out)
            reasoning = []
            for i in range(0, r_out, 64):
                await self._wait(timer, min(64, r_out - i) / m.decode_tps)
                reasoning.append("hm " * 16)
                prog.note_reasoning(len("".join(reasoning)))
                report()
            words = text.split()
            keep = words[:max(0, int(t_out / TOKENS_PER_WORD))] if t_out < tokens(text) else words
            out = []
            for i in range(0, len(keep), 8):
                chunk = keep[i:i + 8]
                await self._wait(timer, len(chunk) * TOKENS_PER_WORD / m.decode_tps)
                out.extend(chunk)
                prog.note_text(len(" ".join(out)))
                report()
            report()
        return LMResponse(call_class=request.call_class, lane=request.lane, text=" ".join(out),
                          reasoning="".join(reasoning) or None, prompt_tokens=n_in, completion_tokens=r_out + t_out,
                          model=m.model)

    async def _answer(self, lane, request, m: SimModel, n_in: int) -> str:
        if request.context is not None:
            try:
                return (await self.fake.send(lane, request)).text
            except AssertionError:
                return "Done."
        user = request.messages[-1].content
        if "code word for each door" in user:
            needles = [(mt.start() / max(len(user), 1), mt.group(1), mt.group(2)) for mt in NEEDLE.finditer(user)]
            got = {c: (w if n_in <= m.recall_tokens or d < 0.1 or d > 0.9 else "unknown") for d, c, w in needles}
            return json.dumps(got)
        story = re.search(r"about (\d+) words", user)
        if story:
            return " ".join(["word"] * int(story.group(1)))
        if request.json_schema is not None:
            return json.dumps({"ok": True, "word": "ready"})
        said = re.search(r"single word: (\w+)", user)
        return said.group(1) if said else "ready"


def _common_prefix(a: str, b: str) -> str:
    """The shared start of two prompts, by halving (slice comparisons run in C: no simulated time is lost to it)."""
    lo, hi = 0, min(len(a), len(b))
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if a[:mid] == b[:mid]:
            lo = mid
        else:
            hi = mid - 1
    return a[:lo]
