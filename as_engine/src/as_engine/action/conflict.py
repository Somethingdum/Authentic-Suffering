"""Contested resources (P5). Rules CONFLICT-01..05. docs/as/07_RULES.md §Conflict.

Time decides most contests: every action lands at its own land_at and later landings see the
world earlier ones left (action.resolve). A CONFLICT is two or more intents of one wave that
touch the same RESOURCE and land at the same millisecond — only then does the precedence ladder
order them. The same resource sets also feed stage 4 (the 'in_conflict' salience flag and the
mandatory rule "contests a resource with the PC's intent").

resources_of(intent) -> list[tuple[str, str]], each resource once, in this order:
  ('body', target_id)       when the target is a body (any def)
  ('object', item_id)       the bound item; and ('object', target_id) when the target is an item
  ('portal', target_id)     when the target is a portal
  ('route', f'{from_place}|{to_place}')  move_through_portal / leave_place / flee: the actor's place
                            and the far side (place ids sorted, joined by '|'); leave_place / flee
                            use the portal their landing would take — computed by the handler, so
                            here: the actor's place and '*'
  ('anchor', destination_id) for move / take_cover / hide to an anchor with cover >= 1 or
                            concealment >= 1 (a hiding place holds one body well)
  ('task_window', task_id)  keep_working (the actor's active task)
  ('line', target_id)       ranged attacks (tag 'ranged') — in addition to ('body', target_id)
  Resources are ENUMERATED, never inferred: nothing else counts.
form_groups(intents) -> (groups, uncontested)
  A group per resource touched by 2+ intents (group.members in actor_id order); an intent may be
  in several groups. uncontested = intents in no group. Groups sorted by resource tuple.
precedence(tx, members, land_at) -> list[Intent]   the ladder, first = lands first:
  1 in progress: the def is keep_working, or the actor already grips the target (grips row)
  2 earlier ACTION_START (they all started at the wave time: skipped within a wave; kept for the
    ACTION_LAND queue which carries older starts)
  3 established control of the resource: the actor holds the item / grips the body / stands at
    the anchor already
  4 shorter distance to the resource (space.point_distance to a body; to the item's or portal's
    or anchor's point otherwise)
  5 capability: higher attr_mod of the def's check attribute (A when the def has no check)
  6 one seeded tie draw per remaining tie: rng.shuffle(tx, 'resolve', f'ladder:{resource}',
    [actor ids sorted]) — pass the rng in; the order of the shuffled list decides.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..kernel.rng import Rng
    from ..kernel.store import Tx
    from .intent import Intent


@dataclass
class ConflictGroup:
    resource: tuple[str, str]
    members: list["Intent"] = field(default_factory=list)


def resources_of(tx: "Tx", intent: "Intent") -> list[tuple[str, str]]:
    raise NotImplementedError("P5")


def form_groups(tx: "Tx", intents: list["Intent"]) -> tuple[list[ConflictGroup], list["Intent"]]:
    """Returns (groups, uncontested intents)."""
    raise NotImplementedError("P5")


def precedence(tx: "Tx", rng: "Rng", resource: tuple[str, str], members: list["Intent"],
               land_at: int) -> list["Intent"]:
    raise NotImplementedError("P5")
