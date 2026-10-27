"""The host's budget decides what a hosted turn spends (D-299). Rules HOST-06..HOST-09.

A hosted turn has a tier the player chose (1 fastest .. 5 deepest) and a time it must stay inside;
both belong to the host. The engine tells the host every step a turn could take — which are
required, which are optional and in what order they go first — and asks before each optional one.
Nothing in the engine measures time for this.

HOST-06 steps. A step is {id, label, required?, drop?, background?, est: {calls, answerTokens, think,
  promptTokens}} (think 'off' | 'brief' | 'full' | 'main'). Ids are content-free; labels are plain
  words with no name in them (a footer may show them to the player). Required steps are never
  skipped; optional ones carry a ``drop`` rank, unique within the turn, 1 dropped first, and the
  kept set is always an upper set of the ranks (the host never keeps a step while dropping one
  ranked above it). turn_steps(config, depth) are declared when the turn starts:
    intake (required) · write (required: the turn's prose) · judge (drop JUDGE) ·
    ambient (drop 2) · audit:portrayal (drop 1) · waves:2+ (drop 3).
  wave_steps(...) are declared at each wave's planning (stage 4), before anything is asked:
    mind:<w>:<actor>   a mandatory mind — required (someone spoken to, attacked, owed an answer
                       always decides);
    focus:<w>:<actor>  a person who could be decided as narrative work, in full voice — optional;
    mind:<w>:<actor>   a person in the background who could decide for themselves — optional.
  Ranks: focus FOCUS + (9 - min(w, 9)) x 1000 + k, minds MIND + (9 - min(w, 9)) x 1000 + k, where k
  counts the wave's candidates of that kind from the least salient (0) up: a later wave goes before
  an earlier one, the least salient before the more, the background minds before anyone's full
  voice, and the second reading of the prose last of all.
HOST-07 the governed plan (replaces lanes.scheduler.plan_cognition's time arithmetic when a turn is
  hosted; the order and the rules about who has anything to decide are the scheduler's own):
  order = mandatory candidates, then the rest, each by (salience desc, actor_id); plan.order = it.
  shape = TIERS[tier]; focus = the host's focus count for the tier, else shape's.
  0. A wave of 2 or later first asks 'waves:2+'; refused, only its mandatory minds decide.
  1. In focus (HOT, lane A): the first ``focus`` of the order, stopping at the first that is not
     mandatory when shape['mandatory_focus'] or when 'waves:2+' was refused, at the first not
     mandatory whose salience is below SchedulerRules.hot_min_salience (D-175), and at the first
     whose focus step the host refuses (and every one after it, HOST-06's upper set).
  2. The rest in order (a person refused full voice in 1 included): a mandatory mind is WARM on
     config.regimes[ACTOR_COGNITION].lane whatever the time. A mind that is not mandatory becomes
     COLD, with every one after it, when its salience is 0 (D-190), when the shape keeps background
     minds out (tiers 1 and 2), when the wave is 2 or later and the host refused 'waves:2+', or when
     the host refuses its mind step; else WARM. (Every such mind's step is declared before
     anything is asked, below its focus step when it has one.)
  COLD people go on with what they were doing (LOD-01: LOD changes who calls a model, never
  competence, knowledge or morality). est_wall_s is 0 and overrun False: time is the host's.
HOST-08 every answer is kept. ``decisions`` holds each step the governor was asked about this turn
  and its answer, ``plan_steps`` those the latest plan_cognition asked (a memoised answer included);
  the pipeline writes a wave's plan_steps into its stage-4 ledger entry ('steps'), so a replay
  plays the same plan (RecordedGovernor), and an answer asked twice in a turn (the strict retry)
  is the first answer again.
HOST-09 tiers: TIERS[t] = {depth, focus, mandatory_focus, minds} — 1: quick, 0, -, no · 2: quick, 1,
  mandatory only, no · 3: balanced, 2, -, yes · 4: deep, 3, -, yes · 5: deep, 4, -, yes. depth is
  RunSettings.turn_depth for the turn (the room's remarks, AMB-02, are capped by it).
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from ..contracts.common import LOD, CallClass, Lane

TIERS: dict[int, dict] = {
    1: {"depth": "quick", "focus": 0, "mandatory_focus": False, "minds": False},
    2: {"depth": "quick", "focus": 1, "mandatory_focus": True, "minds": False},
    3: {"depth": "balanced", "focus": 2, "mandatory_focus": False, "minds": True},
    4: {"depth": "deep", "focus": 3, "mandatory_focus": False, "minds": True},
    5: {"depth": "deep", "focus": 4, "mandatory_focus": False, "minds": True},
}

AUDIT, AMBIENT, WAVES = 1, 2, 3
MIND, FOCUS, JUDGE = 10_000, 20_000, 30_000

LABELS: dict[str, str] = {
    "intake": "reading your move",
    "write": "writing the turn",
    "judge": "the second reading of the prose",
    "ambient": "the room's remarks",
    "audit:portrayal": "the check that people acted like themselves",
    "waves:2+": "the room's further reactions",
    "mind": "people deciding",
    "mind_optional": "people around you deciding for themselves",
    "focus": "people in their own full voice",
}


def _think(regime) -> str:
    return "full" if regime.thinking else "off"


def turn_steps(config: Any, depth: str) -> list[dict]:
    """HOST-06: the steps every turn declares when it starts."""
    from .work import ANSWER_TOKENS
    R, S, P = config.regimes, config.rules.scheduler, config.rules.packet
    warm = P.token_budget.get("warm", 6000)
    return [
        {"id": "intake", "label": LABELS["intake"], "required": True,
         "est": {"calls": 1, "answerTokens": R[CallClass.INTAKE].max_tokens, "think": _think(R[CallClass.INTAKE]),
                 "promptTokens": warm}},
        {"id": "write", "label": LABELS["write"], "required": True,
         "est": {"calls": 1, "answerTokens": ANSWER_TOKENS[CallClass.NARRATION], "think": "main", "promptTokens": 3000}},
        {"id": "judge", "label": LABELS["judge"], "drop": JUDGE,
         "est": {"calls": 1, "answerTokens": ANSWER_TOKENS[CallClass.RENDER_LINT],
                 "think": _think(R[CallClass.RENDER_LINT]), "promptTokens": 3000}},
        {"id": "ambient", "label": LABELS["ambient"], "drop": AMBIENT,
         "est": {"calls": max(1, S.max_ambient.get(depth, 1)), "answerTokens": R[CallClass.AMBIENT_LINE].max_tokens,
                 "think": "off", "promptTokens": 1500}},
        {"id": "audit:portrayal", "label": LABELS["audit:portrayal"], "drop": AUDIT,
         "est": {"calls": 2, "answerTokens": ANSWER_TOKENS[CallClass.PORTRAYAL_AUDIT],
                 "think": _think(R[CallClass.PORTRAYAL_AUDIT]), "promptTokens": warm}},
        {"id": "waves:2+", "label": LABELS["waves:2+"], "drop": WAVES,
         "est": {"calls": 3, "answerTokens": R[CallClass.ACTOR_REACTION].max_tokens,
                 "think": _think(R[CallClass.ACTOR_REACTION]), "promptTokens": P.token_budget.get("reaction", 3000)}},
    ]


def _order(candidates):
    mand = sorted([c for c in candidates if c[2]], key=lambda c: (-c[1], c[0]))
    rest = sorted([c for c in candidates if not c[2]], key=lambda c: (-c[1], c[0]))
    return mand + rest


def _rank(base: int, wave: int, k: int) -> int:
    return base + (9 - min(wave, 9)) * 1000 + min(k, 999)


class Governor:
    """Answers may(step) for one hosted turn. Subclasses say where answers come from."""

    def __init__(self, tier: int = 3, focus: int | None = None):
        self.tier = tier if tier in TIERS else 3
        shape = TIERS[self.tier]
        self.depth: str = shape["depth"]
        self.focus: int = shape["focus"] if focus is None else max(0, int(focus))
        self.decisions: dict[str, bool] = {}
        self.plan_steps: dict[str, bool] = {}     # the steps the latest plan_cognition asked about (HOST-08)
        self._steps: dict[str, str] = {}          # actor -> its step in the latest planned wave

    async def declare(self, steps: list[dict]) -> None:
        return None

    async def _ask(self, step: str) -> bool:
        return True

    async def may(self, step: str) -> bool:
        if step in self.decisions:              # HOST-08: asked again (a strict retry) -> the first answer
            ok = self.decisions[step]
        else:
            ok = bool(await self._ask(step))
            self.decisions[step] = ok
        self.plan_steps[step] = ok
        return ok

    def step_for(self, actor_id: str | None) -> str | None:
        return self._steps.get(actor_id) if actor_id else None

    async def start_turn(self, config: Any) -> None:
        await self.declare(turn_steps(config, self.depth))

    async def plan_cognition(self, candidates: list[tuple[str, float, bool]], config: Any, wave: int,
                             lanes_up: set) -> Any:
        """HOST-07."""
        from ..lanes.scheduler import CognitionPlan
        S, R, P = config.rules.scheduler, config.regimes, config.rules.packet
        shape = TIERS[self.tier]
        self.plan_steps = {}
        plan = CognitionPlan()
        order = _order(candidates)
        plan.order = [a for a, _s, _m in order]
        if not lanes_up:
            for a, _s, _m in order:
                plan.lod[a] = LOD.COLD
            plan.notes.append("NO_LANES")
            return plan
        hot_lane, warm_lane = config.hot_cognition.lane, R[CallClass.ACTOR_COGNITION].lane
        reg_hot = config.hot_cognition
        reg_warm = R[CallClass.ACTOR_REACTION] if wave > 0 else R[CallClass.ACTOR_COGNITION]
        prompt = P.token_budget.get("reaction" if wave > 0 else "warm", 6000)
        # who could be in focus, and who could think for themselves in the background
        hot_cands = []
        for a, sal, mand in order[: self.focus]:
            if shape["mandatory_focus"] and not mand:
                break
            if not mand and sal < S.hot_min_salience:          # D-175
                break
            hot_cands.append((a, sal, mand))
        warm_cands = []                 # everyone not mandatory who could decide for themselves — a person
        for a, sal, mand in order:      # refused full voice included, who can still do so in the background
            if mand:
                continue
            if sal <= 0 or not shape["minds"]:                 # D-190; tiers 1 and 2
                break
            warm_cands.append((a, sal, mand))
        steps = []
        n = len(hot_cands)
        for k, (a, _sal, _mand) in enumerate(hot_cands):
            steps.append({"id": f"focus:{wave}:{a}", "label": LABELS["focus"], "drop": _rank(FOCUS, wave, n - 1 - k),
                          "est": {"calls": 1, "answerTokens": reg_hot.max_tokens, "think": _think(reg_hot),
                                  "promptTokens": P.token_budget.get("hot", 6000)}})
        for a, _sal, mand in order:
            if mand:
                steps.append({"id": f"mind:{wave}:{a}", "label": LABELS["mind"], "required": True,
                              "est": {"calls": 1, "answerTokens": reg_warm.max_tokens, "think": _think(reg_warm),
                                      "promptTokens": prompt}})
        n = len(warm_cands)
        for k, (a, _sal, _mand) in enumerate(warm_cands):
            steps.append({"id": f"mind:{wave}:{a}", "label": LABELS["mind_optional"], "drop": _rank(MIND, wave, n - 1 - k),
                          "est": {"calls": 1, "answerTokens": reg_warm.max_tokens, "think": _think(reg_warm),
                                  "promptTokens": prompt}})
        if steps:
            await self.declare(steps)
        waves_ok = True if wave < 2 else await self.may("waves:2+")
        # 1. in focus (a late wave the host refused keeps only the mandatory minds)
        for a, _sal, mand in hot_cands:
            if not waves_ok and not mand:
                break
            if not await self.may(f"focus:{wave}:{a}"):
                break
            plan.lod[a] = LOD.HOT
            plan.lane[a] = hot_lane
        # 2. everyone else
        warm_ok = {a for a, _s, _m in warm_cands}
        cold = False
        for a, sal, mand in order:
            if a in plan.lod:
                continue
            if mand:
                plan.lod[a] = LOD.WARM
                plan.lane[a] = warm_lane
                continue
            if cold or a not in warm_ok or not waves_ok:
                cold = True
                plan.lod[a] = LOD.COLD
                continue
            if not await self.may(f"mind:{wave}:{a}"):
                cold = True
                plan.lod[a] = LOD.COLD
                continue
            plan.lod[a] = LOD.WARM
            plan.lane[a] = warm_lane
        self._steps = {a: (f"focus:{wave}:{a}" if plan.lod[a] == LOD.HOT else f"mind:{wave}:{a}")
                       for a in plan.lod if plan.lod[a] != LOD.COLD}
        return plan


class LinkGovernor(Governor):
    """A live turn: declare and may go to the host over the bridge link (``ask(type, payload)``).
    ``recorded`` (a turn played again after a crash) answers first, so the turn plans exactly as it did."""

    def __init__(self, ask: Callable[[str, dict], Awaitable[dict]], *, tier: int = 3, focus: int | None = None,
                 recorded: dict[str, bool] | None = None):
        super().__init__(tier, focus)
        self._link = ask
        self._recorded = dict(recorded or {})

    async def declare(self, steps: list[dict]) -> None:
        await self._link("budget.declare", {"steps": steps})

    async def _ask(self, step: str) -> bool:
        if step in self._recorded:
            return self._recorded[step]
        r = await self._link("budget.may", {"step": step})
        return bool(r.get("may", True))


class RecordedGovernor(Governor):
    """A replay (a fork, HOST-08): the answers the original turn got, read from its stage-4 ledger.
    A step it never asked about answers True (a replay that diverged fails on its state hash)."""

    def __init__(self, recorded: dict[str, bool], *, tier: int = 3, focus: int | None = None):
        super().__init__(tier, focus)
        self._recorded = dict(recorded)

    async def _ask(self, step: str) -> bool:
        return self._recorded.get(step, True)
