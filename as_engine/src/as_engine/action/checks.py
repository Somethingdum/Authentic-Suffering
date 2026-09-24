"""The one universal check (P5). Rules CHECK-01..06. docs/as/07_RULES.md §Checks.

TARGET = clamp(attr_mod(attribute) + skill_rank + tag_bonus + situation + scale
               - impairment // 2 - resistance, target_min=1, target_max=9)
  attr_mod: contracts.common.attr_mod (1-2:1, 3-4:2, 5-6:3, 7-8:4, 9-10:5)
  skill_rank: 0..3 from the dossier (absent domain = 0)
  tag_bonus: +2 when ANY of the actor's capability tags is listed in CheckSpec.tags (never stacks)
  situation: -3..+3 from situational modifiers (light, cover, haste, footing; 07_RULES.md table)
  scale: -2..+2 (numbers/size)
  resistance: 0..6 from the resistance key (e.g. portal.lock_quality, portal.barricade,
              target attribute modifier for opposed-by-body, fence height class)
draw = rng.d10(stream='resolve', purpose=f'check:{actor_id}:{def_id}')
MARGIN = TARGET - draw
  margin >= 3 CLEAN ; 0..2 COST ; -1..-2 FAIL ; <= -3 BREAK    (CheckRules)
No free miss (CHECK-04): a failed roll never causes harm by itself; harm only comes from another
committed action or a hazard. Identity is never rolled (L7, CHECK-05): consent, loyalty, values,
moral limits and identity are not check outcomes — only affordances whose CheckSpec exists roll.

Opposed checks (CHECK-06): both sides draw (actor first, then opponent, in precedence order); each
computes its own margin; higher margin wins; |difference| >= 3 clean win, 1..2 winner pays a
causal cost, 0 -> established control, then the precedence ladder, then ONE tie draw
(rng 'resolve', purpose 'tie:<a>:<b>', n=2: 1 -> first). Passive material never draws.

Stealth6 ladder (CHECK-07) for perception-class checks (consequence_ladder 'stealth6'), by the
hider's margin: >=5 ghost_protocol, 3..4 unseen_passage, 1..2 fleeting_suspicion,
0 heightened_suspicion, -1..-2 detected, <=-3 compromised_with_prejudice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..contracts.common import CheckBand

if TYPE_CHECKING:
    from ..contracts.content import CheckSpec
    from ..contracts.settings import CheckRules
    from ..kernel.rng import Rng
    from ..kernel.store import Tx


@dataclass(frozen=True)
class CheckResult:
    target: int
    draw: int
    margin: int
    band: CheckBand
    components: dict[str, int]


def compute_target(attr_value: int, skill_rank: int, has_tag: bool, situation: int, scale: int,
                   impairment: int, resistance: int, rules: "CheckRules") -> int:
    raise NotImplementedError("P5")


def band_for_margin(margin: int, rules: "CheckRules") -> CheckBand:
    raise NotImplementedError("P5")


def stealth6(margin: int) -> str:
    raise NotImplementedError("P5")


def roll(tx: "Tx", rng: "Rng", actor_id: str, def_id: str, spec: "CheckSpec", *, situation: int,
         resistance: int, scale: int = 0, at: int, turn_index: int,
         cause_event_id: str | None = None) -> CheckResult:
    """Inputs for actor_id: attr_value = bodies.special[spec.attribute]; skill_rank = the fused
    dossier's rank in spec.skill (0 when absent, when spec.skill is None, or when the body has no
    actors row — infected and animals are untrained at everything); has_tag = any dossier
    capability tag in spec.tags; impairment = bodies.impairment. TARGET per the formula with
    tx.rules.checks; draw = rng.d10(tx, 'resolve', f'check:{actor_id}:{def_id}'); band =
    band_for_margin, or for consequence_ladder 'stealth6' still band_for_margin (the ladder word
    is stealth6(margin), in the payload). Commits CHECK_RESOLVED (writer 'action.resolve', no
    writes, actor_id = actor_id, at, cause) with payload {actor_id, def_id, attribute, attr_value,
    skill, skill_rank, tag_bonus, situation, scale, impairment, resistance, target, draw, margin,
    band, ladder (stealth6 word or null)}. CheckResult.components = {attr_mod, skill_rank,
    tag_bonus, situation, scale, impairment_penalty (= impairment // 2), resistance}."""
    raise NotImplementedError("P5")


def opposed(tx: "Tx", rng: "Rng", a_id: str, a_spec: "CheckSpec", b_id: str, b_spec: "CheckSpec",
            *, def_id: str, a_situation: int, b_situation: int, at: int, turn_index: int,
            cause_event_id: str | None = None,
            established_control: str | None = None) -> tuple[str, CheckResult, CheckResult, str]:
    """Both sides roll() with resistance 0: the attacker a first (def_id), then the defender b
    (def_id + ':defend'). Higher margin wins: |difference| >= 3 -> how 'clean'; 1..2 -> 'cost';
    equal margins -> the established_control body wins ('control') when it is a or b; else the
    higher attr_mod of each side's check attribute wins ('ladder'); else ONE tie draw
    rng.draw(tx, 'resolve', f'tie:{a_id}:{b_id}', 2): 1 -> a ('tie'). Returns (winner_id, a_result,
    b_result, how). The defender's spec is usually CheckSpec(attribute=a_spec.opposed_attribute,
    skill=a_spec.opposed_skill) — built by the caller."""
    raise NotImplementedError("P5")
